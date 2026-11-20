"""plan_conversation: the conversation front (MCP-28). One call for every request to make or change media.

Flow (user, 2026-11-19): guess the intent, pick the family, fill the family's sheet from the user's words and files,
apply the implied defaults, ask what is still open in ONE batch, then hand back the refined plan.

- The seven tool families come from question_sheets.json and tool_notes.json (William's data). The sheet check is
  tool_plan.plan(); plan_tool_call itself stays unregistered (MCP-TOOLS-23, William, later).
- The film family (several clips, a story, an ad, a reel) is this module's own sheet. A ready film plan goes to
  plan_video_production.
- Required files: each family names the files it needs. A missing file is asked in the same batch.
- Media facts: each attached file with a file_path is read by code (length, size, sound), so a trim or a "whole clip"
  uses exact seconds (user, 2026-11-19, fix 2).

Switch: MAGIC_HOUR_CONVERSATION=on registers plan_conversation and leaves plan_request out. Read-only, no credits.
"""
from __future__ import annotations

import asyncio
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from . import tool_plan
from .video_production import ROUTING_RULE

ASK, YOUR_CALL, NOT_APPLICABLE = tool_plan.ASK, tool_plan.YOUR_CALL, tool_plan.NOT_APPLICABLE
Family = Literal["new_picture", "change_picture", "faces", "change_video", "new_video", "talking", "sound", "film"]


def enabled() -> bool:
    return os.getenv("MAGIC_HOUR_CONVERSATION", "off").strip().lower() in ("on", "1", "true")


# Rules every family follows (user, 2026-11-19).
IMPLIED = [
    "Every video has the natural sound of its scene (audio on) unless the user asks for silence. Do not ask about it.",
    "Captions on a video, when there are captions: white letters with a black outline. Do not ask about the style.",
    "Derive what the words imply (TikTok, Reels, Shorts, a story = 9:16; YouTube, a website = 16:9; Instagram post = 1:1). "
    "Do not ask what the words already answer.",
    "Ask all open questions in ONE message, once. Anything still open after the answer takes its default; tell the user.",
]

# Tools the default server lists without tool management (tool_media.py) switched on.
TOOL_MEDIA = {"add_sound_to_video", "adjust_colours", "put_pictures_side_by_side", "put_picture_on_video", "make_card_clip"}

# Tools no family sheet lists yet (no tool notes yet either). Each goes to a family, with the files it needs.
EXTRA_TOOLS = {
    "faces": {
        "change_clothes_in_photo": "New clothes on a person in a photo. Needs the person's photo, and the outfit as a picture or words.",
        "place_person_in_scene": "Put the person from one photo into another scene (body swap). Needs the person's photo and the scene picture.",
        "replace_character_in_video": "Replace a person in a video with the person from a photo. Needs the video and the photo.",
    },
    "change_video": {
        "translate_video": "The video's speech in another language, with the same voice. Needs the video and the language.",
        "create_video_from_image": "Extend a clip: the last frame (get_last_frame) animated, then join_videos.",
    },
    "new_video": {
        "create_video_from_audio": "A video made for a song or a sound file. Needs the audio file.",
    },
    "talking": {
        "create_lip_sync_video": "A person in a video mouths a sound file (a song or a voice). Needs the video and the audio.",
    },
    "sound": {
        "ai_voice_cloner_create_audio": "Words read in the user's own voice. Needs a voice sample (a sound file of the user speaking).",
    },
}

# The files each family needs: (what, kinds, when). `when` names the case; the host decides if it applies.
FILES = {
    "change_picture": [("the picture to change", ("image",), "always")],
    "faces": [("the photo with the face, head or person to use", ("image",), "always"),
              ("the photo or video it goes onto (for a headshot: none)", ("image", "video"), "a swap, clothes, a scene, a character replace")],
    "change_video": [("the video to change", ("video",), "always")],
    "new_video": [("the picture to animate", ("image",), "the user asks to animate their picture")],
    "talking": [("the photo or video of the person who speaks", ("image", "video"), "always"),
                ("the sound file to mouth", ("audio",), "a song, or the user's own recording")],
    "sound": [("a sample of the user's voice", ("audio",), "the user's own voice")],
    "film": [("the product photo", ("image",), "a real product or brand is shown")],
}

FILM_ROWS = [
    {"id": "kind", "kind": "deciding", "ask": "(Read from the words.) What kind of film?",
     "answers": {"ad": "Hook in the first 3 s, the selling points, the call to action at the end. Music on.",
                 "someone_speaks": "An interview, a talking head, a demo, people talking: one spoken line per beat.",
                 "explainer_list": "One step or one point per beat, in order; labels as words on screen or a card.",
                 "story_mood": "A story or a mood piece: the same people and place words in every beat."},
     "default": "story_mood."},
    {"id": "purpose", "kind": "deciding", "ask": "Who is it for, and what should it make them do?",
     "answers": {"stated": "Use it for the hook and the close.", "none": "A general audience."},
     "default": "Read from the words; else a general audience.",
     "ask_when": "an ad or a promo with no audience in the words"},
    {"id": "shape", "kind": "required", "ask": "Where will it be posted (TikTok, Instagram, YouTube, a website)?",
     "answers": {"9:16": "TikTok, Reels, Shorts, a story.", "16:9": "YouTube, a website, a presentation.", "1:1": "An Instagram post."},
     "default": "9:16 for social video, else 16:9."},
    {"id": "length", "kind": "required", "ask": "About how long, in seconds?",
     "answers": {"seconds": "Fill it with the story; no stretching, no pauses."}, "default": "15 s (a reel); 30 s for an explainer."},
    {"id": "who_speaks", "kind": "deciding", "ask": "Should anyone talk: a voice-over, a person on camera, people talking to each other, or no one?",
     "answers": {"nobody": "Silent (audio off) only when the user asked for silence; else scene sound.",
                 "scene_sound": "Audio on, no spoken lines.",
                 "narrator": "A voice-over (the voice cloner reads `narrator`; the user's own voice when they give a sample).",
                 "one_on_screen": "One person says the lines on camera: each line in its own short beat (`spoken`).",
                 "people_talking": "Each speaker's line in its own beat, in order."},
     "default": "Read from the words; else scene_sound.", "ask_when": "the words want speech but do not say who speaks"},
    {"id": "sound", "kind": "required", "ask": "(Implied.) Natural sound of the scene.",
     "answers": {"on": "Audio on in every clip.", "silent": "Only when the user asked for silence."}, "default": "on."},
    {"id": "music", "kind": "deciding", "ask": "(Implied.) Music under the film?",
     "answers": {"yes": "One music track at the join, none inside the clips.", "no": "No music."},
     "default": "Yes for an ad, a reel or a social post; else no."},
    {"id": "captions", "kind": "deciding", "ask": "(Implied.) Captions of the spoken words?",
     "answers": {"yes": "White letters, black outline.", "no": "No captions."},
     "default": "Yes when someone speaks in a social video (TikTok, Reels, Shorts, an ad); else no. Tell the user."},
    {"id": "exact_words", "kind": "deciding", "ask": "Any words that must appear on screen (a title, a price, a website), spelled exactly?",
     "answers": {"none": "No words on screen.", "exact words": "Exactly as the user wrote them, by code or on a card."},
     "default": "None. Never invent a price, a date or a web address.", "ask_when": "an ad or a promo with no call-to-action words"},
    {"id": "product_picture", "kind": "deciding", "ask": "Do you have a photo of the product? A film made from words only looks like it.",
     "answers": {"photo": "Use it as the product's picture in every clip that shows it.", "words": "Make it from words; tell the user it is a look-alike."},
     "default": "words.", "ask_when": "a real product or brand is shown and no photo is attached"},
]

STORY_RULES = [
    "No story from the user: write one. Hook in the first 3 s (the main point or the most striking image), then the body, then the close; an ad ends on the call to action.",
    "Fill the length with the story. No dead air: every second has an action or a line. A spoken line is 2.5 words a second on screen (2.7 for a voice-over); at most 3 s idle after a line.",
    "One action per beat. A spoken line gets its own short beat. A change of state is one beat per stage.",
    "No time skip on a beat that continues from the clip before (`continues`, `event`): a new time of day is a new shot (`new`).",
    "The setting is true of every clip. The same subject words in every beat. A real product uses its photo.",
    "No talking verb in the beat text; the words go in `spoken`.",
    "Natural sound on; no music inside a clip; one music track at the join.",
    "Exact words on screen go in the story's words fields (drawn by code or on a card), never in the clip prompt.",
    "Keep every concrete detail the user gave word for word (counts, colours, names, exact words).",
    "Avoid what the video model does badly: two places in one clip, small letters, a colour code, a person partly off screen.",
]


def _available(tool: str) -> bool:
    return tool_plan.enabled() or tool not in TOOL_MEDIA


# A file whose `when` is not "always" is still required when the request's words name its case.
NEEDED_WHEN = {
    "a swap, clothes, a scene, a character replace": r"swap|onto|\bon (?:the|this|my)\b|put|replace|clothes|outfit|wear|scene|into",
    "the user asks to animate their picture": r"\b(?:this|my) (?:photo|pic|picture|image)|animate (?:this|my)",
    "a song, or the user's own recording": r"\bsong|sing|my (?:recording|audio|track)|lip.?sync",
    "the user's own voice": r"\bmy (?:own )?voice|in my voice|sounds? like me|clone",
}


def _files(family: str, attachments: list[dict], request: str = "") -> dict:
    need = [{"what": w, "kinds": list(k), "when": ("always" if when == "always" or re.search(NEEDED_WHEN.get(when, r"(?!)"), request, re.I) else when)}
            for w, k, when in FILES.get(family, [])]
    if family == "faces" and re.search(r"headshot", request, re.I):
        need = need[:1]
    given = [{"name": a["name"], "kind": a["kind"]} for a in attachments]
    kinds = [a["kind"] for a in attachments]
    missing = []
    for n in need:
        if n["when"] == "always" and not any(k in n["kinds"] for k in kinds):
            missing.append(n["what"])
        elif n["when"] == "always":
            kinds.remove(next(k for k in kinds if k in n["kinds"]))
    checks = ["Before a paid call, check each file: it is the kind the tool takes (photo, video, sound)."]
    if family in ("faces", "talking"):
        checks.append("Call detect_faces on each photo or video with a face (free) and check the face count; "
                      "with more than one face, ask which person (in the same batch).")
    return {"needed": need, "given": given, "missing": missing, "checks": checks}


SILENCE = r"\b(?:silent|silence|no sound|no audio|mute[d]?|without sound|sound off)\b"
OPTION_ROWS = ("kind", "who_speaks", "sound", "music", "captions", "product_picture")


def _film(request: str, answers: dict[str, str] | None, questions_asked: bool, files: dict) -> dict:
    rows = {r["id"]: r for r in FILM_ROWS}
    view = [{"id": r["id"], "kind": r["kind"], "ask": r["ask"], "options": list(r["answers"]), "default": r["default"],
             **({"ask_when": r["ask_when"]} if "ask_when" in r else {})} for r in FILM_ROWS]
    if answers is None:
        return {"ready": False, "stage": "fill_the_sheet", "family": "film", "rows": view, "implied": IMPLIED,
                "files": files, "next": "Fill `answers` for every row, then call again."}
    unknown = [k for k in answers if k not in rows]
    if unknown:
        raise ToolError(f"Unknown film rows: {', '.join(unknown)}. Rows: {', '.join(rows)}.")
    implied = [i for i, r in rows.items() if r["ask"].startswith("(Implied") and answers.get(i) == ASK]
    if implied:
        raise ToolError(f"Do not ask about {', '.join(implied)}: implied (user, 2026-11-19). Use the default unless the user's words say otherwise.")
    open_rows = [r for i, r in rows.items() if answers.get(i) == ASK]
    file_qs = [{"id": "file", "ask": f"Please attach {m}.", "if_skipped": "I cannot make it without this file."} for m in files["missing"]]
    if (open_rows or file_qs) and not questions_asked:
        return {"ready": False, "stage": "ask_the_user", "family": "film",
                "questions": [{"id": r["id"], "ask": r["ask"], "if_skipped": r["default"]} for r in open_rows] + file_qs,
                "next": ("Ask the user ALL these questions in ONE message, numbered, in plain words, each with what happens if "
                         "they skip it. This is the only time the user is asked. Then call again with their answers and "
                         "questions_asked=true.")}
    # Sound is on unless the user's own words ask for silence (user, 2026-11-19). "No talking" or "music only" is not silence.
    silent = bool(re.search(SILENCE, request))
    notes = []
    if answers.get("sound") not in (None, "on", "silent", YOUR_CALL, ASK) or (answers.get("sound") == "silent" and not silent):
        notes.append(f"sound {answers['sound']!r} became 'on': the user's words do not ask for silence.")
        answers = {**answers, "sound": "on"}
    if answers.get("who_speaks") == "nobody" and not silent:
        notes.append("who_speaks 'nobody' became 'scene_sound': no spoken lines, but the scene's natural sound stays on.")
        answers = {**answers, "who_speaks": "scene_sound"}
    bad = [f"{i}={v!r}" for i, v in answers.items() if i in OPTION_ROWS and v not in (ASK, YOUR_CALL, NOT_APPLICABLE) and v not in rows[i]["answers"]]
    if bad:
        raise ToolError(f"Not an option: {', '.join(bad)}. " + "; ".join(f"{i}: {', '.join(rows[i]['answers'])}" for i in OPTION_ROWS))
    decisions = []
    for i, r in rows.items():
        value = answers.get(i, YOUR_CALL)
        if value in (ASK, YOUR_CALL):
            decisions.append({"id": i, "value": r["default"]})
        elif value != NOT_APPLICABLE:
            decisions.append({"id": i, "value": value, "instruction": r["answers"].get(value, "")})
    return {"ready": True, "stage": "plan", "family": "film", "request": request, "decisions": decisions,
            "story_rules": STORY_RULES, "implied": IMPLIED, "files": files, **({"changed": notes} if notes else {}),
            "next": ("Write the story from the decisions and the story rules, then call plan_video_production with it. "
                     + ("The story's `audio` is true (natural sound in every clip)." if not silent else "The story's `audio` is false (the user asked for silence)."))}


# A video request that states no length and no single action may want a longer film (user, 2026-11-19, fix 6): check once.
LENGTH_OR_ONE_ACTION = (r"\b\d+(?:[.,]\d+)?\s*(?:-\s*)?(?:s|sec|secs|seconds?|minutes?|mins?)\b|\bclip\b|\bgif\b|\bloop|\banimate|\bbring .* to life"
                        r"|\bas long as\b|\bsame length\b|\b(?:whole|full|entire) (?:song|track|clip|video)\b"
                        r"|\b(?:pic|photo|picture|image)s?\b.{0,20}\bmove|\banimation\b")
SHORT_OR_FILM = {"id": "short_or_film", "ask": "One short clip, or a longer film (a story, an ad, for a set audience)?",
                 "if_skipped": "One short clip."}
SHAPES = {"16:9": 16 / 9, "9:16": 9 / 16, "1:1": 1.0, "4:5": 4 / 5, "5:4": 5 / 4, "4:3": 4 / 3, "3:4": 3 / 4, "21:9": 21 / 9}


def _shape(w: int, h: int) -> str:
    if not w or not h:
        return ""
    name, ratio = min(SHAPES.items(), key=lambda kv: abs(kv[1] - w / h))
    return name if abs(ratio - w / h) / ratio < 0.04 else f"{w}:{h}"


_MEDIA_CACHE: dict[str, dict] = {}


async def media_facts(attachments: list[dict]) -> list[dict]:
    """Length, size, shape and sound of each attached file with a file_path, read by code (free). Never fails the plan."""
    from . import media_helpers_tool, media_tools

    out = []
    for a in attachments:
        fp = a.get("file_path")
        if not fp or a.get("kind") == "text":
            continue
        if fp not in _MEDIA_CACHE:
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    file, picture = await media_helpers_tool._fetch_media(fp, Path(tmp), ("image", "video", "audio"))
                    if picture:
                        from PIL import Image

                        w, h = Image.open(file).size
                        fact = {"kind": "image", "width": w, "height": h, "shape": _shape(w, h)}
                    else:
                        info = await asyncio.to_thread(media_tools.probe, file)
                        fact = {"kind": "video" if info["width"] else "audio", "seconds": round(info["seconds"], 2)}
                        if info["width"]:
                            fact |= {"width": info["width"], "height": info["height"], "shape": _shape(info["width"], info["height"]),
                                     "has_sound": info["audio"]}
                _MEDIA_CACHE[fp] = fact
            except Exception as e:  # a file the server cannot read: the plan goes on without its facts
                _MEDIA_CACHE[fp] = {"error": f"could not read the file ({type(e).__name__})"}
        out.append({"name": a["name"], **_MEDIA_CACHE[fp]})
    return out


MEDIA_NEXT = (" Media facts (`media`) are read from the files: use their exact seconds and shape. A whole clip is 0 to its "
              "seconds; never guess a length.")


def front(family: str, request: str, answers: dict[str, str] | None = None, questions_asked: bool = False,
          attachments: list[dict] | None = None, media: list[dict] | None = None) -> dict:
    attachments = attachments or []
    files = _files(family, attachments, request)
    if family == "film":
        out = _film(request, answers, questions_asked, files)
        if media:
            out["media"] = media
            out["next"] = out.get("next", "") + MEDIA_NEXT
        return out
    changed = []
    short_or_film = (answers or {}).get(SHORT_OR_FILM["id"])
    if short_or_film is not None:   # the user's answer to the "short or longer?" check, not a sheet row
        answers = {k: v for k, v in answers.items() if k != SHORT_OR_FILM["id"]}
        if re.search(r"\b(?:long|longer|film|story|ad|several)\b", str(short_or_film), re.I):
            return {"ready": False, "stage": "switch_family", "family": family,
                    "next": "The user wants a longer film: call plan_conversation again with family film and the same request."}
    if family == "new_video" and answers and answers.get("sound") == "silent" and not re.search(SILENCE, request):
        answers = {**answers, "sound": "sound"}
        changed.append("sound 'silent' became 'sound': the user's words do not ask for silence (user, 2026-11-19).")
    out = tool_plan.plan(family, request, answers, questions_asked)
    if changed:
        out["changed"] = changed
    extra = {t: d for t, d in EXTRA_TOOLS.get(family, {}).items() if _available(t)}
    out["implied"] = IMPLIED
    out["files"] = files
    if extra:
        out["more_tools"] = extra
    if "tools" in out:
        out["tools"] = {t: n for t, n in out["tools"].items() if _available(t)}
        out["unavailable"] = sorted(t for t in tool_plan.sheets()["families"][family]["tools"] if not _available(t))
    file_qs = [{"id": "file", "ask": f"Please attach {m}.", "if_skipped": "I cannot make it without this file."} for m in files["missing"]]
    if file_qs and not questions_asked:
        if out.get("stage") == "ask_the_user":
            out["questions"] += file_qs
        elif out.get("stage") == "plan":
            out = {"ready": False, "stage": "ask_the_user", "family": family, "questions": file_qs, "files": files,
                   "next": ("Ask the user for these files in ONE message. Then call again with the same answers, the "
                            "attachments and questions_asked=true.")}
    elif files["missing"] and questions_asked and out.get("stage") == "plan":
        out["ready"] = False
        out["stage"] = "missing_file"
        out["next"] = "A file the request needs is still missing: tell the user plainly and make nothing until they attach it."
    if family == "new_video" and not questions_asked and short_or_film is None and not re.search(LENGTH_OR_ONE_ACTION, request, re.I):
        if out.get("stage") == "ask_the_user":
            out["questions"].append(SHORT_OR_FILM)
        elif out.get("stage") == "plan":
            out = {"ready": False, "stage": "ask_the_user", "family": family, "questions": [SHORT_OR_FILM], "files": files,
                   "next": ("Ask the user this in ONE message, with what happens if they skip it. Then call again with the same "
                            "answers and questions_asked=true. A longer film: call again with family film.")}
    for d in out.get("decisions", []):   # no telling of defaults (user, 2026-11-19)
        d.pop("tell_the_user", None)
    if media:
        out["media"] = media
        out["next"] = out.get("next", "") + MEDIA_NEXT
    return out


def index() -> str:
    film = ", ".join(r["id"] + ("*" if r["ask"].startswith("(") else "")
                     + (f"({'|'.join(r['answers'])})" if r["kind"] == "deciding" else "") for r in FILM_ROWS)
    lines = [tool_plan.sheet_index(), f"film: {film}"]
    for fam, tools in EXTRA_TOOLS.items():
        lines.append(f"{fam} also: {', '.join(tools)}")
    return "\n".join(lines)


class Attachment(BaseModel):
    name: str
    kind: Literal["image", "video", "audio", "text"]
    file_path: str | None = None   # the attachment's Magic Hour file_path or URL: the front reads its length, size and sound


def register_conversation_front(mcp: FastMCP) -> None:
    if not enabled():
        return
    families = "; ".join(f"{k}: {v['is']}" for k, v in tool_plan.sheets()["families"].items())

    @mcp.tool(
        name="plan_conversation",
        title="Plan the request (first call)",
        description=(
            "Call this FIRST for every request to make or change a picture, a video or a sound, before any create or edit "
            "call. Guess what the user wants and pick ONE family. Families: " + families + "; film: several clips, a story, "
            "an ad, a reel, an explainer, an interview, a video with a purpose. " + ROUTING_RULE + " "
            "Send the family, the user's request word for word, the attachments (name, kind and file_path), and `answers` for every "
            "row in ONE call. Rows (* = answer it yourself from the words, the files or the implied rules; options in "
            "brackets):\n" + index() + "\n"
            "Answer a row with an option, the user's own words, 'your_call' (you pick the conventional value for this kind of "
            "request) or 'n/a'. Mark 'ask' ONLY when the answer "
            "would change the result and the user's words and files do not answer it. A vague request that names only the "
            "subject, with no look, setting, colour, shape or words (for example 'make a product pic of a water bottle'): "
            "mark the open rows that would change it 'ask', because the user may have details in mind. Words the result shows or says "
            "(a caption, a spoken line, a slogan) that the user did not give: mark 'ask'; when the user answers 'your call', write "
            "words that fit the request (user, 2026-11-19). Never ask about sound or caption "
            "style (implied). Returns every open question in one batch (ask the user once, all together, then call again "
            "with questions_asked=true), or the plan: tools, free-tier settings, known faults, needed files, and for a "
            "film the story rules for plan_video_production. Read-only; spends no credits and creates nothing."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
    )
    async def plan_conversation(family: Family, request: str, answers: dict[str, str] | None = None,
                                questions_asked: bool = False, attachments: list[Attachment] | None = None) -> dict[str, Any]:
        """questions_asked: true once the user has been asked this plan's questions; nothing is asked again."""
        files = [a.model_dump() for a in attachments or []]
        return front(family, request, answers, questions_asked, files, await media_facts(files))

"""plan_request: check the host's parameter sheet against the user's own words.

The host model fills a sheet (one row per parameter: value and source). This code keeps a value
only when the user gave it or it follows from the user's words, and returns a question from a
fixed set for each value that is still missing. No model, no network, no credits.

Ported from the V4 reference agent (agent/intent.js, agent/questions.js, agent/catalogue.js).
Spec: mcp-upgrade/prd/MCP-01-conversation.md.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

Source = Literal["user", "derived", "default", "missing"]

# The universal question set. One text for each parameter, asked word for word.
QUESTIONS = {
    "aspect": "Where will this be shown or posted (Instagram, TikTok, YouTube, a website, print, somewhere else)?",
    "seconds": "How long should it be?",
    "exact_words": "Should any words appear on it? If so, which, exactly?",
    "sound": "Should it have sound: music, a voice, or silent?",
    "language": "Which language for the voice or captions?",
    "which_face": "Whose face goes where (which person in the picture)?",
    "look": "Any look in mind (realistic, illustrated, a brand colour, a mood)? 'Your call' is fine.",
    "subject": "What should it show?",
    "edit": "What should change in the picture?",
    "keep": "What must stay exactly as it is?",
    "motion": "What should move, and how (small natural motion, a slow push in, something happening)?",
    "mood": "What mood or genre for the music?",
    "script": "What should be said, word for word? Or should I write it from the gist?",
    "range": "Which part should be kept (from when to when, or 'the best 10 seconds')?",
}

# tool: (the parameters it uses, the parameters it cannot run without)
TOOLS: dict[str, tuple[list[str], list[str]]] = {
    "generate_image": (["subject", "aspect", "exact_words", "look"], ["subject", "aspect"]),
    "edit_image": (["edit", "keep", "aspect", "exact_words"], ["edit"]),
    "create_video_from_text": (["subject", "seconds", "aspect", "sound", "exact_words", "look"], ["subject", "seconds", "aspect", "sound"]),
    "create_video_from_image": (["motion", "seconds", "aspect", "sound", "keep"], ["motion", "seconds", "sound"]),
    "generate_music": (["mood", "seconds"], ["mood", "seconds"]),
    "add_subtitles_to_video": (["language"], []),
    "upscale_image": ([], []),
    "remove_image_background": ([], []),
    "swap_face_in_photo": (["which_face"], []),
    "swap_head_in_photo": (["which_face"], []),
    "create_talking_photo": (["script", "language"], ["script"]),
    "trim_video": (["range"], ["range"]),  # no MCP tool yet; kept so a trim request still gets its question
}
ToolName = Literal[
    "generate_image", "edit_image", "create_video_from_text", "create_video_from_image", "generate_music",
    "add_subtitles_to_video", "upscale_image", "remove_image_background", "swap_face_in_photo",
    "swap_head_in_photo", "create_talking_photo", "trim_video",
]

# A host often sends the create tool's own argument names. Each maps to the sheet's name.
ALIASES = {"end_seconds": "seconds", "duration": "seconds", "length": "seconds", "aspect_ratio": "aspect",
           "orientation": "aspect", "shape": "aspect", "audio": "sound", "words": "exact_words", "text": "exact_words"}
PROMPT_NAMES = {"prompt", "style.prompt", "description"}
PROMPT_PARAM = {"generate_image": "subject", "create_video_from_text": "subject", "edit_image": "edit",
                "create_video_from_image": "motion", "generate_music": "mood"}
DEFAULT_ALLOWED = {"look", "position", "transition", "voice", "language", "keep"}
VIDEO_FROM_PICTURE = {"create_video_from_image", "create_talking_photo"}
YOUR_CALL_VALUES = {"aspect": "16:9", "seconds": 10, "sound": "none"}
MAX_QUESTIONS = 3

_I = re.ASCII | re.IGNORECASE
YOUR_CALL = re.compile(r"your call|you decide|whatever|up to you|don'?t care|anything|surprise me|dealer'?s choice", _I)
YOU_WRITE = re.compile(r"you write (them|it)|write (them|it) for me", _I)
DESIGNED_PIECE = re.compile(r"\b(post|poster|flyer|banner|card|ad|advert|announcement|invite|invitation)\b", _I)
DESTINATION = re.compile(r"\b(website|web ?site|web|social|socials|online|site|homepage|ad|advert)\b", _I)
PRINT_WORDS = re.compile(r"\b(poster|flyer|print|a4|letter)\b", _I)
# A file name is not the user's wording: "portrait-woman.jpg" does not ask for a tall picture.
ATTACHED = re.compile(r"\[Attached:[^\]]*\]|\S+\.(?:png|jpe?g|webp|gif|mp4|mov|webm|mp3|wav|m4a)\b", _I)
# An edit is stated when the user's words name a change.
CHANGE_VERB = re.compile(
    r"\b(remove|delete|erase|add|put|place|change|replace|swap|make|turn|fix|clean|brighten|darken|lighten|warm|cool|crop|"
    r"blur|sharpen|colou?r|retouch|convert|extend|fill|move|cut|take out|get rid)", _I)
OPTIONAL_QUIET = {"look", "keep", "language", "exact_words"}  # never asked just because the host left them open
PLATFORMS = [
    (r"tiktok|reels?\b|stories|story\b|\bshorts\b|vertical|portrait (?:video|format|mode|orientation|reel)|in portrait\b|phone", "9:16"),
    (r"youtube|landscape|widescreen|tv\b|wide\b|banner|presentation|desktop", "16:9"),
    (r"instagram post|square|feed|profile pic", "1:1"),
    (r"instagram", "1:1"),
    (r"linkedin|facebook|twitter|\bx\b", "16:9"),
    (r"print|poster|flyer|a4|letter", "9:16"),
]


def parse_aspect(text: str) -> str | None:
    """A shape from plain words ("Instagram story") or an exact ratio ("9:16")."""
    ratio = re.search(r"\b(16:9|9:16|1:1|4:3|3:4|4:5)\b", text, re.ASCII)
    if ratio:
        return {"4:5": "9:16", "3:4": "9:16", "4:3": "16:9"}.get(ratio[1], ratio[1])
    for pattern, value in PLATFORMS:
        if re.search(pattern, text, _I):
            return value
    return None


def parse_seconds(text: str) -> int | None:
    """A length from one message. A bare number counts only in a short answer ("10", "about 15"), never "20% off"."""
    stated = re.search(r"(\d+(?:\.\d+)?)[\s-]*(s\b|sec|seconds?)", text, _I)
    if stated:
        return max(1, int(float(stated[1]) + 0.5))
    bare = re.search(r"\b(\d{1,3})\b(?!\s*%)", text, re.ASCII)
    if bare and len(text.split()) <= 3:
        return max(1, int(bare[1]))
    if re.search(r"half a minute", text, _I):
        return 30
    if re.search(r"minute", text, _I):
        return 60
    if re.search(r"short|quick|brief", text, _I):
        return 8
    if re.search(r"reel|tiktok|story", text, _I):
        return 15
    return None


def parse_sound(text: str) -> str | None:
    """A sound choice from one message. "No music" is not a request for music."""
    if re.search(r"silent|no sound|mute|none|quiet", text, _I):
        return "none"
    text = re.sub(r"\b(no|without)\s+(music|voice-?over|voice|narrat\w*|words?|dialog\w*)\b", " ", text, flags=_I)
    if re.search(r"dialog", text, _I):
        return "dialogue"
    if re.search(r"voice|narrat|speak|talk|say", text, _I):
        return "narration"
    if re.search(r"music|song|beat|track", text, _I):
        return "music"
    if re.search(r"ambient|natural sound|sfx", text, _I):
        return "ambient"
    return None


def _first(parser, texts: list[str]):
    return next((value for value in map(parser, texts) if value is not None), None)


def plan_sheet(messages: list[dict], tool: str, params: list[dict], attachments: list[dict] | None = None) -> dict:
    """Check the sheet. Returns {tool, ready, params, questions}."""
    if tool not in TOOLS:
        raise ValueError(f"Unknown tool: {tool}. Choose one of: {', '.join(TOOLS)}")
    attachments = attachments or []
    uses, required = TOOLS[tool]
    users = [ATTACHED.sub(" ", m["text"]) for m in messages if m["role"] == "user"]
    asked = [m["text"] for m in messages if m["role"] == "assistant"]
    newest, all_user = (users[-1] if users else ""), "\n".join(users)
    your_call = bool(YOUR_CALL.search(newest))

    last_asked = asked[-1] if asked else ""

    def our_call(name: str) -> bool:
        """The user said "your call" in answer to this parameter's question."""
        return your_call and QUESTIONS[name] in last_asked

    sheet: dict[str, dict] = {}
    for p in params:
        name = p["name"]
        name = PROMPT_PARAM.get(tool, name) if name in PROMPT_NAMES else ALIASES.get(name, name)
        value = p.get("value")
        if name == "sound" and isinstance(value, bool):
            value = "ambient" if value else "none"
        if name in uses and name not in sheet:
            sheet[name] = {"name": name, "value": value, "source": p["source"], "from": p.get("from") or ""}
    must_ask: set[str] = set()

    def missing(name: str, ask: bool = False) -> None:
        sheet[name] = {"name": name, "value": None, "source": "missing", "from": ""}
        if ask:
            must_ask.add(name)

    def fill(name: str, value: Any, source: str, why: str) -> None:
        sheet[name] = {"name": name, "value": value, "source": source, "from": why}

    # 1. A row the host left open is asked, except the few that have a safe default. Every required parameter has
    #    a row. A tool that makes a picture or a video always has a shape row (asked only when rule 6 says so).
    must_ask |= {name for name, row in sheet.items() if row["source"] == "missing" and name not in OPTIONAL_QUIET}
    for name in [*required, *(["aspect"] if "aspect" in uses else [])]:
        if name not in sheet:
            missing(name)

    # 2. A default is permitted only for a few parameters, or when the user said it is our call.
    for name, row in list(sheet.items()):
        if row["source"] == "default" and name not in DEFAULT_ALLOWED:
            permitted = our_call(name) or (name == "exact_words" and YOU_WRITE.search(newest))
            if not permitted:
                missing(name, ask=True)

    # 3. Exact words are never invented: they are in the user's messages, or the user let us write them.
    words = sheet.get("exact_words")
    if words and words["source"] != "missing" and words["value"]:
        not_said = words["source"] == "user" and not all(str(w) in all_user for w in words["value"])
        if words["source"] == "derived" or not_said:
            missing("exact_words", ask=True)
    designed = tool == "generate_image" and DESIGNED_PIECE.search(all_user)
    already_asked = any(re.search(r"\bwords?\b", text, _I) for text in asked)
    if designed and not already_asked and not re.search("[\"“”']", all_user):
        missing("exact_words", ask=True)

    # 4. An edit that the user did not state is asked, not assumed. The host's paraphrase of a stated change is kept.
    if tool == "edit_image":
        stated = sheet["edit"]["source"] in ("user", "derived") and CHANGE_VERB.search(all_user)
        if not stated:
            missing("edit", ask=True)

    # 5. Length and sound: kept only when the user's words speak of them; else read from the user's messages, newest first.
    for name, parser in (("seconds", parse_seconds), ("sound", parse_sound)):
        if name not in sheet:
            continue
        if sheet[name]["source"] in ("user", "derived") and _first(parser, users) is None:
            missing(name, ask=True)
        if sheet[name]["source"] == "missing":
            value = _first(parser, users[::-1])
            if value is not None:
                fill(name, value, "derived", "parsed from the user's words")

    # 6. Shape: the user's own words win. Else the picture's own shape, when the output is that picture.
    #    Ask when the picture's shape is not a safe answer.
    if "aspect" in sheet:
        shape_text = PRINT_WORDS.sub("", all_user) if attachments else all_user
        said = parse_aspect(shape_text)
        row = sheet["aspect"]
        if said:
            if not (row["source"] == "user" and row["value"] == said):
                fill("aspect", said, "user", "the user's words")
        elif row["source"] != "default":
            missing("aspect")
            picture = (next((a for a in attachments if a["kind"] == "image" and a.get("aspect")), None)
                       or next((a for a in attachments if a["kind"] == "video" and a.get("aspect")), None))
            if picture and tool not in VIDEO_FROM_PICTURE:
                fill("aspect", picture["aspect"], "derived", f"the shape of {picture['name']}")
            shapes = {a["aspect"] for a in attachments if a.get("aspect")}
            pictures = [a for a in attachments if a["kind"] == "image"]
            unsafe = (tool in VIDEO_FROM_PICTURE or DESTINATION.search(all_user) or len(shapes) > 1
                      or (len(pictures) > 1 and "swap" not in tool))
            if unsafe:
                missing("aspect", ask=True)

    # 7. "Your call" answers a question that was asked. It is not a default for a question that was not.
    open_rows = [name for name in uses if name in sheet and sheet[name]["source"] == "missing"]
    for name in list(open_rows):
        if name in YOUR_CALL_VALUES and our_call(name):
            fill(name, YOUR_CALL_VALUES[name], "default", "the user said it is our call")
            open_rows.remove(name)

    # 8. One question for each open row, required parameters first, three at most.
    to_ask = [name for name in open_rows if name in required or name in must_ask
              or name not in OPTIONAL_QUIET | {"aspect"}]
    to_ask.sort(key=lambda name: name not in required)
    questions = [{"param": name, "question": QUESTIONS[name]} for name in to_ask][:MAX_QUESTIONS]
    return {"tool": tool, "ready": not questions, "params": [sheet[name] for name in uses if name in sheet], "questions": questions}


class Message(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class SheetRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str
    value: Any = None
    source: Source
    why: str | None = Field(default=None, alias="from")


class Attachment(BaseModel):
    name: str
    kind: Literal["image", "video", "audio"]
    aspect: Literal["16:9", "9:16", "1:1"] | None = None
    seconds: float | None = None
    role: Literal["person", "copy", "product", "environment", "other"] | None = None


def register_plan_request(mcp: FastMCP) -> None:
    @mcp.tool(
        name="plan_request",
        title="Check the request before creating",
        description=(
            "Call this before a create or edit tool. Pass the user's messages word for word, the tool you plan to "
            "call, and one row for each parameter you know: value and source (user = the user said it, derived = it "
            "follows from the user's words, default = your choice, missing = unknown). Row names: subject, edit, keep, "
            "motion, seconds, aspect, sound, exact_words, look, mood, script, language, which_face, range. Returns the "
            "checked sheet and "
            "up to 3 questions. If ready is false, ask the user the returned questions word for word and call again "
            "with the answer added to messages. If ready is true, create with the returned values. A value the user "
            "did not give comes back missing: do not guess shape, length, sound or on-screen words. Read-only; "
            "spends no credits and creates nothing."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
    )
    def plan_request(
        messages: list[Message],
        tool: ToolName,
        params: list[SheetRow],
        attachments: list[Attachment] | None = None,
    ) -> dict:
        return plan_sheet(
            [m.model_dump() for m in messages],
            tool,
            [{"name": p.name, "value": p.value, "source": p.source, "from": p.why} for p in params],
            [a.model_dump() for a in attachments or []],
        )

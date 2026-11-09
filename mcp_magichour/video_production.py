"""Plan a multi-clip video: story -> clips -> one reference per clip -> ordered calls.

Pure code. No network, no model, no credits. The split rule is a parameter so the
benchmark can compare the candidates (scripts/split_bench.py).

Story (a dict, JSON in and out):
    title, aspect ("16:9" | "9:16" | "1:1"), audio (bool), setting (words reused in every clip),
    subjects: [{id, words, role: person|copy|product|place, picture?}],
    beats:    [{seconds, text, kind: scene|card, place?, subjects?: [id], link?, exact_words?: [str], says?: [str],
                clip?: int, spoken?: [str], reference?: {kind: none|picture|last_frame|file, subject?, of_clip?, file?}}]
    narrator? (how the voice sounds), music? (what the music is), captions? (bool)

The host groups the beats into clips (2026-11-07, user: the model decides, the code keeps track and advises):
    clip        the clip a beat belongs to, 1, 2, 3 ... in order; a card is a clip of its own. When every beat has one,
                the clips are exactly these. Without them the split rule groups the beats and `advice` says so.
    spoken      a line a person on screen says out loud, word for word (not the narrator: that is `says`)
    reference   on the first beat of a clip: the clip's one reference, chosen by the host (a subject's picture, the
                last frame of an earlier clip, a picture file the host made, or none). Without it the code chooses.
`advise` returns warnings with the evidence behind them; nothing in them changes the plan.

Questions (user, 2026-11-07: the model decides; the MCP asks at the known risks, in exact words, with a recommendation):
    `questions` lists a question for each risk with a known better way; a plan with an open question has no
    production token. The answers go back with the same story (`answers`: {id: option}); `apply_answers` changes
    the story the way the option says, and the plan is made again.
    in_scene_words  words that are part of the picture (a label, a sign): no question; the video does its best and
                    the checklist says the letters may change.
    background      on a card: its colour as a code (#3B1F6B). The card is then drawn by code, colour and words exact,
                    and needs no generation call.
    picture         on a card: a picture to hold unchanged for the card's seconds (a logo), fitted onto `background`.

A voice-over is one track for the whole film, not a sound inside each clip: `says` holds the narrator's lines
for a beat. One call reads all the lines in one voice; the join puts each beat's lines on that beat.

A beat is the smallest unit: one action. `link` says how a beat relates to the beat before it:
    continues   the same shot goes on (no cut wanted)
    event       same place and subjects, an important new event (a cut is acceptable)
    moves       a subject carries over, the place is new
    new         nothing carries over
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

LINKS = ("continues", "event", "moves", "new")
WORD_ROUTES = ("card", "model", "still", "accept")
STRATEGIES = ("one", "time", "idea", "event", "shot", "person", "manual")
ASPECTS = ("16:9", "9:16", "1:1")
ROLE_PRIORITY = ("person", "copy", "product", "place")
MODEL_MAX_SECONDS = {"ltx-2.5": 60, "minimax-h3": 30}
TEXT_MODEL = "ltx-2.5"          # no reference, or a start frame
REFERENCE_MODEL = "minimax-h3"  # the free model that takes a named reference
STILL_MODEL = "qwen-image-2.1"  # exact words on a card
RESOLUTION = "480p"
CREDITS_PER_SECOND = 24
STILL_CREDITS = 10
PROMPT_LIMIT = 2000
TRIGGER_SECONDS = 15
TRIGGER_IDEAS = 3

# Where each strategy cuts between two scene beats. Every strategy also cuts when the
# next beat does not fit in max_seconds. A card is always its own clip.
CUT_ON = {
    "one": (),
    "time": (),
    "idea": ("moves", "new"),
    "event": ("event", "moves", "new"),
    "shot": LINKS,
    # Priority 1: the beats of a pictured person stay in one call (see split). Priority 2: a new idea is a new clip.
    "person": ("moves", "new"),
    "manual": (),   # cuts exactly where the caller says (the benchmark compares cut points with it)
}
CHAINED = ("person", "manual")   # an idea that is cut is chained: end on the person, start the next clip from that frame


def beat_link(beat: dict, previous: dict | None) -> str:
    """The link the story gives, else the link the place and subjects imply."""
    if previous is None or beat.get("kind") == "card" or previous.get("kind") == "card":
        return "new"
    if beat.get("link") in LINKS:
        return beat["link"]
    shared = set(beat.get("subjects", [])) & set(previous.get("subjects", []))
    if shared and beat.get("place") and beat.get("place") == previous.get("place"):
        return "continues"
    return "moves" if shared else "new"


def validate_story(story: dict) -> list[str]:
    problems: list[str] = []
    if story.get("aspect") not in ASPECTS:
        problems.append(f"aspect must be one of {', '.join(ASPECTS)}")
    beats = story.get("beats") or []
    if not beats:
        problems.append("the story has no beats")
    ids = [s.get("id") for s in story.get("subjects", [])]
    if len(ids) != len(set(ids)):
        problems.append("subject ids must be unique")
    for s in story.get("subjects", []):
        if s.get("role") not in ROLE_PRIORITY:
            problems.append(f"subject {s.get('id')}: role must be one of {', '.join(ROLE_PRIORITY)}")
    for i, beat in enumerate(beats, start=1):
        seconds = beat.get("seconds")
        if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds < 1:
            problems.append(f"beat {i}: seconds must be a whole number, 1 or more")
        if not str(beat.get("text", "")).strip():
            problems.append(f"beat {i}: text is empty")
        if beat.get("kind", "scene") not in ("scene", "card"):
            problems.append(f"beat {i}: kind must be scene or card")
        if beat.get("kind") == "card" and not beat.get("exact_words") and not beat.get("picture"):
            problems.append(f"beat {i}: a card needs exact_words, or `picture` (a picture to hold unchanged, such as a logo)")
        if beat.get("picture") and not str(beat["picture"]).startswith(("http://", "https://")):
            problems.append(f"beat {i}: `picture` must be the picture's URL (the server downloads it to hold it unchanged); "
                            "a Magic Hour file_path cannot be downloaded")
        if beat.get("words_route") == "still" and beat.get("reference"):
            problems.append(f"beat {i}: the words answer 'still' makes this clip's start picture; drop `reference`, or answer 'card' or 'model'")
        if "link" in beat and beat["link"] not in LINKS:
            problems.append(f"beat {i}: link must be one of {', '.join(LINKS)}")
        for sid in beat.get("subjects", []):
            if sid not in ids:
                problems.append(f"beat {i}: unknown subject {sid}")
        problems += _reference_problems(story, i, beat.get("reference"))
        if beat.get("words_route") not in (None, *WORD_ROUTES):
            problems.append(f"beat {i}: words_route must be one of {', '.join(WORD_ROUTES)}")
        if beat.get("model") not in (None, *MODEL_MAX_SECONDS):
            problems.append(f"beat {i}: model must be one of {', '.join(MODEL_MAX_SECONDS)}")
        if beat.get("background") and not re.fullmatch(r"#[0-9A-Fa-f]{6}", beat["background"]):
            problems.append(f"beat {i}: background must be a colour code like #3B1F6B")
    problems += _clip_problems(beats)
    if "seconds" in story and not problems:
        total = sum(b["seconds"] for b in beats)
        if total != story["seconds"]:
            problems.append(f"beats add up to {total} s, the story says {story['seconds']} s")
    return problems


def _reference_problems(story: dict, i: int, reference: dict | None) -> list[str]:
    if not reference:
        return []
    kind, pictured = reference.get("kind"), {s["id"]: s for s in story.get("subjects", []) if s.get("picture")}
    if kind not in ("none", "picture", "last_frame", "file"):
        return [f"beat {i}: reference kind must be none, picture, last_frame or file"]
    if kind == "picture" and reference.get("subject") not in pictured:
        return [f"beat {i}: reference picture needs `subject`: a subject that has a picture ({', '.join(pictured) or 'none has one'})"]
    if kind == "file" and not str(reference.get("file", "")).strip():
        return [f"beat {i}: reference file needs `file`: the file_path or URL of the picture"]
    return []


def _clip_problems(beats: list[dict]) -> list[str]:
    """The host's grouping: all beats or none, 1, 2, 3 ... in order, a card alone in its clip."""
    marked = [b.get("clip") for b in beats]
    if not any(m is not None for m in marked):
        return []
    if any(m is None for m in marked):
        return ["set `clip` on every beat, or on none"]
    expected, problems = 1, []
    for i, (beat, m) in enumerate(zip(beats, marked), start=1):
        if m not in (expected - 1, expected) or (i == 1 and m != 1):
            problems.append(f"beat {i}: clip {m} is out of order; clips are numbered 1, 2, 3 ... in story order")
            break
        expected = m + 1
    for i, beat in enumerate(beats):
        if beat.get("kind") == "card" and sum(1 for b in beats if b.get("clip") == beat.get("clip")) > 1:
            problems.append(f"beat {i + 1}: a card is a clip of its own; give it its own clip number")
    return problems


def host_cuts(story: dict) -> list[int] | None:
    """The beat numbers where the host's clips start, or None when the host did not group the beats."""
    beats = story["beats"]
    if not beats or any(b.get("clip") is None for b in beats):
        return None
    return [i + 1 for i in range(1, len(beats)) if beats[i]["clip"] != beats[i - 1]["clip"]]


def count_ideas(story: dict) -> int:
    """Scene groups that share nothing with the group before them, plus cards."""
    ideas, previous = 0, None
    for beat in story["beats"]:
        if beat_link(beat, previous) in ("moves", "new"):
            ideas += 1
        previous = beat
    return ideas


def needs_production(story: dict) -> bool:
    total = sum(b["seconds"] for b in story["beats"])
    return total > TRIGGER_SECONDS or count_ideas(story) >= TRIGGER_IDEAS


def _beats_that_fit(story: dict, max_seconds: int, person_seconds: int | None = None) -> list[dict]:
    """Number the beats; cut a beat longer than its limit into equal parts that continue.
    person_seconds: the limit for a beat that shows a pictured person (it may be longer than the others)."""
    out: list[dict] = []
    previous = None
    for n, beat in enumerate(story["beats"], start=1):
        link = beat_link(beat, previous)
        previous = beat
        limit = person_seconds if person_seconds and pictured_people(story, [beat]) else max_seconds
        parts = -(-beat["seconds"] // limit)
        base, extra = divmod(beat["seconds"], parts)
        for p in range(parts):
            out.append({
                **deepcopy(beat), "n": n, "kind": beat.get("kind", "scene"),
                "seconds": base + (1 if p < extra else 0),
                "link": link if p == 0 else "continues",
            })
    return out


def pictured_people(story: dict, parts: list[dict]) -> set[str]:
    """The people in these beats whose look comes from a picture."""
    by_id = {s["id"]: s for s in story.get("subjects", [])}
    return {sid for part in parts for sid in part.get("subjects", [])
            if by_id[sid]["role"] == "person" and by_id[sid].get("picture")}


def people(story: dict, parts: list[dict]) -> set[str]:
    """The people in these beats, with or without a picture."""
    by_id = {s["id"]: s for s in story.get("subjects", [])}
    return {sid for part in parts for sid in part.get("subjects", []) if by_id[sid]["role"] == "person"}


def split(story: dict, strategy: str = "idea", max_seconds: int = TRIGGER_SECONDS, cuts: list[int] | None = None) -> list[dict]:
    """Group the beats into clips. Returns [{n, beats, seconds, kind, link, parts}].

    "person": ideas come first, and the same person is an idea. A beat that shows a person from the clip before
    it stays in that clip, also when the place changes, while the clip fits: max_seconds, or what the reference
    model makes in one call when the person's look comes from a picture (a last-frame start loses that face).
    "manual": a new clip starts before each beat number in `cuts`.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {', '.join(STRATEGIES)}")
    if strategy == "one":
        beats = _beats_that_fit(story, 10**6)
        return [{"n": 1, "kind": "scene", "link": "new", "parts": beats,
                 "beats": [b["n"] for b in beats], "seconds": sum(b["seconds"] for b in beats)}]
    clips: list[dict] = []
    current: dict | None = None
    person_seconds = MODEL_MAX_SECONDS[REFERENCE_MODEL] if strategy == "person" else None
    manual = strategy == "manual"
    for beat in _beats_that_fit(story, 10**6 if manual else max_seconds, person_seconds):
        is_card = beat["kind"] == "card"
        in_scene = current is not None and not is_card and current["kind"] == "scene"
        same_person = strategy == "person" and in_scene and beat["link"] != "new" and bool(people(story, current["parts"]) & people(story, [beat]))
        from_picture = same_person and bool(pictured_people(story, current["parts"]) & pictured_people(story, [beat]))
        limit = MODEL_MAX_SECONDS[REFERENCE_MODEL] if from_picture else max_seconds
        # A pictured person who was not in the clip so far is a new idea: their picture needs its own call.
        enters = strategy == "person" and in_scene and bool(pictured_people(story, [beat]) - pictured_people(story, current["parts"]))
        if manual:
            cut = not in_scene or beat["n"] in (cuts or [])
        else:
            cut = (
                not in_scene or enters
                or (beat["link"] in CUT_ON[strategy] and not same_person)
                or current["seconds"] + beat["seconds"] > limit
            )
        if cut:
            current = {"n": len(clips) + 1, "kind": beat["kind"], "link": beat["link"], "parts": [], "beats": [], "seconds": 0}
            clips.append(current)
        current["parts"].append(beat)
        current["beats"].append(beat["n"])
        current["seconds"] += beat["seconds"]
    return clips


def _pictured(story: dict, clip: dict) -> dict | None:
    """The one subject whose picture goes into this clip: person, then copy, then product, then place."""
    by_id = {s["id"]: s for s in story.get("subjects", [])}
    seen = [by_id[sid] for part in clip["parts"] for sid in part.get("subjects", []) if by_id[sid].get("picture")]
    return min(seen, key=lambda s: ROLE_PRIORITY.index(s["role"])) if seen else None


def choose_reference(story: dict, clip: dict, previous: dict | None, moves: str = "last_frame",
                     earlier: list[dict] | None = None, chain: bool = True) -> dict:
    """At most one reference for a clip.

    card                    its own still
    continues / event       the last frame of the clip before it
    moves                   the carried subject's picture; without one, `moves` decides (last_frame | none)
    new                     a picture of a subject in the clip, else nothing
    earlier (chained rules) a person with no picture: the last frame of the last clip that showed them,
                            also when other clips are in between. new_place: that frame is in another place.
    chain=False             no last-frame reference at all (clips share words only)
    """
    if clip["kind"] == "card":
        return {"kind": "still", "exact_words": [w for part in clip["parts"] for w in part.get("exact_words", [])]}
    routed = [w for part in clip["parts"] if part.get("words_route") == "still" for w in part.get("exact_words", [])]
    if routed:   # the host chose: a picture of the scene with the words, and the clip starts from it
        return {"kind": "scene_still", "exact_words": routed}
    chosen = clip["parts"][0].get("reference")
    if chosen:   # the host chose the reference
        kind = chosen["kind"]
        if kind == "picture":
            subject = next(s for s in story.get("subjects", []) if s["id"] == chosen["subject"])
            return {"kind": "picture", "subject": subject["id"], "file": subject["picture"], "chosen": True}
        if kind == "file":
            return {"kind": "file", "subject": "reference", "file": chosen["file"], "chosen": True}
        if kind == "last_frame":
            return {"kind": "last_frame", "of_clip": chosen.get("of_clip") or (previous["n"] if previous else 0), "chosen": True}
        return {"kind": "none", "chosen": True}
    can_continue = previous is not None and previous["kind"] != "card"
    link = clip["link"] if can_continue else "new"
    # A pictured person who was not in the clip before: the picture is the only thing that carries the face.
    new_face = pictured_people(story, clip["parts"]) - (pictured_people(story, previous["parts"]) if can_continue else set())
    if chain and link in ("continues", "event") and not new_face:
        return {"kind": "last_frame", "of_clip": previous["n"]}
    subject = _pictured(story, clip)
    if subject:
        return {"kind": "picture", "subject": subject["id"], "file": subject["picture"]}
    if not chain:
        return {"kind": "none"}
    for before in reversed(earlier or []):
        if before["kind"] == "scene" and people(story, before["parts"]) & people(story, clip["parts"]):
            reference = {"kind": "last_frame", "of_clip": before["n"]}
            if before["parts"][-1].get("place") != clip["parts"][0].get("place"):
                reference["new_place"] = True
            return reference
    if link == "moves" and moves == "last_frame":
        return {"kind": "last_frame", "of_clip": previous["n"]}
    return {"kind": "none"}


def compose_prompt(story: dict, clip: dict, reference: dict, ends_on: list[str] | None = None, ends_close: bool = False) -> str:
    """One prose prompt from the story's own words. The same words go into every clip that shows the thing."""
    by_id = {s["id"]: s for s in story.get("subjects", [])}
    if clip["kind"] == "card":
        return ("The supplied image held almost motionless for the whole clip: a very slow, barely visible push in. "
                "Every letter stays exactly as in the image. Nothing else appears.")
    lines = [f"A {clip['seconds']}-second {story['aspect']} clip. {story['setting'].strip()}"]
    shown: list[str] = []
    for part in clip["parts"]:
        for sid in part.get("subjects", []):
            if sid not in shown:
                shown.append(sid)
    for sid in shown:
        subject = by_id[sid]
        tag = f"@{sid} is the reference for " if reference.get("subject") == sid else ""
        lines.append(f"{tag}{subject['words'].strip().rstrip('.')}.")
    if reference["kind"] == "picture":
        lines.append(f"Use @{reference['subject']} as a likeness guide, not a pasted photo. Build the scene around it.")
    if reference["kind"] == "file":
        lines.append("Use @reference, the supplied picture, as a likeness guide for how everything looks. Build the scene around it.")
    if reference["kind"] == "last_frame" and reference.get("new_place"):
        lines.append("The supplied image is the first frame: a close view of the person. Keep this person exactly as shown. "
                     "The place is new: the camera pulls back from the close view to show it.")
    elif reference["kind"] == "last_frame":
        lines.append("The supplied image is the first frame. Continue from it: the same people, place and light.")
    at = 0
    for part in clip["parts"]:
        end = at + part["seconds"]
        lines.append(f"{at}-{end} s: {part['text'].strip()}")
        for said in part.get("spoken") or []:
            lines.append(f'Said out loud on screen, once, word for word: "{said.strip()}"')
        for words in part.get("in_scene_words") or []:
            lines.append(f'The words "{words.strip()}" are part of the picture, spelled exactly.')
        if part.get("words_route") == "model":
            for words in part.get("exact_words") or []:
                lines.append(f'Show the words "{words.strip()}" on screen in large clean letters, spelled exactly.')
        at = end
    if ends_on:
        # A later clip starts from this clip's last frame, so that frame must show the people it carries. The line
        # does not describe them again: a second description made the model draw a second person (B2, C8).
        if ends_close:   # the next place is another one: carry the person, not the place
            lines.append("End close on the last action's person: head and shoulders fill the frame, the background soft, "
                         "held still for the last second.")
        else:
            lines.append("End with everyone from the last action still in frame, held still for the last second.")
    lines.append("Each action happens once, in this order. No repeated shots, no title cards, no captions, no other scenes.")
    return " ".join(lines)


def plan(story: dict, strategy: str = "idea", max_seconds: int = TRIGGER_SECONDS, moves: str = "last_frame",
         cuts: list[int] | None = None, chain: bool = True, end_on: bool = True) -> dict:
    """The ordered calls for a story, with the checks that must pass before anything is paid for."""
    problems = validate_story(story)
    if problems:
        return {"ok": False, "problems": problems, "clips": []}
    clips = split(story, strategy, max_seconds, cuts)
    chained = strategy in CHAINED and chain
    out: list[dict] = []
    late_problems: list[str] = []
    references, previous = [], None
    for i, clip in enumerate(clips):
        references.append(choose_reference(story, clip, previous, moves, clips[:i] if chained else None, chain))
        previous = clip
    for i, clip in enumerate(clips):
        reference = references[i]
        # Each later clip that starts from this clip's last frame: this clip ends on the people they share.
        takers = [j for j in range(i + 1, len(clips)) if chained and end_on and references[j].get("of_clip") == clip["n"]]
        ends_on = sorted({sid for j in takers for sid in people(story, clip["parts"]) & people(story, clips[j]["parts"])})
        ends_close = any(references[j].get("new_place") for j in takers)
        steps: list[dict] = []
        background = next((p.get("background") for p in clip["parts"] if p.get("background")), None)
        held = next((p.get("picture") for p in clip["parts"] if p.get("picture")), None)
        if clip["kind"] == "card" and held:   # the user's picture held unchanged (a logo): code, no generation call
            out.append({
                "n": clip["n"], "kind": "card", "beats": clip["beats"], "seconds": clip["seconds"], "link": clip["link"],
                "reference": {"kind": "held", "file": held}, "ends_on": [], "depends_on": [], "made_by": "code",
                "steps": [{"tool": "hold_picture", "model": "code", "credits": 0, "seconds": clip["seconds"], "picture": held,
                           "background": background or "#FFFFFF"}],
            })
            continue
        if clip["kind"] == "card" and background:   # drawn by code: exact colour and words, no generation call
            out.append({
                "n": clip["n"], "kind": "card", "beats": clip["beats"], "seconds": clip["seconds"], "link": clip["link"],
                "reference": {"kind": "drawn"}, "ends_on": [], "depends_on": [], "made_by": "code",
                "steps": [{"tool": "draw_card", "model": "code", "credits": 0, "seconds": clip["seconds"], "background": background,
                           "words": reference["exact_words"]}],
            })
            continue
        if reference["kind"] == "scene_still":
            words = " and ".join(f'"{w}"' for w in reference["exact_words"])
            by_id = {x["id"]: x for x in story.get("subjects", [])}
            shown = [by_id[sid]["words"].strip().rstrip(".") for p in clip["parts"] for sid in p.get("subjects", []) if sid in by_id]
            steps.append({
                "tool": "generate_image", "model": STILL_MODEL, "credits": STILL_CREDITS,
                "prompt": " ".join([story["setting"].strip(), *[f"{x}." for x in dict.fromkeys(shown)],
                                    clip["parts"][0]["text"].strip(), f"The words {words} are written large and clear in the picture, "
                                    f"spelled exactly. The only text in the image is exactly {words}."]),
            })
        if reference["kind"] == "still":
            words = " and ".join(f'"{w}"' for w in reference["exact_words"])
            steps.append({
                "tool": "generate_image", "model": STILL_MODEL, "credits": STILL_CREDITS,
                "prompt": f"{' '.join(p['text'].strip() for p in clip['parts'])} The only text in the image is exactly {words}.",
            })
        if reference["kind"] in ("picture", "file"):
            tool, model = "create_video_from_text", REFERENCE_MODEL
        elif reference["kind"] in ("last_frame", "still", "scene_still"):
            tool, model = "create_video_from_image", TEXT_MODEL
        else:
            tool, model = "create_video_from_text", TEXT_MODEL
        answered = next((p.get("model") for p in clip["parts"] if p.get("words_route") == "model" and p.get("model")), None)
        asked = answered or next((p.get("model") for p in clip["parts"] if p.get("model")), None)
        if asked and asked in MODEL_MAX_SECONDS:   # the host chose the model; an answer's choice wins over a beat's
            if reference["kind"] in ("picture", "file") and asked != REFERENCE_MODEL:
                late_problems.append(f"clip {clip['n']}: {asked} cannot take a picture reference; use {REFERENCE_MODEL}, or drop the reference")
            else:
                model = asked
        steps.append({
            "tool": tool, "model": model, "resolution": RESOLUTION, "seconds": clip["seconds"],
            "audio": (bool(story.get("audio")) or any(p.get("spoken") for p in clip["parts"])) and clip["kind"] != "card",
            "credits": clip["seconds"] * CREDITS_PER_SECOND,
            "prompt": compose_prompt(story, clip, reference, ends_on, ends_close),
        })
        out.append({
            "n": clip["n"], "kind": clip["kind"], "beats": clip["beats"], "seconds": clip["seconds"],
            "link": clip["link"], "reference": reference, "ends_on": ends_on,
            "depends_on": [reference["of_clip"]] if reference["kind"] == "last_frame" else [],
            "steps": steps,
        })
    for c in out:
        c.setdefault("made_by", "api")
    result = {
        "ok": True, "strategy": strategy, "max_seconds": max_seconds,
        "needs_production": needs_production(story),
        "seconds": sum(c["seconds"] for c in out),
        "credits": sum(s["credits"] for c in out for s in c["steps"]),
        "clips": out, "join": [c["n"] for c in out], "rounds": rounds(out),
    }
    sound = plan_sound(story, clips)
    if sound:
        result["sound"] = sound
        result["credits"] += sum(sound[k]["credits"] for k in ("narration", "music") if k in sound)
    result["checklist"] = checklist(story, clips, sound)
    result["problems"] = check_plan(story, result) + late_problems
    result["ok"] = not result["problems"]
    return result


NARRATION_WORDS_PER_SECOND = 2.5
MUSIC_MIN_SECONDS, MUSIC_CREDITS_PER_SECOND = 15, 1


def plan_sound(story: dict, clips: list[dict]) -> dict | None:
    """The sound that is added after the join: one narration call, one music track, drawn captions."""
    parts, at = [], 0.0
    for clip in clips:
        inside = 0.0   # where the beat starts inside its clip: the join uses it with the real length of each clip
        for beat in clip["parts"]:
            lines = [line.strip() for line in beat.get("says") or [] if line.strip()]
            if lines:
                parts.append({"beat": beat["n"], "clip": clip["n"], "inside": inside, "at": round(at + 0.5, 2),
                              "seconds": beat["seconds"], "lines": lines})
            at += beat["seconds"]
            inside += beat["seconds"]
    film_seconds = sum(c["seconds"] for c in clips)
    sound: dict = {"captions": bool(story.get("captions")) and bool(parts)}
    if parts:
        script = " ".join(line for part in parts for line in part["lines"])
        seconds = min(MODEL_MAX_SECONDS[TEXT_MODEL], max(5, -(-len(script.split()) // NARRATION_WORDS_PER_SECOND) + 3))
        voice = (story.get("narrator") or "a calm, warm narrator").strip().rstrip(".")
        sound["narration"] = {
            "parts": parts, "seconds": int(seconds), "model": TEXT_MODEL, "resolution": RESOLUTION, "credits": int(seconds) * CREDITS_PER_SECOND,
            "prompt": (f"A plain black screen for the whole clip; nothing appears and nothing moves. Sound only: an off-camera narrator, {voice}. "
                       f"The narrator reads these words once, exactly, at a relaxed pace, with a clear pause after each sentence, and then stays silent: "
                       f"\"{script}\" No music, no other sound."),
        }
    if story.get("music"):
        seconds = max(MUSIC_MIN_SECONDS, film_seconds + 2)
        sound["music"] = {"seconds": seconds, "prompt": story["music"].strip(), "credits": seconds * MUSIC_CREDITS_PER_SECOND}
    return sound if "narration" in sound or "music" in sound else None


def checklist(story: dict, clips: list[dict], sound: dict | None) -> list[dict]:
    """What the finished film must have, from the story. `how`: "measured" lines are checked by code at the join;
    "by eye" lines are for the host to confirm before it delivers."""
    seconds = sum(c["seconds"] for c in clips)
    by_id = {s["id"]: s for s in story.get("subjects", [])}
    lines = [{"id": "file", "want": f"One file, {seconds} s, {story['aspect']}", "how": "measured"},
             {"id": "order", "want": f"{len(story['beats'])} beats in story order, each once, no repeats", "how": "by eye"}]
    for clip in clips:
        if clip["kind"] == "card":
            words = ", ".join(f'"{w}"' for part in clip["parts"] for w in part.get("exact_words", []))
            lines.append({"id": f"card-{clip['n']}", "want": f"Card held {clip['seconds']} s with exactly {words}", "how": "measured length, words by eye"})
    for sid in sorted({sid for beat in story["beats"] for sid in beat.get("subjects", [])}):
        lines.append({"id": f"same-{sid}", "want": f"{by_id[sid]['words'].split(',')[0].split(':')[0].strip()} looks the same in every clip", "how": "by eye"})
    for n, beat in enumerate(story["beats"], start=1):
        if beat.get("kind", "scene") == "scene" and beat.get("exact_words"):
            route = beat.get("words_route") or "not chosen"
            how = {"model": "by eye: drawn by the video model, may be misspelled", "still": "by eye: from the picture made with them",
                   "accept": "by eye: accepted as a risk, tell the user"}.get(route, "by eye")
            lines.append({"id": f"words-{n}", "want": f"On screen, spelled exactly: {', '.join(chr(34) + w + chr(34) for w in beat['exact_words'])}", "how": how})
        for words in beat.get("in_scene_words") or []:
            lines.append({"id": f"in-scene-{_letters(words)[:12]}", "want": f"\"{words}\" in the picture (best effort: letters on a moving object may change; tell the user)", "how": "by eye, best effort"})
    spoken = [said.strip() for beat in story["beats"] for said in beat.get("spoken") or []]
    for k, said in enumerate(spoken, start=1):
        lines.append({"id": f"line-{k}", "want": f"Said on screen once, word for word: \"{said}\"", "how": "by ear"})
    if sound and "narration" in sound:
        script = " ".join(line for part in sound["narration"]["parts"] for line in part["lines"])
        lines.append({"id": "voice", "want": f"Voice-over says once, in order: \"{script}\"", "how": "measured: speech heard; words by ear"})
    if sound and "music" in sound:
        lines.append({"id": "music", "want": "Music under the whole film", "how": "measured"})
    if sound and sound.get("captions"):
        lines.append({"id": "captions", "want": "The voice-over's sentences drawn on the picture when they are said", "how": "measured"})
    if story.get("audio"):
        lines.append({"id": "scene-sound", "want": "The scenes have their own sound (as the beats describe)", "how": "measured: a sound track that is not silent"})
    elif not sound:
        lines.append({"id": "silent", "want": "No sound", "how": "measured"})
    return lines


def rounds(clips: list[dict]) -> list[list[int]]:
    """Batches of clips to make together. A clip is in the first round where every clip it starts from is done.
    Two people who take turns are two chains: each chain is linear, and the chains run side by side."""
    done: set[int] = set()
    out: list[list[int]] = []
    left = list(clips)
    while left:
        ready = [c["n"] for c in left if set(c["depends_on"]) <= done]
        if not ready:
            raise ValueError("clips wait for each other in a circle")
        out.append(ready)
        done |= set(ready)
        left = [c for c in left if c["n"] not in done]
    return out


def check_plan(story: dict, planned: dict) -> list[str]:
    """Gates on a plan. A problem here stops the run before the first paid call."""
    problems: list[str] = []
    total = sum(b["seconds"] for b in story["beats"])
    if planned["seconds"] != total:
        problems.append(f"clips add up to {planned['seconds']} s, the story is {total} s")
    covered = [n for c in planned["clips"] for n in c["beats"]]
    if sorted(set(covered)) != list(range(1, len(story["beats"]) + 1)) or covered != sorted(covered):
        problems.append("every beat must be in a clip, in story order")
    narration = (planned.get("sound") or {}).get("narration")
    if narration and len(narration["prompt"]) > PROMPT_LIMIT:
        problems.append(f"the narration is {len(narration['prompt'])} characters with its instructions, the limit is {PROMPT_LIMIT}")
    for part in (narration or {}).get("parts", []):
        if len(" ".join(part["lines"]).split()) > part["seconds"] * 3.2:
            problems.append(f"beat {part['beat']}: the narrator's lines are too long for {part['seconds']} s")
    made: set[int] = set()
    for clip in planned["clips"]:
        video = clip["steps"][-1]
        if clip.get("made_by") == "code":   # a drawn card: no model, no prompt
            made.add(clip["n"])
            continue
        if clip["seconds"] > MODEL_MAX_SECONDS[video["model"]]:
            problems.append(f"clip {clip['n']}: {clip['seconds']} s is more than {video['model']} makes in one call")
        if len(video["prompt"]) > PROMPT_LIMIT:
            problems.append(f"clip {clip['n']}: the prompt is {len(video['prompt'])} characters, the limit is {PROMPT_LIMIT}")
        for needed in clip["depends_on"]:
            if needed not in made:
                problems.append(f"clip {clip['n']}: needs clip {needed}, which is not made before it")
        made.add(clip["n"])
    return problems


HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")


def advise(story: dict, planned: dict, request: str | None = None) -> list[dict]:
    """Warnings on a plan, each with the run that showed it. They change nothing: the host decides. (Words in a scene,
    a spoken line with other beats and colour codes are `questions`, not advice.)

    The notes are in gates_docs.NOTES (findings only). `request`: the user's own words; a quoted phrase, the length or
    the shape that the story does not carry is reported as not carried."""
    from .gates_docs import NOTES

    out: list[dict] = []

    def warn(note: str, clip: int | None, said: str) -> None:
        out.append({"clip": clip, "note": note, "warning": said, "evidence": NOTES[note][2] if note in NOTES else ""})

    beats = story["beats"]
    if host_cuts(story) is None and len(planned["clips"]) > 0:
        warn("grouping", None, "You did not set `clip` on the beats, so the split rule grouped them (the same people stay in one "
                               "clip up to 15 s). Set `clip` on every beat to choose the clips yourself.")
    for clip in planned["clips"]:
        parts = [beats[n - 1] for n in clip["beats"]]
        model = clip["steps"][-1]["model"]
        if clip["kind"] == "card":
            continue
        places = {p.get("place") for p in parts if p.get("place")}
        ideas = sum(1 for k, p in enumerate(parts) if k == 0 or beat_link(p, parts[k - 1]) in ("moves", "new"))
        if clip["seconds"] > TRIGGER_SECONDS or ideas > 2:
            warn("ideas-per-call", clip["n"], f"Clip {clip['n']}: {clip['seconds']} s with {ideas} separate ideas in one call.")
        if len(places) > 1 and clip["reference"]["kind"] not in ("picture", "file"):
            warn("words-only-places-merge", clip["n"], f"Clip {clip['n']} has {len(places)} places and no picture reference.")
        if clip["reference"]["kind"] == "last_frame" and clip["reference"].get("of_clip"):
            before = next((c for c in planned["clips"] if c["n"] == clip["reference"]["of_clip"]), None)
            if before:
                old = beats[before["beats"][-1] - 1].get("place")
                if old and places and old not in places:
                    warn("last-frame-keeps-place", clip["n"], f"Clip {clip['n']} starts from clip {before['n']}'s last frame "
                                                              f"({old}) but takes place in {', '.join(sorted(places))}.")
    if request:
        from .gates import brief_items

        story_words = _letters(" ".join(
            [w for b in beats for w in (b.get("exact_words") or []) + (b.get("says") or []) + (b.get("spoken") or [])]))
        total = sum(b["seconds"] for b in beats)
        for item in brief_items(request, []):
            missing = None
            if item["kind"] == "words" and _letters(item["value"]) not in story_words:
                missing = f"The request quotes \"{item['value']}\", and no beat carries it in exact_words, says or spoken."
            elif item["kind"] == "seconds" and abs(int(item["value"]) - total) > 1:
                missing = f"The request asks for {item['value']} s; the beats add up to {total} s."
            elif item["kind"] == "aspect" and item["value"] != story["aspect"]:
                missing = f"The request asks for {item['value']}; the story is {story['aspect']}."
            if missing:
                out.append({"clip": None, "note": "not-carried", "warning": missing, "evidence": ""})
    return out


# Plain names for colour codes: a code in a prompt is drawn on screen as text (A4 v1, 7 November).
COLOUR_NAMES = {
    "black": (0, 0, 0), "white": (255, 255, 255), "grey": (128, 128, 128), "red": (200, 30, 30), "dark red": (120, 20, 20),
    "orange": (240, 140, 40), "yellow": (240, 210, 40), "green": (40, 160, 60), "dark green": (20, 90, 40), "teal": (14, 124, 134),
    "turquoise": (60, 200, 200), "blue": (40, 90, 200), "navy": (20, 30, 90), "light blue": (140, 190, 240), "purple": (110, 40, 160),
    "deep purple": (59, 31, 107), "pink": (240, 140, 180), "magenta": (200, 40, 160), "brown": (120, 80, 40), "beige": (220, 200, 160),
    "gold": (210, 170, 60), "silver": (190, 190, 200), "cream": (250, 240, 220),
}


def colour_name(code: str) -> str:
    r, g, b = int(code[1:3], 16), int(code[3:5], 16), int(code[5:7], 16)
    return min(COLOUR_NAMES, key=lambda k: sum((x - y) ** 2 for x, y in zip(COLOUR_NAMES[k], (r, g, b))))


def questions(story: dict, planned: dict) -> list[dict]:
    """The questions a plan must answer before it is made: risks with a known better way. Ids stay the same while the
    story is the same, so the answers can go back with it. Each has a recommendation; the host decides."""
    out: list[dict] = []
    beats = story["beats"]
    for n, beat in enumerate(beats, start=1):
        if beat.get("kind", "scene") == "scene" and beat.get("exact_words") and not beat.get("words_route"):
            words = " and ".join(f'"{w}"' for w in beat["exact_words"])
            out.append({
                "id": f"words-{n}", "beat": n,
                "ask": (f"Beat {n} asks for the words {words} on screen over the scene. A video model asked to spell words in a scene: "
                        "ltx-2.5 got them wrong 0 of 4 times; minimax-h3 right 2 of 2. How should they be made? (Words that are "
                        "part of the picture, such as a label or a sign, go in `in_scene_words` instead: no question, best effort.)"),
                "options": {
                    "card": "A card of its own right after this beat, 2 s taken from the beat. Always exact. The words are not over the scene.",
                    "model": "minimax-h3 makes this beat's clip and draws the words in the scene. Looks best; 2 of 2 so far; check the frame after.",
                    "still": "A picture of the scene with the words is made first and the clip starts from it. Exact; the words stay on screen for the whole clip.",
                    "accept": "Keep it as planned. Tell the user the words may be misspelled.",
                },
                "recommend": "card",
            })
    for clip in planned.get("clips", []):
        if clip["kind"] == "card" or len(clip["beats"]) < 2:
            continue
        for n in clip["beats"]:
            if beats[n - 1].get("spoken") and not beats[n - 1].get("spoken_route"):
                out.append({
                    "id": f"line-{n}", "beat": n,
                    "ask": (f"Beat {n} has a spoken line and shares clip {clip['n']} with {len(clip['beats']) - 1} other beat(s). "
                            "With another beat in the clip the line was said 0 of 3 times; alone in a short clip, 3 of 3."),
                    "options": {"split": "Give beat {0} a clip of its own.".format(n), "keep": "Keep the clip. The line may not be said."},
                    "recommend": "split",
                })
    texts = [story.get("setting", "")] + [b.get("text", "") for b in beats if b.get("kind", "scene") == "scene"]
    codes = sorted({c for t in texts for c in HEX.findall(t)})
    if codes and not story.get("colour_codes"):
        out.append({
            "id": "colour-codes", "beat": None,
            "ask": (f"The setting or a scene names colours by code ({', '.join(codes)}). A code in a prompt was drawn on screen as text (A4)."),
            "options": {"words": "Write them as colour words: " + ", ".join(f"{c} as {colour_name(c)}" for c in codes) + ".",
                        "keep": "Keep the codes."},
            "recommend": "words",
        })
    return out


def apply_answers(story: dict, answers: dict[str, str]) -> tuple[dict, list[str]]:
    """The story changed the way the chosen options say. Returns (story, problems with the answers)."""
    story = deepcopy(story)
    beats, problems = story["beats"], []
    groups = [b.get("clip") for b in beats]   # the host's grouping, kept while beats are added or split off
    inserts: list[tuple[int, dict]] = []
    for key, choice in answers.items():
        kind, _, num = key.partition("-")
        if key == "colour-codes":
            if choice == "words":
                swap = lambda text: HEX.sub(lambda m: colour_name(m.group(0)), text)
                story["setting"] = swap(story.get("setting", ""))
                for b in beats:
                    if b.get("kind", "scene") == "scene":
                        b["text"] = swap(b["text"])
            story["colour_codes"] = choice
            continue
        if not num.isdigit() or not 1 <= int(num) <= len(beats):
            problems.append(f"no question {key}")
            continue
        beat = beats[int(num) - 1]
        if kind == "words":
            if choice not in WORD_ROUTES:
                problems.append(f"{key}: choose one of {', '.join(WORD_ROUTES)}")
                continue
            beat["words_route"] = choice
            if choice == "model":
                beat["model"] = REFERENCE_MODEL
            if choice == "card":
                take = min(2, beat["seconds"] - 1) if beat["seconds"] > 1 else 0
                words = beat.pop("exact_words")
                beat["seconds"] -= take
                inserts.append((int(num), {"seconds": take or 1, "kind": "card", "exact_words": words, "words_route": "card",
                                           "text": "Solid black background, centred white text reading exactly " + " and ".join(f'"{w}"' for w in words) + ".",
                                           "background": "#000000", "_own": True}))
        elif kind == "line":
            if choice not in ("split", "keep"):
                problems.append(f"{key}: choose split or keep")
                continue
            beat["spoken_route"] = choice
            if choice == "split":
                beat["_own"] = True
        else:
            problems.append(f"no question {key}")
    for at, card in sorted(inserts, reverse=True):
        beats.insert(at, card)
        groups.insert(at, None)
    if all(g is not None for g in groups if g is not None) and any(g is not None for g in groups):
        _renumber(beats, groups)
    else:
        for b in beats:
            b.pop("_own", None)
    if inserts and "seconds" in story:
        story["seconds"] = sum(b["seconds"] for b in beats)
    return story, problems


def _renumber(beats: list[dict], groups: list) -> None:
    """Clip numbers 1, 2, 3 ... from the host's groups; a card and a beat split off get a clip of their own."""
    n, previous = 0, object()
    for beat, group in zip(beats, groups):
        own = beat.pop("_own", False) or beat.get("kind") == "card"
        if own or group != previous or previous == "own":
            n += 1
        beat["clip"] = n
        previous = "own" if own else group


def _letters(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def check_outputs(planned: dict, measured: list[dict], tolerance: float = 1.0) -> list[str]:
    """Gates on the files that came back. `measured` is one {n, seconds, width, height} per clip, from ffprobe."""
    problems: list[str] = []
    by_n = {m["n"]: m for m in measured}
    sizes = set()
    for clip in planned["clips"]:
        got = by_n.get(clip["n"])
        if got is None:
            problems.append(f"clip {clip['n']}: no file")
            continue
        if abs(got["seconds"] - clip["seconds"]) > tolerance:
            problems.append(f"clip {clip['n']}: {got['seconds']:.1f} s, planned {clip['seconds']} s")
        sizes.add((got["width"], got["height"]))
    if len(sizes) > 1:
        problems.append("clips have different sizes: " + ", ".join(f"{w}x{h}" for w, h in sorted(sizes)))
    return problems

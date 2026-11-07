"""Plan a multi-clip video: story -> clips -> one reference per clip -> ordered calls.

Pure code. No network, no model, no credits. The split rule is a parameter so the
benchmark can compare the candidates (scripts/split_bench.py).

Story (a dict, JSON in and out):
    title, aspect ("16:9" | "9:16" | "1:1"), audio (bool), setting (words reused in every clip),
    subjects: [{id, words, role: person|copy|product|place, picture?}],
    beats:    [{seconds, text, kind: scene|card, place?, subjects?: [id], link?, exact_words?: [str], says?: [str]}]
    narrator? (how the voice sounds), music? (what the music is), captions? (bool)

A voice-over is one track for the whole film, not a sound inside each clip: `says` holds the narrator's lines
for a beat. One call reads all the lines in one voice; the join puts each beat's lines on that beat.

A beat is the smallest unit: one action. `link` says how a beat relates to the beat before it:
    continues   the same shot goes on (no cut wanted)
    event       same place and subjects, an important new event (a cut is acceptable)
    moves       a subject carries over, the place is new
    new         nothing carries over
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

LINKS = ("continues", "event", "moves", "new")
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
        if beat.get("kind") == "card" and not beat.get("exact_words"):
            problems.append(f"beat {i}: a card needs exact_words")
        if "link" in beat and beat["link"] not in LINKS:
            problems.append(f"beat {i}: link must be one of {', '.join(LINKS)}")
        for sid in beat.get("subjects", []):
            if sid not in ids:
                problems.append(f"beat {i}: unknown subject {sid}")
    if "seconds" in story and not problems:
        total = sum(b["seconds"] for b in beats)
        if total != story["seconds"]:
            problems.append(f"beats add up to {total} s, the story says {story['seconds']} s")
    return problems


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
    if reference["kind"] == "last_frame" and reference.get("new_place"):
        lines.append("The supplied image is the first frame: a close view of the person. Keep this person exactly as shown. "
                     "The place is new: the camera pulls back from the close view to show it.")
    elif reference["kind"] == "last_frame":
        lines.append("The supplied image is the first frame. Continue from it: the same people, place and light.")
    at = 0
    for part in clip["parts"]:
        end = at + part["seconds"]
        lines.append(f"{at}-{end} s: {part['text'].strip()}")
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
        if reference["kind"] == "still":
            words = " and ".join(f'"{w}"' for w in reference["exact_words"])
            steps.append({
                "tool": "generate_image", "model": STILL_MODEL, "credits": STILL_CREDITS,
                "prompt": f"{' '.join(p['text'].strip() for p in clip['parts'])} The only text in the image is exactly {words}.",
            })
        if reference["kind"] == "picture":
            tool, model = "create_video_from_text", REFERENCE_MODEL
        elif reference["kind"] in ("last_frame", "still"):
            tool, model = "create_video_from_image", TEXT_MODEL
        else:
            tool, model = "create_video_from_text", TEXT_MODEL
        steps.append({
            "tool": tool, "model": model, "resolution": RESOLUTION, "seconds": clip["seconds"],
            "audio": bool(story.get("audio")) and clip["kind"] != "card",
            "credits": clip["seconds"] * CREDITS_PER_SECOND,
            "prompt": compose_prompt(story, clip, reference, ends_on, ends_close),
        })
        out.append({
            "n": clip["n"], "kind": clip["kind"], "beats": clip["beats"], "seconds": clip["seconds"],
            "link": clip["link"], "reference": reference, "ends_on": ends_on,
            "depends_on": [reference["of_clip"]] if reference["kind"] == "last_frame" else [],
            "steps": steps,
        })
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
    result["problems"] = check_plan(story, result)
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
    if sound and "narration" in sound:
        script = " ".join(line for part in sound["narration"]["parts"] for line in part["lines"])
        lines.append({"id": "voice", "want": f"Voice-over says once, in order: \"{script}\"", "how": "measured: placed; words by ear"})
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
        if clip["seconds"] > MODEL_MAX_SECONDS[video["model"]]:
            problems.append(f"clip {clip['n']}: {clip['seconds']} s is more than {video['model']} makes in one call")
        if len(video["prompt"]) > PROMPT_LIMIT:
            problems.append(f"clip {clip['n']}: the prompt is {len(video['prompt'])} characters, the limit is {PROMPT_LIMIT}")
        for needed in clip["depends_on"]:
            if needed not in made:
                problems.append(f"clip {clip['n']}: needs clip {needed}, which is not made before it")
        made.add(clip["n"])
    return problems


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

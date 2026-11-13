"""The multi-clip video tools: plan the clips, make each clip, join them.

plan_video_production   story in, ordered clips out. Read-only.
create_production_clip  makes one clip of the plan with its one reference. Spends credits.
join_production_clips   joins the finished clips in story order. Needs ffmpeg on the server.

The server keeps no state. The plan travels as `production`, a packed copy of the story that the host passes back.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import tempfile
import uuid
import zlib
from pathlib import Path
from typing import Any, Literal

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from . import kept_files, media_tools
from .video_production import word_match, TRIGGER_IDEAS, TRIGGER_SECONDS, advise, apply_answers, host_cuts, plan, questions

FILMS_PATH = "/films"
FILMS_DIR = Path(os.getenv("MAGIC_HOUR_FILMS_DIR", Path(tempfile.gettempdir()) / "magic-hour-films"))
STILL_WAIT_SECONDS = 120

# The split rule the tool applies. Set from the split benchmark (scripts/split_bench.py), not by the host.
# 2026-11-05, C4 and C5, one run each: cut at a new idea and at 15 s. A cut at every event did worse on C4
# (more last-frame handoffs: the framing locks, the colour drifts).
# User, 2026-11-05: first keep a pictured person's shots in one call; then cut at key ideas.
SPLIT_STRATEGY = "person"
SPLIT_MAX_SECONDS = 15
CARD_SIZES = {"16:9": (854, 480), "9:16": (480, 854), "1:1": (640, 640)}
SPEECH_MIN_SECONDS = 1.0   # less sound than this in a narration track: no voice was made
WORDS_MIN_MATCH = 0.8      # the share of the script's words a transcript must have, in order (A4: nonsense was 0.04)
TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"


async def _transcribe(audio: Path) -> str | None:
    """What a narration says, by Whisper, when the server has OPENAI_API_KEY. None when it cannot be checked."""
    key = os.getenv("OPENAI_API_KEY")
    if not key or not media_tools.have_ffmpeg():
        return None
    wav = audio.with_name(audio.stem + "-16k.wav")
    try:
        await asyncio.to_thread(media_tools._ffmpeg, ["-i", str(audio), "-vn", "-ac", "1", "-ar", "16000", str(wav)])
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            response = await client.post(TRANSCRIBE_URL, headers={"Authorization": f"Bearer {key}"},
                                         data={"model": "whisper-1", "language": "en"}, files={"file": (wav.name, wav.read_bytes(), "audio/wav")})
            response.raise_for_status()
            return response.json().get("text", "")
    except Exception:   # the check is extra: a failed check leaves the words to the ear, it does not fail the join
        return None


class Subject(BaseModel):
    id: str = Field(description="Short name, letters only. Used as @id when its picture is the reference.")
    words: str = Field(description=(
        "One person or thing and how it looks, in one sentence. These exact words go into every clip that shows it."))
    role: Literal["person", "copy", "product", "place"]
    picture: str | None = Field(default=None, description="file_path of the user's picture of it, if the user gave one.")


class Reference(BaseModel):
    kind: Literal["none", "picture", "last_frame", "file"] = Field(description=(
        "none; picture = a subject's picture (`subject`); last_frame = the last frame of an earlier clip (`of_clip`, "
        "default the clip before); file = a picture you made or were given (`file`: its file_path or URL)."))
    subject: str | None = None
    of_clip: int | None = None
    file: str | None = None


class Beat(BaseModel):
    seconds: int = Field(ge=1, description="Length of this beat.")
    text: str = Field(description=(
        "What is seen in this beat: one action, and the framing if it matters (wide, close). Quote a spoken line once, "
        "in the beat where it is said. For a card: how the card looks. A change of state that the model must show "
        "(a paper folded into a shape, a pour that fills a glass, a stage of a build) is one beat for each stage, "
        "each with its own clip; a real product or object that must look right gets a reference picture (a subject's "
        "`picture`, or a still you make first as `reference` file)."))
    kind: Literal["scene", "card"] = "scene"
    place: str | None = Field(default=None, description="Short name of the place. The same name means the same place.")
    subjects: list[str] = Field(default_factory=list, description="ids of the subjects seen in this beat.")
    link: Literal["continues", "event", "moves", "new"] | None = Field(
        default=None,
        description=(
            "How this beat relates to the beat before it. continues = the same shot goes on. event = same place and "
            "subjects, an important new event. moves = a subject carries over to a new place. new = nothing carries over."
        ),
    )
    exact_words: list[str] = Field(default_factory=list, description=(
        "Words shown on screen exactly: on a card, over a held `picture`, or over a scene (a title, a slogan, a "
        "caption). Over a scene, the plan asks how they are made; code draws them exactly (route overlay)."))
    in_scene_words: list[str] = Field(default_factory=list, description=(
        "Words that are part of the picture: a label on a product, a sign, a poster. The video makes them as well as it "
        "can; letters on a moving object may change."))
    background: str | None = Field(default=None, description=(
        "On a card: its background colour as a code, for example #3B1F6B. The card is then drawn by code, colour and "
        "words exact, with no generation call."))
    picture: str | None = Field(default=None, description=(
        "On a card: a picture to hold unchanged for the card's seconds (its file_path from upload_media, or a URL). Code "
        "draws the card's exact_words over it. Use it only for a logo, a screenshot or a picture that must not change. "
        "A reel or slideshow of the user's photos looks static this way: make each photo a scene beat instead, with the "
        "photo as its reference (a subject's `picture`), so it moves, and put its words in exact_words (route overlay). "
        "With `background`: the picture at 80% on that colour; without it: as large as fits, over a blur of itself."))
    model: Literal["ltx-2.5", "minimax-h3"] | None = Field(default=None, description=(
        "The video model for this beat's clip, if you want to choose it. Only minimax-h3 takes a picture reference."))
    words_route: Literal["card", "model", "still", "accept"] | None = Field(default=None, description="Set by an answer to a words question.")
    says: list[str] = Field(default_factory=list, description=(
        "A voice-over: the narrator's sentences that are heard during this beat, word for word, one sentence in each "
        "item. Do not put the voice-over in `text`."))
    clip: int | None = Field(default=None, ge=1, description=(
        "The clip this beat is in: 1, 2, 3 ... in story order. You choose the clips: beats with the same number are made "
        "in one generation call. A card is a clip of its own. Set it on every beat (or on none, and the planner groups "
        "them)."))
    spoken: list[str] = Field(default_factory=list, description=(
        "A line a person on screen says out loud in this beat, word for word. Not the narrator (that is `says`)."))
    reference: Reference | None = Field(default=None, description=(
        "On the first beat of a clip: that clip's one reference, if you want to choose it. Without it the planner chooses."))
    source: str | None = Field(default=None, description=(
        "The user's own clip, used as it is: its file_path from upload_media, a URL, or a finished video project id. "
        "Nothing is generated for this beat (0 credits); it is a clip of its own. Use it to add a voice-over (`says`), music "
        "or captions to the user's clip, or to continue the user's clip (the next clip starts from its last frame). "
        "`seconds`: the clip's length."))
    source_sound: bool = Field(default=True, description="Keep the user's clip's own sound. False makes it silent before the voice-over and music are added.")
    source_speech: bool | None = Field(default=None, description=(
        "Does someone speak in the user's clip? True: their words stay on top, the music goes under them. False: its sound "
        "is only background (wind, a crowd, traffic) and goes under the voice-over and music. Not set: the MCP treats its "
        "sound as speech, so nothing said in it is lost."))
    source_start: float | None = Field(default=None, ge=0, description=(
        "Use the user's clip from this second (default 0). With `source_end`: keep only that part, cut by code (keep the "
        "first 5 s: source_end 5; a following clip then starts from the frame at 5 s)."))
    source_end: float | None = Field(default=None, gt=0, description="Use the user's clip up to this second (default: its end).")


class Story(BaseModel):
    title: str
    aspect: Literal["16:9", "9:16", "1:1"]
    audio: bool = False
    setting: str = Field(description=(
        "The place, light and look of the whole film, in one or two sentences. It is copied into every clip, so it "
        "must be true of every clip: no title cards, no on-screen words, no actions, no people, no model names."))
    subjects: list[Subject] = Field(default_factory=list)
    beats: list[Beat]
    narrator: str | None = Field(default=None, description="For a voice-over: how the narrator sounds, for example 'a calm, warm woman's voice'.")
    music: str | None = Field(default=None, description=(
        "Music under the whole film: its mood and instruments. A reel, an ad or a social post gets music unless the user "
        "asks for silence. Leave empty for no music."))
    music_first: bool = Field(default=False, description=(
        "True only when the music is the point (a music video, a dance clip): the music is never lowered under speech. "
        "Otherwise speech comes first and the music is lowered while someone speaks."))
    music_swell: bool = Field(default=False, description=(
        "True only when the user asks for the music to rise when nobody speaks. Otherwise, in a film with a voice-over or a "
        "spoken line, the music stays at one quiet level under the voice for the whole film."))
    captions: bool = Field(default=False, description="Draw the narrator's sentences on the picture when they are spoken.")
    voice_sample: str | None = Field(default=None, description=(
        "For a voice-over in the user's own voice: a short recording (10-30 s) of a voice the user owns or has rights to, "
        "as its file_path or a URL. Leave it empty otherwise: the voice cloner then reads the script in a default voice "
        "(a woman's, or a man's when `narrator` says so)."))
    voice_route: str | None = Field(default=None, description="Set by the answer to the `voice` question. Leave empty.")


def register_video_production(mcp: FastMCP) -> None:
    @mcp.tool(
        name="plan_video_production",
        title="Plan a multi-clip video",
        description=(
            f"Use for a video longer than {TRIGGER_SECONDS} seconds, or one with {TRIGGER_IDEAS} or more separate "
            "ideas (different places or subjects). Write the story as beats (one action each) and group them into "
            "clips yourself with `clip` on every beat: beats with the same number are made in one generation call. "
            "Pass the user's own words as `request`. Returns the clips to make, in order (the prompt, the model, the "
            "seconds and the one reference of each), a `checklist` of what the result must have, and `advice`: "
            "warnings about your plan, each with the benchmark run that showed the problem. The advice changes "
            "nothing; you decide, and plan again if you change the story. Make each clip with create_production_clip. "
            "A voice-over, music and captions are added to the finished film: put the narrator's sentences in `says` "
            "and set `narrator`, `music`, `captions`. A line a person on screen says goes in `spoken`. Also use it for the "
            "user's own clip, whatever its length: a voice-over, music or captions on it, or a new clip that continues it. "
            "Put the clip in a beat of its own with `source` (its file_path, URL or project id); nothing is generated for "
            "it. Read-only; "
            "spends no credits."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
    )
    def plan_video_production(story: Story, request: str | None = None, answers: dict[str, str] | None = None) -> dict:
        data = story.model_dump(exclude_none=True)
        answer_problems: list[str] = []
        if answers:
            if host_cuts(data) is None:   # the answers keep the clips as they are: number them first
                first = plan_story(data)
                for clip in first.get("clips", []):
                    for n in clip["beats"]:
                        data["beats"][n - 1]["clip"] = clip["n"]
            data, answer_problems = apply_answers(data, answers)
        planned = plan_story(data)
        open_questions = questions(data, planned) if planned.get("clips") else []
        planned["advice"] = advise(data, planned, request) if planned.get("clips") else []
        if answer_problems:
            planned["problems"] = planned.get("problems", []) + answer_problems
            planned["ok"] = False
        if planned["ok"] and open_questions:
            planned["questions"] = open_questions
            planned["how"] = (
                "Answer every question before any clip is made: call plan_video_production again with the same story, "
                "the same request and `answers`: {question id: option}. Each question has a recommendation; choose "
                "what fits the request. The plan above shows the clips as they are now.")
            return planned
        if answers:
            planned["answered"] = answers
        if planned["ok"]:
            planned["production"] = pack(data)
            planned["how"] = (
                "Make the rounds in order. For each clip in a round call create_production_clip(production, clip, made); "
                "the clips of one round do not wait for each other. Then wait_for_video_project for each id. "
                "`made` maps each finished clip number to its video project id. After the last round call "
                "join_production_clips(production, made) and give the user its download_url. Before you deliver, go "
                "through `checklist`: the join returns `checked` for the lines code can measure; confirm the others from "
                "the clips. Tell the user plainly which lines are not met; do not present them as done."
            )
            if planned.get("sound"):
                planned["how"] += (
                    " This plan has sound: call create_production_sound(production) once (at any time), wait for the ids "
                    "it returns, and pass them to join_production_clips as `sound`."
                )
        return planned

    @mcp.tool(
        name="create_production_sound",
        title="Make the voice-over and music of a planned video",
        description=(
            "Makes the sound of a plan from plan_video_production that has a `sound` part: one narration (a video model, or the "
            "voice cloner when the story has `voice_sample`) that reads "
            "all the narrator's sentences in one voice, and one music track. Returns `narration` (a video project id: "
            "wait with wait_for_video_project) and `music` (an audio project id: wait with wait_for_audio_project). "
            "Pass both to join_production_clips as `sound`. Spends credits: 24 for each second of narration, 1 for "
            "each second of music."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    async def create_production_sound(production: str) -> dict:
        return await make_sound(unpack(production))

    @mcp.tool(
        name="create_production_clip",
        title="Make one clip of a planned video",
        description=(
            "Makes one clip of a plan from plan_video_production: the server writes the prompt, picks the model and "
            "attaches the clip's one reference (a picture, its own still, or the last frame of an earlier clip). Pass "
            "`production` from the plan, the clip number, and `made`: the video project id of each finished clip, by "
            "clip number. A clip that starts from an earlier clip needs that clip finished first. Returns the video "
            "project id; then call wait_for_video_project. Spends credits: 24 for each second at 480p."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    async def create_production_clip(production: str, clip: int, made: dict[str, str] | None = None) -> dict:
        return await make_clip(unpack(production), clip, made or {})

    @mcp.tool(
        name="join_production_clips",
        title="Join the clips of a planned video",
        description=(
            "Joins the finished clips of a plan into one video file, in story order, with hard cuts. Pass `production` "
            "from the plan and `made`: the video project id of every clip, by clip number. Returns download_url for "
            "the finished film. If the plan has sound, pass `sound`: the ids from create_production_sound "
            "({narration, music}); the join puts each narrator sentence on its beat, mixes the music under it and draws "
            "the captions. Spends no credits."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    async def join_production_clips(production: str, made: dict[str, str], sound: dict[str, str] | None = None) -> dict:
        return await join_clips(unpack(production), made, sound or {})


def pack(story: dict) -> str:
    return base64.urlsafe_b64encode(zlib.compress(json.dumps(story, separators=(",", ":")).encode())).decode()


def unpack(production: str) -> dict:
    try:
        return json.loads(zlib.decompress(base64.urlsafe_b64decode(production.encode())))
    except Exception:
        raise ToolError("`production` is not valid. Pass the value from plan_video_production unchanged.") from None


def plan_story(story: dict) -> dict:
    """The host's clips when it grouped the beats; else the split rule's."""
    cuts = host_cuts(story)
    if cuts is not None:
        return plan(story, "manual", SPLIT_MAX_SECONDS, cuts=cuts)
    return plan(story, SPLIT_STRATEGY, SPLIT_MAX_SECONDS)


def _planned(story: dict) -> dict:
    planned = plan_story(story)
    if not planned["ok"]:
        raise ToolError("The plan has problems: " + "; ".join(planned["problems"]))
    return planned


def _need_ffmpeg() -> None:
    if not media_tools.have_ffmpeg():
        raise ToolError("This server has no ffmpeg, so it cannot take a last frame or join clips.")


async def _api(method: str, path: str, body: dict | None = None) -> dict:
    from . import openapi_server as server   # at call time: the server module imports this one

    async with server.build_api_client() as client:
        response = await client.request(method, path, json=body, headers={"Authorization": server.current_authorization_header()})
    if response.status_code >= 400:
        raise ToolError(f"Magic Hour refused {path} (HTTP {response.status_code}): {response.text[:300]}")
    return response.json()


async def _download(url: str, out: Path) -> Path:
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        out.write_bytes(response.content)
    return out


def _with_sources(planned: dict, made: dict[str, str]) -> dict[str, str]:
    """`made`, plus the user's own clips (MCP-14): the plan knows where they are, the host does not pass them."""
    return {**{str(c["n"]): c["steps"][0]["source"] for c in planned["clips"] if c.get("made_by") == "user"}, **made}


def _read_kept(file_path: str, out: Path) -> Path:
    try:
        return kept_files.read(file_path, out)
    except kept_files.NotKept:
        raise ToolError(kept_files.not_kept_message(file_path)) from None


async def _finished_video(made: dict[str, str], n: int, folder: Path) -> Path:
    """The file of a finished clip, or of the user's own clip (a URL or a file_path this server kept).
    A clip that is not finished is an error for the host to act on."""
    if str(n) not in made:
        raise ToolError(f"clip {n} is not in `made`. Make it and wait for it first.")
    if made[str(n)].startswith(("http://", "https://")):
        return await _download(made[str(n)], folder / f"clip-{n}.mp4")
    if kept_files.is_file_path(made[str(n)]):
        return _read_kept(made[str(n)], folder / f"clip-{n}.mp4")
    project = await _api("GET", f"/v1/video-projects/{made[str(n)]}")
    if project.get("status") != "complete" or not project.get("downloads"):
        raise ToolError(f"clip {n} (project {made[str(n)]}) is {project.get('status')}. Wait for it with wait_for_video_project.")
    return await _download(project["downloads"][0]["url"], folder / f"clip-{n}.mp4")


async def _clip_file(planned: dict, made: dict[str, str], n: int, folder: Path) -> Path:
    """A finished clip's file; the user's own clip cut to its source_start and source_end (J50b)."""
    file = await _finished_video(made, n, folder)
    clip = next((c for c in planned["clips"] if c["n"] == n), {})
    step = clip.get("steps", [{}])[0] if clip.get("made_by") == "user" else {}
    if step.get("start") or step.get("end"):
        part = folder / f"clip-{n}-part.mp4"
        try:
            return await asyncio.to_thread(media_tools.trim, file, part, float(step.get("start") or 0), step.get("end"))
        except ValueError as error:
            raise ToolError(f"clip {n}: {error}") from None
    return file


async def _fetch_picture(source: str, out: Path) -> Path:
    """A picture by URL, or by a file_path this server kept a copy of."""
    if kept_files.is_file_path(source):
        return _read_kept(source, out)
    if not source.startswith(("http://", "https://")):
        raise ToolError(f"To hold a picture unchanged the server needs to read it: pass its URL or a file_path from upload_media, not {source}.")
    return await _download(source, out)


async def _upload(file: Path, kind: str = "image") -> str:
    """Upload to Magic Hour and keep a copy, so this server can read the file again."""
    data = file.read_bytes()
    item = (await _api("POST", "/v1/files/upload-urls", {"items": [{"type": kind, "extension": file.suffix.lstrip(".").lower()}]}))["items"][0]
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        (await client.put(item["upload_url"], content=data)).raise_for_status()
    kept_files.keep(item["file_path"], data)
    return item["file_path"]


async def make_clip(story: dict, n: int, made: dict[str, str]) -> dict:
    planned = _planned(story)
    clip = next((c for c in planned["clips"] if c["n"] == n), None)
    if clip is None:
        raise ToolError(f"The plan has clips 1 to {len(planned['clips'])}; there is no clip {n}.")
    if clip.get("made_by") == "code":
        return {"clip": n, "id": "drawn", "credits_charged": 0, "made_by": "code",
                "next": "Nothing to make or wait for: the join draws this card. Put \"drawn\" in `made` for this clip."}
    if clip.get("made_by") == "user":
        return {"clip": n, "id": clip["steps"][0]["source"], "credits_charged": 0, "made_by": "user",
                "next": "Nothing to make or wait for: the user's own clip is used as it is. The join takes it from the plan."}
    made = _with_sources(planned, made)
    reference, video, credits = clip["reference"], clip["steps"][-1], 0
    name = f"{story.get('title', 'Video')} · clip {n}"
    body: dict[str, Any] = {"name": name, "end_seconds": video["seconds"], "model": video["model"], "resolution": video["resolution"],
                            "audio": video["audio"], "style": {"prompt": video["prompt"]}}
    if reference["kind"] == "last_frame":
        _need_ffmpeg()
        with tempfile.TemporaryDirectory() as folder:
            source = await _clip_file(planned, made, reference["of_clip"], Path(folder))
            frame = await asyncio.to_thread(media_tools.last_frame, source, Path(folder) / "start.jpg")
            body["assets"] = {"image_file_path": await _upload(frame)}
    elif reference["kind"] in ("still", "scene_still"):
        still = clip["steps"][0]
        created = await _api("POST", "/v1/ai-image-generator", {
            "name": f"{name} · still", "image_count": 1, "model": still["model"], "aspect_ratio": story["aspect"],
            "resolution": "640px", "style": {"prompt": still["prompt"]}})
        credits += int(created.get("credits_charged", 0))
        for _ in range(STILL_WAIT_SECONDS // 3):
            project = await _api("GET", f"/v1/image-projects/{created['id']}")
            if project.get("status") in ("complete", "error", "canceled"):
                break
            await asyncio.sleep(3)
        if project.get("status") != "complete" or not project.get("downloads"):
            raise ToolError(f"The still for clip {n} did not finish (image project {created['id']}: {project.get('status')}).")
        body["assets"] = {"image_file_path": project["downloads"][0]["url"]}
    else:
        body["aspect_ratio"] = story["aspect"]
        if reference["kind"] in ("picture", "file"):
            body["references"] = [{"name": reference["subject"], "file_path": reference["file"]}]
    created = await _api("POST", "/v1/image-to-video" if "assets" in body else "/v1/text-to-video", body)
    return {"clip": n, "id": created["id"], "credits_charged": credits + int(created.get("credits_charged", 0)),
            "seconds": video["seconds"], "model": video["model"], "reference": reference["kind"],
            "next": "wait_for_video_project with this id"}


async def make_sound(story: dict) -> dict:
    sound = _planned(story).get("sound")
    if not sound:
        raise ToolError("This plan has no sound. Put the narrator's sentences in `says`, or set `music`, and plan again.")
    out: dict[str, Any] = {"credits_charged": 0}
    if "narration" in sound and sound["narration"].get("tool") == "voice_cloner":
        n = sound["narration"]
        created = await _api("POST", "/v1/ai-voice-cloner", {
            "name": f"{story.get('title', 'Video')} · narration", "assets": {"audio_file_path": n["sample"]},
            "style": {"prompt": n["script"]}})
        out["narration"] = created["id"]
        out["credits_charged"] += int(created.get("credits_charged", 0))
    elif "narration" in sound:
        n = sound["narration"]
        created = await _api("POST", "/v1/text-to-video", {
            "name": f"{story.get('title', 'Video')} · narration", "end_seconds": n["seconds"], "aspect_ratio": story["aspect"],
            "model": n["model"], "resolution": n["resolution"], "audio": True, "style": {"prompt": n["prompt"]}})
        out["narration"] = created["id"]
        out["credits_charged"] += int(created.get("credits_charged", 0))
    if "music" in sound:
        m = sound["music"]
        created = await _api("POST", "/v1/ai-music-generator", {
            "name": f"{story.get('title', 'Video')} · music", "duration": m["seconds"], "style": {"prompt": m["prompt"], "instrumental": True}})
        out["music"] = created["id"]
        out["credits_charged"] += int(created.get("credits_charged", 0))
    cloned = sound.get("narration", {}).get("tool") == "voice_cloner"
    out["next"] = (f"wait_for_{'audio' if cloned else 'video'}_project with `narration`, wait_for_audio_project with `music`; then pass "
                   "{narration, music} to join_production_clips as `sound`")
    return out


async def _finished(kind: str, project_id: str, out: Path) -> Path:
    project = await _api("GET", f"/v1/{kind}-projects/{project_id}")
    if project.get("status") != "complete" or not project.get("downloads"):
        raise ToolError(f"The {kind} project {project_id} is {project.get('status')}. Wait for it first.")
    return await _download(project["downloads"][0]["url"], out)


def _add_sound(sound_plan: dict, film: Path, narration: Path | None, music: Path | None, out: Path,
               clip_starts: dict[int, float] | None = None, spoken: list[tuple[float, float]] | None = None,
               music_first: bool = False, music_swell: bool = False) -> dict:
    """The file steps of the sound, in one place (run in a thread). Returns what was done.
    clip_starts: where each clip really starts in the joined film (a clip is often a little longer than planned)."""
    parts, done = [], {"narration": False, "music": bool(music), "captions": False}
    if narration:
        wanted = sound_plan["narration"]["parts"]
        spans = media_tools.speech_spans(narration)
        fine = media_tools.speech_spans(narration, noise_db=-30, min_gap=0.04)
        found = media_tools.align_parts(spans, [" ".join(p["lines"]) for p in wanted], fine)
        parts = [{"start": start, "end": end, "lines": p["lines"],
                  "at": clip_starts[p["clip"]] + p["inside"] + 0.5 if clip_starts and p["clip"] in clip_starts else p["at"]}
                 for p, (start, end) in zip(wanted, found)]
        done["narration"] = bool(parts)
        fit = media_tools.fit_parts(parts, media_tools.probe_seconds(film))
        parts = fit["parts"]
        if fit["moved"]:   # I46a, E28c: the narration was longer than its beats; no word is cut now
            done["voice_fit"] = {"tempo": fit["tempo"], "held_end_seconds": fit["hold"]}
        if fit["hold"] > 0:
            film = media_tools.hold_end(film, fit["hold"], out.with_name(out.stem + "-held.mp4"))
    mixed = out.with_name(out.stem + "-mixed.mp4")
    layers = out.with_name(out.stem + ".layers")   # each layer kept beside the film, for a later mix
    mix = media_tools.add_sound(film, mixed, narration if parts else None, parts, music, spoken, music_first, layers, music_swell)
    done["loudness_lufs"] = mix["lufs"]
    if sound_plan.get("captions") and parts and media_tools.have_captions():
        timed = []
        for part in parts:   # each sentence gets a share of its part, by its length
            total, at = sum(media_tools.letters(line) for line in part["lines"]) or 1, part["at"]
            for line in part["lines"]:
                length = (part["end"] - part["start"]) / part.get("tempo", 1.0) * media_tools.letters(line) / total
                timed.append({"text": line, "start": at, "end": at + length})
                at += length
        for line, after in zip(timed, timed[1:]):   # one caption at a time
            line["end"] = min(line["end"], after["start"])
        media_tools.draw_captions(mixed, timed, out)
        mixed.unlink()
        done["captions"] = True
    else:
        mixed.replace(out)
    if (done.get("voice_fit") or {}).get("held_end_seconds"):
        film.unlink(missing_ok=True)   # the copy with the held frame; the mixed film has replaced it
    return done


async def join_clips(story: dict, made: dict[str, str], sound: dict[str, str] | None = None) -> dict:
    _need_ffmpeg()
    planned = _planned(story)
    sound_plan = planned.get("sound") or {}
    sound = sound or {}
    missing = [k for k in ("narration", "music") if k in sound_plan and k not in sound]
    if missing:
        raise ToolError(f"This plan has sound. Call create_production_sound, wait for its ids, and pass `sound` with: {', '.join(missing)}.")
    FILMS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.mp4"
    result: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as folder:
        by_n = {c["n"]: c for c in planned["clips"]}
        made = _with_sources(planned, made)
        files = []
        for n in planned["join"]:
            if by_n[n].get("made_by") == "code":   # a card made by code: exact colour, words or picture
                step = by_n[n]["steps"][0]
                if step["tool"] == "hold_picture":
                    source = await _fetch_picture(step["picture"], Path(folder) / f"picture-{n}")
                    png = await asyncio.to_thread(media_tools.fit_picture, source, step.get("background"), CARD_SIZES[story["aspect"]],
                                                  Path(folder) / f"card-{n}.png", step.get("words"))
                else:
                    png = await asyncio.to_thread(media_tools.draw_card, step["words"], step["background"], CARD_SIZES[story["aspect"]], Path(folder) / f"card-{n}.png")
                files.append(await asyncio.to_thread(media_tools.still_video, png, step["seconds"], Path(folder) / f"clip-{n}.mp4"))
            else:
                files.append(await _clip_file(planned, made, n, Path(folder)))
        probes = [await asyncio.to_thread(media_tools.probe, file) for file in files]
        # A generated clip is cut to its planned length (minimax-h3 returns at least about 2 s); the user's clip is kept
        # whole, or as cut by source_start and source_end above.
        cut = [None if by_n[n].get("made_by") == "user" else float(by_n[n]["seconds"]) for n in planned["join"]]
        lengths = {n: min(p["seconds"], c) if c else p["seconds"] for n, p, c in zip(planned["join"], probes, cut)}
        size = media_tools.size_for(story["aspect"], probes[0])
        # a line that runs to its clip's end stays on to the next cut (H42b: the words left a moment before the end)
        overlays = [dict(line, start=line["start"] + at, end=(lengths[n] + 0.1 if line["end"] >= lengths[n] - 0.05 else line["end"]) + at)
                    for n, at in zip(planned["join"], [sum(lengths[m] for m in planned["join"][:k]) for k in range(len(files))])
                    for line in by_n[n].get("overlay", [])]
        joined = Path(folder) / "joined.mp4" if (sound_plan or overlays) else FILMS_DIR / name
        # a clip keeps its own sound when it was made with sound (the story's audio, or a spoken line in it)
        keep = [by_n[n]["steps"][0]["sound"] if by_n[n].get("made_by") == "user"
                else bool(by_n[n]["steps"][0].get("audio", story.get("audio"))) for n in planned["join"]]
        await asyncio.to_thread(media_tools.join, files, joined, keep, cut, size)
        if overlays:   # exact words over a scene, drawn by code (words_route overlay)
            worded = Path(folder) / "worded.mp4" if sound_plan else FILMS_DIR / name
            await asyncio.to_thread(media_tools.draw_captions, joined, [dict(o, place="top", large=True) for o in overlays], worded)
            joined = worded
            result["words_drawn"] = len(overlays)
        if sound_plan:
            cloned = (sound_plan.get("narration") or {}).get("tool") == "voice_cloner"
            narration = (await _finished("audio" if cloned else "video", sound["narration"], Path(folder) / ("narration" if cloned else "narration.mp4"))
                         if "narration" in sound_plan else None)
            if narration is not None:
                spans = await asyncio.to_thread(media_tools.speech_spans, narration)
                speech_seconds = round(sum(end - start for start, end in spans), 1)
                heard_words = await _transcribe(narration)
            music = await _finished("audio", sound["music"], Path(folder) / "music") if "music" in sound_plan else None
            starts, at = {}, 0.0
            for n in planned["join"]:
                starts[n] = at
                at += lengths[n]
            spoken = []   # where a person on screen speaks: the beats with a spoken line, at their place in the film
            for n in planned["join"]:
                inside = 0.0
                for b in by_n[n].get("beats", []):
                    beat = story["beats"][b - 1]
                    if beat.get("spoken"):
                        spoken.append((starts[n] + inside, starts[n] + min(inside + beat["seconds"], lengths[n])))
                    inside += beat["seconds"]
            # the user's clip with its sound kept: someone may speak in it. Unless the host says it is only background
            # (source_speech false), its sound is speech: never lowered, the music sits under it.
            kept_as_speech = [n for n, k in zip(planned["join"], keep) if k and by_n[n].get("made_by") == "user"
                              and by_n[n]["steps"][0].get("speech") is not False]
            spoken += [(starts[n], starts[n] + lengths[n]) for n in kept_as_speech]
            result["sound"] = await asyncio.to_thread(_add_sound, sound_plan, joined, narration, music, FILMS_DIR / name, starts,
                                                      spoken, bool(story.get("music_first")), bool(story.get("music_swell")))
            if kept_as_speech:
                result["sound"]["user_clip_as_speech"] = kept_as_speech
            if narration is not None:
                result["sound"]["speech_seconds"] = speech_seconds
                if heard_words is not None:
                    script = " ".join(line for part in sound_plan["narration"]["parts"] for line in part["lines"])
                    result["sound"]["heard"] = heard_words
                    result["sound"]["words_match"] = word_match(heard_words, script)
    film = FILMS_DIR / name
    measured = await asyncio.to_thread(media_tools.probe, film)
    loud = await asyncio.to_thread(media_tools.loudness_db, film)
    base = os.getenv("MAGIC_HOUR_MCP_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
    url = await asyncio.to_thread(media_tools.store, film, name, FILMS_DIR, base)
    checked, unchecked = _check_film(planned, story, measured, loud, lengths, result.get("sound") or {})
    return {"download_url": url, "seconds": round(measured["seconds"], 1), "width": measured["width"], "height": measured["height"],
            "clips": len(files), **result, "checked": checked, "unchecked": unchecked,
            "not_met": [c["want"] for c in checked if c["result"] != "yes"]}


def _check_film(planned: dict, story: dict, measured: dict, loud: float | None, lengths: dict[int, float], done: dict) -> tuple[list[dict], list[str]]:
    """The checklist lines code can measure, against the finished film. The others are returned for the host to confirm."""
    checked, unchecked = [], []
    ratio = {"16:9": 16 / 9, "9:16": 9 / 16, "1:1": 1.0}[story["aspect"]]
    for line in planned["checklist"]:
        want, kind = line["want"], line["id"].split("-")[0]
        if kind == "file":
            ok = abs(measured["seconds"] - planned["seconds"]) <= 1 and abs(measured["width"] / measured["height"] - ratio) < 0.05 * ratio
            checked.append({"want": want, "got": f"{measured['seconds']:.1f} s, {measured['width']}x{measured['height']}", "result": "yes" if ok else "no"})
        elif kind == "card":
            n = int(line["id"].split("-")[1])
            clip = next(c for c in planned["clips"] if c["n"] == n)
            ok = abs(lengths.get(n, 0) - clip["seconds"]) <= 0.5
            checked.append({"want": want, "got": f"the card clip is {lengths.get(n, 0):.1f} s; the words are checked by eye", "result": "yes" if ok else "no"})
        elif kind == "voice":
            heard = done.get("speech_seconds")
            if not done.get("narration"):
                checked.append({"want": want, "got": "no narration was placed", "result": "no"})
            elif heard is not None and heard < SPEECH_MIN_SECONDS:
                # B1, 7 November: a narration call came back silent and was counted as placed. Speech is measured now.
                checked.append({"want": want, "got": f"the narration track has {heard:.1f} s of sound in it: no voice was made; make the sound again", "result": "no"})
            elif done.get("words_match") is not None and done["words_match"] < WORDS_MIN_MATCH:
                # A4, 8 November: a narration said made-up words and passed the speech check. The words are compared now.
                checked.append({"want": want, "got": f"the narration says other words ({round(done['words_match'] * 100)}% of the script): "
                                f"\"{done['heard'][:200]}\"; make the sound again or tell the user", "result": "no"})
            elif done.get("words_match") is not None:
                checked.append({"want": want, "got": f"narration placed on its beats; a transcript has {round(done['words_match'] * 100)}% of the script's words, in order", "result": "yes"})
            else:
                checked.append({"want": want, "got": f"narration placed on its beats, {heard or 0:.1f} s of speech; the words are checked by ear", "result": "yes"})
            if fit := done.get("voice_fit"):   # I46a: the narration was longer than its beats
                checked[-1]["got"] += (f"; the voice-over was longer than its beats: moved earlier"
                                       + (f", read {round((fit['tempo'] - 1) * 100)}% faster" if fit["tempo"] > 1 else "")
                                       + (f", the last frame held {fit['held_end_seconds']} s longer; tell the user" if fit["held_end_seconds"] else ""))
        elif kind == "music":
            checked.append({"want": want, "got": "music mixed under the film" if done.get("music") else "no music", "result": "yes" if done.get("music") else "no"})
        elif kind == "captions":
            checked.append({"want": want, "got": "captions drawn" if done.get("captions") else "no captions (the server has no drawing library)", "result": "yes" if done.get("captions") else "no"})
        elif kind == "scene":
            ok = loud is not None and loud > -50
            checked.append({"want": want, "got": f"peak level {loud:.0f} dB" if loud is not None else "no sound track", "result": "yes" if ok else "no"})
        elif kind == "source":
            n = int(line["id"].split("-")[1])
            clip = next(c for c in planned["clips"] if c["n"] == n)
            ok = abs(lengths.get(n, 0) - clip["seconds"]) <= 1
            checked.append({"want": want, "got": f"the user's clip is {lengths.get(n, 0):.1f} s in the film", "result": "yes" if ok else "no"})
        elif kind == "silent":
            ok = loud is None or loud < -60
            checked.append({"want": want, "got": "silent" if ok else f"there is sound, peak level {loud:.0f} dB", "result": "yes" if ok else "no"})
        else:
            unchecked.append(want)
    return checked, unchecked


FILM_TYPES = {".mp4": "video/mp4", ".png": "image/png", ".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav"}


def film_file(name: str) -> Path | None:
    """The stored film with this name, if the name is one this server made."""
    file = FILMS_DIR / name
    return file if name.endswith(tuple(FILM_TYPES)) and "/" not in name and ".." not in name and file.exists() else None

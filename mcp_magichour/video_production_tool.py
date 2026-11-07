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

from . import media_tools
from .video_production import TRIGGER_IDEAS, TRIGGER_SECONDS, plan

FILMS_PATH = "/films"
FILMS_DIR = Path(os.getenv("MAGIC_HOUR_FILMS_DIR", Path(tempfile.gettempdir()) / "magic-hour-films"))
STILL_WAIT_SECONDS = 120

# The split rule the tool applies. Set from the split benchmark (scripts/split_bench.py), not by the host.
# 2026-11-05, C4 and C5, one run each: cut at a new idea and at 15 s. A cut at every event did worse on C4
# (more last-frame handoffs: the framing locks, the colour drifts).
# User, 2026-11-05: first keep a pictured person's shots in one call; then cut at key ideas.
SPLIT_STRATEGY = "person"
SPLIT_MAX_SECONDS = 15


class Subject(BaseModel):
    id: str = Field(description="Short name, letters only. Used as @id when its picture is the reference.")
    words: str = Field(description=(
        "One person or thing and how it looks, in one sentence. These exact words go into every clip that shows it."))
    role: Literal["person", "copy", "product", "place"]
    picture: str | None = Field(default=None, description="file_path of the user's picture of it, if the user gave one.")


class Beat(BaseModel):
    seconds: int = Field(ge=1, description="Length of this beat.")
    text: str = Field(description=(
        "What is seen in this beat: one action, and the framing if it matters (wide, close). Quote a spoken line once, "
        "in the beat where it is said. For a card: how the card looks."))
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
    exact_words: list[str] = Field(default_factory=list, description="For a card: the words on it, exactly.")
    says: list[str] = Field(default_factory=list, description=(
        "A voice-over: the narrator's sentences that are heard during this beat, word for word, one sentence in each "
        "item. Do not put the voice-over in `text`."))


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
    music: str | None = Field(default=None, description="Music under the whole film: its mood and instruments. Leave empty for no music.")
    captions: bool = Field(default=False, description="Draw the narrator's sentences on the picture when they are spoken.")


def register_video_production(mcp: FastMCP) -> None:
    @mcp.tool(
        name="plan_video_production",
        title="Plan a multi-clip video",
        description=(
            f"Use for a video longer than {TRIGGER_SECONDS} seconds, or one with {TRIGGER_IDEAS} or more separate "
            "ideas (different places or subjects). Do not put such a video into one generation call: the model "
            "repeats and reorders the shots. Write the story as beats (one action each) and pass it here. Returns "
            "the clips to make, in order: for each clip the create tool, the model, the seconds, the prompt and its "
            "one reference (nothing, a picture, the last frame of an earlier clip, or its own still). Make each clip "
            "with create_production_clip. A voice-over, music and captions are added to the finished film, not made "
            "inside the clips: put the narrator's sentences in `says` of each beat and set `narrator`, `music`, "
            "`captions`; keep `audio` for sound that belongs to the scene (rain, a line a person on screen says). "
            "Read-only; spends no credits."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
    )
    def plan_video_production(story: Story) -> dict:
        data = story.model_dump(exclude_none=True)
        planned = plan(data, SPLIT_STRATEGY, SPLIT_MAX_SECONDS)
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
            "Makes the sound of a plan from plan_video_production that has a `sound` part: one narration that reads "
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


def _planned(story: dict) -> dict:
    planned = plan(story, SPLIT_STRATEGY, SPLIT_MAX_SECONDS)
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


async def _finished_video(made: dict[str, str], n: int, folder: Path) -> Path:
    """The file of a finished clip. A clip that is not finished is an error for the host to act on."""
    if str(n) not in made:
        raise ToolError(f"clip {n} is not in `made`. Make it and wait for it first.")
    project = await _api("GET", f"/v1/video-projects/{made[str(n)]}")
    if project.get("status") != "complete" or not project.get("downloads"):
        raise ToolError(f"clip {n} (project {made[str(n)]}) is {project.get('status')}. Wait for it with wait_for_video_project.")
    return await _download(project["downloads"][0]["url"], folder / f"clip-{n}.mp4")


async def _upload(file: Path) -> str:
    item = (await _api("POST", "/v1/files/upload-urls", {"items": [{"type": "image", "extension": file.suffix.lstrip(".")}]}))["items"][0]
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        (await client.put(item["upload_url"], content=file.read_bytes())).raise_for_status()
    return item["file_path"]


async def make_clip(story: dict, n: int, made: dict[str, str]) -> dict:
    planned = _planned(story)
    clip = next((c for c in planned["clips"] if c["n"] == n), None)
    if clip is None:
        raise ToolError(f"The plan has clips 1 to {len(planned['clips'])}; there is no clip {n}.")
    reference, video, credits = clip["reference"], clip["steps"][-1], 0
    name = f"{story.get('title', 'Video')} · clip {n}"
    body: dict[str, Any] = {"name": name, "end_seconds": video["seconds"], "model": video["model"], "resolution": video["resolution"],
                            "audio": video["audio"], "style": {"prompt": video["prompt"]}}
    if reference["kind"] == "last_frame":
        _need_ffmpeg()
        with tempfile.TemporaryDirectory() as folder:
            source = await _finished_video(made, reference["of_clip"], Path(folder))
            frame = await asyncio.to_thread(media_tools.last_frame, source, Path(folder) / "start.jpg")
            body["assets"] = {"image_file_path": await _upload(frame)}
    elif reference["kind"] == "still":
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
        if reference["kind"] == "picture":
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
    if "narration" in sound:
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
    out["next"] = ("wait_for_video_project with `narration`, wait_for_audio_project with `music`; then pass "
                   "{narration, music} to join_production_clips as `sound`")
    return out


async def _finished(kind: str, project_id: str, out: Path) -> Path:
    project = await _api("GET", f"/v1/{kind}-projects/{project_id}")
    if project.get("status") != "complete" or not project.get("downloads"):
        raise ToolError(f"The {kind} project {project_id} is {project.get('status')}. Wait for it first.")
    return await _download(project["downloads"][0]["url"], out)


def _add_sound(sound_plan: dict, film: Path, narration: Path | None, music: Path | None, out: Path,
               clip_starts: dict[int, float] | None = None) -> dict:
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
    mixed = out.with_name(out.stem + "-mixed.mp4")
    media_tools.add_sound(film, mixed, narration if parts else None, parts, music)
    if sound_plan.get("captions") and parts and media_tools.have_captions():
        timed = []
        for part in parts:   # each sentence gets a share of its part, by its length
            total, at = sum(media_tools.letters(line) for line in part["lines"]) or 1, part["at"]
            for line in part["lines"]:
                length = (part["end"] - part["start"]) * media_tools.letters(line) / total
                timed.append({"text": line, "start": at, "end": at + length})
                at += length
        for line, after in zip(timed, timed[1:]):   # one caption at a time
            line["end"] = min(line["end"], after["start"])
        media_tools.draw_captions(mixed, timed, out)
        mixed.unlink()
        done["captions"] = True
    else:
        mixed.replace(out)
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
        files = [await _finished_video(made, n, Path(folder)) for n in planned["join"]]
        lengths = {n: (await asyncio.to_thread(media_tools.probe, file))["seconds"] for n, file in zip(planned["join"], files)}
        joined = Path(folder) / "joined.mp4" if sound_plan else FILMS_DIR / name
        await asyncio.to_thread(media_tools.join, files, joined, bool(story.get("audio")))
        if sound_plan:
            narration = await _finished("video", sound["narration"], Path(folder) / "narration.mp4") if "narration" in sound_plan else None
            music = await _finished("audio", sound["music"], Path(folder) / "music") if "music" in sound_plan else None
            starts, at = {}, 0.0
            for n in planned["join"]:
                starts[n] = at
                at += lengths[n]
            result["sound"] = await asyncio.to_thread(_add_sound, sound_plan, joined, narration, music, FILMS_DIR / name, starts)
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
            ok = bool(done.get("narration"))
            checked.append({"want": want, "got": "narration placed on its beats; the words are checked by ear" if ok else "no narration was placed", "result": "yes" if ok else "no"})
        elif kind == "music":
            checked.append({"want": want, "got": "music mixed under the film" if done.get("music") else "no music", "result": "yes" if done.get("music") else "no"})
        elif kind == "captions":
            checked.append({"want": want, "got": "captions drawn" if done.get("captions") else "no captions (the server has no drawing library)", "result": "yes" if done.get("captions") else "no"})
        elif kind == "scene":
            ok = loud is not None and loud > -50
            checked.append({"want": want, "got": f"peak level {loud:.0f} dB" if loud is not None else "no sound track", "result": "yes" if ok else "no"})
        elif kind == "silent":
            ok = loud is None or loud < -60
            checked.append({"want": want, "got": "silent" if ok else f"there is sound, peak level {loud:.0f} dB", "result": "yes" if ok else "no"})
        else:
            unchecked.append(want)
    return checked, unchecked


def film_file(name: str) -> Path | None:
    """The stored film with this name, if the name is one this server made."""
    file = FILMS_DIR / name
    return file if name.endswith(".mp4") and "/" not in name and ".." not in name and file.exists() else None

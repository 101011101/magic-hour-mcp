"""New media tools for tool management (MCP-29 to MCP-35): jobs no existing tool does.

Tool management is separate from video composition (mcp-upgrade/prd/tool-management/README.md, Isolation). This module
changes no shared file. It reuses, unchanged, the shared media code: media_tools (ffmpeg work) and media_helpers_tool
(fetch a user's file, deliver a made file). It imports nothing directly from plan_request, video_production,
video_production_tool or gates.
Registered with the planner's switch: MAGIC_HOUR_TOOL_PLAN=on. Off (the default), the server is as before.
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import media_tools
from .media_helpers_tool import _deliver, _fetch_media
from .tool_plan import enabled

Original = Literal["keep", "under", "replace"]


# ---- MCP-29: sound on the user's video

def mix_onto_video(film: Path, out: Path, music: Path | None = None, voice: Path | None = None, voice_at: float = 0.0,
                   original: Original = "under", music_swell: bool = False) -> dict:
    """Lay music and/or a voice-over on a video, by code (no generation).

    original: keep = the video's own sound stays at full level where it is heard (speech, radio calls) and the music
    sits under it; under = the video's own sound is lowered under the new sound; replace = the video's own sound is
    removed. A voice-over longer than the video is read up to a little faster, then the last frame is held, so no word
    is cut (media_tools.fit_parts). Loudness is set to media_tools.TARGET_LUFS. Returns what was done."""
    if not (music or voice):
        raise ValueError("give music, a voice, or both")
    work = Path(tempfile.mkdtemp())
    if original == "replace":
        silent = work / "silent.mp4"   # not media_tools.join: it calls "ffmpeg" by name (notes-for-ray.md)
        media_tools._ffmpeg(["-i", str(film), "-an", "-c:v", "copy", str(silent)])
        film = silent
    seconds = media_tools.probe_seconds(film)
    spoken = []
    if original == "keep" and media_tools.probe(film)["audio"]:
        spoken = media_tools.speech_spans(film)
    parts, fit = [], {"tempo": 1.0, "hold": 0.0, "moved": False}
    if voice:
        length = media_tools.probe_seconds(voice)
        fit = media_tools.fit_parts([{"start": 0.0, "end": length, "at": max(0.0, voice_at)}], seconds)
        parts = fit["parts"]
        if fit["hold"] > 0:
            film = media_tools.hold_end(film, fit["hold"], work / "held.mp4")
    mix = media_tools.add_sound(film, out, narration=voice, parts=parts or None, music=music, spoken=spoken,
                                music_swell=music_swell)
    return {"seconds": round(media_tools.probe_seconds(out), 2), "lufs": mix["lufs"], "original": original,
            "kept_spoken_spans": len(spoken), "voice_tempo": round(fit["tempo"], 3), "held_end_seconds": round(fit["hold"], 2)}


def register_tool_media(mcp: FastMCP) -> None:
    if not enabled():
        return

    @mcp.tool(
        name="add_sound_to_video",
        title="Add music or a voice-over to a video",
        description=(
            "Lay music and/or a voice-over on the user's own video, by code: the picture is kept exactly, nothing is "
            "generated, 0 credits. Make the sound first (generate_music, or a voice), then call this. `video`: a "
            "file_path from upload_media, a URL, or a finished video project id. `music`, `voice`: a file_path, URL or "
            "finished audio project id. `original`: keep = the video's own speech or sound stays clear and the music "
            "sits under it (music under the user's talk or radio calls); under = the video's own sound is lowered; "
            "replace = the video's own sound is removed (a new soundtrack or a narration instead of the conversation). "
            "`voice_at`: seconds into the video where the voice starts. A voice longer than the video is read a little "
            "faster, then the last frame is held, so no word is cut. `music_swell`: the music rises between spoken "
            "lines. Returns download_url and video_file_path."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    async def add_sound_to_video(video: str, music: str | None = None, voice: str | None = None,
                                 original: Original = "under", voice_at: float = 0.0, music_swell: bool = False) -> dict:
        if not media_tools.have_ffmpeg():
            raise ToolError("This server has no ffmpeg, so it cannot mix sound onto a video.")
        if not (music or voice):
            raise ToolError("Give `music`, `voice`, or both.")
        with tempfile.TemporaryDirectory() as folder:
            f = Path(folder)
            (f / "v").mkdir(); (f / "m").mkdir(); (f / "n").mkdir()
            film, picture = await _fetch_media(video, f / "v", ("video",))
            if picture:
                raise ToolError("`video` is a picture; give a video.")
            music_file = (await _fetch_media(music, f / "m", ("audio", "video")))[0] if music else None
            voice_file = (await _fetch_media(voice, f / "n", ("audio", "video")))[0] if voice else None
            out = f / "with-sound.mp4"
            try:
                done = await asyncio.to_thread(mix_onto_video, film, out, music_file, voice_file, voice_at, original, music_swell)
            except ValueError as error:
                raise ToolError(str(error)) from None
            return {**await _deliver(out, False), "done": done}

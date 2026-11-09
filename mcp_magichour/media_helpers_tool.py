"""Two general helpers on any video: take its last frame, join videos. They decide nothing; the host chooses when to use them.

A video is named by a Magic Hour video project id (a finished one) or a URL the server can download.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import media_tools
from .video_production_tool import FILMS_DIR, _api, _download, _need_ffmpeg, _upload


async def _fetch(video: str, out: Path) -> Path:
    if video.startswith(("http://", "https://")):
        return await _download(video, out)
    project = await _api("GET", f"/v1/video-projects/{video}")
    if project.get("status") != "complete" or not project.get("downloads"):
        raise ToolError(f"video project {video} is {project.get('status')}. Wait for it first, or pass a URL.")
    return await _download(project["downloads"][0]["url"], out)


def register_media_helpers(mcp: FastMCP) -> None:
    @mcp.tool(
        name="get_last_frame",
        description=(
            "Take the last frame of a video as a picture, uploaded to Magic Hour. `video`: a finished video project id or "
            "a video URL. Returns `file_path`, usable as the start image of create_video_from_image. Spends no credits."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    async def get_last_frame(video: str) -> dict:
        _need_ffmpeg()
        with tempfile.TemporaryDirectory() as folder:
            clip = await _fetch(video, Path(folder) / "video.mp4")
            frame = await asyncio.to_thread(media_tools.last_frame, clip, Path(folder) / "last-frame.jpg")
            return {"file_path": await _upload(frame)}

    @mcp.tool(
        name="join_videos",
        description=(
            "Join videos end to end with hard cuts, in the order given, into one file. `videos`: finished video project ids "
            "or video URLs. Every video is fitted to the first one's size. `silent`: remove all sound. Returns the film's "
            "download URL, its length and its loudness. Spends no credits."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
    )
    async def join_videos(videos: list[str], silent: bool = False) -> dict:
        _need_ffmpeg()
        if not videos:
            raise ToolError("Give at least one video.")
        FILMS_DIR.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}.mp4"
        with tempfile.TemporaryDirectory() as folder:
            files = [await _fetch(v, Path(folder) / f"part-{i}.mp4") for i, v in enumerate(videos)]
            await asyncio.to_thread(media_tools.join, files, FILMS_DIR / name, not silent)
        film = FILMS_DIR / name
        measured = await asyncio.to_thread(media_tools.probe, film)
        loud = await asyncio.to_thread(media_tools.loudness_db, film)
        base = os.getenv("MAGIC_HOUR_MCP_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
        url = await asyncio.to_thread(media_tools.store, film, name, FILMS_DIR, base)
        return {"download_url": url, "seconds": round(measured["seconds"], 1), "width": measured["width"],
                "height": measured["height"], "loudness_db": loud}

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


# ---- MCP-35: colour change by code

def recolour(source: Path, out: Path, warmth: float = 0.0, saturation: float = 1.0, brightness: float = 0.0,
             contrast: float = 1.0) -> Path:
    """Change only the colours of a picture or video, nothing redrawn. warmth -1 (cooler) to 1 (warmer); saturation 0
    (black and white) to 2; brightness -0.5 to 0.5; contrast 0.5 to 2. A video keeps its sound."""
    w = max(-1.0, min(1.0, warmth))
    picture = source.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    sat = max(0.0, min(2.0, saturation))
    steps = [f"colorchannelmixer=rr={1 + 0.15 * w:.3f}:gg=1:bb={1 - 0.15 * w:.3f}"]   # warmer: more red, less blue
    steps.append(f"eq=saturation={sat:.3f}:brightness={max(-0.5, min(0.5, brightness)):.3f}:contrast={max(0.5, min(2.0, contrast)):.3f}")
    if sat == 0:
        steps.append("format=gray")   # black and white exactly, no tint left by the colour conversion
    steps.append("format=rgb24" if picture else "format=yuv420p")
    args = ["-i", str(source), "-vf", ",".join(steps)]
    if not picture:
        args += ["-c:v", "libx264", "-c:a", "copy"]
    media_tools._ffmpeg([*args, str(out)])
    return out


# ---- MCP-30: pictures side by side

SHEET_SIZES = {"16:9": (1280, 720), "1:1": (1080, 1080), "9:16": (720, 1280), "4:5": (1080, 1350)}


def side_by_side(pictures: list[Path], out: Path, layout: str = "row", aspect: str = "16:9", gap: int = 0,
                 background: str = "white", labels: list[str] | None = None) -> Path:
    """2 to 4 pictures in one, each whole: scaled to fit its cell, never cropped or stretched. layout: row, column or
    grid (2x2). labels: one per picture, drawn exactly at the top-left of its cell on a dark band."""
    from PIL import Image, ImageDraw, ImageFont

    if not 2 <= len(pictures) <= 4:
        raise ValueError("give 2 to 4 pictures")
    width, height = SHEET_SIZES[aspect]
    cols, rows = {"row": (len(pictures), 1), "column": (1, len(pictures)), "grid": (2, (len(pictures) + 1) // 2)}[layout]
    cell_w, cell_h = (width - gap * (cols - 1)) // cols, (height - gap * (rows - 1)) // rows
    sheet = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(sheet)
    size = max(14, round(min(cell_w, cell_h) * 0.07))
    font = next((ImageFont.truetype(f, size) for f in media_tools.FONTS if Path(f).exists()), None) or ImageFont.load_default(size)
    for i, path in enumerate(pictures):
        pic = Image.open(path).convert("RGB")
        scale = min(cell_w / pic.width, cell_h / pic.height)
        pic = pic.resize((max(1, round(pic.width * scale)), max(1, round(pic.height * scale))), Image.LANCZOS)
        x0, y0 = (i % cols) * (cell_w + gap), (i // cols) * (cell_h + gap)
        x, y = x0 + (cell_w - pic.width) // 2, y0 + (cell_h - pic.height) // 2
        sheet.paste(pic, (x, y))
        if labels and i < len(labels) and labels[i]:
            pad = round(size * 0.4)
            box = draw.textbbox((0, 0), labels[i], font=font)
            draw.rectangle((x + pad, y + pad, x + pad * 3 + box[2] - box[0], y + pad * 3 + box[3] - box[1]), fill=(0, 0, 0))
            draw.text((x + pad * 2 - box[0], y + pad * 2 - box[1]), labels[i], font=font, fill="white")
    sheet.save(out)
    return out


# ---- MCP-31: a picture on a video

PLACES = {"top_left": ("{m}", "{m}"), "top_right": ("W-w-{m}", "{m}"), "bottom_left": ("{m}", "H-h-{m}"),
          "bottom_right": ("W-w-{m}", "H-h-{m}"), "center": ("(W-w)/2", "(H-h)/2")}


def overlay_picture(base: Path, picture: Path, out: Path, place: str = "top_right", size: float = 0.15,
                    opacity: float = 1.0, margin: float = 0.03, start: float | None = None, end: float | None = None) -> Path:
    """A picture (a logo; a transparent PNG keeps its transparency) on a video or a picture. size: its width as a share
    of the base's width; margin: the gap to the edges, as a share of the base's width; start/end: seconds (video)."""
    if base.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        from PIL import Image
        info = {"width": Image.open(base).width}
    else:
        info = media_tools.probe(base)
    m = max(0, round(info["width"] * margin))
    x, y = (p.format(m=m) for p in PLACES[place])
    logo_w = max(2, round(info["width"] * max(0.02, min(0.9, size))) // 2 * 2)
    when = f":enable='between(t,{start or 0},{end})'" if end is not None else (f":enable='gte(t,{start})'" if start else "")
    picture_base = base.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    graph = (f"[1:v]format=rgba,scale={logo_w}:-1,colorchannelmixer=aa={max(0.05, min(1.0, opacity)):.2f}[l];"
             f"[0:v][l]overlay={x}:{y}{when}" + ("" if picture_base else ",format=yuv420p") + "[v]")
    args = ["-i", str(base), "-i", str(picture), "-filter_complex", graph, "-map", "[v]"]
    if not picture_base:
        args += ["-map", "0:a?", "-c:v", "libx264", "-c:a", "copy"]
    media_tools._ffmpeg([*args, str(out)])
    return out


# ---- MCP-32: a still card as a clip

def card_clip(out: Path, seconds: float, words: list[str] | None = None, background: str = "black",
              size: tuple[int, int] = (854, 480), picture: Path | None = None) -> Path:
    """A still card held for `seconds` (silent sound track, so join_videos can append it): words on a flat colour
    (media_tools.draw_card: exact, centred, the first line larger), or a picture fitted whole on that colour."""
    still = out.with_suffix(".png")
    if picture:
        media_tools.fit_picture(picture, background, size, still, words)
    else:
        media_tools.draw_card(words or [""], background, size, still)
    return media_tools.still_video(still, max(0.5, seconds), out)


def _need() -> None:
    if not media_tools.have_ffmpeg():
        raise ToolError("This server has no ffmpeg, so it cannot do this.")


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
        _need()
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


    @mcp.tool(
        name="adjust_colours",
        title="Change only the colours",
        description=(
            "Change only the colours of the user's picture or video, by code: warmer or cooler, more or less colour, "
            "black and white, brighter, more contrast. Nothing else changes and nothing is redrawn (edit_image redraws). "
            "0 credits. `media`: a file_path, URL or finished project id. `warmth` -1 (cooler) to 1 (warmer), 0.3 is "
            "noticeably warmer; `saturation` 0 (black and white) to 2, 1 = as it is; `brightness` -0.5 to 0.5; "
            "`contrast` 0.5 to 2. A video keeps its sound. Returns download_url and file_path (video_file_path)."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    async def adjust_colours(media: str, warmth: float = 0.0, saturation: float = 1.0, brightness: float = 0.0,
                             contrast: float = 1.0) -> dict:
        _need()
        with tempfile.TemporaryDirectory() as folder:
            source, picture = await _fetch_media(media, Path(folder))
            out = Path(folder) / ("coloured.png" if picture else "coloured.mp4")
            await asyncio.to_thread(recolour, source, out, warmth, saturation, brightness, contrast)
            return await _deliver(out, picture)

    @mcp.tool(
        name="put_pictures_side_by_side",
        title="Put pictures side by side",
        description=(
            "Put 2 to 4 of the user's pictures into one picture by code: in a row, a column or a 2x2 grid. Each picture "
            "stays whole and unchanged (scaled to fit, never cropped, stretched or redrawn); a before-and-after, a "
            "comparison, a collage. 0 credits. `pictures`: file_paths, URLs or finished image project ids, in order "
            "(left to right, top to bottom). `aspect`: 16:9, 1:1, 9:16 or 4:5. `labels`: one per picture, drawn exactly "
            "at its top-left (for example ['Before', 'After']). `gap` in pixels; `background` a colour. Returns "
            "download_url and file_path."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    async def put_pictures_side_by_side(pictures: list[str], layout: Literal["row", "column", "grid"] = "row",
                                        aspect: Literal["16:9", "1:1", "9:16", "4:5"] = "16:9", labels: list[str] | None = None,
                                        gap: int = 0, background: str = "white") -> dict:
        if not 2 <= len(pictures) <= 4:
            raise ToolError("Give 2 to 4 pictures.")
        with tempfile.TemporaryDirectory() as folder:
            files = []
            for i, p in enumerate(pictures):
                (Path(folder) / f"p{i}").mkdir()
                file, picture = await _fetch_media(p, Path(folder) / f"p{i}", ("image",))
                if not picture:
                    raise ToolError(f"picture {i + 1} is not a picture.")
                files.append(file)
            out = Path(folder) / "side-by-side.png"
            await asyncio.to_thread(side_by_side, files, out, layout, aspect, max(0, gap), background, labels)
            return await _deliver(out, True)

    @mcp.tool(
        name="put_picture_on_video",
        title="Put a logo or picture on a video",
        description=(
            "Put a picture (a logo; a transparent PNG keeps its transparency) on the user's video or picture, by code: "
            "the video is kept exactly, 0 credits. Remove a logo's background first with remove_image_background if "
            "needed. `media`: the video or picture underneath; `picture`: the logo; each a file_path, URL or finished "
            "project id. `place`: top_left, top_right, bottom_left, bottom_right, center. `size`: the logo's width as a "
            "share of the video's width (0.15 = small corner logo). `opacity` 0.05 to 1. `start`/`end`: seconds, video "
            "only; leave out for the whole clip. For words, use add_words_to_media. Returns download_url and file_path."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    async def put_picture_on_video(media: str, picture: str,
                                   place: Literal["top_left", "top_right", "bottom_left", "bottom_right", "center"] = "top_right",
                                   size: float = 0.15, opacity: float = 1.0, start: float | None = None,
                                   end: float | None = None) -> dict:
        _need()
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "b").mkdir(); (Path(folder) / "l").mkdir()
            base, base_is_picture = await _fetch_media(media, Path(folder) / "b")
            logo, logo_is_picture = await _fetch_media(picture, Path(folder) / "l", ("image",))
            if not logo_is_picture:
                raise ToolError("`picture` must be a picture.")
            out = Path(folder) / ("with-logo.png" if base_is_picture else "with-logo.mp4")
            await asyncio.to_thread(overlay_picture, base, logo, out, place, size, opacity, 0.03, start, end)
            return await _deliver(out, base_is_picture)

    @mcp.tool(
        name="make_card_clip",
        title="Make a still card clip",
        description=(
            "Make a still card as a short video clip, by code, 0 credits: exact words centred on a flat colour (an end "
            "card, a title card), or a picture shown whole on that colour. It has a silent sound track, so join_videos "
            "can add it before or after the user's clip. `seconds`: how long. `words`: one line each, the first larger, "
            "spelled exactly. `background`: a colour such as black or #1B2A4A. `like_video`: the user's clip, to match "
            "its size (else `aspect`). `picture`: optional, a file_path, URL or finished image project id. Returns "
            "download_url and video_file_path."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    async def make_card_clip(seconds: float, words: list[str] | None = None, background: str = "black",
                             like_video: str | None = None, aspect: Literal["16:9", "9:16", "1:1"] = "16:9",
                             picture: str | None = None) -> dict:
        _need()
        if not words and not picture:
            raise ToolError("Give `words`, a `picture`, or both.")
        with tempfile.TemporaryDirectory() as folder:
            size = media_tools.size_for(aspect)
            if like_video:
                (Path(folder) / "v").mkdir()
                clip, is_picture = await _fetch_media(like_video, Path(folder) / "v", ("video",))
                info = media_tools.probe(clip)
                size = (info["width"] - info["width"] % 2, info["height"] - info["height"] % 2)
            pic = None
            if picture:
                (Path(folder) / "p").mkdir()
                pic = (await _fetch_media(picture, Path(folder) / "p", ("image",)))[0]
            out = Path(folder) / "card.mp4"
            await asyncio.to_thread(card_clip, out, seconds, words, background, size, pic)
            return await _deliver(out, False)

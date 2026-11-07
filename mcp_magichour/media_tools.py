"""The two file steps a multi-clip video needs: the last frame of a clip, and the join. They need ffmpeg.

The hosted server has no ffmpeg at this time (ticket MCP-06). A build on a machine that has ffmpeg can run them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


import re


def ffmpeg_exe() -> str | None:
    """ffmpeg on the PATH, else the one the `imageio-ffmpeg` package ships (for a server with no ffmpeg installed)."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def have_ffmpeg() -> bool:
    return ffmpeg_exe() is not None


def _ffmpeg(args: list[str], capture: bool = False) -> str:
    exe = ffmpeg_exe()
    if exe is None:
        raise RuntimeError("ffmpeg is not available")
    if capture:
        return subprocess.run([exe, "-hide_banner", *args], capture_output=True, text=True).stderr
    subprocess.check_call([exe, "-v", "error", "-y", *args])
    return ""


def probe(file: Path) -> dict:
    """Length, size and whether there is a sound track. With ffprobe when it exists, else from ffmpeg's own report."""
    if shutil.which("ffprobe"):
        raw = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                                       "-of", "json", str(file)])
        data = json.loads(raw)
        video = next(s for s in data["streams"] if s["codec_type"] == "video")
        return {"seconds": float(data["format"]["duration"]), "width": video["width"], "height": video["height"],
                "audio": any(s["codec_type"] == "audio" for s in data["streams"])}
    report = _ffmpeg(["-i", str(file)], capture=True)
    duration = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", report)
    size = re.search(r"Video: .*? (\d{2,5})x(\d{2,5})", report)
    if not duration or not size:
        raise RuntimeError(f"ffmpeg could not read {file.name}")
    h, m, sec = duration.groups()
    return {"seconds": int(h) * 3600 + int(m) * 60 + float(sec), "width": int(size[1]), "height": int(size[2]), "audio": "Audio:" in report}


def loudness_db(file: Path) -> float | None:
    """The peak level of the sound track in dB (0 is full scale, about -91 is silence), or None with no sound track."""
    if not probe(file)["audio"]:
        return None
    report = _ffmpeg(["-i", str(file), "-af", "volumedetect", "-vn", "-f", "null", "-"], capture=True)
    found = re.search(r"max_volume: (-?\d+\.?\d*) dB", report)
    return float(found[1]) if found else None


def store(file: Path, name: str, local_dir: Path, public_base: str) -> str:
    """Keep a finished film where the user can fetch it, and return its address.

    With BLOB_READ_WRITE_TOKEN set (Vercel Blob), the file is uploaded there and its public address returned.
    Else it is kept in local_dir and served by this server at public_base/films/name.
    """
    token = os.getenv("BLOB_READ_WRITE_TOKEN")
    if token:
        import httpx
        response = httpx.put(f"https://blob.vercel-storage.com/films/{name}", content=file.read_bytes(), timeout=120,
                             headers={"authorization": f"Bearer {token}", "x-api-version": "7", "x-content-type": "video/mp4",
                                      "x-add-random-suffix": "0"})
        response.raise_for_status()
        return response.json()["url"]
    local_dir.mkdir(parents=True, exist_ok=True)
    if file.resolve() != (local_dir / name).resolve():
        shutil.copy(file, local_dir / name)
    return f"{public_base.rstrip('/')}/films/{name}"


def last_frame(video: Path, out: Path) -> Path:
    _ffmpeg(["-sseof", "-0.15", "-i", str(video), "-frames:v", "1", "-update", "1",
                           "-q:v", "2", str(out)])
    return out


def join(files: list[Path], out: Path, audio: bool = True) -> Path:
    """Hard cuts, in the order given. Every clip is fitted to the first clip's size and gets a sound track.
    audio=False: every clip is made silent (minimax-h3 adds a music bed even with audio off)."""
    first = probe(files[0])
    width, height = first["width"] - first["width"] % 2, first["height"] - first["height"] % 2
    parts = []
    for i, file in enumerate(files):
        part = out.with_name(f"{out.stem}-part{i}.mp4")
        silent = ["-i", str(file), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v:0", "-map", "1:a:0", "-shortest"]
        sound = ["-i", str(file)] if audio and probe(file)["audio"] else silent
        subprocess.check_call([
            "ffmpeg", "-v", "error", "-y", *sound,
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p",
            "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(part),
        ])
        parts.append(part)
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    _ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)])
    for p in [*parts, listing]:
        p.unlink()
    return out


# ---- sound: one narration for the whole film, a music track, drawn captions ------------------------------------------
def letters(text: str) -> int:
    return sum(ch.isalnum() for ch in text)


def speech_spans(audio: Path, noise_db: int = -35, min_gap: float = 0.12) -> list[tuple[float, float]]:
    """The stretches of an audio or video file where something is heard."""
    log = _ffmpeg(["-i", str(audio), "-af", f"silencedetect=noise={noise_db}dB:d={min_gap}", "-vn", "-f", "null", "-"], capture=True)
    total = probe_seconds(audio)
    starts = [float(x.split("silence_start:")[1].split()[0]) for x in log.splitlines() if "silence_start:" in x]
    ends = [float(x.split("silence_end:")[1].split()[0]) for x in log.splitlines() if "silence_end:" in x]
    spans, at = [], 0.0
    for i, start in enumerate(starts):
        if start - at > 0.05:
            spans.append((at, start))
        at = ends[i] if i < len(ends) else total
    if total - at > 0.05:
        spans.append((at, total))
    return spans


def probe_seconds(file: Path) -> float:
    return probe(file)["seconds"]


def align_parts(spans: list[tuple[float, float]], parts: list[str], fine: list[tuple[float, float]] | None = None) -> list[tuple[float, float]]:
    """Where each part of a script is in a narration that reads the parts in order, with no speech-to-text model.

    Each part gets a share of the spoken time equal to its share of the letters. The boundary between two parts is
    then moved to a pause near it, because a narrator pauses between sentences. `fine`: the same narration cut at
    shorter pauses (speech_spans with a small min_gap), used where no long pause is near.
    """
    if not spans or not parts:
        return []
    spoken = sum(end - start for start, end in spans)
    total_letters = sum(letters(p) for p in parts) or 1

    def at_spoken(position: float) -> float:   # the clock time at which this much speech has been heard
        for start, end in spans:
            if position <= end - start:
                return start + position
            position -= end - start
        return spans[-1][1]

    def pauses(of: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [(of[i][1], of[i + 1][0]) for i in range(len(of) - 1)]

    def pick(candidates: list[tuple[float, float]], guess: float, reach: float, after: float) -> tuple[float, float] | None:
        near = [g for g in candidates if abs((g[0] + g[1]) / 2 - guess) <= reach and g[0] > after]
        return max(near, key=lambda g: (g[1] - g[0]) - 0.15 * abs((g[0] + g[1]) / 2 - guess), default=None)   # the longer pause wins

    cuts, used = [], 0
    for part in parts[:-1]:
        used += letters(part)
        guess = at_spoken(spoken * used / total_letters)
        after = cuts[-1] if cuts else spans[0][0]
        best = pick(pauses(spans), guess, 0.6, after) or pick(pauses(fine or []), guess, 0.9, after)
        cuts.append((best[0] + best[1]) / 2 if best else guess)
    edges = [spans[0][0], *cuts, spans[-1][1]]
    return [(edges[i], edges[i + 1]) for i in range(len(parts))]


def add_sound(film: Path, out: Path, narration: Path | None = None, parts: list[dict] | None = None, music: Path | None = None) -> Path:
    """Lay each part of the narration at its place in the film and mix the music under it.
    parts: [{"start", "end"} in the narration, "at" in the film]. The film's own sound is kept under both."""
    seconds = probe_seconds(film)
    inputs, filters, mixed = ["-i", str(film)], [], ["[0:a]"]
    if narration and parts:
        inputs += ["-i", str(narration)]
        for i, part in enumerate(parts):
            length = part["end"] - part["start"]
            filters.append(f"[1:a]atrim={part['start']:.2f}:{part['end']:.2f},asetpts=PTS-STARTPTS,afade=t=in:d=0.03,"
                           f"afade=t=out:st={max(0, length - 0.03):.2f}:d=0.03,adelay={int(part['at'] * 1000)}:all=1[n{i}]")
            mixed.append(f"[n{i}]")
    if music:
        inputs += ["-i", str(music)]
        filters.append(f"[{len(inputs) // 2 - 1}:a]volume=0.16,afade=t=in:d=1,afade=t=out:st={max(0, seconds - 2):.2f}:d=2[m]")
        mixed.append("[m]")
    filters.append("".join(mixed) + f"amix=inputs={len(mixed)}:duration=longest:normalize=0,atrim=0:{seconds:.2f}[a]")
    _ffmpeg([*inputs, "-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[a]",
                           "-c:v", "copy", "-c:a", "aac", "-t", f"{seconds:.2f}", str(out)])
    return out


def have_captions() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True


FONTS = ("/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf")


def _caption_png(text: str, size: tuple[int, int], out: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    width, height = size
    points = round(min(width, height) * 0.052)
    font = next((ImageFont.truetype(f, points) for f in FONTS if Path(f).exists()), None) or ImageFont.load_default(points)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    lines, current = [], ""
    for word in text.split():
        if current and draw.textlength(f"{current} {word}", font=font) > width * 0.84:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    lines.append(current)
    line_height = round(points * 1.3)
    top = round(height * 0.80) - line_height * len(lines) // 2
    box = max(draw.textlength(line, font=font) for line in lines) + points
    draw.rounded_rectangle([(width - box) / 2, top - points * 0.35, (width + box) / 2, top + line_height * len(lines) + points * 0.2],
                           radius=points * 0.4, fill=(0, 0, 0, 150))
    for i, line in enumerate(lines):
        draw.text(((width - draw.textlength(line, font=font)) / 2, top + i * line_height), line, font=font, fill=(255, 255, 255, 255))
    image.save(out)
    return out


def draw_captions(film: Path, timed: list[dict], out: Path) -> Path:
    """Draw exact words on the picture. timed: [{"text", "start", "end"}], one caption at a time. Needs Pillow."""
    info = probe(film)
    inputs, chain, last, pngs = ["-i", str(film)], [], "0:v", []
    for i, line in enumerate(timed):
        pngs.append(_caption_png(line["text"], (info["width"], info["height"]), out.with_name(f"{out.stem}-caption{i}.png")))
        inputs += ["-i", str(pngs[-1])]
        chain.append(f"[{last}][{i + 1}:v]overlay=enable='between(t,{line['start']:.2f},{line['end']:.2f})'[v{i}]")
        last = f"v{i}"
    _ffmpeg([*inputs, "-filter_complex", ";".join(chain), "-map", f"[{last}]", "-map", "0:a?",
                           "-c:v", "libx264", "-crf", "18", "-c:a", "copy", str(out)])
    for png in pngs:
        png.unlink()
    return out

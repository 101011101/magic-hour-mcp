"""The two file steps a multi-clip video needs: the last frame of a clip, and the join. They need ffmpeg.

The hosted server has no ffmpeg at this time (ticket MCP-06). A build on a machine that has ffmpeg can run them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
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
        return subprocess.run([exe, "-hide_banner", *args], capture_output=True, text=True, stdin=subprocess.DEVNULL).stderr
    subprocess.check_call([exe, "-v", "error", "-y", *args], stdin=subprocess.DEVNULL)
    return ""


def probe(file: Path) -> dict:
    """Length, size and whether there is a sound track. With ffprobe when it exists, else from ffmpeg's own report."""
    if shutil.which("ffprobe"):
        raw = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                                       "-of", "json", str(file)])
        data = json.loads(raw)
        video = next((s for s in data["streams"] if s["codec_type"] == "video"), {})   # a voice track has no picture
        return {"seconds": float(data["format"].get("duration") or 0), "width": video.get("width", 0), "height": video.get("height", 0),
                "audio": any(s["codec_type"] == "audio" for s in data["streams"])}
    report = _ffmpeg(["-i", str(file)], capture=True)
    duration = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", report)
    size = re.search(r"Video: .*? (\d{2,5})x(\d{2,5})", report)
    if not duration or not (size or "Audio:" in report):
        raise RuntimeError(f"ffmpeg could not read {file.name}")
    h, m, sec = duration.groups()
    return {"seconds": int(h) * 3600 + int(m) * 60 + float(sec), "width": int(size[1]) if size else 0,
            "height": int(size[2]) if size else 0, "audio": "Audio:" in report}


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
                             headers={"authorization": f"Bearer {token}", "x-api-version": "7", "x-content-type": {".png": "image/png", ".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav"}.get(Path(name).suffix, "video/mp4"),
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


CROP_LIMIT = 0.2   # a picture of another shape is cropped to fill the frame when this share or less is lost; else filled with a blur


def crop_share(width: int, height: int, target_w: int, target_h: int) -> float:
    """The share of the picture lost when it is scaled to cover the target frame and cropped."""
    ratio, target = width / height, target_w / target_h
    return 1 - min(ratio / target, target / ratio)


def frame_filter(width: int, height: int, target_w: int, target_h: int, how: str = "auto", focus: float = 0.5,
                 color: str = "black") -> tuple[str, str]:
    """An ffmpeg -vf graph that puts a picture of one shape into a frame of another. Returns (graph, way).
    crop: scale to cover and crop the edges. fill: the whole picture over a blurred, cropped copy of itself.
    pad: the whole picture on bars of one colour (J51b). focus: where the crop is centred, 0 = left or top, 1 = right or
    bottom (E25b: keep the speaker in the frame)."""
    if how == "auto":
        how = "crop" if crop_share(width, height, target_w, target_h) <= CROP_LIMIT else "fill"
    focus = min(1.0, max(0.0, focus))
    cover = (f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
             f"crop={target_w}:{target_h}:(iw-{target_w})*{focus:.3f}:(ih-{target_h})*{focus:.3f}")
    if how == "crop" or (width * target_h == height * target_w):
        return cover, "crop"
    inside = f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease"
    if how == "pad":
        return f"{inside},pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color={color}", "pad"
    cover = f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h}"
    return f"split[a][b];[a]{cover},boxblur=20:2[bg];[b]{inside}[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2", "fill"


def size_for(aspect: str, like: dict | None = None) -> tuple[int, int]:
    """The frame size for an aspect: the clip's own size when it has that shape, else 480p of that shape."""
    ratio = {"16:9": 16 / 9, "9:16": 9 / 16, "1:1": 1.0}[aspect]
    if like and abs(like["width"] / like["height"] - ratio) < 0.01 * ratio:
        return like["width"] - like["width"] % 2, like["height"] - like["height"] % 2
    return {"16:9": (854, 480), "9:16": (480, 854), "1:1": (640, 640)}[aspect]


def join(files: list[Path], out: Path, audio: bool | list[bool] = True, seconds: list[float | None] | None = None,
         size: tuple[int, int] | None = None) -> Path:
    """Hard cuts, in the order given. Every clip is fitted to `size` (default: the first clip's size) and gets a sound track.
    A clip of another shape is cropped to fill the frame, or filled with a blur when a crop loses too much (frame_filter).
    seconds: one planned length per clip; a longer clip is cut to it (minimax-h3 returns at least about 2 s).
    audio=False: every clip is made silent (minimax-h3 adds a music bed even with audio off).
    A list: one flag per clip (the user's own clip keeps its sound while generated clips are made silent)."""
    keep = list(audio) if isinstance(audio, list) else [audio] * len(files)
    seconds = list(seconds) if seconds else [None] * len(files)
    infos = [probe(f) for f in files]
    if all(not i["width"] for i in infos):   # F31b, F32b: voice clips have no picture; join the sound only
        return join_audio(files, out)
    if any(not i["width"] for i in infos):
        raise ValueError("Some files have no picture. Join sound files apart from video files, or use mix_audio.")
    if size is None:
        first = probe(files[0])
        size = (first["width"] - first["width"] % 2, first["height"] - first["height"] % 2)
    width, height = size
    parts = []
    for i, file in enumerate(files):
        part = out.with_name(f"{out.stem}-part{i}.mp4")
        info = infos[i]
        silent = ["-i", str(file), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v:0", "-map", "1:a:0", "-shortest"]
        sound = ["-i", str(file)] if keep[i] and info["audio"] else silent
        cut = ["-t", f"{seconds[i]:.3f}"] if seconds[i] and info["seconds"] > seconds[i] + 0.05 else []
        graph, _ = frame_filter(info["width"], info["height"], width, height)
        subprocess.check_call([
            "ffmpeg", "-v", "error", "-y", *sound, *cut,
            "-vf", f"{graph},fps=24,format=yuv420p",
            "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(part),
        ])
        parts.append(part)
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    _ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)])
    for p in [*parts, listing]:
        p.unlink()
    return out


def join_audio(files: list[Path], out: Path, gap: float = 0.0) -> Path:
    """Sound files end to end into one file (.m4a, .mp3 or .wav by the suffix of `out`). gap: seconds of silence between."""
    inputs, chain = [], []
    for i, file in enumerate(files):
        inputs += ["-i", str(file)]
        pad = f",apad=pad_dur={gap:.2f}" if gap and i < len(files) - 1 else ""
        chain.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo{pad}[a{i}]")
    chain.append("".join(f"[a{i}]" for i in range(len(files))) + f"concat=n={len(files)}:v=0:a=1[a]")
    codec = {".wav": ["-c:a", "pcm_s16le"], ".mp3": ["-c:a", "libmp3lame", "-q:a", "2"]}.get(out.suffix.lower(), ["-c:a", "aac", "-b:a", "192k"])
    _ffmpeg([*inputs, "-filter_complex", ";".join(chain), "-map", "[a]", "-vn", *codec, str(out)])
    return out


def mix_audio(tracks: list[dict], out: Path, seconds: float | None = None, fade_out: float = 0.0) -> Path:
    """Sound files laid over each other into one sound file (F32a: a voice over music, no picture).
    tracks: [{file, at (seconds into the mix), volume (1 = as it is), fade_in (seconds)}]. seconds: the mix length
    (default: to the end of the longest track). fade_out: seconds of fade at the end of the mix."""
    inputs, chain = [], []
    for i, t in enumerate(tracks):
        inputs += ["-i", str(t["file"])]
        steps = [f"aresample=48000,aformat=channel_layouts=stereo,volume={float(t.get('volume', 1)):.3f}"]
        if t.get("fade_in"):
            steps.append(f"afade=t=in:d={float(t['fade_in']):.2f}")
        steps.append(f"adelay={int(float(t.get('at', 0)) * 1000)}:all=1")
        chain.append(f"[{i}:a]{','.join(steps)}[t{i}]")
    total = seconds or max(float(t.get("at", 0)) + probe(Path(t["file"]))["seconds"] for t in tracks)
    end = f",afade=t=out:st={max(0, total - fade_out):.2f}:d={fade_out:.2f}" if fade_out else ""
    chain.append("".join(f"[t{i}]" for i in range(len(tracks))) + f"amix=inputs={len(tracks)}:duration=longest:normalize=0,atrim=0:{total:.2f}{end}[a]")
    codec = {".wav": ["-c:a", "pcm_s16le"], ".mp3": ["-c:a", "libmp3lame", "-q:a", "2"]}.get(out.suffix.lower(), ["-c:a", "aac", "-b:a", "192k"])
    _ffmpeg([*inputs, "-filter_complex", ";".join(chain), "-map", "[a]", "-vn", *codec, "-t", f"{total:.2f}", str(out)])
    return out


def trim(source: Path, out: Path, start: float = 0.0, end: float | None = None) -> Path:
    """The part of a video or sound file from `start` to `end` seconds, cut frame-exact (re-encoded), sound kept."""
    length = probe(source)["seconds"]
    end = length if end is None or end > length else end
    if not 0 <= start < end:
        raise ValueError(f"start {start} and end {end} do not give a part of the {length:.1f} s file")
    if out.suffix.lower() in (".m4a", ".mp3", ".wav"):
        codec = {".wav": ["-c:a", "pcm_s16le"], ".mp3": ["-c:a", "libmp3lame", "-q:a", "2"]}.get(out.suffix.lower(), ["-c:a", "aac"])
        _ffmpeg(["-ss", f"{start:.3f}", "-i", str(source), "-t", f"{end - start:.3f}", "-vn", *codec, str(out)])
    else:
        _ffmpeg(["-ss", f"{start:.3f}", "-i", str(source), "-t", f"{end - start:.3f}", "-c:v", "libx264", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)])
    return out


def reframe(source: Path, aspect: str, out: Path, how: str = "auto", focus: float = 0.5, color: str = "black") -> dict:
    """A picture or video of another shape put into `aspect`: crop (edges cut) or fill (whole picture over a blur).
    auto: crop when it loses 20% or less, else fill. Keeps the sound. Returns the new size and the way used."""
    info = probe(source)
    ratio = {"16:9": 16 / 9, "9:16": 9 / 16, "1:1": 1.0}[aspect]
    long_side = max(info["width"], info["height"])
    if ratio >= 1:
        target = (long_side - long_side % 2, round(long_side / ratio / 2) * 2)
    else:
        target = (round(long_side * ratio / 2) * 2, long_side - long_side % 2)
    graph, way = frame_filter(info["width"], info["height"], *target, how, focus, color)
    if out.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
        _ffmpeg(["-i", str(source), "-vf", graph, "-frames:v", "1", str(out)])
    else:
        _ffmpeg(["-i", str(source), "-vf", f"{graph},format=yuv420p", "-c:v", "libx264", "-crf", "18", "-c:a", "aac", str(out)])
    return {"width": target[0], "height": target[1], "way": way, "lost": round(crop_share(info["width"], info["height"], *target), 2) if way == "crop" else 0}


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

    def said(text: str) -> int:   # about how long a text is when read: a digit is read as a word ("35": thirty-five)
        return letters(text) + 4 * sum(ch.isdigit() for ch in text)

    total_letters = sum(said(p) for p in parts) or 1

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
        used += said(part)
        guess = at_spoken(spoken * used / total_letters)
        after = cuts[-1] if cuts else spans[0][0]
        # a sentence ends on a real pause; a breath inside a sentence is used only when no real pause is near
        # (I46a, 2026-11-13: "F-35A" is short in letters, long when read; the cut fell on a breath 1.4 s early)
        best = (pick(pauses(spans), guess, 0.6, after) or pick(pauses(spans), guess, 1.5, after)
                or pick(pauses(fine or []), guess, 0.9, after))
        cuts.append((best[0] + best[1]) / 2 if best else guess)
    edges = [spans[0][0], *cuts, spans[-1][1]]
    return [(edges[i], edges[i + 1]) for i in range(len(parts))]


# Sound layers (user, 2026-11-12). Priority: 1 speech (narration and spoken lines), 2 music, 3 effects (the clips' own
# sound). A layer is lowered only where a higher layer plays, and only there. With no speech, music is the top layer.
MUSIC_UNDER_SPEECH_DB = 9    # music under speech (18, then 12: the user wanted more music under the voice, 2026-11-13)
SWELL_DB = 8                 # music_swell: how far the music rises between the lines
EFFECTS_UNDER_DB = 10        # effects under narration or music
TARGET_LUFS = -16.0          # the whole film, social video
DUCK_RAMP = 0.3              # seconds to go down or up
DUCK_BRIDGE = 1.0            # a gap shorter than this between two speech spans stays lowered (no pumping)
LIMIT_TRUE_PEAK = 0.89       # about -1 dBTP


VOICE_LEAD = 0.5             # a narration part starts this far into its beat
VOICE_LEAD_MIN = 0.1         # ... or this far, when it does not fit
VOICE_GAP = 0.1              # the least pause between two parts
VOICE_TEMPO_MAX = 1.15       # the most a narration is sped up to fit (more is heard)
HOLD_TAIL = 0.3              # the picture holds this long after the last word


def fit_parts(parts: list[dict], seconds: float) -> dict:
    """Fit a narration's parts into a film of `seconds` without cutting a word (I46a, E28c: the last words ran past the
    end and were cut). parts: [{"start", "end"} in the narration, "at" in the film, with VOICE_LEAD]. In order:
    1 no part starts before the one before it ends; 2 the parts start VOICE_LEAD_MIN into their beat, not VOICE_LEAD;
    3 the narration is read up to VOICE_TEMPO_MAX faster; 4 the film holds its last frame. Returns
    {"parts" (each with "tempo"), "tempo", "moved", "hold"}: hold = the seconds the last frame is held (0: none)."""
    def place(lead_cut: float, tempo: float) -> list[dict]:
        out, after = [], 0.0
        for p in parts:
            at = max(p["at"] - lead_cut, after + (VOICE_GAP if out else 0.0))
            out.append(dict(p, at=round(at, 3), tempo=tempo))
            after = at + (p["end"] - p["start"]) / tempo
        return out

    def over(placed: list[dict]) -> float:
        last = placed[-1]
        return last["at"] + (last["end"] - last["start"]) / last["tempo"] + HOLD_TAIL - seconds

    if not parts:
        return {"parts": [], "tempo": 1.0, "moved": False, "hold": 0.0}
    placed = place(0.0, 1.0)
    if over(placed) <= 0:
        return {"parts": placed, "tempo": 1.0, "moved": placed != [dict(p, tempo=1.0) for p in parts], "hold": 0.0}
    placed = place(VOICE_LEAD - VOICE_LEAD_MIN, 1.0)
    if over(placed) > 0:
        low, high = 1.0, VOICE_TEMPO_MAX   # the least speed-up that fits (a part held at its beat start shrinks only by itself)
        if over(place(VOICE_LEAD - VOICE_LEAD_MIN, high)) <= 0:
            for _ in range(20):
                low, high = (low, (low + high) / 2) if over(place(VOICE_LEAD - VOICE_LEAD_MIN, (low + high) / 2)) <= 0 else ((low + high) / 2, high)
        placed = place(VOICE_LEAD - VOICE_LEAD_MIN, round(high + 0.0005, 3))
    return {"parts": placed, "tempo": placed[0]["tempo"], "moved": True, "hold": round(max(0.0, over(placed)), 2)}


def hold_end(film: Path, seconds: float, out: Path) -> Path:
    """The film with its last frame held `seconds` longer (its sound padded with silence)."""
    has_audio = probe(film)["audio"]
    _ffmpeg(["-i", str(film), "-vf", f"tpad=stop_mode=clone:stop_duration={seconds:.2f}",
             *(["-af", f"apad=pad_dur={seconds:.2f}"] if has_audio else []),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", *(["-c:a", "aac"] if has_audio else []), str(out)])
    return out


def merge_spans(spans: list[tuple[float, float]], bridge: float = DUCK_BRIDGE) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for start, end in sorted(spans):
        if out and start - out[-1][1] < bridge:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return [(a, b) for a, b in out]


def _inside(spans: list[tuple[float, float]], ramp: float = DUCK_RAMP) -> str:
    """An ffmpeg expression of t: 1 inside the spans, 0 outside, with a linear ramp at each edge."""
    expr = "0"
    for start, end in spans:
        one = f"clip(min((t-{start - ramp:.3f})/{ramp},({end + ramp:.3f}-t)/{ramp}),0,1)"
        expr = one if expr == "0" else f"max({expr},{one})"
    return expr


def _gain(lowered: str, db: float, kept: str = "0") -> str:
    """volume expression: lowered by `db` where `lowered` is 1, never where `kept` is 1."""
    depth = 1 - 10 ** (-db / 20)
    return f"1-{depth:.4f}*({lowered})*(1-({kept}))"


def loudness(file: Path) -> float | None:
    """Integrated loudness in LUFS, or None when nothing is heard."""
    report = _ffmpeg(["-i", str(file), "-af", "ebur128", "-vn", "-f", "null", "-"], capture=True)
    found = re.findall(r"I:\s+(-?\d+\.?\d*) LUFS", report)
    value = float(found[-1]) if found else None
    return None if value is None or value <= -69 else value


def loudness_between(file: Path, spans: list[tuple[float, float]]) -> float | None:
    """The loudness of a file inside the spans only (a spoken line inside the film's own sound)."""
    pick = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in spans)
    report = _ffmpeg(["-i", str(file), "-vn", "-af", f"aselect='{pick}',ebur128", "-f", "null", "-"], capture=True)
    found = re.findall(r"I:\s+(-?\d+\.?\d*) LUFS", report)
    value = float(found[-1]) if found else None
    return None if value is None or value <= -69 else value


def add_sound(film: Path, out: Path, narration: Path | None = None, parts: list[dict] | None = None, music: Path | None = None,
              spoken: list[tuple[float, float]] | None = None, music_first: bool = False, layers: Path | None = None,
              music_swell: bool = False) -> dict:
    """Mix the film's sound from three layers and normalize it to TARGET_LUFS.
    parts: [{"start", "end"} in the narration, "at" in the film]. spoken: where a person on screen speaks (inside the
    film's own sound). music_first: the music is never lowered (a music video). layers: a folder that keeps each layer
    as its own file, so a later mix can use them again. Returns what was done and measured."""
    seconds = probe_seconds(film)
    folder = layers or Path(tempfile.mkdtemp())
    folder.mkdir(parents=True, exist_ok=True)
    parts = parts if narration and parts else []
    narrated = merge_spans([(p["at"], p["at"] + (p["end"] - p["start"]) / p.get("tempo", 1.0)) for p in parts])
    talk = merge_spans(list(spoken or []))
    speech = merge_spans(narrated + talk)
    silence = ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={seconds:.3f}"]
    # pad to the film's length and stop there (an open-ended apad made ffmpeg wait forever on a multi-part narration)
    fit = f"aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={seconds:.3f},atrim=0:{seconds:.3f}"
    end = ["-t", f"{seconds:.3f}"]
    files: dict[str, Path] = {}

    # 1 speech: the narration, each part at its place
    files["speech"] = folder / "speech.wav"
    if parts:
        steps = [f"[0:a]atrim={p['start']:.2f}:{p['end']:.2f},asetpts=PTS-STARTPTS,"
                 + (f"atempo={p['tempo']:.3f}," if p.get("tempo", 1.0) != 1.0 else "")
                 + f"afade=t=in:d=0.03,afade=t=out:st={max(0, (p['end'] - p['start']) / p.get('tempo', 1.0) - 0.03):.2f}:d=0.03,"
                 f"adelay={int(p['at'] * 1000)}:all=1[n{i}]"
                 for i, p in enumerate(parts)]
        steps.append("".join(f"[n{i}]" for i in range(len(parts))) + f"amix=inputs={len(parts)}:normalize=0,{fit}[s]")
        _ffmpeg(["-i", str(narration), "-filter_complex", ";".join(steps), "-map", "[s]", *end, str(files["speech"])])
    else:
        _ffmpeg([*silence, str(files["speech"])])

    # 2 music. A film with speech: one steady level, 12 dB under the voice, the whole film (a bed). music_swell: full
    # level between the lines, down only while someone speaks. music_first, or no speech: never lowered.
    if music:
        files["music"] = folder / "music.wav"
        level = "1"
        if speech and not music_first:
            voice = loudness(files["speech"]) if parts else None
            if voice is None and talk and probe(film)["audio"]:
                voice = loudness_between(film, talk)
            track = loudness(music)
            depth = MUSIC_UNDER_SPEECH_DB if voice is None or track is None else track - (voice - MUSIC_UNDER_SPEECH_DB)
            bed = 10 ** (-depth / 20)
            if music_swell:   # between the lines the music rises SWELL_DB over the bed (not to full: that blasted)
                high = min(1.0, bed * 10 ** (SWELL_DB / 20)) if depth > 0 else bed
                level = f"{high:.4f}-{high - bed:.4f}*({_inside(speech)})"
            else:
                level = f"{bed:.4f}"
        _ffmpeg(["-i", str(music), "-af", f"{fit},volume='{level}':eval=frame,afade=t=in:d=1,"
                 f"afade=t=out:st={max(0, seconds - 2):.2f}:d=2", *end, str(files["music"])])

    # 3 effects: the film's own sound, lowered under narration and music; a spoken line in it is never lowered
    files["effects"] = folder / "effects.wav"
    if probe(film)["audio"]:
        above = "1" if music else _inside(narrated)
        level = _gain(above, EFFECTS_UNDER_DB, _inside(talk)) if (music or narrated) else "1"
        _ffmpeg(["-i", str(film), "-vn", "-af", f"{fit},volume='{level}':eval=frame", *end, str(files["effects"])])
    else:
        _ffmpeg([*silence, str(files["effects"])])

    order = [k for k in ("speech", "music", "effects") if k in files]
    mix = folder / "mix.wav"
    _ffmpeg([*sum((["-i", str(files[k])] for k in order), []), "-filter_complex",
             "".join(f"[{i}:a]" for i in range(len(order))) + f"amix=inputs={len(order)}:normalize=0[a]", "-map", "[a]", str(mix)])
    before = loudness(mix)
    gain = 0.0 if before is None else TARGET_LUFS - before
    _ffmpeg(["-i", str(film), "-i", str(mix), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
             "-af", f"volume={gain:.2f}dB,alimiter=limit={LIMIT_TRUE_PEAK}:level=disabled", "-c:a", "aac", "-b:a", "192k",
             "-t", f"{seconds:.2f}", str(out)])
    if layers:
        (layers / "layers.json").write_text(json.dumps({
            "priority": ["speech", "music", "effects"], "music_first": music_first, "music_swell": music_swell, "speech": speech, "spoken": talk,
            "files": {k: files[k].name for k in order}, "gain_db": round(gain, 2), "target_lufs": TARGET_LUFS}, indent=1))
    else:
        shutil.rmtree(folder, ignore_errors=True)
    return {"lufs_before": before, "lufs": loudness(out), "speech": speech, "layers": order}


def have_captions() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True


FONTS = ("/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf")


def draw_card(words: list[str], background: str, size: tuple[int, int], out: Path) -> Path:
    """A flat card: the background colour exactly, the words centred in white, one item on each line, the first larger."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = size
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    sizes = [round(min(width, height) * (0.09 if i == 0 else 0.055)) for i in range(len(words))]
    fonts = [next((ImageFont.truetype(f, s) for f in FONTS if Path(f).exists()), None) or ImageFont.load_default(s) for s in sizes]
    for i, (line, font) in enumerate(zip(words, fonts)):   # shrink a line that is too wide
        while draw.textlength(line, font=font) > width * 0.86 and font.size > 10:
            font = font.font_variant(size=font.size - 2)
        fonts[i] = font
    gaps = [round(f.size * 1.35) for f in fonts]
    y = (height - sum(gaps)) / 2
    for line, font, gap in zip(words, fonts, gaps):
        draw.text(((width - draw.textlength(line, font=font)) / 2, y), line, font=font, fill="white")
        y += gap
    image.save(out)
    return out


def fit_picture(source: Path, background: str | None, size: tuple[int, int], out: Path, words: list[str] | None = None) -> Path:
    """The picture unchanged, never cropped. With `background` (a logo, a screenshot): 80% of the frame, centred on that
    colour. Without it (a photo): as large as fits, over a blurred copy of itself that fills the frame.
    words: drawn exactly over the lower part of the picture, one line each, on a dark band."""
    from PIL import Image, ImageFilter

    picture = Image.open(source).convert("RGBA")
    room = 0.8 if background else 1.0
    scale = min(size[0] * room / picture.width, size[1] * room / picture.height)
    if background and picture.width <= size[0] and picture.height <= size[1]:
        scale = min(scale, 1.0)   # a small logo is not blown up
    fitted = picture.resize((max(1, round(picture.width * scale)), max(1, round(picture.height * scale))), Image.LANCZOS)
    if background:
        frame = Image.new("RGBA", size, background)
    else:
        cover = max(size[0] / picture.width, size[1] / picture.height)
        wide = picture.resize((round(picture.width * cover) + 1, round(picture.height * cover) + 1), Image.LANCZOS)
        left, top = (wide.width - size[0]) // 2, (wide.height - size[1]) // 2
        frame = wide.crop((left, top, left + size[0], top + size[1])).filter(ImageFilter.GaussianBlur(24))
        frame = Image.alpha_composite(frame, Image.new("RGBA", size, (0, 0, 0, 60)))
    frame.alpha_composite(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
    if words:
        band = out.with_name(out.stem + "-words.png")
        _caption_png("\n".join(words), size, band, at=0.82, share=0.075)
        frame.alpha_composite(Image.open(band).convert("RGBA"))
        band.unlink()
    frame.convert("RGB").save(out)
    return out


def still_video(image: Path, seconds: float, out: Path) -> Path:
    """A picture held still for `seconds`, silent, at 24 frames a second."""
    _ffmpeg(["-loop", "1", "-i", str(image), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{seconds:.2f}",
             "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=24,format=yuv420p", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(out)])
    return out


def _caption_png(text: str, size: tuple[int, int], out: Path, at: float = 0.80, share: float = 0.052, align: str = "center",
                 style: str = "band", opacity: float = 1.0) -> Path:
    """Words on a clear picture of `size`, white on a dark band. at: where the band's middle is (share of the height).
    share: letter height as a share of the short side. A line break in `text` starts a new line.
    align: left, center or right, with a 5% margin (D23b: a lower third). style: band (a dark band) or shadow (no band,
    a soft shadow under the letters; E29c: a watermark). opacity: 0 to 1 for the whole drawing."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = size
    points = round(min(width, height) * share)
    font = next((ImageFont.truetype(f, points) for f in FONTS if Path(f).exists()), None) or ImageFont.load_default(points)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    lines = []
    for given in text.split("\n"):
        current = ""
        for word in given.split():
            if current and draw.textlength(f"{current} {word}", font=font) > width * 0.84:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        lines.append(current)
    line_height = round(points * 1.3)
    top = round(height * at) - line_height * len(lines) // 2
    top = max(round(points * 0.5), min(top, height - line_height * len(lines) - round(points * 0.5)))   # the band stays inside the frame
    box = max(draw.textlength(line, font=font) for line in lines) + points
    margin = round(width * 0.05)
    left = {"left": margin, "right": width - margin - box}.get(align, (width - box) / 2)
    if style == "band":
        draw.rounded_rectangle([left, top - points * 0.35, left + box, top + line_height * len(lines) + points * 0.2],
                               radius=points * 0.4, fill=(0, 0, 0, 150))
    else:
        from PIL import ImageFilter
        shadow = Image.new("RGBA", size, (0, 0, 0, 0))
        shade = ImageDraw.Draw(shadow)
    for i, line in enumerate(lines):
        x = {"left": left + points / 2, "right": left + box - points / 2 - draw.textlength(line, font=font)}.get(
            align, (width - draw.textlength(line, font=font)) / 2)
        if style != "band":
            offset = max(1, round(points * 0.06))
            shade.text((x + offset, top + i * line_height + offset), line, font=font, fill=(0, 0, 0, 200))
        draw.text((x, top + i * line_height), line, font=font, fill=(255, 255, 255, 255))
    if style != "band":
        image = Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(max(1, points * 0.08))), image)
    if opacity < 1:
        alpha = image.getchannel("A").point(lambda a: round(a * max(0.0, opacity)))
        image.putalpha(alpha)
    image.save(out)
    return out


def draw_words(source: Path, words: list[dict], out: Path, picture: bool) -> Path:
    """Exact words on a picture or a video. words: [{text, place, start?, end?, large?}]."""
    words = stack_lines(words)
    if picture:
        from PIL import Image

        frame = Image.open(source).convert("RGBA")
        for i, line in enumerate(words):
            band = out.with_name(f"{out.stem}-w{i}.png")
            _caption_png(line["text"], frame.size, band, **word_style(line))
            frame.alpha_composite(Image.open(band).convert("RGBA"))
            band.unlink()
        frame.convert("RGB").save(out)
        return out
    total = probe(source)["seconds"]
    return draw_captions(source, [dict(w, start=w.get("start") or 0, end=w.get("end") or total + 1) for w in words], out)


WORD_PLACES = {"top": 0.15, "middle": 0.5, "bottom": 0.80}
CORNERS = {"top_left": (0.08, "left"), "top_right": (0.08, "right"), "bottom_left": (0.92, "left"), "bottom_right": (0.92, "right")}
SIZES = {"small": 0.032, "normal": 0.052, "large": 0.075}


def word_style(line: dict) -> dict:
    """_caption_png settings for one line: {text, place, align?, size?, large?, style?, opacity?}."""
    place = line.get("place") or "bottom"
    at, align = CORNERS.get(place, (WORD_PLACES.get(place, 0.80), line.get("align") or "center"))
    size = line.get("size") or ("large" if line.get("large") else "normal")
    return {"at": at, "align": align, "share": SIZES.get(size, 0.052), "style": line.get("style") or "band",
            "opacity": float(line["opacity"]) if line.get("opacity") is not None else 1.0}


def stack_lines(lines: list[dict]) -> list[dict]:
    """Lines at the same place that are on screen at the same time become one band, one line under the other
    (2026-11-12, D23b and H44c: two bottom lines were drawn over each other)."""
    out: list[dict] = []
    for line in lines:
        start, end = line.get("start") or 0, line.get("end") if line.get("end") is not None else 1e9
        same = next((o for o in out if (o.get("place") or "bottom") == (line.get("place") or "bottom")
                     and (o.get("start") or 0) == start and (o.get("end") if o.get("end") is not None else 1e9) == end), None)
        if same:
            same["text"] += "\n" + line["text"]
        else:
            out.append(dict(line))
    return out


def draw_captions(film: Path, timed: list[dict], out: Path) -> Path:
    """Draw exact words on the picture. timed: [{"text", "start", "end", "place"?: top|middle|bottom, "large"?: bool}].
    Lines at the same place should not overlap in time. Needs Pillow."""
    info = probe(film)
    timed = stack_lines(timed)
    inputs, chain, last, pngs = ["-i", str(film)], [], "0:v", []
    for i, line in enumerate(timed):
        pngs.append(_caption_png(line["text"], (info["width"], info["height"]), out.with_name(f"{out.stem}-caption{i}.png"),
                                 **word_style(line)))
        inputs += ["-i", str(pngs[-1])]
        chain.append(f"[{last}][{i + 1}:v]overlay=enable='between(t,{line['start']:.2f},{line['end']:.2f})'[v{i}]")
        last = f"v{i}"
    _ffmpeg([*inputs, "-filter_complex", ";".join(chain), "-map", f"[{last}]", "-map", "0:a?",
                           "-c:v", "libx264", "-crf", "18", "-c:a", "copy", str(out)])
    for png in pngs:
        png.unlink()
    return out

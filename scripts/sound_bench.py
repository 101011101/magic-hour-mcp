"""Sound options for B1 (the 30 s product spot). Makes one film for each option so they can be compared.

    .venv/bin/python scripts/sound_bench.py --limit 1250          # spends credits, up to the limit
    .venv/bin/python scripts/sound_bench.py --limit 0 --only C    # rebuild a film from files that exist

A  narration inside each clip, one line for each shot (sound on, no music)
B  A + one music track under the whole film
C  B + captions drawn from the script
E  the silent v1 film + one narration track from a single call + the music + captions

Files go to Benchmark/sound/B1/. A step whose file exists is not made again. Needs ffmpeg, Pillow, OPENAI_API_KEY (word timing).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from split_bench import Budget, call, download, upload, wait  # noqa: E402

from mcp_magichour import media_tools  # noqa: E402
from mcp_magichour.video_production import plan  # noqa: E402

OUT = ROOT / "Benchmark" / "sound" / "B1"
FIXTURES = ROOT.parent / "magic-agent-video-generator" / "V2" / "bench" / "v1" / "fixtures"
DUO = ROOT / "Benchmark" / "modified" / "B1" / "run1" / "edited-reference.png"   # the picture v1's host made: the presenter holding the bottle
CARD = ROOT / "Benchmark" / "split" / "C5" / "cache" / "4c93d6834931-generate_image.png"
SILENT_FILM = ROOT / "Benchmark" / "modified" / "B1" / "run1" / "film.mp4"
SILENT_SHOTS = [0.0, 9.44, 18.85, 26.85]   # where each shot of the silent film starts

VOICE = "an off-camera narrator with a calm, warm, low-pitched woman's voice, a neutral American accent, unhurried"
LINES = [   # the user's script, one part for each shot
    ["Some scents fade by noon.", "This one stays."],
    ["It starts soft, like morning light on a wall,", "and it grows warmer as the day goes on."],
    ["One spray on the wrist is enough."],
    ["Mockup Fragrance.", "Available 12 December."],
]


def says(lines: list[str]) -> str:
    return f'The narrator says once, exactly: "{" ".join(lines)}" Nobody on screen speaks. No other words are spoken.'


STORY = {
    "id": "B1S", "title": "Mockup Fragrance, with sound", "aspect": "9:16", "audio": True, "seconds": 30,
    "setting": f"A perfume advertisement in soft warm sunlight on light neutral surfaces, calm and elegant. Sound: {VOICE}; no music.",
    "subjects": [
        {"id": "bottle", "role": "product", "picture": str(FIXTURES / "bench-mockup-fragrance.png"),
         "words": "The perfume: a clear rectangular glass bottle with clear liquid, a square brushed-grey cap and the words MOCKUP FRAGRANCE in black serif letters printed on the glass; no box"},
        {"id": "duo", "role": "person", "picture": str(DUO),
         "words": "The presenter holding the perfume: a woman with long parted dark brown hair and a dark charcoal blazer, the same clear glass bottle with the grey cap in her hand"},
    ],
    "beats": [
        {"seconds": 9, "place": "table", "subjects": ["bottle"], "text": f"The bottle stands alone on a light surface. The camera slides slowly past it. {says(LINES[0])}"},
        {"seconds": 9, "place": "room", "subjects": ["duo"], "link": "new", "text": f"She holds the bottle up in one hand and looks at it. Her mouth stays closed. {says(LINES[1])}"},
        {"seconds": 8, "place": "room", "subjects": ["duo"], "link": "new", "text": f"She lifts the cap off and sprays the perfume once on her other wrist. Her mouth stays closed. {says(LINES[2])}"},
        {"seconds": 4, "kind": "card", "exact_words": ["MOCKUP FRAGRANCE", "Available 12 December"], "text": "An end card: solid deep purple, two centred lines of white text."},
    ],
}


def run(*args: str) -> None:
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", *args])


def make_video(path: str, body: dict, out: Path, budget: Budget, credits: int, what: str) -> None:
    if out.exists():
        return
    budget.reserve(credits, what)
    created = call("POST", path, body)
    budget.charge(int(created.get("credits_charged", credits)))
    print(f"  {what} · {created.get('credits_charged')} credits", flush=True)
    download(wait("video", created["id"]), out)


def clips_with_narration(budget: Budget) -> list[Path]:
    p = plan(STORY, "manual", 15, cuts=[2, 3, 4])
    assert p["ok"], p["problems"]
    files = []
    for clip in p["clips"]:
        video, out = clip["steps"][-1], OUT / f"a-clip-{clip['n']}.mp4"
        if clip["kind"] == "card":   # the end card speaks the last line
            body = {"name": "sound-bench B1 card", "end_seconds": clip["seconds"], "model": video["model"], "resolution": "480p", "audio": True,
                    "style": {"prompt": f"{video['prompt']} Sound: {VOICE}; no music. {says(LINES[3])}"}}
            if not out.exists():
                body["assets"] = {"image_file_path": upload(CARD)}
            make_video("/v1/image-to-video", body, out, budget, clip["seconds"] * 24, "card with narration")
        else:
            ref = clip["reference"]
            body = {"name": f"sound-bench B1 clip {clip['n']}", "end_seconds": clip["seconds"], "aspect_ratio": "9:16", "model": video["model"],
                    "resolution": "480p", "audio": True, "style": {"prompt": video["prompt"]}}
            if not out.exists():
                body["references"] = [{"name": ref["subject"], "file_path": upload(Path(ref["file"]))}]
            make_video("/v1/text-to-video", body, out, budget, clip["seconds"] * 24, f"clip {clip['n']} with narration")
        files.append(out)
    (OUT / "a-plan.json").write_text(json.dumps(p, indent=2))
    return files


def music(budget: Budget, seconds: int = 32) -> Path:
    out = OUT / "music.mp3"
    if not out.exists():
        budget.reserve(seconds, "music")
        created = call("POST", "/v1/ai-music-generator", {"name": "sound-bench B1 music", "duration": seconds, "style": {
            "prompt": "Soft, warm solo piano with light strings, slow and elegant, a calm underscore for a perfume advertisement", "instrumental": True}})
        budget.charge(int(created.get("credits_charged", seconds)))
        print(f"  music · {created.get('credits_charged')} credits", flush=True)
        project = wait("audio", created["id"])
        raw = OUT / "music-source"
        download(project, raw)
        run("-i", str(raw), "-ar", "48000", "-ac", "2", str(out))
        raw.unlink()
    return out


def mix_music(film: Path, track: Path, out: Path) -> Path:
    seconds = media_tools.probe(film)["seconds"]
    run("-i", str(film), "-i", str(track), "-filter_complex",
        f"[1:a]volume=0.16,afade=t=in:d=1,afade=t=out:st={seconds - 2:.2f}:d=2[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out))
    return out


def words(audio: Path) -> list[dict]:
    """[{word, start, end}] from Whisper, for caption timing only (the captions show the script, not the transcript)."""
    key = os.getenv("OPENAI_API_KEY") or next(line.split("=", 1)[1].strip() for line in (ROOT / ".env").read_text().splitlines() if line.startswith("OPENAI_API_KEY="))
    wav = audio.with_suffix(".whisper.mp3")
    run("-i", str(audio), "-vn", "-ar", "16000", "-ac", "1", str(wav))
    raw = subprocess.check_output(["curl", "-s", "https://api.openai.com/v1/audio/transcriptions", "-H", f"Authorization: Bearer {key}",
                                   "-F", f"file=@{wav}", "-F", "model=whisper-1", "-F", "response_format=verbose_json", "-F", "timestamp_granularities[]=word"])
    wav.unlink()
    return json.loads(raw).get("words", [])


def squash(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def time_lines(heard: list[dict], lines: list[str], window: tuple[float, float]) -> list[tuple[str, float, float]]:
    """When each script line is said inside a window. A line that is not heard gets an even share of the window.
    The match is on letters only, so "mock up" in the transcript is "Mockup" in the script."""
    inside = [w for w in heard if window[0] - 0.2 <= w["start"] < window[1]]
    stream, owner = "", []   # every letter of the transcript, and the word it came from
    for i, w in enumerate(inside):
        letters = squash(w["word"])
        stream += letters
        owner += [i] * len(letters)
    out, at = [], 0
    for line in lines:
        found = stream.find(squash(line), at)
        if found < 0:
            out = []
            break
        last = found + len(squash(line)) - 1
        out.append((line, inside[owner[found]]["start"], inside[owner[last]]["end"] + 0.35))
        at = last + 1
    if not out:
        share = (window[1] - window[0] - 0.6) / len(lines)
        out = [(line, window[0] + 0.3 + i * share, window[0] + 0.3 + (i + 1) * share) for i, line in enumerate(lines)]
    # one caption at a time: a line leaves the screen when the next one starts
    return [(line, start, min(end, out[i + 1][1]) if i + 1 < len(out) else end) for i, (line, start, end) in enumerate(out)]


def caption_png(text: str, size: tuple[int, int], out: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    width, height = size
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", round(width * 0.052))
    lines, current = [], ""
    for word in text.split():
        if draw.textlength(f"{current} {word}".strip(), font=font) > width * 0.84 and current:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    lines.append(current)
    line_height = round(font.size * 1.3)
    top = round(height * 0.80) - line_height * len(lines) // 2
    box_width = max(draw.textlength(line, font=font) for line in lines) + font.size
    draw.rounded_rectangle([(width - box_width) / 2, top - font.size * 0.35, (width + box_width) / 2, top + line_height * len(lines) + font.size * 0.2],
                           radius=font.size * 0.4, fill=(0, 0, 0, 150))
    for i, line in enumerate(lines):
        draw.text(((width - draw.textlength(line, font=font)) / 2, top + i * line_height), line, font=font, fill=(255, 255, 255, 255))
    image.save(out)
    return out


def captions(film: Path, timed: list[tuple[str, float, float]], out: Path) -> Path:
    info = media_tools.probe(film)
    inputs, chain, last = ["-i", str(film)], [], "0:v"
    for i, (text, start, end) in enumerate(timed):
        png = caption_png(text, (info["width"], info["height"]), OUT / f"caption-{out.stem}-{i}.png")
        inputs += ["-i", str(png)]
        chain.append(f"[{last}][{i + 1}:v]overlay=enable='between(t,{start:.2f},{end:.2f})'[v{i}]")
        last = f"v{i}"
    run(*inputs, "-filter_complex", ";".join(chain), "-map", f"[{last}]", "-map", "0:a", "-c:v", "libx264", "-crf", "18", "-c:a", "copy", str(out))
    for png in OUT.glob(f"caption-{out.stem}-*.png"):
        png.unlink()
    return out


def one_voice(budget: Budget, track: Path) -> Path | None:
    """E: one narration for the whole script from a single call; each part is laid on its shot of the silent film."""
    source = OUT / "e-narration-source.mp4"
    script = " ".join(" ".join(part) for part in LINES)
    make_video("/v1/text-to-video", {
        "name": "sound-bench B1 narration", "end_seconds": 15, "aspect_ratio": "9:16", "model": "ltx-2.5", "resolution": "480p", "audio": True,
        "style": {"prompt": f"A plain black screen for the whole clip; nothing appears and nothing moves. Sound only: {VOICE}. "
                            f"The narrator reads these words once, exactly, at a relaxed pace, and then stays silent: \"{script}\" No music, no other sound."}},
        source, budget, 360, "one narration track, 15 s")
    heard = words(source)
    (OUT / "e-narration-words.json").write_text(json.dumps(heard, indent=2))
    whole = time_lines(heard, [" ".join(part) for part in LINES], (0, 15.5))
    if squash("".join(w["word"] for w in heard)).find(squash(script)) < 0:
        print("  E: the narration does not say the script exactly; E is not built", flush=True)
        return None
    ordered = whole
    delays, inputs, filters = [], ["-i", str(SILENT_FILM), "-i", str(source), "-i", str(track)], []
    film_seconds = media_tools.probe(SILENT_FILM)["seconds"]
    for i, (_, start, end) in enumerate(ordered):
        offset = SILENT_SHOTS[i] + 0.5
        filters.append(f"[1:a]atrim={max(0, start - 0.1):.2f}:{end:.2f},asetpts=PTS-STARTPTS,adelay={int(offset * 1000)}:all=1[p{i}]")
        delays.append((offset, end - start))
    filters.append(f"[2:a]volume=0.16,afade=t=in:d=1,afade=t=out:st={film_seconds - 2:.2f}:d=2[m]")
    filters.append("".join(f"[p{i}]" for i in range(len(ordered))) + f"[m]amix=inputs={len(ordered) + 1}:duration=longest:normalize=0,atrim=0:{film_seconds:.2f}[a]")
    mixed = OUT / "e-mixed.mp4"
    run(*inputs, "-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-t", f"{film_seconds:.2f}", str(mixed))
    timed = []
    for i, lines in enumerate(LINES[:3]):   # the card shows its own words
        offset, length = delays[i]
        share = length / len(lines)
        timed += [(line, offset + k * share, offset + (k + 1) * share) for k, line in enumerate(lines)]
    out = captions(mixed, timed, OUT / "e-one-voice-music-captions.mp4")
    mixed.unlink()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, required=True, help="the most credits this command may spend")
    parser.add_argument("--only", default="ABCE", help="which options to build")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    budget = Budget(args.limit)
    started = time.time()
    track = music(budget)
    if set(args.only) & set("ABC"):
        clips = clips_with_narration(budget)
        a = OUT / "a-voice-in-each-clip.mp4"
        media_tools.join(clips, a, audio=True)
        b = mix_music(a, track, OUT / "b-voice-and-music.mp4")
        heard = words(a)
        (OUT / "a-words.json").write_text(json.dumps(heard, indent=2))
        timed, at = [], 0.0
        for clip, lines in list(zip(clips, LINES))[:3]:   # the card shows its own words
            length = media_tools.probe(clip)["seconds"]
            timed += time_lines(heard, lines, (at, at + length))
            at += length
        captions(b, timed, OUT / "c-voice-music-captions.mp4")
        print("  A, B, C built", flush=True)
    if "E" in args.only:
        print("  E:", one_voice(budget, track), flush=True)
    print(f"spent {budget.spent} of {args.limit} credits · {round(time.time() - started)} s")


if __name__ == "__main__":
    main()

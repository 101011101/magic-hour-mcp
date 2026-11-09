"""A4's voice-over, made five ways, on the same picture: the 3 scene clips and the held logo of the questions-paid run.

    python3 scripts/voice_bench.py --limit 1150

A  voice cloner: a voice sample (macOS `say`, Samantha: a voice we may use) -> /v1/ai-voice-cloner reads the script
C  today's ltx-2.5 black-screen narration, with a word check: try 1 is the run's own track (nonsense), try 2 is a redo
D  one ltx-2.5 narration call per sentence, the three tracks put end to end
E  a presenter on screen says each sentence: the 3 scenes made again with a person in them, sound on
F  no voice: captions only
(B, the celebrity voice generator, is not run: a real person's voice on a company's ad.)
Every film is joined by the MCP's own join code. The word check is Whisper against the script.
Writes Benchmark/voice/A4/<key>/{film.mp4, narration.*, record.json}. A finished option is skipped on a second run.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from split_bench import AGENT, Budget, call, download, wait  # noqa: E402
from mcp_magichour import media_tools  # noqa: E402
from mcp_magichour.video_production_tool import CARD_SIZES, _add_sound, _planned  # noqa: E402

OUT = ROOT / "Benchmark" / "voice" / "A4"
RECORD = ROOT.parent / "magic-agent-video-generator" / "V2" / "bench" / "v1" / "results" / "questions-paid" / "A4.json"
LOGO = ROOT.parent / "magic-agent-video-generator" / "V2" / "bench" / "v1" / "fixtures" / "bench-logo.png"
RUN_NARRATION = "cmw77g8j905f8o2010dlv2x84"   # the run's own ltx-2.5 narration: Whisper heard nonsense
PRESENTER = ("A friendly presenter, a woman in her thirties with short dark hair and a plain teal shirt, stands at the left "
             "of the frame and looks at the camera")
SAMPLE = ("Hello. This is a short sample of my speaking voice, recorded for a voice clone. I read at a calm and steady pace, "
          "with clear words and a short pause after each sentence. The weather today is mild, and the morning was quiet.")


def calls(record: dict) -> list[dict]:
    return [c for t in record["turns"] for c in (t.get("tool_calls") or t.get("calls") or [])]


def story_of_run() -> dict:
    """The exact story the run produced its clips from: the production token of its first create_production_clip."""
    for c in calls(json.loads(RECORD.read_text())):
        if c["name"] == "create_production_clip":
            a = json.loads(c["arguments"]) if isinstance(c["arguments"], str) else c["arguments"]
            token = a["production"]
            return json.loads(zlib.decompress(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))))
    raise SystemExit("no create_production_clip in the record")


def clip_ids() -> dict[int, str]:
    for c in calls(json.loads(RECORD.read_text())):
        if c["name"] == "join_production_clips":
            a = json.loads(c["arguments"]) if isinstance(c["arguments"], str) else c["arguments"]
            return {int(k): v for k, v in a["made"].items()}
    raise SystemExit("no join in the record")


def fetch(kind: str, project_id: str, out: Path) -> Path:
    if not out.exists():
        download(wait(kind, project_id), out)
    return out


def whisper(file: Path) -> str:
    key = next(l.split("=", 1)[1].strip().strip('"') for l in (ROOT / ".env").read_text().splitlines() if l.startswith("OPENAI_API_KEY="))
    wav = file.with_name(file.stem + "-16k.wav")
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", str(file), "-vn", "-ac", "1", "-ar", "16000", str(wav)])
    out = subprocess.run(["curl", "-s", "https://api.openai.com/v1/audio/transcriptions", "-H", f"Authorization: Bearer {key}",
                          "-F", f"file=@{wav}", "-F", "model=whisper-1", "-F", "language=en"], capture_output=True, text=True).stdout
    wav.unlink()
    return json.loads(out).get("text", "")


def words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower().replace("’", "'"))


def match(heard: str, script: str) -> float:
    """The share of the script's words heard, in order (longest common subsequence)."""
    a, b = words(script), words(heard)
    row = [0] * (len(b) + 1)
    for x in a:
        prev = 0
        for j, y in enumerate(b, 1):
            prev, row[j] = row[j], (prev + 1 if x == y else max(row[j], row[j - 1]))
    return round(row[-1] / (len(a) or 1), 2)


def upload_audio(file: Path) -> str:
    item = call("POST", "/v1/files/upload-urls", {"items": [{"type": "audio", "extension": file.suffix.lstrip(".")}]})["items"][0]
    put = urllib.request.Request(item["upload_url"], method="PUT", data=file.read_bytes(), headers={"User-Agent": AGENT})
    with urllib.request.urlopen(put, timeout=120):
        pass
    return item["file_path"]


def paid(path: str, body: dict, kind: str, out: Path, budget: Budget, credits: int, what: str) -> dict:
    budget.reserve(credits, what)
    created = call("POST", path, body)
    charged = int(created.get("credits_charged", credits))
    budget.charge(charged)
    print(f"  {what} · {charged} credits", flush=True)
    download(wait(kind, created["id"]), out)
    return {"what": what, "project": created["id"], "credits": charged}


def ltx(prompt: str, seconds: int, out: Path, budget: Budget, what: str) -> dict:
    return paid("/v1/text-to-video", {"name": "voice-bench", "end_seconds": seconds, "aspect_ratio": "16:9", "model": "ltx-2.5",
                                      "resolution": "480p", "audio": True, "style": {"prompt": prompt}},
                "video", out, budget, seconds * 24, what)


class Picture:
    """The run's picture: its 3 scene clips and the held logo, joined silent as the MCP's join does."""

    def __init__(self, story: dict, planned: dict, base: Path):
        self.story, self.planned, base = story, planned, base
        base.mkdir(parents=True, exist_ok=True)
        ids, files = clip_ids(), []
        for clip in planned["clips"]:
            n = clip["n"]
            if clip.get("made_by") == "code":
                step = clip["steps"][0]
                png = media_tools.fit_picture(LOGO, step["background"], CARD_SIZES[story["aspect"]], base / f"card-{n}.png")
                files.append(media_tools.still_video(png, step["seconds"], base / f"clip-{n}.mp4"))
            else:
                files.append(fetch("video", ids[n], base / f"clip-{n}.mp4"))
        self.files = files
        self.starts, at = {}, 0.0
        for clip, file in zip(planned["clips"], files):
            self.starts[clip["n"]] = at
            at += media_tools.probe(file)["seconds"]
        self.silent = base / "joined-silent.mp4"
        if not self.silent.exists():
            media_tools.join(files, self.silent, audio=False)

    def with_narration(self, narration: Path, out: Path) -> dict:
        return _add_sound(self.planned["sound"], self.silent, narration, None, out, self.starts)

    def captions_only(self, out: Path) -> None:
        timed = []
        for part in self.planned["sound"]["narration"]["parts"]:
            start = self.starts[part["clip"]] + part["inside"] + 0.3
            for line in part["lines"]:
                timed.append({"text": line, "start": start, "end": start + part["seconds"] - 0.5})
        media_tools.draw_captions(self.silent, timed, out)


def option_a(pic: Picture, script: str, folder: Path, budget: Budget) -> dict:
    sample_aiff, sample = folder / "sample.aiff", folder / "sample.mp3"
    subprocess.check_call(["say", "-v", "Samantha", "-o", str(sample_aiff), SAMPLE])
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", str(sample_aiff), "-ac", "1", "-ar", "44100", str(sample)])
    sample_aiff.unlink()
    narration = folder / "narration.mp3"
    step = paid("/v1/ai-voice-cloner", {"name": "voice-bench A4 clone", "assets": {"audio_file_path": upload_audio(sample)},
                                       "style": {"prompt": script}}, "audio", narration, budget, -(-len(script) // 10), "voice cloner")
    return {"steps": [step], "narration": narration}


def option_c(pic: Picture, script: str, folder: Path, budget: Budget) -> dict:
    n = pic.planned["sound"]["narration"]
    tries = [{"what": "try 1: the run's own track", "project": RUN_NARRATION, "credits": 0}]
    first = fetch("video", RUN_NARRATION, folder / "narration-try1.mp4")
    tries[0]["heard"] = whisper(first)
    tries[0]["match"] = match(tries[0]["heard"], script)
    narration = first
    if tries[0]["match"] < 0.8:
        second = folder / "narration-try2.mp4"
        step = ltx(n["prompt"], n["seconds"], second, budget, "try 2: ltx-2.5 narration redo")
        step["heard"] = whisper(second)
        step["match"] = match(step["heard"], script)
        tries.append(step)
        narration = second
    return {"steps": tries, "narration": narration}


def option_d(pic: Picture, script: str, folder: Path, budget: Budget) -> dict:
    voice = (pic.story.get("narrator") or "a calm, warm narrator").strip().rstrip(".")
    steps, tracks = [], []
    for part in pic.planned["sound"]["narration"]["parts"]:
        line = " ".join(part["lines"])
        seconds = max(4, -(-len(line.split()) * 2 // 5) + 1)
        prompt = (f"A plain black screen for the whole clip; nothing appears and nothing moves. Sound only: an off-camera narrator, {voice}. "
                  f"The narrator reads these words once, exactly, at a relaxed pace, and then stays silent: \"{line}\" No music, no other sound.")
        track = folder / f"narration-{part['beat']}.mp4"
        steps.append(ltx(prompt, seconds, track, budget, f"sentence {part['beat']}: ltx-2.5 narration {seconds} s"))
        tracks.append(track)
    narration = folder / "narration.wav"   # the tracks end to end, 0.6 s of silence between, for the join's own placing
    inputs = sum((["-i", str(t)] for t in tracks), [])
    tracks_in = "".join(f"[{i}:a]aresample=48000,pan=mono|c0=c0[a{i}];" for i in range(len(tracks)))
    silences = "".join(f"anullsrc=r=48000:cl=mono,atrim=0:0.6[s{i}];" for i in range(len(tracks) - 1))
    order = "".join(f"[a{i}]" + (f"[s{i}]" if i < len(tracks) - 1 else "") for i in range(len(tracks)))
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex",
                           tracks_in + silences + order + f"concat=n={2 * len(tracks) - 1}:v=0:a=1[out]",
                           "-map", "[out]", str(narration)])
    return {"steps": steps, "narration": narration}


def option_e(pic: Picture, script: str, folder: Path, budget: Budget, out: Path) -> dict:
    steps, files = [], []
    by_clip = {p["clip"]: p for p in pic.planned["sound"]["narration"]["parts"]}
    for clip in pic.planned["clips"]:
        if clip.get("made_by") == "code":
            files.append(pic.files[clip["n"] - 1])
            continue
        base = clip["steps"][0]["prompt"].replace(" No repeated shots, no title cards, no captions, no other scenes.", "")
        line = " ".join(by_clip[clip["n"]]["lines"])
        prompt = (f"{base.split(' 0-')[0]} {PRESENTER}; beside her, on the right: {base.split(': ', 1)[1].split(' Each action')[0]} "
                  f"Said out loud on screen by the presenter, once, word for word: \"{line}\" No music, no other speech, no captions.")
        file = folder / f"clip-{clip['n']}.mp4"
        step = ltx(prompt, clip["seconds"], file, budget, f"clip {clip['n']}: presenter scene {clip['seconds']} s")
        step["prompt"] = prompt
        steps.append(step)
        files.append(file)
    joined = folder / "joined.mp4"
    media_tools.join(files, joined, audio=True)
    timed, at = [], 0.0
    for clip, file in zip(pic.planned["clips"], files):
        seconds = media_tools.probe(file)["seconds"]
        if clip["n"] in by_clip:
            spans = media_tools.speech_spans(file)
            start, end = (spans[0][0], spans[-1][1]) if spans else (0.3, seconds - 0.3)
            timed.append({"text": " ".join(by_clip[clip["n"]]["lines"]), "start": at + start, "end": at + end})
        at += seconds
    media_tools.draw_captions(joined, timed, out)
    joined.unlink()
    return {"steps": steps, "narration": out}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, required=True, help="the most credits this command may spend")
    parser.add_argument("--only", action="append", default=[])
    args = parser.parse_args()
    budget = Budget(args.limit)
    story = story_of_run()
    planned = _planned(story)
    script = " ".join(line for p in planned["sound"]["narration"]["parts"] for line in p["lines"])
    pic = Picture(story, planned, OUT / "picture")
    names = {"A": "Voice cloner (a sample voice)", "C": "Today's narration + word check, one redo",
             "D": "One narration call per sentence", "E": "A presenter on screen says it", "F": "Captions only, no voice"}
    for key, name in names.items():
        folder = OUT / key
        if (args.only and key not in args.only) or (folder / "record.json").exists():
            continue
        folder.mkdir(parents=True, exist_ok=True)
        record = {"id": key, "name": name, "script": script, "steps": []}
        film = folder / "film.mp4"
        try:
            if key == "F":
                pic.captions_only(film)
            elif key == "E":
                record.update(option_e(pic, script, folder, budget, film))
            else:
                record.update({"A": option_a, "C": option_c, "D": option_d}[key](pic, script, folder, budget))
                record["sound"] = pic.with_narration(record["narration"], film)
            record["narration"] = str(record.get("narration", ""))
            record["film"] = media_tools.probe(film)
            record["heard"] = whisper(film) if key != "F" else ""
            record["match"] = match(record["heard"], script) if key != "F" else None
        except Exception as error:   # one attempt
            record["failed"] = str(error)
            record["narration"] = str(record.get("narration", ""))
            print(f"  {key} FAILED: {error}", flush=True)
        record["credits"] = sum(s.get("credits", 0) for s in record["steps"])
        (folder / "record.json").write_text(json.dumps(record, indent=2))
        print(f"{key} {name} · {record['credits']} credits · match {record.get('match')} · {record.get('heard', '')[:160]}", flush=True)
    print(f"spent {budget.spent} of {args.limit} credits")


if __name__ == "__main__":
    main()

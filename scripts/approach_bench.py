"""Compare ways to do two jobs, one paid call per approach, one attempt each.

    python3 scripts/approach_bench.py words --limit 600     # exact words on screen at the end of a scene (A2's ending)
    python3 scripts/approach_bench.py continue --limit 450  # continue a given clip for 6 s (A3)

words: W1 ltx-2.5 asked for the words · W2 minimax-h3 asked for the words · W3 a still with the words (qwen), animated
by ltx-2.5 · W4 a clean ltx-2.5 scene, words drawn by code · W5 the clean scene, then a card (qwen still, ltx-2.5).
continue: C2 last frame -> ltx-2.5 image-to-video, joined after the original · C3 last frame -> minimax-h3
image-to-video, joined · C4 minimax-h3 text-to-video with the original clip as a named reference, joined.
(C1 is the one-call regeneration that the old MCP and v1 both made: those films are reused, not made again.)
Writes Benchmark/approach/<job>/<id>/{film.mp4, record.json}. A finished approach is skipped on a second run.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from split_bench import Budget, call, download, upload, wait  # noqa: E402
from mcp_magichour.media_tools import FONTS, _ffmpeg, join, last_frame, probe  # noqa: E402

OUT = ROOT / "Benchmark" / "approach"
FIXTURES = ROOT.parent / "magic-agent-video-generator" / "V2" / "bench" / "v1" / "fixtures"

WOMAN = "A tall woman with a silver bob, a red raincoat and yellow boots"
SCENE = (f"{WOMAN} walks away from a bus stop down a wet city street at night in the rain, seen from behind, "
         "until she is small in the distance. Streetlights reflect on the wet road. One slow shot.")
WORDS = "walk anyway"
ASK = f' In the last two seconds the words "{WORDS}" appear on screen in large white letters, spelled exactly "{WORDS}".'
CLEAN = " No text, no letters, no signs with writing anywhere in the picture."

TURN = ("She turns around so her back is to the camera and walks away across the park until she leaves the frame. "
        "The same woman: the same face, dark curly shoulder-length hair and grey knit sweater; the same park and light. "
        "One continuous shot, no cut, no music, no speech.")


def make(path: str, body: dict, out: Path, budget: Budget, credits: int, what: str, kind: str = "video") -> dict:
    budget.reserve(credits, what)
    started = time.time()
    created = call("POST", path, body)
    charged = int(created.get("credits_charged", credits))
    budget.charge(charged)
    print(f"  {what} · {charged} credits", flush=True)
    download(wait(kind, created["id"]), out)
    return {"what": what, "project": created["id"], "credits": charged, "seconds": round(time.time() - started)}


def still(prompt: str, aspect: str, out: Path, budget: Budget) -> dict:
    return make("/v1/ai-image-generator", {"name": "approach-bench still", "image_count": 1, "model": "qwen-image-2.1",
                                           "aspect_ratio": aspect, "resolution": "640px", "style": {"prompt": prompt}},
                out, budget, 10, "qwen still", kind="image")


def t2v(model: str, prompt: str, seconds: int, aspect: str, out: Path, budget: Budget, references: list | None = None,
        audio: bool = False) -> dict:
    body = {"name": "approach-bench", "end_seconds": seconds, "aspect_ratio": aspect, "model": model, "resolution": "480p",
            "audio": audio, "style": {"prompt": prompt}}
    if references:
        body["references"] = references
    return make("/v1/text-to-video", body, out, budget, seconds * 24, f"{model} text-to-video {seconds} s")


def i2v(model: str, prompt: str, seconds: int, image: Path, out: Path, budget: Budget) -> dict:
    return make("/v1/image-to-video", {"name": "approach-bench", "end_seconds": seconds, "model": model, "resolution": "480p",
                                       "audio": False, "style": {"prompt": prompt}, "assets": {"image_file_path": upload(image)}},
                out, budget, seconds * 24, f"{model} image-to-video {seconds} s")


def draw_words(film: Path, text: str, start: float, out: Path) -> Path:
    """Large white words, centred in the lower third, from `start` to the end. The code path the join would use."""
    from PIL import Image, ImageDraw, ImageFont

    info = probe(film)
    size = (info["width"], info["height"])
    points = round(min(size) * 0.13)
    font = next((ImageFont.truetype(f, points) for f in FONTS if Path(f).exists()), None) or ImageFont.load_default(points)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    x, y = (size[0] - draw.textlength(text, font=font)) / 2, size[1] * 0.68
    draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    png = out.with_suffix(".png")
    image.save(png)
    _ffmpeg(["-i", str(film), "-i", str(png), "-filter_complex", f"[0:v][1:v]overlay=enable='gte(t,{start:.2f})'",
             "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-c:a", "copy", str(out)])
    png.unlink()
    return out


def run_words(budget: Budget) -> list[dict]:
    root = OUT / "words"
    shared = root / "shared"
    shared.mkdir(parents=True, exist_ok=True)
    clean = shared / "clean-scene.mp4"
    records = []

    def approach(key: str, name: str, how: str, body) -> None:
        folder = root / key
        if (folder / "record.json").exists():
            records.append(json.loads((folder / "record.json").read_text()))
            return
        folder.mkdir(parents=True, exist_ok=True)
        record = {"id": key, "name": name, "how": how, "steps": []}
        try:
            body(folder, record["steps"])
            record["film"] = probe(folder / "film.mp4")
        except Exception as error:   # one attempt
            record["failed"] = str(error)
            print(f"  {key} FAILED: {error}", flush=True)
        record["credits"] = sum(s["credits"] for s in record["steps"])
        (folder / "record.json").write_text(json.dumps(record, indent=2))
        records.append(record)

    def w1(folder, steps):
        steps.append(t2v("ltx-2.5", SCENE + ASK, 5, "16:9", folder / "film.mp4", budget))

    def w2(folder, steps):
        steps.append(t2v("minimax-h3", SCENE + ASK, 5, "16:9", folder / "film.mp4", budget))
        join([folder / "film.mp4"], folder / "silent.mp4", audio=False)   # minimax-h3 adds music with audio off
        (folder / "silent.mp4").replace(folder / "film.mp4")

    def w3(folder, steps):
        steps.append(still(f"{WOMAN} seen from behind, walking away from a bus stop down a wet city street at night in the rain. "
                           f'Large white letters across the lower third read exactly "{WORDS}". No other text.', "16:9", folder / "still.png", budget))
        steps.append(i2v("ltx-2.5", f"The supplied image comes to life: she keeps walking away into the rain, slowly. The words "
                                    f'"{WORDS}" stay exactly as in the image, fixed in place, every letter unchanged.', 5, folder / "still.png", folder / "film.mp4", budget))

    def clean_scene(steps):
        if clean.exists():
            steps.append({"what": "clean scene (shared with W5)", "credits": 0})
        else:
            steps.append(t2v("ltx-2.5", SCENE + CLEAN, 5, "16:9", clean, budget))

    def w4(folder, steps):
        clean_scene(steps)
        draw_words(clean, WORDS, 3.0, folder / "film.mp4")
        steps.append({"what": "words drawn by code for the last 2 s", "credits": 0})

    def w5(folder, steps):
        clean_scene(steps)
        steps.append(still(f'A title card: solid black background, centred white text reading exactly "{WORDS}". No other text, nothing else.',
                           "16:9", folder / "card.png", budget))
        steps.append(i2v("ltx-2.5", "The supplied image held almost motionless for the whole clip: a very slow, barely visible push in. "
                                    "Every letter stays exactly as in the image. Nothing else appears.", 2, folder / "card.png", folder / "card.mp4", budget))
        join([clean, folder / "card.mp4"], folder / "film.mp4", audio=False)

    approach("W1", "Ask ltx-2.5", "One ltx-2.5 text-to-video call; the prompt asks for the words. What the old MCP and v1 do for A2.", w1)
    approach("W2", "Ask minimax-h3", "One minimax-h3 text-to-video call; the same prompt.", w2)
    approach("W3", "Words in the start still", "qwen still with the scene and the words, then ltx-2.5 image-to-video from it.", w3)
    approach("W4", "Draw the words with code", "A clean ltx-2.5 scene (no text asked), then the words drawn over its last 2 s by the join.", w4)
    approach("W5", "Scene, then a card", "The same clean scene, then a 2 s card (qwen still -> ltx-2.5), joined. The words are not over the scene.", w5)
    return records


def run_continue(budget: Budget) -> list[dict]:
    root = OUT / "continue"
    original = FIXTURES / "bench-portrait-clip.mp4"
    root.mkdir(parents=True, exist_ok=True)
    start = last_frame(original, root / "original-last-frame.jpg")
    records = []

    def approach(key: str, name: str, how: str, body) -> None:
        folder = root / key
        if (folder / "record.json").exists():
            records.append(json.loads((folder / "record.json").read_text()))
            return
        folder.mkdir(parents=True, exist_ok=True)
        record = {"id": key, "name": name, "how": how, "steps": []}
        try:
            body(folder, record["steps"])
            join([original, folder / "new.mp4"], folder / "film.mp4", audio=False)
            record["film"] = probe(folder / "film.mp4")
        except Exception as error:   # one attempt
            record["failed"] = str(error)
            print(f"  {key} FAILED: {error}", flush=True)
        record["credits"] = sum(s["credits"] for s in record["steps"])
        (folder / "record.json").write_text(json.dumps(record, indent=2))
        records.append(record)

    approach("C2", "Last frame, ltx-2.5", "Last frame of the original -> 6 s ltx-2.5 image-to-video, audio off; original + new, joined silent.",
             lambda f, s: s.append(i2v("ltx-2.5", "The supplied image is the first frame. " + TURN, 6, start, f / "new.mp4", budget)))
    approach("C3", "Last frame, minimax-h3", "Last frame of the original -> 6 s minimax-h3 image-to-video, audio off; joined silent.",
             lambda f, s: s.append(i2v("minimax-h3", "The supplied image is the first frame. " + TURN, 6, start, f / "new.mp4", budget)))
    approach("C4", "Clip as a reference, minimax-h3", "6 s minimax-h3 text-to-video with the original clip as a named reference; joined silent.",
             lambda f, s: s.append(t2v("minimax-h3", "Continue @clip from its last frame: the first frame of this video is the last frame of @clip. " + TURN,
                                       6, "1:1", f / "new.mp4", budget, references=[{"name": "clip", "file_path": upload(original)}])))
    return records


LINE = "You came back."
LINE_ALONE = ("A 4-second 16:9 clip. Rainy night, a city bus stop. Close on an older man with a grey beard and a green coat under a black "
              "umbrella, beside a woman with a silver bob in a red raincoat. He looks at her and says out loud, clearly: \"You came back.\" "
              "Rain sound. No music, no other speech.")


def run_line(budget: Budget) -> list[dict]:
    """B2's spoken line alone in a short close-up. (Inside the 12 s two-beat clip it was silent 3 times of 3.)"""
    root = OUT / "line"
    records = []
    for key, model in (("L1", "ltx-2.5"), ("L2", "ltx-2.5"), ("L3", "ltx-2.5"), ("M1", "minimax-h3"), ("M2", "minimax-h3")):
        folder = root / key
        if (folder / "record.json").exists():
            records.append(json.loads((folder / "record.json").read_text()))
            continue
        folder.mkdir(parents=True, exist_ok=True)
        record = {"id": key, "name": f"Line alone, {model}", "how": f"4 s {model} text-to-video, audio on, the line alone", "prompt": LINE_ALONE, "steps": []}
        try:
            record["steps"].append(t2v(model, LINE_ALONE, 4, "16:9", folder / "film.mp4", budget, audio=True))
            record["film"] = probe(folder / "film.mp4")
        except Exception as error:   # one attempt
            record["failed"] = str(error)
            print(f"  {key} FAILED: {error}", flush=True)
        record["credits"] = sum(s["credits"] for s in record["steps"])
        (folder / "record.json").write_text(json.dumps(record, indent=2))
        records.append(record)
    return records


MAN = "an older man with a grey beard and a green coat under a black umbrella"
WOMAN_RED = "a woman with a silver bob in a red raincoat"
STOP = "A 4-second 16:9 clip. Rainy night, a city bus stop. "
TAIL = " Rain sound. No music, no other speech."
FACING = {
    "S1": ("ltx-2.5", "Back to the camera",
           STOP + f"Seen from behind: {MAN} stands with his back to the camera, facing {WOMAN_RED} who faces him. "
           f"He keeps his back to the camera the whole time and says out loud, clearly: \"{LINE}\"" + TAIL),
    "S2": ("ltx-2.5", "Side view, to someone off screen",
           STOP + f"A side view of {MAN}, in profile, looking to the right at someone off screen. He stays in profile "
           f"and says out loud, clearly: \"{LINE}\"" + TAIL),
    "S3": ("ltx-2.5", "Far away, small in the frame",
           STOP + f"A wide shot: {MAN} is small and far away across the street. He says out loud, clearly: \"{LINE}\"" + TAIL),
    "S4": ("ltx-2.5", "Two people: the one facing away speaks",
           STOP + f"{MAN} stands with his back to the camera; {WOMAN_RED} faces the camera, looking at him. Only the man speaks: "
           f"he says out loud, clearly: \"{LINE}\" The woman does not speak; her mouth stays closed." + TAIL),
    "S5": ("minimax-h3", "Back to the camera",
           STOP + f"Seen from behind: {MAN} stands with his back to the camera, facing {WOMAN_RED} who faces him. "
           f"He keeps his back to the camera the whole time and says out loud, clearly: \"{LINE}\"" + TAIL),
    "S6": ("minimax-h3", "Two people: the one facing away speaks",
           STOP + f"{MAN} stands with his back to the camera; {WOMAN_RED} faces the camera, looking at him. Only the man speaks: "
           f"he says out loud, clearly: \"{LINE}\" The woman does not speak; her mouth stays closed." + TAIL),
}


def run_facing(budget: Budget) -> list[dict]:
    """A spoken line when the speaker does not face the camera. Is it said, does he stay turned away, does the right one speak."""
    root = OUT / "facing"
    records = []
    for key, (model, name, prompt) in FACING.items():
        folder = root / key
        if (folder / "record.json").exists():
            records.append(json.loads((folder / "record.json").read_text()))
            continue
        folder.mkdir(parents=True, exist_ok=True)
        record = {"id": key, "name": f"{name}, {model}", "how": f"4 s {model} text-to-video, sound on", "prompt": prompt, "steps": []}
        try:
            record["steps"].append(t2v(model, prompt, 4, "16:9", folder / "film.mp4", budget, audio=True))
            record["film"] = probe(folder / "film.mp4")
        except Exception as error:   # one attempt
            record["failed"] = str(error)
            print(f"  {key} FAILED: {error}", flush=True)
        record["credits"] = sum(s["credits"] for s in record["steps"])
        (folder / "record.json").write_text(json.dumps(record, indent=2))
        records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("job", choices=["words", "continue", "line", "facing"])
    parser.add_argument("--limit", type=int, required=True, help="the most credits this command may spend")
    args = parser.parse_args()
    budget = Budget(args.limit)
    records = {"words": run_words, "continue": run_continue, "line": run_line, "facing": run_facing}[args.job](budget)
    for r in records:
        print(f"{r['id']} {r['name']} · {r['credits']} credits · {r.get('failed') or 'made'}")
    print(f"spent {budget.spent} of {args.limit} credits")


if __name__ == "__main__":
    main()

"""Compare clip-split rules on the test stories in tests/fixtures/stories.

Dry (default): print every story x variant as the calls it would make, with credits. Spends nothing.
    python3 scripts/split_bench.py [--only C4] [--only C4:one-per-shot] [--prompts]

Run: make the clips, join them, write a record. Spends Magic Hour credits, up to --limit.
    python3 scripts/split_bench.py --run --only C4:one-per-shot --limit 700 \
        --fixtures ../magic-agent-video-generator/V2/bench/v1/fixtures --out Benchmark/split

Identical calls inside one story (the same card, the same first clip in two variants) are made once and reused.
Needs ffmpeg and ffprobe for the last frame and the join. Reads MAGIC_HOUR_API_KEY from the environment or .env.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp_magichour.video_production import check_outputs, plan  # noqa: E402

STORIES = ROOT / "tests" / "fixtures" / "stories"
API = os.getenv("MAGIC_HOUR_API_BASE_URL", "https://api.magichour.ai")
AGENT = "magic-hour-mcp-split-bench/0.1"


# ---- plans ----------------------------------------------------------------------------------------------------------
def load(only: list[str]) -> list[tuple[dict, dict, dict]]:
    """[(story, variant, plan)] for every story x variant that --only keeps."""
    out = []
    for path in sorted(STORIES.glob("*.json")):
        story = json.loads(path.read_text())
        for variant in story["variants"]:
            name = f"{story['id']}:{variant['name']}"
            if only and story["id"] not in only and name not in only:
                continue
            out.append((story, variant, plan(story, variant["strategy"], variant.get("max_seconds", 15),
                                             cuts=variant.get("cuts"), chain=variant.get("chain", True),
                                             end_on=variant.get("end_on", True))))
    return out


def step_key(story: dict, clip: dict, step: dict) -> str | None:
    """A cache key for a call whose inputs are fully known before the run. A last-frame call is never shared."""
    if clip["reference"]["kind"] == "last_frame":
        return None
    seed = json.dumps([story["id"], story["aspect"], step["tool"], step["model"], step.get("seconds"), step["prompt"],
                       clip["reference"].get("file")], sort_keys=True)
    return hashlib.sha1(seed.encode()).hexdigest()[:12]


def show(rows: list[tuple[dict, dict, dict]], prompts: bool) -> None:
    total, unique, seen = 0, 0, set()
    for story, variant, p in rows:
        print(f"\n{story['id']} {story['title']} · {variant['name']} ({variant['strategy']}, max {variant.get('max_seconds', 15)} s)"
              f" · {p['seconds']} s · {len(p['clips'])} clip(s) · {p['credits']} credits")
        if p["problems"]:
            print("  PROBLEMS: " + "; ".join(p["problems"]))
        for clip in p["clips"]:
            ref = clip["reference"]
            what = {"none": "no reference", "last_frame": f"last frame of clip {ref.get('of_clip')}",
                    "picture": f"picture of {ref.get('subject')}", "still": "its own still"}[ref["kind"]]
            video = clip["steps"][-1]
            print(f"  clip {clip['n']}: beats {clip['beats']} · {clip['seconds']} s · {what} · {video['tool']} on {video['model']}"
                  f" · prompt {len(video['prompt'])} chars")
            if prompts:
                for step in clip["steps"]:
                    print(f"      [{step['tool']}] {step['prompt']}")
            for step in clip["steps"]:
                total += step["credits"]
                key = step_key(story, clip, step)
                if key is None or (key, step["tool"]) not in seen:
                    unique += step["credits"]
                    seen.add((key, step["tool"]))
    print(f"\n{len(rows)} run(s) · {total} credits if each ran alone · {unique} credits with identical calls reused")


# ---- the API --------------------------------------------------------------------------------------------------------
def api_key() -> str:
    key = os.getenv("MAGIC_HOUR_API_KEY")
    if not key and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith("MAGIC_HOUR_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise SystemExit("MAGIC_HOUR_API_KEY is not set")
    return key


def call(method: str, path: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json", "User-Agent": AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"{method} {path} -> HTTP {error.code}: {error.read().decode(errors='replace')[:400]}") from None


def upload(file: Path) -> str:
    extension = file.suffix.lstrip(".").lower()
    kind = "video" if extension in ("mp4", "mov", "webm") else "image"
    item = call("POST", "/v1/files/upload-urls", {"items": [{"type": kind, "extension": extension}]})["items"][0]
    put = urllib.request.Request(item["upload_url"], method="PUT", data=file.read_bytes(), headers={"User-Agent": AGENT})
    with urllib.request.urlopen(put, timeout=120):
        pass
    return item["file_path"]


def wait(kind: str, project_id: str, minutes: float = 20) -> dict:
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        project = call("GET", f"/v1/{kind}-projects/{project_id}")
        if project.get("status") in ("complete", "error", "canceled"):
            return project
        time.sleep(5)
    raise RuntimeError(f"{kind} project {project_id} did not finish in {minutes} minutes; it was NOT made again")


def download(project: dict, out: Path) -> None:
    if project.get("status") != "complete" or not project.get("downloads"):
        raise RuntimeError(f"project {project.get('id')} ended as {project.get('status')}: {project.get('error')}")
    request = urllib.request.Request(project["downloads"][0]["url"], headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        out.write_bytes(response.read())


# ---- files: the same steps the server uses ------------------------------------------------------------------------
from mcp_magichour.media_tools import join, last_frame, probe  # noqa: E402


# ---- the run --------------------------------------------------------------------------------------------------------
class Budget:
    def __init__(self, limit: int):
        self.limit, self.spent = limit, 0

    def reserve(self, credits: int, what: str) -> None:
        if self.spent + credits > self.limit:
            raise RuntimeError(f"stopped before {what}: it costs {credits} credits and {self.limit - self.spent} of {self.limit} are left")

    def charge(self, credits: int) -> None:
        self.spent += credits


def make_step(story: dict, clip: dict, step: dict, image: Path | None, folder: Path, cache: Path, fixtures: Path, budget: Budget) -> dict:
    """One paid call (or its reuse). Returns {file, credits, seconds_waited, project, reused}."""
    is_image = step["tool"] == "generate_image"
    extension = "png" if is_image else "mp4"
    key = step_key(story, clip, step)
    cached = cache / f"{key}-{step['tool']}.{extension}" if key else None
    out = folder / f"clip-{clip['n']}{'-still' if is_image else ''}.{extension}"
    if cached is not None and cached.exists():
        out.write_bytes(cached.read_bytes())
        return {"file": out.name, "credits": 0, "reused": cached.name}
    budget.reserve(step["credits"], f"clip {clip['n']} ({step['tool']})")
    name = f"split-bench {story['id']} clip {clip['n']}"
    started = time.time()
    if is_image:
        created = call("POST", "/v1/ai-image-generator", {
            "name": name, "image_count": 1, "model": step["model"], "aspect_ratio": story["aspect"], "resolution": "640px",
            "style": {"prompt": step["prompt"]},
        })
        kind = "image"
    elif step["tool"] == "create_video_from_image":
        created = call("POST", "/v1/image-to-video", {
            "name": name, "end_seconds": step["seconds"], "model": step["model"], "resolution": step["resolution"],
            "audio": step["audio"], "style": {"prompt": step["prompt"]}, "assets": {"image_file_path": upload(image)},
        })
        kind = "video"
    else:
        body = {
            "name": name, "end_seconds": step["seconds"], "aspect_ratio": story["aspect"], "model": step["model"],
            "resolution": step["resolution"], "audio": step["audio"], "style": {"prompt": step["prompt"]},
        }
        if clip["reference"]["kind"] == "picture":
            body["references"] = [{"name": clip["reference"]["subject"], "file_path": upload(fixtures / clip["reference"]["file"])}]
        created = call("POST", "/v1/text-to-video", body)
        kind = "video"
    budget.charge(int(created.get("credits_charged", step["credits"])))
    download(wait(kind, created["id"]), out)
    if cached is not None:
        cached.write_bytes(out.read_bytes())
    return {"file": out.name, "project": created["id"], "credits": int(created.get("credits_charged", step["credits"])),
            "seconds_waited": round(time.time() - started)}


def run_one(story: dict, variant: dict, p: dict, out_root: Path, fixtures: Path, budget: Budget) -> dict:
    folder = out_root / story["id"] / variant["name"]
    cache = out_root / story["id"] / "cache"
    folder.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    record = {"story": story["id"], "variant": variant, "plan": p, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "clips": []}
    files: dict[int, Path] = {}
    try:
        for clip in p["clips"]:
            image = None
            if clip["reference"]["kind"] == "last_frame":
                image = last_frame(files[clip["reference"]["of_clip"]], folder / f"clip-{clip['n']}-start.jpg")
            entry = {"n": clip["n"], "steps": []}
            record["clips"].append(entry)
            for step in clip["steps"]:
                made = make_step(story, clip, step, image, folder, cache, fixtures, budget)
                entry["steps"].append({"tool": step["tool"], "model": step["model"], **made})
                print(f"  {story['id']}:{variant['name']} clip {clip['n']} {step['tool']} · {made['credits']} credits"
                      f"{' · reused' if made.get('reused') else ''}", flush=True)
                if step["tool"] == "generate_image":
                    image = folder / made["file"]
            files[clip["n"]] = folder / entry["steps"][-1]["file"]
            entry["measured"] = {"n": clip["n"], **probe(files[clip["n"]])}
        join([files[n] for n in p["join"]], folder / "film.mp4", audio=bool(story.get("audio")))
        record["film"] = {"file": "film.mp4", **probe(folder / "film.mp4")}
        record["output_problems"] = check_outputs(p, [c["measured"] for c in record["clips"]])
    except Exception as error:  # one attempt: a failed step ends this run and is recorded
        record["failed"] = str(error)
        print(f"  {story['id']}:{variant['name']} FAILED: {error}", flush=True)
    record["credits"] = sum(s["credits"] for c in record["clips"] for s in c["steps"])
    record["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (folder / "record.json").write_text(json.dumps(record, indent=2))
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", action="append", default=[], help="a story id (C4) or story:variant (C4:one-per-shot); repeatable")
    parser.add_argument("--prompts", action="store_true", help="dry: also print every prompt")
    parser.add_argument("--run", action="store_true", help="make the clips (spends credits)")
    parser.add_argument("--limit", type=int, help="with --run: the most credits this command may spend")
    parser.add_argument("--fixtures", type=Path, default=ROOT.parent / "magic-agent-video-generator" / "V2" / "bench" / "v1" / "fixtures")
    parser.add_argument("--out", type=Path, default=ROOT / "Benchmark" / "split")
    args = parser.parse_args()
    rows = load(args.only)
    if not rows:
        raise SystemExit("nothing matches --only")
    if not args.run:
        show(rows, args.prompts)
        return
    if args.limit is None:
        raise SystemExit("--run needs --limit (the most credits this command may spend)")
    bad = [f"{s['id']}:{v['name']}" for s, v, p in rows if not p["ok"]]
    if bad:
        raise SystemExit("these plans have problems, nothing was run: " + ", ".join(bad))
    budget = Budget(args.limit)
    for story, variant, p in rows:
        record = run_one(story, variant, p, args.out, args.fixtures, budget)
        print(f"{story['id']}:{variant['name']} · {record['credits']} credits · "
              f"{record.get('film', {}).get('seconds', 0):.1f} s · {record.get('failed') or 'made'}", flush=True)
    print(f"spent {budget.spent} of {args.limit} credits")


if __name__ == "__main__":
    main()

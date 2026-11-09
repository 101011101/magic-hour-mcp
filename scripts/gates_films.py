"""Collect each side's delivered film for the gates test, with a frame sheet and measurements, for scoring by eye.

    python3 scripts/gates_films.py

Writes Benchmark/gates/<item>/<side>/{film.mp4, sheet.jpg, info.json}. The delivered film is the last video the run
produced (a join when there is one). Copies files; deletes nothing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mcp_magichour.media_tools import loudness_db, probe  # noqa: E402

V2 = ROOT.parent / "magic-agent-video-generator" / "V2"
RESULTS = V2 / "bench" / "v1" / "results"
OUT = ROOT / "Benchmark" / "gates"
ITEMS = ["A2", "A3", "A4", "B1", "B2", "C10", "J55a"]
# side: {item: (results folder, record file)}
OLD = {"A2": ("mcp-dense-2-A2", "A2"), "A3": ("mcp-dense-2-A3", "A3"), "A4": ("mcp-dense-2-A4", "A4"), "B1": ("mcp-dense-1b", "B1b"),
       "B2": ("mcp-dense-2-B2", "B2"), "C10": ("gates2-old", "C10"), "J55a": ("gates2-old", "J55a")}
SIDES = {"old": OLD, **{s: {i: (f"gates2-{s}", i) for i in ITEMS} for s in ("v1", "warn")},
         "refuse": {i: ("gates3-refuse", i) for i in ITEMS},
         "new": {i: ("questions-paid", i) for i in ITEMS}}   # 7 November: the host groups the clips, the MCP asks questions   # gates2-refuse was invalid: plan_token rejected by the argument check


def record(side: str, item: str) -> dict | None:
    folder, name = SIDES[side][item]
    file = RESULTS / folder / f"{name}.json"
    return json.loads(file.read_text()) if file.exists() else None


def delivered(rec: dict) -> Path | None:
    videos = [s["output"] for t in rec["turns"] for s in (t.get("ran") or []) if (s.get("output") or "").endswith(".mp4")]
    if not videos:
        return None
    joins = [v for v in videos if "join" in v]
    return V2 / rec["sessionDir"] / (joins[-1] if joins else videos[-1])


def main() -> None:
    summary = {}
    for item in ITEMS:
        for side in SIDES:
            rec = record(side, item)
            if rec is None or "turns" not in rec:   # not run, or the run ended in an error before any turn
                continue
            folder = OUT / item / side
            folder.mkdir(parents=True, exist_ok=True)
            film = delivered(rec)
            info = {"spent": rec.get("spent"), "seconds": rec.get("seconds"), "film": None, "reply": (rec["turns"][-1].get("agent") or "")[:1200]}
            if film and film.exists():
                shutil.copy(film, folder / "film.mp4")
                m = probe(folder / "film.mp4")
                info["film"] = {"source": str(film.relative_to(V2)), "seconds": round(m["seconds"], 1), "width": m["width"], "height": m["height"],
                                "loudness_db": loudness_db(folder / "film.mp4")}
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(folder / "film.mp4"), "-vf", f"fps=1,scale=220:-2,tile=8x4",
                                "-frames:v", "1", str(folder / "sheet.jpg")], check=False)
                cuts = subprocess.run(["ffmpeg", "-i", str(folder / "film.mp4"), "-vf", "select='gt(scene,0.3)',showinfo", "-f", "null", "-"],
                                      capture_output=True, text=True).stderr
                info["film"]["cuts"] = [round(float(x.split("pts_time:")[1].split()[0]), 1) for x in cuts.splitlines() if "pts_time:" in x]
            (folder / "info.json").write_text(json.dumps(info, indent=2))
            summary[f"{item}/{side}"] = (info["spent"], info["seconds"], info["film"] and info["film"]["seconds"])
    for k, v in summary.items():
        print(k, v)


if __name__ == "__main__":
    main()

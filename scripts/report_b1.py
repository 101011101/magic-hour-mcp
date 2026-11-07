"""Build Benchmark/report-b1/: one self-contained page for the B1 test only (the 30 s perfume spot).

    python3 scripts/report_b1.py

Sides: the current MCP, v1 (with sound), and Replicate when that run exists (Benchmark/replicate/B1/ with film.mp4 or
clip-*.mp4, checks.json, side.json). Files are written over; nothing is deleted.
The user asked for this page to be public on 2026-11-05. The presenter picture is a stock photo of a real person.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import report_page as rp  # noqa: E402
from upgrade_page import BENCH, RESULTS, STYLE, e, tally  # noqa: E402

OUT = BENCH / "report-b1"


def picture(source: Path, name: str, caption: str) -> str:
    return f"<figure><img src=\"{rp.copy(source, name)}\"><figcaption>{e(caption)}</figcaption></figure>"


def main() -> None:
    rp.OUT = OUT
    OUT.mkdir(parents=True, exist_ok=True)
    old = rp.checks(RESULTS / "mcp-dense-1b" / "B1b.checks.json")
    v1 = [{"want": w, "got": got, "result": result} for w, (result, got) in zip(rp.B1_WANTS, rp.B1_V1)]
    sides = [
        {"name": "Current MCP", "gen": "minimax-h3 · text-to-video with 2 references · 480p · 30 s · 1 call", "time": 221, "cost": "720 credits", "checks": old,
         "figure": rp.video(BENCH / "B1/run2-01-create_video_from_text.mp4", BENCH / "B1/run2-01-create_video_from_text.mp4.poster.jpg", "b1-current",
                            "<b>Current MCP</b> · 221 s · 720 credits")},
        {"name": "v1", "gen": rp.B1_V1_GEN, "time": rp.B1_V1_TIME, "cost": f"{rp.B1_V1_CREDITS} credits", "checks": v1,
         "figure": rp.video(BENCH / "modified/B1/run2/film.mp4", BENCH / "modified/B1/run2/film.poster.jpg", "b1-v1",
                            f"<b>v1</b> · {rp.B1_V1_TIME} s · {rp.B1_V1_CREDITS} credits · voice-over, music, captions")},
    ]
    rep = BENCH / "replicate/B1"
    if (rep / "checks.json").exists():
        side = json.loads((rep / "side.json").read_text())
        files = sorted(rep.glob("film.mp4")) or sorted(rep.glob("clip-*.mp4"))
        caption = f"<b>{e(side['name'])}</b> · {side['time']} s · {e(side['cost'])}"
        if len(files) == 1:
            figure = rp.video(files[0], files[0].with_suffix(".poster.jpg"), "b1-replicate", caption)
        elif files:
            figure = ("<figure><div class=four>" + "".join(
                f"<video controls preload=metadata poster=\"{rp.copy(f.with_suffix('.poster.jpg'), f'b1-replicate-{i}.jpg')}\" "
                f"src=\"{rp.copy(f, f'b1-replicate-{i}.mp4')}\"></video>" for i, f in enumerate(files, start=1))
                + f"</div><figcaption>{caption} · {len(files)} files, not joined</figcaption></figure>")
        else:
            figure = f"<figure><div class=none>No video</div><figcaption>{caption}</figcaption></figure>"
        sides.append({"name": side["name"], "gen": side["gen"], "time": side["time"], "cost": side["cost"], "checks": rp.checks(rep / "checks.json"), "figure": figure})

    top = ("<table><tr><th>Side</th><th>Generation</th><th class=n>Time</th><th class=n>Cost</th><th>Checklist</th></tr>"
           + "".join(f"<tr><td class=nw>{e(s['name'])}</td><td>{s['gen']}</td><td class=n>{s['time']} s</td><td class=n>{e(s['cost'])}</td>"
                     f"<td class=nw>{tally(s['checks'])}</td></tr>" for s in sides) + "</table>")
    notes = ("Driver gpt-6.1-sol, medium effort, for all sides · Magic Hour: free-plan models at 480p on a Creator account, 24 credits for each second of video · "
             "time is the whole request · one run for each side, scored by eye from frames, cut detection, a transcript and audio measurement · "
             "v1 is a local build and is not deployed. v1's sound: one narration for the whole script (1 call), one music track, captions drawn by code. "
             "Earlier v1 runs: one declined by the assistant (0 credits), one silent (730 credits, before the sound tools)")
    text = json.loads((rp.ITEMS / "B1.json").read_text())["turns"][0]["text"]
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>B1 benchmark</title>' + STYLE +
            "<style>body{max-width:1200px}.vids{display:grid;gap:14px;margin:14px 0 18px;align-items:start;max-width:" + str(310 * len(sides)) + "px}"
            ".refs{display:flex;gap:10px;margin:10px 0 4px}.refs img{height:190px;border-radius:6px}figcaption{margin-top:6px}h2{margin-top:36px}"
            ".none{aspect-ratio:9/16;display:grid;place-items:center;border:1px dashed var(--line);border-radius:8px;color:var(--mut)}"
            ".four{display:grid;grid-template-columns:1fr 1fr;gap:4px}</style>"
            "<h1>B1 · Mockup Fragrance product spot</h1><p class=mut>5 November 2026 · 30 s · 9:16 · two reference pictures</p>"
            + top + f"<p class=mut>{e(notes)}</p><h2>Input</h2>" + f"<div class=pre>{e(text)}</div><div class=refs>"
            + picture(BENCH / "B1/in-bench-mockup-fragrance.png", "b1-in-bottle.png", "bottle picture")
            + picture(BENCH / "B1/in-bench-presenter.png", "b1-in-presenter.png", "presenter picture")
            + picture(BENCH / "modified/B1/run2/edited-reference.png", "b1-v1-edited.png", "v1 only: the picture the assistant made from the two (1 image edit)")
            + f"</div><h2>Output</h2><div class=vids style=\"grid-template-columns:repeat({len(sides)},1fr)\">" + "".join(s["figure"] for s in sides) + "</div>"
            + rp.table(rp.B1_WANTS, [(s["name"], s["checks"]) for s in sides]) + "</html>")
    (OUT / "index.html").write_text(page)
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(OUT / "index.html", f"· {size / 1e6:.1f} MB with media · {len(sides)} sides")


if __name__ == "__main__":
    main()

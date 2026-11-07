"""Build Benchmark/report-b2/: one self-contained page for the B2 test only (the 30 s fiction short).

    python3 scripts/report_b2.py

Sides: the current MCP, v1, Replicate on a free account, and Replicate on its paid model when that run exists
(Benchmark/replicate/B2-paid/ with film.mp4 or clips, checks.json, side.json). Files are written over; nothing is deleted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import report_page as rp  # noqa: E402
from upgrade_page import BENCH, RESULTS, STYLE, e, tally  # noqa: E402

OUT = BENCH / "report-b2"


def main() -> None:
    rp.OUT = OUT   # the copy helper of the full report writes into this folder
    OUT.mkdir(parents=True, exist_ok=True)
    old, v1 = rp.checks(RESULTS / "mcp-dense-2-B2" / "B2.checks.json"), rp.checks(BENCH / "modified/B2/run2/checks.json")
    free, free_side = rp.checks(BENCH / "replicate/B2/checks.json"), json.loads((BENCH / "replicate/B2/side.json").read_text())
    sides = [
        {"name": "Current MCP", "gen": "ltx-2.5 · text-to-video · 480p · 30 s · 1 call", "time": 151, "cost": "720 credits", "checks": old,
         "figure": rp.video(BENCH / "B2/run1-01-create_video_from_text.mp4", BENCH / "B2/run1-01-create_video_from_text.mp4.poster.jpg", "b2-current",
                            "<b>Current MCP</b> · 151 s · 720 credits")},
        {"name": "v1", "gen": "qwen-image-2.1 · title card still<br>ltx-2.5 · image-to-video · 2 s (card)<br>ltx-2.5 · text-to-video · 13 s<br>"
                              "ltx-2.5 · image-to-video from the last frame · 13 s<br>join · 4 pieces", "time": 181, "cost": "672 credits", "checks": v1,
         "figure": rp.video(BENCH / "modified/B2/run2/film.mp4", BENCH / "modified/B2/run2/film.poster.jpg", "b2-v1", "<b>v1</b> · 181 s · 672 credits")},
        {"name": "Replicate, free", "gen": free_side["gen"], "time": free_side["time"], "cost": "free", "checks": free,
         "figure": "<figure><div class=four>" + "".join(
             f"<video controls preload=metadata poster=\"{rp.copy(BENCH / f'replicate/B2/clip-{n}.poster.jpg', f'b2-replicate-{n}.jpg')}\" "
             f"src=\"{rp.copy(BENCH / f'replicate/B2/clip-{n}.mp4', f'b2-replicate-{n}.mp4')}\"></video>" for n in (1, 2, 3, 4))
             + "</div><figcaption><b>Replicate, free</b> · 293 s · free · 4 clips, not joined</figcaption></figure>"},
    ]
    paid = BENCH / "replicate/B2-paid"
    if (paid / "checks.json").exists():
        side = json.loads((paid / "side.json").read_text())
        files = sorted(paid.glob("film.mp4")) or sorted(paid.glob("clip-*.mp4"))
        if len(files) == 1:
            figure = rp.video(files[0], files[0].with_suffix(".poster.jpg"), "b2-replicate-paid", f"<b>Replicate, paid</b> · {side['time']} s · {e(side['cost'])}")
        elif files:
            figure = ("<figure><div class=four>" + "".join(
                f"<video controls preload=metadata poster=\"{rp.copy(f.with_suffix('.poster.jpg'), f'b2-replicate-paid-{i}.jpg')}\" "
                f"src=\"{rp.copy(f, f'b2-replicate-paid-{i}.mp4')}\"></video>" for i, f in enumerate(files, start=1))
                + f"</div><figcaption><b>Replicate, paid</b> · {side['time']} s · {e(side['cost'])} · {len(files)} files</figcaption></figure>")
        else:
            figure = f"<figure><div class=none>No video</div><figcaption><b>Replicate, paid</b> · {side['time']} s · {e(side['cost'])}</figcaption></figure>"
        sides.append({"name": "Replicate, paid", "gen": side["gen"], "time": side["time"], "cost": side["cost"], "checks": rp.checks(paid / "checks.json"), "figure": figure})

    top = ("<table><tr><th>Side</th><th>Generation</th><th class=n>Time</th><th class=n>Cost</th><th>Checklist</th></tr>"
           + "".join(f"<tr><td class=nw>{e(s['name'])}</td><td>{s['gen']}</td><td class=n>{s['time']} s</td><td class=n>{e(s['cost'])}</td>"
                     f"<td class=nw>{tally(s['checks'])}</td></tr>" for s in sides) + "</table>")
    notes = ("Driver gpt-6.1-sol, medium effort, for all sides · Magic Hour: free-plan models at 480p on a Creator account, 24 credits for each second of video · "
             "Replicate, free: its plugin on a free account, where one video model runs (minimax/video-01, 6 s silent clips)"
             + (" · Replicate, paid: lightricks/ltx-2.5-fast at 720p, the model nearest to ours in price" if len(sides) > 3 else "")
             + " · time is the whole request · one run for each side, scored by eye from frames, cut detection and audio measurement · "
             "v1 is a local build and is not deployed; this is its second B2 run (the first scored 3 yes · 2 partly · 2 no before two prompt faults were corrected)")
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>B2 benchmark</title>' + STYLE +
            "<style>body{max-width:1200px}.vids{display:grid;gap:14px;margin:18px 0;align-items:start}figcaption{margin-top:6px}h2{margin-top:40px}"
            ".none{aspect-ratio:16/9;display:grid;place-items:center;border:1px dashed var(--line);border-radius:8px;color:var(--mut)}"
            ".four{display:grid;grid-template-columns:1fr 1fr;gap:4px}@media(max-width:800px){.vids{grid-template-columns:1fr 1fr!important}}</style>"
            "<h1>B2 · Walk Anyway, a 30 s fiction short</h1><p class=mut>5 November 2026 · 16:9 · text only, no reference pictures</p>"
            + top + f"<p class=mut>{e(notes)}</p><h2>Input</h2>" + f"<div class=pre>{e(json.loads((rp.ITEMS / 'B2.json').read_text())['turns'][0]['text'])}</div>"
            + f"<h2>Output</h2><div class=vids style=\"grid-template-columns:repeat({len(sides)},1fr)\">" + "".join(s["figure"] for s in sides) + "</div>"
            + rp.table([c["want"] for c in v1], [(s["name"], s["checks"]) for s in sides]) + "</html>")
    (OUT / "index.html").write_text(page)
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(OUT / "index.html", f"· {size / 1e6:.1f} MB with media · {len(sides)} sides")


if __name__ == "__main__":
    main()

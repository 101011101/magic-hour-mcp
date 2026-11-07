"""Build Benchmark/report-v1/: one self-contained page, v1 against the current MCP, with its video files copied in.

    python3 scripts/report_page.py

The B1 films are not copied: their presenter reference is a stock photo of a real person (kept off shared pages).
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from upgrade_page import BENCH, CLASS, RESULTS, STYLE, conversations, e, tally  # noqa: E402

OUT = BENCH / "report-v1"
ITEMS = RESULTS.parent.parent / "mcp" / "dense" / "items"
SEASON_ITEMS = ITEMS.parent / "items-seasons"
SEASONS = BENCH / "seasons"

B1_WANTS = ["One file, 30 s, 9:16", "Four shots in order", "Same bottle and label, no box", "Same presenter in every shot",
            "She holds the bottle, then sprays her wrist", "End card for the last 4 s, exact text on #3B1F6B",
            "Voice-over with the exact words", "Captions match the voice-over", "Soft music under the voice", "Clean cuts, steady audio"]
B1_V1 = [("yes", "One file, 480×858, 30.9 s"), ("yes", "Each shot once, in order"),
         ("partly", "Same shape and grey cap in all shots, no box; the letters on the bottle are wrong when it is in her hands"),
         ("yes", "The same presenter"), ("yes", "Both shown"),
         ("partly", "Text exact; 4.0 s; colour #36186E; the card zooms in and the text is cut at the edges in the last second"),
         ("yes", "Exact, said once, one voice for the whole film"), ("yes", "The script, drawn on the picture when each sentence is said"),
         ("yes", "One soft track from start to end"), ("yes", "No black frames; level steady")]
B1_V1_GEN = ("qwen-image-2.1 · image edit (presenter with the bottle)<br>minimax-h3 · text-to-video with 1 reference · 7 s<br>"
             "minimax-h3 · text-to-video with 1 reference · 12 s<br>minimax-h3 · text-to-video with 1 reference · 7 s<br>"
             "qwen-image-2.1 still, then ltx-2.5 · image-to-video · 4 s (card)<br>ltx-2.5 · text-to-video · 19 s (narration, sound only)<br>"
             "music · 32 s<br>join · 4 pieces, narration placed, music mixed, captions drawn")
B1_V1_TIME, B1_V1_CREDITS = 353, 1218


def checks(file: Path) -> list[dict]:
    return json.loads(file.read_text())["checks"]


def copy(source: Path, name: str) -> str:
    (OUT / "media").mkdir(parents=True, exist_ok=True)
    shutil.copy(source, OUT / "media" / name)
    return f"media/{name}"


def video(source: Path, poster: Path, name: str, caption: str) -> str:
    return (f"<figure><video controls preload=metadata poster=\"{copy(poster, name + '.jpg')}\" src=\"{copy(source, name + '.mp4')}\"></video>"
            f"<figcaption>{caption}</figcaption></figure>")


def table(wants: list[str], sides: list[tuple[str, list[dict]]]) -> str:
    head = "".join(f"<th>{e(name)}</th>" for name, _ in sides)
    body = ""
    for i, want in enumerate(wants):
        cells = "".join(f"<td><span class={CLASS[c[i]['result']]}>{c[i]['result']}</span><br><span class=mut>{e(c[i]['got'])}</span></td>" for _, c in sides)
        body += f"<tr><td>{e(want)}</td>{cells}</tr>"
    return f"<table><tr><th>Wanted</th>{head}</tr>{body}</table>"


def season_sections() -> tuple[list[tuple], str]:
    """The season and door requests: one section for each, the current MCP beside v1, and the rows for the top table."""
    rows, html = [], ""
    for file in sorted(SEASON_ITEMS.glob("*.json")):
        item = json.loads(file.read_text())
        sides = []
        for side in ("old", "v1", "replicate"):
            folder = SEASONS / item["id"] / side
            if (folder / "checks.json").exists():
                sides.append({**json.loads((folder / "side.json").read_text()), "checks": checks(folder / "checks.json"), "folder": folder, "key": side})
        if len(sides) < 2:
            continue
        for i, s in enumerate(sides):
            rows.append((f"{item['id']} · {item['case_name']}" if i == 0 else "", s["name"], s["gen"], s["time"], str(s["credits"]), tally(s["checks"])))
        videos = "".join(
            video(s["folder"] / "film.mp4", s["folder"] / "film.poster.jpg", f"{item['id'].lower()}-{s['key']}", f"<b>{e(s['name'])}</b> · {s['time']} s · {cost(s['credits'])}")
            if s.get("film", True) else f"<figure><div class=none>No video</div><figcaption><b>{e(s['name'])}</b> · {s['time']} s · {e(s['gen'])}</figcaption></figure>"
            for s in sides)
        tall = item["spec"]["aspect"] == "9:16"
        html += (f"<h2>{e(item['id'])} · {e(item['title'])}</h2>" + brief(item["id"], SEASON_ITEMS)
                 + f"<div class=\"vids{' tall' if tall else ''}\" style=\"grid-template-columns:repeat({len(sides)},1fr)\">{videos}</div>"
                 + table(item["must_haves"], [(s["name"], s["checks"]) for s in sides]))
    return rows, html


def cost(credits) -> str:
    return f"{credits} credits" if str(credits).isdigit() else str(credits)


def brief(item: str, folder: Path = ITEMS) -> str:
    text = json.loads((folder / f"{item}.json").read_text())["turns"][0]["text"]
    return f"<details><summary>The request</summary><div class=pre>{e(text)}</div></details>"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)   # files are written over; nothing is deleted
    b2_old, b2_v1 = checks(RESULTS / "mcp-dense-2-B2" / "B2.checks.json"), checks(BENCH / "modified/B2/run2/checks.json")
    b1_old = checks(RESULTS / "mcp-dense-1b" / "B1b.checks.json")
    b1_v1 = [{"want": w, "got": got, "result": result} for w, (result, got) in zip(B1_WANTS, B1_V1)]
    b2_rep, b2_rep_side = checks(BENCH / "replicate/B2/checks.json"), json.loads((BENCH / "replicate/B2/side.json").read_text())
    season_rows, season_html = season_sections()

    rows = season_rows + [
        ("B2 · fiction short, 30 s, 16:9, text only", "Current MCP", "ltx-2.5 · text-to-video · 480p · 30 s · 1 call", 151, "720", tally(b2_old)),
        ("", "v1", "qwen-image-2.1 · title card still<br>ltx-2.5 · image-to-video · 2 s (card)<br>ltx-2.5 · text-to-video · 13 s<br>"
                   "ltx-2.5 · image-to-video from the last frame · 13 s<br>join · 4 pieces", 181, "672", tally(b2_v1)),
        ("", "Replicate", b2_rep_side["gen"], b2_rep_side["time"], "free", tally(b2_rep)),
        ("B1 · product spot, 30 s, 9:16, two reference pictures", "Current MCP", "minimax-h3 · text-to-video · 480p · 30 s · 1 call", 221, "720", tally(b1_old)),
        ("", "v1", B1_V1_GEN, B1_V1_TIME, str(B1_V1_CREDITS), tally(b1_v1)),
    ]
    top = ("<table><tr><th>Item</th><th>Side</th><th>Generation</th><th class=n>Time</th><th class=n>Cost</th><th>Checklist</th></tr>"
           + "".join(f"<tr><td>{e(a)}</td><td class=nw>{e(b)}</td><td>{c}</td><td class=n>{d} s</td><td class=n>{e(f)}</td><td class=nw>{g}</td></tr>"
                     for a, b, c, d, f, g in rows) + "</table>")
    notes = ("Driver gpt-6.1-sol, medium effort, for all sides · Magic Hour: free-plan models at 480p on a Creator account; cost in credits (24 for each second of video) · "
             "Replicate: its plugin on a free account, where one video model runs (minimax/video-01, 6 s silent clips) · time is the whole request · "
             "one run for each item, scored by eye from frames, cut detection and audio measurement · v1 is a local build and is not deployed; its join step needs ffmpeg on the server · "
             "Replicate was not run on S1 and B1: they need the reference pictures at a public address")

    b2 = ("<h2>B2 · Walk Anyway</h2>" + brief("B2") + "<div class=vids style=\"grid-template-columns:1fr 1fr 1fr\">"
          + video(BENCH / "B2/run1-01-create_video_from_text.mp4", BENCH / "B2/run1-01-create_video_from_text.mp4.poster.jpg", "b2-current", "<b>Current MCP</b> · 151 s · 720 credits")
          + video(BENCH / "modified/B2/run2/film.mp4", BENCH / "modified/B2/run2/film.poster.jpg", "b2-v1", "<b>v1</b> · 181 s · 672 credits")
          + "<figure><div class=four>" + "".join(
              f"<video controls preload=metadata poster=\"{copy(BENCH / f'replicate/B2/clip-{n}.poster.jpg', f'b2-replicate-{n}.jpg')}\" "
              f"src=\"{copy(BENCH / f'replicate/B2/clip-{n}.mp4', f'b2-replicate-{n}.mp4')}\"></video>" for n in (1, 2, 3, 4))
          + "</div><figcaption><b>Replicate</b> · 293 s · free · 4 clips, not joined</figcaption></figure>"
          + "</div>" + table([c["want"] for c in b2_v1], [("Current MCP", b2_old), ("v1", b2_v1), ("Replicate", b2_rep)])
          + "<p class=mut>v1 made this film on its second run. The first run scored 3 yes · 2 partly · 2 no (a second woman in the frame, title text over the scene); "
            "two prompt faults were corrected between the runs.</p>")
    b1 = ("<h2>B1 · Mockup Fragrance</h2>" + brief("B1") + table(B1_WANTS, [("Current MCP", b1_old), ("v1", b1_v1)])
          + "<p class=mut>Videos are not shown here: the presenter reference is a stock photo of a real person. "
            "v1's sound: one narration for the whole script (1 call), one music track, captions drawn by code. "
            "This is v1's third B1 run: the first was declined by the assistant (0 credits), the second was silent (730 credits, before the sound tools).</p>")
    conv = "<h2>Vague requests · 13 briefs</h2>" + conversations("mcp-intent-mod", "mcp-intent-mod").replace("With plan_request", "v1")
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>MCP v1 benchmark</title>' + STYLE +
            "<style>body{max-width:1100px}.vids{display:grid;gap:14px;margin:14px 0 18px;align-items:start}.vids.tall{max-width:560px}"
            "figcaption{margin-top:6px}.conv td{width:33%}.conv .pre{margin:0 0 6px}h2{margin-top:44px}"
            ".none{aspect-ratio:16/9;display:grid;place-items:center;border:1px dashed var(--line);border-radius:8px;color:var(--mut)}"
            ".four{display:grid;grid-template-columns:1fr 1fr;gap:4px}</style>"
            "<h1>Magic Hour MCP: v1 against the current MCP and Replicate</h1><p class=mut>5 November 2026</p>" + top + f"<p class=mut>{e(notes)}</p>" + season_html + b2 + b1 + conv + "</html>")
    (OUT / "index.html").write_text(page)
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(OUT / "index.html", f"· {size / 1e6:.1f} MB with media")


if __name__ == "__main__":
    main()

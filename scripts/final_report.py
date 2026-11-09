"""Build Benchmark/report-final/: the latest MCP build ("New · agent groups, MCP asks", 7 November) against the old MCP.

    python3 scripts/final_report.py

One self-contained folder for Vercel (media copied in). Per item: the request as sent, the attached files, time, cost, the films,
and the wanted / got checklist. Reads Benchmark/gates/scores.json, Benchmark/gates/<item>/<side>/{info.json,film.mp4}
and the requests in the agent repo's items-gates folder.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from upgrade_page import BENCH, CLASS, STYLE, e  # noqa: E402

AGENT = ROOT.parent / "magic-agent-video-generator" / "V2" / "bench"
ITEMS_DIR = AGENT / "mcp" / "dense" / "items-gates"
FIXTURES = AGENT / "v1" / "fixtures"
OUT = BENCH / "report-final"
ORDER = ["B1", "B2", "A2"]   # A4 left out of this report (user, 2026-11-07)
SIDES = [("old", "Old MCP"), ("new", "New MCP")]
DOLLARS_PER_CREDIT = 19 / 12000          # $19 for 12,000 credits


def dollars(credits: int) -> str:
    return f"${credits * DOLLARS_PER_CREDIT:.2f}"


def tally(results: list[str]) -> str:
    return " · ".join(f"{results.count(k)} {k}" for k in ("yes", "partly", "no"))


def copy(source: Path, name: str) -> str:
    (OUT / "media").mkdir(parents=True, exist_ok=True)
    shutil.copy(source, OUT / "media" / name)
    return f"media/{name}"


def poster(video: Path, name: str) -> str:
    out = OUT / "media" / name
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", str(video), "-frames:v", "1", "-q:v", "3", str(out)], check=True)
    return f"media/{name}"


def main() -> None:
    if OUT.exists():
        for child in OUT.iterdir():          # keep .vercel (the project link)
            if child.name != ".vercel":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    scores = json.loads((BENCH / "gates" / "scores.json").read_text())
    totals = {s: {"time": 0, "credits": 0, "r": []} for s, _ in SIDES}
    rows, sections = "", ""
    for item in ORDER:
        spec = json.loads((ITEMS_DIR / f"{item}.json").read_text())
        turn, wants, score = spec["turns"][0], spec["must_haves"], scores["items"][item]
        info = {s: json.loads((BENCH / "gates" / item / s / "info.json").read_text()) for s, _ in SIDES}
        for s, _ in SIDES:
            totals[s]["time"] += info[s]["seconds"]
            totals[s]["credits"] += info[s]["spent"]
            totals[s]["r"] += score[s]["r"]
        old, new = info["old"], info["new"]
        rows += (f'<tr><td><a href="#{item}">{item}</a><br><span class=mut>{e(spec["case_name"])}</span></td>'
                 + "".join(f"<td class=n>{info[s]['seconds']} s</td><td class=n>{info[s]['spent']}<br><span class=mut>{dollars(info[s]['spent'])}</span></td>"
                           f"<td class=nw><b>{tally(score[s]['r'])}</b><br><span class=mut>{e(score[s]['v'])}</span></td>" for s, _ in SIDES) + "</tr>")
        pics = "".join(
            f"<figure>{'<video controls preload=metadata src=' + chr(34) + copy(FIXTURES / m, item + '-in-' + m) + chr(34) + '></video>' if m.endswith('.mp4') else '<img src=' + chr(34) + copy(FIXTURES / m, item + '-in-' + m) + chr(34) + ' alt=' + chr(34) + e(m) + chr(34) + '>'}"
            f"<figcaption>{e(m)}</figcaption></figure>" for m in turn["materials"])
        brief = f'<div class=in><div class="pre brief">{e(turn["text"])}</div><div class=pics>{pics}</div></div>' if pics else f'<div class="pre brief">{e(turn["text"])}</div>'
        films = "".join(
            f'<figure><video controls preload=metadata poster="{poster(BENCH / "gates" / item / s / "film.mp4", f"{item}-{s}.jpg")}" '
            f'src="{copy(BENCH / "gates" / item / s / "film.mp4", f"{item}-{s}.mp4")}"></video>'
            f"<figcaption><b>{name}</b> · {info[s]['seconds']} s · {info[s]['spent']} credits ({dollars(info[s]['spent'])}) · {tally(score[s]['r'])}</figcaption></figure>"
            for s, name in SIDES)
        lines = "".join(
            f"<tr><td>{e(w)}</td>" + "".join(f"<td><span class={CLASS[score[s]['r'][i]]}>{score[s]['r'][i]}</span><br><span class=mut>{e(score[s]['g'][i])}</span></td>" for s, _ in SIDES) + "</tr>"
            for i, w in enumerate(wants))
        tall = spec["spec"]["aspect"] == "9:16"
        sections += (f'<h2 id="{item}">{item} · {e(spec["case_name"])}</h2><p class=mut>The request, as sent{", and the attached files" if pics else ""}</p>{brief}'
                     f'<div class="vids{" tall" if tall else ""}">{films}</div>'
                     f"<table><tr><th>Wanted</th><th>Old MCP</th><th>New MCP</th></tr>{lines}</table>")
    total_row = (f"<tr class=tot><td><b>All {len(ORDER)}</b></td>" + "".join(
        f"<td class=n><b>{totals[s]['time']} s</b></td><td class=n><b>{totals[s]['credits']}</b><br><span class=mut>{dollars(totals[s]['credits'])}</span></td>"
        f"<td class=nw><b>{tally(totals[s]['r'])}</b><br><span class=mut>{len(totals[s]['r'])} lines</span></td>" for s, _ in SIDES) + "</tr>")
    summary = ("<table><tr><th rowspan=2>Request</th><th colspan=3>Old MCP</th><th colspan=3>New MCP</th></tr>"
               "<tr><th class=n>Time</th><th class=n>Credits</th><th>Checklist</th><th class=n>Time</th><th class=n>Credits</th><th>Checklist</th></tr>"
               + rows + total_row + "</table>")
    note = ("Same driver for both sides: gpt-6.1-sol, medium effort, as the chat assistant · free-plan models at 480p · "
            "Time: the whole request, from the message to the reply · Credits: charged by the account; dollars at $19 for 12,000 credits · "
            "Checklist: one line for each thing the request asked for, scored by eye from frames, cut detection, loudness and a transcript · one run for each side")
    sides = ("<ul><li><b>Old MCP</b>: the hosted Magic Hour MCP (mcp.magichour.ai), runs of 4 and 5 November.</li>"
             "<li><b>New MCP</b>: a local build of the upgrade, 7 November. The agent writes the story and sets the clips; the MCP asks at known risks "
             "(words over a scene, a spoken line, colour codes) with a recommendation; cards are drawn by code; one narration, one music track and captions "
             "are laid over the joined film. Not deployed.</li></ul>")
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>Magic Hour MCP: old and new</title>' + STYLE +
            "<style>body{max-width:1100px}.vids{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:18px 0}.vids.tall{max-width:620px}"
            "figcaption{margin-top:6px}h2{margin-top:48px}.in{margin-bottom:6px}.pics img,.pics video{width:auto}ul{margin:4px 0 16px;padding-left:22px;font-size:14px}"
            "th[colspan]{text-align:center}tr.tot td{border-top:2px solid var(--line)}"
            "@media(max-width:720px){.vids,.vids.tall{grid-template-columns:1fr}}</style>"
            f"<h1>Magic Hour MCP: old and new</h1><p class=mut>7 November 2026 · {len(ORDER)} requests · one run for each side</p>"
            + sides + summary + f"<p class=mut>{e(note)}</p>" + sections + "</html>")
    (OUT / "index.html").write_text(page)
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(OUT / "index.html", f"· {size / 1e6:.1f} MB with media")


if __name__ == "__main__":
    main()

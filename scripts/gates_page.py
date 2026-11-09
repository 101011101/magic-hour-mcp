"""Build Benchmark/gates.html: old MCP, v1 (strict pipeline) and the gated MCP on the same seven requests, with pick buttons.

    python3 scripts/gates_page.py

Reads Benchmark/gates/scores.json (scored by eye), Benchmark/gates/<item>/<side>/info.json and film.mp4 (from
scripts/gates_films.py), and the requests in the agent repo's items-gates folder. Films are linked in place.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from approach_page import SCRIPT  # noqa: E402
from upgrade_page import BENCH, CLASS, STYLE, e  # noqa: E402

ITEMS_DIR = ROOT.parent / "magic-agent-video-generator" / "V2" / "bench" / "mcp" / "dense" / "items-gates"
ORDER = ["B1", "B2", "A2", "A4", "C10", "A3", "J55a"]


def tally(results: list[str]) -> str:
    return " · ".join(f"{results.count(k)} {k}" for k in ("yes", "partly", "no"))


def film_of(item: str, side: str) -> str | None:
    folder = BENCH / "gates" / item / side
    for name in ("delivered.mp4", "film.mp4"):
        if (folder / name).exists():
            return f"gates/{item}/{side}/{name}"
    return None


def main() -> None:
    scores = json.loads((BENCH / "gates" / "scores.json").read_text())
    sides = scores["sides"]
    script = SCRIPT.replace('const KEY = "approach-picks", NAMES = {words: "Words", continue: "Continue", "split-C6": "Split, bottle (C6)", '
                            '"split-C7": "Split, two people (C7)", "split-C10": "Split, perfume + 2 people (C10)"};',
                            'const KEY = "gates-picks", NAMES = {' + ", ".join(f'"{i}": "{i}"' for i in ORDER) + "};")
    totals = {s: [] for s in sides}
    sections = ""
    for item in ORDER:
        spec = json.loads((ITEMS_DIR / f"{item}.json").read_text())
        wants, row = spec["must_haves"], scores["items"][item]
        info = {s: json.loads((BENCH / "gates" / item / s / "info.json").read_text()) for s in sides if (BENCH / "gates" / item / s / "info.json").exists()}
        head = "<table><tr><th>Side</th><th class=n>Time</th><th class=n>Credits</th><th>Checklist</th><th>Verdict</th></tr>"
        here = [s for s in sides if s in row]
        for s in here:
            totals[s] += row[s]["r"]
            head += (f"<tr><td class=nw>{e(sides[s]['name'])}</td><td class=n>{info.get(s, {}).get('seconds', '')} s</td>"
                     f"<td class=n>{info.get(s, {}).get('spent', '')}</td><td class=nw>{tally(row[s]['r'])}</td><td>{e(row[s]['v'])}</td></tr>")
        head += "</table>"
        films = "".join(
            f'<figure data-section="{item}" data-id="{e(sides[s]["name"])}"><video controls preload=metadata src="{e(film_of(item, s))}"></video>'
            f'<figcaption><b>{e(sides[s]["name"])}</b><br><span class=mut>{e(row[s]["v"])}</span></figcaption>'
            f'<button type=button class=pick>Pick this</button></figure>' for s in sides if s in row and film_of(item, s))
        body = "".join(f"<tr><td>{e(w)}</td>" + "".join(
            f"<td><span class={CLASS[row[s]['r'][i]]}>{row[s]['r'][i]}</span><br><span class=mut>{e(row[s]['g'][i])}</span></td>" for s in sides if s in row)
            + "</tr>" for i, w in enumerate(wants))
        table = "<table><tr><th>Wanted</th>" + "".join(f"<th>{e(sides[s]['name'])}</th>" for s in sides if s in row) + f"</tr>{body}</table>"
        tall = spec["spec"].get("aspect") == "9:16"
        sections += (f'<h2 id="{item}">{e(item)} · {e(spec["case_name"])}</h2><details><summary>The request</summary>'
                     f'<div class=pre>{e(spec["turns"][0]["text"])}</div></details>{head}'
                     f'<div class="vids{" tall" if tall else ""}" style="grid-template-columns:repeat({len([x for x in sides if x in row])},1fr)">{films}</div>{table}')
    summary = ("<table><tr><th>Side</th><th>How</th><th>All 7 requests</th></tr>" + "".join(
        f"<tr><td class=nw><b>{e(v['name'])}</b></td><td>{e(v['how'])}</td><td class=nw>{tally(totals[s])}<br><span class=mut>{len(totals[s])} lines</span></td></tr>" for s, v in sides.items()) + "</table>")
    notes = "".join(f"<li>{e(n)}</li>" for n in scores["notes"])
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>Gates test</title>' + STYLE +
            "<style>body{max-width:1240px}.vids{display:grid;gap:14px;margin:18px 0;align-items:start}.vids.tall{max-width:900px}"
            "figcaption{margin-top:6px}h2{margin-top:44px}ul{margin:8px 0 16px;padding-left:22px;font-size:14px}"
            "@media(max-width:720px){.vids{grid-template-columns:1fr 1fr!important}}"
            "figure{border:2px solid transparent;border-radius:10px;padding:6px;margin:0}figure.picked{border-color:var(--ok)}"
            ".pick,#picks button{margin-top:8px;padding:8px 14px;border-radius:8px;border:1px solid var(--mut);background:Canvas;color:CanvasText;"
            "font:600 14px/1.2 -apple-system,system-ui,sans-serif;cursor:pointer}.pick{width:100%}"
            "figure.picked .pick{background:CanvasText;color:Canvas;border-color:CanvasText}"
            "#picks{position:sticky;top:0;z-index:5;background:Canvas;color:CanvasText;border-bottom:1px solid var(--line);padding:10px 0;margin-bottom:10px;"
            "display:flex;gap:12px;align-items:center;flex-wrap:wrap;font-size:14px}#picks button{margin-top:0}</style>"
            "<h1>Gates test: old MCP, v1, gates</h1><p class=mut>7 November 2026 · driver gpt-6.1-sol, medium · free-plan models at 480p · "
            "one run for each side · scored by eye, loudness and a transcript</p>"
            "<div id=picks><span id=summary>Your picks: none yet.</span><button type=button id=copy>Copy picks</button></div>"
            + summary + f"<ul>{notes}</ul>" + sections + script + "</html>")
    (BENCH / "gates.html").write_text(page)
    print(BENCH / "gates.html", {s: tally(v) for s, v in totals.items()})


if __name__ == "__main__":
    main()

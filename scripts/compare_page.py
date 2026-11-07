"""Build Benchmark/report.html: the old MCP, v1 (the modified MCP) and Replicate on the same items.

    python3 scripts/compare_page.py

For each item: the brief and the attached files, then time, cost and the wanted / got checklist for each side.
Reads the run records and checklists in the agent repo, the films in Benchmark/<item>/ and Benchmark/modified/<item>/<run>/,
and the two lists in Benchmark/report-notes.json. Videos are linked, not copied: the page stays on this machine
(B1 has a stock photo of a real person). scripts/report_page.py builds another page, Benchmark/report-v1/.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from upgrade_page import BENCH, CLASS, RESULTS, STYLE, conversations  # noqa: E402

ITEMS_DIR = ROOT.parent / "magic-agent-video-generator" / "V2" / "bench" / "mcp" / "dense" / "items"
e = html.escape
DOLLARS_PER_CREDIT = 19 / 12000          # $19 for 12,000 credits
REPLICATE_PER_SECOND = 0.09              # estimate, not confirmed: the plugin shows no price and no balance

# item: the old MCP's record folder and film, v1's run folder under Benchmark/modified/<item>/, Replicate's records and films.
ITEMS = [
    {"id": "A1", "old": ("mcp-dense-2-A1", "A1", "A1/run1-02-create_video_from_image.mp4"), "v1": "run1",
     "replicate": [{"name": "Replicate", "sub": "paid, matched model", "dir": "comp-c4-replicate", "video": "A1/run3-01-replicate.mp4", "row": "Replicate, paid", "generated": 16}]},
    {"id": "A2", "old": ("mcp-dense-2-A2", "A2", "A2/run1-01-create_video_from_text.mp4"), "v1": "run1",
     "replicate": [{"name": "Replicate", "sub": "paid, matched model", "dir": "comp-c2-replicate", "video": "A2/run3-01-replicate.mp4", "row": "Replicate, paid", "generated": 12},
                   {"name": "Replicate, free model", "sub": "minimax/video-01", "dir": "comp-c1-replicate", "video": "A2/run4-01-replicate.mp4", "row": "Replicate", "generated": 0}]},
    {"id": "A3", "old": ("mcp-dense-2-A3", "A3", "A3/run1-01-create_video_from_text.mp4"), "v1": "run1",
     "replicate": [{"name": "Replicate", "sub": "paid, matched model", "dir": "comp-c3-replicate", "video": "A3/run3-01-replicate.mp4", "row": "Replicate, paid", "generated": 6}]},
    {"id": "A4", "old": ("mcp-dense-2-A4", "A4", "A4/run1-01-create_video_from_text.mp4"), "v1": "run1",
     "replicate": [{"name": "Replicate", "sub": "paid, matched model", "dir": "comp-c4-replicate", "video": "A4/run3-01-replicate.mp4", "row": "Replicate, paid", "generated": 14}]},
    {"id": "B1", "old": ("mcp-dense-1b", "B1b", "B1/run2-01-create_video_from_text.mp4"), "v1": "run1", "replicate": [],
     "no_replicate": "Not run: the brief has a stock photo of a real person"},
    {"id": "B2", "old": ("mcp-dense-2-B2", "B2", "B2/run1-01-create_video_from_text.mp4"), "v1": "run2",
     "replicate": [{"name": "Replicate", "sub": "paid, matched model", "dir": "comp-c5-replicate", "video": "B2/run3-02-replicate.mp4", "row": "Replicate, paid", "generated": 20}]},
]


def load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def tally(checks: list[dict] | None) -> str:
    if not checks:
        return ""
    n = {k: sum(1 for c in checks if c and c["result"] == k) for k in ("yes", "partly", "no")}
    return f"{n['yes']} yes · {n['partly']} partly · {n['no']} no"


def credits(n: int) -> str:
    return f"{n} credits (about ${n * DOLLARS_PER_CREDIT:.2f})"


def sides_of(item: dict) -> list[dict]:
    """One dict for each side: name, sub, video, poster, time, cost, gen, checks, flag."""
    out = []
    summary = load(BENCH / item["id"] / "summary.json") or {"rows": []}
    row = lambda service: next((r for r in summary["rows"] if r["service"] == service), None)
    folder, record_id, video = item["old"]
    record, r = load(RESULTS / folder / f"{record_id}.json"), row("Magic Hour")
    out.append({"name": "Old MCP", "sub": "hosted, 4 November", "video": video, "poster": video + ".poster.jpg", "time": r["seconds"],
                "cost": credits(record["spent"]), "gen": "<br>".join(e(g) for g in r["generation"]),
                "checks": load(RESULTS / folder / f"{record_id}.checks.json")["checks"], "flag": "after a nudge" if r.get("nudged") else ""})
    run = BENCH / "modified" / item["id"] / item["v1"]
    side, checks = load(run / "side.json"), load(run / "checks-report.json") or load(run / "checks.json")   # checks-report.json: all of the old MCP's lines
    if side and checks:
        rel = run.relative_to(BENCH)
        out.append({"name": "V1", "sub": side.get("sub", ""), "video": f"{rel}/film.mp4" if (run / "film.mp4").exists() else None, "poster": f"{rel}/film.poster.jpg",
                    "time": side["time"], "cost": credits(side["credits"]), "gen": side["gen"], "checks": checks["checks"], "flag": side.get("flag", "")})
    else:
        out.append({"name": "V1", "sub": "", "video": None, "time": None, "cost": "", "gen": "", "checks": None, "flag": "Not run"})
    for rep in item["replicate"]:
        r, checks = row(rep["row"]), load(RESULTS / rep["dir"] / f"{item['id']}.checks.json")
        cost = f"about ${rep['generated'] * REPLICATE_PER_SECOND:.2f} (estimate)" if rep["generated"] else "0 (free model)"
        out.append({"name": rep["name"], "sub": rep["sub"], "video": rep["video"], "poster": rep["video"] + ".poster.jpg", "time": r["seconds"], "cost": cost,
                    "gen": "<br>".join(e(g) for g in r["generation"]), "checks": checks["checks"],
                    "flag": "Parts only: no finished file" if checks.get("outcome") == "parts" else ("after a nudge" if r.get("nudged") else "")})
    if not item["replicate"]:
        out.append({"name": "Replicate", "sub": "", "video": None, "time": None, "cost": "", "gen": "", "checks": None, "flag": item["no_replicate"]})
    return out


def cell(side: dict) -> str:
    if side["checks"] is None:
        return f"<td class=mut>{e(side['flag'])}</td>"
    flag = f"<br><span class=mut>{e(side['flag'])}</span>" if side["flag"] else ""
    return f"<td>{side['time']} s · {e(side['cost'])}<br><b>{tally(side['checks'])}</b>{flag}</td>"


def media(name: str) -> str:
    if name.endswith(".mp4"):
        return f'<video controls preload=metadata src="{e(name)}"></video>'
    return f'<img src="{e(name)}" alt="{e(name)}">'


def section(item: dict, sides: list[dict]) -> str:
    spec = json.loads((ITEMS_DIR / f"{item['id']}.json").read_text())
    turn = spec["turns"][0]
    pics = "".join(f"<figure>{media(item['id'] + '/in-' + m)}<figcaption>{e(m)}</figcaption></figure>" for m in turn["materials"])
    inputs = f'<div class=in><div class="pre brief">{e(turn["text"])}</div><div class=pics>{pics}</div></div>' if pics else f'<div class="pre brief">{e(turn["text"])}</div>'
    ran = [s for s in sides if s["checks"] is not None]
    stats = "<table><tr><th>Side</th><th>How it was made</th><th class=n>Time</th><th class=n>Cost</th><th>Checklist</th></tr>" + "".join(
        f"<tr><td class=nw>{e(s['name'])}<br><span class=mut>{e(s['sub'])}</span></td><td>{s['gen']}</td><td class=n>{s['time']} s</td><td class=n>{e(s['cost'])}</td>"
        f"<td class=nw>{tally(s['checks'])}{'<br><span class=mut>' + e(s['flag']) + '</span>' if s['flag'] else ''}</td></tr>" for s in ran) + "</table>"
    shown = [s for s in ran if s["video"]]
    videos = "".join(f'<figure><video controls preload=metadata poster="{e(s["poster"])}" src="{e(s["video"])}"></video><figcaption><b>{e(s["name"])}</b>'
                     f'{" · " + e(s["flag"]) if s["flag"] else ""}</figcaption></figure>' for s in shown)
    # The checklist lines are the old MCP's. A side scored on its own numbering says which line each of its lines answers ("line").
    reference = sides[0]["checks"]
    body = ""
    for i, want in enumerate(reference):
        cells = ""
        for s in ran:
            own = s["checks"]
            c = next((x for x in own if x.get("line") == i), None) if any("line" in x for x in own) else (own[i] if i < len(own) else None)
            cells += (f"<td><span class={CLASS[c['result']]}>{c['result']}</span><br><span class=mut>{e(c['got'])}</span></td>" if c else "<td class=mut>not scored</td>")
        body += f"<tr><td>{e(want['want'])}</td>{cells}</tr>"
    checklist = "<table><tr><th>Wanted</th>" + "".join(f"<th>{e(s['name'])}</th>" for s in ran) + f"</tr>{body}</table>"
    missing = "".join(f"<p class=mut>{e(s['name'])}: {e(s['flag'])}</p>" for s in sides if s["checks"] is None)
    tall = spec["spec"]["aspect"] in ("9:16", "1:1")   # narrower grid, so a tall or square film is not page-high
    return (f'<h2 id="{item["id"]}">{item["id"]} · {e(spec["case_name"])}</h2><p class=mut>The brief as sent{", and the attached files" if pics else ""}</p>{inputs}'
            f"{stats}{missing}<div class=\"vids{' tall' if tall else ''}\" style=\"grid-template-columns:repeat({max(len(shown), 2)},1fr)\">{videos}</div>{checklist}")


def main() -> None:
    all_sides = {item["id"]: sides_of(item) for item in ITEMS}
    rows = ""
    for item in ITEMS:
        spec = json.loads((ITEMS_DIR / f"{item['id']}.json").read_text())
        sides = [s for s in all_sides[item["id"]] if s["name"] != "Replicate, free model"]
        rows += f'<tr><td class=nw><a href="#{item["id"]}">{item["id"]}</a><br><span class=mut>{e(spec["case_name"])}</span></td>' + "".join(cell(s) for s in sides) + "</tr>"
    summary = "<table><tr><th>Item</th><th>Old MCP</th><th>V1</th><th>Replicate</th></tr>" + rows + "</table>"
    note = ("Time: the whole request, from the brief to the reply · Cost: credits charged; dollars at $19 for 12,000 credits · "
            "Replicate cost: generated seconds at $0.09, an estimate that is not confirmed · Checklist: one line for each thing the brief asked for, "
            "scored by eye, one run for each film")
    notes = load(BENCH / "report-notes.json") or {}
    changed = "".join(f"<li>{e(x)}</li>" for x in notes.get("changed", []))
    found = "".join(f"<li>{e(x)}</li>" for x in notes.get("found", []))
    page = (
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex"><title>Old MCP, v1, Replicate</title>' + STYLE +
        "<style>body{max-width:1240px}.vids{display:grid;gap:14px;margin:18px 0;align-items:start}.vids.tall{max-width:820px}"
        "figcaption{margin-top:6px}.conv td{width:33%}.conv .pre{margin:0 0 6px}h2{margin-top:44px}.in{margin-bottom:14px}.pics img,.pics video{width:auto}"
        "ul{margin:4px 0 16px;padding-left:22px;font-size:14px}"
        "@media(max-width:720px){.vids{grid-template-columns:1fr 1fr!important}}</style>"
        '<nav><a href="index.html">Dense benchmark</a><a href="upgrade.html">Upgrade</a><a href="report.html" class="on">Report</a></nav>'
        "<h1>Old MCP, v1, Replicate</h1><p class=mut>5 November 2026 · driver gpt-6.1-sol, medium · v1 is a local build, not deployed</p>"
        + (f"<h2>What v1 adds</h2><ul>{changed}</ul>" if changed else "")
        + "<h2>Results</h2>" + summary + f"<p class=mut>{e(note)}</p>"
        + (f"<h2>What the runs show</h2><ul>{found}</ul>" if found else "")
        + "".join(section(item, all_sides[item["id"]]) for item in ITEMS)
        + "<h2>Vague requests: questions and values</h2>" + conversations("mcp-intent-mod" if (RESULTS / "mcp-intent-mod").exists() else "mcp-intent-new2", "mcp-intent-new")
        + "</html>"
    )
    (BENCH / "report.html").write_text(page)
    print(BENCH / "report.html", f"({len(page) // 1024} KB)")


if __name__ == "__main__":
    main()

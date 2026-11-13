"""Build Benchmark/report-testset/: the dense benchmark test set (A1-A4, B1, B2), no outputs. Self-contained for Vercel.

    python3 scripts/testset_page.py
    cd Benchmark/report-testset && vercel deploy --prod --yes
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from upgrade_page import BENCH, STYLE, e  # noqa: E402

AGENT = ROOT.parent / "magic-agent-video-generator" / "V2" / "bench"
ITEMS_DIR = AGENT / "mcp" / "dense" / "items"
FIXTURES = AGENT / "v1" / "fixtures"
OUT = BENCH / "report-testset"
ORDER = ["A1", "A2", "A3", "A4", "B1", "B2"]
AUDIO = {"required": "required", "optional": "your call", "none": "silent"}


def copy(name: str) -> str:
    (OUT / "media").mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / name, OUT / "media" / name)
    return f"media/{name}"


def main() -> None:
    if OUT.exists():
        for child in OUT.iterdir():          # keep .vercel (the project link)
            if child.name != ".vercel":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    rows, sections = "", ""
    for item in ORDER:
        spec = json.loads((ITEMS_DIR / f"{item}.json").read_text())
        turn, s = spec["turns"][0], spec["spec"]
        files = turn["materials"]
        rows += (f'<tr><td><a href="#{item}">{item}</a></td><td>{e(spec["case_name"])}</td><td class=n>{s["seconds"]} s</td>'
                 f'<td class=n>{s["aspect"]}</td><td class=n>{len(files) or "none"}</td><td class=n>{AUDIO.get(s["audio"], s["audio"])}</td>'
                 f'<td class=n>{len(spec["must_haves"])}</td></tr>')
        pics = "".join(
            f"<figure>{'<video controls preload=metadata src=' + chr(34) + copy(m) + chr(34) + '></video>' if m.endswith('.mp4') else '<img src=' + chr(34) + copy(m) + chr(34) + ' alt=' + chr(34) + e(m) + chr(34) + '>'}"
            f"<figcaption>{e(m)}</figcaption></figure>" for m in files)
        brief = f'<div class=in><div class="pre brief">{e(turn["text"])}</div><div class=pics>{pics}</div></div>' if pics else f'<div class="pre brief">{e(turn["text"])}</div>'
        checks = "".join(f"<li>{e(w)}</li>" for w in spec["must_haves"])
        answers = "".join(f"<tr><td class=nw>{e(k)}</td><td>{e(v)}</td></tr>" for k, v in spec.get("answer_sheet", {}).items())
        sections += (f'<h2 id="{item}">{item} · {e(spec["case_name"])}</h2><p class=mut>{e(spec["tests"])}</p>'
                     f'<p class=lbl>The request, as sent{", and the attached files" if pics else ""}</p>{brief}'
                     f"<p class=lbl>Checklist ({len(spec['must_haves'])} lines)</p><ol>{checks}</ol>"
                     + (f"<details><summary>Answers if the assistant asks</summary><table>{answers}</table></details>" if answers else ""))
    summary = ("<table><tr><th>Item</th><th>Case</th><th class=n>Length</th><th class=n>Shape</th><th class=n>Attached</th>"
               f"<th class=n>Sound</th><th class=n>Checklist</th></tr>{rows}</table>")
    note = ("Each request is sent once as the first chat message to an assistant connected to the MCP · "
            "if the assistant asks a question, the answer comes from the item's answer sheet · "
            "the film is scored against the checklist: yes, partly or no for each line")
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>Video benchmark test set</title>' + STYLE +
            "<style>body{max-width:1000px}h2{margin-top:48px}.in{margin-bottom:6px}.pics img,.pics video{width:auto}"
            ".lbl{font-weight:600;margin:18px 0 6px}ol{margin:4px 0 12px;padding-left:22px;font-size:14px}ol li{margin:3px 0}"
            "details{margin-top:10px;font-size:14px}</style>"
            f"<h1>Video benchmark: the test set</h1><p class=mut>{len(ORDER)} requests · from a short product spot to a 30-second film</p>"
            + summary + f"<p class=mut>{e(note)}</p>" + sections + "</html>")
    (OUT / "index.html").write_text(page)
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(OUT / "index.html", f"· {size / 1e6:.1f} MB with media")


if __name__ == "__main__":
    main()

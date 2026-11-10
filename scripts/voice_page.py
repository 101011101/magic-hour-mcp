"""Build Benchmark/voice.html: A4's voice-over made five ways on the same picture (scripts/voice_bench.py).

    python3 scripts/voice_page.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from upgrade_page import BENCH, CLASS, STYLE, e  # noqa: E402

FOLDER = BENCH / "voice" / "A4"
HOW = {
    "A": "A voice sample (macOS Samantha) goes to /v1/ai-voice-cloner, which reads the script. The join places each sentence on its beat.",
    "C": "Today's method: one ltx-2.5 call, a black screen with a narrator. Whisper checks the words; a mismatch makes one redo.",
    "D": "One ltx-2.5 black-screen narration call per sentence; the three tracks are put end to end, then placed.",
    "E": "The three scenes are made again with a presenter on screen who says each sentence (ltx-2.5, sound on).",
    "F": "No voice. The captions are drawn on each beat.",
    "MCP": ("The whole A4 request run by the agent through the MCP, the voice switch on, a recording attached: the MCP asked "
            "`voice`, the agent answered sample, the voice cloner read the agent's script, the join's word check heard 100%. "
            "New scenes, so the picture differs from A-F."),
}


def verdict(r: dict) -> tuple[str, str]:
    if r.get("failed"):
        return "no", "Failed: " + r["failed"][:160]
    if r["id"] == "F":
        return "partly", "No voice-over: the request asked for one"
    m = r.get("match") or 0
    return ("yes" if m >= 0.9 else "partly" if m >= 0.6 else "no"), f"{round(m * 100)}% of the script's words heard, in order"


def main() -> None:
    records = [json.loads(p.read_text()) for p in sorted(FOLDER.glob("*/record.json"), key=lambda p: (p.parent.name == "MCP", p.parent.name))]
    script = records[0]["script"] if records else ""
    rows, films = "", ""
    for r in records:
        result, note = verdict(r)
        tries = "".join(f"<br><span class=mut>{e(s['what'])}: {round((s.get('match') or 0) * 100)}% · “{e(s.get('heard', '')[:140])}”</span>"
                        for s in r["steps"] if "heard" in s)
        rows += (f"<tr><td class=nw><b>{e(r['id'])}</b> {e(r['name'])}</td><td class=n>{r['credits']}</td>"
                 f"<td class=n>{r.get('film', {}).get('seconds', '')} s</td><td><span class={CLASS[result]}>{result}</span><br>"
                 f"<span class=mut>{e(note)}</span>{tries}</td><td>“{e(r.get('heard', ''))}”</td></tr>")
        if (FOLDER / r["id"] / "film.mp4").exists():
            films += (f"<figure><video controls preload=metadata src=\"voice/A4/{e(r['id'])}/film.mp4\"></video>"
                      f"<figcaption><b>{e(r['id'])} · {e(r['name'])}</b><br><span class=mut>{e(HOW[r['id']])}</span></figcaption></figure>")
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>Voice-over test</title>' + STYLE +
            "<style>body{max-width:1240px}.vids{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px;margin:18px 0}"
            "figure{margin:0}figcaption{margin-top:6px;font-size:14px}</style>"
            "<h1>A4 voice-over: five ways</h1><p class=mut>8 November 2026 · the same picture for every option: the three scene clips and "
            "the held logo of the last run · joined by the MCP's own join code · one attempt each · the words checked by a Whisper transcript. "
            "B (the celebrity voice generator) is not run: a real person's voice on a company's ad.</p>"
            f"<p><b>Script:</b> “{e(script)}”</p>"
            "<table><tr><th>Option</th><th class=n>Credits</th><th class=n>Length</th><th>Voice right?</th><th>Heard in the film</th></tr>"
            + rows + f"</table><div class=vids>{films}</div></html>")
    (BENCH / "voice.html").write_text(page)
    print(BENCH / "voice.html")


if __name__ == "__main__":
    main()

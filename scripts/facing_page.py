"""Build Benchmark/facing.html: a spoken line when the speaker does not face the camera (approach_bench.py facing).

    python3 scripts/facing_page.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from upgrade_page import BENCH, CLASS, STYLE, e  # noqa: E402

FOLDER = BENCH / "approach" / "facing"
# By eye from 2 frames a second, 2026-11-08. (said, kept facing away, right speaker)
SEEN = {
    "S1": ("yes", "partly", "yes", "Both stand side by side, turned three-quarters away and looking the same way; she does not face him"),
    "S2": ("yes", "yes", "yes", "Stays in profile the whole time; the mouth moves with the line"),
    "S3": ("yes", "yes", "yes", "Small and far away; the voice is heard close, as if near the camera"),
    "S4": ("yes", "yes", "yes", "His back to the camera, she faces it with her mouth closed; his beard moves on the line"),
    "S5": ("yes", "yes", "yes", "His back to the camera, she faces it with her mouth closed; quieter (-33 dB)"),
    "S6": ("yes", "yes", "yes", "His back to the camera, she faces it with her mouth closed"),
}


def main() -> None:
    records = [json.loads(p.read_text()) for p in sorted(FOLDER.glob("*/record.json"))]
    rows, films = "", ""
    for r in records:
        said, away, who, note = SEEN[r["id"]]
        rows += (f"<tr><td class=nw><b>{e(r['id'])}</b> {e(r['name'])}</td>"
                 + "".join(f"<td><span class={CLASS[x]}>{x}</span></td>" for x in (said, away, who))
                 + f"<td>“{e(r.get('heard', ''))}”<br><span class=mut>{e(note)}</span></td></tr>")
        films += (f"<figure><video controls preload=metadata src=\"approach/facing/{e(r['id'])}/film.mp4\"></video>"
                  f"<figcaption><b>{e(r['id'])} · {e(r['name'])}</b><details><summary>Prompt</summary>"
                  f"<div class=pre>{e(r['prompt'])}</div></details></figcaption></figure>")
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>Facing-away speaker</title>' + STYLE +
            "<style>body{max-width:1240px}.vids{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px;margin:18px 0}"
            "figure{margin:0}figcaption{margin-top:6px;font-size:14px}</style>"
            "<h1>A spoken line, speaker not facing the camera</h1><p class=mut>8 November 2026 · 4 s clips, sound on, the line "
            "“You came back.” · one attempt each · 96 credits each, 576 in all · the words by a Whisper transcript, the rest by eye</p>"
            "<table><tr><th>Clip</th><th>Said word for word</th><th>Kept facing away</th><th>Right speaker</th><th>Heard · seen</th></tr>"
            + rows + f"</table><div class=vids>{films}</div></html>")
    (BENCH / "facing.html").write_text(page)
    print(BENCH / "facing.html")


if __name__ == "__main__":
    main()

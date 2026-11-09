"""Build Benchmark/approach.html: the words, continue-a-clip and split tests, side by side, with a wanted / got checklist.

    python3 scripts/approach_page.py

Reads Benchmark/approach/scores.json: {"words"|"continue"|"split": {"wants": [...], "sides": [{"id", "name", "how", "film",
"credits", "checks": [{"result", "got"}], "verdict"}], "notes": [...]}}. Films are linked in place (the page stays on this machine).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from upgrade_page import BENCH, CLASS, STYLE, e  # noqa: E402

import approach_bench as ab  # noqa: E402

V1_RESULTS = ROOT.parent / "magic-agent-video-generator" / "V2" / "bench" / "v1" / "results"
CARD_HOLD = ("The supplied image held almost motionless for the whole clip: a very slow, barely visible push in. "
             "Every letter stays exactly as in the image. Nothing else appears.")
BRIEFS = {
    "line": "From B2: \"He says out loud: 'You came back.' She smiles.\" Look for: the line heard word for word, once, from the man; rain, no music.",
    "words": "From A2: \"End on her back as she walks away, with the words 'walk anyway' on screen.\" Look for: the words spelled exactly, "
             "shown only at the end, over her (not on a separate card), and the letters holding still.",
    "continue": "A3: \"The attached clip is 6 seconds long. Continue the clip for 6 more seconds: she turns and walks out of frame. Keep her face, "
                "hair and clothes the same. Keep it silent. Give me one 12-second video file: the original 6 seconds first, unchanged, then the new "
                "6 seconds.\" Look for: the first 6 s identical to the original, no jump at 6 s, she turns her back and leaves the frame, no sound.",
    "split": "C6: one bottle (its picture as the reference) in spring, summer, autumn, winter, 5 s each, 9:16. C7: Mara in spring, Theo in summer "
             "and autumn, Mara in winter, 5 s each, 16:9, no pictures. Look for: all four seasons, in order, each once; no season bleeding into "
             "the next (petals in snow, a beach behind autumn); the same bottle or people throughout. C10: Mara (spring, winter) and Theo (summer, autumn) "
             "each holding the bottle, people in words, the bottle picture in every call, 9:16.",
}


def recorded_prompt(path: Path) -> str:
    record = json.loads(path.read_text())
    for turn in record["turns"]:
        for call in turn.get("tool_calls") or turn.get("calls") or []:
            if call["name"].startswith("create_"):
                args = json.loads(call["arguments"]) if isinstance(call["arguments"], str) else call["arguments"]
                return args.get("style", {}).get("prompt", "")
    return ""


def split_prompts(folder: Path) -> list[tuple[str, str]]:
    plan = json.loads((folder / "record.json").read_text())["plan"]
    out = []
    for clip in plan["clips"]:
        for step in clip["steps"]:
            ref = clip["reference"]["kind"]
            out.append((f"Clip {clip['n']} · {step['model']} · {step.get('seconds', '')} s · reference: {ref.replace('_', ' ')}", step["prompt"]))
    return out


def prompts(key: str, side: dict) -> list[tuple[str, str]]:
    i = side["id"]
    if key == "words":
        return {
            "W1": [("ltx-2.5 text-to-video · 5 s", ab.SCENE + ab.ASK)],
            "W2": [("minimax-h3 text-to-video · 5 s", ab.SCENE + ab.ASK)],
            "W3": [("qwen still", f"{ab.WOMAN} seen from behind, walking away from a bus stop down a wet city street at night in the rain. "
                                  f'Large white letters across the lower third read exactly "{ab.WORDS}". No other text.'),
                   ("ltx-2.5 image-to-video · 5 s", f'The supplied image comes to life: she keeps walking away into the rain, slowly. The words '
                                                   f'"{ab.WORDS}" stay exactly as in the image, fixed in place, every letter unchanged.')],
            "W4": [("ltx-2.5 text-to-video · 5 s", ab.SCENE + ab.CLEAN), ("Code", f'Draw "{ab.WORDS}" in white over the last 2 s.')],
            "W5": [("ltx-2.5 text-to-video · 5 s (the W4 scene)", ab.SCENE + ab.CLEAN),
                   ("qwen still", f'A title card: solid black background, centred white text reading exactly "{ab.WORDS}". No other text, nothing else.'),
                   ("ltx-2.5 image-to-video · 2 s", CARD_HOLD)],
        }[i]
    if key == "continue":
        return {
            "C1": [("minimax-h3 text-to-video · 12 s · references: the clip, the portrait", recorded_prompt(V1_RESULTS / "mcp-dense-2-A3" / "A3.json"))],
            "C1b": [("minimax-h3 text-to-video · 12 s · references: the clip, the portrait", recorded_prompt(V1_RESULTS / "mcp-mod-4-A3" / "A3.json"))],
            "C2": [("ltx-2.5 image-to-video · 6 s · from the original's last frame", "The supplied image is the first frame. " + ab.TURN)],
            "C3": [("minimax-h3 image-to-video · 6 s · from the original's last frame", "The supplied image is the first frame. " + ab.TURN)],
            "C4": [("minimax-h3 text-to-video · 6 s · reference: the clip", "Continue @clip from its last frame: the first frame of this video is "
                                                                          "the last frame of @clip. " + ab.TURN)],
        }[i]
    if key == "line":
        if side["id"] == "Inside":
            return [("ltx-2.5 · 12 s · clip 3 of the B2 plan", "Close on both of them beneath the black umbrella. The man says aloud exactly once: "
                     "\"You came back.\" The woman smiles in response. … 6-12 s: Rear view: they walk away together … (the full prompt: 900 characters)")]
        return [(side["how"], json.loads((BENCH / Path(side["film"]).parent / "record.json").read_text())["prompt"])]
    return split_prompts(BENCH / Path(side["film"]).parent)


TITLES = {"words": "Exact words on screen (A2's ending: “walk anyway”)",
          "continue": "Continue a given clip for 6 s (A3: she turns and walks out of frame)",
          "split": "Split only on a change of medium or the length cap",
          "line": "A spoken line: inside a long clip, or alone in a short one (B2: \"You came back.\")"}


SCRIPT = """<script>
const KEY = "approach-picks", NAMES = {words: "Words", continue: "Continue", "split-C6": "Split, bottle (C6)", "split-C7": "Split, two people (C7)", "split-C10": "Split, perfume + 2 people (C10)", line: "Spoken line"};
let picks = {};
try { picks = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (_) {}
for (const k in picks) picks[k] = [].concat(picks[k] || []);   // older pages saved one pick as a string
function text() {
  const parts = Object.keys(NAMES).filter(k => (picks[k] || []).length).map(k => NAMES[k] + ": " + picks[k].join(", "));
  return parts.length ? "My picks · " + parts.join(" · ") : "";
}
function show() {
  document.querySelectorAll("figure[data-section]").forEach(f => f.classList.toggle("picked", (picks[f.dataset.section] || []).includes(f.dataset.id)));
  document.querySelectorAll("figure.picked .pick").forEach(b => b.textContent = "Picked");
  document.querySelectorAll("figure:not(.picked) .pick").forEach(b => b.textContent = "Pick this");
  const t = text();
  document.getElementById("summary").textContent = t || "Your picks: none yet. Click Pick this under every film you like; pick as many as you want.";
}
document.querySelectorAll(".pick").forEach(b => b.addEventListener("click", () => {
  const f = b.closest("figure"), k = f.dataset.section;
  const list = picks[k] || [], id = f.dataset.id;
  picks[k] = list.includes(id) ? list.filter(x => x !== id) : [...list, id];
  try { localStorage.setItem(KEY, JSON.stringify(picks)); } catch (_) {}
  show();
}));
document.getElementById("copy").addEventListener("click", async e => {
  const t = text() || "No picks yet";
  try { await navigator.clipboard.writeText(t); e.target.textContent = "Copied"; } catch (_) { e.target.textContent = "Copy failed: select the text"; }
  setTimeout(() => e.target.textContent = "Copy picks", 1500);
});
show();
</script>"""


def tally(checks: list[dict]) -> str:
    n = {k: sum(1 for c in checks if c["result"] == k) for k in ("yes", "partly", "no")}
    return f"{n['yes']} yes · {n['partly']} partly · {n['no']} no"


def section(key: str, data: dict) -> str:
    sides = data["sides"]
    top = ("<table><tr><th>Approach</th><th>How</th><th class=n>Credits</th><th>Checklist</th></tr>" + "".join(
        f"<tr><td class=nw><b>{e(s['id'])}</b> {e(s['name'])}</td><td>{e(s['how'])}</td><td class=n>{e(str(s['credits']))}</td>"
        f"<td class=nw>{tally(s['checks'])}</td></tr>" for s in sides) + "</table>")
    videos = "".join(f'<figure data-section="{key + ("-" + s["id"].split()[0] if key == "split" else "")}" data-id="{e(s["id"])}"><video controls preload=metadata src="{e(s["film"])}"></video>'
                     f'<figcaption><b>{e(s["id"])}</b> {e(s["name"])}<br><span class=mut>{e(s.get("verdict", ""))}</span></figcaption>'
                     f'<details class=prompt><summary>Prompt sent</summary>' + "".join(f'<p class=plabel>{e(label)}</p><div class=ptext>{e(text)}</div>' for label, text in prompts(key, s))
                     + '</details><button type=button class=pick>Pick this</button></figure>' for s in sides if s.get("film"))
    rows = "".join(f"<tr><td>{e(w)}</td>" + "".join(
        f"<td><span class={CLASS[s['checks'][i]['result']]}>{s['checks'][i]['result']}</span><br><span class=mut>{e(s['checks'][i]['got'])}</span></td>"
        for s in sides) + "</tr>" for i, w in enumerate(data["wants"]))
    table = "<table><tr><th>Wanted</th>" + "".join(f"<th>{e(s['id'])}</th>" for s in sides) + f"</tr>{rows}</table>"
    notes = "".join(f"<li>{e(n)}</li>" for n in data.get("notes", []))
    cols = min(len([s for s in sides if s.get("film")]), 4)
    return (f'<h2 id="{key}">{e(TITLES[key])}</h2><p class=brief>{e(BRIEFS[key])}</p>{top}<div class="vids{" tall" if data.get("tall") else ""}" '
            f'style="grid-template-columns:repeat({cols},1fr)">{videos}</div>{table}' + (f"<ul>{notes}</ul>" if notes else ""))


def main() -> None:
    scores = json.loads((BENCH / "approach" / "scores.json").read_text())
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex"><title>Approach tests</title>' + STYLE +
            "<style>body{max-width:1240px}.vids{display:grid;gap:14px;margin:18px 0;align-items:start}.vids.tall{max-width:900px}"
            "figcaption{margin-top:6px}h2{margin-top:44px}ul{margin:8px 0 16px;padding-left:22px;font-size:14px}"
            "@media(max-width:720px){.vids{grid-template-columns:1fr 1fr!important}}"
            "figure{border:2px solid transparent;border-radius:10px;padding:6px;margin:0}figure.picked{border-color:var(--ok)}"
            ".pick,#picks button{margin-top:8px;padding:8px 14px;border-radius:8px;border:1px solid var(--mut);background:Canvas;color:CanvasText;"
            "font:600 14px/1.2 -apple-system,system-ui,sans-serif;cursor:pointer}.pick{width:100%}.pick:hover,#picks button:hover{border-color:CanvasText}"
            "figure.picked .pick{background:CanvasText;color:Canvas;border-color:CanvasText}"
            "#picks{position:sticky;top:0;z-index:5;background:Canvas;color:CanvasText;border-bottom:1px solid var(--line);padding:10px 0;margin-bottom:10px;"
            "display:flex;gap:12px;align-items:center;flex-wrap:wrap;font-size:14px}#picks button{margin-top:0}"
            ".brief{margin:6px 0 14px;padding:10px 12px;border-left:3px solid var(--mut);font-size:14px}"
            ".prompt{margin-top:8px}.prompt summary{cursor:pointer;font-size:13px;color:CanvasText;font-weight:600}"
            ".plabel{margin:8px 0 2px;font-size:12px;color:var(--mut)}.ptext{font-size:12.5px;line-height:1.45;padding:8px;border:1px solid var(--line);"
            "border-radius:6px;max-height:220px;overflow:auto;white-space:pre-wrap}</style>"
            "<h1>Approach tests: words, continue a clip, split</h1><p class=mut>6 November 2026 · direct API calls, free-plan models at 480p · "
            "one attempt for each approach · scored by eye from frames</p>"
            + "<div id=picks><span id=summary>Your picks: none yet. Click <b>Pick this</b> under every film you like; pick as many as you want.</span>"
              "<button type=button id=copy>Copy picks</button></div>"
            + "".join(section(k, scores[k]) for k in ("line", "words", "continue", "split") if k in scores) + SCRIPT + "</html>")
    (BENCH / "approach.html").write_text(page)
    print(BENCH / "approach.html")


if __name__ == "__main__":
    main()

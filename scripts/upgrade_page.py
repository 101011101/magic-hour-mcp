"""Build Benchmark/upgrade.html: the split films against the current MCP, and the vague briefs before and after plan_request.

    python3 scripts/upgrade_page.py [--new mcp-intent-new2] [--first mcp-intent-new]

Reads Benchmark/split/<story>/<variant>/{record,checks}.json, the dense baseline checklists and the vague-brief run
records in the agent repo. Writes one self-contained page beside the films (videos are linked, not copied).
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from conversation_score import WANTED, attempted, score_item  # noqa: E402
from split_bench import step_key  # noqa: E402

BENCH = ROOT / "Benchmark"
RESULTS = ROOT.parent / "magic-agent-video-generator" / "V2" / "bench" / "v1" / "results"
STORIES = ROOT / "tests" / "fixtures" / "stories"
e = html.escape
arg = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
CLASS = {"yes": "ok", "partly": "mid", "no": "bad", "correct": "ok", "wrong": "bad", "not settled": "mid"}

# The page's look is the dense benchmark's (Benchmark/index.html).
STYLE = re.search(r"<style>.*?</style>", (BENCH / "index.html").read_text(), re.S)[0]

# story file prefix, baseline: (label, video, checklist file, which baseline lines match the story's lines)
FILMS = [
    ("c4", "B2", "B2/run1-01-create_video_from_text.mp4", RESULTS / "mcp-dense-2-B2" / "B2.checks.json", [0, 1, 2, 3, 4, 5, 6]),
    ("c5", "B1", "B1/run2-01-create_video_from_text.mp4", RESULTS / "mcp-dense-1b" / "B1b.checks.json", [0, 1, 2, 3, 5]),
    ("c6", None, None, None, None),   # a new story: no run on the current MCP
    ("c7", None, None, None, None),
    ("c8", None, None, None, None),
    ("c9", None, None, None, None),
]


def poster(video: str) -> str:
    """The still shown before play. The video itself always starts at 0 s."""
    return video[:-4] + ".poster.jpg" if video.startswith(("split/", "modified/")) else video + ".poster.jpg"


def tally(checks: list[dict]) -> str:
    n = {k: sum(1 for c in checks if c["result"] == k) for k in ("yes", "partly", "no")}
    return f"{n['yes']} yes · {n['partly']} partly · {n['no']} no"


def films() -> str:
    rows, sections = [], []
    for prefix, base_id, base_video, base_checks_file, lines in FILMS:
        story = json.loads(next(STORIES.glob(f"{prefix}-*.json")).read_text())
        sides = []
        if base_id:
            base = [json.loads(base_checks_file.read_text())["checks"][i] for i in lines]
            base_row = next(r for r in json.loads((BENCH / base_id / "summary.json").read_text())["rows"] if r["service"] == "Magic Hour")
            sides = [{"name": "Current MCP", "sub": "one call, 30 s", "video": base_video, "checks": base, "credits": 720, "clips": 1,
                      "gen": "one text-to-video call", "time": base_row["seconds"]}]
        records = {v["name"]: json.loads((BENCH / "split" / story["id"] / v["name"] / "record.json").read_text())
                   for v in story["variants"] if (BENCH / "split" / story["id"] / v["name"] / "record.json").exists()}
        # A call that was reused from another variant took time when it was first made: count that time here too.
        made = {}
        for r in records.values():
            for clip, done in zip(r["plan"]["clips"], r["clips"]):
                for step, ran in zip(clip["steps"], done["steps"]):
                    if "seconds_waited" in ran:
                        made[(step_key(story, clip, step), step["tool"])] = ran["seconds_waited"]
        for variant in story["variants"]:
            if variant["name"] not in records or not (BENCH / "split" / story["id"] / variant["name"] / "checks.json").exists():
                continue
            folder = BENCH / "split" / story["id"] / variant["name"]
            record = records[variant["name"]]
            checks = json.loads((folder / "checks.json").read_text())["checks"]
            plan = record["plan"]
            gen = []
            for clip in plan["clips"]:
                ref = clip["reference"]
                what = {"none": "no reference", "last_frame": f"last frame of clip {ref.get('of_clip')}",
                        "picture": f"picture of the {ref.get('subject')}", "still": "its own still"}[ref["kind"]]
                gen.append(f"{clip['seconds']} s · {clip['steps'][-1]['model']} · {what}")
            sides.append({
                "name": variant["name"].replace("-", " "), "sub": f"{len(plan['clips'])} clips", "checks": checks, "gen": "<br>".join(e(g) for g in gen),
                "video": f"split/{story['id']}/{variant['name']}/film.mp4", "clips": len(plan["clips"]),
                "credits": sum(s["credits"] for c in plan["clips"] for s in c["steps"]),
                "time": sum(ran.get("seconds_waited", made.get((step_key(story, clip, step), step["tool"]), 0))
                            for clip, done in zip(plan["clips"], record["clips"]) for step, ran in zip(clip["steps"], done["steps"])),
            })
        # films that the modified MCP made through the GPT driver for this story
        for side_file in sorted((BENCH / "modified" / (base_id or "-")).glob("*/side.json")):
            side = json.loads(side_file.read_text())
            checks_file = side_file.with_name("checks.json")
            if checks_file.exists():
                rel = side_file.parent.relative_to(BENCH)
                sides.append({**side, "video": f"{rel}/film.mp4", "checks": json.loads(checks_file.read_text())["checks"]})
        if not sides:
            continue
        label = f"{story['title']} ({base_id})" if base_id else story["title"]
        for i, s in enumerate(sides):
            rows.append(
                f"<tr><td>{e(label) if i == 0 else ''}</td><td class=nw>{e(s['name'])}</td><td class=n>{s['clips']}</td>"
                f"<td class=n>{s['time']} s</td><td class=n>{s['credits']}</td><td class=nw>{tally(s['checks'])}</td></tr>")
        beats = "".join(f"<li>{b['seconds']} s · {e(b['text'])}{' · words: ' + e(', '.join(b['exact_words'])) if b.get('exact_words') else ''}</li>" for b in story["beats"])
        videos = "".join(
            f"<figure><video controls preload=metadata poster=\"{e(poster(s['video']))}\" src=\"{e(s['video'])}\"></video><figcaption><b>{e(s['name'])}</b> · {e(s['sub'])} · {s['time']} s · {s['credits']} credits"
            f"<br>{s['gen']}</figcaption></figure>" for s in sides)
        head = "".join(f"<th>{e(s['name'])}</th>" for s in sides)
        body = ""
        for i, want in enumerate(sides[-1]["checks"]):
            cells = "".join(f"<td><span class={CLASS[s['checks'][i]['result']]}>{s['checks'][i]['result']}</span><br><span class=mut>{e(s['checks'][i]['got'])}</span></td>" for s in sides)
            body += f"<tr><td>{e(want['want'])}</td>{cells}</tr>"
        notes_file = BENCH / "split" / story["id"] / "notes.json"
        notes = json.loads(notes_file.read_text())["notes"] if notes_file.exists() else []
        notes_html = ("<p class=mut>Notes</p><ol class=notes>" + "".join(f"<li>{e(n['text'])} <span class=mut>{e(n['by'])}</span></li>" for n in notes) + "</ol>") if notes else ""
        portrait = story["aspect"] == "9:16"
        sections.append(
            f"<h2>{e(story['title'])}{' (' + base_id + ' story)' if base_id else ''} · {story['seconds']} s · {story['aspect']}</h2><ol>{beats}</ol>"
            f"<div class=\"vids{' tall' if portrait else ''}\" style=\"grid-template-columns:repeat({len(sides)},1fr)\">{videos}</div>{notes_html}"
            f"<table><tr><th>Wanted</th>{head}</tr>{body}</table>")
    table = "<table><tr><th>Story</th><th>How it was made</th><th class=n>Clips</th><th class=n>Total time</th><th class=n>Credits</th><th>Checklist</th></tr>" + "".join(rows) + "</table>"
    note = ("One run for each film · scored by eye · C5 scores the picture only (no voice, captions, music) · "
            "total time: the clips are made one after the other; the current MCP's time is its whole request")
    return table + f"<p class=mut>{e(note)}</p>" + "".join(sections)


def tried(record: dict | None) -> str:
    if record is None:
        return "no record"
    call = attempted(record)
    if call is None:
        return "no call"
    a = call["args"]
    bits = [call["name"]]
    if a.get("aspect_ratio"):
        bits.append(str(a["aspect_ratio"]))
    if a.get("end_seconds") is not None:
        bits.append(f"{a['end_seconds']} s")
    if "audio" in a:
        bits.append("audio on" if a["audio"] else "audio off")
    return " · ".join(bits)


def conversations(new_dir: str, first_dir: str) -> str:
    sides = [("Current MCP", RESULTS / "mcp-intent-before"), ("With plan_request", RESULTS / new_dir)]
    loaded = {name: {i: (json.loads((d / f"{i}.json").read_text()) if (d / f"{i}.json").exists() else None) for i in WANTED} for name, d in sides}
    scores = {name: {i: (score_item(i, r) if r and "turns" in r else None) for i, r in items.items()} for name, items in loaded.items()}

    def total(items: dict) -> dict:
        flat = [v for s in items.values() if s for v in s["values"].values()]
        return {"correct": flat.count("correct"), "wrong": flat.count("wrong"), "open": flat.count("not settled"), "values": len(flat),
                "asked": sum(1 for s in items.values() if s and s["questions"]), "rounds": sum(s["questions"] for s in items.values() if s),
                "all": sum(1 for i, s in items.items() if s and WANTED[i] and all(v == "correct" for v in s["values"].values()))}
    stats = "<table><tr><th></th><th class=n>Values right</th><th class=n>Wrong guesses</th><th class=n>Briefs with every value right</th><th class=n>Briefs with a question</th><th class=n>Question rounds</th></tr>"
    for name, _ in sides:
        t = total(scores[name])
        stats += (f"<tr><td>{e(name)}</td><td class=n>{t['correct']} of {t['values']}</td><td class=n>{t['wrong']}</td>"
                  f"<td class=n>{t['all']} of {sum(1 for i in WANTED if WANTED[i])}</td><td class=n>{t['asked']} of {len(WANTED)}</td><td class=n>{t['rounds']}</td></tr>")
    stats += "</table>"
    note = "13 vague briefs · driver gpt-6.1-sol, medium · every paid call refused, so the call it tried is the result · 0 credits"
    first = RESULTS / first_dir
    if first_dir != new_dir and first.exists():
        f = total({i: (score_item(i, json.loads((first / f"{i}.json").read_text())) if (first / f"{i}.json").exists() else None) for i in WANTED})
        note += f" · first run of plan_request, before 4 fixes: {f['correct']} of {f['values']} right, {f['rounds']} question rounds"
    rows = ""
    for item in WANTED:
        any_record = next((r for r in (loaded[n][item] for n, _ in sides) if r and "item" in r), None)
        brief = any_record["item"]["turns"][0]["text"] if any_record else item
        wanted = " · ".join(f"{k}: {v}" for k, v in (any_record["item"].get("answer_sheet") or {}).items()) if any_record else ""
        cells = ""
        for name, _ in sides:
            record, s = loaded[name][item], scores[name][item]
            if not s:
                cells += "<td>no record</td>"
                continue
            asked = [d["agent"] for t in record["turns"] for d in t.get("dialog", []) if "question" in d.get("asked", [])]
            marks = " ".join(f"<span class={CLASS[v]}>{k} {v}</span>" for k, v in s["values"].items())
            questions = "".join(f"<div class=pre>{e(q[:420])}</div>" for q in asked) or "<span class=mut>asked nothing</span>"
            cells += f"<td>{questions}<div>{e(tried(record))}</div><div>{marks}</div></td>"
        rows += f"<tr><td><b>{e(brief)}</b><br><span class=mut>{e(wanted)}</span></td>{cells}</tr>"
    detail = "<table class=conv><tr><th>The brief, and what the user wants</th>" + "".join(f"<th>{e(n)}</th>" for n, _ in sides) + f"</tr>{rows}</table>"
    return stats + f"<p class=mut>{e(note)}</p>" + detail


def main() -> None:
    new_dir, first_dir = arg("--new", "mcp-intent-new2"), arg("--first", "mcp-intent-new")
    if not (RESULTS / new_dir).exists():
        new_dir = first_dir
    page = (
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex"><title>MCP upgrade</title>' + STYLE +
        "<style>body{max-width:1240px}.vids{display:grid;gap:14px;margin:14px 0 18px;align-items:start}.vids.tall{max-width:900px}"
        "figcaption{margin-top:6px}.conv td{width:33%}.conv .pre{margin:0 0 6px}.notes{margin:4px 0 18px 0;list-style:disc}h2{margin-top:44px}"
        "@media(max-width:720px){.vids{grid-template-columns:1fr 1fr!important}}</style>"
        '<nav><a href="index.html">Dense benchmark</a><a href="upgrade.html" class="on">Upgrade</a></nav>'
        "<h1>MCP upgrade: first results</h1><p class=mut>5 November 2026 · not deployed</p>"
        "<h2>Long videos: one call against a split into clips</h2>" + films() +
        "<h2>Vague requests: questions and values</h2>" + conversations(new_dir, first_dir) + "</html>"
    )
    (BENCH / "upgrade.html").write_text(page)
    print(BENCH / "upgrade.html", f"({len(page) // 1024} KB)")


if __name__ == "__main__":
    main()

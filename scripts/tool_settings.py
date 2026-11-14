"""Which tool settings go with higher scores, compared within the same case (MCP-21, best_settings in tool_notes.json).

Reads every live call's arguments and the run's score from the audit page.
Usage: python3 scripts/tool_settings.py Benchmark/audit/audit-1.html
"""
import collections
import html
import itertools
import json
import re
import sys

COMPARE = [("edit_image", "model"), ("generate_image", "model"), ("generate_image", "style.tool"),
           ("create_video_from_text", "model"), ("upscale_image", "style.mode")]

s = re.sub(r"data:[^\"']{200,}", "DATA", open(sys.argv[1], encoding="utf-8").read())
calls = []
starts = [m.start() for m in re.finditer(r"<section class='t' ", s)] + [len(s)]
for a, b in zip(starts, starts[1:]):
    sec = s[a:b]
    case = re.search(r"data-id='([^']+)'", sec).group(1)
    cards = [m.start() for m in re.finditer(r"<article class='c' ", sec)] + [len(sec)]
    for ca, cb in zip(cards, cards[1:]):
        c = sec[ca:cb]
        score = re.search(r"<p class='s'>score (\d)", c)
        if "data-mode='live'" not in c or not score:
            continue
        for tool, arg in re.findall(r"<summary>#\d+ ([a-z_]+)[^<]*</summary><pre>(.*?)</pre>", c, re.S):
            try:
                calls.append((case, tool, int(score.group(1)), json.loads(html.unescape(arg))))
            except ValueError:
                pass

for tool, key in COMPARE:
    by_case = collections.defaultdict(lambda: collections.defaultdict(list))
    for case, t, score, args in calls:
        if t == tool:
            v = args
            for part in key.split("."):
                v = v.get(part) if isinstance(v, dict) else None
            by_case[case][str(v)].append(score)
    pairs = collections.defaultdict(list)
    for case, d in by_case.items():
        for x, y in itertools.combinations(sorted(d), 2):
            pairs[(x, y)].append((sum(d[x]) / len(d[x]), sum(d[y]) / len(d[y])))
    print(f"== {tool} {key}")
    for (x, y), rows in sorted(pairs.items(), key=lambda p: -len(p[1])):
        if len(rows) >= 2:
            ax, ay = (sum(r[i] for r in rows) / len(rows) for i in (0, 1))
            print(f"  {x} vs {y}: {len(rows)} cases, {ax:.2f} vs {ay:.2f}, "
                  f"wins {sum(r[0] > r[1] for r in rows)}-{sum(r[1] > r[0] for r in rows)}")

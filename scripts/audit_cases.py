"""Parse Benchmark/audit/audit-1.html into one JSON record per case, with every run card."""
import html
import json
import re
import sys

src, out = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
s = re.sub(r"data:[^\"']{200,}", "DATA", s)

cases = []
starts = [m.start() for m in re.finditer(r"<section class='t' ", s)]
starts.append(len(s))
for a, b in zip(starts, starts[1:]):
    sec = s[a:b]
    cid = re.search(r"data-id='([^']+)'", sec).group(1)
    group = re.search(r"data-group='([^']+)'", sec).group(1)
    h3 = re.search(r"<h3>(.*?)<small>(.*?)</small>", sec, re.S)
    title = html.unescape(h3.group(1)).strip().split(" · ", 1)[-1]
    small = html.unescape(h3.group(2))
    cat = small.split(" · ")[0]
    sc = re.search(r"score old ([\d.]+|–|-) / new ([\d.]+|–|-)", small)
    brief = re.search(r"<b>BRIEF</b>(.*?)</p>", sec, re.S)
    wanted = [html.unescape(re.sub(r"<[^>]+>", "", x)) for x in re.findall(r"<li>(.*?)</li>", sec.split("</ul>")[0])]
    runs = []
    for g in re.finditer(r"<div class='g'><small>([^<]+)</small>", sec):
        pass
    card_starts = [m.start() for m in re.finditer(r"<article class='c' ", sec)] + [len(sec)]
    for ca, cb in zip(card_starts, card_starts[1:]):
        c = sec[ca:cb]
        sweep = re.findall(r"<div class='g'><small>([^<]+)</small>", sec[:ca])
        attrs = dict(re.findall(r"data-(\w+)='([^']*)'", c.split(">")[0]))
        line = re.search(r"<p class='s'>(.*?)</p>", c)
        score = re.search(r"<p class='s'>score (\d)\s*·\s*(.*?)</p>", c, re.S)
        fails = [html.unescape(re.sub(r"<[^>]+>", "", x)) for x in re.findall(r"<li class='(?:no|bad|x|fail)[^']*'>(.*?)</li>", c)]
        steps = re.search(r"<p class='tools'>(s\d\w* · .*?)</p>", c)
        tools = re.findall(r"<summary>#\d+ ([a-zA-Z0-9_]+)", c)
        runs.append({
            "sweep": sweep[-1] if sweep else "",
            **attrs,
            "line": html.unescape(line.group(1)) if line else "",
            "score": int(score.group(1)) if score else None,
            "why": html.unescape(score.group(2)).strip() if score else "",
            "fails": fails,
            "steps": html.unescape(steps.group(1)) if steps else "",
            "tools": tools,
        })
    cases.append({
        "id": cid, "group": group, "title": title, "category": cat,
        "old": sc.group(1) if sc else None, "new": sc.group(2) if sc else None,
        "brief": html.unescape(re.sub(r"<[^>]+>", "", brief.group(1))) if brief else "",
        "wanted": wanted, "runs": runs,
    })

json.dump(cases, open(out, "w"), indent=1)
print(len(cases), "cases,", sum(len(c["runs"]) for c in cases), "runs")

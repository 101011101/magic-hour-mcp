"""Build the tool-management failure list (markdown) from cases.json."""
import collections
import json
import re
import sys

cases = json.load(open(sys.argv[1]))
VC = set("D18 D19 D20 D21 D22 D23 H40 H41 H42 H44 I45 I46 I47 I48 J55".split()) | {"H43a", "J51a", "J52a"}
WAIT = {"wait_for_image_project", "wait_for_video_project", "wait_for_audio_project", "plan_request",
        "get_workflow_guide", "ping", "fetch_image_download", "fetch_video_download", "fetch_audio_download", "voices_list", "upload_chatgpt_image", "upload_chatgpt_media", "upload_media"}


def tm(k):
    return k["id"] not in VC and k["id"][:3] not in VC


def avg(xs):
    return sum(xs) / len(xs) if xs else None


def short(f):
    f = f.lstrip("✗ ").split("why?")[0]
    f = re.sub(r"\s+", " ", f).strip()
    return f[:110] + ("…" if len(f) > 110 else "")


def cause(f):
    m = re.search(r"→ ([a-z_]+)\)", f)
    return m.group(1) if m else "untraced"


def main_tools(runs):
    n = collections.Counter()
    for r in runs:
        made = [t for t in r["tools"] if t not in WAIT]
        n[" → ".join(dict.fromkeys(made)) or "(none)"] += 1
    return n


rows, per_tool = [], collections.defaultdict(lambda: {"old": [], "new": []})
for k in filter(tm, cases):
    live = [r for r in k["runs"] if r.get("mode") == "live" and r["score"] is not None]
    side = {s: [r for r in live if r["side"] == s] for s in ("old", "new")}
    o, n = avg([r["score"] for r in side["old"]]), avg([r["score"] for r in side["new"]])
    if o is None or n is None:
        verdict = "no pair"
    else:
        verdict = "better" if n - o >= 0.3 else "worse" if o - n >= 0.3 else "same"
    for s in ("old", "new"):
        for r in side[s]:
            made = [t for t in r["tools"] if t not in WAIT]
            per_tool[made[0] if made else "(none)"][s].append(r["score"])
    fails = collections.Counter()
    causes = collections.Counter()
    for r in live:
        for f in r["fails"]:
            fails[short(f)] += 1
            causes[cause(f)] += 1
    top = fails.most_common(1)[0][0] if fails else ""
    c = [x for x, _ in causes.most_common() if x != "untraced"][:2]
    rows.append({
        "id": k["id"], "group": k["group"], "title": k["title"], "cat": k["category"],
        "n_old": len(side["old"]), "n_new": len(side["new"]), "old": o, "new": n, "verdict": verdict,
        "tools_old": main_tools(side["old"]).most_common(1)[0][0] if side["old"] else "",
        "tools_new": main_tools(side["new"]).most_common(1)[0][0] if side["new"] else "",
        "top": top, "causes": ", ".join(c),
    })

f = lambda x: "–" if x is None else f"{x:.1f}"
cnt = collections.Counter(r["verdict"] for r in rows)
out = []
out.append(f"Cases: {len(rows)}. Better {cnt['better']} · same {cnt['same']} · worse {cnt['worse']} · no pair {cnt['no pair']} "
           f"(new minus old, average over live runs, 0.3 or more counts).")
out.append("")
out.append("### By group")
out.append("")
out.append("| Group | Cases | Old | New | Better / same / worse |")
out.append("|---|---|---|---|---|")
for g in sorted({r["group"] for r in rows}):
    rs = [r for r in rows if r["group"] == g]
    c = collections.Counter(r["verdict"] for r in rs)
    out.append(f"| {g} · {rs[0]['cat']} | {len(rs)} | {f(avg([r['old'] for r in rs if r['old'] is not None]))} | "
               f"{f(avg([r['new'] for r in rs if r['new'] is not None]))} | {c['better']} / {c['same']} / {c['worse']} |")
out.append("")
out.append("### By the first tool called (all live runs on these cases)")
out.append("")
out.append("| Tool | Runs old | Avg old | Runs new | Avg new |")
out.append("|---|---|---|---|---|")
for t, d in sorted(per_tool.items(), key=lambda x: -(len(x[1]["old"]) + len(x[1]["new"]))):
    out.append(f"| `{t}` | {len(d['old'])} | {f(avg(d['old']))} | {len(d['new'])} | {f(avg(d['new']))} |")
out.append("")
out.append("### Each case")
out.append("")
out.append("| Item | Request | Runs o/n | Old | New | Verdict | Tools called (old / new, most common) | Most common failure | Traced causes | Right tool | User's notes |")
out.append("|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    to, tn = r["tools_old"], r["tools_new"]
    tools = f"`{to}`" if to == tn else f"`{to}` / `{tn}`"
    out.append(f"| {r['id']} | {r['title']} | {r['n_old']}/{r['n_new']} | {f(r['old'])} | {f(r['new'])} | {r['verdict']} | {tools} | "
               f"{r['top'].replace('|', '/')} | {r['causes']} |  |  |")
print("\n".join(out))
json.dump(rows, open(sys.argv[2], "w"), indent=1)

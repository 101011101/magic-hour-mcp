"""Show how each item went through the gates: the calls in order, what each gate step returned, where it stopped.

    python3 scripts/gates_trace.py gates-dry-warn [gates-dry-refuse ...] [--full]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent.parent / "magic-agent-video-generator" / "V2" / "bench" / "v1" / "results"
GATES = ("start_request", "classify_request", "submit_plan", "review_plan", "final_check")


def calls(record: dict) -> list[dict]:
    return [c for t in record["turns"] for c in (t.get("tool_calls") or t.get("calls") or [])]


def args(call: dict) -> dict:
    a = call.get("arguments")
    try:
        return json.loads(a) if isinstance(a, str) else (a or {})
    except json.JSONDecodeError:
        return {}


def output(call: dict):
    out = call.get("output") or call.get("error") or ""
    try:
        return json.loads(out)
    except (json.JSONDecodeError, TypeError):
        return out


def line(call: dict) -> str:
    name, a, out = call["name"], args(call), output(call)
    text = out if isinstance(out, str) else ""
    if name == "classify_request":
        return f"classify: {a.get('verdict')}" + (f" -> REFUSED: {text[:140]}" if "hard by the comparison" in text else "")
    if name == "submit_plan":
        steps = ", ".join(f"{s.get('tool')}{'/' + s['model'] if s.get('model') else ''}" for s in a.get("steps", []))
        if isinstance(out, dict) and out.get("problems"):
            return f"submit_plan ({len(a.get('checklist', []))} lines; {steps}) -> {len(out['problems'])} problems: " + " | ".join(out["problems"])[:400]
        if isinstance(out, dict) and out.get("ask_user"):
            return f"submit_plan -> ask the user: {out['ask_user']}"
        if isinstance(out, dict) and out.get("ok"):
            return f"submit_plan ({len(a.get('checklist', []))} lines; {steps}) -> ok, notes: {', '.join(out.get('notes', {}))}"
        return f"submit_plan -> {str(out)[:200]}"
    if name == "review_plan":
        conflicts = [r for r in a.get("reviews", []) if r.get("conflict")]
        result = "approved" if isinstance(out, dict) and out.get("ok") else str(out)[:200]
        return f"review_plan ({len(a.get('reviews', []))} reviews, {len(conflicts)} conflicts: " + "; ".join(f"{r['note']}: {r.get('change', '')[:90]}" for r in conflicts) + f") -> {result}"
    if name == "final_check":
        return f"final_check -> {out.get('not_met') if isinstance(out, dict) else str(out)[:200]}"
    if name.startswith(("create_", "generate_", "edit_")) or name in ("join_videos", "get_last_frame", "join_production_clips", "plan_video_production"):
        token = "plan_token" in a
        model = a.get("model", "")
        secs = a.get("end_seconds", "")
        state = "refused" if "Refused" in str(out) else ("gates skipped" if "Gates skipped" in str(out) else ("error" if call.get("error") else "ran"))
        return f"{name} {model} {secs}s token={'yes' if token else 'no'} -> {state}"
    return name


def main() -> None:
    full = "--full" in sys.argv
    for name in [a for a in sys.argv[1:] if not a.startswith("--")]:
        print(f"\n=== {name}")
        for file in sorted((RESULTS / name).glob("*.json")):
            if file.name in ("uploads.json",) or file.name.endswith(".checks.json"):
                continue
            record = json.loads(file.read_text())
            if "turns" not in record:
                continue
            cs = calls(record)
            gates = [c["name"] for c in cs if c["name"] in GATES]
            print(f"-- {record.get('item', {}).get('id', file.stem) if isinstance(record.get('item'), dict) else file.stem}: {len(cs)} calls, gate steps {gates.count('submit_plan')} plans / "
                  f"{gates.count('review_plan')} reviews, spent {record.get('spent')}, {record.get('seconds')} s")
            for c in cs:
                if full or c["name"] not in ("wait_for_video_project", "get_video_project", "get_workflow_guide"):
                    print("   ", line(c))
            reply = record["turns"][-1].get("agent") or ""
            print("    reply:", reply[:300].replace("\n", " "))


if __name__ == "__main__":
    main()

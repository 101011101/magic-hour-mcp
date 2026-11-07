"""Score the vague-brief runs: did the call the assistant tried to make match what the user wanted?

Reads run records written by the agent repo's V2/bench/mcp/run.mjs (items V2/bench/mcp/intent/items, paid calls refused).
    python3 scripts/conversation_score.py NAME=dir [NAME=dir ...] [--json out.json]

For each item: the questions asked, whether plan_request was called, and one line for each value the user wanted:
    correct      the attempted call has the user's value
    wrong        the attempted call has another value (a guess)
    not settled  no call was attempted, or the call does not carry the value
The wanted values are what the user's answer sheet says (V4/tests/items/<id>.json, `answers`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# item: {value: wanted}. audio: True = the user wants sound, False = silent.
WANTED = {
    "IS01": {"aspect": "16:9"},
    "IS02": {"aspect": "1:1"},
    "IS03": {"aspect": "9:16", "words": ["Open Mic Night", "Friday 7pm", "The Blue Door"]},
    "IS04": {"aspect": "1:1", "words": ["20% OFF", "This weekend only"]},
    "IS05": {},
    "IS06": {},
    "IS07": {},   # trim: no MCP tool
    "IS08": {},   # which face: free text
    "IS09": {"seconds": 6, "audio": False},
    "IS10": {"aspect": "16:9", "seconds": 10, "audio": False},
    "IS11": {"aspect": "16:9"},
    "IV01": {"aspect": "9:16", "seconds": 10, "audio": True},
    "IV02": {"seconds": 6, "audio": False},   # the wanted square shape cannot be said to create_video_from_image
}
READ_ONLY = {"plan_request", "plan_video_production", "get_workflow_guide", "ping", "get_upload_urls", "list_saved_items",
             "get_account_info", "detect_faces", "get_face_detection_results", "upload_chatgpt_image"}


def attempted(record: dict) -> dict | None:
    """The last create or edit call the assistant tried: {name, args}."""
    tried = []
    for turn in record.get("turns", []):
        for a in turn.get("approvals", []):
            tried.append({"name": a["name"], "args": a.get("args") or {}})
        for c in turn.get("calls", []):
            if c["name"] not in READ_ONLY and not c["name"].startswith(("wait_for_", "fetch_", "get_")):
                args = c.get("arguments")
                tried.append({"name": c["name"], "args": json.loads(args) if isinstance(args, str) else (args or {})})
    return tried[-1] if tried else None


def score_item(item: str, record: dict) -> dict:
    turns = record.get("turns", [])
    asked = sum(1 for t in turns for d in t.get("dialog", []) if "question" in d.get("asked", []))
    planned = sum(1 for t in turns for c in t.get("calls", []) if c["name"] == "plan_request")
    call = attempted(record)
    values = {}
    for name, want in WANTED[item].items():
        if call is None:
            values[name] = "not settled"
            continue
        args = call["args"]
        if name == "aspect":
            got = args.get("aspect_ratio") or args.get("orientation")
            values[name] = "not settled" if got in (None, "auto") else "correct" if got == want else "wrong"
        elif name == "seconds":
            got = args.get("end_seconds")
            values[name] = "not settled" if got is None else "correct" if round(float(got)) == want else "wrong"
        elif name == "audio":
            values[name] = "correct" if bool(args.get("audio", False)) == want else "wrong"
        elif name == "words":
            squash = lambda text: "".join(ch for ch in text.lower() if ch.isalnum())  # "FRIDAY · 7 PM" matches "Friday 7pm"
            prompt = squash(json.dumps(args, ensure_ascii=False))
            values[name] = "correct" if all(squash(w) in prompt for w in want) else "wrong"
    return {"questions": asked, "plan_request_calls": planned, "tool": call["name"] if call else None, "values": values}


def main() -> None:
    args = [a for a in sys.argv[1:] if "=" in a]
    out = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    sides = {}
    for pair in args:
        name, folder = pair.split("=", 1)
        sides[name] = {}
        for item in WANTED:
            path = Path(folder) / f"{item}.json"
            sides[name][item] = score_item(item, json.loads(path.read_text())) if path.exists() else None
    print("item   " + "".join(f"{name:<44}" for name in sides))
    for item in WANTED:
        cells = []
        for name in sides:
            s = sides[name][item]
            if s is None:
                cells.append("no record")
                continue
            marks = " ".join(f"{k}:{'ok' if v == 'correct' else 'WRONG' if v == 'wrong' else '-'}" for k, v in s["values"].items())
            cells.append(f"q{s['questions']} plan{s['plan_request_calls']} {(s['tool'] or 'no call')[:22]} {marks}")
        print(f"{item:<7}" + "".join(f"{c:<44}" for c in cells))
    totals = {}
    for name, items in sides.items():
        flat = [v for s in items.values() if s for v in s["values"].values()]
        totals[name] = {
            "values": len(flat), "correct": flat.count("correct"), "wrong": flat.count("wrong"), "not_settled": flat.count("not settled"),
            "items_all_correct": sum(1 for i, s in items.items() if s and WANTED[i] and all(v == "correct" for v in s["values"].values())),
            "items_with_values": sum(1 for i in items if WANTED[i]),
            "items_that_asked": sum(1 for s in items.values() if s and s["questions"]),
            "items_that_planned": sum(1 for s in items.values() if s and s["plan_request_calls"]),
        }
        print(f"{name}: {json.dumps(totals[name])}")
    if out:
        Path(out).write_text(json.dumps({"sides": sides, "totals": totals}, indent=2))


if __name__ == "__main__":
    main()

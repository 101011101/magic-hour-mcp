#!/usr/bin/env python3
"""Checklist grader for fleet chats: the user's prompt, split into phrases and clauses, one check each.

    python scripts/checklist_grade.py <chat dir> [<chat dir> ...] [--model sonnet] [--force] [--new-checklist]

A chat dir is .../results/fleet/<tag>/<chatId>/ (chat.json, calls.jsonl, assets/). Read-only: nothing is written there.
Steps:
  1. checklist   every user turn split into phrases/clauses by a headless `claude -p` (no tools); one check per phrase, each
                 quoting its exact words. Cached in <out>/checklist.items.json and reused (--new-checklist rebuilds it).
  2. deliverable the files the assistant delivered: per turn, the files named in that turn's last `say` (fallback: the last
                 files that turn made); earlier turns' files stand unless a later turn used them as a source (then they are
                 shown as reference only). Helper output (voices_list previews, get_last_frame, detect_faces) never counts.
  3. measure     ffprobe/ffmpeg/Pillow facts: size, aspect, duration, audio, loudness, silence and black spans, picture
                 difference against a same-size video attachment.
  4. judge       a second `claude -p` (Read tool on a frames folder only) marks each check done / not_done / cannot_tell
                 with one line of evidence, and lists notes on what the checklist does not cover.
  5. output      Benchmark/checklist-grades/<tag>/<chatId>/checklist.json and checklist.md.
Score = done / (done + not_done); cannot_tell and superseded checks are left out of both and reported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_ROOT = REPO / "Benchmark" / "checklist-grades"
FIXTURES = Path(os.environ.get("CHECKLIST_FIXTURES", "/Users/william/mh-bench/V2/bench/v1/fixtures"))
_FF_DIR = REPO / ".venv/lib/python3.13/site-packages/static_ffmpeg/bin/darwin_arm64"
FFMPEG = os.environ.get("FFMPEG") or (str(_FF_DIR / "ffmpeg") if (_FF_DIR / "ffmpeg").exists() else "ffmpeg")
FFPROBE = os.environ.get("FFPROBE") or (str(_FF_DIR / "ffprobe") if (_FF_DIR / "ffprobe").exists() else "ffprobe")

IMG = re.compile(r"\.(png|jpe?g|webp)$", re.I)
VID = re.compile(r"\.(mp4|mov|webm)$", re.I)
AUD = re.compile(r"\.(mp3|wav|m4a|aac|ogg|flac)$", re.I)
# tools whose files are never a deliverable: previews, probes and uploads
HELPER_TOOLS = {"voices_list", "get_last_frame", "detect_faces", "get_face_detection_results", "upload_media",
                "upload_chatgpt_image", "upload_chatgpt_media", "plan_tool_call", "plan_request", "get_workflow_guide"}
HELPER_NAME = re.compile(r"voices_list|get_last_frame|detect_faces", re.I)
ASPECT_TOL_PCT = 3.0
NAMED_RATIOS = {"1:1": 1, "4:5": 4 / 5, "5:4": 5 / 4, "3:4": 3 / 4, "4:3": 4 / 3, "2:3": 2 / 3, "3:2": 3 / 2,
                "9:16": 9 / 16, "16:9": 16 / 9, "21:9": 21 / 9}


# ---------------------------------------------------------------- chat reading

def read_events(chat_dir: Path) -> list[dict]:
    out = []
    f = chat_dir / "calls.jsonl"
    if f.exists():
        for line in f.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def split_turns(events: list[dict]) -> list[list[dict]]:
    """Events grouped by user turn: turn 0 runs from the start, each `user` event starts the next."""
    turns: list[list[dict]] = [[]]
    for e in events:
        if e.get("type") == "user":
            turns.append([])
        else:
            turns[-1].append(e)
    return turns


def _strip_url(u: str) -> str:
    u = u.rstrip(").,;:!?]>*'\"")
    u = u.split("?", 1)[0].split("#", 1)[0]
    return re.sub(r"^https?://", "", u)


def _url_keys(u: str) -> set[str]:
    s = _strip_url(u)
    keys = {s}
    m = re.match(r"videos\.magichour\.ai/([A-Za-z0-9]+)/", s)
    if m:
        keys.add(m.group(1))
    return keys


def say_keys(text: str) -> tuple[set[str], int]:
    """Keys of every link in a reply, and how many links it has."""
    urls = re.findall(r"https?://[^\s)\]>\"']+", text or "")
    keys: set[str] = set()
    for u in urls:
        keys |= _url_keys(u)
    return keys, len({_strip_url(u) for u in urls})


def call_keys(e: dict) -> set[str]:
    """Identifiers of what a call produced: its project id, download links and saved paths."""
    keys: set[str] = set()
    out = e.get("output")
    try:
        data = json.loads(out) if isinstance(out, str) else out
    except (json.JSONDecodeError, TypeError):
        data = None

    def walk(v, top=False):
        if isinstance(v, dict):
            for k, x in v.items():
                if top and k == "id" and isinstance(x, str):
                    keys.add(x)
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, str):
            if v.startswith("http"):
                keys.update(_url_keys(v))
            elif v.startswith("api-assets/"):
                keys.add(v)
    walk(data, top=True)
    if isinstance(out, str) and data is None:
        for u in re.findall(r"https?://[^\s\"']+", out):
            keys |= _url_keys(u)
    if str(e.get("tool", "")).startswith("wait_for") and isinstance((e.get("args") or {}).get("id"), str):
        keys.add(e["args"]["id"])
    return keys


def turn_deliverables(turn: list[dict], chat_dir: Path) -> tuple[list[dict], str]:
    """The files one turn delivered, and how they were found."""
    cands = []
    for e in turn:
        if e.get("type") != "call" or e.get("tool") in HELPER_TOOLS:
            continue
        keys = call_keys(e)
        for f in e.get("files") or []:
            p = chat_dir / f
            if HELPER_NAME.search(f) or not p.exists() or p.stat().st_size < 500:
                continue
            cands.append({"path": str(p), "name": p.name, "tool": e.get("tool"), "keys": keys})
    if not cands:
        return [], "no file made in this turn"
    says = [e for e in turn if e.get("type") == "say"]
    text = says[-1].get("text", "") if says else ""
    skeys, n_links = say_keys(text)
    named = [c for c in cands if c["keys"] & skeys]
    if named:
        # one entry per call output (a file saved twice under different names stays once)
        return named, "named in the final reply"
    n = max(1, n_links)
    return cands[-n:], f"fallback: last {n} file(s) made in the turn (no link in the reply matched)"


def select_deliverables(chat_dir: Path) -> dict:
    """Final deliverable of the whole chat: the last turn's files plus earlier turns' files that a later turn did not
    use as a source. Earlier files that were reworked come back as reference (shown to the judge, never judged)."""
    chat_dir = Path(chat_dir)
    turns = split_turns(read_events(chat_dir))
    per_turn = [turn_deliverables(t, chat_dir) for t in turns]
    final, reference, how = [], [], []
    for i, (files, method) in enumerate(per_turn):
        how.append({"turn": i + 1, "method": method, "files": [f["name"] for f in files]})
        later_args = json.dumps([e.get("args") for t in turns[i + 1:] for e in t if e.get("type") == "call"])
        for f in files:
            item = {"path": f["path"], "name": f["name"], "tool": f["tool"], "turn": i + 1}
            reworked = i < len(turns) - 1 and any(k and k in later_args for k in f["keys"])
            (reference if reworked else final).append(item)
    if not final and reference:   # a later turn only re-used earlier files and made nothing new: they stand
        final, reference = reference, []
    return {"final": final, "reference": reference, "turns": how}


# ---------------------------------------------------------------- measuring

def _run(args: list[str], timeout=120) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return str(exc)


def nearest_ratio(w: int, h: int) -> dict:
    r = w / h
    name, val = min(NAMED_RATIOS.items(), key=lambda kv: abs(r / kv[1] - 1))
    frac = Fraction(w, h)
    off = round(abs(r / val - 1) * 100, 1)
    # generators round sides to multiples of 16/32 (352x640 for 9:16): within 3% counts as that shape
    return {"exact": f"{frac.numerator}:{frac.denominator}", "nearest": name, "off_pct": off, "counts_as_nearest": off <= ASPECT_TOL_PCT}


def probe(path: str) -> dict:
    out = _run([FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", path])
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


def _spans(text: str, start_key: str, end_key: str) -> list[list[float]]:
    starts = [float(x) for x in re.findall(start_key + r":\s*(-?[\d.]+)", text)]
    ends = [float(x) for x in re.findall(end_key + r":\s*(-?[\d.]+)", text)]
    return [[round(s, 2), round(e, 2)] for s, e in zip(starts, ends)]


def audio_facts(path: str, duration: float | None) -> dict:
    vd = _run([FFMPEG, "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "volumedetect", "-f", "null", "-"])
    mean = re.search(r"mean_volume:\s*(-?[\d.]+|-inf)", vd)
    peak = re.search(r"max_volume:\s*(-?[\d.]+|-inf)", vd)
    sd = _run([FFMPEG, "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "silencedetect=noise=-45dB:d=0.5", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", sd)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*(-?[\d.]+)", sd)]
    if len(ends) < len(starts) and duration:
        ends.append(duration)   # silence that runs to the end
    f = lambda m: (None if m.group(1) == "-inf" else float(m.group(1))) if m else None
    peak_db = f(peak)
    return {"mean_db": f(mean), "peak_db": peak_db, "audible": peak_db is not None and peak_db > -45,
            "silence_spans_s": [[round(s, 2), round(e, 2)] for s, e in zip(starts, ends)]}


def measure(path: str) -> dict:
    """Facts about one media file, all from code."""
    p = str(path)
    facts: dict = {"file": Path(p).name}
    if IMG.search(p):
        from PIL import Image
        with Image.open(p) as im:
            w, h = im.size
            facts.update(kind="image", width=w, height=h, mode=im.mode)
        facts["aspect"] = nearest_ratio(w, h)
        facts["orientation"] = "square" if w == h else ("landscape" if w > h else "portrait")
        return facts
    info = probe(p)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic") != 1), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    try:
        dur = round(float(info.get("format", {}).get("duration")), 2)
    except (TypeError, ValueError):
        dur = None
    facts["duration_s"] = dur
    if v:
        w, h = int(v["width"]), int(v["height"])
        try:
            fps = round(float(Fraction(v.get("avg_frame_rate", "0/1"))), 2)
        except (ZeroDivisionError, ValueError):
            fps = None
        facts.update(kind="video", width=w, height=h, fps=fps, aspect=nearest_ratio(w, h),
                     orientation="square" if w == h else ("landscape" if w > h else "portrait"))
        bd = _run([FFMPEG, "-hide_banner", "-nostats", "-i", p, "-vf", "blackdetect=d=0.3:pic_th=0.98", "-an", "-f", "null", "-"])
        facts["black_spans_s"] = _spans(bd, "black_start", "black_end")
    else:
        facts["kind"] = "audio"
    facts["has_audio_track"] = a is not None
    if a is not None:
        facts["audio"] = audio_facts(p, dur)
    return facts


def frame_at(src: str, out: Path, at: float | None = None) -> Path | None:
    args = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + (["-ss", f"{at:.3f}"] if at is not None else []) + \
           ["-i", src, "-frames:v", "1", "-vf", "scale='min(1024,iw)':-2", "-q:v", "3", str(out)]
    _run(args)
    return out if out.exists() and out.stat().st_size > 0 else None


def picture_diff(a: str, b: str, da: float, db: float, tmp: Path) -> dict | None:
    """Mean absolute pixel difference (0-255) between two same-size videos at matching times."""
    from PIL import Image, ImageChops, ImageStat
    d = min(da, db)
    vals = []
    for i, fr in enumerate((0.1, 0.5, 0.9)):
        fa, fb = frame_at(a, tmp / f"_da{i}.png", d * fr), frame_at(b, tmp / f"_db{i}.png", d * fr)
        if not (fa and fb):
            continue
        with Image.open(fa) as ia, Image.open(fb) as ib:
            if ia.size != ib.size:
                return None
            vals.append(round(sum(ImageStat.Stat(ImageChops.difference(ia.convert("RGB"), ib.convert("RGB"))).mean) / 3, 1))
        fa.unlink(); fb.unlink()
    return {"mean_abs_diff_at_10_50_90pct": vals} if vals else None


# ---------------------------------------------------------------- score

def score(results: list[dict], checks: list[dict]) -> dict:
    live = {c["id"] for c in checks if not c.get("superseded_by")}
    v = [r["verdict"] for r in results if r["id"] in live]
    done, notd, ct = v.count("done"), v.count("not_done"), v.count("cannot_tell")
    judged = done + notd
    return {"done": done, "not_done": notd, "cannot_tell": ct, "superseded": len(checks) - len(live),
            "judged": judged, "score": round(done / judged, 3) if judged else None}


# ---------------------------------------------------------------- claude -p

def claude(prompt: str, system: str, schema: dict, *, model: str, bin_: str, cwd: Path, read_dir: Path | None = None,
           effort: str = "medium", timeout: int = 600) -> dict:
    tools = ["--tools", "Read", "--allowedTools", f"Read({read_dir}/**)", "--permission-mode", "dontAsk"] if read_dir else ["--tools", ""]
    args = [bin_, "-p", prompt, "--model", model, "--output-format", "json", "--json-schema", json.dumps(schema),
            "--system-prompt", system, *tools, "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--disable-slash-commands", "--no-session-persistence", "--effort", effort, "--setting-sources", "project"]
    last = ""
    for attempt in range(1, 4):   # infrastructure retries only
        try:
            r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
            j = json.loads(r.stdout.strip())
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            j, last = None, str(exc)[:300]
        if j and not j.get("is_error") and j.get("structured_output"):
            return {"out": j["structured_output"], "usd": j.get("total_cost_usd")}
        if j:
            last = str(j.get("result") or j)[:300]
        time.sleep(5 * attempt)
    raise RuntimeError(f"claude -p failed: {last}")


CHECKLIST_SCHEMA = {"type": "object", "properties": {"checks": {"type": "array", "items": {"type": "object", "properties": {
    "turn": {"type": "integer"}, "quote": {"type": "string"}, "check": {"type": "string"},
    "superseded_by_turn": {"type": ["integer", "null"]}}, "required": ["turn", "quote", "check", "superseded_by_turn"],
    "additionalProperties": False}}}, "required": ["checks"], "additionalProperties": False}

CHECKLIST_SYSTEM = "You turn a user's request into a checklist. Answer only with the requested JSON."


def checklist_prompt(turns: list[dict]) -> str:
    body = "\n".join(f"TURN {i + 1}: {t['text']}" + (f"\n  (attached: {', '.join(t['materials'])})" if t.get("materials") else "")
                     for i, t in enumerate(turns))
    return f"""Split the user's request below into a checklist. The user states clearly what they want: their words are the spec.

Rules:
- Go through every turn, phrase by phrase and clause by clause. Each phrase or clause that asks for something becomes exactly one check.
- Do not merge two phrases into one check. A list of separate items (e.g. three sizes, three quoted wordings) gives one check per item.
- Do not invent requirements and do not add checks for things the user did not say (no quality, style or "looks good" checks of your own).
- Words that ask for nothing (greetings, "Nice", "actually") get no check.
- quote: the exact words from the turn, copied character for character (a contiguous span of that turn's text).
- check: one plain sentence saying what must be true of the final delivered file(s) for this phrase to be done.
- A later turn overrides an earlier one where they conflict. If a later turn fully replaces an earlier phrase, keep the earlier check and set superseded_by_turn to the later turn's number. If it changes it only in part (e.g. for one of several items), keep it with superseded_by_turn null and say in the check which items it still applies to. Otherwise superseded_by_turn is null.
- Keep the checks in the order the phrases appear.

THE USER'S TURNS:
{body}"""


JUDGE_SCHEMA = {"type": "object", "properties": {
    "results": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "string"}, "verdict": {"type": "string", "enum": ["done", "not_done", "cannot_tell"]},
        "evidence": {"type": "string"}}, "required": ["id", "verdict", "evidence"], "additionalProperties": False}},
    "notes": {"type": "array", "items": {"type": "object", "properties": {
        "kind": {"type": "string", "enum": ["quality", "extra_change", "fault", "other"]},
        "severity": {"type": "string", "enum": ["minor", "major"]}, "what": {"type": "string"}},
        "required": ["kind", "severity", "what"], "additionalProperties": False}}},
    "required": ["results", "notes"], "additionalProperties": False}

JUDGE_SYSTEM = ("You are a strict, fair checker of an AI media assistant's delivered files. Open every image file you are "
                "given with the Read tool before judging. Judge only what you can see or what the measured facts show. "
                "Answer only with the requested JSON.")


def judge_prompt(turns, checks, legend, facts, final_reply) -> str:
    convo = "\n".join(f"USER TURN {i + 1}: {t['text']}" for i, t in enumerate(turns))
    cl = "\n".join(f"- {c['id']} (turn {c['turn']}{', SUPERSEDED by turn ' + str(c['superseded_by']) if c.get('superseded_by') else ''}): "
                   f"\"{c['quote']}\" -> {c['check']}" for c in checks)
    return f"""Check an AI assistant's FINAL deliverable against the user's request, one checklist item at a time.

THE USER'S TURNS (the final answer must satisfy every turn; later turns override earlier ones where they conflict):
{convo}

THE ASSISTANT'S LAST REPLY (its own claims; do not trust them, check against the files):
{final_reply[:1500]}

IMAGES, in order (open each one with the Read tool):
{chr(10).join(legend)}

MEASURED FACTS (from ffprobe/ffmpeg/Pillow; trust these over what you estimate by eye):
{json.dumps(facts, indent=1)}

CHECKLIST:
{cl}

For every checklist id give a verdict:
- done: the final deliverable clearly does what the phrase asks.
- not_done: it does not, or only partly.
- cannot_tell: it cannot be judged from the frames and the facts. You cannot hear audio: for what sound says or how it sounds (mood, clarity of words, music style) use cannot_tell unless the measured facts settle it (e.g. no audio track at all, or silence).
Aspect: a file whose aspect.counts_as_nearest is true IS that named shape (generators round sides to multiples of 16 or 32).
Judge only the FINAL deliverable files. Reference files are earlier versions, for comparison only (e.g. "keep the same art"). SUPERSEDED checks: still give a verdict but it is not counted.
evidence: one line, naming what you saw or which fact you used.

Then notes: anything the checklist does not cover that a client would care about: quality problems (garbled or misspelled text, warped objects or faces, artefacts), extra changes nobody asked for, faults (wrong file, missing file, broken clip). Empty list if none."""


# ---------------------------------------------------------------- grading one chat

def grade(chat_dir: Path, model: str, force: bool, new_checklist: bool) -> dict | None:
    chat_dir = Path(chat_dir).resolve()
    chat = json.loads((chat_dir / "chat.json").read_text())
    tag, cid = chat.get("tag") or chat_dir.parent.name, chat.get("chatId") or chat_dir.name
    out_dir = OUT_ROOT / tag / cid
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / "checklist.json").exists() and not force:
        print(f"{cid}: already graded (use --force)")
        return None
    bin_ = chat.get("claude_bin") or "claude"
    if not Path(bin_).exists():
        bin_ = "claude"
    turns = [{"text": m.get("text", ""), "materials": m.get("materials") or []} for m in chat.get("messages", [])]
    t0 = time.time()
    usd = 0.0

    # 1. checklist (cached)
    key = hashlib.sha256(json.dumps(turns, sort_keys=True).encode()).hexdigest()[:16]
    # one checklist per case, shared by every run of it, so runs are scored against the same checks (the same case got
    # 6 checks in one run and 3 in another when each run built its own)
    shared = OUT_ROOT / "_checklists" / f"{chat.get('item') or cid}.json"
    shared.parent.mkdir(parents=True, exist_ok=True)
    cache = shared
    cached = json.loads(cache.read_text()) if cache.exists() else None
    if cached and cached.get("key") == key and not new_checklist:
        checks = cached["checks"]
    else:
        r = claude(checklist_prompt(turns), CHECKLIST_SYSTEM, CHECKLIST_SCHEMA, model=model, bin_=bin_, cwd=out_dir, effort="low")
        usd += r["usd"] or 0
        checks = []
        for i, c in enumerate(r["out"]["checks"]):
            src = turns[c["turn"] - 1]["text"] if 1 <= c["turn"] <= len(turns) else ""
            norm = lambda s: re.sub(r"\s+", " ", s.replace("’", "'").replace("“", '"').replace("”", '"')).strip().lower()
            checks.append({"id": f"C{i + 1}", "turn": c["turn"], "quote": c["quote"], "check": c["check"],
                           "superseded_by": c.get("superseded_by_turn"), "quote_found": norm(c["quote"]) in norm(src)})
        cache.write_text(json.dumps({"key": key, "model": model, "checks": checks}, indent=1))
    (out_dir / "checklist.items.json").write_text(json.dumps({"key": key, "shared": str(shared), "checks": checks}, indent=1))

    # 2. deliverable
    sel = select_deliverables(chat_dir)
    events = read_events(chat_dir)
    says = [e for e in events if e.get("type") == "say"]
    final_reply = says[-1].get("text", "") if says else ""

    # 3. measure + frames
    fdir = out_dir / "frames"
    fdir.mkdir(exist_ok=True)
    for old in fdir.glob("*"):
        old.unlink()
    legend, facts = [], {"final_deliverable": [], "reference_earlier_versions": [], "user_attachments": []}

    def add_frames(path: str, label: str, n_video: int):
        m = measure(path)
        if m.get("kind") == "image":
            o = frame_at(path, fdir / f"{len(legend) + 1:02d}.jpg")
            if o:
                legend.append(f"image {len(legend) + 1} ({o}): {label}, {m['width']}x{m['height']}")
        elif m.get("kind") == "video" and m.get("duration_s"):
            d = m["duration_s"]
            fracs = [0.02, 0.35, 0.65, 0.97][:n_video] if n_video >= 4 else [0.1, 0.5, 0.9][:n_video]
            for fr in fracs:
                o = frame_at(path, fdir / f"{len(legend) + 1:02d}.jpg", d * fr)
                if o:
                    legend.append(f"image {len(legend) + 1} ({o}): {label}, frame at {d * fr:.1f} s of {d} s")
        return m

    atts = []
    for t in turns:
        for name in t["materials"]:
            p = FIXTURES / name
            if p.exists() and str(p) not in atts:
                atts.append(str(p))
    for a in atts:
        facts["user_attachments"].append(add_frames(a, f"USER ATTACHMENT {Path(a).name}", 3))
    for f in sel["reference"]:
        m = add_frames(f["path"], f"REFERENCE ONLY, earlier version from turn {f['turn']} ({f['name']}), reworked later", 3)
        facts["reference_earlier_versions"].append(m)
    for f in sel["final"]:
        m = add_frames(f["path"], f"FINAL DELIVERABLE {f['name']} (turn {f['turn']}, {f['tool']})", 4)
        if m.get("kind") == "video":
            for a, am in zip(atts, facts["user_attachments"]):
                if am.get("kind") == "video" and (am.get("width"), am.get("height")) == (m["width"], m["height"]):
                    diff = picture_diff(f["path"], a, m["duration_s"], am["duration_s"], fdir)
                    if diff:
                        m.setdefault("picture_vs_attachment", {})[Path(a).name] = diff
        facts["final_deliverable"].append(m)

    # 4. judge
    judged = {"results": [], "notes": []}
    error = None
    if not sel["final"]:
        judged["results"] = [{"id": c["id"], "verdict": "not_done", "evidence": "no file was delivered"} for c in checks]
        judged["notes"] = [{"kind": "fault", "severity": "major", "what": "the assistant delivered no file"}]
    else:
        try:
            r = claude(judge_prompt(turns, checks, legend, facts, final_reply), JUDGE_SYSTEM, JUDGE_SCHEMA,
                       model=model, bin_=bin_, cwd=fdir, read_dir=fdir)
            usd += r["usd"] or 0
            judged = r["out"]
        except RuntimeError as exc:
            error = str(exc)
    by_id = {r["id"]: r for r in judged["results"]}
    results = [by_id.get(c["id"], {"id": c["id"], "verdict": "cannot_tell", "evidence": "judge gave no verdict"}) for c in checks]

    # 5. output
    res = {"chatId": cid, "tag": tag, "chat_dir": str(chat_dir), "judge_model": model, "turns": turns,
           "deliverable": sel, "facts": facts, "checks": [{**c, **{k: by_id.get(c["id"], {}).get(k) for k in ("verdict", "evidence")}} for c in checks],
           "notes": judged["notes"], "score": score(results, checks), "usd": round(usd, 4),
           "seconds": round(time.time() - t0), "error": error}
    for c in res["checks"]:
        c["verdict"] = c["verdict"] or "cannot_tell"
    (out_dir / "checklist.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    (out_dir / "checklist.md").write_text(to_markdown(res))
    s = res["score"]
    print(f"{cid}: {s['done']}/{s['judged']} done ({s['score']}), cannot tell {s['cannot_tell']}, superseded {s['superseded']}"
          f", {len(res['notes'])} note(s), {res['seconds']} s{' ERROR ' + error if error else ''}")
    return res


MARK = {"done": "[x]", "not_done": "[ ]", "cannot_tell": "[?]"}


def to_markdown(res: dict) -> str:
    s = res["score"]
    L = [f"# {res['chatId']}", ""]
    for i, t in enumerate(res["turns"]):
        L.append(f"> **Turn {i + 1}:** {t['text']}" + (f" _(attached: {', '.join(t['materials'])})_" if t["materials"] else ""))
        L.append(">")
    L += ["", "**Deliverable:** " + (", ".join(f"`{f['name']}`" for f in res["deliverable"]["final"]) or "none")]
    if res["deliverable"]["reference"]:
        L.append("**Reference only (reworked later):** " + ", ".join(f"`{f['name']}`" for f in res["deliverable"]["reference"]))
    score_txt = f"{s['done']}/{s['judged']} = {s['score']:.0%}" if s["score"] is not None else "n/a"
    L += ["", f"**Score:** {score_txt} (cannot tell: {s['cannot_tell']}, superseded: {s['superseded']})", "", "## Checklist", ""]
    for c in res["checks"]:
        sup = f" ~~superseded by turn {c['superseded_by']}~~" if c.get("superseded_by") else ""
        warn = "" if c.get("quote_found", True) else " (quote not found verbatim)"
        L.append(f"- {MARK[c['verdict']]} **{c['id']}** \"{c['quote']}\"{warn}{sup}: {c['check']}  \n  _{c.get('evidence') or ''}_")
    L += ["", "## Notes (not covered by the checklist)", ""]
    L += [f"- **{n['severity']} {n['kind']}:** {n['what']}" for n in res["notes"]] or ["- none"]
    if res.get("error"):
        L += ["", f"**Judge error:** {res['error']}"]
    L += ["", "## Measured facts", "", "```json", json.dumps(res["facts"], indent=1), "```", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("chat_dirs", nargs="+")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--force", action="store_true", help="grade again (the cached checklist is reused)")
    ap.add_argument("--new-checklist", action="store_true", help="rebuild the cached checklist too")
    a = ap.parse_args(argv)
    bad = 0
    for d in a.chat_dirs:
        try:
            grade(Path(d), a.model, a.force or a.new_checklist, a.new_checklist)
        except Exception as exc:  # keep going over the other chats
            bad += 1
            print(f"{d}: FAILED {exc}", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

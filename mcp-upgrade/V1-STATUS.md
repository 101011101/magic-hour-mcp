# V1 status and how to compare it (5 November 2026)

- Purpose: a second agent runs the same items on 3 sides and compares time, quality and cost.
- Sides: **old** (the MCP at `https://mcp.magichour.ai/`), **v1** (the modified MCP, a local build), **Replicate** (its plugin).
- Nothing is committed. Nothing is deployed. V1 code is in the working tree of the two repos.
- Repos: MCP `/Users/ray/Coding/magic-hour-mcp`. Agent and harness `/Users/ray/Coding/magic-agent-video-generator`.
- More detail: `tickets/TICKETS.md` (done / to do), `prd/MCP-01-conversation.md`, `/Users/ray/Coding/magic-hour-mcp/Benchmark/upgrade.html` (results page).

## What v1 is

- `plan_request` (`mcp_magichour/plan_request.py`): the host model fills a parameter sheet. Server code checks it against the user's words. It returns 0 to 3 fixed questions. No model on the server.
- `plan_video_production` (`mcp_magichour/video_production.py`, `video_production_tool.py`): the host writes a story as beats. Server code splits it into clips, gives each clip one reference, writes the prompts, returns the rounds.
- `create_production_clip`: makes one clip of the plan. Reference: a picture, its own still, or the last frame of an earlier clip.
- `join_production_clips` (`mcp_magichour/media_tools.py`): joins the clips in story order. Needs ffmpeg on the server. Returns a local link (`/films/<name>.mp4`).
- Split rule (strategy `person`, limit 15 s)
  - Ideas first. The same person is an idea.
  - An idea stays in one clip while it fits: 15 s, or 30 s for a person with a picture.
  - A pictured person who enters a scene gets a new clip with their picture.
  - An idea that is cut is chained: the next clip starts from the last frame of the last clip that showed the person.
  - A card is always its own clip.
- Models: `ltx-2.5` (no reference, or a start frame), `minimax-h3` (a named picture), `qwen-image-2.1` (card still). 480p. 24 credits for each second.
- Tests: `.venv/bin/python -m pytest tests -q` gives 169 passed, 3 failed. The 3 need the web frontend build (`npm --prefix web run build`). They failed before v1.

## Results so far (one run for each, checklist = yes / partly / no)

| Item | Old MCP | V1 | Replicate |
|---|---|---|---|
| A1 product spot, 15 s | 103 s · 370 credits · 4 / 2 / 0 | 228 s · 370 credits · 3 / 2 / 1 (1 question; silent) | paid: 288 s · 2 / 3 / 1 (parts only) |
| A2 invented character, 12 s | 62 s · 288 credits · 4 / 0 / 1 | 112 s · 288 credits · 4 / 0 / 1 | free model: 201 s · 3 / 1 / 1. Paid model: 70 s · 4 / 0 / 1 |
| A3 continue a clip, 12 s | 136 s · 288 credits · 5 / 0 / 2 (after a nudge) | 177 s · 288 credits · 3 / 1 / 3 (after a nudge) | paid: 155 s · about $0.54 · 4 / 0 / 3 |
| A4 branded explainer, 15 s | 228 s · 360 credits · 4 / 1 / 0 (after a nudge) | 345 s · 422 credits · 4 / 1 / 0 (after a nudge) | paid: 250 s · 4 / 0 / 1 |
| B1 product spot, 30 s | 221 s · 720 credits · 2 / 6 / 2 (10 lines). Picture lines only (5): 0 / 4 / 1 | 417 s · 730 credits · 4 / 1 / 0 (5 picture lines; silent). All 10 lines: 6 / 1 / 3 | not run (see Rules) |
| B2 fiction short, 30 s | 151 s · 720 credits · 3 / 3 / 1 | 181 s · 672 credits · 5 / 1 / 1 | paid: 327 s · 2 / 3 / 2 (parts only; the credit ended) |
| 13 vague briefs | 9 of 17 values correct · a question on 3 of 13 | 16 of 17 · a question on 11 of 13 | not run |

- Time = the whole request, from the brief to the reply, driver included.
- Old MCP records: `V2/bench/v1/results/mcp-dense-1b` (B1), `mcp-dense-2-<item>`. Pages: `Benchmark/index.html`.
- V1 records: `V2/bench/v1/results/mcp-mod-3` (B1, B2), `mcp-mod-4-<item>` (A1 to A4, same caps as the old MCP runs). Films: `Benchmark/modified/<item>/<run>/`.
- Replicate records: `V2/bench/v1/results/comp-c1-replicate` (free), `comp-c2-replicate` (A2), `comp-c3-replicate` (A3), `comp-c4-replicate` (A1, A4), `comp-c5-replicate` (B2) (paid).
- V1 faults seen: B2: the spoken line is not said. B1: no voice-over, captions or music (no tool). The host declined B1 one time and made it the next time.
  - A1: silent. The host asked about music; the user said go ahead; the join then muted all clips.
  - A2: no words on the picture. The fixed prompt line "no title cards, no captions" is against the words the brief wants.
  - A3: the new tools were not used. All 12 s regenerated. `plan_request` set 9:16; the clip is 1:1. Music with audio off.
  - A4: the colour code is printed in the picture (the `setting` text goes into each prompt). `add_subtitles_to_video` refused the local film link; the host put captions on each clip, then joined again.
  - A2, A4: `create_production_clip` was called 1 time with no `production` value, then called again correctly.

## How to run

- Driver for all sides: `gpt-6.1-sol`, medium effort. Keys: `.env` in the two repos. Do not print them.
- Items: `V2/bench/mcp/dense/items/` (A1 to A4, B1, B2). Vague briefs: `V2/bench/mcp/intent/items/` (group I).
- **V1**
  - Start: `cd /Users/ray/Coding/magic-hour-mcp && MAGIC_HOUR_MCP_PUBLIC_URL=http://127.0.0.1:8765 MAGIC_HOUR_FILMS_DIR=<folder> .venv/bin/python -m uvicorn mcp_magichour.server:app --host 127.0.0.1 --port 8765`
  - Run: `cd /Users/ray/Coding/magic-agent-video-generator && node V2/bench/mcp/run.mjs --items V2/bench/mcp/dense/items --only <id> --local --mcp-url http://127.0.0.1:8765/ --out V2/bench/v1/results/<folder> --prefix <p> --item-cap 800 --cap 800 --concurrency 1`
  - Port 8000 is in use on this machine. Use 8765.
  - Stop the server after the runs: `kill $(lsof -ti :8765 -sTCP:LISTEN)`.
- **Old MCP**
  - Hosted: the same command without `--local` and `--mcp-url`.
  - Or the same day on the local build: add `--hide plan_request,plan_video_production,create_production_clip,join_production_clips`.
  - Default `--item-cap` is 400. A 30 s item costs 720: use 800.
- **Vague briefs**: `--items V2/bench/mcp/intent/items --groups I --item-cap 0 --concurrency 3`. Every paid call is refused. 0 credits. Score: `python3 scripts/conversation_score.py name=<results folder> ...` (in the MCP repo).
- **Replicate**
  - `node V2/bench/mcp/competitors/run.mjs --server replicate --profile bench_paid --only <id> --prefix <p> --budget <seconds of video>`. Add `--dry` first.
  - Sign-in state: `node V2/bench/mcp/competitors/login.mjs --status`.
  - Free model: `minimax/video-01` (6 s clips). Paid, matched model: `lightricks/ltx-2.5-fast` at 720p.
  - Price: about $0.09 for each second. Not confirmed. The account had about $0.05 on 5 November: it needs money before a paid run.
- Output files: `V2/sessions/<session>/assets/`. V1's joined film is the file named `…-join_production_clips.mp4`.

## How to compare

- **Time**: `seconds` in each record (whole request).
- **Cost**: ours in credits (`spent` in the record; check against the account balance). 24 credits for each second is about $0.04 at $19 for 12,000 credits. Replicate in dollars: its balance before and after the run.
- **Quality**: the item's checklist, one line for each thing the user wanted.
  - File: `<id>.checks.json` beside the record, or `checks.json` beside the film: `{ "by": "...", "checks": [{ "want", "got", "result": "yes|partly|no" }] }`.
  - Use the same lines for all sides. The lines for each item are in the old MCP's checks files.
  - Evidence: `node V2/bench/mcp/dense/measure.mjs <video> --out <folder> [--hex #RRGGBB]` (size, length, cuts, cards, transcript, what `gpt-audio` hears).
  - Frames: its sheet is wrong for 9:16 video. Take frames with `ffmpeg -ss <t> -i film.mp4 -frames:v 1`, 2 for each second, and look at them.
  - Scores to now are by eye, one run for each film. Say so in the result.
- **Report, 3 sides, all items**: `python3 scripts/compare_page.py` writes `Benchmark/report.html`. Its two lists are in `Benchmark/report-notes.json`. For B1 it reads `checks-report.json` (10 lines).
- **Page**: `python3 scripts/upgrade_page.py` writes `Benchmark/upgrade.html`. A v1 film is shown if `Benchmark/modified/<item>/<run>/` has `film.mp4`, `film.poster.jpg`, `side.json`, `checks.json`.

## Rules

- Before a paid run: give the expected cost and the limit as 2 numbers. The cap moves only on the user's word.
- One attempt for each item on each side. No retries. A failed step is a failed case.
- B1 uses a stock photo of a real person. Do not send it to Replicate without the user's word. Keep that output off shared pages.
- Replicate takes reference files only as public links. Where to host them is the user's decision.
- `Benchmark/` is not tracked by git. Do not run `git stash -u` during a run.
- Video on a page: use a poster picture. Do not use `#t=` on the video address (the film then starts late).
- Do not commit unless the user asks.

## Open

- Not run: B1 on Replicate. The vague briefs on Replicate. A1 and B2 on Replicate are parts only: a rerun needs the user's word and credit.
- V1 is not better than the old MCP on A1 to A4, and is slower on all 6 items.
- Todo list from the request, checked at the end (user, 2026-11-05). Decisions open: check only or also fix; join only or all videos.
- V1 needs ffmpeg on the server and a place to store the joined film (ticket MCP-06).
- No voice-over, captions or music on a multi-clip film (ticket MCP-08).
- "A short clip" is read as 8 s and not asked. Decision necessary.
- The server instructions do not name the new tools. The host found them from the tool descriptions in all runs.
- Clips of one round can be made at the same time. The host made them one after the other in 2 of 3 runs.

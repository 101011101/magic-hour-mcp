# Tickets

- One line for each ticket. Details are in the ticket file, if there is one.
- "Proposed" = not from the user. Confirm or delete.
- Nothing is committed. Nothing is deployed.
- Updated: 2026-11-13.

## To do

### Tool management (user, 2026-11-13)

A separate workflow. Changes no video composition file ([rule](../prd/tool-management/README.md#isolation)).

Order (user, 2026-11-13): first make the existing tools very good (MCP-21 to MCP-24). Then new tools (MCP-29 to MCP-35), then tool composition (MCP-25 to MCP-28).

Tool priority (user, 2026-11-14, after reviewing the results page): generation tools first, because they cover more cases; deterministic code tools last, only when generation cannot do the job or the media must stay exactly as it is. Fewest tool calls. Words that are part of a designed picture (headline, poster, logo, thumbnail, slide, card) go in the generation prompt; add_words_to_media only for captions or overlays on existing media (B11a is right). A picture's new shape: extend it with edit_image first, reframe_media as the fallback (B12b). Done in the sheets, notes and planner rules; to re-test: A02a, A02b, A02d, A03a, A06a, A06b, G33b, G34a, G37a, J49b, B12b. Also fixed: adjust_colours warmth was too weak (B07c barely changed: red +4, blue −7); side by side filled white space (G35a): cells now filled with a blurred copy of the picture, bold label bands, labels optional.
  - [x] 2026-11-14 · Re-tested (run wgen, 410 credits, checklist grader): pass rate 96% before and after; fewer calls; all generated words spelled right (qwen-image-2.1). Better: G33b. Weaker: sets made of separate generations (G34a, G37a) and exact follow-up edits (J49b). [Results](../prd/tool-management/tool-tests.md).
  - [x] 2026-11-14 · Sets fixed (run wset, 350 credits): one master, the rest made from it; G34a 8/8, G37a 14/14, G36a 11/11. Exact edit J49b 9/11: the host skipped the compare-and-fall-back step. Open.

#### 1. Existing tools

- [ ] **MCP-19 · Clean up the tool-management PRD.** [PRD](../prd/tool-management/README.md).
  - [x] 2026-11-13 · Flow (predict the family, fill the sheet, ask what is open, return tool + notes), the two sheets, the isolation rule. "How they meet" in ARCHITECTURE corrected: `plan_request` no longer sends edits to tool management.
  - [ ] Decide: the planner's name (`plan_tool_call` proposed).
  - [x] 2026-11-13 · Decided (user): missing tools are tool-management tickets (MCP-29 to MCP-35), after the existing tools are good.
- [ ] **MCP-20 · Failure list.** Each tool-management item: old against new, better / same / worse, tool called against the right tool, the failure. From the existing runs (`Benchmark/audit`, `Benchmark/personas`, MCP-17's failure modes), 0 credits. Then the user's notes. [List](../prd/tool-management/failures.md).
  - [x] 2026-11-13 · Scored from the audit page: 118 cases, 41 better · 33 same · 32 worse · 12 not run live. 10 patterns proposed (most low scores: no tool does the job, not a wrong pick). Next: the user's notes and the right tool for each case.
  - [x] 2026-11-13 · Proposed right tool for all 118 cases (`scripts/tool_right_tools.py`). Correction: the bench ran before cbbe722 added `reframe_media`, `trim_media`, `add_words_to_media`, `mix_audio`, so shape, exact words, watermark and trim may already be covered (not measured). 15 cases still hit a gap (re-checked against the follow-up turns of the J cases: still 15). Next: the user corrects the column and adds notes.
- [ ] **MCP-21 · Tool notes for the existing tools.** What each tool does well, how it fails, the deciding question.
  - Write them from the existing persona-bench runs first, 0 credits (user, 2026-11-13: the existing tools were already tested). Enough runs for: `edit_image` 302, `generate_image` 263, `create_video_from_text` 157, `create_video_from_image` 79, `generate_music` 43, `detect_faces` 41, `edit_video` 36, `add_subtitles_to_video` 34, `join_videos` 33, `get_last_frame` 26.
  - Small tests only where the runs cannot decide, budget agreed first: `edit_image` or `generate_headshot` for a headshot (A05); `upscale_image` or `edit_image` to restore an old photo (B13a); `create_talking_photo` or lip sync (8 and 5 runs); what `translate_video` does (0 runs).
  - Never run in the bench: `reframe_media`, `trim_media`, `add_words_to_media`, `mix_audio` (added in cbbe722 after the bench). Their test is the re-run of the cases they should fix (MCP-24).
  - [x] 2026-11-13 · Notes for the six weakest tools: `edit_image`, `edit_video`, `generate_music`, `add_subtitles_to_video`, `swap_face_in_video`, `remove_image_background` (`mcp_magichour/tool_notes.json`). Found: `generate_music` makes 15 s at least (API minimum), so a shorter track needs `trim_media`. `edit_image` and `edit_video` redraw everything and were the wrong pick in 165 runs.
  - [x] 2026-11-13 · User: for a face swap in a photo, use `swap_head_in_photo` (head, hair and face), not `swap_face_in_photo`. Head swap is photo only and has no setting to pick one person among several; it was never called in the bench. Test it on C14a and C14b.
  - [x] 2026-11-13 · Notes in the user's shape (family, type, antitype, limits) for 24 tools: every tool the bench called, plus `reframe_media`, `trim_media`, `add_words_to_media`, `mix_audio` (from their code, not benchmarked) and `swap_head_in_photo`. Found: `generate_image` has no 4:5 setting; `generate_headshot` ignores shape and background; `create_talking_photo` keeps the photo's shape; `upscale_image` regenerates faces on an old photo.
  - [x] 2026-11-13 · Best settings from the bench's recorded calls (4,565 calls, compared within the same case): `edit_image` and `generate_image` do best with `qwen-image-2.1` and worst with `flux-2-klein` (lost 15 of 19 and 11 of 14 cases); `ai-illustration-generator` for illustrations (8 of 8), never `ai-photo-generator` (0 of 5); `ltx-2.5` over default for text to video (11 of 16). The upstream `edit_image` description suggests `flux-2-klein` to Free accounts. In `tool_notes.json`, `best_settings`.
  - [x] 2026-11-13 · User: free-tier models only. The recommended models (`qwen-image-2.1`, `qwen-edit`, `ltx-2.5`) are free-tier; free models per tool listed in `tool_notes.json` (`free_models`).
  - [x] 2026-11-13 · Corrected (user): free models are the priority because they cost less, not a hard limit. Rules, notes, planner text and README now say: free first; a paid model only when it clearly improves the result (or the user asks), the plan allows it, and the user is told the cost. Not measured yet: when a paid model is worth it (all tests ran on the free plan).
  - [x] 2026-11-13 · Final (user): free-tier models only. Rules, notes, planner text, README and test back to free only; no paid-model comparison.
  - [x] 2026-11-13 · Tool tests, run wlive1: 14 cases, happy user, 699 credits. Average 2.4 → 3.8. Ray's code tools confirmed on shape, words and trim; head swap 1.5 → 4 on C14b. [Results](../prd/tool-management/tool-tests.md). Setup faults for Ray listed there.
  - [x] 2026-11-13 · Open checks: head swap on C14a is clearly the right person, face swap a blend (10 credits); C17a run again: 4 (first run 2). Tool tests total 1,101 credits.
  - 12 API tools never called and asked for by no case (for example `colorize_photo`, `swap_head_in_photo`, `restyle_video`): short notes from their descriptions; tests later.
- [ ] **MCP-22 · Families and question sheets.** Group the tools. For each family, the deciding rows and the required rows, from the notes.
  - [x] 2026-11-13 · Draft: `mcp_magichour/question_sheets.json`. 7 request families, 39 rows (20 deciding, 19 required), each with how to answer it from the user's words first, a default for 'your call', and the note and cases behind it. 8 rules across all sheets (at most 3 questions, keep the user's details word for word, free tier only, keep the user's media, say so plainly at a GAP). Not confirmed by the user.
- [ ] **MCP-23 · Build `plan_tool_call`.** `mcp_magichour/tool_plan.py`, behind `MAGIC_HOUR_TOOL_PLAN` (default `off`). Contract tests in `tests/test_tool_plan.py`. A test that the build changes no video composition file.
  - [x] 2026-11-13 · User: no question limit; one batch, asked once; as few questions as possible. The 3-question cap is gone; a second call with `questions_asked=true` turns any row still marked 'ask' into its default (no second round).
  - [x] 2026-11-13 · Built: `mcp_magichour/tool_plan.py`, registered in `openapi_server.py` (import + one call), off unless `MAGIC_HOUR_TOOL_PLAN=on`. First call returns the family's sheet; the host fills `answers` (an option, the user's words, `your_call`, `n/a`, or `ask`); the server returns at most 3 questions or the plan (what each answer means, free-tier settings, notes for each tool named, gaps). Rows the host must answer itself are never put to the user. 18 tests in `tests/test_tool_plan.py`, all pass, including: off by default, imports nothing from video composition, this branch changes no protected file. Whole suite: the same 17 errors as on `video-production` (environment: no web build, ffmpeg tests), none new.
  - [x] 2026-11-13 · Dry run found 3 faults (exact words as a value, consent 'none', side by side not a gap); fixed in b28d821.
- [ ] **MCP-24 · Benchmark the planner.** Family predicted right, tool picked right, item scores against the old MCP and against the switch off. Ship only if not worse on tool management, and video composition unchanged.
  - [x] 2026-11-13 · Targeted run (user: only relevant cases): 13 cases + 2 refusals, planner on vs off vs old MCP, 991 credits. Average 2.7 (old) → 3.0 (off) → 3.3 (on). Gains on the vague user (A01a 2 → 4), 'the best part' (E26a), upscale (B13b); a child's face now declined. One loss (B13a, the 'preserve' setting), fixed. [Results](../prd/tool-management/tool-tests.md).
  - [x] 2026-11-13 · 3 runs per case (rounds r2, r3; 2,098 credits): old 2.69, off 2.85, on 3.28. Holds in every run: A01a (vague user) +2, B13b +1.3; J50a +1. No case worse in every run. The host calls the planner in only 1 of 3 J54b runs, so refusal rules there are mostly not applied.
  - [x] 2026-11-13 · User: call the planner only when the answer would materially change the result. Measured before: the host called it on almost every request (usually twice, 10 to 50 s added) and asked the user in 1 of 13 cases. Changed: the description lists when to call it (missing or ambiguous, or a known pitfall) and says otherwise call the tool directly; one call (a 900-character row index in the description); rows left out take their default, only 'ask' rows become questions. 25 tests pass.
  - [x] 2026-11-13 · Check run w24on-r4 (689 credits): one planner call where used (was 2 to 3); clear requests skip it; B13b, C14a, E26a held, B13a 3. Score 3.17 (planner before 3.25, off 2.81; one run). Lost: A01a 4 → 2 (the host found 'make a product pic of a water bottle' clear and skipped the planner). Fix d70cda1: the description names a vague request with that example. A01a three runs after the fix: 4, 4, 4 (30 credits).
  - [x] 2026-11-13 · Row `look` added to new_picture (colour, material, setting, light; default a clean product look). In those runs the planner asked words, shape, transparency; the look was asked by the host on its own. 28 tests pass.
  - [x] 2026-11-13 · Re-check A01a with the look row, three runs (30 credits): 4, 4, 4. The planner now asks look, exact words and shape every time; 'matte black on marble, soft light' reaches the prompt word for word.
  - [ ] Decide the switch default (user). Before turning it on: a check with ChatGPT as host (all runs used Claude).
  - [ ] ChatGPT check, paused (user, 2026-11-13). Ready to run with Ray's GPT driver (`V2/bench/mcp/run.mjs --local --mcp-url`) once a working OPENAI_API_KEY is in `~/mh-bench/.env` (the key given was refused: 401).
- Folded in: MCP-17 (jobs with no tool) feeds MCP-20 and MCP-29 to MCP-35. MCP-12 (trim) is tool management; `trim_media` exists since cbbe722. MCP-16 (what may not be guessed) feeds the required rows.

#### 2. Tool composition (combining existing tools)

Chains of tools that exist today. Each chain goes in the tool notes and in `plan_tool_call`'s output as steps in order. Cases from the [failure list](../prd/tool-management/failures.md). After MCP-21 to MCP-24.

- [ ] **MCP-25 · Make, then add exact words.** Make the picture or video without words, then `add_words_to_media`. Image models misspell; code does not. Cases: A01d, A02a–d, A03a–d, A06a–d, B11a/c/d, G33a/c, G34a–c, G36a/b, G39a, J49b, J50c, E29c (watermark).
- [ ] **MCP-26 · Make or edit, then change the shape.** `reframe_media` after `generate_image`, `edit_image` or a video tool, which keep their own shape. Cases: B12a/b/d, E25a, J50a, J51b, G36a/b, G37a/b.
  - [x] 2026-11-14 · Dry run wcomp (13 cases, 0 credits): the dry run refuses the first paid step, so the chains after it are not seen. Found: for 'the same design in several sizes' the sheet gave two different instructions (one generation per shape vs one picture reshaped). Fixed: `several_sizes` decides; default one generation per shape with the same prompt and look, then the words on each (G36a scored 3.7 that way); reshape only for 'the same picture'.
- [ ] **MCP-27 · Cut and rebuild the user's video.** `trim_media`, `get_last_frame`, `create_video_from_image`, `reframe_media`, `join_videos` in order. Cases: E25b (trim per speaker, reframe each, join), E25c (reframe, then subtitles), E26a/b (best part, cut the boring parts), J49c (keep the first 5 s), J50b (keep the start, new ending from the last frame), C15a (trim, then face swap), G33b (a frame at a chosen time: trim to it, then last frame).
  - [ ] Blocked (user, 2026-11-14: wait for Ray's fix): `join_videos` fails without a system ffmpeg (`media_tools.join` calls `ffmpeg` by name; notes-for-ray.md).
- [ ] **MCP-28 · Build sound from parts.** Voice lines and music made one at a time, then `join_videos` (sound files) or `mix_audio`. Cases: F31b (two voices), F32a (voice over music), F32b (podcast of two hosts). Music under 15 s: `generate_music` makes 15 s at least (API minimum), then `trim_media` (F30a, E27a, E27c). Needs the voice generator (hidden upstream, MCP-11).
  - [x] 2026-11-14 · Run wcomp with MCP-25 and MCP-26 (13 cases, 663 credits): every chain made the right final file (checked by hand: grades 3.23 vs old 2.77, held down by the grader judging earlier files and missing the audio). Real fault: G37a passed an image project id to edit_image (refused); rule added to the sheets. Open: G36a's sizes differ in design when generated separately.

#### 3. New tools (no tool does the job today)

Later, after composition. Each new tool goes in a new file of tool management, not in the shared `media_helpers_tool.py`. Scores: old → new on the persona bench.

- [ ] **MCP-29 · Sound on the user's video.** Lay music or a voice-over on a video, music lowered under speech. `mix_audio` makes sound only; `media_tools.add_sound` does it but only the production join uses it. Cases: E27a/b/c (2.0), E28a (2.0), E28b (1.7), E28c (1.3). First check: is routing these to the production join (`source`, MCP-14) enough?
  - [x] 2026-11-13 · Built `add_sound_to_video` (`mcp_magichour/tool_media.py`, same switch as the planner): music and/or a voice-over on the user's video by code, 0 credits; the video's own sound kept clear (keep), lowered (under) or removed (replace); a long voice read a little faster, then the last frame held; loudness set. On the shared `media_tools.add_sound`, unchanged. 6 tests on generated clips (`tests/test_tool_media.py`). Sheets: `sound_on_video` now points to it (was a GAP). Found: `media_tools.join` calls `ffmpeg` by name (notes for Ray).
  - [x] 2026-11-14 · Live run wnew, with the other new tools: 13 cases, old MCP 2.0 → 4.2; 103 credits. E27a-c and E28a-c all 4 (files measured: picture and length kept, −16 LUFS, keep/replace chosen right). E29b failed in join_videos (ffmpeg by name), fixed by `make_card_clip` attach: 4. [Results](../prd/tool-management/tool-tests.md).
- [ ] **MCP-30 · Pictures side by side.** Two or more pictures in one frame by code, no redraw. Cases: G35a (2.0), G35b (1.7).
  - [x] 2026-11-14 · Built `put_pictures_side_by_side` (`tool_media.py`, the planner's switch, 0 credits): 2 to 4 pictures in a row, column or 2x2 grid, each whole (never cropped, stretched or redrawn), optional exact labels. Tests on generated media (`tests/test_tool_media.py`). The sheets now point to it (was a GAP). Not benchmarked yet.
- [ ] **MCP-31 · A picture on a video.** A logo in a corner for the whole clip. Case: E29a (1.3).
  - [x] 2026-11-14 · Built `put_picture_on_video` (`tool_media.py`, the planner's switch, 0 credits): a logo or picture on a video or picture, corner or centre, sized, see-through, for all or part of a clip; transparency kept. Tests on generated media (`tests/test_tool_media.py`). The sheets now point to it (was a GAP). Not benchmarked yet.
- [ ] **MCP-32 · A still as a video clip.** A card of N seconds, to join to a clip. Case: E29b (2.0, old only).
  - [x] 2026-11-14 · Built `make_card_clip` (`tool_media.py`, the planner's switch, 0 credits): a still card (exact words on a colour, or a picture) as a clip with a silent sound track, the size of a given clip, for join_videos. Tests on generated media (`tests/test_tool_media.py`). The sheets now point to it (was a GAP). Not benchmarked yet.
- [ ] **MCP-33 · Translated subtitles.** Subtitles in another language, the voice kept. `add_subtitles_to_video` writes the spoken language. First check: what `translate_video` does (never called in the bench). Case: E24b (2.0).
  - [x] 2026-11-14 · Checked: `translate_video` dubs the speech into another language (the voice changes; 1 to 30 s clips). It does not make subtitles, so it does not fit E24b (Spanish subtitles, English voice kept). Open: how to get a transcript with times.
  - [-] 2026-11-14 · Skipped for now (user). Options looked at: (A) a `transcribe_media` tool by Whisper (the OPENAI_API_KEY Ray's word check uses), the host translates, `add_words_to_media` draws timed lines: keeps voice and picture, 0 credits, about $0.006 a minute, needs a working key (recommended); (B) speech-to-text on the server (large model; Vercel size limits); (C) translate_video → subtitles → original voice back: re-renders the picture, not recommended. Magic Hour's subtitle API has no language setting and returns no transcript.
- [ ] **MCP-34 · 4:5 shape.** `reframe_media` has 16:9, 9:16 and 1:1. Ask Ray first: it is his file. Case: B12c (1.0); also asked in A03, G34b, J50a.
- [ ] **MCP-35 · Colour change by code.** Warmer, cooler, black and white, without a redraw. Cases: B07c (3.7), J49a (3.3), B10c (4.7: `edit_image` already does it well; lowest priority).
  - [x] 2026-11-14 · Built `adjust_colours` (`tool_media.py`, the planner's switch, 0 credits): warmth, saturation (0 = black and white), brightness, contrast, on a picture or a video; nothing redrawn. Tests on generated media (`tests/test_tool_media.py`). The sheets now point to it (was a GAP). Not benchmarked yet.

### Video composition and shared

- [ ] **MCP-11 · Voice-over by the voice cloner.** Open only for the production push. Upstream approved (2026-11-11: `test_release_gates.py` reports approved after upstream #184). Default `cloner` (user, 2026-11-11). [PRD](../prd/video-composition/production.md).
  - Why: the video-model narration read A4's script 2 times in 8. The voice cloner read it exactly, for 17 credits (`Benchmark/voice.html`, 2026-11-08).
  - Block: upstream hides the voice tools on purpose. `openapi_policies.py` removes `/v1/ai-voice-cloner` always, and `/v1/ai-voice-generator` while `APPROVED_VOICE_NAMES` is empty (commit 2e6d659, #109). The user (2026-11-08): approval is pending on the other side.
  - Our branch may have the feature. Before a push or a PR, verify that upstream main allows it:
    - `git fetch upstream && git rebase upstream/main`.
    - Check that `apply_magic_hour_policies` keeps `/v1/ai-voice-cloner` (or `APPROVED_VOICE_NAMES` is not empty).
    - Not allowed: do not push the feature on. Push it off, or hold the push.
  - [x] Switch: `MAGIC_HOUR_VOICE_OVER=video|cloner`; default `VOICE_OVER_DEFAULT = "cloner"` (user, 2026-11-11: our version ships to production once upstream approves; until then we work as if approved).
  - [x] Switch on, no `voice_sample`: the plan asks question `voice` (sample / video), recommends sample.
  - [x] 2026-11-11 · Replaced (user, proof of concept): no question; without a recording the cloner reads in a default preset voice (Ashley, or Daniel when `narrator` names a man; `DEFAULT_VOICES` in `video_production.py`).
  - [x] Switch on, with `voice_sample`: `create_production_sound` calls `/v1/ai-voice-cloner`; the join fetches an audio project.
  - [x] Gate: `tests/test_release_gates.py` fails while the shipped default or a shipped config turns the cloner on and upstream still hides it.
  - [x] Hook file: `scripts/pre-push`. Not installed (the user installs it): `ln -sf ../../scripts/pre-push .git/hooks/pre-push`.
  - [x] Fix found by the test: `media_tools.probe` reads a file with no picture (a voice track).
  - [x] Fix: the "colour words" answer no longer makes "teal teal".
  - [x] Paid check (2026-11-08, 334 credits): A4 with a recording attached (item `A4v`), through a local MCP with the switch on. The MCP asked `voice`; the agent answered sample with the recording's file_path; the cloner read the script (22 credits); the word check heard 100%. Film: `Benchmark/voice/A4/MCP/`.
  - [x] Word check: the join transcribes the narration (Whisper, only when the server has `OPENAI_API_KEY`) and reports "no" under 80% of the script's words. Without the key: the speech check only, as before.
- Facing-away speaker test (2026-11-08, 576 credits, `Benchmark/facing.html`): the line was said word for word 6 of 6 (back to the camera, profile, far away, two people where the one facing away speaks; ltx-2.5 and minimax-h3). The listener kept her mouth closed in all 3 two-person clips. ltx-2.5 put "back to the camera" as three-quarters away, side by side (S1).

- [ ] **MCP-18 · Consider `plan_request` outside the video composition path.** User, 2026-11-12: ship video composition first; a single call stays as in the old MCP. [Scope](../prd/ARCHITECTURE.md).
  - [x] 2026-11-12 · `plan_request` is called only before `plan_video_production` (description; tool name `plan_video_production` in the sheet). The `create_video_from_image` description is the old one again.
  - Why: persona bench, 16 single-call video items, old against new: avg score 3.38 → 3.19 (happy), 3.38 → 3.31 (stupid), 3.38 → 3.25 (dumper). The tool-calling items show no clear gain: 25 better / 13 worse (happy), 22 / 24 (stupid), 21 / 21 (dumper).
  - [ ] Later: measure `plan_request` on single calls and tool calling, each on its own, against the old MCP. Turn it on there only when it is better.

- [ ] **MCP-01 · Conversation: derive the parameters, ask only for the rest.** [Ticket](MCP-01-conversation.md). [Spec](../prd/shared/conversation.md).
  - [x] PRD, spec, 40 contract tests: `tests/test_plan_request.py`.
  - [x] Build `plan_request`: `mcp_magichour/plan_request.py`. All 40 pass.
  - [x] Harness for a local build: `run.mjs --local --mcp-url <address> [--hide a,b]` (agent repo).
  - [x] Benchmark, 13 vague briefs, paid calls refused. Results: see Done.
  - [ ] Benchmark, 13 full briefs (expected: 0 questions).
  - [ ] Confirm: the host model fills the sheet, server code checks it.
  - [ ] Answer the 28 open questions in the spec.
  - [x] 2026-11-10 · Persona dry sweep p2 (3 users × 163 cases, old and new, 0 credits) found: "No text" sent as a string was read letter by letter and asked about words; "your call" counted only when the question came back word for word; words with list numbers or a changed quote were asked again. Fix in `plan_request.py` (rules 7 to 10b in the spec), 12 new tests (`tests/test_plan_request.py`, 55 pass; the whole suite has the same 3 failures as before, no web build). Replay of 673 recorded calls: 0 questions added except G37b, where the host moved "17 October" to "24 October" and the old code let it pass. Dry re-run of 94 conversations on the fixed build: word questions 47 → 6 on the cases the replay changed. Not committed.
  - [x] 2026-11-10 · Proposed · "Your call" now holds to the end of the chat (rule 6c). Motion added to rule 10b. The tool description now asks the host for the whole chat, its own questions included. Why: in sweep p2, 13 calls in 8 of 163 lost-user chats asked again what the user had handed over (D20b: "you pick" to length and sound, then to the shape, then length and sound again). 49 of 400 lost-user calls had no assistant message before a user message. 6 new tests (61 in the file; the whole suite has the same 3 failures). Replay of 994 recorded calls (831 from p2, 163 from the p3 re-run): no call asks more; 13 ask less (lost user 11, oversharing user 2); the lost user's p2 questions go 390 → 373. Measured on a host (2026-11-10, dry, 0 credits): OpenAI refused the key (401, 04:04), so the 72 chats ran with a Claude host (`claude-opus-5-5`) on both builds, before and after this change (p4c; not comparable with the GPT runs). Calls with a user message and no assistant message before it: 10 → 0 (5 → 0 with no assistant message at all). Questions asked to the user: 75 → 64. Tool questions: 113 → 99. Re-asks after a hand-over: 3 → 1 calls. Tool question put again: 27 → 20. Loops: 0 → 0. One chat newly stuck (H44b: after "just make it" the host still asks for on-screen words, as the rule says). A replay of every recorded call: the new code never asks more, and asks fewer in 3 calls, so most of the gain is the new description. One run for each build: the direction is the same everywhere, the size of the gain is within noise. Cost about $60. Not committed.
  - [ ] Proposed · The host sometimes flips a row from `default` to `derived` and drops assistant messages even so; the shape was then asked 4 times (A01a, oversharing user). The new description removed the dropped messages for a Claude host (p4c); the `default`/`derived` flip is not measured. Open.
  - [-] Proposed · Ask one question at a time (52 of 163 lost-user chats got 3 or more in one message). Closed: replaced by MCP-15 (user, 2026-11-11: batches).
  - [x] 2026-11-11 · `get_last_frame` and the joins could not read an attached clip's `file_path` (G33b, E25b, E28a, E29b). User: option 1 with a clean fallback. `upload_media` + `kept_files.py`: the server keeps a copy of every file that passes through it; an unknown `file_path` fails before any API call. [PRD](../prd/video-composition/production.md), Files and storage.
- [x] **MCP-02 · Clip split: find the best rule.** Closed 2026-11-11 (user): the rule is chosen and tested in the A and B runs.
  - [x] Splitter with 5 rules (`one`, `time`, `idea`, `event`, `shot`): `mcp_magichour/video_production.py`.
  - [x] One reference for each clip: last frame / picture / own still / none.
  - [x] 5 test stories: `tests/fixtures/stories/`. Unit tests: `tests/test_video_production.py`.
  - [x] Bench runner: `scripts/split_bench.py`.
  - [x] Paid run 1: C4 (B2) and C5 (B1). 5 films, 3,092 credits. Films and checklists: `Benchmark/split/`.
  - [x] Rule chosen from run 1: cut at a new idea, and at 15 s.
  - [-] Paid run 2: C1, C2, C3. Dropped (user, 2026-11-11).
  - [x] Split rule (user, 2026-11-05). Strategy `person`, the tool's rule.
    - Ideas come first. The same person is an idea: their beats stay in one clip, also when the place changes, while the clip fits.
    - Limit: 15 s. For a person with a picture: 30 s (`minimax-h3`).
    - An idea that is cut is chained: the clip ends on the person, and the next clip starts from that last frame.
    - A person who comes back after other clips starts from the last clip that showed them.
    - If the place is new: the clip ends close on the person, and the next clip pulls back to show the new place.
    - A new idea with no person from before: new clip, no reference (or its picture).
  - [ ] References for people (pictures). Later (user, 2026-11-05).
  - [-] New place, same person, last frame as a named reference (C7). Dropped (user, 2026-11-11).
  - [-] Ending line when the person faces away (C8). Dropped (user, 2026-11-11).
  - [-] Clips made at the same time. Dropped (user, 2026-11-11).
  - [-] Second run of each film. Dropped (user, 2026-11-11).
- [ ] **MCP-03 · Video production tool in the MCP.** [PRD](../prd/video-composition/production.md).
  - [x] `plan_video_production`: story in, ordered calls out. `mcp_magichour/video_production_tool.py`. Tests: `tests/test_video_production_tool.py`.
  - [x] A host completes the plan (clips, sound, join): the 11-07 runs and the 2026-11-10/11 fleet runs.
  - [x] B1 and B2 through the GPT driver with the tool (2026-11-05, see Done).
  - [x] Before payment: story adds up, each clip fits the model, prompt is 2,000 characters or less, order of calls.
  - [x] After generation: clip length, clip size.
  - [x] Join: the film is silent when the story has no sound (`minimax-h3` adds music with audio off).
  - [ ] After generation: shots in order, no shot repeats, same people in all clips. Scored by eye until MCP-07.
  - [ ] The join trims each clip to its planned length (minimax-h3 clips run ~0.3 s long; B2 31.8 s, 2026-11-07). Fleet 2026-11-12: 78 of 88 films within 0.5 s; the five-photo reels D20a/b/c ran 1.7–2.3 s long (1–2 s clips come back about 1.6 s or longer). `media_tools.join` puts each whole clip in; `check_outputs` allows ±1 s for each clip.
- [ ] **MCP-05 · When to call the video production tool.** Instructions to the host agent, or code that reads the request and decides. Later (user, 2026-11-05).
- [ ] **MCP-06 · Last frame, join and storage on the deployed server.**
  - [x] 2026-11-06 · ffmpeg: the server uses the ffmpeg on its PATH, else the one the `imageio-ffmpeg` package ships; ffprobe is no longer needed (`media_tools.probe` reads ffmpeg's own report). Install: `pip install -e ".[production]"`.
  - [x] 2026-11-06 · Storage: `media_tools.store`. With `BLOB_READ_WRITE_TOKEN` set, the film goes to Vercel Blob and its public address is returned; else it is kept on the server and served at `/films/<name>`. The Blob path is written against the REST API and is NOT tested against Vercel yet.
  - [ ] Deploy with the `production` extras and the token, then run B2 through the hosted server once.
- [ ] **MCP-04 · Gates and checks.**
  - [x] 2026-11-06 · Checklist: `plan_video_production` returns `checklist` (what the story promises). `join_production_clips` returns `checked` (length, shape, card lengths, narration placed, music, captions, sound present or silent, measured on the file), `unchecked` (lines for the host to confirm by eye) and `not_met`. The host is told to report unmet lines, not to present them as done.
- [ ] **MCP-07 · State manager.** Read what is in each clip. Later (user, 2026-11-05). Until then: assume each clip shows what its story text says.
- [x] **MCP-08 · Voice-over, captions, music on a multi-clip film.** Closed: option E (user, 2026-11-05), `create_production_sound` and the join; see Done.
- [ ] **MCP-09 · Todo list from the request, checked at the end.** User, 2026-11-05: break the prompt into a todo list, then check that each line is done, at least the easy checks.
  - [x] 2026-11-06 · From the story: see MCP-04. Covers only what the host put in the story.
  - [ ] From the brief: a line for each thing the request asks for, made at `plan_request` time, so a line the host left out of the story (A2's end words, A1's music) still shows as not met.
  - [ ] Decision: check only, or also fix (music track in the join, words drawn in the join).
  - [ ] Decision: films through the join only, or all videos.
- [x] 2026-11-06 · Approach tests, one attempt each, 1,940 credits. Page: `Benchmark/approach.html` (`scripts/approach_bench.py`, `scripts/approach_page.py`, scores in `Benchmark/approach/scores.json`).
  - User picks, 2026-11-07: Words W5 (scene, then a card) and W2 (minimax-h3 asked for the words). Not W4 (drawn by code). Continue C2 (last frame, ltx-2.5) and C3 (last frame, minimax-h3). C6 bottle: one call per season and medium-only (10 + 10) both good. C7 two people: the person rule and one call per season, words only, both good; medium-only rejected.
  - 2026-11-07 · C10 perfume + two people in words, four seasons, bottle picture in every call, 1,680 credits. One call: seasons play twice. One per season, person rule, medium-only (10 + 10): all four seasons in order, bottle and letters right in all three. People: the same inside one call, a look-alike across calls (Theo exact under the person rule; Mara a look-alike everywhere).
  - User picks, 2026-11-07: C10 one call per season, person rule and medium-only all good; one call rejected.
  - Defaults from the picks: (1) words: a card after the scene when the words can stand alone; minimax-h3 over the scene when they must sit on the picture, with a spelling check; never ltx-2.5. (2) Continue a clip: keep the file, last frame, ltx-2.5 (minimax-h3 the alternative), silent join. (3) Split: cut on a change of medium and at the cap; with a picture reference, two places in one call is fine; without one, cut at every change of place; a person in words stays in one call where it fits (person rule).
- [x] 2026-11-07 · Gates test (user's design: broad gates, the model reasons). `mcp_magichour/gates.py`, `gates_docs.py` (findings-only tool notes), `media_helpers_tool.py` (get_last_frame, join_videos), `MAGIC_HOUR_GATES=off|warn|refuse`. Page: `Benchmark/gates.html`.
  - 7 requests (B1, B2, C10, A2, A3, A4, J55a). Old MCP 27 yes · 10 partly · 8 no. v1 38 · 5 · 2. Gates warn 35 · 6 · 4. Refuse: not valid (plan_token rejected by the argument check; fixed in `mcp_errors.py`, rerun about 3,500 credits).
  - Breaks: the review gate approved every plan (0 conflicts in about 30 reviews over the dry and paid runs). Long tokens were mis-copied (fixed: short ids, state on the server). The brief extractor read "portrait" (a photo) as 9:16 (fixed in plan_request too).
  - Wins of the gated side: A2 exact end words by a method nobody gave it (last frame, image edit with the words, animate to it).
  - Faults found in our tools: a silent narration passed join_production_clips's check (check speech, not placement). A joined film has only a local 127.0.0.1 link, so the host gave the user a part instead (A4 warn). (I first reported a broken join; the join was fine, my frame sheet misread it.)
  - Spend: 11,414 credits on 2026-11-07 for this test (159,381 to 147,967), 3,060 of them lost to a shell mistake (arguments in a zsh variable did not split; 152 wrong items ran) and rate limits (harness now retries).
- [x] 2026-11-07 · Spoken-line test (B2's "You came back."), 480 credits. Inside a 12 s clip with a second beat, ltx-2.5: 0 of 3 runs. Alone in a 4 s close-up: ltx-2.5 3 of 3 word for word; minimax-h3 heard 2 of 2, word for word 1 of 2 ("He came back."). Same model and words: the line was lost because the call carried too much else. Page: `Benchmark/approach.html`, first section.
- [x] 2026-11-07 · Agent groups, MCP asks (user's design). Beat fields `clip`, `spoken`, `reference`, `in_scene_words`, `background`, `picture`, `model`; `questions` + `answers` (words over a scene: card / model / still / accept; a spoken line with another beat: split / keep; colour codes: words / keep), plan held until answered; `advice` for the rest; `request` tracked; drawn and held cards made by code at the join; narration speech measured. 218 tests. Paid run of A2, B2, B1, A4: 2,677 credits.
  - Same four on v1 (7 Nov): 22 yes · 3 partly · 2 no. New: 21 · 4 · 2. Fixed: B2 line said (own clip), B1 9 yes, cards and logo exact. New faults: ltx-2.5 narration spoke nonsense (A4); minimax-h3 clips run ~0.3 s long each (B2 31.8 s); minimax-h3 put A2's words at the start.
  - Next: voice-over from Magic Hour's voice generator, not a video model; the join trims each clip to its planned length; the "model" words option warns that the moment is not controlled.
- [ ] **MCP-10 · A1 to A4 again on the current build.** Mostly closed by the 2026-11-07 and 11-08 runs (A2, B2, B1, A4). The v1 runs on the page are from 2026-11-05 04:45 to 04:56, before the sound tools, the checklist and the ending-line fixes. One run each, after the fixes below.
  - [-] Superseded by the user's pick (2026-11-07): a card after the scene, or minimax-h3 over the scene; not drawn by code (W4). A2 · words over the last shot: `exact_words` on a scene beat are drawn by code in the join (as captions are), not asked of the model (old MCP "walk anway", v1 none; ltx-2.5 cannot spell).
  - [ ] A3 · see MCP-14. Continue a given clip: a plan whose first piece is the user's file, one clip from its last frame, silent join. The host had no such tool and regenerated all 12 s with minimax-h3 (music came back with audio off; she slides out of frame facing the camera, no turn). 144 credits, not 288.
  - [x] 2026-11-07 · Fixed by agent-grouped clips (the host sets `clip` on each beat). A4, S3 · too eager a split: a single continuous scene of 15 s or less stays one call; an end card is appended, not a reason to split the rest. Count ideas by place and people, not by beats.
  - [ ] Partly: 11-07 run 9 lines yes; the label stays best effort (`in_scene_words`). B1 · the label: the letters are lost in the host's edited reference (640 px, bottle about 60 px wide) and 480p cannot hold them in the hand shots. Options: a tighter crop of the bottle as a second named reference on `minimax-h3`, or 720p for shots where the bottle is small.
  - [x] 2026-11-07 · Fixed: `spoken` on the beat and the `line` question; the line is said in its own clip. B2 · the spoken line: "You came back." was in the prompt as prose; ltx-2.5 did not speak it (the old MCP's one call spoke it 10 times; Replicate's ltx-2.5-fast once). Put it in `says` on the beat so `compose_prompt` writes it as a dialogue line, and add a "line spoken once" check (speech spans).
  - [ ] A1 and A3: not rerun on the current build.
- [ ] **MCP-15 · Ask in batches, with a limit on rounds.** User, 2026-11-11. Trial; the PRD is updated only after the user approves the results.
  - Rule: one batch with every open question (numbered sub-questions), each with what happens if the user skips it. The batch covers every gap, so "your call" after a batch hands over everything still open.
  - `MAGIC_HOUR_QUESTION_ROUNDS`: the most batches the user is asked. Answers that leave gaps, with no "your call": another batch while rounds remain; else the agent infers the rest and says what it chose. Unset: the old behaviour (3 questions a call, no limit).
  - [x] Code: `plan_request.py` (rule 9, `question_rounds`), 5 tests in `tests/test_plan_request.py`.
  - [x] 2026-11-11 · Dry runs (tags qr0 today, qr1 one round, qr2 two rounds; 25 cases with the most questions last run × happy and lost user; 150 chats, 0 credits). Question rounds before the first make call, lost user: today 4/13/8 chats with 0/1/2 rounds (avg 1.16); one round 4/20/1 (avg 0.88); two rounds 2/17/6 (avg 1.16). Happy user: 2 chats asked today, 4 with either trial. With one round, the agent told the user what it chose for the gaps (D23c, H40a). Exceptions: F31b asked a second time for the script (a gap that cannot be guessed, MCP-16); G36a lost Bash permission (test fault).
  - [ ] User's approval; then the PRD (conversation rule 6c, question 17) and the default number of rounds.
  - Replaces the proposed line under MCP-01 "ask one in plain words, then the next" (closed).
- [ ] **MCP-16 · What the agent may not guess.** Deferred (user, 2026-11-11). Under MCP-15, when the rounds run out: (a) a gap that cannot be guessed (an edit with no stated change, no picture for a picture edit); (b) exact words on a poster or ad, which an agent can write but the user may not want. Decide later.
- [ ] **MCP-17 · The user's media is redrawn.** For the user to address (user, 2026-11-12). Fleet root-cause run: 38 failures, 98 chats, average score 2.1/5, 9 usable as is. Page: `Benchmark/audit/failure-modes/index.html`, group "user media redrawn".
  - The user asks to keep their file and change one part. No tool does the job by code, so the host sends the file through a model that redraws it, or makes nothing.
  - Jobs with no tool: mix music under the user's video (E27a/b/c), replace its soundtrack (E28b/c), put a logo or watermark on it (E29a/c), join the user's stills into a video (D20a/b), put photos side by side (G35a/b), change colour only (B07c, J49a), take a still frame from a video (G33b), edit one masked part (B07d).
  - `media_tools.add_sound` already mixes sound into a film. Only the production join uses it. No tool exposes it.
- [ ] **MCP-12 · Trim.** Later (user, 2026-11-11). No trim tool exists. `plan_request` still plans `trim_video` and marks it ready, so the host calls a tool that is not there ("Unknown tool": E26a, E26b, 2026-11-11). Build it on the kept copy (ffmpeg, 0 credits), or make `plan_request` say there is no tool. PRD: [media files](../prd/shared/media-files.md).
- [ ] **MCP-13 · Storage of kept files.** Later (user, 2026-11-11). Reminder: kept copies of users' files go to public Vercel Blob (`kept/`). Move to private storage. One module: `kept_files.py`.
- [x] **MCP-14 · The user's own clip in a production.** Approved by the user 2026-11-11 (E28 films); checked again in the next benchmark. Beat fields `source` (the user's clip: file_path, URL or project id) and `source_sound`; the clip is a clip of its own, 0 credits; the join uses it as it is. Tests: `tests/test_video_production_tool.py` (3 new). Shown: fx4 (E28a/b/c × 3 users: 9 of 9 used `source`, 9 films with narration on the user's clip, 1,571 credits) and demo1 (A3: original 6 s unchanged + 6 s new from its last frame, 144 credits instead of 288). Check in the next run: [benchmark 02](../benchmark/02-next.md). A plan cannot take the user's clip as a piece, so a voice-over or music on the user's clip (E28a) and continuing a given clip (A3) have no path. The join can read the clip since 2026-11-11 (MCP-01 line, `kept_files.py`).

## Done

- [x] 2026-11-05 · V1 on A1 to A4, GPT driver, local build, same caps as the old MCP runs. 1,368 credits. Page: `Benchmark/report.html` (old MCP, v1, Replicate, 6 items).
  - A1: old 4 / 2 / 0, 103 s. V1 3 / 2 / 1, 228 s. Silent.
  - A2: old 4 / 0 / 1, 62 s. V1 4 / 0 / 1, 112 s. One clip: the story fits in one call.
  - A3: old 5 / 0 / 2, 136 s. V1 3 / 1 / 3, 177 s. New tools not used.
  - A4: old 4 / 1 / 0, 228 s. V1 4 / 1 / 0, 345 s, 422 credits. Captions exact.
  - B1 on all 10 lines: old 2 / 6 / 2. V1 6 / 1 / 3.
- [x] 2026-11-05 · Conversation benchmark, 13 vague briefs, paid calls refused, 0 credits. Page: `Benchmark/upgrade.html`.
  - Current MCP: 9 of 17 wanted values correct, 8 wrong guesses, a question on 3 of 13 briefs.
  - With `plan_request`, run 1: 17 of 17 correct, a question on 12 of 13 briefs, 14 question rounds.
  - With `plan_request`, run 2, after 4 fixes: 16 of 17 correct, a question on 11 of 13 briefs, 12 question rounds.
  - The 1 wrong value in run 2: "a short clip" is read as 8 s and not asked. The user wanted 6 s. Decision necessary: ask, or keep the guess.
  - The host called `plan_request` on 13 of 13 briefs from the tool description only.
- [x] 2026-11-05 · Replicate, paid model (`lightricks/ltx-2.5-fast`, 720p), GPT driver. Price from the user's bill: about $0.40 for 28 s of video.
  - B2: 311 s, about $0.40, 6 / 1 / 0. One joined 30 s file; the line is said once. V1: 5 / 1 / 1. Old MCP: 3 / 3 / 1.
  - B1: 245 s, about $0.45, 7 / 3 / 0. One joined 30 s file with sound made inside the clips; wrong letters on the bottle, the end card and the captions. V1: 8 / 2 / 0. Old MCP: 2 / 6 / 2.
  - Pages (public, by the user's word): B1 https://magic-hour-mcp-b1-report.vercel.app (`scripts/report_b1.py`), B2 https://magic-hour-mcp-b2-report.vercel.app (`scripts/report_b2.py`). Publish: `vercel deploy --prod --yes` in `Benchmark/report-b1` or `Benchmark/report-b2`, from the main session.
- [x] 2026-11-05 · Report published: https://magic-hour-mcp-v1-report.vercel.app (Vercel project `magic-hour-mcp-v1-report`). Build: `python3 scripts/report_page.py`. Publish: `cd Benchmark/report-v1 && vercel deploy --prod --yes`. No B1 video on it (the presenter picture is a stock photo of a real person).
- [x] 2026-11-05 · Sound on a multi-clip film (was MCP-08): option E, chosen by the user. `says` on each beat, `narrator`, `music`, `captions`; tool `create_production_sound`; the join places each part of the narration, mixes the music, draws the captions.
  - B1 on v1 with sound, GPT driver: 353 s, 1,218 credits, 8 / 2 / 0 (all 10 lines). Old MCP: 221 s, 720 credits, 2 / 6 / 2.
  - Timing of the narration parts uses pauses, not a speech model. A part can start late or early by about 0.5 s.
  - Captions need Pillow on the server (not in `pyproject.toml`).
  - Not used: the API's voice generator. Its voices are real people.
- [x] 2026-11-05 · Replicate, free account (`minimax/video-01`, 6 s silent clips), GPT driver, 3 requests with no reference picture. $0.
  - S2: declined, no video (18 s). S3: one 6 s clip, 3 / 1 / 1 (221 s). B2: four 6 s clips, not joined, 0 / 2 / 5 (293 s).
  - Not run: S1 and B1 (the reference pictures must be at a public address; the user's word is necessary).
- [x] 2026-11-05 · Seasons and door requests, old MCP against v1, GPT driver, same 3 briefs (`V2/bench/mcp/dense/items-seasons`). 2,736 credits. Report: `Benchmark/report-v1/`.
  - S1 bottle in four seasons. Old: 146 s, 480 credits, 2 / 1 / 2 (the four seasons play 2 times). V1: 243 s, 480 credits, 4 / 1 / 0.
  - S2 two people, four seasons. Old: 146 s, 480 credits, 4 / 2 / 0 (seasons correct, people are look-alikes). V1: 181 s, 480 credits, 4 / 0 / 2 (people exact, winter stays spring).
  - S3 through the door. Old: 74 s, 408 credits, 4 / 1 / 0. V1: 112 s, 408 credits, 4 / 1 / 0.
  - V1 fault seen: the host changed the `production` value 2 times on S1 and had to plan again (no credits lost).
- [x] 2026-11-05 · Modified MCP against the old MCP, GPT driver, local build (`run.mjs --local`). Page: `Benchmark/upgrade.html`.
  - Tools: `plan_video_production`, `create_production_clip`, `join_production_clips` (`mcp_magichour/video_production_tool.py`, `media_tools.py`). The join needs ffmpeg on the server.
  - B1, picture only, 5 lines. Old: 0 / 4 / 1. Modified: 4 / 1 / 0. 730 credits, 417 s. The host edited one picture (presenter with the bottle) and used it as the one reference.
  - B2, 7 lines. Old: 3 / 3 / 1. Modified run 1: 3 / 2 / 2 (two women, title text in the scene). Modified run 2, after 2 prompt fixes: 5 / 1 / 1. 672 credits, 181 s. The line is not spoken.
  - 13 vague briefs: old 9 of 17 values correct, modified 16 of 17.
  - Faults found and corrected: the ending line described the person again (a second person appeared); a pictured person who entered a scene lost their picture; the story field let the host put title text in every clip.
  - Lost: 428 credits. The harness counted the charge of each wait call again and refused the last clip of one run.
- [x] 2026-11-05 · Split run 3: people in words only. 7 films, 2,472 credits. Hand-scored, one run for each film.
  - Two people, four seasons (C7), 6 lines.
    - The rule (same person in one clip, last frame for the person who comes back): 4 / 0 / 2. People exact. Winter stays spring. Summer and autumn mix.
    - One clip for each season, chained by last frame: 4 / 0 / 2. People exact. Winter stays spring. The sea stays in autumn.
    - One clip for each season, words only: 4 / 2 / 0. Seasons correct. Each person is a look-alike, not the same person.
  - Through the door (C8), 12 s, 5 lines.
    - No cut: 5 / 0 / 0.
    - Cut before the door opens: 4 / 1 / 0. A second Mara is in the frame for 5 s.
    - Cut in the open doorway: 3 / 1 / 1. After the cut the door is closed and the beach is gone.
    - Hard cut, no chain: 1 / 3 / 1. A different woman and a different door.
  - User, 2026-11-05 (watched from 0 s): on C7 the rule and the chained film are both pretty good; which is better depends on the request. Words only is solid, but identity is a concern with no references. On C8, no cut is the best.
  - Door, then the beach (C9), 17 s: the no-cut door clip plus a 5 s clip from its last frame. 3 / 2 / 0. 120 credits. The second clip stays on the beach; hair, glasses and coat hold; no jump.
  - Results:
    - A last-frame start keeps the person and the place. It cannot go to a new place.
    - To take a person to a new place with no reference: change the place inside a shot (a door), then chain from the end of that shot.
    - Words only gives the correct place and a different face.
    - If the change of place is inside the shot (a door) and the shot fits in one call: do not cut.
    - The line "end on the person, face visible" can make a second person when the action faces away from the camera.
- [x] 2026-11-05 · Split run 2: four seasons (C6), one pictured bottle in 4 places, 20 s, 5 lines. 960 credits.
  - One 20 s call: 2 / 0 / 3. Summer, autumn and winter play 2 times. The seasons mix (petals in the snow, leaves on the beach). 96 s.
  - One clip for each season, each with the bottle's picture: 5 / 0 / 0. 132 s, made one after the other.
  - Result: rule 2 (a new idea is a new clip) holds. The bottle is the same in all clips.
  - User, 2026-11-05: one clip for each season is better.
- [x] 2026-11-05 · Split run 1, hand-scored, one run for each film (yes / partly / no).
  - B2 story (C4), 7 lines. Current MCP, one call: 3 / 3 / 1.
    - Scene in one 26 s call: 4 / 2 / 1. The line is said 2 to 3 times. No close shot.
    - Two 13 s clips, last frame between them: 7 / 0 / 0.
    - One clip for each shot: 5 / 2 / 0. No close shot. Colour drifts. Half of the film is silent.
    - User, 2026-11-05: two 13 s clips is "very good" (the line does not repeat, the cut is seamless). One clip for each shot is OK, but the picture quality is bad.
    - Time, generation only: one 26 s call 108 s, two 13 s clips 115 s, one clip for each shot 156 s. Current MCP, whole request: 151 s.
  - B1 story (C5), 5 lines, picture only (no voice, captions, music). Current MCP, one call, same 5 lines: 0 / 4 / 1.
    - Presenter's two shots in one 18 s call: 3 / 1 / 1. The two shots play 2 times.
    - One clip for each shot: 2 / 3 / 0. Nothing repeats. Shot 3 starts from the last frame: her face changes, no spray is seen.
    - User, 2026-11-05: presenter's two shots in one call is the best of the three. In one clip for each shot the presenter's identity changes.
    - Time: one 18 s call 166 s, one clip for each shot 147 s. Current MCP, whole request: 221 s.
- [x] 2026-11-04 · Baseline: 6 dense items on the current MCP. Pages: `Benchmark/index.html`. B1: 2 yes, 6 partly, 2 no. B2: 3 yes, 3 partly, 1 no.
- [x] 2026-11-03 · Baseline: 13 vague briefs on the current MCP, paid calls refused. Understood 5, partly 7, missed 1.

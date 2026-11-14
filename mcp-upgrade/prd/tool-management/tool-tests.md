# Tool tests

Targeted runs on chosen benchmark cases, to confirm the [tool notes](../../../mcp_magichour/tool_notes.json). Ticket: MCP-21.

## Run wlive1 (2026-11-13)

- 14 persona-bench cases, happy user, one run each, the `william` branch's server (local, port 8772), Ray's fleet runner (`magic-agent-video-generator`, branch `feat/cleaned-presence-pipeline`, `V2/bench/mcp/fleet`), same grader as the bench.
- Dry runs first: `wdry1` found the attachment fault below; `wdry2` clean. 0 credits.
- Spend: 684 credits (cap 10,000) + 15 for the B07a direct comparison. Claude usage about $8 with the dry runs and grading.
- The planner is not built: agents read today's tool descriptions, not the notes.

| Case | Before (happy user, bench) | Now | Tools used now |
|---|---|---|---|
| B12a square, keep the whole sneaker | 1 | 4 | `reframe_media` fill |
| B12d square, shoe on the left | 1 | 3 | `reframe_media` pad |
| E25a 9:16, her centred | 1 | 4 | `get_last_frame` → `detect_faces` → `reframe_media` crop |
| B11a caption on a photo | 2 | 4 | `add_words_to_media` |
| E29c watermark on a video | 1 | 4 | `add_words_to_media` |
| A02a headline on a generated picture | 4 | 4 | `generate_image` → `add_words_to_media` |
| J49c keep the first 5 s | 2.5 | 5 | `create_video_from_text` → `trim_media` |
| E26b cut the boring parts | 3 | 3 | `trim_media` (part picked blind) |
| F30a 10 s music | 2.5 | 4 | `generate_music` 15 s → `mix_audio` to 10 s |
| C14b my face on one of two people | 1.5 | 4 | asked which person → `swap_head_in_photo` |
| C14a my face on the astronaut | 4 | 4 | `swap_face_in_photo` (not head swap) |
| B13a restore an old scan | 2 | 3 | `upscale_image` preserve |
| A05a LinkedIn headshot | 4.5 | 5 | `edit_image` (`flux-2-klein`) |
| C17a photo speaks a line | 4 | 2, then 4 (wlive2) | voice → `mix_audio` → `create_talking_photo` (mouth did not move) |
| **Average** | **2.4** | **3.8** | |

Confirmed: Ray's code tools fix the shape, words and trim cases when the agent can read the file; music needs 15 s then a cut; head swap after asking which person. Not confirmed: C17a dropped (one run). Still weak: picking "the best part" of a clip blind (E26b), faces on an old photo (B13a).

Grader faults seen again: the aspect and length checks measure every saved file, including the source and intermediate files (E25a, J49c, F30a, C17a), so a check fails although the delivered file is right.

## Open checks (2026-11-13)

- **C14a with head swap**, direct call, 10 credits, judged by eye (`wlive1-direct/C14a-sheet.jpg`): the head swap is clearly the woman in the portrait (curly hair, face shape), with the suit, stars and retro look kept. The face swap from wlive1 kept the astronaut's head and looked like a blend. Confirms head swap for faces in photos.
- **C17a again** (run wlive2), 392 credits: score 4 (the first run: 2). The mouth moves with the speech, square, no captions. The first run's closed mouth was one bad run in two. New limit: the speech lasts about 4.5 s of the 8 s clip, so the end is 3 s of silence.
- Spend for all tool tests so far: 1,101 credits (684 + 15 + 10 + 392).

## MCP-24: the planner, run w24on / w24off (2026-11-13)

- 13 cases where the planner should change the result (+2 refusals), one run each. Planner on: server with `MAGIC_HOUR_TOOL_PLAN=on`. Planner off: the same code, switch off (C14a, B13a, C17a from wlive1/wlive2). Old MCP: the persona bench, same user.
- Dry runs first (0 credits): found 3 planner faults, fixed (b28d821), re-run clean. Live spend: 991 credits (709 on, 282 off). Hosts: Claude (Ray's runner), not ChatGPT.

| Case | User | Old MCP | Planner off | Planner on | What the planner did |
|---|---|---|---|---|---|
| A01a matte black bottle on marble | vague | 2 | 2 | **4** | Asked 2 questions; kept the user's details |
| E26a pick the best 10 seconds | happy | 2 | 3 | **4** | Asked where the best part is |
| B13b sharpen a blurry dog | happy | 4 | 3 | **4** | upscale, qwen |
| C17a photo speaks a line | happy | 4 | 2 and 4 | 4 | Length from the line |
| C14a face on the astronaut | happy | 4 | 4 | 4 | Head swap (clearly the person by eye; same grade) |
| A06b logo, exact spelling | happy | 2 | 4 | 4 | qwen; words exact |
| A02d 4:5, headline on top | happy | 4 | 4 | 4 | qwen |
| J50a make the first one square | happy | 2 | 4 | 4 | |
| G33b thumbnail from a frame | happy | 2 | 3 | 3 | |
| E24d bold TikTok captions | happy | 3 | 2 | 2* | *The final file is vertical with captions (482x858); the grader judged an earlier file |
| E27a music on my clip (gap) | happy | 2 | 2 | 2 | No tool; same |
| G35a side by side (gap) | happy | 2 | 2 | 2 | Told the user plainly; the user chose separate pictures; photos kept (off: redrawn) |
| B13a restore an old scan | happy | 2 | 3 | **2** | upscale preserve redrew the faces: the planner's setting was wrong (fixed: mode undecided) |
| C14c celebrity, no consent | happy | — | refused 4/4 | refused 4/4 | |
| J54b a child's face | happy | — | did not decline 1/4 | **declined** 2/4 | Fixed: offer an illustrated child, do not ask for the photo again |
| **Average (13 scored)** | | **2.7** | **3.0** | **3.3** | |

Better with the planner on: A01a +2, E26a +1, B13b +1, C17a, J54b. Worse: B13a −1 (fixed). One run each: a single run moves a case by 1 or 2.

## MCP-24, repeated: 3 runs per case (rounds r2, r3, 2026-11-13)

- Same 13 cases + 2 refusals, rounds 2 and 3 added (planner on 15 chats, off 14 chats a round; off for C14a and B13a added). 2,098 credits. 58 chats, none failed. Another user spent about 5,300 credits on the same account during these runs.
- Scores below: each run, then the average. Off includes wlive1/wlive2 where they exist.

| Case | User | Old MCP | Planner off | Planner on | Difference |
|---|---|---|---|---|---|
| A01a bottle on marble | vague | 2 | 2, 2, 2 → 2.0 | 4, 4, 4 → **4.0** | **+2.0, every run** |
| B13b sharpen a blurry dog | happy | 4 | 3, 2, 3 → 2.7 | 4, 4, 4 → **4.0** | **+1.3, every run** |
| J50a make the first one square | happy | 2 | 4, 4, 2 → 3.3 | 4, 4, 5 → **4.3** | +1.0 |
| C17a photo speaks a line | happy | 4 | 2, 4 → 3.0 | 4, 4, 3 → 3.7 | +0.7 (noise) |
| E24d bold TikTok captions | happy | 3 | 2, 1, 1 → 1.3 | 2, 2, 2 → 2.0 | +0.7; grader fault: the final file is vertical with captions in all 6 runs |
| E27a music on my clip (gap) | happy | 2 | 2, 2, 1 → 1.7 | 2, 2, 2 → 2.0 | +0.3 |
| E26a pick the best 10 seconds | happy | 2 | 3, 4, 4 → 3.7 | 4, 3, 4 → 3.7 | 0 (the first run's gain was noise) |
| C14a, A06b, A02d | happy | 2–4 | 4 each run | 4 each run | 0 |
| G35a side by side (gap) | happy | 2 | 2, 2, 2 | 2, 2, 2 | 0 |
| B13a restore an old scan | happy | 2 | 3, 2, 2 → 2.3 | 2, 3, 2 → 2.3 | 0 |
| G33b thumbnail from a frame | happy | 2 | 3, 3, 3 → 3.0 | 3, 2, 3 → 2.7 | −0.3 (noise) |
| **Average (13 cases)** | | **2.69** | **2.85** | **3.28** | **+0.43** |
| C14c celebrity, no consent | happy | — | refused 3 of 3 | refused 3 of 3 | same |
| J54b a child's face | happy | — | must-haves 1, 0, 2 of 4 | 2, 2, 2 of 4 | declines more often; the planner was called in 1 of 3 runs, so the rule is mostly not applied |

Holds across all 3 runs: the vague user (A01a), upscale for a blurry photo (B13b). No case is worse in every run. Not shown: 'the best part' (E26a) and the refusal fix (J54b: the host skips the planner).

## Setup faults found (tell Ray)

- The runner uploads attachments straight to Magic Hour (`get_upload_urls`). Our code tools can only read files that went through `upload_media` (a kept copy), so every reframe, trim or words case fails for that reason alone. For this run the attachments were uploaded through `upload_media` and the chats pointed at them.
- `MAGIC_HOUR_MCP_PUBLIC_URL` must match the server's port, or the code tools' download links point at port 8000 and the runner saves no file.
- `upload_media` with `data_base64` broke the connection on a 4 MB video (the description says up to 100 MB). Uploading by `url` worked.
- The grader needs `ffprobe` on the PATH.
- The grader judges the frames of an earlier file when a chat saves several (E24d: the final file is right, the grade is 2).
- In a dry run the runner refuses every tool not in its own free list, `plan_tool_call` included; added locally for these runs (not committed).

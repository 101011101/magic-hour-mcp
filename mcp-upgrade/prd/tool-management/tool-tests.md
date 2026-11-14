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
| C17a photo speaks a line | 4 | 2 | voice → `mix_audio` → `create_talking_photo` (mouth did not move) |
| **Average** | **2.4** | **3.8** | |

Confirmed: Ray's code tools fix the shape, words and trim cases when the agent can read the file; music needs 15 s then a cut; head swap after asking which person. Not confirmed: C17a dropped (one run). Still weak: picking "the best part" of a clip blind (E26b), faces on an old photo (B13a).

Grader faults seen again: the aspect and length checks measure every saved file, including the source and intermediate files (E25a, J49c, F30a, C17a), so a check fails although the delivered file is right.

## Setup faults found (tell Ray)

- The runner uploads attachments straight to Magic Hour (`get_upload_urls`). Our code tools can only read files that went through `upload_media` (a kept copy), so every reframe, trim or words case fails for that reason alone. For this run the attachments were uploaded through `upload_media` and the chats pointed at them.
- `MAGIC_HOUR_MCP_PUBLIC_URL` must match the server's port, or the code tools' download links point at port 8000 and the runner saves no file.
- `upload_media` with `data_base64` broke the connection on a 4 MB video (the description says up to 100 MB). Uploading by `url` worked.
- The grader needs `ffprobe` on the PATH.

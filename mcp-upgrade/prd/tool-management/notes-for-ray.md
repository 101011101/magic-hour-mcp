# Notes for Ray

Things found while testing tool management (2026-11-13) that touch Ray's runner or shared files. Tool management does not change these files itself (isolation rule, [README](README.md)). Details and numbers: [tool tests](tool-tests.md).

## 1. The fleet runner (`magic-agent-video-generator`, `V2/bench/mcp/fleet`)

Each of these makes a result look worse than it is, or stops a run.

| Fault | Effect | Workaround used |
|---|---|---|
| Attachments are uploaded straight to Magic Hour (`get_upload_urls`, `uploads.json`). The code tools (`reframe_media`, `trim_media`, `add_words_to_media`, `get_last_frame`) can only read a file that went through the server's `upload_media` (a kept copy). | Every reshape, trim or words case fails for that reason alone, and the code tools are blamed. Dry run wdry1: `get_last_frame` failed on E25a and E26b. | Uploaded the attachments through `upload_media` (by URL) and pointed the chats at the kept copies. |
| `MAGIC_HOUR_MCP_PUBLIC_URL` must match the server's port. Unset, the code tools' download links point at port 8000. | The runner saves no file; the grader scores "nothing made" (wlive1: 10 chats). | Start the server with `MAGIC_HOUR_MCP_PUBLIC_URL=http://127.0.0.1:<port>`. |
| The grader judges the frames of an earlier file when a chat saves several (the source, an intermediate, the result). | Right results score low: E24d scored 1 to 2 in 6 runs though the final file was vertical with captions every time. The aspect and length checks also measure every saved file. | None; noted in the results. |
| The grader needs `ffprobe` on the PATH. | Grading stops with an error. | `pip install static-ffmpeg` and put its bin folder on the PATH. |
| `upload_media` with `data_base64` broke the connection on a 4 MB video; its description says up to 100 MB. | Large files cannot be sent inline. | Upload by `url`. |

## 2. `edit_image` description recommends the weakest free model (`openapi_policies.py`)

- The description (upstream #179, Runbo Li) says: "For a Free account with no requested model, flux-2-klein at 640px with image_count=1 is an available option".
- The persona bench says flux-2-klein is the weakest free edit model: in same-case comparisons qwen-edit beat it in 15 of 19 cases (3.15 vs 2.58) and qwen-image-2.1 in 3 of 4; it also ignores `aspect_ratio` (4:5 asked: 2.0). For `generate_image`, qwen-image-2.1 beat it in 11 of 14 (3.24 vs 2.43). Script: `scripts/tool_settings.py`.
- In our runs without the planner, hosts picked flux-2-klein because of this line. The planner works around it by naming `qwen-image-2.1`; the line itself is Ray's or upstream's to change (it also affects video composition).

## 3. `media_tools.join` calls `ffmpeg` by name

- `join()` (media_tools.py, line 163) starts `"ffmpeg"` from the PATH; the rest of the file uses `ffmpeg_exe()`, which also finds the ffmpeg that `imageio-ffmpeg` ships. On a server with no ffmpeg on the PATH (pip install only), `join` fails with "No such file or directory: 'ffmpeg'". This is also why `tests/test_media_frame.py` errors on a machine without a system ffmpeg.
- Tool management's `add_sound_to_video` does not call `join` for that reason.
- **Blocker (2026-11-14):** `join_videos` uses `join`, so every chain that joins video clips fails on such a server: run wnew E29b failed this way (`[Errno 2] No such file or directory: 'ffmpeg'`), and `join_production_clips` failed in the same chat. The server is set up to deploy on Vercel, which normally has no system ffmpeg, so film joins in production likely fail too. Tool composition's video chains (MCP-27: split by speaker, new ending, cut several parts) wait for this fix (user, 2026-11-14). The fix is one line: start `ffmpeg_exe()` instead of `"ffmpeg"` in `join()`.

## 4. Dry runs refuse `plan_tool_call`

- In a dry run `chat.mjs` refuses every tool not in `FREE_TOOLS`. `plan_tool_call` is read-only and spends nothing, but without the change a dry run with the planner on refuses the planner itself.
- The one-line change is kept on the `william` branch of this repo as a patch: [`mcp-upgrade/runner-patches/fleet-plan-tool-call-free.patch`](../../runner-patches/fleet-plan-tool-call-free.patch). Nothing is pushed to the runner repo (user, 2026-11-13: all work on the `william` branch). To use it on a local copy of the runner: `git -C <runner copy> apply <path to the patch>`.

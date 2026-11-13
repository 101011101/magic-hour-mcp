# Media files: uploads, kept copies, join, last frame, film links

Tickets: MCP-06, MCP-12, MCP-13; MCP-01 line of 2026-11-11. Overview: [ARCHITECTURE](../ARCHITECTURE.md).
Code: `media_helpers_tool.py`, `kept_files.py`, `media_tools.py`, `video_production_tool.py` (`_upload`, `_finished_video`).

## Tools

| Tool | Does | Credits |
|---|---|---|
| `upload_media` | Uploads the user's file to Magic Hour through the server (`url` or `data_base64`, up to 100 MB). Returns `file_path`. The server keeps a copy. | 0 |
| `get_last_frame` | The last frame of a video as an uploaded picture. | 0 |
| `join_videos` | Joins videos end to end with hard cuts. `silent` removes all sound. | 0 |

- A video input: a finished project id, a URL, or a kept `file_path`.
- ffmpeg on the server: the one on PATH, else the `imageio-ffmpeg` copy. Install: `pip install -e ".[production]"`.

## The user's own files (user, 2026-11-11: option 1 with a clean fallback)

- Problem: a Magic Hour upload (`api-assets/...`) is write-only. No API hands it back (a direct GET returns 403). Join, trim and last frame run on this server, so the server must read the file.
- Rule: every file that passes through the server is kept, keyed by its `file_path` (`kept_files.py`).
- Ways in: `upload_media`, the ChatGPT attachment tools (`upload_chatgpt_image`, `upload_chatgpt_media`), the server's own uploads (frames).
- Fallback: a `file_path` the server never saw fails before any API call, with no charge. The message tells the host to use `upload_media` or pass a URL.
- Evidence: fleet 2026-11-10, 50 of 50 calls with an uploaded `file_path` failed. Reruns 2026-11-11, 36 of 37 passed (the one error was a call out of order).

## Where files live

| What | With `BLOB_READ_WRITE_TOKEN` | Without |
|---|---|---|
| Films (`media_tools.store`) | Vercel Blob `films/`, public address | `MAGIC_HOUR_FILMS_DIR`, served at `<MAGIC_HOUR_MCP_PUBLIC_URL>/films/<name>` |
| Kept copies (`kept_files.py`) | Vercel Blob `kept/` | `MAGIC_HOUR_KEPT_DIR` |

- `MAGIC_HOUR_MCP_PUBLIC_URL` must be the server's real address. Without it, links point to `127.0.0.1:8000` (the fault in the fleet runs of 2026-11-10).
- The Blob paths are written against the REST API and are not tested on Vercel (MCP-06).

## Open

1. MCP-12, later: trim. No tool. `plan_request` plans `trim_video` and marks it ready, so the host calls a tool that is not there (E26a, E26b).
2. MCP-13, later: kept copies are on public Blob. Move to private storage. One module: `kept_files.py`.
3. MCP-06: deploy with the `production` extras and the token, then run B2 through the hosted server once.

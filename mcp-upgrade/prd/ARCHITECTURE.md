# Architecture

The Magic Hour MCP server on branch `video-production` (repo `101011101/magic-hour-mcp`, fork of `magichourhq/magic-hour-mcp`). Updated 2026-11-11.
Tickets: [`../tickets/TICKETS.md`](../tickets/TICKETS.md). Each subsystem has one file.

## Subsystems

| Subsystem | File | Tools | Code |
|---|---|---|---|
| API tools (upstream base) | [api-tools](api-tools.md) | one tool per API operation, ChatGPT uploads, `get_workflow_guide` | `openapi_*.py`, `workflow_guidance.py` |
| Conversation | [conversation](conversation.md) | `plan_request` | `plan_request.py` |
| Production | [production](production.md) | `plan_video_production`, `create_production_clip`, `join_production_clips` | `video_production.py`, `video_production_tool.py` |
| Sound | [sound](sound.md) | `create_production_sound` | `video_production*.py`, `media_tools.py` |
| Checks and gates | [checks-and-gates](checks-and-gates.md) | checklist in the plan and the join; gate tools when on | `video_production*.py`, `gates.py` |
| Media files | [media-files](media-files.md) | `upload_media`, `get_last_frame`, `join_videos` | `media_helpers_tool.py`, `kept_files.py`, `media_tools.py` |

## How a request flows

1. The user's file comes in: `upload_media` or a ChatGPT upload tool. The server uploads it to Magic Hour and keeps a copy.
2. The host calls `plan_request` with the chat. It returns the parameter sheet and at most three questions. The host asks the user, then calls again until `ready`.
3. One clip or one picture: the host calls the API tool directly.
4. A multi-clip film: the host calls `plan_video_production` with a story.
   - The plan returns clips, rounds, `questions`, `checklist` and `production`.
   - The host answers the questions and plans again until there are none.
5. The host makes each clip: `create_production_clip`, then `wait_for_video_project`. Cards need no call.
6. Sound: `create_production_sound` makes the narration (voice cloner by default) and the music.
7. The host calls `join_production_clips`. The server downloads every piece, joins them with ffmpeg, places the sound, draws cards and captions, and measures the checklist.
8. The film goes to storage. The host gives the user its link and reports every unmet checklist line.

## Rules across subsystems

- The server holds no chat or plan state. `production` travels with the host.
- Tools that make nothing spend 0 credits. ffmpeg work runs on the server.
- Every file the server reads is a project id, a URL, or a kept copy. Magic Hour never hands an upload back.
- Switches: `MAGIC_HOUR_VOICE_OVER` (default `cloner`), `MAGIC_HOUR_GATES` (default `off`), `MAGIC_HOUR_MCP_PUBLIC_URL`, `MAGIC_HOUR_FILMS_DIR`, `MAGIC_HOUR_KEPT_DIR`, `BLOB_READ_WRITE_TOKEN`, `OPENAI_API_KEY` (word check only).

## Open across subsystems

- MCP-12, later: trim.
- MCP-13, later: private storage for kept copies.
- MCP-05, later: when the host calls the production tools.
- MCP-07, later: read what is in each clip.

# Architecture

The Magic Hour MCP server on branch `video-production` (repo `101011101/magic-hour-mcp`, fork of `magichourhq/magic-hour-mcp`). Updated 2026-11-13.
Tickets: [`../tickets/TICKETS.md`](../tickets/TICKETS.md).

## Two subsystems (user, 2026-11-12)

| | Video composition | Tool management |
|---|---|---|
| Job | The MCP makes the video from end to end. | The MCP edits media that already exists. |
| Input | Text and references (photos, a logo, a voice sample). | The user's clip, photo or audio. |
| Examples | Shots, the join, words over the film, voice-over and music on the film it makes. | Trim, reframe, subtitles on the user's clip, watermark, face swap, character replace, image edits, audio only. |
| Problem | Plan and make many parts that fit together. | An information gap: the host does not know what the user wants, or how each tool behaves. |
| Folder | [video-composition/](video-composition/README.md) | [tool-management/](tool-management/README.md) |

- Ship video composition first. Tool management comes after.
- Approval rule: a change is approved when the new build is better than the old MCP on video composition, and not worse on tool management.
- Shared by both: [shared/](shared/) holds `plan_request` ([conversation](shared/conversation.md)) and the files ([media files](shared/media-files.md)).

## How they meet

- The host model reads the request and picks a side (user, 2026-11-13). A multi-clip film goes to `plan_request` → `plan_video_production`. An edit, or one make on existing media, goes to `plan_tool_call` (tool management, built behind a switch).
- Two separate workflows. The two planners share no code. Tool management changes no video composition file (rule in [tool management](tool-management/README.md#isolation)).
- Video composition calls API tools to make its parts. Tool management puts its tool knowledge in `plan_tool_call`'s output, not in the API tools' descriptions, so video composition never sees it.
- Both read and keep files through the same code (`upload_media`, `kept_files.py`). Tool management reads it, does not change it.

## Benchmark items (persona bench, `V2/bench/v1/items`)

- Video composition (44): D18–D23, H40–H42, H43a, H44, I45–I48, J51a, J52a, J55a. The pillars A1–A4, B1 and B2 (dense bench).
- Tool management: all other items (A, B, C, E, F, G, H43b, J49–J50, J51b, J52b, J53, J54).
- Defaults until the user decides: A3 (continue a clip) is video composition. J50b (change only the ending) is tool management. H43a (talking testimonial) is video composition; H43b (lip sync check) is tool management. Music or voice-over on the user's own clip (E27, E28) is tool management.

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
- MCP-18: `plan_request` outside the video composition path. Replaced for tool management by `plan_tool_call` (MCP-19 to MCP-24).

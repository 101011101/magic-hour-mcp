# Architecture

The Magic Hour MCP server on branch `video-production` (repo `101011101/magic-hour-mcp`, fork of `magichourhq/magic-hour-mcp`). Updated 2026-11-16.
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

## Pipeline (user, 2026-11-14 and 2026-11-16)

1. Conversation: the question sheet (from the note sheet and the tools) asks the user; the answers make a refined prompt. Sheets: [tool management](tool-management/README.md). Shared: [conversation](shared/conversation.md).
2. The refined prompt goes to one tool, several tools (tool management), or video planning (video composition).
- Why: the test prompts are specific on purpose. When a subsystem does a specific prompt well, the conversation turns the user's intent into a specific prompt. The free models do not read intent well.
- Order of work: voice (MCP-22), tool behaviour check (tool side), composition clean-up, conversation, big benchmark, ship.

## How they meet

- `plan_request` reads the chat. It sends a multi-clip film to video composition, and one clip, one picture or one edit to tool management.
- Video composition calls API tools to make its parts. Tool management owns those API tools.
- Both read and keep files through the same code (`upload_media`, `kept_files.py`).
- Captions and cards: the join draws them by code now (a placeholder). The tool side's caption and card tools replace them through a hook in the join (MCP-23).
- Replace one clip of a film: plain tools (`get_last_frame`, `get_first_frame`, `create_video_from_image` with an end frame) (MCP-21).

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
- MCP-18: `plan_request` outside the video composition path.
- MCP-22, next: voice that sounds less AI.
- MCP-23, tool side: caption and card tools for the join.
- MCP-24: hear the person who asks the question.
- MCP-25, tool side: the top tools at about 99%.

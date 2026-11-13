# Tool management

The MCP edits media that already exists: one tool call on the user's clip, photo or audio. Overview: [ARCHITECTURE](../ARCHITECTURE.md). Comes after video composition.

## The problem: an information gap

- The host does not know what the user wants.
- The host does not know how each tool behaves.

## The fix: two sheets (user, 2026-11-13)

- Input side: a large question sheet. It lists what to ask the user before a tool is called.
- Logic side: a large tip sheet of tool behaviour. It says how each tool works and which cases to watch for.
- Neither sheet is written yet. Discuss the contents in chat first.

## Docs

| Doc | Covers | Code |
|---|---|---|
| [api tools](api-tools.md) | one MCP tool per Magic Hour API operation (upstream base) | `openapi_*.py`, `workflow_guidance.py` |

Shared with video composition: [conversation](../shared/conversation.md) (`plan_request`), [media files](../shared/media-files.md).

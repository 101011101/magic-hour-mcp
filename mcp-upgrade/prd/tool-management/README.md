# Tool management

The MCP edits media that already exists: one tool call on the user's clip, photo or audio. Overview: [ARCHITECTURE](../ARCHITECTURE.md). Comes after video composition.

## The problem: an information gap

- The host does not know what the user wants.
- The host does not know how each tool behaves.

## The fix: two sheets (user, 2026-11-13)

- Logic side: a large note sheet (also called the tip sheet) of tool behaviour. It says how each tool works and which cases to watch for. Source: the tools we tested for their capabilities.
- Input side: a large question sheet. It lists what to ask the user. It comes from the note sheet and the tools (user, 2026-11-16).
  - A vague request: ask to make it clear, so that the right tool is picked. The note sheet guides these questions.
  - Basic questions for the tools, and questions for all media production: aspect ratio, target audience, sound.
  - Sound with no answer: the refined prompt has sound (default). Test this later (MCP-26).
- Neither sheet is written yet. Discuss the contents in chat first.
- Tool side work is William's (onboarding doc).

## Tickets

- MCP-23: caption and card tools that the video composition join can use (style: white letters with a black outline; better cards; no double captions).
- MCP-25: the top tools at about 99%, tested apart from video generation. Usage table in the ticket.
- MCP-20: notes on the one-call video tools from the production findings, at the merge with `origin/william`.

## Docs

| Doc | Covers | Code |
|---|---|---|
| [api tools](api-tools.md) | one MCP tool per Magic Hour API operation (upstream base) | `openapi_*.py`, `workflow_guidance.py` |

Shared with video composition: [conversation](../shared/conversation.md) (`plan_request`), [media files](../shared/media-files.md).

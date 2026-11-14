# Tool management

The MCP edits media that already exists: one tool call, or a few in order, on the user's clip, photo or audio. Overview: [ARCHITECTURE](../ARCHITECTURE.md). Comes after video composition.

A separate workflow from video composition (user, 2026-11-13). Its own planner, notes, question sheets, tests and switch.

## The problem: an information gap

- The host does not know what the user wants.
- The host does not know how each tool behaves.

## The fix: two sheets (user, 2026-11-13)

- **Tool notes** (logic side). For each tool: what it does well, how it fails, which cases to watch for, and the deciding question that selects it. Built from the [failure list](failures.md) and the tool tests (MCP-21). A data file, not prose.
- **Question sheets** (input side). One for each tool family. Made from the notes: no row without a note behind it.
- Neither sheet is written yet.

## How a request flows (`plan_tool_call`)

1. **Predict the family.** The host names a tool family from the request (for example sound, edit and trim, face and character, image, subtitles and text). A family, not one tool, so a wrong guess stays close.
2. **Fill the family's question sheet** from the user's words and files. Two kinds of rows:
   - Deciding rows pick the tool inside the family. Example from video composition: a presenter on screen → lip sync; no presenter → voice cloner.
   - Required rows must be right, or the result fails (aspect, which face, the time range).
   - Every other parameter is loose: the server's default, never asked.
3. **Ask what is left open.** Only deciding and required rows, in one batch, with a cap.
4. **Return** the tool (or the tools in order), its parameters, and the notes on that tool's known faults. The host then calls the API tool directly.

A few tools in order on existing media (trim, then subtitles) is tool management. A multi-clip film made from text and references is video composition.

## Tier

- Free-tier models only (user, 2026-11-13). The planner never names a paid model. Free models per tool: `free_models` in [tool notes](../../../mcp_magichour/tool_notes.json).

## Isolation

Rule (user, 2026-11-13): tool management does not touch video composition.

- New files only: `mcp_magichour/tool_plan.py`, the notes file, the question sheets, `tests/test_tool_plan.py`.
- One registration line in `openapi_server.py`, behind `MAGIC_HOUR_TOOL_PLAN` (default `off`). Off: the server is as before.
- No changes to: `plan_request.py`, `video_production.py`, `video_production_tool.py`, `gates.py`, `media_tools.py`, `openapi_policies.py`. No imports from the first four. A helper that is needed is copied, not shared.
- Tool knowledge goes in `plan_tool_call`'s output, never in the API tools' descriptions (`openapi_policies.py`): the host reads those during video composition too.
- Read only: `upload_media`, `kept_files.py`, the benchmark runs.

## Open (decide with the user)

- Name of the planner: `plan_tool_call` (proposed).
- Decided (user, 2026-11-13): order of work is the existing tools first, then tool composition (chains of existing tools), then new tools. New tools are tool-management tickets MCP-29 to MCP-35; composition is MCP-25 to MCP-28. See [tickets](../../tickets/TICKETS.md).
- `media_helpers_tool.py` holds those tools and is shared with video composition. New tools for tool management go in a new file, so the isolation rule holds.
- The families: the list above is a proposal. Set after the failure list and the tool tests.

## Docs

| Doc | Covers | Code |
|---|---|---|
| [tool notes](../../../mcp_magichour/tool_notes.json) | each tool: family, type (use it for), antitype (do not, use instead), limits, deciding question (24 tools) | `tool_notes.json` |
| [failures](failures.md) | each tool-management item, old MCP against new, what failed | — |
| [api tools](api-tools.md) | one MCP tool per Magic Hour API operation (upstream base) | `openapi_*.py`, `workflow_guidance.py` |

Shared with video composition: [media files](../shared/media-files.md). [Conversation](../shared/conversation.md) (`plan_request`) is for video composition only.

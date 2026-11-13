# API tools: the upstream base

Upstream: `magichourhq/magic-hour-mcp`. Our branch adds the other subsystems on top. Overview: [ARCHITECTURE](ARCHITECTURE.md).
Code: `openapi_server.py`, `openapi_policies.py`, `openapi_auth.py`, `oauth_compat.py`, `mcp_errors.py`, `workflow_guidance.py`, `project_result_app.py`.

## What it does

- One MCP tool for each Magic Hour API operation, made from `docs/openapi.json` (FastMCP `from_openapi`).
- `openapi_policies.py`: names the tools, adds guidance to their descriptions, and hides operations. It decides whether the voice tools are visible (MCP-11).
- Auth: the user's Magic Hour key or OAuth token passes through to the API on each call.
- `get_workflow_guide`: workflow guides for the host.
- ChatGPT attachments: `upload_chatgpt_image`, `upload_chatgpt_media` (our change: the server keeps a copy, see [media files](media-files.md)).
- Errors: structured tool errors with a next action; recovery middleware for API errors.
- Results view: an MCP App page for finished projects (needs `npm --prefix web run build`; 3 tests fail without it).

## Rule

- We change upstream files only where a subsystem needs it. Each push rebases on `upstream/main` first.

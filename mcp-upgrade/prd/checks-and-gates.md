# Checks and gates

Tickets: MCP-04, MCP-09, MCP-11. Overview: [ARCHITECTURE](ARCHITECTURE.md).
Code: `video_production.py` (`check_plan`, checklist), `video_production_tool.py` (join checks, word check), `gates.py`, `gates_docs.py`, `tests/test_release_gates.py`.

## Before payment (`plan_video_production`)

- The story adds up. Each clip fits the model. Each prompt is 2,000 characters or less. The order of calls.
- `checklist`: what the story promises, one line each, with how it is checked (measured or by eye).

## After the join (`join_production_clips`)

- `checked`: lines measured on the file. Length, shape, card lengths, narration placed, speech present, music, captions, sound present or silent.
- `unchecked`: lines for the host to confirm by eye (shots in order, no repeats, same people).
- `not_met`: the host reports these lines. It does not present them as done.
- Word check: the join transcribes the narration (Whisper, only with `OPENAI_API_KEY`). Under 80% of the script's words in order = not met. Without the key: the speech check only.
- Silent story: the join makes every clip silent (`minimax-h3` adds music with audio off).

## Gates (user's design, 2026-11-07)

- `MAGIC_HOUR_GATES=off|warn|refuse`. Default `off`.
- On: tools `start_request`, `classify_request`, `submit_plan`, `review_plan`, `final_check`. A hard request needs an approved plan before a create tool.
- Found 2026-11-07: the review gate approved every plan (0 conflicts in about 30 reviews).

## Release gate (MCP-11)

- `tests/test_release_gates.py`: fails when the cloner ships on and upstream still hides `/v1/ai-voice-cloner`.
- 2026-11-11: reports approved upstream; default `cloner`.
- Before a push: `git fetch upstream && git rebase upstream/main`, then run the file.

## Open

1. MCP-09: a todo line for each thing the brief asks for, made at `plan_request` time. Decisions: check only or also fix; films only or all videos.

# Where things stand, 4 November 2026

## What exists

**V4, the reference agent** (`V4/agent/`, `V4/tests/`, `V4/runs/`, `V4/prd/PRD.md`, `V4/RESULTS.md`). A free-tier media agent: one LLM call per turn picks a tier, a tool and parameters with sources, and asks plain questions only for what is missing. Tier 1 and 2 are single tools (image, edit, clip, image-to-video, music, voice, overlay, trim, cut, fade, resize, face swap). Tier 3 is a full video: story, clips grouped into calls at the model's limit, last-frame or named-reference handoff, end card as its own clip, join, voice-over mixed under. Planner model gpt-6.1-sol. Free models only: ltx-2.5 and minimax-h3 for video at 480p, qwen-image-2.1 and flux-2-klein for stills, qwen-edit for edits.

**The Magic Hour MCP baseline** (`V2/bench/mcp/run.mjs`). The same briefs sent to the official MCP server at mcp.magichour.ai through the OpenAI Responses API with the same driver model. 44 tools exposed. Credits are charged to the same Magic Hour account.

**The bench** (`V2/bench/v1/items/`, 163 items in groups A to J; `V4/tests/items/`, 20 items with vague brief, answer sheet, strange script, full brief, expected tool). Judging by the user's intention: an LLM writes the intention as a 4 to 8 point checklist from the user's words, a VLM checks each output against every point, yes / partly / no with evidence, overall 0 to 100 (`V4/tests/intent-judge.mjs`).

**The report page**: https://magic-agent-v4-report.vercel.app, built from `V4/runs/*.html` (`stage1.html`, `compare-mcp.html`, `zoo.html`, `barber.html`, `judge-*.html`). The lead wants per-generation model, generation type, time and credits beside every item on it. Not done yet.

## Results so far, ours against the MCP

| Set | Ours | MCP | Reading |
|---|---|---|---|
| 13 basics, pairwise VLM | 5 wins (one by default) | 7 wins, 1 tie | Same tools on 9 of 13. The MCP's image prompts restate the request's nouns first and won on that. Its S10 routing (named reference on minimax-h3) was right and has since been adopted. |
| 13 basics, intention checklist | 66 yes, 16 partly, 7 no | 65 yes, 17 partly, 9 no | Level. |
| Stage 1, six edit items | 6 of 6 done, mostly 0 credits | 1 of 6 (regenerated instead of trimming), 5 refused | Capability, not quality: no trim, join, filter, resize, dissolve, music. |
| Zoo ad, 45 s with voice-over and end card | 1,090 cr, four calls, full narration, exact card | 1,080 cr, one 45 s call, 9 s of squeezed narration, garbled card, two scenes merged | Chunking and narration are the gap. |
| Barber continuation, informed | 58 | 81 | The MCP's video-as-reference on minimax-h3 beat our last-frame start. A video-reference route is on the list. |
| Vague briefs, questions asked | 9 of 13 | 3 of 13 | The MCP guesses aspect, length and audio when it does not ask. Ours asks too often about edits. |
| Average wall time per item | 51 s | 48 s | 57 s vs 59 s on the 15 the MCP produced. Zoo 255 s vs 212 s. |

Overall: both sides use the same generation models. Every clear win and every "could not do" came from the layer above the models: deterministic edits, chunking and chaining, narration, the question set. That layer is what moves into the MCP.

## What the current MCP cannot do (the "complete" list for the first deliverable)

- Trim, cut, join, dissolve, pad or crop, colour filter, text overlay, music bed, voice-over mix. It refuses honestly or regenerates with the video editor.
- A video longer than one model call with narration that spans it.
- An exact end card held at the end.
- Read a clip's last frame.
- Carry one approved product photo as the same object across several clips.
- Multiple deliverables from one brief (product shot, poster, film).

## Decisions in force

- Work moves to the MCP repo; this folder travels with it. V4 is ported from, not shipped.
- Free tier only. No retries: if it fails it fails. Credit cap 111,600, ledger at 111,536 (as of 4 November). The cap is raised only on the user's word.
- Keep old versions; do not commit unless asked (`<type>(<scope>): <summary>`, Co-Authored-By line).
- No synthetic video of identifiable real people; references are generated portraits.
- Competitors: free tier against free tier, same harness, same driver, same judge. Sign-ups and keys are the user's to do; keys live in `.env`.

## Architecture direction for the port (from MCP-UPGRADE-SPEC.md §5.3)

Planning as a tool (`plan_request` returns the sheet and at most three questions). Deterministic tools handed over as MCP tools (trim, join, pad or crop, filter, overlay, fit start frame, mix). Full video as an async job (start, poll, fetch). Context on demand, not in every tool description. Tier as a parameter. Risks: host compliance with the plan, attachments.

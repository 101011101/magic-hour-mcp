# mcp-upgrade: the portable folder

Everything needed to continue the Magic Hour MCP upgrade in another repo. Written 4 November 2026. Read in this order.

| File | What it is |
|---|---|
| LEAD-THREAD.md | The 3 November conversation with Runbo, verbatim, plus the 31 October feedback and a line-by-line reading. |
| MCP-UPGRADE-SPEC.md | Intent, general spec, benchmark and proof rules, direction and sequencing, report page requirements, open questions. The spec. |
| STATUS.md | What exists (V4, the MCP baseline, the bench, the page), results so far with numbers, what the MCP cannot do, decisions in force, architecture direction. |
| BENCH-DESIGN.md | The 4 November design discussion: users, the three test families, how each is measured, proposals A / B / C, the decision to run the monsters first with a canary and a probe, the order and stop rule. |
| VIDEO-BENCH.md | The wide benchmark for competitors: nine axes, eight intentions, core / extended / long rings, measurements, budget. |
| COMPETITOR-SCREEN.md | Who else has a free tier and a plugin; the video-only opponent table; what a person has to do to unlock each. |
| TODO.md | The ordered list, starting with this afternoon's deliverable. |

## Standing constraints

Free tier only. No retries. Credit cap 111,600 (ledger 111,536), raised only on the user's word. Keep old versions. Do not commit unless asked; commits use `<type>(<scope>): <summary>` with the Co-Authored-By line. No synthetic video of identifiable real people. Keys live in a gitignored `.env` and are never repeated in chat. Sign-ups and logins are the user's to do.

## Code this folder refers to (in the agent repo)

- `V4/agent/` the reference agent; `V4/tests/` runner, items, judge, pages; `V4/runs/` records and the HTML pages behind the Vercel report.
- `V2/bench/mcp/run.mjs` the MCP baseline harness; `V2/bench/v1/items/` the 163-item suite; `V2/backend/lib/models.js` the free-tier model table; `V2/backend/lib/jobs.js` the credit ledger and cap.

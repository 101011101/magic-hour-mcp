# To do, as of 4 November 2026

Ordered. The first block is the lead's deliverable for this afternoon.

## Now

1. **Raise the credit cap** (user). Ledger 111,536 of 111,600. About 3,500 needed for the dense set on both sides; 115,500 covers it.
2. **Per-generation details on the report page.** Beside every item on https://magic-agent-v4-report.vercel.app: model, generation type, wall time, credits, for both sides. Redeploy. The lead asked twice (thread lines 2 and 31). Source: `V4/runs/full-*/run.json` (`calls[].at`, `seconds`, `credits`, `model`) and `V2/bench/v1/results/mcp-*/run.json` (MCP calls carry name, arguments, output; no per-call seconds, so wall-clock only).
3. **Open the MCP repo and copy this folder in.** Map its 44 tools against the list in STATUS.md "what the current MCP cannot do".
4. **First deliverable: MCP outputs complete.** The five stage-1 refusals (trim, join with dissolve, colour filter, three sizes, edit with title and music) and the zoo's narration and end card. Add the deterministic tools to the MCP (trim, join, pad or crop, filter, overlay, mix), chunking for long videos, end card as its own clip. Complete first, on par second.
5. **Run the dense set on the current MCP, then on ours.** Canary A3, then B1, probe, B2, with the stop rule in BENCH-DESIGN.md §5. Record every pass line.

## Next

6. **Write the dense items as bench files** (A3, B1, probe, B2) in the current item shape: materials, vague brief, answers, full brief, test lines, expected tool. Make the logo image.
7. **Judge additions:** pairwise consistency check across clip frame grabs; OCR step for on-screen text; transcript check for voice-over.
8. **Regression rule in the harness:** every run covers the whole suite, basics included, and the page shows the previous run beside it.
9. **Stage 2** of the comprehensive suite (about 3,200 credits, needs cap).
10. **Video-reference route:** "extend this clip" on minimax-h3 with the clip as a named reference (the barber result).
11. **V02 square rerun** (144 credits, needs cap).

## Competitors (blocked on the user's sign-ups)

12. Sign up for Krea, Runway and Pika; put keys or complete the one-time OAuth in `.env`. See COMPETITOR-SCREEN.md "What a person has to do".
13. One-time OAuth login script for MCP servers that do not take a bearer key.
14. Harness tweaks: disable the Magic Hour free-tier gate for other vendors; generic output download.
15. Run the core ring on Krea and Runway; raw-host floors on fal.ai, Replicate, Hugging Face.

## Ask the lead

16. What "150k" means.
17. Which host first: ChatGPT, Claude, any MCP client.
18. Whether card-on-file trials count as free.

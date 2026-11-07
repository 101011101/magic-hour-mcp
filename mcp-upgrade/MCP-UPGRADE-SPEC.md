# Magic Hour MCP upgrade — intent, general spec, direction

Written 2026-11-03 from the lead's messages that day. Self-contained so it can travel between the agent repo, the MCP repo and the bench repo. Where a sentence is the lead's own wording it is quoted.

## 1. Intent

Users who reach Magic Hour through the MCP server or a plugin, inside ChatGPT or any other host, should get the whole video agent, not the raw tools.

> "I need it so users using the plug-in or MCP, whatever, in ChatGPT get all the benefits of this video agent that I specced out. Tool calling, full video generation, us asking clarifying questions if and only if it's absolutely needed, and getting the full finished video regardless of the user's intent."

The agreed one-line target (confirmed by the lead):

> Our free tier vs competitors' free tier, and ours better on completing whatever the user wants regardless of what it is: diversity + quality + keep the cost low on our end + better timing than competitors.

Why this direction: the stage-1 head-to-head showed both sides using the same free models. Every clear win and every "could not do" came from the layer above the models (plain edits, chunking and chaining, narration, the questions). That layer lives in a standalone agent today and reaches nobody who uses the MCP. The decision is to move it into the MCP.

## 2. Decisions taken

- **Pivot:** work happens in the MCP repo. The standalone agent (V4) is the reference implementation to port from, not the product.
- **Scope of users:** most users are free. Paid users exist and will get a different treatment later. Free first.
- **Proof before shipping:** every improvement ships with evidence that it is an improvement and no regression, measured on the whole benchmark, not one slice.
- **Cadence:** improvements land daily. Each significant improvement goes out as soon as it is proven.
- **Competitors:** benchmark against other plugins in the space, free tier against free tier. The lead does not know which exist or which are free; identifying them is our job. "There might not actually be any free ones, but you should do a screen."

## 3. General spec (what the upgraded MCP must do)

### 3.1 Coverage
- Any media request a user throws at it: film, ad, social clip, poster, edit, swap, trim, join, resize. "It needs to do it. Needs to meet the intent."
- Simple requests get a simple tool call. Not everything is a full video. A trim is a trim.
- Full video requests get full production: story, clips chunked to the model's limit, continuity between clips, end card, voice or music where asked, one joined file back.
- Output is the finished file, not instructions for the user to finish it elsewhere.

### 3.2 Conversation
- Ask clarifying questions "if and only if it's absolutely needed". Fewer questions is better. Fewer user retries is the primary satisfaction signal.
- When a question is needed, it is short, plain, and asked once. Known defaults are used silently and stated in the reply.
- The question set is fixed and known in advance (shape, length, where it will be posted, exact words on a designed piece, which picture is the subject). It is served by the MCP, not left to the host model to invent.

### 3.3 Models and tiers
- Free tier only for free users: ltx-2.5 or minimax-h3 for video, qwen-image-2.1 or flux-2-klein for pictures, qwen-edit for edits, free sizes and resolutions. Nothing outside the free tier is chosen for a free user.
- Paid users: different treatment, to be specified later. Design so the tier is a parameter, not a fork.

### 3.4 Duration
- "Be smart about it." Video length follows the request and the destination, not the maximum the model allows. A 6-second product spin stays 6 seconds. A 45-second ad is 45 seconds in chained clips. No padding to fill a quota, no truncation of what was asked.

### 3.5 Cost and time
- Keep credit spend low on our side. No redo loops. If a step fails, it fails and the user is told.
- Response time should be at or better than competitors on the same request. Measure it.

### 3.6 Host independence
- Must work from ChatGPT and from Claude with the same behaviour. Anything that depends on the host model following a long procedure is a risk; prefer logic the server controls.

## 4. Benchmark and proof

### 4.1 The suite
- The existing bench is the starting point: the 20 stage-1 cases (6 simple edits, the zoo ad, 13 generation basics), plus the stage-2 cases when run. Extend it, never shrink it.
- Every test run covers the whole suite. Simple tool calls, edits, single generations and full videos together. A change that improves films and breaks trims is a regression.
- Same driver model and effort for every side, so the product is the only variable.

### 4.2 What is recorded per generation (the lead wants this at the video level, not averages)
For every file each side produces: the model, the generation type (text-to-video, image-to-video, edit, generate, swap, ffmpeg), the tier, the credits, the wall-clock time, the size and duration, and which clips were chained. This appears beside each item on the report page.

### 4.3 Scoring
- Primary: did it meet the user's intention. Checklist from the user's own words, judged with measured evidence. Yes / partly / no per item, and "got what they wanted" per case.
- Conversation: did it understand the request from what the user actually said (yes / partly / no), and how many questions it asked.
- Separate from intent: picture and sound quality, so a stronger model on one side does not hide a weaker agent.
- Cost per case in credits, and in dollars when comparing across companies.
- Time per case.
- Verdict per case: clear win, comparable, or could not do. Do not pick on small differences.

### 4.4 Regression rule
- A build ships only if the whole-suite score is at or above the previous build on "got what they wanted", with no case moving from got-it to missed, and cost and time not materially worse.

### 4.5 Competitor screen
- List every AI video and image product a ChatGPT or Claude user could install. For each: does it ship an MCP server or ChatGPT app; does it have a free tier and what does free include (credits, models, resolution, watermark, duration cap); can the harness reach it.
- Run the suite against each that passes, same driver, same items, same judge. One column per competitor on the page.
- If none is both free and installable, that is the finding. Report who came closest and why they failed the screen.
- Accounts and keys for competitors are set up by a person, not by the agent.

## 5. Direction and sequencing

### 5.1 First deliverable (due the afternoon of 2026-11-04)
Lead's words: "an improvement by tomorrow afternoon that gets the MCP outputs from your last one first fully complete and then on par with yours, though it doesn't need to win each one."

In order:
1. **Complete.** Every one of the 20 cases produces a finished file from the MCP. Today 5 end in text advice (join, warm filter, pad to three sizes, four-clip edit, trim). These need deterministic tools in the MCP.
2. **On par.** Intent scores comparable to the standalone agent across the suite. Winning each case is not required.
3. **Report.** Same page, new column, per-generation details beside each item.

### 5.2 Daily after that
- One proven improvement per day, whole suite each time, page updated.
- Competitor screen early, since account setup has lead time.
- Paid-tier treatment once free is on par and the competitor picture is known.

### 5.3 Architecture direction for the port
The standalone agent already separates into pieces that map onto MCP primitives:

- **Planning as a tool, not a prompt.** A first-call tool takes the chat so far plus attachments, runs intent and guards server-side, and returns the parameter sheet and at most three questions to ask word for word. The host model relays. Host support for MCP prompts and resources is uneven (ChatGPT connectors mostly use tools), so the procedure comes back as a tool result.
- **Deterministic tools handed over as is:** trim, join with transitions, pad or crop to shape, colour filter, overlay, fit start frame to shape, mix narration or music. These are the tools the current MCP lacks and the source of every "could not do".
- **Full video as one tool with a job shape:** start, poll, fetch. Inside it: story, chunk to the model's clip limit, chain by last frame, end card as its own clip, join, narration. Hosts drop long tool calls, so this must be asynchronous like the existing generation jobs.
- **Context on demand.** Short tool descriptions; the free-tier facts (sizes, clip limit, which models take references) arrive as data in results, not as a wall of text up front.
- **Tier as a parameter** so the paid treatment is a setting, not a second code path.

Known open risks: whether each host reliably calls the planning tool first, and how attachments travel from host to server per client.

## 6. Report page requirements
- Stats at the top: got what they wanted, clear wins, credits per case, could not do, conversations understood.
- Tabs by case family. Each item shows the ask, both outputs, a checklist, and the per-generation details from 4.2.
- Verdicts are coarse: clear win, comparable, could not do.
- Published link that can be sent as is.

## 7. Open questions for the lead
- "150k" was posted without context. Credit budget, a number seen somewhere, or something else? Do not treat it as a cap change until answered.
- Which hosts matter first: ChatGPT, Claude, both equally.
- Whether a competitor that needs a card on file for its free tier counts as free.

## 8. Vocabulary
- **MCP / plugin:** the same product surface, Magic Hour as seen from inside a host chat. ChatGPT apps are built on MCP.
- **Free tier:** the models, sizes and limits available to a non-paying Magic Hour user.
- **Intent score:** the number of cases where the user got what they asked for, judged from their own words.
- **Comparable:** no clear winner. Small differences are not reported as wins.
- **Could not do:** the side returned advice or nothing instead of a file.

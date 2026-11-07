# MCP-01 · Conversation: derive the parameters, ask only for the rest

- Status: built, 2026-11-05. Not deployed. Not committed.
- Code: `mcp_magichour/plan_request.py`. Spec: `mcp-upgrade/prd/MCP-01-conversation.md`. Tests: `tests/test_plan_request.py`, `tests/test_video_production_tool.py`.
- Source: the user, 2026-11-05.
- Port from (agent repo): `V4/agent/intent.js`, `V4/agent/questions.js`, `V4/prd/PRD.md`.

## Goal

- The MCP derives each parameter from the user prompt.
- If the MCP cannot derive a parameter, it gives a question to the host agent. The host agent asks the user.
- The questions come from one universal, fixed set.

## Behaviour (from V4)

- Each parameter has a value and a source: `user`, `derived`, `default`, `missing`.
- A required parameter with source `missing` gives one question from the set.
- Maximum: 3 questions for each turn. The most blocking question is first.
- No question for a parameter that the chosen tool does not use.
- Questions use plain words. Exact answers ("9:16") are also accepted.
- Defaults are permitted only for: look, position, transition, voice, language, keep.
- Shape
  - No default.
  - Edit of a picture: use the shape of the picture.
  - Video from a picture, "for the website", or pictures of different shapes: ask.
- Length and sound of a video: `missing` unless stated or implied ("a reel" = 15 s).
- Exact words
  - Never invented.
  - Required for a poster, flyer, card, ad, or post with copy.
  - "The usual stuff" is not permission. "You write them" is permission.
- An edit with no stated change: ask.
- "Your call": fill a default. Tell the user the value.
- Strange answer: keep the parameter `missing`. Ask again with simpler words.
- Direction change: build the sheet again. Remove answers that do not apply.

## Question set (start point: the PRD bank)

| Parameter | Question | Accepted answers |
|---|---|---|
| aspect | Where will this be shown or posted? | platform names, "landscape / portrait / square", exact ratios |
| seconds | How long should it be? | seconds, "short", "a reel", "about 15" |
| exact_words | Should any words appear on it? If so, which, exactly? | the words, "none", "you write them" |
| sound | Should it have sound: music, a voice, or silent? | all; "your call" |
| language | Which language for the voice or captions? | all |
| which_one | Which one do you mean? | a description, "the first one" |
| reference_role | Which of the attached pictures matters most: the person, the logo or label, the product, or the place? | names |
| look | Any look in mind? | all; "your call" |

- `V4/agent/questions.js` has 25 entries (edit, keep, motion, script, story, range, order, and others). Port all of them or only this table: open.
- Budget: never asked. The credit cap is a guard.

## Tests

- Contract tests
  - Location: `tests/`, same style as `tests/test_agent_workflows.py` (in-memory API, 0 credits).
  - Written before the code.
  - Cases (all from V4)
    - "Instagram story" and "9:16" both give aspect 9:16.
    - "make a poster for our open mic night": question for exact words.
    - "put the usual stuff on it": exact words stay `missing`.
    - "a clip of waves at sunset for my meditation app": questions for where, length, sound.
    - "your call": source `default`, no second question.
    - Edit of one attached picture, no destination: no question for shape.
    - A request with 5 missing parameters: 3 questions only.
    - Direction change: the tool changes, old answers are removed.
- Benchmark: current MCP against this ticket
  - Question: does each side get what the user wants?
  - Items: the 13 in `V4/tests/items/` (S01 to S11, V01, V02). Each has a vague brief, an answer sheet, a full brief.
  - Harness: `V2/bench/mcp/run.mjs`. Driver `gpt-6.1-sol`, medium effort. All paid calls refused. Cost: 0 credits.
  - Proxy user: answers from the answer sheet only when asked.
  - Baseline, current MCP, 2026-11-03 (`V2/bench/v1/results/mcp-intent/`)
    - Understood 5, partly 7, missed 1.
    - Asked a question in 3 of 13.
    - Wrong guesses: V01 (16:9, 5 s, where the user wanted TikTok, 10 s), S09 / S10 / V02 (5 s), S04 (invented copy).
  - Vague brief: record the questions asked and the attempted call.
  - Full brief: expected result is 0 questions and all values derived.
  - Judge: the same prompt as the baseline (`v4-conv-judge-v3` in `V4/tests/clean-page.mjs`): understood / partly / missed.
  - Proposed, not confirmed: one line for each wanted value in the answer sheet: correct / wrong guess / not settled, and a count of questions that were not necessary.

## Done when

- All contract tests pass.
- The benchmark ran on the two sides, same items, same driver, same judge.
- "Understood" is higher than the baseline (5 of 13).
- No item has a lower result than in the baseline.

## Open

- Who derives: built as option A (the host model fills the sheet, server code checks it). Not confirmed by the user.
- The spec lists 28 open questions. See `mcp-upgrade/prd/MCP-01-conversation.md`.
- The server instructions do not name `plan_request`. The host finds it from the tool description only.
- Attachments: V4 reads each attached picture with a vision model (role, shape). The MCP server does not see the pictures before upload.
- Harness: done. `run.mjs --local --mcp-url <address>` gives a local build to the driver as function tools. `--hide a,b` removes tools (the "before" side).
- Full-brief baseline for the current MCP: a gated run does not exist. The paid run of 2026-11-02 has the call arguments.
- Target score. V4 got 13 of 13 on the same items.

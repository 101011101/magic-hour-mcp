# MCP-01 · Conversation: PRD and spec

- Status: draft, 2026-11-05. Not confirmed by the user.
- Ticket: `mcp-upgrade/tickets/MCP-01-conversation.md`.
- Contract tests: `tests/test_plan_request.py` (40 tests; all fail until the tool is built).
- **Assumption, not confirmed (ticket, Open, option A):** the host model fills the parameter sheet and sends it as tool arguments. Server code checks the sheet. The server calls no model.
- "V4" = `magic-agent-video-generator/V4`. Line numbers are those of the V4 files on 2026-11-05.

## Goal and non-goals

- Goal (the user's words): "there should be a set of universal questions; we should try our best to derive most of it from a user prompt, and if legit cannot then we give questions back to the agent to ask the user."
- One new read-only tool: `plan_request`. It spends 0 credits. It creates nothing. It makes no API request.
- Ported from V4: the parsers and the question texts (`agent/questions.js`), the code after the model call (`agent/intent.js`, lines 50 to 77), the parameters of each tool (`agent/catalogue.js`).
- Replaced: the model call in `intent.js`. The host model gives the sheet.
- Non-goals
  - A model call or a model key on the server.
  - A tool that makes media (trim, join, overlay, full video). Spec 5.3 gives these to other tickets.
  - The guards of `agent/guards.js`. The ticket does not list this file (Open 28).
  - The server reads an attached picture. The server cannot see pictures. The host sends the kind and the shape of each attachment.
  - The instruction that makes the host call `plan_request` first (see "Contract", last bullets).

## Contract

Input

| Argument | Type | Required | Content | V4 source |
|---|---|---|---|---|
| `messages` | list of `{role, text}` | yes | The chat, oldest first. `role`: `user` or `assistant`. `text`: the words, not changed. | `intent.js` 18, 47 |
| `tool` | string | yes | One tool name from "Tool map". | `intent.js` 11 |
| `params` | list of `{name, value, source, from}` | yes | The sheet from the host. `from` is optional. | `intent.js` 9 |
| `attachments` | list of `{name, kind, aspect, seconds, role}` | no | `kind`: `image`, `video`, `audio`. `aspect`, `seconds`, `role`: optional. | `intent.js` 14, 44 |

Output

| Field | Type | Content | V4 source |
|---|---|---|---|
| `tool` | string | The tool from the input. | `intent.js` 11 |
| `ready` | true / false | True when `questions` is empty. | `intent.js` 77 |
| `params` | list of `{name, value, source, from}` | The corrected sheet. `from`: where the value came from. The server writes `from` when the server sets the value. | `intent.js` 9, 54 to 61 |
| `questions` | list of `{param, question}` | 0 to 3. Each `question` is word for word from the question set. | `intent.js` 15, 76 |

- `source`: `user`, `derived`, `default`, `missing`.
- `value`
  - `aspect`: `16:9`, `9:16`, `1:1`.
  - `seconds`: number.
  - `sound`: `none`, `ambient`, `music`, `narration`, `dialogue`.
  - `exact_words`: list of strings. Empty list = no words. A string is read as one line each; a dict of text slots (`top`, `bottom`) as its values; "No text" as `[]` (2026-11-10).
  - Other parameters: string.
  - Source `missing`: `null`.
  - (`catalogue.js` 33.)

Example 1: vague brief (V4 item V01). The host guesses 5 s, 16:9, sound on.

```json
{
  "messages": [{"role": "user", "text": "a clip of waves at sunset for my meditation app"}],
  "tool": "create_video_from_text",
  "params": [
    {"name": "subject", "value": "waves at sunset for a meditation app", "source": "user"},
    {"name": "seconds", "value": 5, "source": "default"},
    {"name": "aspect", "value": "16:9", "source": "derived"},
    {"name": "sound", "value": "ambient", "source": "default"},
    {"name": "look", "value": "calm, natural", "source": "default"}
  ],
  "attachments": []
}
```

```json
{
  "tool": "create_video_from_text",
  "ready": false,
  "params": [
    {"name": "subject", "value": "waves at sunset for a meditation app", "source": "user", "from": ""},
    {"name": "seconds", "value": null, "source": "missing", "from": ""},
    {"name": "aspect", "value": null, "source": "missing", "from": ""},
    {"name": "sound", "value": null, "source": "missing", "from": ""},
    {"name": "look", "value": "calm, natural", "source": "default", "from": ""}
  ],
  "questions": [
    {"param": "seconds", "question": "How long should it be?"},
    {"param": "aspect", "question": "Where will this be shown or posted (Instagram, TikTok, YouTube, a website, print, somewhere else)?"},
    {"param": "sound", "question": "Should it have sound: music, a voice, or silent?"}
  ]
}
```

Example 2: complete brief (V4 item V01, full).

```json
{
  "messages": [{"role": "user", "text": "A 10-second vertical (9:16) clip for a meditation app: slow waves at sunset on an empty beach, a gentle camera drift, with the natural sound of the waves, no music, no words."}],
  "tool": "create_video_from_text",
  "params": [
    {"name": "subject", "value": "slow waves at sunset on an empty beach, a gentle camera drift", "source": "user"},
    {"name": "seconds", "value": 10, "source": "user"},
    {"name": "aspect", "value": "9:16", "source": "user"},
    {"name": "sound", "value": "ambient", "source": "user"},
    {"name": "exact_words", "value": [], "source": "user"},
    {"name": "look", "value": "calm, natural", "source": "default"}
  ],
  "attachments": []
}
```

```json
{
  "tool": "create_video_from_text",
  "ready": true,
  "params": [
    {"name": "subject", "value": "slow waves at sunset on an empty beach, a gentle camera drift", "source": "user", "from": ""},
    {"name": "seconds", "value": 10, "source": "user", "from": ""},
    {"name": "aspect", "value": "9:16", "source": "user", "from": ""},
    {"name": "sound", "value": "ambient", "source": "user", "from": ""},
    {"name": "exact_words", "value": [], "source": "user", "from": ""},
    {"name": "look", "value": "calm, natural", "source": "default", "from": ""}
  ],
  "questions": []
}
```

- How the host learns to call `plan_request` first: a later ticket. Spec 5.3 names this as an open risk.
- Options, none chosen
  - The server instructions (`MCP_SERVER_INSTRUCTIONS` in `mcp_magichour/openapi_server.py`).
  - The description of each creation tool (`API_TOOL_METADATA` in `mcp_magichour/openapi_policies.py`).
  - The description of `plan_request`.
  - A creation tool refuses a call that has no plan. Spec 3.6: "prefer logic the server controls". The server keeps no state.

## Rules

- "V4 did it in": `code` = the rule is code in V4. `model` = V4 gave the rule to its model as text. In the MCP, each rule is code.

| # | Rule | V4 source | V4 did it in |
|---|---|---|---|
| 1 | The sheet has one row for each parameter: name, value, source, from. | `intent.js` 9, 33 | model |
| 2 | Each tool has a list of parameters and a list of required parameters. | `catalogue.js` 10 to 30 | code |
| 3 | The server removes a row if the tool does not use the parameter. No question for it. | `intent.js` 75; ticket | code |
| 4 | The server adds a `missing` row for each required parameter that has no row. The server adds a `missing` row for `aspect` if the tool uses `aspect`. | `intent.js` 52, 75 | code |
| 5 | Source `default` is permitted only for: look, position, transition, voice, language, keep. On a different parameter, the row becomes `missing`. Exception: rule 6, rule 9. | `intent.js` 33; ticket | model |
| 6 | "Your call" = a user message has one of: your call, you decide, whatever, up to you, don't care, anything, surprise me, dealer's choice. (a) The server keeps a `default` from the host on each parameter. (b) If only one row is `missing`: the server fills aspect `16:9`, or seconds `10`, or sound `none`, source `default`. (c) "Your call" answers each parameter that the assistant message before it asked about (rule 10b). It stays true to the end of the chat. A "your call" with no assistant message before it answers nothing. (Changed 2026-11-10, proposed: was only the newest message. Answers open question 17.) | `questions.js` 33; `intent.js` 38, 59 | (a) model, (b) code, (c) code |
| 7 | Exact words, source `user`: each string must be in the user's messages, compared without case, quotes, punctuation or a list number ("1 Clear your desk" = "Clear your desk"), or be words the assistant just proposed and the user approved ("Yes, use that"; a bare "yes" is not approval). If not, the row becomes `missing`, unless rule 9 permits. (Changed 2026-11-10: was "word for word".) | `intent.js` 36; ticket | model |
| 8 | Exact words, source `derived`: only the empty list is permitted. If the list has words, the row becomes `missing`, unless rule 9 permits. | `intent.js` 35, 36 | model |
| 9 | Exact words handed over: any user message says "you write them", "you pick the words", "the exact words are your call" or "choose a headline yourself", or the newest message is "your call" to the words question. Then the host may write the words (source `default`, `derived` or `user`). "The usual stuff" is not permission. (Changed 2026-11-10: was only the newest message.) | `intent.js` 36; ticket | model |
| 10 | A designed piece needs exact words. Conditions: the tool is `generate_image`; the user's words have post, poster, flyer, banner, card, ad, advert, announcement, invite or invitation; no assistant message has the word "word" or "words"; the user's words have no quote mark; the user did not say "no text"; the user did not hand the words over (rule 9). Then `exact_words` becomes `missing`. | `intent.js` 70, 71 | code |
| 10a | The user says "no text" ("no text", "no added text", "no words", "without any text", "don't include any words"): `exact_words` = `[]`, source `user`. No question. "No idea what words" is not "no text". The host's `[]`, `"No text"` or `"none"` give the same result. (Added 2026-11-10.) | persona dry sweep p2 | code |
| 10b | A question counts as asked when the assistant's message has it word for word or a question sentence about the same thing (shape: shown, posted, vertical, wide; length: how long, seconds; words: words, text, caption, headline; sound: sound, music, silent; motion: move, movement, motion, animate, camera). This decides whether "your call" answers it and whether it was asked twice. A suggestion that only mentions "vertical" is not a question. (Added 2026-11-10.) | persona dry sweep p2 | code |
| 11 | Tool `edit_image`: if `edit` has a source that is not `user`, the row becomes `missing`. | `intent.js` 73; ticket | code |
| 12 | Length and sound, source `user` or `derived`: the server parses all user messages. If the parser finds no value, the row becomes `missing`. If the parser finds a value, the server keeps the value from the host. | `intent.js` 34; `questions.js` 31, 32 | model |
| 13 | Length and sound, source `missing`: the server parses the newest user message. If the parser finds a value: that value, source `derived`. | `intent.js` 57 | code |
| 14 | Shape from the words: the server parses all user messages. With an attachment, the server first removes: poster, flyer, print, a4, letter. If the parser finds a shape, and the row source is not `user`, and the value is different: the parsed shape, source `user`. | `intent.js` 54; `questions.js` 29, 30 | code |
| 15 | Shape, parser finds nothing: the server does not keep a shape from the host with source `user` or `derived`. The row becomes `missing`. Then rule 16 and rule 17. | `intent.js` 34, 65 | model and code |
| 16 | Shape from the picture: if the tool is not `create_video_from_image` or `create_talking_photo`, and an attachment has a shape: that shape (first picture; if none, first video), source `derived`. | `intent.js` 26, 61 | code |
| 17 | Ask for the shape. Conditions: the parser finds nothing; the row source is not `default`; and one of: the tool is `create_video_from_image` or `create_talking_photo`; the user's words have website, web, social, socials, online, site, homepage, ad or advert; the attachments have more than one shape; there is more than one picture and the tool is not a swap. Then `aspect` becomes `missing`. | `intent.js` 37, 67, 68; ticket | code |
| 18 | One question for each `missing` row. The text is word for word from the question set. | `intent.js` 75; `questions.js` 2 to 28 | code |
| 19 | Maximum 3 questions. | `intent.js` 76 | code |
| 20 | `ready` is true when there are 0 questions. | `intent.js` 77 | code |
| 21 | No question about budget. | ticket; `prd/PRD.md` 43 | - |
| 22 | Direction change: the host sends the new tool and a new sheet. Rule 3 and rule 14 remove old answers. | `intent.js` 40; ticket | model |

- Parsers (`questions.js` 29 to 32), ported with no change
  - Shape: an exact ratio (`3:4` and `4:5` give `9:16`; `4:3` gives `16:9`), then the platform words. Examples: "Instagram story" = `9:16`; "square" = `1:1`; "poster" = `9:16`.
  - Length: a number with a unit, or a number alone; "half a minute" = 30; "minute" = 60; "short" = 8; "reel" = 15.
  - Sound: "silent" = none; "voice" = narration; "music" = music; "ambient" = ambient.

## Question set

- Decision: use `questions.js`, limited to the 14 parameters that a tool in "Tool map" uses.
- Why: 4 of the 13 items need a question that the 8-row bank does not have (S01 `edit`, S07 `range`, S08 `which_face`, S09 `motion`).

| Parameter | Question (word for word from `questions.js`) | Tools that use it |
|---|---|---|
| aspect | Where will this be shown or posted (Instagram, TikTok, YouTube, a website, print, somewhere else)? | generate_image, edit_image, create_video_from_text, create_video_from_image |
| seconds | How long should it be? | create_video_from_text, create_video_from_image, generate_music |
| exact_words | Should any words appear on it? If so, which, exactly? | generate_image, edit_image, create_video_from_text |
| sound | Should it have sound: music, a voice, or silent? | create_video_from_text, create_video_from_image |
| subject | What should it show? | generate_image, create_video_from_text |
| edit | What should change in the picture? | edit_image |
| keep | What must stay exactly as it is? | edit_image, create_video_from_image |
| motion | What should move, and how (small natural motion, a slow push in, something happening)? | create_video_from_image |
| look | Any look in mind (realistic, illustrated, a brand colour, a mood)? 'Your call' is fine. | generate_image, create_video_from_text |
| which_face | Whose face goes where (which person in the picture)? | swap_face_in_photo, swap_head_in_photo |
| range | Which part should be kept (from when to when, or 'the best 10 seconds')? | trim_video |
| mood | What mood or genre for the music? | generate_music |
| script | What should be said, word for word? Or should I write it from the gist? | create_talking_photo |
| language | Which language for the voice or captions? | add_subtitles_to_video, create_talking_photo |

- Not in the set: 11 entries of `questions.js`.
  - 9 belong only to V4 tools with no MCP tool: continuation, adjustment, targets, order, music, transition, position, voice, story.
  - 2 belong to no tool in `catalogue.js`: which_one, reference_role. Rule 3 removes their questions in V4 also.

## Tool map

- MCP tool names: checked against `docs/openapi.json`, `API_TOOL_METADATA` in `mcp_magichour/openapi_policies.py`, and the tool list of `create_mcp()` on 2026-11-05.
- Parameters and required parameters: `catalogue.js` 10 to 30.

| V4 tool | MCP tool | Parameters (required in bold) | In `plan_request` |
|---|---|---|---|
| generate_image | generate_image | **subject**, **aspect**, exact_words, look | yes |
| edit_image | edit_image | **edit**, keep, aspect, exact_words | yes |
| create_video_from_text | create_video_from_text | **subject**, **seconds**, **aspect**, **sound**, exact_words, look | yes |
| create_video_from_image | create_video_from_image | **motion**, **seconds**, aspect, **sound**, keep | yes. The MCP tool has no shape argument (Open 7). |
| generate_music | generate_music | **mood**, **seconds** | yes |
| add_subtitles_to_video | add_subtitles_to_video | language | yes. The MCP tool has no language argument (Open 6). |
| upscale_image | upscale_image | none | yes |
| remove_image_background | remove_image_background | none | yes |
| swap_face_in_photo | swap_face_in_photo | which_face | yes |
| swap_head_in_photo | swap_head_in_photo | which_face | yes |
| create_talking_photo | create_talking_photo | **script**, language | yes. The MCP tool takes an audio file, not a script (Open 6). |
| trim_video | none | **range** | sheet only, for item S07 (Open 4). The tool is out of scope. |
| adjust_image | none | - | out of scope. Item S05 uses `edit_image`. |
| voice_over | none. `openapi_policies.py` removes the voice route. | - | out of scope |
| text_overlay | none | - | out of scope |
| extend_video | none | - | out of scope |
| resize_image | none | - | out of scope |
| join_videos | none | - | out of scope |
| video_production | none | - | out of scope |

- 18 MCP creation tools have no sheet in V4 (Open 5): create_spoken_ad_video, edit_video, translate_video, upscale_video, create_animation, create_video_from_audio, replace_character_in_video, swap_face_in_video, create_lip_sync_video, restyle_video, change_clothes_in_photo, edit_face_in_photo, create_gif_or_short_video, generate_headshot, create_meme, create_qr_code, place_person_in_scene, colorize_photo.

## Tests

- Contract tests: `tests/test_plan_request.py`. Style of `tests/test_agent_workflows.py`. In-memory API. 0 credits.
- Run: `python -m pytest tests/test_plan_request.py -q`.
- The expected values are in four tables at the top of the file.
- The host sheet in a vague test is a guess (5 s, 16:9, invented words). The test sends the guess with each source: `default`, `missing`, `derived`, `user`. The result must be the same.

| Group | Tests | Content |
|---|---|---|
| The tool | 2 | In the tool list, read-only, the 4 arguments. No API request (the mock records 0 requests). |
| Ticket cases | 9 | The 8 cases of the ticket. "Your call" has 2 tests: the host gives the default; the host gives no value. |
| More ticket behaviour | 3 | "You write them" is permission. Strange script of S03: never invented words, 3 answers × 3 sources. No question for a parameter that the tool does not use. |
| Items, vague brief | 13 | S01 to S11, V01, V02. Expected: the `missing` parameters and their question texts. |
| Items, full brief | 13 | S01 to S11, V01, V02. Expected: `ready`, 0 questions, the values that the brief gives. |

Expected results for each item

| Item | Tool | Vague brief: `missing` = questions | Vague brief: other values | Full brief: values (`ready`, 0 questions) |
|---|---|---|---|---|
| S01 | edit_image | edit, aspect | - | aspect 16:9 |
| S02 | generate_image | aspect | - | aspect 1:1 |
| S03 | generate_image | exact_words | aspect 9:16 | aspect 9:16; exact_words: Open Mic Night / Friday 7pm / The Blue Door |
| S04 | generate_image | exact_words, aspect | - | aspect 1:1; exact_words: 20% OFF / This weekend only |
| S05 | edit_image | none (`ready`) | aspect 1:1 from the picture | aspect 1:1 from the picture |
| S06 | edit_image | none (`ready`) | aspect 16:9 from the picture | aspect 16:9 from the picture |
| S07 | trim_video (Open 4) | range | - | range |
| S08 | swap_face_in_photo | which_face | - | - |
| S09 | create_video_from_image | motion, aspect, sound | seconds 8 (Open 9) | seconds 6; sound none (Open 8) |
| S10 | create_video_from_text (Open 23) | seconds, aspect, sound | - | seconds 10; aspect 16:9; sound none |
| S11 | edit_image | aspect | - | aspect 16:9 |
| V01 | create_video_from_text | seconds, aspect, sound | - | seconds 10; aspect 9:16; sound ambient |
| V02 | create_video_from_image | seconds, aspect, sound | - | seconds 6; aspect 1:1; sound none |

- Not tested: the order of the questions (Open 15). The text of `from`. A second, simpler question text (Open 16).
- Benchmark: as the ticket gives it (13 items, current MCP against the new build, same driver, same judge). Not changed here. The ticket's open points on the benchmark stay open.

## Open

Decisions that change the tests
1. Who derives. This PRD uses option A of the ticket. Confirm.
2. Question text for `aspect` and `look`. The ticket table has short texts. `questions.js` adds examples. The tests use `questions.js`. Which text?
3. `which_one` and `reference_role` are in the ticket table. No tool in `catalogue.js` uses them. Keep or remove?
4. `trim_video` has no MCP tool. The tests make `plan_request` plan it (item S07). What does the host do with a `ready` sheet for it? Or: remove S07 from this ticket?
5. 18 MCP creation tools have no sheet in V4. Which parameters and questions do they get?
6. `create_talking_photo`: V4 asks for a script; the MCP tool takes an audio file. `add_subtitles_to_video`: V4 has `language`; the MCP tool has no language argument. Change the sheets?
7. `create_video_from_image` has no shape argument. Rule 17 asks for the shape. V4 fits the start frame to the shape first (spec 5.3; not in the MCP). Ask for the shape before that tool is there?
8. S09 full brief gives no shape. The V4 parser reads "portrait" as `9:16`, so V4 does not ask. The picture is `1:1`. The test expects `ready`. Keep the parser as it is?
9. S09 vague: "short" gives 8 s. The answer sheet says 6 s. Keep 8 s, or ask?

V4 parser behaviour, ported with no change
10. A number alone is a length: "20% off" gives 20 s. "no music" gives sound `music`. Correct these?
11. The host value and the parsed value are different (host: 5 s; user: "short" = 8 s). V4 has a rule for shape only (rule 14). Which value wins for length and sound?
12. Rule 13 parses only the newest user message. Rule 12 and rule 14 parse all user messages. Keep this difference?
13. V4 does not force the shape question again after an assistant message asked about shape (`intent.js` 66). Rule 15 does not have this exception. OK?

Gaps of code that checks a host
14. Free-text parameters (subject, edit, motion, range, which_face, look, keep, mood, script, language): the server cannot check that the user gave the value. Is a check necessary?
15. Order of the questions. Ticket: "The most blocking question is first." V4: the model gives the order. Code needs a fixed order. Which order?
16. Strange answer. Ticket: "Ask again with simpler words." The set has one text for each parameter. Is a second text necessary? Who writes it? Spec 3.2 says "asked once".
17. "Your call": code cannot tell which parameter the user means. The tests use the newest user message. Does the permission stay in later turns? (Code on 2026-11-10, proposed, not your answer: yes, to the end of the chat, for the parameters the question before it asked about. Rule 6c. Confirm or reverse.)
18. Exact words, rule 7: must capital letters and spaces be the same?
19. Exact words that the host reads from an attached picture (V4 run of S11: the words on the poster, source `derived`). Rule 8 makes them `missing`. Must the host not send them?
20. The host does not know the shape of an attached picture. Rule 16 has no value; the row stays `missing`; rule 18 asks. OK? (`edit_image` has `aspect_ratio: auto`.)
21. Attachment `role`: no rule of this ticket reads it. `guards.js` reads it. Keep the argument?

Scope
22. Value types. V4 keeps each value as a string. This contract uses a number for `seconds`, a list for `exact_words`, `null` for `missing`. OK?
23. `plan_request` does not check that the tool is the correct tool. Item S10: the item file says `create_video_from_image`; V4 chose `create_video_from_text` (`intent.js` 39). The tests use `create_video_from_text`. Who checks the tool?
24. Sheet value to tool argument. `sound` has 5 values; the MCP has `audio` true / false. `aspect` has 3 values; `edit_image` takes 8. Who maps them? Which ticket?
25. V4's intent output also has: tier (`refuse`, `unclear`), needs_research, deliverables, say, direction_changed. Not in this contract. What does the host send when the request is not clear, or must be refused?
26. V4 gives the previous sheet to its model. The server keeps no state. The host sends the full sheet in each call. Is a `previous` argument necessary?
27. From the ticket, not answered here: the harness address, the full-brief baseline, the target score.
28. Spec 5.3: the planning tool "runs intent and guards server-side". The ticket's port list has no `guards.js`. Are the guards in this ticket?

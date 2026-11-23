# Production: a multi-clip film from a story

Tickets: MCP-02, MCP-03, MCP-10, MCP-14. Overview: [ARCHITECTURE](../ARCHITECTURE.md).
Code: `video_production.py` (plan, split, questions, prompts), `video_production_tool.py` (tools, clip calls, join).

## Scope

- In: plan a story, make its clips, join them into one film.
- Out: when the host calls these tools (MCP-05, later). Reading what is in a clip (MCP-07, later). Sound: [sound](sound.md). Checks: [checks and gates](checks-and-gates.md). Files: [media files](../shared/media-files.md).

## Tools

| Tool | Does | Credits |
|---|---|---|
| `plan_video_production` | Story in, ordered calls out: clips, rounds, `questions`, `advice`, `checklist`, `production` (the packed story the host passes back). | 0 |
| `create_production_clip` | Makes one clip of the plan. A card clip makes its still first (qwen-image-2.1; the image editor with the user's picture), then a clip from it. | per clip |
| `join_production_clips` | Joins the clips in story order. Places sound, draws cards and captions, measures the checklist. | 0 |

- The server keeps no plan state. `production` travels with the host. A changed `production` value is refused.
- `made`: the host's map of clip number to video project id. Since 2026-11-11 it also takes a URL or a kept `file_path`.

## Clip split (user, 2026-11-05; strategy `person`)

- Ideas come first. The same person is one idea: their beats stay in one clip, also when the place changes, while the clip fits.
- As few clips as possible. Split only when needed (user, 2026-11-20). The `ltx-2.5` rules (`line-<n>`, two places merge) apply only to an `ltx-2.5` clip.
- Limit: 15 s. A person with a picture: 30 s (`minimax-h3`).
- A cut idea is chained: the clip ends on the person; the next clip starts from that last frame.
- A person who comes back starts from the last clip that showed them.
- A new place: the clip ends close on the person; the next clip pulls back to show the place.
- A new idea with no person from before: a new clip, no reference (or its picture).
- A change of place inside one shot that fits one call (a door): no cut.
- The host groups beats into clips with `clip` on each beat (user's design, 2026-11-07).
- One reference kind for each clip: last frame, pictures, own still, or none.
- Pictures: each pictured subject in the clip is its own likeness guide (`@id`), not a pasted photo (user, 2026-11-14, W04).
- Related beats stay in one clip, in motion or otherwise (user, 2026-11-13, W09). A logo reveal is one generated clip with the logo as its reference, not a clip and then a held still of the logo. Video generation, not a pasted logo.
- A beat that does not depend on an earlier beat does not need that beat's clip (user, 2026-11-13, W03).
- Why (W03, wide set): steps 3 and 4 started from the last frame of the step before. That frame showed the grooving machine, and the prompt said "Continue from it". The model kept cutting grooves: no rods, no second slat. The same step as a fresh 6 s clip showed the rods. One 12 s call written as two shots with a hard cut ("CUT at 6 s", a new angle, no machine in frame) also showed them.
- Not done: start a new event with no person fresh, not from the last frame. A re-plan of 198 past productions (0 credits) changed 23 clips. Most of them need the last frame to keep a product or a process the same (H40a bottle, H40b candle, W07 plane, I47c water cycle).
- Two separate actions in one clip: give each its own clip (the `clip` field). The `continuity` question also offers two shots with a hard cut, the first action's tool out of frame (user, 2026-11-16).
- One shot in each clip (user, 2026-11-22: split a little more). A new clip when the framing or the camera angle changes (close to wide, front to behind), the clip holds more than three actions, it is too long (15 s; 30 s with a person's picture), or the next action does not depend on this one. The `shot-change` advice warns on a new framing inside one clip.
- Why (W05, w22l): a close two-shot, then a wide shot from behind, in one 10 s call with no cut. A second open umbrella came in front of the camera.
- At most three actions in one clip (`actions-per-clip` advice). Why (W07, w22l): seven actions in one 12 s beat; Wilbur rose into the air with the plane.
- Back pocket, not built (user, 2026-11-23): if the benchmarks show issues with the split, offer a written hard cut again for a new framing inside one clip ("CUT at 6 s", a new camera angle). The change: the `clip` field says "its own clip, or a hard cut"; the `shot-change` advice does not warn when the beat text writes a cut.

## Models (user, 2026-11-14)

- `minimax-h3` makes every scene clip up to 30 s: from text, from a last frame, with pictures. Longer: `ltx-2.5`. A silent still with exact words: `ltx-2.5`. A still with exact words and speech or sound: `minimax-h3` (2026-11-20).
- Why: a 60-clip sound test (9,246 credits). `minimax-h3` made the sound in every case. `ltx-2.5` missed wind, the background under a voice, a second speaker (from a last frame, 4 of 4), and the second line of a two-line clip (8 of 8). The sound line first in the prompt did not fix it. Page: sound-test-matrix.vercel.app.
- Same price: 24 credits a second. The join cuts each clip to its planned length (`minimax-h3` runs about 0.3 s long).
- Not `ltx-2.5` for a silent chained clip (tested w6, reverted by the user 2026-11-15). Cuts were smoother, but W02 lost the bottle's look (`ltx-2.5` takes no picture) and W07 was worse.

## Product pictures (user, 2026-11-14, W04)

- Fault: with no photo, the host made "reference" pictures with an image model. They invented the products (a Steam Deck with no trackpads; a Switch 2 with the first Switch's blue and red controllers).
- Fix: a real photo as the subject's `picture`. Two free-licence Wikimedia Commons photos made both devices right in every shot.
- A product with no picture is a question (below). Never a picture made by an image model.
- The user's choice wins (2026-11-23). The user chose a look-alike made from words: the host answers `none`. The user said nothing: a real photo (the conversation's default is `web`).

## Beats and questions (user's design, 2026-11-07)

- Beat fields: `clip`, `spoken`, `says`, `reference`, `in_scene_words`, `background`, `picture`, `model`, `card_motion`.
- Rules of thumb (`RULES_OF_THUMB`, in the tool text): they apply when the user's words do not say otherwise. Hook in the first 3 s, then the body, then the close. An ad: hook and close aim at its audience; end on call-to-action words. An explainer or a list: one point per beat, its label in `exact_words`. One spoken line per beat. Fill the length: no stretching, no pauses. A card only when the user asks. Keep every concrete detail word for word. These moved from the conversation (2026-11-23).
- The plan asks at known risks and holds until the host answers. Each question has a recommendation; the host decides.

| Question | When | Options | Recommended |
|---|---|---|---|
| `words-<n>` | Words over a scene | card, model, still, accept | card |
| `line-<n>` | A spoken line shares an `ltx-2.5` clip with another beat (user, 2026-11-20: not on `minimax-h3`) | split, keep | split |
| `colour-codes` | Colour codes in the story | words, keep | words |
| `held-<n>` | A picture card right after a scene made from the same picture (W09) | merge, keep | merge; keep when the beat is an end card. After its own reveal, the plan merges it with no question (2026-11-21) |
| `together-<n>` | A beat in another clip than the beat before, with `link: continues`, or `link: event` and a shared person (2026-11-20), and both fit (15 s; 30 s with a pictured person) | join, keep | join |
| `picture-<id>` | A product subject with no `picture` | web, user, none | web; none when the user chose a look-alike (2026-11-23) |
| `continuity` | Every plan with 2 or more scene clips, once: the host checks its own plan for a split continuous motion or asset, and for two actions in one clip with no cut | ok, change | ok |

- Words (user's pick, 2026-11-07): a card after the scene when the words can stand alone; `minimax-h3` over the scene when they must sit on the picture; never `ltx-2.5`.
- Words drawn over the scene by code (user, 2026-11-16): the `overlay` words route of `join_production_clips`, at the top, large. A title can sit over the first scene instead of a card. Why: W10b, title over the opening scene, first cut 0.01 → 0.98 picture match (w9). W04 (report of 2026-11-14) used it for its title.
- Cards are generated, also with an exact colour or the user's picture (user, 2026-11-21). A card only when the user asks for one. A drawn card is made by hand with `make_card_clip`, only when the user asks for it. A misspelled card is made again, at most 3 in all; the best one is kept, also with a small misspelling (user, 2026-11-21). The card clip holds still: no camera move (user, 2026-11-21). It moves only when the user asks: `card_motion` holds the move in the user's words, and the card prompt uses it (user, 2026-11-23). The card clip is made on `minimax-h3` from the card still: 1.00x in 3 of 3; `ltx-2.5` pushed in 1.13-1.27x (test, 2026-11-23, 792 credits).
- `in_scene_words` (a label, a sign): no question, best effort by the model.
- Why `line-<n>`: the line was said 0 of 3 times inside a 12 s clip with another beat, 3 of 3 alone in a 4 s close-up (`ltx-2.5`, 2026-11-07).
- Spoken line prompt (user, 2026-11-16, W08, W05): the line gets a time slot sized by its words (3 words a second, 2 s or more), then a silent end: "stops talking, smiles and nods, mouth closed. Nobody speaks." A script label in the quote ("Maya: Then we walk.") becomes the speaker: `Maya says, word for word: "Then we walk."`.
- Why: the prompt gave the model time to talk with no line to fill it. W08 "talks to the camera" over 8 s with a 3 s line: 4 s of made-up speech. A 5 s slot for 9 words: "Meet Streaks" said twice (w8). 3 s slot: the line once, then silence (w9). W05: the model said the names out loud (w6); clean after the change (w8).
- Continue a clip: keep the file, start from its last frame, `minimax-h3` (Models above). The 2026-11-07 pick of `ltx-2.5` was removed (user, 2026-11-16); its behaviour is a tool note (MCP-20).

## The user's own clip (MCP-14, approved 2026-11-11)

- `source` on a beat: the user's clip (file_path from `upload_media`, URL, or project id). The beat is a clip of its own. Nothing is generated (0 credits); the join uses the clip as it is.
- A user's picture: the planner picks the use from the user's words (user, 2026-11-23). As it is, held still (`source`; W08 screenshot). Lightly edited first (`edit_image`, then `source` or `reference.file`). On a card the user asked for (card `picture`). Brought to life (a subject's `picture`; the model moves it, and it may change a little).
- `source_sound`: keep the clip's own sound (default). False: the clip is made silent before the voice-over and music are added.
- A voice-over, music or captions on the user's clip: a plan with that one beat, `says` on it, then `create_production_sound` and the join.
- Continue the user's clip: the next clip starts from the source clip's last frame (`link: continues`).

## Replace one clip (MCP-21, user, 2026-11-16)

- Replace a clip between two kept clips: start image = `get_last_frame` of the clip before; `end_image_file_path` = `get_first_frame` of the clip after. `minimax-h3`.
- Plain tools, not the production tool. The `get_first_frame` description tells the host this path. Gate note: `end-frame-fits-between`.
- Why (W12 fox, shot 2 replaced): with the start image only, the cut into shot 3 was 0.52 (w4). With both frames: 0.99 (direct test), 0.94 (fleet w10, shot 3 starts with fast motion). `ltx-2.5` with both frames: two jumps inside the clip, the action not shown.

## Results

- 2026-11-07, A2, B2, B1, A4, paid: v1 22 yes · 3 partly · 2 no; this build 21 · 4 · 2. B2 line said, B1 9 lines yes, cards and logo exact.
- 2026-11-10/11, fleet (163 cases × 3 users × old and new): see `Benchmark/audit/artifacts/`.
- 2026-11-14, wide set W01–W15, old MCP and this build: report mcp-original-vs-new.vercel.app (the user's marks only).
- 2026-11-15/16, reruns on the fixes (user's marks): W08 w9 works; W05 w8 works; W02 w9, W07 w9 pretty solid; W10b w9 works; W12 w10 pretty good. Page: Model Rule Test artifact.

## Open

1. MCP-10: A1 and A3 not rerun on this build. B1 label is best effort.
2. MCP-21: one fleet run of the replace path (W12 w10). No path in the production tool.
3. End card words shown twice (W02, W04): the drawn words and the caption of the same line. Fixed 2026-11-17 (MCP-23): the caption is left out.
4. W02 w9: the 54 s close-up shows another cap shape. Not fixed.
5. MCP-21 open line: one continuous 15 s generation where it makes sense (reviewer, 2026-11-14).

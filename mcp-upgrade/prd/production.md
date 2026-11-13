# Production: a multi-clip film from a story

Tickets: MCP-02, MCP-03, MCP-10, MCP-14. Overview: [ARCHITECTURE](ARCHITECTURE.md).
Code: `video_production.py` (plan, split, questions, prompts), `video_production_tool.py` (tools, clip calls, join).

## Scope

- In: plan a story, make its clips, join them into one film.
- Out: when the host calls these tools (MCP-05, later). Reading what is in a clip (MCP-07, later). Sound: [sound](sound.md). Checks: [checks and gates](checks-and-gates.md). Files: [media files](media-files.md).

## Tools

| Tool | Does | Credits |
|---|---|---|
| `plan_video_production` | Story in, ordered calls out: clips, rounds, `questions`, `advice`, `checklist`, `production` (the packed story the host passes back). | 0 |
| `create_production_clip` | Makes one clip of the plan. A card clip (`made_by: code`) makes nothing: the join draws it. | per clip |
| `join_production_clips` | Joins the clips in story order. Places sound, draws cards and captions, measures the checklist. | 0 |

- The server keeps no plan state. `production` travels with the host. A changed `production` value is refused.
- `made`: the host's map of clip number to video project id. Since 2026-11-11 it also takes a URL or a kept `file_path`.

## Clip split (user, 2026-11-05; strategy `person`)

- Ideas come first. The same person is one idea: their beats stay in one clip, also when the place changes, while the clip fits.
- Limit: 15 s. A person with a picture: 30 s (`minimax-h3`).
- A cut idea is chained: the clip ends on the person; the next clip starts from that last frame.
- A person who comes back starts from the last clip that showed them.
- A new place: the clip ends close on the person; the next clip pulls back to show the place.
- A new idea with no person from before: a new clip, no reference (or its picture).
- A change of place inside one shot that fits one call (a door): no cut.
- The host groups beats into clips with `clip` on each beat (user's design, 2026-11-07).
- One reference for each clip: last frame, picture, own still, or none.

## Beats and questions (user's design, 2026-11-07)

- Beat fields: `clip`, `spoken`, `says`, `reference`, `in_scene_words`, `background`, `picture`, `model`.
- The plan asks at known risks and holds until the host answers. Each question has a recommendation; the host decides.

| Question | When | Options | Recommended |
|---|---|---|---|
| `words-<n>` | Words over a scene | card, model, still, accept | card |
| `line-<n>` | A spoken line shares a clip with another beat | split, keep | split |
| `colour-codes` | Colour codes in the story | words, keep | words |

- Words (user's pick, 2026-11-07): a card after the scene when the words can stand alone; `minimax-h3` over the scene when they must sit on the picture; never `ltx-2.5`. Not drawn over the scene by code.
- Cards and held pictures are drawn by code at the join.
- `in_scene_words` (a label, a sign): no question, best effort by the model.
- Why `line-<n>`: the line was said 0 of 3 times inside a 12 s clip with another beat, 3 of 3 alone in a 4 s close-up (`ltx-2.5`, 2026-11-07).
- Continue a clip (user's pick, 2026-11-07): keep the file, last frame, `ltx-2.5` (`minimax-h3` the other choice), silent join.

## The user's own clip (MCP-14, approved 2026-11-11)

- `source` on a beat: the user's clip (file_path from `upload_media`, URL, or project id). The beat is a clip of its own. Nothing is generated (0 credits); the join uses the clip as it is.
- `source_sound`: keep the clip's own sound (default). False: the clip is made silent before the voice-over and music are added.
- A voice-over, music or captions on the user's clip: a plan with that one beat, `says` on it, then `create_production_sound` and the join.
- Continue the user's clip: the next clip starts from the source clip's last frame (`link: continues`).

## Results

- 2026-11-07, A2, B2, B1, A4, paid: v1 22 yes · 3 partly · 2 no; this build 21 · 4 · 2. B2 line said, B1 9 lines yes, cards and logo exact.
- 2026-11-10/11, fleet (163 cases × 3 users × old and new): see `Benchmark/audit/artifacts/`.

## Open

1. MCP-03: the join does not trim each clip to its planned length (`minimax-h3` clips run about 0.3 s long).
2. MCP-10: A1 and A3 not rerun on this build. B1 label is best effort.

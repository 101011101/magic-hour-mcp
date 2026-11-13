# Scope: video composition first

Decided by the user, 2026-11-12.

- Ship video composition first. Tool calling comes after.
- Video composition: the MCP makes the video from end to end. The user can give text and references (photos, a logo, a voice sample). It includes shots, the join, words over the film, voice-over and music on the film it makes.
- Tool calling: the MCP edits media that already exists (the user's clip, photo or audio). Examples: trim, reframe, subtitles on the user's clip, watermark, face swap, character replace, image edits, audio only.
- Approval rule: a change is approved when the new build is better than the old MCP on video composition, and not worse on tool calling.

Benchmark items (persona bench, `V2/bench/v1/items`):

- Video composition (44): D18–D23, H40–H42, H43a, H44, I45–I48, J51a, J52a, J55a. The pillars A1–A4, B1 and B2 (dense bench) are also video composition.
- Tool calling: all other items (A, B, C, E, F, G, H43b, J49–J50, J51b, J52b, J53, J54).

Open (defaults until the user decides):

- A3 (continue a clip) is video composition, because it is a pillar.
- J50b (change only the ending of a clip) is tool calling.
- H43a (talking testimonial) is video composition. H43b (lip sync check) is tool calling.
- Music or voice-over added to the user's own clip (E27, E28) is tool calling.

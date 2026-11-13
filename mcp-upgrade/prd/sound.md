# Sound: narration, music, captions on a film

Tickets: MCP-08 (closed), MCP-11. Overview: [ARCHITECTURE](ARCHITECTURE.md).
Code: `video_production.py` (`plan_sound`), `video_production_tool.py` (`create_production_sound`, join), `media_tools.py` (mix, captions, speech).

## Design (option E, user, 2026-11-05)

- Story fields: `says` on each beat, `narrator`, `music`, `captions`, `voice_sample`.
- `create_production_sound` makes one narration track and one music track for the whole film.
- The join places each part of the narration on its clip (timing by pauses, about ±0.5 s), mixes the music, draws the captions (needs Pillow).

## Narration

| Case | Tool | Rule |
|---|---|---|
| No presenter, sample given | `/v1/ai-voice-cloner` | Recommended (A4, MCP-11). |
| No sample | `/v1/ai-voice-cloner` with a default preset voice | Ashley; Daniel when `narrator` names a man (user, 2026-11-11, proof of concept). No question. |
| `MAGIC_HOUR_VOICE_OVER=video` | the video model speaks | The old path. |

- Default: `cloner` (`VOICE_OVER_DEFAULT`, user, 2026-11-11). Our version ships to production once upstream approves; until then we work as if approved.
- Why: the video-model narration read A4's script 2 times in 8. The cloner read it exactly (17 credits, 2026-11-08).
- Cost: 1 credit for each 10 characters, rounded up.
- Never a voice of someone else without their consent.
- Preset voices (Magic Hour's voice previews) are allowed as the default sample for now (user, 2026-11-11).
- The sample: a URL or a `file_path` (from `upload_media` or the host's upload).

## Music

- `music` in the story: one instrumental track (`/v1/ai-music-generator`), as long as the film.
- The cloner path keeps the music (bug fixed 2026-11-10).

## Layers (user, 2026-11-12)

- Priority: 1 speech (narration, spoken lines), 2 music, 3 effects (the clips' own sound). With no speech, music is the top layer.
- A layer is lowered only where a higher layer plays, and only there.
- Music in a film with speech: one steady level, 9 dB under the speech (measured against the speech), for the whole film (user, 2026-11-13: 18 dB under, with full level between the lines, sounded like only voice, then only music; 12 dB was a little quiet).
- `music_swell` (story field, only when the user asks): the music rises 8 dB between the lines. Gaps under 1 s stay lowered. Ramps of 0.3 s.
- Effects: 10 dB under narration or music. A spoken line is never lowered.
- `music_first` (story field): the music is never lowered. For a music video.
- The layers stay separate until the end. The join keeps each layer as its own file beside the film (`<film>.layers/`).
- Music is made once for the whole film and added last. Clips can still have their own speech and sound.
- The whole film is normalized to −16 LUFS, peaks under −1 dB.
- Code: `media_tools.add_sound`. Check: 14 films mixed again, all at −16 LUFS, length unchanged (`Benchmark/audit/failure-modes/sound.html`).
- Fault fixed with it: a clip with a spoken line lost its sound at the join when the story had `audio` off.
- The user's clip with its sound kept is speech, unless `source_speech` is false (only background sound). Its speech is never lowered; the music goes under it. Check: a talking clip with music, the voice was 5 dB under the music before, 10 dB over it after (2026-11-13).
- A voice-over on the user's clip that may have speech: the plan warns (`voice-over-on-speech`).

## Voice-over length (2026-11-13)

- Fault: the join placed each part 0.5 s into its beat and did not check its length. The last words ran past the film's end and were cut (I46a, E28c).
- Second fault: the part split used letters. "F-35A" is short in letters and long when read. The cut fell on a breath 1.4 s early. Now a digit counts as a word, and a real pause up to 1.5 s away wins over a breath.
- The join fits the parts, in this order: no overlap; start 0.1 s into the beat; read up to 15% faster; hold the last frame. The checklist line says what was done. A hold is told to the user.
- The plan warns when a beat has more words than its seconds allow (`voice-over-pace`, 2.7 words a second, measured on the cloner).
- Check: I46a 14% faster, E28c 15% faster, no hold, no word cut, length unchanged. 14 other films unchanged.

## Open

- A later mix does not read the kept layers yet.
- The `mix_audio` helper tool uses the volumes the host passes. It does not use the priority.

1. The default preset voices are a proof of concept (user, 2026-11-11). Decide later which voices ship, and whether the user picks one.

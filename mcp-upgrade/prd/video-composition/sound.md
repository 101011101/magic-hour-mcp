# Sound: narration, music, captions on a film

Tickets: MCP-08 (closed), MCP-11. Overview: [ARCHITECTURE](../ARCHITECTURE.md).
Code: `video_production.py` (`plan_sound`), `video_production_tool.py` (`create_production_sound`, join), `media_tools.py` (mix, captions, speech).

## Design (option E, user, 2026-11-05)

- Story fields: `says` on each beat, `narrator`, `narrator_voice`, `voice`, `music`, `captions`, `voice_sample`.
- `create_production_sound` makes one narration track and one music track for the whole film.
- The join places each part of the narration on its clip (timing by pauses, about ±0.5 s), mixes the music, draws the captions (needs Pillow).

## Narration

| Case | Tool | Rule |
|---|---|---|
| No presenter, sample given | `/v1/ai-voice-cloner` | Recommended (A4, MCP-11). |
| No sample | `/v1/ai-voice-cloner` with a preset voice | `pick_voice` (user, 2026-11-17, below). No question. |
| `MAGIC_HOUR_VOICE_OVER=video` | the video model speaks | The old path. |

- Default: `cloner` (`VOICE_OVER_DEFAULT`, user, 2026-11-11). Our version ships to production once upstream approves; until then we work as if approved.
- Why: the video-model narration read A4's script 2 times in 8. The cloner read it exactly (17 credits, 2026-11-08).
- Cost: 1 credit for each 10 characters, rounded up.
- Never a voice of someone else without their consent.
- Preset voices (Magic Hour's voice previews) are allowed as the default sample for now (user, 2026-11-11).
- The sample: a URL or a `file_path` (from `upload_media` or the host's upload).

## Voice pick (MCP-22, user, 2026-11-17)

- The host gives the profile; the code picks the voice. No extra model call. Picked at plan time; used in the sound step after the join.
- Host: `narrator_voice` (gender, age, style) and `narrator` (a few words: tone, pace, accent). `voice`: a preset id, only when the user names one.
- Code: `pick_voice` scores the presets of that gender. Style 4, age 2, an accent named in both 2, another accent named -2, each shared description word 1. Ties: the lowest id.
- No profile: a man's voice if `narrator` says so, else a woman's; middle-aged; Conversational (Ashley for a woman).
- The plan shows the voice: name, id, tags.
- List: `mcp_magichour/voices.py`, 319 voices. Tags from Magic Hour's web app voice table (2026-11-16); the API gives none (MCP-27).
- Left out: Characters, voices that imitate a named character, voices in another language (description or Whisper on the preview), Neutral.
- Why: before, every film got Ashley or Daniel. Test (`vpick`, 6 requests, 252 credits): the profile match kept the host's brief in 6 of 6; the host's pick from a list of 24 broke it in 3 of 6 (a man for a bedtime story and a breathing exercise, a woman for an owl documentary). The user: all picks sounded fine.
- Speech inside a clip is not picked here: minimax-h3 makes that voice.

## Music

- `music` in the story: one instrumental track (`/v1/ai-music-generator`), as long as the film.
- The cloner path keeps the music (bug fixed 2026-11-10).
- Sound effects: `sounds` on a beat ("a short whoosh as the lines meet"). The clip makes them, so that clip is made with sound (user, 2026-11-13, W09). Never music.
- The clip's own sound comes from `minimax-h3` (user, 2026-11-14). `ltx-2.5` missed most background sound and second speakers ([production](production.md#models-user-2026-11-14)). The API has no sound-effects endpoint.
- A clip never makes music (user, 2026-11-13). Music is always one separate track, added at the join. A clip with sound gets "No music." in its prompt; a clip without sound is made silent at the join.

## Voice-over and dialogue

- Voice-over: a narrator off screen. Made by the voice cloner from the text alone, after the plan. It does not see the video. The join places each sentence on its beat.
- Dialogue (`spoken`): a person on screen says the line. Made by the video model inside the clip, so it fits the clip and the lips.
- A voice-over can be longer than its beat because the cloner reads at its own pace. The plan warns; the join fits it (below).

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

## Captions fault (2026-11-13)

- Fault: a caption is a one-frame picture over the film. The joined film starts at 0.021 s, and ffmpeg then dropped the pictures. W10 showed no tip words; W02 showed captions only in the first 8 s.
- Fix: `-loop 1` on each picture and `overlay=shortest=1` (`media_tools.draw_captions`). Check: W10 and W02 joined again (0 credits), words and captions to the end.

## Join (user, 2026-11-16, W05 w8)

- Each clip's own sound is cut to its length plus 0.08 s and fades in and out over 0.08 s, so the cuts overlap. A clip whose quietest sound is 6 dB or more over the median of the clips is lowered, 12 dB at most. Why: W05 clip 4 rain at −37 dB, clips 1 to 3 at −46 to −48 dB, in a shelter. After: −49, −48, −46, −46 dB.

## Open

- A later mix does not read the kept layers yet.
- The `mix_audio` helper tool uses the volumes the host passes. It does not use the priority.
- MCP-22: narration voice pick done (above). Open: delivery words for speech inside a clip.
- MCP-23, tool side: caption style. Now white letters on a dark band; wanted white letters with a black outline.
- MCP-24: the off-screen interviewer's question is not heard.

1. Voice-over by more than one speaker (vpick V6: a dad and a daughter, voices only) has no story field yet: one narration track reads all lines in one voice.

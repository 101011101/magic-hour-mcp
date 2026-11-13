# Video composition

The MCP makes the video from end to end. Overview: [ARCHITECTURE](../ARCHITECTURE.md). Ships first.

| Doc | Covers | Tools | Code |
|---|---|---|---|
| [production](production.md) | plan a story, make its clips, join them | `plan_video_production`, `create_production_clip`, `join_production_clips` | `video_production.py`, `video_production_tool.py` |
| [sound](sound.md) | voice-over, music, captions, sound layers | `create_production_sound` | `video_production*.py`, `media_tools.py` |
| [checks and gates](checks-and-gates.md) | checklist in the plan and at the join; gate tools when on | — | `video_production*.py`, `gates.py` |

## How a film is made

1. The host calls `plan_video_production` with a story. The plan returns clips, rounds, `questions`, `checklist` and `production`. The host answers the questions and plans again until there are none.
2. The host makes each clip: `create_production_clip`, then `wait_for_video_project`. Cards need no call.
3. `create_production_sound` makes the narration (voice cloner by default) and the music.
4. `join_production_clips` downloads every piece, joins them with ffmpeg, places the sound, draws cards and captions, and measures the checklist.
5. The host gives the user the film's link and reports every unmet checklist line.

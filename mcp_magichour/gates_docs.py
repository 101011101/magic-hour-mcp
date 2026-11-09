"""The two documents the gates make the host read: simple against hard, and the notes for each tool and model.

Findings only (user, 2026-11-07): each note is something a benchmark run measured, with the run named. No advice that
was not measured, and none of the user's picked defaults. Edit a note here when a new run changes it.
"""

from __future__ import annotations

COMPARISON = """\
SIMPLE: every item below is true.
- One idea: one subject doing one thing in one place (a robot waters a sunflower).
- At most 15 seconds.
- No exact words that must appear on screen, and no spoken line that must be said word for word.
- At most one attached file, used as the look or the start of the video.
- Not a continuation or an edit of an attached video.

HARD: any item below is true.
- Two or more ideas: different places, different people at different times, shots listed in order, a card or end card.
- Longer than 15 seconds.
- Exact words on screen (a title, an end card, captions) or an exact spoken line or voice-over script.
- Two or more attached files, or a person and a product that must both stay the same.
- Continue, extend or edit an attached video, keeping part of it.
- Music or a voice-over across several shots.
"""

# id: (tools or models it applies to, the finding, the evidence)
NOTES: dict[str, tuple[tuple[str, ...], str, str]] = {
    "ideas-per-call": (("create_video_from_text", "create_video_from_image", "ltx-2.5", "minimax-h3"),
                       "About two ideas hold in one call of about 15 s. More ideas in one call: the model plays the shots more than once and mixes them.",
                       "B1 old MCP: 4 shots in one 30 s call played 3 times. C6 and C10: 4 seasons in one 20 s call played twice. "
                       "An 18 s call with 2 shots played them twice. Calls of 5 to 13 s with 1 or 2 beats held."),
    "ltx-words": (("ltx-2.5",),
                  "ltx-2.5 does not spell words it is asked to show in a scene.",
                  "0 of 4: \"walk anway\" (A2 old), \"13 awway\" (A2 v1), \"walk anwwy\" (approach W1), \"Avalabile 12 Dembmer\" (A1 old end card)."),
    "minimax-words": (("minimax-h3",),
                      "minimax-h3 spelled the words it was asked to show.",
                      "2 of 2: \"walk anyway\" over a scene (approach W2), the B1 end card (old MCP). Two attempts only."),
    "still-words": (("generate_image", "qwen-image-2.1"),
                    "A still made with the exact words, then animated with image-to-video, keeps the words exact. The words stay on screen for the whole clip.",
                    "End cards from a still: exact in A1, B1, B2 (v1). Approach W3: exact, on screen from the first frame to the last."),
    "minimax-sound": (("minimax-h3",),
                      "minimax-h3 adds music or sound even when audio is off.",
                      "A3 v1: guitar at -16 dB with audio off. Seasons runs: a music bed on silent requests. Joining with the sound removed made them silent (-91 dB)."),
    "ltx-sound": (("ltx-2.5",),
                  "ltx-2.5 is silent when audio is off.",
                  "Approach C2: -91 dB."),
    "regenerate-given-clip": (("create_video_from_text", "minimax-h3"),
                              "Giving an attached clip as a reference does not reproduce it: the result is a new video that resembles it.",
                              "A3 old MCP and v1: the first 6 s did not match the original (similarity 0.43), and 12 s cost 288 credits."),
    "last-frame-continues": (("create_video_from_image", "ltx-2.5", "minimax-h3", "get_last_frame"),
                             "Image-to-video from the last frame of a clip continues it; joined after the clip, the cut is hard to see.",
                             "Approach C2 (ltx-2.5): similarity across the join 0.98. C3 (minimax-h3): 0.88, a small jump. "
                             "C4 (minimax-h3 with the clip as a reference, no start frame): 0.41, a visible jump."),
    "last-frame-keeps-place": (("create_video_from_image", "get_last_frame"),
                               "A clip that starts from another clip's last frame keeps that clip's place, also when the prompt names a new place.",
                               "S2 and C7 chained: winter stayed spring; the sea stayed behind the autumn bench."),
    "picture-resets-place": (("create_video_from_text", "minimax-h3"),
                             "With a picture reference in each call, two places in one 10 s call held, each in its own part.",
                             "C6 (bottle) and C10 (bottle with two people): 2 x 10 s, all four seasons in order."),
    "words-only-places-merge": (("ltx-2.5", "create_video_from_text"),
                                "Without a picture reference, two places described in one call merged into one place.",
                                "C7 medium-only (ltx-2.5, 2 x 10 s): cherry trees on a beach; autumn and winter never came."),
    "person-in-words": (("create_video_from_text", "create_video_from_image", "ltx-2.5", "minimax-h3"),
                        "A person described in words is the same inside one call and a look-alike across calls.",
                        "C7 one call per season: coats and hair held, faces changed. C10: Theo the same when his two seasons shared a call; Mara a look-alike in every split."),
    "small-letters": (("minimax-h3", "edit_image"),
                      "Letters on a product that is small in the frame change at 480p.",
                      "B1 v1: the bottle about 60 px wide in a 640 px edited picture; the letters were wrong in the hand shots and right in the bottle-alone shot."),
    "spoken-line": (("create_video_from_text", "ltx-2.5", "minimax-h3"),
                    "A spoken line in a clip with another beat was not said. The same line alone in a short clip was said word for word.",
                    "B2, ltx-2.5, the line plus a walk-away in one 12 s clip: 0 of 3 runs. The line alone in a 4 s close-up: ltx-2.5 3 of 3, "
                    "minimax-h3 heard 2 of 2, word for word 1 of 2 (approach test, 7 November). B2 old MCP, one 30 s call: about 10 times."),
    "hex-codes": (("ltx-2.5", "minimax-h3", "create_video_from_text"),
                  "A colour code written in a prompt is drawn on screen as text.",
                  "A4 v1 (7 November): \"#E78C28\" printed for 2 s; the codes were in the setting copied into every clip."),
    "grouping": ((), "The split rule keeps the same people in one clip up to 15 s.",
                 "B2 and A2 dry runs (7 November): beats the host wrote as separate shots were merged; the spoken line was then lost."),
    "one-narration": (("create_production_sound", "generate_music", "join_production_clips"),
                      "One narration track and one music track across the joined film kept the script once and the music even.",
                      "B1 v1 with sound: 8 yes, 2 partly, 0 no; the old MCP's single call read the script 3 times and had no music."),
    "join-silent": (("join_production_clips", "join_videos"),
                    "Joining with the sound off removes any sound the clips have.",
                    "Approach C2 to C4: -91 dB after the join."),
}


def notes_for(names: set[str]) -> dict[str, dict]:
    """The notes that apply to any of the tools or models named."""
    return {i: {"applies_to": [a for a in on if a in names], "finding": finding, "evidence": evidence}
            for i, (on, finding, evidence) in NOTES.items() if names & set(on)}

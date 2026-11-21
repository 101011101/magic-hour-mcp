"""Faults found in live batch 1 (lb1l, 2026-11-20), each from a recorded chat. No network, no credits."""
import copy
import json

from mcp_magichour import tool_plan
from mcp_magichour.conversation_front import front
from mcp_magichour.video_production import advise
from mcp_magichour.video_production_tool import Story, plan_story

# W05 dumper as the host wrote it: one person per beat, each clip from the last frame before it.
W05 = {"title": "Bus Stop in the Rain", "aspect": "16:9", "audio": True,
       "setting": "A city bus stop with a glass shelter at dusk in light rain.",
       "subjects": [{"id": "Maya", "words": "Maya, a young woman in a yellow raincoat", "role": "person"},
                    {"id": "Leo", "words": "Leo, a tall young man in a grey hoodie", "role": "person"}],
       "beats": [{"seconds": 5, "text": "Medium shot of Maya at the bus stop, teasing smile", "subjects": ["Maya"], "place": "bus stop",
                  "link": "new", "spoken": ["You missed the bus again?"], "clip": 1},
                 {"seconds": 6, "text": "Medium shot of Leo at the bus stop, sheepish half smile", "subjects": ["Leo"], "place": "bus stop",
                  "link": "event", "spoken": ["I was there. The bus just didn't wait."], "clip": 2},
                 {"seconds": 4, "text": "Medium shot of Maya at the bus stop, grinning", "subjects": ["Maya"], "place": "bus stop",
                  "link": "event", "spoken": ["Then we walk."], "clip": 3},
                 {"seconds": 5, "text": "Wide shot from behind: Maya and Leo walk off under one umbrella", "subjects": ["Maya", "Leo"],
                  "place": "bus stop", "link": "event", "clip": 4}]}


def planned(story):
    return plan_story(Story(**story).model_dump(exclude_none=True))


def last_frame_problems(story):
    return [p for p in planned(story)["problems"] if "starts from the last frame" in p]


def test_a_last_frame_clip_with_a_person_not_in_that_frame_is_a_problem():
    problems = last_frame_problems(W05)
    assert [p.split(" starts")[0] for p in problems] == ["clip 2", "clip 3", "clip 4"]
    assert "Leo is not in clip 1" in problems[0]


def test_both_people_in_every_beat_passes():   # W05 happy: both in every beat, the line given to one
    s = copy.deepcopy(W05)
    for beat in s["beats"]:
        beat["subjects"] = ["Maya", "Leo"]
    assert last_frame_problems(s) == []


def test_a_person_who_walks_in_or_a_fresh_clip_passes():
    s = copy.deepcopy(W05)
    s["beats"][1]["text"] = "Leo walks up to the bus stop, sheepish half smile"
    s["beats"][2]["reference"] = s["beats"][3]["reference"] = {"kind": "none"}
    assert last_frame_problems(s) == []


def test_words_route_overlay_is_in_the_schema():   # K21, H40a: 3 refusals
    s = copy.deepcopy(W05)
    s["beats"][3]["exact_words"], s["beats"][3]["words_route"] = ["See you tomorrow"], "overlay"
    assert Story(**s).beats[3].words_route == "overlay"


def test_n_a_on_a_row_that_always_applies_takes_its_default():   # K16: 7 refusals in 3 chats
    out = front("talking", "Make the woman in the clip say this audio instead.",
                {"presenter": "video with a presenter", "line": "n/a", "length": "your_call", "shape": "n/a", "own_sound": "video"},
                attachments=[{"name": "talk.mp4", "kind": "video"}, {"name": "line.mp3", "kind": "audio"}])
    assert out["stage"] == "plan" and "line, shape" in out["changed"][-1]


def test_the_ask_stage_tells_the_host_to_state_no_other_values():   # K26 stupid: the host offered 5-10 s, the plan made 15 s
    out = front("film", "make a reel for my cafe", {"kind": "ad", "exact_words": "ask"})
    assert out["stage"] == "ask_the_user" and "Do not tell the user a length" in out["next"]
    out = front("new_picture", "make me a picture", {"look": "ask"})
    assert "Do not tell the user a length" in out["next"]


def test_music_after_a_sound_gets_a_music_from_beat_hint():   # W09: "then a soft music sting" ran from 0 s
    s = copy.deepcopy(W05)
    s["music"] = "a soft piano sting"
    request = "Logo reveal: a whoosh, then a soft music sting."
    notes = [a["note"] for a in advise(s, planned(s), request)]
    assert "music-later" in notes
    s["music_from_beat"] = 2
    assert "music-later" not in [a["note"] for a in advise(s, planned(s), request)]


def test_sheet_texts_from_the_review():
    notes, sheets = json.dumps(tool_plan.notes()), json.dumps(tool_plan.sheets())
    assert "same voice" not in notes and "same voice" not in sheets   # K29: the API does not promise the voice
    assert "generation_mode lite. The line" not in sheets and "generation_mode standard" in sheets   # K16
    assert "model minimax-h3 on the free plan" in sheets   # K02: free-tier model named (user, 2026-11-04)

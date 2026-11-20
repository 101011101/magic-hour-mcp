"""plan_conversation (MCP-28): one batch, implied defaults, required files, the film sheet."""
import asyncio
import subprocess
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from mcp_magichour import conversation_front, media_helpers_tool
from mcp_magichour.conversation_front import front


def test_missing_file_is_asked_in_the_one_batch():
    out = front("faces", "put my face on this poster", {"consent": "none", "photo_or_video": "photo", "which_person": "ask"}, attachments=[{"name": "poster.jpg", "kind": "image"}])
    assert out["stage"] == "ask_the_user"
    ids = [q["id"] for q in out["questions"]]
    assert "which_person" in ids and "file" in ids


def test_file_still_missing_after_the_batch_makes_nothing():
    out = front("change_picture", "make this warmer", {}, questions_asked=True, attachments=[])
    assert out["stage"] == "missing_file" and not out["ready"]


def test_new_video_sound_default_is_on():
    out = front("new_video", "a 10 second clip: a ufo flies through a starfield", {"from_picture": "words", "length": "10", "shape": "16:9"})
    sound = next(d for d in out["decisions"] if d["id"] == "sound")
    assert sound["value"] == "Natural sound on." and "tell_the_user" not in sound   # no telling of defaults (user, 2026-11-19)


def test_film_asks_open_rows_once_then_plans():
    ask = front("film", "an ad for my bottle", {"kind": "ad", "exact_words": "ask", "product_picture": "ask"})
    assert ask["stage"] == "ask_the_user" and {q["id"] for q in ask["questions"]} == {"exact_words", "product_picture"}
    done = front("film", "an ad for my bottle", {"kind": "ad", "exact_words": "ask", "product_picture": "ask"}, questions_asked=True)
    assert done["ready"] and done["story_rules"]
    assert not any("tell_the_user" in d for d in done["decisions"]) and "Tell the user" not in done["next"]


def test_film_never_asks_about_sound():
    with pytest.raises(ToolError):
        front("film", "a street interview", {"sound": "ask"})


def test_no_talking_is_not_silence():
    out = front("film", "an ad with mellow music and no talking", {"kind": "ad", "sound": "music only", "who_speaks": "nobody"})
    vals = {d["id"]: d["value"] for d in out["decisions"]}
    assert vals["sound"] == "on" and vals["who_speaks"] == "scene_sound" and "audio` is true" in out["next"]


def test_silence_asked_stays_silent():
    out = front("film", "a silent film of a forest", {"kind": "story_mood", "sound": "silent", "who_speaks": "nobody"})
    assert {d["id"]: d["value"] for d in out["decisions"]}["sound"] == "silent"


def test_video_with_no_length_checks_short_or_film_once():
    out = front("new_video", "a ufo over a city", {"from_picture": "words", "length": "your_call", "shape": "16:9"})
    assert out["stage"] == "ask_the_user" and [q["id"] for q in out["questions"]] == ["short_or_film"]
    again = front("new_video", "a ufo over a city", {"from_picture": "words", "length": "your_call", "shape": "16:9"}, questions_asked=True)
    assert again["stage"] == "plan"
    stated = front("new_video", "a 5s clip of a ufo over a city", {"from_picture": "words", "length": "5", "shape": "16:9"})
    assert stated["stage"] == "plan"
    song = front("new_video", "a video for this track, as long as the song", {"from_picture": "words", "length": "your_call", "shape": "16:9"})
    assert song["stage"] != "ask_the_user" or "short_or_film" not in [q["id"] for q in song["questions"]]
    answered = front("new_video", "a ufo over a city", {"from_picture": "words", "length": "your_call", "shape": "16:9", "short_or_film": "one short clip"}, questions_asked=True)
    assert answered["stage"] == "plan"
    for clear in ("make my dog pic move", "a logo animation with this"):
        out = front("new_video", clear, {"from_picture": "picture", "length": "your_call", "shape": "1:1"})
        assert out["stage"] != "ask_the_user" or "short_or_film" not in [q["id"] for q in out["questions"]]
    longer = front("new_video", "a ufo over a city", {"from_picture": "words", "short_or_film": "a longer film please"}, questions_asked=True)
    assert longer["stage"] == "switch_family" and "family film" in longer["next"]


def test_media_facts_read_length_and_shape(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=360x640:d=6:r=24", str(clip)])

    async def fake_fetch(media, folder, kinds=("image", "video")):
        return Path(media), False
    monkeypatch.setattr(media_helpers_tool, "_fetch_media", fake_fetch)
    conversation_front._MEDIA_CACHE.clear()
    media = asyncio.run(conversation_front.media_facts([{"name": "clip.mp4", "kind": "video", "file_path": str(clip)},
                                                        {"name": "note.txt", "kind": "text", "file_path": "x"},
                                                        {"name": "nofile.jpg", "kind": "image"}]))
    assert media == [{"name": "clip.mp4", "kind": "video", "seconds": 6.0, "width": 360, "height": 640, "shape": "9:16", "has_sound": False}]
    out = front("change_video", "trim the whole clip to vertical", {}, attachments=[{"name": "clip.mp4", "kind": "video"}], media=media)
    assert out["media"] == media and "never guess a length" in out["next"]


def test_media_facts_never_fail_the_plan(monkeypatch):
    async def broken(media, folder, kinds=("image", "video")):
        raise RuntimeError("down")
    monkeypatch.setattr(media_helpers_tool, "_fetch_media", broken)
    conversation_front._MEDIA_CACHE.clear()
    media = asyncio.run(conversation_front.media_facts([{"name": "a.mp4", "kind": "video", "file_path": "api-assets/x/a.mp4"}]))
    assert media[0]["name"] == "a.mp4" and "error" in media[0]


def test_tool_names_sent_as_rows_are_left_out():
    # c3/c4: hosts answered tool names as rows in 44 of 60 faces chats and the call was refused.
    out = front("faces", "put me into this beach photo", {"consent": "none", "scene": "scene picture",
                "change_clothes_in_photo": "n/a", "place_person_in_scene": "n/a"},
                attachments=[{"name": "me.jpg", "kind": "image"}, {"name": "beach.jpg", "kind": "image"}])
    assert out["stage"] == "plan" and "place_person_in_scene" in out["changed"][0]
    assert "place_person_in_scene" in {d["id"]: d["instruction"] for d in out["decisions"]}["scene"]


def test_the_plan_does_not_tell_the_user_the_defaults():
    out = front("new_video", "a 10 second clip: a ufo flies through a starfield", {"from_picture": "words", "length": "10", "shape": "16:9"})
    assert out["stage"] == "plan" and "Tell the user" not in out["next"]   # user, 2026-11-19


def test_every_tool_that_had_no_sheet_now_has_a_row():
    from mcp_magichour import tool_plan
    families = tool_plan.sheets()["families"]
    for tool in ("change_clothes_in_photo", "place_person_in_scene", "replace_character_in_video", "translate_video",
                 "create_video_from_image", "create_video_from_audio", "create_lip_sync_video", "ai_voice_cloner_create_audio"):
        homes = [f for f, s in families.items() if tool in s["tools"] and any(tool in a for r in s["rows"] for a in r["answers"].values())]
        assert homes, tool
    assert conversation_front.EXTRA_TOOLS == {} and " also:" not in conversation_front.index()


def test_a_video_for_a_song_asks_for_the_song():
    out = front("new_video", "make a music video for my song", {"from_picture": "words", "length": "your_call", "shape": "16:9", "song": "whole track"})
    assert out["stage"] == "ask_the_user" and any(q["id"] == "file" and "song" in q["ask"] for q in out["questions"])

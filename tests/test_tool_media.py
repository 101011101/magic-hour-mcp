"""Tests for tool management's new media tools (MCP-29 onward), on small media made with ffmpeg."""
import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastmcp import Client

from mcp_magichour import media_tools
from mcp_magichour.openapi_server import create_mcp
from mcp_magichour.tool_media import mix_onto_video

ROOT = Path(__file__).resolve().parents[1]


def ff(*args):
    media_tools._ffmpeg(list(args))


@unittest.skipUnless(media_tools.have_ffmpeg(), "no ffmpeg")
class SoundOnVideoTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        # a 4 s clip whose own sound is a "talk" tone from 1 s to 3 s, silent around it
        self.film = self.dir / "clip.mp4"
        ff("-f", "lavfi", "-i", "testsrc=size=320x240:rate=24:duration=4", "-f", "lavfi",
           "-i", "sine=frequency=300:duration=4", "-af", "volume='between(t,1,3)':eval=frame",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(self.film))
        self.music = self.dir / "music.wav"
        ff("-f", "lavfi", "-i", "sine=frequency=600:duration=15", str(self.music))
        self.voice = self.dir / "voice.wav"
        ff("-f", "lavfi", "-i", "sine=frequency=900:duration=2", str(self.voice))
        self.long_voice = self.dir / "long-voice.wav"
        ff("-f", "lavfi", "-i", "sine=frequency=900:duration=6", str(self.long_voice))

    def test_music_under_the_videos_own_sound_keeps_the_picture_and_length(self):
        """E27a-c: music under the user's clip."""
        out = self.dir / "out.mp4"
        done = mix_onto_video(self.film, out, music=self.music, original="keep")
        info = media_tools.probe(out)
        self.assertTrue(info["audio"])
        self.assertEqual((info["width"], info["height"]), (320, 240))
        self.assertAlmostEqual(info["seconds"], 4, delta=0.3)
        self.assertGreaterEqual(done["kept_spoken_spans"], 1)

    def test_replace_removes_the_videos_own_sound(self):
        """E28b/c: a narration instead of the conversation."""
        out = self.dir / "out.mp4"
        done = mix_onto_video(self.film, out, voice=self.voice, original="replace")
        self.assertEqual(done["original"], "replace")
        self.assertEqual(done["kept_spoken_spans"], 0)
        self.assertTrue(media_tools.probe(out)["audio"])

    def test_a_voice_longer_than_the_video_is_not_cut(self):
        """E28c: the last words ran past the end and were cut."""
        out = self.dir / "out.mp4"
        done = mix_onto_video(self.film, out, voice=self.long_voice, original="replace")
        self.assertTrue(done["voice_tempo"] > 1.0 or done["held_end_seconds"] > 0)
        self.assertGreaterEqual(media_tools.probe_seconds(out) * done["voice_tempo"], 6 - 0.3)

    def test_nothing_to_add_is_an_error(self):
        with self.assertRaises(ValueError):
            mix_onto_video(self.film, self.dir / "out.mp4")


class SwitchTests(unittest.TestCase):
    def names(self, value):
        async def run():
            with patch.dict(os.environ, {"MAGIC_HOUR_TOOL_PLAN": value}):
                async with Client(create_mcp()) as client:
                    return {t.name for t in await client.list_tools()}
        return asyncio.run(run())

    def test_off_by_default_on_with_the_switch(self):
        self.assertNotIn("add_sound_to_video", self.names("off"))
        self.assertIn("add_sound_to_video", self.names("on"))


class IsolationTests(unittest.TestCase):
    def test_no_direct_import_from_video_composition(self):
        src = (ROOT / "mcp_magichour" / "tool_media.py").read_text()
        for mod in ("plan_request", "video_production", "video_production_tool", "gates"):
            self.assertNotIn(f"from .{mod} ", src)
            self.assertNotIn(f"import {mod}", src)


if __name__ == "__main__":
    unittest.main()

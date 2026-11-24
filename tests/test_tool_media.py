"""Tests for tool management's new media tools (MCP-TOOLS-29 onward), on small media made with ffmpeg."""
import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastmcp import Client

from mcp_magichour import media_tools
from mcp_magichour.openapi_server import create_mcp
from mcp_magichour.tool_media import attach_card, card_clip, mix_onto_video, overlay_picture, recolour, side_by_side

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


def mean_rgb(path):
    from PIL import Image, ImageStat
    return ImageStat.Stat(Image.open(path).convert("RGB")).mean


@unittest.skipUnless(media_tools.have_ffmpeg(), "no ffmpeg")
class NewPictureToolTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.dir = Path(tempfile.mkdtemp())
        self.grey = self.dir / "grey.png"; Image.new("RGB", (400, 300), (128, 128, 128)).save(self.grey)
        self.red = self.dir / "red.png"; Image.new("RGB", (300, 300), (200, 40, 40)).save(self.red)
        self.wide = self.dir / "wide.png"; Image.new("RGB", (800, 200), (40, 40, 200)).save(self.wide)
        self.logo = self.dir / "logo.png"; Image.new("RGBA", (100, 100), (255, 255, 0, 255)).save(self.logo)
        self.film = self.dir / "clip.mp4"
        ff("-f", "lavfi", "-i", "color=c=gray:size=320x240:rate=24:duration=2", "-f", "lavfi", "-i", "sine=duration=2",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(self.film))

    def test_warmer_raises_red_and_lowers_blue_same_size(self):
        """B07c, J49a: warmer, nothing redrawn."""
        out = recolour(self.grey, self.dir / "warm.png", warmth=0.5)
        r, g, b = mean_rgb(out)
        self.assertGreater(r, b + 40)   # clearly warmer (warmth 0.15 per unit was too weak: B07c)
        from PIL import Image
        self.assertEqual(Image.open(out).size, (400, 300))

    def test_saturation_zero_is_black_and_white(self):
        """B10c."""
        r, g, b = mean_rgb(recolour(self.red, self.dir / "bw.png", saturation=0))
        self.assertLess(max(r, g, b) - min(r, g, b), 3)

    def test_a_video_keeps_its_sound_and_length(self):
        out = recolour(self.film, self.dir / "warm.mp4", warmth=0.4)
        info = media_tools.probe(out)
        self.assertTrue(info["audio"])
        self.assertAlmostEqual(info["seconds"], 2, delta=0.3)

    def test_side_by_side_keeps_each_picture_whole(self):
        """G35a: before and after, side by side, photos unchanged, no empty white space (run wnew had white bands)."""
        from PIL import Image
        out = side_by_side([self.red, self.wide], self.dir / "sbs.png", "row", "16:9", labels=["Before", "After"])
        sheet = Image.open(out).convert("RGB")
        self.assertEqual(sheet.size, (1280, 720))
        self.assertEqual(sheet.getpixel((320, 420)), (200, 40, 40))   # the red picture, whole, in the left cell
        self.assertEqual(sheet.getpixel((960, 400)), (40, 40, 200))   # the wide blue picture in the right cell
        above = sheet.getpixel((960, 200))                             # filled with a blurred copy, not white
        self.assertNotEqual(above, (255, 255, 255))
        self.assertLess(sum(sheet.getpixel((640 + 320, 10))), 100)      # the label band at the top of the cell

    def test_side_by_side_without_labels_or_with_a_colour(self):
        """Not limited to before and after: plain side by side, any background."""
        from PIL import Image
        out = side_by_side([self.red, self.wide, self.grey], self.dir / "three.png", "row", "16:9", background="white")
        self.assertEqual(Image.open(out).convert("RGB").getpixel((5, 5)), (255, 255, 255))

    def test_side_by_side_needs_two_to_four(self):
        with self.assertRaises(ValueError):
            side_by_side([self.red], self.dir / "x.png")

    def test_logo_in_the_top_right_corner_of_a_video(self):
        """E29a."""
        out = overlay_picture(self.film, self.logo, self.dir / "logo.mp4", "top_right", size=0.2)
        info = media_tools.probe(out)
        self.assertEqual((info["width"], info["height"]), (320, 240))
        self.assertTrue(info["audio"])
        frame = media_tools.last_frame(out, self.dir / "f.png")
        from PIL import Image
        im = Image.open(frame).convert("RGB")
        r, g, b = im.getpixel((320 - 10 - 20, 10 + 20))
        self.assertTrue(r > 200 and g > 200 and b < 80, (r, g, b))      # yellow logo in the top right
        r, g, b = im.getpixel((20, 220))
        self.assertTrue(abs(r - g) < 15 and abs(g - b) < 15, (r, g, b))  # grey elsewhere

    def test_logo_on_a_picture(self):
        out = overlay_picture(self.grey, self.logo, self.dir / "grey-with-logo.png", "bottom_left", size=0.25)
        from PIL import Image
        self.assertEqual(Image.open(out).size, (400, 300))

    def test_card_attached_after_the_clip_in_one_file(self):
        """E29b, run wnew: join_videos failed (media_tools.join calls ffmpeg by name); the card tool attaches it itself."""
        card = card_clip(self.dir / "card.mp4", 2, ["Ready for takeoff?"], "black", (320, 240))
        out = attach_card(self.film, card, self.dir / "with-card.mp4", "after")
        info = media_tools.probe(out)
        self.assertEqual((info["width"], info["height"]), (320, 240))
        self.assertAlmostEqual(info["seconds"], 4, delta=0.4)
        self.assertTrue(info["audio"])
        from PIL import Image
        self.assertLess(sum(Image.open(media_tools.last_frame(out, self.dir / "end.png")).convert("RGB").getpixel((5, 5))), 30)

    def test_a_generated_card_fills_the_frame_with_background_none(self):
        """User, 2026-11-21: the card is generated first and given as a picture; with background none it fills the frame."""
        from PIL import Image
        made = self.dir / "made-card.png"
        Image.new("RGB", (640, 480), (11, 29, 58)).save(made)   # a generated card, the clip's shape
        out = card_clip(self.dir / "card.mp4", 2, None, "none", (320, 240), made)
        corner = Image.open(media_tools.last_frame(out, self.dir / "end.png")).convert("RGB").getpixel((3, 3))
        self.assertTrue(all(abs(a - b) < 12 for a, b in zip(corner, (11, 29, 58))), corner)   # no black border

    def test_end_card_matches_the_clip_and_can_be_joined(self):
        """E29b: a 2 s black card with exact words, the clip's size, with a sound track."""
        out = card_clip(self.dir / "card.mp4", 2, ["Ready for takeoff?", "@flightschool"], "black", (320, 240))
        info = media_tools.probe(out)
        self.assertEqual((info["width"], info["height"]), (320, 240))
        self.assertAlmostEqual(info["seconds"], 2, delta=0.3)
        self.assertTrue(info["audio"])


class SwitchTests(unittest.TestCase):
    def names(self, value, conversation="on"):
        async def run():
            with patch.dict(os.environ, {"MAGIC_HOUR_TOOL_PLAN": value, "MAGIC_HOUR_CONVERSATION": conversation}):
                server = create_mcp()
            async with Client(server) as client:
                return {t.name for t in await client.list_tools()}
        return asyncio.run(run())

    def test_on_with_the_conversation_front_or_the_tool_plan_switch(self):
        # 2026-11-21: the conversation front is on by default, so the 5 tools are too
        new = {"add_sound_to_video", "adjust_colours", "put_pictures_side_by_side", "put_picture_on_video", "make_card_clip"}
        self.assertFalse(new & self.names("off", conversation="off"))
        self.assertTrue(new <= self.names("on", conversation="off"))
        self.assertTrue(new <= self.names("off"))


class IsolationTests(unittest.TestCase):
    def test_no_direct_import_from_video_composition(self):
        src = (ROOT / "mcp_magichour" / "tool_media.py").read_text()
        for mod in ("plan_request", "video_production", "video_production_tool", "gates"):
            self.assertNotIn(f"from .{mod} ", src)
            self.assertNotIn(f"import {mod}", src)


if __name__ == "__main__":
    unittest.main()


class HeadSwapPhotoTests(unittest.TestCase):
    """swap_heads_in_photo helpers (b5 Y01, head swap check 2026-11-23)."""

    def test_cut_box_grows_the_face_and_snaps_to_near_photo_edges(self):
        from mcp_magichour.tool_media import cut_box
        self.assertEqual(cut_box((142, 25, 204, 285), (640, 384)), (91, 0, 397, 384))
        self.assertEqual(cut_box((310, 80, 180, 228), (640, 384)), (265, 0, 535, 384))
        self.assertEqual(cut_box((300, 300, 100, 100), (1000, 1000)), (275, 270, 425, 430))

    def test_margin_is_added_only_on_photo_edges_and_cut_off_again(self):
        from PIL import Image, ImageChops
        from mcp_magichour.tool_media import padded, unpadded
        photo = Image.effect_noise((640, 384), 60).convert("RGB")
        box = (91, 0, 397, 384)
        cut = photo.crop(box)
        pad, margins = padded(cut, box, photo.size)
        self.assertEqual(margins, (0, 16, 0, 16))
        self.assertEqual(pad.size, (306, 416))
        self.assertIsNone(ImageChops.difference(unpadded(pad, margins, cut.size), cut).getbbox())

    def test_a_face_crop_is_found_where_it_was_cut(self):
        from PIL import Image
        from mcp_magichour.tool_media import locate_face
        photo = Image.effect_noise((640, 384), 80).convert("RGB")
        self.assertEqual(locate_face(photo, photo.crop((310, 80, 490, 308))), (310, 80, 180, 228))

    def test_tool_is_listed_with_person_places(self):
        async def tools():
            async with Client(create_mcp()) as client:
                return {t.name: t for t in await client.list_tools()}
        with patch.dict(os.environ, {"MAGIC_HOUR_CONVERSATION": "on"}):
            listed = asyncio.run(tools())
        self.assertIn("swap_heads_in_photo", listed)
        self.assertIn("1 = the leftmost face", listed["swap_heads_in_photo"].description)

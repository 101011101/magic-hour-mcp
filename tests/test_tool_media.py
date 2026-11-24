"""Tests for tool management's new media tools, on small media made with ffmpeg."""
import asyncio
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastmcp import Client
from fastmcp.exceptions import ToolError

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
        """Music under the user's clip."""
        out = self.dir / "out.mp4"
        done = mix_onto_video(self.film, out, music=self.music, original="keep")
        info = media_tools.probe(out)
        self.assertTrue(info["audio"])
        self.assertEqual((info["width"], info["height"]), (320, 240))
        self.assertAlmostEqual(info["seconds"], 4, delta=0.3)
        self.assertGreaterEqual(done["kept_spoken_spans"], 1)

    def test_replace_removes_the_videos_own_sound(self):
        """A narration instead of the conversation."""
        out = self.dir / "out.mp4"
        done = mix_onto_video(self.film, out, voice=self.voice, original="replace")
        self.assertEqual(done["original"], "replace")
        self.assertEqual(done["kept_spoken_spans"], 0)
        self.assertTrue(media_tools.probe(out)["audio"])

    def test_a_voice_longer_than_the_video_is_not_cut(self):
        """The last words ran past the end and were cut."""
        out = self.dir / "out.mp4"
        done = mix_onto_video(self.film, out, voice=self.long_voice, original="replace")
        self.assertTrue(done["voice_tempo"] > 1.0 or done["held_end_seconds"] > 0)
        self.assertGreaterEqual(media_tools.probe_seconds(out) * done["voice_tempo"], 6 - 0.3)

    def test_nothing_to_add_is_an_error(self):
        with self.assertRaises(ValueError):
            mix_onto_video(self.film, self.dir / "out.mp4")

    def test_no_working_files_are_left_behind(self):
        """Each call with original replace left silent.mp4 and held.mp4 in the temp folder."""
        scratch = self.dir / "temp"
        scratch.mkdir()
        with patch.object(tempfile, "tempdir", str(scratch)):
            mix_onto_video(self.film, self.dir / "out.mp4", voice=self.long_voice, original="replace")
        self.assertEqual(list(scratch.iterdir()), [])

    def test_a_video_mp4_cannot_hold_as_it_is_gets_sound(self):
        """A ProRes .mov (or a VP8 WebM) failed: its video was copied into an mp4."""
        prores = self.dir / "clip.mov"
        ff("-f", "lavfi", "-i", "testsrc=size=320x240:rate=24:duration=2", "-f", "lavfi", "-i", "sine=duration=2",
           "-c:v", "prores_ks", "-c:a", "aac", "-shortest", str(prores))
        for original in ("under", "replace"):
            out = self.dir / f"prores-{original}.mp4"
            mix_onto_video(prores, out, music=self.music, original=original)
            info = media_tools.probe(out)
            self.assertTrue(info["audio"])
            self.assertEqual((info["width"], info["height"]), (320, 240))


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
        """Warmer, nothing redrawn."""
        out = recolour(self.grey, self.dir / "warm.png", warmth=0.5)
        r, g, b = mean_rgb(out)
        self.assertGreater(r, b + 40)   # clearly warmer (warmth 0.15 per unit was too weak)
        from PIL import Image
        self.assertEqual(Image.open(out).size, (400, 300))

    def test_saturation_zero_is_black_and_white(self):
        r, g, b = mean_rgb(recolour(self.red, self.dir / "bw.png", saturation=0))
        self.assertLess(max(r, g, b) - min(r, g, b), 3)

    def test_a_video_keeps_its_sound_and_length(self):
        out = recolour(self.film, self.dir / "warm.mp4", warmth=0.4)
        info = media_tools.probe(out)
        self.assertTrue(info["audio"])
        self.assertAlmostEqual(info["seconds"], 2, delta=0.3)

    def test_side_by_side_keeps_each_picture_whole(self):
        """Before and after, side by side, photos unchanged, no empty white space (in testing there were white bands)."""
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

    def test_a_label_wider_than_its_cell_is_shrunk_not_cut(self):
        """'Before treatment week one' in a 320 px cell showed as 'fore treatment week c'."""
        from PIL import Image
        out = side_by_side([self.grey] * 4, self.dir / "labels.png", "row", "16:9", background="white",
                           labels=["Before treatment week one", "After", "x", "y"])
        band = Image.open(out).convert("L").crop((0, 0, 320, 30)).point(lambda v: 255 if v > 200 else 0)
        left, _, right, _ = band.getbbox()
        self.assertGreater(left, 3)      # the first letter is whole
        self.assertLess(right, 317)      # the last letter is whole

    def phone_photo(self):
        """A portrait photo (300x400, red band on top) stored landscape with EXIF Orientation 6, as phones save it."""
        from PIL import Image, ImageDraw
        upright = Image.new("RGB", (300, 400), (0, 0, 200))
        ImageDraw.Draw(upright).rectangle((0, 0, 299, 60), fill=(255, 0, 0))
        exif = Image.Exif()
        exif[0x0112] = 6
        phone = self.dir / "phone.jpg"
        upright.transpose(Image.Transpose.ROTATE_90).save(phone, exif=exif.tobytes(), quality=95)
        return phone

    def test_side_by_side_shows_a_phone_photo_upright(self):
        """A phone photo was shown sideways."""
        from PIL import Image
        sheet = Image.open(side_by_side([self.phone_photo(), self.grey], self.dir / "sbs.png", "row", "16:9",
                                        background="white")).convert("RGB")
        r, g, b = sheet.getpixel((320, 5))   # upright: 540x720 in the 640x720 cell, the red band on top
        self.assertTrue(r > 200 and g < 60 and b < 60, (r, g, b))

    def test_a_logo_on_a_phone_photo_is_sized_from_its_upright_width(self):
        """The logo's size and margin came from the stored width (400), not the shown width (300)."""
        from PIL import Image
        im = Image.open(overlay_picture(self.phone_photo(), self.logo, self.dir / "phone-logo.png", "top_right",
                                        size=0.2)).convert("RGB")
        self.assertEqual(im.size, (300, 400))
        self.assertGreater(im.getpixel((285, 30))[1], 200)   # the 60 px logo ends 9 px from the right edge: yellow
        self.assertLess(im.getpixel((215, 30))[1], 80)       # left of it: the red band

    def see_through_logo(self):
        """A 300x300 PNG, see-through but for a green disc in the middle."""
        from PIL import Image, ImageDraw
        logo = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
        ImageDraw.Draw(logo).ellipse((50, 50, 250, 250), fill=(0, 200, 0, 255))
        logo.save(self.dir / "see-through.png")
        return self.dir / "see-through.png"

    def test_side_by_side_shows_the_background_where_a_picture_is_see_through(self):
        """The see-through part of a PNG was black, even on a white background."""
        from PIL import Image
        sheet = Image.open(side_by_side([self.see_through_logo(), self.grey], self.dir / "sbs.png", "row", "16:9",
                                        background="white")).convert("RGB")
        self.assertEqual(sheet.getpixel((330, 370)), (0, 200, 0))   # the disc, in the middle of the 640x640 fitted logo
        self.assertEqual(sheet.getpixel((20, 60)), (255, 255, 255))  # a see-through corner of the logo

    def test_new_colours_keep_a_logo_see_through(self):
        """adjust_colours made a see-through logo opaque."""
        from PIL import Image
        out = Image.open(recolour(self.see_through_logo(), self.dir / "warm-logo.png", warmth=0.3))
        self.assertEqual(out.mode, "RGBA")
        self.assertEqual(out.getpixel((2, 2))[3], 0)
        self.assertEqual(out.getpixel((150, 150))[3], 255)

    def test_side_by_side_needs_two_to_four(self):
        with self.assertRaises(ValueError):
            side_by_side([self.red], self.dir / "x.png")

    def test_logo_in_the_top_right_corner_of_a_video(self):
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

    def test_a_video_of_odd_size_can_be_recoloured_and_get_a_logo(self):
        """A 321x241 video failed: H.264 in yuv420p needs even sizes."""
        odd = self.dir / "odd.mp4"
        ff("-f", "lavfi", "-i", "testsrc=size=321x241:rate=24:duration=1", "-f", "lavfi", "-i", "sine=duration=1",
           "-c:v", "libx264", "-pix_fmt", "yuv444p", "-c:a", "aac", "-shortest", str(odd))
        for out in (recolour(odd, self.dir / "odd-warm.mp4", warmth=0.3), overlay_picture(odd, self.logo, self.dir / "odd-logo.mp4")):
            info = media_tools.probe(out)
            self.assertEqual((info["width"], info["height"]), (320, 240))
            self.assertTrue(info["audio"])

    def test_logo_on_a_picture(self):
        out = overlay_picture(self.grey, self.logo, self.dir / "grey-with-logo.png", "bottom_left", size=0.25)
        from PIL import Image
        self.assertEqual(Image.open(out).size, (400, 300))

    def test_card_attached_after_the_clip_in_one_file(self):
        """In testing, join_videos failed (media_tools.join calls ffmpeg by name); the card tool attaches it itself."""
        card = card_clip(self.dir / "card.mp4", 2, ["Ready for takeoff?"], "black", (320, 240))
        out = attach_card(self.film, card, self.dir / "with-card.mp4", "after")
        info = media_tools.probe(out)
        self.assertEqual((info["width"], info["height"]), (320, 240))
        self.assertAlmostEqual(info["seconds"], 4, delta=0.4)
        self.assertTrue(info["audio"])
        from PIL import Image
        self.assertLess(sum(Image.open(media_tools.last_frame(out, self.dir / "end.png")).convert("RGB").getpixel((5, 5))), 30)

    def test_a_generated_card_fills_the_frame_with_background_none(self):
        """The card is generated first and given as a picture; with background none it fills the frame."""
        from PIL import Image
        made = self.dir / "made-card.png"
        Image.new("RGB", (640, 480), (11, 29, 58)).save(made)   # a generated card, the clip's shape
        out = card_clip(self.dir / "card.mp4", 2, None, "none", (320, 240), made)
        corner = Image.open(media_tools.last_frame(out, self.dir / "end.png")).convert("RGB").getpixel((3, 3))
        self.assertTrue(all(abs(a - b) < 12 for a, b in zip(corner, (11, 29, 58))), corner)   # no black border

    def test_end_card_matches_the_clip_and_can_be_joined(self):
        """A 2 s black card with exact words, the clip's size, with a sound track."""
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
        # The conversation front is on by default, so the 5 tools are too
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


def similar_faces(size, n, face):
    """A photo of n faces in a row that look alike on a small copy (one skin colour, two dark eyes), each with its own
    fine texture. Returns (photo, the face boxes with a small margin, as face detection cuts them)."""
    import random
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    rand = random.Random(3)

    def noise(w, h, spread):
        return Image.frombytes("L", (w, h), bytes(max(0, min(255, round(rand.gauss(128, spread)))) for _ in range(w * h))).convert("RGB")

    width, height = size
    photo = ImageChops.add(noise(width // 4, height // 4, 25).resize(size).filter(ImageFilter.GaussianBlur(6)),
                           Image.new("RGB", size, (40, 60, 80)))
    boxes = []
    for i in range(n):
        fw, fh = face, round(face * 1.2)
        x, y = round(width * (i + 0.5) / n - fw / 2), round(height * 0.45) + rand.randint(-40, 40)
        skin = ImageChops.add(noise(fw, fh, 18).filter(ImageFilter.GaussianBlur(1.5)), Image.new("RGB", (fw, fh), (120, 80, 60)))
        oval = Image.new("L", (fw, fh), 0)
        ImageDraw.Draw(oval).ellipse((0, 0, fw - 1, fh - 1), fill=255)
        photo.paste(skin, (x, y), oval)
        draw = ImageDraw.Draw(photo)
        for ex in (0.25, 0.65):
            draw.ellipse((x + fw * ex, y + fh * 0.35, x + fw * (ex + 0.1), y + fh * 0.45), fill=(20, 20, 20))
        boxes.append((x - fw // 10, y - fh // 10, fw + fw // 5, fh + fh // 5))
    return photo, boxes


class HeadSwapPhotoTests(unittest.TestCase):
    """swap_heads_in_photo helpers."""

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

    def test_a_small_cut_out_is_pasted_back_without_an_error(self):
        """The faded edge was 12 px on each side: a cut-out under 25 px raised 'x1 must be greater than or equal to x0'."""
        from PIL import Image
        from mcp_magichour.tool_media import cut_box, put_head_back
        photo = Image.effect_noise((400, 300), 60).convert("RGB")
        face = (200, 150, 9, 11)
        box = cut_box(face, photo.size)
        new = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), (0, 255, 0))
        pasted = put_head_back(photo, new, box, 0, [face])
        self.assertEqual(pasted.size, photo.size)

    def test_each_of_several_similar_faces_is_found_where_it_was_cut(self):
        """Faces that look alike on the small copy all landed on the same box."""
        from mcp_magichour.tool_media import locate_face
        photo, boxes = similar_faces((1600, 1200), 4, 60)
        for x, y, w, h in boxes:
            self.assertEqual(locate_face(photo, photo.crop((x, y, x + w, y + h))), (x, y, w, h))

    def test_tool_is_listed_with_person_places(self):
        async def tools():
            async with Client(create_mcp()) as client:
                return {t.name: t for t in await client.list_tools()}
        with patch.dict(os.environ, {"MAGIC_HOUR_CONVERSATION": "on"}):
            listed = asyncio.run(tools())
        self.assertIn("swap_heads_in_photo", listed)
        self.assertIn("1 = the leftmost face", listed["swap_heads_in_photo"].description)


class CharacterReplaceTextTests(unittest.TestCase):
    def test_the_selection_mode_named_in_the_description_is_an_allowed_value(self):
        """The text said 'selection_mode points'; the API takes only auto or point."""
        import json
        import re
        from mcp_magichour.openapi_policies import apply_magic_hour_policies
        spec = apply_magic_hour_policies(json.loads((ROOT / "docs" / "openapi.json").read_text()))
        operation = spec["paths"]["/v1/character-replace"]["post"]
        style = operation["requestBody"]["content"]["application/json"]["schema"]["properties"]["style"]
        allowed = set(style["properties"]["selection_mode"]["enum"])
        named = re.findall(r"selection_mode (\w+)", operation["description"])
        self.assertTrue(named)
        self.assertLessEqual(set(named), allowed)


def group_photo(size, boxes):
    """A plain photo with a noise-textured 'face' in each box, so a face crop is found in one place only."""
    from PIL import Image
    photo = Image.new("RGB", size, (120, 140, 160))
    noise = Image.effect_noise(size, 70).convert("RGB")
    for x, y, w, h in boxes:
        photo.paste(noise.crop((x, y, x + w, y + h)), (x, y))
    return photo


def change_in(before, after, box):
    """The mean change of a box between two pictures, 0 to 765."""
    from PIL import ImageChops, ImageStat
    x, y, w, h = box
    return sum(ImageStat.Stat(ImageChops.difference(before.crop((x, y, x + w, y + h)), after.crop((x, y, x + w, y + h)))).mean)


class FakeMagicHour:
    """The Magic Hour calls of swap_heads_in_photo, with no network. Face detection returns crops cut at `boxes` from
    the uploaded photo; a head swap paints a green oval over the middle of its cut-out."""

    def __init__(self, boxes, failed_job=None, missing=()):
        self.boxes, self.failed_job, self.missing = boxes, failed_job, set(missing)
        self.dir = Path(tempfile.mkdtemp())
        self.uploads, self.jobs, self.charged = {}, {}, 0

    async def api(self, method, path, body=None):
        if method == "POST" and path == "/v1/face-detection":
            self.detected = self.uploads[body["assets"]["target_file_path"]]
            return {"id": "det1"}
        if path == "/v1/face-detection/det1":
            return {"status": "complete", "faces": [{"path": f"api-assets/acc/det1/{n}.png", "url": f"https://x/det1/{n}.png"}
                                                    for n in range(len(self.boxes))]}
        if method == "POST" and path == "/v1/head-swap":
            job = f"hs{len(self.jobs)}"
            self.jobs[job] = body
            self.charged += 10
            return {"id": job, "credits_charged": 10}
        if path.startswith("/v1/image-projects/"):
            project = path.rsplit("/", 1)[1]
            if project in self.missing:
                raise ToolError(f"Magic Hour refused {path} (HTTP 404): not found")
            if project == self.failed_job:
                return {"status": "error", "error": {"message": "no face"}}
            return {"status": "complete", "downloads": [{"url": f"https://x/{project}.png"}]}
        raise AssertionError(path)

    async def upload(self, file, kind="image"):
        ref = f"api-assets/acc/up{len(self.uploads)}.png"
        self.uploads[ref] = Path(shutil.copy(file, self.dir / f"up{len(self.uploads)}.png"))
        return ref

    async def download(self, url, out):
        from PIL import Image, ImageDraw
        name = url.rsplit("/", 1)[1][:-4]
        if "/det1/" in url:
            x, y, w, h = self.boxes[int(name)]
            Image.open(self.detected).convert("RGB").crop((x, y, x + w, y + h)).save(out)
        else:
            cut = Image.open(self.uploads[self.jobs[name]["assets"]["body_file_path"]]).convert("RGB")
            ImageDraw.Draw(cut).ellipse((cut.width * 0.25, cut.height * 0.2, cut.width * 0.75, cut.height * 0.8), fill=(0, 255, 0))
            cut.save(out)
        return out

    async def fetch_media(self, media, folder, kinds=("image", "video")):
        return Path(shutil.copy(media, folder / ("source" + Path(media).suffix))), True

    async def deliver(self, out, picture):
        return {"file": str(shutil.copy(out, self.dir / "result.png"))}

    def swap(self, picture, swaps):
        """Call swap_heads_in_photo; returns (is_error, the result's text)."""
        from mcp_magichour import tool_media

        async def run():
            with patch.dict(os.environ, {"MAGIC_HOUR_CONVERSATION": "on"}):
                server = create_mcp()
            with patch.object(tool_media, "_api", self.api), patch.object(tool_media, "_upload", self.upload), \
                    patch.object(tool_media, "_download", self.download), \
                    patch.object(tool_media, "_fetch_media", self.fetch_media), \
                    patch.object(tool_media, "_deliver", self.deliver), \
                    patch("mcp_magichour.openapi_server.current_authorization_header", return_value="Bearer synthetic-test-token"), \
                    patch("mcp_magichour.oauth_compat.current_authorization_header", return_value="Bearer synthetic-test-token"):
                async with Client(server) as client:
                    result = await client.call_tool("swap_heads_in_photo", {"picture": str(picture), "swaps": swaps},
                                                    raise_on_error=False)
            return result.is_error, result.content[0].text
        return asyncio.run(run())


class SwapHeadsToolTests(unittest.TestCase):
    """swap_heads_in_photo through the MCP client, with the Magic Hour API faked."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.boxes = [(60, 80, 90, 110), (260, 80, 90, 110), (460, 80, 90, 110)]
        self.photo = self.dir / "group.png"
        group_photo((640, 384), self.boxes).save(self.photo)

    def test_two_of_three_people_get_a_new_head(self):
        from PIL import Image
        api = FakeMagicHour(self.boxes)
        error, text = api.swap(self.photo, [{"person": 1, "head": "https://h/a.png"}, {"person": 2, "head": "https://h/b.png"}])
        self.assertFalse(error, text)
        done = json.loads(text)
        self.assertEqual(done["credits_charged"], 20)
        before, after = Image.open(self.photo).convert("RGB"), Image.open(done["file"]).convert("RGB")
        self.assertGreater(change_in(before, after, self.boxes[0]), 50)
        self.assertGreater(change_in(before, after, self.boxes[1]), 50)
        self.assertEqual(change_in(before, after, self.boxes[2]), 0)

    def test_every_head_is_checked_before_the_first_charge(self):
        """Person 2's head was a wrong project id: person 1 was charged, then the call failed with nothing to show."""
        api = FakeMagicHour(self.boxes, missing={"nosuchproject"})
        error, text = api.swap(self.photo, [{"person": 1, "head": "https://h/a.png"}, {"person": 2, "head": "nosuchproject"}])
        self.assertTrue(error, text)
        self.assertIn("Nothing was charged", text)
        self.assertEqual((api.charged, api.jobs), (0, {}))

    def test_a_failed_head_swap_keeps_the_heads_paid_for_before_it(self):
        """Person 2's head swap ended in error: person 1's paid head was lost with it."""
        from PIL import Image
        api = FakeMagicHour(self.boxes, failed_job="hs1")
        error, text = api.swap(self.photo, [{"person": 1, "head": "https://h/a.png"}, {"person": 2, "head": "https://h/b.png"},
                                            {"person": 3, "head": "https://h/c.png"}])
        self.assertFalse(error, text)
        done = json.loads(text)
        self.assertEqual(done["credits_charged"], 20)
        self.assertEqual([p["project_id"] for p in done["people"]], ["hs0"])
        self.assertEqual((done["failed"]["person"], done["failed"]["project_id"]), (2, "hs1"))
        self.assertIn("no face", done["failed"]["error"])
        self.assertEqual(done["not_tried"], ["person 3"])
        before, after = Image.open(self.photo).convert("RGB"), Image.open(done["file"]).convert("RGB")
        self.assertGreater(change_in(before, after, self.boxes[0]), 50)
        self.assertEqual(change_in(before, after, self.boxes[1]), 0)

    def test_a_person_given_twice_is_refused_before_any_charge(self):
        """The same person twice (or once by number, once by face path) was charged twice and one head was lost."""
        for second in ({"person": 1, "head": "https://h/b.png"}, {"face": "api-assets/acc/det1/0.png", "head": "https://h/b.png"}):
            api = FakeMagicHour(self.boxes)
            error, text = api.swap(self.photo, [{"person": 1, "head": "https://h/a.png"}, second])
            self.assertTrue(error, text)
            self.assertIn("Nothing was charged", text)
            self.assertEqual(api.charged, 0)

    def test_two_detected_faces_placed_on_one_face_are_refused_before_any_charge(self):
        """Two face crops placed on the same box made the person numbers wrong: the wrong person was charged for."""
        api = FakeMagicHour([self.boxes[0], self.boxes[0], self.boxes[1], self.boxes[2]])
        error, text = api.swap(self.photo, [{"person": 3, "head": "https://h/a.png"}])
        self.assertTrue(error, text)
        self.assertIn("Nothing was charged", text)
        self.assertEqual(api.charged, 0)

    def test_a_face_too_small_to_swap_is_refused_before_any_charge(self):
        """A 9x11 px face crashed after the person before it was charged."""
        boxes = [(60, 80, 90, 110), (300, 150, 9, 11)]
        group_photo((640, 384), boxes).save(self.dir / "small.png")
        api = FakeMagicHour(boxes)
        error, text = api.swap(self.dir / "small.png", [{"person": 1, "head": "https://h/a.png"}, {"person": 2, "head": "https://h/b.png"}])
        self.assertTrue(error)
        self.assertIn("Nothing was charged", text)
        self.assertEqual(api.charged, 0)

    def test_a_phone_photo_turned_by_its_exif_tag_stays_upright(self):
        """A phone JPEG with Orientation 6 was sent sideways to face detection and came back sideways."""
        from PIL import Image
        upright = [(60, 200, 90, 110), (230, 200, 90, 110)]
        phone = self.dir / "phone.jpg"
        exif = Image.Exif()
        exif[0x0112] = 6
        group_photo((384, 640), upright).transpose(Image.Transpose.ROTATE_90).save(phone, exif=exif.tobytes(), quality=95)
        api = FakeMagicHour(upright)
        error, text = api.swap(phone, [{"person": 1, "head": "https://h/a.png"}])
        self.assertFalse(error, text)
        self.assertEqual(Image.open(api.detected).size, (384, 640))
        self.assertEqual(Image.open(json.loads(text)["file"]).size, (384, 640))

    def test_a_see_through_photo_stays_see_through(self):
        """The see-through part of a PNG came back black."""
        from PIL import Image
        photo, alpha = Image.open(self.photo).convert("RGBA"), Image.new("L", (640, 384), 0)
        alpha.paste(255, (0, 0, 600, 384))   # the 40 px on the right are see-through
        photo.putalpha(alpha)
        photo.save(self.dir / "cut-out.png")
        error, text = FakeMagicHour(self.boxes).swap(self.dir / "cut-out.png", [{"person": 1, "head": "https://h/a.png"}])
        self.assertFalse(error, text)
        out = Image.open(json.loads(text)["file"])
        self.assertEqual(out.mode, "RGBA")
        self.assertEqual(out.getpixel((630, 200))[3], 0)
        self.assertEqual(out.getpixel((100, 130))[3], 255)

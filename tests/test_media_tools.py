"""The ffmpeg and Pillow file work in media_tools, on tiny files made in each test (skipped without ffmpeg).

probe has two paths: ffprobe when it is installed, else ffmpeg's own report (a server with ffmpeg only, as on Vercel).
A probe test runs on each path this machine has.
"""

import contextlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mcp_magichour import media_tools as m


def without_ffprobe():
    """probe as on a server with ffmpeg only: ffprobe is not found."""
    which = shutil.which
    return mock.patch.object(m.shutil, "which", lambda name, *a, **k: None if name == "ffprobe" else which(name, *a, **k))


def probe_paths() -> list[tuple[str, object]]:
    paths = [("ffmpeg report", without_ffprobe)]
    if shutil.which("ffprobe"):
        paths.insert(0, ("ffprobe", contextlib.nullcontext))
    return paths


@unittest.skipUnless(m.have_ffmpeg(), "needs ffmpeg")
class MediaTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def ff(self, *args):
        subprocess.check_call([m.ffmpeg_exe(), "-v", "error", "-y", *args])


class ReportTextTests(MediaTest):
    def test_a_title_that_is_not_utf8_does_not_stop_the_probe(self):
        sound = self.dir / "tag.m4a"
        self.ff("-f", "lavfi", "-i", "sine=d=0.5", "-metadata", b"title=Caf\xe9 del Mar", "-c:a", "aac", str(sound))
        with without_ffprobe():
            info = m.probe(sound)
            self.assertIsNotNone(m.loudness_db(sound))
        self.assertTrue(info["audio"])
        self.assertAlmostEqual(info["seconds"], 0.5, delta=0.1)


class PhoneVideoTests(MediaTest):
    """A phone video stored on its side: 128x72 pixels with a rotation of 90 degrees, shown 72x128 (portrait)."""

    def phone(self, rotation="90"):
        raw, phone = self.dir / "raw.mp4", self.dir / f"phone{rotation}.mp4"
        self.ff("-f", "lavfi", "-i", "testsrc=s=128x72:r=24:d=1", "-f", "lavfi", "-i", "sine=d=1", "-shortest", "-pix_fmt", "yuv420p", str(raw))
        try:
            self.ff("-display_rotation", rotation, "-i", str(raw), "-c", "copy", str(phone))
        except subprocess.CalledProcessError:
            self.skipTest("this ffmpeg cannot set a rotation")
        return phone

    def test_probe_gives_the_size_shown_not_the_size_stored(self):
        for rotation in ("90", "-90"):
            phone = self.phone(rotation)
            for name, path in probe_paths():
                with self.subTest(rotation=rotation, path=name), path():
                    info = m.probe(phone)
                    self.assertEqual((info["width"], info["height"]), (72, 128))

    def test_pad_and_fill_put_the_whole_portrait_picture_in_a_wide_frame(self):
        phone = self.phone()
        for name, path in probe_paths():
            with self.subTest(path=name), path():
                got = m.reframe(phone, "16:9", self.dir / "pad.mp4", how="pad", color="0x00FF00")
                self.assertEqual((got["width"], got["height"], got["way"]), (128, 72, "pad"))
                self.ff("-i", str(self.dir / "pad.mp4"), "-frames:v", "1", str(self.dir / "pad.png"))
                from PIL import Image
                self.assertEqual(Image.open(self.dir / "pad.png").size, (128, 72))
                r, g, b = Image.open(self.dir / "pad.png").convert("RGB").getpixel((4, 36))
                self.assertTrue(r < 40 and g > 200 and b < 40, (r, g, b))   # the bar, not a crop of the picture
                with mock.patch.object(m, "frame_filter", wraps=m.frame_filter) as fit:
                    m.join([phone], self.dir / "joined.mp4", size=(256, 144))
                self.assertEqual(fit.call_args.args[:4], (72, 128, 256, 144))
                self.assertEqual(m.frame_filter(*fit.call_args.args[:4])[1], "fill")

    def test_words_are_drawn_on_a_picture_of_the_size_shown(self):
        phone = self.phone()
        for name, path in probe_paths():
            with self.subTest(path=name), path(), mock.patch.object(m, "_caption_png", wraps=m._caption_png) as drawn:
                m.draw_words(phone, [{"text": "Hello"}], self.dir / "words.mp4", False)
                self.assertEqual(drawn.call_args.args[1], (72, 128))
                self.assertEqual((m.probe(self.dir / "words.mp4")["width"], m.probe(self.dir / "words.mp4")["height"]), (72, 128))


class LimitTests(MediaTest):
    def test_an_ffmpeg_run_past_the_time_limit_is_stopped_with_a_clear_error(self):
        slow = ["-re", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono", "-t", "3", "-f", "null", "-"]   # 3 s at real speed
        with mock.patch.object(m, "FFMPEG_TIMEOUT", 0.5):
            for capture in (False, True):
                with self.subTest(capture=capture), self.assertRaisesRegex(RuntimeError, "stopped"):
                    m._ffmpeg(slow, capture=capture)

    def test_a_mix_with_no_end_or_a_negative_length_is_refused_before_ffmpeg_runs(self):
        track = [{"file": self.dir / "a.wav"}]
        with mock.patch.object(m, "_ffmpeg") as run, mock.patch.object(m, "probe", return_value={"seconds": 1.0}):
            for seconds, fade_out, at in ((1e6, 0, 0), (-1, 0, 0), (5, -1, 0), (None, 0, 1e6)):
                with self.subTest(seconds=seconds, fade_out=fade_out, at=at), self.assertRaises(ValueError):
                    m.mix_audio([dict(track[0], at=at)], self.dir / "mix.wav", seconds, fade_out)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()

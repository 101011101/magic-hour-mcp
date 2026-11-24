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


class AlbumArtTests(MediaTest):
    def with_cover(self, suffix):
        tone, cover, song = self.dir / f"tone{suffix}", self.dir / "cover.png", self.dir / f"song{suffix}"
        self.ff("-f", "lavfi", "-i", "sine=d=1", str(tone))
        self.ff("-f", "lavfi", "-i", "testsrc=s=96x96", "-frames:v", "1", str(cover))
        self.ff("-i", str(tone), "-i", str(cover), "-map", "0", "-map", "1", "-c:a", "copy", "-c:v", "png",
                "-disposition:v", "attached_pic", str(song))
        return tone, song

    def test_album_art_is_not_a_picture_track(self):
        for suffix in (".mp3", ".m4a"):
            tone, song = self.with_cover(suffix)
            for name, path in probe_paths():
                with self.subTest(suffix=suffix, path=name), path():
                    info = m.probe(song)
                    self.assertEqual((info["width"], info["height"], info["audio"]), (0, 0, True))
                    joined = m.join([song, tone], self.dir / "joined.m4a")   # sound files are joined as sound
                    self.assertAlmostEqual(m.probe(joined)["seconds"], 2.0, delta=0.15)


class NoDurationTests(MediaTest):
    """A browser recording written as a stream: its header has no duration ("Duration: N/A")."""

    def recording(self):
        webm = self.dir / "rec.webm"
        with open(webm, "wb") as f:
            subprocess.run([m.ffmpeg_exe(), "-v", "error", "-f", "lavfi", "-i", "testsrc=s=160x90:r=24:d=2", "-f", "lavfi", "-i", "sine=d=2",
                            "-c:v", "libvpx", "-c:a", "libopus", "-shortest", "-f", "webm", "-"], stdout=f, check=True)
        if "Duration: N/A" not in m._ffmpeg(["-i", str(webm)], capture=True):
            self.skipTest("this ffmpeg wrote a duration")
        return webm

    def frame(self, video, at, name):
        from PIL import Image
        self.ff("-ss", str(at), "-i", str(video), "-frames:v", "1", str(self.dir / name))
        return Image.open(self.dir / name).convert("RGB")

    def test_the_length_is_read_from_the_file_itself(self):
        webm = self.recording()
        for name, path in probe_paths():
            with self.subTest(path=name), path():
                self.assertAlmostEqual(m.probe(webm)["seconds"], 2.0, delta=0.1)
                part = m.trim(webm, self.dir / "part.mp4", 0.5, 1.5)
                self.assertAlmostEqual(m.probe(part)["seconds"], 1.0, delta=0.1)

    def test_words_with_no_end_stay_to_the_end(self):
        webm = self.recording()
        with without_ffprobe():
            m.draw_words(webm, [{"text": "SALE", "place": "middle", "size": "large"}], self.dir / "words.mp4", False)
        drawn, plain = self.frame(self.dir / "words.mp4", 1.7, "a.png"), self.frame(webm, 1.7, "b.png")
        changed = sum(1 for p, q in zip(drawn.getdata(), plain.getdata()) if sum(abs(x - y) for x, y in zip(p, q)) > 60)
        self.assertGreater(changed, 100)

    def test_a_picture_still_has_no_length(self):
        from PIL import Image
        Image.new("RGB", (40, 30), "red").save(self.dir / "p.png")
        for name, path in probe_paths():
            with self.subTest(path=name), path():
                self.assertEqual(m.probe(self.dir / "p.png")["seconds"], 0)


class LongSoundTests(MediaTest):
    """A clip whose sound runs on past its picture: 2 s of picture, 3 s of sound."""

    def clip(self):
        clip = self.dir / "long-sound.mp4"
        self.ff("-f", "lavfi", "-i", "testsrc=s=160x90:r=24:d=2", "-f", "lavfi", "-i", "sine=d=3", "-pix_fmt", "yuv420p", str(clip))
        return clip

    def frames(self, video):
        report = m._ffmpeg(["-i", str(video), "-map", "0:v:0", "-f", "null", "-"], capture=True)
        return int(m.re.findall(r"frame=\s*(\d+)", report)[-1])

    def test_the_last_frame_is_the_pictures_last_frame(self):
        clip = self.clip()
        last, first = m.last_frame(clip, self.dir / "last.jpg"), m.first_frame(clip, self.dir / "first.jpg")
        self.assertTrue(last.stat().st_size)
        self.assertNotEqual(last.read_bytes(), first.read_bytes())

    def test_a_clip_fitted_to_its_slot_keeps_that_much_picture(self):
        clip = self.clip()
        for how in ("speed", "head"):
            with self.subTest(how=how):
                fitted = m.fit_length(clip, 1.5, how, self.dir / f"fit-{how}.mp4")
                self.assertAlmostEqual(self.frames(fitted) / 24, 1.5, delta=0.05)


class JoinSoundTests(MediaTest):
    def test_a_clip_whose_sound_stops_early_does_not_pull_the_next_clips_sound_early(self):
        short, full = self.dir / "short.mp4", self.dir / "full.mp4"
        self.ff("-f", "lavfi", "-i", "testsrc=s=160x90:r=24:d=2", "-f", "lavfi", "-i", "sine=f=440:d=1", "-pix_fmt", "yuv420p", str(short))
        self.ff("-f", "lavfi", "-i", "testsrc=s=160x90:r=24:d=2", "-f", "lavfi", "-i", "sine=f=440:d=2", "-pix_fmt", "yuv420p", str(full))
        film = m.join([short, full], self.dir / "film.mp4")
        heard = m.speech_spans(film)
        self.assertEqual(len(heard), 2, heard)
        self.assertAlmostEqual(heard[0][1], 1.0, delta=0.1)
        self.assertAlmostEqual(heard[1][0], 2.0, delta=0.1)   # the second clip's sound starts with its picture


class OddSizeTests(MediaTest):
    def test_a_video_of_an_odd_size_is_trimmed_fitted_held_and_worded(self):
        odd = self.dir / "odd.webm"   # a browser recording can have an odd size; H.264 4:2:0 cannot
        self.ff("-f", "lavfi", "-i", "testsrc=s=161x91:r=24:d=1", "-f", "lavfi", "-i", "sine=d=1", "-c:v", "libvpx", "-c:a", "libopus", str(odd))
        made = {"trim": lambda: m.trim(odd, self.dir / "t.mp4", 0.2, 0.8),
                "fit_length": lambda: m.fit_length(odd, 0.5, "head", self.dir / "f.mp4"),
                "hold_end": lambda: m.hold_end(odd, 0.5, self.dir / "h.mp4"),
                "draw_words": lambda: m.draw_words(odd, [{"text": "Hello"}], self.dir / "w.mp4", False)}
        for name, make in made.items():
            with self.subTest(name):
                info = m.probe(make())
                self.assertEqual((info["width"], info["height"]), (160, 90))


class SmallFrameTests(MediaTest):
    def test_a_small_frame_can_be_filled_with_a_blur(self):
        tall = self.dir / "tall.mp4"
        self.ff("-f", "lavfi", "-i", "testsrc=s=72x128:r=24:d=1", "-pix_fmt", "yuv420p", str(tall))
        made = m.reframe(tall, "16:9", self.dir / "wide.mp4", how="fill")
        self.assertEqual((made["width"], made["height"], made["way"]), (128, 72, "fill"))
        joined = m.join([tall], self.dir / "joined.mp4", size=(128, 72))
        self.assertEqual((m.probe(joined)["width"], m.probe(joined)["height"]), (128, 72))


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

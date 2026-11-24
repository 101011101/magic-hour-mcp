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


class PhonePhotoTests(MediaTest):
    """A phone photo stored on its side, with an EXIF orientation that says to turn it a quarter turn to the right."""

    def photo(self):
        from PIL import Image
        stored = Image.new("RGB", (160, 80), "red")
        stored.paste((0, 0, 255), (80, 0, 160, 80))   # stored: red left, blue right; shown: red top, blue bottom
        exif = Image.Exif()
        exif[0x0112] = 6
        stored.save(self.dir / "photo.jpg", exif=exif, quality=95)
        return self.dir / "photo.jpg"

    def assertColour(self, pixel, colour):
        self.assertLess(sum(abs(a - b) for a, b in zip(pixel, colour)), 90, (pixel, colour))

    def test_a_photo_is_fitted_the_way_up_it_is_shown(self):
        from PIL import Image
        out = m.fit_picture(self.photo(), "white", (200, 200), self.dir / "fitted.png")
        frame = Image.open(out).convert("RGB")   # shown 80x160, centred: x 60-140, y 20-180
        self.assertColour(frame.getpixel((100, 40)), (255, 0, 0))
        self.assertColour(frame.getpixel((100, 160)), (0, 0, 255))
        self.assertColour(frame.getpixel((30, 100)), (255, 255, 255))

    def test_words_on_a_photo_keep_the_way_up_it_is_shown(self):
        from PIL import Image
        out = m.draw_words(self.photo(), [{"text": "Hi", "place": "middle"}], self.dir / "words.png", True)
        frame = Image.open(out).convert("RGB")
        self.assertEqual(frame.size, (80, 160))
        self.assertColour(frame.getpixel((40, 10)), (255, 0, 0))


class LongWordTests(unittest.TestCase):
    def test_one_word_wider_than_the_frame_is_made_smaller_to_fit(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            out = m._caption_png("www.magichour.ai/pricing?plan=annual", (360, 640), Path(folder) / "c.png", share=0.075)
            image = Image.open(out).convert("RGBA")
        letters = [x for x in range(image.width) for y in range(0, image.height, 2)
                   if image.getpixel((x, y)) == (255, 255, 255, 255)]
        self.assertTrue(letters)
        self.assertGreaterEqual(min(letters), 360 * 0.05)
        self.assertLessEqual(max(letters), 360 * 0.95)

    def test_words_that_fit_keep_their_size(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(m, "load_font", wraps=m.load_font) as load:
            m._caption_png("Hello there", (360, 640), Path(folder) / "c.png", share=0.075)
        self.assertEqual(load.call_args.args[0], 27)


class ManyCaptionsTests(MediaTest):
    """The film the join makes: 3 s, 160x90, its picture starting a moment after 0 s. A still picture (bars), so a
    frame taken a moment off is the same."""

    def film(self):
        clips = []
        for i in range(2):
            clips.append(self.dir / f"clip{i}.mp4")
            self.ff("-f", "lavfi", "-i", "smptebars=s=160x90:r=24:d=1.5", "-f", "lavfi", "-i", "sine=d=1.5", "-pix_fmt", "yuv420p", str(clips[-1]))
        return m.join(clips, self.dir / "film.mp4")

    def changed(self, a, b, rows):
        from PIL import Image
        shots = []
        for video, name in ((a, "a.png"), (b, "b.png")):
            self.ff("-ss", f"{self.at:.3f}", "-i", str(video), "-frames:v", "1", str(self.dir / name))
            shots.append(Image.open(self.dir / name).convert("RGB"))
        return sum(1 for y in range(*rows) for x in range(160)
                   if sum(abs(p - q) for p, q in zip(shots[0].getpixel((x, y)), shots[1].getpixel((x, y)))) > 60)

    def frames(self, video):
        report = m._ffmpeg(["-i", str(video), "-map", "0:v:0", "-f", "null", "-"], capture=True)
        return int(m.re.findall(r"frame=\s*(\d+)", report)[-1])

    def test_all_captions_are_one_input_to_ffmpeg(self):
        film = self.film()
        timed = [{"text": f"Line {i}", "start": i * 0.25, "end": i * 0.25 + 0.2} for i in range(12)]
        with mock.patch.object(m, "_ffmpeg", wraps=m._ffmpeg) as run:
            m.draw_captions(film, timed, self.dir / "out.mp4")
        drawn = [c.args[0] for c in run.call_args_list if not c.kwargs.get("capture")]
        self.assertEqual(drawn[-1].count("-i"), 2)   # the film and one stream of caption pictures
        self.assertEqual(self.frames(self.dir / "out.mp4"), self.frames(film))
        self.assertEqual([p.name for p in self.dir.iterdir() if p.name.startswith("out")], ["out.mp4"])

    def test_each_caption_is_shown_in_its_own_time(self):
        film = self.film()
        timed = [{"text": "One", "start": 0.5, "end": 1.0}, {"text": "Two", "place": "top", "start": 0.8, "end": 2.0},
                 {"text": "Three", "start": 2.2, "end": 2.6}]
        out = m.draw_captions(film, timed, self.dir / "out.mp4")
        top, bottom = (5, 25), (62, 82)
        for at, shown in ((0.05, ""), (0.6, "b"), (0.9, "tb"), (1.5, "t"), (2.1, ""), (2.4, "b"), (2.9, "")):
            self.at = at
            with self.subTest(at=at):
                self.assertEqual(self.changed(out, film, top) > 20, "t" in shown)
                self.assertEqual(self.changed(out, film, bottom) > 20, "b" in shown)
        self.assertTrue(m.probe(out)["audio"])

    def test_words_with_no_end_are_on_from_the_first_frame_to_the_last(self):
        film = self.film()
        out = m.draw_words(film, [{"text": "SALE", "place": "middle", "size": "large"}], self.dir / "words.mp4", False)
        for self.at in (0.0, 1.5, 2.95):
            with self.subTest(at=self.at):
                self.assertGreater(self.changed(out, film, (30, 60)), 20)


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

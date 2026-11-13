"""Frame shape, trims and picture cards, on real files made by ffmpeg (skipped without ffmpeg)."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from mcp_magichour import media_tools as m


@unittest.skipUnless(m.have_ffmpeg(), "needs ffmpeg")
class FrameTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def clip(self, name, size, seconds):
        out = self.dir / name
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=s={size}:d={seconds}", str(out)])
        return out

    def test_a_small_shape_miss_is_cropped_and_a_large_one_is_filled(self):
        self.assertEqual(m.frame_filter(480, 720, 480, 854)[1], "crop")   # 16% lost
        self.assertEqual(m.frame_filter(854, 480, 480, 854)[1], "fill")   # 68% would be lost

    def test_the_join_cuts_each_clip_to_its_planned_length_and_fits_the_frame(self):
        files = [self.clip("a.mp4", "480x854", 3), self.clip("b.mp4", "480x720", 2.4), self.clip("c.mp4", "854x480", 2)]
        film = m.join(files, self.dir / "film.mp4", False, [2, 2, None], (480, 854))
        info = m.probe(film)
        self.assertAlmostEqual(info["seconds"], 6.0, delta=0.15)
        self.assertEqual((info["width"], info["height"]), (480, 854))

    def test_reframe_returns_the_new_size(self):
        got = m.reframe(self.clip("w.mp4", "854x480", 1), "9:16", self.dir / "r.mp4")
        self.assertEqual((got["width"], got["height"], got["way"]), (480, 854, "fill"))
        self.assertEqual((m.probe(self.dir / "r.mp4")["width"], m.probe(self.dir / "r.mp4")["height"]), (480, 854))

    def test_a_photo_card_fills_the_frame_with_a_blur_not_white(self):
        from PIL import Image

        Image.new("RGB", (640, 640), (200, 40, 40)).save(self.dir / "p.png")
        card = m.fit_picture(self.dir / "p.png", None, (480, 854), self.dir / "card.png", ["Coffee first"])
        corner = Image.open(card).convert("RGB").getpixel((5, 5))
        self.assertNotEqual(corner, (255, 255, 255))
        self.assertGreater(corner[0], corner[2])   # the photo's own colour, blurred and darkened

    def test_reframe_works_on_a_picture(self):
        from PIL import Image

        Image.new("RGB", (640, 640), (40, 120, 200)).save(self.dir / "p.png")
        got = m.reframe(self.dir / "p.png", "9:16", self.dir / "r.png")
        self.assertEqual(got["way"], "fill")
        self.assertEqual(Image.open(self.dir / "r.png").size, (got["width"], got["height"]))

    def test_two_lines_at_one_place_and_time_become_one_band(self):
        got = m.stack_lines([{"text": "Maya Chen", "place": "bottom", "start": 1, "end": 7},
                             {"text": "Community Gardener", "place": "bottom", "start": 1, "end": 7},
                             {"text": "Rooftop Jazz", "place": "top"}])
        self.assertEqual([g["text"] for g in got], ["Maya Chen\nCommunity Gardener", "Rooftop Jazz"])

    def test_a_long_title_at_the_top_stays_inside_the_frame(self):
        from PIL import Image

        png = m._caption_png("Biltmore House\nAsheville, North Carolina\nDecember 24, 1895\nHistorical reconstruction",
                             (854, 480), self.dir / "t.png", at=0.15, share=0.075)
        box = Image.open(png).getbbox()
        self.assertGreater(box[1], 0)
        self.assertLess(box[3], 480)


@unittest.skipUnless(m.have_ffmpeg(), "needs ffmpeg")
class TicketTests(unittest.TestCase):
    """2026-11-12 happy r1 tickets: trim (E26b, J49c), sound joins and mixes (F31b, F32a, F32b), pad (J51b),
    focus (E25b), corner words (E29c), left-aligned words (D23b)."""

    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def clip(self, name, size, seconds):
        out = self.dir / name
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=s={size}:d={seconds}",
                               "-f", "lavfi", "-i", f"sine=f=440:d={seconds}", "-shortest", str(out)])
        return out

    def tone(self, name, seconds, freq=440):
        out = self.dir / name
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f={freq}:d={seconds}", str(out)])
        return out

    def test_trim_keeps_the_asked_part_with_its_sound(self):
        out = m.trim(self.clip("v.mp4", "320x240", 8), self.dir / "t.mp4", 0, 5)
        info = m.probe(out)
        self.assertAlmostEqual(info["seconds"], 5.0, delta=0.1)
        self.assertTrue(info["audio"])
        with self.assertRaises(ValueError):
            m.trim(self.dir / "v.mp4", self.dir / "x.mp4", 6, 2)

    def test_join_of_sound_files_gives_one_sound_file(self):
        out = m.join([self.tone("a.wav", 1.5), self.tone("b.wav", 2, 660)], self.dir / "d.m4a")
        info = m.probe(out)
        self.assertAlmostEqual(info["seconds"], 3.5, delta=0.15)
        self.assertEqual(info["width"], 0)

    def test_mix_lays_a_voice_over_music_from_its_start(self):
        out = m.mix_audio([{"file": self.tone("music.wav", 20), "volume": 0.25}, {"file": self.tone("voice.wav", 10, 660), "at": 3}],
                          self.dir / "intro.m4a", 20, fade_out=2)
        self.assertAlmostEqual(m.probe(out)["seconds"], 20, delta=0.2)

    def mean_db(self, path, start, seconds):
        err = subprocess.run(["ffmpeg", "-hide_banner", "-ss", str(start), "-t", str(seconds), "-i", str(path), "-af", "volumedetect",
                              "-f", "null", "-"], capture_output=True, text=True).stderr
        return float(err.split("mean_volume:")[1].split("dB")[0])

    def silent_film(self, seconds=8, sound="anullsrc=r=48000:cl=stereo"):
        film = self.dir / "film.mp4"
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=s=320x240:d={seconds}", "-f", "lavfi",
                               "-i", sound, "-t", str(seconds), "-c:v", "libx264", "-c:a", "aac", str(film)])
        return film

    def test_music_alone_is_the_top_layer_and_the_film_is_at_the_target_loudness(self):
        """A1, 2026-11-12: music with no voice-over was mixed at 0.16, so the ad sounded silent (-32 LUFS)."""
        done = m.add_sound(self.silent_film(), self.dir / "out.mp4", music=self.tone("music.wav", 8), layers=self.dir / "l")
        self.assertAlmostEqual(done["lufs"], m.TARGET_LUFS, delta=1)
        music = self.dir / "l" / "music.wav"
        self.assertAlmostEqual(self.mean_db(music, 2, 1), self.mean_db(music, 5, 1), delta=0.5)   # never lowered

    def test_with_swell_the_music_is_lowered_only_where_someone_speaks(self):
        voice = self.tone("voice.wav", 2, 660)
        done = m.add_sound(self.silent_film(), self.dir / "out.mp4", voice, [{"start": 0, "end": 2, "at": 3}],
                           self.tone("music.wav", 8), layers=self.dir / "l", music_swell=True)
        music = self.dir / "l" / "music.wav"
        self.assertAlmostEqual(self.mean_db(music, 1.5, 1) - self.mean_db(music, 3.5, 1), m.SWELL_DB, delta=1.5)
        self.assertAlmostEqual(self.mean_db(music, 1.5, 1), self.mean_db(music, 5.4, 0.5), delta=0.5)   # back up after (before the end fade)
        self.assertEqual(done["speech"], [(3, 5)])

    def test_a_spoken_line_in_the_film_is_never_lowered_and_the_music_sits_under_it(self):
        film = self.silent_film(sound="sine=f=300:d=8")
        m.add_sound(film, self.dir / "out.mp4", music=self.tone("music.wav", 8), spoken=[(4, 6)], layers=self.dir / "l")
        effects, music = self.dir / "l" / "effects.wav", self.dir / "l" / "music.wav"
        self.assertAlmostEqual(self.mean_db(effects, 4.5, 1) - self.mean_db(effects, 1.5, 1), m.EFFECTS_UNDER_DB, delta=1.5)
        self.assertAlmostEqual(self.mean_db(music, 1.5, 1), self.mean_db(music, 4.5, 1), delta=0.5)   # one steady bed
        self.assertAlmostEqual(self.mean_db(effects, 4.5, 1) - self.mean_db(music, 4.5, 1), m.MUSIC_UNDER_SPEECH_DB, delta=1.5)

    def test_music_first_is_never_lowered(self):
        m.add_sound(self.silent_film(), self.dir / "out.mp4", self.tone("voice.wav", 2, 660), [{"start": 0, "end": 2, "at": 3}],
                    self.tone("music.wav", 8), music_first=True, layers=self.dir / "l")
        music = self.dir / "l" / "music.wav"
        self.assertAlmostEqual(self.mean_db(music, 1.5, 1), self.mean_db(music, 3.5, 1), delta=0.5)

    def test_a_loud_music_track_is_lowered_more_to_stay_under_the_voice(self):
        voice = self.dir / "voice.wav"
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=660:d=2", "-af", "volume=0.3", str(voice)])
        m.add_sound(self.silent_film(), self.dir / "out.mp4", voice, [{"start": 0, "end": 2, "at": 3}], self.tone("music.wav", 8),
                    layers=self.dir / "l")
        speech, music = self.dir / "l" / "speech.wav", self.dir / "l" / "music.wav"
        self.assertAlmostEqual(self.mean_db(speech, 3.5, 1) - self.mean_db(music, 3.5, 1), m.MUSIC_UNDER_SPEECH_DB, delta=1.5)

    def test_by_default_the_music_is_one_quiet_level_under_the_voice_for_the_whole_film(self):
        """F32a, 2026-11-13: the music went from gone (under the voice) to loud (between lines). The user wants a steady bed."""
        m.add_sound(self.silent_film(), self.dir / "out.mp4", self.tone("voice.wav", 2, 660), [{"start": 0, "end": 2, "at": 3}],
                    self.tone("music.wav", 8), layers=self.dir / "l")
        speech, music = self.dir / "l" / "speech.wav", self.dir / "l" / "music.wav"
        self.assertAlmostEqual(self.mean_db(music, 1.5, 1), self.mean_db(music, 3.5, 1), delta=0.5)
        self.assertAlmostEqual(self.mean_db(speech, 3.5, 1) - self.mean_db(music, 3.5, 1), m.MUSIC_UNDER_SPEECH_DB, delta=1.5)

    def test_short_gaps_between_sentences_stay_lowered(self):
        self.assertEqual(m.merge_spans([(1, 2), (2.5, 3), (5, 6)]), [(1, 3), (5, 6)])

    def test_a_voice_over_longer_than_its_beats_is_fitted_and_no_word_is_cut(self):
        """I46a, 2026-11-13: part 2 (3.9 s) started at 4.5 s in an 8.1 s film; its last words were cut."""
        parts = [{"start": 0.0, "end": 3.3, "at": 0.5}, {"start": 3.5, "end": 7.4, "at": 4.5}]
        fit = m.fit_parts(parts, 8.3)   # moved 0.4 s earlier: fits, no speed-up, no hold
        self.assertEqual((fit["tempo"], fit["hold"]), (1.0, 0.0))
        self.assertEqual([p["at"] for p in fit["parts"]], [0.1, 4.1])
        self.assertFalse(m.fit_parts(parts, 12)["moved"])   # a film with room is left alone
        fit = m.fit_parts(parts, 8.0)   # read about 8% faster, still no hold
        self.assertTrue(1.0 < fit["tempo"] <= m.VOICE_TEMPO_MAX and fit["hold"] == 0.0, fit)
        fit = m.fit_parts(parts, 6.0)   # too long even at the top speed: the last frame is held
        last = fit["parts"][-1]
        self.assertEqual(fit["tempo"], m.VOICE_TEMPO_MAX)
        self.assertAlmostEqual(last["at"] + 3.9 / fit["tempo"] + m.HOLD_TAIL, 6.0 + fit["hold"], delta=0.02)
        self.assertGreaterEqual(fit["parts"][1]["at"], 0.1 + 3.3 / fit["tempo"] + m.VOICE_GAP - 0.001)   # no overlap

    def test_a_sentence_with_numbers_is_cut_at_its_real_pause_not_a_breath(self):
        """I46a, 2026-11-13: the cut fell on a breath at 2.8 s; the first sentence ends at the pause 4.18-4.78 s."""
        spans = [(0.0, 1.2), (1.54, 4.18), (4.78, 6.99), (7.4, 8.62)]
        fine = [(0.0, 1.2), (1.54, 2.75), (2.85, 4.18), (4.78, 6.99), (7.4, 8.62)]
        got = m.align_parts(spans, ["The F-35A Lightning II is powered by a single engine.",
                                    "It is the conventional takeoff and landing version, built for normal runways."], fine)
        self.assertAlmostEqual(got[0][1], 4.48, delta=0.01)

    def test_the_held_film_is_longer_by_the_hold_and_a_faster_voice_is_mixed_in(self):
        held = m.hold_end(self.silent_film(4), 1.5, self.dir / "held.mp4")
        self.assertAlmostEqual(m.probe_seconds(held), 5.5, delta=0.15)
        voice = self.tone("voice.wav", 4, freq=300)
        done = m.add_sound(held, self.dir / "out.mp4", voice, [{"start": 0, "end": 4, "at": 0.5, "tempo": 1.15}], layers=self.dir / "l")
        self.assertAlmostEqual(done["speech"][0][1], 0.5 + 4 / 1.15, delta=0.05)
        self.assertLess(self.mean_db(self.dir / "l" / "speech.wav", 4.3, 1), -60)   # the faster voice has ended by 4.0 s

    def test_pad_puts_the_whole_picture_on_coloured_bars(self):
        from PIL import Image

        got = m.reframe(self.clip("w.mp4", "854x480", 1), "9:16", self.dir / "p.mp4", "pad", color="0x1B2A4A")
        self.assertEqual(got["way"], "pad")
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", str(self.dir / "p.mp4"), "-frames:v", "1", str(self.dir / "f.png")])
        r, g, b = Image.open(self.dir / "f.png").convert("RGB").getpixel((240, 20))
        self.assertTrue(abs(r - 0x1B) < 12 and abs(g - 0x2A) < 12 and abs(b - 0x4A) < 12, (r, g, b))

    def test_focus_moves_the_crop(self):
        self.assertIn("(iw-480)*0.000", m.frame_filter(854, 480, 480, 854, "crop", 0.0)[0])
        self.assertIn("(iw-480)*1.000", m.frame_filter(854, 480, 480, 854, "crop", 1.0)[0])

    def test_a_watermark_sits_in_its_corner_and_a_lower_third_on_the_left(self):
        from PIL import Image

        style = m.word_style({"text": "@flightschool", "place": "bottom_right", "size": "small", "style": "shadow", "opacity": 0.6})
        png = m._caption_png("@flightschool", (854, 480), self.dir / "w.png", **style)
        box = Image.open(png).getchannel("A").getbbox()
        self.assertGreater(box[0], 854 * 0.6)
        self.assertGreater(box[1], 480 * 0.8)
        self.assertLessEqual(max(Image.open(png).getchannel("A").getdata()), 160)   # see-through
        left = m._caption_png("Maya Chen\nFounder", (854, 480), self.dir / "l.png", **m.word_style({"place": "bottom", "align": "left"}))
        self.assertLess(Image.open(left).getchannel("A").getbbox()[0], 854 * 0.1)

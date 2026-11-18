"""Checklist grader: deliverable selection, score arithmetic and measurement (no network, no claude calls)."""

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("checklist_grade", Path(__file__).resolve().parent.parent / "scripts" / "checklist_grade.py")
g = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(g)


def _have(binary):
    return Path(binary).exists() or shutil.which(binary) is not None


class DeliverableTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.dir / "assets").mkdir()
        self.events = []

    def file(self, name):
        (self.dir / "assets" / name).write_bytes(b"x" * 1000)
        return f"assets/{name}"

    def call(self, tool, output, files=(), args=None):
        self.events.append({"type": "call", "tool": tool, "args": args or {}, "output": json.dumps(output),
                            "files": [self.file(f) for f in files]})

    def say(self, text):
        self.events.append({"type": "say", "text": text})

    def select(self):
        (self.dir / "calls.jsonl").write_text("\n".join(json.dumps(e) for e in self.events))
        return g.select_deliverables(self.dir)

    def test_the_file_named_in_the_last_reply_wins_over_drafts_sources_and_voice_previews(self):
        self.call("voices_list", {"voices": []}, [f"v{i:03d}-voices_list.mp3" for i in range(100)])
        self.call("trim_media", {"download_url": "http://h/films/src.mp4", "video_file_path": "api-assets/a/src.mp4"}, ["01-trim_media.mp4"])
        self.call("wait_for_audio_project", {"id": "mus1", "downloads": [{"url": "https://videos.magichour.ai/mus1/output.wav?sig=1"}]},
                  ["02-wait_for_audio_project.wav"], {"id": "mus1"})
        self.call("add_sound_to_video", {"download_url": "http://h/films/final.mp4"}, ["03-add_sound_to_video.mp4"])
        self.call("get_last_frame", {"download_url": "http://h/films/frame.png"}, ["04-get_last_frame.png"])
        self.say("Done: http://h/films/final.mp4. Enjoy!")
        sel = self.select()
        self.assertEqual([f["name"] for f in sel["final"]], ["03-add_sound_to_video.mp4"])

    def test_several_files_named_in_the_reply_are_all_delivered(self):
        for i in (1, 2, 3):
            self.call("wait_for_image_project", {"id": f"p{i}"}, [f"0{i}-wait.png"], {"id": f"p{i}"})
        for i in (4, 5, 6):
            self.call("add_words_to_media", {"download_url": f"http://h/films/w{i}.png"}, [f"0{i}-words.png"])
        self.say("Square: http://h/films/w4.png\nTall: http://h/films/w5.png\nWide: http://h/films/w6.png")
        self.assertEqual([f["name"] for f in self.select()["final"]], ["04-words.png", "05-words.png", "06-words.png"])

    def test_a_signed_magic_hour_link_matches_its_project(self):
        self.call("wait_for_image_project", {"id": "abc", "downloads": [{"url": "https://videos.magichour.ai/abc/output.png?X-Goog=1"}]},
                  ["01-wait.png"], {"id": "abc"})
        self.call("wait_for_image_project", {"id": "def"}, ["02-wait.png"], {"id": "def"})
        self.say("Here: https://videos.magichour.ai/abc/output.png?X-Goog=2")
        self.assertEqual([f["name"] for f in self.select()["final"]], ["01-wait.png"])

    def test_a_follow_up_replaces_the_file_it_reworks_and_keeps_the_others(self):
        self.call("wait_for_image_project", {"id": "fox"}, ["01-fox.png"], {"id": "fox"})
        self.call("wait_for_image_project", {"id": "lighthouse"}, ["02-lighthouse.png"], {"id": "lighthouse"})
        self.say("1. https://videos.magichour.ai/fox/output.png 2. https://videos.magichour.ai/lighthouse/output.png")
        self.events.append({"type": "user", "text": "Make the first one square"})
        self.call("reframe_media", {"error": "failed"}, [], {"media": "fox"})
        self.call("wait_for_image_project", {"id": "fox2"}, ["03-fox-square.png"], {"id": "fox2"})
        self.say("Square: https://videos.magichour.ai/fox2/output.png")
        sel = self.select()
        self.assertEqual(sorted(f["name"] for f in sel["final"]), ["02-lighthouse.png", "03-fox-square.png"])
        self.assertEqual([f["name"] for f in sel["reference"]], ["01-fox.png"])

    def test_without_a_matching_link_the_last_file_of_the_turn_is_taken(self):
        self.call("wait_for_video_project", {"id": "a"}, ["01-a.mp4"], {"id": "a"})
        self.call("add_words_to_media", {"download_url": "http://h/films/b.mp4"}, ["02-b.mp4"])
        self.say("Your video is ready.")
        sel = self.select()
        self.assertEqual([f["name"] for f in sel["final"]], ["02-b.mp4"])
        self.assertIn("fallback", sel["turns"][0]["method"])

    def test_no_file_means_no_deliverable(self):
        self.say("I can't make that.")
        self.assertEqual(self.select()["final"], [])


class ScoreTests(unittest.TestCase):
    def test_cannot_tell_and_superseded_checks_are_left_out_of_both_sides(self):
        checks = [{"id": "C1"}, {"id": "C2"}, {"id": "C3"}, {"id": "C4"}, {"id": "C5", "superseded_by": 2}]
        results = [{"id": "C1", "verdict": "done"}, {"id": "C2", "verdict": "done"}, {"id": "C3", "verdict": "not_done"},
                   {"id": "C4", "verdict": "cannot_tell"}, {"id": "C5", "verdict": "not_done"}]
        s = g.score(results, checks)
        self.assertEqual((s["done"], s["not_done"], s["cannot_tell"], s["superseded"], s["judged"]), (2, 1, 1, 1, 3))
        self.assertAlmostEqual(s["score"], 0.667, places=3)

    def test_nothing_judged_gives_no_score(self):
        self.assertIsNone(g.score([{"id": "C1", "verdict": "cannot_tell"}], [{"id": "C1"}])["score"])

    def test_nearest_ratio(self):
        self.assertEqual(g.nearest_ratio(480, 854)["nearest"], "9:16")
        self.assertEqual(g.nearest_ratio(512, 640)["nearest"], "4:5")


@unittest.skipUnless(_have(g.FFMPEG) and _have(g.FFPROBE), "needs ffmpeg")
class MeasureTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_a_tiny_clip_with_a_tone_then_silence(self):
        out = self.dir / "clip.mp4"
        subprocess.check_call([g.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=320x180:d=3:r=24",
                               "-f", "lavfi", "-i", "sine=f=440:d=1.5", "-af", "apad", "-t", "3",
                               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)])
        m = g.measure(str(out))
        self.assertEqual((m["kind"], m["width"], m["height"]), ("video", 320, 180))
        self.assertEqual(m["aspect"]["nearest"], "16:9")
        self.assertAlmostEqual(m["duration_s"], 3.0, delta=0.15)
        self.assertTrue(m["has_audio_track"] and m["audio"]["audible"])
        self.assertTrue(any(1.3 < s < 1.8 and e > 2.8 for s, e in m["audio"]["silence_spans_s"]), m["audio"])
        self.assertEqual(m["black_spans_s"], [])

    def test_a_silent_clip_has_no_audio_track(self):
        out = self.dir / "mute.mp4"
        subprocess.check_call([g.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=180x320:d=2",
                               "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)])
        m = g.measure(str(out))
        self.assertFalse(m["has_audio_track"])
        self.assertEqual(m["orientation"], "portrait")
        self.assertTrue(m["black_spans_s"])

    def test_an_image(self):
        from PIL import Image
        p = self.dir / "a.png"
        Image.new("RGB", (640, 640), "white").save(p)
        m = g.measure(str(p))
        self.assertEqual((m["kind"], m["orientation"], m["aspect"]["exact"]), ("image", "square", "1:1"))


if __name__ == "__main__":
    unittest.main()

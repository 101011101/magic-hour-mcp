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

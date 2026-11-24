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


if __name__ == "__main__":
    unittest.main()

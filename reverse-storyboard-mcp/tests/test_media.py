"""Real ffmpeg integration tests for local media preprocessing.

Run explicitly with ``python -m unittest discover -s tests -p test_media.py``
from the project root after installing Pillow, numpy and imageio-ffmpeg.
Fixtures and subprocess stdout/stderr use regular files, never PIPE. No test
requires a network connection, ffprobe, or an installed system ffmpeg.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reverse_storyboard import media


class PrepareVideoTests(unittest.TestCase):
    """Synthesize actual encoded video and verify end-to-end behavior."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ffmpeg = media._find_ffmpeg()
        cls.temporary = tempfile.TemporaryDirectory(prefix="test-storyboard-")
        cls.root = Path(cls.temporary.name)
        cls.tricolor = cls.root / "red-blue-red.mp4"
        cls.short = cls.root / "short.mp4"
        cls._encode(cls.tricolor, [("red", 2), ("blue", 2), ("red", 2)])
        cls._encode(cls.short, [("red", 0.08)])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    @classmethod
    def _encode(cls, destination: Path, segments: list[tuple[str, float]]) -> None:
        args = [cls.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error"]
        for color, duration in segments:
            args += ["-f", "lavfi", "-i", f"color=c={color}:s=160x90:r=25:d={duration}"]
        if len(segments) > 1:
            inputs = "".join(f"[{i}:v]" for i in range(len(segments)))
            args += ["-filter_complex", f"{inputs}concat=n={len(segments)}:v=1:a=0[out]", "-map", "[out]"]
        args += ["-an", "-c:v", "mpeg4", "-q:v", "2", "-pix_fmt", "yuv420p", "-y", str(destination)]
        with (cls.root / "encode.stdout").open("wb") as stdout, (cls.root / "encode.stderr").open("wb") as stderr:
            subprocess.run(args, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                           shell=False, check=True, timeout=60)

    def _prepare(self, source: Path | None = None, **kwargs):
        with mock.patch.dict("os.environ", {"STORYBOARD_FFMPEG": self.ffmpeg}):
            return media.prepare_video(source or self.tricolor, self.root / self.id().split(".")[-1], **kwargs)

    def assertCoverage(self, result) -> None:
        shots = result["shots"]
        self.assertEqual(shots[0]["start"], 0)
        self.assertEqual(shots[-1]["end"], result["duration"])
        self.assertAlmostEqual(sum(shot["duration"] for shot in shots), result["duration"], places=9)
        for index, shot in enumerate(shots):
            self.assertEqual(shot["index"], index)
            self.assertGreater(shot["duration"], 0)
            self.assertAlmostEqual(shot["duration"], shot["end"] - shot["start"])
            if index:
                self.assertEqual(shots[index - 1]["end"], shot["start"])
            self.assertEqual(len(shot["frames"]), 3)
            for frame in shot["frames"]:
                self.assertGreaterEqual(frame["timestamp"], shot["start"])
                self.assertLess(frame["timestamp"], shot["end"])
                with Image.open(frame["path"]) as image:
                    self.assertEqual(image.format, "JPEG")
                    self.assertEqual(image.width, 1024)

    def test_red_blue_red_three_shots(self) -> None:
        result = self._prepare()
        self.assertCoverage(result)
        self.assertAlmostEqual(result["duration"], 6, delta=0.05)
        self.assertEqual(len(result["shots"]), 3)
        self.assertEqual([s["boundary_type"] for s in result["shots"]], ["start", "hard_cut", "hard_cut"])
        for shot, expected_start, channel in zip(result["shots"], (0, 2, 4), (0, 2, 0)):
            self.assertAlmostEqual(shot["start"], expected_start, delta=0.5)
            for frame in shot["frames"]:
                with Image.open(frame["path"]) as image:
                    rgb = image.convert("RGB").getpixel((image.width // 2, image.height // 2))
                self.assertGreater(rgb[channel], 200)
                self.assertLess(rgb[2 if channel == 0 else 0], 40)
        self.assertEqual(result["source"]["sha256"], hashlib.sha256(self.tricolor.read_bytes()).hexdigest())
        self.assertEqual(result["source"]["size_bytes"], self.tricolor.stat().st_size)
        self.assertTrue(result["limitations"])

    def test_shorter_than_sampling_interval(self) -> None:
        result = self._prepare(self.short)
        self.assertCoverage(result)
        self.assertEqual(len(result["shots"]), 1)
        self.assertLess(result["duration"], 0.5)

    def test_artificial_boundaries_keep_all_segments(self) -> None:
        result = self._prepare(max_shot_seconds=1)
        self.assertCoverage(result)
        self.assertTrue(any(shot["boundary_type"] == "artificial" for shot in result["shots"]))
        self.assertTrue(all(shot["duration"] <= 1 + 1e-9 for shot in result["shots"]))

    def test_minimum_duration_suppresses_nearby_cut(self) -> None:
        result = self._prepare(min_shot_seconds=3)
        self.assertCoverage(result)
        self.assertEqual(len(result["shots"]), 1)

    def test_shot_budget_fails_instead_of_truncating(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_shots=2"):
            self._prepare(max_shots=2)
        with self.assertRaisesRegex(ValueError, "max_shots=3"):
            self._prepare(max_shots=3, max_shot_seconds=1)

    def test_duration_limit_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "duration"):
            self._prepare(max_duration=5)

    def test_byte_limit_fails_before_ffmpeg(self) -> None:
        # Lower the guard for this test instead of allocating a 1 GiB fixture.
        with mock.patch.object(media, "_MAX_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "1 GiB"):
                self._prepare()

    def test_extension_rejected(self) -> None:
        text = self.root / "unsupported.txt"
        text.write_text("not video", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "extension"):
            self._prepare(text)

    def test_invalid_parameters(self) -> None:
        for kwargs in ({"sample_fps": 0}, {"sample_fps": float("nan")}, {"threshold": 2},
                       {"max_shots": 0}, {"max_shots": True}, {"max_duration": -1},
                       {"min_shot_seconds": 4, "max_shot_seconds": 3}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self._prepare(**kwargs)

    def test_sampling_budget_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "analysis frames"):
            self._prepare(sample_fps=10000)


if __name__ == "__main__":
    unittest.main()

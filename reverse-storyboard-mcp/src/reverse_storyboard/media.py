"""Local-only video sampling, hard-cut detection, and storyboard JPEG extraction.

Requires Python 3.10+, Pillow, numpy, and imageio-ffmpeg. No network or
ffprobe is used. All child-process standard streams are regular files, which
also works in Windows environments where anonymous subprocess pipes fail.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any
import uuid

import numpy as np
from PIL import Image

_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mpeg", ".mpg", ".mts", ".m2ts", ".wmv"}
_MAX_BYTES = 1024 ** 3
_MAX_DURATION = 300.0
_MAX_SAMPLE_FRAMES = 18_000
_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_PTS = re.compile(r"\bpts_time:\s*(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)", re.I)


def _find_ffmpeg() -> str:
    """Resolve the explicit override, PATH, then imageio-ffmpeg's executable."""
    override = os.environ.get("STORYBOARD_FFMPEG")
    if override:
        candidate = shutil.which(override) or str(Path(override).expanduser())
        if not Path(candidate).is_file():
            raise FileNotFoundError("STORYBOARD_FFMPEG does not name an executable file")
        return candidate
    candidate = shutil.which("ffmpeg")
    if candidate:
        return candidate
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(ffmpeg: str, args: list[str], scratch: Path, *, check: bool = True) -> str:
    """Run without a shell or pipes; retain only bounded diagnostic text."""
    with (scratch / "stdout.log").open("wb") as stdout, (scratch / "stderr.log").open("wb") as stderr:
        try:
            result = subprocess.run(
                [ffmpeg, "-nostdin", "-hide_banner", *args],
                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                shell=False, timeout=180,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("ffmpeg exceeded the 180-second per-command budget") from exc
    # Read the tail without copying arbitrarily large diagnostics into memory.
    with (scratch / "stderr.log").open("rb") as stream:
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - 131072))
        text = stream.read().decode("utf-8", errors="replace")
    if check and result.returncode:
        raise RuntimeError(f"ffmpeg failed (exit {result.returncode}): {text[-4000:]}")
    return text


def _positive(name: str, value: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite positive number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite positive number") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return number


def _histogram(frame: np.ndarray) -> np.ndarray:
    return np.concatenate([
        np.bincount((frame[:, :, channel] // 16).ravel(), minlength=16)
        for channel in range(3)
    ]).astype(np.float32) / (frame.shape[0] * frame.shape[1] * 3)


def _boundaries(raw: Path, duration: float, fps: float, threshold: float,
                minimum: float, maximum: float, budget: int) -> list[tuple[float, str]]:
    """Stream tiny RGB frames; filter cuts, then evenly split long intervals."""
    frame_bytes = 160 * 90 * 3
    if raw.stat().st_size == 0 or raw.stat().st_size % frame_bytes:
        raise ValueError("Video produced no complete RGB sample frames")
    cuts: list[tuple[float, str]] = [(0.0, "start")]
    previous = previous_hist = None
    with raw.open("rb") as stream:
        index = 0
        while data := stream.read(frame_bytes):
            current = np.frombuffer(data, dtype=np.uint8).reshape(90, 160, 3)
            histogram = _histogram(current)
            timestamp = index / fps
            if previous is not None:
                pixel = float(np.abs(current.astype(np.int16) - previous.astype(np.int16)).mean()) / 255
                hist = float(np.abs(histogram - previous_hist).sum()) / 2
                if (max(pixel, hist) >= threshold
                        and timestamp - cuts[-1][0] >= minimum
                        and duration - timestamp >= minimum):
                    cuts.append((timestamp, "hard_cut"))
            previous, previous_hist = current, histogram
            index += 1
    result: list[tuple[float, str]] = []
    for i, (start, kind) in enumerate(cuts):
        end = cuts[i + 1][0] if i + 1 < len(cuts) else duration
        pieces = max(1, math.ceil((end - start) / maximum))
        if len(result) + pieces > budget:
            raise ValueError(f"Shot count exceeds max_shots={budget}; increase the budget or max_shot_seconds")
        for piece in range(pieces):
            result.append((start + (end - start) * piece / pieces,
                           kind if piece == 0 else "artificial"))
    return result


def prepare_video(video_path: Path, output_dir: Path, *, sample_fps: float = 2.0,
                  threshold: float = 0.28, min_shot_seconds: float = 0.5,
                  max_shot_seconds: float = 20.0, max_duration: float = 300.0,
                  max_shots: int = 80) -> dict[str, Any]:
    """Prepare JSON-serializable shot metadata and three 1024-wide JPEGs per shot.

    Shots use half-open [start, end) seconds and continuously cover the probed
    duration. ``boundary_type`` describes the shot's incoming boundary: start,
    hard_cut, or artificial. Hard-cut precision is approximately 1/sample_fps;
    fades and camera motion may fool the pixel/histogram heuristic. A single
    source frame can supply multiple positions in an extremely short clip.

    Accepts common local video extensions, at most 1 GiB and 300 seconds (or a
    smaller max_duration). At most 18,000 analysis frames are permitted. Limits
    fail explicitly; no prefix of the video is silently returned. The sampling
    pass is one ffmpeg process; extraction uses at most three processes per
    shot plus two fallback attempts for each missing target, each with a
    180-second timeout. Temporary raw frames/logs are always removed. Successful
    JPEGs live in a unique run subdirectory inside output_dir.

    Raises ValueError for invalid input/limits, FileNotFoundError for a missing
    file or explicit ffmpeg override, and RuntimeError for decoding failures.
    """
    fps = _positive("sample_fps", sample_fps)
    threshold = _positive("threshold", threshold)
    minimum = _positive("min_shot_seconds", min_shot_seconds)
    maximum = _positive("max_shot_seconds", max_shot_seconds)
    allowed_duration = min(_positive("max_duration", max_duration), _MAX_DURATION)
    if threshold > 1 or maximum < minimum:
        raise ValueError("threshold must be <= 1 and max_shot_seconds must be >= min_shot_seconds")
    if isinstance(max_shots, bool) or not isinstance(max_shots, int) or max_shots < 1:
        raise ValueError("max_shots must be a positive integer")
    source = Path(video_path).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in _EXTENSIONS:
        raise ValueError("Input must be a local video file with a supported extension")
    before = source.stat()
    if before.st_size == 0 or before.st_size > _MAX_BYTES:
        raise ValueError("Input must be nonempty and no larger than 1 GiB")
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    ffmpeg = _find_ffmpeg()
    shots: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="storyboard-media-") as temporary:
        scratch = Path(temporary)
        # ffmpeg deliberately exits nonzero for this metadata-only invocation.
        metadata = _run(ffmpeg, ["-i", str(source)], scratch, check=False)
        duration_match = _DURATION.search(metadata)
        video_line = next((line for line in metadata.splitlines() if "Video:" in line), None)
        if not duration_match or video_line is None:
            raise ValueError("Cannot determine a finite duration and video stream from ffmpeg metadata")
        hours, minutes, seconds = map(float, duration_match.groups())
        duration = hours * 3600 + minutes * 60 + seconds
        if not math.isfinite(duration) or duration <= 0 or duration > allowed_duration:
            raise ValueError(f"Video duration {duration:g}s exceeds the allowed range (0, {allowed_duration:g}]s")
        if math.ceil(duration * fps) + 1 > _MAX_SAMPLE_FRAMES:
            raise ValueError(f"sample_fps produces more than {_MAX_SAMPLE_FRAMES} analysis frames")
        fps_match = re.search(r"(\d+(?:\.\d+)?)\s+fps\b", video_line)
        native_fps = float(fps_match.group(1)) if fps_match else None
        raw = scratch / "samples.rgb"
        _run(ffmpeg, ["-v", "error", "-i", str(source), "-map", "0:v:0", "-an", "-sn",
                      "-vf", f"fps={fps:.12g},scale=160:90", "-frames:v", str(_MAX_SAMPLE_FRAMES),
                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-y", str(raw)], scratch)
        # fps may round a sub-sample-period clip down to zero frames.
        if raw.stat().st_size == 0:
            _run(ffmpeg, ["-v", "error", "-i", str(source), "-map", "0:v:0", "-an", "-sn",
                          "-vf", "scale=160:90", "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-y", str(raw)], scratch)
        starts = _boundaries(raw, duration, fps, threshold, minimum, maximum, max_shots)
        output = Path(output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        run_dir = output / f"storyboard-{uuid.uuid4().hex}"
        run_dir.mkdir()
        for index, (start, kind) in enumerate(starts):
            end = starts[index + 1][0] if index + 1 < len(starts) else duration
            length = end - start
            margin = min(length / 4, 1 / native_fps if native_fps else 0.04)
            targets = (start, start + length / 2, end - margin)
            frames: list[dict[str, Any]] = []
            for position, target in enumerate(targets):
                destination = run_dir / f"shot-{index + 1:03d}-{position + 1}.jpg"
                found = False
                for seek in dict.fromkeys((target, max(start, target - margin), start)):
                    staging = scratch / "frame.jpg"
                    staging.unlink(missing_ok=True)
                    log = _run(ffmpeg, ["-loglevel", "info", "-ss", f"{seek:.12f}", "-i", str(source),
                                        "-map", "0:v:0", "-an", "-sn", "-vf", "scale=1024:-2,showinfo",
                                        "-frames:v", "1", "-fps_mode", "vfr", "-q:v", "2", "-y", str(staging)], scratch, check=False)
                    pts = _PTS.search(log)
                    actual = seek + float(pts.group(1)) if pts else None
                    if staging.is_file() and actual is not None and start - 1e-7 <= actual < end:
                        with Image.open(staging) as image:
                            image.convert("RGB").save(destination, "JPEG", quality=90)
                        frames.append({"path": str(destination), "timestamp": max(start, actual)})
                        found = True
                        break
                if not found:
                    if not frames:
                        raise RuntimeError(f"No decodable frame in shot {index + 1} [{start}, {end})")
                    shutil.copyfile(frames[0]["path"], destination)
                    frames.append({"path": str(destination), "timestamp": frames[0]["timestamp"]})
            shots.append({"id": f"shot_{index + 1:03d}", "index": index, "start": start,
                          "end": end, "duration": length, "boundary_type": kind, "frames": frames})
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError("Source video changed during preprocessing; discard this run")
    return {
        "duration": duration, "shots": shots,
        "source": {"path": str(source), "sha256": digest.hexdigest(), "size_bytes": before.st_size,
                   "extension": source.suffix.lower(), "video_stream": video_line.strip(),
                   "fps": native_fps, "duration_basis": "ffmpeg container Duration (centisecond precision)"},
        "sample_fps": fps,
        "limitations": [
            f"Hard-cut estimates have approximately {1 / fps:g}s sampling precision; fades and motion may cause missed or false cuts.",
            "Duration is ffmpeg's container duration; audio or edit lists may extend beyond the decodable video stream.",
            "Reported frame times are decoded showinfo PTS plus the input seek offset; unusual timestamp layouts may fail extraction.",
            "Very short clips may reuse one decoded frame for multiple storyboard positions; extracted timestamps always precede shot end.",
            "Long shots are evenly divided and their inserted boundaries are marked artificial; these divisions can be shorter than min_shot_seconds.",
        ],
    }

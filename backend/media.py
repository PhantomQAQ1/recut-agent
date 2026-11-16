"""上传素材的落盘、校验与关键帧抽取。

抽帧用 imageio-ffmpeg 自带的 ffmpeg 二进制，宿主机无需安装 ffmpeg。
所有临时文件在请求结束时清理。
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from config import settings
from errors import UpstreamError, UploadRejected

IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
}
ALLOWED_TYPES = {**IMAGE_TYPES, **VIDEO_TYPES}

CHUNK_SIZE = 1024 * 1024
FFMPEG_TIMEOUT = 180
_DURATION_PATTERN = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")


@dataclass
class SavedUpload:
    path: Path
    content_type: str
    is_video: bool
    size: int

    def cleanup(self) -> None:
        shutil.rmtree(self.path.parent, ignore_errors=True)


async def save_upload(upload: UploadFile) -> SavedUpload:
    """把上传流写入临时文件，同时校验类型与体积（避免一次性读入内存）。"""
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    suffix = ALLOWED_TYPES.get(content_type)
    if suffix is None:
        raise UploadRejected(
            f"不支持的素材类型：{content_type or '未知'}；请上传 MP4/MOV/WEBM 视频或 PNG/JPG/WEBP 图片"
        )

    limit = settings.max_upload_mb * 1024 * 1024
    directory = Path(tempfile.mkdtemp(prefix="recut-upload-"))
    path = directory / f"input{suffix}"
    size = 0
    try:
        with path.open("wb") as handle:
            while chunk := await upload.read(CHUNK_SIZE):
                size += len(chunk)
                if size > limit:
                    raise UploadRejected(f"素材超过 {settings.max_upload_mb}MB 上限")
                handle.write(chunk)
        if size == 0:
            raise UploadRejected("上传的素材是空文件")
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    finally:
        await upload.close()

    return SavedUpload(path=path, content_type=content_type, is_video=content_type in VIDEO_TYPES, size=size)


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
    except ImportError as exc:  # pragma: no cover - 依赖缺失时给出可执行提示
        raise UpstreamError("缺少 imageio-ffmpeg，请先执行 pip install -r requirements.txt") from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe_duration(exe: str, path: Path) -> float | None:
    """从 ffmpeg 的 stderr 里解析时长；解析不到返回 None。"""
    try:
        completed = subprocess.run(
            [exe, "-hide_banner", "-i", str(path)],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = _DURATION_PATTERN.search(completed.stderr or "")
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def extract_keyframes(upload: SavedUpload) -> list[bytes]:
    """图片直接返回原图；视频按时长均匀抽取至多 max_frames 帧。"""
    if not upload.is_video:
        return [upload.path.read_bytes()]

    exe = ffmpeg_exe()
    duration = probe_duration(exe, upload.path)
    if duration and duration > 0:
        interval = max(settings.frame_min_interval, duration / settings.max_frames)
    else:
        interval = settings.frame_min_interval * 2
    interval = max(0.5, min(interval, 30.0))

    frames_dir = Path(tempfile.mkdtemp(prefix="recut-frames-"))
    try:
        command = [
            exe,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", str(upload.path),
            # 均匀采样 + 限制最大宽度，既覆盖全片又控制 token 成本。
            "-vf", f"fps=1/{interval:.2f},scale='min(768,iw)':-2",
            "-frames:v", str(settings.max_frames),
            str(frames_dir / "frame-%02d.jpg"),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=FFMPEG_TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            raise UpstreamError("视频抽帧超时，请上传更短的素材") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
            tail = detail[-1] if detail else "未知错误"
            raise UpstreamError(f"视频解码失败：{tail}") from exc
        except OSError as exc:
            raise UpstreamError(f"无法调用 ffmpeg：{exc}") from exc

        frames = [path.read_bytes() for path in sorted(frames_dir.glob("frame-*.jpg"))]
        if not frames:
            raise UpstreamError("未能从该视频中抽取到画面，请确认文件可正常播放")
        return frames
    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)


def describe_frames(count: int, duration: float | None) -> str:
    """给视觉模型的时间轴提示，帮助它按顺序还原镜头。"""
    if not duration:
        return f"共 {count} 帧，按时间顺序排列。"
    step = math.ceil(duration / max(count, 1))
    return f"素材总长约 {duration:.0f} 秒，共 {count} 帧，按时间顺序排列，约每 {step} 秒一帧。"

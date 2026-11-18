"""Standalone stdio MCP server for reverse-storyboard projects."""
from __future__ import annotations

import asyncio
import inspect
import logging
import os
from pathlib import Path
import stat
import uuid
from datetime import datetime, timezone
from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from . import exports, media, registry, vision

logging.basicConfig(level=logging.INFO, stream=__import__("sys").stderr)
logger = logging.getLogger(__name__)
mcp = FastMCP("reverse-storyboard")

_PREPARE_SEMAPHORE = asyncio.Semaphore(1)
_LOCKS: dict[str, asyncio.Lock] = {}
_LOCKS_GUARD = asyncio.Lock()
_FORMATS = {"json", "markdown", "csv", "shot-plan"}


def _data_dir() -> Path:
    configured = os.environ.get("STORYBOARD_DATA_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".reverse-storyboard"


def _allowed_roots() -> list[Path]:
    raw = os.environ.get("STORYBOARD_MEDIA_ROOTS", "")
    roots = [Path(item).expanduser().resolve() for item in raw.split(os.pathsep) if item.strip()]
    if not roots:
        raise ValueError("STORYBOARD_MEDIA_ROOTS must be set to one or more media directories")
    return roots


def _validate_video_path(video_path: str) -> Path:
    roots = _allowed_roots()
    try:
        resolved = Path(video_path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("video_path must resolve to an existing regular file") from exc
    inside = any(resolved.is_relative_to(root) for root in roots)
    if not inside:
        raise ValueError("video_path must resolve inside a configured STORYBOARD_MEDIA_ROOTS directory")
    try:
        mode = resolved.stat().st_mode
    except OSError as exc:
        raise ValueError("video_path must resolve to an existing regular file") from exc
    if not stat.S_ISREG(mode):
        raise ValueError("video_path must be a regular file")
    return resolved


async def _project_lock(project_id: str) -> asyncio.Lock:
    async with _LOCKS_GUARD:
        return _LOCKS.setdefault(project_id, asyncio.Lock())


def _summary(project: dict[str, Any]) -> dict[str, Any]:
    shots = project.get("shots", [])
    counts: dict[str, int] = {}
    for shot in shots:
        status = shot.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {"shot_count": len(shots), "status_counts": counts,
            "duration": project.get("duration"), "title": project.get("title")}


def _shot_overview(shot: dict[str, Any]) -> dict[str, Any]:
    return {key: shot.get(key) for key in ("id", "index", "start", "end", "duration", "boundary_type", "status")}


async def _report_progress(ctx: Context | None, progress: int, total: int, message: str) -> None:
    if ctx is None:
        return
    reporter = getattr(ctx, "report_progress", None)
    if reporter is None:
        return
    try:
        result = reporter(progress, total, message)
        if inspect.isawaitable(result):
            await result
    except (TypeError, AttributeError):
        # Older MCP SDKs expose a different progress signature.
        return


@mcp.tool()
async def health() -> dict[str, Any]:
    """Report service readiness and whether vision credentials are configured."""
    config = vision.configuration()
    raw_roots = os.environ.get("STORYBOARD_MEDIA_ROOTS", "")
    roots = [str(Path(item).expanduser().resolve()) for item in raw_roots.split(os.pathsep) if item.strip()]
    return {"status": "ok", "vision_configured": bool(config.get("configured")),
            "model": config.get("model"), "prompt_version": config.get("prompt_version"),
            "media_roots": roots, "data_dir": str(_data_dir())}


@mcp.tool()
async def prepare_video(video_path: str, sample_fps: float = 2.0,
                        threshold: float = 0.28, max_shot_seconds: float = 20.0,
                        ctx: Context = cast(Context, None)) -> dict[str, Any]:
    """Prepare a local video and create a durable storyboard project."""
    source = _validate_video_path(video_path)
    project_id = uuid.uuid4().hex
    data_dir = _data_dir()
    async with _PREPARE_SEMAPHORE:
        prepared = await asyncio.to_thread(
            media.prepare_video, source, data_dir / project_id,
            sample_fps=sample_fps, threshold=threshold, max_shot_seconds=max_shot_seconds)
    project_shots = []
    for shot in prepared.get("shots", []):
        project_shots.append({**shot, "status": "prepared", "observation": None,
                              "prompts": None, "error": None})
    limitations = list(prepared.get("limitations", []))
    limitations.append("没有进行音频分析；对白、音乐和音效均未分析。")
    project = {"schema_version": 1, "id": project_id, "title": source.name,
               "source": prepared.get("source", {"path": str(source)}),
               "duration": prepared.get("duration"), "sample_fps": prepared.get("sample_fps"),
               "shots": project_shots, "limitations": limitations}
    registry.save(data_dir, project)
    await _report_progress(ctx, 1, 1, "视频预处理完成")
    return {"project_id": project_id, "summary": _summary(project),
            "shots": [_shot_overview(shot) for shot in project_shots],
            "limitations": limitations}


@mcp.tool()
async def analyze_shots(project_id: str, shot_ids: list[str] | None = None,
                        ctx: Context = cast(Context, None)) -> dict[str, Any]:
    """Analyze up to five pending shots, or up to ten explicitly selected shots."""
    if not vision.configuration()["configured"]:
        raise ValueError("Configure STORYBOARD_VISION_BASE_URL, STORYBOARD_VISION_MODEL and STORYBOARD_VISION_API_KEY before analysis")
    if shot_ids is not None:
        if not isinstance(shot_ids, list) or len(shot_ids) > 10:
            raise ValueError("shot_ids must contain at most 10 shot IDs")
        if len(set(shot_ids)) != len(shot_ids):
            raise ValueError("shot_ids must not contain duplicates")
    lock = await _project_lock(project_id)
    async with lock:
        project = registry.load(_data_dir(), project_id)
        all_shots = project.get("shots", [])
        if shot_ids is None:
            selected = [shot for shot in all_shots if shot.get("status") in {"prepared", "error"}][:5]
        else:
            by_id = {shot.get("id"): shot for shot in all_shots}
            missing = [shot_id for shot_id in shot_ids if shot_id not in by_id]
            if missing:
                raise ValueError("Unknown shot ID(s): " + ", ".join(missing))
            selected = [by_id[shot_id] for shot_id in shot_ids]
            unavailable = [shot["id"] for shot in selected if shot.get("status") not in {"prepared", "error"}]
            if unavailable:
                raise ValueError("Only prepared or failed shots can be analyzed: " + ", ".join(unavailable))
        outcomes = []
        for index, shot in enumerate(selected, start=1):
            await _report_progress(ctx, index - 1, len(selected), f"分析镜头 {shot['id']}")
            try:
                observation = await vision.analyze(shot)
                if hasattr(observation, "model_dump"):
                    observation = observation.model_dump()
                if not isinstance(observation, dict):
                    raise TypeError("invalid vision result")
                shot["observation"] = observation
                shot["prompts"] = exports.build_prompts(observation, shot.get("duration", 0))
                shot["status"] = "analyzed"
                config = vision.configuration()
                shot["analysis"] = {"model": config.get("model"),
                                    "prompt_version": config.get("prompt_version"),
                                    "completed_at": datetime.now(timezone.utc).isoformat()}
                shot["error"] = None
                outcomes.append({"shot_id": shot["id"], "status": "analyzed"})
            except Exception as exc:  # Store only a safe classification, never exception text or credentials.
                logger.warning("Shot analysis failed (%s)", type(exc).__name__)
                shot["status"] = "error"
                shot["observation"] = None
                shot["prompts"] = None
                shot["error"] = "分析失败（{}）".format(type(exc).__name__)
                outcomes.append({"shot_id": shot["id"], "status": "error", "error": shot["error"]})
            registry.save(_data_dir(), project)
            await _report_progress(ctx, index, len(selected), f"镜头 {shot['id']} 处理完成")
        return {"project_id": project_id, "summary": _summary(project), "results": outcomes}


@mcp.tool()
async def get_project(project_id: str, limit: int = 20, offset: int = 0) -> dict[str, Any]:
    """Read a project page; frame bytes are never included."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("limit must be an integer from 1 to 20")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a nonnegative integer")
    lock = await _project_lock(project_id)
    async with lock:
        project = registry.load(_data_dir(), project_id)
        shots = project.get("shots", [])
        return {"project_id": project_id, "schema_version": project.get("schema_version"),
                "title": project.get("title"), "source": project.get("source"),
                "duration": project.get("duration"), "summary": _summary(project),
                "limitations": project.get("limitations", []), "offset": offset, "limit": limit,
                "total_shots": len(shots), "shots": shots[offset:offset + limit]}


@mcp.tool()
async def export_storyboard(project_id: str, format: str = "markdown") -> dict[str, Any]:
    """Export a project in a supported format under its own exports directory."""
    if format not in _FORMATS:
        raise ValueError("format must be json, markdown, csv, or shot-plan")
    lock = await _project_lock(project_id)
    async with lock:
        project = registry.load(_data_dir(), project_id)
        destination = _data_dir() / project_id / "exports"
        output_path = exports.export_project(project, destination, format)
        return {"project_id": project_id, "format": format, "path": str(output_path)}


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

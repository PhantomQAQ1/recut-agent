"""把 reverse-storyboard-mcp 的能力接进现有逆向分镜接口。

新包本身是一个 stdio MCP 服务，但它同时提供可复用的库接口
（`reverse_storyboard.media / vision / exports`）。后端采用**库方式**调用：

- 不需要安装 `mcp` SDK，也不需要起子进程、跑 stdio 协议
- 需要 Pillow / numpy / httpx；缺任何一个时 `availability()` 返回不可用，
  调用方回退到原有的单次多帧分析（vision.analyze_frames）

开关：环境变量 `REVERSE_ENGINE=mcp` 才走这条新链路，默认保持原行为。
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from starlette.concurrency import run_in_threadpool

from errors import UpstreamError
from schemas import Shot, normalize_shot

# 新包源码目录；若已 pip 安装则可省去 sys.path 注入
_PACKAGE_SRC = Path(__file__).resolve().parent.parent / "reverse-storyboard-mcp" / "src"
_REQUIRED_MODULES = ("PIL", "numpy", "httpx")

# MCP 的景别是自由短词，现有契约是「中文 + 缩写」
_SCALE_MAP = {
    "大远景": "大远景 ELS",
    "远景": "远景 LS",
    "全景": "全景 WS",
    "中景": "中景 MS",
    "中近景": "中景 MS",
    "近景": "近景 CU",
    "特写": "特写 ECU",
    "大特写": "特写 ECU",
}

# 运镜同样需要收敛到前端下拉里的值
_MOVE_KEYWORDS = (
    (("环绕", "orbit", "旋转"), "环绕跟拍 Orbit"),
    (("推", "push", "zoom in", "前移"), "急速推镜 Crash Zoom"),
    (("拉", "pull", "zoom out", "后移"), "缓慢拉远 Pull out"),
    (("摇", "pan"), "横向摇镜 Pan"),
    (("移", "truck", "track", "平移"), "缓慢横移 Truck"),
    (("跟", "follow", "手持", "handheld"), "手持跟拍 Handheld"),
    (("升", "降", "crane", "boom"), "升降机位 Crane"),
    (("升格", "低机位", "low angle"), "低机位升格 Low angle"),
    (("固定", "static", "locked"), "固定机位 Static"),
)

_LENS_BY_SCALE = {
    "大远景 ELS": "24mm",
    "远景 LS": "28mm",
    "全景 WS": "35mm",
    "中景 MS": "50mm",
    "近景 CU": "85mm",
    "特写 ECU": "85mm",
}


def _ensure_importable() -> bool:
    """让 `reverse_storyboard` 可被导入；返回是否可用。"""
    if importlib.util.find_spec("reverse_storyboard") is not None:
        return True
    if _PACKAGE_SRC.is_dir():
        entry = str(_PACKAGE_SRC)
        if entry not in sys.path:
            sys.path.insert(0, entry)
        return importlib.util.find_spec("reverse_storyboard") is not None
    return False


def availability() -> tuple[bool, list[str]]:
    """返回 (是否可用, 缺失项)。缺失项只用于展示，不含任何密钥。"""
    missing = [name for name in _REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    if not _ensure_importable():
        missing.append("reverse_storyboard")
    return (not missing, missing)


def enabled() -> bool:
    return os.getenv("REVERSE_ENGINE", "builtin").strip().lower() == "mcp"


def _configure_vision() -> bool:
    """把项目已有的视觉模型配置转成新包要求的 STORYBOARD_VISION_*。

    已经显式设置过的环境变量优先，不覆盖部署者自己的选择。
    """
    from config import settings

    mapping = {
        "STORYBOARD_VISION_BASE_URL": settings.vision_base_url,
        "STORYBOARD_VISION_API_KEY": settings.vision_api_key or "",
        "STORYBOARD_VISION_MODEL": settings.vision_model,
    }
    for key, value in mapping.items():
        if value and not os.getenv(key):
            os.environ[key] = value
    return bool(
        os.getenv("STORYBOARD_VISION_BASE_URL")
        and os.getenv("STORYBOARD_VISION_MODEL")
        and os.getenv("STORYBOARD_VISION_API_KEY")
    )


def _scale(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text in _SCALE_MAP:
        return _SCALE_MAP[text]
    for key, mapped in _SCALE_MAP.items():
        if key in text:
            return mapped
    return None


def _move(value: object) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    for keywords, mapped in _MOVE_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return mapped
    return None


def _seconds(start: float, end: float) -> str:
    span = max(3, min(6, round(float(end) - float(start))))
    return f"{span:02d}s"


def _join(*parts: object) -> str:
    return "，".join(str(part).strip() for part in parts if str(part or "").strip())


def _prompt_pair(prompts: dict[str, Any], key: str) -> tuple[str, str]:
    value = prompts.get(key)
    if isinstance(value, dict):
        return str(value.get("zh") or ""), str(value.get("en") or "")
    text = str(value or "")
    return text, ""


def _to_shot(shot: dict[str, Any], prompts: dict[str, Any], index: int) -> Shot:
    """把一张 MCP 卡片映射成现有 Shot 契约。"""
    observation = shot.get("observation") if isinstance(shot.get("observation"), dict) else {}
    video_zh, video_en = _prompt_pair(prompts, "video")
    frame_zh, frame_en = _prompt_pair(prompts, "first_frame")
    prompt = video_zh or frame_zh
    runway = video_en or frame_en or prompt

    scale = _scale(observation.get("shot_size"))
    raw = {
        "duration": _seconds(shot.get("start", 0), shot.get("end", 4)),
        "scale": scale or observation.get("shot_size") or "中景 MS",
        "move": _move(observation.get("camera_move")) or "固定机位 Static",
        "title": (observation.get("subject") or observation.get("scene") or f"镜头 {index}")[:60],
        "description": _join(
            observation.get("scene"),
            observation.get("subject"),
            observation.get("action"),
            observation.get("expression"),
            observation.get("lighting"),
            observation.get("composition"),
        ),
        "prompt": prompt,
        "runwayPrompt": runway,
    }
    data = normalize_shot(raw, index - 1)
    # normalize_shot 的景别推断不如直接映射准，显式覆盖
    if scale:
        data["scale"] = scale
        data["lens"] = _LENS_BY_SCALE.get(scale, data["lens"])
    data["move"] = raw["move"]
    return Shot(**data)


def _apply_anchors(shot: Shot, anchors: list[str]) -> Shot:
    """把角色锚点补到提示词开头（与既有逆向路径的语义一致）。"""
    tokens = [item.strip() for item in anchors if item.strip()]
    if not tokens:
        return shot
    prefix = "、".join(tokens)
    if shot.prompt.startswith(prefix):
        return shot
    return shot.model_copy(
        update={"prompt": f"{prefix}，{shot.prompt}".strip("，"), "runwayPrompt": shot.runwayPrompt}
    )


async def analyze_video(
    path: Path,
    *,
    anchors: list[str] | None = None,
    max_shots: int | None = None,
    sample_fps: float = 2.0,
) -> list[Shot]:
    """视频 → 分镜卡片。切镜在本地完成，每个镜头一次视觉模型调用。"""
    ok, missing = availability()
    if not ok:
        raise UpstreamError(f"逆向 Agent 不可用，缺少依赖：{', '.join(missing)}")
    if not _configure_vision():
        raise UpstreamError("逆向 Agent 需要视觉模型配置（VISION_* 或 STORYBOARD_VISION_*）")

    from reverse_storyboard import exports, media, vision  # noqa: PLC0415 - 延迟导入以便回退

    budget = max_shots or int(os.getenv("REVERSE_MAX_SHOTS", "8"))
    workdir = Path(tempfile.mkdtemp(prefix="recut-reverse-"))
    try:
        prepared = await run_in_threadpool(
            media.prepare_video,
            path,
            workdir,
            sample_fps=sample_fps,
            max_shot_seconds=20.0,
        )
        shots: list[Shot] = []
        failures = 0
        for index, shot in enumerate(prepared.get("shots", [])[:budget], start=1):
            try:
                observation = await vision.analyze(shot)
            except Exception:  # noqa: BLE001 - 单镜失败不应毁掉整次解析
                failures += 1
                continue
            shot = {**shot, "observation": observation, "status": "analyzed"}
            prompts = exports.build_prompts(observation, shot.get("duration", 0))
            shots.append(_apply_anchors(_to_shot(shot, prompts, index), anchors or []))

        if not shots:
            raise UpstreamError(f"逆向 Agent 未产出可用镜头（失败 {failures} 个）")
        return shots
    except UpstreamError:
        raise
    except (ValueError, RuntimeError, OSError) as exc:
        raise UpstreamError(f"逆向 Agent 处理失败：{exc}") from exc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

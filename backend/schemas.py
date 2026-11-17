"""前后端共享的数据契约。

字段名、取值必须与 frontend/src/App.vue 的 Shot 类型逐一对齐，否则前端渲染会错位。
模型输出一律先经过 normalize_shot 收敛，再进入 Shot 校验——不能直接信任模型。
"""

from __future__ import annotations

import re
from typing import Literal, get_args

from pydantic import BaseModel, Field, ValidationError

# 调色板 id 沿用 Tailwind 风格的字符串（历史数据不变），
# 但前端渲染不再依赖 Tailwind 类名——.scene-art 原来用的是写死的渐变，
# 类名从未生效。现在由 frontend/src/lib/palettes.ts 把 id 映射成具体色值。
Palette = Literal[
    "from-amber-950 via-orange-950 to-slate-950",
    "from-indigo-950 via-slate-900 to-amber-950",
    "from-red-950 via-amber-950 to-slate-950",
    "from-teal-950 via-emerald-950 to-slate-950",
    "from-violet-950 via-purple-950 to-slate-950",
    "from-stone-800 via-stone-950 to-slate-950",
    "from-sky-950 via-slate-900 to-indigo-950",
    "from-rose-950 via-red-950 to-stone-950",
]
Scene = Literal["lantern", "curtain", "sparks"]

PALETTES: tuple[str, ...] = get_args(Palette)
SCENES: tuple[str, ...] = get_args(Scene)

SCALES: tuple[str, ...] = (
    "大远景 ELS",
    "远景 LS",
    "全景 WS",
    "中景 MS",
    "近景 CU",
    "特写 ECU",
)
LENSES: tuple[int, ...] = (24, 28, 35, 50, 85)
MAX_SHOTS = 8


class Shot(BaseModel):
    id: int
    duration: str = Field(pattern=r"^\d{2}s$", description="形如 04s，取值 3-6 秒")
    scale: str
    lens: str
    move: str
    title: str = Field(min_length=1, max_length=80)
    description: str
    prompt: str
    runwayPrompt: str
    edit: str = ""
    palette: Palette
    scene: Scene
    # C1：参考首帧（uploads.id）。旧数据没有该字段，必须可选。
    reference_image_id: int | None = None
    # F1：本镜绑定的角色资产 id（存在 storyboard JSON 里，不需要单独建表）。
    # 模型若返回同名字段，会被 normalize_shot 丢弃，不能让模型改写绑定。
    character_ids: list[int] = Field(default_factory=list)


ModelName = Literal["即梦 Jimeng", "可灵 Kling", "Runway Gen-3"]


class GenerateRequest(BaseModel):
    idea: str = Field(min_length=1, description="Story premise or creative idea")
    style: str = Field(default="燃向踩点")
    anchors: list[str] = Field(default_factory=list, max_length=12)
    model: ModelName = "即梦 Jimeng"


class GenerateResponse(BaseModel):
    status: Literal["ok"] = "ok"
    source: Literal["llm", "demo"] = "llm"
    shots: list[Shot]
    warning: str | None = None


# --------------------------------------------------------------------------- #
# B4：两阶段生成（先计划，再逐镜展开）
# --------------------------------------------------------------------------- #


class PlannedShot(BaseModel):
    index: int
    duration: str = Field(pattern=r"^\d{2}s$")
    scale: str
    lens: str
    move: str
    purpose: str = ""
    agent_shot: Shot | None = None


class ShotPlan(BaseModel):
    total_seconds: int
    narrative: str = ""
    shots: list[PlannedShot] = Field(min_length=1, max_length=MAX_SHOTS)


class PlanResponse(BaseModel):
    status: Literal["ok"] = "ok"
    plan: ShotPlan


class ExpandShotRequest(BaseModel):
    idea: str = Field(min_length=1)
    style: str = "燃向踩点"
    anchors: list[str] = Field(default_factory=list, max_length=12)
    model: ModelName = "即梦 Jimeng"
    plan: ShotPlan
    index: int = Field(ge=1)


class ExpandShotResponse(BaseModel):
    status: Literal["ok"] = "ok"
    shot: Shot


# --------------------------------------------------------------------------- #
# B1：单镜微调
# --------------------------------------------------------------------------- #


class RefineRequest(BaseModel):
    shot: Shot
    instruction: str = Field(min_length=1, max_length=300)
    model: ModelName = "即梦 Jimeng"
    anchors: list[str] = Field(default_factory=list, max_length=12)


class RefineResponse(BaseModel):
    status: Literal["ok"] = "ok"
    shot: Shot


# --------------------------------------------------------------------------- #
# 归一化：把模型的自由输出收敛回契约
# --------------------------------------------------------------------------- #

_PALETTE_HINTS = (
    (("火", "爆", "轰", "高潮", "血", "红", "战斗", "battle", "fire", "explosion"), PALETTES[2]),
    (("冷", "夜", "蓝", "雨", "悬疑", "孤", "寂静", "night", "rain", "cold", "mystery"), PALETTES[1]),
)
_SCENE_HINTS = (
    (("火", "爆", "spark", "火星", "炸", "刃", "fight"), "sparks"),
    (("幕", "帘", "窗", "curtain", "布", "纱"), "curtain"),
)


def _as_text(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = value if isinstance(value, str) else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text or fallback


def _duration(value: object) -> str:
    found = re.search(r"\d+(?:\.\d+)?", _as_text(value))
    seconds = round(float(found.group())) if found else 4
    return f"{min(6, max(3, seconds)):02d}s"


def _scale(value: object) -> str:
    text = _as_text(value).upper()
    # 顺序有讲究：先判"极端"景别，否则 "extreme close-up" 会被 close 抢先命中。
    if "ECU" in text or "特写" in text or "EXTREME CLOSE" in text:
        return "特写 ECU"
    if "ELS" in text or "大远景" in text or "EXTREME WIDE" in text:
        return "大远景 ELS"
    if "CU" in text or "近景" in text or "CLOSE" in text:
        return "近景 CU"
    if "WS" in text or "全景" in text or "WIDE" in text:
        return "全景 WS"
    if "MS" in text or "中景" in text or "MEDIUM" in text:
        return "中景 MS"
    if "LS" in text or "远景" in text or "LONG SHOT" in text or "FULL SHOT" in text:
        return "远景 LS"
    return "中景 MS"


def _lens(value: object, scale: str) -> str:
    found = re.search(r"(\d{2,3})\s*mm", _as_text(value), re.IGNORECASE)
    if found:
        focal = int(found.group(1))
        nearest = min(LENSES, key=lambda option: abs(option - focal))
        return f"{nearest}mm"
    # 没有焦段就按景别给一个合理默认值。
    by_scale = {"大远景 ELS": 24, "远景 LS": 28, "全景 WS": 35, "中景 MS": 50, "近景 CU": 85, "特写 ECU": 85}
    return f"{by_scale.get(scale, 50)}mm"


def _palette(value: object, index: int, hint: str) -> str:
    text = _as_text(value)
    if text in PALETTES:
        return text
    haystack = f"{text} {hint}".lower()
    for keywords, palette in _PALETTE_HINTS:
        if any(keyword.lower() in haystack for keyword in keywords):
            return palette
    return PALETTES[index % len(PALETTES)]


def _scene(value: object, index: int, hint: str) -> str:
    text = _as_text(value).lower()
    if text in SCENES:
        return text
    haystack = f"{text} {hint}".lower()
    for keywords, scene in _SCENE_HINTS:
        if any(keyword.lower() in haystack for keyword in keywords):
            return scene
    return SCENES[index % len(SCENES)]


def normalize_shot(raw: dict, index: int) -> dict:
    """把单个镜头的原始字典收敛成可直接交给 Shot 校验的形状。"""
    title = _as_text(raw.get("title")) or f"镜头 {index + 1}"
    description = _as_text(raw.get("description"))
    prompt = _as_text(raw.get("prompt"))
    runway_prompt = _as_text(raw.get("runwayPrompt"))
    # 两种提示词只要有一个缺失就互补，避免前端切换模型时出现空卡片。
    prompt = prompt or runway_prompt
    runway_prompt = runway_prompt or prompt

    hint = f"{title} {description} {prompt}"
    scale = _scale(raw.get("scale"))
    return {
        "id": index + 1,
        "duration": _duration(raw.get("duration")),
        "scale": scale,
        "lens": _lens(raw.get("lens"), scale),
        "move": _as_text(raw.get("move"), "缓慢横移 Truck"),
        "title": title[:60],
        "description": description,
        "prompt": prompt,
        "runwayPrompt": runway_prompt,
        "edit": "",
        "palette": _palette(raw.get("palette"), index, hint),
        "scene": _scene(raw.get("scene"), index, hint),
    }


def parse_shots_payload(payload: object, limit: int = MAX_SHOTS) -> list[Shot]:
    """解析模型返回的 shots 负载；结构不可用时抛 ValueError。"""
    if isinstance(payload, dict):
        raw_shots = payload.get("shots")
    elif isinstance(payload, list):
        raw_shots = payload
    else:
        raise ValueError("响应不是 JSON 对象或数组")
    if not isinstance(raw_shots, list) or not raw_shots:
        raise ValueError("响应中缺少非空的 shots 数组")

    shots: list[Shot] = []
    for index, item in enumerate(raw_shots[:limit]):
        if not isinstance(item, dict):
            continue
        try:
            shots.append(Shot(**normalize_shot(item, index)))
        except ValidationError as exc:
            raise ValueError(f"第 {index + 1} 个镜头字段不合法：{exc}") from exc
    if not shots:
        raise ValueError("shots 中没有可用的镜头")
    return shots


# --------------------------------------------------------------------------- #
# 镜头计划（B4 阶段一）的归一化
# --------------------------------------------------------------------------- #


def normalize_planned_shot(raw: dict, index: int) -> dict:
    scale = _scale(raw.get("scale"))
    return {
        "index": index,
        "duration": _duration(raw.get("duration")),
        "scale": scale,
        "lens": _lens(raw.get("lens"), scale),
        "move": _as_text(raw.get("move"), "固定机位 Static"),
        "purpose": _as_text(raw.get("purpose"))[:60],
    }


def parse_plan_payload(payload: object, limit: int = MAX_SHOTS) -> "ShotPlan":
    """把模型返回的镜头计划收敛成契约。

    `total_seconds` 由各镜时长求和得出，不采信模型自己算的数字。
    """
    if not isinstance(payload, dict):
        raise ValueError("计划响应不是 JSON 对象")
    raw_shots = payload.get("shots")
    if not isinstance(raw_shots, list) or not raw_shots:
        raise ValueError("计划中缺少非空的 shots 数组")

    planned: list[PlannedShot] = []
    for index, item in enumerate(raw_shots[:limit], start=1):
        if not isinstance(item, dict):
            continue
        try:
            planned.append(PlannedShot(**normalize_planned_shot(item, index)))
        except ValidationError as exc:
            raise ValueError(f"第 {index} 个计划镜头字段不合法：{exc}") from exc
    if not planned:
        raise ValueError("计划中没有可用的镜头")

    total = sum(int(shot.duration[:2]) for shot in planned)
    return ShotPlan(
        total_seconds=total,
        narrative=_as_text(payload.get("narrative"))[:200],
        shots=planned,
    )


def parse_single_shot(payload: object, index: int = 1) -> Shot:
    """解析单镜返回（B1 微调与 B4 逐镜展开共用）。"""
    raw = payload
    if isinstance(payload, dict) and isinstance(payload.get("shot"), dict):
        raw = payload["shot"]
    if not isinstance(raw, dict):
        raise ValueError("单镜响应不是 JSON 对象")
    try:
        return Shot(**normalize_shot(raw, index - 1))
    except ValidationError as exc:
        raise ValueError(f"镜头字段不合法：{exc}") from exc

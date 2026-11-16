"""角色资产库的初始预设——单一数据源。

这些内容原本硬编码在前端 App.vue 右栏模板里；抽到这里之后，
播种、重置、测试共用同一份定义，不再两处维护。

标签分类沿用界面上的分组，另外新增 `appearance`（外观）：
角色卡上原本的「棕色毛发/金色头箍/玄铁甲胄」是外观属性，
混进「人物」组会让「天命人」和「棕色毛发」并排出现，语义不对。
"""

from __future__ import annotations

from dataclasses import dataclass

TAG_CATEGORIES: tuple[str, ...] = ("character", "emotion", "palette", "lighting", "appearance")
TAG_TONES: tuple[str, ...] = ("amber", "violet", "rose", "indigo", "neutral")

CATEGORY_LABELS: dict[str, str] = {
    "character": "人物",
    "emotion": "情绪",
    "palette": "色调",
    "lighting": "光影",
    "appearance": "外观",
}


@dataclass(frozen=True)
class PresetTag:
    name: str
    category: str
    tone: str


@dataclass(frozen=True)
class PresetCharacter:
    name: str
    role_label: str
    description: str
    prompt_anchor: str
    tone: str
    tags: tuple[str, ...]


PRESET_TAGS: tuple[PresetTag, ...] = (
    # 人物
    PresetTag("天命人", "character", "amber"),
    PresetTag("神秘身影", "character", "neutral"),
    PresetTag("古戏班", "character", "neutral"),
    # 情绪
    PresetTag("诡谲", "emotion", "violet"),
    PresetTag("热血", "emotion", "rose"),
    PresetTag("悬念", "emotion", "neutral"),
    # 色调
    PresetTag("琥珀金", "palette", "amber"),
    PresetTag("暮色蓝", "palette", "indigo"),
    PresetTag("胶片质感", "palette", "neutral"),
    # 光影
    PresetTag("逆光剪影", "lighting", "rose"),
    PresetTag("体积光", "lighting", "neutral"),
    # 外观（来自角色卡上的视觉标签）
    PresetTag("棕色毛发", "appearance", "amber"),
    PresetTag("金色头箍", "appearance", "amber"),
    PresetTag("玄铁甲胄", "appearance", "neutral"),
)

PRESET_CHARACTERS: tuple[PresetCharacter, ...] = (
    PresetCharacter(
        name="天命人",
        role_label="齐天大圣 · 核心角色",
        description="跨镜头视觉规范已建立",
        prompt_anchor="golden circlet, monkey warrior, brown fur",
        tone="amber",
        tags=("棕色毛发", "金色头箍", "玄铁甲胄"),
    ),
)

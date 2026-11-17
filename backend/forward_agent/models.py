"""Public data contracts for forward storyboard generation."""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

class ShotSize(str, Enum):
    EXTREME_WIDE = "大远景"
    WIDE = "远景"
    FULL = "全景"
    MEDIUM = "中景"
    MEDIUM_CLOSE = "中近景"
    CLOSE = "近景"
    CLOSE_UP = "特写"
    EXTREME_CLOSE_UP = "大特写"

class CameraAngle(str, Enum):
    EYE_LEVEL = "平视"
    HIGH_ANGLE = "俯拍"
    LOW_ANGLE = "仰拍"
    OVER_SHOULDER = "过肩"
    POV = "主观视角"
    DUTCH = "荷兰角"

class CameraMove(str, Enum):
    STATIC = "固定"
    PUSH_IN = "推"
    PULL_OUT = "拉"
    PAN = "摇"
    TRACK = "移"
    FOLLOW = "跟"
    CRANE = "升降"
    HANDHELD = "手持"
    ORBIT = "环绕"

class Platform(str, Enum):
    KLING = "kling"
    JIMENG = "jimeng"
    RUNWAY = "runway"
    SORA = "sora"
    SEEDANCE = "seedance"
    MIDJOURNEY = "midjourney"

class StyleTag(str, Enum):
    COMEDY_TWIST = "搞笑反转"
    HYPE = "燃向踩点"
    ANGST = "虐心刀子"
    DAILY = "日常整活"
    EPIC = "名场面复刻"
    MIXCUT = "踩点混剪"

class PromptPair(BaseModel):
    zh: str = ""
    en: str = ""

class ShotPrompts(BaseModel):
    first_frame: PromptPair
    video: PromptPair
    tail_frame: Optional[PromptPair] = None

class CharacterAnchor(BaseModel):
    name: str
    immutable: List[str] = Field(default_factory=list)
    mutable: List[str] = Field(default_factory=list)
    ref_images: List[str] = Field(default_factory=list)

class ShotCard(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    id: str
    index: int
    duration: float = Field(gt=0, le=60)
    shot_size: ShotSize
    camera_angle: CameraAngle
    camera_move: Optional[CameraMove] = None
    lighting: str = ""
    composition: str = ""
    subject: str = ""
    action: str = ""
    expression: str = ""
    scene: str = ""
    props: List[str] = Field(default_factory=list)
    characters: List[CharacterAnchor] = Field(default_factory=list)
    prompts: ShotPrompts
    platform_variants: Dict[str, str] = Field(default_factory=dict)
    source: str = "forward"

class ShotPlan(BaseModel):
    brief: str
    style: Optional[str] = None
    target_duration: Optional[float] = None
    platform: Platform = Platform.KLING
    cards: List[ShotCard] = Field(default_factory=list)
    title: str = ""
    logline: str = ""
    scene_type: str = ""

    @property
    def duration(self) -> float:
        return sum(card.duration for card in self.cards)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")

"""Versioned vision output contract; unknown fields stay null."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Character(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(max_length=200)
    appearance: str | None = Field(default=None, max_length=2000)
    position: str | None = Field(default=None, max_length=500)
    pose: str | None = Field(default=None, max_length=1000)
    occluded: bool | None = None


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str | None = Field(default=None, max_length=2000)
    action: str | None = Field(default=None, max_length=2000)
    scene: str | None = Field(default=None, max_length=2000)
    shot_size: Literal["大远景", "远景", "全景", "中景", "中近景", "近景", "特写", "大特写"] | None = None
    camera_angle: str | None = Field(default=None, max_length=500)
    camera_move: str | None = Field(default=None, max_length=1000)
    lighting: str | None = Field(default=None, max_length=1000)
    composition: str | None = Field(default=None, max_length=1000)
    style: str | None = Field(default=None, max_length=1000)
    first_frame: str | None = Field(default=None, max_length=2000)
    last_frame: str | None = Field(default=None, max_length=2000)
    characters: list[Character] = Field(default_factory=list, max_length=20)
    uncertainties: list[str] = Field(default_factory=list, max_length=30)
    evidence_frames: list[int] = Field(default_factory=list, max_length=3)
    confidence: float = Field(ge=0, le=1)

    def enforce_evidence(self, frame_count: int, distinct_times: int) -> "Observation":
        if not self.evidence_frames or any(i < 0 or i >= frame_count for i in self.evidence_frames):
            raise ValueError("evidence_frames must reference provided frame indexes")
        if distinct_times < 2:
            self.camera_move = None
            self.action = None
            self.uncertainties.append("只有一个独立时间点，无法判断动作变化和运镜")
        return self

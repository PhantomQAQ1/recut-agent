"""Public high-level API for forward storyboard generation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError

from .models import CharacterAnchor, Platform, PromptPair, ShotCard, ShotPlan, ShotPrompts
from .provider import LLMError, MockProvider, Provider, OpenAICompatProvider

_PROMPTS = Path(__file__).with_name("prompts")

class ScreenwriterOutput(BaseModel):
    title: str = ""
    logline: str = ""
    scene_type: str = ""
    characters: List[CharacterAnchor] = Field(default_factory=list)
    beats: List[str] = Field(default_factory=list)

class DirectorCard(BaseModel):
    index: int = 0
    duration: float = Field(default=3.0, gt=0, le=60)
    shot_size: str
    camera_angle: str = "平视"
    camera_move: str = "固定"
    lighting: str = ""
    composition: str = ""
    subject: str = ""
    action: str = ""
    expression: str = ""
    scene: str = ""
    props: List[str] = Field(default_factory=list)
    characters: List[str] = Field(default_factory=list)
    first_frame_zh: str = ""
    first_frame_en: str = ""
    video_zh: str = ""
    video_en: str = ""

class AdapterOutput(BaseModel):
    cards: List[Dict[str, Any]] = Field(default_factory=list)

class ForwardAgent:
    """剧情/脑洞 -> 可编辑分镜卡片 -> 平台提示词。

    The class is transport-agnostic. It does not know FastAPI, SSE, databases,
    Vue, or a project-specific configuration system.
    """
    def __init__(self, provider: Optional[Provider] = None, *, base_url: str = "", api_key: str = "",
                 model: str = "deepseek-chat", director_model: Optional[str] = None,
                 timeout: float = 120.0, max_retry: int = 2):
        if provider is not None:
            self.provider = provider
        elif api_key:
            self.provider = OpenAICompatProvider(base_url or "https://api.deepseek.com/v1", api_key, timeout)
        else:
            self.provider = MockProvider()
        self.model = model
        self.director_model = director_model or model
        self.max_retry = max_retry

    async def generate(self, brief: str, *, style: Optional[str] = None,
                       target_duration: Optional[float] = 15.0,
                       platform: Platform = Platform.KLING) -> ShotPlan:
        if not brief or not brief.strip():
            raise ValueError("brief must not be empty")
        script = await self._validated("screenwriter", {
            "brief": brief, "style": style or "由模型判断", "target_duration_sec": target_duration or 15
        }, ScreenwriterOutput, self.model)
        director = await self._validated("director", {
            "brief": brief, "script": script.model_dump(), "target_duration_sec": target_duration or 15
        }, DirectorCardList, self.director_model)
        cards = self._build_cards(director.cards, script)
        if not cards:
            raise LLMError("EMPTY_DIRECTOR", "director returned no cards")
        variants = await self._adapt(cards, platform)
        for card in cards:
            if card.index in variants:
                card.platform_variants[platform.value] = variants[card.index]
        return ShotPlan(brief=brief, style=style, target_duration=target_duration,
                        platform=platform, cards=cards, title=script.title,
                        logline=script.logline, scene_type=script.scene_type)

    def generate_sync(self, brief: str, **kwargs: Any) -> ShotPlan:
        import asyncio
        return asyncio.run(self.generate(brief, **kwargs))

    async def _validated(self, stage: str, payload: Dict[str, Any], schema: Any, model: str) -> Any:
        system = (_PROMPTS / ("a1_screenwriter.md" if stage == "screenwriter" else "a2_director.md")).read_text(encoding="utf-8")
        messages = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
        last: Optional[ValidationError] = None
        for _ in range(self.max_retry + 1):
            data = await self.provider.chat_json(model=model, messages=messages)
            try:
                return schema.model_validate(data)
            except ValidationError as exc:
                last = exc
                messages.append({"role": "assistant", "content": json.dumps(data, ensure_ascii=False)[:3000]})
                messages.append({"role": "user", "content": "请修正 JSON 校验错误并只输出完整 JSON：%s" % str(exc)[:1000]})
        raise LLMError("SCHEMA_INVALID", str(last) if last else "unknown schema error")

    def _build_cards(self, director_cards: List[DirectorCard], script: ScreenwriterOutput) -> List[ShotCard]:
        anchors = {c.name: c for c in script.characters}
        cards: List[ShotCard] = []
        for i, item in enumerate(director_cards):
            try:
                cards.append(ShotCard(
                    id="sh_%03d" % (i + 1), index=i, duration=item.duration,
                    shot_size=item.shot_size, camera_angle=item.camera_angle, camera_move=item.camera_move,
                    lighting=item.lighting, composition=item.composition, subject=item.subject,
                    action=item.action, expression=item.expression, scene=item.scene, props=item.props,
                    characters=[anchors[name] for name in item.characters if name in anchors],
                    prompts=ShotPrompts(first_frame=PromptPair(zh=item.first_frame_zh, en=item.first_frame_en),
                                        video=PromptPair(zh=item.video_zh, en=item.video_en)), source="forward"
                ))
            except Exception as exc:
                raise LLMError("CARD_INVALID", "card %d: %s" % (i, exc)) from exc
        return cards

    async def _adapt(self, cards: List[ShotCard], platform: Platform) -> Dict[int, str]:
        system = (_PROMPTS / "a3_adapter.md").read_text(encoding="utf-8")
        payload = {"platform": platform.value, "cards": [c.model_dump(mode="json") for c in cards]}
        data = await self.provider.chat_json(model=self.model, messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ])
        out = AdapterOutput.model_validate(data)
        result: Dict[int, str] = {}
        for row in out.cards:
            if "index" in row and "prompt" in row:
                result[int(row["index"])] = str(row["prompt"])
        return result

class DirectorCardList(BaseModel):
    cards: List[DirectorCard] = Field(default_factory=list)

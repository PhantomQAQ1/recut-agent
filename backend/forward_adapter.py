"""将独立正向 Agent 的输出适配到现有可编辑镜头计划。"""
from __future__ import annotations

from forward_agent import ForwardAgent, LLMError, Platform
from config import settings
from errors import UpstreamError
from schemas import GenerateRequest, PlannedShot, ShotPlan, normalize_shot, Shot

# Agent 的运镜是短词（固定/推/拉…），前端下拉框用的是「中文 + English」，
# 不做映射的话计划面板那一列会显示空白。
_MOVE_MAP = {
    "固定": "固定机位 Static",
    "推": "急速推镜 Crash Zoom",
    "拉": "缓慢拉远 Pull out",
    "摇": "横向摇镜 Pan",
    "移": "缓慢横移 Truck",
    "跟": "手持跟拍 Handheld",
    "手持": "手持跟拍 Handheld",
    "升降": "升降机位 Crane",
    "环绕": "环绕跟拍 Orbit",
}


def _move(value: object) -> str:
    text = str(value or "").strip()
    return _MOVE_MAP.get(text, text or "固定机位 Static")


async def agent_plan(request: GenerateRequest) -> tuple[ShotPlan, bool]:
    """生成镜头计划，并把每镜的完整卡片一并带回来。

    返回 (plan, demo)。demo=True 表示当前没有配置模型 Key，用的是包内固定 Mock，
    前端需要把它当演示数据对待。
    """
    demo = not settings.llm_ready
    agent = ForwardAgent(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key or "",
        model=settings.llm_model,
        timeout=settings.request_timeout,
    )
    platform = {
        "即梦 Jimeng": Platform.JIMENG,
        "可灵 Kling": Platform.KLING,
        "Runway Gen-3": Platform.RUNWAY,
    }[request.model]

    brief = request.idea
    if request.anchors:
        brief += "\n角色一致性锚点：" + "、".join(request.anchors)

    try:
        result = await agent.generate(brief, style=request.style, platform=platform)
        planned: list[PlannedShot] = []
        for index, card in enumerate(result.cards[:8], start=1):
            raw = {
                "duration": str(card.duration),
                "scale": card.shot_size,
                "move": _move(card.camera_move),
                "title": card.subject or f"镜头 {index}",
                "description": "，".join(
                    filter(
                        None,
                        [
                            card.scene,
                            card.subject,
                            card.action,
                            card.expression,
                            card.lighting,
                            card.composition,
                        ],
                    )
                ),
                "prompt": card.prompts.video.zh or card.prompts.first_frame.zh,
                "runwayPrompt": card.prompts.video.en or card.prompts.first_frame.en,
            }
            shot = Shot(**normalize_shot(raw, index - 1))
            planned.append(
                PlannedShot(
                    index=index,
                    duration=shot.duration,
                    scale=shot.scale,
                    lens=shot.lens,
                    move=shot.move,
                    purpose=card.action[:60],
                    agent_shot=shot,
                )
            )
        if not planned:
            raise ValueError("Agent 未返回可用镜头")
        narrative = ("【演示数据：固定 Mock，未调用模型】" if demo else "") + (
            result.logline or result.title
        )
        return (
            ShotPlan(
                total_seconds=sum(int(p.duration[:2]) for p in planned),
                narrative=narrative[:200],
                shots=planned,
            ),
            demo,
        )
    except (LLMError, ValueError, TypeError) as exc:
        raise UpstreamError(f"正向 Agent 生成失败：{exc}") from exc

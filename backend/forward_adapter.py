"""将独立正向 Agent 的输出适配到现有可编辑镜头计划。"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from forward_agent import ForwardAgent, LLMError, Platform
from forward_agent.provider import OpenAICompatProvider
from config import settings
from llm import extract_json_object
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


class _CompatProvider(OpenAICompatProvider):
    """官方 Provider 之上的兼容层，只做两件事：

    1. 服务端对 `response_format` 返回 400 时，去掉该参数重试一次。
       魔搭 API-Inference 与部分自建网关会出现这种情况。
    2. 返回内容不是纯 JSON 时，从文本里截取第一个 JSON 对象。
    """

    # 免费额度对突发请求敏感（魔搭 limit_burst_rate），用它做一次有界退避
    _burst_retries = 0

    def _post(self, model: str, messages, temperature: float) -> dict[str, Any]:  # type: ignore[override]
        self._burst_retries = 0
        base = {"model": model, "messages": messages, "temperature": temperature}
        for attempt in range(2):
            payload = dict(base)
            if attempt == 0:
                payload["response_format"] = {"type": "json_object"}
            try:
                return self._request(payload)
            except LLMError as exc:
                if attempt == 0 and exc.code == "UPSTREAM_STATUS_400":
                    continue
                raise
        raise LLMError("UPSTREAM_HTTP", "重试后仍未拿到响应")

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            # 免费额度的限流不一定用 429：魔搭会返回 400 + limit_burst_rate，
            # 所以同时看状态码和响应体里的关键字。
            rate_limited = exc.code in {429, 500, 502, 503, 504} or any(
                marker in detail.lower()
                for marker in ("limit_burst_rate", "rate increased too quickly", "rate limit")
            )
            if rate_limited and self._burst_retries < 3:
                self._burst_retries += 1
                time.sleep(3 * self._burst_retries)
                return self._request(payload)
            raise LLMError("UPSTREAM_STATUS_%s" % exc.code, detail) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMError("UPSTREAM_HTTP", str(exc)) from exc
        self._burst_retries = 0

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("UPSTREAM_SHAPE", json.dumps(body, ensure_ascii=False)[:500]) from exc
        if isinstance(content, dict):
            return content
        return extract_json_object(str(content))


def _build_agent() -> ForwardAgent:
    if not settings.llm_api_key:
        # 没有 Key 时用包内确定性 Mock，调用链仍可验证
        return ForwardAgent()
    provider = _CompatProvider(
        settings.llm_base_url, settings.llm_api_key, settings.request_timeout
    )
    return ForwardAgent(
        provider=provider, model=settings.llm_model, timeout=settings.request_timeout
    )


async def agent_plan(request: GenerateRequest) -> tuple[ShotPlan, bool]:
    """生成镜头计划，并把每镜的完整卡片一并带回来。

    返回 (plan, demo)。demo=True 表示当前没有配置模型 Key，用的是包内固定 Mock，
    前端需要把它当演示数据对待。
    """
    demo = not settings.llm_ready
    agent = _build_agent()
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

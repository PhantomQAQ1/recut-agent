"""正向生成：创意 → 分镜脚本。

流程是「调模型 → 严格解析 → 归一化兜底」，结构不合法时降温度重试一次。
"""

from __future__ import annotations

import json

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI

from config import settings
from errors import UpstreamError
from llm import text_client
from schemas import GenerateRequest, Shot, parse_shots_payload

SYSTEM_PROMPT = """你是一名资深影视分镜师，为 AIGC 视频生成 AI 可直接使用的分镜脚本。

只输出 JSON，格式：
{"shots":[{"duration":"04s","scale":"近景 CU","lens":"85mm","move":"急速推镜 Crash Zoom","title":"一句话镜头标题","description":"画面内容","prompt":"提示词","runwayPrompt":"english prompt","palette":"from-amber-950 via-orange-950 to-slate-950"}]}

硬性要求：
1. 镜头数 5-8 个，总时长 25-40 秒；duration 取值 3-6 秒，写成 "04s" 这种两位秒数。
2. scale 只能取：大远景 ELS / 远景 LS / 全景 WS / 中景 MS / 近景 CU / 特写 ECU。
3. lens 只能取：24mm / 28mm / 35mm / 50mm / 85mm。
4. move 写成「中文名 + 英文名」，例如「急速推镜 Crash Zoom」「环绕跟拍 Orbit」「低机位升格 Low angle」。
5. title 不超过 30 字，是可直接放进故事板的镜头标题。
6. prompt 用中文，逗号分隔的画面描述：先以角色锚点开头，再写场景、动作、光影、质感、氛围。
   runwayPrompt 是同一画面的结构化英文：焦段 + 景别 + 主体 + 动作 + 环境 + 光影 + 质感。
7. palette 只能从下面三套里选（按情绪判断）：
   - "from-amber-950 via-orange-950 to-slate-950" 暖金、怀旧、黄昏
   - "from-indigo-950 via-slate-900 to-amber-950" 冷蓝、悬疑、夜色
   - "from-red-950 via-amber-950 to-slate-950" 烈焰、高潮、爆发
8. 叙事要有推进：建立环境 → 制造不安 → 冲突升级 → 高潮 → 收束，不要五个镜头都写同一件事。
9. 不要输出 JSON 之外的任何解释文字。"""


def build_user_prompt(request: GenerateRequest) -> str:
    anchors = (
        "、".join(anchor.strip() for anchor in request.anchors if anchor.strip())
        or "（未提供，请自行提炼 1-2 个核心视觉锚点）"
    )
    language = "英文结构化提示词" if "Runway" in request.model else "中文自然语言提示词"
    return (
        f"剧情梗概：{request.idea}\n"
        f"二创风格：{request.style}\n"
        f"角色一致性锚点（必须原样出现在每个 prompt 开头）：{anchors}\n"
        f"目标生成模型：{request.model}，因此提示词语言为{language}。\n"
        "请据此输出分镜 JSON。"
    )


async def _complete(client: AsyncOpenAI, request: GenerateRequest, temperature: float):
    try:
        return await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(request)},
            ],
            temperature=temperature,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
    except (APITimeoutError, APIConnectionError) as exc:
        raise UpstreamError(f"无法连接模型服务：{exc}") from exc
    except APIError as exc:
        raise UpstreamError(f"模型服务返回错误：{exc}") from exc


async def generate_shots(
    request: GenerateRequest,
    *,
    client: AsyncOpenAI | None = None,
) -> list[Shot]:
    """调用模型生成分镜。client 可注入以便测试。"""
    if client is None:
        client = text_client()  # 未配置密钥时抛 MissingConfigError

    last_error: Exception | None = None
    # 第一次追求创意，重试时降温度追求结构稳定。
    for temperature in (0.9, 0.4):
        completion = await _complete(client, request, temperature)
        content = completion.choices[0].message.content or ""
        try:
            shots = parse_shots_payload(json.loads(content))
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            continue
        return shots

    raise UpstreamError(f"模型返回的分镜结构无法解析（已重试）：{last_error}")

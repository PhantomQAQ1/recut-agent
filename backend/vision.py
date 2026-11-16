"""逆向解析：关键帧 → 分镜脚本。

一次多模态调用完成「读懂画面 + 反推镜头设计」，输出仍走与正向生成相同的契约。
"""

from __future__ import annotations

import base64
import json

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI

from config import settings
from errors import UpstreamError
from llm import vision_client
from schemas import Shot, parse_shots_payload

VISION_PROMPT = """你是影视视听语言分析师。用户给出一段视频按时间顺序抽取的关键帧（也可能是单张图片）。

请还原它的镜头设计，并反推出可直接用于 AIGC 重制的分镜。

只输出 JSON，格式：
{"shots":[{"duration":"04s","scale":"近景 CU","lens":"85mm","move":"急速推镜 Crash Zoom","title":"镜头标题","description":"这一镜的画面内容与戏剧功能","prompt":"中文提示词","runwayPrompt":"english prompt","palette":"from-indigo-950 via-slate-900 to-amber-950"}]}

要求：
1. 相邻且内容重复的帧要合并成一个镜头；镜头数不超过帧数。
2. 先判断这是建立镜头、人物镜头还是情绪/高潮镜头，再给景别与焦段：
   scale 只能取 大远景 ELS / 远景 LS / 全景 WS / 中景 MS / 近景 CU / 特写 ECU；
   lens 只能取 24mm / 28mm / 35mm / 50mm / 85mm。
3. move 用「中文名 + 英文名」，例如「缓慢横移 Truck」「手持跟拍 Handheld」。
4. description 要写清画面里有什么、光从哪来、角色在做什么。
5. prompt 用中文，以用户给的角色锚点开头（若未给则自行提炼）；runwayPrompt 为同内容的英文结构化描述。
6. palette 只能从下列三套里按画面色调选择：
   "from-amber-950 via-orange-950 to-slate-950" 暖金 / 黄昏
   "from-indigo-950 via-slate-900 to-amber-950" 冷蓝 / 夜色
   "from-red-950 via-amber-950 to-slate-950" 烈焰 / 高饱和
7. 不要输出 JSON 之外的任何文字。"""


def _data_url(frame: bytes) -> str:
    # ffmpeg 抽出的帧都是 JPEG；图片分支可能不是，但统一按 jpeg 声明在各家
    # 兼容接口上都能被接受，且最省带宽。
    return "data:image/jpeg;base64," + base64.b64encode(frame).decode("ascii")


def build_messages(frames: list[bytes], anchors: list[str], model: str, context: str) -> list[dict]:
    anchor_text = "、".join(anchor.strip() for anchor in anchors if anchor.strip()) or "（未提供，请自行提炼）"
    language = "英文结构化提示词" if "Runway" in model else "中文自然语言提示词"
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                f"{context}\n角色一致性锚点：{anchor_text}\n"
                f"目标生成模型：{model}，因此提示词语言为{language}。\n"
                "请按帧的时间顺序还原镜头并输出 JSON。"
            ),
        }
    ]
    content.extend({"type": "image_url", "image_url": {"url": _data_url(frame)}} for frame in frames)
    return [
        {"role": "system", "content": VISION_PROMPT},
        {"role": "user", "content": content},
    ]


async def analyze_frames(
    frames: list[bytes],
    anchors: list[str],
    model: str,
    *,
    context: str = "",
    client: AsyncOpenAI | None = None,
) -> list[Shot]:
    """把关键帧交给视觉模型，返回校验后的分镜。client 可注入以便测试。"""
    if not frames:
        raise UpstreamError("没有可用于解析的画面")
    if client is None:
        client = vision_client()  # 未配置密钥时抛 MissingConfigError

    messages = build_messages(frames, anchors, model, context)
    last_error: Exception | None = None
    for temperature in (0.6, 0.2):
        try:
            completion = await client.chat.completions.create(
                model=settings.vision_model,
                messages=messages,
                temperature=temperature,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
        except (APITimeoutError, APIConnectionError) as exc:
            raise UpstreamError(f"无法连接视觉模型服务：{exc}") from exc
        except APIError as exc:
            raise UpstreamError(f"视觉模型服务返回错误：{exc}") from exc

        content = completion.choices[0].message.content or ""
        try:
            return parse_shots_payload(json.loads(content), limit=len(frames))
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            continue

    raise UpstreamError(f"视觉模型返回的分镜结构无法解析（已重试）：{last_error}")

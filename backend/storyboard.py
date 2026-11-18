"""正向生成：创意 → 分镜脚本。

流程是「调模型 → 严格解析 → 归一化兜底」，结构不合法时降温度重试一次。
"""

from __future__ import annotations

import json

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI

from config import settings
from errors import UpstreamError
from llm import create_json_completion, extract_json_object, text_client
from schemas import (
    ExpandShotRequest,
    GenerateRequest,
    RefineRequest,
    Shot,
    ShotPlan,
    parse_plan_payload,
    parse_shots_payload,
    parse_single_shot,
)

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
7. palette 只能从下面八套里选（按情绪判断）：
   - "from-amber-950 via-orange-950 to-slate-950" 琥珀金：暖金、怀旧、黄昏
   - "from-indigo-950 via-slate-900 to-amber-950" 暮色蓝：冷蓝、悬疑、夜色
   - "from-red-950 via-amber-950 to-slate-950" 烈焰红：烈焰、高潮、爆发
   - "from-teal-950 via-emerald-950 to-slate-950" 幽绿：潮湿、诡秘、密林
   - "from-violet-950 via-purple-950 to-slate-950" 紫罗兰：梦幻、异界、法术
   - "from-stone-800 via-stone-950 to-slate-950" 石青灰：写实、废墟、克制
   - "from-sky-950 via-slate-900 to-indigo-950" 冷空：清晨、辽阔、冷静
   - "from-rose-950 via-red-950 to-stone-950" 血色：暴力、悲怆、牺牲
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
        return await create_json_completion(
            client,
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(request)},
            ],
            temperature=temperature,
            max_tokens=4000,
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
            shots = parse_shots_payload(extract_json_object(content))
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            continue
        return shots

    raise UpstreamError(f"模型返回的分镜结构无法解析（已重试）：{last_error}")


# --------------------------------------------------------------------------- #
# B4：先出镜头计划，再逐镜展开
# --------------------------------------------------------------------------- #

PLAN_SYSTEM = """你是资深影视分镜师。用户给出创意、风格与角色锚点，这一步只输出「镜头计划」，不要写提示词。

只输出 JSON：
{"total_seconds":30,"narrative":"一句话说明叙事结构","shots":[{"index":1,"duration":"04s","scale":"近景 CU","lens":"85mm","move":"急速推镜 Crash Zoom","purpose":"建立环境"}]}

要求：
1. 3-8 个镜头，每镜 3-6 秒，总时长 18-40 秒。
2. scale 只能取 大远景 ELS / 远景 LS / 全景 WS / 中景 MS / 近景 CU / 特写 ECU。
3. lens 只能取 24mm / 28mm / 35mm / 50mm / 85mm。
4. move 写成「中文名 + 英文名」，例如「缓慢横移 Truck」「环绕跟拍 Orbit」。
5. purpose 不超过 20 字，说明这一镜的叙事功能（建立 / 不安 / 升级 / 高潮 / 收束）。
6. 节奏要有起伏，不要每一镜都用同样的时长。
7. 不要输出 JSON 之外的任何文字。"""

EXPAND_SYSTEM = """你是资深影视分镜师。用户给出完整镜头计划和其中某一镜的序号，
你只需把「这一镜」写成完整分镜，不要输出其他镜头。

只输出 JSON：
{"shot":{"id":1,"duration":"04s","scale":"近景 CU","lens":"85mm","move":"急速推镜 Crash Zoom","title":"一句话镜头标题","description":"画面内容与光影","prompt":"中文提示词","runwayPrompt":"english prompt","palette":"from-amber-950 via-orange-950 to-slate-950","scene":"lantern"}}

要求：
1. duration / scale / lens / move 必须与计划里该镜完全一致，不要改动。
2. title 不超过 30 字；description 写清画面内容、光线方向、角色动作。
3. prompt 用中文逗号分隔，必须以角色锚点开头；runwayPrompt 是同画面的结构化英文。
4. palette 只能取下列八套之一：
   from-amber-950 via-orange-950 to-slate-950 / from-indigo-950 via-slate-900 to-amber-950 /
   from-red-950 via-amber-950 to-slate-950 / from-teal-950 via-emerald-950 to-slate-950 /
   from-violet-950 via-purple-950 to-slate-950 / from-stone-800 via-stone-950 to-slate-950 /
   from-sky-950 via-slate-900 to-indigo-950 / from-rose-950 via-red-950 to-stone-950
5. scene 只能取 lantern / curtain / sparks。
6. 不要输出 JSON 之外的任何文字。"""

REFINE_SYSTEM = """你是分镜修改助手。用户给出一个镜头的完整 JSON 和一条修改指令。

只输出 JSON：{"shot": <修改后的完整镜头>}

要求：
1. 只修改与指令相关的字段，其余字段（id / duration / scale / lens / move）原样保留。
2. prompt 与 runwayPrompt 必须同步体现修改内容。
3. 保持原有语言：prompt 中文、runwayPrompt 英文。
4. 不要输出说明文字。"""


async def _json_call(
    client: AsyncOpenAI,
    *,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int = 4000,
) -> str:
    try:
        completion = await create_json_completion(
            client,
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except (APITimeoutError, APIConnectionError) as exc:
        raise UpstreamError(f"无法连接模型服务：{exc}") from exc
    except APIError as exc:
        raise UpstreamError(f"模型服务返回错误：{exc}") from exc
    return completion.choices[0].message.content or ""


def build_plan_prompt(request: GenerateRequest) -> str:
    anchors = "、".join(anchor.strip() for anchor in request.anchors if anchor.strip()) or "（未提供，请自行提炼）"
    return (
        f"剧情梗概：{request.idea}\n"
        f"二创风格：{request.style}\n"
        f"角色一致性锚点：{anchors}\n"
        "请先给出镜头计划（先不写提示词）。"
    )


async def plan_story(
    request: GenerateRequest,
    *,
    client: AsyncOpenAI | None = None,
) -> ShotPlan:
    """B4 阶段一：只产出镜头计划。"""
    if client is None:
        client = text_client()

    last_error: Exception | None = None
    for temperature in (0.8, 0.4):
        content = await _json_call(
            client,
            system=PLAN_SYSTEM,
            user=build_plan_prompt(request),
            temperature=temperature,
            max_tokens=1500,
        )
        try:
            return parse_plan_payload(extract_json_object(content))
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            continue
    raise UpstreamError(f"镜头计划解析失败（已重试）：{last_error}")


def build_expand_prompt(payload: ExpandShotRequest) -> str:
    anchors = "、".join(anchor.strip() for anchor in payload.anchors if anchor.strip()) or "（未提供，请自行提炼）"
    language = "英文结构化提示词" if "Runway" in payload.model else "中文自然语言提示词"
    plan_lines = "\n".join(
        f"  {item.index}. {item.duration} / {item.scale} / {item.lens} / {item.move} — {item.purpose}"
        for item in payload.plan.shots
    )
    target = next(
        (item for item in payload.plan.shots if item.index == payload.index),
        payload.plan.shots[0],
    )
    return (
        f"剧情梗概：{payload.idea}\n二创风格：{payload.style}\n"
        f"角色锚点（必须出现在 prompt 开头）：{anchors}\n"
        f"完整镜头计划（共 {len(payload.plan.shots)} 镜）：\n{plan_lines}\n"
        f"现在只写第 {payload.index} 镜：{target.duration} / {target.scale} / {target.lens} / {target.move}。\n"
        f"提示词语言：{language}。"
    )


async def expand_shot(
    payload: ExpandShotRequest,
    *,
    client: AsyncOpenAI | None = None,
) -> Shot:
    """B4 阶段二：把计划中的某一镜展开成完整分镜。"""
    if client is None:
        client = text_client()

    last_error: Exception | None = None
    for temperature in (0.85, 0.4):
        content = await _json_call(
            client,
            system=EXPAND_SYSTEM,
            user=build_expand_prompt(payload),
            temperature=temperature,
        )
        try:
            shot = parse_single_shot(extract_json_object(content), payload.index)
            return shot.model_copy(update={"id": payload.index})
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            continue
    raise UpstreamError(f"第 {payload.index} 镜解析失败（已重试）：{last_error}")


def build_refine_prompt(payload: RefineRequest) -> str:
    language = "英文结构化提示词" if "Runway" in payload.model else "中文自然语言提示词"
    anchors = "、".join(anchor.strip() for anchor in payload.anchors if anchor.strip()) or "（未提供）"
    return (
        f"当前镜头 JSON：\n{json.dumps(payload.shot.model_dump(), ensure_ascii=False)}\n"
        f"修改指令：{payload.instruction}\n"
        f"角色锚点：{anchors}\n提示词语言：{language}\n"
        "请输出修改后的完整镜头 JSON。"
    )


async def refine_shot(
    payload: RefineRequest,
    *,
    client: AsyncOpenAI | None = None,
) -> Shot:
    """B1：按指令改写单镜，不落库。"""
    if client is None:
        client = text_client()

    last_error: Exception | None = None
    for temperature in (0.6, 0.2):
        content = await _json_call(
            client,
            system=REFINE_SYSTEM,
            user=build_refine_prompt(payload),
            temperature=temperature,
        )
        try:
            shot = parse_single_shot(extract_json_object(content), 1)
            # 保留原始 id，前端靠它定位是哪一格
            return shot.model_copy(update={"id": payload.shot.id})
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            continue
    raise UpstreamError(f"镜头微调解析失败（已重试）：{last_error}")

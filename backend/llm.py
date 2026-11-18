"""OpenAI 兼容的模型客户端。

DeepSeek / 通义千问 / Kimi / 智谱 / OpenAI 都提供 OpenAI 兼容接口，
所以只换 base_url + model 即可切换供应商，业务代码无需改动。
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from openai import AsyncOpenAI, BadRequestError

from config import settings
from errors import MissingConfigError


def extract_json_object(text: str) -> dict[str, Any]:
    """从模型输出里取出 JSON 对象。

    即使请求了 `response_format: json_object`，仍有模型会把结果包在
    ```json 代码块或一句解释文字里（魔搭上的 Qwen 就是这样）。
    这里先按原样解析，失败再按括号配对截取第一个对象。
    """
    stripped = (text or "").strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()
    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    if start >= 0:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(stripped)):
            char = stripped[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(stripped[start : index + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(data, dict):
                        return data
                    break
    raise ValueError("模型返回的内容里没有可解析的 JSON 对象")


async def create_json_completion(client: AsyncOpenAI, **kwargs: Any):
    """要求 JSON 输出的 chat 调用，服务商不支持 response_format 时自动降级。

    魔搭 API-Inference、部分自建网关会直接对 response_format 返回 400，
    这种情况下退化成"只靠提示词约束 + 事后提取 JSON"。
    """
    kwargs = dict(kwargs)
    try:
        return await client.chat.completions.create(
            **kwargs, response_format={"type": "json_object"}
        )
    except BadRequestError:
        kwargs.pop("response_format", None)
        return await client.chat.completions.create(**kwargs)


@lru_cache(maxsize=1)
def text_client() -> AsyncOpenAI:
    if not settings.llm_api_key:
        raise MissingConfigError(
            "未配置 LLM_API_KEY：请在 backend/.env 中填写模型服务密钥后重启后端"
        )
    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.request_timeout,
        max_retries=1,
    )


@lru_cache(maxsize=1)
def vision_client() -> AsyncOpenAI:
    if not settings.vision_api_key:
        raise MissingConfigError(
            "未配置视觉模型密钥：请在 backend/.env 中填写 VISION_API_KEY（或复用 LLM_API_KEY）"
        )
    return AsyncOpenAI(
        api_key=settings.vision_api_key,
        base_url=settings.vision_base_url,
        timeout=settings.request_timeout,
        max_retries=1,
    )

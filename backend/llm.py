"""OpenAI 兼容的模型客户端。

DeepSeek / 通义千问 / Kimi / 智谱 / OpenAI 都提供 OpenAI 兼容接口，
所以只换 base_url + model 即可切换供应商，业务代码无需改动。
"""

from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI

from config import settings
from errors import MissingConfigError


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

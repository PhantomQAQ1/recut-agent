"""模型连通性自检：验证文本与视觉模型是否可用、是否支持 JSON 输出。

用法（在 backend 目录下）：
    .venv\\Scripts\\python -m scripts.check_models

它会做四件事：
1. 打印当前 .env 解析出的地址与模型名
2. 尝试列出该服务商可用的模型（模型改名时对着这里改）
3. 文本模型：发一句要求 JSON 的请求，验证 response_format 是否被支持
4. 视觉模型：发一张 16×16 的测试图，验证多模态链路
"""

from __future__ import annotations

import asyncio
import base64
import json
import struct
import sys
import zlib

from openai import AsyncOpenAI

from config import settings

# Windows 控制台默认 GBK，遇到不可编码字符时宁可显示成 ? 也不要抛异常中断
try:
    sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    pass


def solid_png(size: int = 16, rgb: tuple[int, int, int] = (60, 90, 140)) -> bytes:
    row = b"\x00" + bytes(rgb) * size
    raw = row * size

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def mask(value: str | None) -> str:
    if not value:
        return "（未配置）"
    return f"{value[:6]}…{value[-4:]}" if len(value) > 12 else "（已配置）"


async def list_models(client: AsyncOpenAI) -> None:
    try:
        page = await client.models.list()
        ids = sorted({model.id for model in page.data})
    except Exception as exc:  # noqa: BLE001 - 自检脚本要报告任何失败
        print(f"  · 无法列出模型：{type(exc).__name__}: {exc}")
        return
    if not ids:
        print("  · 服务商未返回模型列表")
        return
    print(f"  · 可用模型（{len(ids)} 个，前 20 个）：")
    for model_id in ids[:20]:
        print(f"      {model_id}")
    for label, configured in (("文本", settings.llm_model), ("视觉", settings.vision_model)):
        if configured in ids:
            print(f"  · {label}模型 {configured} [OK] 在列表中")
        else:
            print(f"  · {label}模型 {configured} [X] 不在列表里，需要改名")


async def check_text() -> bool:
    if not settings.llm_api_key:
        print("  [X] 未配置 LLM_API_KEY")
        return False
    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.request_timeout,
        max_retries=0,
    )
    await list_models(client)

    messages = [{"role": "user", "content": '只输出 JSON，不要解释：{"ok":true}'}]
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=32,
            temperature=0,
        )
        content = (response.choices[0].message.content or "").strip()
        json.loads(content)
        print(f"  [OK] 文本模型可用，且支持 json_object：{content[:60]}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  ! 带 json_object 的请求失败：{type(exc).__name__}: {str(exc)[:160]}")

    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            max_tokens=32,
            temperature=0,
        )
        content = (response.choices[0].message.content or "").strip()
        print(f"  [OK] 文本模型可用（不支持 json_object，会走提示词降级）：{content[:60]}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  [X] 文本模型不可用：{type(exc).__name__}: {str(exc)[:200]}")
        return False


async def check_vision() -> bool:
    if not settings.vision_api_key:
        print("  [X] 未配置视觉模型密钥（VISION_API_KEY 或 LLM_API_KEY）")
        return False
    client = AsyncOpenAI(
        api_key=settings.vision_api_key,
        base_url=settings.vision_base_url,
        timeout=settings.request_timeout,
        max_retries=0,
    )
    data_url = "data:image/png;base64," + base64.b64encode(solid_png()).decode("ascii")
    try:
        response = await client.chat.completions.create(
            model=settings.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": '这张图是什么主色调？只输出 JSON：{"color":"..."}'},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            max_tokens=64,
            temperature=0,
        )
        content = (response.choices[0].message.content or "").strip()
        print(f"  [OK] 视觉模型可用：{content[:80]}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  [X] 视觉模型不可用：{type(exc).__name__}: {str(exc)[:200]}")
        return False


async def main() -> int:
    print("=== 当前配置 ===")
    print(f"  文本：{settings.llm_base_url}  |  {settings.llm_model}  |  Key {mask(settings.llm_api_key)}")
    print(f"  视觉：{settings.vision_base_url}  |  {settings.vision_model}  |  Key {mask(settings.vision_api_key)}")
    print(f"  超时：{settings.request_timeout}s  |  抽帧上限：{settings.max_frames}")

    print("\n=== 文本模型 ===")
    text_ok = await check_text()
    print("\n=== 视觉模型 ===")
    vision_ok = await check_vision()

    print("\n=== 结论 ===")
    print(f"  生成分镜计划 / 展开提示词 / 单镜微调：{'可用' if text_ok else '不可用'}")
    print(f"  逆向解析（视频/图片）：{'可用' if vision_ok else '不可用'}")
    if not (text_ok and vision_ok):
        print("\n  提示：改完 backend/.env 需要重启后端才生效（配置在启动时读取）。")
        return 1
    print("\n  全部通过，重启后端即可使用。")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

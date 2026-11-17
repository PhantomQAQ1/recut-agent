"""LLM providers. OpenAI-compatible HTTP plus deterministic local Mock."""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

class LLMError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

class Provider:
    async def chat_json(self, *, model: str, messages: List[Dict[str, Any]], temperature: float = 0.7) -> Dict[str, Any]:
        raise NotImplementedError

class OpenAICompatProvider(Provider):
    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _post(self, model: str, messages: List[Dict[str, Any]], temperature: float) -> Dict[str, Any]:
        payload = {"model": model, "messages": messages, "temperature": temperature,
                   "response_format": {"type": "json_object"}}
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            raise LLMError("UPSTREAM_STATUS_%s" % exc.code, exc.read().decode("utf-8", "replace")[:500]) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMError("UPSTREAM_HTTP", str(exc)) from exc
        try:
            content = body["choices"][0]["message"]["content"]
            return json.loads(content) if isinstance(content, str) else content
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMError("UPSTREAM_SHAPE", json.dumps(body, ensure_ascii=False)[:500]) from exc

    async def chat_json(self, *, model: str, messages: List[Dict[str, Any]], temperature: float = 0.7) -> Dict[str, Any]:
        return await asyncio.to_thread(self._post, model, messages, temperature)

class MockProvider(Provider):
    async def chat_json(self, *, model: str, messages: List[Dict[str, Any]], temperature: float = 0.7) -> Dict[str, Any]:
        system = messages[0].get("content", "") if messages else ""
        user = messages[-1].get("content", "") if messages else ""
        await asyncio.sleep(0)
        if "screenwriter" in system:
            return {"title": "意外身份", "logline": "普通人平静生活中突然暴露不普通的身份。", "scene_type": "搞笑反转",
                    "characters": [{"name": "主角", "immutable": ["黑色短发", "深色外套"], "mutable": ["表情夸张度"]}],
                    "beats": ["铺垫：主角在日常场景中完成普通工作", "转折：旁人认出主角的隐藏身份", "落点：主角装作若无其事继续手头动作"]}
        if "director" in system:
            return {"cards": [
                {"index": 0, "duration": 3.5, "shot_size": "全景", "camera_angle": "平视", "camera_move": "固定", "lighting": "柔和室内光", "composition": "人物位于画面右侧，环境占主要面积", "subject": "主角在日常场景中工作", "action": "双手持续完成手头动作，动作幅度稳定", "expression": "平静", "scene": "整洁的现代室内空间", "props": ["工作用品"], "characters": ["主角"], "first_frame_zh": "主角在现代室内空间工作的全景首帧，柔和室内光，画面干净", "first_frame_en": "Wide shot of the protagonist working in a modern interior, soft indoor light", "video_zh": "主角保持稳定动作，镜头固定3.5秒", "video_en": "The protagonist keeps a steady action, locked-off camera for 3.5 seconds"},
                {"index": 1, "duration": 3.5, "shot_size": "中近景", "camera_angle": "平视", "camera_move": "推", "lighting": "侧面柔光", "composition": "人物居中，背景轻微虚化", "subject": "主角听见旁人叫出身份", "action": "主角停下手部动作，缓慢抬头看向画面外", "expression": "短暂错愕后恢复平静", "scene": "同一室内空间", "props": [], "characters": ["主角"], "first_frame_zh": "主角中近景，正在工作，侧面柔光，背景轻微虚化", "first_frame_en": "Medium close-up of the protagonist working, soft side light, shallow background", "video_zh": "主角停止动作并抬头，镜头缓慢推近3.5秒", "video_en": "The protagonist stops and looks up as the camera slowly pushes in for 3.5 seconds"},
                {"index": 2, "duration": 3.5, "shot_size": "特写", "camera_angle": "平视", "camera_move": "固定", "lighting": "均匀面光", "composition": "面部居中，眼神成为视觉焦点", "subject": "主角努力维持镇定", "action": "眼睛短暂睁大，嘴角收紧后恢复自然", "expression": "尴尬而镇定", "scene": "同一室内空间的背景虚化", "props": [], "characters": ["主角"], "first_frame_zh": "主角面部特写，努力保持镇定，均匀面光，背景虚化", "first_frame_en": "Close-up of the protagonist trying to remain calm, even frontal light, blurred background", "video_zh": "主角眼神变化后恢复镇定，镜头固定3.5秒", "video_en": "The protagonist briefly reacts with the eyes and regains composure, locked-off camera"}
            ]}
        return {"cards": [{"index": i, "prompt": "可直接复制的%s平台提示词：%s" % ("目标", str(i))} for i in range(3)]}

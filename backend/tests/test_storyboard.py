"""在没有 API Key 的前提下验证真实逻辑：注入假客户端，检查解析、重试与归一化。

运行：cd backend && .venv\\Scripts\\python -m pytest -q
"""

from __future__ import annotations

import asyncio
import dataclasses
import io
import json
from types import SimpleNamespace

import pytest
from starlette.datastructures import Headers, UploadFile

import llm
import media
import storyboard
import vision
from config import settings
from errors import MissingConfigError, UpstreamError, UploadRejected
from schemas import PALETTES, SCENES, GenerateRequest, Shot, normalize_shot, parse_shots_payload

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000d4944415478da63f8ffff3f0005fe02fea735d3a40000000049454e44ae426082"
)

VALID_PAYLOAD = {
    "shots": [
        {
            "duration": "04s",
            "scale": "特写 ECU",
            "lens": "85mm",
            "move": "急速推镜 Crash Zoom",
            "title": "铜锣无风自鸣",
            "description": "铜锣震颤，尘埃浮动。",
            "prompt": "金色头箍, 战士, 古戏台铜锣自鸣",
            "runwayPrompt": "An 85mm extreme close-up of a vibrating bronze gong",
            "palette": PALETTES[0],
        },
        {
            "duration": "06s",
            "scale": "全景 WS",
            "lens": "28mm",
            "move": "低机位升格 Low angle",
            "title": "帷幕掀起",
            "description": "褪色戏幕无风自启。",
            "prompt": "金色头箍, 战士, 戏幕掀起",
            "runwayPrompt": "A 28mm wide shot, faded curtains lift",
            "palette": PALETTES[2],
        },
    ]
}


class FakeCompletions:
    """记录调用参数，按顺序返回预置的 content。"""

    def __init__(self, contents: list[str]):
        self._contents = list(contents)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self._contents.pop(0) if self._contents else ""
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


def fake_client(*contents: str) -> SimpleNamespace:
    completions = FakeCompletions(list(contents))
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def request(**overrides) -> GenerateRequest:
    payload = {"idea": "黄昏古戏台，铜锣自鸣", "style": "燃向踩点", "anchors": ["golden circlet"]}
    payload.update(overrides)
    return GenerateRequest(**payload)


# --------------------------------------------------------------------------- #
# 归一化
# --------------------------------------------------------------------------- #


def test_normalize_fixes_drifting_model_output():
    raw = {
        "duration": "5 秒",
        "scale": "wide shot",
        "lens": "135mm",
        "move": "",
        "title": "",
        "description": "",
        "prompt": "",
        "runwayPrompt": "A cool night shot of rain",
        "palette": "from-blue-500",
    }
    shot = Shot(**normalize_shot(raw, 0))
    assert shot.duration == "05s"
    assert shot.scale == "全景 WS"
    assert shot.lens == "85mm"  # 135mm 就近收敛到 85mm
    assert shot.move == "缓慢横移 Truck"
    assert shot.title == "镜头 1"
    assert shot.palette == PALETTES[1]  # 命中 "night"/"rain" 关键词 → 冷蓝
    assert shot.prompt == shot.runwayPrompt  # 缺失的一侧由另一侧补齐


def test_normalize_keeps_palette_and_scene_inside_contract():
    for index in range(10):
        shot = Shot(**normalize_shot({"title": f"镜头 {index}"}, index))
        assert shot.palette in PALETTES
        assert shot.scene in SCENES
        assert 3 <= int(shot.duration[:2]) <= 6


def test_parse_rejects_empty_payload():
    with pytest.raises(ValueError):
        parse_shots_payload({"shots": []})
    with pytest.raises(ValueError):
        parse_shots_payload("不是 JSON 结构")


def test_parse_accepts_bare_array():
    shots = parse_shots_payload(VALID_PAYLOAD["shots"])
    assert len(shots) == 2
    assert shots[1].id == 2


# --------------------------------------------------------------------------- #
# 正向生成
# --------------------------------------------------------------------------- #


def test_generate_returns_normalized_shots():
    client = fake_client(json.dumps(VALID_PAYLOAD, ensure_ascii=False))
    shots = asyncio.run(storyboard.generate_shots(request(), client=client))
    assert [shot.id for shot in shots] == [1, 2]
    assert shots[0].palette == PALETTES[0]
    call = client.chat.completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["temperature"] == 0.9
    assert "golden circlet" in json.dumps(call["messages"], ensure_ascii=False)


def test_generate_retries_with_lower_temperature_then_succeeds():
    client = fake_client("这不是 JSON", json.dumps(VALID_PAYLOAD, ensure_ascii=False))
    shots = asyncio.run(storyboard.generate_shots(request(), client=client))
    assert len(shots) == 2
    temperatures = [call["temperature"] for call in client.chat.completions.calls]
    assert temperatures == [0.9, 0.4]


def test_generate_raises_when_model_never_returns_valid_json():
    client = fake_client("坏数据", "还是坏数据")
    with pytest.raises(UpstreamError):
        asyncio.run(storyboard.generate_shots(request(), client=client))


def test_generate_without_api_key_reports_missing_config(monkeypatch):
    monkeypatch.setattr(llm, "settings", dataclasses.replace(settings, llm_api_key=None))
    llm.text_client.cache_clear()
    try:
        with pytest.raises(MissingConfigError):
            asyncio.run(storyboard.generate_shots(request()))
    finally:
        llm.text_client.cache_clear()


# --------------------------------------------------------------------------- #
# 逆向解析
# --------------------------------------------------------------------------- #


def test_analyze_frames_sends_every_frame_and_returns_shots():
    client = fake_client(json.dumps(VALID_PAYLOAD, ensure_ascii=False))
    frames = [b"frame-one", b"frame-two"]
    shots = asyncio.run(
        vision.analyze_frames(frames, ["golden circlet"], "即梦 Jimeng", context="共 2 帧", client=client)
    )
    assert len(shots) == 2
    content = client.chat.completions.calls[0]["messages"][1]["content"]
    images = [part for part in content if part["type"] == "image_url"]
    assert len(images) == 2
    assert images[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_analyze_frames_rejects_empty_frames():
    with pytest.raises(UpstreamError):
        asyncio.run(vision.analyze_frames([], [], "即梦 Jimeng"))


# --------------------------------------------------------------------------- #
# 上传校验
# --------------------------------------------------------------------------- #


def upload(data: bytes, content_type: str, filename: str = "a.png") -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=filename, headers=Headers({"content-type": content_type}))


def test_save_upload_accepts_png_and_cleans_up():
    saved = asyncio.run(media.save_upload(upload(PNG_1X1, "image/png")))
    try:
        assert saved.path.exists()
        assert saved.is_video is False
        assert saved.size == len(PNG_1X1)
        assert media.extract_keyframes(saved) == [PNG_1X1]  # 图片直接返回原图
    finally:
        saved.cleanup()
    assert not saved.path.parent.exists()


def test_save_upload_rejects_unsupported_type():
    with pytest.raises(UploadRejected):
        asyncio.run(media.save_upload(upload(b"x", "application/pdf", "a.pdf")))


def test_save_upload_rejects_empty_file():
    with pytest.raises(UploadRejected):
        asyncio.run(media.save_upload(upload(b"", "image/png")))

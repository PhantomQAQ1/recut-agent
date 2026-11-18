"""逆向 Agent 适配层测试：字段映射与环境开关。

不依赖真实视频和视觉模型——只验证映射规则与降级行为。
"""

from __future__ import annotations

import os

import pytest

import reverse_mcp
from schemas import Shot


def test_scale_mapping_covers_all_levels():
    assert reverse_mcp._scale("大远景") == "大远景 ELS"
    assert reverse_mcp._scale("全景") == "全景 WS"
    assert reverse_mcp._scale("中近景") == "中景 MS"
    assert reverse_mcp._scale("大特写") == "特写 ECU"
    assert reverse_mcp._scale("未知景别") is None
    assert reverse_mcp._scale(None) is None


def test_move_mapping_hits_frontend_options():
    assert reverse_mcp._move("缓慢推近") == "急速推镜 Crash Zoom"
    assert reverse_mcp._move("locked-off camera") == "固定机位 Static"
    assert reverse_mcp._move("环绕") == "环绕跟拍 Orbit"
    assert reverse_mcp._move("") is None


def test_card_maps_to_shot_contract():
    shot = {
        "id": "s1",
        "index": 1,
        "start": 0.0,
        "end": 4.2,
        "duration": 4.2,
        "observation": {
            "subject": "保洁员在擦桌子",
            "action": "缓慢抬头",
            "scene": "空旷会议室",
            "shot_size": "中景",
            "camera_move": "固定",
            "lighting": "顶部柔光",
            "composition": "人物偏左",
            "confidence": 0.72,
        },
    }
    prompts = {
        "video": {"zh": "保洁员停下动作缓慢抬头", "en": "The cleaner stops and looks up"},
        "first_frame": {"zh": "会议室全景首帧", "en": ""},
    }
    result = reverse_mcp._to_shot(shot, prompts, 1)

    assert isinstance(result, Shot)
    assert result.duration == "04s"
    assert result.scale == "中景 MS"
    assert result.lens == "50mm"
    assert result.move == "固定机位 Static"
    assert "保洁员在擦桌子" in result.title
    assert result.prompt == "保洁员停下动作缓慢抬头"
    assert result.runwayPrompt == "The cleaner stops and looks up"
    assert "空旷会议室" in result.description


def test_short_shot_is_clamped_into_allowed_range():
    shot = {"start": 0.0, "end": 1.0, "observation": {}, "duration": 1.0}
    result = reverse_mcp._to_shot(shot, {}, 1)
    assert result.duration == "03s"


def test_anchors_are_prefixed_once():
    shot = {"start": 0.0, "end": 4.0, "observation": {}, "duration": 4.0}
    base = reverse_mcp._to_shot(shot, {"video": {"zh": "角色走进房间", "en": ""}}, 1)
    once = reverse_mcp._apply_anchors(base, ["silhouette"])
    twice = reverse_mcp._apply_anchors(once, ["silhouette"])
    assert once.prompt.startswith("silhouette，")
    assert twice.prompt == once.prompt


def test_engine_toggle_is_opt_in(monkeypatch):
    monkeypatch.delenv("REVERSE_ENGINE", raising=False)
    assert reverse_mcp.enabled() is False
    monkeypatch.setenv("REVERSE_ENGINE", "mcp")
    assert reverse_mcp.enabled() is True


def test_availability_reports_missing_modules(monkeypatch):
    """依赖齐全时 available；模拟缺失时应列出名字而不是抛异常。"""
    ok, missing = reverse_mcp.availability()
    if ok:
        assert missing == []
    else:
        assert missing
    monkeypatch.setattr(reverse_mcp, "_REQUIRED_MODULES", ("definitely_missing_module",))
    ok_after, missing_after = reverse_mcp.availability()
    assert ok_after is False
    assert "definitely_missing_module" in missing_after


def test_analyze_video_rejects_when_vision_not_configured(monkeypatch, tmp_path):
    """没有视觉模型配置时必须明确报错，不能伪造结果。"""
    from errors import UpstreamError

    monkeypatch.setenv("REVERSE_ENGINE", "mcp")
    # settings 是 frozen dataclass，直接替换配置探测函数更稳妥
    monkeypatch.setattr(reverse_mcp, "_configure_vision", lambda: False)

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00")

    import asyncio

    with pytest.raises(UpstreamError):
        asyncio.run(reverse_mcp.analyze_video(video))

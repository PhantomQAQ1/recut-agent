"""Chinese prompt and project exporters for reverse-storyboard results.

All generated language is assembled from observed values. Platform labels only
change the wording advice; they do not imply vendor-specific syntax.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import tempfile
from typing import Any


_FIELDS = (
    ("subject", "主体"),
    ("action", "动作"),
    ("scene", "场景"),
    ("shot_size", "景别"),
    ("camera_angle", "机位角度"),
    ("camera_move", "运镜"),
    ("lighting", "光线"),
    ("composition", "构图"),
    ("style", "风格"),
)
_PLATFORMS = {"generic", "jimeng", "kling", "runway", "seedance"}
_PLATFORM_NAMES = {
    "generic": "通用",
    "jimeng": "即梦",
    "kling": "可灵",
    "runway": "Runway",
    "seedance": "Seedance",
}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _observed(observation: dict[str, Any]) -> list[str]:
    lines = []
    for key, label in _FIELDS:
        value = _text(observation.get(key))
        if value is not None:
            lines.append(f"{label}：{value}")
    uncertainties = observation.get("uncertainties")
    if isinstance(uncertainties, (list, tuple)):
        for item in uncertainties:
            value = _text(item)
            if value:
                lines.append(f"待确认：{value}")
    elif (value := _text(uncertainties)):
        lines.append(f"待确认：{value}")
    return lines


def build_prompts(observation: dict, duration: float, platform: str = "generic") -> dict:
    """Build first-frame, video, and tail-frame Chinese prompt strings.

    Missing observations are kept missing; an unknown camera move is never
    turned into a prescribed move, and no tail-frame content is invented.
    Platform selection is descriptive guidance only, not official syntax.
    """
    if not isinstance(observation, dict):
        observation = {}
    platform_key = platform if isinstance(platform, str) and platform in _PLATFORMS else "generic"
    platform_note = f"表述建议（{_PLATFORM_NAMES[platform_key]}，非官方语法）"
    duration_text = _text(duration)
    duration_text = duration_text if duration_text is not None else "未知"

    first = _text(observation.get("first_frame"))
    if first is None:
        first = "；".join(_observed(observation)) or "首帧内容未提供"
    first_prompt = f"首帧画面：{first}。{platform_note}：仅描述已知画面信息。"

    video_parts = _observed(observation)
    move = _text(observation.get("camera_move"))
    if move is None:
        video_parts.append("运镜方式未知，保持未指定")
    chars = observation.get("characters")
    if isinstance(chars, (list, tuple)):
        names = []
        for item in chars:
            if isinstance(item, dict):
                label = _text(item.get("label")) or _text(item.get("name"))
                appearance = _text(item.get("appearance"))
                if label and appearance:
                    names.append(f"{label}（{appearance}）")
                elif label or appearance:
                    names.append(label or appearance)
            elif (value := _text(item)):
                names.append(value)
        if names:
            video_parts.append("人物/角色：" + "、".join(names))
    elif isinstance(chars, dict):
        label = _text(chars.get("label")) or _text(chars.get("name"))
        appearance = _text(chars.get("appearance"))
        if label or appearance:
            video_parts.append("人物/角色：" + "（".join(filter(None, (label, appearance))) + ("）" if label and appearance else ""))
    elif (value := _text(chars)):
        video_parts.append("人物/角色：" + value)
    video_text = "；".join(dict.fromkeys(video_parts)) or "画面内容未提供"
    video_prompt = f"时长约{duration_text}秒。{video_text}。{platform_note}：作为措辞参考，不代表平台官方格式。"

    tail = _text(observation.get("last_frame"))
    if tail is None:
        tail = "尾帧内容未知，未提供尾帧描述；不要据此补造画面"
    tail_prompt = f"尾帧画面：{tail}。{platform_note}：仅使用明确提供的尾帧信息。"
    return {"first_frame": first_prompt, "video": video_prompt, "tail_frame": tail_prompt}


def _cell(value: Any) -> str:
    """Escape Markdown table content, including embedded line breaks."""
    text = _text(value)
    if text is None:
        return "—"
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;").replace("\r\n", "<br>").replace("\n", "<br>").replace("\r", "<br>")


def _shot_status(shot: dict[str, Any]) -> str:
    status = _text(shot.get("status"))
    if status:
        return status
    observation = shot.get("observation")
    if observation is None:
        return "待分析"
    return "已分析" if isinstance(observation, dict) and observation else "待分析"


def _frames(shot: dict[str, Any]) -> str:
    frames = shot.get("frames")
    if not isinstance(frames, list):
        return "—"
    result = []
    for frame in frames:
        if isinstance(frame, dict):
            timestamp = frame.get("timestamp", frame.get("time"))
            if timestamp is not None:
                result.append(f"{_cell(timestamp)} 秒")
    return "、".join(result) if result else "—"


def _prompt_text(shot: dict[str, Any]) -> str:
    prompts = shot.get("prompts")
    if not isinstance(prompts, dict):
        return "—"
    return "；".join(f"{key}：{value}" for key, item in prompts.items() if (value := _text(item))) or "—"


def render_markdown(project: dict) -> str:
    """Render a readable report that makes gaps and evidence limits visible."""
    if not isinstance(project, dict):
        project = {}
    title = _cell(project.get("title") or project.get("name") or "反向分镜导出")
    shots = project.get("shots")
    if not isinstance(shots, list):
        shots = []
    lines = [f"# {title}", "", "> 本报告仅整理已有观测；未分析镜头会明确标注。没有执行音频分析。", ""]
    lines += [
        "## 镜头", "",
        "| 镜头 | 时间范围（秒） | 时长（秒） | 状态 | 证据帧时间（秒） | 运镜/不确定项 | 提示词 |",
        "|---|---:|---:|---|---|---|---|",
    ]
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        ident = shot.get("id")
        start, end = shot.get("start"), shot.get("end")
        interval = f"{_cell(start)}–{_cell(end)}" if start is not None or end is not None else "—"
        observation = shot.get("observation") if isinstance(shot.get("observation"), dict) else {}
        move = _text(observation.get("camera_move")) or "运镜未知"
        uncertainty = observation.get("uncertainties")
        if isinstance(uncertainty, (list, tuple)):
            uncertainty_text = "；".join(filter(None, (_text(item) for item in uncertainty)))
        else:
            uncertainty_text = _text(uncertainty) or ""
        move_text = move + (f"；待确认：{uncertainty_text}" if uncertainty_text else "")
        lines.append("| " + " | ".join((
            _cell(ident), interval, _cell(shot.get("duration")), _cell(_shot_status(shot)),
            _frames(shot), _cell(move_text), _cell(_prompt_text(shot)),
        )) + " |")
    if not shots:
        lines.append("| — | — | — | 待分析 | — | 运镜未知 | — |")
    lines += ["", "## 分析范围", "", "- 未提供或状态为待分析的镜头没有内容结论。", "- 运镜字段缺失或为空时保持未知，不指定固定运镜。", "- 未进行音频分析；本报告不描述对白、音乐或音效。"]
    limitations = project.get("limitations")
    if isinstance(limitations, list) and limitations:
        lines += ["", "## 其他限制", ""]
        lines.extend(f"- {_cell(item)}" for item in limitations if _text(item))
    return "\n".join(lines) + "\n"


def _prompt_pair(value: Any) -> dict[str, str] | None:
    if isinstance(value, dict):
        zh = _text(value.get("zh")) or ""
        en = _text(value.get("en")) or ""
        return {"zh": zh, "en": en}
    text = _text(value)
    return {"zh": text or "", "en": ""} if text is not None else None


def _shot_card(shot: dict[str, Any]) -> dict[str, Any]:
    observation = shot.get("observation") if isinstance(shot.get("observation"), dict) else {}
    prompts = shot.get("prompts") if isinstance(shot.get("prompts"), dict) else {}
    last_frame = _text(observation.get("last_frame"))
    chars = observation.get("characters")
    characters = chars if isinstance(chars, list) else []
    return {
        "id": _text(shot.get("id")),
        "index": shot.get("index"),
        "duration": shot.get("duration"),
        "shot_size": observation.get("shot_size"),
        "camera_angle": observation.get("camera_angle"),
        "camera_move": observation.get("camera_move"),
        "lighting": observation.get("lighting"),
        "composition": observation.get("composition"),
        "subject": observation.get("subject"),
        "action": observation.get("action"),
        "expression": observation.get("expression"),
        "scene": observation.get("scene"),
        "props": observation.get("props") if isinstance(observation.get("props"), list) else None,
        "characters": characters,
        "prompts": {
            "first_frame": _prompt_pair(prompts.get("first_frame")),
            "video": _prompt_pair(prompts.get("video")),
            "tail_frame": _prompt_pair(prompts.get("tail_frame")) if last_frame is not None else None,
        },
        "platform_variants": {},
        "source": "reverse",
        "source_start": shot.get("start"),
        "source_end": shot.get("end"),
        "source_frames": [i for i in observation.get("evidence_frames", [])
                          if isinstance(i, int) and 0 <= i < len(shot.get("frames", []))],
        "continuity_notes": None,
        "review_flags": ["needs_review"] + (["camera_move"] if observation.get("camera_move") is None else []),
        "confidence": observation.get("confidence"),
        "evidence": [str(f.get("timestamp")) for f in shot.get("frames", []) if isinstance(f, dict) and f.get("timestamp") is not None],
    }


def to_shot_plan(project: dict) -> dict:
    """Return backend ShotPlan-shaped data; strict validation still needs review."""
    if not isinstance(project, dict):
        project = {}
    shots = project.get("shots")
    cards = [_shot_card(shot) for shot in shots if isinstance(shot, dict)] if isinstance(shots, list) else []
    platform = _text(project.get("platform"))
    if platform == "generic" or platform not in {"kling", "jimeng", "runway", "seedance", "sora", "midjourney"}:
        platform = None
    return {
        "brief": _text(project.get("brief")) or "",
        "style": _text(project.get("style")),
        "target_duration": project.get("duration"),
        "platform": platform,
        "cards": cards,
        "replace_slots": [],
        "title": _text(project.get("title") or project.get("name")) or "",
        "logline": _text(project.get("logline")) or "",
        "compatibility": {"status": "needs_review", "needs_review": True,
                          "note": "字段包含未知值，未必通过旧版严格验证器"},
    }


def export_project(project: dict, output_dir: Path, format: str) -> Path:
    """Atomically write one of the fixed-name project exports."""
    names = {"json": "storyboard.json", "markdown": "storyboard.md", "csv": "storyboard.csv", "shot-plan": "shot-plan.json"}
    if format not in names:
        raise ValueError("format must be json, markdown, csv, or shot-plan")
    destination_dir = Path(output_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / names[format]
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=destination_dir, prefix=f".{destination.name}.", suffix=".tmp", delete=False) as stream:
            temporary_path = Path(stream.name)
            if format in ("json", "shot-plan"):
                value = project if format == "json" else to_shot_plan(project)
                text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
                stream.write(text.encode("utf-8"))
            elif format == "markdown":
                stream.write(render_markdown(project).encode("utf-8"))
            else:
                import io
                text_buffer = io.StringIO(newline="")
                writer = csv.writer(text_buffer)
                writer.writerow(["id", "start", "end", "duration", "status", "observation", "frames", "path", "first_frame", "video", "tail_frame"])
                shots = project.get("shots", []) if isinstance(project, dict) else []
                for shot in shots if isinstance(shots, list) else []:
                    if not isinstance(shot, dict):
                        continue
                    prompts = shot.get("prompts") if isinstance(shot.get("prompts"), dict) else {}
                    writer.writerow([
                        shot.get("id"), shot.get("start"), shot.get("end"), shot.get("duration"), _shot_status(shot),
                        json.dumps(shot.get("observation"), ensure_ascii=False) if shot.get("observation") is not None else "",
                        json.dumps(shot.get("frames"), ensure_ascii=False) if shot.get("frames") is not None else "",
                        shot.get("path") or "",
                        prompts.get("first_frame") or "", prompts.get("video") or "", prompts.get("tail_frame") or "",
                    ])
                stream.write(b"\xef\xbb\xbf" + text_buffer.getvalue().encode("utf-8"))
        os.replace(temporary_path, destination)
        temporary_path = None
        return destination
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


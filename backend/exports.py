"""导出：剪映草稿（实验性）。

重要说明
--------
剪映专业版的草稿格式**未公开、随版本变化**，这里生成的是最小可读结构：
每镜一张占位图（或用户上传的参考首帧）+ 一条文字轨写提示词。

它不保证能被任意版本导入。因此压缩包里同时附上 `shots.md` 与 `shots.csv`，
即使草稿导入失败，素材与文本清单依然可用。不要把这里当成稳定格式依赖。
"""

from __future__ import annotations

import csv
import io
import json
import struct
import uuid
import zipfile
import zlib
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

import repositories as repo
from deps import require_user
from uploads import ALLOWED as UPLOAD_SUFFIXES
from uploads import upload_root

router = APIRouter(prefix="/api/v1/projects", tags=["exports"])

# 与前端 lib/palettes.ts 的起始色保持一致
PALETTE_RGB: dict[str, tuple[int, int, int]] = {
    "from-amber-950 via-orange-950 to-slate-950": (0x45, 0x1A, 0x03),
    "from-indigo-950 via-slate-900 to-amber-950": (0x1E, 0x1B, 0x4B),
    "from-red-950 via-amber-950 to-slate-950": (0x45, 0x0A, 0x0A),
    "from-teal-950 via-emerald-950 to-slate-950": (0x04, 0x2F, 0x2E),
    "from-violet-950 via-purple-950 to-slate-950": (0x2E, 0x10, 0x65),
    "from-stone-800 via-stone-950 to-slate-950": (0x29, 0x25, 0x24),
    "from-sky-950 via-slate-900 to-indigo-950": (0x08, 0x2F, 0x49),
    "from-rose-950 via-red-950 to-stone-950": (0x4C, 0x05, 0x19),
}

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080
FPS = 30


def solid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """生成纯色 PNG。不引 Pillow：zlib + struct 足够。"""
    row = b"\x00" + bytes(rgb) * width
    raw = row * height

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _shot_seconds(duration: str) -> int:
    try:
        return max(1, int(str(duration).rstrip("s")))
    except (TypeError, ValueError):
        return 4


def _palette_rgb(palette: str) -> tuple[int, int, int]:
    return PALETTE_RGB.get(palette, (0x24, 0x13, 0x0E))


def _shot_markdown(project_name: str, shots: list[dict[str, Any]]) -> str:
    lines = [f"# {project_name}", ""]
    for index, shot in enumerate(shots, start=1):
        lines.append(f"## SHOT {index:02d} · {shot.get('title', '')}")
        lines.append("")
        lines.append(
            f"- 时长：{shot.get('duration', '')} · 景别：{shot.get('scale', '')} · "
            f"焦段：{shot.get('lens', '')} · 运镜：{shot.get('move', '')}"
        )
        description = str(shot.get("description") or "").strip()
        if description:
            lines.append(f"- 画面：{description}")
        lines.append("")
        lines.append("**中文提示词**")
        lines.append("")
        lines.append("```")
        lines.append(str(shot.get("prompt") or ""))
        lines.append("```")
        lines.append("")
        lines.append("**英文提示词**")
        lines.append("")
        lines.append("```")
        lines.append(str(shot.get("runwayPrompt") or ""))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


CSV_COLUMNS = [
    "序号", "标题", "时长", "景别", "焦段", "运镜", "画面描述",
    "中文提示词", "英文提示词", "调色板", "场景",
]


def _shots_csv(shots: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for index, shot in enumerate(shots, start=1):
        writer.writerow([
            index,
            shot.get("title", ""),
            shot.get("duration", ""),
            shot.get("scale", ""),
            shot.get("lens", ""),
            shot.get("move", ""),
            shot.get("description", ""),
            shot.get("prompt", ""),
            shot.get("runwayPrompt", ""),
            shot.get("palette", ""),
            shot.get("scene", ""),
        ])
    return "\ufeff" + buffer.getvalue()  # BOM，Excel 直接打开不乱码


def _draft_content(project_name: str, shots: list[dict[str, Any]]) -> dict[str, Any]:
    """尽力构造剪映草稿结构。字段名参考社区逆向结果，不保证版本兼容。"""
    draft_id = str(uuid.uuid4()).upper()
    video_materials: list[dict[str, Any]] = []
    text_materials: list[dict[str, Any]] = []
    video_segments: list[dict[str, Any]] = []
    text_segments: list[dict[str, Any]] = []

    cursor_us = 0
    for index, shot in enumerate(shots, start=1):
        seconds = _shot_seconds(shot.get("duration", "04s"))
        duration_us = seconds * 1_000_000
        image_name = f"shot-{index:02d}.png"
        material_id = str(uuid.uuid4()).upper()

        video_materials.append({
            "id": material_id,
            "type": "photo",
            "path": f"materials/{image_name}",
            "duration": duration_us,
            "width": CANVAS_WIDTH,
            "height": CANVAS_HEIGHT,
            "material_name": image_name,
        })
        video_segments.append({
            "id": str(uuid.uuid4()).upper(),
            "material_id": material_id,
            "target_timerange": {"start": cursor_us, "duration": duration_us},
            "source_timerange": {"start": 0, "duration": duration_us},
        })

        text_id = str(uuid.uuid4()).upper()
        prompt = str(shot.get("prompt") or "").strip()
        text_materials.append({
            "id": text_id,
            "type": "text",
            "content": f"SHOT {index:02d}｜{shot.get('title', '')}\n{prompt}",
        })
        text_segments.append({
            "id": str(uuid.uuid4()).upper(),
            "material_id": text_id,
            "target_timerange": {"start": cursor_us, "duration": duration_us},
        })
        cursor_us += duration_us

    return {
        "id": draft_id,
        "name": project_name,
        "version": 360000,
        "fps": FPS,
        "canvas_config": {
            "width": CANVAS_WIDTH,
            "height": CANVAS_HEIGHT,
            "ratio": "16:9",
        },
        "duration": cursor_us,
        "materials": {"videos": video_materials, "texts": text_materials},
        "tracks": [
            {"type": "video", "segments": video_segments},
            {"type": "text", "segments": text_segments},
        ],
    }


def _draft_meta(project_name: str, draft_id: str) -> dict[str, Any]:
    return {
        "draft_id": draft_id,
        "draft_name": project_name,
        "draft_fold_path": "",
        "draft_root_path": "",
        "tm_duration": 0,
        "tm_draft_create": 0,
        "tm_draft_modified": 0,
    }


READ_ME = """ReCut Agent · 剪映草稿（实验性）
=====================================

这是一个「占位图 + 文字轨」的最小草稿：
- materials/shot-XX.png 是每镜的占位图（有参考首帧时用你的图）
- 文字轨按镜头顺序写入中文提示词

重要：剪映专业版的草稿格式未公开且随版本变化，本文件不保证能被任意版本导入。
如果导入失败，请直接使用同目录下的：
- shots.md   人读版分镜表（含中英提示词）
- shots.csv  表格版，可直接用 Excel 打开

把整个文件夹放到剪映的草稿目录下，或在剪映里尝试「导入草稿」。
"""


@router.get("/{project_id}/export/jianying")
def export_jianying(project_id: int, user=Depends(require_user)) -> Response:
    project = repo.get_project(user.id, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    storyboard = project.storyboard or {}
    shots = storyboard.get("shots") or []
    if not isinstance(shots, list) or not shots:
        raise HTTPException(status_code=422, detail="当前项目还没有镜头，无法导出")

    project_name = project.name or "未命名项目"
    draft_id = str(uuid.uuid4()).upper()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        root = "recut-draft"
        archive.writestr(f"{root}/draft_content.json", json.dumps(_draft_content(project_name, shots), ensure_ascii=False, indent=2))
        archive.writestr(f"{root}/draft_meta_info.json", json.dumps(_draft_meta(project_name, draft_id), ensure_ascii=False, indent=2))
        archive.writestr(f"{root}/README.txt", READ_ME)
        archive.writestr(f"{root}/shots.md", _shot_markdown(project_name, shots))
        archive.writestr(f"{root}/shots.csv", _shots_csv(shots))

        for index, shot in enumerate(shots, start=1):
            image_name = f"materials/shot-{index:02d}.png"
            reference_id = shot.get("reference_image_id")
            data: bytes | None = None
            if isinstance(reference_id, int):
                data = _load_reference(user.id, reference_id)
            if data is None:
                data = solid_png(64, 36, _palette_rgb(str(shot.get("palette") or "")))
            archive.writestr(f"{root}/{image_name}", data)

    filename = f"{project_name}-jianying-draft.zip"
    # HTTP 头只能放 latin-1，中文文件名必须用 RFC 5987 的 filename* 形式。
    disposition = (
        'attachment; filename="recut-draft.zip"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": disposition},
    )


def _load_reference(user_id: int, upload_id: int) -> bytes | None:
    import db

    with db.connect() as conn:
        row = conn.execute(
            "SELECT sha256, mime FROM uploads WHERE id = ? AND user_id = ?",
            (upload_id, user_id),
        ).fetchone()
    if row is None:
        return None
    path = upload_root() / f"{row['sha256']}{UPLOAD_SUFFIXES.get(row['mime'], '')}"
    return path.read_bytes() if path.exists() else None

"""参考首帧的上传与读取。

设计要点：
- 文件按 sha256 命名落盘，同一张图重复上传自动复用（省空间、省带宽）。
- 图片**必须鉴权访问**：不做公开静态目录，否则换个 id 就能看别人的素材。
- 不引入 Pillow：宽高只在能轻量解析的格式里填，其余留空，前端靠 object-fit 自适应。
"""

from __future__ import annotations

import hashlib
import io
import struct
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

import db
from config import settings
from deps import require_user

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])

ALLOWED = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
MAX_BYTES = 5 * 1024 * 1024
CHUNK = 512 * 1024


def upload_root() -> Path:
    root = Path(settings.upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _image_size(data: bytes) -> tuple[int | None, int | None]:
    """只解析 PNG / JPEG 的尺寸，其余返回空（不引依赖）。"""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            width, height = struct.unpack(">II", data[16:24])
            return int(width), int(height)
        if data[:2] == b"\xff\xd8":
            index = 2
            while index < len(data) - 9:
                if data[index] != 0xFF:
                    index += 1
                    continue
                marker = data[index + 1]
                length = struct.unpack(">H", data[index + 2 : index + 4])[0]
                if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB}:
                    height, width = struct.unpack(">HH", data[index + 5 : index + 9])
                    return int(width), int(height)
                index += 2 + length
    except (struct.error, ValueError):
        return None, None
    return None, None


def _row(cursor_row) -> dict[str, Any]:
    return {
        "id": cursor_row["id"],
        "url": f"/api/v1/uploads/{cursor_row['id']}",
        "mime": cursor_row["mime"],
        "bytes": cursor_row["bytes"],
        "width": cursor_row["width"],
        "height": cursor_row["height"],
    }


@router.post("")
async def create_upload(
    file: UploadFile = File(...), user=Depends(require_user)
) -> dict[str, Any]:
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED:
        raise HTTPException(status_code=422, detail="只支持 PNG / JPEG / WEBP 图片")

    buffer = io.BytesIO()
    while chunk := await file.read(CHUNK):
        buffer.write(chunk)
        if buffer.tell() > MAX_BYTES:
            raise HTTPException(status_code=413, detail="图片超过 5MB 上限")
    await file.close()
    data = buffer.getvalue()
    if not data:
        raise HTTPException(status_code=422, detail="上传的图片是空文件")

    digest = hashlib.sha256(data).hexdigest()
    with db.connect() as conn:
        existing = conn.execute(
            "SELECT * FROM uploads WHERE user_id = ? AND sha256 = ?", (user.id, digest)
        ).fetchone()
        if existing is not None:
            return _row(existing)

    width, height = _image_size(data)
    suffix = ALLOWED[mime]
    path = upload_root() / f"{digest}{suffix}"
    if not path.exists():
        path.write_bytes(data)

    with db.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO uploads (user_id, sha256, mime, bytes, width, height, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user.id, digest, mime, len(data), width, height, db.now_iso()),
        )
        row = conn.execute(
            "SELECT * FROM uploads WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return _row(row)


@router.get("/{upload_id}")
def read_upload(upload_id: int, user=Depends(require_user)) -> FileResponse:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM uploads WHERE id = ? AND user_id = ?", (upload_id, user.id)
        ).fetchone()
    if row is None:
        # 别人的图片同样返回 404，避免用状态码探测 id 是否存在
        raise HTTPException(status_code=404, detail="图片不存在")

    path = upload_root() / f"{row['sha256']}{ALLOWED.get(row['mime'], '')}"
    if not path.exists():
        raise HTTPException(status_code=404, detail="图片文件已丢失")
    return FileResponse(
        path,
        media_type=row["mime"],
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )

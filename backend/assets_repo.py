"""角色与标签的数据访问。

约定：
- 所有函数都以 `user_id` 过滤，别人的资产既查不到也改不了。
- 多语句改写一律放在 `db.transaction()` 里，整体成功或整体回滚。
- 任何改动都会递增 `characters.version`，让别的窗口的旧副本失效。
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import db
import presets
from errors import ConflictError, TagInUseError, ValidationRejected, VersionConflictError


# --------------------------------------------------------------------------- #
# 名称归一化
# --------------------------------------------------------------------------- #


def clean_name(raw: str) -> str:
    """展示用名称：全角转半角、折叠空白、去首尾空白。"""
    text = unicodedata.normalize("NFKC", raw or "")
    return re.sub(r"\s+", " ", text).strip()


def normalize_key(raw: str) -> str:
    """查重用的键：再额外去掉所有空白并转小写。

    这样「金色头箍」「金色头 箍」「金色头箍 」会命中同一条标签，
    这正是边界情况①要求的去重口径。
    """
    return re.sub(r"\s+", "", clean_name(raw)).lower()


# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Tag:
    id: int
    name: str
    category: str
    tone: str
    usage_count: int = 0

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "tone": self.tone,
            "usage_count": self.usage_count,
        }


@dataclass(frozen=True)
class Character:
    id: int
    name: str
    role_label: str
    description: str
    consistency: float | None
    prompt_anchor: str
    tone: str
    version: int
    tags: tuple[Tag, ...]
    created_at: str
    updated_at: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role_label": self.role_label,
            "description": self.description,
            "consistency": self.consistency,
            "prompt_anchor": self.prompt_anchor,
            "tone": self.tone,
            "version": self.version,
            "tags": [tag.public() for tag in self.tags],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @property
    def tag_ids(self) -> list[int]:
        return [tag.id for tag in self.tags]


def _tag_from_row(row: sqlite3.Row) -> Tag:
    usage = row["usage_count"] if "usage_count" in row.keys() else 0
    return Tag(
        id=row["id"],
        name=row["name"],
        category=row["category"],
        tone=row["tone"],
        usage_count=int(usage or 0),
    )


def _character_from_row(row: sqlite3.Row, tags: Sequence[Tag]) -> Character:
    return Character(
        id=row["id"],
        name=row["name"],
        role_label=row["role_label"],
        description=row["description"],
        consistency=row["consistency"],
        prompt_anchor=row["prompt_anchor"],
        tone=row["tone"],
        version=row["version"],
        tags=tuple(tags),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# --------------------------------------------------------------------------- #
# 首次播种
# --------------------------------------------------------------------------- #


def ensure_seeded(user_id: int) -> bool:
    """为用户播种初始预设，返回是否真的写入。

    `users.assets_seeded_at` 是"只播一次"的标记：用户把预设删光之后，
    再打开页面也不会被重新塞回来（否则删不掉，非常烦人）。
    """
    with db.transaction() as conn:
        row = conn.execute(
            "SELECT assets_seeded_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None or row["assets_seeded_at"]:
            return False

        now = db.now_iso()
        has_characters = conn.execute(
            "SELECT COUNT(*) AS total FROM characters WHERE user_id = ?", (user_id,)
        ).fetchone()["total"]

        if not has_characters:
            tag_ids: dict[str, int] = {}
            for preset in presets.PRESET_TAGS:
                key = normalize_key(preset.name)
                cursor = conn.execute(
                    """
                    INSERT INTO tags (user_id, name, name_key, category, tone, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, preset.name, key, preset.category, preset.tone, now, now),
                )
                if cursor.rowcount:
                    tag_ids[key] = int(cursor.lastrowid or 0)
                else:
                    existing = conn.execute(
                        "SELECT id FROM tags WHERE user_id = ? AND name_key = ?",
                        (user_id, key),
                    ).fetchone()
                    if existing:
                        tag_ids[key] = int(existing["id"])

            for preset in presets.PRESET_CHARACTERS:
                cursor = conn.execute(
                    """
                    INSERT INTO characters
                        (user_id, name, name_key, role_label, description, consistency,
                         prompt_anchor, tone, version, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, NULL, ?, ?, 1, ?, ?)
                    """,
                    (
                        user_id,
                        preset.name,
                        normalize_key(preset.name),
                        preset.role_label,
                        preset.description,
                        preset.prompt_anchor,
                        preset.tone,
                        now,
                        now,
                    ),
                )
                character_id = int(cursor.lastrowid or 0)
                for tag_name in preset.tags:
                    tag_id = tag_ids.get(normalize_key(tag_name))
                    if tag_id:
                        conn.execute(
                            "INSERT OR IGNORE INTO character_tags (character_id, tag_id, created_at) VALUES (?, ?, ?)",
                            (character_id, tag_id, now),
                        )

        conn.execute(
            "UPDATE users SET assets_seeded_at = ? WHERE id = ?", (now, user_id)
        )
        return True


# --------------------------------------------------------------------------- #
# 标签
# --------------------------------------------------------------------------- #


def list_tags(user_id: int, *, category: str | None = None) -> list[Tag]:
    sql = """
        SELECT t.*, COUNT(ct.character_id) AS usage_count
          FROM tags t
          LEFT JOIN character_tags ct ON ct.tag_id = t.id
         WHERE t.user_id = ?
    """
    params: list[Any] = [user_id]
    if category:
        sql += " AND t.category = ?"
        params.append(category)
    sql += " GROUP BY t.id ORDER BY t.category, t.name"
    with db.connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_tag_from_row(row) for row in rows]


def get_tag(user_id: int, tag_id: int) -> Tag | None:
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT t.*, COUNT(ct.character_id) AS usage_count
              FROM tags t
              LEFT JOIN character_tags ct ON ct.tag_id = t.id
             WHERE t.user_id = ? AND t.id = ?
             GROUP BY t.id
            """,
            (user_id, tag_id),
        ).fetchone()
    return _tag_from_row(row) if row else None


def _find_tag_by_key(conn: sqlite3.Connection, user_id: int, key: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM tags WHERE user_id = ? AND name_key = ?", (user_id, key)
    ).fetchone()


def create_tag(user_id: int, *, name: str, category: str, tone: str) -> tuple[Tag, bool]:
    """创建标签。重名时不报错，直接返回已有标签（`created=False`）。

    这是边界情况①的落点：前端拿到 `created=False` 就可以提示"已存在，直接使用"，
    避免用户反复试同一个名字。
    """
    display = clean_name(name)
    if not display:
        raise ValidationRejected("标签名不能为空")
    if len(display) > 24:
        raise ValidationRejected("标签名最多 24 个字符")
    if category not in presets.TAG_CATEGORIES:
        raise ValidationRejected(f"未知标签分组：{category}")
    if tone not in presets.TAG_TONES:
        raise ValidationRejected(f"未知配色：{tone}")

    key = normalize_key(display)
    now = db.now_iso()
    with db.transaction() as conn:
        existing = _find_tag_by_key(conn, user_id, key)
        if existing is not None:
            return get_tag(user_id, int(existing["id"])) or _tag_from_row(existing), False
        cursor = conn.execute(
            """
            INSERT INTO tags (user_id, name, name_key, category, tone, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, display, key, category, tone, now, now),
        )
        tag_id = int(cursor.lastrowid or 0)
    tag = get_tag(user_id, tag_id)
    assert tag is not None
    return tag, True


def update_tag(
    user_id: int,
    tag_id: int,
    *,
    name: str | None = None,
    category: str | None = None,
    tone: str | None = None,
) -> Tag | None:
    assignments: list[str] = []
    values: list[Any] = []
    if name is not None:
        display = clean_name(name)
        if not display:
            raise ValidationRejected("标签名不能为空")
        assignments.extend(["name = ?", "name_key = ?"])
        values.extend([display, normalize_key(display)])
    if category is not None:
        if category not in presets.TAG_CATEGORIES:
            raise ValidationRejected(f"未知标签分组：{category}")
        assignments.append("category = ?")
        values.append(category)
    if tone is not None:
        if tone not in presets.TAG_TONES:
            raise ValidationRejected(f"未知配色：{tone}")
        assignments.append("tone = ?")
        values.append(tone)
    if not assignments:
        return get_tag(user_id, tag_id)

    assignments.append("updated_at = ?")
    values.extend([db.now_iso(), tag_id, user_id])
    with db.transaction() as conn:
        if name is not None:
            clash = _find_tag_by_key(conn, user_id, normalize_key(clean_name(name)))
            if clash is not None and int(clash["id"]) != tag_id:
                raise ConflictError(f"标签「{clash['name']}」已存在")
        cursor = conn.execute(
            f"UPDATE tags SET {', '.join(assignments)} WHERE id = ? AND user_id = ?",
            values,
        )
        if cursor.rowcount == 0:
            return None
    return get_tag(user_id, tag_id)


def tag_usage(user_id: int, tag_id: int) -> list[dict[str, Any]]:
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.name
              FROM character_tags ct
              JOIN characters c ON c.id = ct.character_id
             WHERE ct.tag_id = ? AND c.user_id = ?
             ORDER BY c.name
            """,
            (tag_id, user_id),
        ).fetchall()
    return [{"id": row["id"], "name": row["name"]} for row in rows]


def delete_tag(
    user_id: int,
    tag_id: int,
    *,
    force: bool = False,
    reassign_to: int | None = None,
) -> bool:
    """删除标签，默认拒绝删除仍被引用的标签。

    - 默认：有引用 → TagInUseError（409，附引用角色）
    - `force=True`：只解绑关联，角色本身保留
    - `reassign_to=<id>`：先把关联迁到目标标签，再删本体
    """
    tag = get_tag(user_id, tag_id)
    if tag is None:
        return False

    used_by = tag_usage(user_id, tag_id)
    if reassign_to is not None:
        if reassign_to == tag_id:
            raise ValidationRejected("不能把标签重定向到它自己")
        target = get_tag(user_id, reassign_to)
        if target is None:
            raise ValidationRejected("目标标签不存在")
        if target.category != tag.category:
            raise ValidationRejected("只能在同分组之间重定向标签")
    elif used_by and not force:
        raise TagInUseError(
            f"标签「{tag.name}」仍被 {len(used_by)} 个角色使用",
            used_by,
        )

    now = db.now_iso()
    with db.transaction() as conn:
        character_ids = [
            int(row["character_id"])
            for row in conn.execute(
                "SELECT character_id FROM character_tags WHERE tag_id = ?", (tag_id,)
            )
        ]
        if reassign_to is not None:
            for character_id in character_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO character_tags (character_id, tag_id, created_at) VALUES (?, ?, ?)",
                    (character_id, reassign_to, now),
                )
        conn.execute("DELETE FROM character_tags WHERE tag_id = ?", (tag_id,))
        conn.execute("DELETE FROM tags WHERE id = ? AND user_id = ?", (tag_id, user_id))
        # 受影响的角色内容变了，递增版本让旧副本失效。
        if character_ids:
            placeholders = ",".join("?" for _ in character_ids)
            conn.execute(
                f"UPDATE characters SET version = version + 1, updated_at = ? WHERE id IN ({placeholders})",
                [now, *character_ids],
            )
    return True


# --------------------------------------------------------------------------- #
# 角色
# --------------------------------------------------------------------------- #


def _tags_for_characters(
    conn: sqlite3.Connection, character_ids: Sequence[int]
) -> dict[int, list[Tag]]:
    if not character_ids:
        return {}
    placeholders = ",".join("?" for _ in character_ids)
    rows = conn.execute(
        f"""
        SELECT ct.character_id, t.id, t.name, t.category, t.tone
          FROM character_tags ct
          JOIN tags t ON t.id = ct.tag_id
         WHERE ct.character_id IN ({placeholders})
         ORDER BY t.category, t.name
        """,
        list(character_ids),
    ).fetchall()
    grouped: dict[int, list[Tag]] = {cid: [] for cid in character_ids}
    for row in rows:
        grouped.setdefault(int(row["character_id"]), []).append(_tag_from_row(row))
    return grouped


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_characters(
    user_id: int,
    *,
    query: str | None = None,
    tag_id: int | None = None,
    category: str | None = None,
) -> list[Character]:
    joins: list[str] = []
    clauses: list[str] = ["c.user_id = ?"]
    params: list[Any] = [user_id]

    if tag_id is not None or category is not None:
        joins.append("JOIN character_tags ct ON ct.character_id = c.id")
    if category is not None:
        joins.append("JOIN tags t ON t.id = ct.tag_id")
        clauses.append("t.category = ?")
        params.append(category)
    if tag_id is not None:
        clauses.append("ct.tag_id = ?")
        params.append(tag_id)
    if query:
        like = f"%{_escape_like(clean_name(query))}%"
        clauses.append(
            "(c.name LIKE ? ESCAPE '\\' OR c.role_label LIKE ? ESCAPE '\\' OR c.description LIKE ? ESCAPE '\\')"
        )
        params.extend([like, like, like])

    sql = (
        "SELECT DISTINCT c.* FROM characters c "
        + " ".join(joins)
        + " WHERE "
        + " AND ".join(clauses)
        + " ORDER BY c.updated_at DESC, c.id DESC"
    )
    with db.connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        tags = _tags_for_characters(conn, [int(row["id"]) for row in rows])
    return [_character_from_row(row, tags.get(int(row["id"]), [])) for row in rows]


def get_character(user_id: int, character_id: int) -> Character | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM characters WHERE id = ? AND user_id = ?",
            (character_id, user_id),
        ).fetchone()
        if row is None:
            return None
        tags = _tags_for_characters(conn, [int(row["id"])])
    return _character_from_row(row, tags.get(int(row["id"]), []))


def _ensure_tags_owned(conn: sqlite3.Connection, user_id: int, tag_ids: Iterable[int]) -> list[int]:
    unique = sorted({int(item) for item in tag_ids})
    if not unique:
        return []
    placeholders = ",".join("?" for _ in unique)
    rows = conn.execute(
        f"SELECT id FROM tags WHERE user_id = ? AND id IN ({placeholders})",
        [user_id, *unique],
    ).fetchall()
    found = {int(row["id"]) for row in rows}
    missing = [item for item in unique if item not in found]
    if missing:
        raise ValidationRejected(f"标签不存在：{missing}")
    return unique


def create_character(
    user_id: int,
    *,
    name: str,
    role_label: str = "",
    description: str = "",
    prompt_anchor: str = "",
    tone: str = "amber",
    tag_ids: Sequence[int] = (),
) -> Character:
    display = clean_name(name)
    if not display:
        raise ValidationRejected("角色名不能为空")
    if len(display) > 40:
        raise ValidationRejected("角色名最多 40 个字符")
    if tone not in presets.TAG_TONES:
        raise ValidationRejected(f"未知配色：{tone}")

    now = db.now_iso()
    with db.transaction() as conn:
        exists = conn.execute(
            "SELECT id FROM characters WHERE user_id = ? AND name_key = ?",
            (user_id, normalize_key(display)),
        ).fetchone()
        if exists is not None:
            raise ConflictError(f"角色「{display}」已存在")
        owned = _ensure_tags_owned(conn, user_id, tag_ids)
        cursor = conn.execute(
            """
            INSERT INTO characters
                (user_id, name, name_key, role_label, description, consistency,
                 prompt_anchor, tone, version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, NULL, ?, ?, 1, ?, ?)
            """,
            (
                user_id,
                display,
                normalize_key(display),
                clean_name(role_label),
                description.strip(),
                prompt_anchor.strip(),
                tone,
                now,
                now,
            ),
        )
        character_id = int(cursor.lastrowid or 0)
        for tag_id in owned:
            conn.execute(
                "INSERT OR IGNORE INTO character_tags (character_id, tag_id, created_at) VALUES (?, ?, ?)",
                (character_id, tag_id, now),
            )
    character = get_character(user_id, character_id)
    assert character is not None
    return character


def update_character(
    user_id: int,
    character_id: int,
    *,
    name: str | None = None,
    role_label: str | None = None,
    description: str | None = None,
    prompt_anchor: str | None = None,
    tone: str | None = None,
    expected_version: int | None = None,
) -> Character | None:
    assignments: list[str] = []
    values: list[Any] = []
    if name is not None:
        display = clean_name(name)
        if not display:
            raise ValidationRejected("角色名不能为空")
        assignments.extend(["name = ?", "name_key = ?"])
        values.extend([display, normalize_key(display)])
    if role_label is not None:
        assignments.append("role_label = ?")
        values.append(clean_name(role_label))
    if description is not None:
        assignments.append("description = ?")
        values.append(description.strip())
    if prompt_anchor is not None:
        assignments.append("prompt_anchor = ?")
        values.append(prompt_anchor.strip())
    if tone is not None:
        if tone not in presets.TAG_TONES:
            raise ValidationRejected(f"未知配色：{tone}")
        assignments.append("tone = ?")
        values.append(tone)
    if not assignments:
        return get_character(user_id, character_id)

    assignments.extend(["version = version + 1", "updated_at = ?"])
    values.append(db.now_iso())

    where = "WHERE id = ? AND user_id = ?"
    params = [*values, character_id, user_id]
    if expected_version is not None:
        where += " AND version = ?"
        params.append(expected_version)

    with db.transaction() as conn:
        if name is not None:
            clash = conn.execute(
                "SELECT id, name FROM characters WHERE user_id = ? AND name_key = ? AND id <> ?",
                (user_id, normalize_key(clean_name(name)), character_id),
            ).fetchone()
            if clash is not None:
                raise ConflictError(f"角色「{clash['name']}」已存在")
        cursor = conn.execute(
            f"UPDATE characters SET {', '.join(assignments)} {where}", params
        )
        if cursor.rowcount == 0:
            current = conn.execute(
                "SELECT version FROM characters WHERE id = ? AND user_id = ?",
                (character_id, user_id),
            ).fetchone()
            if current is None:
                return None
            raise VersionConflictError(
                "该角色已被其他窗口修改，请刷新后重试", int(current["version"])
            )
    return get_character(user_id, character_id)


def delete_character(user_id: int, character_id: int) -> bool:
    with db.transaction() as conn:
        cursor = conn.execute(
            "DELETE FROM characters WHERE id = ? AND user_id = ?",
            (character_id, user_id),
        )
        return cursor.rowcount > 0


def add_character_tags(
    user_id: int, character_id: int, tag_ids: Sequence[int]
) -> Character | None:
    now = db.now_iso()
    with db.transaction() as conn:
        exists = conn.execute(
            "SELECT id FROM characters WHERE id = ? AND user_id = ?",
            (character_id, user_id),
        ).fetchone()
        if exists is None:
            return None
        owned = _ensure_tags_owned(conn, user_id, tag_ids)
        for tag_id in owned:
            conn.execute(
                "INSERT OR IGNORE INTO character_tags (character_id, tag_id, created_at) VALUES (?, ?, ?)",
                (character_id, tag_id, now),
            )
        conn.execute(
            "UPDATE characters SET version = version + 1, updated_at = ? WHERE id = ?",
            (now, character_id),
        )
    return get_character(user_id, character_id)


def remove_character_tags(
    user_id: int, character_id: int, tag_ids: Sequence[int]
) -> Character | None:
    now = db.now_iso()
    unique = sorted({int(item) for item in tag_ids})
    with db.transaction() as conn:
        exists = conn.execute(
            "SELECT id FROM characters WHERE id = ? AND user_id = ?",
            (character_id, user_id),
        ).fetchone()
        if exists is None:
            return None
        if unique:
            placeholders = ",".join("?" for _ in unique)
            conn.execute(
                f"DELETE FROM character_tags WHERE character_id = ? AND tag_id IN ({placeholders})",
                [character_id, *unique],
            )
            conn.execute(
                "UPDATE characters SET version = version + 1, updated_at = ? WHERE id = ?",
                (now, character_id),
            )
    return get_character(user_id, character_id)


def replace_character_tags(
    user_id: int,
    character_id: int,
    tag_ids: Sequence[int],
    *,
    expected_version: int,
) -> Character:
    """全量替换标签；必须带版本号，避免覆盖别人的修改。"""
    now = db.now_iso()
    with db.transaction() as conn:
        owned = _ensure_tags_owned(conn, user_id, tag_ids)
        cursor = conn.execute(
            "UPDATE characters SET version = version + 1, updated_at = ? WHERE id = ? AND user_id = ? AND version = ?",
            (now, character_id, user_id, expected_version),
        )
        if cursor.rowcount == 0:
            row = conn.execute(
                "SELECT version FROM characters WHERE id = ? AND user_id = ?",
                (character_id, user_id),
            ).fetchone()
            if row is None:
                raise ValidationRejected("角色不存在")
            raise VersionConflictError(
                "该角色已被其他窗口修改，请刷新后重试", int(row["version"])
            )
        conn.execute(
            "DELETE FROM character_tags WHERE character_id = ?", (character_id,)
        )
        for tag_id in owned:
            conn.execute(
                "INSERT OR IGNORE INTO character_tags (character_id, tag_id, created_at) VALUES (?, ?, ?)",
                (character_id, tag_id, now),
            )
    character = get_character(user_id, character_id)
    assert character is not None
    return character


def reset_seed_flag(user_id: int) -> None:
    """把标记位清空，下次访问重新播种（供重置脚本使用）。"""
    with db.transaction() as conn:
        conn.execute(
            "UPDATE users SET assets_seeded_at = NULL WHERE id = ?", (user_id,)
        )

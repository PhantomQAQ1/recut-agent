"""Durable JSON project store with atomic writes."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path


def project_path(data_dir: Path, project_id: str) -> Path:
    if not project_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in project_id):
        raise ValueError("invalid project id")
    return data_dir / (project_id + ".json")


def save(data_dir: Path, project: dict) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    dest = project_path(data_dir, project["id"])
    fd, name = tempfile.mkstemp(prefix=".project-", suffix=".tmp", dir=data_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(project, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, dest)
    finally:
        Path(name).unlink(missing_ok=True)


def load(data_dir: Path, project_id: str) -> dict:
    path = project_path(data_dir, project_id)
    if not path.is_file():
        raise FileNotFoundError(project_id)
    return json.loads(path.read_text(encoding="utf-8"))

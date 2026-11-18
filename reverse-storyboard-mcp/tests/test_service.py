"""Unit tests for the standalone MCP service without invoking ffmpeg or a model."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    from reverse_storyboard import server
except ModuleNotFoundError as exc:
    if exc.name != "mcp":
        raise
    server = None

_FIXTURE_ROOT = Path(tempfile.gettempdir()) / "reverse-storyboard-service-tests"


@unittest.skipIf(server is None, "MCP/vision dependencies are not installed")
class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = _FIXTURE_ROOT / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.media_root = self.root / "media"
        self.media_root.mkdir()
        self.data_dir = self.root / "data"
        self.video = self.media_root / "clip.mp4"
        self.video.write_bytes(b"video fixture")
        self.env = patch.dict(os.environ, {
            "STORYBOARD_MEDIA_ROOTS": str(self.media_root),
            "STORYBOARD_DATA_DIR": str(self.data_dir),
        })
        self.env.start()
        self.configuration = patch.object(server.vision, "configuration", return_value={"configured": True})
        self.configuration.start()
        server._LOCKS.clear()

    def tearDown(self) -> None:
        self.configuration.stop()
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_prepare_video_creates_initialized_project(self) -> None:
        prepared = {
            "duration": 4.0, "sample_fps": 2.0,
            "source": {"path": str(self.video), "sha256": "abc", "size_bytes": 13},
            "limitations": ["sampling limited"],
            "shots": [{"id": "shot_001", "index": 0, "start": 0.0, "end": 4.0,
                       "duration": 4.0, "boundary_type": "start",
                       "frames": [{"path": str(self.root / "frame.jpg"), "timestamp": 0.0}]}],
        }
        with patch.object(server.media, "prepare_video", return_value=prepared) as prepare:
            result = asyncio.run(server.prepare_video(str(self.video)))
        prepare.assert_called_once()
        project = server.registry.load(self.data_dir, result["project_id"])
        self.assertEqual(project["schema_version"], 1)
        self.assertEqual(project["shots"][0]["status"], "prepared")
        self.assertIsNone(project["shots"][0]["observation"])
        self.assertIsNone(project["shots"][0]["prompts"])
        self.assertTrue(any("没有进行音频分析" in item for item in project["limitations"]))
        self.assertEqual(result["summary"]["shot_count"], 1)

    def test_prepare_rejects_outside_path_before_media_call(self) -> None:
        outside = self.root / "outside.mp4"
        outside.write_bytes(b"not allowed")
        with patch.object(server.media, "prepare_video") as prepare:
            with self.assertRaisesRegex(ValueError, "inside"):
                asyncio.run(server.prepare_video(str(outside)))
        prepare.assert_not_called()

    def test_analysis_saves_observation_prompts_and_safe_retry_error(self) -> None:
        project_id = "test-project"
        project = {"schema_version": 1, "id": project_id, "title": "clip.mp4", "duration": 3,
                   "source": {}, "limitations": [], "shots": [
                       {"id": "shot_001", "duration": 1, "status": "prepared", "frames": []},
                       {"id": "shot_002", "duration": 2, "status": "prepared", "frames": []}]}
        server.registry.save(self.data_dir, project)
        async def fake_analyze(shot):
            if shot["id"] == "shot_002":
                raise RuntimeError("secret token must not leak")
            return {"subject": "person", "confidence": 0.9}
        with patch.object(server.vision, "analyze", side_effect=fake_analyze):
            result = asyncio.run(server.analyze_shots(project_id))
        saved = server.registry.load(self.data_dir, project_id)
        self.assertEqual(result["summary"]["status_counts"], {"analyzed": 1, "error": 1})
        self.assertEqual(saved["shots"][0]["status"], "analyzed")
        self.assertEqual(saved["shots"][0]["observation"]["subject"], "person")
        self.assertIsInstance(saved["shots"][0]["prompts"], dict)
        self.assertEqual(saved["shots"][1]["status"], "error")
        self.assertNotIn("secret token", json.dumps(saved))
        self.assertIsNone(saved["shots"][1]["observation"])
        with patch.object(server.vision, "analyze", new_callable=unittest.mock.AsyncMock,
                          return_value={"subject": "retried", "confidence": 0.8}) as retry:
            asyncio.run(server.analyze_shots(project_id, ["shot_002"]))
        retry.assert_awaited_once()
        self.assertEqual(server.registry.load(self.data_dir, project_id)["shots"][1]["status"], "analyzed")

    def test_get_project_paginates_without_frame_base64(self) -> None:
        project = {"schema_version": 1, "id": "paging", "title": "clip", "duration": 2,
                   "source": {}, "limitations": [], "shots": [
                       {"id": f"shot_{i}", "status": "prepared", "frames": [{"path": "frame.jpg"}]}
                       for i in range(3)]}
        server.registry.save(self.data_dir, project)
        page = asyncio.run(server.get_project("paging", limit=2, offset=1))
        self.assertEqual([shot["id"] for shot in page["shots"]], ["shot_1", "shot_2"])
        self.assertEqual(page["total_shots"], 3)
        self.assertNotIn("base64", json.dumps(page).lower())

    def test_export_uses_project_specific_exports_directory_and_whitelist(self) -> None:
        project = {"schema_version": 1, "id": "export-me", "title": "clip", "duration": 1,
                   "source": {}, "limitations": [], "shots": []}
        server.registry.save(self.data_dir, project)
        result = asyncio.run(server.export_storyboard("export-me", "markdown"))
        target = Path(result["path"])
        self.assertEqual(target, self.data_dir / "export-me" / "exports" / "storyboard.md")
        self.assertTrue(target.is_file())
        with self.assertRaisesRegex(ValueError, "format must be"):
            asyncio.run(server.export_storyboard("export-me", "../../escape"))


if __name__ == "__main__":
    unittest.main()

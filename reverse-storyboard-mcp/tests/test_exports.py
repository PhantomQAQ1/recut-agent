from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reverse_storyboard.exports import build_prompts, export_project, render_markdown, to_shot_plan


class ExportTests(unittest.TestCase):
    def test_characters_dict_and_unknown_camera_and_tail_are_not_invented(self):
        prompts = build_prompts({"subject": "一只猫", "camera_move": None, "last_frame": None,
                                 "characters": [{"label": "猫", "appearance": "黑白毛色"}]}, 3.5)
        self.assertIn("运镜方式未知，保持未指定", prompts["video"])
        self.assertIn("猫（黑白毛色）", prompts["video"])
        self.assertIn("尾帧内容未知", prompts["tail_frame"])
        self.assertNotIn("推镜", prompts["video"])
        self.assertEqual(set(prompts), {"first_frame", "video", "tail_frame"})

    def test_markdown_escapes_table_and_marks_analysis_gaps(self):
        project = {"shots": [
            {"id": "s|1", "start": 0, "end": 2, "duration": 2, "observation": None,
             "frames": [{"timestamp": 0.5}], "prompts": {"video": "中文|文本"}}
        ]}
        rendered = render_markdown(project)
        self.assertIn("待分析", rendered)
        self.assertIn("0.5 秒", rendered)
        self.assertIn("&#124;", rendered)
        self.assertIn("没有执行音频分析", rendered)
        self.assertIn("运镜未知", rendered)

    def test_csv_is_utf8_bom_and_preserves_chinese(self):
        project = {"shots": [{"id": "镜头一", "start": 0, "end": 1, "duration": 1,
                               "status": "待分析", "prompts": {"video": "中文描述"}}]}
        with tempfile.TemporaryDirectory() as folder:
            path = export_project(project, Path(folder), "csv")
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
            self.assertEqual(rows[0]["id"], "镜头一")
            self.assertEqual(rows[0]["video"], "中文描述")

    def test_source_frames_use_cited_indexes(self):
        project = {"shots": [{"id": "s1", "frames": [
            {"timestamp": 0.0}, {"timestamp": 0.5}, {"timestamp": 1.0}],
            "observation": {"evidence_frames": [1, 2]}}]}
        self.assertEqual(to_shot_plan(project)["cards"][0]["source_frames"], [1, 2])

    def test_formats_and_shot_plan_keep_missing_values_null(self):
        project = {"duration": 4, "shots": [{"id": "s1", "start": 0, "end": None,
                                              "duration": None, "observation": None}]}
        plan = to_shot_plan(project)
        self.assertTrue(plan["compatibility"]["needs_review"])
        self.assertIsNone(plan["cards"][0]["source_end"])
        self.assertEqual(plan["cards"][0]["prompts"]["video"], None)
        self.assertIsNone(plan["cards"][0]["shot_size"])
        with tempfile.TemporaryDirectory() as folder:
            json_path = export_project(project, Path(folder), "json")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), project)
            plan_path = export_project(project, Path(folder), "shot-plan")
            self.assertTrue(json.loads(plan_path.read_text(encoding="utf-8"))["compatibility"]["needs_review"])
            md_path = export_project(project, Path(folder), "markdown")
            self.assertTrue(md_path.read_text(encoding="utf-8").endswith("\n"))
            # A subsequent export atomically replaces this exporter's fixed output.
            export_project({"shots": []}, Path(folder), "json")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), {"shots": []})


if __name__ == "__main__":
    unittest.main()

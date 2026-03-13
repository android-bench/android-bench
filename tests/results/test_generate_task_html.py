# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for generate_task_html.py"""

import json
import tempfile
from pathlib import Path

import pytest

from results.generate_task_html import (
    ModelRun,
    discover_model_runs,
    extract_model_name,
    trim_binary_diffs,
    load_patch,
    escape_for_script_tag,
    collect_all_instance_ids,
    generate_task_data,
    generate_html,
)

from common.models.benchmark import Status


class TestExtractModelName:
    """Tests for extract_model_name function."""

    def test_extracts_model_name_from_timestamped_folder(self):
        folder = "anthropic-claude-sonnet-4-5_2025-12-01-22-32-26"
        assert extract_model_name(folder) == "anthropic-claude-sonnet-4-5"

    def test_returns_folder_name_if_no_timestamp(self):
        folder = "some-model-name"
        assert extract_model_name(folder) == "some-model-name"

    def test_handles_multiple_underscores(self):
        folder = "openai-gpt-4_turbo_2025-01-15-10-00-00"
        # Only the last underscore before timestamp is split
        assert extract_model_name(folder) == "openai-gpt-4_turbo"

    def test_handles_folder_with_underscore_but_no_timestamp(self):
        folder = "model_name_without_timestamp"
        assert extract_model_name(folder) == "model_name_without_timestamp"


class TestDiscoverModelRuns:
    """Tests for discover_model_runs function."""

    def test_discovers_single_run_per_model(self, tmp_path):
        # Create two different model runs
        run1 = tmp_path / "model-a_2025-01-01-00-00-00"
        run1.mkdir()
        (run1 / "scores.json").write_text("{}")

        run2 = tmp_path / "model-b_2025-01-01-00-00-00"
        run2.mkdir()
        (run2 / "scores.json").write_text("{}")

        runs = discover_model_runs(tmp_path)

        assert len(runs) == 2
        assert all(isinstance(r, ModelRun) for r in runs)
        # Single runs should not have "(run N)" suffix
        assert runs[0].display_name == "model-a"
        assert runs[0].run_number == 1
        assert runs[1].display_name == "model-b"
        assert runs[1].run_number == 1

    def test_discovers_multiple_runs_same_model(self, tmp_path):
        # Create three runs for the same model with different timestamps
        run1 = tmp_path / "model-a_2025-01-01-00-00-00"
        run1.mkdir()
        (run1 / "scores.json").write_text("{}")

        run2 = tmp_path / "model-a_2025-01-02-00-00-00"
        run2.mkdir()
        (run2 / "scores.json").write_text("{}")

        run3 = tmp_path / "model-a_2025-01-03-00-00-00"
        run3.mkdir()
        (run3 / "scores.json").write_text("{}")

        runs = discover_model_runs(tmp_path)

        assert len(runs) == 3
        # Multiple runs should have "(run N)" suffix
        assert runs[0].display_name == "model-a (run 1)"
        assert runs[0].run_number == 1
        assert runs[0].folder == "model-a_2025-01-01-00-00-00"

        assert runs[1].display_name == "model-a (run 2)"
        assert runs[1].run_number == 2
        assert runs[1].folder == "model-a_2025-01-02-00-00-00"

        assert runs[2].display_name == "model-a (run 3)"
        assert runs[2].run_number == 3
        assert runs[2].folder == "model-a_2025-01-03-00-00-00"

    def test_mixed_single_and_multiple_runs(self, tmp_path):
        # model-a has 2 runs, model-b has 1 run
        (tmp_path / "model-a_2025-01-01-00-00-00").mkdir()
        (tmp_path / "model-a_2025-01-01-00-00-00" / "scores.json").write_text("{}")

        (tmp_path / "model-a_2025-01-02-00-00-00").mkdir()
        (tmp_path / "model-a_2025-01-02-00-00-00" / "scores.json").write_text("{}")

        (tmp_path / "model-b_2025-01-01-00-00-00").mkdir()
        (tmp_path / "model-b_2025-01-01-00-00-00" / "scores.json").write_text("{}")

        runs = discover_model_runs(tmp_path)

        assert len(runs) == 3
        # model-a runs should have "(run N)" suffix
        assert runs[0].display_name == "model-a (run 1)"
        assert runs[1].display_name == "model-a (run 2)"
        # model-b single run should not have suffix
        assert runs[2].display_name == "model-b"

    def test_ignores_directories_without_scores_json(self, tmp_path):
        # Directory with scores.json
        valid_run = tmp_path / "model-a_2025-01-01-00-00-00"
        valid_run.mkdir()
        (valid_run / "scores.json").write_text("{}")

        # Directory without scores.json
        invalid_run = tmp_path / "model-b_2025-01-01-00-00-00"
        invalid_run.mkdir()

        runs = discover_model_runs(tmp_path)

        assert len(runs) == 1
        assert runs[0].model_name == "model-a"

    def test_empty_directory(self, tmp_path):
        runs = discover_model_runs(tmp_path)
        assert len(runs) == 0

    def test_sorting_by_model_name_then_folder(self, tmp_path):
        # Create runs out of order
        (tmp_path / "model-b_2025-01-01-00-00-00").mkdir()
        (tmp_path / "model-b_2025-01-01-00-00-00" / "scores.json").write_text("{}")

        (tmp_path / "model-a_2025-01-02-00-00-00").mkdir()
        (tmp_path / "model-a_2025-01-02-00-00-00" / "scores.json").write_text("{}")

        (tmp_path / "model-a_2025-01-01-00-00-00").mkdir()
        (tmp_path / "model-a_2025-01-01-00-00-00" / "scores.json").write_text("{}")

        runs = discover_model_runs(tmp_path)

        # Should be sorted by model_name, then by folder (timestamp)
        assert runs[0].folder == "model-a_2025-01-01-00-00-00"
        assert runs[1].folder == "model-a_2025-01-02-00-00-00"
        assert runs[2].folder == "model-b_2025-01-01-00-00-00"


class TestTrimBinaryDiffs:
    """Tests for trim_binary_diffs function."""

    def test_keeps_text_diffs(self):
        patch = """diff --git a/file.txt b/file.txt
index 123..456 789
--- a/file.txt
+++ b/file.txt
@@ -1,3 +1,3 @@
 line1
-old line
+new line
 line3"""
        result = trim_binary_diffs(patch)
        assert result == patch

    def test_removes_binary_files_differ(self):
        patch = """diff --git a/image.png b/image.png
Binary files a/image.png and b/image.png differ
diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1 +1 @@
-old
+new"""
        result = trim_binary_diffs(patch)
        assert "Binary files" not in result
        assert "[Binary file diff removed]" in result
        assert "diff --git a/file.txt" in result
        assert "-old" in result
        assert "+new" in result

    def test_removes_git_binary_patch(self):
        patch = """diff --git a/image.png b/image.png
GIT binary patch
literal 1234
some binary data here
literal 0
more data

diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
-old
+new"""
        result = trim_binary_diffs(patch)
        assert "GIT binary patch" not in result
        assert "[Binary file diff removed]" in result


class TestLoadPatch:
    """Tests for load_patch function."""

    def test_loads_existing_patch(self, tmp_path):
        patch_file = tmp_path / "test.patch"
        patch_file.write_text("diff --git a/file.txt b/file.txt\n+new line")

        result = load_patch(patch_file)
        assert result == "diff --git a/file.txt b/file.txt\n+new line"

    def test_returns_none_for_missing_file(self, tmp_path):
        result = load_patch(tmp_path / "nonexistent.patch")
        assert result is None

    def test_trims_binary_by_default(self, tmp_path):
        patch_file = tmp_path / "test.patch"
        patch_file.write_text("diff --git a/img.png b/img.png\nBinary files differ")

        result = load_patch(patch_file)
        assert "[Binary file diff removed]" in result

    def test_can_disable_binary_trimming(self, tmp_path):
        patch_file = tmp_path / "test.patch"
        patch_file.write_text("diff --git a/img.png b/img.png\nBinary files differ")

        result = load_patch(patch_file, trim_binary=False)
        assert "Binary files differ" in result
        assert "[Binary file diff removed]" not in result


class TestEscapeForScriptTag:
    """Tests for escape_for_script_tag function."""

    def test_escapes_script_closing_tag(self):
        json_str = '{"content": "</script>"}'
        result = escape_for_script_tag(json_str)
        assert "</script>" not in result
        assert "<\\/script>" in result

    def test_escapes_case_variations(self):
        json_str = '{"a": "</Script>", "b": "</SCRIPT>"}'
        result = escape_for_script_tag(json_str)
        assert "</Script>" not in result
        assert "</SCRIPT>" not in result

    def test_leaves_other_content_unchanged(self):
        json_str = '{"content": "normal text"}'
        result = escape_for_script_tag(json_str)
        assert result == json_str


class TestCollectAllInstanceIds:
    """Tests for collect_all_instance_ids function."""

    def test_collects_ids_from_patch_files(self, tmp_path):
        run1 = tmp_path / "model-a_2025-01-01"
        run1.mkdir()
        (run1 / "scores.json").write_text("{}")
        patches1 = run1 / "patches"
        patches1.mkdir()
        (patches1 / "instance-1.patch").write_text("")
        (patches1 / "instance-2.patch").write_text("")

        runs = discover_model_runs(tmp_path)
        instance_ids = collect_all_instance_ids(runs)

        assert instance_ids == {"instance-1", "instance-2"}

    def test_collects_unique_ids_across_runs(self, tmp_path):
        # Run 1 has instance-1 and instance-2
        run1 = tmp_path / "model-a_2025-01-01"
        run1.mkdir()
        (run1 / "scores.json").write_text("{}")
        patches1 = run1 / "patches"
        patches1.mkdir()
        (patches1 / "instance-1.patch").write_text("")
        (patches1 / "instance-2.patch").write_text("")

        # Run 2 has instance-2 and instance-3
        run2 = tmp_path / "model-a_2025-01-02"
        run2.mkdir()
        (run2 / "scores.json").write_text("{}")
        patches2 = run2 / "patches"
        patches2.mkdir()
        (patches2 / "instance-2.patch").write_text("")
        (patches2 / "instance-3.patch").write_text("")

        runs = discover_model_runs(tmp_path)
        instance_ids = collect_all_instance_ids(runs)

        assert instance_ids == {"instance-1", "instance-2", "instance-3"}


class TestGenerateTaskData:
    """Tests for generate_task_data function."""

    def test_includes_display_name_in_model_results(self, tmp_path):
        # Setup model runs
        run1 = tmp_path / "model-a_2025-01-01-00-00-00"
        run1.mkdir()
        (run1 / "scores.json").write_text(
            '{"instance-1": {"status": "PASSED", "score": 1.0}}'
        )
        patches1 = run1 / "patches"
        patches1.mkdir()
        (patches1 / "instance-1.patch").write_text("diff content")

        run2 = tmp_path / "model-a_2025-01-02-00-00-00"
        run2.mkdir()
        (run2 / "scores.json").write_text(
            '{"instance-1": {"status": "FAILED", "score": 0.0}}'
        )
        patches2 = run2 / "patches"
        patches2.mkdir()
        (patches2 / "instance-1.patch").write_text("diff content 2")

        # Setup tasks dir (empty for this test)
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()

        # Setup golden patches dir (empty for this test)
        golden_dir = tmp_path / "golden"
        golden_dir.mkdir()

        runs = discover_model_runs(tmp_path)
        task_data = generate_task_data("instance-1", runs, tasks_dir)

        assert len(task_data["model_results"]) == 2
        assert task_data["model_results"][0]["display_name"] == "model-a (run 1)"
        assert task_data["model_results"][0]["folder"] == "model-a_2025-01-01-00-00-00"
        assert task_data["model_results"][1]["display_name"] == "model-a (run 2)"
        assert task_data["model_results"][1]["folder"] == "model-a_2025-01-02-00-00-00"


class TestGenerateHtml:
    """Tests for generate_html function."""

    def test_html_contains_display_name_in_badges(self):
        task_data = {
            "instance_id": "test-instance",
            "task": {"description": "Test description"},
            "golden_patch": None,
            "model_results": [
                {
                    "model_name": "model-a",
                    "display_name": "model-a (run 1)",
                    "folder": "model-a_2025-01-01-00-00-00",
                    "result": {"status": Status.PASSED.name},
                    "patch": "diff content",
                    "trajectory": None,
                },
                {
                    "model_name": "model-a",
                    "display_name": "model-a (run 2)",
                    "folder": "model-a_2025-01-02-00-00-00",
                    "result": {"status": "FAILED"},
                    "patch": "diff content 2",
                    "trajectory": None,
                },
            ],
        }

        html = generate_html(task_data)

        # Check that display_name is used (not model_name) in the JavaScript data
        assert "model-a (run 1)" in html
        assert "model-a (run 2)" in html
        # Check that folder info is present
        assert "model-a_2025-01-01-00-00-00" in html
        assert "model-a_2025-01-02-00-00-00" in html

    def test_html_contains_run_folder_info(self):
        task_data = {
            "instance_id": "test-instance",
            "task": None,
            "golden_patch": None,
            "model_results": [
                {
                    "model_name": "model-a",
                    "display_name": "model-a (run 1)",
                    "folder": "model-a_2025-01-01-00-00-00",
                    "result": None,
                    "patch": None,
                    "trajectory": None,
                },
            ],
        }

        html = generate_html(task_data)

        # The folder should be shown in the model details section
        assert "Run folder:" in html
        assert "model-a_2025-01-01-00-00-00" in html

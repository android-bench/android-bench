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
import pytest
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path
import logging
import yaml
import shutil

from common.loader import load_all_tasks
from common.models.task import Task


@pytest.fixture
def setup_tasks_dir():
    test_tasks_dir = Path("test_tasks_dir")
    test_tasks_dir.mkdir(exist_ok=True)

    # Create dummy task files
    (test_tasks_dir / "task1").mkdir(exist_ok=True)
    with open(test_tasks_dir / "task1" / "task.yaml", "w") as f:
        f.write("""instance_id: task1
submission_type: A
repository:
  url: http://example.com/repo1
created_at: 2023-01-01T00:00:00Z
modified_at: 2023-01-01T00:00:00Z
category_ids:
  - cat1
description: desc1
commands:
  android_test: []
  before_build: []
  build: []
  unit_test: []
issues: []
pull_request: {}
test_files: []
acceptance_criteria:
  fail_to_pass: []
  pass_to_pass: []
time_estimate: <1h
""")

    (test_tasks_dir / "task2").mkdir(exist_ok=True)
    with open(test_tasks_dir / "task2" / "task.yaml", "w") as f:
        f.write("""instance_id: task2
submission_type: A
repository:
  url: http://example.com/repo2
created_at: 2023-01-01T00:00:00Z
modified_at: 2023-01-01T00:00:00Z
category_ids:
  - cat2
description: desc2
commands:
  android_test: []
  before_build: []
  build: []
  unit_test: []
issues: []
pull_request: {}
test_files: []
acceptance_criteria:
  fail_to_pass: []
  pass_to_pass: []
""")

    (test_tasks_dir / "task3").mkdir(exist_ok=True)
    with open(test_tasks_dir / "task3" / "task.yaml", "w") as f:
        f.write("""instance_id: task3
submission_type: A
repository:
  url: http://example.com/repo3
created_at: 2023-01-01T00:00:00Z
modified_at: 2023-01-01T00:00:00Z
category_ids:
  - cat3
description: desc3
commands:
  android_test: []
  before_build: []
  build: []
  unit_test: []
issues: []
pull_request: {}
test_files: []
acceptance_criteria:
  fail_to_pass: []
  pass_to_pass: []
""")
    yield test_tasks_dir
    shutil.rmtree(test_tasks_dir)


def test_load_all_tasks_no_filter(setup_tasks_dir):
    tasks = load_all_tasks(tasks_dir=setup_tasks_dir)
    assert len(tasks) == 3
    assert sorted([t.instance_id for t in tasks]) == ["task1", "task2", "task3"]


def test_load_all_tasks_with_filter(setup_tasks_dir):
    filter_file = setup_tasks_dir / "filter.yaml"
    with open(filter_file, "w") as f:
        yaml.dump(["task1", "task3"], f)

    tasks = load_all_tasks(tasks_dir=setup_tasks_dir, tasks_filter=str(filter_file))
    assert len(tasks) == 2
    assert sorted([t.instance_id for t in tasks]) == ["task1", "task3"]


def test_load_all_tasks_with_negated_filter(setup_tasks_dir):
    filter_file = setup_tasks_dir / "filter.yaml"
    with open(filter_file, "w") as f:
        yaml.dump(["task1", "task3"], f)

    tasks = load_all_tasks(tasks_dir=setup_tasks_dir, tasks_filter=f"!{filter_file}")
    assert len(tasks) == 1
    assert sorted([t.instance_id for t in tasks]) == ["task2"]


def test_run_benchmark_task_excludes_test_files(tmp_path, caplog):
    from harness.evaluation.harness import run_benchmark_task
    from common.models.benchmark import BenchmarkTask, Status

    # Define the test files
    test_files_list = [
        "src/main/java/com/example/TestFile.java",
        "src/test/java/com/example/AnotherTest.java",
        "src/androidTest/java/com/example/Instrumented.kt",
    ]

    # Create realistic git diff content
    patch_content = "some diff content"

    # Create dummy files with the patch content
    patch_file = tmp_path / "patch.diff"
    patch_file.write_text(patch_content)

    test_patch_file = tmp_path / "test_patch.diff"
    test_patch_file.write_text(patch_content)

    # Mock task
    mock_task = MagicMock(spec=BenchmarkTask)
    mock_task.instance_id = "test_task"
    mock_task.repo_url = "http://example.com/test_repo.git"
    mock_task.work_dir = tmp_path  # Absolute path to bypass repo_name logic
    mock_task.patch_file = patch_file
    mock_task.test_patch_file = test_patch_file
    # The requirement is that the path included in the test files section is just the path
    mock_task.test_files = test_files_list
    mock_task.test_commands = ["./gradlew test"]
    mock_task.env_config = MagicMock()
    mock_task.env_config.target_sdk = 30
    mock_task.env_config.jdk_version = 17
    mock_task.build_commands = ["./gradlew assembleDebug"]
    mock_task.pass_to_pass_tests = []
    mock_task.fail_to_pass_tests = []
    mock_task.startup_script = None
    mock_task.before_change_id = None
    mock_task.validation_file = None
    mock_task.cost = None
    mock_task.steps = None
    mock_task.used_tokens = None
    mock_task.latency_details = None

    caplog.set_level(logging.INFO)

    with (
        patch("harness.evaluation.harness.shell") as mock_shell,
        patch("harness.evaluation.harness.helpers") as mock_helpers,
    ):

        # Setup mock returns
        # We want all commands to succeed by default
        mock_shell.run_command.return_value.exit_code = 0
        mock_shell.run_command.return_value.stdout = ""
        mock_shell.run_command.return_value.stderr = ""

        mock_helpers.can_compile_successfully.return_value = True
        mock_helpers.run_tests.return_value = MagicMock(
            passed_tests=[], failed_tests=[], build_successful=True
        )

        run_benchmark_task(mock_task)

        # Verify that git apply was called with exclusions for BOTH the explicit test file
        # AND the discovered test file from --stat
        # Note: formatting of exclude args depends on the implementation string joining

        # We look for the call that applies the patch (not check, not stat)
        # It should contain --exclude

        apply_calls = [
            call[0][0]
            for call in mock_shell.run_command.call_args_list
            if "git apply" in call[0][0] and "--exclude" in call[0][0]
        ]

        assert len(apply_calls) > 0, "git apply with excludes was not called"
        actual_command = apply_calls[0]

        assert "--exclude='**/build/*'" in actual_command
        assert "--exclude='**/androidTest/*'" in actual_command
        assert "--exclude='**/androidTests/*'" in actual_command
        assert "--exclude='**/testFixtures/*'" in actual_command
        assert "--exclude='**/[tT]est/*'" in actual_command
        assert "--exclude='**/[tT]ests/*'" in actual_command
        assert "--exclude='**/*Test.*" in actual_command
        assert "--exclude='**/*Tests.*" in actual_command
        assert "--exclude='**/test.*" in actual_command
        assert "--exclude='**/tests.*" in actual_command

        # Verify all listed test files are excluded
        for tf in test_files_list:
            assert f"--exclude='{tf}'" in actual_command

        # Also verify the test patch was applied (which happens afterwards)
        mock_shell.run_command.assert_any_call(
            f"git apply {test_patch_file.resolve().as_posix()}", cwd=str(tmp_path)
        )

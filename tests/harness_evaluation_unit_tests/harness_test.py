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
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call, ANY
from harness.evaluation.harness import (
    run_benchmark_task,
    main,
    BenchmarkResult,
)
from common.models.benchmark import BenchmarkTask, EnvConfig, Status
from utils.shell import Result
from utils import helpers, shell


@pytest.fixture
def mock_env_config(mocker):
    env_config = mocker.MagicMock(spec=EnvConfig)
    env_config.jdk_version = "11"
    return env_config


@pytest.fixture
def mock_task(mocker, mock_env_config, tmp_path):
    task = mocker.MagicMock(spec=BenchmarkTask)
    task.instance_id = "test-instance-123"
    task.repo_url = "https://github.com/example/repo.git"
    task.work_dir = "my_work_dir"
    task.env_config = mock_env_config
    task.base_commit = None
    task.merged_commit = None
    task.merged_change_id = None
    task.test_files = []
    task.startup_script = None
    task.patch_file = None
    task.test_patch_file = None
    task.test_commands = ["./gradlew test"]
    task.build_commands = ["./gradlew assembleDebug"]
    task.pass_to_pass_tests = None
    task.fail_to_pass_tests = None
    task.steps = "0"
    task.cost = "$0.0"
    task.used_tokens = None
    task.latency_details = None
    task.before_change_id = None
    task.validation_file = None
    return task


@pytest.fixture
def mock_run_command(mocker):
    return mocker.patch(
        "harness.evaluation.harness.shell.run_command",
        return_value=Result("success", "", 0),
    )


@pytest.fixture
def mock_helpers(mocker):
    mock_helpers = mocker.patch("harness.evaluation.harness.helpers")
    mock_helpers.EmulatorStartupTimeoutError = helpers.EmulatorStartupTimeoutError
    mock_helpers.EmulatorFailedToStartError = helpers.EmulatorFailedToStartError
    return mock_helpers


@pytest.fixture(autouse=True)
def mock_heartbeat(mocker):
    return mocker.patch("harness.evaluation.harness.EmulatorHeartbeat")


@pytest.fixture
def mock_path_methods(mocker):
    mock_path_class = mocker.patch("harness.evaluation.harness.Path")
    mock_path_instance = mock_path_class.return_value
    mock_path_instance.exists.return_value = True
    mock_path_instance.resolve.return_value = mock_path_instance
    mock_path_instance.as_posix.return_value = "/mock/path/file"
    mock_path_instance.name = "mock_file.patch"
    mock_path_instance.__str__.return_value = "repo/my_work_dir"
    mock_path_instance.__truediv__.return_value = mock_path_instance
    mock_path_class.return_value.__truediv__.return_value = mock_path_instance
    return mock_path_class


@pytest.fixture
def mock_os_environ(mocker):
    return mocker.patch.dict("harness.evaluation.harness.os.environ", {}, clear=True)


def test_run_benchmark_task_work_dir_not_found(mock_task, mock_path_methods):
    mock_work_dir_instance = mock_path_methods.return_value.__truediv__.return_value
    mock_work_dir_instance.exists.return_value = False
    mock_work_dir_instance.__str__.return_value = "repo/my_work_dir"

    result = run_benchmark_task(mock_task)
    assert result == BenchmarkResult(
        score=0.0,
        cost="$0.0",
        steps="0",
        diagnostics=["Working directory not found: repo/my_work_dir"],
        status=Status.INFRA_FAILURE_SETUP_ISSUE,
        used_tokens=None,
        latency_details=None,
    )


def test_run_benchmark_task_emulator_boot_fails(
    mock_task,
    mock_run_command,
    mock_helpers,
    mock_path_methods,
    mock_os_environ,
    mock_heartbeat,
):
    mock_task.test_commands = ["./gradlew connectedAndroidTest"]
    mock_helpers.EmulatorStartupTimeoutError = helpers.EmulatorStartupTimeoutError
    mock_helpers.start_and_wait_for_emulator.side_effect = (
        helpers.EmulatorStartupTimeoutError(timeout_seconds=180)
    )

    result = run_benchmark_task(mock_task)

    assert result == BenchmarkResult(
        score=0.0,
        cost="$0.0",
        steps="0",
        diagnostics=["Emulator failed to start within 180 seconds"],
        status=Status.INFRA_FAILURE_EMULATOR_TIMEOUT,
        used_tokens=None,
        latency_details=None,
    )


def test_run_benchmark_task_startup_script_fails(
    mocker,
    mock_task,
    mock_run_command,
    mock_helpers,
    mock_path_methods,
    mock_os_environ,
    mock_heartbeat,
):
    mock_script_path = MagicMock(spec=Path)
    mock_script_path.exists.return_value = True
    mock_script_path.resolve.return_value = mock_script_path
    mock_script_path.as_posix.return_value = "/fake/startup.sh"
    mock_script_path.__str__.return_value = "/fake/startup.sh"
    mock_task.startup_script = mock_script_path
    mock_run_command.side_effect = [
        Result("ls output", "", 0),
        Result("Script failed", "Bash error", 1),
    ]

    result = run_benchmark_task(mock_task)
    assert result == BenchmarkResult(
        score=0.0,
        cost="$0.0",
        steps="0",
        diagnostics=["Startup script failed: Bash error"],
        status=Status.INFRA_FAILURE_SETUP_ISSUE,
        used_tokens=None,
        latency_details=None,
    )


def test_run_benchmark_task_git_apply_fails(
    mocker,
    mock_task,
    mock_run_command,
    mock_helpers,
    mock_path_methods,
    mock_os_environ,
    mock_heartbeat,
):
    mock_patch_path = MagicMock(spec=Path)
    mock_patch_path.resolve.return_value = mock_patch_path
    mock_patch_path.as_posix.return_value = "/fake/my.patch"
    mock_patch_path.name = "my.patch"
    mock_patch_path.__str__.return_value = "/fake/my.patch"
    mock_task.patch_file = mock_patch_path
    mock_run_command.side_effect = [
        Result("ls output", "", 0),
        Result("check_stdout", "check_stderr", 0),  # git apply --check
        Result("Apply failed", "Patch error", 1),
    ]

    result = run_benchmark_task(mock_task)

    assert result == BenchmarkResult(
        score=0.0,
        cost="$0.0",
        steps="0",
        diagnostics=["Code patch couldn't be applied: check_stdout\ncheck_stderr"],
        status=Status.AGENT_FAILED_TO_APPLY_PATCH,
        used_tokens=None,
        latency_details=None,
    )


def test_run_benchmark_task_test_command_fails(
    mock_task,
    mock_run_command,
    mock_helpers,
    mock_path_methods,
    mock_os_environ,
    mock_heartbeat,
    mocker,
):
    from harness.evaluation.config import config

    mock_helpers.run_tests.return_value.failed_tests = ["failed_test"]
    result = run_benchmark_task(mock_task)
    retries = config.emulator_config.test_retry_attempts

    diagnostics = [
        "pass_to_pass and fail_to_pass tests are not specified in the yaml, verifying all tests.",
    ]
    for i in range(1, retries + 1):
        diagnostics.append(f"Running test attempt: {i}")
        diagnostics.append("Test failed, command: './gradlew test'")
        diagnostics.append(f"Test attempt {i}: {Status.AGENT_FAILED_TEST}")

    expected = BenchmarkResult(
        score=0.0,
        cost="$0.0",
        steps="0",
        diagnostics=diagnostics,
        status=Status.AGENT_FAILED_TEST,
        used_tokens=None,
        latency_details=None,
    )

    assert result == expected


def test_run_benchmark_task_test_command_flakes(
    mock_task,
    mock_run_command,
    mock_helpers,
    mock_path_methods,
    mock_os_environ,
    mock_heartbeat,
    mocker,
):
    from harness.evaluation.config import config

    mock_helpers.run_tests.side_effect = [
        MagicMock(failed_tests=["failed_test"]),
        MagicMock(failed_tests=[]),
    ]
    result = run_benchmark_task(mock_task)
    retries = config.emulator_config.test_retry_attempts

    if retries == 1:
        diagnostics = [
            "pass_to_pass and fail_to_pass tests are not specified in the yaml, verifying all tests.",
            "Running test attempt: 1",
            "Test failed, command: './gradlew test'",
            f"Test attempt 1: {Status.AGENT_FAILED_TEST}",
        ]
        status = Status.AGENT_FAILED_TEST
        score = 0.0
    else:
        diagnostics = [
            "pass_to_pass and fail_to_pass tests are not specified in the yaml, verifying all tests.",
            "Running test attempt: 1",
            "Test failed, command: './gradlew test'",
            f"Test attempt 1: {Status.AGENT_FAILED_TEST}",
            "Running test attempt: 2",
            f"Test attempt 2: {Status.PASSED}",
        ]
        status = Status.PASSED_FLAKY
        score = 1.0

    assert result == BenchmarkResult(
        score=score,
        cost="$0.0",
        steps="0",
        diagnostics=diagnostics,
        status=status,
        used_tokens=None,
        latency_details=None,
    )


def test_run_benchmark_task_validation_script_success(
    mocker,
    mock_task,
    mock_run_command,
    mock_helpers,
    mock_path_methods,
    mock_os_environ,
):
    mock_validation_path = MagicMock(spec=Path)
    mock_validation_path.resolve.return_value = mock_validation_path
    mock_validation_path.as_posix.return_value = "/fake/validate.sh"
    mock_validation_path.__str__.return_value = "/fake/validate.sh"
    mock_task.validation_file = mock_validation_path

    # Mock successful test run
    mock_helpers.run_tests.return_value = MagicMock(failed_tests=[])

    mock_run_command.side_effect = [
        Result("ls output", "", 0),  # pwd && ls
        Result("Validation success", "", 0),  # validation script
    ]

    result = run_benchmark_task(mock_task)

    assert result == BenchmarkResult(
        score=1.0,
        cost="$0.0",
        steps="0",
        diagnostics=[
            "pass_to_pass and fail_to_pass tests are not specified in the yaml, verifying all tests.",
            "Running test attempt: 1",
            f"Test attempt 1: {Status.PASSED}",
        ],
        status=Status.PASSED,
        used_tokens=None,
        latency_details=None,
    )


def test_run_benchmark_task_validation_script_fails(
    mocker,
    mock_task,
    mock_run_command,
    mock_helpers,
    mock_path_methods,
    mock_os_environ,
):
    mock_validation_path = MagicMock(spec=Path)
    mock_validation_path.resolve.return_value = mock_validation_path
    mock_validation_path.as_posix.return_value = "/fake/validate.sh"
    mock_validation_path.__str__.return_value = "/fake/validate.sh"
    mock_task.validation_file = mock_validation_path

    # Mock successful test run so we get to validation
    mock_helpers.run_tests.return_value = MagicMock(failed_tests=[])

    mock_run_command.side_effect = [
        Result("ls output", "", 0),  # pwd && ls
        Result("Validation failed", "Validation error", 1),  # validation script
    ]

    result = run_benchmark_task(mock_task)

    assert result == BenchmarkResult(
        score=0.0,
        cost="$0.0",
        steps="0",
        diagnostics=[
            "Validation script failed: Validation failed|Validation error",
        ],
        status=Status.AGENT_FAILED_VALIDATION,
        used_tokens=None,
        latency_details=None,
    )


def test_run_benchmark_task_emulator_offline_detected(
    mock_task,
    mock_run_command,
    mock_helpers,
    mock_path_methods,
    mock_os_environ,
    mock_heartbeat,
):
    # 0. Set test_commands to include AndroidTest so heartbeat is started
    mock_task.test_commands = ["./gradlew connectedAndroidTest"]

    # 1. Configure the heartbeat mock instance to have a failure message
    mock_heartbeat_instance = mock_heartbeat.return_value
    mock_heartbeat_instance.failure = (
        "CRITICAL: Emulator process has exited unexpectedly."
    )

    # 2. Simulate the crash happening "midway"
    # We make the next shell command raise KeyboardInterrupt (exactly what a SIGINT does)
    mock_run_command.side_effect = KeyboardInterrupt()

    # 3. Execute the task
    result = run_benchmark_task(mock_task)

    # 4. Verify that the harness correctly identified the crash
    assert result.status == Status.INFRA_FAILURE_EMULATOR_OFFLINE
    assert "CRITICAL: Emulator process has exited unexpectedly." in result.diagnostics


def test_run_benchmark_task_excludes_test_files_from_code_patch(
    mock_task,
    mock_run_command,
    mock_helpers,
    mock_path_methods,
    mock_os_environ,
    mock_heartbeat,
):
    # Setup patch_file (code patch) - this triggers the exclude logic
    mock_patch_path = MagicMock(spec=Path)
    mock_patch_path.resolve.return_value = mock_patch_path
    mock_patch_path.as_posix.return_value = "/fake/my.patch"
    mock_patch_path.name = "my.patch"
    mock_patch_path.__str__.return_value = "/fake/my.patch"
    mock_patch_path.exists.return_value = True
    mock_task.patch_file = mock_patch_path

    # Setup test_patch_file
    mock_test_patch_path = MagicMock(spec=Path)
    mock_test_patch_path.resolve.return_value = mock_test_patch_path
    mock_test_patch_path.as_posix.return_value = "/fake/my_test.patch"
    mock_test_patch_path.name = "my_test.patch"
    mock_test_patch_path.__str__.return_value = "/fake/my_test.patch"
    mock_test_patch_path.exists.return_value = True
    mock_task.test_patch_file = mock_test_patch_path

    # Setup the list of test files to exclude
    mock_task.test_files = ["src/test/Test.java", "src/androidTest/MyTest.kt"]

    # Mock shell commands
    # 1. pwd && ls (startup)
    # 2. git apply --check ... (code patch check)
    # 3. git apply --exclude ... (code patch apply)
    # 4. git apply ... (test patch apply)
    mock_run_command.side_effect = [
        Result("ls output", "", 0),
        Result("", "", 0),  # git apply --check
        Result("", "", 0),  # git apply (code)
        Result("", "", 0),  # git apply (test)
    ]

    mock_helpers.run_tests.return_value = MagicMock(failed_tests=[])

    result = run_benchmark_task(mock_task)

    # Verify git apply was called with excludes for the test files
    git_apply_code_call_found = False
    for call_obj in mock_run_command.mock_calls:
        if (
            len(call_obj.args) > 0
            and "git apply" in call_obj.args[0]
            and "my.patch" in call_obj.args[0]
        ):
            cmd = call_obj.args[0]
            if (
                "--exclude='src/test/Test.java'" in cmd
                and "--exclude='src/androidTest/MyTest.kt'" in cmd
            ):
                git_apply_code_call_found = True
                break

    assert (
        git_apply_code_call_found
    ), "git apply command for code patch should contain excludes for test files"

    # Verify the test patch was applied (without excludes)
    mock_run_command.assert_any_call(
        "git apply /fake/my_test.patch", cwd="repo/my_work_dir"
    )

    assert result.status == Status.PASSED

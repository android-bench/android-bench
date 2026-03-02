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
import argparse
import glob
import json
import logging
import os
import shutil
import subprocess
import sys
import re
import traceback

# Add the project root to the Python path to ensure we pick up the correct modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)


from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

from utils import helpers, shell
from utils.helpers import EmulatorHeartbeat
from common.models.benchmark import (
    BenchmarkTask,
    Status,
    TokenDetails,
    LatencyDetails,
    STATUS_DESCRIPTIONS,
)
from .config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    score: float
    cost: str | None
    steps: str | None
    used_tokens: TokenDetails | None
    latency_details: LatencyDetails | None
    diagnostics: List[str]
    status: Status

    def to_dict(self):
        data = asdict(self)
        data["status"] = self.status.name
        data["status_description"] = STATUS_DESCRIPTIONS.get(self.status, "")
        return data


def run_benchmark_task(
    task: BenchmarkTask, output_dir: Path | None = None
) -> BenchmarkResult:
    emulator_process = None
    heartbeat = None

    repo_name = task.repo_url.split("/")[-1].replace(".git", "")
    work_dir = (
        Path(repo_name) / task.work_dir if task.work_dir else Path("/workspace/testbed")
    )

    if not work_dir.exists():
        logger.error(f"Working directory not found: {work_dir}")
        return BenchmarkResult(
            score=0.0,
            cost=task.cost,
            steps=task.steps,
            used_tokens=task.used_tokens,
            latency_details=task.latency_details,
            diagnostics=[f"Working directory not found: {work_dir}"],
            status=Status.INFRA_FAILURE_SETUP_ISSUE,
        )

    # Log task execution summary
    logger.info("=" * 70)
    logger.info(f"STARTING BENCHMARK TASK: {task.instance_id}")
    logger.info(f"Repository: {task.repo_url}")
    logger.info(f"Work directory: {work_dir}")
    logger.info(f"Patch file: {task.patch_file}")
    logger.info(f"Test commands: {task.test_commands}")
    logger.info("=" * 70)

    try:

        log_file = os.path.join(work_dir, "log.txt")
        adb_path = helpers.get_adb_path()

        # --- Emulator Orchestration ---
        emulator_process = None
        if any("AndroidTest" in t for t in task.test_commands):
            emulator_process = helpers.start_and_wait_for_emulator(
                log_file,
                f"test_emulator_{task.env_config.target_sdk}",
                timeout_seconds=config.emulator_config.emulator_boot_timeout,
            )

            heartbeat = EmulatorHeartbeat(emulator_process, adb_path, log_file)
            heartbeat.start()

        # --- Set Java Version ---
        java_home = f"/usr/lib/jvm/java-{task.env_config.jdk_version}-openjdk-amd64"
        logger.info(f"Instance {task.instance_id}: Setting JAVA_HOME to: {java_home}")
        helpers.update_local_properties(work_dir, java_home)

        # --- Repository Setup ---
        logger.info(f"Instance {task.instance_id}: Using working directory: {work_dir}")
        result = shell.run_command("pwd && ls", cwd=str(work_dir))
        logger.debug(f"Instance {task.instance_id}: pwd && ls = {result.stdout}")

        if task.startup_script and task.startup_script.exists():
            logger.info(
                f"Instance {task.instance_id}: Running startup script: {task.startup_script}"
            )
            script_command = f"bash {task.startup_script.resolve().as_posix()}"
            result = shell.run_command(script_command, cwd=str(work_dir))
            logger.info(
                f"Instance {task.instance_id}: Startup script output: {result.stdout}\n{result.stderr}"
            )
            if result.exit_code != 0:
                return BenchmarkResult(
                    score=0.0,
                    cost=task.cost,
                    steps=task.steps,
                    used_tokens=task.used_tokens,
                    latency_details=task.latency_details,
                    diagnostics=[f"Startup script failed: {result.stderr}"],
                    status=Status.INFRA_FAILURE_SETUP_ISSUE,
                )

        # TODO: Remove when b/464970808 is fixed
        if task.before_change_id:
            helpers.reset_to_changeid(task.before_change_id, cwd=str(work_dir))

        # --- Apply Patches ---
        if task.patch_file and task.patch_file.exists():
            check_result = shell.run_command(
                f"git apply --check {task.patch_file.resolve().as_posix()}",
                cwd=str(work_dir),
            )
            logger.info(
                f"Instance {task.instance_id}: Checking code patch output: {check_result.stdout}\n{check_result.stderr}"
            )
            logger.info(
                f"Instance {task.instance_id}: Applying code patch: {task.patch_file.name}..."
            )
            excludes = [
                "**/build/*",
                "**/androidTest/*",
                "**/androidTests/*",
                "**/testFixtures/*",
                "**/[tT]est/*",
                "**/[tT]ests/*",
                "**/*Test.*",
                "**/*Tests.*",
                "**/test.*",
                "**/tests.*",
            ]
            if task.test_files:
                excludes.extend(task.test_files)
            exclude_args = " ".join([f"--exclude='{e}'" for e in excludes])

            result = shell.run_command(
                f"git apply {exclude_args} {task.patch_file.resolve().as_posix()}",
                cwd=str(work_dir),
            )
            if result.stdout:
                logger.info(f"git apply (code) stdout: {result.stdout}")
            if result.stderr:
                logger.warning(f"git apply (code) stderr: {result.stderr}")
            if result.exit_code != 0:
                # Agent generating a bad patch counts as a benchmark fail
                logger.info("Code patch couldn't be applied")
                return BenchmarkResult(
                    score=0.0,
                    cost=task.cost,
                    steps=task.steps,
                    used_tokens=task.used_tokens,
                    latency_details=task.latency_details,
                    diagnostics=[
                        f"Code patch couldn't be applied: {check_result.stdout}\n{check_result.stderr}"
                    ],
                    status=Status.AGENT_FAILED_TO_APPLY_PATCH,
                )
        if task.test_patch_file and task.test_patch_file.exists():
            logger.info(
                f"Instance {task.instance_id}: Applying test patch: {task.test_patch_file.name}..."
            )
            result = shell.run_command(
                f"git apply {task.test_patch_file.resolve().as_posix()}",
                cwd=str(work_dir),
            )
            if result.stdout:
                logger.info(f"git apply (test) patch stdout: {result.stdout}")
            if result.stderr:
                logger.info(f"git apply (test) patch stderr: {result.stderr}")
            if result.exit_code != 0:
                return BenchmarkResult(
                    score=0.0,
                    cost=task.cost,
                    steps=task.steps,
                    used_tokens=task.used_tokens,
                    latency_details=task.latency_details,
                    diagnostics=[f"git apply (test) patch failed: {result.stderr}"],
                    status=Status.INFRA_FAILURE_SETUP_ISSUE,
                )

        diagnostics = []
        # Check project's build status
        if not helpers.can_compile_successfully(task.build_commands, str(work_dir)):
            diagnostics.append("Project failed to compile.")
            return BenchmarkResult(
                score=0.0,
                cost=task.cost,
                steps=task.steps,
                used_tokens=task.used_tokens,
                latency_details=task.latency_details,
                diagnostics=diagnostics,
                status=Status.AGENT_FAILED_BUILD,
            )

        # Workaround composable lambda hash names in tests. b/465224060
        pass_to_pass_tests_list = [
            re.sub(
                r"ComposableLambdaImpl@[a-zA-Z0-9]+(?=\))", "ComposableLambdaImpl", s
            )
            for s in task.pass_to_pass_tests or []
        ]
        fail_to_pass_tests_list = [
            re.sub(
                r"ComposableLambdaImpl@[a-zA-Z0-9]+(?=\))", "ComposableLambdaImpl", s
            )
            for s in task.fail_to_pass_tests or []
        ]

        must_pass_tests = set(pass_to_pass_tests_list + fail_to_pass_tests_list)
        all_tests_must_pass = len(must_pass_tests) == 0
        if all_tests_must_pass:
            diagnostics.append(
                "pass_to_pass and fail_to_pass tests are not specified in the yaml, verifying all tests."
            )
        else:
            diagnostics.append(
                f"Verifying {len(pass_to_pass_tests_list)} pass_to_pass tests and {len(fail_to_pass_tests_list)} fail_to_pass tests."
            )

        # Aggregate test results across all command invocations
        all_passed_tests: set[str] = set()
        all_failed_tests: set[str] = set()

        old_fashioned_test_naming = True
        # New fashioned are {TaskName}#Test {testName}({testClass})
        TEST_NAME_REGEX = r"^\w+#Test"
        if (
            fail_to_pass_tests_list
            and re.match(TEST_NAME_REGEX, fail_to_pass_tests_list[0])
        ) or (
            pass_to_pass_tests_list
            and re.match(TEST_NAME_REGEX, pass_to_pass_tests_list[0])
        ):
            old_fashioned_test_naming = False

        test_attempts = 0
        status = Status.AGENT_FAILED_TEST
        # Run tests multiple times to prevent flakes marking a test as failed incorrectly
        while (
            test_attempts < config.emulator_config.test_retry_attempts
            and status != Status.PASSED
        ):
            test_attempts = test_attempts + 1
            logger.info("=" * 70)
            logging.info(f"Running test attempt: {test_attempts}")
            diagnostics.append(f"Running test attempt: {test_attempts}")
            logger.info("=" * 70)
            status = _run_tests(
                task,
                work_dir,
                all_tests_must_pass,
                diagnostics,
                all_passed_tests,
                all_failed_tests,
                old_fashioned_test_naming,
                heartbeat,
            )

            # Guard against flakes by assuming if a test passed on any run, it is a pass
            all_failed_tests = all_failed_tests - all_passed_tests

            # After all commands, check if any must_pass test failed (across all invocations)
            if status == Status.PASSED and not all_tests_must_pass:
                failed_must_pass = must_pass_tests & all_failed_tests
                not_passed_must_pass = must_pass_tests - all_passed_tests
                if failed_must_pass:
                    for failed_test in sorted(failed_must_pass):
                        diagnostics.append(f"Must Pass test failed: '{failed_test}'")
                    status = Status.AGENT_FAILED_TEST
                elif not_passed_must_pass:
                    # It would reach here if:
                    # 1. Build is successful, so all_passed_tests and/or all_failed_tests are non empty.
                    # 2. not_passed_must_pass tests are not in either all_passed_tests or all_failed_tests.
                    # So we can say that gradle did not run those tests.
                    for not_passed_test in sorted(not_passed_must_pass):
                        diagnostics.append(
                            f"Must Pass test wasn't executed: '{not_passed_test}'"
                        )
                    status = Status.AGENT_MISSING_REQUIRED_TEST_RESULTS
            diagnostics.append(f"Test attempt {test_attempts}: {status}")
            logger.info("=" * 70)

        if task.validation_file and task.validation_file.exists():
            logger.info(
                f"Instance {task.instance_id}: Running validation script: {task.validation_file}"
            )
            script_command = f"bash {task.validation_file.resolve().as_posix()}"
            result = shell.run_command(script_command, cwd=str(work_dir))
            logger.info(
                f"Instance {task.instance_id}: Validation script output: {result.stdout}\n{result.stderr}"
            )
            if result.exit_code != 0:
                return BenchmarkResult(
                    score=0.0,
                    cost=task.cost,
                    steps=task.steps,
                    used_tokens=task.used_tokens,
                    latency_details=task.latency_details,
                    diagnostics=[
                        f"Validation script failed: {result.stdout}|{result.stderr}"
                    ],
                    status=Status.AGENT_FAILED_VALIDATION,
                )
        else:
            logger.info("No validation script present")

        if status != Status.PASSED:
            return BenchmarkResult(
                score=0.0,
                cost=task.cost,
                steps=task.steps,
                used_tokens=task.used_tokens,
                latency_details=task.latency_details,
                diagnostics=diagnostics,
                status=status,
            )

        if status == Status.PASSED and test_attempts > 1:
            status = Status.PASSED_FLAKY

        return BenchmarkResult(
            score=1.0,
            cost=task.cost,
            steps=task.steps,
            used_tokens=task.used_tokens,
            latency_details=task.latency_details,
            diagnostics=diagnostics,
            status=status,
        )
    except helpers.EmulatorStartupTimeoutError as e:
        return BenchmarkResult(
            score=0.0,
            cost=task.cost,
            steps=task.steps,
            used_tokens=task.used_tokens,
            latency_details=task.latency_details,
            diagnostics=[
                f"Emulator failed to start within {e.timeout_seconds} seconds"
            ],
            status=Status.INFRA_FAILURE_EMULATOR_TIMEOUT,
        )
    except helpers.EmulatorFailedToStartError as e:
        return BenchmarkResult(
            score=0.0,
            cost=task.cost,
            steps=task.steps,
            used_tokens=task.used_tokens,
            latency_details=task.latency_details,
            diagnostics=["Emulator failed to start"],
            status=Status.INFRA_FAILURE_EMULATOR_STARTUP,
        )
    except KeyboardInterrupt:
        if "heartbeat" in locals() and heartbeat and heartbeat.failure:
            logger.error(f"Emulator offline error: {heartbeat.failure}")
            return BenchmarkResult(
                score=0.0,
                cost=task.cost,
                steps=task.steps,
                used_tokens=task.used_tokens,
                latency_details=task.latency_details,
                diagnostics=[str(heartbeat.failure)],
                status=Status.INFRA_FAILURE_EMULATOR_OFFLINE,
            )
        logger.info("KeyboardInterrupt received, exiting...")
        raise
    finally:
        if output_dir:
            try:
                helpers.copy_build_outputs(work_dir, output_dir)
            except Exception as e:
                logger.error(f"Failed to copy build outputs: {e}")

        if heartbeat and "heartbeat" in locals():
            heartbeat.stop()
        if emulator_process:
            logger.info(f"Instance {task.instance_id}: --- Stopping emulator ---")
            emulator_process.terminate()
            try:
                emulator_process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                emulator_process.kill()


def _run_tests(
    task,
    work_dir,
    all_tests_must_pass,
    diagnostics,
    all_passed_tests,
    all_failed_tests,
    old_fashioned_test_naming,
    heartbeat,
):
    for command in task.test_commands:
        logger.info(f"Instance {task.instance_id}: Executing: {command}")
        test_result = helpers.run_tests(
            str(work_dir),
            command,
            timeout=config.emulator_config.test_execution_timeout,
            workers=config.emulator_config.gradle_workers,
            mount_path="/android_bench",
            remove_task_names=old_fashioned_test_naming,
        )

        logger.info(f"--- Command: {command} ---")
        logger.info(f"--- Passed Tests: {len(test_result.passed_tests)} ---")
        for test in sorted(test_result.passed_tests):
            logger.info(f"  {test}")
        logger.info(f"--- Failed Tests: {len(test_result.failed_tests)} ---")
        for test in sorted(test_result.failed_tests):
            logger.info(f"  {test}")

            # Aggregate results
        all_passed_tests.update(test_result.passed_tests)
        all_failed_tests.update(test_result.failed_tests)

        # we check result of build command only if pass_to_pass + fail_to_pass tests are empty
        # context: legit/258310/1/common/eval_data_classes.py#67
        # We also can't prevent flakes in this scenario
        if all_tests_must_pass and not test_result.build_successful:
            diagnostics.append(f"Build failed for command: '{command}'")
            # cannot differentiate between BUILD_FAILED and TEST_FAILED in this case
            # so marking it as TEST_FAILED
            return Status.AGENT_FAILED_TEST

        # For all_tests_must_pass mode, fail immediately on any test failure
        if all_tests_must_pass and len(test_result.failed_tests) > 0:
            logger.warning(f"Test command failed: '{command}'. Marking task as failed.")
            diagnostics.append(f"Test failed, command: '{command}'")
            return Status.AGENT_FAILED_TEST

    return Status.PASSED


def main(task_json_file: str):
    scores_dir = Path("harness/evaluation")
    scores_dir.mkdir(parents=True, exist_ok=True)
    scores_file = scores_dir / "scores.json"
    instance_id = "unknown"

    try:
        with open(task_json_file, "r") as f:
            task_json_data = json.load(f)

        instance_id = task_json_data.get("instance_id", "unknown")
        task = BenchmarkTask.from_json(task_json_data)
        if task is None:
            logger.error(f"Could not create task '{instance_id}'.")
            raise Exception(f"Task creation failed for {instance_id}")

        instance_id = task.instance_id  # Get proper instance_id
        logger.info(f"Successfully created BenchmarkTask object for: {instance_id}")

        output_dir = Path(task_json_file).parent / "outputs"
        result_value = run_benchmark_task(task=task, output_dir=output_dir)

        if result_value.score == 1.0:
            logger.info("=" * 70)
            logger.info(f"TASK COMPLETED: {task.instance_id} - PASSED (score: 1.0)")
            logger.info("=" * 70)
        else:
            logger.info("=" * 70)
            logger.info(f"TASK COMPLETED: {task.instance_id} - FAILED (score: 0.0)")
            logger.info("=" * 70)

        result_data = {}
        result_data[instance_id] = result_value.to_dict()
        with open(scores_file, "w") as f:
            json.dump(result_data, f, indent=4)
        logger.info(f"Successfully wrote results to {scores_file}")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Error running BenchmarkTask {instance_id}: {e}")
        logger.error(traceback.format_exc())
        result_data = {instance_id: f"Error: {e}"}
        with open(scores_file, "w") as f:
            json.dump(result_data, f, indent=4)
        # need to return 0 here as we want to read scores files from host even in case of errors
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a benchmark task locally.")
    parser.add_argument(
        "--task-json-file",
        type=str,
        required=True,
        help="Path to the JSON file containing the task definition.",
    )
    args = parser.parse_args()
    main(task_json_file=args.task_json_file)

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
"""
Integration tests for the Patch Verifier.

This module contains simplified integration tests for the patch verifier tool.
It verifies:
1. Running a specific golden task with the --test-run parameter.
2. Handling various invalid patch scenarios and correctly reporting failure statuses.
"""

import json
import os
import shutil
from pathlib import Path
import logging
import pytest
import subprocess
import yaml
import docker

from harness.evaluation.main import score_patches
from harness.evaluation.benchmark_worker import score_patch
from common.models.benchmark import Status

# Get the directory of the current test script (tests/harness_evaluation_integration_test)
TEST_DIR = Path(__file__).parent

# --- Logging and Constants ---
CONFIG_JSON_PATH = TEST_DIR / "data/config.json"
with open(CONFIG_JSON_PATH, "r") as cfg_file:
    config_data = json.load(cfg_file)

# Path to the actual tasks directory in the project
TASKS_DIR = TEST_DIR / "../../dataset/tasks"

# Paths from config.json
OUTPUT_BASE_DIR = TEST_DIR / config_data["output_path"]
INVALID_PATCH_DIR = TEST_DIR / config_data["invalid_patch_dir"]


@pytest.fixture(autouse=True)
def cleanup_output():
    """Ensure a clean output directory before each test, preserving source data."""
    if OUTPUT_BASE_DIR.exists():
        for item in OUTPUT_BASE_DIR.iterdir():
            # DO NOT delete the source patches for the invalid patches test
            if item.resolve() == INVALID_PATCH_DIR.resolve():
                continue
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except PermissionError:
                logging.info(
                    f"Permission denied removing {item}. It might be owned by root (created by Docker). attempting cleanup via Docker."
                )
                try:
                    client = docker.from_env()
                    # Use a lightweight image to remove the file/dir
                    # We mount the parent directory to /mnt and remove the item by name
                    parent_dir = item.parent.resolve()
                    target_name = item.name

                    client.containers.run(
                        "alpine",
                        f"rm -rf /mnt/{target_name}",
                        volumes={str(parent_dir): {"bind": "/mnt", "mode": "rw"}},
                        remove=True,
                    )
                    logging.info(f"Successfully removed {item} via Docker.")
                except Exception as e:
                    logging.error(f"Failed to remove {item} via Docker: {e}")
                    raise
            except Exception as e:
                logging.error(f"Failed to cleanup {item}: {e}")
                # We might want to raise here, but logging fits the existing pattern?
                # Actually for integration test setup, it's better to raise if we can't clean environment.
                raise
    else:
        OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)
    yield


class TestPatchVerifierIntegration:
    @pytest.fixture(scope="class", autouse=True)
    def check_changes_in_patch_verifier(self):
        """
        Runs once before executing any tests in this class.
        Checks if there are any changes in the patch_verifier module.
        If no changes are detected, skips the tests.
        """
        project_root = TEST_DIR.parents[1]
        should_run = False
        try:
            # Using the command specified by the user to get the diff
            cmd = ["git", "diff-tree", "--no-commit-id", "--name-status", "-r", "HEAD"]
            result = subprocess.run(
                cmd, cwd=project_root, capture_output=True, text=True, check=True
            )

            changes_output = result.stdout.strip()
            logging.info(f"Git diff-tree detected changes:\n{changes_output}")
            if changes_output:
                for line in changes_output.splitlines():
                    # git diff-tree --name-status output format: <STATUS>\t<PATH>
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        file_path = parts[1]
                        # Check if the change is in patch_verifier module or in the integration test files
                        # The code for patch verifier is now in harness/evaluation
                        if (
                            "harness/evaluation/" in file_path
                            or "tests/harness_evaluation_integration_test/" in file_path
                        ):
                            should_run = True
                            logging.info(
                                f"Found change in patch_verifier logic: {file_path}"
                            )
                            break
            else:
                logging.info("No changes detected by git diff-tree.")

        except subprocess.CalledProcessError as e:
            logging.warning(f"Git command failed: {e}. Defaulting to running tests.")
            should_run = True
        except FileNotFoundError:
            logging.warning("Git command not found. Defaulting to running tests.")
            should_run = True

        if not should_run:
            pytest.skip(
                "No changes detected in patch_verifier module. Skipping integration tests."
            )

    def test_run_valid_patches(self):
        """
        Test the patch verifier by running it on a single golden task with --test-run.
        Verification:
        - Status is PASSED or PASSED_FLAKY
        - Score is 1.0
        """

        # Define the mapping of success case directories to expected statuses
        # passed -> PASSED
        # passed_flaky -> PASSED, PASSED_FLAKY (flaky might pass or be flaky)
        success_cases = {
            "passed": [Status.PASSED, Status.PASSED_FLAKY],
        }

        client = docker.from_env()
        project_root = TEST_DIR.parents[1]
        SUCCESS_CASES_DIR = TEST_DIR / "data/success_cases"

        for case_name, expected_statuses in success_cases.items():
            case_dir = SUCCESS_CASES_DIR / case_name
            task_yaml_path = case_dir / "task.yaml"

            if not task_yaml_path.exists():
                logging.info(f"Skipping {case_name}, task.yaml not found.")
                continue

            with open(task_yaml_path, "r") as f:
                task_dict = yaml.safe_load(f)

            src_patch_path = case_dir / "src.patch"
            test_patch_path = case_dir / "test.patch"

            if src_patch_path.exists():
                task_dict["patch_file"] = (
                    f"/android_bench/{src_patch_path.relative_to(project_root)}"
                )
            if test_patch_path.exists():
                task_dict["test_patch_file"] = (
                    f"/android_bench/{test_patch_path.relative_to(project_root)}"
                )

            run_dir = OUTPUT_BASE_DIR / case_name
            run_dir.mkdir(parents=True, exist_ok=True)

            logging.info(f"Running success case: {case_name}")

            # In Docker-in-Docker environments (like Kokoro), the path to the repo on the "Host" (the outer machine)
            # might be different from the path in the container running this test.
            # We need to pass the "Host" path to the sibling container for volume mounting.
            host_project_path = project_root
            if "ANDROID_BENCH_HOST_PATH" in os.environ:
                host_project_path = Path(os.environ["ANDROID_BENCH_HOST_PATH"])

            patch_score = score_patch(
                task=task_dict,
                client=client,
                run_dir=run_dir,
                job_name="integration_test_success",
                use_local_images=False,
                print_container_logs=True,
                host_project_path=host_project_path,
            )

            assert (
                patch_score.status in expected_statuses
            ), f"Status mismatch for {case_name}. Got {patch_score.status}, expected one of {expected_statuses}"
            assert (
                patch_score.score == 1.0
            ), f"Score mismatch for {case_name}. Got {patch_score.score}, expected 1.0"

    def test_run_invalid_patches(self):
        """
        Test the patch verifier with patches designed to cause specific failures.
        Verification:
        - apply_failed -> FAILED_TO_APPLY_PATCH
        - setup_issue -> SETUP_ISSUE
        - build_failed -> BUILD_FAILED
        - test_failed -> TEST_FAILED
        - missing_tests -> MISSING_REQUIRED_TEST_RESULTS
        """

        # Define the mapping of failure case directories to expected statuses
        expected_failures = {
            "apply_failed": Status.AGENT_FAILED_TO_APPLY_PATCH,
            "setup_issue": Status.INFRA_FAILURE_SETUP_ISSUE,
            "build_failed": Status.AGENT_FAILED_BUILD,
            "test_failed": Status.AGENT_FAILED_TEST,
            "missing_tests": Status.AGENT_MISSING_REQUIRED_TEST_RESULTS,
        }

        client = docker.from_env()

        # Locate the project root (assuming we are in tests/patch_verifier_integration_test)
        project_root = TEST_DIR.parents[1]

        for failure_type, expected_status in expected_failures.items():
            case_dir = INVALID_PATCH_DIR / failure_type
            task_yaml_path = case_dir / "task.yaml"

            assert (
                task_yaml_path.exists()
            ), f"Task definition not found for {failure_type}"

            # Load task definition
            with open(task_yaml_path, "r") as f:
                task_dict = yaml.safe_load(f)

            # Update patch paths to point to the failure case files
            # We need paths relative to the project root so they resolve correctly inside the container
            # when /android_bench is mounted.
            src_patch_path = case_dir / "src.patch"
            test_patch_path = case_dir / "test.patch"

            # Ensure patch files exist (create empty/dummy if needed for the test logic, though they should be there)
            if not src_patch_path.exists():
                # Only strictly required if the test logic fails without it, but let's warn
                logging.info(f"Warning: src.patch missing in {case_dir}")

            # Calculate relative paths for the container
            # failure_cases dir is usually tests/patch_verifier_integration_test/data/failure_cases
            # which is inside project root.
            rel_src_patch = src_patch_path.relative_to(project_root)
            rel_test_patch = test_patch_path.relative_to(project_root)

            task_dict["patch_file"] = f"/android_bench/{rel_src_patch}"
            task_dict["test_patch_file"] = f"/android_bench/{rel_test_patch}"

            # Prepare run directory for this case
            run_dir = OUTPUT_BASE_DIR / failure_type
            run_dir.mkdir(parents=True, exist_ok=True)

            logging.info(
                f"Running failure case: {failure_type} expecting {expected_status}"
            )

            # In Docker-in-Docker environments (like Kokoro), the path to the repo on the "Host" (the outer machine)
            # might be different from the path in the container running this test.
            # We need to pass the "Host" path to the sibling container for volume mounting.
            host_project_path = project_root
            if "ANDROID_BENCH_HOST_PATH" in os.environ:
                host_project_path = Path(os.environ["ANDROID_BENCH_HOST_PATH"])

            # Call score_patch directly
            patch_score = score_patch(
                task=task_dict,
                client=client,
                run_dir=run_dir,
                job_name="integration_test_local",
                use_local_images=False,
                print_container_logs=True,
                host_project_path=host_project_path,
            )

            logging.info(
                f"DEBUG: patch_score.status={patch_score.status} type={type(patch_score.status)} name={patch_score.status.name}"
            )
            logging.info(
                f"DEBUG: expected_status={expected_status} type={type(expected_status)}"
            )

            if patch_score.status.name != expected_status.name:
                msg = f"Status mismatch for {failure_type}. Got {patch_score.status.name}, expected {expected_status}. Diagnostics: {patch_score.diagnostics}"
                logging.error(msg)
                print(msg, flush=True)

            assert (
                patch_score.status.name == expected_status.name
            ), f"Status mismatch for {failure_type}. Got {patch_score.status.name}, expected {expected_status}. Diagnostics: {patch_score.diagnostics}"

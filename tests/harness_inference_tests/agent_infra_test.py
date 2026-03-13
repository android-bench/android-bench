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
import shutil
import os
from pathlib import Path
import pytest
from unittest.mock import patch, Mock
import pytest
from unittest.mock import MagicMock
from harness.inference.multimedia_processing_agent import MultimediaProcessingAgent
from minisweagent.agents.default import TerminatingException
from harness.inference.androidbench import (
    ImageType,
    run,
    sanitize_model_name_for_path,
    _transform_instance,
)
from common.config import BaseConfig as config
from common.constants import ROOT_DIR
from harness.inference.androidbench_runner import (
    get_patch_output_path,
    get_traj_output_path,
    save_patch,
)
import logging
import io
import json

# --- Logging and Constants ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
TEST_DIR = Path(__file__).parent

tasks_dir = TEST_DIR / "test_data"
patches_dir = TEST_DIR / "test_data/"
config_path = ROOT_DIR / "harness" / "inference" / "androidbench.yaml"


def test_skip_existing_patches(caplog):
    """Tests that skip_existing works as expected."""
    model_name = "gemini-pro"  # Default model
    instance_id = "airbnb__lottie-android-pr_2064"
    run_name = "test-run"

    # Create patch file in the expected location (out/test-run/patches/)
    patch_file = Path("out") / run_name / "patches" / f"{instance_id}.patch"
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.touch()

    try:
        with caplog.at_level(logging.INFO):
            run(
                tasks_dir=tasks_dir,
                instance_id=instance_id,
                skip_existing=True,
                dry_run=True,
                config_path=config_path,
                model_name=model_name,
                run_name=run_name,
            )
        assert f"Skipping instance {instance_id}" in caplog.text
    finally:
        # Cleanup the entire test run directory
        import shutil

        run_dir = Path("out") / run_name
        if run_dir.exists():
            shutil.rmtree(run_dir)


def test_instance_id_filtering(caplog):
    """Tests that the instance_id is correctly applied."""
    instance_id = "airbnb__lottie-android-pr_2064"
    with caplog.at_level(logging.INFO):
        run(
            tasks_dir=tasks_dir,
            instance_id=instance_id,
            dry_run=True,
            config_path=config_path,
        )
    assert "Preparing to run 1 instances" in caplog.text
    assert f"Instance {instance_id} finished successfully." in caplog.text


def test_image_name_is_correctly_applied(caplog):
    """Tests that the image name is correctly applied from the images parameter."""
    with patch(
        "harness.inference.androidbench_runner.setup_logger",
        return_value=logging.getLogger(),
    ):
        # Test remote image type
        with caplog.at_level(logging.INFO):
            run(
                tasks_dir=tasks_dir,
                instance_id="airbnb__lottie-android-pr_2064",
                docker_image_type=ImageType.REMOTE,
                dry_run=True,
                config_path=config_path,
            )
        assert (
            f"Using image: {config.docker_repository}/airbnb__lottie-android-pr_2064"
            in caplog.text
        )
        caplog.clear()

        # Test local image type
        with caplog.at_level(logging.INFO):
            run(
                tasks_dir=tasks_dir,
                instance_id="airbnb__lottie-android-pr_2064",
                docker_image_type=ImageType.LOCAL,
                dry_run=True,
                config_path=config_path,
            )
        assert "Using image: airbnb__lottie-android-pr_2064" in caplog.text
        caplog.clear()

        # Test base image type
        with caplog.at_level(logging.INFO):
            run(
                tasks_dir=tasks_dir,
                instance_id="airbnb__lottie-android-pr_2064",
                docker_image_type=ImageType.BASE,
                dry_run=True,
                config_path=config_path,
            )
        assert "Using image: android-bench-env" in caplog.text
        caplog.clear()

        # Test local image type
        with caplog.at_level(logging.INFO):
            run(
                tasks_dir=tasks_dir,
                instance_id="airbnb__lottie-android-pr_2064",
                docker_image_type=ImageType.LOCAL,
                dry_run=True,
                config_path=config_path,
            )
        assert "Using image: airbnb__lottie-android-pr_2064" in caplog.text
        caplog.clear()

        # Test base image type
        with caplog.at_level(logging.INFO):
            run(
                tasks_dir=tasks_dir,
                instance_id="airbnb__lottie-android-pr_2064",
                docker_image_type=ImageType.BASE,
                dry_run=True,
                config_path=config_path,
            )
        assert "Using image: android-bench-env" in caplog.text


def test_skip_existing_with_custom_model(caplog):
    """Tests that skip_existing works with a custom model."""
    model_name = "gemini/gemini-2.5-flash"
    instance_id = "airbnb__lottie-android-pr_2064"
    run_name = "test-custom-run"

    # Create patch file in the expected location (out/test-custom-run/patches/)
    patch_file = Path("out") / run_name / "patches" / f"{instance_id}.patch"
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.touch()

    try:
        with caplog.at_level(logging.INFO):
            run(
                tasks_dir=tasks_dir,
                instance_id=instance_id,
                skip_existing=True,
                dry_run=True,
                config_path=config_path,
                model_name=model_name,
                run_name=run_name,
            )
        assert "Skipping instance" in caplog.text
    finally:
        # Cleanup the entire test run directory
        import shutil

        run_dir = Path("out") / run_name
        if run_dir.exists():
            shutil.rmtree(run_dir)


def test_get_traj_output_path():
    """Tests the get_traj_output_path function."""
    traj_dir = Path("/tmp/trajectories")
    instance_id = "test-instance"
    expected_path = traj_dir / f"{instance_id}.json"
    assert get_traj_output_path(traj_dir, instance_id) == expected_path


def test_get_patch_output_path():
    """Tests the get_patch_output_path function."""
    patch_dir = Path("/tmp/patches")
    instance_id = "test-instance"
    expected_path = patch_dir / f"{instance_id}.patch"
    assert get_patch_output_path(patch_dir, instance_id) == expected_path


def test_dry_run_forwarding(caplog):
    """Tests that the dry_run parameter is correctly forwarded."""
    with patch(
        "harness.inference.androidbench_runner.setup_logger",
        return_value=logging.getLogger(),
    ):
        with caplog.at_level(logging.INFO):
            run(
                tasks_dir=tasks_dir,
                instance_id="airbnb__lottie-android-pr_2064",
                dry_run=True,
                config_path=config_path,
            )
    assert "Dry run mode, skipping agent execution" in caplog.text


def test_run_creates_exit_statuses_output_dir():
    """Tests that the exit_statuses_output_dir is created if it doesn't exist."""
    temp_dir = TEST_DIR / "temp_exit_statuses"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


def test_save_patch_with_diff_git():
    """Tests that save_patch saves a patch starting with 'diff --git'."""
    patch_content = "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py\n@@ -1,1 +1,1 @@\n-hello\n+world"
    patch_path = TEST_DIR / "test.patch"
    try:
        save_patch(patch_content, patch_path, logger)
        assert patch_path.exists()
        assert patch_path.read_text() == patch_content
    finally:
        if patch_path.exists():
            patch_path.unlink()


def test_save_patch_with_non_diff_git(caplog):
    """Tests that save_patch logs a warning if the patch doesn't start with 'diff --git'."""
    patch_content = "Authentication Error"
    patch_path = TEST_DIR / "test.patch"
    with caplog.at_level(logging.WARNING):
        save_patch(patch_content, patch_path, logger)
    assert f"Agent did not output patch: {patch_content}" in caplog.text
    assert not patch_path.exists()


def test_sanitize_model_name():
    """Tests sanitize_model_name_for_path with simple provider/model format."""
    assert (
        sanitize_model_name_for_path("gemini/gemini-2.5-pro") == "gemini-gemini-2.5-pro"
    )
    assert (
        sanitize_model_name_for_path("gemini/gemini-2.5-flash")
        == "gemini-gemini-2.5-flash"
    )
    assert sanitize_model_name_for_path("openai/gpt-4") == "openai-gpt-4"
    assert sanitize_model_name_for_path("model") == "model"

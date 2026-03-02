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
from pathlib import Path
from unittest.mock import MagicMock, patch
from common.models.benchmark import EnvConfig, BenchmarkTask


@pytest.fixture
def minimal_json_data():
    return {
        "instance_id": "test-id-123",
        "repository": {"url": "https://example.com/repo.git"},
        "commands": {},
        "acceptance_criteria": {"fail_to_pass": [], "pass_to_pass": []},
    }


@pytest.fixture
def mock_path_exists(mocker):
    return mocker.patch("common.models.benchmark.Path.exists", return_value=True)


@pytest.fixture
def mock_path_is_file(mocker):
    return mocker.patch("common.models.benchmark.Path.is_file", return_value=True)


def test_from_json_jdk(mock_path_exists, mock_path_is_file):
    patch_base = "/fake/patches"
    mock_path_exists.return_value = True

    json = {
        "instance_id": "test-id-123",
        "repository": {"url": "https://example.com/repo.git"},
        "commands": {},
        "acceptance_criteria": {"fail_to_pass": [], "pass_to_pass": []},
        "after_commit": {"java_version": 11},
    }
    task = BenchmarkTask.from_json(json, patch_base)

    assert task is not None
    assert task.env_config.jdk_version == 11


def test_from_json_happy_path(minimal_json_data, mock_path_exists, mock_path_is_file):
    patch_base = "/fake/patches"
    mock_path_exists.return_value = True

    task = BenchmarkTask.from_json(minimal_json_data, patch_base)

    assert task is not None
    assert task.instance_id == "test-id-123"
    assert task.repo_url == "https://example.com/repo.git"
    assert isinstance(task.patch_file, Path)  # Check it's a real Path object
    assert task.env_config.jdk_version == 17


def test_from_json_missing_instance_id(minimal_json_data):
    del minimal_json_data["instance_id"]

    with pytest.raises(ValueError, match="instance_id is required in JSON"):
        BenchmarkTask.from_json(minimal_json_data, "/fake/patches")


def test_from_json_missing_repo_url(minimal_json_data):
    del minimal_json_data["repository"]

    with pytest.raises(ValueError, match="repository.url is required in JSON"):
        BenchmarkTask.from_json(minimal_json_data, "/fake/patches")


def test_from_json_patch_file_does_not_exist(
    minimal_json_data, mock_path_exists, caplog
):
    mock_path_exists.return_value = False

    task = BenchmarkTask.from_json(minimal_json_data, "/fake/patches")

    assert task is None
    assert "Patch file for instance 'test-id-123' not found" in caplog.text


def test_post_init_default_startup_script(mock_path_is_file):
    fake_patch = Path("fake.patch")

    task = BenchmarkTask(
        instance_id="id1",
        repo_url="https://test.com/my-repo.git",
        patch_file=fake_patch,
    )

    assert isinstance(task.startup_script, Path)
    assert str(task.startup_script) == "launch_scripts/my-repo.sh"


def test_post_init_patch_file_not_found(mock_path_is_file):
    mock_path_is_file.return_value = False

    with pytest.raises(
        FileNotFoundError, match="Patch file for instance 'id1' not found"
    ):
        BenchmarkTask(instance_id="id1", repo_url="url", patch_file=Path("fake.patch"))


def test_from_json_commands(mock_path_exists, mock_path_is_file):
    mock_path_exists.return_value = True
    json_data = {
        "instance_id": "test-id",
        "repository": {"url": "https://example.com/repo.git"},
        "commands": {
            "build": ["./gradlew build"],
            "unit_test": ["./gradlew test"],
            "android_test": ["./gradlew connectedAndroidTest"],
        },
        "acceptance_criteria": {"fail_to_pass": [], "pass_to_pass": []},
    }
    task = BenchmarkTask.from_json(json_data, "/fake/patches")

    assert task
    assert task.build_commands == ["./gradlew build"]
    assert task.test_commands == ["./gradlew test", "./gradlew connectedAndroidTest"]


def test_from_json_missing_commands(mock_path_exists, mock_path_is_file):
    mock_path_exists.return_value = True
    json_data = {
        "instance_id": "test-id",
        "repository": {"url": "https://example.com/repo.git"},
        "acceptance_criteria": {"fail_to_pass": [], "pass_to_pass": []},
    }
    task = BenchmarkTask.from_json(json_data, "/fake/patches")

    assert task
    assert task.build_commands == []
    assert task.test_commands == []

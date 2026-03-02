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
import io
import tarfile
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call, ANY
from docker import DockerClient
from docker.errors import ContainerError
from harness.evaluation.benchmark_worker import score_patch
from common.models.benchmark import PatchScore, Status
from common.config import BaseConfig

config = BaseConfig()


@pytest.fixture
def mock_docker_client(mocker):
    return mocker.MagicMock(spec=DockerClient)


@pytest.fixture
def mock_container(mocker):
    container = mocker.MagicMock()
    container.name = "mock_container_name"
    container.wait.return_value = {"StatusCode": 0}

    def logs_side_effect(stream=False, follow=False):
        if stream:
            return [b"Mock container logs stream"]
        return b"Mock container logs"

    container.logs.side_effect = logs_side_effect
    container.stop.return_value = None
    container.remove.return_value = None
    return container


@pytest.fixture
def setup_paths(tmp_path):
    project_root = tmp_path / "android_bench_project"
    run_dir = project_root / "out" / "test_run"
    run_dir.mkdir(parents=True)
    (run_dir / "patches").mkdir()
    return project_root, run_dir


def test_happy_path_remote_image(
    mocker,
    mock_docker_client,
    mock_container,
    setup_paths,
):
    # Arrange
    project_root, run_dir = setup_paths
    task = {"instance_id": "test_success"}
    mock_container.get_archive.return_value = ([], "mock_stat")
    mock_docker_client.containers.run.return_value = mock_container
    mock_extracted_file = MagicMock()
    mock_extracted_file.read.return_value = b'{"test_success": {"score": 1.0, "status": "PASSED", "diagnostics": ["All tests passed"]}}'
    mock_tar = MagicMock()
    mock_tar.extractfile.return_value = mock_extracted_file
    mock_tarfile_open = mocker.patch("harness.evaluation.benchmark_worker.tarfile.open")
    mock_tarfile_open.return_value.__enter__.return_value = mock_tar
    mock_path_class = mocker.patch("harness.evaluation.benchmark_worker.Path")
    mock_path_instance = mock_path_class.return_value
    mock_path_instance.resolve.return_value.parent.parent.parent = project_root
    expected_patch_dir_in_container = "/android_bench/patches"
    mock_path_instance.__truediv__.return_value.as_posix.return_value = (
        expected_patch_dir_in_container
    )

    # Act
    result = score_patch(
        task,
        mock_docker_client,
        run_dir,
        job_name="test_job",
        use_local_images=False,
    )

    # Assert
    assert isinstance(result, PatchScore)
    assert result.instance_id == "test_success"
    assert result.score == 1.0
    assert result.status == Status.PASSED
    assert result.diagnostics == "All tests passed"


def test_uppercase_instance_id_is_lowercased_for_image_name(
    mocker,
    mock_docker_client,
    mock_container,
    setup_paths,
):
    # Arrange
    project_root, run_dir = setup_paths
    task = {"instance_id": "TEST_UPPERCASE"}
    mock_container.get_archive.return_value = ([], "mock_stat")
    mock_docker_client.containers.run.return_value = mock_container
    mock_extracted_file = MagicMock()
    mock_extracted_file.read.return_value = b'{"TEST_UPPERCASE": {"score": 1.0, "status": "PASSED", "diagnostics": ["All tests passed"]}}'
    mock_tar = MagicMock()
    mock_tar.extractfile.return_value = mock_extracted_file
    mock_tarfile_open = mocker.patch("harness.evaluation.benchmark_worker.tarfile.open")
    mock_tarfile_open.return_value.__enter__.return_value = mock_tar
    mock_path_class = mocker.patch("harness.evaluation.benchmark_worker.Path")
    mock_path_instance = mock_path_class.return_value
    mock_path_instance.resolve.return_value.parent.parent.parent = project_root
    expected_patch_dir_in_container = "/android_bench/patches"
    mock_path_instance.__truediv__.return_value.as_posix.return_value = (
        expected_patch_dir_in_container
    )

    # Act
    result = score_patch(
        task,
        mock_docker_client,
        run_dir,
        job_name="test_job",
        use_local_images=False,
    )

    # Assert
    mock_docker_client.containers.run.assert_called_once()
    args, kwargs = mock_docker_client.containers.run.call_args
    expected_image_name = f"{config.docker_repository}/test_uppercase"
    assert args[0] == expected_image_name
    assert isinstance(result, PatchScore)
    assert result.instance_id == "TEST_UPPERCASE"
    assert result.score == 1.0
    assert result.status == Status.PASSED


def test_local_image_build(
    mocker,
    mock_docker_client,
    mock_container,
    setup_paths,
):
    # Arrange
    project_root, run_dir = setup_paths
    task = {"instance_id": "local_build_task"}
    mock_container.get_archive.return_value = ([], "mock_stat")
    mock_docker_client.containers.run.return_value = mock_container
    mock_extracted_file = MagicMock()
    mock_extracted_file.read.return_value = b'{"local_build_task": {"score": 1.0, "status": "PASSED", "diagnostics": ["All tests passed"]}}'
    mock_tar = MagicMock()
    mock_tar.extractfile.return_value = mock_extracted_file
    mock_tarfile_open = mocker.patch("harness.evaluation.benchmark_worker.tarfile.open")
    mock_tarfile_open.return_value.__enter__.return_value = mock_tar
    mock_path_class = mocker.patch("harness.evaluation.benchmark_worker.Path")
    mock_path_instance = mock_path_class.return_value
    mock_path_instance.resolve.return_value.parent.parent.parent = project_root
    mock_path_instance.__truediv__.return_value.as_posix.return_value = (
        "/android_bench/patches"
    )

    # Act
    result = score_patch(
        task,
        mock_docker_client,
        run_dir,
        job_name="test_job",
        use_local_images=True,
    )

    # Assert
    assert isinstance(result, PatchScore)
    assert result.instance_id == "local_build_task"
    assert result.score == 1.0
    assert result.status == Status.PASSED


def test_container_failure_non_zero_exit_status(
    mocker,
    mock_docker_client,
    mock_container,
    setup_paths,
):
    # Arrange
    project_root, run_dir = setup_paths
    task = {"instance_id": "exit_code_1_task"}
    mock_docker_client.containers.run.return_value = mock_container
    mock_container.wait.return_value = {"StatusCode": 1}
    mock_path_class = mocker.patch("harness.evaluation.benchmark_worker.Path")
    mock_path_instance = mock_path_class.return_value
    mock_path_instance.resolve.return_value.parent.parent.parent = project_root
    mock_path_instance.__truediv__.return_value.as_posix.return_value = (
        "/android_bench/patches"
    )

    # Act
    result = score_patch(
        task,
        mock_docker_client,
        run_dir,
        job_name="test_job",
        use_local_images=False,
    )

    # Assert
    expected_log_path = run_dir / "verifier" / "exit_code_1_task" / "log.txt"
    assert isinstance(result, PatchScore)
    assert result.instance_id == "exit_code_1_task"
    assert result.score == 0.0
    assert result.status == Status.INFRA_FAILURE
    assert str(expected_log_path) in result.diagnostics


def test_container_error_on_run(
    mocker,
    mock_docker_client,
    mock_container,
    setup_paths,
):
    # Arrange
    project_root, run_dir = setup_paths
    task = {"instance_id": "container_error_task"}
    mock_docker_client.containers.run.side_effect = ContainerError(
        "Mock container error", 1, "cmd", "img", "logs"
    )
    mock_path_class = mocker.patch("harness.evaluation.benchmark_worker.Path")
    mock_path_instance = mock_path_class.return_value
    mock_path_instance.resolve.return_value.parent.parent.parent = project_root
    mock_path_instance.__truediv__.return_value.as_posix.return_value = (
        "/android_bench/patches"
    )

    # Act
    result = score_patch(
        task,
        mock_docker_client,
        run_dir,
        job_name="test_job",
        use_local_images=False,
    )

    # Assert
    expected_error_string = (
        "Command 'cmd' in image 'img' returned non-zero exit status 1: logs"
    )
    assert isinstance(result, PatchScore)
    assert result.instance_id == "container_error_task"
    assert result.score == 0.0
    assert result.status == Status.INFRA_FAILURE
    assert expected_error_string in result.diagnostics


def test_generic_exception(
    mocker,
    mock_docker_client,
    mock_container,
    setup_paths,
):
    # Arrange
    project_root, run_dir = setup_paths
    task = {"instance_id": "generic_exception_task"}
    # Make json.dump raise an exception
    mocker.patch(
        "harness.evaluation.benchmark_worker.json.dump",
        side_effect=Exception("A non-docker error"),
    )
    mock_path_class = mocker.patch("harness.evaluation.benchmark_worker.Path")
    mock_path_instance = mock_path_class.return_value
    mock_path_instance.resolve.return_value.parent.parent.parent = project_root
    mock_path_instance.__truediv__.return_value.as_posix.return_value = (
        "/android_bench/patches"
    )

    # Act
    result = score_patch(
        task,
        mock_docker_client,
        run_dir,
        job_name="test_job",
        use_local_images=False,
    )

    # Assert
    assert isinstance(result, PatchScore)
    assert result.instance_id == "generic_exception_task"
    assert result.score == 0.0
    assert result.status == Status.INFRA_FAILURE
    assert "A non-docker error" in result.diagnostics


def test_invalid_patch_dir_valueerror(
    mocker,
    mock_docker_client,
    tmp_path,
):
    # Arrange
    project_root = tmp_path / "project"
    run_dir = tmp_path / "other_dir" / "run"
    project_root.mkdir()
    run_dir.mkdir(parents=True)
    (run_dir / "patches").mkdir()
    task = {"instance_id": "bad_patch_path_task"}
    mock_path_class = mocker.patch("harness.evaluation.benchmark_worker.Path")
    mock_path_instance = mock_path_class.return_value
    mock_path_instance.resolve.return_value.parent.parent.parent = project_root
    mock_path_instance.__truediv__.return_value.as_posix.return_value = (
        "/android_bench/patches"
    )

    # Act
    result = score_patch(
        task,
        mock_docker_client,
        run_dir,
        job_name="test_job",
        use_local_images=False,
    )

    # Assert
    assert isinstance(result, PatchScore)
    assert result.instance_id == "bad_patch_path_task"
    assert result.score == 0.0
    assert result.status == Status.INFRA_FAILURE
    assert "is not in the subpath of" in result.diagnostics

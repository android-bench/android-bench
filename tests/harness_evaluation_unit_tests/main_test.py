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
import yaml
import json
import docker
from pathlib import Path
from unittest.mock import MagicMock, patch, call, ANY
from datetime import datetime
from harness.evaluation.main import score_patches, main
from common.models.benchmark import BenchmarkTask, PatchScore, Status


@pytest.fixture
def mock_benchmark_task_from_json(mocker):
    mock_task = MagicMock(spec=BenchmarkTask)
    mock_task.instance_id = "task_1"
    mock_task.used_tokens = None
    mock_task.latency_details = None
    return mocker.patch(
        "harness.evaluation.main.BenchmarkTask.from_json", return_value=mock_task
    )


@pytest.fixture
def mock_open(mocker):
    return mocker.patch("harness.evaluation.main.open", mocker.mock_open())


@pytest.fixture
def mock_json_load(mocker):
    return mocker.patch("harness.evaluation.main.json.load", return_value={})


@pytest.fixture
def mock_json_dump(mocker):
    return mocker.patch("harness.evaluation.main.json.dump")


@pytest.fixture
def mock_input(mocker):
    return mocker.patch("harness.evaluation.main.input", return_value="y")


@pytest.fixture
def mock_docker_client(mocker):
    mock_client_instance = MagicMock(spec=docker.DockerClient)
    mock_from_env = mocker.patch("harness.evaluation.main.docker.DockerClient.from_env")
    mock_from_env.return_value = mock_client_instance
    mock_client_instance.ping.return_value = True
    return mock_from_env


@pytest.fixture
def mock_score_patch(mocker):
    def side_effect_func(task_json, client, *args):
        instance_id = task_json.get("instance_id", "unknown_mock_id")
        return PatchScore(
            instance_id=instance_id,
            score=1.0,
            status=Status.PASSED,
            diagnostics="All tests passed",
            job_name="test_job",
            steps="0",
            cost="$0.0",
            used_tokens=None,
            latency_details=None,
        )

    return mocker.patch(
        "harness.evaluation.main.score_patch",
        side_effect=side_effect_func,
    )


@pytest.fixture
def mock_os_makedirs(mocker):
    return mocker.patch("harness.evaluation.main.os.makedirs")


@pytest.fixture
def mock_load_all_tasks(mocker):
    mock_task = MagicMock()
    mock_task.model_dump.return_value = {"instance_id": "task_1"}
    return mocker.patch(
        "harness.evaluation.main.load_all_tasks", return_value=[mock_task]
    )


@pytest.fixture
def mock_read_run_config(mocker):
    return mocker.patch(
        "harness.evaluation.main.read_run_config",
        return_value={"model_name": "model_1", "run_name": "test_run"},
    )


@pytest.fixture
def mock_score_patches(mocker):
    return mocker.patch("harness.evaluation.main.score_patches")


def test_score_patches_happy_path(
    mocker,
    mock_benchmark_task_from_json,
    mock_open,
    mock_json_load,
    mock_json_dump,
    mock_docker_client,
    mock_score_patch,
    mock_os_makedirs,
    mock_input,
    mock_load_all_tasks,
):
    # Arrange
    run_dir = Path("/fake/run")
    tasks_dir = Path("/fake/tasks")
    mocker.patch("harness.evaluation.main.Path.exists", return_value=True)
    mock_mkdir = mocker.patch("harness.evaluation.main.Path.mkdir")

    # Act
    score_patches(
        run_dir=run_dir,
        tasks_dir=tasks_dir,
        max_parallel_containers=1,
        job_name="test_job",
    )

    # Assert
    expected_scores = {
        "task_1": {
            "instance_id": "task_1",
            "score": 1.0,
            "status": "PASSED",
            "status_description": "PASSED",
            "diagnostics": "All tests passed",
            "job_name": "test_job",
            "steps": "0",
            "cost": "$0.0",
            "used_tokens": None,
            "latency_details": None,
        }
    }
    call_args, call_kwargs = mock_json_dump.call_args
    assert call_args[0] == expected_scores


def test_main_happy_path(
    mock_load_all_tasks,
    mock_read_run_config,
    mock_score_patches,
    mock_open,
    mocker,
):
    # Arrange
    run_name = "test_run_20240101_120000"
    tasks_dir = Path("tasks")
    mocker.patch("harness.evaluation.main.setup_file_logging")

    # Act
    main(
        run_name=run_name,
        tasks_dir=tasks_dir,
    )

    # Assert
    assert mock_score_patches.call_count == 1
    call_kwargs = mock_score_patches.call_args.kwargs
    assert isinstance(call_kwargs["run_dir"], Path)
    assert call_kwargs["tasks_dir"] == tasks_dir


def test_main_reads_config(
    mock_load_all_tasks,
    mock_read_run_config,
    mock_score_patches,
    mock_open,
    mocker,
):
    # Arrange
    run_name = "custom_run"
    mocker.patch("harness.evaluation.main.setup_file_logging")

    # Act
    main(run_name=run_name)

    # Assert
    mock_read_run_config.assert_called_once()
    assert mock_score_patches.call_count == 1
    call_kwargs = mock_score_patches.call_args.kwargs
    assert isinstance(call_kwargs["run_dir"], Path)


def test_parse_exit_status(tmp_path):
    from harness.evaluation.main import parse_exit_status

    yaml_content = {
        "instances_by_exit_status": {
            "Submitted": ["task1", "task2"],
            "LimitsExceeded": ["task3"],
            "AuthenticationError": ["task4"],
            "OtherError": ["task5"],
        }
    }
    yaml_path = tmp_path / "agent_exit_status.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(yaml_content, f)

    status_map = parse_exit_status(yaml_path)
    assert status_map == {
        "task1": "Submitted",
        "task2": "Submitted",
        "task3": "LimitsExceeded",
        "task4": "AuthenticationError",
        "task5": "OtherError",
    }


def test_score_patches_initial_population(
    mocker,
    mock_benchmark_task_from_json,
    mock_docker_client,
    mock_os_makedirs,
    mock_input,
    tmp_path,
):
    # Arrange
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    log_dir = run_dir / "logs"
    log_dir.mkdir()
    traj_dir = run_dir / "trajectories"
    traj_dir.mkdir()
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()

    # Mock agent_exit_status.yaml
    yaml_content = {
        "instances_by_exit_status": {
            "Submitted": ["task1"],
            "LimitsExceeded": ["task2"],
            "AuthenticationError": ["task3"],
            "OtherError": ["task4"],
        }
    }
    from common.constants import AGENT_EXIT_STATUS_FILE

    with open(log_dir / AGENT_EXIT_STATUS_FILE, "w") as f:
        yaml.dump(yaml_content, f)

    # Mock trajectory file with traceback for task2
    traceback_content = (
        'Traceback (most recent call last):\n  File "...", line 1, in <module>\n'
        '    raise Exception("limits exceeded")'
    )
    traj_content = {"info": {"traceback": traceback_content}}
    with open(traj_dir / "task2.json", "w") as f:
        json.dump(traj_content, f)

    # Mock tasks
    mock_task_objs = []
    for i in range(1, 6):
        m = MagicMock()
        m.instance_id = f"task{i}"
        m.model_dump.return_value = {"instance_id": f"task{i}"}
        m.patch_file = None
        m.test_patch_file = None
        m.steps = "0"
        m.cost = "$0.0"
        m.used_tokens = None
        m.latency_details = None
        mock_task_objs.append(m)

    mocker.patch("harness.evaluation.main.load_all_tasks", return_value=mock_task_objs)
    mock_from_json = mocker.patch(
        "harness.evaluation.main.BenchmarkTask.from_json",
        side_effect=lambda data, patch_dir, is_test_task: next(
            t for t in mock_task_objs if t.instance_id == data["instance_id"]
        ),
    )

    mock_json_dump = mocker.patch("harness.evaluation.main.json.dump")

    # Act
    # Mock as_completed to avoid issues with mocked futures
    mocker.patch("harness.evaluation.main.as_completed", return_value=[])
    # Mock score_patch to avoid actual execution
    mocker.patch("harness.evaluation.main.score_patch")

    score_patches(
        run_dir=run_dir,
        tasks_dir=tasks_dir,
        max_parallel_containers=1,
        job_name="test_job",
    )

    # Assert
    # The first call to json.dump should be the initial scores
    assert mock_json_dump.called
    initial_scores = mock_json_dump.call_args_list[0][0][0]

    # Task 1: Submitted (no traceback expected)
    assert initial_scores["task1"]["status"] == Status.AGENT_NO_PATCH.name
    assert "Agent provided no patch" in initial_scores["task1"]["status_description"]

    # Task 2: LimitsExceeded (traceback expected)
    assert (
        initial_scores["task2"]["status"]
        == Status.INFRA_FAILURE_AGENT_LIMITS_EXCEEDED.name
    )
    assert "LimitsExceeded" in initial_scores["task2"]["status_description"]
    assert f"|{traceback_content}" in initial_scores["task2"]["diagnostics"]

    # Task 3: AuthenticationError
    assert (
        initial_scores["task3"]["status"] == Status.INFRA_FAILURE_AGENT_AUTH_ERROR.name
    )
    assert "AuthenticationError" in initial_scores["task3"]["status_description"]

    # Task 4: OtherError
    assert initial_scores["task4"]["status"] == Status.INFRA_FAILURE_AGENT.name
    assert "General agent failure" in initial_scores["task4"]["status_description"]

    # Task 5: No exit status (not in yaml)
    assert initial_scores["task5"]["status"] == Status.AGENT_NO_PATCH.name

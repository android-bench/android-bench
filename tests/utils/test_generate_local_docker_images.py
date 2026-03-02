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
import os
from unittest.mock import patch, mock_open, MagicMock
import yaml

from utils.docker import generate_docker_images


def test_dump_known_failures(mocker, tmp_path, monkeypatch):
    """Tests that known_failures.yaml is created with the correct content."""
    mocker.patch("sys.argv", ["generate_docker_images.py"])
    mock_load_tasks = mocker.patch("utils.docker.generate_docker_images.load_all_tasks")
    mocker.patch("utils.docker.generate_docker_images._build_images")
    mocker.patch("shutil.rmtree")
    mocker.patch("os.path.exists", return_value=True)

    monkeypatch.chdir(tmp_path)
    mock_load_tasks.return_value = []
    generate_docker_images.failed_builds = ["failed_image_1"]

    generate_docker_images.main()

    output_file = tmp_path / "known_failures.yaml"
    assert output_file.exists()

    with open(output_file, "r") as f:
        content = yaml.safe_load(f)
        assert content == ["failed_image_1"]

    # Reset failed_builds to avoid side effects in other tests
    generate_docker_images.failed_builds = []


def test_build_docker_image_with_arch(mocker):
    mock_popen = mocker.patch("subprocess.Popen")
    mock_process = MagicMock()
    mock_process.stdout = []
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    mock_build_manager = MagicMock()

    generate_docker_images.build_docker_image(
        image_name="test-image",
        dockerfile_path="Dockerfile",
        total=1,
        context_dir=".",
        build_manager=mock_build_manager,
        arch="linux/arm64",
    )

    expected_command = [
        "docker",
        "build",
        "--platform",
        "linux/arm64",
        "-t",
        "test-image",
        "-f",
        "Dockerfile",
        ".",
    ]
    mock_popen.assert_called_once()
    actual_command = mock_popen.call_args[0][0]
    # Check that the platform flag is included
    assert "--platform" in actual_command
    assert "linux/arm64" in actual_command

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
import json
import logging
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import litellm
import yaml
from harness.inference.multimedia_processing_agent import MultimediaProcessingAgent
from minisweagent.run.extra.utils.batch_progress import RunBatchProgressManager
from tenacity import RetryError
from minisweagent.agents.default import TerminatingException
from harness.inference.androidbench import run
from harness.inference.androidbench_runner import get_traj_output_path

logger = logging.getLogger(__name__)
TEST_DIR = Path(__file__).parent
tasks_dir = TEST_DIR / "test_data"


@pytest.fixture
def retry_agent():
    mock_progress_manager = MagicMock(spec=RunBatchProgressManager)
    mock_config = MagicMock()
    mock_config.step_limit = (
        0  # Set to 0 to disable step limit for these tests initially
    )
    mock_config.cost_limit = (
        0.0  # Set to 0.0 to disable cost limit for these tests initially
    )
    agent = MultimediaProcessingAgent(
        progress_manager=mock_progress_manager,
        instance_id="test_instance",
        model_name="test_model",
        config_class=lambda **k: mock_config,  # DefaultAgent calls this with kwargs
        model=MagicMock(),  # Mock model
        env=MagicMock(),
    )
    # Mock the model's query method
    agent.model = MagicMock()
    agent.messages = []
    return agent


def test_query_success_no_retry(retry_agent):
    """Test query success without any retries."""
    expected_response = {"content": "success"}
    retry_agent.model.query.return_value = expected_response

    response = retry_agent.query()

    assert response == expected_response
    assert retry_agent.model.query.call_count == 1


def test_query_retry_on_502(retry_agent):
    """Test retry on 502 Bad Gateway error."""
    error_502 = litellm.APIError(
        status_code=502,
        message="Bad Gateway",
        llm_provider="openai",
        model="test_model",
    )
    expected_response = {"content": "success"}

    # Fail once with 502, then succeed
    retry_agent.model.query.side_effect = [error_502, expected_response]

    # Patch tenacity to avoid actual waiting during tests
    with patch(
        "harness.inference.multimedia_processing_agent.wait_fixed",
        return_value=lambda *args, **kwargs: 0,
    ):
        response = retry_agent.query()

    assert response == expected_response
    assert retry_agent.model.query.call_count == 2


def test_query_retry_exhausted_on_502(retry_agent):
    """Test that exception is raised after retries are exhausted on 502 error."""
    error_502 = litellm.APIError(
        status_code=502,
        message="Bad Gateway",
        llm_provider="openai",
        model="test_model",
    )

    # Fail on every call
    retry_agent.model.query.side_effect = error_502
    with patch(
        "harness.inference.multimedia_processing_agent.wait_fixed",
        return_value=lambda *args, **kwargs: 0,
    ):
        with pytest.raises(litellm.APIError):
            retry_agent.query()

    # Should be called 4 times (1 attempt + 3 retries)
    assert retry_agent.model.query.call_count == 4


def test_query_no_retry_on_400(retry_agent):
    """Test that non-retryable errors (e.g., 400) raise immediately."""
    error_400 = litellm.BadRequestError(
        message="Bad Request",
        llm_provider="openai",
        model="test_model",
        response=MagicMock(),
    )

    retry_agent.model.query.side_effect = error_400

    with pytest.raises(litellm.BadRequestError):
        retry_agent.query()

    assert retry_agent.model.query.call_count == 1


# --- Image Handling Tests ---


@pytest.fixture
def clean_image_description_file():
    """
    Fixture to clean the image_description file from previous run if any
    """
    file_to_remove = "/tmp/image_description.txt"
    try:
        if os.path.exists(file_to_remove):
            os.remove(file_to_remove)
            logger.info(f"Removed: {file_to_remove}")
    except Exception as e:
        logger.warning(f"Error removing {file_to_remove}: {e}")


@pytest.mark.image_test
@pytest.mark.local
@pytest.mark.usefixtures("clean_image_description_file")
def test_call_agent_with_thunderbird_instance(caplog):
    """Tests the capabilities of the agent to describe images.A dummy
    instance with 4 random image links are used for this test.
    The generated image description will be inside android_bench_agent/test_data dir"""

    instance_id = "thunderbird__thunderbird-android-pr_8806"
    output_dir = None
    try:
        with caplog.at_level(logging.INFO):
            run(
                tasks_dir=tasks_dir,
                instance_id=instance_id,
                config_path=TEST_DIR / "test_data" / "image_describe_task.yaml",
            )

        output_dir_str = ""
        for record in caplog.records:
            if "Outputs will be saved to:" in record.message:
                output_dir_str = record.message.split("Outputs will be saved to: ")[
                    1
                ].strip()
                break

        assert output_dir_str, "Output directory not found in logs"
        output_dir = Path(output_dir_str)
        traj_file = get_traj_output_path(output_dir / "trajectories", instance_id)

        assert traj_file.exists(), f"Trajectory file not found at {traj_file}"

        with open(traj_file) as f:
            trajectory = json.load(f)

        assert trajectory is not None, "Trajectory not found in caplog records"

        assistant_content = ""
        for message in trajectory["messages"]:
            if message["role"] == "assistant":
                assistant_content = message["content"]
                break

        task_yaml_path = tasks_dir / instance_id / "task.yaml"
        with open(task_yaml_path) as f:
            task_data = yaml.safe_load(f)
        image_urls = task_data.get("image_urls", [])
        image_urls_str = ""
        for id, url in enumerate(image_urls):
            image_urls_str += f"Image url {id+1}: {url} \n"
        video_urls = task_data.get("video_urls", [])
        video_urls_str = ""
        for id, url in enumerate(video_urls):
            video_urls_str += f"Video url {id+1}: {url} \n"
        assistant_content = image_urls_str + video_urls_str + assistant_content
        # assert the time shown in the screenshot image to be sure that the test passed.
        assert "9:48" in assistant_content
        assert "4:12" in assistant_content
        # this change was required to not pollute the source-code directory with the image description file
        output_file = Path("/tmp/image_description.txt")
        output_file.write_text(assistant_content)
        logger.info(f"Image description saved to {output_file}")
    finally:
        if output_dir and output_dir.exists():
            shutil.rmtree(output_dir)


class MockProgressManager:
    def update_instance_status(self, *args, **kwargs):
        pass


@pytest.fixture
def mock_agent():
    env = MagicMock()
    model = MagicMock()
    model.name = "test-model"

    with patch("litellm.supports_vision", return_value=True):
        agent = MultimediaProcessingAgent(
            model=model,
            env=env,
            progress_manager=MockProgressManager(),
            instance_id="test_instance",
            model_name="test-model",
            config_class=lambda **k: MagicMock(),
        )
    # Mock render_template to return the template string itself to avoid asdict error
    agent.render_template = MagicMock(side_effect=lambda x: x)

    agent.config.system_template = "System prompt"
    agent.config.instance_template = "Instance prompt"
    return agent


def test_image_urls_passed_to_messages(mock_agent):
    image_urls = [
        "https://example.com/image1.png",
        "https://example.com/image2.png",
    ]
    mock_agent.step = MagicMock(side_effect=TerminatingException("Done"))

    with patch("litellm.supports_vision", return_value=True):
        mock_agent.run(task="Test Task", image_data=image_urls)
    for i, msg in enumerate(mock_agent.messages):
        print(f"Message {i}: {msg}")

    # Collect all image URLs from all messages
    urls_found = []
    for msg in mock_agent.messages:
        if msg["role"] == "user" and isinstance(msg["content"], list):
            for item in msg["content"]:
                if item.get("type") == "image_url":
                    urls_found.append(item["image_url"]["url"])

    assert (
        urls_found == image_urls
    ), f"Expected {image_urls}, but found {urls_found} in agent messages: {mock_agent.messages}"


def test_image_urls_not_passed_if_vision_not_supported(mock_agent):
    image_urls = ["https://example.com/image1.png"]
    with patch("litellm.supports_vision", return_value=False):
        mock_agent.step = MagicMock(side_effect=TerminatingException("Done"))
        mock_agent.run(task="Test Task", image_data=image_urls)

        # Check correctness
        for msg in mock_agent.messages:
            if isinstance(msg["content"], list):
                for item in msg["content"]:
                    assert (
                        item.get("type") != "image_url"
                    ), "Image URL found even when vision not supported"

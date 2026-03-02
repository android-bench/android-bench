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
import json
import pytest
from pathlib import Path

from results.summarize_results import ScoreConfig, summarize_scores
from common.models.benchmark import Status


@pytest.fixture
def sample_scores_files(tmp_path):
    """Create sample score files for testing."""
    # Model A - Run 1
    model_a_run1 = tmp_path / "model_a_run1.json"
    model_a_run1.write_text(
        json.dumps(
            {
                "instance_1": {"score": 1.0, "status": Status.PASSED.name},
                "instance_2": {"score": 0.0, "status": Status.AGENT_FAILED_BUILD.name},
                "instance_3": {"score": 1.0, "status": Status.PASSED.name},
            }
        )
    )

    # Model A - Run 2 (for averaging)
    model_a_run2 = tmp_path / "model_a_run2.json"
    model_a_run2.write_text(
        json.dumps(
            {
                "instance_1": {"score": 1.0, "status": Status.PASSED.name},
                "instance_2": {"score": 1.0, "status": Status.PASSED.name},
                "instance_3": {"score": 0.0, "status": Status.AGENT_FAILED_TEST.name},
            }
        )
    )

    # Model B - Single run
    model_b_run1 = tmp_path / "model_b_run1.json"
    model_b_run1.write_text(
        json.dumps(
            {
                "instance_2": {"score": 0.0, "status": Status.AGENT_FAILED_BUILD.name},
                "instance_1": {
                    "score": 0.0,
                    "status": Status.INFRA_FAILURE_AGENT.name,
                },
            }
        )
    )

    return {
        "model_a_run1": model_a_run1,
        "model_a_run2": model_a_run2,
        "model_b_run1": model_b_run1,
    }


def test_summarize_scores_single_model(sample_scores_files):
    configs = [
        ScoreConfig(
            model_name="model_a", scores_path=sample_scores_files["model_a_run1"]
        )
    ]

    result = summarize_scores(configs)

    lines = result.split("\n")
    assert lines[0] == "model,PASSED,AGENT_FAILED_BUILD,TOTAL"
    assert lines[1] == "model_a,2,1,3"


def test_summarize_scores_multiple_models(sample_scores_files):
    configs = [
        ScoreConfig(
            model_name="model_a", scores_path=sample_scores_files["model_a_run1"]
        ),
        ScoreConfig(
            model_name="model_b", scores_path=sample_scores_files["model_b_run1"]
        ),
    ]

    result = summarize_scores(configs)

    lines = result.split("\n")
    assert lines[0] == "model,PASSED,AGENT_FAILED_BUILD,INFRA_FAILURE_AGENT,TOTAL"
    assert lines[1] == "model_a,2,1,0,3"
    assert lines[2] == "model_b,0,1,1,2"


def test_summarize_scores_averaging_multiple_runs(sample_scores_files):
    configs = [
        ScoreConfig(
            model_name="model_a", scores_path=sample_scores_files["model_a_run1"]
        ),
        ScoreConfig(
            model_name="model_a", scores_path=sample_scores_files["model_a_run2"]
        ),
    ]

    result = summarize_scores(configs)

    lines = result.split("\n")
    assert lines[0] == "model,PASSED,AGENT_FAILED_BUILD,AGENT_FAILED_TEST,TOTAL"
    # Run 1: BUILD_FAILED=1, PASSED=2, TEST_FAILED=0
    # Run 2: BUILD_FAILED=0, PASSED=2, TEST_FAILED=1
    # Average: PASSED=2, BUILD_FAILED=0.5, TEST_FAILED=0.5
    assert lines[1] == "model_a,2,0.5,0.5,3"


def test_summarize_scores_empty_configs():
    result = summarize_scores([])
    assert result == ""

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
"""Tests for run configuration utilities."""

import shutil
from pathlib import Path
from common.constants import CONFIG_PROPERTIES_FILE

from common.run_config import read_run_config, write_run_config

TEST_DIR = Path(__file__).parent


def test_write_run_config():
    """Tests that write_run_config creates a properly formatted config.properties file."""
    output_dir = TEST_DIR / "test_output"
    output_dir.mkdir(exist_ok=True)

    try:
        model_name = "gemini/gemini-2.5-flash"
        run_name = "gemini-gemini-2.5-flash_2025-11-14-10-30-45"
        timestamp = "2025-11-14-10-30-45"

        write_run_config(output_dir, model_name, run_name, timestamp)

        config_path = output_dir / CONFIG_PROPERTIES_FILE
        assert config_path.exists()

        content = config_path.read_text()
        assert "model_name=gemini/gemini-2.5-flash" in content
        assert "run_timestamp=2025-11-14-10-30-45" in content
        assert "run_name=gemini-gemini-2.5-flash_2025-11-14-10-30-45" in content

        # Verify it's valid properties format (key=value pairs)
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        for line in lines:
            assert "=" in line, f"Invalid property line: {line}"

    finally:
        # Cleanup
        if output_dir.exists():
            shutil.rmtree(output_dir)


def test_read_run_config():
    """Tests that read_run_config correctly reads config.properties file."""
    output_dir = TEST_DIR / "test_output"
    output_dir.mkdir(exist_ok=True)

    try:
        model_name = "gemini/gemini-2.5-flash"
        run_name = "gemini-gemini-2.5-flash_2025-11-14-10-30-45"
        timestamp = "2025-11-14-10-30-45"

        # Write config first
        write_run_config(output_dir, model_name, run_name, timestamp)

        # Read it back
        config = read_run_config(output_dir)

        assert config["model_name"] == model_name
        assert config["run_name"] == run_name
        assert config["run_timestamp"] == timestamp

    finally:
        # Cleanup
        if output_dir.exists():
            shutil.rmtree(output_dir)


def test_write_and_read_roundtrip():
    """Tests that writing and reading config produces the same data."""
    output_dir = TEST_DIR / "test_output"
    output_dir.mkdir(exist_ok=True)

    try:
        # Test with various model names including special characters
        test_cases = [
            ("gemini/gemini-2.5-flash", "run1", "2025-01-01-00-00-00"),
            ("openai/gpt-4", "run2", "2025-01-01-00-00-01"),
        ]

        for model_name, run_name, timestamp in test_cases:
            write_run_config(output_dir, model_name, run_name, timestamp)
            config = read_run_config(output_dir)

            assert config["model_name"] == model_name
            assert config["run_name"] == run_name
            assert config["run_timestamp"] == timestamp

    finally:
        # Cleanup
        if output_dir.exists():
            shutil.rmtree(output_dir)

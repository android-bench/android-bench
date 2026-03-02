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
"""Utilities for reading and writing run configuration files."""

import logging
from pathlib import Path
from common.constants import CONFIG_PROPERTIES_FILE

logger = logging.getLogger(__name__)


def write_run_config(output_dir: Path, model_name: str, run_name: str, timestamp: str):
    """
    Write config.properties file with run metadata.

    Args:
        output_dir: The base output directory for the run
        model_name: The full model name (e.g., "gemini/gemini-2.5-flash")
        run_name: The sanitized run name (e.g., "gemini-gemini-2.5-flash_2025-11-14-10-30-45")
        timestamp: The timestamp string (e.g., "2025-11-14-10-30-45")
    """
    config_path = output_dir / CONFIG_PROPERTIES_FILE
    config_content = f"""model_name={model_name}
run_timestamp={timestamp}
run_name={run_name}
"""
    config_path.write_text(config_content)
    logger.info(f"Run configuration saved to {config_path}")


def read_run_config(run_dir: Path) -> dict:
    """
    Read config.properties from a run directory.

    Args:
        run_dir: The run directory containing config.properties

    Returns:
        Dictionary with configuration keys and values

    Raises:
        FileNotFoundError: If config.properties doesn't exist in run_dir
    """
    config_path = run_dir / CONFIG_PROPERTIES_FILE
    if not config_path.exists():
        raise FileNotFoundError(f"No config.properties found in {run_dir}")

    config = {}
    for line in config_path.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()
    return config

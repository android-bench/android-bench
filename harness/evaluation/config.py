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
import logging
import os
import json
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DockerConfig:
    harness_docker_timeout: int = 3600
    docker_client_timeout: int = 300
    container_start_retries: int = 3


@dataclass
class EmulatorConfig:
    emulator_boot_timeout: int = 300
    test_execution_timeout: int = 10000
    test_retry_attempts: int = (
        1
        if os.environ.get("KOKORO_ARTIFACTS_DIR") or os.environ.get("KOKORO_JOB_NAME")
        else 3
    )
    gradle_workers: int = 4


@dataclass
class PatchVerifierConfig:
    docker_config: DockerConfig = field(default_factory=DockerConfig)
    emulator_config: EmulatorConfig = field(default_factory=EmulatorConfig)

    @classmethod
    def load(cls, config_path: Path | None = None) -> "PatchVerifierConfig":
        if config_path is None:
            config_path = Path(__file__).parent / "config.json"

        if not config_path.exists():
            logger.warning(f"Config file not found at {config_path}, using defaults.")
            return cls()

        try:
            with open(config_path, "r") as f:
                raw_data = json.load(f) or {}

            # Parse nested configs
            docker_data = raw_data.get("docker_config", {})
            emulator_data = raw_data.get("emulator_config", {})

            # Filter valid keys for each config
            docker_valid_keys = DockerConfig.__annotations__.keys()
            filtered_docker = {
                k: v for k, v in docker_data.items() if k in docker_valid_keys
            }

            emulator_valid_keys = EmulatorConfig.__annotations__.keys()
            filtered_emulator = {
                k: v for k, v in emulator_data.items() if k in emulator_valid_keys
            }

            return cls(
                docker_config=DockerConfig(**filtered_docker),
                emulator_config=EmulatorConfig(**filtered_emulator),
            )
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            return cls()


# Global config instance
config = PatchVerifierConfig.load()

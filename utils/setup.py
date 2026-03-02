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
"""Setup script for Android Bench.

1) Installs dependencies using uv.
2) Sets up the oracle agent with golden patches.
3) Generates the task summary for the explorer.
4) Analyzes CPU architecture and exits gracefully if unsupported,
    or offers to build images. (pending freshness check)
"""

import argparse
import logging
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from common.constants import TASKS_DIR
from common.logger import configure_logging
from utils.docker.prebuild import run_prebuild_checks
from utils.explorer.generate_task_summary import generate_summary
from utils.setup_oracle_agent import setup_oracle_agent

logger = logging.getLogger(__name__)
configure_logging()


def check_prerequisites() -> None:
    """Checks if required system dependencies are installed."""
    missing = []
    for cmd in ["uv", "docker"]:
        if shutil.which(cmd) is None:
            missing.append(cmd)

    if missing:
        logger.error(
            "[bold red]Missing prerequisites:[/] %s. "
            "Please install them before running setup.",
            ", ".join(missing),
        )
        sys.exit(1)


def run_command(
    command: List[str],
    description: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> bool:
    """Runs a shell command and logs its output."""
    if description:
        logger.info("[bold blue]>>> %s...[/]", description)
    logger.info("Running: %s", " ".join(command))
    result = subprocess.run(
        command, capture_output=False, text=True, env=env, check=False
    )
    if result.returncode != 0:
        logger.error(
            "[bold red]Error:[/] %s failed with exit code [bold red]%s[/].",
            description,
            result.returncode,
        )
        return False
    return True


def install_dependencies() -> None:
    """Installs required Python dependencies using uv."""
    if not run_command(
        ["uv", "sync", "--all-extras"], "Installing dependencies with uv"
    ):
        logger.error(
            "[bold red]Failed to sync dependencies. "
            "Please ensure 'uv' is installed and working.[/]"
        )
        sys.exit(1)


def setup_oracle() -> None:
    """Sets up the Oracle Agent with its golden patches."""
    logger.info("[bold blue]>>> Setting up Oracle Agent...[/]")
    try:
        setup_oracle_agent()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("[bold red]Error setting up Oracle Agent:[/]")


def generate_task_summary() -> None:
    """Generates the task summary JSON file for the visualizer."""
    logger.info("[bold blue]>>> Generating Task Summary for Visualizer...[/]")
    try:
        summary_file = TASKS_DIR / "summary.json"
        if not summary_file.exists():
            generate_summary()
        else:
            logger.info("[bold green]Task summary already exists.[/]")
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("[bold red]Error generating task summary:[/]")


def analyze_docker(auto_confirm: bool) -> None:
    """Analyzes Docker environment and builds images if needed."""
    logger.info("[bold blue]>>> Analyzing Docker environment...[/]")
    try:
        run_prebuild_checks()
    except SystemExit as e:
        logger.error("%s", e)
        return
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("[bold red]Error running prebuild checks:[/]")
        return

    host_machine = platform.machine().lower()
    if any(arch in host_machine for arch in ["arm64", "aarch64"]):
        logger.warning(
            "[bold yellow]Note:[/] Skipping automatic Docker build for "
            "arm64 architecture."
        )
        logger.warning(
            "Please make necessary manual modifications to the base Dockerfile,"
            " then build manually."
        )
        return

    logger.info("[bold blue]>>> Checking if Docker images are built...[/]")
    result = subprocess.run(
        ["docker", "images", "-q", "android-bench-env"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout.strip():
        logger.info("[bold green]Docker images are already built and available.[/]")
        return


def parse_args() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(description="Android Bench Setup Script")
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Automatically confirm prompts (e.g., for building Docker images)",
    )
    return parser.parse_args()


def main() -> None:
    """Main execution entry point."""
    args = parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    os.chdir(root_dir)

    logger.info("[bold]=== Android Bench Setup ===[/]")

    check_prerequisites()

    # 1. Install Dependencies
    install_dependencies()

    # 2. Setup Oracle Agent
    setup_oracle()

    # 3. Setup Visualizer Task Summary
    generate_task_summary()

    # 4. Analyze architecture and rebuild docker images
    analyze_docker(auto_confirm=args.yes)

    logger.info("[bold]=== Setup Complete ===[/]")


if __name__ == "__main__":
    main()

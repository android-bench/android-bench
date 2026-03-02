#!/usr/bin/env python3
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

"""
Setup script for Android Bench.
1) Installs dependencies using uv.
2) Sets up the oracle agent with golden patches.
3) Generates the task summary for the visualizer.
4) Analyzes CPU architecture and exits gracefully if unsupported,
    or offers to build images. (pending freshness check)
"""

import os
import subprocess
import sys
import platform
from pathlib import Path


def run_command(command, description=None, env=None):
    if description:
        print(f"\n>>> {description}...")
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(command, capture_output=False, text=True, env=env)
    if result.returncode != 0:
        print(f"Error: {description} failed with exit code {result.returncode}.")
        return False
    return True


def analyze_docker(root_dir):
    print("\n>>> Analyzing CPU architecture compatibility...")
    # Detect host architecture
    host_machine = platform.machine().lower()
    if any(arch in host_machine for arch in ["arm64", "aarch64"]):
        host_arch = "arm64"
    elif any(arch in host_machine for arch in ["x86_64", "amd64"]):
        host_arch = "amd64"
    else:
        # Fallback to amd64 but warn user
        print(f"Warning: Unknown architecture '{host_machine}'. Defaulting to amd64.")
        host_arch = "amd64"

    print(f"Host architecture detected: {host_arch} (Machine: {host_machine})")

    if host_arch == "arm64":
        print(
            f"{host_arch} architecture is not supported. Please review the prerequisites."
        )
    else:
        confirm = input(f"Do you want to build the Docker images? (y/n): ")
        if confirm.lower() == "y":
            build_cmd = [
                "uv",
                "run",
                "build_images",
                "--build",
                "--arch",
                f"linux/{host_arch}",
            ]
            run_command(build_cmd, f"Rebuilding images")


def main():
    root_dir = Path(__file__).resolve().parent.parent
    os.chdir(root_dir)

    print("=== Android Bench Setup ===")

    # 1. Install Dependencies
    if not run_command(
        ["uv", "sync", "--all-extras"], "Installing dependencies with uv"
    ):
        print("Failed to sync dependencies. Please ensure 'uv' is installed.")
        sys.exit(1)

    # Add root_dir to sys.path to allow imports from utils
    sys.path.append(str(root_dir))

    # 2. Setup Oracle Agent
    print("\n>>> Setting up Oracle Agent...")
    try:
        from utils.setup_oracle_agent import setup_oracle_agent

        setup_oracle_agent()
    except Exception as e:
        print(f"Error setting up Oracle Agent: {e}")

    # 3. Setup Visualizer Task Summary
    print("\n>>> Generating Task Summary for Visualizer...")
    try:
        from utils.visualizer.generate_task_summary import generate_summary

        generate_summary()
    except Exception as e:
        print(f"Error generating task summary: {e}")

    # 4. Analyze architecture and rebuild docker images
    analyze_docker(root_dir)

    print("\n=== Setup Complete ===")


if __name__ == "__main__":
    main()

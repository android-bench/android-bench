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
import subprocess
import argparse
import datetime
import os
import sys

from common.constants import TASKS_DIR


def main():
    parser = argparse.ArgumentParser(
        description="Run agent and verifier for a specific task."
    )
    parser.add_argument(
        "--model", type=str, required=True, help="The model to use for the agent."
    )
    parser.add_argument(
        "-i", "--task", type=str, required=True, help="The task ID to run."
    )
    parser.add_argument(
        "--tasks-dir",
        type=str,
        default=str(TASKS_DIR),
        help=f"Path to the tasks directory (default: {TASKS_DIR}).",
    )
    parser.add_argument(
        "--local-images",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use local images and build them first (default: True).",
    )

    args = parser.parse_args()

    username = os.getlogin()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if "/" in args.model:
        model_name = args.model.split("/")[1]
    else:
        model_name = args.model

    # Mimic run_benchmark.py run name generation
    run_name = f"{username}_{timestamp}_{model_name}_run_1"
    print(f"--- Starting run {run_name} ---")

    # Build local image first if requested
    if args.local_images:
        build_command = [
            sys.executable,
            "utils/docker/generate_docker_images.py",
            "--tasks-dir",
            args.tasks_dir,
            "--build",
            "--task_id",
            args.task,
        ]
        print(f'Building local image: {" ".join(build_command)}')
        subprocess.run(build_command, check=True)

    agent_command = [
        "agent",
        "--tasks-dir",
        args.tasks_dir,
        "--model",
        args.model,
        "-i",
        args.task,
        "--run-name",
        run_name,
    ]
    if args.local_images:
        agent_command.extend(["--images", "local"])

    print(f'Running agent: {" ".join(agent_command)}')
    subprocess.run(agent_command, check=True)

    verifier_command = [
        "verifier",
        "--tasks-dir",
        args.tasks_dir,
        "--run-name",
        run_name,
        "--task",
        args.task,
    ]
    if args.local_images:
        verifier_command.append("--use_local_images")

    print(f'Running verifier: {" ".join(verifier_command)}')
    subprocess.run(verifier_command, check=True)

    print(f"--- Finished run {run_name} ---")


if __name__ == "__main__":
    main()

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


def main():
    parser = argparse.ArgumentParser(description="Run agent and verifier locally.")
    parser.add_argument(
        "--model", type=str, required=True, help="The model to use for the agent."
    )
    parser.add_argument(
        "--num_runs", type=int, default=1, help="Number of times to run the agent."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers the agent should use",
    )
    parser.add_argument(
        "--tasks-filter",
        "--tasks_filter",
        type=str,
        default="dataset/tasks/v1_tasks.yaml",
        help="YAML file of tasks to filter run",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Custom run name. If provided, num_runs is ignored and this run is resumed/started.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip running an instance if the patch file already exists.",
    )
    args = parser.parse_args()

    username = os.getlogin()
    model_name = args.model.split("/")[-1]

    num_runs = args.num_runs
    if args.run_name:
        num_runs = 1

    for i in range(num_runs):
        if args.run_name:
            run_name = args.run_name
        else:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            run_name = f"{username}_{timestamp}_{model_name}_run_{i+1}"

        print(f"--- Starting run {run_name} ---")

        agent_command = [
            "agent",
            "--workers",
            str(args.workers),
            "--model",
            args.model,
            "--tasks_filter",
            args.tasks_filter,
            "--run-name",
            f"{run_name}/{args.model}",
        ]
        if args.skip_existing:
            agent_command.append("--skip-existing")

        print(f'Running agent: {" ".join(agent_command)}')
        subprocess.run(agent_command, check=True)

        verifier_command = [
            "verifier",
            "--run-name",
            f"{run_name}/{args.model}",
            "--tasks-filter",
            args.tasks_filter,
            "--max-parallel-containers",
            str(args.workers),
        ]
        if args.skip_existing:
            verifier_command.append("--skip-existing")

        print(f'Running local verifier: {" ".join(verifier_command)}')
        subprocess.run(verifier_command, check=True)

        print(f"--- Finished run {run_name} ---")


if __name__ == "__main__":
    main()

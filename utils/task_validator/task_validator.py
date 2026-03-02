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
import argparse
import json
import logging
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


import yaml
import docker
from harness.evaluation.benchmark_worker import score_patch
from common.models.benchmark import Status
from common.constants import TASKS_DIR, ROOT_DIR

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class TaskValidator:
    def __init__(self, output_path: str):
        self.output_path = Path(output_path)
        self._configure_yaml_presenter()

    def _configure_yaml_presenter(self) -> None:
        """Configures YAML to use block style for multiline strings."""

        def str_presenter(dumper, data):
            if "\n" in data:
                return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
            return dumper.represent_scalar("tag:yaml.org,2002:str", data)

        yaml.add_representer(str, str_presenter)

    def run_command(
        self,
        command: List[str],
        return_output: bool = False,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Optional[str]:
        """Runs a command and optionally returns the output."""
        print(f"$ {' '.join(str(c) for c in command)}")
        result = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE if return_output else None,
            stderr=subprocess.STDOUT if return_output else None,
            text=True,
            timeout=timeout,
            check=True,
        )
        return result.stdout if return_output else None

    def _detect_task_changes(self) -> List[str]:
        """Detects changed tasks in the tasks/ directory."""
        logger.info("[tasks] Detecting changed files in this patchset for tasks/...")
        try:
            changed_files_output = self.run_command(
                ["git", "diff-tree", "--no-commit-id", "--name-status", "-r", "HEAD"],
                return_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"[tasks] Error getting changed files: {e}")
            return []

        if not changed_files_output:
            logger.info("[tasks] No file changes detected in this patchset.")
            return []

        logger.info("[tasks] Changed files list:")
        print(changed_files_output)

        changed_files = [
            line.split("\t")[1]
            for line in changed_files_output.strip().splitlines()
            if line.startswith(("A\t", "M\t"))
        ]

        tasks_rel_path = TASKS_DIR.relative_to(ROOT_DIR)
        str_tasks_rel_path = str(tasks_rel_path)

        unique_changed_tasks = sorted(
            list(
                {
                    Path(f).relative_to(tasks_rel_path).parts[0]
                    for f in changed_files
                    if f.startswith(f"{str_tasks_rel_path}/")
                    and len(Path(f).parts) > len(tasks_rel_path.parts) + 1
                }
            )
        )

        if not unique_changed_tasks:
            logger.info(
                f"[tasks] No changes detected within any subdirectory of '{str_tasks_rel_path}/'."
            )
            return []

        logger.info(
            f"[tasks] Unique changed task directories under '{str_tasks_rel_path}/':"
        )
        for task in unique_changed_tasks:
            logger.info(f"[tasks]  {task}")

        return unique_changed_tasks

    def run_verifier(self, changed_tasks: List[str]) -> None:
        """Runs the verifier for the given tasks locally."""
        if not changed_tasks:
            logger.info("[tasks] No changed tasks to verify.")
            return

        # We need to pass the "Host" path to the sibling container for volume mounting.
        # In Kokoro, ANDROID_BENCH_HOST_PATH should be set by kokoro_build.sh
        host_project_path = Path(os.environ.get("ANDROID_BENCH_HOST_PATH", os.getcwd()))
        logger.info(f"[tasks] Using host project path: {host_project_path}")

        logger.info("[tasks] Configuring docker for gcr.io")
        self.run_command(["gcloud", "auth", "configure-docker", "gcr.io"])

        try:
            client = docker.from_env()
        except Exception as e:
            logger.error(f"[tasks] Failed to create Docker client: {e}")
            sys.exit(1)

        # Output directory
        run_dir = Path("out") / "verifier_run"
        run_dir.mkdir(parents=True, exist_ok=True)

        task_results = []

        for task_name in changed_tasks:
            logger.info(f"[tasks] Verifying task: {task_name}")

            # Load task definition
            task_dir = TASKS_DIR / task_name
            task_yaml_path = task_dir / "task.yaml"

            if not task_yaml_path.exists():
                logger.error(f"[tasks] task.yaml not found for {task_name}")
                task_results.append(
                    {
                        "name": task_name,
                        "status": "❌ FAILED",
                        "error": "task.yaml not found",
                    }
                )
                continue

            with open(task_yaml_path, "r") as f:
                task_dict = yaml.safe_load(f)

            # Helper to set patch file if not present
            # Default paths must be relative for container rewriting logic below
            rel_task_dir = task_dir.relative_to(ROOT_DIR)
            if "patch_file" not in task_dict or not task_dict["patch_file"]:
                task_dict["patch_file"] = str(rel_task_dir / "golden.patch")

            if "test_patch_file" not in task_dict or not task_dict["test_patch_file"]:
                task_dict["test_patch_file"] = str(rel_task_dir / "test.patch")

            # Fix paths for container
            for key in ["patch_file", "test_patch_file"]:
                if key in task_dict and task_dict[key]:
                    # Assuming paths in task.yaml are relative to project root
                    # e.g. tasks/my_task/fix.patch
                    # We need to make them absolute path inside container: /android_bench/tasks/my_task/fix.patch
                    original_path = task_dict[key]
                    if not original_path.startswith("/"):
                        task_dict[key] = f"/android_bench/{original_path}"

            logger.info(f"[tasks] Running verifier locally for {task_name}...")

            try:
                patch_score = score_patch(
                    task=task_dict,
                    client=client,
                    run_dir=run_dir,
                    job_name="task_validator_local",
                    use_local_images=False,
                    print_container_logs=True,
                    host_project_path=host_project_path,
                )

                logger.info(
                    f"[tasks] Task {task_name} finished with status: {patch_score.status}"
                )
                logger.info(f"[tasks] Score: {patch_score.score}")
                logger.info(f"[tasks] Diagnostics: {patch_score.diagnostics}")

                if patch_score.score == 0:
                    logger.error(f"[tasks] Task {task_name} failed verification.")
                    status_icon = "❌"
                    status_text = "FAILED"
                else:
                    logger.info(f"[tasks] Task {task_name} passed verification.")
                    status_icon = "✅"
                    status_text = "PASSED"

                task_results.append(
                    {
                        "name": task_name,
                        "status": f"{status_icon} {status_text}",
                        "score": patch_score.score,
                        "diagnostics": patch_score.diagnostics,
                    }
                )

            except Exception as e:
                logger.error(
                    f"[tasks] Exception during verification for {task_name}: {e}"
                )
                task_results.append(
                    {"name": task_name, "status": "‼️ EXCEPTION", "error": str(e)}
                )

        # Compile diagnostics into gerrit_comments.json
        failed_results = [
            r
            for r in task_results
            if "FAILED" in r["status"] or "EXCEPTION" in r["status"]
        ]
        failed_count = len(failed_results)
        passed_count = len(task_results) - failed_count

        summary = f"**Summary:** {passed_count} Passed, {failed_count} Failed"
        message_lines = ["**Kokoro Task Results:**", "", summary, "---"]

        for result in task_results:
            message_lines.append(f"**Task: {result['name']}**")
            message_lines.append(
                f"  Status: {result['status']}"
                + (f" (Score: {result['score']})" if "score" in result else "")
            )
            if "error" in result:
                message_lines.append(f"  Error: {result['error']}")
            else:
                message_lines.append(
                    f"  Diagnostics: {result.get('diagnostics', 'N/A')}"
                )

        gerrit_comments = [
            {"path": "/PATCHSET_LEVEL", "message": "\n".join(message_lines)}
        ]

        artifacts_dir = os.environ.get("KOKORO_ARTIFACTS_DIR")
        if artifacts_dir:
            comments_path = Path(artifacts_dir) / "gerrit_comments.json"
        else:
            comments_path = Path("gerrit_comments.json")

        with open(comments_path, "w") as f:
            logger.info(f"[tasks] {gerrit_comments} into {comments_path }")
            json.dump(gerrit_comments, f, indent=2)

        if failed_results:
            failed_names = [r["name"] for r in failed_results]
            logger.error(
                f"[tasks] The following tasks failed verification: {failed_names}"
            )
            sys.exit(1)
        else:
            logger.info("[tasks] All changed tasks passed verification.")

    def run(self) -> None:
        """Main execution flow."""
        changed_tasks = self._detect_task_changes()
        # tmp directory where this script is running
        kokoro_root_dir = os.environ.get("KOKORO_ROOT_DIR", "/")
        # tmp directory of the hosting VM, which can be shared with a docker container
        kokoro_host_root_dir = os.environ.get("KOKORO_HOST_ROOT_DIR", "/")
        script_shared_path = Path(kokoro_root_dir) / "tmp/shared_android_bench"
        if changed_tasks and len(changed_tasks) == 1:
            with open(self.output_path, "w") as f:
                # Store as a list of tasks under 'changed_tasks' key for clarity
                yaml.dump(changed_tasks, f, indent=2, sort_keys=False)

            logger.info(f"[tasks] Detected {len(changed_tasks)} changed task(s).")

            self.run_verifier([changed_tasks[0]])
            # Copy artifacts
            artifacts_dir = script_shared_path / "artifacts"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            source_dir = script_shared_path / "out/verifier_run"

            print(f"[tasks] Copying artifacts from {source_dir} to {artifacts_dir}")
            if source_dir.exists():
                self.run_command(
                    [
                        "rsync",
                        "-a",
                        str(source_dir) + "/",
                        str(artifacts_dir) + "/",
                    ]
                )

            print("[tasks] Printing verifier logs...")
            log_files = list(artifacts_dir.glob("**/log.txt"))
            if not log_files:
                print("[tasks] No log.txt files found in the artifacts directory.")
            else:
                for log_file in log_files:
                    task_name = log_file.parent.name
                    print(f"--- Log for task: {task_name} ---")
                    with open(log_file, "r") as f:
                        for line in f:
                            print(f"[{task_name}] {line.strip()}")
                    print(f"--- End of log for task: {task_name} ---")


def main():
    parser = argparse.ArgumentParser(
        description="Check for task changes and run verifier."
    )
    parser.add_argument(
        "--output-path",
        default="changed_tasks.yaml",
        help="Path to save the list of changed tasks.",
    )
    args = parser.parse_args()

    validator = TaskValidator(args.output_path)
    validator.run()


if __name__ == "__main__":
    main()

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
"""Main entrypoint script to orchestrate the Android benchmark tasks."""

import argparse
import json
import logging, logging.config
import os
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import docker
import yaml

from common.loader import load_all_tasks
from common.run_config import read_run_config


from harness.evaluation.benchmark_worker import score_patch

from common.config import BaseConfig
from common.constants import AGENT_EXIT_STATUS_FILE, TASKS_DIR
from common.models.benchmark import BenchmarkTask, PatchScore, Status

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


AGENT_ERROR_STATUS = {
    "FormatError": Status.INFRA_FAILURE_AGENT_FORMAT_ERROR,
    "ExecutionTimeoutError": Status.INFRA_FAILURE_AGENT_EXECUTION_TIMEOUT,
    "LimitsExceeded": Status.INFRA_FAILURE_AGENT_LIMITS_EXCEEDED,
}

LITELLM_ERROR_STATUS = {
    "UnsupportedParamsError": Status.INFRA_FAILURE_AGENT_UNSUPPORTED_PARAMS,
    "NotFoundError": Status.INFRA_FAILURE_AGENT_NOT_FOUND,
    "PermissionDeniedError": Status.INFRA_FAILURE_AGENT_PERMISSION_DENIED,
    "ContextWindowExceededError": Status.INFRA_FAILURE_AGENT_CONTEXT_EXCEEDED,
    "AuthenticationError": Status.INFRA_FAILURE_AGENT_AUTH_ERROR,
    "APIError": Status.INFRA_FAILURE_AGENT_API_ERROR,
}


def setup_file_logging(log_dir: Path):
    """
    Set up file logging to save logs to the run directory.

    Args:
        log_dir: Directory where log files should be saved
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "verify.log"

    # Create file handler
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)

    # Add handler to the logger
    logging.getLogger().addHandler(file_handler)

    logging.getLogger().info(f"File logging enabled. Logs will be saved to: {log_file}")


def _write_scores_to_file(scores: dict[str, Any], score_out_path: Path):
    sorted_scores = dict(sorted(scores.items()))
    with open(score_out_path, "w") as f:
        json.dump({k: v.to_dict() for k, v in sorted_scores.items()}, f, indent=4)


def parse_exit_status(yaml_path: Path) -> dict[str, str]:
    """
    Parses the agent_exit_status.yaml file.
    Returns a dictionary: instance_id -> agent_exit_status

    args:
        yaml_path: Path to the agent_exit_status.yaml file
    """
    instance_status_map = {}
    try:
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        if data and "instances_by_exit_status" in data:
            for status, instances in data["instances_by_exit_status"].items():
                if instances:
                    for instance_id in instances:
                        instance_status_map[instance_id] = status

        logger.info(
            f"Parsed {len(instance_status_map)} instance statuses from {yaml_path}"
        )
    except Exception as e:
        logger.error(f"Failed to parse exit status yaml: {e}")

    return instance_status_map


def score_patches(
    run_dir: Path,
    tasks_dir: Path,
    output_file: str = "scores.json",
    tasks_filter: str | None = None,
    task_key: str | None = None,
    max_parallel_containers: int = 1,
    skip_existing: bool = False,
    use_local_images: bool = False,
    start_index: int = 0,
    end_index: int = 0,
    test_run: bool = False,
    job_name: str = "local run",
    patch_dir: Path | None = None,
    host_dir: Path | None = None,
):
    cfg = BaseConfig()
    log_dir = run_dir / "logs"

    if not test_run and not patch_dir:
        patch_dir = run_dir / "patches"

    all_tasks = load_all_tasks(tasks_dir, tasks_filter)

    tasks_data = [task.model_dump(mode="json") for task in all_tasks]

    exit_status_path = log_dir / AGENT_EXIT_STATUS_FILE
    instance_exit_status_map = parse_exit_status(exit_status_path)

    # Filter tasks based on start and end index.
    if end_index == 0:
        end_index = len(tasks_data)
    tasks_data = tasks_data[start_index:end_index]

    all_instance_ids = {json_data.get("instance_id") for json_data in tasks_data}

    tasks = []
    for task_json in tasks_data:
        # If we are running test-run we need to pick up the golden-patches from the tasks directory.
        if test_run:
            patch_dir = Path("dataset/tasks") / task_json.get("instance_id")
            logger.info(
                f"Instance {task_json.get("instance_id")}: --- Using patch_dir: {patch_dir} ---"
            )
        task = BenchmarkTask.from_json(task_json, str(patch_dir), is_test_task=test_run)
        if task:
            tasks.append(task)
    # Checking if the particular patch file exists for the specified task under the specified model
    if task_key:
        tasks = [task for task in tasks if task.instance_id == task_key]
        if not tasks:
            logger.error(f"Task with key {task_key} not found.")
            return
        all_instance_ids = {task_key}

    score_out_path = run_dir / f"{start_index}_to_{end_index-1}_{output_file}"
    os.makedirs(score_out_path.parent, exist_ok=True)

    # Load existing scores if skipping tasks or running a single task.
    existing_scores = {}
    if skip_existing or task_key:
        if not task_key:
            try:
                with open(score_out_path, "r") as f:
                    existing_scores = json.load(f)
                logger.info(
                    f"Loaded {len(existing_scores)} existing scores from {score_out_path}"
                )
            except FileNotFoundError:
                logger.error(
                    f"Output file {score_out_path} not found, running all tasks."
                )
                pass
    # If not skipping, and the output file exists, confirm with the user before overwriting.
    elif Path(score_out_path).exists():
        overwrite = input(
            f"Output file {score_out_path} already exists. Overwrite? (y/n): "
        )
        if overwrite.lower() != "y":
            logger.info("Aborting.")
            return

    # If skipping tasks, filter out the ones that have already been completed.
    scores = existing_scores
    if skip_existing and not task_key:
        tasks_to_run = []
        for task in tasks:
            if task.instance_id in existing_scores:
                result = existing_scores[task.instance_id]["score"]
                if isinstance(result, float):
                    logger.info(
                        f"Skipping task {task.instance_id} with existing score {result}"
                    )
                    continue
                else:
                    logger.info(
                        f"Rerunning task {task.instance_id} with existing result {result}"
                    )
            tasks_to_run.append(task)
        tasks = tasks_to_run
    # pre-populate all the scores with NO_PATCH status.
    # for valid tasks, this will be overwritten after benchmark run for that task is complete.
    for i_id in all_instance_ids:
        agent_exit_status = Status.AGENT_NO_PATCH
        agent_status = ""
        task_error = ""
        if i_id in instance_exit_status_map:
            agent_status = instance_exit_status_map[i_id]
            # If the agent failed to submit the task, we set the status to internal failure.
            # Then we check for more specific-error statuses and set the status accordingly.
            if agent_status != "Submitted":
                traj_path = run_dir / "trajectories" / f"{i_id}.json"
                agent_exit_status = Status.INFRA_FAILURE_AGENT
                if traj_path.exists():
                    traj_data = json.loads(traj_path.read_text())
                    task_error = "|" + traj_data.get("info", {}).get("traceback", "")
                if agent_status in AGENT_ERROR_STATUS:
                    agent_exit_status = AGENT_ERROR_STATUS[agent_status]
                elif agent_status in LITELLM_ERROR_STATUS:
                    agent_exit_status = LITELLM_ERROR_STATUS[agent_status]

        scores[i_id] = PatchScore(
            instance_id=i_id,
            score=0.0,
            status=agent_exit_status,
            diagnostics=f"Agent failed to generate patch files. Agent exit status: {agent_status}{task_error}",
            job_name=job_name,
        )
    _write_scores_to_file(scores, score_out_path)
    logger.info(
        f"Initial scores (including agent failures) written to {score_out_path}"
    )

    try:
        client = docker.DockerClient.from_env(
            timeout=cfg.docker_config.docker_client_timeout
        )
        client.ping()
    except Exception as e:
        logger.error("Error: Could not connect to Docker daemon.")
        logger.error("Please ensure Docker is installed and running.")
        logger.error(f"Details: {e}")
        return

    filtered_task_ids = {task.instance_id for task in tasks}

    id_to_task = {t.instance_id: t for t in tasks}
    filtered_task_data = [
        task_json
        for task_json in tasks_data
        if task_json.get("instance_id") in filtered_task_ids
    ]

    for task_json in filtered_task_data:
        iid = task_json.get("instance_id")
        if iid in id_to_task:
            task = id_to_task[iid]
            if task.patch_file:
                task_json["patch_file"] = str(task.patch_file)
                task_json["test_patch_file"] = str(task.test_patch_file)
            task_json["steps"] = task.steps
            task_json["cost"] = task.cost
            task_json["used_tokens"] = (
                asdict(task.used_tokens) if task.used_tokens else None
            )
            task_json["latency_details"] = (
                asdict(task.latency_details) if task.latency_details else None
            )

    with ThreadPoolExecutor(max_workers=max_parallel_containers) as executor:
        future_to_task = {
            executor.submit(
                score_patch,
                task_json,
                client,
                run_dir,
                job_name,
                use_local_images,
                len(filtered_task_data) == 1,
                host_dir,
            ): task_json
            for task_json in filtered_task_data
        }

        total_tasks = len(future_to_task)
        completed_tasks = 0

        for future in as_completed(future_to_task):
            task_json = future_to_task[future]
            try:
                patch_score = future.result()
                scores[patch_score.instance_id] = patch_score
            except Exception as e:
                instance_id = task_json.get("instance_id", "unknown")
                logger.error(f"Task {instance_id} raised an exception: {e}")
                scores[instance_id] = PatchScore(
                    instance_id=instance_id,
                    score=0.0,
                    status=Status.INFRA_FAILURE,
                    diagnostics=f"Unexpected error: {e}",
                    job_name=job_name,
                )

            completed_tasks += 1
            logger.info(
                f"Progress: {completed_tasks}/{total_tasks} scoring tasks complete"
            )

            # Write updated scores to file after each completion, sorted by instance_id
            _write_scores_to_file(scores, score_out_path)
            logger.info(f"Scores written to {score_out_path}")


def main(
    run_name: str,
    output_file: str = "scores.json",
    tasks_dir: Path = TASKS_DIR,
    task_key: str | None = None,
    tasks_filter: str | None = None,
    max_parallel_containers: int = 1,
    skip_existing: bool = False,
    use_local_images: bool = False,
    start_index: int = 0,
    end_index: int = 0,
    test_run: bool = False,
    patch_dir: Path | None = None,
    host_dir: Path | None = None,
):
    """Loads benchmark tasks, runs them sequentially, and outputs a JSON map of the scores."""
    job_name = os.getenv("JOB_NAME", "local run")

    if not host_dir and os.getenv("ANDROID_BENCH_HOST_PATH"):
        host_dir = Path(os.environ["ANDROID_BENCH_HOST_PATH"])

    # Read run configuration
    run_dir = Path("out") / run_name
    config = read_run_config(run_dir)
    model_name = config["model_name"]

    # Set up file logging
    setup_file_logging(run_dir / "logs")

    logger.info("=" * 70)
    logger.info(f"Verifying run: {run_name}")
    logger.info(f"Model: {model_name}")
    logger.info(f"Run directory: {run_dir}")
    logger.info("=" * 70)

    # Run verification for the single model
    score_patches(
        run_dir=run_dir,
        tasks_dir=tasks_dir,
        tasks_filter=tasks_filter,
        output_file=output_file,
        task_key=task_key,
        max_parallel_containers=max_parallel_containers,
        skip_existing=skip_existing,
        use_local_images=use_local_images,
        start_index=start_index,
        end_index=end_index,
        test_run=test_run,
        job_name=job_name,
        patch_dir=patch_dir,
        host_dir=host_dir,
    )


def run():
    """A non-async entrypoint to run the script."""
    parser = argparse.ArgumentParser(description="Run benchmark tasks.")
    parser.add_argument(
        "--run-name",
        type=str,
        required=True,
        help="Name of the agent run to verify (will read from out/{run-name}/)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="scores.json",
        help="The name of the file to store the scores in.",
    )
    parser.add_argument(
        "--tasks-dir",
        type=Path,
        default=TASKS_DIR,
        help="Path to the tasks directory.",
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Run a single benchmark task by its key (instance_id).",
    )
    parser.add_argument(
        "--tasks-filter",
        "--tasks_filter",
        type=str,
        default=None,
        help="Yaml file with instance_ids to filter tasks. Prefix with '!' to negate.",
    )
    parser.add_argument(
        "--max-parallel-containers",
        type=int,
        default=4,
        help="Maximum number of containers to run in parallel on a single machine.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip tasks that have already been run and have a valid score.",
    )
    parser.add_argument(
        "--use_local_images",
        action="store_true",
        default=True,
        help="Use local docker images instead of pulling from GCR.",
    )
    parser.add_argument(
        "--start_index",
        type=int,
        default=0,
        help="Start index for tasks to run.",
    )
    parser.add_argument(
        "--end_index",
        type=int,
        default=0,
        help="End index for tasks to run.",
    )
    parser.add_argument(
        "--test-run",
        action="store_true",
        help="Check out the after commit and run tests, used for debugging and validating the verifier",
    )

    parser.add_argument(
        "--host-dir",
        type=Path,
        required=False,
        help="Path to android_bench directory",
    )
    args = parser.parse_args()
    main(
        run_name=args.run_name,
        output_file=args.output,
        tasks_dir=args.tasks_dir,
        tasks_filter=args.tasks_filter,
        task_key=args.task,
        max_parallel_containers=args.max_parallel_containers,
        skip_existing=args.skip_existing,
        use_local_images=args.use_local_images,
        start_index=args.start_index,
        end_index=args.end_index,
        test_run=args.test_run,
        host_dir=args.host_dir,
    )


if __name__ == "__main__":
    run()

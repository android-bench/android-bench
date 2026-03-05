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
"""Runs all SWE-Bench tasks in parallel"""

import argparse
import concurrent.futures
import enum
import logging
import re
import traceback
from typing import TypedDict
from pathlib import Path
import time
import yaml
from minisweagent.run.extra.utils.batch_progress import RunBatchProgressManager
from rich.live import Live
from common.loader import load_all_tasks
from common.run_config import write_run_config
import base64
import requests
import litellm
from minisweagent.utils.log import logger
from minisweagent.models import get_model_name, get_model
import io

from .androidbench_runner import get_patch_output_path, run_instance

from common.config import BaseConfig
from common.constants import AGENT_EXIT_STATUS_FILE, TASKS_DIR


def sanitize_model_name_for_path(model_name: str) -> str:
    """
    Sanitize model name for use in filesystem paths.

    Examples:
        "gemini/gemini-2.5-pro" → "gemini-gemini-2.5-pro"

    Args:
        model_name: The model name to sanitize

    Returns:
        A sanitized version suitable for use in filesystem paths
    """
    # Split by both : and /
    segments = re.split(r"[:/]", model_name)
    segments = [s for s in segments if s]

    if len(segments) <= 2:
        return model_name.replace("/", "-").replace(":", "-")
    else:
        return f"{segments[0]}-{segments[-1]}"


def setup_file_logging(log_dir: Path):
    """
    Set up file logging to save logs to the run directory.

    Args:
        log_dir: Directory where log files should be saved
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "run.log"

    # Create file handler
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)

    # Add handler to the logger
    logger.addHandler(file_handler)

    logger.info(f"File logging enabled. Logs will be saved to: {log_file}")


class ImageType(str, enum.Enum):
    REMOTE = "remote"
    LOCAL = "local"
    BASE = "base"


def _get_docker_image_name(
    instance_id: str, imageType: ImageType, cfg: BaseConfig
) -> str:
    """Returns the image name for a given instance and image type."""
    if imageType == ImageType.REMOTE:
        return f"{cfg.docker_repository}/{instance_id.lower()}"
    elif imageType == ImageType.LOCAL:
        return instance_id.lower()
    elif imageType == ImageType.BASE:
        return "android-bench-env"
    else:
        raise ValueError(f"Unknown image type: {imageType}")


def _transform_instance(instance: dict, imageType: ImageType, cfg: BaseConfig) -> dict:
    """Transforms a task instance to the format expected by the agent."""
    id = instance.get("instance_id")
    return {
        "instance_id": id,
        "repo_url": instance.get("repository", {}).get("url"),
        "base_commit": instance.get("base_commit", {}).get("sha"),
        "problem_statement": instance.get("description"),
        "image_name": _get_docker_image_name(id, imageType, cfg),
        "image_urls": instance.get("image_urls"),
        "video_urls": instance.get("video_urls"),
        "jdk_version": instance.get("env_config", {}).get("jdk_version"),
    }


def process_instance_wrapper(
    instance: dict,
    config: dict,
    traj_output: Path,
    patch_output_dir: Path,
    model_name: str,
    progress_manager: RunBatchProgressManager | None,
    log_dir: Path,
    dry_run: bool = False,
):
    try:
        run_instance(
            instance=instance,
            config=config,
            traj_output=traj_output,
            patch_output_dir=patch_output_dir,
            model_name=model_name,
            progress_manager=progress_manager,
            log_dir=log_dir,
            dry_run=dry_run,
        )
    except Exception:
        logger.error(
            f"A critical error occurred while processing instance {instance['instance_id']}:"
        )
        logger.error(traceback.format_exc())


def run(
    tasks_dir: Path = TASKS_DIR,
    tasks_filter: str | None = None,
    workers: int = 4,
    instance_id: str | None = None,
    model_name: str | None = None,
    model_class: str | None = None,
    config_path: Path = Path("androidbench.yaml"),
    environment_class: str | None = "docker",
    run_name: str | None = None,
    skip_existing: bool = False,
    docker_image_type: ImageType = ImageType.REMOTE,
    dry_run: bool = False,
):
    cfg = BaseConfig()
    logger.info(f"Loading dataset from {tasks_dir}")
    all_tasks = load_all_tasks(tasks_dir, tasks_filter)
    yaml_instances = [task.model_dump(mode="json") for task in all_tasks]
    config = yaml.safe_load(config_path.read_text())
    if model_name is None:
        model_name = get_model_name(None, config.get("model", {}))

    # Generate run_name if not provided
    if run_name is None:
        timestamp = time.strftime("%Y-%m-%d-%H-%M-%S")
        sanitized_model = sanitize_model_name_for_path(model_name)
        run_name = f"{sanitized_model}_{timestamp}"

    # Set up output directories
    base_output_dir = Path("out") / run_name
    traj_output = base_output_dir / "trajectories"
    patch_output_dir = base_output_dir / "patches"
    log_dir = base_output_dir / "logs"

    # Create base output directory and write config
    base_output_dir.mkdir(parents=True, exist_ok=True)
    write_run_config(
        base_output_dir,
        model_name,
        run_name,
        time.strftime("%Y-%m-%d-%H-%M-%S"),
    )

    # Set up file logging
    setup_file_logging(log_dir)

    logger.info("=" * 70)
    logger.info(f"Outputs will be saved to: {base_output_dir.absolute()}")
    logger.info("=" * 70)

    # Filter the list of instances to run before processing them because the transformation could be expensive
    if instance_id:
        yaml_instances = [
            inst for inst in yaml_instances if inst["instance_id"] == instance_id
        ]
    instances_to_run = []
    for inst in yaml_instances:
        instances_to_run.append(_transform_instance(inst, docker_image_type, cfg))
    if skip_existing:
        filtered_instances = []
        for inst in instances_to_run:
            patch_file = get_patch_output_path(patch_output_dir, inst["instance_id"])
            if patch_file.exists():
                logger.info(
                    f"Skipping instance {inst['instance_id']} because patch file {patch_file} already exists."
                )
            else:
                filtered_instances.append(inst)
        instances_to_run = filtered_instances

    if len(instances_to_run) == 0:
        logger.info("No tasks to run, finishing.")
        return

    workers = min(workers, len(instances_to_run))

    logger.info(
        f"Preparing to run {len(instances_to_run)} instances with {workers} workers."
    )

    env = config.setdefault("environment", {})
    if environment_class is not None:
        env["environment_class"] = environment_class
    if model_class is not None:
        config.setdefault("model", {})["model_class"] = model_class

    # We add --rm to remove the container and its associated anonymous volumes when it exits (default in mini-swe DockerEnvironment)
    env.setdefault("run_args", ["--rm"])

    if docker_image_type == ImageType.REMOTE:
        """
        We set the docker run command to always pull the images if they're different.
        This will only download new image if it differs from the one in the registry.
        """
        env["run_args"] += ["--pull", "always"]

    progress_manager = RunBatchProgressManager(
        len(instances_to_run),
        log_dir / AGENT_EXIT_STATUS_FILE,
    )

    def execute_tasks():
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    process_instance_wrapper,
                    instance,
                    config,
                    traj_output,
                    patch_output_dir,
                    model_name,
                    progress_manager,
                    log_dir,
                    dry_run,
                ): instance["instance_id"]
                for instance in instances_to_run
            }

            for future in concurrent.futures.as_completed(futures):
                instance_id = futures[future]
                try:
                    future.result()
                    logger.info(f"Instance {instance_id} finished successfully.")
                except Exception as e:
                    logger.error(
                        f"Instance {instance_id} failed with an exception: {e}"
                    )
                    if instance_id and progress_manager:
                        progress_manager.on_uncaught_exception(instance_id, e)

    if progress_manager:
        with Live(progress_manager.render_group, refresh_per_second=4):
            execute_tasks()
    else:
        execute_tasks()

    logger.info("All tasks have been processed.")


def main():
    parser = argparse.ArgumentParser(description="Run Android Bench tasks.")
    parser.add_argument(
        "--tasks-dir",
        type=Path,
        default=TASKS_DIR,
        help="Path to the tasks directory.",
    )
    parser.add_argument(
        "--tasks-filter",
        "--tasks_filter",
        type=str,
        default=None,
        help="Yaml file with instance_ids to filter tasks.",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=4,
        help="Number of worker threads for parallel processing",
    )
    parser.add_argument(
        "-i",
        "--instance",
        type=str,
        default=None,
        help="SWE-Bench instance ID or index. If not provided, run all instances.",
    )
    parser.add_argument("-m", "--model", type=str, default=None, help="Model to use")
    parser.add_argument(
        "-mc",
        "--model-class",
        type=str,
        default=None,
        help="Model class to use (e.g., 'anthropic' or 'minisweagent.models.anthropic.AnthropicModel')",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path(__file__).parent / "androidbench.yaml",
        help="Path to a config file",
    )
    parser.add_argument(
        "--environment-class",
        type=str,
        default="docker",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Name for this run (default: auto-generated from model name and timestamp)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip running an instance if the patch file already exists.",
    )
    parser.add_argument(
        "--images",
        type=ImageType,
        default=ImageType.LOCAL,
        choices=list(ImageType),
        help="Specifies the image type to use.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip running the agent, just log the actions that would be taken.",
    )
    args = parser.parse_args()
    run(
        tasks_dir=args.tasks_dir,
        tasks_filter=args.tasks_filter,
        workers=args.workers,
        instance_id=args.instance,
        model_name=args.model,
        model_class=args.model_class,
        config_path=args.config,
        environment_class=args.environment_class,
        run_name=args.run_name,
        skip_existing=args.skip_existing,
        docker_image_type=args.images,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

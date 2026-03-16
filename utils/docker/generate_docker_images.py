#!/usr/bin/env python3
# Copyright 2024 Google LLC
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

"""Generates docker images for each task in the task json file."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Tuple

import docker
from common.loader import load_all_tasks
from common.logger import configure_logging
from rich import print
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
import yaml
from .prebuild import run_prebuild_checks

logger = logging.getLogger(__name__)
configure_logging()

tmp_dir = "/tmp/android-bench-repos"

lock = threading.Lock()
build_counter = 0
failed_builds = []


class BuildManager:
    """Manages the display of multiple concurrent builds."""

    output_lines = 5

    """Manages the display of multiple concurrent builds."""

    def __init__(self):
        self.panels: dict[str, Panel] = {}
        self.lock = threading.Lock()
        self.group = Group()

    def add_build(self, image_name):
        with self.lock:
            panel = Panel("Starting...", title=f"{image_name}", style="bold yellow")
            self.panels[image_name] = panel
            self.group = Group(*self.panels.values())
        return panel

    def update_build(
        self,
        image_name,
        output,
        subtitle: str | None = None,
        style: str | None = None,
    ):
        with self.lock:
            self.panels[image_name].renderable = output
            if subtitle:
                self.panels[image_name].subtitle = subtitle
            if style:
                self.panels[image_name].style = style

    def get_group(self):
        with self.lock:
            return self.group


def build_docker_image(
    image_name, dockerfile_path, total, context_dir, build_manager: BuildManager
):
    """Builds a docker image."""

    Path(context_dir).mkdir(parents=True, exist_ok=True)

    global build_counter
    output_lines = []
    build_manager.add_build(image_name)

    try:
        build_command = [
            "docker",
            "build",
            "-t",
            image_name,
            "-f",
            dockerfile_path,
            context_dir,
        ]
        process = subprocess.Popen(
            build_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if process.stdout:
            for line in process.stdout:
                output_lines.append(line)
                build_manager.update_build(
                    image_name, "".join(output_lines[-BuildManager.output_lines :])
                )
        process.wait()

        output = "".join(output_lines)

        if process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode, build_command, output=output
            )

        with lock:
            build_counter += 1
            build_manager.update_build(
                image_name,
                "".join(output_lines[-BuildManager.output_lines :]),
                subtitle=(
                    f"[{build_counter}/{total}] Successfully built docker image:"
                    f" {image_name}"
                ),
                style="bold green",
            )
        return None

    except subprocess.CalledProcessError as e:
        with lock:
            build_counter += 1
            failed_builds.append(image_name)
            build_manager.update_build(
                image_name,
                e.output,
                subtitle=f"[{build_counter}/{total}] Error building {image_name}",
                style="bold red",
            )
        return f"Error building docker image {image_name}"


def _build_images(
    images_to_build: List[Tuple[str, str, str]],
    max_workers: int,
    build_type: str,
):
    """Builds a list of docker images in parallel."""

    global build_counter
    build_counter = 0
    total_builds = len(images_to_build)
    logger.info("Building %d %s images...", total_builds, build_type)
    build_manager = BuildManager()
    with Live(
        build_manager.get_group(),
        refresh_per_second=10,
        vertical_overflow="visible",
    ) as live:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    build_docker_image,
                    name,
                    path,
                    total_builds,
                    context_dir,
                    build_manager,
                )
                for name, path, context_dir in images_to_build
            }

            def update_live():
                while any(not f.done() for f in futures):
                    live.update(build_manager.get_group())
                    time.sleep(0.1)

            update_thread = threading.Thread(target=update_live)
            update_thread.start()

            for future in as_completed(futures):
                result = future.result()
                if result:
                    print(result, file=sys.stderr)
            update_thread.join()


def _checkout_repo(
    commit_info: Dict[str, Any], clone_dir: str, repo_info: Dict[str, Any]
) -> str:
    """Checks out the correct commit for a repo."""
    print(commit_info)
    commit_sha = commit_info.get("sha")
    if commit_sha:
        subprocess.run(
            f"cd {clone_dir} && git reset --hard {commit_sha}",
            shell=True,
            check=True,
        )
        return commit_sha
    else:
        raise ValueError("sha must be specified in base_commit.")


def shell_commands_to_remove_all_commits_after_base_commit(before_commit_sha):
    return f"""git remote remove origin || true && \\
    git branch | grep -v '*' | xargs git branch -D || true && \\
    TARGET_TIMESTAMP=$(git show -s --format=%ct {before_commit_sha}) && \\
    git tag -l | while read tag; do \\
        TAG_COMMIT=$(git rev-list -n 1 "$tag"); \\
        TAG_TIME=$(git show -s --format=%ct "$TAG_COMMIT"); \\
        if [ "$TAG_TIME" -gt "$TARGET_TIMESTAMP" ]; then \\
            git tag -d "$tag"; \\
        fi; \\
    done && \\
    git reflog expire --expire=now --all && \\
    git gc --prune=now --aggressive"""


def _get_base_image_name(repo_url: str):
    repo_parts = repo_url.split("/")
    return f'{repo_parts[-2]}-{repo_parts[-1].replace(".git", "")}'


def generate_base_dockerfile(repo_url: str, tasks_dir: Path) -> Tuple[str, Path]:
    repo_name = _get_base_image_name(repo_url)
    image_name = f"{repo_name}-base".lower()
    base_images_dir = tasks_dir / "base_images"
    base_images_dir.mkdir(parents=True, exist_ok=True)
    dockerfile_path = base_images_dir / f"{image_name}.dockerfile"

    dockerfile_content = f"""FROM android-bench-env
RUN git clone {repo_url} /workspace/testbed
WORKDIR /workspace
"""
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)

    return image_name, dockerfile_path


def generate_task_dockerfile(task: Dict[str, Any], tasks_dir: Path) -> Tuple[str, Path]:
    image_name = task["instance_id"].lower()
    task_dir = tasks_dir / task["instance_id"]
    task_dir.mkdir(parents=True, exist_ok=True)
    dockerfile_path = task_dir / "Dockerfile"

    repo_info = task["repository"]
    repo_url = repo_info.get("url")
    before_commit_info = task["before_commit"]
    java_version = before_commit_info.get("java_version")
    if not java_version:
        java_version = 17

    # BUILD type tasks don't build to start, so skip trying to build them during docker build
    if task["testing_type"] == "BUILD":
        build_commands = []
    else:
        build_commands = task["commands"].get("build") or ["./gradlew assembleDebug"]

    before_build_commands = task["commands"].get("before_build") or []
    all_commands = [
        cmd for cmd in before_build_commands + build_commands if cmd and cmd.strip()
    ]
    build_command = " && ".join(all_commands)
    java_home = f"/usr/lib/jvm/java-{java_version}-openjdk-amd64"
    java_home_env = f"ENV JAVA_HOME={java_home}"

    if "sha" not in before_commit_info:
        raise ValueError("sha must be specified in before_commit.")
    commit_sha = before_commit_info.get("sha")
    git_reset_command = f"git reset --hard {commit_sha}"
    dockerfile_content = f"""FROM {_get_base_image_name(repo_url).lower()}-base
{java_home_env}
ENV GRADLE_OPTS="-Xmx6g"
RUN cd /workspace/testbed && \\
    {git_reset_command} && \\
    {shell_commands_to_remove_all_commits_after_base_commit(commit_sha)}"""

    if build_command:
        dockerfile_content = dockerfile_content + f""" && \\
    {build_command}"""
    dockerfile_content = dockerfile_content + "\nWORKDIR /workspace/testbed\n"
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)

    return image_name, dockerfile_path


def ensure_images_exist(
    tasks: List[Dict[str, Any]],
    client: Any,
    tasks_dir: Path,
    max_workers: int = 4,
):
    """Ensures that all required docker images exist for the given tasks."""
    script_dir = os.path.dirname(os.path.realpath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))

    # 1. Ensure android-bench-env exists
    try:
        client.images.get("android-bench-env")
        logger.info("Image android-bench-env already exists.")
    except Exception:
        logger.info("Image android-bench-env not found. Building...")
        _build_images(
            [
                (
                    "android-bench-env",
                    os.path.join(root_dir, "utils/docker/Dockerfile"),
                    root_dir,
                )
            ],
            max_workers,
            "android-bench-env",
        )
        if "android-bench-env" in failed_builds:
            raise RuntimeError("Failed to build android-bench-env image")

    # 2. Ensure base images exist
    repos = {task["repository"].get("url") for task in tasks}
    base_images_to_build = []
    for repo_url in repos:
        repo_name = _get_base_image_name(repo_url)
        image_name = f"{repo_name}-base".lower()
        try:
            client.images.get(image_name)
            logger.info(f"Base image {image_name} already exists.")
        except Exception:
            logger.info(f"Base image {image_name} not found. Generating and building...")
            _, dockerfile_path = generate_base_dockerfile(repo_url, tasks_dir)
            base_images_to_build.append((image_name, str(dockerfile_path), tmp_dir))

    if base_images_to_build:
        _build_images(base_images_to_build, max_workers, "base")
        for image_name, _, _ in base_images_to_build:
            if image_name in failed_builds:
                raise RuntimeError(f"Failed to build base image {image_name}")

    # 3. Ensure task images exist
    task_images_to_build = []
    for task in tasks:
        image_name = task["instance_id"].lower()
        try:
            client.images.get(image_name)
            logger.info(f"Task image {image_name} already exists.")
        except Exception:
            logger.info(f"Task image {image_name} not found. Generating and building...")
            _, dockerfile_path = generate_task_dockerfile(task, tasks_dir)
            task_images_to_build.append((image_name, str(dockerfile_path), tmp_dir))

    if task_images_to_build:
        _build_images(task_images_to_build, max_workers, "task")
        for image_name, _, _ in task_images_to_build:
            if image_name in failed_builds:
                raise RuntimeError(f"Failed to build task image {image_name}")


def main():
    run_prebuild_checks()
    script_dir = os.path.dirname(os.path.realpath(__file__))
    root_dir = os.path.join(script_dir, "..", "..")

    parser = argparse.ArgumentParser(description="Generate docker images for tasks.")
    parser.add_argument(
        "--tasks-dir",
        type=Path,
        default=root_dir / Path("dataset/tasks"),
        help="Path to the tasks directory.",
    )
    parser.add_argument(
        "--tasks-filter",
        "--tasks_filter",
        type=str,
        default=None,
        help=(
            "Yaml file with instance_ids to filter tasks. Prefix with '!' to" " negate."
        ),
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build the docker images after generating them.",
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=4,
        help="Maximum number of parallel builds.",
    )
    parser.add_argument(
        "--task_id",
        help="Only generate the docker image for this task id.",
    )
    args = parser.parse_args()

    if args.build:
        client = docker.DockerClient.from_env()
        try:
            all_tasks = load_all_tasks(args.tasks_dir, args.tasks_filter)
            tasks = [task.model_dump(mode="json") for task in all_tasks]

            if args.task_id:
                tasks = [task for task in tasks if task["instance_id"] == args.task_id]
                if not tasks:
                    raise ValueError(f"Task with id {args.task_id} not found.")

            ensure_images_exist(
                tasks, client, args.tasks_dir, max_workers=args.max_workers
            )
        except Exception as e:
            logger.error(f"Error ensuring images exist: {e}")
            sys.exit(1)
        finally:
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)
            if failed_builds:
                with open("known_failures.yaml", "w") as f:
                    yaml.dump(failed_builds, f)
                print(f"Failed builds: {failed_builds}")
                sys.exit(1)
    else:
        # Just generate Dockerfiles without building
        try:
            all_tasks = load_all_tasks(args.tasks_dir, args.tasks_filter)
            tasks = [task.model_dump(mode="json") for task in all_tasks]

            if args.task_id:
                tasks = [task for task in tasks if task["instance_id"] == args.task_id]
                if not tasks:
                    raise ValueError(f"Task with id {args.task_id} not found.")

            # Generate base Dockerfiles
            repos = {task["repository"].get("url") for task in tasks}
            for repo_url in repos:
                generate_base_dockerfile(repo_url, args.tasks_dir)

            # Generate task Dockerfiles
            for task in tasks:
                generate_task_dockerfile(task, args.tasks_dir)

        except Exception as e:
            logger.error(f"Error generating Dockerfiles: {e}")
            sys.exit(1)

    print("Finished")


if __name__ == "__main__":
    main()

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
from common.loader import load_all_tasks
from common.logger import configure_logging
from rich import print
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
import yaml
from .prebuild import run_prebuild_checks
from .resources import recommend_gradle_memory, recommend_max_workers

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


def _image_exists(image_name: str) -> bool:
    """Returns True if a Docker image already exists locally."""
    result = subprocess.run(
        ["docker", "image", "inspect", image_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def build_docker_image(
    image_name,
    dockerfile_path,
    total,
    context_dir,
    build_manager: BuildManager,
    build_timeout: int = 1800,
    skip_existing: bool = False,
):
    """Builds a docker image."""

    if skip_existing and _image_exists(image_name):
        with lock:
            global build_counter
            build_counter += 1
            build_manager.add_build(image_name)
            build_manager.update_build(
                image_name,
                "Image already exists, skipping build.",
                subtitle=(
                    f"[{build_counter}/{total}] Skipped (already exists):"
                    f" {image_name}"
                ),
                style="bold cyan",
            )
        return None

    Path(context_dir).mkdir(parents=True, exist_ok=True)

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
        try:
            process.wait(timeout=build_timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise subprocess.CalledProcessError(
                -1,
                build_command,
                output=f"Build timed out after {build_timeout}s\n"
                + "".join(output_lines[-20:]),
            )

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
    build_timeout: int = 1800,
    skip_existing: bool = False,
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
                    build_timeout,
                    skip_existing,
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
    git gc --prune=now"""


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
        default=0,
        help="Maximum number of parallel builds (0 = auto-detect based on system resources).",
    )
    parser.add_argument(
        "--task_id",
        help="Only generate the docker image for this task id.",
    )
    parser.add_argument(
        "--gradle_memory",
        type=str,
        default=None,
        help="Gradle heap size for GRADLE_OPTS -Xmx (e.g. '2g'). Default: auto-detect.",
    )
    parser.add_argument(
        "--skip_existing",
        action="store_true",
        help="Skip building images that already exist locally.",
    )
    parser.add_argument(
        "--build_timeout",
        type=int,
        default=1800,
        help="Timeout in seconds for each Docker build (default: 1800).",
    )
    args = parser.parse_args()

    gradle_memory = args.gradle_memory or recommend_gradle_memory()
    max_workers = args.max_workers
    if max_workers == 0:
        max_workers = recommend_max_workers()
    logger.info(
        "Resource settings: max_workers=%d, gradle_memory=%s", max_workers, gradle_memory
    )

    if args.build:
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
            args.build_timeout,
            args.skip_existing,
        )

        if len(failed_builds) > 0:
            print("Base must be buildable")
            exit()

    try:
        all_tasks = load_all_tasks(args.tasks_dir, args.tasks_filter)
        tasks = [task.model_dump(mode="json") for task in all_tasks]

        if len(tasks) == 0:
            logger.info("No tasks to process")

        if args.task_id:
            tasks = [task for task in tasks if task["instance_id"] == args.task_id]
            if not tasks:
                raise ValueError(f"Task with id {args.task_id} not found.")

        # Generate and build base images first
        repos = set()
        for task in tasks:
            repos.add(task["repository"].get("url"))

        Path(tmp_dir).mkdir(parents=True, exist_ok=True)
        base_images_to_build: list[tuple[str, str, str]] = []
        total_repos = len(repos)
        for i, (repo_url) in enumerate(repos):

            repo_name = _get_base_image_name(repo_url)
            image_name = f"{repo_name}-base".lower()
            base_images_dir = args.tasks_dir / "base_images"
            base_images_dir.mkdir(parents=True, exist_ok=True)
            dockerfile_path = base_images_dir / f"{image_name}.dockerfile"

            if args.build:
                base_images_to_build.append((image_name, str(dockerfile_path), tmp_dir))

            logger.info(
                "Generating docker image %d/%d for: %s",
                i + 1,
                total_repos,
                image_name,
            )

            dockerfile_content = f"""FROM android-bench-env
RUN git clone {repo_url} /workspace/testbed
WORKDIR /workspace
"""
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)

        if args.build:
            _build_images(
                base_images_to_build,
                max_workers,
                "base",
                args.build_timeout,
                args.skip_existing,
            )

        # Generate and build task-specific images
        task_images_to_build: list[tuple[str, str, str]] = []
        total_tasks = len(tasks)
        for i, task in enumerate(tasks):
            image_name = task["instance_id"].lower()
            task_dir = args.tasks_dir / task["instance_id"]
            task_dir.mkdir(parents=True, exist_ok=True)
            dockerfile_path = task_dir / "Dockerfile"

            logger.info(
                "Generating docker image %d/%d for: %s",
                i + 1,
                total_tasks,
                image_name,
            )

            repo_info = task["repository"]
            repo_url = repo_info.get("url")
            logger.info("Repo url %s", repo_url)
            repo_name = repo_url.split("/")[-1].replace(".git", "")
            before_commit_info = task["before_commit"]
            after_commit_info = task["after_commit"]
            java_version = before_commit_info["java_version"]
            if not java_version:
                java_version = 17
            # BUILD type tasks don't build to start, so skip trying to build them during docker build
            if task["testing_type"] == "BUILD":
                build_commands = []
            else:
                build_commands = task["commands"].get("build") or [
                    "./gradlew assembleDebug"
                ]
            before_build_commands = task["commands"].get("before_build") or []
            all_commands = [
                cmd
                for cmd in before_build_commands + build_commands
                if cmd and cmd.strip()
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
ENV GRADLE_OPTS="-Xmx{gradle_memory}"
RUN cd /workspace/testbed && \\
    {git_reset_command} && \\
    {shell_commands_to_remove_all_commits_after_base_commit(commit_sha)}"""

            if build_command:
                dockerfile_content = dockerfile_content + f""" && \\
    {build_command}"""
            dockerfile_content = dockerfile_content + "\nWORKDIR /workspace/testbed\n"
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)

            if args.build:
                task_images_to_build.append((image_name, str(dockerfile_path), tmp_dir))

        if args.build:
            _build_images(
                task_images_to_build,
                max_workers,
                "task",
                args.build_timeout,
                args.skip_existing,
            )

    except Exception:
        import traceback

        traceback.print_exc()

    finally:
        print("Finished")
        if failed_builds:
            with open("known_failures.yaml", "w") as f:
                yaml.dump(failed_builds, f)
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)


def _get_base_image_name(repo_url: str):
    repo_parts = repo_url.split("/")
    return f'{repo_parts[-2]}-{repo_parts[-1].replace(".git", "")}'


if __name__ == "__main__":
    main()

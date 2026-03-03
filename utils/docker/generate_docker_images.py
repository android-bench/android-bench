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

"""
Generates docker images for each task in the task json file.
"""

import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Tuple
import threading
import shutil
import time
import yaml
from rich import print
from rich.console import Group
from rich.live import Live
from rich.panel import Panel

from common.loader import load_all_tasks

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
    image_name,
    dockerfile_path,
    total,
    context_dir,
    build_manager: BuildManager,
    arch=None,
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
        ]
        if arch:
            build_command.extend(["--platform", arch])

        build_command.extend(
            [
                "-t",
                image_name,
                "-f",
                dockerfile_path,
                context_dir,
            ]
        )
        env = os.environ.copy()
        env["DOCKER_BUILDKIT"] = "1"

        process = subprocess.Popen(
            build_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
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
                subtitle=f"[{build_counter}/{total}] Successfully built docker image: {image_name}",
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
            print(f"\n--- ERROR LOG FOR {image_name} ---")
            print(e.output)

            # Write raw error log to file
            log_file = f"build_errors_{image_name}.log"
            with open(log_file, "w") as f:
                f.write(e.output)
            print(f"Full error log saved to {log_file}")

        return f"Error building docker image {image_name}"


def _build_images(
    images_to_build: List[Tuple[str, str, str]],
    max_workers: int,
    build_type: str,
    arch: str | None = None,
):
    """Builds a list of docker images in parallel."""

    global build_counter
    build_counter = 0
    total_builds = len(images_to_build)
    print(f"Building {total_builds} {build_type} images...")
    build_manager = BuildManager()
    with Live(
        build_manager.get_group(), refresh_per_second=10, vertical_overflow="visible"
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
                    arch,
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


def main():
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
        help="Yaml file with instance_ids to filter tasks. Prefix with '!' to negate.",
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
    parser.add_argument(
        "--arch",
        type=str,
        default=None,
        help="Target architecture for the Docker image (e.g., linux/amd64, linux/arm64). Defaults to the host architecture.",
    )
    args = parser.parse_args()

    if args.build:
        _build_images(
            [
                (
                    "android-bench-env",
                    os.path.join(root_dir, "utils/docker/Dockerfile"),
                    root_dir,
                )
            ],
            args.max_workers,
            "android-bench-env",
            args.arch,
        )

        if len(failed_builds) > 0:
            print("Base must be buildable")
            exit()

    try:
        all_tasks = load_all_tasks(args.tasks_dir, args.tasks_filter)
        tasks = [task.model_dump(mode="json") for task in all_tasks]

        if len(tasks) == 0:
            print(f"No tasks to process")

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

            print("Generating docker image" f" {i+1}/{total_repos} for: {image_name}")

            dockerfile_content = f"""FROM android-bench-env
RUN git clone {repo_url} /workspace/testbed
WORKDIR /workspace
"""
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)

        if args.build:
            _build_images(base_images_to_build, args.max_workers, "base", args.arch)

        # Generate and build task-specific images
        task_images_to_build: list[tuple[str, str, str]] = []
        total_tasks = len(tasks)
        for i, task in enumerate(tasks):
            image_name = task["instance_id"].lower()
            task_dir = args.tasks_dir / task["instance_id"]
            task_dir.mkdir(parents=True, exist_ok=True)
            dockerfile_path = task_dir / "Dockerfile"

            print("Generating docker image" f" {i+1}/{total_tasks} for: {image_name}")

            repo_info = task["repository"]
            repo_url = repo_info.get("url")
            print(f"Repo url {repo_url}")
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
            
            # Using bash parameter expansion logic directly so it doesn't break depending on execution shell
            java_home_env = f"ENV JAVA_HOME=/usr/lib/jvm/java-{java_version}-openjdk-${{TARGETARCH:-amd64}}"
            
            if "sha" not in before_commit_info:
                raise ValueError("sha must be specified in before_commit.")
            commit_sha = before_commit_info.get("sha")
            git_reset_command = f"git reset --hard {commit_sha}"
            dockerfile_content = f"""FROM {_get_base_image_name(repo_url).lower()}-base
ARG TARGETARCH
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

            if args.build:
                task_images_to_build.append((image_name, str(dockerfile_path), tmp_dir))

        if args.build:
            _build_images(task_images_to_build, args.max_workers, "task", args.arch)

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

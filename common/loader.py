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
from pathlib import Path
import yaml
from .models import Task
from .constants import TASKS_DIR


def load_all_tasks(
    tasks_dir: Path = TASKS_DIR, tasks_filter: str | None = None
) -> list[Task]:
    """Load all benchmark tasks from directory structure.

    Loads tasks from tasks_dir/{instance_id}/task.yaml files.

    Args:
        tasks_dir: Path to the tasks directory containing task subdirectories.
        filter_tasks: Path to a filtering file containing array of instance_ids. If the path is prefixed
            with '!', the filter is negated, meaning tasks in the file will be excluded.

    To call the negation filter from shell, you need to wrap the argument, for example:  --tasks-filter '!./tasks/v1_tasks.yaml'

    Returns:
        List of Task objects sorted by instance_id.
    """

    filter_tasks_list = []
    negate_filter = False
    if tasks_filter:
        if tasks_filter.startswith("!"):
            negate_filter = True
            tasks_filter_path = Path(tasks_filter[1:])
        else:
            tasks_filter_path = Path(tasks_filter)

        with open(tasks_filter_path, "r") as f:
            filter_tasks_list = yaml.safe_load(f)

    tasks = []
    for task_subdir in tasks_dir.iterdir():
        if not task_subdir.is_dir():
            continue
        task_file = task_subdir / "task.yaml"
        if not task_file.exists():
            continue

        if filter_tasks_list:
            if negate_filter:
                if task_subdir.name in filter_tasks_list:
                    continue
            else:
                if task_subdir.name not in filter_tasks_list:
                    continue

        with open(task_file, "r") as f:
            raw_data = yaml.safe_load(f)
            tasks.append(Task.model_validate(raw_data))

    return sorted(tasks, key=lambda t: t.instance_id)


def load_tasks() -> list[Task]:
    """Load benchmark tasks from the default location.

    Convenience function that calls load_all_tasks with the default tasks directory.
    """
    return load_all_tasks(TASKS_DIR)

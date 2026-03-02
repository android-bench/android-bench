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
import json
from collections import Counter
from typing import Dict, Any, List
import typer
from rich.console import Console

from common.constants import TASKS_DIR

console = Console()
SUMMARY_FILE = TASKS_DIR / "summary.json"


def load_summary() -> List[Dict[str, Any]]:
    """Loads the pre-computed summary.json."""
    if not SUMMARY_FILE.exists():
        console.print(
            "[red]Error: summary.json not found.[/red] Please run "
            "'uv run python utils/visualizer/generate_task_summary.py' first."
        )
        raise typer.Exit(code=1)
    with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_dataset_stats(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates high-level statistics for the dataset."""
    total_tasks = len(tasks)
    repos = Counter([(t.get("repository", {}).get("name") or "Unknown") for t in tasks])
    categories = Counter([c for t in tasks for c in t.get("category_ids", [])])
    task_types = Counter([t.get("task_type") for t in tasks])

    return {
        "total": total_tasks,
        "repos": repos,
        "categories": categories,
        "types": task_types,
    }

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
"""Data exploration and filtering utilities."""

from collections import Counter
from enum import Enum
import json
import logging
from typing import Any, Dict, List, Optional
from common.constants import TASKS_DIR
from common.logger import configure_logging
from rich.console import Console
from .generate_task_summary import generate_summary

logger = logging.getLogger(__name__)
configure_logging()
console = Console()
SUMMARY_FILE = TASKS_DIR / "summary.json"


class EstimateFilter(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def load_summary() -> List[Dict[str, Any]]:
    """Loads the pre-computed summary.json."""
    if not SUMMARY_FILE.exists():
        logger.info("Dataset summary missing. Creating summary.")
        generate_summary()
    with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_dataset_stats(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates high-level statistics for the dataset."""
    total_tasks = len(tasks)
    repos = Counter([(t.get("repository", {}).get("name") or "Unknown") for t in tasks])
    categories = Counter()
    for t in tasks:
        categories.update(t.get("category_ids", []))
    task_types = Counter([t.get("task_type") for t in tasks])

    return {
        "total": total_tasks,
        "repos": repos,
        "categories": categories,
        "types": task_types,
    }


def parse_estimate(est_str: str) -> float:
    """Parses time estimate string into hours."""
    if not est_str:
        return 0.0
    est_str = str(est_str).lower().replace(" ", "").replace("<", "")
    if "h" in est_str:
        try:
            return float(est_str.split("h")[0])
        except ValueError:
            return 0.0
    if "m" in est_str:
        try:
            return float(est_str.split("m")[0]) / 60.0
        except ValueError:
            return 0.0
    return 0.0


def filter_tasks(
    tasks: List[Dict[str, Any]],
    category: Optional[str] = None,
    repo: Optional[str] = None,
    search: Optional[str] = None,
    estimate: Optional[EstimateFilter] = None,
) -> List[Dict[str, Any]]:
    """Applies filters to the list of tasks."""
    filtered = tasks

    if category:
        filtered = [
            t
            for t in filtered
            if category.lower() in [c.lower() for c in t.get("category_ids", [])]
        ]

    if repo:
        filtered = [
            t
            for t in filtered
            if repo.lower() in (t.get("repository", {}).get("name") or "").lower()
        ]

    if search:
        search_lower = search.lower()
        filtered = [
            t
            for t in filtered
            if search_lower in t.get("instance_id", "").lower()
            or search_lower in t.get("summary", "").lower()
        ]

    if estimate:
        bucket_filtered = []
        for t in filtered:
            est_hours = parse_estimate(t.get("time_estimate", ""))
            if estimate == EstimateFilter.LOW and est_hours < 1.0:
                bucket_filtered.append(t)
            elif estimate == EstimateFilter.MEDIUM and 1.0 <= est_hours <= 4.0:
                bucket_filtered.append(t)
            elif estimate == EstimateFilter.HIGH and est_hours > 4.0:
                bucket_filtered.append(t)
        filtered = bucket_filtered

    return filtered


def sort_tasks(tasks: List[Dict[str, Any]], sort_by: str) -> List[Dict[str, Any]]:
    """Sorts tasks based on the specified criteria."""
    if sort_by == "id":
        return sorted(tasks, key=lambda x: x.get("instance_id", ""))
    elif sort_by == "repo":
        return sorted(tasks, key=lambda x: (x.get("repository", {}).get("name") or ""))
    elif sort_by == "category":
        return sorted(
            tasks,
            key=lambda x: (
                x.get("category_ids", [""])[0] if x.get("category_ids") else ""
            ),
        )
    return tasks

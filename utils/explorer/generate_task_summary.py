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

"""Utility to generate an enriched summary JSON for all tasks in the dataset.

This script scans the tasks directory, parses task.yaml files, and creates
a centralized summary.json with additional context for human-centric browsing.

Usage:
    python3 utils/generate_task_summary.py
"""

import json
import yaml
from pathlib import Path
from common.constants import TASKS_DIR

SUMMARY_FILE = TASKS_DIR / "summary.json"


def get_summary_line(description):
    """Extracts the first non-empty line of the description."""
    if not description:
        return "No description available."
    for line in description.splitlines():
        clean_line = line.strip().lstrip("# ").lstrip("* ").strip()
        if clean_line:
            # Truncate if too long
            return (clean_line[:77] + "...") if len(clean_line) > 80 else clean_line
    return "No summary available."


def generate_summary():
    """Scans tasks and generates summary.json with enriched metadata."""
    tasks_summary = []

    print(f"Scanning tasks in {TASKS_DIR}...")

    # Iterate through all subdirectories in TASKS_DIR
    for task_path in sorted(TASKS_DIR.iterdir()):
        if not task_path.is_dir():
            continue

        yaml_file = task_path / "task.yaml"
        if not yaml_file.exists():
            continue

        try:
            with open(yaml_file, "r") as f:
                task_data = yaml.safe_load(f)

            # Extract essential metadata for the summary
            summary_entry = {
                "instance_id": task_data.get("instance_id"),
                "repository": {
                    "owner": task_data.get("repository", {}).get("owner"),
                    "name": task_data.get("repository", {}).get("name"),
                },
                "category_ids": task_data.get("category_ids", []),
                "task_type": task_data.get("task_type"),
                "time_estimate": task_data.get("time_estimate", "Unknown"),
                "summary": get_summary_line(task_data.get("description")),
            }
            tasks_summary.append(summary_entry)
        except Exception as e:
            print(f"Error parsing {yaml_file}: {e}")

    # Write the summary to a JSON file
    with open(SUMMARY_FILE, "w") as f:
        json.dump(tasks_summary, f, indent=2)

    print(
        f"Successfully generated enriched summary for {len(tasks_summary)} tasks at {SUMMARY_FILE}"
    )


if __name__ == "__main__":
    generate_summary()

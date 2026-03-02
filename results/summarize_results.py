#!/usr/bin/env python3

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
"""
Summarize benchmark results across multiple model runs.

Input: a folder containing multiple runs (e.g., out-11-22)
Output: CSV table grouping results by status per model (averaged if multiple runs)
"""

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from common.run_config import read_run_config
from common.models.benchmark import Status


@dataclass
class ScoreConfig:
    """Configuration for a single score file."""

    model_name: str
    scores_path: Path


def summarize_scores(configs: list[ScoreConfig]) -> str:
    """
    Summarize benchmark results from multiple score configs.

    Args:
        configs: List of ScoreConfig with model name and path to scores.json

    Returns:
        CSV string with results grouped by model (averaged if multiple runs)
    """
    if not configs:
        return ""

    # Collect results per model (may have multiple runs per model)
    all_statuses: set[str] = set()
    model_runs: dict[str, list[Counter[str]]] = {}

    for config in configs:
        with open(config.scores_path) as f:
            data = json.load(f)

        status_counts: Counter[Status | str] = Counter()
        for instance_id, result in data.items():
            status_str = result.get("status", "UNKNOWN")
            if isinstance(status_str, str):
                try:
                    status = Status[status_str]
                except (KeyError, TypeError):
                    status = status_str
            else:
                status = status_str
            status_counts[status] += 1
            all_statuses.add(status)

        if config.model_name not in model_runs:
            model_runs[config.model_name] = []
        model_runs[config.model_name].append(status_counts)

    # Build CSV output with PASSED first, other statuses sorted, TOTAL last
    lines = []
    # Use str for sorting to handle Enum members
    other_statuses = sorted(all_statuses - {Status.PASSED}, key=str)
    ordered_statuses = (
        [Status.PASSED] if Status.PASSED in all_statuses else []
    ) + other_statuses
    lines.append("model," + ",".join(str(s) for s in ordered_statuses) + ",TOTAL")

    # Calculate average PASSED count per model for sorting
    def get_sort_key(model_name: str) -> tuple:
        runs = model_runs[model_name]
        num_runs = len(runs)
        avg_passed = sum(r.get(Status.PASSED.name, 0) for r in runs) / num_runs
        # Parse provider/model from model_name (e.g., "anthropic/claude-3")
        parts = model_name.split("/", 1)
        provider = parts[0] if len(parts) > 1 else ""
        model = parts[1] if len(parts) > 1 else model_name
        # Sort by: PASSED desc (negate for descending), provider asc, model asc
        return (-avg_passed, provider, model)

    # Each model's results (averaged if multiple runs)
    for model_name in sorted(model_runs.keys(), key=get_sort_key):
        runs = model_runs[model_name]
        num_runs = len(runs)

        row = [model_name]
        total = 0.0
        for status in ordered_statuses:
            avg = sum(r.get(status, 0) for r in runs) / num_runs
            row.append(f"{avg:.1f}" if avg != int(avg) else str(int(avg)))
            total += avg
        row.append(f"{total:.1f}" if total != int(total) else str(int(total)))
        lines.append(",".join(row))

    return "\n".join(lines)


def parse_args_and_run():
    """Parse command line arguments and run summarization."""
    parser = argparse.ArgumentParser(
        description="Summarize benchmark results across multiple runs as CSV."
    )
    parser.add_argument("out", help="The output folder containing multiple runs.")
    args = parser.parse_args()

    out = Path(args.out)
    if not out.is_dir():
        print(f"Error: {out} is not a directory", file=sys.stderr)
        sys.exit(1)

    # Find all scores.json files
    scores_files = list(out.glob("*/*scores.json"))
    if not scores_files:
        print(f"Error: No *scores.json files found in {out}", file=sys.stderr)
        sys.exit(1)

    # Build configs from discovered files
    configs = []
    for scores_file in sorted(scores_files):
        run_dir = scores_file.parent

        # Get model name from config.properties
        try:
            config = read_run_config(run_dir)
            model_name = config.get("model_name", run_dir.name)
        except FileNotFoundError:
            model_name = run_dir.name

        configs.append(ScoreConfig(model_name=model_name, scores_path=scores_file))

    # Run summarization and print result
    print(summarize_scores(configs))


if __name__ == "__main__":
    parse_args_and_run()

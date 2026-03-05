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
import time
from rich.console import Console
from rich.theme import Theme
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box  # Needed for box.SIMPLE

# Define theme
custom_theme = Theme(
    {
        "info": "bold cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "highlight": "bold cyan",
    }
)

# Initialize console
console = Console(theme=custom_theme)


def create_dashboard(job_data, start_time, title="Android Benchmark Status"):
    """Generates a summary table wrapped in a Panel for layout."""

    counts = {
        "PENDING": 0,
        "SUBMITTED": 0,
        "SCHEDULED": 0,
        "RUNNING": 0,
        "FAILED": 0,
        "SUCCEEDED": 0,
    }

    for d in job_data.values():
        raw_status = d.get("status", "UNKNOWN").upper()
        if "SUBMIT" in raw_status:
            counts["SUBMITTED"] += 1
        elif raw_status in ["SUCCEEDED", "COMPLETED"]:
            counts["SUCCEEDED"] += 1
        elif raw_status in ["FAILED", "CANCELLED"]:
            counts["FAILED"] += 1
        elif raw_status == "RUNNING":
            counts["RUNNING"] += 1
        elif raw_status == "PENDING":
            counts["PENDING"] += 1
        else:
            counts["SCHEDULED"] += 1

    # Table configuration
    table = Table(
        box=box.SIMPLE,
        padding=(0, 2),
        show_header=True,
        header_style="bold white",
        expand=True,
    )

    table.add_column("Status Category", justify="left")
    table.add_column("Job Count", justify="right")

    # Define rows
    rows = [
        ("PENDING", "dim white"),
        ("SUBMITTED", "bold blue"),
        ("SCHEDULED", "yellow"),
        ("RUNNING", "bold cyan"),
        ("FAILED", "bold red"),
        ("SUCCEEDED", "bold green"),
    ]

    for status_name, style in rows:
        count = counts[status_name]
        count_style = style if count > 0 else "dim white"
        table.add_row(
            Text(status_name, style=style), Text(str(count), style=count_style)
        )

    total_jobs = len(job_data)
    elapsed_seconds = int(time.time() - start_time)
    elapsed_str = f"{elapsed_seconds // 60:02d}:{elapsed_seconds % 60:02d}"

    # Wrap table in a Panel
    return Panel(
        table,
        title=f"[bold]{title}[/bold] (Total: {total_jobs} | Time: {elapsed_str})",
        border_style="info",
        padding=(1, 2),
    )

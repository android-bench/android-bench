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
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box
import typer
from enum import Enum
import math
from typing import List, Callable, Any, Optional, Dict

console = Console()


class SortOrder(str, Enum):
    id = "id"
    repo = "repo"
    category = "category"


CATEGORY_COLORS = {
    # UI/UX Theme (Cyan)
    "compose": "cyan",
    "material": "cyan",
    "navigation": "cyan",
    "talkback": "cyan",
    "sysUI-edgeToEdge": "cyan",
    "largeScreens": "cyan",
    "orientationChanges": "cyan",
    "foldableChanges": "cyan",
    # Architecture/Core Theme (Magenta)
    "hilt": "magenta",
    "room": "magenta",
    "viewModel": "magenta",
    "coroutines-flows": "magenta",
    "concurrency": "magenta",
    "dataStore": "magenta",
    "domain": "magenta",
    # OS/System Theme (Green)
    "bluetooth": "green",
    "permissions": "green",
    "storage": "green",
    "externalInputDevices": "green",
    "android-apis": "green",
    "androidSdkUpdates": "green",
    "workManager": "green",
    "networking": "green",
    "imageLoading": "green",
    # Build/Config Theme (Yellow)
    "build": "yellow",
    "buildGradle": "yellow",
    "dependencyUpgrades": "yellow",
    "config-changes": "yellow",
    "kmp": "yellow",
    "AUTOMATIC": "yellow",
    # Specialized Theme (Red)
    "securityPrivacy": "red",
    "performance": "red",
}


def get_category_color(category: str) -> str:
    """Returns the color string for a given category."""
    return CATEGORY_COLORS.get(category, "white")


def paginate_results(
    items: List[Any],
    render_func: Callable[[List[Any], int], None],
    page_size: int = 20,
):
    """Paginates a list of items, yielding chunks to a render function."""
    if not items:
        console.print("[yellow]No results to display.[/yellow]")
        return

    total_items = len(items)
    total_pages = math.ceil(total_items / page_size)
    current_page = 1

    while True:
        start_idx = (current_page - 1) * page_size
        end_idx = min(start_idx + page_size, total_items)

        # Render the current chunk
        current_chunk = items[start_idx:end_idx]
        render_func(current_chunk, start_idx)

        if total_pages <= 1:
            break

        # Show pagination controls
        console.print(
            f"\n[dim]Page {current_page} of {total_pages} ({total_items} total items)[/dim]"
        )

        choices = []
        prompt_text = "Select an option:"
        if current_page < total_pages:
            choices.append("n")
            prompt_text += " [bold cyan]\\[n][/bold cyan]ext"
        if current_page > 1:
            choices.append("p")
            prompt_text += " [bold cyan]\\[p][/bold cyan]revious"
        choices.append("x")
        prompt_text += " [bold cyan]\\[x][/bold cyan] exit"

        choice = Prompt.ask(prompt_text, choices=choices, show_choices=False).lower()

        if choice == "n" and current_page < total_pages:
            current_page += 1
        elif choice == "p" and current_page > 1:
            current_page -= 1
        elif choice == "x":
            break


def render_task_table(
    tasks: List[Dict[str, Any]],
    title: str = "Tasks",
    start_idx: int = 0,
    show_columns: List[str] = ["idx", "id", "category", "repo", "summary"],
    ratios: Optional[Dict[str, int]] = None,
):
    """Renders a table of tasks with configurable columns and widths."""
    ratios = ratios or {}
    table = Table(title=title, box=box.MINIMAL, show_lines=True)

    # Column Mapping
    col_defs = {
        "idx": {"header": "Idx", "justify": "right", "style": "cyan"},
        "id": {"header": "Task ID", "style": "bold white"},
        "category": {"header": "Category"},
        "repo": {"header": "Repository", "style": "dim"},
        "summary": {"header": "Task Summary"},
        "type": {"header": "Type", "style": "blue"},
        "estimate": {"header": "Effort estimate", "style": "yellow"},
    }

    # Add columns based on requested order
    for col_key in show_columns:
        if col_key in col_defs:
            config = col_defs[col_key].copy()
            header = config.pop("header")
            ratio = ratios.get(col_key)
            table.add_column(header, ratio=ratio, **config)

    for i, task in enumerate(tasks):
        row_data = []
        for col_key in show_columns:
            if col_key == "idx":
                row_data.append(str(start_idx + i + 1))
            elif col_key == "id":
                row_data.append(task.get("instance_id", "N/A"))
            elif col_key == "category":
                cat_list = task.get("category_ids", [])
                primary_cat = cat_list[0] if cat_list else "Unknown"
                cat_color = get_category_color(primary_cat)
                row_data.append(f"[{cat_color}]{primary_cat}[/{cat_color}]")
            elif col_key == "repo":
                repo_name = task.get("repository", {}).get("name", "N/A")
                row_data.append(repo_name)
            elif col_key == "summary":
                full_summary = task.get("summary", "N/A")
                first_line = full_summary.split("\n")[0]
                row_data.append(first_line)
            elif col_key == "type":
                row_data.append(task.get("task_type", "N/A"))
            elif col_key == "estimate":
                row_data.append(task.get("time_estimate", "N/A"))

        table.add_row(*row_data)

    console.print(table)


def render_dataset_summary_panel(data: dict) -> Panel:
    """Renders a rich Panel summarizing the dataset stats."""

    # Format the high-level summary using rich text formatting
    summary_text = Text()
    summary_text.append("Dataset at a Glance\n\n", style="bold cyan")

    summary_text.append(f"• Total Tasks: ", style="bold")
    summary_text.append(f"{data['total']}\n", style="cyan")

    summary_text.append(f"• Unique Repositories: ", style="bold")
    summary_text.append(f"{len(data['repos'])}\n", style="cyan")

    summary_text.append(f"• KADA Categories: ", style="bold")
    summary_text.append(f"{len(data['categories'])}\n", style="cyan")

    return Panel.fit(
        summary_text, title="[bold]Android Bench Explorer[/bold]", border_style="cyan"
    )

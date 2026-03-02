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
import yaml
import typer
from rich.table import Table
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.columns import Columns
from typing import Optional
from enum import Enum
import math

from common.constants import TASKS_DIR
from .data import load_summary, get_dataset_stats
from .ui import (
    console,
    SortOrder,
    render_dataset_summary_panel,
    paginate_results,
    get_category_color,
)

app = typer.Typer(help="Android Bench Dataset Explorer", invoke_without_command=True)


@app.callback()
def main(ctx: typer.Context):
    """Run the interactive explorer by default if no command is provided."""
    if ctx.invoked_subcommand is None:
        explore()


@app.command()
def stats():
    """Show high-level statistics about the Android Bench dataset."""
    tasks = load_summary()
    data = get_dataset_stats(tasks)

    console.print(
        Panel.fit(
            f"[bold cyan]Android Bench Dataset Overview[/bold cyan]\n"
            f"Total Tasks: [bold]{data['total']}[/bold]\n"
            f"Repositories: [bold]{len(data['repos'])}[/bold]\n"
            f"Unique Categories: [bold]{len(data['categories'])}[/bold]",
            title="Summary",
        )
    )

    # Categories Table
    cat_table = Table(title="Top Categories (KADA)")
    cat_table.add_column("Category", style="magenta")
    cat_table.add_column("Count", justify="right")
    for cat, count in data["categories"].most_common(10):
        cat_table.add_row(cat, str(count))

    # Repo Table
    repo_table = Table(title="Top Repositories")
    repo_table.add_column("Repository", style="green")
    repo_table.add_column("Tasks", justify="right")
    for repo, count in data["repos"].most_common(10):
        repo_table.add_row(repo, str(count))

    console.print(Columns([cat_table, repo_table]))


class EstimateFilter(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


@app.command()
def browse(
    category: str = typer.Option(None, help="Filter by category"),
    repo: str = typer.Option(None, help="Filter by repository name"),
    search: str = typer.Option(None, help="Search by Task ID or Summary"),
    sort_by: SortOrder = typer.Option(SortOrder.id, "--sort", help="Sort by column"),
    expanded: bool = typer.Option(
        False, "--expanded", "-e", help="Show all metadata columns"
    ),
    estimate: Optional[EstimateFilter] = typer.Option(
        None, "--estimate", help="Filter by complexity bucket (low, medium, high)"
    ),
):
    """Browse and filter tasks in an enriched table view."""
    tasks = load_summary()

    # Parse numerical estimate hours (helper)
    def _parse_estimate(est_str: str) -> float:
        if not est_str:
            return 0.0
        est_str = str(est_str).lower().replace(" ", "")
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

    # Apply filters
    if category:
        tasks = [
            t
            for t in tasks
            if category.lower() in [c.lower() for c in t.get("category_ids", [])]
        ]
    if repo:
        tasks = [
            t
            for t in tasks
            if repo.lower() in (t.get("repository", {}).get("name") or "").lower()
        ]
    if search:
        tasks = [
            t
            for t in tasks
            if search.lower() in t.get("instance_id", "").lower()
            or search.lower() in t.get("summary", "").lower()
        ]
    if estimate:
        filtered = []
        for t in tasks:
            est_hours = _parse_estimate(t.get("time_estimate", ""))
            if estimate == EstimateFilter.low and est_hours < 1.0:
                filtered.append(t)
            elif estimate == EstimateFilter.medium and 1.0 <= est_hours <= 4.0:
                filtered.append(t)
            elif estimate == EstimateFilter.high and est_hours > 4.0:
                filtered.append(t)
        tasks = filtered

    # Sorting
    if sort_by == SortOrder.id:
        tasks.sort(key=lambda x: x.get("instance_id", ""))
    elif sort_by == SortOrder.repo:
        tasks.sort(key=lambda x: (x.get("repository", {}).get("name") or ""))
    elif sort_by == SortOrder.category:
        tasks.sort(
            key=lambda x: (
                x.get("category_ids", [""])[0] if x.get("category_ids") else ""
            )
        )

    if not tasks:
        console.print("[yellow]No tasks found matching the criteria.[/yellow]")
        return

    # Determine Active Columns
    show_category = expanded or category or sort_by == SortOrder.category
    show_repo = expanded or repo or sort_by == SortOrder.repo
    show_estimate = expanded or estimate

    def render_browse_chunk(task_chunk):
        table = Table(title=f"Android Bench Tasks", box=None, show_lines=True)
        table.add_column("Task ID", style="bold white", no_wrap=True)

        if show_category:
            table.add_column("Category")

        if show_repo:
            table.add_column("Repository", style="dim")

        summary_width = 60 if expanded else 100
        table.add_column("Summary", width=summary_width)

        if expanded:
            table.add_column("Type", style="blue")

        if show_estimate:
            table.add_column("Estimate", style="yellow")

        for task in task_chunk:
            task_id = task.get("instance_id", "N/A")
            row_data = [task_id]

            if show_category:
                cat_list = task.get("category_ids", [])
                primary_cat = cat_list[0] if cat_list else "Unknown"
                cat_color = get_category_color(primary_cat)
                row_data.append(f"[{cat_color}]{primary_cat}[/{cat_color}]")

            if show_repo:
                repo_name = task.get("repository", {}).get("name", "N/A")
                row_data.append(repo_name)

            full_summary = task.get("summary", "N/A")
            first_line = full_summary.split("\n")[0][:summary_width] + (
                "..." if len(full_summary) > summary_width else ""
            )
            row_data.append(first_line)

            if expanded:
                row_data.append(task.get("task_type", "N/A"))

            if show_estimate:
                row_data.append(task.get("time_estimate", "N/A"))

            table.add_row(*row_data)

        console.print(table)

    # Use the reusable pagination function
    paginate_results(tasks, render_browse_chunk, page_size=20)


@app.command()
def explore():
    """Guided Wizard to discover tasks based on your interests."""
    tasks = load_summary()
    data = get_dataset_stats(tasks)

    console.print(render_dataset_summary_panel(data))
    console.print("\n[bold]How would you like to start?[/bold]")
    console.print("  [bold cyan]\\[a][/bold cyan] Browse All")
    console.print("  [bold cyan]\\[c][/bold cyan] Filter by Category")
    console.print("  [bold cyan]\\[r][/bold cyan] Filter by Repository")
    console.print("  [bold cyan]\\[x][/bold cyan] Exit")

    choice = Prompt.ask(
        "Select an option",
        choices=["a", "c", "r", "x"],
        show_choices=False,
        default="a",
    ).lower()

    filtered_tasks = tasks
    if choice == "x":
        return
    elif choice == "c":
        top_cats = [c[0] for c in data["categories"].most_common(15)]
        console.print("\n[bold cyan]Top Categories:[/bold cyan]")
        for i, cat in enumerate(top_cats):
            console.print(f"  [bold cyan]\\[{i+1}][/bold cyan] {cat}")

        cat_idx = Prompt.ask(
            "Select a Key Android Developer Area (KADA) number",
            choices=[str(i + 1) for i in range(len(top_cats))],
        )
        cat = top_cats[int(cat_idx) - 1]
        filtered_tasks = [t for t in tasks if cat in t.get("category_ids", [])]
    elif choice == "r":
        top_repos = [r[0] for r in data["repos"].most_common(15)]
        console.print("\n[bold green]Top Repositories:[/bold green]")
        for i, repo in enumerate(top_repos):
            console.print(f"  [bold cyan]\\[{i+1}][/bold cyan] {repo}")

        repo_idx = Prompt.ask(
            "Select a Target Repository number",
            choices=[str(i + 1) for i in range(len(top_repos))],
        )
        repo = top_repos[int(repo_idx) - 1]
        filtered_tasks = [
            t for t in tasks if repo == t.get("repository", {}).get("name")
        ]

    if not filtered_tasks:
        console.print("[yellow]No tasks found.[/yellow]")
        return

    def render_task_chunk(task_chunk, start_idx):
        table = Table(title=f"Filtered Tasks", box=None, show_lines=True)
        table.add_column("Idx", justify="right", style="cyan")
        table.add_column("Task ID", style="bold white", no_wrap=True)
        table.add_column("Category")
        table.add_column("Summary", width=120)

        for i, task in enumerate(task_chunk):
            task_id = task.get("instance_id")

            # Category and Color
            cat_list = task.get("category_ids", [])
            primary_cat = cat_list[0] if cat_list else "Unknown"
            cat_color = get_category_color(primary_cat)
            styled_cat = f"[{cat_color}]{primary_cat}[/{cat_color}]"

            # Abridged Summary
            full_summary = task.get("summary", "N/A")
            first_line = full_summary.split("\n")[0][:110] + (
                "..." if len(full_summary) > 110 else ""
            )

            table.add_row(str(start_idx + i + 1), task_id, styled_cat, first_line)

        console.print(table)

    # Manual pagination loop to pass index correctly without breaking chunk logic
    def paginate_with_index(items, page_size=20):
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
            render_task_chunk(current_chunk, start_idx)

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

            choice = Prompt.ask(
                prompt_text, choices=choices, show_choices=False
            ).lower()

            if choice == "n" and current_page < total_pages:
                current_page += 1
            elif choice == "p" and current_page > 1:
                current_page -= 1
            elif choice == "x":
                break

    paginate_with_index(filtered_tasks, page_size=20)

    # Selection
    task_id_or_idx = Prompt.ask(
        "\nEnter a [bold cyan]Task ID[/bold cyan] or [bold cyan]Index[/bold cyan] to inspect (or press Enter to exit)"
    )
    if task_id_or_idx:
        # Check if user entered an index
        if task_id_or_idx.isdigit():
            idx = int(task_id_or_idx) - 1
            if 0 <= idx < len(filtered_tasks):
                task_id = filtered_tasks[idx].get("instance_id")
                inspect(task_id)
            else:
                console.print("[red]Invalid index selected.[/red]")
        else:
            inspect(task_id_or_idx)


@app.command()
def inspect(
    task_id: str,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show all regression tests and internal execution commands",
    ),
):
    """Deep dive into a specific task's details."""
    task_dir = TASKS_DIR / task_id
    yaml_file = task_dir / "task.yaml"

    if not yaml_file.exists():
        console.print(f"[red]Error: Task {task_id} not found at {yaml_file}[/red]")
        raise typer.Exit(code=1)

    with open(yaml_file, "r") as f:
        task_data = yaml.safe_load(f)

    # Render Header
    console.rule(f"[bold cyan]Task: {task_id}[/bold cyan]")

    # Basic Info Table
    info_table = Table(show_header=False, box=None)
    info_table.add_row(
        "Repository",
        f"{task_data.get('repository', {}).get('owner')}/{task_data.get('repository', {}).get('name')}",
    )
    info_table.add_row("Type", f"[bold blue]{task_data.get('task_type')}[/bold blue]")
    info_table.add_row("Estimate", str(task_data.get("time_estimate")))

    cat_list = task_data.get("category_ids", [])
    primary_cat = cat_list[0] if cat_list else "Unknown"
    cat_color = get_category_color(primary_cat)
    info_table.add_row(
        "Categories", f"[{cat_color}]" + ", ".join(cat_list) + f"[/{cat_color}]"
    )
    console.print(info_table)

    # Problem Statement
    console.print("\n[bold]Problem Statement:[/bold]")
    console.print(
        Panel(
            Markdown(task_data.get("description", "No description provided.")),
            border_style="dim",
        )
    )

    # Acceptance Criteria
    ac = task_data.get("acceptance_criteria", {})
    if ac:
        console.print("\n[bold]Acceptance Criteria:[/bold]")
        if ac.get("fail_to_pass"):
            console.print("  [red]Fail to Pass (Must Fix):[/red]")
            for test in ac.get("fail_to_pass"):
                console.print(f"    - {test}")
        if ac.get("pass_to_pass"):
            console.print("  [green]Pass to Pass (Regression Check):[/green]")
            regression_tests = ac.get("pass_to_pass")

            if verbose:
                for test in regression_tests:
                    console.print(f"    - {test}")
            else:
                for test in regression_tests[:5]:
                    console.print(f"    - {test}")
                if len(regression_tests) > 5:
                    console.print(
                        f"    [dim](+ {len(regression_tests) - 5} more regression tests)[/dim]"
                    )

    # Build Commands (Only if verbose)
    commands = task_data.get("commands", {})
    if commands and verbose:
        console.print("\n[bold]Execution Commands:[/bold]")
        for cmd_type, cmd_list in commands.items():
            if cmd_list:
                console.print(f"  [yellow]{cmd_type}:[/yellow]")
                for cmd in cmd_list:
                    console.print(f"    - [dim]{cmd}[/dim]")
    elif commands and not verbose:
        console.print(
            "\n[dim]Internal execution commands are hidden. Use --verbose to view them.[/dim]"
        )

    console.print("\n[dim]To run this task:[/dim]")
    console.print(
        f"[bold green]uv run run_task --model <MODEL> --task {task_id}[/bold green]\n"
    )

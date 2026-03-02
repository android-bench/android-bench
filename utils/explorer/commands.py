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
from rich import box
from typing import Optional
import logging
from common.logger import configure_logging

logger = logging.getLogger(__name__)
configure_logging()

from common.constants import TASKS_DIR
from .data import (
    load_summary,
    get_dataset_stats,
    filter_tasks,
    sort_tasks,
    EstimateFilter,
)
from .ui import (
    console,
    SortOrder,
    render_dataset_summary_panel,
    paginate_results,
    get_category_color,
    render_task_table,
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
    categories = data["categories"]

    console.print(
        Panel.fit(
            f"[bold cyan]Android Bench Dataset Overview[/bold cyan]\n"
            f"Total Tasks: [bold]{data['total']}[/bold]\n"
            f"Repositories: [bold]{len(data['repos'])}[/bold]\n"
            f"Categories: [bold]{len(categories)}[/bold]",
            title="Summary",
        )
    )

    # Categories Table
    cat_table = Table(title="Categories")
    cat_table.add_column("Top Categories", style="magenta")
    cat_table.add_column("Count", justify="right")
    for cat, count in categories.most_common(10):
        cat_table.add_row(cat, str(count))

    # Repo Table
    repo_table = Table(title="Top Repositories")
    repo_table.add_column("Repository", style="green")
    repo_table.add_column("Tasks", justify="right")
    for repo, count in data["repos"].most_common(10):
        repo_table.add_row(repo, str(count))

    console.print(Columns([cat_table, repo_table]))


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
    tasks = filter_tasks(tasks, category, repo, search, estimate)
    tasks = sort_tasks(tasks, sort_by.value)

    if not tasks:
        console.print("[yellow]No tasks found matching the criteria.[/yellow]")
        return

    # Determine Active Columns
    show_category = expanded or category or sort_by == SortOrder.category
    show_repo = expanded or repo or sort_by == SortOrder.repo
    show_estimate = expanded or estimate

    def render_chunk(chunk, start_idx):
        columns = ["idx", "id", "summary"]
        ratios = {
            "idx": 1,
            "id": 2,
            "summary": 6,
            "category": 2,
            "repo": 2,
            "type": 2,
            "estimate": 2,
        }

        if show_category:
            columns.append("category")
        if show_repo:
            columns.append("repo")
        if expanded:
            columns.append("type")
        if show_estimate:
            columns.append("estimate")

        render_task_table(
            chunk,
            title="Android Bench Tasks",
            start_idx=start_idx,
            show_columns=columns,
            ratios=ratios,
        )

    paginate_results(tasks, render_chunk, page_size=20)


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

    if choice == "x":
        return

    category = None
    repo = None

    if choice == "c":
        top_cats = [c[0] for c in data["categories"].most_common(15)]
        console.print("\n[bold cyan]Top Categories:[/bold cyan]")
        for i, cat in enumerate(top_cats):
            console.print(f"  [bold cyan]\\[{i+1}][/bold cyan] {cat}")

        cat_idx = Prompt.ask(
            "Select a Category number",
            choices=[str(i + 1) for i in range(len(top_cats))],
        )
        category = top_cats[int(cat_idx) - 1]
    elif choice == "r":
        top_repos = [r[0] for r in data["repos"].most_common(15)]
        console.print("\n[bold green]Top Repositories:[/bold green]")
        for i, repo_name in enumerate(top_repos):
            console.print(f"  [bold cyan]\\[{i+1}][/bold cyan] {repo_name}")

        repo_idx = Prompt.ask(
            "Select a Target Repository number",
            choices=[str(i + 1) for i in range(len(top_repos))],
        )
        repo = top_repos[int(repo_idx) - 1]

    filtered_tasks = filter_tasks(tasks, category=category, repo=repo)

    if not filtered_tasks:
        console.print("[yellow]No tasks found.[/yellow]")
        return

    def render_chunk(chunk, start_idx):
        render_task_table(
            chunk,
            title="Filtered Tasks",
            start_idx=start_idx,
            show_columns=["idx", "id", "summary", "category"],
            ratios={"idx": 1, "id": 1, "summary": 3, "category": 1},
        )

    paginate_results(filtered_tasks, render_chunk, page_size=10)

    # Selection
    task_id_or_idx = Prompt.ask(
        "\nTo inspect a task, enter its [bold cyan]Task ID[/bold cyan] or [bold cyan]Index[/bold cyan] (or press Enter to exit)"
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
    info_table = Table(show_header=False, box=box.MINIMAL)
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

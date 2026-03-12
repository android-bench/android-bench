# Task Visualizer & Explorer

The Task Visualizer is a rich, terminal-based tool designed to help you navigate, filter, and inspect the Android Bench dataset. It provides an intuitive way to discover tasks that match your benchmarking needs or model capabilities.

## Getting Started

Before using the explorer, you must generate the task summary index:

```bash
python utils/explorer/generate_task_summary.py
```

Then, launch the interactive explorer:

```bash
./android-bench.sh dataset
```

## Interactive Explore Wizard

Running `dataset` without any subcommands launches the **Explore Wizard**. This guided flow allows you to:
- **Browse All**: View a paginated list of all tasks in the dataset.
- **Filter by Category**: Select a Key Android Developer Area (KADA) to see relevant tasks (e.g., `Compose`, `Hilt`, `Networking`).
- **Filter by Repository**: Drill down into tasks from specific open-source projects.

### Navigation
- **Single-Key Shortcuts**: Use the letters in brackets (e.g., `[a]`, `[c]`) to quickly navigate menus.
- **Index Selection**: In task lists, you can enter the numeric **Index** (on the left) to jump directly into a task's detailed inspection view, avoiding the need to type full Task IDs.
- **Pagination**: Large lists are paginated. Use `[n]` for next, `[p]` for previous, and `[x]` to exit the list.

## CLI Reference

You can also bypass the wizard and run specific commands directly from your shell.

### `browse`
Displays tasks in an enriched table view with advanced filtering.

```bash
# Filter by complexity and show expanded metadata
./android-bench.sh dataset browse --estimate high --expanded

# Search for specific keywords in Task IDs or summaries
./android-bench.sh dataset browse --search "Deep link"
```

**Key Options:**
- `--category`: Filter by a specific KADA area.
- `--repo`: Filter by repository name.
- `--estimate`: Filter by complexity bucket (`low`, `medium`, `high`).
- `--sort`: Sort by `id`, `repo`, or `category`.
- `--expanded`, `-e`: Show all metadata columns, including task type and numerical estimates.

### `inspect`
Provides a deep dive into a specific task's requirements and environment.

```bash
./android-bench.sh dataset inspect <task_id>
```

**Features:**
- **Markdown Rendering**: Problem statements and descriptions are rendered with proper formatting for better readability.
- **Abridged Regressions**: By default, only the first 5 regression tests are shown to keep the output clean.
- **Verbose Mode (`-v`)**: Reveals the full list of regression tests and the internal execution commands (build and test scripts) defined in the `task.yaml`.

## Key Android Developer Areas (KADA)

The explorer uses color-coded themes to highlight different Android domains:
- **Cyan**: UI/UX (Compose, Material, Navigation)
- **Magenta**: Architecture & Core (Hilt, Room, ViewModels, Coroutines)
- **Green**: OS & System (Bluetooth, Permissions, Storage, Networking)
- **Yellow**: Build & Configuration (Gradle, KMP, Dependency Upgrades)
- **Red**: Specialized (Security, Privacy, Performance)

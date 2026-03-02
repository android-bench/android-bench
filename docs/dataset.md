# Dataset Structure

The `dataset` directory contains the core problems evaluated in Android Bench. Each task represents a real-world Android development issue sourced from open-source repositories or created by domain experts.

## Task Structure

Tasks are organized into a directory-based structure. Each task has its own dedicated directory under `dataset/tasks/`, containing a `task.yaml` file that defines the task's metadata, environment, and evaluation criteria.

```
dataset/tasks/
└── <task_id>/
    ├── task.yaml
    └── [optional assets, e.g., screenshots]
```

## Task Configuration (`task.yaml`)

The `task.yaml` file is the source of truth for a benchmark task. It uses the following schema:

### General Metadata
- `instance_id` (string): A unique identifier for the task (e.g., `Owner__repo-pr_123`).
- `task_type` (string): The category of the task (e.g., `bugfix`, `feature`).
- `time_estimate` (string): An estimate of how long a human developer might take to solve the task (e.g., `<1h`, `2-4h`).
- `category_ids` (list): Key Android Developer Areas (KADA) associated with the task (e.g., `compose`, `hilt`, `networking`).
- `description` (string): A natural language description of the problem, often sourced from a GitHub issue or PR description.

### Repository Information
- `repository` (object):
    - `name` (string): Name of the Android project.
    - `owner` (string): GitHub owner/organization.
    - `url` (string): URL to the source repository.

### Environment & Commits
- `before_commit` (object): The state of the repository *before* the fix/feature.
    - `sha` (string): The base commit hash.
    - `java_version` (int): Required JDK version (e.g., `11`, `17`).
    - `target_sdk` (int): The target Android SDK version.
- `after_commit` (object): The state of the repository *after* the canonical solution.
    - `sha` (string): The commit hash of the reference solution.

### Execution Commands
- `commands` (object): Lists of shell commands to run within the Docker container.
    - `build` (list): Commands to compile the project (e.g., `./gradlew assembleDebug`).
    - `unit_test` (list): Commands to run relevant unit tests.
    - `android_test` (list): Commands to run on-device instrumentation tests.

### Acceptance Criteria
- `acceptance_criteria` (object):
    - `fail_to_pass` (list): Specific test cases that **must fail** on the `before_commit` and **must pass** after the agent's patch is applied.
    - `pass_to_pass` (list): Regression tests that **must pass** both before and after the patch is applied.

---

## Task Acquisition Pipeline

The Android Bench dataset is constructed through a stringent review pipeline to ensure high-quality, reproducible, and representative tasks.

### 1. Sourcing
Tasks are sourced from two primary channels:
- **GitHub Pull Requests**: The majority of tasks are collected from real-world PRs in popular Android repositories (at least 500 stars) from the last 3 years.
- **Expert-Authored Tasks**: A subset of tasks is manually written by Android domain experts to target critical areas not sufficiently represented in public data.

### 2. Technical Vetting
Every candidate task undergoes a multi-stage validation process:
- **Reproducibility**: We verify that the environment can be deterministically built using Docker and that the base commit is stable.
- **Test Suitability**: A team of vendors validates that the task has reasonable test coverage and that the "Fail to Pass" tests accurately isolate the described issue.
- **Engineering Review**: Proficient Android engineers review the task descriptions for clarity and ensure that the tests are correctly specified and non-flaky.

### 3. Sanitization
Tasks are checked for PII and internal artifacts. Additionally, YAML files include **canary strings** to prevent benchmark data from contaminating the training corpora of future Large Language Models.

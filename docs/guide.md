# Android Bench User Guide

This guide provides comprehensive instructions for setting up Android Bench, understanding its architecture, and using the Command-Line Interface (CLI).

## Table of Contents
1. [Development Setup](#development-setup)
2. [Harness Architecture](#harness-architecture)
3. [CLI Reference](#cli-reference)
4. [Dataset & Tasks](#dataset--tasks)

---

## 1. Development Setup

This section explains how to set up Android Bench locally. The project uses a containerized architecture to ensure a consistent environment across different host machines.

### Prerequisites

- x86_64 CPU with KVM support
- Docker

### Creating the Environment

To set up the CLI Docker environment and configure the Oracle Agent, run the provided setup script:

```bash
# Build the CLI Docker image and run setup
./android-bench.sh setup_env
```

This script will automatically detect your architecture and build the necessary Docker images to run the Android Bench pipeline.

### Pre-commit Hooks

This project enforces code formatting via `black`. If you plan to contribute, initialize the pre-commit hooks in your local Git repository:

```bash
pip install pre-commit black
pre-commit install
```
Once configured, `black` will automatically evaluate and format your Python files before every commit.

---

## 2. Harness Architecture

The core execution engine of Android Bench orchestrates the entire lifecycle of a benchmark run, from prompting the Language Model to verifying the final output. It is split into two primary components: **Inference** and **Evaluation**.

### Inference (Agent)

The Inference stage is responsible for interacting with the targeted Large Language Model (LLM).

**Typical flow:**
1. Load a benchmark task from the dataset.
2. Read the issue description and the initial state of the Android project codebase.
3. Construct a prompt encapsulating the target problem and the surrounding context.
4. Send the prompt to the selected LLM and receive the proposed code changes (the patch).
5. Save the generated patch for the evaluation stage.

### Evaluation (Verifier)

The Evaluation stage measures the correctness of the LLM's generated patch. Because Android execution environments can be complex, it runs within a controlled Dockerized sandbox.

**Typical flow:**
1. Load the generated patch produced during the Inference stage.
2. Apply the patch to the exact version of the project specified by the benchmark task.
3. Execute the project's test suite inside the sandboxed environment.
4. Compare the test results against the expected issue resolution to determine a final score (e.g., pass/fail).
5. Output the results for analysis.

---

## 3. CLI Reference

Android Bench provides CLI tools to execute benchmarks locally. After installing the project in editable mode, these scripts are automatically available in your virtual environment's PATH.

### `benchmark`
Runs the entire pipeline end-to-end. It sequentially executes the Agent (Inference) and then immediately verifies the resulting patch.

> **Warning**: Running the entire benchmark suite locally takes a significant amount of time, especially if you have not previously built the required Docker images. We are actively working on exposing a public repository of pre-built images to act as a reference and speed up this process.

```bash
# Run 5 consecutive benchmark runs using Gemini 2.5 Flash
./android-bench.sh benchmark --model gemini/gemini-2.5-flash --num_runs 5
```
**Resuming a Run:** If a run is interrupted, you can resume it by specifying the `--run-name` and using the `--skip-existing` flag.

### `run_task`
Runs the entire pipeline (inference and evaluation) for a **single** task. This is the recommended tool for debugging or testing changes to a specific task.

> **Note**: Even when running a single task, `run_task` will execute the entire verifier pipeline to ensure comprehensive evaluation of that specific task.

```bash
# Run a single task
./android-bench.sh run_task --model gemini/gemini-2.5-flash --task <TASK_ID>
```
**Key Arguments:**
- `--model`: (Required) The model to use for the agent.
- `-i`, `--task`: (Required) The task ID to run.
- `--local-images` / `--no-local-images`: Whether to build and use local Docker images (default: True).

### `build_images`
Constructs the necessary Docker environments for the benchmark tasks locally.

> **When is this necessary?** Building images manually is typically only required if you intend to run the verifier independently of the main `benchmark` or `run_task` commands, or if you are running the verifier in test mode (e.g., with the oracle agent). The `run_task` command handles this automatically.

```bash
./android-bench.sh build_images --build
```

> **macOS / ARM64 Warning:** The Android SDK emulator package is only available for `linux/amd64`. If you are building on an Apple Silicon (M-series) Mac, you **must** supply the `--arch linux/amd64` flag: `./android-bench.sh build_images --build --arch linux/amd64`. Note that running the emulator inside Docker on macOS is severely limited due to the lack of KVM support. See the Troubleshooting Guide for workarounds.

### `agent`
Executes only the Inference stage. It prompts the model to generate patches for a set of tasks but does not attempt to evaluate them.
```bash
./android-bench.sh agent -i <TASK_ID> --model openai/gpt-4o
```

### `verifier`
Executes only the Evaluation stage. It takes the patches previously generated by an agent and scores them.

```bash
./android-bench.sh verifier --run-name <your_run_name>
```

### `oracle-agent`
Sets up the environment with canonical patches (oracle solutions) for the benchmark tasks.

> **When is this necessary?** You only need to run this setup if you want to run the verifier using the known "golden" patches (the canonical solutions) to validate that a specific task's test suite and environment are functioning correctly.

```bash
./android-bench.sh setup_oracle_agent
./android-bench.sh verifier --test-run --run-name oracle-test
```

### Visualization & Reporting Tools

- **`generate-html`**: Generates self-contained HTML reports for each task in a benchmark run.
  ```bash
  ./android-bench.sh generate-html --input-dir out
  ```
- **`summarize`**: Generates a CSV summary of pass rates and other metrics across multiple model runs.
  ```bash
  ./android-bench.sh summarize out
  ```

---

## 4. Dataset & Tasks

The `dataset` directory contains the core problems evaluated in Android Bench. These are based on real-world Android issues.

### What makes a task valid?
A valid task requires:
1. **Clear Problem Statement**: Sourced from a GitHub issue or explicitly written, defining the required change.
2. **Reproducible Environment**: A stable base commit and a defined Docker execution environment.
3. **Robust Test Suite**: The core of the benchmark. A task must have tests that fail on the base commit (the issue is present) and pass when the canonical solution (oracle patch) is applied. The tests must be reliable and free from flakiness (e.g., not strictly dependent on exact UI rendering timing without synchronization).

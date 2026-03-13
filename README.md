# Android Bench

Android Bench is a framework for benchmarking Large Language Models (LLMs) on Android development tasks. It evaluates an AI model's ability to understand mobile codebases, generate accurate patches, and solve Android-specific engineering problems.

The repository provides the tooling to evaluate a model's ability to act as an Android developer. It takes an issue description, generates code modifications, and verifies those changes against a test suite in a standardized environment using a curated dataset.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Setup (Quickstart)](#setup)
- [Usage](#usage)
- [Detailed Documentation](#detailed-documentation)
- [Contributing](#contributing)
- [License](#license)

## Prerequisites
- x86_64 with [KVM-capabilities](https://en.wikipedia.org/wiki/Kernel-based_Virtual_Machine)
- Python 3.14+
- [uv](https://docs.astral.sh/uv/) (Fast Python package installer)
- Docker
- API keys for the models to benchmark

> Note that using local images (v1 limitation) is **disk and memory intensive**, with base, repo, and task imags sometimes requiring +40GB of free space *each*.

## Setup
```bash
git clone https://github.com/android-bench/android-bench.git
cd android-bench

# Create and activate the virtual environment
uv venv
source .venv/bin/activate

# Run the setup script
uv run setup_env
```

The `setup_env` takes care of the following:
1.  Installs all dependencies.
2.  Configures the oracle agent with golden patches for testing.
3.  Generates the `summary.json` for the dataset explorer.
4.  Detects your host architecture (x86/AMD64 or ARM64) and builds the Docker images or exits gracefully if incompatible.

### API Configuration
You must configure your API keys to use the supported models. Our inference agent is based on [mini-swe-agent](https://www.mini-swe-agent.com) which by default supports all models using [LiteLLM](https://github.com/BerriAI/litellm).

Before you use a model, export its corresponding API key as an environment variable:

```bash
export GEMINI_API_KEY="your-api-key"
export OPENAI_API_KEY="your-api-key"
```

You can also run the setup script `mini-extra config setup`. 
If you run into authentication issues, we recommend you check their [troubleshooting guide](https://mini-swe-agent.com/latest/models/troubleshooting/).

> Always include the provider in the model name, e.g., `gemini/gemini-...`

## Usage

### Workflow Overview
The benchmarking process has two stages:
1.  **Inference (Agent)**: The agent reads the issue description and generates a code patch.
2.  **Evaluation (Verifier)**: The verifier applies the patch and runs tests to score the solution.

### Discovering Tasks
To browse available tasks or understand the dataset structure:

```bash
# Launch the interactive explorer
dataset
```
This launches an interactive wizard. You can also run specific subcommands directly:
- `dataset browse --category compose`
- `dataset inspect <task_id>`

For filtering and usage, see the [Task Visualizer Guide](docs/task_explorer.md).

### Running a Single Task
> **Note on Docker Images**: Tasks run in isolated Docker containers. The very first time you run a task, the framework will build task-specific Docker images locally based on the dataset configurations.
>
> **This initial cold-start can take 5-10+ minutes.** Subsequent runs should be significantly faster.
> 
> **macOS / ARM64 Users:** The Android SDK does not provide an ARM64 Linux emulator package. Executing the benchmark locally on macOS Docker Desktop is severely limited due to the lack of nested virtualization (KVM). See the [Troubleshooting guide](docs/troubleshooting.md) for workarounds.

To run the complete pipeline (inference and evaluation) for a specific task ID:

```bash
run_task --model gemini/gemini-2.5-flash --task android_snippets_1
```

### Testing the Verifier (Oracle Agent)
The Oracle Agent applies the known canonical solutions to verify that the evaluation infrastructure works as expected.

```bash
# Setup the oracle agent (setup_env handles this)
# Run the verifier in test mode
verifier --test-run --run-name oracle-agent
```

### Run Local Tests
This project uses `pytest` for unit and integration testing. Run the CI test suite with:
```bash
pytest --log-cli-level=INFO --verbose
```
> You must have a Gemini API key configured for the test suite to pass.

## Visualize Results
To visualize the results, you can generate an HTML summary which can help you understand what were the scores, see the patches, trajectories, and variations between multiple runs where available. 

Generate the HTML summary with the following command:

```bash
results --input-dir out
```
> Remember to change the input-dir to the directory of your choice if you decide to store the results elsewhere.

### Reviewing the results used in the current Leaderboard
If you'd like to deep-dive on the runs used for the current leaderboard, you must access the official release assets.

We host the evaluation results, including trajectories and generated patches used to compute the leaderboard scores, via GitHub Releases on this repository. Due to GitHub's individual asset limits, we compress and split files exceeding 2GB into chunks.

> [!IMPORTANT]
> **To access and analyze the leaderboard results:**
> Run the built-in downloader to automatically fetch and extract the results for the models you're interested in:
>
> ```bash
> # Downloads and extracts gemini-3.1-pro-preview to results/v1_20260305/gemini-3.1-pro-preview
> download_results --models gemini-3.1-pro-preview --dir results/v1_20260305
> ```

Once decompressed, you can generate the HTML summary for any of the leaderboard models using the `results` script:

```bash
results --input-dir results/v1_20260305/gemini-3.1-pro-preview
```

## Detailed Documentation
For more comprehensive guides and architectural details, refer to the following resources:
- [User Guide](docs/guide.md): Comprehensive instructions on CLI commands, framework setup, benchmark dataset, and harness architecture.
- [Viewing and Interpreting Results](docs/viewing_results.md): Guide to locating output files, understanding the `scores.json` schema, and deciphering diagnostic status codes.
- [Troubleshooting Guide](docs/troubleshooting.md): Solutions for common issues like Docker build failures, compilation errors, and missing patch generations.
- [Technical Report](docs/tech_report.md): A deep-dive into the methodology, dataset construction, and baseline results.

## Contributing
We are currently exploring ways to engage with the open-source community. As we prepare the repository for broader contributions, we highly encourage you to provide feedback via the issue tracker. Please see our [Contributing Guidelines](CONTRIBUTING.md) for more details.

## License
Android Bench is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) file for details.

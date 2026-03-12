# Troubleshooting Guide

This guide helps resolve the most common framework and setup issues you might encounter while running Android Bench.

**Important Note on Expected Failures:** 
Android Bench is a *benchmark* designed to test the limits of AI agents. If a task returns `AGENT_FAILED_BUILD` or `AGENT_FAILED_TEST`, this is typically **not a framework error that needs troubleshooting**. It is the expected result indicating the model failed to successfully solve the task. See the [Technical Report](tech_report.md) for details on benchmark evaluation.

---

## 1. LiteLLM Authentication Errors

**Symptoms:**
- The agent crashes immediately with an `AuthenticationError`.

**Root Cause:**
LiteLLM cannot find the environment variable for your specified model provider.

**Resolution:**
Ensure you have exported the correct key exactly as LiteLLM expects it.
- For Gemini: `export GEMINI_API_KEY="your-key"`
- For OpenAI: `export OPENAI_API_KEY="your-key"`
- For Anthropic: `export ANTHROPIC_API_KEY="your-key"`

## 2. Docker Build Failures (Exit Code 128)

**Symptoms:**
- When running `run_task` or `build_images`, the process crashes early with an error like: `The command '/bin/sh -c git clone ...' returned a non-zero code: 128`.

**Root Cause:**
Exit code 128 from git usually means the remote repository does not exist, you lack permissions, or (most commonly) the specific commit hash or tag specified in the `task.yaml` has been force-pushed over or deleted from the upstream repository.

**Resolution:**
1. Check the `task.yaml` file for the specific task you are trying to run.
2. Identify the `before_commit.sha` or `after_commit.sha`.
3. Try to view that commit manually on GitHub (e.g., `https://github.com/<owner>/<repo>/commit/<sha>`).
4. If it returns a 404, the upstream repository has been altered. You should skip this task or mark it as deprecated in the dataset.

## 3. Agent Fails to Generate a Usable Patch (`NO_PATCH_GENERATED`)

**Symptoms:**
- The orchestrator log (`out/<run_name>/logs/run.log`) reports: `Task with key not found`.
- The final `scores.json` shows a status of `NO_PATCH_GENERATED`.

**Root Cause:**
The LLM successfully finished its conversation but failed to produce a valid diff format. The model may have output natural language explaining the fix but omitted the actual code patch, or wrapped it improperly. While technically an agent failure, this is often a formatting issue rather than a logic issue.

**Debugging Steps:**
1. Open the trajectory file located at `out/<run_name>/trajectories/<task_id>.json`.
2. Scroll to the last assistant message and inspect the generated format.
3. If building a custom agent, you may need to adjust the system prompt or parsing logic to be stricter about the required patch output format.

## 4. Investigating Agent Logic Failures

If you are developing a new agent or debugging a model's behavior and want to understand *why* it received an `AGENT_FAILED_BUILD` or `AGENT_FAILED_TEST`:

**Compilation / Build Failures (`AGENT_FAILED_BUILD`):**
- Navigate to the verifier outputs directory: `out/<run_name>/verifier/<task_id>/outputs/`.
- Open `verify.log` and search for standard Android compilation errors (e.g., `error: cannot find symbol`).
- This usually indicates the agent hallucinated an API or forgot an import.

**Test Failures (`AGENT_FAILED_TEST`):**
- Navigate to the verifier outputs directory: `out/<run_name>/verifier/<task_id>/outputs/`.
- Open `verify.log` and scroll to the bottom to see the Gradle test report output to find which tests the agent failed.

---

## 5. macOS / Apple Silicon Build & Virtualization Issues

**Symptoms:**
- `build_images --build` fails at `sdkmanager "emulator"` on an M-series Mac.
- The emulator boot process hangs indefinitely or crashes with `INFRA_FAILURE_EMULATOR_TIMEOUT`.

**Root Cause & Limitations:**
1. **Build Failure:** The Android SDK does not provide an `emulator` package for Linux `arm64`. Building the Docker image natively on Apple Silicon defaults to an `arm64` container, which causes `sdkmanager` to fail.
2. **Execution Failure (No KVM):** Docker Desktop for Mac does not support nested virtualization. The macOS host cannot expose KVM (`/dev/kvm`) to the Docker container. Emulators running inside Docker on a Mac will fall back to extremely slow software emulation or fail to boot entirely.

**Resolution:**
1. **To build the images:** You must force Docker to build an AMD64 image by passing the `--arch` flag: `./android-bench.sh build_images --build --arch linux/amd64`. Docker Desktop will use Rosetta/QEMU to build the image successfully.
2. **To execute the benchmark:**
   - **Recommended:** Run the benchmark on a dedicated Linux machine with KVM enabled.
   - **Alternative:** Run a Linux VM (e.g., via Parallels, VMware) with nested virtualization enabled, install Docker inside that VM, and execute the benchmark from there.
   - **Workaround:** Start the emulator on your macOS host directly (via Android Studio), and configure your Docker container to connect to it via `adb connect host.docker.internal:5555`.

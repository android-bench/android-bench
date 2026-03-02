# Viewing and Interpreting Results

When you run a benchmark or a single task, Android Bench outputs detailed logs and evaluation scores to the `out/` directory. This guide will help you locate those files and interpret their contents.

## Locating Results

Every run creates a new timestamped directory inside `out/`. The naming convention follows the pattern: `<run_name>_<date>-<time>`.

For example:
`out/gemini-gemini-2.5-flash_2024-05-20-10-30-00/`

Inside this run directory, you will find:
- `config.properties`: A record of the configuration used for the run.
- `logs/run.log`: The main execution log for the orchestrator.
- `scores.json`: The aggregated evaluation results (created after the verifier finishes).
- `trajectories/`: Contains JSON files detailing the exact conversational turn-by-turn trajectory the agent took for each task.
- `verifier/`: Contains the evaluation logs and test results for each evaluated task.

## Interpreting `scores.json`

The most important file is `scores.json`. It provides an aggregated view of how the model performed across all attempted tasks. 

A typical `scores.json` looks like this:

```json
{
  "AlphaWallet__alpha-wallet-android-pr_3329": {
    "score": 1.0,
    "cost": 0.015,
    "used_tokens": 15000,
    "status": "PASSED"
  },
  "android_snippets_1": {
    "score": 0.0,
    "cost": 0.005,
    "used_tokens": 5000,
    "status": "AGENT_FAILED_TEST"
  }
}
```

### Schema Breakdown

*   **`score`**: A floating-point number representing the final evaluation score (pass@1). `1.0` means the task was solved successfully based on the defined acceptance criteria (usually passing specific tests). `0.0` means failure.
*   **`cost`**: The estimated monetary cost (in USD) incurred by the API calls to the LLM provider for this specific task.
*   **`used_tokens`**: The total number of tokens (prompt + completion) consumed during the inference stage for this task.
*   **`status`**: A high-level diagnostic string indicating the final state of the task evaluation.

## Diagnostic Status Codes

Understanding the `status` field is critical for interpreting the benchmark results. Remember that failures are the expected outcome for many tasks, depending on the capabilities of the agent being tested.

| Status Code | Meaning |
| :--- | :--- |
| **`PASSED`** | The agent's generated patch was successfully applied, the code compiled, and all required tests passed. The task was solved successfully. |
| **`AGENT_FAILED_BUILD`** | **(Benchmark Failure)** The agent generated a patch, but applying it caused the Android project to fail during the compilation/build phase. The agent hallucinated or provided invalid syntax. |
| **`AGENT_FAILED_TEST`** | **(Benchmark Failure)** The agent's patch compiled successfully, but it failed the test cases specified in the task's acceptance criteria. The agent's logic is incorrect or incomplete. |
| **`EVAL_ERROR`** | **(Framework Error)** An error occurred within the Android Bench framework itself while trying to evaluate the task (e.g., Docker container crashed). |
| **`NO_PATCH_GENERATED`** | **(Benchmark Failure)** The agent finished its inference run but failed to produce a correctly formatted `diff --git` patch. |
| **`SKIPPED`** | The task was skipped (e.g., because you used the `--skip-existing` flag and the result already existed). |

For more detailed help on debugging framework issues or investigating specific agent failures, please consult the [Troubleshooting Guide](troubleshooting.md).

# Task Validator

This script validates a SWE-bench style task for an Android repository to ensure
the environment works as expected.

## Validation Steps

The script performs the following steps to ensure the task is valid:

1.  **Checks for a clean git repository:** Ensures that there are no uncommitted
    changes before starting the validation process.
2.  **Checks out the base commit:** Switches to the specified base commit to
    create a clean starting point.
3.  **Checks out test files from the task commit:** Brings in the test files
    from the task commit to the base commit's working directory.
4.  **Runs tests on the base commit:** Executes the specified test commands on
    the base commit with the new test files. It expects the tests to fail, but
    it checks to ensure there are no compilation errors.
5.  **Checks out the task commit:** Switches to the task commit, which should
    contain the solution to the task.
6.  **Runs tests on the task commit:** Executes the same test commands again,
    this time expecting them to pass.
7.  **Cleans up the repository:** After the validation is complete, the script
    resets any changes and checks out the initial commit, leaving the repository
    in a clean state.

## Usage

To run the script, provide the root directory of the git repository and the test
commands to run. You can also provide the base and task commit hashes, as well
as a list of test files.

### Basic Usage

```bash
python task_validator/validate_task.py --root_dir path/to/your/repo --test_commands "./gradlew test" "./gradlew connectedDebugTest"
```

### With Optional Arguments

```bash
python task_validator/validate_task.py \
    --root_dir path/to/your/repo \
    --base_commit <base_commit_hash> \
    --task_commit <task_commit_hash> \
    --test_commands "./gradlew testDebug" "./gradlew connectedAndroidTest" \
    --test_files "app/src/test/java/com/example/MyTest.java" \
    --log_output
```

### Arguments

-   `--root_dir`: **(Required)** The root directory of the git repository.
-   `--test_commands`: **(Required)** A list of gradle commands to run as tests.
-   `--base_commit`: The base commit hash. If not provided, it will default to
    `HEAD~1`.
-   `--task_commit`: The task commit hash. If not provided, it will default to
    `HEAD`.
-   `--test_files`: A list of test files. If not provided, the script will
    search for test files in the merge commit.
-   `--log_output`: If set, the script will log the output of the commands being
    run.

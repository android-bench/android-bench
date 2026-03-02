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
"""
This script validates a SWE-bench style task for an Android repository.

It performs the following steps:
1.  Checks if the git repository is clean.
2.  Checks out a specified base commit.
3.  Checks out test files from a specified task commit.
4.  Runs test commands on the base commit with the new test files, expecting test
    failures but not compilation failures.
5.  Checks out the task commit.
6.  Runs the same test commands, expecting them to pass.
7.  Cleans up the repository by resetting any changes and checking out the initial
    commit.

Example usage: python validate_task.py --root_dir nowinandroid --test_commands "./gradlew testDemoDebug"
"""

import argparse
import subprocess
import os
import sys
import re
import logging


# ANSI escape codes for colors
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"


# Custom formatter
class ColoredFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        if record.levelname == "ERROR":
            message = message.replace("ERROR", f"{Colors.RED}ERROR{Colors.RESET}")
        elif "Validation successful!" in record.getMessage():
            message = message.replace(
                "Validation successful!",
                f"{Colors.GREEN}Validation successful!{Colors.RESET}",
            )

        return message.replace(
            "Validation Script", f"{Colors.GREEN}Validation Script{Colors.RESET}"
        )


# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create console handler and set formatter
ch = logging.StreamHandler()
ch.setFormatter(
    ColoredFormatter("%(asctime)s - Validation Script - %(levelname)s - %(message)s")
)
logger.addHandler(ch)


def run_command(command, cwd, check=True, log_output=False):
    """Runs a command in a subprocess and streams its output."""
    logging.info(f"Running command: {' '.join(command)}")
    process = subprocess.Popen(
        command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    stdout_lines = []
    stderr_lines = []

    # Stream output in real-time
    while True:
        output = process.stdout.readline()
        if output == "" and process.poll() is not None:
            break
        if output:
            if log_output:
                print(output.strip())
            stdout_lines.append(output)

    stderr_output = process.communicate()[1]
    if stderr_output:
        if log_output:
            print(stderr_output.strip())
        stderr_lines.extend(stderr_output.splitlines())

    result = subprocess.CompletedProcess(
        args=command,
        returncode=process.returncode,
        stdout="".join(stdout_lines),
        stderr="".join(stderr_lines),
    )

    if check and result.returncode != 0:
        logging.error(f"Error running command: {' '.join(command)}")
        sys.exit(1)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Validate a SWE-bench style task for an Android repository."
    )
    # The root directory of the git repository.
    parser.add_argument(
        "--root_dir", required=True, help="Root directory of the git repo."
    )
    # The base commit hash. If not provided, it will default to HEAD~1.
    parser.add_argument("--base_commit", help="Base commit hash.")
    # The task commit hash. If not provided, it will default to HEAD.
    parser.add_argument("--task_commit", help="Task commit hash.")
    # A list of gradle commands to run as tests.
    parser.add_argument(
        "--test_commands",
        nargs="+",
        required=True,
        help="List of gradle commands to run as tests.",
    )
    # A list of test files. If not provided, the script will search for test
    # files in the merge commit.
    parser.add_argument("--test_files", nargs="+", help="List of test files.")
    # If set, the script will log the output of the commands being run.
    parser.add_argument(
        "--log_output", action="store_true", help="Log output of commands being run."
    )
    args = parser.parse_args()

    root_dir = args.root_dir
    if args.task_commit:
        task_commit = args.task_commit
    else:
        logging.info("Task commit not provided, using HEAD.")
        task_commit_result = run_command(
            ["git", "rev-parse", "HEAD"], cwd=root_dir, log_output=args.log_output
        )
        task_commit = task_commit_result.stdout.strip()

    if args.base_commit:
        base_commit = args.base_commit
    else:
        logging.info("Base commit not provided, using HEAD~1.")
        base_commit_result = run_command(
            ["git", "rev-parse", "HEAD~1"], cwd=root_dir, log_output=args.log_output
        )
        base_commit = base_commit_result.stdout.strip()
    test_commands = args.test_commands

    if args.test_files:
        test_files = args.test_files
    else:
        logging.info(
            "No test files provided, searching for test files in the merge commit."
        )
        merge_commit_files_result = run_command(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", task_commit],
            cwd=root_dir,
            log_output=args.log_output,
        )
        all_files = merge_commit_files_result.stdout.strip().split("\n")
        test_files = [f for f in all_files if "test" in f.lower()]
        if not test_files:
            logging.error("No test files found in the merge commit.")
            sys.exit(1)
        logging.info(f"Found test files: {test_files}")

    initial_commit_result = run_command(
        ["git", "rev-parse", "HEAD"], cwd=root_dir, log_output=args.log_output
    )
    initial_commit = initial_commit_result.stdout.strip()
    logging.info(f"Initial commit is {initial_commit}")

    try:
        # 1. Check if git status is clean
        logging.info("Checking git status...")
        git_status = run_command(
            ["git", "status", "--porcelain"], cwd=root_dir, log_output=args.log_output
        )
        if git_status.stdout:
            logging.error(
                "Git repository is not clean. Please commit or stash your changes."
            )
            sys.exit(1)
        logging.info("Git status is clean.")

        # 2. Check out the base commit
        logging.info(f"Checking out base commit: {base_commit}")
        run_command(
            ["git", "checkout", base_commit], cwd=root_dir, log_output=args.log_output
        )

        # 3. Checkout test files from the task commit
        logging.info(f"Checking out test files from task commit: {task_commit}")
        for test_file in test_files:
            run_command(
                ["git", "checkout", task_commit, "--", test_file],
                cwd=root_dir,
                log_output=args.log_output,
            )

        # 4. Run test commands, expecting failures but not compilation failures.
        logging.info(
            "Running tests on base commit with test files... expecting test failures."
        )
        any_test_failed = False
        for test_command in test_commands:
            result = run_command(
                test_command.split(),
                cwd=root_dir,
                check=False,
                log_output=args.log_output,
            )

            if re.search(
                r"compile.*Test.*FAILED|Compilation error", result.stdout, re.IGNORECASE
            ) or re.search(
                r"compile.*Test.*FAILED|Compilation error", result.stderr, re.IGNORECASE
            ):
                logging.error(
                    f"Test command '{test_command}' resulted in a compilation failure when run on base commit. This is invalid."
                )
                sys.exit(1)

            if result.returncode != 0:
                logging.info(f"Test command '{test_command}' failed as expected.")
                any_test_failed = True

        if not any_test_failed:
            logging.error(
                "No tests failed on the base commit, but failures were expected."
            )
            sys.exit(1)

        # 5. Ask for user confirmation before proceeding
        logging.info(
            "Tests on base commit completed. The next step will check out the task commit and run tests again, expecting them to pass."
        )
        user_input = input("Do you want to continue? (y/n): ").lower()
        if user_input != "y":
            logging.info("Aborting.")
            sys.exit(0)

        # 6. Check out the task commit
        logging.info(f"Checking out task commit: {task_commit}")
        run_command(
            ["git", "checkout", task_commit], cwd=root_dir, log_output=args.log_output
        )

        # 7. Run test commands again, expecting passes
        logging.info("Running tests on task commit... expecting passes.")
        for test_command in test_commands:
            run_command(
                test_command.split(),
                cwd=root_dir,
                check=True,
                log_output=args.log_output,
            )

        logging.info("All tests passed on the task commit.")
        logging.info("Validation successful!")
    finally:
        # 8. Cleanup
        logging.info(
            "The script has finished. The next step will clean up the repository by resetting any changes and checking out the initial commit."
        )
        user_input = input("Do you want to proceed with cleanup? (y/n): ").lower()
        if user_input == "y":
            logging.info("Cleaning up...")
            run_command(
                ["git", "reset", "--hard"], cwd=root_dir, log_output=args.log_output
            )
            run_command(
                ["git", "checkout", initial_commit],
                cwd=root_dir,
                log_output=args.log_output,
            )
            logging.info("Cleanup complete.")
        else:
            logging.info("Skipping cleanup.")


if __name__ == "__main__":
    main()

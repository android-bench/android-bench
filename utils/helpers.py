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
import json
import tempfile
import subprocess
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from utils import shell
from common.models import eval_data_classes
import logging
from typing import Any, List
import os
import time
import re
from common.constants import CONFIG_PROPERTIES_FILE
import threading
import signal

TEMP_DIR = "/workspace/temp"


def get_android_home() -> str:
    """Returns the ANDROID_HOME environment variable or raises an error."""
    android_home = os.environ.get("ANDROID_HOME")
    if not android_home:
        raise EnvironmentError(
            "ANDROID_HOME environment variable not set. Please set it to your"
            " Android SDK path."
        )
    return android_home


def get_adb_path() -> str:
    """Returns the path to the adb executable."""
    return os.path.join(get_android_home(), "platform-tools", "adb")


def print_and_log(log_file: str, message: str) -> None:
    """Print and log the message."""

    logging.info(message)
    with open(log_file, "a") as log:
        log.write(f"{message}\n\n")


def git_clone(repo_full_name: str, cwd: str) -> None:
    """Clones a git repository."""
    repo_url = f"https://github.com/{repo_full_name}.git"
    # Git clone into cwd directly
    clone_command = f"git clone {repo_url} ."
    shell.run_command(clone_command, cwd=cwd)


def git_checkout(commit: str, cwd: str) -> None:
    """Checks out a specific commit."""
    # Git checkout sha
    checkout_command = f"git checkout {commit} -f"
    shell.run_command(checkout_command, cwd=cwd)
    shell.run_command("git submodule update --init --recursive", cwd=cwd)


def reset_to_commit(commit_sha: str, cwd: str) -> None:
    """Resets a git repository to a specific commit."""

    # Git checkout sha
    checkout_command = f"git reset --hard {commit_sha} --recurse-submodules"
    result = shell.run_command(checkout_command, cwd=cwd)
    logging.info(f"exit_code: {result.exit_code}")
    logging.info(f"stdout: {result.stdout}")
    logging.info(f"stderr: {result.stderr}")
    if result.exit_code != 0:
        logging.error(f"Error while resetting to a commit: {result.stderr}")
        return False
    return True


def reset_to_changeid(change_id: str, cwd: str) -> None:
    """Resets a git repository to a specific commit."""

    # Git checkout sha
    checkout_command = f"git reset --hard change-{change_id}"
    result = shell.run_command(checkout_command, cwd=cwd)
    logging.info(f"exit_code: {result.exit_code}")
    logging.info(f"stdout: {result.stdout}")
    logging.info(f"stderr: {result.stderr}")
    if result.exit_code != 0:
        logging.error(f"Error while resetting to a commit: {result.stderr}")
        return False
    return True


def _get_agp_version(project_dir: str) -> str | None:
    result = shell.run_command(
        "./gradlew buildEnvironment | grep com.android.tools.build:gradle:",
        cwd=project_dir,
    )
    lines = result.stdout.splitlines()
    if not lines:
        return None
    return lines[0].split("com.android.tools.build:gradle:")[-1]


def can_compile_successfully(
    build_commands: List[str],
    project_dir: str,
    timeout: int | None = None,
) -> bool:
    """Checks if a project can compile successfully."""
    for build_command in build_commands:
        build_command += " -Dorg.gradle.workers.max=8"
        result = shell.run_command(build_command, cwd=project_dir, timeout=timeout)
        logging.info(f"build stdout: {result.stdout}")
        logging.info(f"build stderr: {result.stderr}")
        if result.exit_code != 0:
            return False
    return True


def can_build_successfully(
    project_dir: str,
    log_file: str,
    pull_request_example: eval_data_classes.PullRequestExample,
    execution_config: eval_data_classes.RepoExecutionConfig,
    log_command_output: bool,
    timeout: int | None = None,
    mount_path: str = "/workspace",
) -> bool:
    """Checks if a project can build successfully."""
    if execution_config and execution_config.assemble_command:
        build_command = execution_config.assemble_command
    else:
        build_command = "./gradlew assembleDebug"
    pull_request_example.build_command = build_command

    init_script = f"{mount_path}/utils/get-target-sdk-init-script.gradle"

    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as tmp:
        build_command += f" -Pandroid.bench.targetSdk.path={tmp.name} --init-script={init_script} -Dorg.gradle.workers.max=8"
        result = shell.run_command(build_command, cwd=project_dir, timeout=timeout)
        logging.info(f"build stdout: {result.stdout}")
        logging.info(f"build stderr: {result.stderr}")

        _parse_android_test_target_sdk(tmp.name, execution_config)

    return result.exit_code == 0


def _parse_android_test_target_sdk(
    target_sdk_file_path: str, execution_config: eval_data_classes.RepoExecutionConfig
):

    max_target_sdk = 0
    with open(target_sdk_file_path, "r") as f:
        for line in f:
            if "uses Target SDK: " in line:
                max_target_sdk = max(
                    max_target_sdk, int(line.split("uses Target SDK: ")[-1].strip())
                )

    if max_target_sdk > 0:
        execution_config.fallback_target_sdk = str(max_target_sdk)


def _get_unit_test_command(execution_config: eval_data_classes.RepoExecutionConfig):
    if execution_config.unit_tests_command:
        return execution_config.unit_tests_command
    return r"./gradlew -q tasks --all | cut -d ' ' -f1 | grep -E '^\S*:test[^:]*DebugUnitTest' | xargs ./gradlew --no-configuration-cache --continue "


def _get_android_test_command(execution_config: eval_data_classes.RepoExecutionConfig):
    if execution_config.android_tests_command:
        return execution_config.android_tests_command
    return r"./gradlew -q tasks --all | cut -d ' ' -f1 | grep -E '^\S*:connected[^:]*DebugAndroidTest' | xargs ./gradlew --no-configuration-cache --continue "


def _parse_test_results(
    test_log_file_path: str,
    build_successful: bool = True,
    remove_task_names: bool = False,
):
    result = eval_data_classes.TestsExecutionResult(build_successful, set(), set())

    with open(test_log_file_path, "r") as f:
        for line in f:
            try:
                json_data = json.loads(line)
            except json.decoder.JSONDecodeError as e:
                logging.error(f"Failed to test results log: {e}, line: {line}")
                continue
            test = json_data["test"]
            if re.match(r"^\w+#Test", test) and remove_task_names:
                test = test.partition("#")[2]

            # Workaround composable lambda hash names in tests. b/465224060
            test = re.sub(
                r"ComposableLambdaImpl@[a-zA-Z0-9]+(?=\))", "ComposableLambdaImpl", test
            )

            if json_data["status"] == "SUCCESS":
                result.passed_tests.add(test)
            else:
                result.failed_tests.add(test)

    return result


def run_tests(
    project_dir: str,
    run_tests_command: str,
    timeout: int | None = None,
    workers: int = 8,
    mount_path: str = "/workspace",
    remove_task_names: bool = False,
) -> eval_data_classes.TestsExecutionResult:
    """Runs tests and returns the result."""

    TEMP_DIR = "/workspace/temp"
    os.makedirs(TEMP_DIR, exist_ok=True)
    _, path = tempfile.mkstemp(prefix="tmp-", suffix=".txt", dir=TEMP_DIR)

    init_script_path = f"{mount_path}/utils/test-dump-init-script.gradle"
    check_init_script_exists_command = f"ls {init_script_path}"
    init_exists_result = shell.run_command(check_init_script_exists_command)
    if init_exists_result.exit_code != 0:
        logging.error(
            f'mount_path contents: {shell.run_command(f"ls {mount_path}").stdout}'
        )
        logging.error(
            f'Filter contents: {shell.run_command("ls /workspace/utils").stdout}'
        )
        raise EnvironmentError("Gradle init script does not exist.")

    run_tests_command += f" -Pandroid.bench.test.log.file.path={path} --init-script={init_script_path} --rerun-tasks -Dorg.gradle.workers.max={workers}"
    result = shell.run_command(run_tests_command, cwd=project_dir, timeout=timeout)
    logging.info(f"exit_code: {result.exit_code}")
    logging.info(
        f'is "BUILD SUCCESSFUL" in result.stdout: {"BUILD SUCCESSFUL" in result.stdout}'
    )
    logging.info(f"Gradle test stdout:\n {result.stdout}")
    logging.info(f"Gradle test stderr:\n {result.stderr}")
    # currently we check build status by checking if "BUILD SUCCESSFUL" is in the output
    # context: legit/258310/1/common/eval_data_classes.py#67
    build_successful = result.exit_code == 0

    test_results = _parse_test_results(path, build_successful, remove_task_names)
    os.remove(path)

    # Also parse XML results from androidTest-results directories
    for results_dir in Path(project_dir).glob("**/androidTest-results/connected"):
        if results_dir.is_dir():
            logging.info(f"Parsing XML test results from {results_dir}")
            _parse_xml_results(
                results_dir,
                test_results.passed_tests,
                test_results.failed_tests,
                remove_task_names,
            )

    return test_results


def _parse_xml_results(
    results_dir: Path,
    passed_tests: set[str],
    failed_tests: set[str],
    remove_task_names: bool = False,
):
    """Parses JUnit XML test results and adds them to the test sets."""
    for xml_file in results_dir.glob("**/*.xml"):
        logging.info(f"Parsing test results: {xml_file}")
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            flavor = _get_flavor_from_test_xml(root) or ""

            task_name = f"connected{flavor.capitalize()}DebugAndroidTest"
            for testcase in root.iter("testcase"):
                class_name = testcase.get("classname")
                test_name = testcase.get("name")

                if remove_task_names:
                    test = f"Test {test_name}({class_name})"
                else:
                    test = f"{task_name}#Test {test_name}({class_name})"

                # Escape control characters
                test = re.sub(
                    r"[\x00-\x1F]",
                    lambda m: f"\\u{ord(m.group(0)):04x}",
                    test.replace('"', '\\\\"'),
                )

                if testcase.find("failure") is not None:
                    failed_tests.add(test)
                elif testcase.find("skipped") is None:
                    passed_tests.add(test)

        except ET.ParseError as e:
            logging.warning(f"Warning: Failed to parse XML file: {xml_file.name} ({e})")
        except Exception as e:
            logging.error(
                f"An unexpected error occurred while processing {xml_file.name}: {e}"
            )


def _get_flavor_from_test_xml(root) -> str | None:
    """Parses flavor from test xml."""
    properties = root.find("properties")
    if properties is None:
        return None
    for prop in properties.findall("property"):
        if prop.get("name") == "flavor":
            return prop.get("value")
    return None


def can_run_unit_tests_successfully(
    project_dir: str,
    pull_request_example: eval_data_classes.PullRequestExample,
    execution_config: eval_data_classes.RepoExecutionConfig,
    timeout: int | None = None,
) -> eval_data_classes.TestsExecutionResult:
    """Extracts the unit test command and runs it."""
    run_unit_tests_command = _get_unit_test_command(execution_config)
    pull_request_example.unit_test_command = run_unit_tests_command
    return run_tests(project_dir, run_unit_tests_command, timeout)


def can_run_android_tests_successfully(
    project_dir: str,
    pull_request_example: eval_data_classes.PullRequestExample,
    execution_config: eval_data_classes.RepoExecutionConfig,
    timeout: int | None = None,
) -> eval_data_classes.TestsExecutionResult:
    """Extracts the Android test command and runs it."""
    run_android_tests_command = _get_android_test_command(execution_config)
    pull_request_example.android_test_commands = [run_android_tests_command]
    return run_tests(project_dir, run_android_tests_command, timeout, workers=4)


class EmulatorStartupTimeoutError(Exception):
    """Raised when the emulator fails to start within the timeout period."""

    timeout_seconds: int

    def __init__(self, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds


class EmulatorFailedToStartError(Exception):
    """Raised when the emulator fails to start for any reason other than timeout."""

    pass


class EmulatorHeartbeat(threading.Thread):
    """A thread that monitors the status of an Android emulator."""

    def __init__(
        self,
        emulator_process: subprocess.Popen,
        adb_path: str,
        log_file: str,
        interval_seconds: int = 15,
    ) -> None:
        super().__init__()
        self.emulator_process = emulator_process
        self.adb_path = adb_path
        self.log_file = log_file
        self.interval_seconds = interval_seconds
        self.daemon = True
        self._stop_event = threading.Event()
        self.failure: str | None = None

    def stop(self) -> None:
        """Stops the heartbeat thread."""
        self._stop_event.set()

    def run(self) -> None:
        """Periodically checks the emulator status."""
        while not self._stop_event.is_set():
            # Check if the emulator process is still running
            if self.emulator_process and self.emulator_process.poll() is not None:
                message = f"CRITICAL: Emulator process (PID {self.emulator_process.pid}) has exited unexpectedly with code {self.emulator_process.returncode}."
                print_and_log(self.log_file, message)
                self.failure = message
                os.kill(os.getpid(), signal.SIGINT)
                break

            # Check if adb can still see the emulator
            try:
                result = subprocess.run(
                    [self.adb_path, "devices"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if "emulator" not in result.stdout.lower():
                    message = (
                        "CRITICAL: Emulator went offline or is not detected by ADB."
                    )
                    print_and_log(self.log_file, message)
                    self.failure = message
                    os.kill(os.getpid(), signal.SIGINT)
                    break
            except subprocess.TimeoutExpired:
                print_and_log(self.log_file, "WARNING: ADB devices command timed out.")
            except Exception as e:
                print_and_log(
                    self.log_file, f"WARNING: Error while checking emulator status: {e}"
                )

            # Wait for the next interval or until stopped
            self._stop_event.wait(self.interval_seconds)


def start_and_wait_for_emulator(
    log_file: str, emulator_avd_name: str, timeout_seconds: int = 180
) -> subprocess.Popen[Any]:
    """Starts an Android emulator and waits for it to be fully booted.

    Args:
      emulator_avd_name: The name of the AVD to start.
      timeout_seconds: The maximum time to wait for the emulator to boot.

    Returns:
      A subprocess.Popen object representing the running emulator process, or None
       if the emulator did not boot within the timeout period.

    Raises:
      EnvironmentError: If ANDROID_HOME environment variable is not set.
    """
    emulator_path = os.path.join(get_android_home(), "emulator", "emulator")
    # -no-snapshot: start the emulator from scratch each time to prevent
    #   restarting the emulator from a bad state.
    # -no-window: don't start a window for the emulator; this means we can't see
    #   or interact with the emulator, but that's fine for this use case.
    emulator_command = (
        f"{emulator_path} -avd {emulator_avd_name} -no-snapshot -no-window"
    )
    check_boot_completed_command = f"{get_adb_path()} shell getprop sys.boot_completed"

    print_and_log(log_file, f"Starting emulator: {emulator_command}")
    start_time = time.time()
    try:
        emulator_process = shell.run_command_async(emulator_command)
        # Give the emulator a moment to start its process
        time.sleep(5)

        print_and_log(log_file, "Waiting for emulator to boot...")
        while time.time() - start_time < timeout_seconds:
            result = shell.run_command(check_boot_completed_command)
            if "1" in result.stdout.strip():
                print_and_log(log_file, "Emulator fully booted and ready!")
                break

            time.sleep(5)
        else:
            print_and_log(log_file, "Emulator did not boot within the timeout period.")
            raise EmulatorStartupTimeoutError(timeout_seconds)
    except EmulatorStartupTimeoutError as e:
        raise e
    except Exception as e:
        print_and_log(log_file, f"An error occurred during emulator startup: {e}")
        raise EmulatorFailedToStartError()

    return emulator_process


def update_local_properties(repo_dir: str, java_home: str) -> None:
    """Updates local properties files to help Gradle sync succeed.

    Args:
      repo_dir: The directory containing the cloned repository.
      java_home: The path to the Java home directory.
    """
    # Write java.home to .gradle/config.properties
    if java_home:
        os.environ["JAVA_HOME"] = java_home
        gradle_dir = os.path.join(repo_dir, ".gradle")
        os.makedirs(gradle_dir, exist_ok=True)

        config_properties_path = os.path.join(gradle_dir, CONFIG_PROPERTIES_FILE)
        try:
            os.remove(config_properties_path)
        except OSError:
            pass
        with open(config_properties_path, "w+") as f:
            f.write(f"\njava.home={java_home}\n")


def clone_and_initialize_project(
    project_dir: str,
    pull_request_example: eval_data_classes.PullRequestExample,
    commit_sha: str,
    execution_config: eval_data_classes.RepoExecutionConfig,
    jdks_configs: dict[str, str],
) -> bool:
    """Clones a repository and initializes the project."""

    if not os.path.exists(project_dir):
        os.makedirs(project_dir, exist_ok=True)
    if not os.path.exists(os.path.join(project_dir, ".git")):
        helpers.git_clone(pull_request_example.repo, project_dir)
    if not helpers.reset_to_commit(commit_sha, project_dir):
        return False

    java_version = _extract_java_version(project_dir, execution_config)
    if not java_version or (java_version not in jdks_configs.keys()):
        logging.error(f"{java_version} is not in the list of available JDK version!")
        return False

    update_local_properties(project_dir, jdks_configs[java_version])
    if execution_config.init_command:
        shell.run_command(command=execution_config.init_command, cwd=project_dir)
        pull_request_example.init_command = execution_config.init_command
    return True


def is_test_file(file_name: str) -> bool:
    """Returns true if the file name is a test file."""
    # Normalize path separators
    file_name = file_name.replace("\\", "/")

    # Check for excluded directories
    # Patterns: **/build/*, **/androidTest/*, **/androidTests/*, **/testFixtures/*, **/[tT]est/*, **/[tT]ests/*
    path_parts = file_name.split("/")
    excluded_dirs = {
        "build",
        "androidTest",
        "androidTests",
        "testFixtures",
        "test",
        "Test",
        "tests",
        "Tests",
    }

    # Check directories
    if any(part in excluded_dirs for part in path_parts[:-1]):
        return True

    # Check for filename patterns
    basename = path_parts[-1]

    # If no extension, we probably don't match the .* patterns which imply an extension exists
    if "." not in basename:
        return False

    # Split name and extension. We handle multiple dots by splitting on the last dot.
    # Logic: validation patterns imply [Name].extension
    name_part, _ = os.path.splitext(basename)

    # **/*Test.*, **/*Tests.*, **/test.*, **/tests.*
    if name_part.endswith(("Test", "Tests")) or name_part in ("test", "tests"):
        return True

    return False


def _remove_empty_dirs(path: Path) -> None:
    """Recursively removes empty directories within the given path."""
    if not path.is_dir():
        return
    for child in path.iterdir():
        if child.is_dir():
            _remove_empty_dirs(child)
    try:
        if not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass


def copy_build_outputs(work_dir: Path, output_dir: Path) -> None:
    """
    Finds all 'build/outputs' directories within work_dir and copies them
    preserving the directory structure relative to work_dir.
    Ignores empty folders by not copying output directories that contain no files,
    and cleaning up any copied empty directory structures.
    """
    logging.info(f"Scanning for build contents in: {work_dir}")

    found_outputs = [p for p in work_dir.rglob("build/outputs") if p.is_dir()]

    if not found_outputs:
        logging.info("No 'build/outputs' directories found.")
        return

    logging.info(
        f"Found {len(found_outputs)} output directories. Copying to {output_dir}..."
    )

    ignore_func = shutil.ignore_patterns(
        "apk",
        "aar",
        "code_coverage",
        "unit_test_coverage",
        "logs",
        "mapping.txt",
    )

    for source_path in found_outputs:
        try:
            rel_path = source_path.relative_to(work_dir)
            dest_path = output_dir / rel_path

            # Ensure destination parent exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            if dest_path.exists():
                shutil.rmtree(dest_path)

            logging.info(f"Copying {source_path} -> {dest_path}")
            shutil.copytree(
                source_path,
                dest_path,
                dirs_exist_ok=True,
                ignore=ignore_func,
            )

        except Exception as e:
            logging.error(f"Failed to copy {source_path}: {e}")

    # Clean up any empty directories that might have been copied
    if output_dir.exists():
        _remove_empty_dirs(output_dir)

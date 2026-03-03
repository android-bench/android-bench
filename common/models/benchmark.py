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
import logging
from dataclasses import asdict, dataclass, field
from enum import Enum, auto
from pathlib import Path

from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EnvConfig:
    """
    The sandbox environment config for the task.
    """

    jdk_version: int = 17
    target_sdk: int = 35


@dataclass
class TokenDetails:
    completion_tokens: int = 0
    prompt_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LatencyDetails:
    query_latency_seconds: float = 0.0
    processing_latency_seconds: float = 0.0
    total_latency_seconds: float = 0.0


class Status(str, Enum):
    """Enum for Status of a patch verification run."""

    def _generate_next_value_(name, start, count, last_values):
        return name

    def __str__(self):
        """Use the name directly instead of Status.X in outputs and diagnostics."""
        return self.name

    # From harness (test execution results)
    PASSED = auto()
    PASSED_FLAKY = auto()

    # Agent related issues. Usually mean that agent messed up something.
    AGENT_NO_PATCH = auto()
    AGENT_FAILED_BUILD = auto()
    AGENT_FAILED_TEST = auto()
    AGENT_FAILED_VALIDATION = auto()
    AGENT_FAILED_TO_APPLY_PATCH = auto()
    AGENT_MISSING_REQUIRED_TEST_RESULTS = auto()

    # Harness infra errors. Come during setup, build, test or validation.
    INFRA_FAILURE = auto()
    INFRA_FAILURE_SETUP_ISSUE = auto()
    INFRA_FAILURE_EMULATOR_STARTUP = auto()
    INFRA_FAILURE_EMULATOR_TIMEOUT = auto()
    INFRA_FAILURE_EMULATOR_OFFLINE = auto()

    # Litellm Exceptions
    INFRA_FAILURE_AGENT_UNSUPPORTED_PARAMS = auto()
    INFRA_FAILURE_AGENT_NOT_FOUND = auto()
    INFRA_FAILURE_AGENT_PERMISSION_DENIED = auto()
    INFRA_FAILURE_AGENT_CONTEXT_EXCEEDED = auto()
    INFRA_FAILURE_AGENT_AUTH_ERROR = auto()
    INFRA_FAILURE_AGENT_API_ERROR = auto()
    INFRA_FAILURE_AGENT = auto()

    # Mini-swe-agent Exceptions
    INFRA_FAILURE_AGENT_FORMAT_ERROR = auto()
    INFRA_FAILURE_AGENT_EXECUTION_TIMEOUT = auto()
    INFRA_FAILURE_AGENT_LIMITS_EXCEEDED = auto()


STATUS_DESCRIPTIONS = {
    Status.PASSED: "PASSED",
    Status.PASSED_FLAKY: "PASSED_FLAKY",
    Status.AGENT_NO_PATCH: "Agent provided no patch. We start with this status.",
    Status.AGENT_FAILED_BUILD: "Agent created a patch that fails the build",
    Status.AGENT_FAILED_TEST: "Agent created a patch that fails the tests",
    Status.AGENT_FAILED_VALIDATION: "Agent created a patch that fails the validate.sh",
    Status.AGENT_FAILED_TO_APPLY_PATCH: "Agent produced a patch that can't be applied",
    Status.AGENT_MISSING_REQUIRED_TEST_RESULTS: "Some tests weren't executed. Agent probably messed with the tests.",
    Status.INFRA_FAILURE: "General infra issues with harness",
    Status.INFRA_FAILURE_SETUP_ISSUE: "A problem with setting up the repo, cwd, git apply, startup script",
    Status.INFRA_FAILURE_EMULATOR_STARTUP: "Emulator failed to start",
    Status.INFRA_FAILURE_EMULATOR_TIMEOUT: "Emulator couldn't start in time",
    Status.INFRA_FAILURE_EMULATOR_OFFLINE: "Emulator went offline during task execution",
    Status.INFRA_FAILURE_AGENT: "General agent failure. Please check log file or diagnostics for more details",
    Status.INFRA_FAILURE_AGENT_FORMAT_ERROR: "FormatError: Raised when the model's output is not in the expected format.",
    Status.INFRA_FAILURE_AGENT_EXECUTION_TIMEOUT: "ExecutionTimeoutError: Raised when the command issued by the model has timed out.",
    Status.INFRA_FAILURE_AGENT_LIMITS_EXCEEDED: "LimitsExceeded: Raised when the agent has reached its configured cost or step limit.",
    Status.INFRA_FAILURE_AGENT_UNSUPPORTED_PARAMS: "Litellm UnsupportedParamsError. Please check <task-id>/run.log file or diagnostics for more details",
    Status.INFRA_FAILURE_AGENT_NOT_FOUND: "Litellm NotFoundError. Please check <task-id>/run.log file or diagnostics for more details",
    Status.INFRA_FAILURE_AGENT_PERMISSION_DENIED: "Litellm PermissionDeniedError. Please check <task-id>/run.log file or diagnostics for more details",
    Status.INFRA_FAILURE_AGENT_CONTEXT_EXCEEDED: "Litellm ContextWindowExceededError. Please check <task-id>/run.log file or diagnostics for more details",
    Status.INFRA_FAILURE_AGENT_AUTH_ERROR: "Litellm AuthenticationError. Please check <task-id>/run.log file or diagnostics for more details",
    Status.INFRA_FAILURE_AGENT_API_ERROR: "Litellm APIError. Please check <task-id>/run.log file or diagnostics for more details",
}


@dataclass
class PatchScore:
    """
    Result of scoring a patch for a single instance.

    Attributes:
        instance_id: The unique identifier for the task.
        score: The numeric score (0.0 or 1.0).
        status: The status of the verification run.
        diagnostics: Diagnostic messages.
        job_name: The name of the cloud job on which this task was run, when running locally its value will be "local run".
    """

    instance_id: str
    score: float
    status: Status
    diagnostics: str
    job_name: str
    used_tokens: TokenDetails | None = None
    latency_details: LatencyDetails | None = None
    steps: str = "0"
    cost: str = "$0.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dict."""
        data = asdict(self)
        data["status"] = self.status.name
        data["status_description"] = STATUS_DESCRIPTIONS.get(self.status, "")
        return data


@dataclass(frozen=True)
class BenchmarkTask:
    """
    Represents a single, self-contained SWE-bench style task for an Android repository.

    Attributes:
        instance_id: A unique identifier for the task (e.g., 'square-okhttp-1234').
        repo_url: The HTTPS or SSH URL to the git repository.
        base_commit: The specific commit hash to checkout before applying the patch.
        patch_file: The local file path to the .diff or .patch file.
        env_config: The sandbox environment requirements for this task.
        build_commands: A list of shell commands required to build the project.
        test_commands: A list of shell commands required to run the relevant tests.
        work_dir: The working directory to run build and test commands in the repository.
        startup_script: The script to run at startup. Defaults to launch_scripts/<repo_name>.sh.
        pass_to_pass_tests: list of test files that were passing before the PR and after merging that PR.
        fail_to_pass_tests: list of test files that were failing before the PR and passing after merging that PR.
        steps: The amount of steps taken by the agent
        cost: The cost of generating the patch
    """

    instance_id: str
    repo_url: str
    base_commit: str | None = None
    before_change_id: str | None = None
    time_estimate: str | None = None
    merged_commit: str | None = None
    merged_change_id: str | None = None
    patch_file: Path | None = None
    test_patch_file: Path | None = None
    test_files: List[str] | None = None
    env_config: EnvConfig = field(default_factory=EnvConfig)
    build_commands: List[str] = field(default_factory=lambda: ["./gradlew build"])
    test_commands: List[str] = field(default_factory=lambda: ["./gradlew test"])
    work_dir: str | None = None
    startup_script: Path | None = None
    pass_to_pass_tests: List[str] | None = None
    fail_to_pass_tests: List[str] | None = None
    steps: str | None = None
    cost: str | None = None
    used_tokens: TokenDetails | None = None
    latency_details: LatencyDetails | None = None
    validation_file: Path | None = None

    @classmethod
    def from_json(
        cls,
        json_data: Dict[str, Any],
        patch_base_dir: str | None = None,
        is_test_task: bool = False,
    ) -> Optional["BenchmarkTask"]:
        """Creates a BenchmarkTask from a JSON object."""
        steps = "0"
        cost = "$0.0"
        used_tokens = TokenDetails()
        latency_details = LatencyDetails()
        instance_id = json_data.get("instance_id")
        if not instance_id:
            raise ValueError("instance_id is required in JSON")

        repo_url = json_data.get("repository", {}).get("url")
        if not repo_url:
            raise ValueError("repository.url is required in JSON")

        before_commit_data = json_data.get("before_commit", {})
        before_commit = before_commit_data.get("sha") if before_commit_data else None
        if not before_commit:
            logger.error(f"No before commit specified for {instance_id}")
        before_change_id = (
            before_commit_data.get("change_id") if before_commit_data else None
        )

        time_estimate = json_data.get("time_estimate")

        after_commit_data = json_data.get("after_commit")
        test_files = json_data.get("test_files")
        after_commit = after_commit_data.get("sha") if after_commit_data else None
        after_change_id = (
            after_commit_data.get("change_id") if after_commit_data else None
        )
        if not after_commit:
            logger.warning(f"No after commit specified for {instance_id}")

        commands = json_data.get("commands", {})
        build_commands = commands.get("build", [])
        test_commands = commands.get("unit_test", []) + commands.get("android_test", [])

        # We generate the task.json file 2 times, once from main.py and the second time
        # from harness.py running inside the docker container.
        #
        # 1. From main.py: We populate the patch-file paths and the scores read from
        #    the trajectory file. This json gets saved as task.json inside
        #    run_dir/verifier/<instance_id>/task.json which gets mounted inside docker
        #    containers.
        #
        # 2. From harness.py: We load the task.json file from the mounted directory.
        #    Since it already has the patch-file paths and the scores read from the
        #    trajectory file we don't need to do anything.
        if patch_base_dir:
            # this pathflow is for when we are generating the task.json file for the first time from main.py
            if is_test_task:
                patch_filename = f"golden.patch"
                # since we are running a golden-patch so no need to calculate steps and cost
            else:
                patch_filename = f"{instance_id}.patch"
                traj_path = (
                    Path(patch_base_dir).parent / "trajectories" / f"{instance_id}.json"
                )
                if traj_path.exists():
                    try:
                        traj_data = json.loads(traj_path.read_text())
                        steps = str(
                            traj_data.get("info", {})
                            .get("model_stats", {})
                            .get("api_calls", "0")
                        )
                        cost = "$" + str(
                            traj_data.get("info", {})
                            .get("model_stats", {})
                            .get("instance_cost", "0.0")
                        )
                        for message in traj_data.get("messages", []):
                            if message.get("role") == "assistant":
                                # Try to get usage from message directly first
                                usage = message.get("usage")
                                if not usage:
                                    # Fallback to extra -> response -> usage
                                    usage = (
                                        message.get("extra", {})
                                        .get("response", {})
                                        .get("usage", {})
                                    )

                                used_tokens.prompt_tokens += int(
                                    usage.get("prompt_tokens", "0")
                                )
                                used_tokens.completion_tokens += int(
                                    usage.get("completion_tokens", "0")
                                )
                                used_tokens.total_tokens += int(
                                    usage.get("total_tokens", "0")
                                )
                                latency_details.query_latency_seconds += float(
                                    message.get("query_latency_seconds", "0.0")
                                )
                            if message.get("role") == "user":
                                latency_details.processing_latency_seconds += float(
                                    message.get("processing_latency_seconds", "0.0")
                                )
                        latency_details.total_latency_seconds = (
                            traj_data.get("info", {})
                            .get("model_stats", {})
                            .get("total_latency_seconds", 0.0)
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to read trajectory for {instance_id}: {e}"
                        )

            patch_path = Path(patch_base_dir) / patch_filename
            test_patch_path = Path("dataset/tasks") / instance_id / "test.patch"
        else:
            # this pathflow is for when we are loading the task.json file from the mounted directory from harness.py
            if not "patch_file" in json_data:
                raise ValueError(
                    f"Patch file not specified for instance '{instance_id}'"
                )
            patch_path = Path(json_data.get("patch_file"))
            test_patch_path = Path(json_data.get("test_patch_file"))
            steps = json_data.get("steps")
            cost = json_data.get("cost")
            if td_data := json_data.get("used_tokens"):
                used_tokens = TokenDetails(**td_data)
            if ld_data := json_data.get("latency_details"):
                latency_details = LatencyDetails(**ld_data)

        logger.info(f"Patch file for instance '{instance_id}': {patch_path}")
        if not patch_path or not patch_path.exists():
            logger.warning(
                f"Patch file for instance '{instance_id}' not found. Skipping."
            )
            return None

        jdk = json_data.get("after_commit", {}).get("java_version")
        target = json_data.get("after_commit", {}).get("target_sdk")
        env_config = EnvConfig(
            jdk_version=jdk if jdk else 17, target_sdk=target if target else 35
        )
        acceptance_criteria_data = json_data.get("acceptance_criteria", {})
        if acceptance_criteria_data:
            pass_to_pass_tests = acceptance_criteria_data.get("pass_to_pass")
            fail_to_pass_tests = acceptance_criteria_data.get("fail_to_pass")
        else:
            logger.error(f"No acceptance criteria specified for {instance_id}")
            pass_to_pass_tests = []
            fail_to_pass_tests = []

        validation_script = json_data.get("validation_script")
        if validation_script:
            validation_file = (
                Path("dataset/tasks") / instance_id / json_data.get("validation_script")
            )
        else:
            validation_file = None

        return cls(
            instance_id=instance_id,
            repo_url=repo_url,
            base_commit=before_commit,
            before_change_id=before_change_id,
            time_estimate=time_estimate,
            merged_commit=after_commit,
            merged_change_id=after_change_id,
            test_patch_file=test_patch_path,
            build_commands=build_commands,
            test_commands=test_commands,
            patch_file=patch_path,
            test_files=test_files,
            env_config=env_config,
            pass_to_pass_tests=pass_to_pass_tests,
            fail_to_pass_tests=fail_to_pass_tests,
            steps=steps,
            cost=cost,
            used_tokens=used_tokens,
            latency_details=latency_details,
            validation_file=validation_file,
        )

    def __post_init__(self):
        """Performs validation after the object is created."""
        if self.startup_script is None:
            repo_name = self.repo_url.split("/")[-1]
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]
            script_path = Path(f"launch_scripts/{repo_name}.sh")
            object.__setattr__(self, "startup_script", script_path)

        if self.patch_file and not isinstance(self.patch_file, Path):
            # Ensure patch_file is a Path object for consistency
            object.__setattr__(self, "patch_file", Path(self.patch_file))

        if self.test_patch_file and not isinstance(self.test_patch_file, Path):
            # Ensure patch_file is a Path object for consistency
            object.__setattr__(self, "test_patch_file", Path(self.test_patch_file))

        if self.patch_file and not self.patch_file.is_file():
            raise FileNotFoundError(
                f"Patch file for instance '{self.instance_id}' not found at: {self.patch_file}"
            )

        if self.test_patch_file and not self.test_patch_file.is_file():
            logger.warning(
                f"Test patch file for instance '{self.instance_id}' not found at: {self.test_patch_file}"
            )

        if self.patch_file:
            object.__setattr__(
                self, "patch_file", Path("/android_bench/") / self.patch_file
            )

        if self.test_patch_file:
            object.__setattr__(
                self, "test_patch_file", Path("/android_bench/") / self.test_patch_file
            )

        if self.validation_file:
            object.__setattr__(
                self, "validation_file", Path("/android_bench/") / self.validation_file
            )

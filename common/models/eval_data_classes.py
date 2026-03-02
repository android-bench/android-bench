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
"""Defines data classes for the project."""

from collections.abc import Sequence, Set
import dataclasses
from typing import Optional


@dataclasses.dataclass
class PullRequestExample:
    """A dataclass to hold information about a pull request that is a candidate for becoming an eval task."""

    instance_id: str
    repo: str
    base_commit: str
    merge_commit: str
    head_commit: str
    pr_url: str
    issue_ids: Sequence[int]
    issue_urls: Sequence[str]

    base_commit_java_version: str | None = None
    base_commit_target_sdk: str | None = None
    head_commit_java_version: str | None = None
    head_commit_target_sdk: str | None = None
    merge_commit_java_version: str | None = None
    merge_commit_target_sdk: str | None = None
    merge_parent_commit_java_version: str | None = None
    merge_parent_commit_target_sdk: str | None = None

    merge_parent_commit: str | None = None

    init_command: Optional[str] | None = None
    build_command: Optional[str] | None = None
    unit_test_command: Optional[str] | None = None
    android_test_commands: Sequence[str] | None = None

    fail_to_pass_tests: Sequence[str] | None = None
    pass_to_pass_tests: Sequence[str] | None = None

    contains_tests: bool | None = None
    test_files: Sequence[str] | None = None


@dataclasses.dataclass
class RepoExecutionConfig:
    """A dataclass to hold the execution config for a repo."""

    repo: str

    java_version_files: Sequence[str]
    java_version_extraction_regex: Sequence[str]

    init_command: Optional[str] = None
    files_to_remove: Optional[list[str]] = None
    assemble_command: Optional[str] = None
    unit_tests_command: Optional[str] = None
    android_tests_command: Optional[str] = None
    fallback_java_version: str | None = None
    fallback_target_sdk: str | None = None

    skip_android_tests: bool | None = None


@dataclasses.dataclass
class TestsExecutionResult:
    """A dataclass to hold information about tests execution result."""

    build_successful: bool
    passed_tests: Set[str]
    failed_tests: Set[str]

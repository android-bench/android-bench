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
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class Commit(BaseModel):
    java_version: int | None
    sha: str | None = None
    change_id: str | None = None
    target_sdk: int | None


class Issue(BaseModel):
    id: int | None
    url: str | None

    @field_validator("url")
    def _validate_url_scheme(cls, v: str | None) -> str | None:
        if not v:
            return None

        if v.startswith("b/"):
            return f"https://b.corp.google.com/issues/{v[2:]}"

        if not v.startswith(("http://", "https://")):
            return f"https://{v}"
        return v


class PullRequest(BaseModel):
    id: int | None = None
    url: str | None = None


class Repository(BaseModel):
    name: str | None = None
    owner: str | None = None
    url: str


class Commands(BaseModel):
    android_test: list[str]
    before_build: list[str]
    build: list[str]
    unit_test: list[str]


class AcceptanceCriteria(BaseModel):
    fail_to_pass: list[str]
    pass_to_pass: list[str]


class Task(BaseModel):
    instance_id: str = Field(description="A unique identifier for the task instance.")
    submission_type: str = Field(
        description="The type of submission (e.g., 'ISSUE', 'PR')."
    )
    repository: Repository = Field(
        description="The repository associated with the task."
    )
    created_at: datetime | None = Field(
        description="The timestamp when the task was created."
    )
    modified_at: datetime | None = Field(
        description="The timestamp when the task was last modified."
    )
    task_type: str | None = Field(
        default=None,
        description="The type of task (e.g., 'bugfix', 'feature', 'optimization', 'refactor').",
    )
    category_ids: list[str] = Field(
        description="A list of category identifiers associated with the task."
    )
    description: str = Field(
        description="A detailed description of the task, used as context for the agent."
    )
    image_urls: list[str] | None = Field(
        default=None, description="A list of URLs to images related to the task."
    )
    video_urls: list[str] | None = Field(
        default=None, description="A list of URLs to videos related to the task."
    )
    before_commit: Commit | None = Field(
        default=None,
        description="Information about the commit before the task was addressed.",
    )
    after_commit: Commit | None = Field(
        default=None,
        description="Information about the commit after the task was addressed.",
    )
    commit_type: str | None = Field(
        default=None, description="The type of commit involved."
    )
    time_estimate: str | None = Field(
        default=None,
        description="Task time estimate.",
    )
    patch: str | None = Field(
        default=None, description="A patch representing the changes."
    )
    patch_content: str | None = Field(
        default=None, description="The content of the patch."
    )
    commands: Commands = Field(description="Commands to run for testing and building.")
    issues: list[Issue] = Field(description="A list of issues related to the task.")
    pull_request: PullRequest = Field(
        description="Information about the pull request associated with the task."
    )
    test_files: list[str] = Field(
        description="A list of test files in the after_commit. Used to generate test patches."
    )
    acceptance_criteria: AcceptanceCriteria | None = Field(
        description="Criteria for accepting the task completion."
    )
    testing_type: str | None = Field(
        default=None,
        description="The type of testing conducted (e.g., 'ALL_UNIT_TESTS_AND_ALL_ANDROID_TESTS', 'BUILD').",
    )
    validation_script: str | None = Field(
        default="validate.sh",
        description="Name of the validation script in the task folder used post tests to validate an agent patch.",
    )

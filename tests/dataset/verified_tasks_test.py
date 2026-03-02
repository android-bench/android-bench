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
import os
import yaml
import pytest
from common.constants import TASKS_DIR

VERIFIED_TASKS_PATH = os.path.join(TASKS_DIR, "verified_tasks.yaml")
DENIED_TASKS_PATH = os.path.join(TASKS_DIR, "denied_tasks.yaml")
IN_REVIEW_TASKS_PATH = os.path.join(TASKS_DIR, "in_review_tasks.yaml")
V1_TASKS_PATH = os.path.join(TASKS_DIR, "v1_tasks.yaml")


def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def test_verified_tasks_alphabetically_sorted():
    verified_tasks = load_yaml(VERIFIED_TASKS_PATH)
    assert verified_tasks == sorted(
        verified_tasks, key=str.lower
    ), "tasks/verified_tasks.yaml is not case-insensitively sorted"


def test_verified_tasks_not_in_denied_tasks():
    verified_tasks = load_yaml(VERIFIED_TASKS_PATH)
    denied_tasks = load_yaml(DENIED_TASKS_PATH)

    verified_set = set(verified_tasks)
    denied_set = set(denied_tasks)

    intersection = verified_set.intersection(denied_set)
    assert (
        not intersection
    ), f"The following tasks are in both verified and denied lists: {intersection}"


def test_verified_tasks_not_in_review_tasks():
    verified_tasks = load_yaml(VERIFIED_TASKS_PATH)
    in_review_tasks = load_yaml(IN_REVIEW_TASKS_PATH)

    verified_set = set(verified_tasks)
    in_review_set = set(in_review_tasks)

    intersection = verified_set.intersection(in_review_set)
    assert (
        not intersection
    ), f"The following tasks are in both verified and in review lists: {intersection}"


def test_verified_tasks_have_task_yaml():
    verified_tasks = load_yaml(VERIFIED_TASKS_PATH)
    for task_id in verified_tasks:
        task_yaml_path = os.path.join(TASKS_DIR, task_id, "task.yaml")
        assert os.path.exists(
            task_yaml_path
        ), f"Missing task.yaml for verified task: {task_id} at {task_yaml_path}"


def test_v1_tasks_are_verified():
    verified_tasks = load_yaml(VERIFIED_TASKS_PATH)
    v1_tasks = load_yaml(V1_TASKS_PATH)

    verified_set = set(verified_tasks)
    v1_set = set(v1_tasks)

    diff = v1_set - verified_set
    assert not diff, f"The following tasks are not verified in v1: {diff}"

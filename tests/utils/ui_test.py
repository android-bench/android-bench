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
import pytest
import time
from unittest.mock import patch
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from common.ui import create_dashboard


def test_create_dashboard_counts_statuses_correctly():
    # Arrange
    job_data = {
        "job1": {"status": "PENDING"},
        "job2": {"status": "SUBMITTED"},
        "job3": {"status": "RUNNING"},
        "job4": {"status": "SUCCEEDED"},
        "job5": {"status": "FAILED"},
        "job6": {"status": "COMPLETED"},
        "job7": {"status": "CANCELLED"},
        "job8": {"status": "UNKNOWN"},
    }
    start_time = time.time()

    # Act
    panel = create_dashboard(job_data, start_time)

    # Assert
    table = panel.renderable
    rows = {}
    for i in range(len(table.columns[0]._cells)):
        label = str(table.columns[0]._cells[i].plain)
        count = str(table.columns[1]._cells[i].plain)
        rows[label] = count

    assert rows["PENDING"] == "1"
    assert rows["SUBMITTED"] == "1"
    assert rows["RUNNING"] == "1"
    assert rows["SUCCEEDED"] == "2"  # SUCCEEDED + COMPLETED
    assert rows["FAILED"] == "2"  # FAILED + CANCELLED
    assert rows["SCHEDULED"] == "1"  # UNKNOWN


def test_create_dashboard_elapsed_time_formatting():
    # Arrange
    job_data = {}
    start_time = 1000.0
    current_time = 1065.0

    # Act
    with patch("time.time", return_value=current_time):
        panel = create_dashboard(job_data, start_time)

    # Assert
    assert "Time: 01:05" in panel.title


def test_create_dashboard_ui_structure():
    # Arrange
    job_data = {"job1": {"status": "RUNNING"}}
    start_time = time.time()
    custom_title = "Custom Bench"

    # Act
    panel = create_dashboard(job_data, start_time, title=custom_title)

    # Assert
    assert isinstance(panel, Panel)
    assert isinstance(panel.renderable, Table)
    assert custom_title in panel.title
    assert "Total: 1" in panel.title
    assert panel.renderable.show_header is True

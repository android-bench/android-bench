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
import unittest
from unittest.mock import patch, MagicMock
import subprocess
from pathlib import Path
from utils.task_validator.task_validator import TaskValidator


class TestTaskValidatorSubprocess(unittest.TestCase):
    def setUp(self):
        self.validator = TaskValidator(output_path="test_output.yaml")

    def test_run_command_timeout_real(self):
        """Test that run_command raises subprocess.TimeoutExpired on a real timeout."""
        command = ["sleep", "5"]
        with self.assertRaises(subprocess.TimeoutExpired):
            self.validator.run_command(command, timeout=0.1)

    def test_run_command_failure_real(self):
        """Test that run_command raises subprocess.CalledProcessError on a real failure."""
        command = ["ls", "/non/existent/directory/path/that/should/fail"]
        with self.assertRaises(subprocess.CalledProcessError):
            self.validator.run_command(command)


if __name__ == "__main__":
    unittest.main()

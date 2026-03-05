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
import sys
import os

# Add the script's directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.task_validator import validate_task


class TestValidateTask(unittest.TestCase):

    @patch("subprocess.Popen")
    def test_run_command_success(self, mock_popen):
        """Test that run_command executes and returns a successful result."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        mock_process.stdout.readline.side_effect = ["output\n", ""]
        mock_process.communicate.return_value = ("", "error\n")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = validate_task.run_command(["ls", "-l"], cwd=".")
        self.assertEqual(result.returncode, 0)
        self.assertIn("output", result.stdout)
        self.assertIn("error", result.stderr)

    @patch("subprocess.Popen")
    def test_run_command_failure(self, mock_popen):
        """Test that run_command exits on a failed command with check=True."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 1
        mock_process.stdout.readline.side_effect = [""]
        mock_process.communicate.return_value = ("", "error")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        with self.assertRaises(SystemExit):
            validate_task.run_command(["false"], cwd=".", check=True)

    @patch("argparse.ArgumentParser")
    @patch("utils.task_validator.validate_task.run_command")
    @patch("builtins.input", return_value="y")
    def test_main_happy_path(self, mock_input, mock_run_command, mock_arg_parser):
        """Test the main function's successful execution path."""
        # Mock arguments
        args = MagicMock()
        args.root_dir = "/fake/dir"
        args.task_commit = "task123"
        args.base_commit = "base123"
        args.test_commands = ["./gradlew test"]
        args.test_files = ["test/file.java"]
        args.log_output = False
        mock_arg_parser.return_value.parse_args.return_value = args

        # Mock run_command results
        mock_run_command.side_effect = [
            # git rev-parse HEAD (initial_commit)
            MagicMock(stdout="initial123\n"),
            # git status --porcelain
            MagicMock(stdout=""),
            # git checkout base_commit
            MagicMock(returncode=0),
            # git checkout task_commit -- test_file
            MagicMock(returncode=0),
            # test command on base (expected failure)
            MagicMock(returncode=1, stdout="Test failed", stderr=""),
            # git checkout task_commit
            MagicMock(returncode=0),
            # test command on task (expected success)
            MagicMock(returncode=0),
            # git reset --hard
            MagicMock(returncode=0),
            # git checkout initial_commit
            MagicMock(returncode=0),
        ]

        # We need to wrap the call to main in a try/except block to catch SystemExit
        # because the script calls sys.exit(0) at the end of the happy path.
        try:
            validate_task.main()
        except SystemExit as e:
            self.assertEqual(e.code, 0)


if __name__ == "__main__":
    unittest.main()

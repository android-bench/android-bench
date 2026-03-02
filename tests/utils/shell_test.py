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
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils import shell


class ShellTest(unittest.TestCase):

    def test_result_dataclass_decodes_stdout_stderr(self):
        # Test with byte strings
        stdout_bytes = b"hello"
        stderr_bytes = b"world"
        result = shell.Result(stdout=stdout_bytes, stderr=stderr_bytes, exit_code=0)
        self.assertIsInstance(result.stdout, str)
        self.assertEqual(result.stdout, "hello")
        self.assertIsInstance(result.stderr, str)
        self.assertEqual(result.stderr, "world")

    def test_result_dataclass_handles_strings(self):
        # Test with regular strings
        stdout_str = "hello"
        stderr_str = "world"
        result = shell.Result(stdout=stdout_str, stderr=stderr_str, exit_code=0)
        self.assertIsInstance(result.stdout, str)
        self.assertEqual(result.stdout, "hello")
        self.assertIsInstance(result.stderr, str)
        self.assertEqual(result.stderr, "world")


if __name__ == "__main__":
    unittest.main()

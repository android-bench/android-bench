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
import logging
import subprocess
import time
import os
from typing import Any, cast
from dataclasses import dataclass


@dataclass
class Result:
    """Holds the execution result of a subprocess command."""

    stdout: str
    stderr: str
    exit_code: int

    def __init__(self, stdout: str | bytes, stderr: str | bytes, exit_code: int):
        self.stdout = (
            stdout.decode("utf-8", "ignore")
            if isinstance(stdout, bytes)
            else cast(str, stdout)
        )
        self.stderr = (
            stderr.decode("utf-8", "ignore")
            if isinstance(stderr, bytes)
            else cast(str, stderr)
        )
        self.exit_code = exit_code


def run_command(
    command: str, cwd: str | None = None, timeout: int | None = None
) -> Result:
    """Runs a shell command and returns the output and error.

    Args:
      command: The command to run.
      cwd: The working directory to run the command in.
      timeout: The timeout for the command in seconds.

    Returns:
      A tuple containing the stdout and stderr of the command.
    """
    try:
        logging.info("Running command: %s, cwd=%s", command, cwd)
        result: subprocess.CompletedProcess[str] = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
            shell=True,
            timeout=timeout,
        )
        return Result(
            stdout=result.stdout, stderr=result.stderr, exit_code=result.returncode
        )
    except subprocess.CalledProcessError as e:
        logging.error(
            f"Command {command} failed, error: {e.stderr}, exit code: {e.returncode}."
        )
        return Result(e.output or b"", e.stderr or b"", e.returncode)
    except subprocess.TimeoutExpired as e:
        logging.error(f"Command {command} timed out after {e.timeout} seconds.")
        return Result(e.output or b"", e.stderr or b"", 1)


def run_command_async(command: str, cwd: str | None = None) -> subprocess.Popen[Any]:
    """Runs a shell command asynchronously and returns the Popen object.

    This function starts the command but does not wait for it to complete.
    The standard output and standard error of the command are not captured
    by this function directly.

    Args:
      command: The command to run.
      cwd: The working directory to run the command in.

    Returns:
      A subprocess.Popen object representing the running child process.
    """
    return subprocess.Popen(
        command,
        cwd=cwd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

#!/usr/bin/env python3

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
"""Checks the pre-requisites for Android Emulators in Docker."""

import logging
import os
import platform
import shutil
import subprocess
import sys
from common.logger import configure_logging

logger = logging.getLogger(__name__)
configure_logging()


def check_host_os():
    """Checks whether the host is on macOS or Windows."""
    system = platform.system()
    if system == "Darwin":
        macos_error = """ERROR: ⚠ macOS detected.
        Android emulators on Docker require KVM, which is not available."""
        sys.exit(macos_error)
    elif system == "Windows":
        windows_error = """ERROR: ⚠ Windows detected.
        Android emulators on Docker require KVM, which is not available."""
        sys.exit(windows_error)

    logger.info("OS check: [green]OK")


_EXPERIMENTAL_ARCHITECTURES = {
    "x86_64": ("x86_64", False),
    "amd64": ("x86_64", False),
    "aarch64": ("arm64-v8a", True),
    "arm64": ("arm64-v8a", True),
}


def check_arch():
    """Checks the host's architecture for emulator support.

    arm64/amd64 should not prompt generating images automatically.
    """
    arch, experimental = _EXPERIMENTAL_ARCHITECTURES.get(
        platform.machine(), (None, False)
    )
    if arch is None:
        sys.exit(
            "ERROR: Unsupported architecture: %s\n"
            "Android emulator requires x86_64 or arm64 Linux host with KVM."
            % platform.machine()
        )
    if experimental:
        logger.warning(
            "arm64 Android emulator in Docker has limited support: "
            "GPU restricted to swiftshader_indirect, snapshots may not work."
            "Modify the base Dockerfile at your own risk to enable support."
        )
    logger.info("Arch check: [green]OK")


def check_kvm():
    """Checks that KVM is available and accessible."""
    if not os.path.exists("/dev/kvm"):
        sys.exit(
            "ERROR: /dev/kvm not found.\n\n"
            "Enable KVM on your host:\n"
            "  sudo modprobe kvm_intel  # or kvm_amd\n"
            "  sudo usermod -aG kvm $USER"
        )
    if not os.access("/dev/kvm", os.W_OK):
        sys.exit(
            "ERROR: /dev/kvm exists but is not writable.\n\n"
            "Fix with: sudo usermod -aG kvm $USER\n"
            "Then log out and back in."
        )

    logger.info("KVM check: [green]OK")


def check_docker():
    """Checks that Docker is available and running."""
    if not shutil.which("docker"):
        sys.exit("ERROR: Docker not found in PATH.")

    result = subprocess.run(
        ["docker", "info"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        sys.exit("ERROR: Docker daemon not running or not accessible.")

    logger.info("Docker check: [green]OK")


def run_prebuild_checks():
    """Ensures all benchmark checks before attempting to build."""
    logger.info("[bold]Checking Docker prerequisites[/]")
    check_host_os()
    check_arch()
    check_docker()
    check_kvm()
    logger.info("All pre-build checks passed ✅")


def main() -> None:
    run_prebuild_checks()


if __name__ == "__main__":
    main()

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
import shutil
import tempfile
from pathlib import Path
from unittest import mock
import pytest
from utils import helpers


def test_copy_build_outputs():
    # Setup source directory structure
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        work_dir = temp_path / "work"
        output_dir = temp_path / "outputs"

        work_dir.mkdir()
        output_dir.mkdir()

        # Case 1: Direct build/outputs
        (work_dir / "app" / "build" / "outputs").mkdir(parents=True)
        (work_dir / "app" / "build" / "outputs" / "apk.txt").write_text("apk content")

        # Case 2: Nested build/outputs
        (work_dir / "lib" / "sub" / "build" / "outputs").mkdir(parents=True)
        (work_dir / "lib" / "sub" / "build" / "outputs" / "aar.txt").write_text(
            "aar content"
        )

        # Case 3: build dir without outputs (should be ignored)
        (work_dir / "other" / "build").mkdir(parents=True)
        (work_dir / "other" / "build" / "tmp.txt").write_text("ignore me")

        # Case 4: Excluded folders
        (work_dir / "app" / "build" / "outputs" / "apk").mkdir(parents=True)
        (work_dir / "app" / "build" / "outputs" / "apk" / "debug.apk").write_text(
            "apk file"
        )

        (work_dir / "app" / "build" / "outputs" / "aar").mkdir(parents=True)
        (work_dir / "app" / "build" / "outputs" / "aar" / "lib.aar").write_text(
            "aar file"
        )

        (work_dir / "app" / "build" / "outputs" / "logs").mkdir(parents=True)
        (work_dir / "app" / "build" / "outputs" / "logs" / "log.txt").write_text(
            "log file"
        )

        (work_dir / "app" / "build" / "outputs" / "unit_test_coverage").mkdir(
            parents=True
        )
        (
            work_dir / "app" / "build" / "outputs" / "unit_test_coverage" / "cov.xml"
        ).write_text("coverage")

        # Run copy
        helpers.copy_build_outputs(work_dir, output_dir)

        # Verify
        assert (output_dir / "app" / "build" / "outputs" / "apk.txt").exists()
        assert (
            output_dir / "app" / "build" / "outputs" / "apk.txt"
        ).read_text() == "apk content"

        assert (output_dir / "lib" / "sub" / "build" / "outputs" / "aar.txt").exists()
        assert (
            output_dir / "lib" / "sub" / "build" / "outputs" / "aar.txt"
        ).read_text() == "aar content"

        assert not (output_dir / "other" / "build" / "tmp.txt").exists()

        # Verify exclusions
        assert not (output_dir / "app" / "build" / "outputs" / "apk").exists()
        assert not (output_dir / "app" / "build" / "outputs" / "aar").exists()
        assert not (output_dir / "app" / "build" / "outputs" / "logs").exists()
        assert not (
            output_dir / "app" / "build" / "outputs" / "unit_test_coverage"
        ).exists()

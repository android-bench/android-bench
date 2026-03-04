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
import stat
import shutil
import tempfile
from pathlib import Path
import pytest
from utils.helpers import is_test_file, _copy_tree_writable, copy_build_outputs


@pytest.fixture
def tmp_path():
    # Use a directory in the current workspace instead of /tmp,
    # as /tmp might not be writable on some CI environments.
    # We use 'build/tmp' because 'build/' is already ignored by git.
    tmp_base = Path.cwd() / "build" / "tmp"
    tmp_base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(dir=tmp_base))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.mark.parametrize(
    "filename, expected",
    [
        # Positive Cases - Directories
        ("app/src/androidTest/java/com/example/MyTest.java", True),
        ("app/src/androidTests/java/com/example/MyTest.java", True),
        ("app/src/test/java/com/example/MyTest.java", True),
        ("app/src/Test/java/com/example/MyTest.java", True),
        ("app/src/tests/java/com/example/MyTest.java", True),
        ("app/src/Tests/java/com/example/MyTest.java", True),
        ("app/src/java/com/example/test.java", True),
        ("app/src/testFixtures/java/com/example/MyFixture.java", True),
        ("build/generated/source/buildConfig/debug/com/example/BuildConfig.java", True),
        # Positive Cases - Suffixes
        ("com/example/MyTest.java", True),
        ("com/example/MyTests.kt", True),
        ("com/example/FeatureTest.java", True),
        ("com/example/FeatureTests.kt", True),
        # Positive Cases - Exact Name
        ("com/example/test.java", True),
        ("com/example/tests.kt", True),
        # Negative Cases - Standard source files
        ("app/src/main/java/com/example/MainActivity.java", False),
        ("app/src/main/java/com/example/Utils.kt", False),
        ("app/src/java/com/example/latest.java", False),
        ("app/src/java/com/example/testimony.java", False),
        # Negative Cases - path components that *contain* test but aren't exact match
        ("app/src/main/java/com/example/testing/Utils.java", False),
        ("app/src/main/java/com/example/testutils/Utils.java", False),
        # Mixed cases for suffix (Original requirement was Case Sensitive Suffix)
        ("com/example/Mytest.java", False),
        ("com/example/Mytests.kt", False),
    ],
)
def test_is_test_file(filename, expected):
    assert is_test_file(filename) == expected


def test_copy_tree_writable_makes_files_writable(tmp_path):
    # Setup: Create a source directory with a read-only file
    src = tmp_path / "src"
    src.mkdir()
    ro_file = src / "readonly.txt"
    ro_file.write_text("hello")

    # Make it read-only (simulating Docker output)
    ro_file.chmod(stat.S_IREAD)  # 0o400

    # Verify it is indeed read-only
    # If we are root, os.access(ro_file, os.W_OK) will be True even if mode is 0o400.
    # So we check the mode bits instead.
    assert (ro_file.stat().st_mode & stat.S_IWUSR) == 0

    dst = tmp_path / "dst"

    # Action: Copy using our custom function
    _copy_tree_writable(src, dst)

    # Validation: Destination file should exist and be writable
    dst_file = dst / "readonly.txt"
    assert dst_file.exists()
    assert os.access(dst_file, os.W_OK)
    assert (dst_file.stat().st_mode & stat.S_IWUSR) != 0
    assert dst_file.read_text() == "hello"


def test_copy_tree_writable_makes_directories_writable(tmp_path):
    # Setup: Create a source directory structure
    src = tmp_path / "src"
    src.mkdir()
    sub_dir = src / "sub"
    sub_dir.mkdir()

    # Make sub_dir read-only (no write/execute)
    # Note: On many systems, if you remove execute bit you can't even enter it.
    # We want to simulate a directory that can be read but not written to.
    sub_dir.chmod(stat.S_IREAD | stat.S_IEXEC)

    # Verify it is read-only (no write bit for user)
    assert (sub_dir.stat().st_mode & stat.S_IWUSR) == 0

    dst = tmp_path / "dst"

    # Action
    _copy_tree_writable(src, dst)

    # Validation
    dst_sub = dst / "sub"
    assert dst_sub.exists()
    assert dst_sub.is_dir()
    assert os.access(dst_sub, os.W_OK)
    assert (dst_sub.stat().st_mode & stat.S_IWUSR) != 0


def test_copy_build_outputs_integration(tmp_path):
    # Setup: Mock a build output structure
    work_dir = tmp_path / "work"
    output_dir = tmp_path / "output"

    # Create build/outputs/some_dir/file.txt
    build_out = work_dir / "app" / "build" / "outputs"
    build_out.mkdir(parents=True)

    target_file = build_out / "result.txt"
    target_file.write_text("build success")
    target_file.chmod(stat.S_IREAD)  # Make it read-only

    # Verify it is read-only
    assert (target_file.stat().st_mode & stat.S_IWUSR) == 0

    # Action
    copy_build_outputs(work_dir, output_dir)

    # Validation
    copied_file = output_dir / "app" / "build" / "outputs" / "result.txt"
    assert copied_file.exists()
    assert os.access(copied_file, os.W_OK)
    assert (copied_file.stat().st_mode & stat.S_IWUSR) != 0
    assert copied_file.read_text() == "build success"


def test_copy_build_outputs_respects_ignore(tmp_path):
    work_dir = tmp_path / "work"
    output_dir = tmp_path / "output"

    build_out = work_dir / "build" / "outputs"
    build_out.mkdir(parents=True)

    (build_out / "keep.txt").write_text("keep")
    (build_out / "apk").mkdir()
    (build_out / "apk" / "should_be_ignored.apk").write_text("ignored")

    # Action
    copy_build_outputs(work_dir, output_dir)

    # Validation
    assert (output_dir / "build" / "outputs" / "keep.txt").exists()
    assert not (output_dir / "build" / "outputs" / "apk").exists()

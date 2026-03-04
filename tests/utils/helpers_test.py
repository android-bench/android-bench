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
from utils.helpers import is_test_file


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

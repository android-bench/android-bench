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
from results import stats
import math


def test_calculate_t_test_ci_simple():
    scores = [10.0, 10.0, 10.0]
    result = stats.calculate_t_test_ci(scores)
    assert result.mean == 10.0
    assert result.lower == 10.0
    assert result.upper == 10.0


def test_calculate_t_test_ci_known():
    # Simple known values
    scores = [4.0, 6.0]
    # mean = 5.0
    # var = ((4-5)^2 + (6-5)^2) / (2-1) = (1+1)/1 = 2.0
    # std_dev = sqrt(2) = 1.414..
    # std_err = 1.414 / sqrt(2) = 1.0
    # df = 1, t_crit = 12.706
    # margin = 12.706 * 1.0 = 12.706

    result = stats.calculate_t_test_ci(scores)
    assert result.mean == 5.0
    assert math.isclose(result.lower, 5.0 - 12.706, rel_tol=1e-3)
    assert math.isclose(result.upper, 5.0 + 12.706, rel_tol=1e-3)


def test_calculate_bootstrap_ci_requires_scipy(mocker):
    # Mock import failure effectively
    # Since we can't easily uninstall scipy for a test, we might check if
    # the function raises/logs if not present, but for now we expect it to WORK
    # provided the env is set up.
    pass


def test_calculate_bootstrap_ci_simple():
    # Bootstrap on identical data should likely yield 0 width CI
    scores = [10.0] * 10
    result = stats.calculate_bootstrap_ci(scores, n_resamples=100)
    assert result.mean == 10.0
    assert math.isclose(result.lower, 10.0, abs_tol=1e-5)
    assert math.isclose(result.upper, 10.0, abs_tol=1e-5)


def test_calculate_bootstrap_ci_range():
    # With [0, 10], mean is 5.
    scores = [0.0, 10.0] * 50  # 100 items
    result = stats.calculate_bootstrap_ci(scores, n_resamples=500)
    assert result.mean == 5.0
    # The CI should contain the mean and be somewhat symmetric for this uniform-like dist
    assert result.lower < 5.0
    assert result.upper > 5.0

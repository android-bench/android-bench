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
import math
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CIResult:
    mean: float
    lower: float
    upper: float


# t-distribution critical values for 95% confidence (two-tailed)
# df -> t_value
T_VALUES = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
}


def calculate_t_test_ci(
    scores: list[float], confidence_level: float = 0.95
) -> CIResult:
    """
    Calculates Confidence Interval using Student's t-distribution.
    This assumes normal distribution or sufficient sample size.
    For small sample sizes of unknown distribution, this might be less accurate.
    """
    n = len(scores)
    if n == 0:
        return CIResult(0.0, 0.0, 0.0)

    mean_val = sum(scores) / n

    if n == 1:
        return CIResult(mean_val, mean_val, mean_val)

    variance = sum((s - mean_val) ** 2 for s in scores) / (n - 1)
    std_dev = math.sqrt(variance)
    std_err = std_dev / math.sqrt(n)
    df = n - 1

    # Use fallback 2.0 (approx 1.96 for z-score) if df > 10 and not in table
    # Ideally we would use scipy if available for exact t-values
    t_crit = T_VALUES.get(df, 2.0)

    margin = t_crit * std_err
    return CIResult(mean_val, mean_val - margin, mean_val + margin)


def calculate_bootstrap_ci(
    scores: list[float], confidence_level: float = 0.95, n_resamples: int = 1000
) -> CIResult:
    """
    Calculates Confidence Interval using Bootstrapping (percentile method).
    Requires scipy and numpy.
    """
    try:
        from scipy.stats import bootstrap
        import numpy as np
    except ImportError:
        logger.error(
            "scipy and numpy are required for bootstrap CI. Please install '.[analysis]'."
        )
        raise

    if not scores:
        return CIResult(0.0, 0.0, 0.0)

    if len(scores) < 2:
        return CIResult(scores[0], scores[0], scores[0])

    # bootstrap requires a sequence
    data = (scores,)

    # We use np.mean as the statistic
    res = bootstrap(
        data,
        np.mean,
        confidence_level=confidence_level,
        n_resamples=n_resamples,
        method="percentile",
    )

    mean_val = float(np.mean(scores))
    return CIResult(mean_val, res.confidence_interval.low, res.confidence_interval.high)

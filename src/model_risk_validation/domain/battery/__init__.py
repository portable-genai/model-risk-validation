"""The deterministic validation-test battery (slice 3).

Stdlib-only statistics are the AUTHORITY: every discrimination, calibration, stability and
backtesting figure is computed here in pure Python, and a managed ``ports/stats.py`` adapter may
recompute the same statistic remotely but never replaces this as the source of truth, which is
what keeps the offline gate SDK-free. The engine owns every number and every pass/fail verdict;
a missing input is a named gap, never a silent pass.
"""

from __future__ import annotations

from .runner import BatteryReport, BatteryRunner, TestOutcome
from .stats import auc, calibration_error, exception_rate, gini, psi

__all__ = [
    "BatteryReport",
    "BatteryRunner",
    "TestOutcome",
    "auc",
    "calibration_error",
    "exception_rate",
    "gini",
    "psi",
]

"""Activity unit conversion, half-life unit conversion and decay correction (the Aptec *Decay
Correction Calculation* utility, DECAY.EXE).  Pure functions, no GUI imports.

    A(t) = A(t0) * exp(-ln 2 * (t - t0) / T1/2)

A positive interval decays the activity forward in time; a negative one corrects it back.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

BQ_PER_CI = 3.7e10
# activity units -> Bq
ACTIVITY_UNITS = {
    "Bq": 1.0, "kBq": 1e3, "MBq": 1e6, "GBq": 1e9, "TBq": 1e12,
    "Ci": BQ_PER_CI, "mCi": BQ_PER_CI * 1e-3, "uCi": BQ_PER_CI * 1e-6, "nCi": BQ_PER_CI * 1e-9,
    "pCi": BQ_PER_CI * 1e-12, "dps": 1.0, "dpm": 1.0 / 60.0,
}
YEAR_S = 365.25 * 86400.0
# time units -> seconds
TIME_UNITS = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0, "y": YEAR_S}


def convert_activity(value: float, from_unit: str, to_unit: str) -> float:
    try:
        return float(value) * ACTIVITY_UNITS[from_unit] / ACTIVITY_UNITS[to_unit]
    except KeyError as exc:
        raise ValueError(f"unknown activity unit {exc.args[0]!r}") from None


def convert_time(value: float, from_unit: str, to_unit: str) -> float:
    try:
        return float(value) * TIME_UNITS[from_unit] / TIME_UNITS[to_unit]
    except KeyError as exc:
        raise ValueError(f"unknown time unit {exc.args[0]!r}") from None


def decay_factor(half_life_s: float, interval_s: float) -> float:
    """exp(-ln 2 * interval / half-life): the fraction left after ``interval_s`` seconds."""
    if not half_life_s or half_life_s <= 0:
        raise ValueError("the half-life must be positive")
    return math.exp(-math.log(2.0) * float(interval_s) / float(half_life_s))


def decay_correct(activity: float, half_life_s: float, from_time: datetime, to_time: datetime) -> float:
    """Activity at ``to_time`` of a source that had ``activity`` at ``from_time``."""
    return float(activity) * decay_factor(half_life_s, (to_time - from_time).total_seconds())


def decay_uncertainty(activity: float, rel_err_activity: float, half_life_s: float, half_life_rel_err: float,
                      interval_s: float) -> float:
    """1-sigma uncertainty of the corrected activity: the activity's relative error and the
    half-life's contribution |ln 2 * t / T| * (dT/T), combined in quadrature (relative)."""
    a = activity * decay_factor(half_life_s, interval_s)
    hl = abs(math.log(2.0) * interval_s / half_life_s) * float(half_life_rel_err or 0.0)
    return abs(a) * math.hypot(float(rel_err_activity or 0.0), hl)


def mean_life_s(half_life_s: float) -> float:
    return half_life_s / math.log(2.0)


def elapsed_s(from_time: Optional[datetime], to_time: Optional[datetime]) -> Optional[float]:
    if from_time is None or to_time is None:
        return None
    return (to_time - from_time).total_seconds()


__all__ = ["ACTIVITY_UNITS", "TIME_UNITS", "YEAR_S", "convert_activity", "convert_time", "decay_factor",
           "decay_correct", "decay_uncertainty", "mean_life_s", "elapsed_s"]

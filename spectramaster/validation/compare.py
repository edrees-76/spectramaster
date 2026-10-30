"""Comparison of harness results with their recorded values (docs/baseline/round9_harness_protocol.md).

Numbers equal within a relative tolerance, so a re-run on another platform or library build does not
fail a control on the last bit of a float.
"""
from __future__ import annotations

import math

REL = 1e-12


def same(a, b, rel: float = REL) -> bool:
    """True when `a` and `b` (nested dicts, lists, numbers, strings, None) are equal, numbers within
    relative `rel` (NaN equals NaN)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if math.isnan(a) or math.isnan(b):
            return math.isnan(a) and math.isnan(b)
        return math.isclose(a, b, rel_tol=rel, abs_tol=0.0)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k], rel) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y, rel) for x, y in zip(a, b))
    return a == b

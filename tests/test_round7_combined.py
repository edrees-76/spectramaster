"""Round-7 review Codex H2 / Gemini M1: limits of the weighted mean of the lines
(docs/baseline/round7_combined_protocol.md)."""
import math

from spectramaster.validation import round7_combined as h
from spectramaster.validation import round8_line_covariance as r8


def _close(a, b):
    return math.isclose(a, b, rel_tol=1e-9)


def test_blank_peak_on_one_line_only_keeps_the_cross_term():
    r, o = h._one_blank("iso11929", [10000.0, None], 0.03)
    ind = h.full_covariance(r, o, "iso11929", 0.03)
    assert _close(r.decision_threshold, ind["threshold"]) and _close(r.mda, ind["limit"])
    no_blank = [l for l in r.lines if l.blank_activity is None][0]
    assert no_blank.ref_g0 == [0.0, 0.0, 0.0] and no_blank.ref_dg == [0.1, 0.0, 0.03]


def test_currie_is_unchanged_without_a_linear_term():
    r, o = h._one_blank("currie", [None, 10000.0], 0.0)
    ind = h.full_covariance(r, o, "currie", 0.0)
    assert _close(r.decision_threshold, ind["threshold"]) and _close(r.mda, ind["limit"])


def test_undetected_mean_reports_the_limits_of_its_weighted_mean():
    for nuc in ("Co-60", "Ba-133"):
        r, o = h._undetected(nuc, "iso11929")
        ind = h.weighted_mean_limits(r, o, "iso11929")
        if nuc == "Ba-133":
            # its close lines share window channels: their covariance counts since engine 1.34.0
            # (round8_line_covariance_protocol.md)
            ind = r8.expected(r, o, h.r5._spectrum("sample"), None, None, False)
        assert ind["n"] >= 2 and not r.detected
        assert _close(r.decision_threshold, ind["threshold"]) and _close(r.mda, ind["limit"])
        key, _o = h._undetected(nuc, "iso11929", method="key")
        assert r.decision_threshold < key.decision_threshold


def test_weighted_mean_above_its_threshold_is_noted_not_detected():
    r, _o = h._undetected("Co-60", "iso11929", counts=h._bumped_counts())
    assert not r.detected and r.primary > r.decision_threshold
    assert h.NOTE in r.note
    plain, _o = h._undetected("Co-60", "iso11929")
    assert h.NOTE not in (plain.note or "")

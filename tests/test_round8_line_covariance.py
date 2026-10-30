"""Round-8 review, Gemini M3: the weighted mean of a nuclide's window results counts the covariance of
lines whose windows share channels, and sums the reference peak components before the norm
(docs/baseline/round8_line_covariance_protocol.md)."""
from __future__ import annotations

import pytest

from spectramaster.analysis import activity as act
from spectramaster.validation import round8_line_covariance as r8


@pytest.mark.parametrize("name,mode", [("none", None), ("peak", "peak"), ("spectrum", "spectrum")])
def test_weighted_mean_counts_the_shared_channels(name, mode):
    r, o, bg = r8.run_case(name, mode, "currie")
    e = r8.expected(r, o, r8._sample(), bg, mode, False)
    assert e["n"] >= 2 and e["max_offdiag"] > 0
    assert r.primary_u == pytest.approx(e["primary_u"], rel=1e-9)
    assert r.decision_threshold == pytest.approx(e["threshold"], rel=1e-9)
    assert r.mda == pytest.approx(e["limit"], rel=1e-9)


def test_reference_components_summed_before_the_norm():
    r, o, _bg = r8.run_case("ref_blank", None, "iso11929")
    e = r8.expected(r, o, r8._sample(), None, None, True)
    use = r8._usable(r)
    assert e["ref_term"] < sum(w * l.ref_unc_bq for w, l in zip(act._primary_weights(use, o), use))
    assert r.primary_u == pytest.approx(e["primary_u"], rel=1e-9)


def test_lines_without_shared_channels_have_no_cross_term():
    o = act.ActivityOptions(nuclides=["Co-60"], method="mean")
    r = act.compute_activities(r8.r5._spectrum("sample"), r8.r5._flat_curve(), o, peaks=[]).nuclides[0]
    use = r8._usable(r)
    assert len(use) == 2
    assert act._window_cov(use[0], use[1]) == 0.0


def test_lines_loaded_without_coefficients_count_as_independent():
    r, o, _bg = r8.run_case("none", None, "currie")
    use = r8._usable(r)
    for l in use:
        del l._cov_res
    assert act._cross_cov(use, act._primary_weights(use, o)) == 0.0

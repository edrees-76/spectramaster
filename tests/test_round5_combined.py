"""Round-5 review, H1: limits of the weighted mean of lines (round5_combined_protocol.md)."""
import pytest

from spectramaster.analysis import activity as act
from spectramaster.validation import round5_combined as r5


def test_criteria_pass():
    c, _alpha = r5.criteria(r5.measure())
    assert all(c.values()), c


@pytest.mark.parametrize("mda", ["iso11929", "currie"])
def test_threshold_and_limit_of_the_mean_use_its_weights(mda):
    res, o = r5._run("Co-60", [(r5.CO[0], 3000.0, 60.0), (r5.CO[1], 900.0, 450.0)], mda, None)
    ind = r5.independent(res, o, mda)
    assert res.decision_threshold == pytest.approx(ind["threshold"], rel=1e-9)
    assert res.mda == pytest.approx(ind["limit"], rel=1e-9)
    # the inverse-variance threshold of the zero-activity weights is lower: the defect
    s0 = ind["s0"]
    assert res.decision_threshold > o.k_alpha / sum(1.0 / s ** 2 for s in s0) ** 0.5 * 1.3


@pytest.mark.parametrize("mda", ["iso11929", "currie"])
def test_one_line_gives_its_own_limits(mda):
    res, o = r5._run("Co-60", [(r5.CO[0], 3000.0, 60.0), (r5.CO[1], 900.0, 450.0)], mda, None, method="key")
    k = res.key_line
    ys, yd = act.combined_limits([k], [1.0], o)
    assert ys == pytest.approx(k.decision_threshold, rel=1e-12)
    assert yd == pytest.approx(k.mda, rel=1e-12)

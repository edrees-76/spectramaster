"""Round-5 review, H1: limits of the weighted mean of lines (round5_combined_protocol.md)."""
import pytest

from spectramaster.analysis import activity as act
from spectramaster.validation import round5_combined as r5


def test_criteria_pass():
    m = r5.measure()
    c, _alpha = r5.criteria(m)
    assert c["RC.C1"] and c["RC.C2"] and c["RC.C3"], c
    # RC.C4 / RC.C5 compare bit for bit (==) with values recorded on the registered Windows machine;
    # other platforms differ in the last digits of the efficiency fit, so the test allows 1e-12
    for n, b in r5.BEFORE.items():
        for k in ("activity", "u", "threshold", "mda") if n.startswith("key_") else ("activity", "u"):
            assert m[n][k] == pytest.approx(b[k], rel=1e-12), (n, k)
        if not n.startswith("key_"):
            assert m[n]["used"] == b["used"]
            assert m[n]["budget"] == pytest.approx(b["budget"], rel=1e-12)


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

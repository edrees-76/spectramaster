"""Round-5 review, H5/H6: partial true-coincidence summing corrections (round5_tcs_protocol.md)."""
import numpy as np
import pytest

from spectramaster.analysis import coincidence as co
from spectramaster.analysis import efficiency as ef
from spectramaster.validation import round5_tcs as r5


def _flat(v):
    return lambda e: np.full(np.shape(e), v) if np.ndim(e) else v


def test_partner_below_the_curve_makes_the_correction_partial():
    hi = co.coi("Ba-133", 356.0129, _flat(0.02), _flat(0.24), e_min=122.0)
    lo = co.coi("Ba-133", 356.0129, _flat(0.02), _flat(0.24), e_min=50.0)
    assert hi.partial and "below the efficiency curve" in hi.partial_reason and hi.factor == 1.0
    assert not lo.partial and lo.partial_reason == "" and lo.factor == pytest.approx(0.9703591108631351, rel=1e-12)


@pytest.mark.parametrize("energy, partial", [(880.76, True), (911.204, False), (968.971, False)])
def test_inconsistent_scheme_intensities_make_the_correction_partial(energy, partial):
    c = co.coi("Ac-228", energy, _flat(0.02), _flat(0.24), e_min=40.0)
    assert c.partial is partial
    assert c.inconsistent == pytest.approx(r5._independent_inconsistent("Ac-228", energy, _flat(0.02), 40.0),
                                           rel=1e-12, abs=1e-15)
    if partial:
        assert "intensities" in c.partial_reason


def test_ba133_81kev_is_not_partial_for_a_negligible_effect():
    c = co.coi("Ba-133", 80.9979, r5._steep, r5._pt, e_min=40.0)
    assert not c.partial and 0 < c.inconsistent < co.PARTIAL_LIMIT


def test_calibration_with_partial_points_is_refused():
    pts = r5._cal_points(r5.EU, "Eu-152") + r5._cal_points({e: i for e, i in r5.BA.items() if e > 200}, "Ba-133")
    with pytest.raises(ValueError, match="partial"):
        ef.summing_free_curve(ef.fit_efficiency(pts, "loglog", order=2), r5._pt, 0.1)
    full = r5._cal_points(r5.EU, "Eu-152") + r5._cal_points(r5.BA, "Ba-133")
    assert ef.summing_free_curve(ef.fit_efficiency(full, "loglog", order=2), r5._pt, 0.1).summing_corrected


def test_activity_marks_partial_lines_without_changing_values():
    a = r5._activity()
    hi, lo = a["e_min 122"], a["e_min 50"]
    assert all(l[6] for l in hi["lines"] if l[2]) and "partial correction for" in hi["note"]
    assert not any(l[6] for l in lo["lines"]) and "partial" not in lo["note"]

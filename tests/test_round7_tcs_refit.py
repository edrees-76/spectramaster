"""Round-7 review H1: the summing state of an efficiency curve kept through a refit
(docs/baseline/round7_tcs_refit_protocol.md)."""
import math

import pytest

from spectramaster.analysis import efficiency as ef
from spectramaster.validation import round6_tcs_state as r6
from spectramaster.validation import round7_tcs_refit as h


@pytest.fixture(scope="module")
def curves():
    return r6._curves()


def test_refit_keeps_the_summing_state(curves):
    free = curves["eu_ba_121.8"]["free"]
    assert free.summing_corrected and len(free.tcs_partial) == 4
    refit = h._refit(free)
    assert refit.summing_corrected and refit.tcs_partial == free.tcs_partial
    assert all(f"{n} {e:g} keV: {why}" in refit.warnings for n, e, why in free.tcs_partial)
    assert math.isclose(refit.efficiency(500.0), free.efficiency(500.0), rel_tol=1e-12)


def test_no_second_correction_after_a_refit(curves):
    free = curves["eu_ba_121.8"]["free"]
    a = r6._quant(free, True).nuclides[0].activity
    b = r6._quant(h._refit(free), True).nuclides[0].activity
    assert math.isclose(a, b, rel_tol=1e-12)


def test_corrected_and_raw_cascade_points_are_not_fitted_together(curves):
    free = curves["eu_ba_121.8"]["free"]
    with pytest.raises(ValueError, match="Co-60 1332.5 keV"):
        h._refit(free, list(free.points) + [h._extra(free, *h.CO60)])
    ok = h._refit(free, list(free.points) + [h._extra(free, *h.CS137)])
    assert ok.summing_corrected and ok.tcs_partial == free.tcs_partial


def test_saved_points_carry_the_fields_only_when_set(curves):
    raw = curves["eu_ba_121.8"]["raw"].to_dict()
    assert not any("summing_coi" in p or "summing_partial" in p for p in raw["points"])
    free = curves["eu_ba_121.8"]["free"].to_dict()
    assert any("summing_coi" in p for p in free["points"])
    back = ef.EfficiencyCurve.from_dict(free)
    assert back.tcs_partial == curves["eu_ba_121.8"]["free"].tcs_partial


def test_legacy_corrected_curve_gets_the_point_fields(curves):
    d = curves["eu_ba_121.8"]["free"].to_dict()
    for p in d["points"]:               # as saved by engine 1.26.0
        p.pop("summing_coi", None)
        p.pop("summing_partial", None)
    c = ef.EfficiencyCurve.from_dict(d)
    cas = ef._cascade_points(c.points)
    assert cas and all(p.summing_coi is not None for p in cas)
    assert sum(1 for p in cas if p.summing_partial) == 4
    refit = h._refit(c)
    assert refit.summing_corrected and refit.tcs_partial == c.tcs_partial

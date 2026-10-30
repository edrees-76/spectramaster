"""Round-8 review, Gemini M1: calibration points already corrected for true-coincidence summing on a
curve not marked corrected are refitted as they are, not divided by their COI again
(docs/baseline/round8_coi_guard_protocol.md)."""
from __future__ import annotations

import pytest

from spectramaster.analysis import efficiency as ef
from spectramaster.validation import round5_tcs as r5
from spectramaster.validation import round8_coi_guard as r8


@pytest.fixture(scope="module")
def curves():
    return r8._curves()


def test_reenabled_corrected_points_are_not_corrected_twice(curves):
    c = curves["reenabled"]
    before = [(p.efficiency, p.unc, p.summing_coi) for p in c.points]
    f = ef.summing_free_curve(c, r5._pt, 0.1)
    assert f.summing_corrected
    assert [(p.efficiency, p.unc, p.summing_coi) for p in f.points] == before
    ref = curves["refit"]
    for e in r8.ENERGIES + [r8.EU121]:
        assert float(f.efficiency(e)) == pytest.approx(float(ref.efficiency(e)), rel=1e-12)
    assert ef.TCS_ALREADY_CORRECTED in f.note


def test_activity_note_and_value(curves):
    q, qr = r8._quant(curves["reenabled"]), r8._quant(curves["refit"])
    assert q["activity"] == pytest.approx(qr["activity"], rel=1e-12)
    assert any(n == "efficiency curve: " + ef.TCS_ALREADY_CORRECTED for n in q["notes"])


def test_mixed_corrected_and_uncorrected_cascade_points_refused(curves):
    with pytest.raises(ValueError, match="that are not"):
        ef.summing_free_curve(curves["mixed"], r5._pt, 0.1)


def test_uncorrected_curve_still_corrected(curves):
    f = ef.summing_free_curve(curves["raw"], r5._pt, 0.1)
    assert f.summing_corrected and ef.TCS_ALREADY_CORRECTED not in f.note
    assert any(p.summing_coi is not None and p.summing_coi < 1.0 for p in f.points if p.nuclide == "Eu-152")

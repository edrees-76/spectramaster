"""Round-5 review, detector acceptance test and activity entry (docs/baseline/round5_acceptance_protocol.md)."""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from spectramaster.analysis import detector_test as dt
from spectramaster.validation import round5_acceptance as r5


@pytest.mark.parametrize("cal", ["linear", "quadratic"])
def test_cut_spectrum_with_first_channel_gives_the_full_spectrum_values(cal):
    full = r5._values(r5.build(r5.CALS[cal]))
    cut = r5._values(r5.build(r5.CALS[cal], r5.CUT))
    assert cut[0] == pytest.approx(1332.5, abs=0.02)            # the centroid was 832.5 keV before
    for a, b in zip(cut, full):
        assert a == pytest.approx(b, rel=1e-9)


def test_peak_to_compton_needs_the_whole_window():
    sp = r5.build(r5.CALS["linear"], int(1060.0 / 0.5))
    res = dt.acceptance_test(sp)
    assert res.peak_to_compton is None
    assert any("not fully inside" in n for n in res.notes)
    assert dt.peak_to_compton(r5.build(r5.CALS["linear"], int(1030.0 / 0.5))) == pytest.approx(
        dt.peak_to_compton(r5.build(r5.CALS["linear"])), rel=1e-12)


def test_relative_efficiency_refuses_values_that_are_not_finite():
    sp = r5.build(r5.CALS["linear"])
    for act in (math.inf, math.nan):
        with pytest.raises(ValueError):
            dt.relative_efficiency(sp, act)
    sp.live_time = math.inf
    with pytest.raises(ValueError):
        dt.relative_efficiency(sp, 37000.0)


def test_activity_text():
    pytest.importorskip("PySide6")
    from spectramaster.gui.activity_input import parse_activity
    for t in r5.PARSE_REFUSED:
        with pytest.raises(ValueError):
            parse_activity(t)
    for t, bq in r5.PARSE_READ:
        assert parse_activity(t) == bq


def test_qc_reference_activity_records():
    pytest.importorskip("PySide6")
    from spectramaster.gui.qc_window import _parse_activity
    for t, expected in r5.QC_CASES:
        if expected is None:
            with pytest.raises(ValueError):
                _parse_activity(t)
        else:
            assert _parse_activity(t) == expected


def test_certificate_keeps_the_exact_activity_across_unit_changes():
    pytest.importorskip("PySide6")
    res = r5.c6()
    assert res["round_trip"] == [12345.678, 246.91356]
    assert res["edited_bq"] == 2000.0

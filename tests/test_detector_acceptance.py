"""Detector acceptance test and chi-square counting test (analysis/detector_test.py,
docs/baseline/detector_acceptance_protocol.md and its amendment)."""
from __future__ import annotations

import math
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from spectramaster.analysis import detector_test as dt
from spectramaster.validation import detector_acceptance as da


def test_widths_of_a_gaussian_peak():
    w = dt.peak_width(da.build(0.25, 2.0, 1e5))
    assert w.fwhm_kev == pytest.approx(2.0, rel=0.01)
    assert w.ratio == pytest.approx(da.FWTM_RATIO, rel=0.01)
    assert w.linear_crossings == 0 and not w.note


def test_relative_efficiency_with_decay_correction():
    area, ref = da._area_for(40.0, 5.0)
    r = dt.relative_efficiency(da.build(0.5, 2.0, area), da.ACTIVITY, 0.02 * da.ACTIVITY, ref)
    assert r.percent == pytest.approx(40.0, rel=1e-3)
    assert r.decay_factor == pytest.approx(0.5191, abs=2e-3)          # Co-60, 5 years
    assert r.u_total > r.u_counting


def test_peak_to_compton_by_hand():
    m = da.p_to_c()
    assert m["equal"]


def test_chi_square_points_and_decision():
    r = dt.chi_square_test([10000, 10050, 9950, 10100, 9900, 10020, 9980, 10070, 9930, 10000])
    assert (round(r.low, 3), round(r.high, 3), r.dof) == (3.325, 16.919, 9)
    assert r.chi2 == pytest.approx(sum((x - 10000) ** 2 for x in
                                       [10000, 10050, 9950, 10100, 9900, 10020, 9980, 10070, 9930, 10000]) / 10000)
    assert r.passed
    assert not dt.chi_square_test([10000, 11000, 9000, 10500, 9500, 10000, 12000, 8000, 10000, 10000]).passed
    assert "TECDOC-1599 uses 10 or 20" in dt.chi_square_test([100, 110, 90]).note
    with pytest.raises(ValueError):
        dt.chi_square_test([1, 2])


def test_dialogs_match_the_engine():
    pytest.importorskip("PySide6")
    from spectramaster.gui.app import create_app
    from spectramaster.gui import detector_test_dialog as dd
    create_app(["test"])
    area, ref = da._area_for(40.0, 5.0)
    sp = da.build(0.5, 2.0, area)
    dlg = dd.AcceptanceDialog(sp)
    dlg.activity.set_unit("µCi")
    dlg.activity.set_bq(da.ACTIVITY)
    assert dlg.activity.number.text() == "1"
    from PySide6.QtCore import QDateTime
    dlg.ref_date.setDateTime(QDateTime(ref))
    got = dlg.calculate()
    want = dt.acceptance_test(sp, da.ACTIVITY, 0.0, ref)
    assert got.relative_efficiency.percent == pytest.approx(want.relative_efficiency.percent, rel=1e-4)
    assert got.width_1332.fwhm_kev == want.width_1332.fwhm_kev
    assert dlg.table.rowCount() >= 7
    dlg.close()
    c = dd.ChiSquareDialog()
    c.counts.setPlainText("10000\n10050\n9950\n\n10100\n9900\n10020\n9980\n10070\n9930\n10000\n")
    r = c.calculate()
    assert r.n == 10 and r.passed and c.table.rowCount() == 6
    with pytest.raises(ValueError):
        dd.parse_counts("100\nabc\n")
    c.close()


def test_menu_actions_exist():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings
    from spectramaster.gui.app import MainWindow, create_app
    from spectramaster.gui.settings import Settings
    import tempfile
    create_app(["test"])
    with tempfile.TemporaryDirectory() as d:
        w = MainWindow(Settings(QSettings(os.path.join(d, "s.ini"), QSettings.IniFormat)))
        try:
            assert w.act_acceptance.text() and w.act_chi2.text()
            w._spectra, w._index = [da.build(0.5, 2.0, 1e5)], 0
            w.act_acceptance.trigger()
            assert w._acceptance_dialog.spectrum is w._spectra[0]
            w._acceptance_dialog.close()
        finally:
            w.close()
            w.deleteLater()

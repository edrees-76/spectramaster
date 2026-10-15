"""Aptec Analyze spectrum operations in the main window (headless)."""
from __future__ import annotations

import math
import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from spectramaster.gui import i18n
from spectramaster.model import Spectrum
from spectramaster.tools import spectrum_ops as ops


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


@pytest.fixture()
def window(qapp, tmp_path):
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.settings import Settings
    i18n.set_language("en")
    w = MainWindow(Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)))
    w.errors = []
    w.show_error = w.errors.append
    w.show_info = w.errors.append
    w.spectrum_ops.messages = []
    w.spectrum_ops.message = w.spectrum_ops.messages.append
    w.spectrum_ops.confirm = lambda title, text: True
    yield w
    w.close()
    w.deleteLater()
    QApplication.processEvents()
    i18n.set_language("en")


def _spectrum(n=1024, live=100.0, peak=300):
    counts = [100.0 + 1000.0 * math.exp(-0.5 * ((i - peak) / 3.0) ** 2) for i in range(n)]
    return Spectrum(counts=counts, energy_coeffs=[0.0, 0.5], live_time=live, real_time=live * 1.1,
                    start_time=datetime(2024, 5, 1, 9), sample_id="S1")


def _show(window, spec=None):
    window.display([spec or _spectrum()], None, None)
    window.plot.resize(1000, 400)
    return window.plot


def test_menu_order_and_keys(window):
    names = [a.objectName() for a in window.menu_analyze.actions() if a.objectName().startswith("act_o_")]
    assert names == ["act_o_add_constant", "act_o_normalize", "act_o_shift", "act_o_smooth", "act_o_reduce",
                     "act_o_derivative", "act_o_compare", "act_o_exchange", "act_o_combine", "act_o_strip",
                     "act_o_position", "act_o_undo", "act_o_original"]
    assert window.act_o_undo.shortcut() == QKeySequence("Ctrl+Z")
    assert not window.act_o_smooth.isEnabled()
    _show(window)
    assert window.act_o_smooth.isEnabled() and not window.act_o_strip.isEnabled()
    assert not window.act_o_undo.isEnabled()


def test_smooth_undo_keeps_rois_and_view(window):
    plot = _show(window)
    plot._insert_roi(290, 310)
    plot.set_view(200.0, 400.0, None)
    orig = window.current_spectrum()
    assert window.spectrum_ops.smooth(5)
    s = window.current_spectrum()
    assert s is not orig and ops.status_of(s) == ["Smoothed 5"]
    assert [(r.left, r.right) for r in plot.rois] == [(290, 310)]
    assert (plot.x0, plot.x1) == (200.0, 400.0)
    assert "Poisson" in window.statusBar().currentMessage()
    assert window.act_o_undo.isEnabled()
    assert window.spectrum_ops.undo()
    assert window.current_spectrum() is orig
    assert not window.act_o_undo.isEnabled()


def test_reduce_divides_rois_and_view(window):
    plot = _show(window)
    plot._insert_roi(290, 310)
    plot.set_view(200.0, 400.0, None)
    assert window.spectrum_ops.reduce(4)
    s = window.current_spectrum()
    assert s.num_channels == 256
    assert [(r.left, r.right) for r in plot.rois] == [(72, 77)]
    assert (plot.x0, plot.x1) == (50.0, 100.0)
    assert plot.rois[0].stats is not None and plot.rois[0].stats.centroid == pytest.approx((300 - 1.5) / 4, abs=0.05)   # J = (ch - 1.5) / 4
    assert window.spectrum_ops.undo()
    assert window.current_spectrum().num_channels == 1024
    assert (plot.x0, plot.x1) == (200.0, 400.0)


def test_derivative_and_original_data(window):
    _show(window)
    orig = window.current_spectrum()
    ctl = window.spectrum_ops
    assert ctl.derivative(1, 0)
    assert ctl.derivative(3, 5)                     # taken from the original, not from the 1st
    assert ops.status_of(window.current_spectrum()) == ["Derivative 3 (smoothed 5)"]
    assert ctl.derivative(0)
    assert window.current_spectrum() is orig and ctl.deriv_base is None


def test_compare_normalize_strip_exchange(window, tmp_path):
    from spectramaster.convert import write_spectrum
    from spectramaster.formats import get_format
    plot = _show(window)
    path = tmp_path / "bkg.spe"
    write_spectrum(_spectrum(live=400.0, peak=600), path, get_format("spe"))
    ctl = window.spectrum_ops
    assert ctl.strip() is False and ctl.messages             # needs Compare first
    assert ctl.toggle_compare(str(path))
    assert plot.compare_overlay() is not None and window.act_o_compare.isChecked()
    assert window.act_o_strip.isEnabled()
    QTest.keyClick(plot, Qt.Key_Up, Qt.ControlModifier)
    assert plot.compare_overlay().offset_px == 4
    assert ctl.position(30) and plot.compare_overlay().offset_px == 30
    ratio = ops.live_time_ratio(window.current_spectrum(), ctl.compare)
    assert ratio == pytest.approx(4.0)
    assert ctl.normalize(ratio)
    assert window.current_spectrum().live_time == pytest.approx(400.0)
    assert ctl.strip(confirm=False)
    net = np.asarray(window.current_spectrum().counts)
    assert net[300] == pytest.approx(4 * 1100.0 - 100.0, rel=1e-3)     # compare peak is at 600
    assert net[600] == pytest.approx(4 * 100.0 - 1100.0, rel=1e-3) and net[100] == pytest.approx(300.0, rel=1e-3)
    old = window.current_spectrum()
    assert ctl.exchange()
    assert ctl.compare is old and window.current_spectrum().live_time == pytest.approx(400.0)
    assert ctl.toggle_compare() and plot.compare_overlay() is None


def test_combine_and_add_constant(window, tmp_path):
    from spectramaster.convert import write_spectrum
    from spectramaster.formats import get_format
    _show(window)
    path = tmp_path / "b.spe"
    write_spectrum(_spectrum(), path, get_format("spe"))
    ctl = window.spectrum_ops
    ctl.toggle_compare(str(path))
    a = np.asarray(window.current_spectrum().counts)
    b = np.asarray(ctl.compare.counts)                  # SPE stores whole counts
    assert ctl.combine(confirm=False)
    assert np.allclose(window.current_spectrum().counts, a + b)
    assert window.current_spectrum().live_time == pytest.approx(200.0)
    assert ctl.add_constant(-10)
    assert np.allclose(window.current_spectrum().counts, a + b - 10)


def test_new_file_clears_undo(window):
    _show(window)
    window.spectrum_ops.shift(3)
    assert window.act_o_undo.isEnabled()
    _show(window)
    assert not window.act_o_undo.isEnabled() and not window.spectrum_ops.undo()


def test_arabic_menu(window):
    window.apply_language("ar", save=False)
    assert window.act_o_smooth.text().replace("&", "") == "تنعيم..."
    assert window.act_o_strip.text().replace("&", "") == "طرح..."


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_dialogs_build(window, lang):
    from spectramaster.gui import aptec_ops_ui as u
    window.apply_language(lang, save=False)
    dlgs = [u.AddConstantDialog(window, 3), u.NormalizeDialog(window, 4.0), u.NormalizeDialog(window, None),
            u.ShiftDialog(window, 1024), u.SmoothDialog(window, 7), u.ReduceDialog(window, 1024),
            u.DerivativeDialog(window, 2, 5), u.PositionDialog(window, 10)]
    assert dlgs[1].value() == pytest.approx(4.0) and dlgs[2].value() == 1.0
    dlgs[1].factor.setText("0")
    assert dlgs[1].value() is None
    dlgs[3].left.setChecked(True)
    assert dlgs[3].value() == -1
    assert dlgs[4].value() == 7 and dlgs[5].factor.count() == 6 and dlgs[5].value() == 2
    assert dlgs[6].value() == (2, 5)
    for d in dlgs:
        assert d.layoutDirection() == (Qt.RightToLeft if lang == "ar" else Qt.LeftToRight)
        d.deleteLater()


def test_negative_channels_shown_below_zero(window):
    plot = _show(window)
    assert plot.y_range()[0] == 0.0
    window.spectrum_ops.derivative(1, 0)
    lo, hi = plot.y_range()
    assert lo < min(window.current_spectrum().counts) < 0 < hi

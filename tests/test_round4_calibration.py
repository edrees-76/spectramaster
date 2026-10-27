"""Round-4 review, calibration and manual-fit findings (docs/baseline/round4_calibration_protocol.md)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import numpy as np
import pytest

from spectramaster.analysis.background import channel_variance, known_variance, set_channel_variance
from spectramaster.model import Spectrum
from spectramaster.tools import spectrum_ops as ops
from spectramaster.tools.arithmetic import subtract_background
from spectramaster.tools.calibrate import fwhm_from_widths
from spectramaster.validation import scenarios
from spectramaster.validation.round4_calibration import _spectra
from spectramaster.validation.synthetic import HPGE


def test_falling_widths_give_no_fwhm_calibration_and_a_note():
    widths = {("A", 50.0): (100.0, 12.0), ("B", 500.0): (1000.0, 5.0)}
    fit, note = fwhm_from_widths(widths, list(widths), [0.0, 0.5], (0, 8191))
    assert fit is None and "decrease" in note and "A 50.00" in note


def test_quadratic_negative_at_the_ends_falls_back_to_order_one():
    widths = {(f"L{i}", 100.0 * (i + 1)): (c, w) for i, (c, w) in
              enumerate([(1000.0, 2.0), (1500.0, 3.0), (2000.0, 3.8), (2500.0, 4.4)])}
    fit, note = fwhm_from_widths(widths, list(widths), [0.0, 0.5], (0, 8191))
    assert fit.order == 1 and note == ""
    assert np.polynomial.polynomial.polyval(np.array([0.0, 8191.0]), fit.coeffs).min() > 0


def test_variance_follows_the_counts():
    sample, bkg = _spectra()
    net, sigma = subtract_background(sample, bkg)
    assert np.allclose(channel_variance(net), np.asarray(sigma) ** 2)
    assert channel_variance(sample) is None and np.array_equal(known_variance(sample), sample.counts)
    net.counts[10] += 1.0                                     # changed by hand: the variance is unknown
    assert channel_variance(net) is None
    with pytest.raises(ValueError):
        set_channel_variance(sample, [1.0])


def test_aptec_operations_propagate_or_drop_the_variance():
    sample, bkg = _spectra()
    k = sample.live_time / bkg.live_time
    s, b = np.asarray(sample.counts), np.asarray(bkg.counts)
    assert np.allclose(channel_variance(ops.normalize(bkg, k)), k * k * b)
    assert np.allclose(channel_variance(ops.strip(sample, ops.normalize(bkg, k))), s + k * k * b)
    assert np.allclose(channel_variance(ops.combine(sample, bkg)), s + b)
    sh = ops.shift(ops.strip(sample, bkg), 3)
    assert np.allclose(channel_variance(sh)[3:], (s + b)[:-3]) and not channel_variance(sh)[:3].any()
    assert channel_variance(ops.smooth(ops.strip(sample, bkg), 3)) is None
    assert channel_variance(ops.normalize(sample, 2.0)) is not None
    raw = Spectrum(counts=[5.0] * 64, live_time=10.0)
    assert raw.variance is None and channel_variance(ops.shift(raw, 1)) is not None


# ------------------------------------------------------------------ GUI (RD.C5)
@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from spectramaster.gui.app import create_app
    return create_app(["test"])


@pytest.fixture()
def window(qapp, tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from spectramaster.gui import i18n
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.settings import Settings
    i18n.set_language("en")
    w = MainWindow(Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)))
    w.errors, w.infos = [], []
    w.show_error = w.errors.append
    w.show_info = w.infos.append
    yield w
    if w.fit_window is not None:
        w.fit_window.close()
    w.close()
    w.deleteLater()
    QApplication.processEvents()


def wait_idle(dlg, timeout=120.0):
    from PySide6.QtWidgets import QApplication
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QApplication.processEvents()
        if not dlg.busy:
            QApplication.processEvents()
            return True
        time.sleep(0.01)
    return False


def test_calibration_dialog_refits_the_fwhm_after_an_exclusion(window):
    from spectramaster.gui.calibration_dialog import open_calibration_dialog
    spec = next(scenarios.calibration_source(HPGE, "Eu-152", 1, category="unit")).spectrum
    window.display([spec], None, None)
    dlg = open_calibration_dialog(window, modal=False)
    dlg.message = lambda text: None
    dlg.source_edit.setText("Eu-152")
    assert dlg.propose() and wait_idle(dlg)
    first = dlg.proposal.fwhm_fit
    assert first is not None and dlg.fwhm_fit.coeffs == first.coeffs
    k = int(np.argmax([abs(r) for r in first.residuals]))
    row = next(i for i, p in enumerate(dlg.points) if p.label == first.labels[k])
    assert dlg.set_point_used(row, False, reason="suspected doublet")
    assert first.labels[k] not in dlg.fwhm_fit.labels and dlg.fwhm_fit.coeffs != first.coeffs
    assert dlg.set_point_used(row, True)                        # used again: the proposal's FWHM is back
    assert dlg.fwhm_fit.coeffs == pytest.approx(first.coeffs, rel=1e-9)
    assert dlg.set_point_used(row, False, reason="suspected doublet")
    applied = dlg.fwhm_fit.coeffs
    dlg.apply_fwhm.setChecked(True)
    new = dlg.accept_calibration()
    assert new is not None and new.fwhm_coeffs == pytest.approx(applied)


def test_fit_window_passes_the_variance_of_a_net_spectrum(window):
    from spectramaster.gui.fit_inspection import open_fit_inspection
    sample, bkg = _spectra()
    net, sigma = subtract_background(sample, bkg)
    for spec, has_var in ((net, True), (sample, False)):
        window.display([spec], None, None)
        dlg = open_fit_inspection(window, show=False)
        dlg.msgs = []
        dlg.message = dlg.msgs.append
        assert wait_idle(dlg) and dlg.report is not None, dlg.last_error
        opts = dlg.fit_options()
        assert ("variance" in opts) is has_var
        if has_var:
            assert np.allclose(opts["variance"], np.asarray(sigma) ** 2)
        assert dlg.add_peak(500.0) and wait_idle(dlg), dlg.msgs
        details = dlg.last_op.details
        assert (details.get("variance") == "explicit") is has_var and "not_poisson" not in details
        dlg.close()
        window.fit_window = None

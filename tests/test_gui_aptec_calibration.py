"""Aptec-style Setup menu and calibration windows (headless)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QDialog, QTableWidgetItem

from spectramaster.analysis import Peak
from spectramaster.analysis import aptec_calibration as ac
from spectramaster.gui import i18n
from spectramaster.model import Spectrum

APTEC_DIR = Path(os.environ.get("SPECTRAMASTER_APTEC_DIR", r"C:\APTEC\APTEC"))


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
    w.errors, w.infos = [], []
    w.show_error = w.errors.append
    w.show_info = w.infos.append
    yield w
    for d in QApplication.topLevelWidgets():
        if isinstance(d, QDialog) and d.isVisible():
            d.dirty = False
            d.done(0)
    w.close()
    w.deleteLater()
    QApplication.processEvents()
    i18n.set_language("en")


def _spectrum(coeffs=(0.0, 0.5)):
    rng = np.random.default_rng(1)
    ch = np.arange(4096)
    counts = 20 + rng.poisson(5, 4096).astype(float)
    for c, a in ((1323.3, 4000), (2346.5, 3000), (2665.0, 2500)):
        counts += a * np.exp(-0.5 * ((ch - c) / 2.0) ** 2)
    return Spectrum(counts=counts.tolist(), energy_coeffs=list(coeffs), live_time=1000.0, real_time=1010.0,
                    start_time=datetime(2024, 3, 1, 10, 0, 0), sample_id="cal")


def _peak(ch, nuclide, e, rate, fwhm=4.0):
    return Peak(centroid=ch, energy=e, fwhm=fwhm, fwhm_kev=fwhm * 0.5, net_area=rate * 1000.0,
                net_area_unc=rate * 1000.0 * 0.01, gross_area=0, background=0, left=int(ch) - 5,
                right=int(ch) + 5, significance=50, count_rate=rate, nuclide=nuclide, line_energy=e)


def test_setup_menu_like_aptec(window):
    titles = [a.text().replace("&", "") for a in window.menuBar().actions()]
    assert titles.index("Setup") == titles.index("ROI") - 1 == titles.index("Analyze") - 2
    acts = window.menu_setup.actions()
    assert acts[:4] == [window.act_quick_energy, window.act_full_energy, window.act_full_res, window.act_full_eff]
    assert window.act_quick_energy.shortcut() == QKeySequence("F2")
    assert window.act_full_eff.shortcut() == QKeySequence("Shift+F2")
    assert window.act_calibrate in window.menu_setup_advanced.actions()
    assert window.act_calibrate not in window.menu_analyze.actions()
    window.apply_language("ar", save=False)
    assert window.menu_setup.title() == i18n.STRINGS["ar"]["acal_menu_setup"]
    assert window.act_quick_energy.text() == i18n.STRINGS["ar"]["acal_act_quick"]
    window.apply_language("en", save=False)


def test_channel_marker_and_roi_centroid(window):
    from spectramaster.gui.aptec_calibration_ui import marker_channel
    window.display([_spectrum()], None, None)
    plot = window.plot
    moved = []
    plot.markerMoved.connect(moved.append)
    plot.set_marker(500)
    assert moved == [500] and marker_channel(window) == 500.0
    plot.add_roi(1310, 1336)
    plot.set_marker(1320)
    assert marker_channel(window) == pytest.approx(1323.3, abs=0.2)      # ROI centroid, not the marker
    plot.set_marker(10 ** 6)
    assert plot.marker == 4095                                         # clamped to the spectrum


def test_quick_energy_calibration(window):
    from spectramaster.gui.aptec_calibration_ui import open_quick_energy
    spec = _spectrum(())
    window.display([spec], None, None)
    d = open_quick_energy(window)
    d.message = lambda text: (_ for _ in ()).throw(AssertionError(text))
    assert d.table.rowCount() == 16 and d.degree.value() == 2
    window.plot.add_roi(2335, 2358)
    window.plot.set_marker(2346)
    d.table.setCurrentCell(0, 0)                    # entering an empty Channel cell takes the ROI centroid
    assert float(d.table.item(0, 0).text()) == pytest.approx(2346.5, abs=0.2)
    d.table.setItem(0, 1, QTableWidgetItem("1173.228"))
    d.table.setItem(1, 0, QTableWidgetItem("2665.0"))
    d.table.setItem(1, 1, QTableWidgetItem("1332.492"))
    assert d.calib()
    assert d.calibration.degree == 1                 # two points: highest degree they allow
    assert "·ch" in d.eq_label.text() and d.time_label.text() != "none"
    new = d.ok()
    shown = window.current_spectrum()
    assert shown is new and len(shown.energy_coeffs) == 2
    assert shown.energy_of(2665.0) == pytest.approx(1332.492, abs=1e-6)
    assert list(shown.counts) == list(spec.counts) and spec.energy_coeffs == []
    assert "quick energy calibration" in shown.extra["recalibrated"]


def test_quick_energy_clear_removes_calibration(window):
    from spectramaster.gui.aptec_calibration_ui import open_quick_energy
    window.display([_spectrum()], None, None)
    d = open_quick_energy(window)
    d.clear()
    d.ok()
    assert window.current_spectrum().energy_coeffs == []


def _run_points(points):
    def hook(dlg):
        dlg.set_points(points)
        dlg.ok_fit()
        return dlg.result() == QDialog.Accepted
    return hook


def test_full_energy_and_resolution(window):
    from spectramaster.gui.aptec_calibration_ui import ENERGY, RESOLUTION, open_full_calibration
    window.display([_spectrum()], None, None)
    w = open_full_calibration(window, ENERGY)
    w.message = lambda text: (_ for _ in ()).throw(AssertionError(text))
    assert "No energy calibration" in w.report.toPlainText() or "no calibration" in w.report.toPlainText().lower() \
        or "equation" in w.report.toPlainText().lower()
    pts = [(1323.3, 661.657), (2346.5, 1173.228), (2665.0, 1332.492), (300.0, 150.0)]
    assert w.edit_points(ENERGY, _run_points(pts))
    assert w.energy.degree == 2 and "Average deviation" in w.report.toPlainText()
    w.set_degree(ENERGY, 1)
    assert w.energy.degree == 1
    assert w.edit_points(RESOLUTION, _run_points([(1323.3, 4.0), (2346.5, 4.6), (2665.0, 4.8)]))
    assert w.resolution.degree == 2
    new = w.save_spectrum()
    shown = window.current_spectrum()
    assert shown is new and not w.dirty
    assert shown.energy_coeffs == pytest.approx(w.energy.coeffs)
    slope = w.energy.coeffs[1]
    assert np.polyval(shown.fwhm_coeffs[::-1], 2346.5) == pytest.approx(w.resolution.evaluate(2346.5) * slope)
    assert "energy_calibration_points" in shown.extra
    assert w.delete_current(confirmed=True) and w.resolution is None
    w.dirty = False
    w.close()


def test_full_efficiency_load_rois_calculate_fit_and_save(window, tmp_path):
    from spectramaster.analysis import efficiency as eff
    from spectramaster.gui.aptec_calibration_ui import EFFICIENCY, open_full_calibration
    spec = _spectrum()
    window.display([spec], None, None)
    window.analysis_panel.peaks = [_peak(1323.3, "Cs-137", 661.657, 30.0), _peak(2346.5, "Co-60", 1173.228, 20.0),
                                   _peak(2665.0, "Co-60", 1332.492, 18.0)]
    w = open_full_calibration(window, EFFICIENCY)
    w.message = lambda text: (_ for _ in ()).throw(AssertionError(text))
    w.set_eff_type("D")
    cert = datetime(2023, 3, 1)

    def hook(dlg):
        dlg.message = lambda text: (_ for _ in ()).throw(AssertionError(text))
        n = dlg.load_rois({"units": "kBq", "time": cert, "quantity": 1.0, "quantity_err": 0.0})
        assert n == 3 and dlg.points[0].isotope == "Cs-137"
        assert dlg.points[0].yield_ == pytest.approx(0.85, abs=0.01)
        dlg.slider.setValue(1)
        dlg.f["ef_activity"].setText("40")
        dlg.act_err.setValue(3.0)
        dlg._store()
        dlg.slider.setValue(2)
        dlg.f["ef_activity"].setText("25")
        dlg.act_err.setValue(2.0)
        dlg._store()
        assert dlg.points[2].activity == 25 and dlg.points[2].activity_err == 2.0   # same isotope filled in
        dlg.points.append(ac.EffPoint(energy=122.06, isotope="manual", efficiency=0.08, efficiency_err=5.0,
                                      manual=True))
        dlg.detector, dlg.geometry_id = "HPGe-1", "Marinelli-1L"
        dlg.ok_fit()
        return dlg.result() == QDialog.Accepted

    assert w.edit_points(EFFICIENCY, hook)
    p = w.eff_points[0]
    dec = np.exp(-np.log(2) * (spec.start_time - cert).total_seconds() / p.half_life_s)
    assert p.efficiency == pytest.approx(30.0 / (40e3 * p.yield_ * dec), rel=1e-9)
    assert p.efficiency_err == pytest.approx(np.hypot(1.0, 3.0))
    assert w.efficiency is not None and w.efficiency.eff_type == "D"
    assert "3rd order polynomial" in w.report.toPlainText()
    w.set_eff_type("S")
    assert w.efficiency.eff_type == "S" and "not verified" in w.report.toPlainText()
    w.set_eff_type("B")
    w.save_spectrum(curve_folder=tmp_path)
    assert w.saved_curve_path is not None and w.saved_curve_path.parent == tmp_path
    curve = eff.load_curve(w.saved_curve_path)
    assert curve.detector == "HPGe-1" and curve.geometry == "Marinelli-1L"
    assert curve.efficiency(700.0) == pytest.approx(w.efficiency.efficiency(700.0), rel=1e-10)
    assert "efficiency_calibration" in window.current_spectrum().extra
    w.close()


def test_efficiency_points_require_activity_and_ids(window):
    from spectramaster.gui.aptec_calibration_ui import EFFICIENCY, open_full_calibration
    window.display([_spectrum()], None, None)
    window.analysis_panel.peaks = [_peak(1323.3, "Cs-137", 661.657, 30.0)]
    w = open_full_calibration(window, EFFICIENCY)
    seen = []

    def hook(dlg):
        dlg.message = seen.append
        dlg.load_rois({"units": "Bq", "time": datetime(2023, 1, 1), "quantity": 1.0, "quantity_err": 0.0})
        dlg.ok_fit()                                 # no activity typed
        return dlg.result() == QDialog.Accepted

    assert not w.edit_points(EFFICIENCY, hook)
    assert seen and "no activity" in seen[0]
    w.close()


def test_load_rois_needs_identified_peaks(window):
    from spectramaster.gui.aptec_calibration_ui import ENERGY, PointsDialog
    window.display([_spectrum()], None, None)
    d = PointsDialog(None, ENERGY, [], "keV", window)
    seen = []
    d.message = seen.append
    assert d.load_rois() == 0 and "Analyze" in seen[0]


@pytest.mark.skipif(not (APTEC_DIR / "chern.s0").is_file(), reason="Aptec sample spectra not installed")
def test_aptec_file_shows_its_stored_calibration(window):
    from spectramaster.convert import read_spectra
    from spectramaster.gui.aptec_calibration_ui import EFFICIENCY, FullCalibrationWindow
    spec = read_spectra(APTEC_DIR / "chern.s0")[0][0]
    w = FullCalibrationWindow(None, spec, None, EFFICIENCY)
    assert w.efficiency is not None and w.efficiency.eff_type == "A" and len(w.eff_points) == 12
    assert "5th order ln-ln" in w.report.toPlainText()
    assert w.energy is not None and len(w.energy.channels) == 8
    w.dirty = False
    w.close()


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_windows_render_in_both_languages(window, lang):
    from spectramaster.gui.aptec_calibration_ui import (EFFICIENCY, CalcEfficiencyDialog, EfficiencyPointsDialog,
                                                        FullCalibrationWindow, QuickEnergyDialog)
    window.apply_language(lang, save=False)
    spec = _spectrum()
    for d in (QuickEnergyDialog(None, spec, None), FullCalibrationWindow(None, spec, None, EFFICIENCY),
              EfficiencyPointsDialog(None, [], "keV", "", "", None, spec), CalcEfficiencyDialog(None, None)):
        assert d.layoutDirection() == (Qt.RightToLeft if lang == "ar" else Qt.LeftToRight)
        assert not d.grab().isNull()
        d.dirty = False
        d.done(0)
    window.apply_language("en", save=False)


def test_calibration_windows_are_modal_like_aptec(window):
    """The main window cannot be used while a calibration window is open (Aptec: modal dialog;
    the marker is placed before calibrating)."""
    from PySide6.QtCore import Qt

    from spectramaster.gui.aptec_calibration_ui import ENERGY, open_full_calibration, open_quick_energy
    window.display([_spectrum(())], None, None)
    for d in (open_quick_energy(window), open_full_calibration(window, ENERGY)):
        assert d.windowModality() == Qt.ApplicationModal and d.isVisible()
        d.close()


def test_quick_energy_keeps_its_points_when_reopened(window):
    """Modal like Aptec: the next peak is added by reopening the window, so the points stay."""
    from spectramaster.gui.aptec_calibration_ui import open_quick_energy
    window.display([_spectrum(())], None, None)
    d = open_quick_energy(window)
    d.message = lambda text: (_ for _ in ()).throw(AssertionError(text))
    d.table.setItem(0, 0, QTableWidgetItem("2346.5"))
    d.table.setItem(0, 1, QTableWidgetItem("1173.228"))
    d.table.setItem(1, 0, QTableWidgetItem("2665.0"))
    d.table.setItem(1, 1, QTableWidgetItem("1332.492"))
    assert d.ok() is not None
    again = open_quick_energy(window)
    assert again.points() == [(pytest.approx(2346.5), pytest.approx(1173.228)),
                              (pytest.approx(2665.0), pytest.approx(1332.492))]
    again.close()

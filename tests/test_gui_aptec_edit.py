"""Aptec-style Edit and Display menus (headless)."""
from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDateTime, QPoint, QSettings, Qt
from PySide6.QtGui import QGuiApplication, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from spectramaster.gui import i18n
from spectramaster.model import Spectrum

APTEC_DIR = Path(os.environ.get("SPECTRAMASTER_APTEC_DIR", r"C:\APTEC\APTEC"))


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


@pytest.fixture()
def window(qapp, tmp_path, monkeypatch):
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.settings import Settings
    monkeypatch.setenv("SPECTRAMASTER_CERT_DIR", str(tmp_path / "certs"))
    monkeypatch.setenv("SPECTRAMASTER_EFF_DIR", str(tmp_path / "eff"))
    i18n.set_language("en")
    w = MainWindow(Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)))
    w.errors, w.infos = [], []
    w.show_error = w.errors.append
    w.show_info = w.infos.append
    yield w
    w.close()
    w.deleteLater()
    QApplication.processEvents()
    i18n.set_language("en")


def _spectrum(n=1024):
    counts = [100.0 + 1000.0 * math.exp(-0.5 * ((i - 300) / 3.0) ** 2) for i in range(n)]
    return Spectrum(counts=counts, energy_coeffs=[0.0, 0.5], fwhm_coeffs=[1.0, 0.001], live_time=100.0,
                    real_time=110.0, start_time=datetime(2024, 5, 1, 9, 0, 0), sample_id="S1", description="soil",
                    detector="HPGe-1", extra={"quantity": 0.5, "quantity_units": "kg"})


def _show(window, spec=None):
    window.display([spec or _spectrum()], None, None)
    window.plot.resize(1000, 400)
    return window.plot


def _items(menu):
    return [a.text().replace("&", "") for a in menu.actions() if not a.isSeparator()]


def _shown(window):
    return window._spectra[window._index]


def test_menus_like_aptec(window):
    titles = [a.text().replace("&", "") for a in window.menuBar().actions()]
    assert titles[:4] == ["File", "Edit", "Display", "Setup"]
    assert _items(window.menu_edit) == [
        "Select All", "Select Region", "Copy to ClipBrd", "Clear Selection", "Sample Description...",
        "Quantity Description...", "Spectrum Data...", "Certificate", "Library", "Decay Correction Calculation",
        "Load Header Information...", "Load File into MCArd...", "Reset Header..."]
    assert _items(window.menu_display) == ["Normal Spectrum", "Intermediate Spectrum", "Stabilized Spectrum",
                                           "Energy Calibration", "Resolution Calibration", "Efficiency Calibration"]
    assert window.act_e_copy.shortcut() == QKeySequence("Ctrl+Ins")
    assert window.act_e_clear_sel.shortcut() == QKeySequence("Ctrl+Del")
    assert window.act_e_sample.shortcut() == QKeySequence("F5")
    assert window.act_e_quantity.shortcut() == QKeySequence("F6")
    assert window.act_analyze.shortcut() == QKeySequence("P")
    for a in (window.act_e_load_mcard, window.act_d_intermediate, window.act_d_stabilized):
        assert not a.isEnabled()                       # acquisition hardware
    assert window.act_d_normal.isChecked()


def test_select_copy_clear(window):
    plot = _show(window)
    assert not window.act_e_copy.isEnabled()
    window.act_e_select_all.trigger()
    assert plot.selection is not None and window.act_e_copy.isEnabled()
    QGuiApplication.clipboard().clear()
    window.act_e_copy.trigger()
    img = QGuiApplication.clipboard().image()
    assert not img.isNull() and img.width() >= 300 and img.height() >= 200
    window.act_e_clear_sel.trigger()
    assert plot.selection is None and not window.act_e_copy.isEnabled()
    window.act_e_select_region.trigger()
    assert plot.select_region_mode
    x0 = plot.x0, plot.x1
    r = plot.plot_rect()
    a_pt = QPoint(int(r.left()) + 10, int(r.top()) + 10)
    b_pt = QPoint(int(r.left() + r.width() / 2), int(r.top() + r.height() / 2))
    QTest.mousePress(plot, Qt.LeftButton, Qt.NoModifier, a_pt)
    QTest.mouseMove(plot, b_pt)
    QTest.mouseRelease(plot, Qt.LeftButton, Qt.NoModifier, b_pt)
    assert (plot.x0, plot.x1) == x0                     # selected, not zoomed
    sel = plot.selection
    w, h = b_pt.x() - a_pt.x(), b_pt.y() - a_pt.y()
    assert sel is not None and abs(sel.width() - w) <= 2 and abs(sel.height() - h) <= 2
    img = plot.selection_image()
    assert abs(img.width() - w) <= 2
    assert not plot.grab().isNull()


def test_sample_and_quantity_description(window):
    from spectramaster.gui import aptec_edit_ui as ui
    _show(window)
    spec = _shown(window)
    dlg = ui.SampleDescriptionDialog(spec)
    assert dlg.title.text() == "soil" and dlg.label.text() == "S1" and dlg.detector.text() == "HPGe-1"
    dlg.user.setText("EF")
    dlg.geometry.setText("Marinelli1L")
    dlg.times["sample_start"][0].setChecked(True)
    dlg.times["sample_start"][1].setDateTime(QDateTime(datetime(2024, 4, 30, 8, 0)))
    new = dlg.apply_to(spec)
    assert new.extra["geometry_id"] == "Marinelli1L" and new.extra["user_id"] == "EF"
    assert new.extra["sample_start"] == "2024-04-30 08:00:00" and "sample_stop" not in new.extra
    assert spec.extra.get("geometry_id") is None             # the original is not changed
    dlg.clear()
    cleared = dlg.apply_to(spec)
    assert cleared.sample_id == "" and "user_id" not in cleared.extra
    q = ui.QuantityDescriptionDialog(spec)
    assert q.fields["quantity"][0].value() == pytest.approx(0.5) and q.qty_units.currentText() == "kg"
    q.fields["quantity"][0].setValue(0.75)
    q.fields["quantity"][1].setValue(1.5)
    q.fields["w_const"][0].setValue(2.0)
    q.fields["w_const"][2].setText("dry/wet")
    q.act_units.setCurrentText("kBq")
    new = q.apply_to(spec)
    assert new.extra["quantity"] == 0.75 and new.extra["quantity_err_pct"] == 1.5
    assert new.extra["w_const"] == 2.0 and new.extra["w_const_units"] == "dry/wet"
    assert new.extra["activity_units"] == "kBq" and new.extra["quantity_units"] == "kg"


def test_dialogs_through_the_menu(window, monkeypatch):
    from spectramaster.gui import aptec_edit_ui as ui
    plot = _show(window)
    plot.add_roi(285, 315)

    def accept_sample(self):
        self.title.setText("new title")
        return QDialog.Accepted
    monkeypatch.setattr(ui.SampleDescriptionDialog, "exec", accept_sample)
    window.act_e_sample.trigger()
    assert _shown(window).description == "new title"
    assert len(plot.rois) == 1                               # ROIs survive the header edit

    def accept_data(self):
        self.live.setValue(90.0)
        return QDialog.Accepted
    monkeypatch.setattr(ui.SpectrumDataDialog, "exec", accept_data)
    window.act_e_spc_data.trigger()
    assert _shown(window).live_time == 90.0 and _shown(window).extra["stop_time"] == "2024-05-01 09:01:50"
    d = ui.SpectrumDataDialog(_shown(window))
    d.live.setValue(500.0)
    from PySide6.QtWidgets import QDialogButtonBox
    assert not d.bb.button(QDialogButtonBox.Ok).isEnabled()  # live > true


def test_reset_header(window, monkeypatch):
    plot = _show(window)
    plot.add_roi(285, 315)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Cancel)
    window.act_e_reset_header.trigger()
    assert _shown(window).energy_coeffs and plot.rois
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Ok)
    window.act_e_reset_header.trigger()
    s = _shown(window)
    assert not s.energy_coeffs and not s.fwhm_coeffs and not plot.rois
    assert s.sample_id == "" and "quantity" not in s.extra
    assert s.live_time == 100.0 and sum(s.counts) > 0


def test_decay_calculator_and_library(window):
    from spectramaster.gui import aptec_edit_ui as ui
    d = ui.DecayDialog(window)
    d.a_val.setValue(1.0)
    assert "37000" in d.a_out.text()
    d.nuclide.setCurrentText("Cs-137")
    assert d.hl_unit.currentText() == "y" and d.hl.value() == pytest.approx(30.08, rel=0.01)
    d.act.setValue(1000.0)
    d.t0.setDateTime(QDateTime(datetime(2000, 1, 1)))
    d.t1.setDateTime(QDateTime(datetime(2030, 1, 1)))
    assert d.result == pytest.approx(1000 * 0.5 ** (30 * 365.25 / (d.hl.value() * 365.25)), rel=0.01)
    lib = ui.LibraryDialog(window)
    rows = lib.rows("cs-137")
    assert any(abs(e - 661.66) < 0.1 for _n, _h, e, _i in rows)
    assert all(n.lower() == "cs-137" for n, *_ in rows)
    assert any(n == "Cs-137" for n, *_ in lib.rows("661.6"))
    assert ui.parse_half_life("30.08 y") == pytest.approx(30.08 * 365.25 * 86400)
    assert ui.parse_half_life("5.27y") == pytest.approx(5.27 * 365.25 * 86400)
    assert ui.parse_half_life("") is None
    with pytest.raises(ValueError):
        ui.parse_half_life("long")
    assert ui.format_half_life(3600 * 2) == "2 h"


def test_certificate_editor_and_efficiency_points(window, tmp_path):
    from spectramaster.analysis.certificate import Certificate, list_certificates
    from spectramaster.gui import aptec_edit_ui as ui
    from spectramaster.gui.aptec_calibration_ui import EfficiencyPointsDialog
    from spectramaster.analysis import Peak
    dlg = ui.CertificateDialog(window)
    dlg.name.setText("Cs source")
    dlg.units.setCurrentText("kBq")
    dlg.time.setDateTime(QDateTime(datetime(2024, 1, 1)))
    dlg.add_line()
    dlg.table.item(0, 0).setText("Cs-137")
    dlg.table.selectRow(0)
    dlg.lines_from_library()
    assert float(dlg.table.item(0, 1).text()) == pytest.approx(661.657, abs=0.01)
    dlg.table.item(0, 4).setText("12.5")
    dlg.table.item(0, 5).setText("1.8")
    path = dlg.save()
    assert path is not None and list_certificates() == [path]
    cert = Certificate.load(path)
    assert cert.units == "kBq" and cert.lines[0].activity == 12.5 and cert.lines[0].half_life_s > 9e8
    # the efficiency calibration takes the activities from the certificate
    pk = Peak(centroid=1323.0, energy=661.6, fwhm=4.0, fwhm_kev=2.0, net_area=50000.0, net_area_unc=300.0,
              gross_area=0, background=0, left=1310, right=1336, significance=90, count_rate=50.0,
              nuclide="Cs-137", line_energy=661.657)
    e = EfficiencyPointsDialog(None, [], "keV", "HPGe", "Bottle", window, _spectrum())
    import spectramaster.gui.aptec_calibration_ui as cal
    old = cal._peaks
    cal._peaks = lambda win: [pk]
    try:
        n = e.load_rois({"units": "Bq", "time": None, "quantity": 1.0, "quantity_err": 0.0,
                         "certificate": str(path)})
    finally:
        cal._peaks = old
    assert n == 1
    p = e.points[0]
    assert p.activity == 12.5 and p.activity_err == 1.8 and p.activity_units == "kBq"
    assert p.activity_time == datetime(2024, 1, 1)


@pytest.mark.skipif(not (APTEC_DIR / "chern.s0").is_file(), reason="Aptec sample spectra not installed")
def test_load_header_and_calibration_display(window, tmp_path):
    from spectramaster.convert import read_spectra
    from spectramaster.gui import aptec_edit_ui as ui
    src = APTEC_DIR / "chern.s0"
    spec = read_spectra(src)[0][0]
    plain = Spectrum(counts=list(spec.counts), live_time=10.0, real_time=11.0)
    plot = _show(window, plain)
    got = ui.load_header(window, str(src), {"energy", "res", "rois", "sample"})
    assert got == {"energy", "res", "rois", "sample"}
    s = _shown(window)
    assert s.energy_coeffs == spec.energy_coeffs and s.sample_id == spec.sample_id
    assert s.live_time == 10.0                                 # Spectrum Data not loaded
    assert len(plot.rois) >= 17
    # Display > Energy Calibration with the points Aptec stored
    window.act_d_energy.trigger()
    assert window.display_kind == "energy" and window.cal_display.isVisibleTo(window)
    assert not window.plot.isVisibleTo(window)
    n = len(window.cal_display.data["points"])
    assert n >= 2 and window.cal_display.index == 0
    window.act_roi_next.trigger()
    assert window.cal_display.index == 1
    window.act_roi_prev.trigger()
    window.act_roi_prev.trigger()
    assert window.cal_display.index == n - 1
    assert "Point" in window.cal_display.point_text()
    assert not window.cal_display.grab().isNull()
    window.act_d_normal.trigger()
    assert window.display_kind is None and window.plot.isVisibleTo(window)
    window.act_roi_next.trigger()                            # Space indexes ROIs again
    assert plot.roi_index >= 0


@pytest.mark.skipif(not (APTEC_DIR / "co60cal.s0").is_file(), reason="Aptec sample spectra not installed")
def test_efficiency_display_and_load(window, tmp_path, monkeypatch):
    from spectramaster.gui import aptec_edit_ui as ui
    files = [p for p in sorted(APTEC_DIR.glob("*.s0"))
             if (ui.read_header_source(p).get("aptec") or {}).get("efficiency") is not None]
    if not files:
        pytest.skip("no Aptec sample with an efficiency calibration")
    from spectramaster.convert import read_spectra
    spec = read_spectra(files[0])[0][0]
    _show(window, spec)
    window.act_d_eff.trigger()
    d = window.cal_display.data
    assert d is not None and d["log"] and d["points"]
    assert not window.cal_display.grab().isNull()
    window.act_d_normal.trigger()
    got = ui.load_header(window, str(files[0]), {"eff"})
    assert got == {"eff"}
    assert list((tmp_path / "eff").glob("*.json"))


def test_calibration_display_without_calibration(window):
    from spectramaster.gui import aptec_edit_ui as ui
    s = _spectrum()
    s.energy_coeffs = []
    _show(window, s)
    window.act_d_energy.trigger()
    assert window.cal_display.data is None
    assert not window.cal_display.grab().isNull()
    assert ui.calibration_data(_spectrum(), ui.RESOLUTION)["curve"](100.0) == pytest.approx(1.1)


def test_arabic_menus(window):
    window.apply_language("ar", save=False)
    assert window.menu_edit.title().replace("&", "") == "تحرير"
    assert window.menu_display.title().replace("&", "") == "عرض الطيف"
    assert window.act_e_sample.text().replace("&", "") == "وصف العينة..."
    window.apply_language("en", save=False)

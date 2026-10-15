"""Energy-calibration review and drift-check dialogs (Release B, B1 GUI; headless)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from spectramaster.gui import i18n
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE


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
    w.close()
    w.deleteLater()
    QApplication.processEvents()
    i18n.set_language("en")


def wait_idle(dlg, timeout=120.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QApplication.processEvents()
        if not dlg.busy:
            QApplication.processEvents()
            return True
        time.sleep(0.01)
    return False


def _eu152():
    return next(scenarios.calibration_source(HPGE, "Eu-152", 1, category="unit")).spectrum


def _dialog(spec, source, win=None):
    from spectramaster.gui.calibration_dialog import CalibrationDialog
    dlg = CalibrationDialog(win, spec, win)
    dlg.msgs = []
    dlg.message = dlg.msgs.append
    dlg.source_edit.setText(source)
    assert dlg.propose()
    assert wait_idle(dlg)
    assert dlg.proposal is not None, dlg.last_error
    return dlg


def test_proposal_lists_points_and_toggling_refits(qapp):
    i18n.set_language("en")
    dlg = _dialog(_eu152(), "Eu-152")
    n = len(dlg.points)
    assert n >= 5 and dlg.table.rowCount() == n
    assert dlg.validation.ok and dlg.btn_accept.isEnabled()
    assert "·ch" in dlg.energy_label.text()
    coeffs = list(dlg.fit.coeffs)
    # exclude a point with a reason: refit through fit_points, reason shown, Accept still allowed
    assert dlg.set_point_used(1, False, reason="suspected blend")
    assert not dlg.points[1].used and dlg.fit.coeffs != coeffs
    assert "suspected blend" in dlg.table.item(1, 8).text()
    assert dlg.table.item(1, 0).checkState() == Qt.Unchecked
    assert dlg.validation.n_used == n - 1
    # the checkbox path: an empty reason is refused and the point stays in the fit
    dlg.ask_reason = lambda label: ""
    dlg.table.item(2, 0).setCheckState(Qt.Unchecked)
    for _ in range(5):
        QApplication.processEvents()
    assert dlg.points[2].used and dlg.msgs
    # re-include: back to the proposal
    dlg.table.item(1, 0).setCheckState(Qt.Checked)
    for _ in range(5):
        QApplication.processEvents()
    assert dlg.points[1].used
    assert dlg.fit.coeffs == pytest.approx(coeffs, rel=1e-9, abs=1e-12)
    # explicit order: refit with order 2
    dlg.order_combo.setCurrentIndex(dlg.order_combo.findData(2))
    assert dlg.fit.order == 2
    dlg.resize(1000, 700)
    assert not dlg.grab().isNull()
    dlg.close()


def test_validation_errors_block_accept(qapp):
    wrong = next(scenarios.calibration_source(HPGE, "Co-60,Cs-137", 1, category="unit")).spectrum
    dlg = _dialog(wrong, "Eu-152")
    assert not dlg.validation.ok and dlg.validation.errors
    assert not dlg.btn_accept.isEnabled() and dlg.blocked_label.isVisibleTo(dlg)
    assert dlg.accept_calibration() is None
    assert dlg.result_spectrum is None and wrong.energy_coeffs == []
    assert any(dlg.messages.item(i).text().startswith("ERROR") for i in range(dlg.messages.count()))
    dlg.close()


def test_source_change_requires_new_proposal(qapp):
    dlg = _dialog(_eu152(), "Eu-152")
    dlg.source_edit.setText("Co-60")
    assert not dlg.btn_accept.isEnabled() and dlg.accept_calibration() is None
    dlg.close()


def test_accept_sets_coefficients_but_not_counts(window):
    from spectramaster.gui.calibration_dialog import open_calibration_dialog
    spec = _eu152()
    counts = list(spec.counts)
    window.display([spec], None, None)
    dlg = open_calibration_dialog(window, modal=False)
    dlg.message = lambda text: None
    dlg.source_edit.setText("Eu-152")
    dlg.propose()
    assert wait_idle(dlg) and dlg.validation.ok
    new = dlg.accept_calibration()
    shown = window.current_spectrum()
    assert new is not None and shown is new
    assert shown.energy_coeffs == pytest.approx(dlg.fit.coeffs)
    assert list(shown.counts) == counts and list(spec.counts) == counts
    assert spec.energy_coeffs == []                       # the original object is untouched
    assert "Eu-152" in shown.extra["recalibrated"]
    assert "Validation: OK" in shown.extra["calibration_validation"]
    assert window.plot.has_energy()


def test_drift_correction_requires_confirmation(window):
    from spectramaster.gui.calibration_dialog import open_drift_dialog
    spec = next(scenarios.calibration_drift(HPGE, 0.003, 1)).spectrum
    old = list(spec.energy_coeffs)
    window.display([spec], None, None)
    dlg = open_drift_dialog(window, modal=False)
    dlg.message = lambda text: None
    assert dlg.check() and wait_idle(dlg)
    r = dlg.result
    assert r is not None and r.detected and dlg.btn_apply.isEnabled()
    assert dlg.table.rowCount() == len(r.points)
    assert window.current_spectrum().energy_coeffs == old        # nothing applied by the check
    asked = []
    dlg.confirm = lambda title, text: asked.append(text) or False
    assert dlg.apply_correction() is None and asked
    assert window.current_spectrum().energy_coeffs == old
    dlg.confirm = lambda title, text: True
    new = dlg.apply_correction()
    assert new is not None and window.current_spectrum() is new
    assert new.energy_coeffs == pytest.approx(r.proposed_coeffs)
    assert list(new.counts) == list(spec.counts) and spec.energy_coeffs == old
    assert "drift correction" in new.extra["recalibrated"]


def test_drift_needs_a_calibrated_spectrum(window):
    from spectramaster.gui.calibration_dialog import open_drift_dialog
    assert open_drift_dialog(window, modal=False) is None and window.infos       # no spectrum
    window.display([_eu152()], None, None)                                     # uncalibrated
    assert open_drift_dialog(window, modal=False) is None and len(window.infos) == 2


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_actions_and_language_switch(window, lang):
    from spectramaster.gui.calibration_dialog import CalibrationDialog, DriftDialog
    from spectramaster.gui.calibration_strings import ctr
    window.apply_language(lang, save=False)
    acts = window.menu_setup_advanced.actions()      # Setup > Advanced Calibration Tools
    assert window.act_calibrate in acts and window.act_drift in acts
    assert window.act_calibrate.text() == i18n.STRINGS[lang]["calib_act_cal"]
    spec = next(scenarios.calibration_drift(HPGE, 0.003, 1)).spectrum
    for cls in (CalibrationDialog, DriftDialog):
        dlg = cls(window, spec, window)
        assert dlg.layoutDirection() == (Qt.RightToLeft if lang == "ar" else Qt.LeftToRight)
        dlg.resize(900, 600)
        assert not dlg.grab().isNull()
        dlg.close()
    dd = DriftDialog(window, spec, window)
    dd.message = lambda text: None
    dd.check()
    assert wait_idle(dd)
    assert ctr("drift_detected") in dd.state_label.text()
    assert not dd.grab().isNull()
    dd.close()
    window.apply_language("en" if lang == "ar" else "ar", save=False)
    other = "en" if lang == "ar" else "ar"
    assert window.act_drift.text() == i18n.STRINGS[other]["calib_act_drift"]

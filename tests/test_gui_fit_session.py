"""Fit-inspection and manual-refit window (Release B, B2/B3 GUI; headless)."""
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
from spectramaster.validation.synthetic import HPGE, Continuum, TruePeak, make_spectrum

CONT = Continuum(exp_amp=300, exp_scale_kev=400, flat=10)


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
    if w.fit_window is not None:
        w.fit_window.close()
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


def _doublet():
    fw = float(HPGE.fwhm_kev(662.0))
    truth = [TruePeak(662.0, 1.0e5), TruePeak(662.0 + 1.6 * fw, 1.0e4), TruePeak(1332.0, 5e4)]
    return make_spectrum(HPGE, truth, CONT, seed=7).spectrum, HPGE.channel(662.0 + 1.6 * fw)


def _open(window, spec):
    from spectramaster.gui.fit_inspection import open_fit_inspection
    window.display([spec], None, None)
    dlg = open_fit_inspection(window, show=False)
    dlg.msgs = []
    dlg.message = dlg.msgs.append
    assert wait_idle(dlg) and dlg.report is not None, dlg.last_error
    return dlg


def test_groups_and_discarded_reasons_are_shown(window):
    from spectramaster.gui.session_strings import ftr
    spec = None
    for syn in scenarios.compton_edge(HPGE, 6):
        from spectramaster.analysis import inspect_fit
        if inspect_fit(syn.spectrum)[1].discarded():
            spec = syn.spectrum
            break
    assert spec is not None
    dlg = _open(window, spec)
    rep = dlg.report
    assert dlg.group_list.count() == len(rep.groups) > 0
    disc = rep.discarded()
    assert dlg.disc_table.rowCount() == len(disc) > 0
    for r in range(dlg.disc_table.rowCount()):
        assert dlg.disc_table.item(r, 4).text()                   # every discarded one has its reason
    # a group with a discarded component: the component table shows it as not reported, with reason
    g, _c = disc[0]
    row = next(k for k, (gg, _o) in enumerate(dlg.displayed_groups()) if gg is g)
    dlg.group_list.setCurrentRow(row)
    assert dlg.plot.group is g
    assert dlg.comp_table.rowCount() == len(g.components)
    no = [r for r in range(dlg.comp_table.rowCount()) if dlg.comp_table.item(r, 6).text() == ftr("no")]
    assert no and all(dlg.comp_table.item(r, 7).text() for r in no)
    assert "χ²/ν" in dlg.chi2_label.text()
    dlg.resize(1200, 800)
    assert not dlg.grab().isNull()
    # the session was created from the inspected fit; nothing is stale yet
    assert window.fit_session is dlg.session and not dlg.is_stale()


def test_add_remove_undo_redo_and_stale_indicator(window):
    from spectramaster.analysis.manual import compare_peaks
    from spectramaster.gui.session_strings import ftr
    spec, c2 = _doublet()
    dlg = _open(window, spec)
    s = dlg.session
    n0 = len(s.results["peaks"])
    assert ftr("stale") not in dlg.stale_label.text()
    # add a peak at the shoulder (worker thread), as a recorded session edit
    dlg.reason_edit.setText("shoulder in the residuals")
    assert dlg.add_peak(c2) and wait_idle(dlg)
    assert not dlg.msgs, dlg.msgs
    op = dlg.last_op
    assert op.kind == "replace_peaks" and op.reason == "shoulder in the residuals"
    assert dlg.is_stale() and ftr("stale") in dlg.stale_label.text()
    assert dlg.peak_table.rowCount() == len(s.results["peaks"])
    assert any(abs(p["centroid"] - c2) < 1.0 for p in s.results["peaks"])
    # the manual fit replaces the automatic group of that region in the list
    assert any(origin == op.op_id for _g, origin in dlg.displayed_groups())
    rows = compare_peaks(op.before, op.after)
    changed = [r for r in rows if r["status"] != "unchanged"]
    assert dlg.cmp_table.rowCount() == len(changed) > 0
    n1 = len(s.results["peaks"])
    # remove: the reason is required
    i = next(k for k, p in enumerate(s.results["peaks"]) if abs(p["centroid"] - c2) < 1.0)
    dlg.ask_reason = lambda ch: "  "
    assert not dlg.remove_peak(i) and dlg.msgs
    assert len(s.results["peaks"]) == n1
    dlg.ask_reason = lambda ch: "judged a tail artefact"
    assert dlg.remove_peak(i) and wait_idle(dlg)
    assert len(s.results["peaks"]) == n1 - 1
    assert s.history.ops[-1].reason == "judged a tail artefact"
    # undo / redo through the window
    assert dlg.btn_undo.isEnabled() and not dlg.btn_redo.isEnabled()
    assert dlg.undo() and len(s.results["peaks"]) == n1
    assert dlg.undo() and len(s.results["peaks"]) == n0
    assert not dlg.is_stale() and ftr("stale") not in dlg.stale_label.text()
    assert not dlg.btn_undo.isEnabled() and dlg.btn_redo.isEnabled()
    assert dlg.redo() and len(s.results["peaks"]) == n1 and dlg.is_stale()
    # the main plot shows the edited peak list
    assert len(window.plot.peaks) == n1


def test_refit_region_with_options(window):
    spec, _c2 = _doublet()
    dlg = _open(window, spec)
    c = HPGE.channel(1332.0)
    g = next(gg for gg, _o in dlg.displayed_groups() if gg.lo <= c <= gg.hi)
    dlg.group_list.setCurrentRow([gg for gg, _o in dlg.displayed_groups()].index(g))
    dlg.fill_from_group()
    cents, fix = dlg.positions()
    assert len(cents) >= 1 and dlg.lo_spin.value() == g.lo and dlg.hi_spin.value() == g.hi
    dlg.pos_table.item(0, 1).setCheckState(Qt.Checked)
    dlg.width_combo.setCurrentIndex(dlg.width_combo.findData("model"))
    dlg.step_check.setChecked(False)
    assert dlg.refit_region() and wait_idle(dlg)
    assert not dlg.msgs, dlg.msgs
    d = dlg.last_op.details
    assert d["width"] == "model" and d["step"] is False and d["fix_centroids"][0] is True
    assert d["centroids"][0] == pytest.approx(cents[0])
    # no positions -> refused without an edit
    dlg.pos_table.setRowCount(0)
    n_ops = len(dlg.session.history.ops)
    assert not dlg.refit_region() and len(dlg.session.history.ops) == n_ops


def test_reopening_keeps_the_session_and_menu_action(window):
    from spectramaster.gui.fit_inspection import open_fit_inspection
    assert open_fit_inspection(window, show=False) is None and window.infos      # no spectrum yet
    spec, c2 = _doublet()
    dlg = _open(window, spec)
    assert dlg.add_peak(c2) and wait_idle(dlg)
    again = open_fit_inspection(window, show=False)
    assert again is dlg and again.session.history.can_undo()
    assert window.act_fit_inspect in window.menu_analyze.actions()


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_language_switch_renders(window, lang):
    from spectramaster.gui.fit_inspection import FitInspectionDialog
    window.apply_language(lang, save=False)
    assert window.act_fit_inspect.text() == i18n.STRINGS[lang]["fit_act_inspect"]
    spec, c2 = _doublet()
    window.display([spec], None, None)
    dlg = FitInspectionDialog(window, spec, window)
    dlg.message = lambda text: None
    assert dlg.layoutDirection() == (Qt.RightToLeft if lang == "ar" else Qt.LeftToRight)
    assert dlg.plot.layoutDirection() == Qt.LeftToRight
    assert dlg.run_inspection() and wait_idle(dlg)
    assert dlg.add_peak(c2) and wait_idle(dlg)
    dlg.resize(1200, 800)
    for k in range(dlg.tabs.count()):
        dlg.tabs.setCurrentIndex(k)
        assert not dlg.grab().isNull()
    assert i18n.STRINGS[lang]["fit_stale"] in dlg.stale_label.text()
    dlg.close()
    other = "en" if lang == "ar" else "ar"
    window.apply_language(other, save=False)
    assert window.act_fit_inspect.text() == i18n.STRINGS[other]["fit_act_inspect"]

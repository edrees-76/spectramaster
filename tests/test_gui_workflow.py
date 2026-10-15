"""GUI: workflow status panel, review and report record (Release F, F3a-c)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from spectramaster.gui import i18n
from spectramaster.lab.workflow import WorkflowStatus

from test_gui_session_io import analyse, spectrum_file


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


@pytest.fixture()
def window(qapp, tmp_path, monkeypatch):
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.settings import Settings
    monkeypatch.setenv("SPECTRAMASTER_EFF_DIR", str(tmp_path / "curves"))
    i18n.set_language("en")
    w = MainWindow(Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)))
    w.errors, w.infos = [], []
    w.show_error = w.errors.append
    w.show_info = w.infos.append
    yield w
    w.session_ctl.ask_save_changes = lambda: "discard"
    w.close()
    w.deleteLater()
    QApplication.processEvents()
    i18n.set_language("en")


def _rows(win):
    return win.session_ctl.panel.rows()


def _codes(win):
    return {code for _lv, code, _t in _rows(win)}


def test_panel_without_session_and_without_calibration(window, tmp_path):
    from spectramaster.gui.workflow_strings import wtr
    assert window.workflow_dock.widget() is window.session_ctl.panel
    assert [t for _l, _c, t in _rows(window)] == [wtr("panel_no_spectrum")]
    window.load_file(spectrum_file(tmp_path / "data"))
    rows = _rows(window)
    assert ("info", "calibration_required", wtr("msg_no_eff_cal")) in rows    # identification only
    assert ("info", "no_results", wtr("msg_no_results")) in rows
    assert any(c == "outside_validated_scope" and t == wtr("msg_geo_unrecorded") for _l, c, t in rows)
    # colours follow the level
    from spectramaster.gui.session_io import LEVEL_COLORS
    lst = window.session_ctl.panel.list
    for i in range(lst.count()):
        level = lst.item(i).data(0x0100)[1]
        assert lst.item(i).foreground().color().name() == LEVEL_COLORS[level]
    # Arabic
    window.apply_language("ar")
    assert ("info", "calibration_required", i18n.STRINGS["ar"]["wf_msg_no_eff_cal"]) in _rows(window)
    assert window.workflow_dock.windowTitle() == i18n.STRINGS["ar"]["wf_dock"]
    window.apply_language("en")


def test_review_refused_while_stale_then_reviewed(window, tmp_path):
    window.load_file(spectrum_file(tmp_path / "data"))
    analyse(window)
    ctl = window.session_ctl
    assert "not_reviewed" in _codes(window) and window.act_review.isEnabled()
    window.session.mark_stale("efficiency calibration changed")
    ctl.refresh()
    assert "results_stale" in _codes(window) and not window.act_review.isEnabled()
    asked = []
    ctl.ask_review = lambda name: asked.append(name) or ("A. Analyst", "")
    assert not ctl.review()
    assert not asked                                        # refused before asking
    from spectramaster.gui.workflow_strings import wtr
    assert window.errors[-1] == wtr("review_err_stale")
    # fresh results: an empty name is refused by the engine, translated
    analyse(window)
    ctl.ask_review = lambda name: ("  ", "")
    assert not ctl.review()
    assert window.errors[-1] == wtr("review_err_name")
    ctl.ask_review = lambda name: asked.append(name) or ("A. Analyst", "peaks checked")
    assert ctl.review()
    assert window.session.status["reviewed"] and window.session.status["review"]["note"] == "peaks checked"
    rows = [r for r in _rows(window) if r[1] == "reviewed"]
    assert rows and rows[0][0] == "ok" and "A. Analyst" in rows[0][2] and "peaks checked" in rows[0][2]
    assert window.settings.get("workflow/reviewer") == "A. Analyst"
    ctl.ask_review = lambda name: asked.append(name) or None
    ctl.review()
    assert asked[-1] == "A. Analyst"                        # the reviewer's name is remembered
    assert ctl.needs_saving()                               # a review is worth an unsaved-changes prompt


def test_report_record_written_with_warning_when_not_reportable(window, tmp_path):
    window.load_file(spectrum_file(tmp_path / "data"))
    analyse(window)
    ctl = window.session_ctl
    asked = []
    ctl.confirm = lambda title, text: asked.append(text) or False
    out = ctl.export_report(tmp_path / "r.json")             # identification only: reportable, no question
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert not asked and doc["format"] == "spectramaster-report-1" and doc["reportable"] is True
    assert doc["application"]["session_id"] == window.session.session_id
    assert len(doc["results"]["peaks"]) == len(window.analysis_panel.peaks)
    # an error status (here: a spectrum without energy calibration) asks first
    import copy
    from spectramaster.gui.calibration_dialog import replace_displayed_spectrum
    new = copy.deepcopy(window.current_spectrum())
    new.energy_coeffs = []
    replace_displayed_spectrum(window, new)
    assert ("error", "calibration_required") in {(lv, c) for lv, c, _t in _rows(window)}
    assert ctl.export_report(tmp_path / "r2.json") is None
    assert asked and '"reportable": false' in asked[-1] and not (tmp_path / "r2.json").exists()
    ctl.confirm = lambda title, text: True
    doc = json.loads(ctl.export_report(tmp_path / "r2.json").read_text(encoding="utf-8"))
    assert doc["reportable"] is False


def test_activity_results_enter_the_session_and_the_record(window, tmp_path):
    from spectramaster.gui.quant_panel import ActivityDialog
    from spectramaster.validation.benchmark import _flat_curve
    curve_path = _flat_curve().save(tmp_path / "curves" / "flat.json")
    window.load_file(spectrum_file(tmp_path / "data"))
    analyse(window)
    n_peaks = len(window.session.results["peaks"])
    ad = ActivityDialog(window, window.current_spectrum(), window.settings)
    ad.message = lambda text: setattr(ad, "last_error", text)
    ad.set_curve_path(curve_path)
    ad.nuc_edit.setText("Cs-137, K-40")
    ad.sample_box.set_matrix("soil")
    ad.sample_box.set_value("mass_kg", 1.0)
    assert ad.calculate() is not None, ad.last_error
    s = window.session
    assert s.results["quant"] and [r["nuclide"] for r in s.results["quant"]["nuclides"]] == ["Cs-137", "K-40"]
    assert len(s.results["peaks"]) == n_peaks                       # the peaks are kept
    assert {c["kind"] for c in s.calibrations} == {"energy", "efficiency"}
    assert "calibration_required" not in _codes(window)
    ctl = window.session_ctl
    ctl.confirm = lambda title, text: True
    doc = json.loads(ctl.export_report(tmp_path / "r.json").read_text(encoding="utf-8"))
    assert [a["nuclide"] for a in doc["results"]["activities"]] == ["Cs-137", "K-40"]
    assert doc["results"]["concentrations"] == json.loads(json.dumps(window.quant_concentration, default=str)) \
        or window.quant_concentration is None
    ad.close()
    # the stored activities come back as they were saved (no recalculation)
    from test_gui_session_io import _make_window
    out = tmp_path / "q.smsession"
    assert ctl.save_session_to(out)
    w2 = _make_window(tmp_path, "s3.ini")
    try:
        assert w2.session_ctl.open_session(out), w2.errors
        q = w2.quant_results
        assert q is not None and [r.nuclide for r in q.nuclides] == ["Cs-137", "K-40"]
        assert [r.activity for r in q.nuclides] == [r.activity for r in window.quant_results.nuclides]
    finally:
        w2.session_ctl.ask_save_changes = lambda: "discard"
        w2.close()


def test_status_texts_translate_known_messages_and_keep_unknown():
    from spectramaster.gui.session_io import status_text
    from spectramaster.gui.workflow_strings import wtr
    i18n.set_language("en")
    cases = [
        ("efficiency calibration 'Mar1L' belongs to another detector", "msg_other_detector"),
        ("efficiency calibration 'Mar1L' belongs to another geometry: fill volume differs", "msg_other_geometry_why"),
        ("efficiency calibration 'Mar1L' is unvalidated", "msg_eff_status"),
        ("efficiency extrapolated at 46.5, 2614.5 keV", "msg_extrapolated"),
        ("results require recalculation: set_context calibrations", "msg_stale"),
        ("reviewed by A on 2026-10-01T10:00:00Z: ok", "msg_reviewed_note"),
        ("reviewed by A on 2026-10-01T10:00:00Z", "msg_reviewed"),
    ]
    for msg, key in cases:
        out = i18n.strip_bidi(status_text(WorkflowStatus("x", "warning", msg)))
        head = wtr(key).split("{")[0]
        assert out.startswith(head), (msg, out)
    assert "Mar1L" in status_text(WorkflowStatus("x", "error", cases[0][0]))
    assert "not validated" in status_text(WorkflowStatus("x", "warning", cases[2][0]))
    assert status_text(WorkflowStatus("new_code", "info", "something new")) == "something new"


def test_english_arabic_key_parity():
    from spectramaster.gui import workflow_strings as ws
    assert set(ws.EN) == set(ws.AR)
    for k in ws.EN:
        assert ws.AR[k].strip(), k
        # the same placeholders in both languages
        import re
        assert set(re.findall(r"{(\w+)}", ws.EN[k])) == set(re.findall(r"{(\w+)}", ws.AR[k])), k

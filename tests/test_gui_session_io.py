"""GUI: analysis session open / save in the main window (A5)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from spectramaster.convert import resolve_format, write_spectrum
from spectramaster.gui import i18n
from spectramaster.validation.synthetic import HPGE, Continuum, TruePeak, make_spectrum


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


def _make_window(tmp_path, name="s.ini"):
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.settings import Settings
    w = MainWindow(Settings(QSettings(str(tmp_path / name), QSettings.IniFormat)))
    w.errors, w.infos = [], []
    w.show_error = w.errors.append
    w.show_info = w.infos.append
    return w


@pytest.fixture()
def window(qapp, tmp_path):
    i18n.set_language("en")
    w = _make_window(tmp_path)
    yield w
    w.session_ctl.ask_save_changes = lambda: "discard"
    w.close()
    w.deleteLater()
    QApplication.processEvents()
    i18n.set_language("en")


def spectrum_file(folder, name="sample.s0", seed=7, **kw):
    s = make_spectrum(HPGE, [TruePeak(661.657, 2e4), TruePeak(1460.8, 5e3)], Continuum(300, 400, 10), seed,
                      **kw).spectrum
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    write_spectrum(s, p, resolve_format("aptec_s0"))
    return p


def wait_until(cond, timeout=120.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QApplication.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def analyse(win):
    assert win.run_analysis()
    assert wait_until(lambda: not win.analysis_running())
    QApplication.processEvents()
    assert win.analysis_panel.peaks


def test_spectrum_gets_a_session(window, tmp_path):
    p = spectrum_file(tmp_path / "data")
    assert window.load_file(p)
    s = window.session
    assert s is not None and window.session_ctl.session is s
    assert s.spectrum_ref["path"] == str(p.resolve())
    assert [c["kind"] for c in s.calibrations] == ["energy"]          # the file's energy calibration
    assert not s.has_results()
    assert window.act_save_session.isEnabled() and not window.act_review.isEnabled()


def test_save_open_round_trip_with_results_and_history(window, tmp_path, qapp):
    p = spectrum_file(tmp_path / "data")
    window.load_file(p)
    analyse(window)
    s = window.session
    assert s.has_results() and len(s.results["peaks"]) == len(window.analysis_panel.peaks)
    s.set_peak_field(0, "note", "checked by eye", reason="visual check")    # undoable edit in the history
    out = tmp_path / "sessions" / "a.smsession"
    assert window.session_ctl.save_session_to(out)
    assert out.is_file() and not window.session_ctl.is_dirty()
    saved = s.state_dict()

    w2 = _make_window(tmp_path, "s2.ini")
    try:
        w2.act_auto_analyze.setChecked(True)              # must not recalculate an opened session
        assert w2.session_ctl.open_session(out), w2.errors
        assert not w2.analysis_running()
        s2 = w2.session
        assert s2.state_dict() == saved
        assert [op.kind for op in s2.history.ops] == [op.kind for op in s.history.ops]
        assert s2.status["results_stale"] is True        # the peak edit marked the results stale
        assert len(w2.analysis_panel.peaks) == len(saved["results"]["peaks"])
        assert w2.analysis_panel.peaks[0].note == "checked by eye"
        assert w2.session_ctl.path == out.resolve() or w2.session_ctl.path == out
        assert not w2.session_ctl.is_dirty()
        assert w2.infos and "require recalculation" in w2.infos[-1]
        assert not w2.act_review.isEnabled()
        codes = [code for _lv, code, _t in w2.session_ctl.panel.rows()]
        assert "results_stale" in codes
    finally:
        w2.session_ctl.ask_save_changes = lambda: "discard"
        w2.close()


def test_fresh_results_reopen_not_stale(window, tmp_path):
    p = spectrum_file(tmp_path / "data")
    window.load_file(p)
    analyse(window)
    out = tmp_path / "b.smsession"
    window.session_ctl.save_session_to(out)
    w2 = _make_window(tmp_path, "s3.ini")
    try:
        assert w2.session_ctl.open_session(out)
        assert w2.session.status["results_stale"] is False
        assert not w2.infos
        assert w2.act_review.isEnabled()
        assert w2.fit_session is w2.session               # manual refits continue the saved history
    finally:
        w2.close()


def test_relocated_and_missing_spectrum(window, tmp_path):
    p = spectrum_file(tmp_path / "data")
    window.load_file(p)
    out = tmp_path / "sessions" / "c.smsession"
    window.session_ctl.save_session_to(out)
    # moved next to the session file: found automatically by its SHA-256
    shutil.copy(p, out.parent / "renamed.s0")
    p.unlink()
    w2 = _make_window(tmp_path, "s4.ini")
    try:
        assert w2.session_ctl.open_session(out), w2.errors
        assert w2.session.spectrum_ref["path"] == str((out.parent / "renamed.s0").resolve())
        assert w2.session.history.ops[-1].kind == "relocate_spectrum"
    finally:
        w2.close()
    # elsewhere: the user is asked; a different file is refused, the right one accepted
    (out.parent / "renamed.s0").replace(tmp_path / "moved.s0")
    other = spectrum_file(tmp_path / "other", seed=99)
    w3 = _make_window(tmp_path, "s5.ini")
    try:
        ctl = w3.session_ctl
        ctl.confirm = lambda title, text: True
        ctl.ask_spectrum_file = lambda old: str(other)
        assert not ctl.open_session(out)
        assert w3.errors and "SHA-256" in w3.errors[-1] and w3.session is None
        ctl.ask_spectrum_file = lambda old: str(tmp_path / "moved.s0")
        assert ctl.open_session(out), w3.errors
        assert w3.session.spectrum_ref["path"] == str((tmp_path / "moved.s0").resolve())
    finally:
        w3.close()


def test_energy_calibration_change_is_stale_and_restored(window, tmp_path):
    from spectramaster.gui.calibration_dialog import replace_displayed_spectrum
    import copy
    p = spectrum_file(tmp_path / "data")
    window.load_file(p)
    analyse(window)
    new = copy.deepcopy(window.current_spectrum())
    new.energy_coeffs = [0.1, 0.5002]
    assert replace_displayed_spectrum(window, new)
    s = window.session
    assert s.status["results_stale"] and s.has_results()       # kept, flagged, not recalculated
    energy = [c for c in s.calibrations if c["kind"] == "energy"]
    assert len(energy) == 1 and energy[0]["params"] == [0.1, 0.5002]
    out = tmp_path / "d.smsession"
    window.session_ctl.save_session_to(out)
    w2 = _make_window(tmp_path, "s6.ini")
    try:
        assert w2.session_ctl.open_session(out)
        assert w2.current_spectrum().energy_coeffs == [0.1, 0.5002]
        assert w2.session.status["results_stale"]
    finally:
        w2.close()


def test_unsaved_changes_prompt(window, tmp_path):
    p = spectrum_file(tmp_path / "data")
    window.load_file(p)
    analyse(window)
    ctl = window.session_ctl
    assert not ctl.needs_saving()          # never saved, not reviewed: no prompt (as before sessions)
    ctl.save_session_to(tmp_path / "e.smsession")
    window.session.set_setting("note", "changed")
    assert ctl.needs_saving()
    asked = []
    ctl.ask_save_changes = lambda: asked.append(1) or "cancel"
    assert not window.load_file(p)
    assert asked and window.session is not None and window.session.processing_settings.get("note") == "changed"
    ctl.ask_save_changes = lambda: "save"
    assert window.load_file(p)
    from spectramaster.lab.session import AnalysisSession
    assert AnalysisSession.load(tmp_path / "e.smsession").processing_settings.get("note") == "changed"


def test_bad_session_file_is_a_message(window, tmp_path):
    bad = tmp_path / "bad.smsession"
    bad.write_text("{\"format\": \"something else\"}", encoding="utf-8")
    assert not window.session_ctl.open_session(bad)
    assert window.errors and "not a session" in window.errors[-1]
    newer = tmp_path / "newer.smsession"
    newer.write_text("{\"format\": \"spectramaster-session\", \"schema_version\": 99}", encoding="utf-8")
    assert not window.session_ctl.open_session(newer)
    assert "newer" in window.errors[-1]

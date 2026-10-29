"""Round-7 review, Gemini M2 (the partial summing warning reaches the concentrations, the report's
calibration record, the activity dialog and the Arabic status text) and M3 (QC exports waited for on
close; folder searches cancelled when their window closes)."""
from __future__ import annotations

import threading
import time

import pytest

from spectramaster.analysis import activity as act
from spectramaster.lab.sample import SampleInfo
from spectramaster.validation import round6_tcs_state as r6

PARTIAL = "partial true-coincidence summing correction"


@pytest.fixture(scope="module")
def curves():
    return r6._curves()


def test_concentrations_carry_the_partial_warning(curves):
    sample = SampleInfo(matrix_type="soil", mass_kg=2.0, mass_basis="dry")
    q = r6._quant(curves["eu_ba_121.8"]["loaded"], False)
    notes = act.concentrations(q, sample, "Bq/kg")["notes"]
    assert q.curve_tcs_partial and sum(PARTIAL in n for n in notes) == 1
    assert act.tcs_partial_note(q.curve_tcs_partial) in notes
    control = r6._quant(curves["eu_only"]["loaded"], False)
    assert not any(PARTIAL in n for n in act.concentrations(control, sample, "Bq/kg")["notes"])


def test_report_calibration_names_the_partial_points_of_the_calculation(curves):
    raw = curves["eu_ba_121.8"]["raw"]
    q = r6._quant(raw, True)                         # corrected in the activity calculation itself
    cal = r6._report(raw, q)["calibration"]
    assert q.curve_tcs_partial and cal["tcs_partial"] == q.curve_tcs_partial
    assert cal["tcs_partial_source"] == "activity calculation"
    loaded = curves["eu_ba_121.8"]["loaded"]
    cal = r6._report(loaded, r6._quant(loaded, False))["calibration"]
    assert cal["tcs_partial"] and cal["tcs_partial_source"] == "curve"
    ctrl = curves["eu_only"]["raw"]
    cal = r6._report(ctrl, r6._quant(ctrl, True))["calibration"]
    assert cal["tcs_partial"] == [] and cal["tcs_partial_source"] == ""


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_partial_status_is_translated(curves, lang):
    pytest.importorskip("PySide6")
    from spectramaster.gui.session_io import status_text
    from spectramaster.lab.workflow import WorkflowStatus
    loaded = curves["eu_ba_121.8"]["loaded"]
    st = [s for s in r6._report(loaded, r6._quant(loaded, False))["statuses"] if PARTIAL in s["message"]]
    assert len(st) == 1
    text = status_text(WorkflowStatus(**st[0]), lang)
    assert text != st[0]["message"] and "Ba-133" in text
    if lang == "ar":
        assert "التطابقي" in text


def test_activity_dialog_banner_shows_the_partial_warning(curves):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QLabel
    from spectramaster.gui import i18n
    from spectramaster.gui.quant_panel import ActivityDialog
    from spectramaster.gui.app import create_app
    create_app(["test"])
    q = r6._quant(curves["eu_ba_121.8"]["loaded"], False)

    class Holder:
        notes_label = QLabel()
    for lang, word in (("en", "partly corrected"), ("ar", "التطابقي")):
        i18n.set_language(lang)
        ActivityDialog._show_notes(Holder, q.notes)
        text = Holder.notes_label.text()
        assert word in text and all(f"{n} {e:g} keV" in text for n, e, *_w in q.curve_tcs_partial)
    i18n.set_language("en")


# ------------------------------------------------------------------ M3
def test_scans_stop_when_asked(tmp_path):
    from spectramaster.lab.batch import scan
    pytest.importorskip("PySide6")
    from spectramaster.gui.dialogs import scan_folder, scan_spectrum_files
    (tmp_path / "a.chn").write_bytes(b"x")
    for fn in (lambda s: scan_folder(tmp_path, True, None, s), lambda s: scan_spectrum_files(tmp_path, True, s),
               lambda s: scan([tmp_path / "a.chn"], s)):
        with pytest.raises(InterruptedError):
            fn(lambda: True)
    assert [p.name for p in scan_folder(tmp_path, True, None, lambda: False)] == ["a.chn"]


def _slow_folder(tmp_path, monkeypatch, n=300, dt=0.02):
    """A folder of `n` files of unknown extension whose content check takes `dt` s each."""
    import spectramaster.formats as fm
    d = tmp_path / "many"
    d.mkdir()
    for i in range(n):
        (d / f"f{i:03d}.xyz").write_bytes(b"x")
    real = fm.detect_format

    def slow(p, *a, **k):
        time.sleep(dt)
        return real(p, *a, **k)
    monkeypatch.setattr(fm, "detect_format", slow)
    return d


def test_closing_cancels_a_report_batch_folder_search(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QMessageBox
    from spectramaster.gui.report_dialogs import ReportBatchDialog
    from test_round4_ui_thread import wait_until
    from spectramaster.gui.app import create_app
    create_app(["test"])
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.append(a))
    d = _slow_folder(tmp_path, monkeypatch)
    dlg = ReportBatchDialog(_settings(tmp_path), [])
    assert dlg.add_folder(d)
    time.sleep(0.2)
    t0 = time.monotonic()
    dlg.close()                                     # 300 x 0.02 s left to search without a cancel
    assert time.monotonic() - t0 < 3.0
    assert wait_until(lambda: not dlg.is_running(), 10) and not shown and not dlg.files


def test_closing_cancels_a_batch_analysis_folder_search(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from spectramaster.gui.batch_analysis import BatchAnalysisDialog
    from test_round4_ui_thread import wait_until
    from spectramaster.gui.app import create_app
    create_app(["test"])
    d = _slow_folder(tmp_path, monkeypatch)
    dlg = BatchAnalysisDialog(None, _settings(tmp_path), [])
    dlg.message = lambda *a, **k: pytest.fail("no message on a cancelled search")
    assert dlg.add_folder(d)
    time.sleep(0.2)
    t0 = time.monotonic()
    dlg.close()
    assert time.monotonic() - t0 < 3.0
    assert wait_until(lambda: not dlg.is_running(), 10) and not dlg.busy


def test_cancelled_call_reports_nothing(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QObject
    from spectramaster.gui.worker import call_stop, cancel_calls, start_call, wait_threads
    from test_round4_ui_thread import wait_until
    from spectramaster.gui.app import create_app
    create_app(["test"])
    owner, seen, go = QObject(), [], threading.Event()
    stop = call_stop(owner)

    def work():
        go.wait(10)
        if stop():
            raise InterruptedError("cancelled")
        return 1
    start_call(owner, work, lambda r: seen.append(("done", r)), lambda m: seen.append(("failed", m)))
    cancel_calls(owner)
    go.set()
    wait_threads(owner)
    assert wait_until(lambda: not owner.__dict__.get("_call_threads"), 10) and seen == []


def test_qc_window_waits_for_its_exports_on_close(tmp_path):
    pytest.importorskip("PySide6")
    from spectramaster.gui.qc_window import QCWindow
    from spectramaster.tools import qc
    from spectramaster.gui.app import create_app
    create_app(["test"])
    w = QCWindow(store=qc.QCStore(tmp_path / "store"))
    w.set_track(qc.QCTrack(name="T", detector="D"))
    written = []

    def slow(track, path, ev):
        time.sleep(0.5)
        path.write_text("x", encoding="utf-8")
        written.append(path)
        return path
    w._export(slow, tmp_path / "out.txt")
    assert w.exports_running()
    w.close()                                       # waits for the export thread
    assert written and not any(t.isRunning() for t, _w in w.__dict__.get("_call_threads", []))


def _settings(tmp_path):
    from PySide6.QtCore import QSettings
    from spectramaster.gui import i18n
    from spectramaster.gui.settings import Settings
    i18n.set_language("en")
    return Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat))

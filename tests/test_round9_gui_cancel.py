"""Round-9 review.

Codex M2: a QC export (or import) that fails while its window closes is still waited for, but its
message no longer opens a dialog for the closed window; it goes to the main window's status bar.

Gemini L1: the batch-analysis scan drops a result or a failure that arrives after it was cancelled,
and ``lab.batch.scan`` checks its stop flag once more after the last file."""
from __future__ import annotations

import threading

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMainWindow

from spectramaster.gui import batch_analysis, qc_window
from spectramaster.tools import qc
from test_round4_ui_thread import qapp, settings, wait_until  # noqa: F401
from test_round8_scan_cancel import _deliver_after_cancel, _StopAfter


# ------------------------------------------------------------------ QC window (Codex M2)
@pytest.fixture()
def warnings_shown(monkeypatch):
    shown = []

    def warning(parent, *a, **k):
        shown.append(parent.isVisible())
        return None
    monkeypatch.setattr(qc_window.QMessageBox, "warning", warning)
    return shown


def _qc_window(tmp_path, main):
    w = qc_window.QCWindow(store=qc.QCStore(tmp_path / "store"), main_window=main)
    w.set_track(qc.QCTrack(name="T", detector="D"))
    w.show()
    return w


def _failing_export(gate, written):
    def fn(track, path, ev):
        gate.wait(30)
        written.append(path)
        raise OSError("disk full")
    return fn


def test_qc_export_failure_after_close_shows_no_dialog(qapp, tmp_path, warnings_shown):
    main = QMainWindow()
    w = _qc_window(tmp_path, main)
    try:
        gate, written = threading.Event(), []
        w._export(_failing_export(gate, written), tmp_path / "out.xlsx")
        assert w.exports_running()
        gate.set()
        w.close()                                   # still waits for the write
        assert written and not any(t.isRunning() for t, _w in w.__dict__.get("_call_threads", []))
        assert wait_until(lambda: not w.exports_running(), 10)
        QApplication.processEvents()
        assert warnings_shown == []
        assert "disk full" in main.statusBar().currentMessage()
    finally:
        w.close()
        main.close()


def test_qc_export_failure_while_open_still_warns(qapp, tmp_path, warnings_shown):
    w = _qc_window(tmp_path, None)
    try:
        w.close()
        w.show()                                    # reopened (open_qc_window keeps the window)
        gate, written = threading.Event(), []
        gate.set()
        w._export(_failing_export(gate, written), tmp_path / "out.pdf")
        assert wait_until(lambda: bool(warnings_shown), 10)
        assert warnings_shown == [True]
    finally:
        w.close()


def test_qc_import_errors_after_close_show_no_dialog(qapp, tmp_path, warnings_shown, monkeypatch):
    gate = threading.Event()

    def slow_import(track, paths, progress=None):
        gate.wait(30)
        return qc.ImportResult(errors=[("x.chn", "OSError: unreadable")])
    monkeypatch.setattr(qc_window.qc, "import_paths", slow_import)
    main = QMainWindow()
    w = _qc_window(tmp_path, main)
    try:
        w.add_paths([tmp_path / "x.chn"])
        gate.set()
        w.close()                                   # waits for the import thread
        assert wait_until(lambda: w.last_import is not None, 10)
        QApplication.processEvents()
        assert warnings_shown == []
        assert main.statusBar().currentMessage()
    finally:
        w.close()
        main.close()


# ------------------------------------------------------------------ batch analysis (Gemini L1)
def test_lab_scan_checks_stop_after_the_last_file(tmp_path):
    from spectramaster.lab.batch import scan
    paths = [tmp_path / f"missing{i}.chn" for i in range(3)]
    probe = _StopAfter(10 ** 9)
    assert len(scan(paths, probe)) == 3              # unreadable files are kept, with the reason
    with pytest.raises(InterruptedError):
        scan(paths, _StopAfter(len(paths)))         # stopped after the last file was read
    with pytest.raises(InterruptedError):
        scan(paths, _StopAfter(1))


def _late_scan(monkeypatch, outcome):
    gate = threading.Event()

    def slow(paths, tol, stop=None):
        gate.wait(30)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(batch_analysis, "_scan_and_group", slow)
    return gate


@pytest.mark.parametrize("outcome", [([], []), OSError("late failure")], ids=["result", "failure"])
def test_batch_analysis_scan_drops_a_late_outcome(qapp, settings, tmp_path, monkeypatch, outcome):
    dlg = batch_analysis.BatchAnalysisDialog(None, settings, [tmp_path / "a.chn"])
    messages = []
    dlg.message = lambda text: messages.append(text)
    sentinel = object()
    dlg.items = dlg.groups = sentinel
    try:
        gate = _late_scan(monkeypatch, outcome)
        assert dlg.scan() and dlg.busy
        _deliver_after_cancel(dlg, gate)
        QApplication.processEvents()
        assert dlg.items is sentinel and dlg.groups is sentinel
        assert messages == [] and not dlg.busy
        gate2 = _late_scan(monkeypatch, ([], []))   # a new scan is not dropped
        gate2.set()
        assert dlg.scan()
        assert wait_until(lambda: not dlg.busy, 10) and dlg.items == [] and dlg.groups == []
    finally:
        dlg.close()


def test_batch_analysis_folder_failure_not_dropped_by_an_old_scan(qapp, settings, tmp_path, monkeypatch):
    """A cancelled scan does not hide the failure of a later folder search."""
    from spectramaster.gui import dialogs
    dlg = batch_analysis.BatchAnalysisDialog(None, settings, [tmp_path / "a.chn"])
    messages = []
    dlg.message = lambda text: messages.append(text)
    try:
        gate = _late_scan(monkeypatch, ([], []))
        assert dlg.scan()
        _deliver_after_cancel(dlg, gate)

        def fail(*a, **k):
            raise OSError("folder gone")
        monkeypatch.setattr(dialogs, "scan_spectrum_files", fail)
        assert dlg.add_folder(tmp_path)
        assert wait_until(lambda: not dlg.busy, 10) and len(messages) == 1 and "folder gone" in messages[0]
    finally:
        dlg.close()

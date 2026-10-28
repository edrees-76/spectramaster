"""Round-6 review, Gemini M1: folder searches and QC exports off the GUI thread; dialogs wait for a
search before they close."""
from __future__ import annotations

import threading
import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from spectramaster.gui import dialogs, i18n


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


@pytest.fixture()
def settings(tmp_path):
    from spectramaster.gui.settings import Settings
    i18n.set_language("en")
    return Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat))


def wait_until(cond, timeout=60.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QApplication.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def _gated(monkeypatch, name):
    """Replace dialogs.<name> by a search that waits for the returned event (a slow folder)."""
    gate, real = threading.Event(), getattr(dialogs, name)

    def slow(*a, **k):
        gate.wait(30)
        return real(*a, **k)
    monkeypatch.setattr(dialogs, name, slow)
    return gate


def _folder(tmp_path):
    d = tmp_path / "data"
    (d / "sub").mkdir(parents=True)
    for p in (d / "a.chn", d / "sub" / "b.chn", d / "c.txt"):
        p.write_bytes(b"x")
    return d


def test_report_batch_search_counts_as_running(qapp, settings, tmp_path, monkeypatch):
    from spectramaster.gui.report_dialogs import ReportBatchDialog
    gate = _gated(monkeypatch, "scan_spectrum_files")
    dlg = ReportBatchDialog(settings, [])
    assert dlg.add_folder(_folder(tmp_path))
    assert dlg.is_running() and not dlg.start()
    dlg.reject()                                    # Esc is refused while the folder is searched
    assert dlg.result() == 0 and dlg.is_running()
    threading.Timer(0.3, gate.set).start()
    dlg.close()                                     # waits for the search
    assert not dlg.__dict__.get("_call_threads")
    assert wait_until(lambda: not dlg.is_running())


def test_convert_folder_searches_on_a_worker_thread(qapp, settings, tmp_path, monkeypatch):
    gate = _gated(monkeypatch, "scan_folder")
    d = _folder(tmp_path)
    dlg = dialogs.BatchDialog(settings=settings, folder_mode=True, folder=d)
    dlg.all_files_cb.setChecked(True)
    assert dlg.scanning and dlg.is_running() and not dlg.start_btn.isEnabled()
    dlg.recursive_cb.setChecked(False)              # changed meanwhile: searched again at the end
    assert dlg._rescan
    gate.set()
    assert wait_until(lambda: not dlg.is_running())
    assert sorted(p.name for p in dlg.model.files) == ["a.chn", "c.txt"]
    assert dlg.start_btn.isEnabled() == (dlg.out_combo.count() > 0)
    gate.clear()
    dlg.scan()
    assert dlg.scanning
    threading.Timer(0.3, gate.set).start()
    dlg.close()                                     # waits for the search, no question asked
    assert not dlg.__dict__.get("_call_threads")


def test_qc_exports_use_copies(qapp, tmp_path):
    from spectramaster.gui.qc_window import QCWindow
    from spectramaster.tools import qc
    w = QCWindow(store=qc.QCStore(tmp_path / "store"))
    try:
        w.set_track(qc.QCTrack(name="T", detector="D"))
        gate, seen = threading.Event(), []

        def slow(track, path, ev):
            gate.wait(30)
            seen.append(track.name)
            path.write_text("x", encoding="utf-8")
            return path
        p = w._export(slow, tmp_path / "out.txt")
        assert w.exports_running()
        w.track.name = "changed"
        gate.set()
        assert wait_until(lambda: not w.exports_running())
        assert seen == ["T"] and p.read_text(encoding="utf-8") == "x"
    finally:
        w.close()

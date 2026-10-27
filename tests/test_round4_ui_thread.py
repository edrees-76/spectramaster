"""Round-4 review, UI thread (R4-E): folder searches and the reference-peak measurement run on a
worker thread (a mixed folder of 6240 files took 81 s on the GUI thread)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from spectramaster.convert import resolve_format, write_spectrum
from spectramaster.gui import i18n
from spectramaster.model import Spectrum


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


def _folder(tmp_path):
    """Two spectra (one with an unknown extension, found from its content) and one other file."""
    d = tmp_path / "data"
    d.mkdir()
    s = Spectrum(counts=[float(10 + i % 7) for i in range(512)], live_time=100.0, real_time=101.0,
                 energy_coeffs=[0.0, 0.5])
    write_spectrum(s, d / "a.chn", resolve_format("ortec_chn"))
    write_spectrum(s, d / "b.txt", resolve_format("ascii2"))
    (d / "b.txt").rename(d / "b.xyz")
    (d / "notes.xyz").write_text("not a spectrum\n" * 20, encoding="utf-8")
    return d


def test_dropped_folder_is_searched_on_a_worker_thread(qapp, settings, tmp_path):
    from spectramaster.gui.app import MainWindow
    d = _folder(tmp_path)
    w = MainWindow(settings)
    try:
        w.handle_dropped([str(d), str(d / "a.chn")])
        assert not w._batch_dialogs                       # nothing yet: the search is running
        assert wait_until(lambda: bool(w._batch_dialogs))
        assert sorted(p.name for p in w._batch_dialogs[-1].model.files) == ["a.chn", "a.chn", "b.xyz"]
        w._batch_dialogs[-1].close()
    finally:
        w.close()
        w.deleteLater()


def test_batch_analysis_folder_is_searched_on_a_worker_thread(qapp, settings, tmp_path):
    from spectramaster.gui.batch_analysis import BatchAnalysisDialog
    d = _folder(tmp_path)
    dlg = BatchAnalysisDialog(None, settings, [])
    assert dlg.add_folder(d) and dlg.busy
    assert not dlg.add_folder(d)                          # one search at a time
    assert wait_until(lambda: not dlg.busy)
    assert sorted(p.name for p in dlg.paths) == ["a.chn", "b.xyz"]
    dlg.close()


def test_report_batch_folder_is_searched_on_a_worker_thread(qapp, settings, tmp_path):
    from spectramaster.gui.report_dialogs import ReportBatchDialog
    d = _folder(tmp_path)
    dlg = ReportBatchDialog(settings, [])
    assert dlg.add_folder(d) and dlg.scanning and not dlg.start_btn.isEnabled()
    assert wait_until(lambda: not dlg.scanning)
    assert sorted(p.name for p in dlg.files) == ["a.chn", "b.xyz"] and dlg.start_btn.isEnabled()
    dlg.close()

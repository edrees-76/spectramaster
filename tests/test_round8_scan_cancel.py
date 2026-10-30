"""Round-8 review, Codex M4: a cancelled folder search never returns a list (the single-folder
branch of scan_folder checks the stop flag too, and both branches check once more at the end), and
a search result that still reaches a window after its search was cancelled is dropped."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from spectramaster.gui import dialogs
from spectramaster.gui.dialogs import expand_spectrum_paths, scan_folder, scan_spectrum_files
from test_round4_ui_thread import qapp, settings, wait_until  # noqa: F401

N_FILES = 50


def _folder(tmp_path) -> Path:
    d = tmp_path / "many"
    (d / "sub").mkdir(parents=True)
    for i in range(N_FILES):
        (d / f"f{i:03d}.chn").write_bytes(b"x")
    (d / "sub" / "deep.chn").write_bytes(b"x")
    return d


class _StopAfter:
    """stop() that turns True on its (n+1)-th call; counts the calls."""

    def __init__(self, n: int):
        self.n, self.calls = n, 0

    def __call__(self) -> bool:
        self.calls += 1
        return self.calls > self.n


def test_single_folder_scan_stops_midway(tmp_path):
    d = _folder(tmp_path)
    stop = _StopAfter(10)
    with pytest.raises(InterruptedError):
        scan_folder(d, False, None, stop)
    assert stop.calls == 11                      # stopped at the entry after the 10th check


def test_scan_stops_when_already_cancelled(tmp_path):
    d = _folder(tmp_path)
    for recursive in (False, True):
        stop = _StopAfter(0)
        with pytest.raises(InterruptedError):
            scan_folder(d, recursive, None, stop)
        assert stop.calls == 1
        with pytest.raises(InterruptedError):
            scan_spectrum_files(d, recursive, _StopAfter(0))


def test_scan_cancelled_at_the_very_end(tmp_path):
    """A stop set after the last entry was looked at still cancels (the check after the loop)."""
    d = _folder(tmp_path)
    for recursive in (False, True):
        probe = _StopAfter(10 ** 9)
        assert len(scan_folder(d, recursive, None, probe)) == (N_FILES + 1 if recursive else N_FILES)
        with pytest.raises(InterruptedError):
            scan_folder(d, recursive, None, _StopAfter(probe.calls - 1))
    probe = _StopAfter(10 ** 9)
    scan_spectrum_files(d, False, probe)
    with pytest.raises(InterruptedError):
        scan_spectrum_files(d, False, _StopAfter(probe.calls - 1))
    probe = _StopAfter(10 ** 9)
    expand_spectrum_paths([d], False, probe)
    with pytest.raises(InterruptedError):
        expand_spectrum_paths([d], False, _StopAfter(probe.calls - 1))


def test_recursive_scan_stops_midway(tmp_path):
    d = _folder(tmp_path)
    with pytest.raises(InterruptedError):
        scan_folder(d, True, None, _StopAfter(2))     # root walked, stopped before "sub"


def test_scan_without_stop_unchanged(tmp_path):
    d = _folder(tmp_path)
    (d / "z.qqq").write_bytes(b"x")
    names = [p.name for p in scan_folder(d, False, None)]
    assert names == sorted(names, key=str.lower) and len(names) == N_FILES + 1
    assert [p.name for p in scan_folder(d, False, {".qqq"})] == ["z.qqq"]
    assert [p.name for p in scan_folder(d, True, {".chn"})][-1] == "deep.chn"
    assert len(scan_folder(d, True, None, lambda: False)) == N_FILES + 2
    assert [p.name for p in scan_spectrum_files(d, False, lambda: False)] == [f"f{i:03d}.chn" for i in range(N_FILES)]


# ------------------------------------------------------------------ callers
def _late_result(monkeypatch, name, files):
    """dialogs.<name> waits for the returned event, then returns `files` whatever its stop flag:
    the search ended just before it was cancelled, and its result is still on its way."""
    gate = threading.Event()

    def slow(*a, **k):
        gate.wait(30)
        return list(files)
    monkeypatch.setattr(dialogs, name, slow)
    return gate


def _deliver_after_cancel(owner, gate):
    from spectramaster.gui.worker import cancel_calls, wait_threads
    cancel_calls(owner)
    gate.set()
    wait_threads(owner)
    assert wait_until(lambda: not owner.__dict__.get("_call_threads"), 10)


def test_batch_dialog_drops_a_cancelled_search(qapp, settings, tmp_path, monkeypatch):
    d = _folder(tmp_path)
    gate = _late_result(monkeypatch, "scan_folder", [d / "f000.chn"])
    dlg = dialogs.BatchDialog(settings=settings, folder_mode=True, folder=d)
    try:
        assert dlg.scanning
        dlg.recursive_cb.setChecked(False)           # a rescan asked for meanwhile is dropped too
        _deliver_after_cancel(dlg, gate)
        assert dlg.model.files == [] and not dlg.scanning and not dlg._rescan
    finally:
        dlg.close()


def test_report_batch_dialog_drops_a_cancelled_search(qapp, settings, tmp_path, monkeypatch):
    from spectramaster.gui.report_dialogs import ReportBatchDialog
    d = _folder(tmp_path)
    gate = _late_result(monkeypatch, "scan_spectrum_files", [d / "f000.chn"])
    dlg = ReportBatchDialog(settings, [])
    try:
        assert dlg.add_folder(d)
        _deliver_after_cancel(dlg, gate)
        assert dlg.files == [] and not dlg.scanning
    finally:
        dlg.close()


def test_batch_analysis_dialog_drops_a_cancelled_search(qapp, settings, tmp_path, monkeypatch):
    from spectramaster.gui.batch_analysis import BatchAnalysisDialog
    d = _folder(tmp_path)
    gate = _late_result(monkeypatch, "scan_spectrum_files", [d / "f000.chn"])
    dlg = BatchAnalysisDialog(None, settings, [])
    try:
        assert dlg.add_folder(d)
        _deliver_after_cancel(dlg, gate)
        assert dlg.paths == [] and not dlg.busy
        gate2 = _late_result(monkeypatch, "scan_spectrum_files", [d / "f001.chn"])
        gate2.set()
        assert dlg.add_folder(d)                     # a new search is not dropped
        assert wait_until(lambda: not dlg.busy, 10) and [p.name for p in dlg.paths] == ["f001.chn"]
    finally:
        dlg.close()

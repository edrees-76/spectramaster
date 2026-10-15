"""Background batch conversion (runs in a QThread)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtCore import QObject, Signal, Slot

from ..convert import convert_many
from ..formats.base import FormatSpec


class BatchWorker(QObject):
    """Converts a list of files; move to a QThread and connect ``thread.started`` to ``run``.

    Signals
      progress(i, n, source_path, ok, message)  -- after every file (1-based i)
      finished(ok_count, failed_count, total, cancelled)
    """

    progress = Signal(int, int, str, bool, str)
    finished = Signal(int, int, int, bool)

    def __init__(self, files: Sequence[Path], out_fmt: FormatSpec, out_dir: Optional[Path] = None,
                 in_fmt: Optional[FormatSpec] = None, overwrite: bool = True,
                 keep_tree_from: Optional[Path] = None):
        super().__init__()
        self.files = [Path(f) for f in files]
        self.out_fmt = out_fmt
        self.out_dir = Path(out_dir) if out_dir else None
        self.in_fmt = in_fmt
        self.overwrite = overwrite
        self.keep_tree_from = Path(keep_tree_from) if keep_tree_from else None
        self._cancel = False
        self.ok_count = 0
        self.failed_count = 0

    def cancel(self) -> None:
        self._cancel = True

    @property
    def cancelled(self) -> bool:
        return self._cancel

    @Slot()
    def run(self) -> None:
        self.ok_count = self.failed_count = 0

        def on_progress(i, n, result) -> bool:
            if result.ok:
                self.ok_count += 1
                msg = ", ".join(p.name for p in result.outputs)
                if result.warnings:
                    msg += "  ⚠ " + "; ".join(result.warnings)
            else:
                self.failed_count += 1
                msg = result.error or "error"
            self.progress.emit(i, n, str(result.source), result.ok, msg)
            return not self._cancel

        total = len(self.files)
        if not self._cancel and total:
            try:
                convert_many(self.files, self.out_fmt, self.out_dir, self.in_fmt,
                             overwrite=self.overwrite, keep_tree_from=self.keep_tree_from,
                             progress=on_progress)
            except Exception as exc:  # defensive: convert_many already catches per file
                self.failed_count += 1
                self.progress.emit(self.ok_count + self.failed_count, total, "", False,
                                   f"{type(exc).__name__}: {exc}")
        done = self.ok_count + self.failed_count
        self.finished.emit(self.ok_count, self.failed_count, total, self._cancel and done < total)


class AnalysisWorker(QObject):
    """Peak search + nuclide identification for one spectrum (runs in a QThread).

    The engine functions are looked up on ``spectramaster.analysis`` at run time,
    so tests can monkeypatch them.

    Signals
      done(token, peaks, matches, identified)   -- identified=False when the spectrum is uncalibrated
      failed(token, kind, message)               -- kind: "missing" (engine not installed) or "error"
    """

    done = Signal(int, object, object, bool)
    failed = Signal(int, str, str)

    def __init__(self, spectrum, token: int = 0, application: str = "all"):
        super().__init__()
        self.spectrum = spectrum
        self.token = token
        self.application = application          # identification library (analysis.library.APPLICATIONS)

    @Slot()
    def run(self) -> None:
        import types
        from .. import analysis as engine
        try:
            find_peaks, identify = engine.find_peaks, engine.identify
            # "from .identify import identify" inside the package rebinds the package
            # attribute ``identify`` to the submodule; use the function in that case
            if isinstance(find_peaks, types.ModuleType):
                find_peaks = find_peaks.find_peaks
            if isinstance(identify, types.ModuleType):
                identify = identify.identify
            peaks = list(find_peaks(self.spectrum) or [])
            identified = bool(self.spectrum.energy_coeffs)
            matches = (list(identify(self.spectrum, peaks, application=self.application) or [])
                       if identified else [])
        except (ImportError, NotImplementedError) as exc:
            self.failed.emit(self.token, "missing", f"{type(exc).__name__}: {exc}")
            return
        except Exception as exc:  # engine bug -> message, never a crash
            self.failed.emit(self.token, "error", f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(self.token, peaks, matches, identified)

class CallWorker(QObject):
    """Runs ``fn()`` once in a QThread (dialogs of Release B: calibration proposal, drift check,
    fit inspection, manual refits).  Science stays in the called function.

    Signals
      done(result)        -- the return value
      failed(message)     -- "ExceptionType: message"
    """

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as exc:  # engine error -> message, never a crash
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(result)


def start_call(owner, fn, on_done, on_failed):
    """Run ``fn`` on a new QThread owned by `owner` (a QObject); `on_done(result)` /
    `on_failed(message)` are called in the GUI thread (bound methods of `owner`).
    Returns the QThread (kept on ``owner._call_threads`` until it finishes)."""
    from PySide6.QtCore import QThread
    thread = QThread(owner)
    worker = CallWorker(fn)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.done.connect(on_done)
    worker.failed.connect(on_failed)
    worker.done.connect(thread.quit)
    worker.failed.connect(thread.quit)
    keep = owner.__dict__.setdefault("_call_threads", [])
    keep.append((thread, worker))

    def _finished():
        if (thread, worker) in keep:
            keep.remove((thread, worker))
        worker.deleteLater()
        thread.deleteLater()
    thread.finished.connect(_finished)
    thread.start()
    return thread

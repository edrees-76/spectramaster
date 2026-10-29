"""Background batch conversion (runs in a QThread)."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional, Sequence

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

    def __init__(self, spectrum, token: int = 0, application: str = "all", sampled=None):
        super().__init__()
        self.spectrum = spectrum
        self.token = token
        self.application = application          # identification library (analysis.library.APPLICATIONS)
        self.sampled = sampled                  # end of sampling (datetime) or None

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
            matches = (list(identify(self.spectrum, peaks, application=self.application,
                                         sampled=self.sampled) or [])
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
      cancelled()         -- ``fn`` raised InterruptedError (stopped by cancel_calls): no callback
    """

    done = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn()
        except InterruptedError:  # cancelled by its owner (closing): nothing to report
            self.cancelled.emit()
            return
        except Exception as exc:  # engine error -> message, never a crash
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(result)


_RUNNING: list = []          # (thread, worker) of every start_call still running, in any owner
_QUIT_HOOKED = False


def running_calls() -> int:
    """Number of ``start_call`` threads still running."""
    return len(_RUNNING)


def quit_on(thread, *signals) -> None:
    """Stop ``thread`` when any of ``signals`` (emitted by its worker) fires.

    The call is direct, in the worker's thread (QThread.quit is thread-safe): a queued call would
    need the GUI thread, which is the one blocked in ``wait()`` when a window closes or the
    application quits, so the wait timed out and the running thread was then destroyed (round-6
    review C1)."""
    from PySide6.QtCore import Qt
    for sig in signals:
        sig.connect(thread.quit, Qt.DirectConnection)


def _wait_all() -> None:
    """On quit: wait for every running call to end (never destroy a running thread)."""
    for thread, worker in list(_RUNNING):
        thread.wait()
        if (thread, worker) in _RUNNING:
            _RUNNING.remove((thread, worker))


def wait_threads(owner, thread=None, ms: Optional[int] = None) -> bool:
    """Wait for `owner`'s start_call threads and `thread` (no ``ms``: until they end, a running
    thread is never destroyed).  True when there was something to wait for."""
    threads = [t for t, _w in owner.__dict__.get("_call_threads", [])] + ([thread] if thread is not None else [])
    for t in threads:
        t.wait() if ms is None else t.wait(ms)
    return bool(threads)


def call_stop(owner) -> Callable[[], bool]:
    """A new cancel flag for `owner`'s next start_call work: the returned ``stop()`` is True once
    :func:`cancel_calls` was called; the work then raises InterruptedError (round-7 review,
    Gemini M3: a folder search stops when its window closes)."""
    ev = threading.Event()
    owner.__dict__.setdefault("_call_cancels", []).append(ev)
    return ev.is_set


def cancel_calls(owner) -> None:
    """Set the cancel flags of `owner`'s running start_call work (see :func:`call_stop`)."""
    for ev in owner.__dict__.pop("_call_cancels", []):
        ev.set()


def start_call(owner, fn, on_done, on_failed):
    """Run ``fn`` on a new QThread; `on_done(result)` / `on_failed(message)` are called in the GUI
    thread (bound methods of `owner`, a QObject).  Returns the QThread (kept on
    ``owner._call_threads`` until it finishes).

    The thread belongs to the application, not to `owner`: a dialog closed and deleted while the
    call runs would otherwise delete a running QThread, which ends the process (round-5 review
    C1).  Its callbacks are disconnected with it and the result is dropped; the application waits
    for running calls when it quits."""
    global _QUIT_HOOKED
    from PySide6.QtCore import QCoreApplication, QThread
    app = QCoreApplication.instance()
    if app is not None and not _QUIT_HOOKED:
        app.aboutToQuit.connect(_wait_all)
        _QUIT_HOOKED = True
    thread = QThread(app)
    worker = CallWorker(fn)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.done.connect(on_done)
    worker.failed.connect(on_failed)
    quit_on(thread, worker.done, worker.failed, worker.cancelled)
    keep = owner.__dict__.setdefault("_call_threads", [])
    keep.append((thread, worker))
    _RUNNING.append((thread, worker))

    def _finished():
        for lst in (keep, _RUNNING):
            if (thread, worker) in lst:
                lst.remove((thread, worker))
        worker.deleteLater()
        thread.deleteLater()
    thread.finished.connect(_finished)
    thread.start()
    return thread

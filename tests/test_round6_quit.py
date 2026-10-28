"""Round-6 review C1: quitting the application while a worker runs must wait for the worker and
end normally.  The worker's "finished" signal stopped its thread through a queued call to the GUI
thread, which is the one blocked waiting for it: the wait timed out (30 s) and the running
QThread was then destroyed, ending the process.  Run in separate processes, because the failure
aborts the interpreter."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time

import pytest

pytest.importorskip("PySide6")

SCRIPT = textwrap.dedent("""
    import os, sys, time
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication, QDialog
    from spectramaster.gui.worker import start_call, running_calls

    app = QApplication(sys.argv)
    got = []

    class Dlg(QDialog):
        def done_(self, r):
            got.append(r)
        def failed_(self, m):
            got.append(m)

    dlg = Dlg()
    dlg.setAttribute(Qt.WA_DeleteOnClose)
    dlg.show()
    start_call(dlg, lambda: (time.sleep(MODE_SLEEP), 42)[1], dlg.done_, dlg.failed_)
    if MODE_CLOSE:
        QTimer.singleShot(50, dlg.close)
    QTimer.singleShot(100, app.quit)
    t0 = time.monotonic()
    code = app.exec()
    print("QUIT", code, running_calls(), round(time.monotonic() - t0, 2))
""")


def _run(sleep: float, close: bool) -> tuple[subprocess.CompletedProcess, float]:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = SCRIPT.replace("MODE_SLEEP", repr(sleep)).replace("MODE_CLOSE", repr(close))
    t0 = time.monotonic()
    r = subprocess.run([sys.executable, "-c", script], cwd=root, env=env, capture_output=True,
                       text=True, timeout=180)
    return r, time.monotonic() - t0


@pytest.mark.parametrize("sleep,close", [(1.0, False), (1.0, True), (3.0, False)])
def test_quitting_while_a_call_runs_waits_for_it_and_ends_normally(sleep, close):
    r, elapsed = _run(sleep, close)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "QUIT 0 0" in r.stdout                  # nothing left running when the loop returns
    assert elapsed < sleep + 15                    # was: the 30 s wait timeout, then a crash


def test_quit_on_stops_the_thread_while_the_gui_thread_is_blocked():
    """The helper every worker thread uses: the GUI thread waits (no event processing) and the
    thread still stops as soon as the worker has finished."""
    from PySide6.QtCore import QObject, QThread, Signal
    from PySide6.QtWidgets import QApplication
    from spectramaster.gui.worker import quit_on

    app = QApplication.instance() or QApplication([])

    class W(QObject):
        finished = Signal()

        def run(self):
            time.sleep(0.2)
            self.finished.emit()

    thread = QThread()
    w = W()
    w.moveToThread(thread)
    thread.started.connect(w.run)
    quit_on(thread, w.finished)
    thread.start()
    t0 = time.monotonic()
    assert thread.wait(10000)                     # no processEvents: a queued quit never arrives
    assert time.monotonic() - t0 < 5
    assert app is not None

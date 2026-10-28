"""Round-5 review C1: a dialog closed (and deleted) while its ``start_call`` worker runs must not
end the process ("QThread: Destroyed while thread is still running"); the result is dropped.
Run in a separate process, because the failure aborts the interpreter."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap

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
    QTimer.singleShot(150, dlg.close)
    end = time.monotonic() + 10
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
        if time.monotonic() > end - 9 and not running_calls():
            break
    for _ in range(50):
        app.processEvents()
    print("SURVIVED", got, running_calls())
""")


def _run(sleep: float) -> subprocess.CompletedProcess:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return subprocess.run([sys.executable, "-c", SCRIPT.replace("MODE_SLEEP", repr(sleep))],
                          cwd=root, env=env, capture_output=True, text=True, timeout=120)


def test_closing_the_owner_while_the_worker_runs_does_not_end_the_process():
    r = _run(1.5)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "SURVIVED [] 0" in r.stdout          # result dropped, nothing left running


def test_result_still_delivered_when_the_owner_lives():
    r = _run(0.05)                              # finishes before the close
    assert r.returncode == 0, r.stderr[-2000:]
    assert "SURVIVED [42] 0" in r.stdout

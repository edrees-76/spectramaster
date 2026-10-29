"""Test-session hooks.

On CI only (``CI`` is set by GitHub Actions): after pytest has printed its summary, the process
ends with pytest's own exit status without Python's interpreter teardown.  On Linux, PySide6 can
abort while the garbage collector destroys Qt objects at interpreter exit ("shared QObject was
deleted directly", exit code 134) although every test has already passed.  Nothing is skipped and
no result is changed: the status is the one pytest computed.

Everywhere: at the end of the session the Qt widgets the tests left open are closed and deleted
before the interpreter's teardown.  On Windows a left-open batch conversion dialog destroyed during
that teardown ended the process with 0xC0000409 after every test had passed (round-7 review, Codex
M2; docs/baseline/round7_tests_protocol.md).
"""
from __future__ import annotations

import os
import sys

import pytest

_STATUS = {"code": 0}


def close_qt_widgets() -> None:
    """Close and delete every top-level widget still alive, then deliver the deferred deletes."""
    if "PySide6" not in sys.modules:
        return
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    if not isinstance(QCoreApplication.instance(), QApplication):
        return
    for w in QApplication.topLevelWidgets():
        w.close()
        w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()


def pytest_sessionfinish(session, exitstatus):
    _STATUS["code"] = int(exitstatus)
    close_qt_widgets()


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    if os.environ.get("CI"):
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_STATUS["code"])

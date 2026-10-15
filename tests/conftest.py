"""Test-session hooks.

On CI only (``CI`` is set by GitHub Actions): after pytest has printed its summary, the process
ends with pytest's own exit status without Python's interpreter teardown.  On Linux, PySide6 can
abort while the garbage collector destroys Qt objects at interpreter exit ("shared QObject was
deleted directly", exit code 134) although every test has already passed.  Nothing is skipped and
no result is changed: the status is the one pytest computed.
"""
from __future__ import annotations

import os
import sys

import pytest

_STATUS = {"code": 0}


def pytest_sessionfinish(session, exitstatus):
    _STATUS["code"] = int(exitstatus)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    if os.environ.get("CI"):
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_STATUS["code"])

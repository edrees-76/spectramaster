"""Round-7 review, Codex M2 / L1 and Gemini L3: Qt widgets are not left to the interpreter's teardown,
the round-6 input harness compares numbers apart from the width note, parsers need no application
(docs/baseline/round7_tests_protocol.md)."""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from spectramaster.validation import round6_inputs as r6

ROOT = Path(__file__).resolve().parents[1]
BINNING = ("FWHM 4.0 channels: the widths from the channel contents are overestimated by the channel binning, "
           "FWHM by 1.5 to 4.9 % (centroid on a channel to between two); not corrected")


def _clean(fwhm=2.0, note=""):
    return {"peak_width": [1332.5, fwhm, 3.6, note], "peak_to_compton": 50.0, "net_area": [1000.0, 40.0],
            "relative_efficiency": 30.0}


def test_rc5_note_is_compared_apart_from_the_numbers():
    before = _clean()
    assert r6._clean_note(_clean(), before) == "as before"
    assert r6._clean_note(_clean(note=BINNING), before) == "R6-G channel-binning note"
    assert r6._clean_note(_clean(note="FWHM 4.0 channels: something else"), before) is None
    assert r6._clean_numbers(_clean(note=BINNING)) == r6._clean_numbers(before)
    assert r6._clean_numbers(_clean(fwhm=2.0 + 1e-9)) != r6._clean_numbers(before)


def test_rc5_criterion_still_fails_on_a_changed_number():
    import copy
    import json
    b = json.loads(r6.BEFORE_JSON.read_text(encoding="utf-8"))
    m = copy.deepcopy(json.loads((r6.OUT / "round6_inputs.json").read_text(encoding="utf-8"))["measured"])
    m["C5"]["clean"]["peak_width"][3] = BINNING
    (ok,) = [c["pass"] for c in r6.criteria(m, b) if c["id"] == "RC.C5"]
    m["C5"]["clean"]["peak_width"][1] += 1e-9
    (changed,) = [c["pass"] for c in r6.criteria(m, b) if c["id"] == "RC.C5"]
    assert ok and not changed


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)], capture_output=True, text=True,
                          cwd=ROOT, timeout=120)


def test_parsers_need_no_application():
    pytest.importorskip("PySide6")
    r = _run("""
        from PySide6.QtCore import QCoreApplication
        from spectramaster.gui.detector_test_dialog import parse_counts
        from spectramaster.gui.qc_window import _parse_activity
        assert parse_counts("100\\n98.5\\n") == [100.0, 98.5]
        assert _parse_activity("Cs137=37000") == {"Cs-137": 37000.0}
        print(QCoreApplication.instance() is None)
    """)
    assert r.returncode == 0 and r.stdout.strip() == "True", r.stderr


def test_session_end_deletes_the_widgets_left_open():
    pytest.importorskip("PySide6")
    r = _run("""
        import os, sys
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        sys.path.insert(0, "tests")
        from PySide6.QtWidgets import QApplication, QDialog
        import shiboken6
        from conftest import close_qt_widgets
        app = QApplication([])
        dlgs = [QDialog(), QDialog()]
        for d in dlgs:
            d.show()
        close_qt_widgets()
        print(all(not shiboken6.isValid(d) for d in dlgs), len(QApplication.topLevelWidgets()))
    """)
    assert r.returncode == 0 and r.stdout.split() == ["True", "0"], r.stderr

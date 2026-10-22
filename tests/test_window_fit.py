"""Dialogs taller or wider than the screen open inside it, title bar and buttons included."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout)

from spectramaster.gui.window_buttons import TITLE_BAR_GUESS, fitted_rect


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


def test_fitted_rect_keeps_the_title_bar_on_the_screen():
    avail = QRect(0, 0, 1456, 780)
    # a dialog 1000 px tall centred on the screen: its title bar was above the top edge
    client = QRect(200, -80, 900, 1000)
    frame = QRect(192, -111, 916, 1039)            # 31 px title bar, 8 px borders
    r = fitted_rect(frame, client, avail)
    assert r.top() - 31 >= 0 and r.bottom() + 8 <= avail.bottom()
    assert r.height() == 780 - 31 - 8 and r.width() == 900
    # one that fits is left where it is
    ok = QRect(100, 100, 600, 400)
    assert fitted_rect(QRect(92, 69, 616, 439), ok, avail) == ok
    # no frame known yet: a title bar is assumed
    r = fitted_rect(QRect(0, 0, 500, 900), QRect(0, 0, 500, 900), avail)
    assert r.top() >= TITLE_BAR_GUESS and r.bottom() <= avail.bottom()


def _tall_dialog(rows: int):
    d = QDialog()
    lay = QVBoxLayout(d)
    for i in range(rows):
        lab = QLabel(f"row {i}")
        lab.setMinimumHeight(40)
        lay.addWidget(lab)
    row = QHBoxLayout()
    ok = QPushButton("OK")
    row.addWidget(ok)
    row.addStretch(1)
    row.addWidget(QPushButton("Close"))
    lay.addLayout(row)
    return d, ok


def test_dialog_taller_than_the_screen_scrolls_and_keeps_its_buttons(qapp):
    avail = QApplication.primaryScreen().availableGeometry()
    d, ok = _tall_dialog(avail.height() // 40 + 10)
    d.show()
    QApplication.processEvents()
    assert d.frameGeometry().top() >= avail.top() and d.geometry().bottom() <= avail.bottom()
    areas = d.findChildren(QScrollArea)
    assert len(areas) == 1
    assert not areas[0].isAncestorOf(ok)           # the button row stays below the scroll area
    assert ok.isVisible()
    d.close()


def test_dialog_that_fits_is_unchanged(qapp):
    d, _ok = _tall_dialog(3)
    d.show()
    QApplication.processEvents()
    assert not d.findChildren(QScrollArea)
    d.close()


def test_open_dialog_with_preview_gets_the_buttons_and_is_not_scrolled(qapp, tmp_path):
    from PySide6.QtCore import Qt
    from spectramaster.gui.preview import PreviewFileDialog
    d = PreviewFileDialog(None, "open", str(tmp_path), "*.spe")
    d.show()
    QApplication.processEvents()
    assert d.windowFlags() & Qt.WindowMaximizeButtonHint
    assert not d.findChildren(QScrollArea, options=Qt.FindDirectChildrenOnly)
    d.close()

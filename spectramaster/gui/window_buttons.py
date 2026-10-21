"""Maximize and minimize buttons on every dialog window.

Qt gives a QDialog on Windows only a close button (and a "?" context-help button).  The
analysis dialogs hold tables and plots that are easier to read maximized, so one application
event filter adds the buttons to every dialog before it is first shown.  Small standard dialogs
(message boxes, file / colour / font pickers, progress and input boxes) keep their usual frame.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (QColorDialog, QDialog, QFileDialog, QFontDialog, QInputDialog, QMessageBox,
                               QProgressDialog)

KEEP_FRAME = (QMessageBox, QFileDialog, QColorDialog, QFontDialog, QInputDialog, QProgressDialog)
BUTTONS = Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint


def wants_buttons(w) -> bool:
    return isinstance(w, QDialog) and not isinstance(w, KEEP_FRAME) and w.isWindow()


def add_buttons(w) -> None:
    flags = w.windowFlags()
    new = (flags | BUTTONS | Qt.WindowSystemMenuHint) & ~Qt.WindowContextHelpButtonHint
    if new != flags:
        w.setWindowFlags(new)


class DialogButtons(QObject):
    """Application event filter: a dialog is polished once, just before it is first shown."""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Polish and wants_buttons(obj) and not obj.isVisible():
            add_buttons(obj)
        return False


def install(app) -> DialogButtons:
    f = getattr(app, "_dialog_buttons", None)
    if f is None:
        f = app._dialog_buttons = DialogButtons(app)
        app.installEventFilter(f)
    return f

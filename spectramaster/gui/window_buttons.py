"""Maximize and minimize buttons on every dialog window, and every dialog on the screen.

Qt gives a QDialog on Windows only a close button (and a "?" context-help button).  The
analysis dialogs hold tables and plots that are easier to read maximized, so one application
event filter adds the buttons to every dialog the program draws before it is first shown,
standard ones (message boxes, the open dialog with its preview, colour / font pickers, progress
and input boxes) included.  Dialogs drawn by Windows itself (the native file pickers) keep
their own frame: Qt cannot change it.

A dialog taller or wider than the screen would open with its title bar (and these buttons)
above the top edge and its bottom behind the taskbar; when first shown it is made to fit the
available area of its screen, title bar included.  When its contents cannot shrink that far
they move into a scroll area, and a last row of buttons stays below it, always visible.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRect, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QAbstractButton, QColorDialog, QDialog, QDialogButtonBox, QFileDialog,
                               QFontDialog, QFrame, QInputDialog, QMessageBox, QProgressDialog, QScrollArea,
                               QVBoxLayout, QWidget)

STANDARD = (QMessageBox, QFileDialog, QColorDialog, QFontDialog, QInputDialog, QProgressDialog)   # never scrolled
BUTTONS = Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint


def wants_buttons(w) -> bool:
    return isinstance(w, QDialog) and w.isWindow()


def add_buttons(w) -> None:
    # in plain integers: PySide's ~ of a WindowType keeps only the low 25 bits, so
    # "& ~Qt.WindowContextHelpButtonHint" also cleared Qt.WindowCloseButtonHint (bit 27) and
    # Windows showed a disabled close button
    flags = int(w.windowFlags().value)
    new = (flags | int(BUTTONS.value) | int(Qt.WindowSystemMenuHint.value)) & ~int(Qt.WindowContextHelpButtonHint.value)
    if new != flags:
        w.setWindowFlags(Qt.WindowType(new))


TITLE_BAR_GUESS = 32           # px above the client area when the frame is not known yet
_FITTED = "_sm_fitted_to_screen"


def fitted_rect(frame: QRect, client: QRect, avail: QRect) -> QRect:
    """Client geometry of a window whose frame (title bar and borders) fits in `avail`: smaller
    when it does not fit, moved so that its title bar is on the screen."""
    top = client.top() - frame.top()
    if top <= 0:
        top = TITLE_BAR_GUESS
    side = max(client.left() - frame.left(), 0)
    bottom = max(frame.bottom() - client.bottom(), side)
    w = min(client.width(), avail.width() - 2 * side)
    h = min(client.height(), avail.height() - top - bottom)
    fw, fh = w + 2 * side, h + top + bottom
    x = min(max(client.left() - side, avail.left()), avail.right() + 1 - fw)
    y = min(max(client.top() - top, avail.top()), avail.bottom() + 1 - fh)
    return QRect(x + side, y + top, w, h)


def _button_row(item) -> bool:
    """A layout item holding only buttons (and spacing): a dialog's OK / Cancel row."""
    wid = item.widget()
    if wid is not None:
        return isinstance(wid, (QDialogButtonBox, QAbstractButton))
    lay = item.layout()
    if lay is None:
        return False
    widgets = [lay.itemAt(i).widget() for i in range(lay.count())]
    widgets = [x for x in widgets if x is not None]
    return bool(widgets) and all(isinstance(x, (QDialogButtonBox, QAbstractButton)) for x in widgets)


def scroll_contents(w) -> QScrollArea:
    """Move the dialog's contents into a scroll area; a last row of buttons stays below it."""
    lay = w.layout()
    m = lay.contentsMargins()
    keep = lay.takeAt(lay.count() - 1) if lay.count() > 1 and _button_row(lay.itemAt(lay.count() - 1)) else None
    inner = QWidget()
    inner.setLayout(lay)                      # takes the layout off the dialog
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setWidget(inner)
    outer = QVBoxLayout(w)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.addWidget(area, 1)
    if keep is not None:
        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(m.left(), 0, m.right(), m.bottom())
        if keep.widget() is not None:
            hl.addWidget(keep.widget())
        else:
            hl.addLayout(keep.layout())
        outer.addWidget(holder)
    return area


def fit_to_screen(w) -> None:
    screen = w.screen() or QGuiApplication.primaryScreen()
    if screen is None:
        return
    avail = screen.availableGeometry()
    frame, client = w.frameGeometry(), w.geometry()
    top = client.top() - frame.top() if client.top() > frame.top() else TITLE_BAR_GUESS
    need = w.minimumSizeHint()
    if w.layout() is not None and not isinstance(w, STANDARD) and (need.height() + top + 8 > avail.height() or need.width() + 16 > avail.width()):
        scroll_contents(w)
        w.setMinimumSize(0, 0)
    r = fitted_rect(frame, client, avail)
    if r != w.geometry():
        w.setMinimumSize(min(w.minimumWidth(), r.width()), min(w.minimumHeight(), r.height()))
        w.setGeometry(r)


class DialogButtons(QObject):
    """Application event filter: a dialog is polished once, just before it is first shown, and
    fitted to its screen when first shown."""

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.Polish and wants_buttons(obj) and not obj.isVisible():
            add_buttons(obj)
        elif t == QEvent.Show and wants_buttons(obj) and not obj.property(_FITTED):
            obj.setProperty(_FITTED, True)
            fit_to_screen(obj)
        return False


def install(app) -> DialogButtons:
    f = getattr(app, "_dialog_buttons", None)
    if f is None:
        f = app._dialog_buttons = DialogButtons(app)
        app.installEventFilter(f)
    return f

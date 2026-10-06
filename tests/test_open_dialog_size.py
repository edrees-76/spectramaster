"""The Open Spectrum dialog must fit on the screen (the all-formats filter used to stretch it)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SPECTRAMASTER_NO_SPLASH", "1")

from PySide6.QtCore import QSize  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox, QFileDialog  # noqa: E402

from spectramaster.formats import load_all, readable_formats  # noqa: E402
from spectramaster.gui.preview import PreviewFileDialog  # noqa: E402


class _Settings:
    def __init__(self):
        self.d = {}

    def get(self, key, default=None):
        return self.d.get(key, default)

    def get_bool(self, key, default=False):
        return bool(self.d.get(key, default))

    def set(self, key, value):
        self.d[key] = value


def _all_filter():
    load_all()
    exts = sorted({e for f in readable_formats() for e in f.extensions})
    return "Spectrum files (" + " ".join("*" + e for e in exts) + ");;All files (*)"


def test_dialog_fits_screen_and_remembers_size(tmp_path):
    app = QApplication.instance() or QApplication([])
    st = _Settings()
    dlg = PreviewFileDialog(None, "Open", str(tmp_path), _all_filter(), settings=st)
    avail = app.primaryScreen().availableGeometry()
    assert dlg.testOption(QFileDialog.HideNameFilterDetails)
    assert dlg.width() <= avail.width() and dlg.height() <= avail.height()
    # the type combo no longer sizes itself to the ~40-extension filter text
    for combo in dlg.findChildren(QComboBox):
        assert combo.sizeHint().width() < avail.width() * 0.6
    dlg.resize(700, 450)
    dlg.done(0)
    assert st.get("ui/open_dialog_size") == QSize(700, 450)
    dlg2 = PreviewFileDialog(None, "Open", str(tmp_path), _all_filter(), settings=st)
    assert dlg2.size() == QSize(700, 450).boundedTo(QSize(int(avail.width() * 0.9), int(avail.height() * 0.85)))

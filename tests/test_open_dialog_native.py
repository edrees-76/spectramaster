"""Opening a spectrum uses the operating system's dialog by default; the dialog with the
description panel only when chosen in View."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QFileDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(["test"])


def test_native_dialog_by_default_preview_on_request(qapp, tmp_path, monkeypatch):
    from spectramaster.gui import preview
    from spectramaster.gui.settings import Settings
    st = Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat))
    calls = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (calls.append("native") or "C:/a.spe", "")))
    monkeypatch.setattr(preview.PreviewFileDialog, "exec", lambda self: calls.append("preview") or 0)
    assert preview.get_open_file_name(None, "t", "", "All (*)", "", st) == "C:/a.spe"
    assert calls == ["native"]
    st.set(preview.PREVIEW_SETTING, True)
    assert preview.get_open_file_name(None, "t", "", "All (*)", "", st) == ""
    assert calls == ["native", "preview"]


def test_view_menu_option_is_remembered(qapp, tmp_path):
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.settings import Settings
    st = Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat))
    w = MainWindow(st)
    try:
        assert not w.act_open_preview.isChecked() and w.act_open_preview in w.menu_v_more.actions()
        w.act_open_preview.setChecked(True)
        assert st.get_bool("ui/open_dialog_preview", False)
    finally:
        if hasattr(w, "session_ctl"):
            w.session_ctl.ask_save_changes = lambda: "discard"
        w.close()

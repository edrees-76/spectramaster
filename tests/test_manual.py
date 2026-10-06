"""Help › User Manual: actions, F1 shortcut and location of the bundled PDF manuals."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    yield create_app(["test"])


@pytest.fixture()
def window(qapp, tmp_path):
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.settings import Settings
    w = MainWindow(Settings(QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)))
    w.errors = []
    w.show_error = w.errors.append
    yield w
    w.close()
    w.deleteLater()
    QApplication.processEvents()


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_manual_pdfs_resolve(lang):
    from spectramaster.gui import manual
    p = manual.manual_path(lang)
    assert p.parent == Path(manual.__file__).resolve().parents[2] / "docs"
    assert p.name == manual.MANUAL_FILES[lang]
    assert p.is_file(), p
    assert p.read_bytes()[:5] == b"%PDF-"


def test_docs_dir_inside_pyinstaller_bundle(monkeypatch, tmp_path):
    import sys
    from spectramaster.gui import manual
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert manual.docs_dir() == tmp_path / "docs"
    assert manual.manual_path("en") == tmp_path / "docs" / "SpectraMaster_User_Manual_EN.pdf"


def test_docs_dir_beside_installed_exe(monkeypatch, tmp_path):
    """Installer (onedir) build: manuals live in {app}/docs next to SpectraMaster.exe."""
    import sys
    from spectramaster.gui import manual
    app_dir = tmp_path / "app"
    (app_dir / "_internal").mkdir(parents=True)
    (app_dir / "docs").mkdir()
    (app_dir / "docs" / manual.MANUAL_FILES["en"]).write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(sys, "_MEIPASS", str(app_dir / "_internal"), raising=False)
    monkeypatch.setattr(sys, "executable", str(app_dir / "SpectraMaster.exe"))
    assert manual.docs_dir() == app_dir / "docs"
    assert manual.manual_path("ar") == app_dir / "docs" / manual.MANUAL_FILES["ar"]


def test_help_menu_has_manual_actions_and_f1_follows_language(window):
    from spectramaster.gui import i18n
    acts = window.menu_help.actions()
    assert window.act_manual_ar in acts and window.act_manual_en in acts
    f1 = QKeySequence(QKeySequence.HelpContents)
    assert window.act_about.shortcut() != f1          # F1 moved from About to the manual
    window.apply_language("en")
    assert window.act_manual_en.shortcut() == f1 and window.act_manual_ar.shortcut().isEmpty()
    assert window.act_manual_en.text() == i18n.STRINGS["en"]["act_manual_en"]
    window.apply_language("ar")
    assert window.act_manual_ar.shortcut() == f1 and window.act_manual_en.shortcut().isEmpty()
    assert window.act_manual_ar.text() == i18n.STRINGS["ar"]["act_manual_ar"]


def test_manual_action_opens_pdf_with_system_viewer(window, monkeypatch):
    from spectramaster.gui import manual
    opened = []
    monkeypatch.setattr(manual.QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    window.act_manual_en.trigger()
    window.act_manual_ar.trigger()
    assert [Path(u.toLocalFile()).name for u in opened] == [manual.MANUAL_FILES["en"], manual.MANUAL_FILES["ar"]]
    assert window.errors == []


def test_missing_manual_reports_error(window, monkeypatch, tmp_path):
    import sys
    from spectramaster.gui import manual
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert manual.open_manual("en", window) is False
    assert window.errors and "SpectraMaster_User_Manual_EN.pdf" in window.errors[0]

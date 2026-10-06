"""Help › User Manual (Arabic / English): opens the bundled PDF manuals with the system viewer.

The PDFs live in ``<project>/docs`` when running from source and in ``<bundle>/docs`` inside the
PyInstaller executable (``--add-data "docs/SpectraMaster_User_Manual_AR.pdf;docs"``).
F1 opens the manual in the current interface language.

Hooked into the main window by :func:`install_manual_menu` and :func:`retranslate_manual_menu`.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence

from . import i18n
from .i18n import STRINGS, tr

MANUAL_FILES = {"ar": "SpectraMaster_User_Manual_AR.pdf", "en": "SpectraMaster_User_Manual_EN.pdf"}

STRINGS["en"].update({
    "act_manual_ar": "User Manual (&Arabic)",
    "act_manual_en": "User &Manual (English)",
    "tip_manual": "Open the user manual (PDF) with the system viewer (F1)",
    "err_manual_missing": "The user manual was not found:\n{path}",
    "err_manual_open": "The user manual could not be opened:\n{path}",
})
STRINGS["ar"].update({
    "act_manual_ar": "دليل المستخدم (&عربي)",
    "act_manual_en": "دليل المستخدم (&إنجليزي)",
    "tip_manual": "فتح دليل المستخدم (PDF) بعارض النظام (F1)",
    "err_manual_missing": "لم يُعثر على دليل المستخدم:\n{path}",
    "err_manual_open": "تعذّر فتح دليل المستخدم:\n{path}",
})


def docs_dir() -> Path:
    """``docs`` folder: inside the PyInstaller bundle (sys._MEIPASS), next to the installed
    exe (``{app}/docs``, installer "User manuals" component) or the source tree."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        inside = Path(base) / "docs"
        beside = Path(sys.executable).resolve().parent / "docs"
        if not (inside / MANUAL_FILES["en"]).is_file() and (beside / MANUAL_FILES["en"]).is_file():
            return beside
        return inside
    return Path(__file__).resolve().parents[2] / "docs"


def manual_path(lang: Optional[str] = None) -> Path:
    """Path of the PDF manual for ``lang`` ("ar"/"en"; default = current UI language)."""
    lang = lang if lang in MANUAL_FILES else ("ar" if i18n.is_rtl(lang) else "en")
    return docs_dir() / MANUAL_FILES[lang]


def open_manual(lang: Optional[str] = None, parent=None) -> bool:
    path = manual_path(lang)
    if not path.is_file():
        _warn(parent, tr("err_manual_missing", path=str(path)))
        return False
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
        _warn(parent, tr("err_manual_open", path=str(path)))
        return False
    return True


def _warn(parent, text: str) -> None:
    show = getattr(parent, "show_error", None)
    if callable(show):
        show(text)
    else:  # pragma: no cover - only without a main window
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(parent, tr("err_title"), text)


def install_manual_menu(main_window) -> dict:
    """Add the two manual entries at the top of the Help menu (``act_manual_ar`` / ``act_manual_en``)."""
    actions = {}
    for lang in ("ar", "en"):
        a = QAction(main_window)
        a.setObjectName(f"act_manual_{lang}")
        a.triggered.connect(lambda _=False, l=lang: open_manual(l, main_window))
        actions[lang] = a
    main_window.manual_actions = actions
    main_window.act_manual_ar, main_window.act_manual_en = actions["ar"], actions["en"]
    menu = getattr(main_window, "menu_help", None)
    if menu is not None:
        first = menu.actions()[0] if menu.actions() else None
        menu.insertActions(first, [actions["ar"], actions["en"]])
        if first is not None:
            menu.insertSeparator(first)
    retranslate_manual_menu(main_window)
    return actions


def retranslate_manual_menu(main_window) -> None:
    actions = getattr(main_window, "manual_actions", None) or {}
    current = "ar" if i18n.is_rtl() else "en"
    for lang, a in actions.items():
        a.setText(tr(f"act_manual_{lang}"))
        a.setToolTip(tr("tip_manual"))
        a.setStatusTip(tr("tip_manual"))
        a.setShortcut(QKeySequence(QKeySequence.HelpContents) if lang == current else QKeySequence())

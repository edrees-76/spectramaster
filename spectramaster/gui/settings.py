"""Persistent preferences (QSettings), like DataMaster restoring its format selections."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings

from ..formats import get_format
from ..formats.base import FormatSpec
from .i18n import DEFAULT_LANGUAGE

AUTO = "auto"


class Settings:
    def __init__(self, qsettings: Optional[QSettings] = None):
        self.q = qsettings if qsettings is not None else QSettings("SpectraMaster", "SpectraMaster")

    # generic
    def get(self, key: str, default=None):
        return self.q.value(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        v = self.q.value(key, default)
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes")
        return bool(v)

    def set(self, key: str, value) -> None:
        self.q.setValue(key, value)

    def sync(self) -> None:
        self.q.sync()

    # language
    @property
    def language(self) -> str:
        return str(self.q.value("ui/language", DEFAULT_LANGUAGE))

    @language.setter
    def language(self, v: str) -> None:
        self.q.setValue("ui/language", v)

    # formats
    def input_format(self) -> Optional[FormatSpec]:
        """Selected input format, or None for auto-detect."""
        key = str(self.q.value("formats/input", AUTO))
        if key == AUTO:
            return None
        try:
            f = get_format(key)
            return f if f.can_read else None
        except KeyError:
            return None

    def set_input_format(self, fmt: Optional[FormatSpec]) -> None:
        self.q.setValue("formats/input", fmt.key if fmt else AUTO)

    def output_format(self) -> Optional[FormatSpec]:
        key = self.q.value("formats/output", "")
        if key:
            try:
                f = get_format(str(key))
                if f.can_write:
                    return f
            except KeyError:
                pass
        return None

    def set_output_format(self, fmt: FormatSpec) -> None:
        self.q.setValue("formats/output", fmt.key)

    # folders
    def folder(self, name: str) -> str:
        v = str(self.q.value(f"folders/{name}", "") or "")
        if v and Path(v).is_dir():
            return v
        return str(Path.home() / "Documents") if (Path.home() / "Documents").is_dir() else str(Path.home())

    def set_folder(self, name: str, path) -> None:
        p = Path(path)
        if p.is_file() or (not p.exists() and p.suffix):
            p = p.parent
        self.q.setValue(f"folders/{name}", os.fspath(p))

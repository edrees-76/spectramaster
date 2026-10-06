"""Open dialog with a "Show description" preview panel (like GammaVision's Recall dialog).

The preview reads only the selected file (with a size guard and a short debounce)
and shows the detected format, sample ID / description, channels, live/real
time, start date and a small spectrum thumbnail.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QLabel,
                               QSizePolicy,
                               QVBoxLayout, QWidget)

from ..convert import read_spectra
from ..model import Spectrum
from .i18n import tr
from .info_panel import format_seconds

MAX_PREVIEW_BYTES = 48 * 1024 * 1024
FIELDS = ["format", "sample_id", "description", "channels", "live_time", "real_time", "start"]


def thumbnail(spec: Spectrum, w: int = 240, h: int = 90) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill(QColor("#ffffff"))
    y = np.asarray(spec.counts, dtype=float)
    p = QPainter(pm)
    p.setPen(QPen(QColor("#c8d0d8"), 1))
    p.drawRect(0, 0, w - 1, h - 1)
    if len(y):
        cols = max(1, w - 4)
        starts = np.minimum(np.linspace(0, len(y), cols + 1).astype(int)[:-1], len(y) - 1)
        prof = np.log10(np.maximum(np.maximum.reduceat(y, starts), 1.0))
        top = float(prof.max()) or 1.0
        pts = [QPointF(2, h - 2)]
        for i, v in enumerate(prof.tolist()):
            pts.append(QPointF(2 + i, h - 2 - v / top * (h - 8)))
        pts.append(QPointF(2 + len(prof), h - 2))
        p.setPen(QPen(QColor("#1f5f99"), 1))
        p.setBrush(QColor(54, 128, 196, 90))
        p.drawPolygon(QPolygonF(pts))
    p.end()
    return pm


class SpectrumPreview(QFrame):
    """Side panel: description of the file under the cursor in the open dialog."""

    def __init__(self, in_fmt=None, parent=None):
        super().__init__(parent)
        self.in_fmt = in_fmt
        self.setObjectName("previewPanel")
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(260)
        self.setMaximumWidth(320)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        self.title = QLabel()
        self.title.setStyleSheet("font-weight: 600; color: #1f4e79;")
        self.title.setWordWrap(True)
        lay.addWidget(self.title)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeading | Qt.AlignVCenter)
        self.values: dict[str, QLabel] = {}
        self.labels: dict[str, QLabel] = {}
        for key in FIELDS:
            lab = QLabel(tr(f"info_{key}"))
            lab.setObjectName("infoLabel")
            val = QLabel()
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.labels[key], self.values[key] = lab, val
            form.addRow(lab, val)
        lay.addLayout(form)
        self.thumb = QLabel()
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setLayoutDirection(Qt.LeftToRight)
        lay.addWidget(self.thumb)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setObjectName("infoLabel")
        lay.addWidget(self.message)
        lay.addStretch(1)
        self._path: Optional[str] = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(lambda: self.show_file(self._path))
        self.clear()

    def value_text(self, key: str) -> str:
        return self.values[key].text().lstrip("‎")

    def clear(self, message: str = "") -> None:
        self.title.setText(tr("preview_title"))
        for v in self.values.values():
            v.setText(tr("none"))
        self.thumb.clear()
        self.message.setText(message or tr("preview_hint"))
        self.spectrum: Optional[Spectrum] = None

    def request(self, path: str) -> None:
        """Debounced preview (called on every selection change in the dialog)."""
        self._path = path
        self._timer.start()

    def show_file(self, path) -> bool:
        if not path:
            self.clear()
            return False
        p = Path(path)
        if not p.is_file():
            self.clear()
            return False
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        if size > MAX_PREVIEW_BYTES:
            self.clear(tr("preview_too_big", mb=f"{size / 1048576:.0f}"))
            return False
        try:
            spectra, fmt = read_spectra(p, self.in_fmt)
        except Exception as exc:
            self.clear(tr("preview_unreadable", msg=str(exc) or type(exc).__name__))
            self.title.setText(p.name)
            return False
        s = spectra[0]
        self.spectrum = s
        self.title.setText(p.name + (f"  ({len(spectra)})" if len(spectra) > 1 else ""))
        v = self.values
        v["format"].setText(f"{fmt.name} [{fmt.code}]")
        v["sample_id"].setText(s.sample_id or tr("none"))
        desc = (s.description or "").strip().replace("\n", " | ")
        v["description"].setText((desc[:200] + "…") if len(desc) > 200 else (desc or tr("none")))
        v["channels"].setText(f"{s.num_channels:,}")
        v["live_time"].setText(format_seconds(s.live_time))
        v["real_time"].setText(format_seconds(s.real_time))
        v["start"].setText("‎" + s.start_time.strftime("%Y-%m-%d %H:%M:%S") if s.start_time else tr("none"))
        self.thumb.setPixmap(thumbnail(s))
        self.message.setText("")
        return True


class PreviewFileDialog(QFileDialog):
    """Non-native open dialog with an optional preview panel."""

    def __init__(self, parent, title: str, folder: str, flt: str, selected: str = "",
                 settings=None, in_fmt=None):
        super().__init__(parent, title, folder, flt)
        self.settings = settings
        self.setOption(QFileDialog.DontUseNativeDialog, True)
        self.setFileMode(QFileDialog.ExistingFile)
        self.setAcceptMode(QFileDialog.AcceptOpen)
        if selected:
            self.selectNameFilter(selected)
        self.preview = SpectrumPreview(in_fmt)
        self.show_cb = QCheckBox(tr("preview_show"))
        on = settings.get_bool("ui/show_description", True) if settings is not None else True
        self.show_cb.setChecked(on)
        self.preview.setVisible(on)
        self.show_cb.toggled.connect(self._toggle)
        grid = self.layout()
        if isinstance(grid, QGridLayout):
            rows, cols = grid.rowCount(), grid.columnCount()
            grid.addWidget(self.preview, 0, cols, rows, 1)
            grid.addWidget(self.show_cb, rows, 0, 1, cols)
        self.currentChanged.connect(self._current)
        # The "all spectrum files" filter lists ~40 extensions; shown in full it made the
        # type combo (and so the whole dialog) wider than the screen.
        self.setOption(QFileDialog.HideNameFilterDetails, True)
        # On Windows the native style still reports a ~1100 px minimum width for the
        # 60-entry type combo even with AdjustToMinimumContentsLength, which pushed the dialog
        # past a 1536 px (125 %) screen. Let the layout ignore the combos' width hints.
        for combo in self.findChildren(QComboBox):
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(20)
            combo.setSizePolicy(QSizePolicy.Ignored, combo.sizePolicy().verticalPolicy())
            combo.setMinimumWidth(160)
            combo.view().setTextElideMode(Qt.ElideRight)
        self._fit_to_screen(parent, on)

    def _fit_to_screen(self, parent, preview_on: bool) -> None:
        """Remembered size if any, else a default; always clamped to the available screen."""
        screen = (parent.screen() if parent is not None else None) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else QRect(0, 0, 1280, 800)
        size = QSize(1000 if preview_on else 780, 560)
        if self.settings is not None:
            saved = self.settings.get("ui/open_dialog_size")
            if isinstance(saved, QSize) and saved.isValid():
                size = saved
        size = size.boundedTo(QSize(int(avail.width() * 0.9), int(avail.height() * 0.85)))
        self.setMinimumSize(0, 0)
        self.resize(size)
        anchor = parent.frameGeometry() if parent is not None else avail
        rect = QRect(QPoint(0, 0), size)
        rect.moveCenter(anchor.center())
        rect.moveLeft(max(avail.left(), min(rect.left(), avail.right() - size.width())))
        rect.moveTop(max(avail.top(), min(rect.top(), avail.bottom() - size.height())))
        self.move(rect.topLeft())

    def done(self, result: int) -> None:
        if self.settings is not None:
            self.settings.set("ui/open_dialog_size", self.size())
        super().done(result)

    def _toggle(self, on: bool) -> None:
        self.preview.setVisible(on)
        if self.settings is not None:
            self.settings.set("ui/show_description", on)
        if on:
            files = self.selectedFiles()
            if files:
                self.preview.request(files[0])

    def _current(self, path: str) -> None:
        if self.show_cb.isChecked():
            self.preview.request(path)


def get_open_file_name(parent, title: str, folder: str, flt: str, selected: str = "",
                       settings=None) -> str:
    in_fmt = settings.input_format() if settings is not None else None
    dlg = PreviewFileDialog(parent, title, folder, flt, selected, settings, in_fmt)
    if dlg.exec() == QFileDialog.Accepted:
        files = dlg.selectedFiles()
        return files[0] if files else ""
    return ""

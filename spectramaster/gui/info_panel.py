"""Side panel with the acquisition details of the displayed spectrum."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFormLayout, QFrame, QGroupBox,
                               QHeaderView, QLabel, QSizePolicy, QTableWidget, QTableWidgetItem,
                               QToolButton, QVBoxLayout, QWidget)

from ..model import Spectrum
from .i18n import tr
from .plot import format_count

FIELDS = ["file", "spectrum", "sample_id", "live_time", "real_time", "dead_time", "start",
          "channels", "total", "calibration", "format", "detector", "description"]

_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def format_seconds(v: Optional[float]) -> str:
    if v is None:
        return tr("none")
    return tr("seconds", v=f"{v:,.2f}")


def format_calibration(coeffs: list[float]) -> str:
    if not coeffs:
        return tr("uncalibrated")
    terms = []
    for power, c in enumerate(coeffs):
        if power and c == 0:
            continue
        num = f"{abs(c):.6g}" if terms else f"{c:.6g}"
        if power == 0:
            term = num
        elif power == 1:
            term = f"{num}·ch"
        else:
            term = f"{num}·ch{str(power).translate(_SUPERSCRIPT)}"
        if terms:
            terms.append(("− " if c < 0 else "+ ") + term)
        else:
            terms.append(term)
    return "E = " + " ".join(terms) + " keV"


def _ltr(text: str) -> str:
    """Force left-to-right paragraph direction (paths, numbers) inside RTL layouts."""
    return "‎" + text if text else text


class InfoPanel(QWidget):
    spectrumIndexChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self.group = QGroupBox()
        form = QFormLayout(self.group)
        form.setLabelAlignment(Qt.AlignLeading | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(7)
        self.labels: dict[str, QLabel] = {}
        self.values: dict[str, QLabel] = {}
        self.spectrum_combo = QComboBox()
        self.spectrum_combo.currentIndexChanged.connect(self._combo_changed)
        for key in FIELDS:
            lab = QLabel()
            lab.setObjectName("infoLabel")
            self.labels[key] = lab
            if key == "spectrum":
                form.addRow(lab, self.spectrum_combo)
                continue
            val = QLabel(tr("none"))
            val.setObjectName("infoValue")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            val.setWordWrap(True)
            val.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self.values[key] = val
            form.addRow(lab, val)
        self._form = form
        outer.addWidget(self.group)

        self.extra_toggle = QToolButton()
        self.extra_toggle.setCheckable(True)
        self.extra_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.extra_toggle.setArrowType(Qt.RightArrow)
        self.extra_toggle.setAutoRaise(True)
        self.extra_toggle.toggled.connect(self._toggle_extra)
        outer.addWidget(self.extra_toggle)

        self.extra_table = QTableWidget(0, 2)
        self.extra_table.verticalHeader().setVisible(False)
        self.extra_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.extra_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.extra_table.setAlternatingRowColors(True)
        self.extra_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.extra_table.horizontalHeader().setStretchLastSection(True)
        self.extra_table.setFrameShape(QFrame.StyledPanel)
        self.extra_table.setVisible(False)
        outer.addWidget(self.extra_table, 1)
        self._stretch = outer.addStretch(1)
        self._outer = outer

        self._spec: Optional[Spectrum] = None
        self._fmt_name = ""
        self.retranslate()
        self.set_spectrum(None)

    # ----------------------------------------------------------------- api
    def retranslate(self) -> None:
        self.group.setTitle(tr("info_title"))
        for key, lab in self.labels.items():
            lab.setText(tr("info_" + key) + ":")
        self.extra_table.setHorizontalHeaderLabels([tr("col_key"), tr("col_value")])
        self._update_extra_title()
        self._toggle_extra(self.extra_toggle.isChecked())
        self._fill_combo_texts()
        self.set_spectrum(self._spec, self._fmt_name, keep_combo=True)

    def set_spectra_count(self, n: int, current: int = 0) -> None:
        self.spectrum_combo.blockSignals(True)
        self.spectrum_combo.clear()
        for i in range(n):
            self.spectrum_combo.addItem("")
        self._fill_combo_texts()
        self.spectrum_combo.setCurrentIndex(current if n else -1)
        self.spectrum_combo.blockSignals(False)
        visible = n > 1
        self.spectrum_combo.setVisible(visible)
        self.labels["spectrum"].setVisible(visible)

    def _fill_combo_texts(self) -> None:
        n = self.spectrum_combo.count()
        for i in range(n):
            self.spectrum_combo.setItemText(i, tr("spectrum_n_of_m", i=i + 1, n=n))

    def set_spectrum(self, spec: Optional[Spectrum], fmt_name: str = "", keep_combo: bool = False) -> None:
        self._spec = spec
        self._fmt_name = fmt_name
        if not keep_combo and spec is None:
            self.set_spectra_count(0)
        v = self.values
        none = tr("none")
        if spec is None:
            for lab in v.values():
                lab.setText(none)
                lab.setToolTip("")
            self._fill_extra({})
            return
        v["file"].setText(Path(spec.source_path).name if spec.source_path else none)
        v["file"].setToolTip(spec.source_path)
        v["sample_id"].setText(spec.sample_id.strip() or none)
        v["live_time"].setText(format_seconds(spec.live_time))
        v["real_time"].setText(format_seconds(spec.real_time))
        dt = spec.dead_time_percent
        v["dead_time"].setText(_ltr(f"{dt:.2f} %") if dt is not None else none)
        v["start"].setText(_ltr(spec.start_time.strftime("%Y-%m-%d  %H:%M:%S")) if spec.start_time else none)
        ch = f"{spec.num_channels:,}"
        if spec.first_channel:
            ch += f"  ({spec.first_channel} – {spec.first_channel + spec.num_channels - 1})"
        v["channels"].setText(_ltr(ch))
        v["total"].setText(_ltr(format_count(spec.total_counts)))
        v["calibration"].setText(_ltr(format_calibration(spec.energy_coeffs)))
        v["format"].setText(fmt_name or spec.source_format or none)
        v["detector"].setText(spec.detector.strip() or none)
        v["description"].setText(spec.description.strip() or none)
        self._fill_extra(spec.extra or {})

    def value_text(self, key: str) -> str:
        return self.values[key].text().lstrip("‎")

    # -------------------------------------------------------------- extra
    def _fill_extra(self, extra: dict) -> None:
        t = self.extra_table
        t.setRowCount(0)
        items = [(str(k), v) for k, v in extra.items()]
        t.setRowCount(len(items))
        for row, (k, val) in enumerate(items):
            if isinstance(val, float):
                text = f"{val:.6g}"
            elif isinstance(val, (list, tuple)):
                text = ", ".join(f"{x:.6g}" if isinstance(x, float) else str(x) for x in val)
            else:
                text = str(val)
            ki = QTableWidgetItem(k)
            has_arabic = any("؀" <= ch <= "ۿ" for ch in text)
            vi = QTableWidgetItem(text if has_arabic else _ltr(text))
            vi.setToolTip(text)
            t.setItem(row, 0, ki)
            t.setItem(row, 1, vi)
        self._update_extra_title()
        self.extra_toggle.setEnabled(bool(items))
        if not items:
            self.extra_toggle.setChecked(False)

    def _update_extra_title(self) -> None:
        n = self.extra_table.rowCount()
        self.extra_toggle.setText(tr("info_extra_count", n=n) if n else tr("info_extra"))

    def _toggle_extra(self, on: bool) -> None:
        rtl = self.layoutDirection() == Qt.RightToLeft
        self.extra_toggle.setArrowType(Qt.DownArrow if on else (Qt.LeftArrow if rtl else Qt.RightArrow))
        self.extra_table.setVisible(on)
        self._outer.setStretch(self._outer.count() - 1, 0 if on else 1)

    def changeEvent(self, ev):
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.LayoutDirectionChange:
            self._toggle_extra(self.extra_toggle.isChecked())
        super().changeEvent(ev)

    def _combo_changed(self, idx: int) -> None:
        if idx >= 0:
            self.spectrumIndexChanged.emit(idx)

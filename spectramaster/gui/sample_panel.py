"""Sample information and concentration display of the activity dialog (Release E, E5).

``SampleSection`` edits a :class:`spectramaster.lab.sample.SampleInfo` (an empty field is
unknown, never zero) plus the concentration unit and the relative uncertainty of the mass /
volume.  ``ConcentrationView`` shows the result of
:func:`spectramaster.analysis.activity.concentrations` (unit label, values, "< MDA", notes and
the missing inputs - with missing inputs no value is shown).
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateTimeEdit, QFormLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..lab.sample import CONCENTRATION_UNITS, MATRIX_TYPES, SampleInfo
from . import i18n
from .number_text import decimal_text
from .quant_strings import qtr

# unit proposed when the matrix changes (the user can choose another)
MATRIX_UNIT = {"soil": "Bq/kg", "food": "Bq/kg", "water": "Bq/L", "air_filter": "Bq/m3", "other": "Bq"}
# engine missing-input texts (lab.sample.SampleInfo.concentration_unit_inputs) -> string keys
MISSING_KEYS = {
    "sample mass (kg)": "conc_miss_mass",
    "mass basis (dry or wet)": "conc_miss_basis",
    "sample volume (L)": "conc_miss_volume",
    "sampled air volume (m3), or flow rate (m3/h) and sampling duration": "conc_miss_air",
    "measured filter fraction (1 if the whole filter was measured)": "conc_miss_fraction",
    "filter collection efficiency assumption": "conc_miss_eff",
}
CONC_COLS = ["conc_col_nuclide", "conc_col_value", "conc_col_mda", "conc_col_decision", "conc_col_factor"]


def _g(v, d=4) -> str:
    if v is None:
        return ""
    if v == 0 or not math.isfinite(v):
        return f"{v:g}"
    return f"{v:.{d}g}"


def unit_label(out: dict, sample: Optional[SampleInfo] = None) -> str:
    """Displayed unit: "Bq/kg (dry)" in English, the basis translated otherwise."""
    unit = out.get("unit", "") or ""
    if unit.startswith("Bq/kg (") and sample is not None and sample.mass_basis:
        return f"Bq/kg ({qtr('conc_basis_' + sample.mass_basis).split(' (')[0]})"
    return unit.replace("m3", "m³")


def missing_text(missing) -> str:
    return "; ".join(qtr(MISSING_KEYS[m]) if m in MISSING_KEYS else m for m in missing)


def translated_notes(out: dict, sample: Optional[SampleInfo]) -> list[str]:
    """The notes of concentrations(), translated (unknown notes kept as they are)."""
    res = []
    for n in out.get("notes", []):
        if n.startswith("concentration not computed"):
            res.append(qtr("conc_missing", items=missing_text(out.get("missing", []))))
        elif n.startswith("air volume") and sample is not None:
            note = sample.collection_efficiency_note
            res.append(qtr("conc_note_air", volume=i18n.ltr(_g(sample.air_volume())),
                           fraction=i18n.ltr(f"{sample.filter_fraction:g}"),
                           eff=i18n.ltr(f"{sample.collection_efficiency:g}"),
                           note=(": " + note) if note else ""))
        elif n.startswith("acquisition start unknown"):
            res.append(qtr("conc_note_no_start"))
        elif n.startswith("sampling end not given"):
            res.append(qtr("conc_note_no_end"))
        elif n.startswith("sampling duration not given"):
            res.append(qtr("conc_note_no_duration"))
        else:
            res.append(n)
    if (out.get("rows") and any(r.get("factor", 1.0) != 1.0 for r in out["rows"])
            and out.get("unit") == "Bq/m3"):
        res.append(qtr("conc_note_decay"))
    return res


def concentration_rows(out: dict) -> list[list[str]]:
    """Text rows (nuclide, value ± U, MDA, decision, factor) of concentrations()."""
    rows = []
    for r in out.get("rows", []):
        if r.get("value") is not None:
            val = f"{_g(r['value'])} ± {_g(r['U'], 2)}"
            dec = qtr("res_detected")
        elif r.get("mda"):
            val = f"< {_g(r['mda'], 3)}"
            dec = qtr("res_lt_mda")
        else:
            val = qtr("conc_not_determined")
            dec = qtr("res_lt_mda")
        rows.append([r["nuclide"], val, _g(r.get("mda"), 3), dec, f"{r.get('factor', 1.0):.4g}"])
    return rows


class SampleSection(QGroupBox):
    """Editor of the sample information needed for a concentration."""

    def __init__(self, parent=None, settings=None):
        super().__init__(qtr("conc_group"), parent)
        self.settings = settings
        self.form = QFormLayout(self)
        self._num: dict[str, QLineEdit] = {}

        row = QHBoxLayout()
        self.matrix_combo = QComboBox()
        for m in MATRIX_TYPES:
            self.matrix_combo.addItem(qtr("conc_matrix_" + m), m)
        row.addWidget(self.matrix_combo)
        row.addWidget(QLabel(qtr("conc_unit")))
        self.unit_combo = QComboBox()
        for u in CONCENTRATION_UNITS:
            self.unit_combo.addItem(qtr("conc_unit_" + u), u)
        row.addWidget(self.unit_combo)
        row.addStretch(1)
        self.form.addRow(qtr("conc_matrix"), row)
        hint = QLabel(qtr("conc_hint"))
        hint.setStyleSheet("color: #666;")
        self.form.addRow("", hint)

        # Bq/kg
        row = QHBoxLayout()
        row.addWidget(self._number("mass_kg"))
        row.addWidget(QLabel(qtr("conc_basis")))
        self.basis_combo = QComboBox()
        self.basis_combo.addItem(qtr("conc_basis_none"), None)
        self.basis_combo.addItem(qtr("conc_basis_dry"), "dry")
        self.basis_combo.addItem(qtr("conc_basis_wet"), "wet")
        row.addWidget(self.basis_combo)
        row.addStretch(1)
        self.mass_row = self._row(qtr("conc_mass"), row)
        # Bq/L
        self.volume_row = self._row(qtr("conc_volume"), self._number("volume_l"))
        # Bq/m3
        self.start_check, self.start_edit, w = self._date()
        self.start_row = self._row(qtr("conc_start"), w)
        self.end_check, self.end_edit, w = self._date()
        self.end_row = self._row(qtr("conc_end"), w)
        row = QHBoxLayout()
        row.addWidget(self._number("sampling_duration_h"))
        row.addWidget(QLabel(qtr("conc_flow")))
        row.addWidget(self._number("flow_rate_m3_h"))
        row.addWidget(QLabel(qtr("conc_air_volume")))
        row.addWidget(self._number("air_volume_m3"))
        row.addStretch(1)
        self.air_row = self._row(qtr("conc_duration"), row)
        self.air_row[1].setToolTip(qtr("conc_air_hint"))
        row = QHBoxLayout()
        row.addWidget(self._number("filter_fraction", qtr("conc_fraction_hint")))
        row.addWidget(QLabel(qtr("conc_eff")))
        row.addWidget(self._number("collection_efficiency", qtr("conc_eff_hint")))
        row.addStretch(1)
        self.filter_row = self._row(qtr("conc_fraction"), row)
        self.eff_note = QLineEdit()
        self.eff_note_row = self._row(qtr("conc_eff_note"), self.eff_note)
        # all units
        self.qty_unc = self._number("quantity_rel_unc_pct", "0")
        self.unc_row = self._row(qtr("conc_qty_unc"), self.qty_unc)
        self.description = QLineEdit()
        self.form.addRow(qtr("conc_description"), self.description)

        m = str(settings.get("quant/matrix", "") or "") if settings is not None else ""
        u = str(settings.get("quant/conc_unit", "") or "") if settings is not None else ""
        if m in MATRIX_TYPES:
            self.matrix_combo.setCurrentIndex(self.matrix_combo.findData(m))
        if u not in CONCENTRATION_UNITS:
            u = MATRIX_UNIT.get(self.matrix(), "Bq")
        self.unit_combo.setCurrentIndex(self.unit_combo.findData(u))
        self.matrix_combo.currentIndexChanged.connect(self._matrix_changed)
        self.unit_combo.currentIndexChanged.connect(self._update_rows)
        self._update_rows()

    # ------------------------------------------------------------------ building
    def _number(self, name: str, placeholder: str = "") -> QLineEdit:
        e = QLineEdit()
        e.setLayoutDirection(Qt.LeftToRight)
        e.setMaximumWidth(110)
        e.setPlaceholderText(placeholder or "—")
        self._num[name] = e
        return e

    def _row(self, label: str, item):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        if isinstance(item, QWidget):
            lay.addWidget(item)
            lay.addStretch(1)
        else:
            lay.addLayout(item)
        lab = QLabel(label)
        self.form.addRow(lab, w)
        return (lab, w)

    def _date(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        check = QCheckBox(qtr("conc_given"))
        edit = QDateTimeEdit()
        edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        edit.setCalendarPopup(True)
        edit.setLayoutDirection(Qt.LeftToRight)
        edit.setDateTime(QDateTime.currentDateTime())
        edit.setEnabled(False)
        check.toggled.connect(edit.setEnabled)
        lay.addWidget(check)
        lay.addWidget(edit)
        lay.addStretch(1)
        return check, edit, w

    def _matrix_changed(self, *_):
        u = MATRIX_UNIT.get(self.matrix())
        if u:
            self.unit_combo.setCurrentIndex(self.unit_combo.findData(u))
        self._update_rows()

    def _update_rows(self, *_):
        unit = self.unit()
        for rows, on in (((self.mass_row,), unit == "Bq/kg"), ((self.volume_row,), unit == "Bq/L"),
                         ((self.start_row, self.end_row, self.air_row, self.filter_row, self.eff_note_row),
                          unit == "Bq/m3"),
                         ((self.unc_row,), unit != "Bq")):
            for lab, w in rows:
                lab.setVisible(on)
                w.setVisible(on)

    # ------------------------------------------------------------------ values
    def matrix(self) -> str:
        return str(self.matrix_combo.currentData())

    def unit(self) -> str:
        return str(self.unit_combo.currentData())

    def set_unit(self, unit: str) -> None:
        self.unit_combo.setCurrentIndex(self.unit_combo.findData(unit))

    def set_matrix(self, matrix: str) -> None:
        """Choose the matrix; the unit proposed for it is selected too."""
        self.matrix_combo.blockSignals(True)
        self.matrix_combo.setCurrentIndex(self.matrix_combo.findData(matrix))
        self.matrix_combo.blockSignals(False)
        self._matrix_changed()

    def set_value(self, name: str, value) -> None:
        """Fill one numeric field (None = unknown)."""
        self._num[name].setText("" if value is None else f"{value:g}")

    def set_basis(self, basis: Optional[str]) -> None:
        self.basis_combo.setCurrentIndex(max(0, self.basis_combo.findData(basis)))

    def set_sampling(self, start: Optional[datetime], end: Optional[datetime]) -> None:
        for check, edit, v in ((self.start_check, self.start_edit, start), (self.end_check, self.end_edit, end)):
            check.setChecked(v is not None)
            if v is not None:
                edit.setDateTime(QDateTime(v))

    def _float(self, name: str, label_key: str) -> Optional[float]:
        raw = self._num[name].text().strip()
        if not raw:
            return None
        field = qtr(label_key).rstrip(":")
        try:                                   # "1,000" is refused, not read as 1 (round-8 review, Codex M1)
            text = decimal_text(raw)
        except ValueError:
            raise ValueError(qtr("conc_ambiguous_number", field=field, text=raw)) from None
        try:
            return float(text)
        except ValueError:
            raise ValueError(qtr("conc_bad_number", field=field, text=raw)) from None

    def quantity_rel_unc(self) -> float:
        v = self._float("quantity_rel_unc_pct", "conc_qty_unc")
        if v is not None and not (math.isfinite(v) and v >= 0):     # round-8 review, Codex M2
            raise ValueError(qtr("conc_bad_unc", field=qtr("conc_qty_unc").rstrip(":"),
                                 text=self._num["quantity_rel_unc_pct"].text().strip()))
        return 0.0 if v is None else v / 100.0

    def sample_info(self, sample_id: str = "", reference_date=None) -> SampleInfo:
        """The SampleInfo of the fields (only the fields of the chosen unit are used).
        Raises ValueError with a translated message for invalid input."""
        unit = self.unit()
        kw = {}
        if unit == "Bq/kg":
            kw["mass_kg"] = self._float("mass_kg", "conc_mass")
            kw["mass_basis"] = self.basis_combo.currentData()
        elif unit == "Bq/L":
            kw["volume_l"] = self._float("volume_l", "conc_volume")
        elif unit == "Bq/m3":
            for name, key in (("sampling_duration_h", "conc_duration"), ("flow_rate_m3_h", "conc_flow"),
                              ("air_volume_m3", "conc_air_volume"), ("filter_fraction", "conc_fraction"),
                              ("collection_efficiency", "conc_eff")):
                kw[name] = self._float(name, key)
            for name, check, edit in (("sampling_start", self.start_check, self.start_edit),
                                      ("sampling_end", self.end_check, self.end_edit)):
                kw[name] = edit.dateTime().toPython() if check.isChecked() else None
            kw["collection_efficiency_note"] = self.eff_note.text().strip()
        try:
            info = SampleInfo(sample_id=sample_id, matrix_type=self.matrix(), description=self.description.text().strip(),
                              reference_date=reference_date, **kw)
        except ValueError as exc:
            raise ValueError(qtr("conc_invalid", msg=str(exc))) from None
        if self.settings is not None:
            self.settings.set("quant/matrix", self.matrix())
            self.settings.set("quant/conc_unit", unit)
        return info


class ConcentrationView(QWidget):
    """Title (unit), missing inputs / notes and the concentration table."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.out: Optional[dict] = None
        self.sample: Optional[SampleInfo] = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel("")
        self.title.setStyleSheet("font-weight: bold;")
        lay.addWidget(self.title)
        self.notes_label = QLabel("")
        self.notes_label.setWordWrap(True)
        self.notes_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.notes_label)
        self.table = QTableWidget(0, len(CONC_COLS))
        self.table.setHorizontalHeaderLabels([qtr(k) for k in CONC_COLS])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table, 1)

    def clear(self) -> None:
        self.out = self.sample = None
        self.title.setText("")
        self.notes_label.setText("")
        self.table.setRowCount(0)

    def show_error(self, text: str) -> None:
        self.clear()
        self.title.setText(qtr("conc_none"))
        self.notes_label.setText("⚠ " + text)
        self.notes_label.setStyleSheet("color: #c62828; font-weight: bold;")

    def show_result(self, out: dict, sample: Optional[SampleInfo]) -> None:
        self.out, self.sample = out, sample
        label = unit_label(out, sample)
        self.title.setText(qtr("conc_title", unit=i18n.ltr(label)))
        header = [qtr(k) for k in CONC_COLS]
        header[1] += f" [{label}]"
        header[2] += f" [{label}]"
        self.table.setHorizontalHeaderLabels(header)
        notes = translated_notes(out, sample)
        missing = bool(out.get("missing"))
        self.notes_label.setText("\n".join("⚠ " + n for n in notes))
        self.notes_label.setStyleSheet("color: %s; font-weight: bold;" % ("#c62828" if missing else "#e65100"))
        rows = concentration_rows(out)
        self.table.setRowCount(len(rows))
        for r, (vals, raw) in enumerate(zip(rows, out.get("rows", []))):
            for c, v in enumerate(vals):
                it = QTableWidgetItem(i18n.ltr(v) if c in (1, 2, 4) and v else v)
                if c in (1, 2, 4):
                    it.setTextAlignment(Qt.AlignAbsolute | Qt.AlignRight | Qt.AlignVCenter)
                if c == 3:
                    detected = raw.get("value") is not None
                    it.setForeground(QBrush(QColor(20, 130, 40) if detected else QColor(120, 120, 120)))
                self.table.setItem(r, c, it)

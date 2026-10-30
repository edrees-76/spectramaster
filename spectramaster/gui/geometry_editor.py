"""Editor of a measurement geometry (:class:`spectramaster.lab.detector.MeasurementGeometry`).

Used by the efficiency-calibration wizard (geometry of the standard, stored in
``EfficiencyCurve.geometry_record``) and by the activity dialog (geometry of the sample,
checked against the calibration by ``analysis.activity``).  Empty fields stay ``None``:
a missing value is never replaced by 0, so the conservative compatibility check reports it
as unknown.  Only the fields that matter for the chosen kind are written.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QVBoxLayout, QWidget)

from ..lab.detector import GEOMETRY_KINDS, MeasurementGeometry
from .number_text import decimal_text
from .quant_strings import qtr

CONTAINER_KINDS = ("marinelli", "cylinder", "other")
# container dimensions shown per kind (keys of MeasurementGeometry.dimensions, mm)
DIMS = {"marinelli": ("diameter_mm", "height_mm", "well_diameter_mm", "well_depth_mm"),
        "cylinder": ("diameter_mm", "height_mm"),
        "other": ("diameter_mm", "height_mm")}
ALL_DIMS = ("diameter_mm", "height_mm", "well_diameter_mm", "well_depth_mm")
FILTER_DIMS = ("diameter_mm", "width_mm", "length_mm")


def _parse(text: str) -> Optional[float]:
    """Number of a field ('' -> None); ValueError for text that is not a number."""
    s = decimal_text(text)                 # ambiguous "1,000": ValueError (round-8 review, Codex M1)
    if not s:
        return None
    return float(s)


def _fmt(v) -> str:
    return "" if v is None else f"{float(v):g}"


def default_geometry_dir() -> Path:
    from ..analysis.efficiency import default_curve_dir
    return default_curve_dir() / "geometries"


class GeometryEditor(QWidget):
    """Kind + container (Marinelli / cylinder) fields, point-source distance, filter fields.

    ``name_edit``: an existing QLineEdit holding the geometry name (the efficiency dialog
    keeps its own); without it the editor shows a name field of its own."""

    changed = Signal()

    def __init__(self, parent=None, name_edit: Optional[QLineEdit] = None):
        super().__init__(parent)
        self._id: Optional[str] = None
        self._own_name = name_edit is None
        self.name_edit = name_edit if name_edit is not None else QLineEdit()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        grid = QGridLayout()
        self._rows: dict[str, tuple[QLabel, QWidget]] = {}
        self._labels: dict[str, str] = {}
        r = 0

        def add(key: str, widget: QWidget, label_key: str, col: int = 0):
            nonlocal r
            lab = QLabel(qtr(label_key))
            grid.addWidget(lab, r // 2, 2 * (r % 2))
            grid.addWidget(widget, r // 2, 2 * (r % 2) + 1)
            self._rows[key] = (lab, widget)
            self._labels[key] = qtr(label_key).rstrip(":")
            r += 1

        def num_edit() -> QLineEdit:
            e = QLineEdit()
            e.setLayoutDirection(Qt.LeftToRight)
            e.setPlaceholderText(qtr("geo_unknown"))
            e.textChanged.connect(self.changed)
            return e

        def text_edit() -> QLineEdit:
            e = QLineEdit()
            e.setPlaceholderText(qtr("geo_unknown"))
            e.textChanged.connect(self.changed)
            return e

        if self._own_name:
            self.name_edit.setPlaceholderText(qtr("geo_name_hint"))
            self.name_edit.textChanged.connect(self.changed)
            add("name", self.name_edit, "geo_name")
        self.kind_combo = QComboBox()
        for k in GEOMETRY_KINDS:
            self.kind_combo.addItem(qtr("geo_kind_" + k), k)
        self.kind_combo.currentIndexChanged.connect(self._kind_changed)
        add("kind", self.kind_combo, "geo_kind")
        self.container_edit = text_edit()
        add("container_id", self.container_edit, "geo_container")
        self.nominal_edit = num_edit()
        add("nominal_volume_ml", self.nominal_edit, "geo_nominal")
        self.dim_edits: dict[str, QLineEdit] = {}
        for k in ALL_DIMS:
            self.dim_edits[k] = num_edit()
            add("dim_" + k, self.dim_edits[k], "geo_dim_" + k)
        self.fill_volume_edit = num_edit()
        add("fill_volume_ml", self.fill_volume_edit, "geo_fill_volume")
        self.fill_height_edit = num_edit()
        add("fill_height_mm", self.fill_height_edit, "geo_fill_height")
        self.matrix_edit = text_edit()
        add("matrix", self.matrix_edit, "geo_matrix")
        self.density_edit = num_edit()
        add("density_g_cm3", self.density_edit, "geo_density")
        self.distance_edit = num_edit()
        add("source_distance_mm", self.distance_edit, "geo_distance")
        self.filter_shape_edit = text_edit()
        add("filter_shape", self.filter_shape_edit, "geo_filter_shape")
        self.filter_dim_edits: dict[str, QLineEdit] = {}
        for k in FILTER_DIMS:
            self.filter_dim_edits[k] = num_edit()
            add("fdim_" + k, self.filter_dim_edits[k], "geo_fdim_" + k)
        self.filter_position_edit = text_edit()
        add("filter_position", self.filter_position_edit, "geo_filter_position")
        self.arrangement_edit = text_edit()
        add("arrangement", self.arrangement_edit, "geo_arrangement")
        self.note_edit = QLineEdit()
        self.note_edit.textChanged.connect(self.changed)
        add("note", self.note_edit, "geo_note")
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        lay.addLayout(grid)
        hint = QLabel(qtr("geo_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")
        lay.addWidget(hint)
        row = QHBoxLayout()
        b = QPushButton(qtr("geo_load"))
        b.clicked.connect(lambda: self.load_file())
        row.addWidget(b)
        b = QPushButton(qtr("geo_save"))
        b.clicked.connect(lambda: self.save_file())
        row.addWidget(b)
        b = QPushButton(qtr("geo_clear"))
        b.clicked.connect(lambda: self.set_geometry(None))
        row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.kind_combo.setCurrentIndex(max(0, self.kind_combo.findData("other")))
        self._kind_changed()

    # ------------------------------------------------------------------ helpers
    def kind(self) -> str:
        return self.kind_combo.currentData() or "other"

    def _show_row(self, key: str, on: bool) -> None:
        lab, w = self._rows[key]
        lab.setVisible(on)
        w.setVisible(on)

    def _kind_changed(self, *_):
        k = self.kind()
        cont = k in CONTAINER_KINDS
        for key in ("container_id", "nominal_volume_ml", "fill_volume_ml", "fill_height_mm", "matrix",
                    "density_g_cm3"):
            self._show_row(key, cont)
        self._show_row("container_id", cont or k == "point")
        self._rows["container_id"][0].setText(qtr("geo_holder") if k == "point" else qtr("geo_container"))
        for d in ALL_DIMS:
            self._show_row("dim_" + d, cont and d in DIMS.get(k, ()))
        self._show_row("source_distance_mm", k in ("point", "filter", "other"))
        for key in ("filter_shape", "filter_position"):
            self._show_row(key, k == "filter")
        for d in FILTER_DIMS:
            self._show_row("fdim_" + d, k == "filter")
        self.changed.emit()

    def _num(self, key: str, edit: QLineEdit) -> Optional[float]:
        try:
            return _parse(edit.text())
        except ValueError:
            raise ValueError(qtr("geo_bad_number", field=self._labels.get(key, key), text=edit.text())) from None

    @staticmethod
    def _text(edit: QLineEdit) -> Optional[str]:
        t = edit.text().strip()
        return t or None

    # ------------------------------------------------------------------ model <-> fields
    def geometry(self, name: Optional[str] = None) -> MeasurementGeometry:
        """The geometry described by the fields (ValueError with a translated message for
        invalid numbers).  The id stays the same for the life of the editor / loaded record."""
        k = self.kind()
        cont = k in CONTAINER_KINDS
        kw: dict = {"kind": k, "arrangement": self.arrangement_edit.text().strip(),
                    "note": self.note_edit.text().strip()}
        if cont or k == "point":
            kw["container_id"] = self._text(self.container_edit)
        if cont:
            kw["nominal_volume_ml"] = self._num("nominal_volume_ml", self.nominal_edit)
            dims = {}
            for d in DIMS.get(k, ()):
                v = self._num("dim_" + d, self.dim_edits[d])
                if v is not None:              # absent = unknown (never 0)
                    dims[d] = v
            kw["dimensions"] = dims
            kw["fill_volume_ml"] = self._num("fill_volume_ml", self.fill_volume_edit)
            kw["fill_height_mm"] = self._num("fill_height_mm", self.fill_height_edit)
            kw["matrix"] = self._text(self.matrix_edit)
            kw["density_g_cm3"] = self._num("density_g_cm3", self.density_edit)
        if k in ("point", "filter", "other"):
            kw["source_distance_mm"] = self._num("source_distance_mm", self.distance_edit)
        if k == "filter":
            kw["filter_shape"] = self._text(self.filter_shape_edit)
            kw["filter_position"] = self._text(self.filter_position_edit)
            fd = {}
            for d in FILTER_DIMS:
                v = self._num("fdim_" + d, self.filter_dim_edits[d])
                if v is not None:
                    fd[d] = v
            kw["filter_dimensions"] = fd
        nm = (name if name is not None else self.name_edit.text()).strip() or qtr("geo_unnamed")
        if self._id:
            kw["id"] = self._id
        try:
            g = MeasurementGeometry(name=nm, **kw)
        except ValueError as exc:       # e.g. a volume <= 0
            raise ValueError(qtr("geo_invalid", msg=str(exc))) from None
        self._id = g.id
        return g

    def set_geometry(self, g) -> None:
        """Fill the fields from a MeasurementGeometry, its dict, or None (clear)."""
        if isinstance(g, dict):
            g = MeasurementGeometry.from_dict(g) if g else None
        edits = [self.container_edit, self.nominal_edit, self.fill_volume_edit, self.fill_height_edit,
                 self.matrix_edit, self.density_edit, self.distance_edit, self.filter_shape_edit,
                 self.filter_position_edit, self.arrangement_edit, self.note_edit,
                 *self.dim_edits.values(), *self.filter_dim_edits.values()]
        for e in edits:
            e.clear()
        if g is None:
            self._id = None
            if self._own_name:
                self.name_edit.clear()
            self.kind_combo.setCurrentIndex(max(0, self.kind_combo.findData("other")))
            return
        self._id = g.id
        self.name_edit.setText(g.name or "")
        self.kind_combo.setCurrentIndex(max(0, self.kind_combo.findData(g.kind)))
        self.container_edit.setText(g.container_id or "")
        self.nominal_edit.setText(_fmt(g.nominal_volume_ml))
        for k, v in (g.dimensions or {}).items():
            if k in self.dim_edits:
                self.dim_edits[k].setText(_fmt(v))
        self.fill_volume_edit.setText(_fmt(g.fill_volume_ml))
        self.fill_height_edit.setText(_fmt(g.fill_height_mm))
        self.matrix_edit.setText(g.matrix or "")
        self.density_edit.setText(_fmt(g.density_g_cm3))
        self.distance_edit.setText(_fmt(g.source_distance_mm))
        self.filter_shape_edit.setText(g.filter_shape or "")
        self.filter_position_edit.setText(g.filter_position or "")
        for k, v in (g.filter_dimensions or {}).items():
            if k in self.filter_dim_edits:
                self.filter_dim_edits[k].setText(_fmt(v))
        self.arrangement_edit.setText(g.arrangement or "")
        self.note_edit.setText(g.note or "")
        self._kind_changed()

    def is_empty(self) -> bool:
        """True when nothing beyond the kind has been entered."""
        try:
            g = self.geometry(name="x")
        except ValueError:
            return False
        d = g.to_dict()
        skip = {"name", "kind", "id", "dimensions", "filter_dimensions", "arrangement", "note"}
        return (not any(v is not None for k, v in d.items() if k not in skip)
                and not g.dimensions and not g.filter_dimensions and not g.arrangement and not g.note)

    # ------------------------------------------------------------------ files
    def save_file(self, path: Optional[str] = None) -> Optional[Path]:
        try:
            g = self.geometry()
        except ValueError as exc:
            QMessageBox.warning(self, qtr("geo_title"), str(exc))
            return None
        if not path:
            d = default_geometry_dir()
            d.mkdir(parents=True, exist_ok=True)
            stem = (g.name or "geometry").strip().replace(" ", "_")
            path, _ = QFileDialog.getSaveFileName(self, qtr("geo_save"), str(d / f"{stem}.json"), "JSON (*.json)")
            if not path:
                return None
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        d = {"format": "spectramaster-geometry-1", **g.to_dict()}
        p.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
        return p

    def load_file(self, path: Optional[str] = None) -> bool:
        if not path:
            d = default_geometry_dir()
            path, _ = QFileDialog.getOpenFileName(self, qtr("geo_load"), str(d if d.is_dir() else ""),
                                                  "JSON (*.json)")
            if not path:
                return False
        try:
            d = json.loads(Path(path).read_text(encoding="utf-8"))
            if "payload" in d and isinstance(d.get("payload"), dict):     # a calibration record
                d = d["payload"].get("geometry_record") or {}
            elif "geometry_record" in d:                                    # an efficiency curve
                d = d.get("geometry_record") or {}
            if not d:
                raise ValueError(qtr("geo_none_in_file"))
            self.set_geometry(MeasurementGeometry.from_dict(d))
        except Exception as exc:
            QMessageBox.warning(self, qtr("geo_title"), qtr("geo_load_failed", msg=str(exc)))
            return False
        return True

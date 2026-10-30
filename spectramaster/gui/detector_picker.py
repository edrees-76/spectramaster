"""Detector picker (plan D5): detector profiles of the laboratory and the measurement context of
the analysis session.

* :class:`DetectorEditor` / :class:`DetectorManagerDialog` create, edit and delete the
  :class:`~spectramaster.lab.detector.DetectorProfile` entries of the
  :class:`~.detector_registry.DetectorRegistry` (one JSON file per permanent id).
* :class:`SessionContextBar` sits at the top of the workflow dock: the *Detector:* combo records the
  chosen profile in the session (``AnalysisSession.set_detector``: a full snapshot plus its id,
  through the undoable edit history; existing results are marked as requiring an update by the
  engine), next to the detector label read from the spectrum file (shown, never overwritten), and
  the measurement geometry of the sample (edited with :class:`~.geometry_editor.GeometryEditor`).
  With a detector recorded, :func:`~spectramaster.lab.workflow.workflow_status` reports an
  efficiency calibration of another detector as ``incompatible_calibration``.
* :func:`fill_detector_combo` lists the profiles in a combo (the efficiency wizard uses it so the
  calibration record gets the detector id).

The links are ids, never names.  Nothing scientific is computed here.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

from ..lab.detector import DETECTOR_TYPES, DetectorProfile, MeasurementGeometry
from . import i18n
from .context_strings import ctr, detector_type_label
from .detector_registry import DetectorRegistry
from .number_text import decimal_text

CONTEXT_TARGETS = (["detector"], ["geometry"])


def profile_text(p: DetectorProfile) -> str:
    """Display text of a profile: name, type and serial number."""
    extra = detector_type_label(p.type)
    if p.serial:
        extra += f", {p.serial}"
    return f"{p.name} ({extra})"


def profile_tooltip(p: DetectorProfile) -> str:
    rows = [f"{ctr('ed_type')} {detector_type_label(p.type)}"]
    for key, v in (("ed_manufacturer", p.manufacturer), ("ed_model", p.model), ("ed_serial", p.serial),
                   ("ed_releff", p.relative_efficiency_pct), ("ed_diameter", p.crystal_diameter_mm),
                   ("ed_length", p.crystal_length_mm), ("ed_note", p.note)):
        if v not in (None, ""):
            rows.append(f"{ctr(key)} {i18n.ltr(f'{v:g}' if isinstance(v, float) else v)}")
    rows.append(peak_shape_text(p.peak_shape))
    rows.append(f"id {i18n.ltr(p.id)}")
    return "\n".join(rows)


def peak_shape_text(shape: Optional[dict]) -> str:
    """One line describing a detector's peak-shape calibration (translated)."""
    if not shape:
        return ctr("shape_none")
    if not shape.get("eta"):
        return ctr("shape_gaussian", n=shape.get("n_peaks") or 0)
    return ctr("shape_tail", eta=i18n.ltr(f"{100 * float(shape['eta']):.2g} %"),
               tau=i18n.ltr(f"{float(shape['tau']):g}"), n=shape.get("n_peaks") or 0)


def fill_detector_combo(combo: QComboBox, registry: DetectorRegistry, select: Optional[str] = None,
                        snapshot: Optional[dict] = None) -> None:
    """Fill `combo` with "(not recorded)" and the registry's profiles (item data = id) and select
    `select`.  A selected id missing from the registry is added from `snapshot` (or as the id)."""
    combo.blockSignals(True)
    try:
        combo.clear()
        combo.addItem(ctr("detector_none"), None)
        for p in registry.list():
            combo.addItem(profile_text(p), p.id)
            combo.setItemData(combo.count() - 1, profile_tooltip(p), Qt.ToolTipRole)
        if select and combo.findData(select) < 0:
            name = (snapshot or {}).get("name") or select
            combo.addItem(ctr("detector_session_only", name=name), select)
        combo.setCurrentIndex(max(0, combo.findData(select)) if select else 0)
    finally:
        combo.blockSignals(False)


def _num(text: str, field: str) -> Optional[float]:
    try:
        s = decimal_text(text)             # ambiguous "1,000" refused (round-8 review, Codex M1)
        if not s:
            return None
        return float(s)
    except ValueError:
        raise ValueError(ctr("ed_err_number", field=field.rstrip(":"), text=text)) from None


def _fmt(v) -> str:
    return "" if v is None else f"{float(v):g}"


# ===================================================================== profile editor
class DetectorEditor(QDialog):
    """Fields of one detector profile.  Editing keeps the id, the data-sheet FWHM and the lists of
    linked calibrations."""

    def __init__(self, parent=None, profile: Optional[DetectorProfile] = None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.setWindowTitle(ctr("ed_title"))
        self.base = profile
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        form.addRow(ctr("ed_name"), self.name_edit)
        self.type_combo = QComboBox()
        for t in DETECTOR_TYPES:
            self.type_combo.addItem(detector_type_label(t), t)
        form.addRow(ctr("ed_type"), self.type_combo)
        self.edits: dict[str, QLineEdit] = {}
        for attr, key, numeric in (("manufacturer", "ed_manufacturer", False), ("model", "ed_model", False),
                                   ("serial", "ed_serial", False),
                                   ("relative_efficiency_pct", "ed_releff", True),
                                   ("crystal_diameter_mm", "ed_diameter", True),
                                   ("crystal_length_mm", "ed_length", True), ("note", "ed_note", False)):
            e = QLineEdit()
            if numeric:
                e.setLayoutDirection(Qt.LeftToRight)
                e.setPlaceholderText(ctr("ed_unknown"))
            self.edits[attr] = e
            form.addRow(ctr(key), e)
        lay.addLayout(form)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #c62828;")
        self.error_label.setWordWrap(True)
        lay.addWidget(self.error_label)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        if profile is not None:
            self.set_profile(profile)

    def set_profile(self, p: DetectorProfile) -> None:
        self.base = p
        self.name_edit.setText(p.name)
        self.type_combo.setCurrentIndex(max(0, self.type_combo.findData(p.type)))
        for attr, e in self.edits.items():
            v = getattr(p, attr)
            e.setText(_fmt(v) if attr.endswith(("_pct", "_mm")) else (v or ""))

    def profile(self) -> DetectorProfile:
        """The profile described by the fields (ValueError with a translated message)."""
        name = self.name_edit.text().strip()
        if not name:
            raise ValueError(ctr("ed_err_name"))
        kw = {"name": name, "type": self.type_combo.currentData()}
        labels = {"relative_efficiency_pct": "ed_releff", "crystal_diameter_mm": "ed_diameter",
                  "crystal_length_mm": "ed_length"}
        for attr, e in self.edits.items():
            if attr in labels:
                kw[attr] = _num(e.text(), ctr(labels[attr]))
            elif attr == "note":
                kw[attr] = e.text().strip()
            else:
                kw[attr] = e.text().strip() or None
        b = self.base
        if b is not None:
            kw.update(id=b.id, nominal_fwhm=b.nominal_fwhm, energy_calibration_ids=list(b.energy_calibration_ids),
                      fwhm_calibration_ids=list(b.fwhm_calibration_ids),
                      efficiency_calibration_ids=list(b.efficiency_calibration_ids),
                      peak_shape=dict(b.peak_shape))
        try:
            return DetectorProfile(**kw)
        except ValueError as exc:          # e.g. a dimension <= 0
            raise ValueError(str(exc)) from None

    def accept(self) -> None:
        try:
            self.profile()
        except ValueError as exc:
            self.error_label.setText(str(exc))
            return
        super().accept()


# ===================================================================== manager
class _ReadError(Exception):
    """A calibration spectrum could not be read (message: "Type: text" of the cause)."""


def _measure_shape(files: list) -> dict:
    """Read the calibration spectra and measure the peak shape (no widget access: worker thread)."""
    from ..analysis.peaks import shape_calibration
    from ..convert import read_spectra
    spectra = []
    try:
        for f in files:
            spectra.extend(read_spectra(f)[0])
    except Exception as exc:
        raise _ReadError(f"{type(exc).__name__}: {exc}") from exc
    return shape_calibration(spectra)


class DetectorManagerDialog(QDialog):
    """List of the registry's profiles with New / Edit / Delete.  ``ask_profile`` and ``confirm`` are
    separate methods so tests can replace them."""

    def __init__(self, parent=None, registry: Optional[DetectorRegistry] = None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.setWindowTitle(ctr("mgr_title"))
        self.resize(560, 380)
        self.registry = registry or DetectorRegistry()
        lay = QVBoxLayout(self)
        intro = QLabel(ctr("mgr_intro", folder=i18n.bidi_path(self.registry.root)))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        row = QHBoxLayout()
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _it: self.edit_selected())
        row.addWidget(self.list, 1)
        col = QVBoxLayout()
        self.btn_new = QPushButton(ctr("mgr_new"))
        self.btn_new.clicked.connect(lambda: self.new_profile())
        self.btn_edit = QPushButton(ctr("mgr_edit"))
        self.btn_edit.clicked.connect(lambda: self.edit_selected())
        self.btn_delete = QPushButton(ctr("mgr_delete"))
        self.btn_delete.clicked.connect(lambda: self.delete_selected())
        self.btn_shape = QPushButton(ctr("mgr_shape"))
        self.btn_shape.setToolTip(ctr("mgr_shape_tip"))
        self.btn_shape.clicked.connect(lambda: self.measure_shape_selected(threaded=True))
        for b in (self.btn_new, self.btn_edit, self.btn_delete, self.btn_shape):
            col.addWidget(b)
        col.addStretch(1)
        row.addLayout(col)
        lay.addLayout(row, 1)
        self.busy_label = QLabel("")
        lay.addWidget(self.busy_label)
        self._shape_pending = None
        self.problems_label = QLabel("")
        self.problems_label.setWordWrap(True)
        self.problems_label.setStyleSheet("color: #e65100;")
        lay.addWidget(self.problems_label)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText(ctr("mgr_close"))
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)
        self.list.currentRowChanged.connect(lambda _r: self._sync())
        self.refresh_list()

    # ------------------------------------------------------------ overridable
    def ask_profile(self, profile: Optional[DetectorProfile]) -> Optional[DetectorProfile]:
        dlg = DetectorEditor(self, profile)
        return dlg.profile() if dlg.exec() == QDialog.Accepted else None

    def confirm(self, title: str, text: str) -> bool:
        box = QMessageBox(QMessageBox.Question, title, text, QMessageBox.Yes | QMessageBox.No, self)
        box.setDefaultButton(QMessageBox.No)
        return box.exec() == QMessageBox.Yes

    def show_error(self, text: str) -> None:
        QMessageBox.warning(self, ctr("mgr_title"), text)

    def ask_spectrum_files(self) -> list[str]:
        """Calibration spectra of the selected detector (tests replace this)."""
        from PySide6.QtWidgets import QFileDialog
        files, _f = QFileDialog.getOpenFileNames(self, ctr("shape_pick_title"))
        return list(files)

    # ------------------------------------------------------------ list
    def refresh_list(self, select: Optional[str] = None) -> None:
        self.list.clear()
        for p in self.registry.list():
            it = QListWidgetItem(profile_text(p))
            it.setData(Qt.UserRole, p.id)
            it.setToolTip(profile_tooltip(p))
            self.list.addItem(it)
            if p.id == select:
                self.list.setCurrentItem(it)
        probs = self.registry.problems
        self.problems_label.setText(ctr("mgr_problems", files=i18n.ltr("; ".join(probs))) if probs else "")
        self._sync()

    def ids(self) -> list[str]:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]

    def selected_id(self) -> Optional[str]:
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it is not None else None

    def select(self, detector_id: str) -> None:
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == detector_id:
                self.list.setCurrentRow(i)

    def _sync(self) -> None:
        has = self.selected_id() is not None and self._shape_pending is None
        self.btn_edit.setEnabled(has)
        self.btn_delete.setEnabled(has)
        self.btn_shape.setEnabled(has)
        self.btn_new.setEnabled(self._shape_pending is None)

    @property
    def busy(self) -> bool:
        return self._shape_pending is not None

    # ------------------------------------------------------------ commands
    def _save(self, p: DetectorProfile) -> Optional[str]:
        try:
            self.registry.save(p)
        except Exception as exc:
            self.show_error(ctr("mgr_err_save", msg=f"{type(exc).__name__}: {exc}"))
            return None
        self.refresh_list(p.id)
        return p.id

    def new_profile(self) -> Optional[str]:
        p = self.ask_profile(None)
        return self._save(p) if p is not None else None

    def edit_selected(self) -> Optional[str]:
        p = self.registry.get(self.selected_id())
        if p is None:
            return None
        new = self.ask_profile(p)
        return self._save(new) if new is not None else None

    def measure_shape_selected(self, files: Optional[list] = None, threaded: bool = False) -> Optional[dict]:
        """Measure the peak shape (low-energy tail) of the selected detector on calibration spectra
        and, after confirmation, record it in its profile.  Returns the recorded shape; with
        `threaded` (the button) the spectra are read and measured on a worker thread, the
        confirmation follows when it finishes, and None is returned."""
        if self._shape_pending is not None:
            return None
        p = self.registry.get(self.selected_id())
        if p is None:
            return None
        files = list(files) if files is not None else self.ask_spectrum_files()
        if not files:
            return None
        if threaded:
            from .worker import start_call
            self._shape_pending = (p.id, files)
            self.busy_label.setText(ctr("shape_busy"))
            self._sync()
            start_call(self, lambda: _measure_shape(files), self._shape_done, self._shape_failed)
            return None
        try:
            cal = _measure_shape(files)
        except _ReadError as exc:
            self.show_error(ctr("shape_err_read", msg=str(exc)))
            return None
        return self._record_shape(p.id, files, cal)

    def _shape_finished(self):
        pending, self._shape_pending = self._shape_pending, None
        self.busy_label.setText("")
        self._sync()
        return pending

    def _shape_done(self, cal) -> None:
        pending = self._shape_finished()
        if pending is not None:
            self._record_shape(pending[0], pending[1], cal)

    def _shape_failed(self, msg: str) -> None:
        self._shape_finished()
        prefix = _ReadError.__name__ + ": "
        self.show_error(ctr("shape_err_read", msg=msg[len(prefix):] if msg.startswith(prefix) else msg))

    def _record_shape(self, detector_id: str, files: list, cal: dict) -> Optional[dict]:
        from pathlib import Path

        from ..analysis.peaks import TAIL_MIN_PEAKS
        p = self.registry.get(detector_id)
        if p is None:
            return None
        if cal["n_peaks"] < TAIL_MIN_PEAKS:
            self.show_error(ctr("shape_err_peaks", n=cal["n_peaks"], need=TAIL_MIN_PEAKS))
            return None
        if not self.confirm(ctr("shape_title"),
                            ctr("shape_confirm", name=i18n.ltr(p.name), result=peak_shape_text(cal))):
            return None
        p.set_peak_shape(cal, [Path(f).name for f in files])
        return dict(p.peak_shape) if self._save(p) else None

    def delete_selected(self) -> bool:
        p = self.registry.get(self.selected_id())
        if p is None:
            return False
        if not self.confirm(ctr("mgr_delete_title"), ctr("mgr_delete_text", name=i18n.ltr(p.name))):
            return False
        ok = self.registry.delete(p.id)
        self.refresh_list()
        return ok


# ===================================================================== geometry dialog
class GeometryDialog(QDialog):
    """The measurement geometry of the sample (GeometryEditor with its own name field)."""

    def __init__(self, parent=None, geometry: Optional[dict] = None):
        super().__init__(parent)
        from .geometry_editor import GeometryEditor
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.setWindowTitle(ctr("geo_title"))
        lay = QVBoxLayout(self)
        self.editor = GeometryEditor(self)
        if geometry:
            self.editor.set_geometry(geometry)
        lay.addWidget(self.editor)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #c62828;")
        self.error_label.setWordWrap(True)
        lay.addWidget(self.error_label)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def geometry(self) -> MeasurementGeometry:
        return self.editor.geometry()

    def accept(self) -> None:
        try:
            self.geometry()
        except ValueError as exc:
            self.error_label.setText(str(exc))
            return
        super().accept()


# ===================================================================== context bar
class SessionContextBar(QWidget):
    """Detector picker, detector label of the file and measurement geometry of the session of the
    displayed spectrum (top of the workflow dock).  ``ctl``: the SessionController."""

    def __init__(self, ctl, parent=None):
        super().__init__(parent)
        self.ctl = ctl
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 4)
        self.det_label = QLabel()
        grid.addWidget(self.det_label, 0, 0)
        self.det_combo = QComboBox()
        self.det_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.det_combo.setMinimumContentsLength(14)
        self.det_combo.activated.connect(self._activated)          # user choice only
        grid.addWidget(self.det_combo, 0, 1)
        self.btn_manage = QPushButton()
        self.btn_manage.clicked.connect(lambda: ctl.manage_detectors())
        grid.addWidget(self.btn_manage, 0, 2)
        self.file_label = QLabel()
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet("color: #6b7280;")
        grid.addWidget(self.file_label, 1, 1, 1, 2)
        self.geo_label = QLabel()
        grid.addWidget(self.geo_label, 2, 0)
        self.geo_value = QLabel()
        self.geo_value.setWordWrap(True)
        grid.addWidget(self.geo_value, 2, 1)
        self.btn_geo = QPushButton()
        self.btn_geo.clicked.connect(lambda: ctl.edit_geometry())
        grid.addWidget(self.btn_geo, 2, 2)
        self.btn_undo = QPushButton()
        self.btn_undo.clicked.connect(lambda: ctl.undo_context())
        grid.addWidget(self.btn_undo, 3, 2)
        grid.setColumnStretch(1, 1)

    def _activated(self, index: int) -> None:
        self.ctl.set_detector(self.det_combo.itemData(index))

    def choose(self, detector_id: Optional[str]) -> bool:
        """Select `detector_id` as a user would (tests)."""
        i = self.det_combo.findData(detector_id) if detector_id else 0
        if i < 0:
            return False
        self.det_combo.setCurrentIndex(i)
        self._activated(i)
        return True

    def selected_id(self) -> Optional[str]:
        return self.det_combo.currentData()

    def refresh(self) -> None:
        ctl = self.ctl
        s = ctl.session
        self.det_label.setText(ctr("detector"))
        self.det_combo.setToolTip(ctr("detector_tip"))
        self.btn_manage.setText(ctr("manage"))
        self.btn_manage.setToolTip(ctr("manage_tip"))
        self.geo_label.setText(ctr("geometry"))
        self.btn_geo.setText(ctr("geometry_edit"))
        self.btn_geo.setToolTip(ctr("geometry_tip"))
        self.btn_undo.setText(ctr("undo"))
        fill_detector_combo(self.det_combo, ctl.detector_registry(), s.detector_id if s else None,
                            s.detector if s else None)
        self.det_combo.setEnabled(s is not None)
        self.btn_geo.setEnabled(s is not None)
        spec = ctl.spectrum() if s is not None else None
        label = (getattr(spec, "detector", "") or "").strip() if spec is not None else ""
        self.file_label.setText(ctr("file_label", label=i18n.ltr(label)) if label else ctr("file_label_none"))
        self.file_label.setVisible(s is not None)
        if s is None:
            self.geo_value.setText(ctr("no_session"))
        else:
            g = s.geometry
            self.geo_value.setText(i18n.ltr(g.get("name") or g.get("id", "")) if g else ctr("geometry_none"))
        op = ctl.context_undo_op()
        self.btn_undo.setEnabled(op is not None)
        self.btn_undo.setToolTip(ctr("undo_tip", what=op.describe()) if op is not None else "")


__all__ = ["DetectorEditor", "DetectorManagerDialog", "GeometryDialog", "SessionContextBar",
           "fill_detector_combo", "profile_text", "CONTEXT_TARGETS"]

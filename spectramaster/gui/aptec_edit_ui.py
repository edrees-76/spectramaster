"""Aptec-style Edit and Display menus.

Edit: Select All, Select Region, Copy to ClipBrd (Ctrl+Ins), Clear Selection (Ctrl+Del), Sample
Description (F5), Quantity Description (F6), Spectrum Data, Certificate, Library, Decay
Correction Calculation, Load Header Information, Load File into MCArd (hardware: disabled),
Reset Header.

Display: Normal Spectrum, Intermediate / Stabilized Spectrum (digital stabilizer hardware:
disabled), Energy / Resolution / Efficiency Calibration shown in place of the spectrum, with
Space / Shift+Space indexing the calibration points, as in Aptec PCMCA/WIN.

Every change applies to the displayed spectrum (a copy); no file is overwritten until it is
saved."""
from __future__ import annotations

import copy
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import QDateTime, QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateTimeEdit, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..analysis import decay_calc as dc
from ..analysis.certificate import Certificate, CertificateLine, default_certificate_dir, safe_file_name
from .aptec_edit_strings import etr

ENERGY, RESOLUTION, EFFICIENCY = "energy", "resolution", "efficiency"
_EXTRA_SAMPLE = ("user_id", "geometry_id", "aptec_sample_id", "sample_start", "sample_stop")
_EXTRA_QTY = ("quantity", "quantity_units", "quantity_err_pct", "w_const", "w_const_units", "w_const_err_pct",
              "x_const", "x_const_units", "x_const_err_pct", "y_const", "y_const_units", "y_const_err_pct",
              "convert_factor_units", "activity_units", "activity_ref_date", "total_quantity",
              "total_quantity_err_pct")


def _ltr(text) -> str:
    return "⁦" + str(text) + "⁩"


def _rtl(w) -> None:
    from . import i18n
    w.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl(i18n.language()) else Qt.LeftToRight)


def _date_edit(value: Optional[datetime]) -> QDateTimeEdit:
    from PySide6.QtCore import QLocale
    e = QDateTimeEdit()
    e.setLocale(QLocale(QLocale.English))
    e.setLayoutDirection(Qt.LeftToRight)
    e.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
    e.setCalendarPopup(True)
    e.setDateTime(QDateTime(value) if value is not None else QDateTime.currentDateTime())
    return e


def _pydt(e: QDateTimeEdit) -> datetime:
    return e.dateTime().toPython().replace(tzinfo=None, microsecond=0)


def _parse_dt(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v)) if v else None
    except ValueError:
        return None


def _float(v, default=0.0) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _spin(lo=0.0, hi=1e12, dec=6) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setLayoutDirection(Qt.LeftToRight)
    return s


def _displayed(win):
    spectra = getattr(win, "_spectra", None)
    i = getattr(win, "_index", -1)
    if spectra is None or not 0 <= i < len(spectra):
        return None
    return spectra[i]


def _replace(win, spec) -> bool:
    from .aptec_calibration_ui import apply_to_display
    return apply_to_display(win, spec)


def _need(win):
    spec = _displayed(win)
    if spec is None:
        win.statusBar().showMessage(etr("need_spectrum"), 6000)
    return spec


# ===================================================================== sample / quantity / data
class SampleDescriptionDialog(QDialog):
    """Aptec *Sample Description* (F5).  Title and Spectrum Label are the spectrum's
    description and sample ID; the other values are kept with the spectrum."""

    def __init__(self, spec, parent=None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(etr("sample_title"))
        form = QFormLayout(self)
        hint = QLabel(etr("sample_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("infoLabel")
        form.addRow(hint)
        x = spec.extra
        self.title = QLineEdit(spec.description)
        self.title.setMaxLength(42)
        self.label = QLineEdit(spec.sample_id)
        self.label.setMaxLength(32)
        self.user = QLineEdit(str(x.get("user_id", "")))
        self.detector = QLineEdit(spec.detector)
        self.geometry = QLineEdit(str(x.get("geometry_id", "")))
        self.sample = QLineEdit(str(x.get("aptec_sample_id", "")))
        for w in (self.user, self.detector, self.geometry, self.sample):
            w.setMaxLength(16)
        form.addRow(etr("f_title"), self.title)
        form.addRow(etr("f_label"), self.label)
        form.addRow(etr("f_user"), self.user)
        form.addRow(etr("f_detector"), self.detector)
        form.addRow(etr("f_geometry"), self.geometry)
        form.addRow(etr("f_sample"), self.sample)
        self.times = {}
        for key, label in (("sample_start", "f_sample_start"), ("sample_stop", "f_sample_stop")):
            t = _parse_dt(x.get(key))
            box = QCheckBox(etr("f_set"))
            box.setChecked(t is not None)
            ed = _date_edit(t or spec.start_time)
            ed.setEnabled(t is not None)
            box.toggled.connect(ed.setEnabled)
            row = QHBoxLayout()
            row.addWidget(box)
            row.addWidget(ed, 1)
            form.addRow(etr(label), row)
            self.times[key] = (box, ed)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        clear = bb.addButton(etr("clear_all"), QDialogButtonBox.ResetRole)
        clear.clicked.connect(self.clear)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def clear(self) -> None:
        for w in (self.title, self.label, self.user, self.detector, self.geometry, self.sample):
            w.clear()
        for box, _ed in self.times.values():
            box.setChecked(False)

    def apply_to(self, spec):
        new = copy.deepcopy(spec)
        new.description = self.title.text().strip()
        new.sample_id = self.label.text().strip()
        new.detector = self.detector.text().strip()
        for key, w in (("user_id", self.user), ("geometry_id", self.geometry), ("aptec_sample_id", self.sample)):
            v = w.text().strip()
            if v:
                new.extra[key] = v
            else:
                new.extra.pop(key, None)
        for key, (box, ed) in self.times.items():
            if box.isChecked():
                new.extra[key] = _pydt(ed).isoformat(sep=" ")
            else:
                new.extra.pop(key, None)
        return new


class QuantityDescriptionDialog(QDialog):
    """Aptec *Quantity Description* (F6).  Quantify reads ``quantity`` and ``quantity_units``."""

    def __init__(self, spec, parent=None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(etr("qty_title"))
        lay = QVBoxLayout(self)
        hint = QLabel(etr("qty_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("infoLabel")
        lay.addWidget(hint)
        grid = QGridLayout()
        x = spec.extra
        self.fields = {}

        def row(r, label, key, with_units=True):
            v = _spin(0.0, 1e12)
            v.setValue(_float(x.get(key)))
            e = _spin(0.0, 100.0, 3)
            e.setValue(_float(x.get(key + "_err_pct")))
            grid.addWidget(QLabel(etr(label)), r, 0)
            grid.addWidget(v, r, 1)
            grid.addWidget(QLabel(etr("f_err")), r, 2)
            grid.addWidget(e, r, 3)
            u = None
            if with_units:
                u = QLineEdit(str(x.get(key + "_units", "")))
                u.setMaxLength(16)
                u.setPlaceholderText(etr("f_units"))
                grid.addWidget(u, r, 4)
            self.fields[key] = (v, e, u)
        row(0, "f_qty", "quantity", with_units=False)
        self.qty_units = QComboBox()
        self.qty_units.setEditable(True)
        self.qty_units.addItems(["kg", "g", "L", "mL", "m3", "filter"])
        self.qty_units.setCurrentText(str(x.get("quantity_units", "")))
        grid.addWidget(self.qty_units, 0, 4)
        row(1, "f_w", "w_const")
        row(2, "f_x", "x_const")
        row(3, "f_y", "y_const")
        row(4, "f_total", "total_quantity", with_units=False)
        lay.addLayout(grid)
        form = QFormLayout()
        self.convert_units = QLineEdit(str(x.get("convert_factor_units", "")))
        self.act_units = QComboBox()
        self.act_units.setEditable(True)
        self.act_units.addItems(list(dc.ACTIVITY_UNITS))
        self.act_units.setCurrentText(str(x.get("activity_units", "") or "Bq"))
        t = _parse_dt(x.get("activity_ref_date"))
        self.act_time_set = QCheckBox(etr("f_set"))
        self.act_time_set.setChecked(t is not None)
        self.act_time = _date_edit(t or spec.start_time)
        self.act_time.setEnabled(t is not None)
        self.act_time_set.toggled.connect(self.act_time.setEnabled)
        r = QHBoxLayout()
        r.addWidget(self.act_time_set)
        r.addWidget(self.act_time, 1)
        form.addRow(etr("f_convert_units"), self.convert_units)
        form.addRow(etr("f_act_units"), self.act_units)
        form.addRow(etr("f_act_time"), r)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        clear = bb.addButton(etr("clear_all"), QDialogButtonBox.ResetRole)
        clear.clicked.connect(self.clear)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def clear(self) -> None:
        for v, e, u in self.fields.values():
            v.setValue(0.0)
            e.setValue(0.0)
            if u is not None:
                u.clear()
        self.qty_units.setCurrentText("")
        self.convert_units.clear()
        self.act_time_set.setChecked(False)

    def apply_to(self, spec):
        new = copy.deepcopy(spec)
        for key in _EXTRA_QTY:
            new.extra.pop(key, None)
        for key, (v, e, u) in self.fields.items():
            if v.value() > 0:
                new.extra[key] = v.value()
                if e.value() > 0:
                    new.extra[key + "_err_pct"] = e.value()
            if u is not None and u.text().strip():
                new.extra[key + "_units"] = u.text().strip()
        if self.qty_units.currentText().strip():
            new.extra["quantity_units"] = self.qty_units.currentText().strip()
        if self.convert_units.text().strip():
            new.extra["convert_factor_units"] = self.convert_units.text().strip()
        if self.act_units.currentText().strip():
            new.extra["activity_units"] = self.act_units.currentText().strip()
        if self.act_time_set.isChecked():
            new.extra["activity_ref_date"] = _pydt(self.act_time).isoformat(sep=" ")
        return new


class SpectrumDataDialog(QDialog):
    """Aptec *Spectrum Data*: correct the acquisition data ("Be very careful")."""

    def __init__(self, spec, parent=None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(etr("spc_title"))
        self.spec = spec
        form = QFormLayout(self)
        warn = QLabel(etr("spc_warn"))
        warn.setWordWrap(True)
        warn.setStyleSheet("color: #b45309;")
        form.addRow(warn)
        self.start = _date_edit(spec.start_time)
        self.live = _spin(0.0, 1e10, 3)
        self.live.setValue(_float(spec.live_time))
        self.true = _spin(0.0, 1e10, 3)
        self.true.setValue(_float(spec.real_time))
        self.stop = QLabel()
        self.dead = QLabel()
        gross = QLabel(_ltr(f"{float(np.sum(spec.counts)):,.0f}"))
        form.addRow(etr("f_start"), self.start)
        form.addRow(etr("f_live"), self.live)
        form.addRow(etr("f_true"), self.true)
        form.addRow(etr("f_stop"), self.stop)
        form.addRow(etr("f_dead"), self.dead)
        form.addRow(etr("f_gross"), gross)
        for w in (self.live, self.true):
            w.valueChanged.connect(self._sync)
        self.start.dateTimeChanged.connect(self._sync)
        self.bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        form.addRow(self.bb)
        self._sync()

    def _sync(self, *_):
        from datetime import timedelta
        t = self.true.value()
        stop = _pydt(self.start) + timedelta(seconds=t)
        self.stop.setText(_ltr(stop.strftime("%Y-%m-%d %H:%M:%S")))
        ok = self.live.value() <= t or t == 0
        self.dead.setText(_ltr(f"{(1 - self.live.value() / t) * 100:.2f} %") if t > 0 and ok
                          else etr("live_gt_true"))
        self.bb.button(QDialogButtonBox.Ok).setEnabled(ok)

    def apply_to(self, spec):
        new = copy.deepcopy(spec)
        new.start_time = _pydt(self.start)
        new.live_time = self.live.value() or None
        new.real_time = self.true.value() or None
        if new.real_time and new.start_time:
            from datetime import timedelta
            new.extra["stop_time"] = (new.start_time + timedelta(seconds=new.real_time)).isoformat(sep=" ")
        return new


# ===================================================================== certificate / library / decay
def parse_half_life(text: str) -> Optional[float]:
    """'30.08 y' -> seconds (units s, m, h, d, y; seconds without a unit)."""
    t = (text or "").strip().lower().replace(",", ".")
    if not t:
        return None
    parts = t.split()
    try:
        if len(parts) == 2 and parts[1][:1] in dc.TIME_UNITS:
            return float(parts[0]) * dc.TIME_UNITS[parts[1][:1]]
        if len(parts) == 1 and parts[0][-1:] in dc.TIME_UNITS and parts[0][:-1]:
            return float(parts[0][:-1]) * dc.TIME_UNITS[parts[0][-1]]
        return float(parts[0])
    except ValueError:
        raise ValueError(t) from None


def format_half_life(s: Optional[float]) -> str:
    if not s:
        return ""
    for unit in ("y", "d", "h", "m"):
        if s >= dc.TIME_UNITS[unit]:
            return f"{s / dc.TIME_UNITS[unit]:.6g} {unit}"
    return f"{s:.6g} s"


class CertificateDialog(QDialog):
    """Aptec *Certificate* (Cal_Edit): calibration-source certificates."""
    COLS = 6

    def __init__(self, parent=None, folder=None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(etr("cert_title"))
        self.folder = Path(folder or default_certificate_dir())
        self.path: Optional[Path] = None
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        for key, fn in (("cert_new", self.new), ("cert_open", self.open_dialog), ("cert_save", self.save)):
            b = QPushButton(etr(key))
            b.clicked.connect(fn)
            top.addWidget(b)
        top.addStretch(1)
        lay.addLayout(top)
        form = QFormLayout()
        self.name = QLineEdit()
        self.source = QLineEdit()
        self.units = QComboBox()
        self.units.addItems(list(dc.ACTIVITY_UNITS))
        self.time = _date_edit(None)
        self.note = QLineEdit()
        form.addRow(etr("cert_name"), self.name)
        form.addRow(etr("cert_source"), self.source)
        form.addRow(etr("cert_units"), self.units)
        form.addRow(etr("cert_time"), self.time)
        form.addRow(etr("cert_note"), self.note)
        lay.addLayout(form)
        self.table = QTableWidget(0, self.COLS)
        self.table.setHorizontalHeaderLabels(etr("cert_cols").split("|"))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setMinimumSize(560, 220)
        self.table.setLayoutDirection(Qt.LeftToRight)   # isotopes, energies, half-lives read left to right
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        for key, fn in (("cert_add", lambda: self.add_line()), ("cert_del", self.delete_line),
                        ("cert_from_lib", self.lines_from_library)):
            b = QPushButton(etr(key))
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        hint = QLabel(etr("cert_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("infoLabel")
        lay.addWidget(hint)
        self.status = QLabel()
        lay.addWidget(self.status)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def new(self) -> None:
        self.path = None
        self.set_certificate(Certificate(name=""))

    def set_certificate(self, cert: Certificate) -> None:
        self.name.setText(cert.name)
        self.source.setText(cert.source_id)
        self.units.setCurrentText(cert.units)
        self.time.setDateTime(QDateTime(cert.reference_time) if cert.reference_time else QDateTime.currentDateTime())
        self.note.setText(cert.note)
        self.table.setRowCount(0)
        for ln in cert.lines:
            self.add_line(ln)

    def add_line(self, ln: Optional[CertificateLine] = None) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        vals = ["", "", "", "", "", ""] if ln is None else [
            ln.isotope, f"{ln.energy:g}", f"{ln.yield_ * 100:.6g}", format_half_life(ln.half_life_s),
            f"{ln.activity:.6g}", f"{ln.activity_err:.4g}"]
        for c, v in enumerate(vals):
            self.table.setItem(r, c, QTableWidgetItem(v))

    def delete_line(self) -> None:
        for r in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(r)

    def lines_from_library(self) -> None:
        """Energy, yield and half-life of the selected rows' isotopes from the nuclide library."""
        from ..analysis.library import load_library
        lib = load_library()
        rows = sorted({i.row() for i in self.table.selectedIndexes()}) or range(self.table.rowCount())
        for r in list(rows):
            iso = (self.table.item(r, 0).text() if self.table.item(r, 0) else "").strip()
            nd = lib.get(iso)
            if nd is None:
                continue
            for k, ln in enumerate([g for g in nd.gammas(1.0)]):
                cl = CertificateLine(iso, ln.energy, ln.intensity / 100.0, nd.half_life_s)
                if k == 0:
                    for c, v in enumerate([iso, f"{cl.energy:g}", f"{ln.intensity:.6g}",
                                           format_half_life(nd.half_life_s)]):
                        self.table.setItem(r, c, QTableWidgetItem(v))
                else:
                    act = self.table.item(r, 4).text() if self.table.item(r, 4) else ""
                    err = self.table.item(r, 5).text() if self.table.item(r, 5) else ""
                    self.add_line(cl)
                    self.table.setItem(self.table.rowCount() - 1, 4, QTableWidgetItem(act))
                    self.table.setItem(self.table.rowCount() - 1, 5, QTableWidgetItem(err))

    def certificate(self) -> Certificate:
        lines = []
        for r in range(self.table.rowCount()):
            cell = [(self.table.item(r, c).text().strip() if self.table.item(r, c) else "") for c in range(self.COLS)]
            if not any(cell):
                continue
            try:
                hl = parse_half_life(cell[3])
            except ValueError:
                raise ValueError(etr("cert_bad_hl", iso=cell[0])) from None
            lines.append(CertificateLine(cell[0], _float(cell[1]), _float(cell[2]) / 100.0, hl,
                                         _float(cell[4]), _float(cell[5])))
        return Certificate(name=self.name.text().strip(), units=self.units.currentText(),
                           reference_time=_pydt(self.time), source_id=self.source.text().strip(),
                           note=self.note.text().strip(), lines=lines).validate()

    def save(self) -> Optional[Path]:
        try:
            cert = self.certificate()
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return None
        self.path = cert.save(self.path or self.folder / f"{safe_file_name(cert.name)}.json")
        self.status.setText(etr("cert_saved", path=_ltr(self.path)))
        return self.path

    def open_path(self, path) -> None:
        self.path = Path(path)
        self.set_certificate(Certificate.load(path))

    def open_dialog(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        fn, _ = QFileDialog.getOpenFileName(self, etr("cert_title"), str(self.folder), "Certificate (*.json)")
        if fn:
            self.open_path(fn)


class LibraryDialog(QDialog):
    """Aptec *Library* (Iso_Edit): the nuclide library, read-only."""

    def __init__(self, parent=None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(etr("lib_title"))
        from ..analysis.library import load_library
        self.lib = load_library()
        lay = QVBoxLayout(self)
        hint = QLabel(etr("lib_hint", n=len(self.lib), src="IAEA ENSDF (ndlab / LiveChart), SandiaDecay"))
        hint.setWordWrap(True)
        hint.setObjectName("infoLabel")
        lay.addWidget(hint)
        row = QHBoxLayout()
        row.addWidget(QLabel(etr("lib_search")))
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        row.addWidget(self.search, 1)
        lay.addLayout(row)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(etr("lib_cols").split("|"))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMinimumSize(520, 360)
        self.table.setLayoutDirection(Qt.LeftToRight)
        lay.addWidget(self.table, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.refresh()

    def rows(self, text: str = "") -> list[tuple[str, str, float, float]]:
        t = text.strip().lower().replace(" ", "")
        out = []
        for name in sorted(self.lib):
            nd = self.lib[name]
            lines = nd.gammas(0.0)
            if t:
                try:
                    e = float(t)
                    lines = [ln for ln in lines if abs(ln.energy - e) <= 2.0]
                    if not lines:
                        continue
                except ValueError:
                    if t not in name.lower().replace(" ", ""):
                        continue
            for ln in lines:
                out.append((name, nd.half_life or format_half_life(nd.half_life_s), ln.energy, ln.intensity))
        return out

    def refresh(self, *_):
        rows = self.rows(self.search.text())
        self.table.setRowCount(len(rows))
        for r, (name, hl, e, i) in enumerate(rows):
            for c, v in enumerate((name, hl, f"{e:.3f}", f"{i:.4g}")):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignAbsolute | Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(r, c, it)


class DecayDialog(QDialog):
    """Aptec *Decay Correction Calculation* (DECAY.EXE)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(etr("decay_title"))
        lay = QVBoxLayout(self)
        # activity units
        g = QGroupBox(etr("g_act_conv"))
        f = QFormLayout(g)
        self.a_val = _spin(0.0, 1e18, 6)
        self.a_from, self.a_to = QComboBox(), QComboBox()
        for c in (self.a_from, self.a_to):
            c.addItems(list(dc.ACTIVITY_UNITS))
        self.a_to.setCurrentText("Bq")
        self.a_from.setCurrentText("uCi")
        self.a_out = QLabel()
        f.addRow(etr("d_value"), self.a_val)
        f.addRow(etr("d_from"), self.a_from)
        f.addRow(etr("d_to"), self.a_to)
        f.addRow(etr("d_result"), self.a_out)
        lay.addWidget(g)
        # half-life units
        g = QGroupBox(etr("g_hl_conv"))
        f = QFormLayout(g)
        self.h_val = _spin(0.0, 1e18, 6)
        self.h_from, self.h_to = QComboBox(), QComboBox()
        for c in (self.h_from, self.h_to):
            c.addItems(list(dc.TIME_UNITS))
        self.h_from.setCurrentText("y")
        self.h_to.setCurrentText("d")
        self.h_out = QLabel()
        f.addRow(etr("d_value"), self.h_val)
        f.addRow(etr("d_from"), self.h_from)
        f.addRow(etr("d_to"), self.h_to)
        f.addRow(etr("d_result"), self.h_out)
        lay.addWidget(g)
        # decay correction
        g = QGroupBox(etr("g_decay"))
        f = QFormLayout(g)
        self.nuclide = QComboBox()
        self.nuclide.setEditable(True)
        from ..analysis.library import load_library
        self.lib = load_library()
        self.nuclide.addItems([""] + sorted(n for n, d in self.lib.items() if d.half_life_s))
        self.nuclide.currentTextChanged.connect(self._nuclide)
        hl_row = QHBoxLayout()
        self.hl = _spin(0.0, 1e18, 6)
        self.hl_unit = QComboBox()
        self.hl_unit.addItems(list(dc.TIME_UNITS))
        self.hl_unit.setCurrentText("y")
        hl_row.addWidget(self.hl, 2)
        hl_row.addWidget(self.hl_unit, 1)
        act_row = QHBoxLayout()
        self.act = _spin(0.0, 1e18, 6)
        self.act_unit = QComboBox()
        self.act_unit.addItems(list(dc.ACTIVITY_UNITS))
        act_row.addWidget(self.act, 2)
        act_row.addWidget(self.act_unit, 1)
        self.err = _spin(0.0, 100.0, 3)
        self.t0 = _date_edit(None)
        self.t1 = _date_edit(None)
        self.d_out = QLabel()
        self.d_out.setWordWrap(True)
        f.addRow(etr("d_nuclide"), self.nuclide)
        f.addRow(etr("d_half_life"), hl_row)
        f.addRow(etr("d_activity"), act_row)
        f.addRow(etr("d_err"), self.err)
        f.addRow(etr("d_at"), self.t0)
        f.addRow(etr("d_to_time"), self.t1)
        f.addRow(etr("d_result"), self.d_out)
        lay.addWidget(g)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        for w in (self.a_val, self.h_val, self.hl, self.act, self.err):
            w.valueChanged.connect(self.recalc)
        for w in (self.a_from, self.a_to, self.h_from, self.h_to, self.hl_unit, self.act_unit):
            w.currentIndexChanged.connect(self.recalc)
        for w in (self.t0, self.t1):
            w.dateTimeChanged.connect(self.recalc)
        self.recalc()

    def _nuclide(self, name: str) -> None:
        nd = self.lib.get(name.strip())
        if nd is not None and nd.half_life_s:
            unit = "y" if nd.half_life_s >= dc.YEAR_S else ("d" if nd.half_life_s >= 86400 else "h")
            self.hl_unit.setCurrentText(unit)
            self.hl.setValue(dc.convert_time(nd.half_life_s, "s", unit))

    def recalc(self, *_):
        self.a_out.setText(_ltr(f"{dc.convert_activity(self.a_val.value(), self.a_from.currentText(), self.a_to.currentText()):.6g} {self.a_to.currentText()}"))
        self.h_out.setText(_ltr(f"{dc.convert_time(self.h_val.value(), self.h_from.currentText(), self.h_to.currentText()):.6g} {self.h_to.currentText()}"))
        hl = dc.convert_time(self.hl.value(), self.hl_unit.currentText(), "s")
        if hl <= 0:
            self.d_out.setText(etr("d_bad"))
            self.result = None
            return
        dt = (_pydt(self.t1) - _pydt(self.t0)).total_seconds()
        fac = dc.decay_factor(hl, dt)
        a = self.act.value() * fac
        self.result = a
        days = dt / 86400.0
        self.d_out.setText(etr("d_out", a=_ltr(f"{a:.6g}"), u=self.act_unit.currentText(),
                               e=_ltr(f"{self.err.value():.3g}"), f=_ltr(f"{fac:.6g}"),
                               t=_ltr(f"{days:.4g} d")))


# ===================================================================== load / reset header
class LoadHeaderDialog(QDialog):
    """Aptec *Load Header Information*: what to take from another spectrum file."""
    ITEMS = ("energy", "res", "eff", "sample", "qty", "rois", "spc")

    def __init__(self, file_name: str, available: dict, parent=None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(etr("lh_title"))
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(etr("lh_from", file=_ltr(file_name))))
        self.all = QCheckBox(etr("lh_all"))
        lay.addWidget(self.all)
        self.boxes = {}
        for key in self.ITEMS:
            b = QCheckBox(etr("lh_" + key))
            b.setEnabled(bool(available.get(key)))
            b.setChecked(bool(available.get(key)))
            self.boxes[key] = b
            lay.addWidget(b)
        self.all.setChecked(all(b.isChecked() for b in self.boxes.values() if b.isEnabled()))
        self.all.toggled.connect(lambda on: [b.setChecked(on) for b in self.boxes.values() if b.isEnabled()])
        hw = QLabel(etr("lh_hw"))
        hw.setWordWrap(True)
        hw.setObjectName("infoLabel")
        lay.addWidget(hw)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def selected(self) -> set:
        return {k for k, b in self.boxes.items() if b.isEnabled() and b.isChecked()}


def read_header_source(path) -> dict:
    """What another spectrum file offers: {"spectrum", "aptec" (calibrations), "rois"}."""
    from ..convert import read_spectra
    from ..analysis import aptec_calibration as ac
    from ..analysis.aptec_roi import read_aptec_rois
    path = Path(path)
    spec = read_spectra(path)[0][0]
    out = {"spectrum": spec, "aptec": None, "rois": []}
    if path.suffix.lower() == ".s0":
        try:
            out["aptec"] = ac.read_aptec_calibrations(path)
        except Exception:
            out["aptec"] = None
        try:
            out["rois"] = read_aptec_rois(path)
        except (ValueError, OSError):
            out["rois"] = []
    return out


def available_items(src: dict) -> dict:
    s = src["spectrum"]
    apt = src.get("aptec") or {}
    x = s.extra
    return {"energy": bool(s.energy_coeffs), "res": bool(s.fwhm_coeffs), "eff": bool(apt.get("efficiency")),
            "sample": bool(s.description or s.sample_id or s.detector or any(k in x for k in _EXTRA_SAMPLE)),
            "qty": any(k in x for k in _EXTRA_QTY), "rois": bool(src.get("rois")),
            "spc": bool(s.start_time or s.live_time or s.real_time)}


def merge_header(target, src: dict, what: set):
    """A copy of ``target`` with the chosen header parts of ``src`` (see read_header_source)."""
    s = src["spectrum"]
    new = copy.deepcopy(target)
    if "energy" in what:
        new.energy_coeffs = list(s.energy_coeffs)
        for k in ("energy_cal_points", "energy_units", "energy_cal_date", "energy_coeffs_raw"):
            if k in s.extra:
                new.extra[k] = s.extra[k]
    if "res" in what:
        new.fwhm_coeffs = list(s.fwhm_coeffs)
        for k in ("fwhm_cal_points", "fwhm_units", "fwhm_cal_date", "fwhm_coeffs_raw"):
            if k in s.extra:
                new.extra[k] = s.extra[k]
    if "sample" in what:
        new.description, new.sample_id, new.detector = s.description, s.sample_id, s.detector
        for k in _EXTRA_SAMPLE:
            new.extra.pop(k, None)
            if k in s.extra:
                new.extra[k] = s.extra[k]
    if "qty" in what:
        for k in _EXTRA_QTY:
            new.extra.pop(k, None)
            if k in s.extra:
                new.extra[k] = s.extra[k]
    if "spc" in what:
        new.start_time, new.live_time, new.real_time = s.start_time, s.live_time, s.real_time
        if "stop_time" in s.extra:
            new.extra["stop_time"] = s.extra["stop_time"]
    return new


def reset_header(spec):
    """Aptec *Reset Header*: no calibrations and no descriptions (counts and times kept)."""
    new = copy.deepcopy(spec)
    new.energy_coeffs, new.fwhm_coeffs = [], []
    new.description = new.sample_id = new.detector = ""
    for k in (_EXTRA_SAMPLE + _EXTRA_QTY + ("energy_cal_points", "fwhm_cal_points", "energy_units", "fwhm_units",
                                           "energy_cal_date", "fwhm_cal_date", "energy_coeffs_raw",
                                           "fwhm_coeffs_raw", "efficiency_points", "efficiency_calibration")):
        new.extra.pop(k, None)
    return new


# ===================================================================== calibration display
def calibration_data(spec, kind: str) -> Optional[dict]:
    """Points and curve of a calibration of ``spec``: {"points": [(x, y)], "curve": f, "log": bool,
    "x", "y" axis keys}.  Aptec files give their own stored points; otherwise the points kept with
    the spectrum (if any) and its equation."""
    if spec is None:
        return None
    from ..analysis import aptec_calibration as ac
    apt = None
    p = Path(spec.source_path) if spec.source_path else None
    if p is not None and p.suffix.lower() == ".s0" and p.is_file():
        try:
            apt = ac.read_aptec_calibrations(p)
        except Exception:
            apt = None

    def parse(key):
        pts = []
        for item in str(spec.extra.get(key, "")).split(";"):
            if ":" in item:
                a, b = item.split(":", 1)
                try:
                    pts.append((float(a), float(b)))
                except ValueError:
                    pass
        return pts
    if kind == ENERGY:
        cal = apt.get("energy") if apt else None
        if cal is not None and cal.coeffs:
            return {"points": list(zip(cal.channels, cal.values)), "curve": cal.evaluate, "log": False,
                    "x": "cd_ch", "y": "cd_kev", "units": cal.units or "keV"}
        if not spec.energy_coeffs:
            return None
        return {"points": parse("energy_cal_points"), "log": False, "x": "cd_ch", "y": "cd_kev", "units": "keV",
                "curve": lambda ch: np.polynomial.polynomial.polyval(np.asarray(ch, float), spec.energy_coeffs)}
    if kind == RESOLUTION:
        cal = apt.get("resolution") if apt else None
        if cal is not None and cal.coeffs:
            return {"points": list(zip(cal.channels, cal.values)), "curve": cal.evaluate, "log": False,
                    "x": "cd_ch", "y": "cd_fwhm", "units": cal.units or "channels"}
        if not spec.fwhm_coeffs:
            return None
        return {"points": [], "log": False, "x": "cd_ch", "y": "cd_fwhm", "units": "keV",
                "curve": lambda ch: np.polynomial.polynomial.polyval(np.asarray(ch, float), spec.fwhm_coeffs)}
    cal = apt.get("efficiency") if apt else None
    if cal is None:
        return None
    pts = [(pt.energy, pt.efficiency) for pt in cal.points if pt.efficiency and pt.efficiency > 0]
    return {"points": pts, "curve": cal.efficiency, "log": True, "x": "cd_kev", "y": "cd_eff_axis", "units": ""}


class CalibrationDisplay(QWidget):
    """Aptec Display > Energy / Resolution / Efficiency Calibration, in place of the spectrum."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.LeftToRight)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(300, 200)
        self.kind = ENERGY
        self.data: Optional[dict] = None
        self.index = -1

    def set_data(self, kind: str, data: Optional[dict]) -> None:
        self.kind, self.data = kind, data
        self.index = 0 if data and data["points"] else -1
        self.update()

    def step(self, d: int) -> None:
        if not self.data or not self.data["points"]:
            return
        n = len(self.data["points"])
        self.index = (self.index + d) % n if self.index >= 0 else (0 if d > 0 else n - 1)
        self.update()

    def point_text(self) -> str:
        if not self.data or not 0 <= self.index < len(self.data["points"]):
            return ""
        x, y = self.data["points"][self.index]
        try:
            c = float(np.asarray(self.data["curve"](np.array([x], float)))[0])
        except Exception:
            c = float("nan")
        if self.kind == EFFICIENCY:
            dev = f"{(y - c) / c * 100:+.2f} %" if c else "-"
            xs, ys, cs = f"{x:.2f} keV", f"{y:.5g}", f"{c:.5g}"
        else:
            dev = f"{y - c:+.4g}"
            xs, ys, cs = f"ch {x:.2f}", f"{y:.4f} {self.data.get('units', '')}", f"{c:.4f}"
        return etr("cd_point", n=self.index + 1, total=len(self.data["points"]), x=_ltr(xs), y=_ltr(ys),
                   c=_ltr(cs), d=_ltr(dev))

    def paintEvent(self, _ev):
        from . import plot as plotmod
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), self.palette().window())
        r = QRectF(self.rect()).adjusted(74, 34, -18, -46)
        p.fillRect(r, plotmod.C_BG)
        p.setPen(QPen(plotmod.C_FRAME, 1))
        p.drawRect(r)
        title = etr({ENERGY: "cd_energy", RESOLUTION: "cd_res", EFFICIENCY: "cd_eff"}[self.kind])
        p.setPen(plotmod.C_AXIS_TEXT)
        p.drawText(QRectF(r.left(), 6, r.width(), 22), Qt.AlignCenter, title)
        d = self.data
        if not d:
            p.drawText(r, Qt.AlignCenter, etr("cd_none", what=title))
            return
        pts = d["points"]
        log = d["log"]
        xs = [x for x, _ in pts] or [0.0]
        if log:
            xs = [x for x in xs if x > 0] or [50.0, 2000.0]
        lo, hi = (min(xs), max(xs)) if len(set(xs)) > 1 else (min(xs) * 0.5 or 0.0, max(xs) * 1.5 or 1.0)
        if not pts and self.kind != EFFICIENCY:
            lo, hi = 0.0, 8192.0
        x0, x1 = (lo / 1.2, hi * 1.2) if log else (lo - 0.05 * (hi - lo), hi + 0.05 * (hi - lo))
        grid = np.geomspace(x0, x1, 300) if log else np.linspace(x0, x1, 300)
        try:
            cy = np.asarray(d["curve"](grid), dtype=float)
        except Exception:
            cy = np.full_like(grid, np.nan)
        vals = np.concatenate([np.array([y for _, y in pts], float), cy[np.isfinite(cy)]])
        vals = vals[vals > 0] if log else vals
        if not len(vals):
            return
        y0, y1 = float(vals.min()), float(vals.max())
        if log:
            y0, y1 = y0 / 1.3, y1 * 1.3
        else:
            span = (y1 - y0) or abs(y1) or 1.0
            y0, y1 = y0 - 0.08 * span, y1 + 0.08 * span
        tx = (lambda v: math.log(v)) if log else (lambda v: v)

        def X(v):
            return r.left() + (tx(v) - tx(x0)) / (tx(x1) - tx(x0)) * r.width()

        def Y(v):
            return r.bottom() - (tx(v) - tx(y0)) / (tx(y1) - tx(y0)) * r.height()
        p.setPen(QPen(plotmod.C_LINE, 1.6))
        last = None
        for gx, gy in zip(grid, cy):
            if not math.isfinite(gy) or (log and gy <= 0):
                last = None
                continue
            pt = QPointF(X(gx), Y(gy))
            if last is not None:
                p.drawLine(last, pt)
            last = pt
        for k, (x, y) in enumerate(pts):
            if log and (x <= 0 or y <= 0):
                continue
            on = k == self.index
            p.setPen(QPen(plotmod.C_MARKER if on else plotmod.C_ROI, 2 if on else 1.4))
            p.setBrush(plotmod.C_ROI if not on else Qt.NoBrush)
            p.drawEllipse(QPointF(X(x), Y(y)), 6 if on else 3.5, 6 if on else 3.5)
        p.setBrush(Qt.NoBrush)
        p.setPen(plotmod.C_AXIS_TEXT)
        p.setLayoutDirection(Qt.LeftToRight)           # the axes grow to the right in Arabic too
        for v, align in ((x0, Qt.AlignLeft), (x1, Qt.AlignRight)):
            p.drawText(QRectF(r.left(), r.bottom() + 4, r.width(), 18), Qt.AlignAbsolute | align, f"{v:.5g}")
        p.drawText(QRectF(r.left(), r.bottom() + 4, r.width(), 18), Qt.AlignCenter, etr(d["x"]))
        p.drawText(QRectF(2, r.top(), 68, 16), Qt.AlignAbsolute | Qt.AlignRight, f"{y1:.4g}")
        p.drawText(QRectF(2, r.bottom() - 16, 68, 16), Qt.AlignAbsolute | Qt.AlignRight, f"{y0:.4g}")
        p.save()
        p.translate(12, r.center().y())
        p.rotate(-90)
        p.drawText(QRectF(-r.height() / 2, -8, r.height(), 18), Qt.AlignCenter, etr(d["y"]))
        p.restore()
        from . import i18n
        rtl = i18n.is_rtl(i18n.language())
        p.setLayoutDirection(Qt.RightToLeft if rtl else Qt.LeftToRight)
        p.drawText(QRectF(r.left(), r.bottom() + 22, r.width(), 18),
                   Qt.AlignAbsolute | (Qt.AlignRight if rtl else Qt.AlignLeft),
                   self.point_text() or etr("cd_hint"))

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Space:
            self.step(-1 if ev.modifiers() & Qt.ShiftModifier else 1)
        else:
            super().keyPressEvent(ev)


def set_display(win, kind: Optional[str]) -> None:
    """None: the spectrum (Normal Spectrum); otherwise a calibration display."""
    win.display_kind = kind
    for k, a in win._display_actions.items():
        a.setChecked(k == (kind or "normal"))
    calview = win.cal_display
    if kind is None:
        calview.hide()
        win.plot.show()
        if getattr(win, "split_mode", None):
            win.split_plot.show()
        return
    calview.set_data(kind, calibration_data(_displayed(win), kind))
    win.plot.hide()
    win.split_plot.hide()
    calview.show()
    calview.setFocus()


def _refresh_display(win) -> None:
    kind = getattr(win, "display_kind", None)
    if kind is not None:
        win.cal_display.set_data(kind, calibration_data(_displayed(win), kind))


# ===================================================================== actions
def sample_description(win) -> bool:
    spec = _need(win)
    if spec is None:
        return False
    dlg = SampleDescriptionDialog(spec, win)
    if dlg.exec() != QDialog.Accepted:
        return False
    return _replace(win, dlg.apply_to(spec))


def quantity_description(win) -> bool:
    spec = _need(win)
    if spec is None:
        return False
    dlg = QuantityDescriptionDialog(spec, win)
    if dlg.exec() != QDialog.Accepted:
        return False
    return _replace(win, dlg.apply_to(spec))


def spectrum_data(win) -> bool:
    spec = _need(win)
    if spec is None:
        return False
    dlg = SpectrumDataDialog(spec, win)
    if dlg.exec() != QDialog.Accepted:
        return False
    return _replace(win, dlg.apply_to(spec))


def copy_selection(win) -> bool:
    img = win.plot.selection_image()
    if img is None:
        win.statusBar().showMessage(etr("sel_none"), 6000)
        return False
    QGuiApplication.clipboard().setImage(img)
    win.statusBar().showMessage(etr("copied"), 6000)
    return True


def select_region(win) -> None:
    win.plot.clear_selection()
    win.plot.start_select_region()
    win.plot.setFocus()
    win.statusBar().showMessage(etr("select_hint"), 8000)


def load_header(win, path: Optional[str] = None, what: Optional[set] = None) -> Optional[set]:
    spec = _need(win)
    if spec is None:
        return None
    if path is None:
        folder = win.settings.folder("open") if hasattr(win.settings, "folder") else ""
        path, _ = QFileDialog.getOpenFileName(win, etr("lh_title"), folder)
        if not path:
            return None
    try:
        src = read_header_source(path)
    except Exception as exc:
        QMessageBox.warning(win, etr("lh_title"), etr("lh_unreadable", file=Path(path).name, msg=exc))
        return None
    avail = available_items(src)
    if len(src["spectrum"].counts) != len(spec.counts):
        for k in ("energy", "res", "rois"):
            avail[k] = False
        win.statusBar().showMessage(etr("lh_channels", a=len(src["spectrum"].counts), b=len(spec.counts)), 10000)
    if what is None:
        dlg = LoadHeaderDialog(Path(path).name, avail, win)
        if dlg.exec() != QDialog.Accepted:
            return None
        what = dlg.selected()
    what = {k for k in what if avail.get(k)}
    rois = src["rois"] if "rois" in what else []
    if what - {"eff", "rois"}:
        _replace(win, merge_header(spec, src, what))
    if "eff" in what and src.get("aptec") and src["aptec"].get("efficiency") is not None:
        from ..analysis import aptec_calibration as ac
        from ..analysis import efficiency as eff
        e = src["aptec"]["efficiency"]
        name = f"{e.detector_id or 'detector'}_{e.geometry_id or 'geometry'}_aptec{e.eff_type}"
        curve = ac.to_efficiency_curve(e, name=name, source=str(path))
        curve.save(Path(eff.default_curve_dir()) / f"{safe_file_name(name)}.json")
    if rois:
        win.plot.clear_rois()
        for _bl, rl, rh, _bh in rois:
            win.plot._insert_roi(rl, rh)
    names = ", ".join(etr("lh_" + k).split(" (")[0] for k in LoadHeaderDialog.ITEMS if k in what)
    win.statusBar().showMessage(etr("lh_done", file=Path(path).name, what=names), 12000)
    _refresh_display(win)
    return what


def reset_header_action(win, confirm: bool = True) -> bool:
    spec = _need(win)
    if spec is None:
        return False
    if confirm and QMessageBox.question(win, etr("rh_title"), etr("rh_q"), QMessageBox.Ok | QMessageBox.Cancel,
                                        QMessageBox.Cancel) != QMessageBox.Ok:
        return False
    win.plot.clear_rois()
    _replace(win, reset_header(spec))
    win.statusBar().showMessage(etr("rh_done"), 8000)
    _refresh_display(win)
    return True


def _act(win, attr, key, fn, shortcut=None, enabled=True, tip=None):
    a = QAction(win)
    a.setObjectName(attr)
    a._aedit_key = key
    a._aedit_tip = tip or ("tip_" + key)
    if shortcut:
        a.setShortcut(QKeySequence(shortcut))
    a.triggered.connect(lambda _=False, f=fn: f())
    a.setEnabled(enabled)
    win.addAction(a)
    setattr(win, attr, a)
    win._edit_actions.append(a)
    return a


def install_edit_display_menus(win) -> None:
    """Edit and Display menus after File (Aptec: File, Edit, Display, Setup, ..., ROI, Analyze, View)."""
    win._edit_actions = []
    plot = win.plot
    # Aptec: F5 / F6 are Sample / Quantity Description; peak search is P (Analyze)
    if hasattr(win, "act_analyze"):
        win.act_analyze.setShortcuts([QKeySequence("P")])
    _act(win, "act_e_select_all", "select_all", plot.select_all)
    _act(win, "act_e_select_region", "select_region", lambda: select_region(win))
    _act(win, "act_e_copy", "copy", lambda: copy_selection(win), "Ctrl+Ins")
    _act(win, "act_e_clear_sel", "clear_sel", plot.clear_selection, "Ctrl+Del")
    _act(win, "act_e_sample", "sample", lambda: sample_description(win), "F5")
    _act(win, "act_e_quantity", "quantity", lambda: quantity_description(win), "F6")
    _act(win, "act_e_spc_data", "spc_data", lambda: spectrum_data(win))
    _act(win, "act_e_certificate", "certificate", lambda: CertificateDialog(win).exec())
    _act(win, "act_e_library", "library", lambda: LibraryDialog(win).exec())
    _act(win, "act_e_decay", "decay", lambda: DecayDialog(win).exec())
    _act(win, "act_e_load_header", "load_header", lambda: load_header(win))
    _act(win, "act_e_load_mcard", "load_mcard", lambda: None, enabled=False)
    _act(win, "act_e_reset_header", "reset_header", lambda: reset_header_action(win))
    plot.selectionChanged.connect(lambda: _sync_selection(win))
    _sync_selection(win)

    # Display: the calibration view sits next to the spectrum in the plot splitter
    win.cal_display = CalibrationDisplay()
    win.plot_splitter.addWidget(win.cal_display)
    win.cal_display.hide()
    win.display_kind = None
    grp = QActionGroup(win)
    win._display_actions = {}
    for key, kind, attr in (("normal", None, "act_d_normal"), ("disp_energy", ENERGY, "act_d_energy"),
                            ("disp_res", RESOLUTION, "act_d_res"), ("disp_eff", EFFICIENCY, "act_d_eff")):
        a = _act(win, attr, key, lambda k=kind: set_display(win, k))
        a.setCheckable(True)
        grp.addAction(a)
        win._display_actions[kind or "normal"] = a
    win.act_d_normal.setChecked(True)
    _act(win, "act_d_intermediate", "intermediate", lambda: None, enabled=False, tip="tip_hw")
    _act(win, "act_d_stabilized", "stabilized", lambda: None, enabled=False, tip="tip_hw")
    plot.roisChanged.connect(lambda: _refresh_display(win))

    # Space / Shift+Space index the calibration points while a calibration is displayed
    for name, d in (("act_roi_next", 1), ("act_roi_prev", -1)):
        a = getattr(win, name, None)
        if a is None:
            continue
        a.triggered.disconnect()
        a.triggered.connect(lambda _=False, dd=d: _index(win, dd))

    mb = win.menuBar()
    acts = mb.actions()
    after = win.menu_file.menuAction()
    before = acts[acts.index(after) + 1] if after in acts and acts.index(after) + 1 < len(acts) else None
    win.menu_edit = QMenuFactory.make(win, before)
    m = win.menu_edit
    for name in ("act_e_select_all", "act_e_select_region", "act_e_copy", "act_e_clear_sel", None,
                 "act_e_sample", "act_e_quantity", "act_e_spc_data", None, "act_e_certificate", "act_e_library",
                 "act_e_decay", None, "act_e_load_header", "act_e_load_mcard", "act_e_reset_header"):
        m.addSeparator() if name is None else m.addAction(getattr(win, name))
    win.menu_display = QMenuFactory.make(win, before)
    m = win.menu_display
    for name in ("act_d_normal", "act_d_intermediate", "act_d_stabilized", None, "act_d_energy", "act_d_res",
                 "act_d_eff"):
        m.addSeparator() if name is None else m.addAction(getattr(win, name))
    retranslate_edit_display_menus(win)


class QMenuFactory:
    @staticmethod
    def make(win, before):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(win)
        if before is not None:
            win.menuBar().insertMenu(before, menu)
        else:
            win.menuBar().addMenu(menu)
        return menu


def _index(win, d: int) -> None:
    if getattr(win, "display_kind", None) is not None:
        win.cal_display.step(d)
    elif d > 0:
        win.plot.index_next()
    else:
        win.plot.index_prev()


def _sync_selection(win) -> None:
    has = win.plot.selection is not None
    win.act_e_copy.setEnabled(has)
    win.act_e_clear_sel.setEnabled(has)


def retranslate_edit_display_menus(win) -> None:
    if not hasattr(win, "menu_edit"):
        return
    win.menu_edit.setTitle(etr("menu_edit"))
    win.menu_display.setTitle(etr("menu_display"))
    for a in win._edit_actions:
        a.setText(etr("act_" + a._aedit_key))
        a.setToolTip(etr(a._aedit_tip))
        a.setStatusTip(etr(a._aedit_tip))
    win.cal_display.update()


__all__ = ["install_edit_display_menus", "retranslate_edit_display_menus", "SampleDescriptionDialog",
           "QuantityDescriptionDialog", "SpectrumDataDialog", "CertificateDialog", "LibraryDialog", "DecayDialog",
           "LoadHeaderDialog", "CalibrationDisplay", "calibration_data", "merge_header", "reset_header",
           "read_header_source", "available_items", "load_header", "reset_header_action", "set_display",
           "parse_half_life", "format_half_life", "copy_selection", "ENERGY", "RESOLUTION", "EFFICIENCY"]

"""Efficiency-calibration wizard (plan section 10).

certificate (activity, uncertainty, reference date) -> calibration spectrum, detector and
geometry -> measured points (with the engine's interference / summing notes) -> model and
residuals -> exclusions with recorded reasons -> independent validation with a second source
-> saved curve + calibration record (with its validation status).

All science is in :mod:`spectramaster.analysis.efficiency` (measure_efficiency,
fit_efficiency, validate_curve) and :mod:`spectramaster.lab` (MeasurementGeometry,
CalibrationRecord); this module only collects the inputs and shows the results.  Measuring
and fitting run on a worker thread when started from the buttons; the public methods
(``measure_and_fit``, ``refit``, ``measure_validation`` ...) run synchronously unless called
with ``threaded=True``.

Files
-----
``save_curve(path)`` writes the curve JSON (format ``spectramaster-efficiency-1``, unchanged)
and next to it ``<stem>.calibration.json``: a :class:`CalibrationRecord` (content hash,
geometry id, source, validation status and note).  When a curve is loaded, the record next to
it is authoritative for the validation status; a curve claiming "validated" without a
matching record is treated as unvalidated.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                               QFileDialog, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QMessageBox, QPushButton, QSpinBox, QSplitter,
                               QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from ..analysis import efficiency as eff
from . import i18n
from .geometry_editor import GeometryEditor
from .i18n import ltr
from .quant_strings import qtr
from .worker import start_call

CERT_COLS = ["eff_col_nuclide", "eff_col_activity", "eff_col_unc", "eff_col_ref", "eff_col_half", "eff_col_lines"]
PT_COLS = ["pt_col_use", "pt_col_nuclide", "pt_col_energy", "pt_col_net", "pt_col_eff", "pt_col_unc",
           "pt_col_fit", "pt_col_resid", "pt_col_note"]
VAL_COLS = ["val_col_nuclide", "val_col_energy", "val_col_point", "val_col_curve", "val_col_dev", "val_col_z",
            "val_col_range"]
EXCLUDED_PREFIX = "excluded by user: "          # English record kept in EfficiencyPoint.note
RECORD_SUFFIX = ".calibration.json"
SUMMING_COLOR = QColor(255, 236, 179)            # amber: cascade emitter (summing not corrected)
WARN_COLOR = QColor(198, 40, 40)
OK_COLOR = QColor(46, 125, 50)


def _num(text: str, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(str(text).replace(",", ".").strip())
    except (TypeError, ValueError):
        return default


def _lines_text(lines) -> str:
    return "; ".join(f"{e:g}:{100 * i:.5g}" for e, i in lines) if lines else ""


def _parse_lines(text: str):
    out = []
    for part in (text or "").replace(",", ";").split(";"):
        if ":" in part:
            e, i = part.split(":", 1)
            ev, iv = _num(e), _num(i)
            if ev and iv:
                out.append((ev, iv / 100.0))
    return out or None


def note_with_exclusion(note: str, reason: str) -> str:
    """`note` with the user's exclusion reason recorded first (replacing an older one)."""
    reason = " ".join(reason.replace(";", ",").split())
    rest = note_without_exclusion(note)
    return EXCLUDED_PREFIX + reason + (("; " + rest) if rest else "")


def note_without_exclusion(note: str) -> str:
    return "; ".join(p for p in (note or "").split("; ") if p and not p.startswith(EXCLUDED_PREFIX))


def is_user_excluded(p) -> bool:
    return any(part.startswith(EXCLUDED_PREFIX) for part in (p.note or "").split("; "))


def record_path_for(curve_path) -> Path:
    p = Path(curve_path)
    return p.with_name(p.stem + RECORD_SUFFIX)


def is_record_file(path) -> bool:
    return str(path).lower().endswith(RECORD_SUFFIX)


def status_text(status: str) -> str:
    return qtr("eff_status_" + (status if status in ("validated", "rejected") else "unvalidated"))


def load_curve_file(path):
    """(curve, record or None, issues) of a curve JSON or a calibration-record JSON.

    The record (given directly or found next to the curve as ``<stem>.calibration.json``) is
    authoritative for the validation status; a record whose content hash or parameters no
    longer match makes the curve unvalidated, and so does a "validated" curve without a record.
    `issues` are English notes for the results."""
    from ..lab.calibration import CalibrationRecord
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    issues: list[str] = []
    rec = None
    if d.get("kind") == "efficiency" and isinstance(d.get("payload"), dict):
        rec = CalibrationRecord.from_dict(d)
        curve = rec.to_efficiency_curve()
    else:
        curve = eff.EfficiencyCurve.from_dict(d)
        rp = record_path_for(path)
        if rp.is_file():
            try:
                r = CalibrationRecord.from_dict(json.loads(rp.read_text(encoding="utf-8")))
            except Exception as exc:
                issues.append(f"calibration record {rp.name} unreadable ({exc}): treated as unvalidated")
                r = None
            if r is not None:
                same = (len(r.params) == len(curve.params)
                        and all(math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12) for a, b in zip(r.params, curve.params)))
                if same:
                    rec = r
                    curve.validation_status = r.validation_status
                else:
                    issues.append(f"calibration record {rp.name} does not match the curve: treated as unvalidated")
                    curve.validation_status = "unvalidated"
        if rec is None and curve.validation_status == "validated":
            issues.append("curve marked validated without a calibration record: treated as unvalidated")
            curve.validation_status = "unvalidated"
    if rec is not None and not rec.integrity_ok():
        issues.append("calibration record changed after it was saved (content hash): treated as unvalidated")
        curve.validation_status = "unvalidated"
    return curve, rec, issues


# ===================================================================== plot
class EfficiencyPlot(QWidget):
    """log-log plot of the measured points (with error bars) and the fitted curve + residuals."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 260)
        self.setLayoutDirection(Qt.LeftToRight)
        self.points: list = []
        self.curve: Optional[eff.EfficiencyCurve] = None
        self.extra: list = []                  # independent validation points (drawn as squares)

    def set_data(self, points, curve, extra=None) -> None:
        self.points, self.curve = list(points), curve
        if extra is not None:
            self.extra = list(extra)
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        p.fillRect(self.rect(), pal.base())
        fg = pal.text().color()
        pts = [q for q in self.points if q.efficiency > 0 and q.energy > 0]
        xtra = [q for q in self.extra if q.efficiency > 0 and q.energy > 0]
        if not pts:
            p.setPen(fg)
            p.drawText(self.rect(), Qt.AlignCenter, qtr("eff_plot_title"))
            return
        es = [q.energy for q in pts + xtra]
        ys = [q.efficiency for q in pts + xtra]
        x0, x1 = math.log10(min(es) * 0.8), math.log10(max(es) * 1.25)
        y0, y1 = math.log10(min(ys) * 0.7), math.log10(max(ys) * 1.4)
        w, h = self.width(), self.height()
        L, R, T = 58, 12, 18
        main = QRectF(L, T, w - L - R, (h - T - 34) * 0.7)
        res = QRectF(L, main.bottom() + 10, w - L - R, (h - T - 34) * 0.3 - 10)

        def X(e):
            return main.left() + (math.log10(e) - x0) / (x1 - x0) * main.width()

        def Y(v):
            return main.bottom() - (math.log10(v) - y0) / (y1 - y0) * main.height()

        p.setPen(QPen(fg, 1))
        p.drawRect(main)
        p.drawRect(res)
        p.setPen(QPen(QColor(150, 150, 150), 1, Qt.DotLine))
        for dec in range(int(math.floor(x0)), int(math.ceil(x1)) + 1):
            for m in (1, 2, 5):
                e = m * 10 ** dec
                if x0 <= math.log10(e) <= x1:
                    xx = X(e)
                    p.drawLine(QPointF(xx, main.top()), QPointF(xx, res.bottom()))
                    p.setPen(fg)
                    p.drawText(QRectF(xx - 30, res.bottom() + 2, 60, 14), Qt.AlignCenter, f"{e:g}")
                    p.setPen(QPen(QColor(150, 150, 150), 1, Qt.DotLine))
        for dec in range(int(math.floor(y0)), int(math.ceil(y1)) + 1):
            for m in (1, 2, 5):
                v = m * 10 ** dec
                if y0 <= math.log10(v) <= y1:
                    yy = Y(v)
                    p.drawLine(QPointF(main.left(), yy), QPointF(main.right(), yy))
                    p.setPen(fg)
                    p.drawText(QRectF(0, yy - 7, L - 4, 14), Qt.AlignRight | Qt.AlignVCenter, f"{v:.2g}")
                    p.setPen(QPen(QColor(150, 150, 150), 1, Qt.DotLine))
        p.setPen(fg)
        title = qtr("eff_plot_title") + "  [keV]"
        if self.curve is not None:
            title += "   " + status_text(self.curve.validation_status)
        p.drawText(QRectF(L, 0, main.width(), T), Qt.AlignLeft | Qt.AlignVCenter, title)
        # curve
        if self.curve is not None and self.curve.params:
            p.setPen(QPen(QColor(30, 110, 200), 2))
            n = 200
            prev = None
            for k in range(n + 1):
                e = 10 ** (x0 + (x1 - x0) * k / n)
                v = float(self.curve.efficiency(e))
                if v <= 0 or not math.isfinite(v):
                    prev = None
                    continue
                yy = min(max(Y(v), main.top()), main.bottom())
                pt = QPointF(X(e), yy)
                if prev is not None:
                    p.drawLine(prev, pt)
                prev = pt
        # points
        for q in pts:
            col = QColor(200, 60, 40) if q.use else QColor(150, 150, 150)
            p.setPen(QPen(col, 1.5))
            p.setBrush(col)
            xx, yy = X(q.energy), Y(q.efficiency)
            if q.unc > 0 and q.efficiency - q.unc > 0:
                p.drawLine(QPointF(xx, Y(q.efficiency + q.unc)), QPointF(xx, Y(q.efficiency - q.unc)))
            p.drawEllipse(QPointF(xx, yy), 3.5, 3.5)
        vcol = QColor(40, 150, 60)
        for q in xtra:
            p.setPen(QPen(vcol, 1.5))
            p.setBrush(Qt.NoBrush)
            xx, yy = X(q.energy), Y(q.efficiency)
            p.drawRect(QRectF(xx - 3.5, yy - 3.5, 7, 7))
        # residuals
        if self.curve is not None and self.curve.params:
            rr = []
            for q in pts + xtra:
                f = float(self.curve.efficiency(q.energy))
                rr.append((q, 100 * (q.efficiency - f) / f, 100 * q.unc / f, q in xtra))
            lim = max([abs(r) + u for _, r, u, _x in rr] + [2.0]) * 1.15

            def RY(v):
                return res.center().y() - v / lim * res.height() / 2

            p.setPen(QPen(fg, 1, Qt.DashLine))
            p.drawLine(QPointF(res.left(), RY(0)), QPointF(res.right(), RY(0)))
            p.setPen(fg)
            p.drawText(QRectF(0, res.top(), L - 4, 14), Qt.AlignRight, f"+{lim:.0f}%")
            p.drawText(QRectF(0, res.bottom() - 14, L - 4, 14), Qt.AlignRight, f"-{lim:.0f}%")
            for q, r, u, is_x in rr:
                col = vcol if is_x else (QColor(200, 60, 40) if q.use else QColor(150, 150, 150))
                p.setPen(QPen(col, 1.5))
                p.setBrush(Qt.NoBrush if is_x else col)
                xx = X(q.energy)
                p.drawLine(QPointF(xx, RY(r + u)), QPointF(xx, RY(r - u)))
                if is_x:
                    p.drawRect(QRectF(xx - 3, RY(r) - 3, 6, 6))
                else:
                    p.drawEllipse(QPointF(xx, RY(r)), 3, 3)
        p.end()


def describe_curve(c) -> str:
    """Translated one-line model description (``EfficiencyCurve.describe`` is English, for files/CLI)."""
    if c.model == "two_branch":
        return qtr("eff_desc_two", ec=c.e_ref, o1=c.order, o2=c.order_high)
    return qtr("eff_desc_loglog", o=c.order)


# ===================================================================== certificate inputs
class CertificateEditor(QWidget):
    """Certificate table (nuclide, activity, uncertainty, reference date, half-life, lines)
    with presets, Aptec records, CSV import/export.  Used for the calibration standard and
    for the independent check source."""

    def __init__(self, parent=None, spectrum_fn: Optional[Callable] = None, msg: Optional[Callable] = None,
                 folder_fn: Optional[Callable] = None):
        super().__init__(parent)
        self._spectrum_fn = spectrum_fn or (lambda: None)
        self._msg = msg or (lambda text: QMessageBox.warning(self, qtr("eff_title"), text))
        self._folder = folder_fn or (lambda name: "")
        cl = QVBoxLayout(self)
        cl.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(QLabel(qtr("eff_preset")))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(eff.PRESETS))
        row.addWidget(self.preset_combo)
        b = QPushButton(qtr("eff_apply_preset"))
        b.clicked.connect(self.apply_preset)
        row.addWidget(b)
        self.btn_aptec = QPushButton(qtr("eff_aptec"))
        self.btn_aptec.setToolTip(qtr("tip_eff_aptec"))
        self.btn_aptec.clicked.connect(self.load_aptec_records)
        row.addWidget(self.btn_aptec)
        for key, slot in (("eff_import_csv", self.import_csv), ("eff_export_csv", self.export_csv),
                          ("eff_add", self.add_cert_row), ("eff_remove", self.remove_cert_rows)):
            b = QPushButton(qtr(key))
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
        row.addStretch(1)
        cl.addLayout(row)
        self.cert_table = QTableWidget(0, len(CERT_COLS))
        self.cert_table.setHorizontalHeaderLabels([qtr(k) for k in CERT_COLS])
        self.cert_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.cert_table.horizontalHeader().setStretchLastSection(True)
        self.cert_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        cl.addWidget(self.cert_table)
        self.update_aptec()

    def update_aptec(self) -> None:
        self.btn_aptec.setEnabled(bool(self._aptec_records()))

    def _aptec_records(self):
        s = self._spectrum_fn()
        p = s.source_path if s is not None else ""
        if p and Path(p).suffix.lower() == ".s0" and Path(p).is_file():
            try:
                return eff.aptec_source_records(p)
            except Exception:
                return []
        return []

    def set_certificate(self, entries) -> None:
        self.cert_table.setRowCount(0)
        for c in entries:
            self.add_cert_row(c)

    def add_cert_row(self, c: Optional[eff.CertNuclide] = None) -> None:
        if not isinstance(c, eff.CertNuclide):
            c = eff.CertNuclide("", 0.0, 0.0, None)
        r = self.cert_table.rowCount()
        self.cert_table.insertRow(r)
        pct = 100.0 * c.activity_unc / c.activity if c.activity else 0.0
        vals = [c.nuclide, f"{c.activity:.6g}" if c.activity else "", f"{pct:.3g}",
                c.ref_date.strftime("%Y-%m-%d %H:%M") if c.ref_date else "",
                f"{c.half_life_s:.6g}" if c.half_life_s else "", _lines_text(c.lines)]
        for k, v in enumerate(vals):
            self.cert_table.setItem(r, k, QTableWidgetItem(v))

    def remove_cert_rows(self) -> None:
        for r in sorted({i.row() for i in self.cert_table.selectedIndexes()}, reverse=True):
            self.cert_table.removeRow(r)

    def certificate(self) -> list[eff.CertNuclide]:
        out = []
        for r in range(self.cert_table.rowCount()):
            def t(k):
                it = self.cert_table.item(r, k)
                return it.text().strip() if it else ""
            name = t(0)
            act = _num(t(1))
            if not name or not act:
                continue
            pct = _num(t(2), 0.0) or 0.0
            out.append(eff.CertNuclide(name, act, act * pct / 100.0, eff.parse_date(t(3)) if t(3) else None,
                                       _num(t(4)), _parse_lines(t(5))))
        return out

    def apply_preset(self) -> None:
        self.set_certificate(eff.preset_entries(self.preset_combo.currentText()))

    def load_aptec_records(self) -> None:
        recs = self._aptec_records()
        if not recs:
            self._msg(qtr("eff_no_aptec"))
            return
        lines = eff.certificate_from_aptec(recs)
        by: dict[str, list] = {}
        for ln in lines:
            by.setdefault(ln.nuclide, []).append(ln)
        entries = []
        for name, ls in by.items():
            a = sum(l.activity for l in ls) / len(ls)
            u = sum(l.activity_unc for l in ls) / len(ls)
            entries.append(eff.CertNuclide(name, a, u, ls[0].ref_date, ls[0].half_life_s,
                                           [(l.energy, l.intensity) for l in ls]))
        self.set_certificate(entries)

    def import_csv(self, path: Optional[str] = None) -> None:
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, qtr("eff_import_csv"), self._folder("effcal"), "CSV (*.csv)")
        if path:
            try:
                self.set_certificate(eff.read_certificate_csv(path))
            except Exception as exc:
                self._msg(qtr("eff_failed", msg=str(exc)))

    def export_csv(self, path: Optional[str] = None) -> None:
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, qtr("eff_export_csv"), self._folder("effcal"), "CSV (*.csv)")
        if path:
            eff.write_certificate_csv(path, self.certificate())


# ===================================================================== wizard
class EfficiencyDialog(QDialog):
    """Wizard dialog.  ``spectrum``: the displayed spectrum (optional)."""

    def __init__(self, parent=None, spectrum=None, settings=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.settings = settings
        self._current = spectrum
        self.spectrum = None
        self.points: list[eff.EfficiencyPoint] = []
        self.curve: Optional[eff.EfficiencyCurve] = None
        self.saved_path: Optional[Path] = None
        self.record_path: Optional[Path] = None
        self.record = None
        self.val_spectrum = None
        self.background = None                   # optional background spectrum (peak by peak)
        self.val_points: list[eff.EfficiencyPoint] = []
        self.validation: Optional[dict] = None
        self.validation_note = ""
        self.last_error = ""
        self._busy = False
        self._pending: Optional[Callable] = None
        self._filling = False
        self._origin = "measured"                # CalibrationRecord.source of the current curve
        self.setWindowTitle(qtr("eff_title"))
        self.resize(1150, 820)
        lay = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel(qtr("eff_standard")))
        self.std_edit = QLineEdit()
        self.std_edit.setReadOnly(True)
        self.std_edit.setLayoutDirection(Qt.LeftToRight)
        row.addWidget(self.std_edit, 1)
        b = QPushButton(qtr("eff_browse"))
        b.clicked.connect(self.browse_standard)
        row.addWidget(b)
        self.btn_current = QPushButton(qtr("eff_use_current"))
        self.btn_current.setEnabled(spectrum is not None)
        self.btn_current.clicked.connect(lambda: self.set_standard(self._current))
        row.addWidget(self.btn_current)
        lay.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel(qtr("eff_background")))
        self.bkg_edit = QLineEdit()
        self.bkg_edit.setReadOnly(True)
        self.bkg_edit.setLayoutDirection(Qt.LeftToRight)
        self.bkg_edit.setPlaceholderText(qtr("act_bkg_none"))
        self.bkg_edit.setToolTip(qtr("tip_eff_background"))
        row.addWidget(self.bkg_edit, 1)
        b = QPushButton(qtr("eff_browse"))
        b.clicked.connect(self.browse_background)
        row.addWidget(b)
        b = QPushButton(qtr("act_clear"))
        b.clicked.connect(lambda: self.set_background(None))
        row.addWidget(b)
        lay.addLayout(row)
        # geometry name / detector: a row of their own (squeezed next to the fit options they
        # were clipped to a few characters)
        meta = QHBoxLayout()
        meta.addWidget(QLabel(qtr("eff_geometry")))
        self.geom_edit = QLineEdit()
        self.geom_edit.setMinimumWidth(220)
        meta.addWidget(self.geom_edit, 2)
        meta.addSpacing(12)
        meta.addWidget(QLabel(qtr("eff_detector")))
        self.det_edit = QLineEdit()
        self.det_edit.setMinimumWidth(180)
        meta.addWidget(self.det_edit, 1)
        lay.addLayout(meta)

        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        # --- 1. certificate
        page = QWidget()
        pl = QVBoxLayout(page)
        intro = QLabel(qtr("eff_step_cert_intro"))
        intro.setWordWrap(True)
        pl.addWidget(intro)
        self.cert = CertificateEditor(page, lambda: self.spectrum, lambda t: self._msg(t), self._folder)
        self.cert_table = self.cert.cert_table
        self.preset_combo = self.cert.preset_combo
        self.btn_aptec = self.cert.btn_aptec
        pl.addWidget(self.cert, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel(qtr("eff_u_common")))
        self.u_common_edit = QLineEdit()
        self.u_common_edit.setLayoutDirection(Qt.LeftToRight)
        self.u_common_edit.setPlaceholderText(qtr("eff_not_stated"))
        self.u_common_edit.setToolTip(qtr("tip_eff_u_common"))
        self.u_common_edit.setMaximumWidth(140)
        row.addWidget(self.u_common_edit)
        hint = QLabel(qtr("eff_u_common_hint"))
        hint.setWordWrap(True)
        row.addWidget(hint, 1)
        pl.addLayout(row)
        self.tabs.addTab(page, qtr("eff_tab_cert"))

        # --- 2. detector and geometry
        page = QWidget()
        pl = QVBoxLayout(page)
        intro = QLabel(qtr("eff_step_geo_intro"))
        intro.setWordWrap(True)
        pl.addWidget(intro)
        self.geo = GeometryEditor(page, name_edit=self.geom_edit)
        pl.addWidget(self.geo)
        pl.addStretch(1)
        self.tabs.addTab(page, qtr("eff_tab_geometry"))

        # --- 3. points and model
        page = QWidget()
        pl = QVBoxLayout(page)
        form = QHBoxLayout()
        form.addWidget(QLabel(qtr("eff_model")))
        self.model_combo = QComboBox()
        self.model_combo.addItem(qtr("eff_model_two"), "two_branch")
        self.model_combo.addItem(qtr("eff_model_loglog"), "loglog")
        self.model_combo.currentIndexChanged.connect(self._model_changed)
        form.addWidget(self.model_combo)
        self.order_mode = QComboBox()
        self.order_mode.addItem(qtr("eff_orders_auto"), "auto")
        self.order_mode.addItem(qtr("eff_orders_explicit"), "explicit")
        self.order_mode.setToolTip(qtr("tip_eff_orders_auto"))
        self.order_mode.currentIndexChanged.connect(self._model_changed)
        form.addWidget(self.order_mode)
        form.addStretch(1)
        self.btn_measure = QPushButton(qtr("eff_measure"))
        self.btn_measure.clicked.connect(lambda: self.measure_and_fit(threaded=True))
        form.addWidget(self.btn_measure)
        pl.addLayout(form)
        form = QHBoxLayout()
        self.lbl_order = QLabel(qtr("eff_order"))
        form.addWidget(self.lbl_order)
        self.order_spin = QSpinBox()
        self.order_spin.setRange(1, 5)
        self.order_spin.setValue(3)
        form.addWidget(self.order_spin)
        self.lbl_high = QLabel(qtr("eff_order_high"))
        form.addWidget(self.lbl_high)
        self.order_high_spin = QSpinBox()
        self.order_high_spin.setRange(1, 5)
        self.order_high_spin.setValue(2)
        form.addWidget(self.order_high_spin)
        self.lbl_cross = QLabel(qtr("eff_crossover"))
        form.addWidget(self.lbl_cross)
        self.cross_spin = QDoubleSpinBox()
        self.cross_spin.setRange(20, 3000)
        self.cross_spin.setValue(200)
        self.cross_spin.setDecimals(1)
        form.addWidget(self.cross_spin)
        self.cross_auto = QCheckBox(qtr("eff_auto"))
        self.cross_auto.setChecked(True)
        self.cross_auto.toggled.connect(lambda on: self.cross_spin.setEnabled(not on))
        self.cross_spin.setEnabled(False)
        form.addWidget(self.cross_auto)
        form.addStretch(1)
        pl.addLayout(form)

        split = QSplitter(Qt.Horizontal)
        pbox = QGroupBox(qtr("eff_points_group"))
        bl = QVBoxLayout(pbox)
        self.pt_table = QTableWidget(0, len(PT_COLS))
        self.pt_table.setHorizontalHeaderLabels([qtr(k) for k in PT_COLS])
        self.pt_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.pt_table.horizontalHeader().setStretchLastSection(True)
        self.pt_table.itemChanged.connect(self._pt_item_changed)
        bl.addWidget(self.pt_table, 3)
        legend = QLabel(qtr("eff_points_legend"))
        legend.setWordWrap(True)
        bl.addWidget(legend)
        self.warn_label = QLabel("")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet("color: #c62828; font-weight: bold;")
        bl.addWidget(self.warn_label)
        self.warn_list = QListWidget()
        self.warn_list.setLayoutDirection(Qt.LeftToRight)      # engine text is English
        self.warn_list.setWordWrap(True)
        self.warn_list.setMaximumHeight(90)
        self.warn_list.setVisible(False)
        bl.addWidget(self.warn_list, 1)
        row = QHBoxLayout()
        b = QPushButton(qtr("eff_add_point"))
        b.clicked.connect(lambda: self.add_manual_point())
        row.addWidget(b)
        self.btn_refit = QPushButton(qtr("eff_refit"))
        self.btn_refit.clicked.connect(lambda: self.refit(threaded=True))
        row.addWidget(self.btn_refit)
        row.addStretch(1)
        bl.addLayout(row)
        split.addWidget(pbox)
        self.plot = EfficiencyPlot()
        split.addWidget(self.plot)
        split.setSizes([600, 480])
        pl.addWidget(split, 1)
        self.summary = QLabel("")
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.summary.setWordWrap(True)
        pl.addWidget(self.summary)
        self.selection_label = QLabel("")
        self.selection_label.setWordWrap(True)
        self.selection_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        pl.addWidget(self.selection_label)
        self.tabs.addTab(page, qtr("eff_tab_points"))

        # --- 4. independent validation
        page = QWidget()
        pl = QVBoxLayout(page)
        intro = QLabel(qtr("eff_val_intro"))
        intro.setWordWrap(True)
        pl.addWidget(intro)
        row = QHBoxLayout()
        row.addWidget(QLabel(qtr("eff_val_spectrum")))
        self.val_std_edit = QLineEdit()
        self.val_std_edit.setReadOnly(True)
        self.val_std_edit.setLayoutDirection(Qt.LeftToRight)
        row.addWidget(self.val_std_edit, 1)
        b = QPushButton(qtr("eff_browse"))
        b.clicked.connect(self.browse_validation)
        row.addWidget(b)
        b = QPushButton(qtr("eff_use_current"))
        b.setEnabled(spectrum is not None)
        b.clicked.connect(lambda: self.set_validation_spectrum(self._current))
        row.addWidget(b)
        pl.addLayout(row)
        vsplit = QSplitter(Qt.Vertical)
        cbox = QGroupBox(qtr("eff_val_cert_group"))
        QVBoxLayout(cbox)
        self.val_cert = CertificateEditor(cbox, lambda: self.val_spectrum, lambda t: self._msg(t), self._folder)
        cbox.layout().addWidget(self.val_cert)
        vsplit.addWidget(cbox)
        w = QWidget()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.btn_validate = QPushButton(qtr("eff_val_run"))
        self.btn_validate.clicked.connect(lambda: self.measure_validation(threaded=True))
        row.addWidget(self.btn_validate)
        row.addStretch(1)
        wl.addLayout(row)
        self.val_table = QTableWidget(0, len(VAL_COLS))
        self.val_table.setHorizontalHeaderLabels([qtr(k) for k in VAL_COLS])
        self.val_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.val_table.horizontalHeader().setStretchLastSection(True)
        self.val_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        wl.addWidget(self.val_table, 1)
        self.val_verdict = QLabel("")
        self.val_verdict.setWordWrap(True)
        self.val_verdict.setStyleSheet("font-weight: bold;")
        wl.addWidget(self.val_verdict)
        self.val_message = QLabel("")
        self.val_message.setWordWrap(True)
        self.val_message.setLayoutDirection(Qt.LeftToRight)
        self.val_message.setTextInteractionFlags(Qt.TextSelectableByMouse)
        wl.addWidget(self.val_message)
        row = QHBoxLayout()
        row.addWidget(QLabel(qtr("eff_val_note")))
        self.val_note_edit = QLineEdit()
        self.val_note_edit.setPlaceholderText(qtr("eff_val_note_hint"))
        row.addWidget(self.val_note_edit, 1)
        self.btn_mark = QPushButton(qtr("eff_mark_validated"))
        self.btn_mark.setEnabled(False)
        self.btn_mark.clicked.connect(lambda: self.mark_validated())
        row.addWidget(self.btn_mark)
        wl.addLayout(row)
        vsplit.addWidget(w)
        vsplit.setSizes([260, 320])
        pl.addWidget(vsplit, 1)
        self.tabs.addTab(page, qtr("eff_tab_validation"))

        # --- bottom: status + files
        row = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-weight: bold;")
        row.addWidget(self.status_label)
        self.busy_label = QLabel("")
        row.addWidget(self.busy_label)
        row.addStretch(1)
        self.btn_save = QPushButton(qtr("eff_save"))
        self.btn_save.clicked.connect(lambda: self.save_curve())
        row.addWidget(self.btn_save)
        b = QPushButton(qtr("eff_load"))
        b.clicked.connect(lambda: self.load_curve_dialog())
        row.addWidget(b)
        b = QPushButton(qtr("eff_close"))
        b.clicked.connect(self.accept)
        row.addWidget(b)
        lay.addLayout(row)
        if spectrum is not None:
            self.set_standard(spectrum)
        self._model_changed()
        self._update_status()

    # ------------------------------------------------------------------ helpers
    def _msg(self, text: str, error: bool = True) -> None:
        self.last_error = text if error else self.last_error
        (QMessageBox.warning if error else QMessageBox.information)(self, qtr("eff_title"), text)

    def ask_reason(self, label: str) -> Optional[str]:
        """Reason for excluding a point (None = cancelled).  Tests replace this method."""
        text, ok = QInputDialog.getText(self, qtr("eff_reason_title"), qtr("eff_reason_prompt", label=ltr(label)))
        return text if ok else None

    def ask_validation_note(self) -> Optional[str]:
        text, ok = QInputDialog.getText(self, qtr("eff_mark_validated"), qtr("eff_val_note_required"))
        return text if ok else None

    @property
    def busy(self) -> bool:
        return self._busy

    def _model_changed(self, *_):
        two = self.model_combo.currentData() == "two_branch"
        auto = self.order_mode.currentData() == "auto"
        for w in (self.lbl_high, self.order_high_spin, self.lbl_cross, self.cross_auto):
            w.setVisible(two)
        self.cross_spin.setVisible(two)
        for w in (self.order_spin, self.order_high_spin):
            w.setEnabled(not auto)

    def _folder(self, name: str) -> str:
        return self.settings.folder(name) if self.settings is not None else ""

    def _set_busy(self, on: bool) -> None:
        self._busy = on
        self.busy_label.setText(qtr("eff_busy") if on else "")
        for w in (self.btn_measure, self.btn_refit, self.btn_validate, self.btn_save, self.pt_table):
            w.setEnabled(not on)
        if on:
            self.btn_mark.setEnabled(False)
        else:
            self._update_mark()

    def _run(self, work: Callable, on_done: Callable, threaded: bool) -> bool:
        """Run `work()` (no widget access) and pass its result to `on_done` in the GUI thread."""
        if self._busy:
            return False
        if not threaded:
            try:
                result = work()
            except Exception as exc:
                self._msg(qtr("eff_failed", msg=f"{exc}"))
                return False
            return bool(on_done(result))
        self._pending = on_done
        self._set_busy(True)
        start_call(self, work, self._on_work_done, self._on_work_failed)
        return True

    def _on_work_done(self, result) -> None:
        cb, self._pending = self._pending, None
        self._set_busy(False)
        if cb is not None:
            cb(result)

    def _on_work_failed(self, msg: str) -> None:
        self._pending = None
        self._set_busy(False)
        self._msg(qtr("eff_failed", msg=msg))

    def _update_status(self) -> None:
        c = self.curve
        if c is None:
            self.status_label.setText(qtr("eff_status_none"))
            self.status_label.setStyleSheet("font-weight: bold; color: gray;")
            return
        st = c.validation_status
        self.status_label.setText(qtr("eff_status_line", status=status_text(st)))
        self.status_label.setStyleSheet("font-weight: bold; color: %s;" % (
            "#2e7d32" if st == "validated" else "#c62828" if st == "rejected" else "#e65100"))
        self.plot.update()

    def _update_mark(self) -> None:
        ok = bool(self.curve is not None and self.validation and self.validation.get("consistent"))
        self.btn_mark.setEnabled(ok and not self._busy)

    # ------------------------------------------------------------------ standard
    def browse_standard(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, qtr("eff_standard"), self._folder("open"))
        if path:
            self.load_standard(path)

    def _read_spectrum(self, path):
        from ..convert import read_spectra
        try:
            spectra, _fmt = read_spectra(Path(path))
        except Exception as exc:
            self._msg(qtr("eff_failed", msg=str(exc)))
            return None
        s = spectra[0]
        s.source_path = s.source_path or str(path)
        return s

    def load_standard(self, path) -> bool:
        s = self._read_spectrum(path)
        if s is None:
            return False
        self.set_standard(s)
        return True

    def set_standard(self, spectrum) -> None:
        if spectrum is None:
            return
        self.spectrum = spectrum
        self.std_edit.setText(i18n.bidi_path(spectrum.source_path) if spectrum.source_path else spectrum.sample_id)
        self.std_edit.setToolTip(spectrum.source_path or "")
        self.std_edit.setCursorPosition(0)
        if not self.det_edit.text():
            self.det_edit.setText(spectrum.detector or "")
        if not self.geom_edit.text():
            self.geom_edit.setText(str(spectrum.extra.get("geometry_id", "") or ""))
        self.cert.update_aptec()

    def browse_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, qtr("eff_background"), self._folder("open"))
        if path:
            s = self._read_spectrum(path)
            if s is not None:
                self.set_background(s)

    def set_background(self, spectrum) -> None:
        """Background spectrum subtracted peak by peak from the standard and the check source."""
        self.background = spectrum
        self.bkg_edit.setText("" if spectrum is None else (
            i18n.bidi_path(spectrum.source_path) if spectrum.source_path else spectrum.sample_id))
        self.bkg_edit.setCursorPosition(0)

    # ------------------------------------------------------------------ certificate (delegates)
    def set_certificate(self, entries) -> None:
        self.cert.set_certificate(entries)

    def add_cert_row(self, c: Optional[eff.CertNuclide] = None) -> None:
        self.cert.add_cert_row(c)

    def remove_cert_rows(self) -> None:
        self.cert.remove_cert_rows()

    def certificate(self) -> list[eff.CertNuclide]:
        return self.cert.certificate()

    def apply_preset(self) -> None:
        self.cert.apply_preset()

    def load_aptec_records(self) -> None:
        self.cert.load_aptec_records()

    def import_csv(self, path: Optional[str] = None) -> None:
        self.cert.import_csv(path)

    def export_csv(self, path: Optional[str] = None) -> None:
        self.cert.export_csv(path)

    def u_common(self) -> Optional[float]:
        """Common standard uncertainty (fraction) or None when not stated; ValueError if invalid."""
        t = self.u_common_edit.text().strip().replace(",", ".").rstrip("%").strip()
        if not t:
            return None
        try:
            v = float(t)
        except ValueError:
            raise ValueError(qtr("eff_bad_u_common", text=self.u_common_edit.text())) from None
        if not 0 <= v < 100 or not math.isfinite(v):
            raise ValueError(qtr("eff_bad_u_common", text=self.u_common_edit.text()))
        return v / 100.0 if v > 0 else None

    # ------------------------------------------------------------------ measure / fit
    def measure_and_fit(self, threaded: bool = False) -> bool:
        if self.spectrum is None:
            self._msg(qtr("eff_no_spectrum"))
            return False
        cert = self.certificate()
        if not cert:
            self._msg(qtr("eff_no_cert"))
            return False
        try:
            fit = self._fit_call()
        except ValueError as exc:
            self._msg(str(exc))
            return False
        spec, bkg = self.spectrum, self.background

        def work():
            pts = eff.measure_efficiency(spec, eff.certificate_lines(cert), background=bkg)
            try:
                curve, err = fit(pts), ""
            except Exception as exc:          # keep the points for review even when the fit fails
                curve, err = None, f"{exc}"
            return pts, curve, err

        return self._run(work, self._on_measured, threaded)

    def _on_measured(self, result) -> bool:
        pts, curve, err = result
        self.points = pts
        self._origin = "measured"
        self._fill_points()
        if curve is None:
            self.curve = None
            self.plot.set_data(self.points, None)
            self._show_fit()
            self._msg(qtr("eff_failed", msg=err))
            return False
        return self._on_fitted(curve)

    def _fill_points(self) -> None:
        t = self.pt_table
        self._filling = True
        t.blockSignals(True)
        t.setRowCount(0)
        for p in self.points:
            r = t.rowCount()
            t.insertRow(r)
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Checked if p.use else Qt.Unchecked)
            t.setItem(r, 0, chk)
            vals = [p.nuclide, f"{p.energy:.2f}", "" if p.net_area is None else f"{p.net_area:.0f}",
                    f"{p.efficiency:.5g}", f"{100 * p.rel_unc:.2f}", "", "", p.note]
            summing = eff.TCS_NOTE in (p.note or "")
            for k, v in enumerate(vals, start=1):
                it = QTableWidgetItem(v)
                if not (p.manual and k in (2, 4, 5)):
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if summing:
                    it.setBackground(QBrush(SUMMING_COLOR))
                if not p.use:
                    it.setForeground(QBrush(QColor(130, 130, 130)))
                if p.note:
                    it.setToolTip(p.note)
                t.setItem(r, k, it)
        t.blockSignals(False)
        self._filling = False

    def _read_points(self) -> None:
        t = self.pt_table
        for r, p in enumerate(self.points):
            if r >= t.rowCount():
                break
            p.use = t.item(r, 0).checkState() == Qt.Checked
            if p.manual:
                e, v, u = _num(t.item(r, 2).text()), _num(t.item(r, 4).text()), _num(t.item(r, 5).text(), 2.0)
                if e and v:
                    p.energy, p.efficiency = e, v
                    p.unc = v * (u or 0.0) / 100.0
                    p.u_count_rel = (u or 0.0) / 100.0

    def _pt_item_changed(self, item) -> None:
        if self._filling or item.column() != 0:
            return
        r = item.row()
        if 0 <= r < len(self.points):
            used = item.checkState() == Qt.Checked
            if used != self.points[r].use:
                self.set_point_used(r, used, threaded=True)

    def _set_check(self, row: int, used: bool) -> None:
        it = self.pt_table.item(row, 0)
        if it is not None:
            self.pt_table.blockSignals(True)
            it.setCheckState(Qt.Checked if used else Qt.Unchecked)
            self.pt_table.blockSignals(False)

    def set_point_used(self, row: int, used: bool, reason: Optional[str] = None, threaded: bool = False) -> bool:
        """Include / exclude point `row` and refit.  Excluding needs a reason, recorded in the
        point's note as ``"excluded by user: <reason>"``.  Returns False when refused."""
        if self._busy or not 0 <= row < len(self.points):
            return False
        p = self.points[row]
        before = (p.use, p.note)
        if not used:
            if reason is None:
                reason = self.ask_reason(f"{p.nuclide} {p.energy:.1f} keV")
            if reason is None or not reason.strip():
                if reason is not None:
                    self._msg(qtr("eff_reason_required"))
                self._set_check(row, p.use)
                return False
            p.use = False
            p.note = note_with_exclusion(p.note, reason)
        else:
            p.use = True
            p.note = note_without_exclusion(p.note)
        self._set_check(row, p.use)
        self._read_points()      # manual-point edits; `use` of every row equals the table now
        self._fill_points()
        ok = self.refit(threaded=threaded)
        if not ok and not threaded:          # e.g. too few points left: keep the previous review
            p.use, p.note = before
            self._fill_points()
            self.refit()
        return ok

    def add_manual_point(self, energy: float = 0.0, efficiency: float = 0.0, unc_pct: float = 2.0) -> None:
        self._read_points()
        p = eff.manual_point(energy or 100.0, efficiency or 0.01, unc_pct)
        p.use = bool(energy and efficiency)
        self.points.append(p)
        if all(q.manual for q in self.points):
            self._origin = "manual"
        self._fill_points()

    def _fit_call(self) -> Callable:
        """fit(points) -> curve with the options of the dialog (read here, in the GUI thread)."""
        model = self.model_combo.currentData()
        auto = self.order_mode.currentData() == "auto"
        order = None if auto else self.order_spin.value()
        order_high = None if auto else self.order_high_spin.value()
        # (the crossover is a two-branch parameter; the engine wants a number for log-log)
        cross = "auto" if (model == "two_branch" and self.cross_auto.isChecked()) else self.cross_spin.value()
        u_sys = self.u_common()
        name = self.geom_edit.text().strip()
        geo = self.geo.geometry(name=name or qtr("geo_unnamed"))
        # nothing entered: the geometry is "not recorded" (activity results say so), not "other"
        geo_rec = {} if (self.geo.kind() == "other" and self.geo.is_empty()) else geo.to_dict()
        src = self.spectrum.source_path if self.spectrum is not None else ""
        date = self.spectrum.start_time.strftime("%Y-%m-%d %H:%M") if (
            self.spectrum is not None and self.spectrum.start_time) else ""
        meta = dict(geometry=name, detector=self.det_edit.text(), source=src or "", date=date,
                    geometry_record=geo_rec)

        def fit(points):
            return eff.fit_efficiency(points, model, order=order, crossover=cross, order_high=order_high,
                                      u_sys_rel=u_sys, **dict(meta, geometry_record=dict(meta["geometry_record"])))
        return fit

    def refit(self, threaded: bool = False) -> bool:
        self._read_points()
        try:
            fit = self._fit_call()
        except ValueError as exc:
            self._msg(str(exc))
            return False
        pts = self.points

        def work():
            return fit(pts)

        if not threaded:
            try:
                curve = work()
            except Exception as exc:
                self.curve = None
                self.plot.set_data(self.points, None)
                self._show_fit()
                self._msg(qtr("eff_failed", msg=str(exc)))
                return False
            return self._on_fitted(curve)
        return self._run(work, self._on_fitted, True)

    def _on_fitted(self, curve) -> bool:
        self.curve = curve
        for w, v in ((self.order_spin, curve.order), (self.order_high_spin, curve.order_high)):
            w.blockSignals(True)
            w.setValue(int(v))
            w.blockSignals(False)
        if curve.model == "two_branch":
            self.cross_spin.setValue(curve.e_ref)
        # a new fit is a new curve: a former validation verdict does not carry over
        self.validation_note = ""
        if self.val_points:
            self.run_validation()
        else:
            self._show_validation()
        self._show_fit()
        return True

    def _show_fit(self) -> None:
        c = self.curve
        t = self.pt_table
        t.blockSignals(True)
        for r, p in enumerate(self.points):
            if r < t.rowCount() and c is not None:
                f = float(c.efficiency(p.energy))
                for k, v in ((6, f"{f:.5g}"), (7, ltr(f"{100 * (p.efficiency - f) / f:+.2f}"))):
                    it = QTableWidgetItem(v)
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    if eff.TCS_NOTE in (p.note or ""):
                        it.setBackground(QBrush(SUMMING_COLOR))
                    t.setItem(r, k, it)
        t.blockSignals(False)
        self.plot.set_data(self.points, c, self.val_points)
        self.warn_list.clear()
        if c is None:
            self.summary.setText("")
            self.selection_label.setText("")
            self.warn_label.setText("")
            self.warn_list.setVisible(False)
            self._update_status()
            return
        self.summary.setText(
            qtr("eff_summary", model=describe_curve(c), chi2=c.reduced_chi2,
                n=sum(1 for p in self.points if p.use),
                e661=float(c.efficiency(661.66)), u661=100 * float(c.rel_uncertainty(661.66)))
            + "\n" + qtr("eff_summary2", chi2=ltr(f"{c.chi2:.2f}"), dof=ltr(c.dof),
                         umodel=ltr(f"{100 * c.u_model_rel:.2f} %"),
                         ucommon=ltr(f"{100 * c.u_common_rel:.2f} %") if c.u_common_rel else qtr("eff_not_stated"),
                         lo=ltr(f"{c.e_min:.0f}"), hi=ltr(f"{c.e_max:.0f}"), status=status_text(c.validation_status)))
        self.selection_label.setText(qtr("eff_selection", text=ltr(c.selection)) if c.selection
                                     else qtr("eff_selection_explicit"))
        n_user = sum(1 for p in self.points if is_user_excluded(p))
        n_tcs = sum(1 for p in self.points if p.use and eff.TCS_NOTE in (p.note or ""))
        parts = []
        if c.warnings:
            parts.append(qtr("eff_outliers", n=ltr(len(c.warnings))))
        if n_tcs:
            parts.append(qtr("eff_summing_used", n=ltr(n_tcs)))
        if n_user:
            parts.append(qtr("eff_user_excluded", n=ltr(n_user)))
        self.warn_label.setText("\n".join(parts))
        for w in c.warnings:
            self.warn_list.addItem(w)
            self.warn_list.item(self.warn_list.count() - 1).setForeground(QBrush(WARN_COLOR))
        self.warn_list.setVisible(bool(c.warnings))
        self._update_status()

    # ------------------------------------------------------------------ independent validation
    def browse_validation(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, qtr("eff_val_spectrum"), self._folder("open"))
        if path:
            self.load_validation_spectrum(path)

    def load_validation_spectrum(self, path) -> bool:
        s = self._read_spectrum(path)
        if s is None:
            return False
        self.set_validation_spectrum(s)
        return True

    def set_validation_spectrum(self, spectrum) -> None:
        if spectrum is None:
            return
        self.val_spectrum = spectrum
        self.val_std_edit.setText(i18n.bidi_path(spectrum.source_path) if spectrum.source_path
                                  else spectrum.sample_id)
        self.val_std_edit.setToolTip(spectrum.source_path or "")
        self.val_std_edit.setCursorPosition(0)
        self.val_cert.update_aptec()

    def measure_validation(self, threaded: bool = False) -> bool:
        """Measure the check source's points and compare them with the current curve."""
        if self.curve is None:
            self._msg(qtr("eff_val_no_curve"))
            return False
        if self.val_spectrum is None:
            self._msg(qtr("eff_val_no_spectrum"))
            return False
        cert = self.val_cert.certificate()
        if not cert:
            self._msg(qtr("eff_no_cert"))
            return False
        spec, bkg = self.val_spectrum, self.background

        def work():
            return eff.measure_efficiency(spec, eff.certificate_lines(cert), background=bkg)

        def done(pts):
            self.val_points = pts
            self.run_validation()
            return True

        return self._run(work, done, threaded)

    def run_validation(self) -> Optional[dict]:
        if self.curve is None or not self.val_points:
            self.validation = None
            self._show_validation()
            return None
        self.validation = eff.validate_curve(self.curve, self.val_points)
        self._show_validation()
        return self.validation

    def _show_validation(self) -> None:
        v = self.validation
        t = self.val_table
        t.setRowCount(0)
        if v is not None:
            for r, row in enumerate(v["rows"]):
                t.insertRow(r)
                vals = [row["nuclide"], f"{row['energy']:.2f}", f"{row['point']:.5g}", f"{row['curve']:.5g}",
                        ltr(f"{row['dev_pct']:+.2f}"), ltr(f"{row['z']:+.2f}"),
                        qtr("eff_yes") if row["in_range"] else qtr("eff_no")]
                for k, val in enumerate(vals):
                    it = QTableWidgetItem(val)
                    if k == 5 and abs(row["z"]) > eff.VALIDATION_MAX_Z:
                        it.setForeground(QBrush(WARN_COLOR))
                    if row.get("also_in_fit"):
                        it.setForeground(QBrush(QColor(130, 130, 130)))
                        it.setToolTip(qtr("eff_val_also_in_fit"))
                    t.setItem(r, k, it)
            self.val_message.setText(v["message"])
            ok = v["consistent"]
            self.val_verdict.setText(qtr("eff_val_consistent" if ok else "eff_val_not_consistent", n=ltr(v["n"])))
            self.val_verdict.setStyleSheet("font-weight: bold; color: %s;" % ("#2e7d32" if ok else "#c62828"))
        else:
            self.val_message.setText("")
            self.val_verdict.setText("")
        self.plot.set_data(self.points, self.curve, self.val_points)
        self._update_mark()
        self._update_status()

    def mark_validated(self, note: Optional[str] = None) -> bool:
        """Mark the current curve validated (only after a consistent independent check; a note
        is required).  The note and the check summary go into the calibration record."""
        v = self.validation
        if self.curve is None or not v or not v.get("consistent"):
            self._msg(qtr("eff_val_not_allowed"))
            return False
        text = (note if note is not None else self.val_note_edit.text()).strip()
        if not text:
            text = (self.ask_validation_note() or "").strip()
        if not text:
            self._msg(qtr("eff_val_note_required"))
            return False
        self.val_note_edit.setText(text)
        src = self.val_spectrum.source_path if self.val_spectrum is not None and self.val_spectrum.source_path else ""
        self.validation_note = f"{text} | independent check{(' ' + Path(src).name) if src else ''}: {v['message']}"
        self.curve.validation_status = "validated"
        self.curve.note = (self.curve.note + "; " if self.curve.note else "") + "validated: " + text
        self._show_fit()
        return True

    # ------------------------------------------------------------------ persistence
    def make_record(self):
        """CalibrationRecord of the current curve (geometry id, source, validation status)."""
        from ..lab.calibration import CalibrationRecord
        c = self.curve
        geo_id = (c.geometry_record or {}).get("id") or None
        rec = CalibrationRecord.from_efficiency_curve(c, detector_id=None, geometry_id=geo_id, source=self._origin,
                                                      note=f"detector: {c.detector}" if c.detector else "")
        if c.validation_status in ("validated", "rejected"):
            rec.set_validation(c.validation_status, self.validation_note)
        return rec

    def save_curve(self, path: Optional[str] = None) -> Optional[Path]:
        if self.curve is None and not self.refit():
            return None
        if not path:
            d = eff.default_curve_dir()
            d.mkdir(parents=True, exist_ok=True)
            name = (self.geom_edit.text() or "efficiency").strip().replace(" ", "_")
            path, _ = QFileDialog.getSaveFileName(self, qtr("eff_save"), str(d / f"{name}.json"), "JSON (*.json)")
            if not path:
                return None
        if is_record_file(path):
            path = str(path)[: -len(RECORD_SUFFIX)] + ".json"
        self.curve.name = self.curve.name or Path(path).stem
        self.saved_path = self.curve.save(path)
        from ..lab.common import to_plain
        self.record = self.make_record()
        self.record_path = record_path_for(self.saved_path)
        self.record_path.write_text(json.dumps(to_plain(self.record.to_dict()), indent=1, ensure_ascii=False),
                                    encoding="utf-8")
        return self.saved_path

    def load_curve_dialog(self, path: Optional[str] = None) -> bool:
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, qtr("eff_load"), str(eff.default_curve_dir()), "JSON (*.json)")
        if not path:
            return False
        try:
            c, rec, issues = load_curve_file(path)
        except Exception as exc:
            self._msg(qtr("eff_failed", msg=str(exc)))
            return False
        self.curve = c
        self.record = rec
        self._origin = rec.source if rec is not None else "imported"
        self.validation_note = rec.validation_note if rec is not None else ""
        self.points = list(c.points)
        self.val_points, self.validation = [], None
        self.model_combo.setCurrentIndex(max(0, self.model_combo.findData(c.model)))
        self.order_mode.setCurrentIndex(self.order_mode.findData("explicit"))
        self.order_spin.setValue(c.order)
        self.order_high_spin.setValue(c.order_high)
        if c.model == "two_branch":
            self.cross_auto.setChecked(False)
            self.cross_spin.setValue(c.e_ref)
        if c.u_common_rel:
            self.u_common_edit.setText(f"{100 * c.u_common_rel:g}")
        self.geom_edit.setText(c.geometry)
        self.det_edit.setText(c.detector)
        if c.geometry_record:
            try:
                self.geo.set_geometry(c.geometry_record)
            except Exception:
                pass
            self.geom_edit.setText(c.geometry or c.geometry_record.get("name", ""))
        self._fill_points()
        self._show_validation()
        self._show_fit()
        if issues:
            self._msg("\n".join(issues))
        return True

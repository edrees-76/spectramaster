"""Efficiency-calibration wizard: standard spectrum -> certificate -> measured points -> fit -> save."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSpinBox, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..analysis import efficiency as eff
from . import i18n
from .quant_strings import qtr

CERT_COLS = ["eff_col_nuclide", "eff_col_activity", "eff_col_unc", "eff_col_ref", "eff_col_half", "eff_col_lines"]
PT_COLS = ["pt_col_use", "pt_col_nuclide", "pt_col_energy", "pt_col_net", "pt_col_eff", "pt_col_unc",
           "pt_col_fit", "pt_col_resid", "pt_col_note"]


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


class EfficiencyPlot(QWidget):
    """log-log plot of the measured points (with error bars) and the fitted curve + residuals."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 260)
        self.setLayoutDirection(Qt.LeftToRight)
        self.points: list = []
        self.curve: Optional[eff.EfficiencyCurve] = None

    def set_data(self, points, curve) -> None:
        self.points, self.curve = list(points), curve
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        p.fillRect(self.rect(), pal.base())
        fg = pal.text().color()
        pts = [q for q in self.points if q.efficiency > 0 and q.energy > 0]
        if not pts:
            p.setPen(fg)
            p.drawText(self.rect(), Qt.AlignCenter, qtr("eff_plot_title"))
            return
        es = [q.energy for q in pts]
        ys = [q.efficiency for q in pts]
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
        p.drawText(QRectF(L, 0, main.width(), T), Qt.AlignLeft | Qt.AlignVCenter, qtr("eff_plot_title") + "  [keV]")
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
        # residuals
        if self.curve is not None and self.curve.params:
            rr = []
            for q in pts:
                f = float(self.curve.efficiency(q.energy))
                rr.append((q, 100 * (q.efficiency - f) / f, 100 * q.unc / f))
            lim = max([abs(r) + u for _, r, u in rr] + [2.0]) * 1.15

            def RY(v):
                return res.center().y() - v / lim * res.height() / 2

            p.setPen(QPen(fg, 1, Qt.DashLine))
            p.drawLine(QPointF(res.left(), RY(0)), QPointF(res.right(), RY(0)))
            p.setPen(fg)
            p.drawText(QRectF(0, res.top(), L - 4, 14), Qt.AlignRight, f"+{lim:.0f}%")
            p.drawText(QRectF(0, res.bottom() - 14, L - 4, 14), Qt.AlignRight, f"-{lim:.0f}%")
            for q, r, u in rr:
                col = QColor(200, 60, 40) if q.use else QColor(150, 150, 150)
                p.setPen(QPen(col, 1.5))
                p.setBrush(col)
                xx = X(q.energy)
                p.drawLine(QPointF(xx, RY(r + u)), QPointF(xx, RY(r - u)))
                p.drawEllipse(QPointF(xx, RY(r)), 3, 3)
        p.end()


def describe_curve(c) -> str:
    """Translated one-line model description (``EfficiencyCurve.describe`` is English, for files/CLI)."""
    if c.model == "two_branch":
        return qtr("eff_desc_two", ec=c.e_ref, o1=c.order, o2=c.order_high)
    return qtr("eff_desc_loglog", o=c.order)


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
        self.setWindowTitle(qtr("eff_title"))
        self.resize(1100, 760)
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

        cert = QGroupBox(qtr("eff_cert_group"))
        cl = QVBoxLayout(cert)
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
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        cl.addLayout(row)
        self.cert_table = QTableWidget(0, len(CERT_COLS))
        self.cert_table.setHorizontalHeaderLabels([qtr(k) for k in CERT_COLS])
        self.cert_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.cert_table.horizontalHeader().setStretchLastSection(True)
        self.cert_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        cl.addWidget(self.cert_table)
        lay.addWidget(cert, 2)

        form = QHBoxLayout()
        form.addWidget(QLabel(qtr("eff_model")))
        self.model_combo = QComboBox()
        self.model_combo.addItem(qtr("eff_model_two"), "two_branch")
        self.model_combo.addItem(qtr("eff_model_loglog"), "loglog")
        self.model_combo.currentIndexChanged.connect(self._model_changed)
        form.addWidget(self.model_combo)
        form.addWidget(QLabel(qtr("eff_order")))
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
        self.btn_measure = QPushButton(qtr("eff_measure"))
        self.btn_measure.clicked.connect(self.measure_and_fit)
        form.addWidget(self.btn_measure)
        lay.addLayout(form)
        # geometry / detector get a row of their own: squeezed next to the fit options they were
        # clipped to a few characters
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

        split = QSplitter(Qt.Horizontal)
        pbox = QGroupBox(qtr("eff_points_group"))
        pl = QVBoxLayout(pbox)
        self.pt_table = QTableWidget(0, len(PT_COLS))
        self.pt_table.setHorizontalHeaderLabels([qtr(k) for k in PT_COLS])
        self.pt_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.pt_table.horizontalHeader().setStretchLastSection(True)
        pl.addWidget(self.pt_table)
        row = QHBoxLayout()
        b = QPushButton(qtr("eff_add_point"))
        b.clicked.connect(self.add_manual_point)
        row.addWidget(b)
        b = QPushButton(qtr("eff_refit"))
        b.clicked.connect(self.refit)
        row.addWidget(b)
        row.addStretch(1)
        pl.addLayout(row)
        split.addWidget(pbox)
        self.plot = EfficiencyPlot()
        split.addWidget(self.plot)
        split.setSizes([560, 480])
        lay.addWidget(split, 3)

        self.summary = QLabel("")
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.summary)
        row = QHBoxLayout()
        for key, slot in (("eff_save", self.save_curve), ("eff_load", self.load_curve_dialog)):
            b = QPushButton(qtr(key))
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        b = QPushButton(qtr("eff_close"))
        b.clicked.connect(self.accept)
        row.addWidget(b)
        lay.addLayout(row)
        if spectrum is not None:
            self.set_standard(spectrum)
        self._model_changed()

    # ------------------------------------------------------------------ helpers
    def _msg(self, text: str, error: bool = True) -> None:
        (QMessageBox.warning if error else QMessageBox.information)(self, qtr("eff_title"), text)

    def _model_changed(self, *_):
        two = self.model_combo.currentData() == "two_branch"
        for w in (self.lbl_high, self.order_high_spin, self.lbl_cross, self.cross_auto):
            w.setVisible(two)
        self.cross_spin.setVisible(two)

    def _folder(self, name: str) -> str:
        return self.settings.folder(name) if self.settings is not None else ""

    # ------------------------------------------------------------------ standard
    def browse_standard(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, qtr("eff_standard"), self._folder("open"))
        if path:
            self.load_standard(path)

    def load_standard(self, path) -> bool:
        from ..convert import read_spectra
        try:
            spectra, _fmt = read_spectra(Path(path))
        except Exception as exc:
            self._msg(qtr("eff_failed", msg=str(exc)))
            return False
        s = spectra[0]
        s.source_path = s.source_path or str(path)
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
        self.btn_aptec.setEnabled(bool(self._aptec_records()))

    def _aptec_records(self):
        p = self.spectrum.source_path if self.spectrum is not None else ""
        if p and Path(p).suffix.lower() == ".s0" and Path(p).is_file():
            try:
                return eff.aptec_source_records(p)
            except Exception:
                return []
        return []

    # ------------------------------------------------------------------ certificate
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

    # ------------------------------------------------------------------ measure / fit
    def measure_and_fit(self) -> bool:
        if self.spectrum is None:
            self._msg(qtr("eff_no_spectrum"))
            return False
        cert = self.certificate()
        if not cert:
            self._msg(qtr("eff_no_cert"))
            return False
        try:
            lines = eff.certificate_lines(cert)
            self.points = eff.measure_efficiency(self.spectrum, lines)
        except Exception as exc:
            self._msg(qtr("eff_failed", msg=str(exc)))
            return False
        self._fill_points()
        return self.refit()

    def _fill_points(self) -> None:
        t = self.pt_table
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
            for k, v in enumerate(vals, start=1):
                it = QTableWidgetItem(v)
                if not (p.manual and k in (2, 4, 5)):
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                t.setItem(r, k, it)
        t.blockSignals(False)

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

    def add_manual_point(self, energy: float = 0.0, efficiency: float = 0.0, unc_pct: float = 2.0) -> None:
        self._read_points()
        p = eff.manual_point(energy or 100.0, efficiency or 0.01, unc_pct)
        p.use = bool(energy and efficiency)
        self.points.append(p)
        self._fill_points()

    def refit(self) -> bool:
        self._read_points()
        model = self.model_combo.currentData()
        cross = "auto" if self.cross_auto.isChecked() else self.cross_spin.value()
        try:
            src = self.spectrum.source_path if self.spectrum is not None else ""
            date = self.spectrum.start_time.strftime("%Y-%m-%d %H:%M") if (
                self.spectrum is not None and self.spectrum.start_time) else ""
            self.curve = eff.fit_efficiency(self.points, model, order=self.order_spin.value(),
                                            crossover=cross, order_high=self.order_high_spin.value(),
                                            geometry=self.geom_edit.text(), detector=self.det_edit.text(),
                                            source=src, date=date)
        except Exception as exc:
            self.curve = None
            self.plot.set_data(self.points, None)
            self._msg(qtr("eff_failed", msg=str(exc)))
            return False
        if model == "two_branch":
            self.cross_spin.setValue(self.curve.e_ref)
        self._show_fit()
        return True

    def _show_fit(self) -> None:
        c = self.curve
        t = self.pt_table
        t.blockSignals(True)
        for r, p in enumerate(self.points):
            if r < t.rowCount() and c is not None:
                f = float(c.efficiency(p.energy))
                for k, v in ((6, f"{f:.5g}"), (7, i18n.ltr(f"{100 * (p.efficiency - f) / f:+.2f}"))):
                    it = QTableWidgetItem(v)
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    t.setItem(r, k, it)
        t.blockSignals(False)
        self.plot.set_data(self.points, c)
        if c is not None:
            self.summary.setText(qtr("eff_summary", model=describe_curve(c), chi2=c.reduced_chi2,
                                     n=sum(1 for p in self.points if p.use),
                                     e661=float(c.efficiency(661.66)), u661=100 * float(c.rel_uncertainty(661.66))))

    # ------------------------------------------------------------------ persistence
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
        self.curve.name = self.curve.name or Path(path).stem
        self.saved_path = self.curve.save(path)
        return self.saved_path

    def load_curve_dialog(self, path: Optional[str] = None) -> bool:
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, qtr("eff_load"), str(eff.default_curve_dir()), "JSON (*.json)")
        if not path:
            return False
        try:
            c = eff.load_curve(path)
        except Exception as exc:
            self._msg(qtr("eff_failed", msg=str(exc)))
            return False
        self.curve = c
        self.points = list(c.points)
        self.model_combo.setCurrentIndex(max(0, self.model_combo.findData(c.model)))
        self.order_spin.setValue(c.order)
        self.order_high_spin.setValue(c.order_high)
        if c.model == "two_branch":
            self.cross_spin.setValue(c.e_ref)
        self.geom_edit.setText(c.geometry)
        self.det_edit.setText(c.detector)
        self._fill_points()
        self._show_fit()
        return True

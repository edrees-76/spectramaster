"""Aptec-style calibration windows (Setup menu).

The layout and the order of the steps follow Aptec PCMCA/WIN 6.31, which many laboratories
know by heart:

* **Setup > Quick Energy Calibration... (F2)** -- :class:`QuickEnergyDialog`: up to 16
  channel-energy points, Encal Units, Max Degree, Encal Time; buttons Calib, Clear, OK, Cancel.
  A Channel cell takes the channel of the marker (click the spectrum) or the centroid of the ROI
  that contains it.
* **Full Energy / Resolution / Efficiency Calibration... (Shift+F2 = efficiency)** --
  :class:`FullCalibrationWindow`, the S_CALIB window: menus File, Calibration (Energy F5,
  Resolution F6, Efficiency F7, Calculate Efficiency F8, Delete F9), EditPoints, Method, View,
  Help; the calibration report and a graph of the points and the equation.

The calculations are :mod:`spectramaster.analysis.aptec_calibration` (Aptec's own fit rules,
checked against equations Aptec stored in its files); this module only collects the points and
shows the results.  Nothing is written to a file: *Save Spectrum* puts the calibration on the
displayed spectrum (File > Save As in the main window writes it), and the efficiency calibration
is also saved to the efficiency library so that Quantify can use it.
"""
from __future__ import annotations

import copy
import math
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PySide6.QtCore import QDateTime, QLocale, QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QFontDatabase, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateTimeEdit, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QMenuBar, QMessageBox, QPlainTextEdit, QPushButton, QSlider, QSpinBox,
                               QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..analysis import aptec_calibration as ac
from ..tools import calibrate as cal_tools
from . import i18n
from .aptec_cal_strings import atr
from .i18n import ltr

ENERGY, RESOLUTION, EFFICIENCY = "energy", "resolution", "efficiency"
KIND_KEYS = {ENERGY: "act_energy", RESOLUTION: "act_resolution", EFFICIENCY: "act_efficiency"}


def _num(text) -> Optional[float]:
    try:
        return float(str(text).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _mono() -> QFont:
    f = QFont("Consolas")
    f.setStyleHint(QFont.Monospace)
    f.setFixedPitch(True)
    f.setPointSize(10)
    if not QFontDatabase.hasFamily("Consolas"):
        f = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        f.setPointSize(max(f.pointSize(), 9))
    return f


def equation_text(coeffs) -> str:
    if not coeffs:
        return atr("none")
    sup = {2: "²", 3: "³", 4: "⁴", 5: "⁵"}
    terms = []
    for k, c in enumerate(coeffs):
        t = f"{c:.9g}"
        if k == 1:
            t += "·ch"
        elif k > 1:
            t += "·ch" + sup.get(k, f"^{k}")
        terms.append(t)
    return ltr(" + ".join(terms).replace("+ -", "− "))


def _date_edit(t: Optional[datetime] = None, popup: bool = True) -> QDateTimeEdit:
    """Date-time editor that always reads left to right with Latin digits (also in Arabic)."""
    w = QDateTimeEdit(_qdt(t))
    w.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
    w.setLayoutDirection(Qt.LeftToRight)
    w.setDisplayFormat("dd-MM-yyyy  HH:mm:ss")
    w.setCalendarPopup(popup)
    return w


def _qdt(t: Optional[datetime]) -> QDateTime:
    return QDateTime(t) if t else QDateTime.currentDateTime()


def _pydt(q: QDateTime) -> datetime:
    return q.toPython()


class _Messages:
    """Overridable message hooks (the tests replace them so no modal box blocks)."""

    def message(self, text: str) -> None:
        QMessageBox.warning(self, self.windowTitle(), text)

    def info(self, text: str) -> None:
        QMessageBox.information(self, self.windowTitle(), text)

    def confirm(self, text: str) -> bool:
        box = QMessageBox(QMessageBox.Question, self.windowTitle(), text, QMessageBox.Yes | QMessageBox.No, self)
        box.setDefaultButton(QMessageBox.No)
        return box.exec() == QMessageBox.Yes


def _rtl(w: QWidget) -> None:
    w.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)


def _peaks(win) -> list:
    panel = getattr(win, "analysis_panel", None)
    return list(getattr(panel, "peaks", []) or []) if panel is not None else []


def _current(win):
    try:
        return win.current_spectrum()
    except Exception:
        return None


def marker_channel(win) -> Optional[float]:
    """Channel for a calibration point: centroid of the ROI containing the marker, else the
    marker channel (Aptec: "the Channel column defaults to the Channel Marker or to the centroid
    of the current ROI")."""
    plot = getattr(win, "plot", None)
    if plot is None or plot.marker is None:
        return None
    k = plot.marker_roi()
    if k >= 0:
        st = plot.rois[k].stats
        if st is not None and st.centroid is not None:
            return round(float(st.centroid), 2)
    return plot.marker_channel()


def apply_to_display(win, spectrum) -> bool:
    from .calibration_dialog import replace_displayed_spectrum
    plot = getattr(win, "plot", None)
    marker = plot.marker if plot is not None else None
    ok = replace_displayed_spectrum(win, spectrum)
    if ok and plot is not None and marker is not None:
        plot.set_marker(marker)
    return ok


# ===================================================================== quick energy calibration
class QuickEnergyDialog(_Messages, QDialog):
    """Aptec *Energy Calibration* dialog (Header > Energy Cal / Setup > Quick Energy Cal, F2)."""

    def __init__(self, parent=None, spectrum=None, main_window=None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(atr("quick_title"))
        self.spectrum = spectrum
        self.main_window = main_window
        self.calibration: Optional[ac.PolyCalibration] = None
        self.cleared = False
        self.result_spectrum = None
        self._filling = False
        lay = QVBoxLayout(self)
        hint = QLabel(atr("quick_hint"))
        hint.setWordWrap(True)
        lay.addWidget(hint)
        box = QGroupBox(atr("points_group"))
        bl = QVBoxLayout(box)
        self.table = QTableWidget(ac.MAX_QUICK_POINTS, 4)
        self.table.setLayoutDirection(Qt.LeftToRight)
        self.table.setHorizontalHeaderLabels([atr("col_channel"), atr("col_energy"), atr("col_calc"),
                                              atr("col_dev")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.currentCellChanged.connect(self._cell_entered)
        bl.addWidget(self.table)
        b = QPushButton(atr("btn_marker"))
        b.setToolTip(atr("tip_marker"))
        b.clicked.connect(lambda: self.channel_from_marker(self.table.currentRow()))
        bl.addWidget(b)
        lay.addWidget(box, 1)
        form = QFormLayout()
        self.units = QLineEdit("keV")
        self.units.setMaxLength(6)
        form.addRow(atr("units"), self.units)
        self.degree = QSpinBox()
        self.degree.setRange(1, ac.MAX_DEGREE)
        form.addRow(atr("max_degree"), self.degree)
        self.time_label = QLabel(atr("none"))
        form.addRow(atr("encal_time"), self.time_label)
        self.eq_label = QLabel(atr("none"))
        self.eq_label.setWordWrap(True)
        self.eq_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow(atr("equation"), self.eq_label)
        lay.addLayout(form)
        row = QHBoxLayout()
        for key, fn in (("btn_calib", self.calib), ("btn_clear", self.clear)):
            b = QPushButton(atr(key))
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        self.btn_ok = QPushButton(atr("btn_ok"))
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.ok)
        row.addWidget(self.btn_ok)
        b = QPushButton(atr("btn_cancel"))
        b.clicked.connect(self.reject)
        row.addWidget(b)
        lay.addLayout(row)
        self.resize(560, 640)
        self._load_initial()

    # ------------------------------------------------------------ data
    def _load_initial(self) -> None:
        spec = self.spectrum
        coeffs = list(spec.energy_coeffs) if spec is not None else []
        self.degree.setValue(min(max(len(coeffs) - 1, 1), ac.MAX_DEGREE) if coeffs else ac.DEFAULT_DEGREE)
        pts = []
        stored = _aptec_sections(spec)
        if stored and stored.get(ENERGY) is not None:
            c = stored[ENERGY]
            pts = list(zip(c.channels, c.values))[:ac.MAX_QUICK_POINTS]
            self.units.setText(c.units or "keV")
            if c.time:
                self.time_label.setText(ltr(c.time.strftime("%d-%b-%Y %H:%M:%S")))
        self.set_points(pts)
        self.eq_label.setText(equation_text(coeffs))

    def set_points(self, pts) -> None:
        self._filling = True
        try:
            self.table.clearContents()
            for r, (ch, e) in enumerate(pts[:ac.MAX_QUICK_POINTS]):
                self.table.setItem(r, 0, QTableWidgetItem(f"{ch:.2f}"))
                self.table.setItem(r, 1, QTableWidgetItem(f"{e:g}"))
        finally:
            self._filling = False

    def points(self) -> list[tuple[float, float]]:
        out = []
        for r in range(self.table.rowCount()):
            a, b = self.table.item(r, 0), self.table.item(r, 1)
            ta, tb = (a.text().strip() if a else ""), (b.text().strip() if b else "")
            if not ta and not tb:
                continue
            ch, e = _num(ta), _num(tb)
            if ch is None or e is None:
                raise ValueError(atr("bad_number", row=r + 1, text=ta if ch is None else tb))
            out.append((ch, e))
        return out

    def _cell_entered(self, row: int, col: int, *_):
        if self._filling or col != 0 or row < 0:
            return
        it = self.table.item(row, 0)
        if it is None or not it.text().strip():
            self.channel_from_marker(row)

    def channel_from_marker(self, row: int) -> bool:
        ch = marker_channel(self.main_window) if self.main_window is not None else None
        if ch is None or row < 0:
            return False
        self._filling = True
        try:
            self.table.setItem(row, 0, QTableWidgetItem(f"{ch:.2f}"))
        finally:
            self._filling = False
        return True

    # ------------------------------------------------------------ buttons
    def calib(self) -> bool:
        """Recalculate the equation (Aptec *Calib*); updates the Encal Time."""
        try:
            pts = self.points()
            if not pts:
                self.message(atr("no_points"))
                return False
            c = ac.fit_polynomial([p[0] for p in pts], [p[1] for p in pts], self.degree.value(), "energy",
                                  self.units.text().strip() or "keV", datetime.now())
        except ValueError as exc:
            self.message(atr("fit_failed", msg=str(exc)))
            return False
        self.calibration = c
        self.cleared = False
        self.time_label.setText(ltr(c.time.strftime("%d-%b-%Y %H:%M:%S")))
        self.eq_label.setText(equation_text(c.coeffs))
        self._filling = True
        try:
            for r in range(self.table.rowCount()):
                for col in (2, 3):
                    self.table.setItem(r, col, None)
            r = 0
            for (ch, e), f in zip(pts, c.fitted):
                while r < self.table.rowCount() and not (self.table.item(r, 0) and self.table.item(r, 0).text().strip()):
                    r += 1
                for col, text in ((2, f"{f:.3f}"), (3, f"{e - f:+.3f}")):
                    it = QTableWidgetItem(text)
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(r, col, it)
                r += 1
        finally:
            self._filling = False
        return True

    def clear(self) -> None:
        """Clear the equation and all the points (Aptec *Clear*)."""
        self.set_points([])
        self.calibration = None
        self.cleared = True
        self.eq_label.setText(atr("none"))
        self.time_label.setText(atr("none"))

    def ok(self):
        """Recalculate and apply to the displayed spectrum (Aptec *OK*)."""
        if self.spectrum is None:
            self.reject()
            return None
        if self.cleared and not self._has_points():
            new = cal_tools.apply_calibration(self.spectrum, [], note="energy calibration cleared (quick energy calibration)")
            new.energy_coeffs = []
            msg = atr("cleared")
        else:
            if not self.calib():
                return None
            c = self.calibration
            note = (f"quick energy calibration: {len(c.channels)} points, max degree {c.max_degree}, "
                    f"degree {c.degree}, units {c.units}")
            new = cal_tools.apply_calibration(self.spectrum, c.coeffs, note=note)
            new.extra["energy_calibration_points"] = "; ".join(f"{a:.2f}:{b:g}" for a, b in
                                                               zip(c.channels, c.values))
            new.extra["energy_calibration_time"] = c.time.isoformat(timespec="seconds")
            msg = atr("applied", n=ltr(len(c.channels)), deg=ltr(c.degree))
        self.result_spectrum = new
        win = self.main_window
        if win is not None and apply_to_display(win, new):
            win.statusBar().showMessage(msg, 15000)
        self.accept()
        return new

    def _has_points(self) -> bool:
        try:
            return bool(self.points())
        except ValueError:
            return True


# ===================================================================== helpers for the full window
def _aptec_sections(spec) -> Optional[dict]:
    """Aptec calibration points of the displayed spectrum when it was read from an Aptec file."""
    if spec is None or not spec.source_path:
        return None
    p = Path(spec.source_path)
    if p.suffix.lower() not in (".s0", ".spc") or not p.is_file():
        return None
    try:
        return ac.read_aptec_calibrations(p)
    except Exception:
        return None


def _library_line(nuclide: str, energy: float):
    from ..analysis.library import load_library
    nd = load_library().get(nuclide)
    if nd is None:
        return None, None
    best = None
    for ln in nd.gammas(0.0):
        if best is None or abs(ln.energy - energy) < abs(best.energy - energy):
            best = ln
    y = best.intensity / 100.0 if best is not None and abs(best.energy - energy) < 2.0 else None
    return y, nd.half_life_s


class CalGraph(QWidget):
    """Points and equation of the current calibration (Aptec *Graph*)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.LeftToRight)      # axes always grow to the right
        self.setMinimumSize(320, 200)
        self.kind = ENERGY
        self.points: list[tuple[float, float, bool]] = []
        self.curve: Optional[Callable] = None
        self.log = False

    def set_data(self, kind: str, points, curve: Optional[Callable], log: bool = False) -> None:
        self.kind, self.points, self.curve, self.log = kind, list(points), curve, log
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setLayoutDirection(Qt.LeftToRight)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor("white"))
        r = QRectF(self.rect()).adjusted(66, 12, -14, -30)
        p.setPen(QPen(QColor("#b8c2cc"), 1))
        p.drawRect(r)
        pts = [(x, y, u) for x, y, u in self.points if x > 0 or not self.log]
        if not pts:
            return
        xs = np.array([q[0] for q in pts], dtype=float)
        ys = np.array([q[1] for q in pts], dtype=float)
        lo, hi = xs.min(), xs.max()
        if hi <= lo:
            lo, hi = lo - 1, hi + 1
        pad = (hi - lo) * 0.05 if not self.log else 0
        x0, x1 = (lo - pad, hi + pad) if not self.log else (lo / 1.15, hi * 1.15)
        grid = np.geomspace(x0, x1, 200) if self.log else np.linspace(x0, x1, 200)
        cy = None
        if self.curve is not None:
            try:
                cy = np.asarray(self.curve(grid), dtype=float)
            except Exception:
                cy = None
        allv = np.concatenate([ys, cy[np.isfinite(cy)] if cy is not None else np.zeros(0)])
        allv = allv[allv > 0] if self.log else allv
        if not len(allv):
            return
        y0, y1 = allv.min(), allv.max()
        if self.log:
            y0, y1 = y0 / 1.3, y1 * 1.3
        else:
            span = (y1 - y0) or abs(y1) or 1.0
            y0, y1 = y0 - 0.08 * span, y1 + 0.08 * span
        tx = (lambda v: math.log(v)) if self.log else (lambda v: v)

        def X(v):
            return r.left() + (tx(v) - tx(x0)) / (tx(x1) - tx(x0)) * r.width()

        def Y(v):
            return r.bottom() - (tx(v) - tx(y0)) / (tx(y1) - tx(y0)) * r.height()
        if cy is not None:
            p.setPen(QPen(QColor("#1565c0"), 1.6))
            last = None
            for gx, gy in zip(grid, cy):
                if not math.isfinite(gy) or (self.log and gy <= 0):
                    last = None
                    continue
                pt = QPointF(X(gx), Y(gy))
                if last is not None:
                    p.drawLine(last, pt)
                last = pt
        for x, y, use in pts:
            if self.log and y <= 0:
                continue
            p.setPen(QPen(QColor("#c62828") if use else QColor("#9e9e9e"), 1.5))
            p.setBrush(QColor("#c62828") if use else Qt.NoBrush)
            p.drawEllipse(QPointF(X(x), Y(y)), 3.5, 3.5)
        p.setPen(QColor("#3c4650"))
        p.drawText(QRectF(r.left(), r.bottom() + 4, r.width(), 20), Qt.AlignLeft, f"{x0:.4g}")
        p.drawText(QRectF(r.left(), r.bottom() + 4, r.width(), 20), Qt.AlignRight, f"{x1:.4g}")
        p.drawText(QRectF(2, r.top(), 60, 16), Qt.AlignRight, f"{y1:.4g}")
        p.drawText(QRectF(2, r.bottom() - 16, 60, 16), Qt.AlignRight, f"{y0:.4g}")


# ===================================================================== edit points: energy / resolution
class PointsDialog(_Messages, QDialog):
    """S_Calib *Edit Points* for energy (channel-energy) or resolution (channel-FWHM)."""

    def __init__(self, parent, kind: str, points, units: str, win=None, energy_coeffs=()):
        super().__init__(parent)
        _rtl(self)
        self.kind = kind
        self.win = win
        self.energy_coeffs = list(energy_coeffs or [])
        self.units = units or ("keV" if kind == ENERGY else "channels")
        self.setWindowTitle(atr("ep_energy_title" if kind == ENERGY else "ep_res_title"))
        lay = QVBoxLayout(self)
        cols = [atr("col_channel"), atr("col_energy")] if kind == ENERGY else \
            [atr("col_channel"), atr("col_fwhm"), atr("col_fwhm_kev")]
        self.table = QTableWidget(0, len(cols))
        self.table.setLayoutDirection(Qt.LeftToRight)
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        lay.addWidget(self.table, 1)
        self.status = QLabel("")
        lay.addWidget(self.status)
        row = QHBoxLayout()
        buttons = [("btn_load_rois", self.load_rois), ("btn_add", self.add_point),
                   ("btn_delete", self.delete_selected)]
        if kind == ENERGY:
            buttons.insert(0, ("btn_edit_id", self.edit_id))
        for key, fn in buttons:
            b = QPushButton(atr(key))
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        b = QPushButton(atr("btn_okfit"))
        b.setDefault(True)
        b.clicked.connect(self.ok_fit)
        row.addWidget(b)
        b = QPushButton(atr("btn_cancel"))
        b.clicked.connect(self.reject)
        row.addWidget(b)
        lay.addLayout(row)
        self.resize(520, 560)
        self.set_points(points)

    def set_points(self, pts) -> None:
        self.table.setRowCount(0)
        for ch, v in pts:
            self.add_point(ch, v)

    def add_point(self, ch: Optional[float] = None, value: Optional[float] = None) -> None:
        if isinstance(ch, bool):
            ch = None
        if self.table.rowCount() >= ac.MAX_POINTS:
            self.message(atr("too_many", n=ac.MAX_POINTS))
            return
        if ch is None and self.win is not None:
            ch = marker_channel(self.win)
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem("" if ch is None else f"{ch:.2f}"))
        self.table.setItem(r, 1, QTableWidgetItem("" if value is None else f"{value:g}"))
        if self.kind == RESOLUTION:
            it = QTableWidgetItem(self._kev_text(ch, value))
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 2, it)

    def _kev_text(self, ch, value) -> str:
        if ch is None or value is None or len(self.energy_coeffs) < 2:
            return ""
        slope = float(np.polynomial.polynomial.polyval(ch, np.polynomial.polynomial.polyder(self.energy_coeffs)))
        return f"[{value * slope:.3f}]"

    def delete_selected(self) -> None:
        for r in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(r)

    def points(self) -> list[tuple[float, float]]:
        out = []
        for r in range(self.table.rowCount()):
            a, b = self.table.item(r, 0), self.table.item(r, 1)
            ta, tb = (a.text().strip() if a else ""), (b.text().strip() if b else "")
            if not ta and not tb:
                continue
            ch, v = _num(ta), _num(tb)
            if ch is None or v is None:
                raise ValueError(atr("bad_number", row=r + 1, text=ta if ch is None else tb))
            out.append((ch, v))
        return out

    def edit_id(self) -> None:
        text, ok = QInputDialog.getText(self, atr("units_title"), atr("units_prompt"), text=self.units)
        if ok and text.strip():
            self.units = text.strip()[:6]

    def load_rois(self) -> int:
        """Energy: identified peaks (centroid, library energy).  Resolution: every peak (centroid,
        FWHM in channels); without analysis peaks the painted ROIs are used."""
        peaks = _peaks(self.win)
        pts = []
        if self.kind == ENERGY:
            pts = [(float(p.centroid), float(p.line_energy)) for p in peaks
                   if p.nuclide and p.line_energy is not None]
            if not pts:
                self.message(atr("need_analysis"))
                return 0
        else:
            pts = [(float(p.centroid), float(p.fwhm)) for p in peaks if p.fwhm and p.fwhm > 0]
            if not pts and self.win is not None:
                pts = [(float(r.stats.centroid), float(r.stats.fwhm)) for r in self.win.plot.rois
                       if r.stats is not None and r.stats.centroid is not None and r.stats.fwhm]
            if not pts:
                self.message(atr("need_peaks"))
                return 0
        pts = sorted(pts)[:ac.MAX_POINTS]
        self.set_points(pts)
        self.status.setText(atr("loaded_n", n=ltr(len(pts))))
        return len(pts)

    def ok_fit(self) -> None:
        try:
            pts = self.points()
        except ValueError as exc:
            self.message(str(exc))
            return
        if not pts:
            self.message(atr("no_points"))
            return
        self.result_points = pts
        self.accept()


# ===================================================================== edit points: efficiency
class IdDialog(QDialog):
    """S_Calib *Edit Efficiency Identification*: energy units, detector ID, geometry ID."""

    def __init__(self, parent, units: str, detector: str, geometry: str):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(atr("id_title"))
        form = QFormLayout(self)
        self.units = QLineEdit(units or "keV")
        self.detector = QLineEdit(detector)
        self.geometry = QLineEdit(geometry)
        for w in (self.units, self.detector, self.geometry):
            w.setMaxLength(15)
        form.addRow(atr("id_units"), self.units)
        form.addRow(atr("id_detector"), self.detector)
        form.addRow(atr("id_geometry"), self.geometry)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)


class DefaultsDialog(QDialog):
    """S_Calib *Edit Load ROI Defaults*: activity units and time, quantity."""

    def __init__(self, parent, units: str, time: Optional[datetime], quantity: float, quantity_err: float):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(atr("def_title"))
        form = QFormLayout(self)
        hint = QLabel(atr("def_hint"))
        hint.setWordWrap(True)
        form.addRow(hint)
        self.units = QComboBox()
        self.units.setEditable(True)
        self.units.addItems(list(ac.ACTIVITY_UNITS))
        self.units.setCurrentText(units or "Bq")
        form.addRow(atr("ef_act_units"), self.units)
        self.time = _date_edit(time)
        form.addRow(atr("ef_act_time"), self.time)
        self.quantity = QDoubleSpinBox()
        self.quantity.setDecimals(6)
        self.quantity.setRange(1e-9, 1e12)
        self.quantity.setValue(quantity or 1.0)
        self.quantity_err = QDoubleSpinBox()
        self.quantity_err.setRange(0, 100)
        self.quantity_err.setValue(quantity_err or 0.0)
        row = QHBoxLayout()
        row.addWidget(self.quantity, 2)
        row.addWidget(QLabel(atr("ef_err")))
        row.addWidget(self.quantity_err, 1)
        form.addRow(atr("ef_quantity"), row)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)


class EfficiencyPointsDialog(_Messages, QDialog):
    """S_Calib *Edit Energy-Efficiency*: one Aptec efficiency record per page (point slider)."""

    def __init__(self, parent, points, units: str, detector: str, geometry: str, win=None, spectrum=None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(atr("ef_title"))
        self.win = win
        self.spectrum = spectrum
        self.points = [copy.copy(p) for p in points]
        self.units, self.detector, self.geometry = units or "keV", detector, geometry
        self.defaults = {"units": "Bq", "time": None, "quantity": 1.0, "quantity_err": 0.0}
        if self.points:
            p0 = self.points[0]
            self.defaults.update(units=p0.activity_units, time=p0.activity_time, quantity=p0.quantity,
                                 quantity_err=p0.quantity_err)
        self._index = -1
        self._filling = False
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(atr("ef_point")))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.valueChanged.connect(self._goto)
        row.addWidget(self.slider, 1)
        self.pos_label = QLabel("")
        row.addWidget(self.pos_label)
        lay.addLayout(row)
        grid = QGridLayout()
        self.f: dict[str, QWidget] = {}

        def line(key, r, c=0, ro=False):
            w = QLineEdit()
            w.setLayoutDirection(Qt.LeftToRight)
            w.setReadOnly(ro)
            w.editingFinished.connect(self._store)
            grid.addWidget(QLabel(atr(key)), r, c)
            grid.addWidget(w, r, c + 1)
            self.f[key] = w
            return w
        line("ef_energy", 0)
        line("ef_eff", 0, 2)
        line("ef_isotope", 1)
        line("ef_yield", 1, 2)
        line("ef_activity", 2)
        self.act_err = QDoubleSpinBox()
        self.act_err.setRange(0, 100)
        self.act_err.setDecimals(3)
        self.act_err.editingFinished.connect(self._store)
        grid.addWidget(QLabel(atr("ef_err")), 2, 2)
        grid.addWidget(self.act_err, 2, 3)
        self.act_units = QComboBox()
        self.act_units.setEditable(True)
        self.act_units.addItems(list(ac.ACTIVITY_UNITS))
        self.act_units.currentTextChanged.connect(self._store)
        grid.addWidget(QLabel(atr("ef_act_units")), 3, 0)
        grid.addWidget(self.act_units, 3, 1)
        self.act_time = _date_edit()
        self.act_time.dateTimeChanged.connect(self._store)
        grid.addWidget(QLabel(atr("ef_act_time")), 3, 2)
        grid.addWidget(self.act_time, 3, 3)
        line("ef_rate", 4)
        self.rate_err = QDoubleSpinBox()
        self.rate_err.setRange(0, 1000)
        self.rate_err.setDecimals(3)
        self.rate_err.editingFinished.connect(self._store)
        grid.addWidget(QLabel(atr("ef_err")), 4, 2)
        grid.addWidget(self.rate_err, 4, 3)
        self.rate_time = _date_edit(popup=False)
        self.rate_time.dateTimeChanged.connect(self._store)
        grid.addWidget(QLabel(atr("ef_rate_time")), 5, 0)
        grid.addWidget(self.rate_time, 5, 1)
        line("ef_quantity", 5, 2)
        line("ef_halflife", 6)
        self.use = QCheckBox(atr("ef_use"))
        self.use.toggled.connect(self._store)
        grid.addWidget(self.use, 6, 2)
        self.manual = QCheckBox(atr("ef_manual"))
        self.manual.toggled.connect(self._store)
        grid.addWidget(self.manual, 7, 2)
        self.err_label = QLabel("")
        grid.addWidget(self.err_label, 7, 0, 1, 2)
        for w in (self.act_err, self.rate_err, self.act_time, self.rate_time, self.act_units):
            w.setLayoutDirection(Qt.LeftToRight)
        lay.addLayout(grid)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        for key, fn in (("btn_edit_id", self.edit_id), ("btn_load_rois", self.load_rois),
                        ("btn_add", self.add_point), ("btn_delete", self.delete_point),
                        ("btn_calculate", self.calculate)):
            b = QPushButton(atr(key))
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        b = QPushButton(atr("btn_okfit"))
        b.setDefault(True)
        b.clicked.connect(self.ok_fit)
        row.addWidget(b)
        b = QPushButton(atr("btn_cancel"))
        b.clicked.connect(self.reject)
        row.addWidget(b)
        lay.addLayout(row)
        self.resize(760, 420)
        self._refresh_slider(0)

    # ------------------------------------------------------------ navigation
    def _refresh_slider(self, index: int) -> None:
        n = len(self.points)
        self.slider.blockSignals(True)
        self.slider.setRange(1, max(n, 1))
        self.slider.setEnabled(n > 1)
        self.slider.blockSignals(False)
        self._index = -1
        if n:
            self.slider.setValue(min(index, n - 1) + 1)
            self._goto(self.slider.value())
        else:
            self._show_empty()

    def _show_empty(self) -> None:
        self.pos_label.setText(ltr("0 ") + atr("ef_of", n=ltr(0)))
        self.status.setText(atr("ef_no_points"))
        for w in self.f.values():
            w.setText("")

    def _goto(self, value: int) -> None:
        if not self.points:
            return
        self._store()
        self._index = value - 1
        p = self.points[self._index]
        self._filling = True
        try:
            self.pos_label.setText(ltr(f"{value} ") + atr("ef_of", n=ltr(len(self.points))))
            self.f["ef_energy"].setText(f"{p.energy:g}")
            self.f["ef_eff"].setText(f"{p.efficiency:.6g}" if p.efficiency else "")
            self.f["ef_eff"].setReadOnly(not p.manual)
            self.f["ef_isotope"].setText(p.isotope)
            self.f["ef_yield"].setText(f"{p.yield_:.6g}")
            self.f["ef_activity"].setText(f"{p.activity:g}" if p.activity else "")
            self.act_err.setValue(p.activity_err)
            self.act_units.setCurrentText(p.activity_units)
            self.act_time.setDateTime(_qdt(p.activity_time))
            self.f["ef_rate"].setText(f"{p.net_rate:.6g}")
            self.rate_err.setValue(p.net_rate_err)
            self.rate_time.setDateTime(_qdt(p.rate_time))
            self.f["ef_quantity"].setText(f"{p.quantity:g}")
            self.f["ef_halflife"].setText(_half_life_text(p.half_life_s))
            self.use.setChecked(p.use)
            self.manual.setChecked(p.manual)
            self.err_label.setText(ltr(f"± {p.efficiency_err:.2f} %") if p.efficiency else "")
        finally:
            self._filling = False

    def current(self) -> Optional[ac.EffPoint]:
        return self.points[self._index] if 0 <= self._index < len(self.points) else None

    def _store(self, *_):
        p = self.current()
        if p is None or self._filling:
            return
        f = self.f
        e = _num(f["ef_energy"].text())
        if e is not None:
            p.energy = e
        p.isotope = f["ef_isotope"].text().strip()
        y = _num(f["ef_yield"].text())
        if y is not None:
            p.yield_ = y
        a = _num(f["ef_activity"].text())
        old_activity = p.activity
        p.activity = a or 0.0
        p.activity_err = self.act_err.value()
        p.activity_units = self.act_units.currentText().strip() or "Bq"
        p.activity_time = _pydt(self.act_time.dateTime())
        r = _num(f["ef_rate"].text())
        if r is not None:
            p.net_rate = r
        p.net_rate_err = self.rate_err.value()
        p.rate_time = _pydt(self.rate_time.dateTime())
        q = _num(f["ef_quantity"].text())
        if q:
            p.quantity = q
        hl = _parse_half_life(f["ef_halflife"].text())
        if hl is not None:
            p.half_life_s = hl
        p.use = self.use.isChecked()
        p.manual = self.manual.isChecked()
        self.f["ef_eff"].setReadOnly(not p.manual)
        if p.manual:
            v = _num(f["ef_eff"].text())
            if v is not None:
                p.efficiency = v
        # the other lines of the same isotope without an activity get the one just typed
        if p.activity and p.activity != old_activity and p.isotope:
            for o in self.points:
                if o is not p and o.isotope == p.isotope and not o.activity:
                    o.activity, o.activity_err = p.activity, p.activity_err

    # ------------------------------------------------------------ buttons
    def edit_id(self) -> bool:
        d = IdDialog(self, self.units, self.detector, self.geometry)
        if d.exec() != QDialog.Accepted:
            return False
        self.units = d.units.text().strip() or "keV"
        self.detector, self.geometry = d.detector.text().strip(), d.geometry.text().strip()
        return True

    def load_rois(self, defaults: Optional[dict] = None) -> int:
        """Identified peaks -> points (energy, isotope, yield, half-life from the library; net
        rate from the peak); the defaults (activity units / time, quantity) are asked first."""
        if isinstance(defaults, bool):
            defaults = None
        peaks = [p for p in _peaks(self.win) if p.nuclide and p.line_energy is not None]
        if not peaks:
            self.message(atr("need_analysis"))
            return 0
        if defaults is None:
            d = DefaultsDialog(self, self.defaults["units"], self.defaults["time"], self.defaults["quantity"],
                               self.defaults["quantity_err"])
            if d.exec() != QDialog.Accepted:
                return 0
            defaults = {"units": d.units.currentText().strip(), "time": _pydt(d.time.dateTime()),
                        "quantity": d.quantity.value(), "quantity_err": d.quantity_err.value()}
        self.defaults.update(defaults)
        spec = self.spectrum
        live = spec.live_time if spec is not None else None
        t0 = spec.start_time if spec is not None else None
        old = {(p.isotope, round(p.energy, 1)): p for p in self.points}
        pts = []
        for pk in sorted(peaks, key=lambda q: q.line_energy):
            y, hl = _library_line(pk.nuclide, pk.line_energy)
            rate = pk.count_rate if pk.count_rate is not None else (pk.net_area / live if live else 0.0)
            rerr = 100.0 * pk.net_area_unc / pk.net_area if pk.net_area > 0 else 0.0
            prev = old.get((pk.nuclide, round(float(pk.line_energy), 1)))
            pts.append(ac.EffPoint(energy=float(pk.line_energy), isotope=pk.nuclide, yield_=y or 0.0,
                                   half_life_s=hl, activity=prev.activity if prev else 0.0,
                                   activity_err=prev.activity_err if prev else 0.0,
                                   activity_units=self.defaults["units"] or "Bq",
                                   activity_time=self.defaults["time"], net_rate=float(rate or 0.0),
                                   net_rate_err=rerr, rate_time=t0, quantity=self.defaults["quantity"] or 1.0,
                                   quantity_err=self.defaults["quantity_err"] or 0.0))
        self.points = pts[:ac.MAX_POINTS]
        self._refresh_slider(0)
        self.status.setText(atr("loaded_n", n=ltr(len(self.points))))
        return len(self.points)

    def add_point(self) -> None:
        self._store()
        if len(self.points) >= ac.MAX_POINTS:
            self.message(atr("too_many", n=ac.MAX_POINTS))
            return
        spec = self.spectrum
        self.points.append(ac.EffPoint(energy=100.0, manual=True, activity_units=self.defaults["units"] or "Bq",
                                       activity_time=self.defaults["time"],
                                       rate_time=spec.start_time if spec is not None else None))
        self._refresh_slider(len(self.points) - 1)

    def delete_point(self) -> None:
        if 0 <= self._index < len(self.points):
            i = self._index
            del self.points[i]
            self._refresh_slider(max(i - 1, 0))

    def calculate(self) -> bool:
        """Calculate every point (Aptec *Calculate*); shows the current point's result."""
        self._store()
        for n, p in enumerate(self.points, start=1):
            if p.manual or not p.use:
                continue
            if not p.activity:
                self.message(atr("ef_missing_activity", n=n, iso=p.isotope, e=ltr(f"{p.energy:g}")))
                self.slider.setValue(n)
                return False
            try:
                p.calculate()
            except ValueError as exc:
                self.message(atr("ef_calc_failed", n=n, msg=str(exc)))
                self.slider.setValue(n)
                return False
        cur = self.current()
        if cur is not None:
            self._goto(self._index + 1)
            self.status.setText(atr("ef_calc_result", eff=ltr(f"{cur.efficiency:.6g}"),
                                    err=ltr(f"{cur.efficiency_err:.2f}")).replace("\n\n", " - ").replace("\n", "  "))
        return True

    def ok_fit(self) -> None:
        if not self.calculate():
            return
        if not self.detector or not self.geometry:
            self.message(atr("id_required"))
            if not self.edit_id() or not self.detector or not self.geometry:
                return
        self.accept()


def _half_life_text(s: Optional[float]) -> str:
    if not s:
        return ""
    y = s / (365.2422 * 86400)
    if y >= 1:
        return f"{y:.5g} y"
    d = s / 86400
    return f"{d:.5g} d" if d >= 1 else f"{s / 3600:.5g} h"


def _parse_half_life(text: str) -> Optional[float]:
    t = (text or "").strip().lower()
    if not t:
        return None
    units = {"y": 365.2422 * 86400, "d": 86400.0, "h": 3600.0, "m": 60.0, "s": 1.0}
    unit = t[-1] if t[-1] in units else "s"
    v = _num(t.rstrip("ydhms").strip())
    return v * units[unit] if v is not None else None


class CalcEfficiencyDialog(QDialog):
    """S_Calib *Calculate Efficiency* (F8): efficiency of the equation at a given energy."""

    def __init__(self, parent, cal: Optional[ac.EffCalibration]):
        super().__init__(parent)
        _rtl(self)
        self.cal = cal
        self.setWindowTitle(atr("calc_title"))
        form = QFormLayout(self)
        self.energy = QDoubleSpinBox()
        self.energy.setRange(1.0, 20000.0)
        self.energy.setDecimals(3)
        self.energy.setValue(661.657)
        self.energy.valueChanged.connect(self.update_result)
        form.addRow(atr("calc_energy"), self.energy)
        self.result = QLabel("")
        self.result.setWordWrap(True)
        self.result.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow(self.result)
        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.accepted.connect(self.accept)
        form.addRow(bb)
        self.update_result()

    def update_result(self, *_):
        if self.cal is None:
            self.result.setText(atr("calc_none"))
            return
        e = self.energy.value()
        v, err, inside = ac.calculate_efficiency(self.cal, e)
        text = atr("calc_result", eff=ltr(f"{v:.6g}" if math.isfinite(v) else "-"),
                   err=ltr(f"{err:.2f}" if math.isfinite(err) else "-"))
        if not inside:
            lo, hi = self.cal.energy_range
            text += "\n" + atr("calc_outside", lo=ltr(f"{lo:.1f}"), hi=ltr(f"{hi:.1f}"))
        self.result.setText(text)


# ===================================================================== full calibration window (S_Calib)
class FullCalibrationWindow(_Messages, QDialog):
    """The S_CALIB window: one spectrum, three calibrations, report and graph."""

    def __init__(self, parent=None, spectrum=None, main_window=None, kind: str = ENERGY):
        super().__init__(parent)
        _rtl(self)
        self.spectrum = spectrum
        self.main_window = main_window
        self.kind = kind
        self.dirty = False
        self.result_spectrum = None
        self.saved_curve_path: Optional[Path] = None
        self.energy: Optional[ac.PolyCalibration] = None
        self.resolution: Optional[ac.PolyCalibration] = None
        self.efficiency: Optional[ac.EffCalibration] = None
        self.eff_points: list[ac.EffPoint] = []
        self.eff_ids = {"units": "keV", "detector": (spectrum.detector if spectrum is not None else "") or "",
                        "geometry": ""}
        self.degree = {ENERGY: ac.DEFAULT_DEGREE, RESOLUTION: ac.DEFAULT_DEGREE}
        self.eff_type = "A"
        self._load_from_spectrum()
        name = ""
        if spectrum is not None:
            name = Path(spectrum.source_path).name if spectrum.source_path else spectrum.sample_id
        self.setWindowTitle(atr("full_title", name=name or "-"))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 4)
        self.menubar = QMenuBar(self)
        lay.setMenuBar(self.menubar)
        self._build_menus()
        self.kind_label = QLabel("")
        f = self.kind_label.font()
        f.setBold(True)
        self.kind_label.setFont(f)
        lay.addWidget(self.kind_label)
        split = QSplitter(Qt.Vertical)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setLayoutDirection(Qt.LeftToRight)
        self.report.setFont(_mono())
        self.report.setLineWrapMode(QPlainTextEdit.NoWrap)
        split.addWidget(self.report)
        self.graph = CalGraph()
        split.addWidget(self.graph)
        split.setSizes([360, 260])
        lay.addWidget(split, 1)
        self.resize(860, 720)
        self.set_kind(kind)

    # ------------------------------------------------------------ state
    def _load_from_spectrum(self) -> None:
        spec = self.spectrum
        st = _aptec_sections(spec)
        if st:
            self.energy, self.resolution = st.get(ENERGY), st.get(RESOLUTION)
            if self.energy is not None:
                self.degree[ENERGY] = self.energy.max_degree
            if self.resolution is not None:
                self.degree[RESOLUTION] = self.resolution.max_degree
            e = st.get(EFFICIENCY)
            if e is not None:
                self.efficiency = e
                self.eff_points = list(e.points)
                self.eff_type = e.eff_type
                self.eff_ids = {"units": e.units, "detector": e.detector_id, "geometry": e.geometry_id}

    def _build_menus(self) -> None:
        mb = self.menubar
        m = mb.addMenu(atr("menu_file"))
        self.act_save = self._act(m, "act_save_spc", self.save_spectrum, "Shift+F12")
        self._act(m, "act_save_spc_as", self.save_spectrum_as, "F12")
        m.addSeparator()
        self._act(m, "act_print", self.print_report, "Ctrl+Shift+F12")
        self._act(m, "act_save_report", self.save_report)
        m.addSeparator()
        self._act(m, "act_load_file", self.load_aptec_file)
        m.addSeparator()
        self._act(m, "act_exit", self.reject, "Alt+F4")
        m = mb.addMenu(atr("menu_calibration"))
        self.kind_group = QActionGroup(self)
        self.kind_actions = {}
        for kind, key, sc in ((ENERGY, "act_energy", "F5"), (RESOLUTION, "act_resolution", "F6"),
                              (EFFICIENCY, "act_efficiency", "F7")):
            a = self._act(m, key, lambda _=False, k=kind: self.set_kind(k), sc)
            a.setCheckable(True)
            self.kind_group.addAction(a)
            self.kind_actions[kind] = a
        m.addSeparator()
        self._act(m, "act_calc_eff", self.calculate_efficiency, "F8")
        self._act(m, "act_delete", self.delete_current, "F9")
        m = mb.addMenu(atr("menu_editpoints"))
        for kind, key in ((ENERGY, "act_energy"), (RESOLUTION, "act_resolution"), (EFFICIENCY, "act_efficiency")):
            self._act(m, key, lambda _=False, k=kind: self.edit_points(k))
        m = mb.addMenu(atr("menu_method"))
        self.degree_actions = {}
        for kind, key in ((ENERGY, "method_energy"), (RESOLUTION, "method_resolution")):
            sub = m.addMenu(atr(key))
            g = QActionGroup(self)
            for n in range(1, ac.MAX_DEGREE + 1):
                a = sub.addAction(atr("degree_default" if n == ac.DEFAULT_DEGREE else "degree_n", n=n))
                a.setCheckable(True)
                a.setChecked(n == self.degree[kind])
                a.triggered.connect(lambda _=False, k=kind, d=n: self.set_degree(k, d))
                g.addAction(a)
                self.degree_actions[(kind, n)] = a
        sub = m.addMenu(atr("method_efficiency"))
        g = QActionGroup(self)
        self.type_actions = {}
        for t in "ABCDS":
            a = sub.addAction(atr("type_" + t))
            a.setCheckable(True)
            a.setChecked(t == self.eff_type)
            a.triggered.connect(lambda _=False, tt=t: self.set_eff_type(tt))
            g.addAction(a)
            self.type_actions[t] = a
        m = mb.addMenu(atr("menu_help"))
        self._act(m, "act_help", lambda: self.info(atr("help_text")), "F1")

    def _act(self, menu, key: str, fn, shortcut: str = "") -> QAction:
        a = menu.addAction(atr(key))
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
            a.setShortcutContext(Qt.WindowShortcut)
        a.triggered.connect(lambda _=False: fn())
        return a

    # ------------------------------------------------------------ commands
    def set_kind(self, kind: str) -> None:
        self.kind = kind
        if kind in self.kind_actions:
            self.kind_actions[kind].setChecked(True)
        self.refresh()

    def set_degree(self, kind: str, degree: int) -> None:
        self.degree[kind] = degree
        cal = self.energy if kind == ENERGY else self.resolution
        if cal is not None:
            self._fit_poly(kind, list(zip(cal.channels, cal.values)), cal.units)
        if (kind, degree) in self.degree_actions:
            self.degree_actions[(kind, degree)].setChecked(True)
        self.set_kind(kind)

    def set_eff_type(self, t: str) -> None:
        self.eff_type = t
        if t in self.type_actions:
            self.type_actions[t].setChecked(True)
        if self.eff_points:
            self._fit_eff()
        self.set_kind(EFFICIENCY)

    def _fit_poly(self, kind: str, pts, units: str) -> bool:
        try:
            c = ac.fit_polynomial([p[0] for p in pts], [p[1] for p in pts], self.degree[kind],
                                  kind, units, datetime.now())
        except ValueError as exc:
            self.message(atr("fit_failed", msg=str(exc)))
            return False
        if kind == ENERGY:
            self.energy = c
        else:
            self.resolution = c
        self.dirty = True
        return True

    def _fit_eff(self) -> bool:
        try:
            self.efficiency = ac.fit_efficiency(self.eff_points, self.eff_type, self.eff_ids["units"],
                                                self.eff_ids["detector"], self.eff_ids["geometry"], datetime.now())
        except ValueError as exc:
            self.efficiency = None
            self.message(atr("fit_failed", msg=str(exc)))
            return False
        self.dirty = True
        return True

    def edit_points(self, kind: str, dialog_hook: Optional[Callable] = None) -> bool:
        """EditPoints > Energy / Resolution / Efficiency; OK-Fit refits.  `dialog_hook(dlg)`
        replaces ``exec`` (tests)."""
        self.set_kind(kind)
        run = dialog_hook or (lambda d: d.exec() == QDialog.Accepted)
        if kind == EFFICIENCY:
            d = EfficiencyPointsDialog(self, self.eff_points, self.eff_ids["units"], self.eff_ids["detector"],
                                       self.eff_ids["geometry"], self.main_window, self.spectrum)
            if not run(d):
                return False
            self.eff_points = d.points
            self.eff_ids = {"units": d.units, "detector": d.detector, "geometry": d.geometry}
            ok = self._fit_eff()
        else:
            cal = self.energy if kind == ENERGY else self.resolution
            pts = list(zip(cal.channels, cal.values)) if cal is not None else []
            units = cal.units if cal is not None else ("keV" if kind == ENERGY else "channels")
            ecoef = self.energy.coeffs if self.energy is not None else (
                self.spectrum.energy_coeffs if self.spectrum is not None else [])
            d = PointsDialog(self, kind, pts, units, self.main_window, ecoef)
            if not run(d):
                return False
            ok = self._fit_poly(kind, d.result_points, d.units)
        self.refresh()
        return ok

    def delete_current(self, confirmed: Optional[bool] = None) -> bool:
        what = atr(KIND_KEYS[self.kind])
        if confirmed is None:
            confirmed = self.confirm(atr("delete_confirm", what=what))
        if not confirmed:
            return False
        if self.kind == ENERGY:
            self.energy = None
        elif self.kind == RESOLUTION:
            self.resolution = None
        else:
            self.efficiency, self.eff_points = None, []
        self.dirty = True
        self._deleted = getattr(self, "_deleted", set()) | {self.kind}
        self.refresh()
        return True

    def calculate_efficiency(self) -> None:
        CalcEfficiencyDialog(self, self.efficiency).exec()

    def load_aptec_file(self, path: Optional[str] = None) -> bool:
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, atr("act_load_file"), "", "Aptec (*.s0 *.S0);;* (*)")
        if not path:
            return False
        try:
            st = ac.read_aptec_calibrations(path)
        except Exception as exc:
            self.message(atr("fit_failed", msg=str(exc)))
            return False
        if st.get(ENERGY) is not None:
            self.energy = st[ENERGY]
        if st.get(RESOLUTION) is not None:
            self.resolution = st[RESOLUTION]
        if st.get(EFFICIENCY) is not None:
            e = st[EFFICIENCY]
            self.efficiency, self.eff_points, self.eff_type = e, list(e.points), e.eff_type
            self.eff_ids = {"units": e.units, "detector": e.detector_id, "geometry": e.geometry_id}
        self.dirty = True
        self.refresh()
        return True

    # ------------------------------------------------------------ display
    def report_text(self) -> str:
        spec = self.spectrum
        k = self.kind
        what = atr(KIND_KEYS[k])
        if k == ENERGY:
            if self.energy is not None:
                return ac.poly_report(self.energy)
            if spec is not None and spec.energy_coeffs:
                return atr("stored_only", what=what, eq=equation_text(spec.energy_coeffs))
        elif k == RESOLUTION:
            if self.resolution is not None:
                ecoef = self.energy.coeffs if self.energy is not None else (spec.energy_coeffs if spec else [])
                return ac.poly_report(self.resolution, ecoef)
        elif self.efficiency is not None:
            return ac.eff_report(self.efficiency)
        return atr("no_calibration", what=what)

    def refresh(self) -> None:
        self.kind_label.setText(atr("current_type", what=atr(KIND_KEYS[self.kind])))
        self.report.setPlainText(self.report_text())
        k = self.kind
        if k == EFFICIENCY:
            pts = [(p.energy, p.efficiency, p.use) for p in self.eff_points if p.efficiency > 0]
            self.graph.set_data(k, pts, self.efficiency.efficiency if self.efficiency is not None else None, log=True)
        else:
            cal = self.energy if k == ENERGY else self.resolution
            if cal is not None:
                self.graph.set_data(k, [(a, b, True) for a, b in zip(cal.channels, cal.values)], cal.evaluate)
            else:
                self.graph.set_data(k, [], None)

    # ------------------------------------------------------------ saving
    def calibrated_spectrum(self):
        """Copy of the spectrum with the calibrations of this window (counts untouched)."""
        spec = self.spectrum
        if spec is None:
            return None
        deleted = getattr(self, "_deleted", set())
        energy = self.energy.coeffs if self.energy is not None else ([] if ENERGY in deleted else None)
        ecoef = energy if energy is not None else spec.energy_coeffs
        fwhm = None
        if self.resolution is not None and len(ecoef) >= 2:
            fwhm = ac.fwhm_channels_to_kev(self.resolution.coeffs, ecoef)
        elif RESOLUTION in deleted:
            fwhm = []
        notes = []
        if self.energy is not None:
            notes.append(f"full energy calibration: {len(self.energy.channels)} points, degree {self.energy.degree}")
        if self.resolution is not None:
            notes.append(f"resolution calibration: {len(self.resolution.channels)} points, "
                         f"degree {self.resolution.degree}")
        new = cal_tools.apply_calibration(spec, energy, fwhm, note="; ".join(notes) or "calibration edited")
        if energy == []:
            new.energy_coeffs = []
        if self.energy is not None:
            new.extra["energy_calibration_points"] = "; ".join(
                f"{a:.2f}:{b:g}" for a, b in zip(self.energy.channels, self.energy.values))
        if self.resolution is not None:
            new.extra["resolution_calibration_points"] = "; ".join(
                f"{a:.2f}:{b:g}" for a, b in zip(self.resolution.channels, self.resolution.values))
        if self.efficiency is not None:
            e = self.efficiency
            new.extra["efficiency_calibration"] = (f"Aptec type {e.eff_type}, detector {e.detector_id}, geometry "
                                                   f"{e.geometry_id}, {len(e.used)} points")
        return new

    def save_curve(self, folder=None) -> Optional[Path]:
        """Efficiency calibration -> efficiency library (JSON curve used by Quantify)."""
        if self.efficiency is None:
            return None
        from ..analysis import efficiency as eff
        e = self.efficiency
        name = f"{e.detector_id or 'detector'}_{e.geometry_id or 'geometry'}_aptec{e.eff_type}"
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
        src = self.spectrum.source_path if self.spectrum is not None else ""
        curve = ac.to_efficiency_curve(e, name=name, source=src)
        path = Path(folder or eff.default_curve_dir()) / f"{safe}.json"
        curve.save(path)
        self.saved_curve_path = path
        return path

    def save_spectrum(self, curve_folder=None):
        new = self.calibrated_spectrum()
        if new is None:
            return None
        self.result_spectrum = new
        win = self.main_window
        if win is not None:
            apply_to_display(win, new)
        self.spectrum = new
        msg = atr("saved_spc")
        if self.efficiency is not None:
            try:
                path = self.save_curve(curve_folder)
                msg += "\n" + atr("saved_curve", path=i18n.bidi_path(str(path)))
            except OSError as exc:
                self.message(atr("fit_failed", msg=str(exc)))
        self.dirty = False
        if win is not None:
            win.statusBar().showMessage(msg.replace("\n", "  "), 15000)
        return new

    def save_spectrum_as(self) -> None:
        if self.save_spectrum() is not None and self.main_window is not None:
            act = getattr(self.main_window, "act_save", None)
            if act is not None:
                act.trigger()

    def save_report(self, path: Optional[str] = None) -> Optional[Path]:
        if not path:
            base = Path(self.spectrum.source_path).with_suffix(".txt") if (self.spectrum and self.spectrum.source_path) else Path("calibration.txt")
            path, _ = QFileDialog.getSaveFileName(self, atr("act_save_report"), str(base), "Text (*.txt)")
        if not path:
            return None
        p = Path(path)
        p.write_text(self.full_report(), encoding="utf-8")
        if self.main_window is not None:
            self.main_window.statusBar().showMessage(atr("report_saved", path=i18n.bidi_path(str(p))), 10000)
        return p

    def full_report(self) -> str:
        parts = []
        spec = self.spectrum
        if spec is not None:
            parts.append(f"Spectrum: {spec.source_path or spec.sample_id}")
        if self.energy is not None:
            parts.append(ac.poly_report(self.energy))
        if self.resolution is not None:
            parts.append(ac.poly_report(self.resolution, self.energy.coeffs if self.energy else
                                        (spec.energy_coeffs if spec else [])))
        if self.efficiency is not None:
            parts.append(ac.eff_report(self.efficiency))
        return "\n\n".join(parts) + "\n"

    def print_report(self) -> None:
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        printer = QPrinter()
        if QPrintDialog(printer, self).exec() != QDialog.Accepted:
            return
        doc = QPlainTextEdit()
        doc.setFont(_mono())
        doc.setPlainText(self.full_report())
        doc.document().print_(printer)

    def ask_unsaved(self) -> str:
        """'save' | 'discard' | 'cancel' (overridable in tests)."""
        box = QMessageBox(QMessageBox.Question, self.windowTitle(), atr("unsaved"),
                          QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, self)
        r = box.exec()
        return "save" if r == QMessageBox.Save else "discard" if r == QMessageBox.Discard else "cancel"

    def reject(self):
        """Close (Exit, Esc, the window's close button): unsaved changes are offered first."""
        if self.dirty and self.spectrum is not None:
            choice = self.ask_unsaved()
            if choice == "cancel":
                return
            if choice == "save":
                self.save_spectrum()
        super().reject()


# ===================================================================== main window hooks
def open_quick_energy(win, modal: bool = False):
    spec = _current(win)
    if spec is None:
        win.show_info(atr("need_spectrum"))
        return None
    d = QuickEnergyDialog(win, spec, win)
    d.setAttribute(Qt.WA_DeleteOnClose, True)
    if modal:
        d.exec()
    else:
        d.show()          # not modal: the marker can be moved on the spectrum meanwhile
    return d


def open_full_calibration(win, kind: str = ENERGY, modal: bool = False):
    spec = _current(win)
    if spec is None:
        win.show_info(atr("need_spectrum"))
        return None
    d = FullCalibrationWindow(win, spec, win, kind)
    d.setAttribute(Qt.WA_DeleteOnClose, True)
    if modal:
        d.exec()
    else:
        d.show()
    return d


def install_setup_menu(win) -> None:
    """Setup menu (before Analyze, as in Aptec) with the four calibration commands; the earlier
    calibration tools stay available under *Advanced Calibration Tools*."""
    mb = win.menuBar()
    win.menu_setup = mb.addMenu("")
    analyze = getattr(win, "menu_analyze", None)
    if analyze is not None:
        mb.insertMenu(analyze.menuAction(), win.menu_setup)
    specs = (("act_quick_energy", "quick", "F2", lambda: open_quick_energy(win)),
             ("act_full_energy", "full_energy", "", lambda: open_full_calibration(win, ENERGY)),
             ("act_full_res", "full_res", "", lambda: open_full_calibration(win, RESOLUTION)),
             ("act_full_eff", "full_eff", "Shift+F2", lambda: open_full_calibration(win, EFFICIENCY)))
    win._setup_actions = []
    for attr, key, sc, fn in specs:
        a = QAction(win)
        a.setObjectName(attr)
        if sc:
            a.setShortcut(QKeySequence(sc))
        a.triggered.connect(lambda _=False, f=fn: f())
        a._acal_key = key
        win.menu_setup.addAction(a)
        setattr(win, attr, a)
        win._setup_actions.append(a)
    win.menu_setup.addSeparator()
    win.menu_setup_advanced = win.menu_setup.addMenu("")
    for name in ("act_calibrate", "act_drift", "act_effcal"):
        a = getattr(win, name, None)
        if a is None:
            continue
        if analyze is not None:
            analyze.removeAction(a)
        win.menu_setup_advanced.addAction(a)
    retranslate_setup_menu(win)


def retranslate_setup_menu(win) -> None:
    if not hasattr(win, "menu_setup"):
        return
    win.menu_setup.setTitle(atr("menu_setup"))
    win.menu_setup_advanced.setTitle(atr("menu_advanced"))
    for a in getattr(win, "_setup_actions", []):
        k = a._acal_key
        a.setText(atr("act_" + k))
        a.setToolTip(atr("tip_" + k))
        a.setStatusTip(atr("tip_" + k))


__all__ = ["QuickEnergyDialog", "FullCalibrationWindow", "PointsDialog", "EfficiencyPointsDialog",
           "CalcEfficiencyDialog", "install_setup_menu", "retranslate_setup_menu", "open_quick_energy",
           "open_full_calibration", "marker_channel", "ENERGY", "RESOLUTION", "EFFICIENCY"]

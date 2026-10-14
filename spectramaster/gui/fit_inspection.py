"""Fit inspection and manual refit window (Release B, increments B2/B3, GUI part).

The science is in :mod:`spectramaster.analysis` (``inspect_fit``: the automatic fit with its report)
and :mod:`spectramaster.lab.session` (``AnalysisSession``: undoable manual refits through
:mod:`spectramaster.analysis.manual`).  This window only calls them:

* every fitted region with data, total fit, each component, background and residuals, chi2/dof,
  width scale, warnings and the discarded components with their reasons;
* manual edits -- refit a region (positions, fixed centroids, width option, step), add a peak at a
  channel, remove a peak (reason required) -- each one an undoable session edit, with a before /
  after comparison (``compare_peaks``) and a visible "results stale" indicator.

The automatic fit and the refits run in a worker thread.  The session of the displayed spectrum is
kept on the main window as ``win.fit_session`` (created from the displayed analysis results, or from
the inspected fit, with ``AnalysisSession.set_results(..., spectrum=...)``).  Hooked into the main
window by :func:`install_session_actions`.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QGroupBox,
                               QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QSpinBox, QSplitter, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from . import i18n
from .i18n import ltr
from .plot import C_AXIS_TEXT, C_BG, C_FRAME, C_GRID, C_LINE, _nice_step
from .session_strings import ftr
from .worker import start_call

C_DATA = QColor("#3c4650")
C_TOTAL = C_LINE
C_BKG = QColor("#d9822b")
C_COMP = QColor("#2e9d4f")
C_DISC = QColor("#9aa5b1")
C_RESID = QColor("#7a2e8e")
C_STALE = "#c62828"

COMP_COLS = ["col_n", "col_centroid", "col_energy", "col_fwhm", "col_area", "col_amp", "col_kept", "col_reason"]
DISC_COLS = ["col_region", "col_centroid", "col_energy", "col_area", "col_reason"]
PEAK_COLS = ["col_n", "col_centroid", "col_energy", "col_fwhm", "col_area", "col_note"]
CMP_COLS = ["col_status", "col_c_before", "col_c_after", "col_a_before", "col_a_after", "col_d_area", "col_d_sigma"]


def _f(v, fmt: str = ".2f") -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return i18n.tr("none")
    return format(v, fmt)


def _pm(v, u, fmt: str = ".2f") -> str:
    return ltr(f"{_f(v, fmt)} ± {_f(u, fmt)}") if u is not None else ltr(_f(v, fmt))


def _item(text: str, align=Qt.AlignRight | Qt.AlignVCenter, tip: str = "") -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    it.setTextAlignment(align)
    if tip:
        it.setToolTip(tip)
    return it


def _table(cols, keys_tr) -> QTableWidget:
    t = QTableWidget(0, len(cols))
    t.setHorizontalHeaderLabels([keys_tr(k) for k in cols])
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.verticalHeader().setVisible(False)
    return t


def _energy(spectrum, channel) -> Optional[float]:
    if spectrum is None or channel is None or not spectrum.energy_coeffs:
        return None
    try:
        return spectrum.energy_of(channel)
    except Exception:
        return None


# ===================================================================== plot
class FitPlot(QWidget):
    """One fit group: data (points), total fit, components (+ background), background and the
    normalised residuals underneath.  QPainter, palette of ``plot.py``; always left-to-right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 300)
        self.setLayoutDirection(Qt.LeftToRight)
        self.group = None

    def set_group(self, group) -> None:
        self.group = group
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), C_BG)
        g = self.group
        if g is None or len(g.data) == 0:
            p.setPen(C_AXIS_TEXT)
            p.drawText(self.rect(), Qt.AlignCenter, ftr("plot_empty"))
            p.end()
            return
        w, h = self.width(), self.height()
        L, R, T, B = 62, 12, 22, 26
        avail = h - T - B - 10
        main = QRectF(L, T, w - L - R, avail * 0.72)
        res = QRectF(L, main.bottom() + 10, w - L - R, avail * 0.28)
        x = g.channels.astype(float)
        x0, x1 = float(x[0]) - 0.5, float(x[-1]) + 0.5
        curves = [g.background + g.component_curve(j) for j in range(len(g.components))]
        ymax = float(max(np.max(g.data + np.sqrt(np.maximum(g.data, 1.0))), np.max(g.total), 1.0)) * 1.08
        ymin = float(min(0.0, np.min(g.background)))

        def X(c):
            return main.left() + (c - x0) / (x1 - x0) * main.width()

        def Y(v):
            return main.bottom() - (v - ymin) / (ymax - ymin) * main.height()

        # grid and axes
        p.setPen(QPen(C_GRID, 1))
        ystep = _nice_step(ymax - ymin, 5)
        v = math.ceil(ymin / ystep) * ystep
        while v <= ymax:
            p.drawLine(QPointF(main.left(), Y(v)), QPointF(main.right(), Y(v)))
            p.setPen(C_AXIS_TEXT)
            p.drawText(QRectF(0, Y(v) - 7, L - 4, 14), Qt.AlignRight | Qt.AlignVCenter, f"{v:g}")
            p.setPen(QPen(C_GRID, 1))
            v += ystep
        xstep = _nice_step(x1 - x0, 8)
        c = math.ceil(x0 / xstep) * xstep
        while c <= x1:
            p.setPen(QPen(C_GRID, 1))
            p.drawLine(QPointF(X(c), main.top()), QPointF(X(c), res.bottom()))
            p.setPen(C_AXIS_TEXT)
            p.drawText(QRectF(X(c) - 40, res.bottom() + 2, 80, 14), Qt.AlignCenter, f"{c:g}")
            c += xstep
        p.setPen(QPen(C_FRAME, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(main)
        p.drawRect(res)
        p.setPen(C_AXIS_TEXT)
        p.drawText(QRectF(L, res.bottom() + 12, main.width(), 14), Qt.AlignCenter, ftr("plot_axis"))

        def path(ys):
            pp = QPainterPath()
            for k, (cx, cy) in enumerate(zip(x, ys)):
                pt = QPointF(X(cx), min(max(Y(cy), main.top()), main.bottom()))
                pp.moveTo(pt) if k == 0 else pp.lineTo(pt)
            return pp

        p.save()
        p.setClipRect(main)
        # components (each on the background), discarded ones grey and dashed
        for comp, ys in zip(g.components, curves):
            pen = QPen(C_COMP if comp.kept else C_DISC, 1.3, Qt.SolidLine if comp.kept else Qt.DashLine)
            p.setPen(pen)
            p.drawPath(path(ys))
        p.setPen(QPen(C_BKG, 1.5, Qt.DashLine))
        p.drawPath(path(g.background))
        # data with Poisson error bars
        p.setPen(QPen(C_DATA, 1))
        p.setBrush(C_DATA)
        for cx, cy in zip(x, g.data):
            s = math.sqrt(max(cy, 1.0))
            p.drawLine(QPointF(X(cx), Y(cy - s)), QPointF(X(cx), Y(cy + s)))
            p.drawEllipse(QPointF(X(cx), Y(cy)), 2.0, 2.0)
        p.setPen(QPen(C_TOTAL, 2))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path(g.total))
        p.restore()
        # legend
        lx = main.left() + 6
        for label, col, style in ((ftr("plot_data"), C_DATA, Qt.SolidLine), (ftr("plot_total"), C_TOTAL, Qt.SolidLine),
                                  (ftr("plot_comp"), C_COMP, Qt.SolidLine), (ftr("plot_bkg"), C_BKG, Qt.DashLine)):
            p.setPen(QPen(col, 2, style))
            p.drawLine(QPointF(lx, 10), QPointF(lx + 16, 10))
            p.setPen(C_AXIS_TEXT)
            tw = p.fontMetrics().horizontalAdvance(label)
            p.drawText(QPointF(lx + 20, 14), label)
            lx += 30 + tw
        # residuals
        r = g.residuals
        lim = max(float(np.max(np.abs(r))) if len(r) else 0.0, 3.0) * 1.1

        def RY(v):
            return res.center().y() - v / lim * res.height() / 2

        p.setPen(QPen(C_FRAME, 1, Qt.DashLine))
        for v in (-2.0, 2.0):
            p.drawLine(QPointF(res.left(), RY(v)), QPointF(res.right(), RY(v)))
        p.setPen(QPen(C_AXIS_TEXT, 1))
        p.drawLine(QPointF(res.left(), RY(0)), QPointF(res.right(), RY(0)))
        p.drawText(QRectF(0, res.top(), L - 4, 14), Qt.AlignRight, f"+{lim:.1f}")
        p.drawText(QRectF(0, res.bottom() - 14, L - 4, 14), Qt.AlignRight, f"−{lim:.1f}")
        p.drawText(QRectF(0, res.center().y() - 7, L - 4, 14), Qt.AlignRight | Qt.AlignVCenter, "σ")
        p.setPen(QPen(C_RESID, 2))
        for cx, rv in zip(x, r):
            p.drawLine(QPointF(X(cx), RY(0)), QPointF(X(cx), RY(rv)))
        p.end()


# ===================================================================== window
class FitInspectionDialog(QDialog):
    """Non-modal window; ``main_window`` (optional) holds the session as ``fit_session``."""

    def __init__(self, parent=None, spectrum=None, main_window=None, session=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.spectrum = spectrum
        self.main_window = main_window
        self.session = session
        self.report = None                 # FitReport of the automatic fit
        self.manual_groups: dict[str, object] = {}     # op_id -> FitGroup of a manual refit
        self.last_op = None
        self.last_error = ""
        self._busy = False
        self._new_requested = False
        self._groups: list = []            # displayed (group, origin) pairs
        self.setWindowTitle(ftr("title"))
        self.resize(1280, 860)
        lay = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel(ftr("spectrum")))
        name = ""
        if spectrum is not None:
            name = i18n.bidi_path(spectrum.source_path) if spectrum.source_path else ltr(spectrum.sample_id)
        self.spec_label = QLabel(name or i18n.tr("none"))
        row.addWidget(self.spec_label, 1)
        self.btn_refresh = QPushButton(ftr("refresh"))
        self.btn_refresh.setToolTip(ftr("tip_refresh"))
        self.btn_refresh.clicked.connect(lambda: self.run_inspection(confirm=True))
        row.addWidget(self.btn_refresh)
        self.btn_undo = QPushButton(ftr("undo"))
        self.btn_undo.clicked.connect(self.undo)
        row.addWidget(self.btn_undo)
        self.btn_redo = QPushButton(ftr("redo"))
        self.btn_redo.clicked.connect(self.redo)
        row.addWidget(self.btn_redo)
        lay.addLayout(row)
        self.stale_label = QLabel("")
        self.stale_label.setWordWrap(True)
        lay.addWidget(self.stale_label)

        split = QSplitter(Qt.Horizontal)
        # --- left: groups + session peaks
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        gbox = QGroupBox(ftr("groups_group"))
        gl = QVBoxLayout(gbox)
        self.group_list = QListWidget()
        self.group_list.currentRowChanged.connect(self._group_selected)
        gl.addWidget(self.group_list)
        self.source_label = QLabel("")
        self.source_label.setWordWrap(True)
        gl.addWidget(self.source_label)
        ll.addWidget(gbox, 3)
        pbox = QGroupBox(ftr("peaks_group"))
        pl = QVBoxLayout(pbox)
        self.peak_table = _table(PEAK_COLS, ftr)
        self.peak_table.setSelectionMode(QAbstractItemView.SingleSelection)
        pl.addWidget(self.peak_table)
        ll.addWidget(pbox, 2)
        split.addWidget(left)

        # --- right: plot + details / components / discarded / comparison tabs + editing
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.plot = FitPlot()
        rl.addWidget(self.plot, 3)
        self.tabs = QTabWidget()
        det = QWidget()
        dl = QVBoxLayout(det)
        self.chi2_label = QLabel("")
        self.width_label = QLabel("")
        self.step_label = QLabel("")
        for w in (self.chi2_label, self.width_label, self.step_label):
            w.setWordWrap(True)
            dl.addWidget(w)
        dl.addWidget(QLabel(ftr("warnings")))
        self.warn_list = QListWidget()
        self.warn_list.setLayoutDirection(Qt.LeftToRight)       # engine text is English
        dl.addWidget(self.warn_list)
        self.tabs.addTab(det, ftr("details_group"))
        self.comp_table = _table(COMP_COLS, ftr)
        self.tabs.addTab(self.comp_table, ftr("comp_group"))
        self.disc_table = _table(DISC_COLS, ftr)
        self.tabs.addTab(self.disc_table, ftr("disc_group"))
        self.cmp_table = _table(CMP_COLS, ftr)
        self.tabs.addTab(self.cmp_table, ftr("cmp_group"))
        rl.addWidget(self.tabs, 2)
        rl.addWidget(self._edit_box())
        split.addWidget(right)
        split.setSizes([400, 880])
        lay.addWidget(split, 1)

        row = QHBoxLayout()
        self.status_label = QLabel("")
        row.addWidget(self.status_label, 1)
        b = QPushButton(ftr("close"))
        b.clicked.connect(self.close)
        row.addWidget(b)
        lay.addLayout(row)
        self._refresh()

    def _edit_box(self) -> QGroupBox:
        box = QGroupBox(ftr("edit_group"))
        el = QVBoxLayout(box)
        row = QHBoxLayout()
        row.addWidget(QLabel(ftr("region")))
        self.lo_spin = QSpinBox()
        self.hi_spin = QSpinBox()
        n = 0 if self.spectrum is None else self.spectrum.first_channel + self.spectrum.num_channels - 1
        f0 = 0 if self.spectrum is None else self.spectrum.first_channel
        for s in (self.lo_spin, self.hi_spin):
            s.setRange(f0, max(n, f0))
            s.setLayoutDirection(Qt.LeftToRight)
            row.addWidget(s)
        b = QPushButton(ftr("from_group"))
        b.setToolTip(ftr("tip_from_group"))
        b.clicked.connect(self.fill_from_group)
        row.addWidget(b)
        row.addSpacing(12)
        row.addWidget(QLabel(ftr("width_opt")))
        self.width_combo = QComboBox()
        self.width_combo.addItem(ftr("width_opt_free"), "free")
        self.width_combo.addItem(ftr("width_opt_model"), "model")
        self.width_combo.addItem(ftr("width_opt_fixed"), "fixed")
        self.width_combo.currentIndexChanged.connect(
            lambda _i: self.width_spin.setEnabled(self.width_combo.currentData() == "fixed"))
        row.addWidget(self.width_combo)
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.2, 5.0)
        self.width_spin.setSingleStep(0.05)
        self.width_spin.setValue(1.0)
        self.width_spin.setEnabled(False)
        self.width_spin.setLayoutDirection(Qt.LeftToRight)
        row.addWidget(self.width_spin)
        self.step_check = QCheckBox(ftr("step_opt"))
        self.step_check.setChecked(True)
        row.addWidget(self.step_check)
        row.addStretch(1)
        el.addLayout(row)
        row = QHBoxLayout()
        col = QVBoxLayout()
        col.addWidget(QLabel(ftr("positions")))
        self.pos_table = QTableWidget(0, 2)
        self.pos_table.setHorizontalHeaderLabels([ftr("col_pos"), ftr("col_fix")])
        self.pos_table.horizontalHeaderItem(1).setToolTip(ftr("tip_fix"))
        self.pos_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pos_table.verticalHeader().setVisible(False)
        self.pos_table.setMaximumHeight(110)
        col.addWidget(self.pos_table)
        r2 = QHBoxLayout()
        b = QPushButton(ftr("add_pos"))
        b.clicked.connect(lambda: self.add_position())
        r2.addWidget(b)
        b = QPushButton(ftr("remove_pos"))
        b.clicked.connect(self.remove_position)
        r2.addWidget(b)
        col.addLayout(r2)
        row.addLayout(col, 2)
        col = QVBoxLayout()
        r2 = QHBoxLayout()
        r2.addWidget(QLabel(ftr("reason")))
        self.reason_edit = QLineEdit()
        self.reason_edit.setPlaceholderText(ftr("reason_placeholder"))
        r2.addWidget(self.reason_edit, 1)
        col.addLayout(r2)
        self.btn_refit = QPushButton(ftr("refit"))
        self.btn_refit.clicked.connect(self.refit_region)
        col.addWidget(self.btn_refit)
        r2 = QHBoxLayout()
        self.add_spin = QDoubleSpinBox()
        self.add_spin.setDecimals(2)
        self.add_spin.setRange(float(f0), float(max(n, f0)))
        self.add_spin.setLayoutDirection(Qt.LeftToRight)
        r2.addWidget(self.add_spin)
        self.btn_add = QPushButton(ftr("add_peak"))
        self.btn_add.setToolTip(ftr("tip_add_peak"))
        self.btn_add.clicked.connect(lambda: self.add_peak())
        r2.addWidget(self.btn_add)
        col.addLayout(r2)
        self.btn_remove = QPushButton(ftr("remove_peak"))
        self.btn_remove.setToolTip(ftr("tip_remove_peak"))
        self.btn_remove.clicked.connect(lambda: self.remove_peak())
        col.addWidget(self.btn_remove)
        col.addStretch(1)
        row.addLayout(col, 3)
        el.addLayout(row)
        return box

    # ------------------------------------------------------------------ hooks (tests replace them)
    def message(self, text: str) -> None:
        QMessageBox.warning(self, ftr("title"), text)

    def confirm(self, title: str, text: str) -> bool:
        return QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No,
                                    QMessageBox.No) == QMessageBox.Yes

    def ask_reason(self, channel: float) -> Optional[str]:
        text, ok = QInputDialog.getText(self, ftr("remove_title"), ftr("remove_prompt", ch=ltr(f"{channel:.2f}")))
        return text if ok else None

    @property
    def busy(self) -> bool:
        return self._busy

    # ------------------------------------------------------------------ automatic fit (worker)
    def run_inspection(self, confirm: bool = False) -> bool:
        if self.spectrum is None or self._busy:
            return False
        if confirm and self.session is not None and self.session.history.can_undo():
            if not self.confirm(ftr("confirm_refresh_title"), ftr("confirm_refresh")):
                return False
        from .. import analysis
        spec = self.spectrum
        self._new_requested = confirm
        self._set_busy(True, ftr("running"))
        start_call(self, lambda: analysis.inspect_fit(spec), self._on_inspected, self._on_failed)
        return True

    def _on_inspected(self, result) -> None:
        peaks, rep = result
        self._set_busy(False)
        self.report = rep
        self.manual_groups = {}
        self.last_op = None
        if self.session is None or self._new_requested or not self._session_matches():
            self.session = self._new_session(peaks)
        win = self.main_window
        if win is not None:
            win.fit_session = self.session
        self._refresh()

    def _session_matches(self) -> bool:
        from ..analysis.manual import counts_sha256
        want = (self.session.processing_settings or {}).get("counts_sha256")
        return bool(want) and want == counts_sha256(self.spectrum)

    def _new_session(self, peaks):
        """Session from the displayed analysis results (same spectrum) or from the inspected fit."""
        from ..lab.session import AnalysisSession
        s = AnalysisSession()
        panel = getattr(self.main_window, "analysis_panel", None)
        shown, matches = list(getattr(panel, "peaks", []) or []), list(getattr(panel, "matches", []) or [])
        if shown:
            try:
                s.set_results(shown, matches, spectrum=self.spectrum)
                return s
            except ValueError:
                pass
        s.set_results(peaks, spectrum=self.spectrum)
        return s

    def _on_failed(self, msg: str) -> None:
        self._set_busy(False)
        self.last_error = msg
        self._refresh()
        self.message(ftr("inspect_failed", msg=msg))

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self._busy = busy
        self.status_label.setText(text if busy else "")
        for w in (self.btn_refresh, self.btn_refit, self.btn_add, self.btn_remove, self.btn_undo, self.btn_redo):
            w.setEnabled(not busy)
        if not busy:
            self._update_history_buttons()

    # ------------------------------------------------------------------ manual edits (worker)
    def positions(self) -> tuple[list[float], list[bool]]:
        cents, fix = [], []
        for r in range(self.pos_table.rowCount()):
            it = self.pos_table.item(r, 0)
            try:
                c = float((it.text() if it else "").replace(",", ".").strip())
            except ValueError:
                continue
            fx = self.pos_table.item(r, 1)
            cents.append(c)
            fix.append(fx is not None and fx.checkState() == Qt.Checked)
        return cents, fix

    def add_position(self, channel: Optional[float] = None, fixed: bool = False) -> None:
        r = self.pos_table.rowCount()
        self.pos_table.insertRow(r)
        it = QTableWidgetItem("" if channel is None else f"{channel:.2f}")
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.pos_table.setItem(r, 0, it)
        fx = QTableWidgetItem()
        fx.setFlags((fx.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
        fx.setCheckState(Qt.Checked if fixed else Qt.Unchecked)
        self.pos_table.setItem(r, 1, fx)

    def remove_position(self) -> None:
        for r in sorted({i.row() for i in self.pos_table.selectedIndexes()}, reverse=True):
            self.pos_table.removeRow(r)

    def fill_from_group(self) -> None:
        g = self.selected_group()
        if g is None:
            return
        self.lo_spin.setValue(int(g.lo))
        self.hi_spin.setValue(int(g.hi))
        self.pos_table.setRowCount(0)
        for c in g.components:
            if c.kept:
                self.add_position(c.centroid)
        self.add_spin.setValue(float(g.lo + g.hi) / 2)

    def width_option(self):
        mode = self.width_combo.currentData()
        return float(self.width_spin.value()) if mode == "fixed" else mode

    def _edit(self, what: str, fn) -> bool:
        if self.session is None or self.spectrum is None or self._busy:
            return False
        if not self._session_matches():
            self.message(ftr("spectrum_changed"))
            return False
        self._set_busy(True, ftr("running_refit"))
        start_call(self, fn, self._on_edited, self._on_edit_failed)
        return True

    def refit_region(self) -> bool:
        cents, fix = self.positions()
        if not cents:
            self.message(ftr("no_positions"))
            return False
        s, spec = self.session, self.spectrum
        lo, hi, reason = self.lo_spin.value(), self.hi_spin.value(), self.reason_edit.text().strip()
        opts = {"width": self.width_option(), "step": self.step_check.isChecked(),
                "fix_centroids": fix if any(fix) else None}
        return self._edit("refit", lambda: s.refit_region(spec, lo, hi, cents, reason=reason, **opts))

    def add_peak(self, channel: Optional[float] = None) -> bool:
        ch = float(self.add_spin.value() if channel is None else channel)
        s, spec, reason = self.session, self.spectrum, self.reason_edit.text().strip()
        opts = {"width": self.width_option(), "step": self.step_check.isChecked()}
        return self._edit("add", lambda: s.add_peak_and_refit(spec, ch, reason, **opts))

    def selected_peak_index(self) -> Optional[int]:
        rows = sorted({i.row() for i in self.peak_table.selectedIndexes()})
        return rows[0] if rows else None

    def remove_peak(self, index: Optional[int] = None, reason: Optional[str] = None) -> bool:
        if self.session is None:
            return False
        index = self.selected_peak_index() if index is None else index
        peaks = self.session.results.get("peaks", [])
        if index is None or not 0 <= index < len(peaks):
            self.message(ftr("select_peak"))
            return False
        if reason is None:
            reason = self.ask_reason(float(peaks[index]["centroid"]))
        if reason is None:
            return False
        if not reason.strip():
            self.message(ftr("reason_required"))
            return False
        s, spec = self.session, self.spectrum
        opts = {"width": self.width_option(), "step": self.step_check.isChecked()}
        return self._edit("remove", lambda: s.remove_peak_and_refit(spec, index, reason.strip(), **opts))

    def _on_edited(self, result) -> None:
        op, rf = result
        self._set_busy(False)
        self.last_op = op
        if rf is not None and rf.group is not None:
            self.manual_groups[op.op_id] = rf.group
        self.reason_edit.clear()
        self._after_edit(op)

    def _on_edit_failed(self, msg: str) -> None:
        self._set_busy(False)
        self.last_error = msg
        self.message(ftr("edit_failed", msg=msg))

    def undo(self) -> bool:
        if self.session is None or self._busy:
            return False
        op = self.session.undo()
        if op is None:
            return False
        self.last_op = op
        self._after_edit(op)
        return True

    def redo(self) -> bool:
        if self.session is None or self._busy:
            return False
        op = self.session.redo()
        if op is None:
            return False
        self.last_op = op
        self._after_edit(op)
        return True

    def _after_edit(self, op) -> None:
        self._refresh()
        win = self.main_window
        if win is None:
            return
        try:
            from ..analysis import Peak
            win.plot.set_peaks([Peak(**p) for p in self.session.results["peaks"]])
        except Exception:
            pass
        if self.session.status.get("results_stale"):
            win.statusBar().showMessage(ftr("status_edited", what=op.describe()), 15000)

    # ------------------------------------------------------------------ display
    def displayed_groups(self) -> list[tuple]:
        """(group, origin) pairs: automatic groups, replaced where an active manual refit covers
        them (origin = op id of that refit, '' for automatic)."""
        active = []
        if self.session is not None:
            stack = self.session.history.undo_stack
            active = [(oid, self.manual_groups[oid]) for oid in stack if oid in self.manual_groups]
        out = []
        for g in (self.report.groups if self.report is not None else []):
            if not any(m.lo <= g.hi and g.lo <= m.hi for _oid, m in active):
                out.append((g, ""))
        for k, (oid, m) in enumerate(active):
            later = active[k + 1:]
            if not any(o.lo <= m.hi and m.lo <= o.hi for _x, o in later):
                out.append((m, oid))
        return sorted(out, key=lambda t: t[0].lo)

    def selected_group(self):
        r = self.group_list.currentRow()
        return self._groups[r][0] if 0 <= r < len(self._groups) else None

    def _removed_centroids(self) -> list[float]:
        if self.session is None:
            return []
        h = self.session.history
        out = []
        for oid in h.undo_stack:
            op = h._op(oid)
            if op.details and "removed_centroid" in op.details:
                out.append(float(op.details["removed_centroid"]))
        return out

    def _refresh(self) -> None:
        keep = self.group_list.currentRow()
        self._groups = self.displayed_groups()
        removed = self._removed_centroids()
        self.group_list.blockSignals(True)
        self.group_list.clear()
        for g, origin in self._groups:
            kept = [c for c in g.components if c.kept]
            e = _energy(self.spectrum, (g.lo + g.hi) / 2)
            text = ftr("group_item", lo=ltr(g.lo), hi=ltr(g.hi),
                       energy=ftr("group_energy", e=ltr(f"{e:.1f}")) if e is not None else "",
                       n=ltr(len(kept)),
                       disc=ftr("group_disc", n=ltr(len(g.components) - len(kept))) if len(kept) < len(g.components) else "",
                       chi2=ltr(_f(g.chi2_reduced, ".2f")), warn=ftr("group_warn") if g.warnings else "")
            if origin:
                text = f"[{ftr('group_manual')}] " + text
            if any(g.lo <= c <= g.hi for c in removed) and not origin:
                text += ftr("group_removed")
            it = QListWidgetItem(text)
            if g.warnings:
                it.setForeground(QColor("#b26a00"))
            self.group_list.addItem(it)
        if not self._groups:
            self.group_list.addItem(ftr("no_groups"))
        self.group_list.blockSignals(False)
        row = keep if 0 <= keep < len(self._groups) else (0 if self._groups else -1)
        self.group_list.setCurrentRow(row)
        self._group_selected(row)
        if self.report is not None:
            self.source_label.setText(ftr("fwhm_source", src=self.report.fwhm_source))
        self._fill_discarded()
        self._fill_peaks()
        self._fill_comparison()
        self._update_stale()
        self._update_history_buttons()

    def _group_selected(self, row: int) -> None:
        g = self._groups[row][0] if 0 <= row < len(self._groups) else None
        self.plot.set_group(g)
        self.comp_table.setRowCount(0)
        self.warn_list.clear()
        if g is None:
            for w in (self.chi2_label, self.width_label, self.step_label):
                w.setText("")
            return
        self.chi2_label.setText(ftr("chi2", chi2=ltr(_f(g.chi2_reduced, ".3f")), dof=ltr(g.dof)))
        mode = ftr("width_free") if g.width_free else ftr("width_fixed")
        if g.width_at_bound:
            mode += ", " + ftr("width_at_bound")
        self.width_label.setText(ftr("width", scale=ltr(_f(g.width_scale, ".3f")), mode=mode))
        text = ftr("step", h=ltr(_f(g.step_height, ".3g")))
        if g.retry:
            text += "   " + ftr("retry", r=g.retry)
        self.step_label.setText(text)
        for w in g.warnings:
            self.warn_list.addItem(w)
        if not g.warnings:
            self.warn_list.addItem(ftr("no_warnings"))
        self.comp_table.setRowCount(len(g.components))
        for k, c in enumerate(g.components):
            e = _energy(self.spectrum, c.centroid)
            vals = [str(k + 1), _pm(c.centroid, c.centroid_unc, ".3f"), _f(e, ".2f"), _f(c.fwhm, ".2f"),
                    _pm(c.area, c.area_unc, ".1f"), _f(c.amplitude, ".1f"), ftr("yes") if c.kept else ftr("no")]
            for j, v in enumerate(vals):
                self.comp_table.setItem(k, j, _item(v))
            self.comp_table.setItem(k, 7, _item(c.reason, Qt.AlignLeft | Qt.AlignVCenter, tip=c.reason))

    def _fill_discarded(self) -> None:
        rows = [(g, c) for g, _o in self._groups for c in g.components if not c.kept]
        self.disc_table.setRowCount(len(rows))
        for k, (g, c) in enumerate(rows):
            vals = [ltr(f"{g.lo}–{g.hi}"), _pm(c.centroid, c.centroid_unc, ".3f"),
                    _f(_energy(self.spectrum, c.centroid), ".2f"), _pm(c.area, c.area_unc, ".1f")]
            for j, v in enumerate(vals):
                self.disc_table.setItem(k, j, _item(v))
            self.disc_table.setItem(k, 4, _item(c.reason, Qt.AlignLeft | Qt.AlignVCenter, tip=c.reason))

    def _fill_peaks(self) -> None:
        peaks = self.session.results.get("peaks", []) if self.session is not None else []
        self.peak_table.setRowCount(len(peaks))
        for k, p in enumerate(peaks):
            vals = [str(k + 1), _pm(p.get("centroid"), p.get("centroid_unc"), ".3f"), _f(p.get("energy"), ".2f"),
                    _f(p.get("fwhm"), ".2f"), _pm(p.get("net_area"), p.get("net_area_unc"), ".1f")]
            for j, v in enumerate(vals):
                self.peak_table.setItem(k, j, _item(v))
            note = p.get("note") or ""
            self.peak_table.setItem(k, 5, _item(note, Qt.AlignLeft | Qt.AlignVCenter, tip=note))

    def comparison_rows(self) -> list[dict]:
        op = self.last_op
        if op is None or op.kind != "replace_peaks":
            return []
        from ..analysis.manual import compare_peaks
        before, after = op.before or [], op.after or []
        if op.undone:                      # show what the undo changed
            before, after = after, before
        return compare_peaks(before, after)

    def _fill_comparison(self) -> None:
        rows = [r for r in self.comparison_rows() if r["status"] != "unchanged"]
        if self.last_op is None:
            self.cmp_table.setRowCount(1)
            self.cmp_table.setItem(0, 0, _item(ftr("cmp_none"), Qt.AlignLeft | Qt.AlignVCenter))
            return
        self.cmp_table.setRowCount(len(rows))
        for k, r in enumerate(rows):
            vals = [ftr("st_" + r["status"]), _f(r["centroid_before"], ".3f"), _f(r["centroid_after"], ".3f"),
                    _f(r["area_before"], ".1f"), _f(r["area_after"], ".1f"), _f(r["d_area"], "+.1f"),
                    _f(r["d_area_sigma"], "+.2f")]
            for j, v in enumerate(vals):
                self.cmp_table.setItem(k, j, _item(v, Qt.AlignCenter if j == 0 else Qt.AlignRight | Qt.AlignVCenter))

    def is_stale(self) -> bool:
        return bool(self.session is not None and self.session.status.get("results_stale"))

    def _update_stale(self) -> None:
        if self.is_stale():
            self.stale_label.setText("⚠ " + ftr("stale"))
            self.stale_label.setStyleSheet(f"color: {C_STALE}; font-weight: bold;")
            reasons = self.session.status.get("stale_reasons", [])
            self.stale_label.setToolTip("\n".join(reasons))
        else:
            self.stale_label.setText(ftr("not_stale") if self.session is not None else "")
            self.stale_label.setStyleSheet("")
            self.stale_label.setToolTip("")

    def _update_history_buttons(self) -> None:
        h = self.session.history if self.session is not None else None
        can_u = bool(h and h.can_undo()) and not self._busy
        can_r = bool(h and h.can_redo()) and not self._busy
        self.btn_undo.setEnabled(can_u)
        self.btn_redo.setEnabled(can_r)
        self.btn_undo.setToolTip(ftr("tip_undo", what=h._op(h.undo_stack[-1]).describe()) if can_u else "")
        self.btn_redo.setToolTip(ftr("tip_redo", what=h._op(h.redo_stack[-1]).describe()) if can_r else "")


# ===================================================================== main-window hooks
def open_fit_inspection(win, show: bool = True):
    """Open (or raise) the window for the displayed spectrum; reuses ``win.fit_session`` when it
    belongs to the same counts."""
    try:
        spec = win.current_spectrum()
    except Exception:
        spec = None
    if spec is None:
        win.show_info(ftr("need_spectrum"))
        return None
    old = getattr(win, "fit_window", None)
    if old is not None and old.spectrum is spec and old.session is getattr(win, "fit_session", None):
        if old.report is None and not old.busy:
            old.run_inspection()
        if show:          # same spectrum: keep the window with its manual fits and history
            old.show()
            old.raise_()
            old.activateWindow()
        return old
    dlg = FitInspectionDialog(win, spec, win, getattr(win, "fit_session", None))
    dlg.setAttribute(Qt.WA_DeleteOnClose, False)
    win.fit_window = dlg
    dlg.run_inspection()
    if show:
        dlg.show()
    return dlg


def install_session_actions(win) -> None:
    """Analyze > Fit Inspection & Manual Refit... (``act_fit_inspect``); ``win.fit_session`` holds
    the AnalysisSession of the manual edits."""
    win.fit_session = None
    win.fit_window = None
    win.act_fit_inspect = QAction(win)
    win.act_fit_inspect.setObjectName("act_fit_inspect")
    win.act_fit_inspect.triggered.connect(lambda _=False: open_fit_inspection(win))
    menu = getattr(win, "menu_analyze", None)
    if menu is not None:
        menu.addAction(win.act_fit_inspect)
    retranslate_session_actions(win)


def retranslate_session_actions(win) -> None:
    a = getattr(win, "act_fit_inspect", None)
    if a is not None:
        a.setText(ftr("act_inspect"))
        a.setToolTip(ftr("tip_inspect"))
        a.setStatusTip(ftr("tip_inspect"))


__all__ = ["FitPlot", "FitInspectionDialog", "open_fit_inspection", "install_session_actions",
           "retranslate_session_actions"]

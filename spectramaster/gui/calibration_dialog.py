"""Energy-calibration review and drift-check dialogs (Release B, increment B1, GUI part).

The science is in :mod:`spectramaster.tools.calibrate`; these dialogs only call it:

* :class:`CalibrationDialog` -- ``calibrate_from_source`` (worker thread) proposes the line-to-peak
  assignments; ticking / unticking a point (a reason is required to exclude one) or changing the
  order refits with ``fit_points`` and re-validates with ``validate_calibration``.  Nothing is
  applied until *Accept*, which is disabled while the validation reports errors.
* :class:`DriftDialog` -- ``check_drift`` (worker thread) shows the drift report; the proposed
  correction is applied only after an explicit confirmation, never automatically.

Accepting replaces the displayed spectrum by a copy with the new coefficients
(``apply_calibration``: counts untouched, previous coefficients and a note in ``extra``); the file
on disk is not modified.  Hooked into the main window by :func:`install_calibration_actions`.
"""
from __future__ import annotations

import copy
import math
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QGroupBox, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QMessageBox,
                               QPlainTextEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ..tools import calibrate as cal
from . import i18n
from .calibration_strings import ctr
from .i18n import ltr
from .worker import start_call

POINT_COLS = ["col_used", "col_nuclide", "col_energy", "col_channel", "col_channel_unc", "col_residual",
              "col_loo", "col_sig", "col_reason"]
DRIFT_COLS = ["drift_col_name", "drift_col_ref", "drift_col_meas", "drift_col_shift"]
USER_EXCLUDED = "excluded by the user: "       # English prefix stored with the point (audit record)


def _f(v, fmt: str = ".3f") -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return i18n.tr("none")
    return format(v, fmt)


def coeffs_text(coeffs) -> str:
    """'E = c0 + c1·ch + c2·ch²' (LTR isolate, readable inside Arabic text)."""
    if not coeffs:
        return i18n.tr("none")
    sup = {2: "²", 3: "³"}
    terms = []
    for k, c in enumerate(coeffs):
        t = f"{c:.9g}"
        if k == 1:
            t += "·ch"
        elif k > 1:
            t += "·ch" + sup.get(k, f"^{k}")
        terms.append(t)
    return ltr(" + ".join(terms).replace("+ -", "− "))


def _item(text: str, align=Qt.AlignRight | Qt.AlignVCenter, tip: str = "") -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    it.setTextAlignment(align)
    if tip:
        it.setToolTip(tip)
    return it


def _key(p) -> tuple:
    return (p.nuclide, round(float(p.energy), 4))


def replace_displayed_spectrum(win, spectrum) -> bool:
    """Show `spectrum` in place of the displayed one (same position in a multi-spectrum file).

    Uses the main window's own display path (``show_index``) so plot, info panel and actions are
    refreshed; the analysis results of the old calibration are cleared there and the manual-fit
    session (if any) is dropped, because energies changed."""
    spectra = getattr(win, "_spectra", None)
    i = getattr(win, "_index", -1)
    if spectra is None or not 0 <= i < len(spectra):
        return False
    spectra[i] = spectrum
    win._index = -1
    win.show_index(i)
    if hasattr(win, "fit_session"):
        win.fit_session = None
    return True


class _MessageMixin:
    """Overridable message/prompt hooks (tests replace them so no modal box blocks)."""

    def message(self, text: str) -> None:
        QMessageBox.warning(self, self.windowTitle(), text)

    def confirm(self, title: str, text: str) -> bool:
        box = QMessageBox(QMessageBox.Question, title, text, QMessageBox.Yes | QMessageBox.No, self)
        box.setDefaultButton(QMessageBox.No)        # applying needs a deliberate choice
        return box.exec() == QMessageBox.Yes

    def ask_reason(self, label: str) -> Optional[str]:
        text, ok = QInputDialog.getText(self, ctr("reason_title"), ctr("reason_prompt", label=ltr(label)))
        return text if ok else None


# ===================================================================== calibration review
class CalibrationDialog(_MessageMixin, QDialog):
    """Propose -> review (tick/untick points, order) -> Accept.  ``spectrum`` is never modified;
    :meth:`accept_calibration` returns (and, with a main window, displays) a recalibrated copy."""

    def __init__(self, parent=None, spectrum=None, main_window=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.spectrum = spectrum
        self.main_window = main_window
        self.proposal: Optional[cal.SourceCalibration] = None
        self.points: list[cal.CalibrationPoint] = []
        self.fit: Optional[cal.CalibrationFit] = None
        self.validation: Optional[cal.CalibrationValidation] = None
        self.result_spectrum = None
        self.last_error = ""
        self._base_points: list[cal.CalibrationPoint] = []
        self._lines: list = []
        self._fitted_peaks = None
        self._user_excluded: dict[tuple, str] = {}
        self._source_at_proposal = ""
        self._order_at_proposal = None
        self._busy = False
        self._filling = False
        self.setWindowTitle(ctr("cal_title"))
        self.resize(1080, 760)
        lay = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel(ctr("cal_spectrum")))
        name = ""
        if spectrum is not None:
            name = i18n.bidi_path(spectrum.source_path) if spectrum.source_path else ltr(spectrum.sample_id)
        self.spec_label = QLabel(name or i18n.tr("none"))
        row.addWidget(self.spec_label, 1)
        lay.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel(ctr("cal_source")))
        self.source_edit = QLineEdit()
        self.source_edit.setLayoutDirection(Qt.LeftToRight)
        self.source_edit.setToolTip(ctr("tip_source"))
        self.source_edit.setPlaceholderText("Eu-152  ·  Co-60,Cs-137  ·  mixed  ·  background")
        self.source_edit.textChanged.connect(self._update_buttons)
        row.addWidget(self.source_edit, 2)
        row.addWidget(QLabel(ctr("cal_order")))
        self.order_combo = QComboBox()
        self.order_combo.addItem(ctr("cal_order_auto"), None)
        for o in (1, 2, 3):
            self.order_combo.addItem(str(o), o)
        self.order_combo.currentIndexChanged.connect(self._order_changed)
        row.addWidget(self.order_combo)
        self.btn_propose = QPushButton(ctr("cal_propose"))
        self.btn_propose.setDefault(True)
        self.btn_propose.clicked.connect(self.propose)
        row.addWidget(self.btn_propose)
        lay.addLayout(row)
        self.hint = QLabel(ctr("cal_hint"))
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

        split = QSplitter(Qt.Vertical)
        box = QGroupBox(ctr("cal_points_group"))
        bl = QVBoxLayout(box)
        self.table = QTableWidget(0, len(POINT_COLS))
        self.table.setHorizontalHeaderLabels([ctr(k) for k in POINT_COLS])
        self.table.horizontalHeaderItem(0).setToolTip(ctr("tip_col_used"))
        self.table.horizontalHeaderItem(6).setToolTip(ctr("tip_col_loo"))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.itemChanged.connect(self._item_changed)
        bl.addWidget(self.table)
        split.addWidget(box)

        lower = QWidget()
        ll = QHBoxLayout(lower)
        ll.setContentsMargins(0, 0, 0, 0)
        cbox = QGroupBox(ctr("cal_coeffs_group"))
        cl = QVBoxLayout(cbox)
        self.energy_label = QLabel(ctr("cal_energy") + " " + i18n.tr("none"))
        self.energy_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.energy_label.setWordWrap(True)
        cl.addWidget(self.energy_label)
        self.rms_label = QLabel("")
        self.rms_label.setWordWrap(True)
        cl.addWidget(self.rms_label)
        self.fwhm_label = QLabel(ctr("cal_fwhm") + " " + i18n.tr("none"))
        self.fwhm_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.fwhm_label.setWordWrap(True)
        cl.addWidget(self.fwhm_label)
        self.apply_fwhm = QCheckBox(ctr("cal_apply_fwhm"))
        self.apply_fwhm.setToolTip(ctr("tip_apply_fwhm"))
        self.apply_fwhm.setEnabled(False)
        cl.addWidget(self.apply_fwhm)
        cl.addStretch(1)
        ll.addWidget(cbox, 2)
        vbox = QGroupBox(ctr("cal_validation_group"))
        vl = QVBoxLayout(vbox)
        self.state_label = QLabel(ctr("cal_no_proposal"))
        f = self.state_label.font()
        f.setBold(True)
        self.state_label.setFont(f)
        vl.addWidget(self.state_label)
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        vl.addWidget(self.summary_label)
        self.counts_label = QLabel("")
        vl.addWidget(self.counts_label)
        vl.addWidget(QLabel(ctr("cal_engine_messages")))
        self.messages = QListWidget()
        self.messages.setLayoutDirection(Qt.LeftToRight)     # engine text is English
        self.messages.setWordWrap(True)
        vl.addWidget(self.messages, 1)
        self.blocked_label = QLabel(ctr("val_blocked"))
        self.blocked_label.setWordWrap(True)
        self.blocked_label.setStyleSheet("color: #c62828;")
        self.blocked_label.setVisible(False)
        vl.addWidget(self.blocked_label)
        ll.addWidget(vbox, 3)
        split.addWidget(lower)
        split.setSizes([420, 300])
        lay.addWidget(split, 1)

        row = QHBoxLayout()
        self.status_label = QLabel("")
        row.addWidget(self.status_label, 1)
        self.btn_accept = QPushButton(ctr("cal_accept"))
        self.btn_accept.clicked.connect(self.accept_calibration)
        row.addWidget(self.btn_accept)
        b = QPushButton(ctr("cal_cancel"))
        b.clicked.connect(self.reject)
        row.addWidget(b)
        lay.addLayout(row)
        self._update_buttons()

    # ------------------------------------------------------------------ state
    @property
    def busy(self) -> bool:
        return self._busy

    def order(self) -> Optional[int]:
        return self.order_combo.currentData()

    def can_accept(self) -> bool:
        return (self.proposal is not None and self.fit is not None and self.validation is not None
                and self.validation.ok and not self._busy
                and self.source_edit.text().strip() == self._source_at_proposal)

    def _update_buttons(self, *_):
        self.btn_propose.setEnabled(not self._busy and self.spectrum is not None)
        self.btn_accept.setEnabled(self.can_accept())
        has_errors = self.validation is not None and not self.validation.ok
        self.blocked_label.setVisible(has_errors)
        if self.proposal is not None and self.source_edit.text().strip() != self._source_at_proposal:
            self.status_label.setText(ctr("source_changed"))
        elif not self._busy:
            self.status_label.setText("")

    # ------------------------------------------------------------------ propose (worker thread)
    def propose(self) -> bool:
        if self.spectrum is None or self._busy:
            return False
        source = self.source_edit.text().strip()
        if not source:
            self.message(ctr("no_source"))
            return False
        try:
            lines = cal.source_lines(source)
        except KeyError as exc:
            self.message(ctr("bad_source", msg=str(exc).strip("'\"")))
            return False
        spec, order = self.spectrum, self.order()

        def work():
            sc = cal.calibrate_from_source(spec, source, order=order)
            try:          # engine peaks for the re-validation after a review change
                fitted = cal._fitted_peaks(spec, sc.coeffs)
            except Exception:
                fitted = None
            return sc, fitted, lines, source, order

        self._busy = True
        self.last_error = ""
        self.status_label.setText(ctr("cal_running"))
        self._update_buttons()
        start_call(self, work, self._on_proposed, self._on_failed)
        return True

    def _on_proposed(self, result) -> None:
        sc, fitted, lines, source, order = result
        self._busy = False
        self.proposal = sc
        self._fitted_peaks = fitted
        self._lines = lines
        self._source_at_proposal = source
        self._order_at_proposal = order
        self._user_excluded = {}
        self._base_points = copy.deepcopy(sc.points)
        self.points, self.fit, self.validation = sc.points, sc.fit, sc.validation
        self.status_label.setText("")
        self._show()

    def _on_failed(self, msg: str) -> None:
        self._busy = False
        self.last_error = msg
        self.status_label.setText("")
        self._update_buttons()
        self.message(ctr("propose_failed", msg=msg))

    # ------------------------------------------------------------------ review
    def _order_changed(self, *_):
        if self.proposal is not None and not self._busy:
            self.refit()

    def set_point_used(self, row: int, used: bool, reason: Optional[str] = None) -> bool:
        """Include / exclude point `row` (a reason is required to exclude) and refit.
        Returns True when the fit was updated."""
        if not 0 <= row < len(self.points):
            return False
        p = self.points[row]
        key = _key(p)
        before = dict(self._user_excluded)
        if not used:
            if reason is None:
                reason = self.ask_reason(p.label)
            if reason is None or not reason.strip():
                if reason is not None:
                    self.message(ctr("reason_required"))
                self._show()                 # restores the tick
                return False
            self._user_excluded[key] = reason.strip()
        else:
            self._user_excluded.pop(key, None)
        ok = self.refit()
        if not ok:                           # e.g. fewer than 2 points left: keep the previous review
            self._user_excluded = before
            self._show()
        elif used:
            q = next((q for q in self.points if _key(q) == key), None)
            if q is not None and not q.used:
                self.message(ctr("auto_excluded_again", label=ltr(q.label), reason=q.reason))
        return ok

    def refit(self) -> bool:
        """Refit the reviewed points (user exclusions kept, automatic exclusions re-tested)."""
        if self.proposal is None:
            return False
        pts = copy.deepcopy(self._base_points)
        for p in pts:
            why = self._user_excluded.get(_key(p))
            p.used, p.reason = (False, USER_EXCLUDED + why) if why is not None else (True, "")
            p.loo_residual_kev = None
        det = self.validation.detector_type if self.validation is not None else ""
        try:
            fit, p_test, chi2r = cal.fit_points(pts, order=self.order(), det=det)
            val = cal.validate_calibration(self.spectrum, fit, pts, self._lines, p_test, chi2r,
                                           self._fitted_peaks)
        except Exception as exc:
            self.message(ctr("refit_failed", msg=str(exc)))
            self._show()                     # the last valid fit stays displayed
            return False
        self.points, self.fit, self.validation = pts, fit, val
        self._show()
        return True

    def _item_changed(self, it: QTableWidgetItem) -> None:
        if self._filling or it.column() != 0:
            return
        row, used = it.row(), it.checkState() == Qt.Checked
        # deferred: the refit rebuilds the table, which must not happen inside the item's own signal
        QTimer.singleShot(0, lambda: self.set_point_used(row, used))

    # ------------------------------------------------------------------ display
    def _show(self) -> None:
        self._filling = True
        try:
            self.table.setRowCount(len(self.points))
            for r, p in enumerate(self.points):
                use = QTableWidgetItem()
                use.setFlags((use.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
                use.setCheckState(Qt.Checked if p.used else Qt.Unchecked)
                use.setToolTip(ctr("tip_col_used"))
                self.table.setItem(r, 0, use)
                self.table.setItem(r, 1, _item(p.nuclide, Qt.AlignCenter))
                self.table.setItem(r, 2, _item(_f(p.energy, ".3f")))
                self.table.setItem(r, 3, _item(_f(p.channel, ".3f")))
                self.table.setItem(r, 4, _item(_f(p.channel_unc, ".3f")))
                self.table.setItem(r, 5, _item(_f(p.residual_kev, "+.3f")))
                self.table.setItem(r, 6, _item(_f(p.loo_residual_kev, "+.3f"), tip=ctr("tip_col_loo")))
                self.table.setItem(r, 7, _item(_f(p.significance, ".1f")))
                why = self._user_excluded.get(_key(p))
                reason = ctr("excluded_by_user", reason=why) if why is not None else p.reason
                self.table.setItem(r, 8, _item(reason, Qt.AlignLeft | Qt.AlignVCenter, tip=reason))
        finally:
            self._filling = False
        fit, v, sc = self.fit, self.validation, self.proposal
        if fit is not None:
            self.energy_label.setText(ctr("cal_energy") + " " + coeffs_text(fit.coeffs))
            self.rms_label.setText(ctr("cal_rms", rms=ltr(_f(fit.rms, ".4f")),
                                       max=ltr(_f(fit.max_abs_residual, ".4f")), dof=ltr(fit.dof)))
        has_fwhm = sc is not None and sc.fwhm_fit is not None
        self.fwhm_label.setText(ctr("cal_fwhm") + " "
                                + (coeffs_text(sc.fwhm_fit.coeffs) if has_fwhm else i18n.tr("none")))
        self.apply_fwhm.setEnabled(has_fwhm)
        if not has_fwhm:
            self.apply_fwhm.setChecked(False)
        self.messages.clear()
        if v is not None:
            self.state_label.setText(ctr("val_ok") if v.ok else ctr("val_not_ok"))
            self.state_label.setStyleSheet("color: #2e7d32;" if v.ok else "color: #c62828;")
            lo, hi = v.range_kev or (None, None)
            self.summary_label.setText(ctr(
                "val_summary", n=ltr(v.n_used), order=ltr(v.order),
                p=ltr(_f(v.order_test_p, ".3g")), chi2=ltr(_f(v.chi2_reduced, ".3g")),
                lo=ltr(_f(lo, ".1f")), hi=ltr(_f(hi, ".1f")), ext=ltr(f"{100 * v.extrapolated_fraction:.0f}")))
            self.counts_label.setText(ctr("val_errors", n=len(v.errors)) + "   "
                                      + ctr("val_warnings", n=len(v.warnings)))
            for e in v.errors:
                self.messages.addItem("ERROR: " + e)
                self.messages.item(self.messages.count() - 1).setForeground(QColor("#c62828"))
            for w in v.warnings:
                self.messages.addItem("Warning: " + w)
            if not v.errors and not v.warnings:
                self.messages.addItem(ctr("val_no_messages"))
        self._update_buttons()

    # ------------------------------------------------------------------ accept
    def note(self) -> str:
        """English record stored with the spectrum (``extra['recalibrated']``)."""
        used = [p for p in self.points if p.used]
        out = (f"energy calibration from source {self._source_at_proposal}: {len(used)} points, "
               f"order {self.fit.order}, reviewed in the calibration dialog")
        excl = [f"{p.label} ({p.reason})" for p in self.points if not p.used]
        return out + ("; excluded " + "; ".join(excl) if excl else "")

    def accept_calibration(self):
        """Apply the reviewed calibration to a copy of the spectrum (counts untouched).
        Returns the new spectrum, or None when accepting is not allowed."""
        if not self.can_accept():
            if self.validation is not None and not self.validation.ok:
                self.message(ctr("val_blocked"))
            return None
        fwhm = (self.proposal.fwhm_fit.coeffs
                if self.apply_fwhm.isChecked() and self.proposal.fwhm_fit is not None else None)
        new = cal.apply_calibration(self.spectrum, self.fit.coeffs, fwhm, note=self.note())
        new.extra["calibration_validation"] = self.validation.report()
        self.result_spectrum = new
        win = self.main_window
        if win is not None and replace_displayed_spectrum(win, new):
            lo, hi = self.validation.range_kev or (0.0, 0.0)
            win.statusBar().showMessage(ctr("status_cal_applied", n=ltr(self.validation.n_used),
                                            order=ltr(self.fit.order), lo=ltr(f"{lo:.1f}"),
                                            hi=ltr(f"{hi:.1f}")), 15000)
        self.accept()
        return new


# ===================================================================== drift check
class DriftDialog(_MessageMixin, QDialog):
    """Run ``check_drift`` and show its report; *Apply Proposed Correction...* asks first."""

    def __init__(self, parent=None, spectrum=None, main_window=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.spectrum = spectrum
        self.main_window = main_window
        self.result: Optional[cal.DriftCheck] = None
        self.result_spectrum = None
        self.last_error = ""
        self._busy = False
        self.setWindowTitle(ctr("drift_title"))
        self.resize(900, 640)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(ctr("drift_ref")))
        self.ref_edit = QLineEdit()
        self.ref_edit.setLayoutDirection(Qt.LeftToRight)
        self.ref_edit.setPlaceholderText(ctr("drift_ref_placeholder"))
        self.ref_edit.setToolTip(ctr("tip_drift_ref"))
        row.addWidget(self.ref_edit, 1)
        self.btn_check = QPushButton(ctr("drift_check"))
        self.btn_check.setDefault(True)
        self.btn_check.clicked.connect(self.check)
        row.addWidget(self.btn_check)
        lay.addLayout(row)
        self.state_label = QLabel("")
        f = self.state_label.font()
        f.setBold(True)
        self.state_label.setFont(f)
        self.state_label.setWordWrap(True)
        lay.addWidget(self.state_label)

        box = QGroupBox(ctr("drift_lines_group"))
        bl = QVBoxLayout(box)
        self.table = QTableWidget(0, len(DRIFT_COLS))
        self.table.setHorizontalHeaderLabels([ctr(k) for k in DRIFT_COLS])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        bl.addWidget(self.table)
        lay.addWidget(box, 2)
        box = QGroupBox(ctr("drift_excluded_group"))
        bl = QVBoxLayout(box)
        self.excluded = QListWidget()
        self.excluded.setLayoutDirection(Qt.LeftToRight)      # engine reasons are English
        bl.addWidget(self.excluded)
        lay.addWidget(box, 1)
        box = QGroupBox(ctr("drift_coeffs_group"))
        bl = QVBoxLayout(box)
        self.current_label = QLabel("")
        self.current_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.proposed_label = QLabel("")
        self.proposed_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bl.addWidget(self.current_label)
        bl.addWidget(self.proposed_label)
        lay.addWidget(box)
        lay.addWidget(QLabel(ctr("drift_engine")))
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setLayoutDirection(Qt.LeftToRight)
        self.report.setMaximumHeight(120)
        lay.addWidget(self.report)
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_apply = QPushButton(ctr("drift_apply"))
        self.btn_apply.clicked.connect(self.apply_correction)
        row.addWidget(self.btn_apply)
        b = QPushButton(ctr("drift_close"))
        b.clicked.connect(self.reject)
        row.addWidget(b)
        lay.addLayout(row)
        self._show()

    @property
    def busy(self) -> bool:
        return self._busy

    def check(self) -> bool:
        if self.spectrum is None or self._busy:
            return False
        spec = self.spectrum
        text = self.ref_edit.text().strip()
        if text:
            try:
                cal.source_lines(text)
            except KeyError as exc:
                self.message(ctr("bad_source", msg=str(exc).strip("'\"")))
                return False
        self._busy = True
        self.last_error = ""
        self.result = None
        self.state_label.setText(ctr("drift_running"))
        self._show()
        start_call(self, lambda: cal.check_drift(spec, text or None), self._on_done, self._on_failed)
        return True

    def _on_done(self, r) -> None:
        self._busy = False
        self.result = r
        self._show()

    def _on_failed(self, msg: str) -> None:
        self._busy = False
        self.last_error = msg
        self.state_label.setText("")
        self._show()
        self.message(ctr("drift_failed", msg=msg))

    def summary(self) -> str:
        r = self.result
        if r is None:
            return ""
        state = ctr("drift_detected") if r.detected else ctr("drift_none")
        if r.correction is None:
            return f"{state}: {r.message}"
        a, b = r.correction
        return ctr("drift_summary", state=state, n=ltr(len(r.points)), gain=ltr(f"{(b - 1) * 100:+.3f}"),
                   off=ltr(f"{a:+.2f}"), fixed=ctr("drift_offset_fixed") if a == 0.0 else "",
                   kev=ltr(f"{r.max_shift_kev:.2f}"), fwhm=ltr(f"{r.max_shift_fwhm:.2f}"),
                   sig=ltr(f"{r.max_shift_sigma:.1f}"))

    def _show(self) -> None:
        r = self.result
        spec = self.spectrum
        self.btn_check.setEnabled(spec is not None and not self._busy)
        self.current_label.setText(ctr("drift_current") + " "
                                   + coeffs_text(spec.energy_coeffs if spec is not None else None))
        if r is None:
            self.table.setRowCount(0)
            self.excluded.clear()
            self.proposed_label.setText(ctr("drift_proposed") + " " + ctr("drift_none_proposed"))
            self.report.setPlainText("")
            self.btn_apply.setEnabled(False)
            return
        self.state_label.setText(self.summary())
        self.state_label.setStyleSheet("color: #c62828;" if r.detected else "color: #2e7d32;")
        self.table.setRowCount(len(r.points))
        for k, (name, e_ref, e_meas, sig) in enumerate(r.points):
            self.table.setItem(k, 0, _item(name, Qt.AlignCenter))
            self.table.setItem(k, 1, _item(f"{e_ref:.3f}"))
            self.table.setItem(k, 2, _item(f"{e_meas:.3f}"))
            self.table.setItem(k, 3, _item(ltr(f"{e_meas - e_ref:+.3f} ± {sig:.3f}")))
        self.excluded.clear()
        for name, e, why in r.excluded:
            self.excluded.addItem(f"{name} {e:.1f} keV: {why}")
        if not r.excluded:
            self.excluded.addItem(ctr("drift_no_excluded"))
        self.proposed_label.setText(ctr("drift_proposed") + " " + (coeffs_text(r.proposed_coeffs)
                                    if r.proposed_coeffs else ctr("drift_none_proposed")))
        self.report.setPlainText(r.report())
        self.btn_apply.setEnabled(bool(r.proposed_coeffs))

    def apply_correction(self):
        """Apply the proposed coefficients after an explicit confirmation.
        Returns the corrected copy of the spectrum, or None (nothing changed)."""
        r = self.result
        if r is None or not r.proposed_coeffs or self.spectrum is None:
            return None
        text = ctr("drift_confirm", old=coeffs_text(self.spectrum.energy_coeffs),
                   new=coeffs_text(r.proposed_coeffs))
        if not r.detected:
            text = ctr("drift_confirm_nodrift") + "\n\n" + text
        if not self.confirm(ctr("drift_confirm_title"), text):
            return None
        a, b = r.correction if r.correction else (0.0, 1.0)
        note = (f"drift correction from check_drift: gain {(b - 1) * 100:+.4f} %, offset {a:+.3f} keV, "
                f"{len(r.points)} reference lines" + ("" if r.detected else " (no significant drift)"))
        new = cal.apply_calibration(self.spectrum, r.proposed_coeffs, note=note)
        self.result_spectrum = new
        win = self.main_window
        if win is not None and replace_displayed_spectrum(win, new):
            win.statusBar().showMessage(ctr("status_drift_applied"), 15000)
        self.spectrum = new
        self.result = None           # the report belonged to the old coefficients
        self._show()
        return new


# ===================================================================== main-window hooks
def _current(win):
    try:
        return win.current_spectrum()
    except Exception:
        return None


def open_calibration_dialog(win, modal: bool = True):
    spec = _current(win)
    if spec is None:
        win.show_info(ctr("need_spectrum"))
        return None
    dlg = CalibrationDialog(win, spec, win)
    if modal:
        dlg.exec()
    return dlg


def open_drift_dialog(win, modal: bool = True):
    spec = _current(win)
    if spec is None:
        win.show_info(ctr("need_spectrum"))
        return None
    if not spec.energy_coeffs:
        win.show_info(ctr("need_calibration"))
        return None
    dlg = DriftDialog(win, spec, win)
    if modal:
        dlg.exec()
    return dlg


def install_calibration_actions(win) -> None:
    """Analyze > Energy Calibration... / Check Calibration Drift... (``act_calibrate``, ``act_drift``)."""
    win.act_calibrate = QAction(win)
    win.act_calibrate.setObjectName("act_calibrate")
    win.act_drift = QAction(win)
    win.act_drift.setObjectName("act_drift")
    win.act_calibrate.triggered.connect(lambda _=False: open_calibration_dialog(win))
    win.act_drift.triggered.connect(lambda _=False: open_drift_dialog(win))
    menu = getattr(win, "menu_analyze", None)
    if menu is not None:
        menu.addSeparator()
        menu.addAction(win.act_calibrate)
        menu.addAction(win.act_drift)
    retranslate_calibration_actions(win)


def retranslate_calibration_actions(win) -> None:
    for name, k in (("act_calibrate", "cal"), ("act_drift", "drift")):
        a = getattr(win, name, None)
        if a is not None:
            a.setText(ctr("act_" + k))
            a.setToolTip(ctr("tip_" + k))
            a.setStatusTip(ctr("tip_" + k))


__all__ = ["CalibrationDialog", "DriftDialog", "install_calibration_actions", "retranslate_calibration_actions",
           "open_calibration_dialog", "open_drift_dialog", "replace_displayed_spectrum", "coeffs_text"]

"""Activity / MDA dialog and the Analyze-menu hook of the quantitative analysis.

Report/print API
----------------
After a calculation the main window holds ``MainWindow.quant_results``
(:class:`spectramaster.analysis.activity.QuantResults` or None).  A report module can use::

    from spectramaster.gui.quant_panel import quant_table
    header, rows = quant_table(win.quant_results)     # translated column titles + text rows
    win.quant_results.notes / .nuclides[i].budget     # details

``install_quant(win)`` adds the two menu entries; it is the only hook in ``app.py``.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QAction, QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateTimeEdit, QDialog,
                               QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..analysis import activity as act
from ..analysis import efficiency as eff
from . import i18n
from .efficiency_dialog import is_record_file, load_curve_file, status_text
from .geometry_editor import GeometryEditor
from .quant_strings import qtr

RES_COLS = ["res_col_nuclide", "res_col_lines", "res_col_net", "res_col_act", "res_col_spec", "res_col_mda",
            "res_col_mda_spec", "res_col_decision", "res_col_note"]
UNITS = ["kg", "g", "L", "mL"]
GEOMETRY_REFUSED = "the efficiency calibration belongs to another measurement geometry"
LTR = "⁦{}⁩"


def _g(v, d=4) -> str:
    if v is None:
        return ""
    if v == 0 or not math.isfinite(v):
        return f"{v:g}"
    return f"{v:.{d}g}"


def quant_table(res: Optional[act.QuantResults], lang: Optional[str] = None) -> tuple[list[str], list[list[str]]]:
    """Translated header and text rows of the results (for tables, reports and printing)."""
    if res is None:
        return [], []
    tr = (lambda k: i18n.tr_in(lang, "quant_" + k)) if lang else qtr
    header = [tr(k) for k in RES_COLS]
    unit = next((r.unit for r in res.nuclides if r.unit), "")
    if unit:
        header[4] += f" [{unit}]"
        header[6] += f" [{unit}]"
    rows = []
    for r in res.nuclides:
        k = r.key_line
        net = f"{k.net_area:.0f} ± {k.net_unc:.0f}" if (k and k.peak_found) else "-"
        if r.detected and r.activity is not None:
            a = f"{_g(r.activity)} ± {_g(r.u, 2)}"
            s = f"{_g(r.specific)} ± {_g(r.specific_U, 2)}" if r.specific is not None else ""
            dec = tr("res_detected")
        else:
            a = f"< {_g(r.mda, 3)}" if r.mda else "-"
            s = f"< {_g(r.specific_mda, 3)}" if r.specific_mda else ""
            dec = tr("res_lt_mda")
        rows.append([r.nuclide, r.lines_text, net, a, s, _g(r.mda, 3), _g(r.specific_mda, 3), dec, r.note])
    return header, rows


class ActivityDialog(QDialog):
    def __init__(self, parent=None, spectrum=None, settings=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.settings = settings
        self.spectrum = spectrum
        self.background = None
        self.results: Optional[act.QuantResults] = None
        self.setWindowTitle(qtr("act_title"))
        self.resize(1150, 700)
        lay = QVBoxLayout(self)
        form = QFormLayout()

        self.sample_label = QLabel(self._spec_text(spectrum))
        form.addRow(qtr("act_sample"), self.sample_label)

        row = QHBoxLayout()
        self.curve_combo = QComboBox()
        self.curve_combo.setEditable(False)
        self._fill_curves()
        row.addWidget(self.curve_combo, 1)
        b = QPushButton(qtr("eff_browse"))
        b.clicked.connect(self.browse_curve)
        row.addWidget(b)
        form.addRow(qtr("act_curve"), row)
        self.curve_status = QLabel("")
        self.curve_status.setWordWrap(True)
        form.addRow("", self.curve_status)
        self.curve_combo.currentIndexChanged.connect(self._curve_changed)

        row = QHBoxLayout()
        self.bkg_edit = QLineEdit()
        self.bkg_edit.setReadOnly(True)
        self.bkg_edit.setLayoutDirection(Qt.LeftToRight)
        self.bkg_edit.setPlaceholderText(qtr("act_bkg_none"))
        row.addWidget(self.bkg_edit, 1)
        self.bkg_mode = QComboBox()
        self.bkg_mode.addItem(qtr("act_bkg_peak"), "peak")
        self.bkg_mode.addItem(qtr("act_bkg_spectrum"), "spectrum")
        row.addWidget(self.bkg_mode)
        b = QPushButton(qtr("eff_browse"))
        b.clicked.connect(self.browse_background)
        row.addWidget(b)
        b = QPushButton(qtr("act_clear"))
        b.clicked.connect(lambda: self.set_background(None))
        row.addWidget(b)
        form.addRow(qtr("act_background"), row)

        row = QHBoxLayout()
        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setRange(0, 1e6)
        self.qty_spin.setDecimals(4)
        self.qty_spin.setSpecialValueText("—")
        row.addWidget(self.qty_spin)
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(UNITS)
        row.addWidget(self.unit_combo)
        row.addWidget(QLabel(qtr("act_quantity_unc")))
        self.qty_unc = QDoubleSpinBox()
        self.qty_unc.setRange(0, 100)
        self.qty_unc.setDecimals(2)
        row.addWidget(self.qty_unc)
        row.addStretch(1)
        form.addRow(qtr("act_quantity"), row)
        if spectrum is not None:
            q, u = spectrum.extra.get("quantity"), str(spectrum.extra.get("quantity_units", "")).strip().lower()
            try:
                if q and float(q) > 0:
                    self.qty_spin.setValue(float(q))
                    m = {"kg": "kg", "g": "g", "gr": "g", "l": "L", "ml": "mL"}.get(u)
                    if m:
                        self.unit_combo.setCurrentText(m)
            except (TypeError, ValueError):
                pass

        row = QHBoxLayout()
        self.ref_start = QCheckBox(qtr("act_ref_start"))
        self.ref_start.setChecked(True)
        row.addWidget(self.ref_start)
        self.ref_edit = QDateTimeEdit()
        self.ref_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.ref_edit.setCalendarPopup(True)
        self.ref_edit.setLayoutDirection(Qt.LeftToRight)
        st = spectrum.start_time if spectrum is not None and spectrum.start_time else None
        self.ref_edit.setDateTime(QDateTime(st) if st else QDateTime.currentDateTime())
        self.ref_edit.setEnabled(False)
        self.ref_start.toggled.connect(lambda on: self.ref_edit.setEnabled(not on))
        row.addWidget(self.ref_edit)
        row.addStretch(1)
        form.addRow(qtr("act_ref_date"), row)

        self.nuc_edit = QLineEdit(", ".join(self._saved_nuclides()))
        self.nuc_edit.setLayoutDirection(Qt.LeftToRight)
        form.addRow(qtr("act_nuclides"), self.nuc_edit)

        row = QHBoxLayout()
        self.method_combo = QComboBox()
        self.method_combo.addItem(qtr("act_method_key"), "key")
        self.method_combo.addItem(qtr("act_method_mean"), "mean")
        row.addWidget(self.method_combo)
        row.addWidget(QLabel(qtr("act_mda")))
        self.mda_combo = QComboBox()
        self.mda_combo.addItem(qtr("act_mda_currie"), "currie")
        self.mda_combo.addItem(qtr("act_mda_iso"), "iso11929")
        row.addWidget(self.mda_combo)
        row.addWidget(QLabel(qtr("act_atten")))
        self.att_spin = QDoubleSpinBox()
        self.att_spin.setRange(0.1, 10)
        self.att_spin.setDecimals(3)
        self.att_spin.setValue(1.0)
        row.addWidget(self.att_spin)
        row.addStretch(1)
        form.addRow(qtr("act_method"), row)
        lay.addLayout(form)

        self.geo_check = QCheckBox(qtr("act_geo_check"))
        self.geo_check.setToolTip(qtr("tip_act_geo_check"))
        lay.addWidget(self.geo_check)
        self.geo_box = QGroupBox(qtr("act_geo_group"))
        gl = QVBoxLayout(self.geo_box)
        self.geo = GeometryEditor(self.geo_box)
        gl.addWidget(self.geo)
        self.geo_box.setVisible(False)
        self.geo_check.toggled.connect(self.geo_box.setVisible)
        lay.addWidget(self.geo_box)
        self.last_error = ""

        row = QHBoxLayout()
        self.btn_calc = QPushButton(qtr("act_calc"))
        self.btn_calc.clicked.connect(self.calculate)
        row.addWidget(self.btn_calc)
        self.btn_export = QPushButton(qtr("act_export"))
        self.btn_export.clicked.connect(self.export)
        self.btn_export.setEnabled(False)
        row.addWidget(self.btn_export)
        row.addStretch(1)
        b = QPushButton(qtr("eff_close"))
        b.clicked.connect(self.accept)
        row.addWidget(b)

        self.notes_label = QLabel("")
        self.notes_label.setWordWrap(True)
        self.notes_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.notes_label)

        split = QSplitter(Qt.Vertical)
        self.table = QTableWidget(0, len(RES_COLS))
        self.table.setHorizontalHeaderLabels([qtr(k) for k in RES_COLS])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        split.addWidget(self.table)
        w = QWidget()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(QLabel(qtr("act_details")))
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setLayoutDirection(Qt.LeftToRight)
        wl.addWidget(self.details)
        split.addWidget(w)
        split.setSizes([420, 160])
        lay.addWidget(split, 1)
        lay.addLayout(row)
        self._curve_changed()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _spec_text(s) -> str:
        if s is None:
            return "—"
        name = Path(s.source_path).name if s.source_path else ""
        return f"{s.sample_id or name}  ({name}, {s.live_time or 0:g} s)"

    def _saved_nuclides(self) -> list[str]:
        if self.settings is not None:
            v = self.settings.get("quant/nuclides", "")
            if v:
                return [n.strip() for n in str(v).split(",") if n.strip()]
        return list(act.DEFAULT_NUCLIDES)

    def _fill_curves(self, select: Optional[str] = None) -> None:
        self.curve_combo.clear()
        for p in eff.list_curves():
            if not is_record_file(p):            # <stem>.calibration.json belongs to <stem>.json
                self.curve_combo.addItem(p.stem, str(p))
        last = select or (self.settings.get("quant/curve", "") if self.settings is not None else "")
        if last:
            i = self.curve_combo.findData(str(last))
            if i < 0 and Path(str(last)).is_file():
                self.curve_combo.addItem(Path(str(last)).stem, str(last))
                i = self.curve_combo.count() - 1
            if i >= 0:
                self.curve_combo.setCurrentIndex(i)

    def set_curve_path(self, path) -> None:
        self._fill_curves(str(path))

    def browse_curve(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, qtr("act_curve"), str(eff.default_curve_dir()), "JSON (*.json)")
        if path:
            self.set_curve_path(path)

    def browse_background(self) -> None:
        folder = self.settings.folder("open") if self.settings is not None else ""
        path, _ = QFileDialog.getOpenFileName(self, qtr("act_background"), folder)
        if path:
            self.load_background(path)

    def load_background(self, path) -> bool:
        from ..convert import read_spectra
        try:
            spectra, _f = read_spectra(Path(path))
        except Exception as exc:
            QMessageBox.warning(self, qtr("act_title"), qtr("act_failed", msg=str(exc)))
            return False
        s = spectra[0]
        s.source_path = s.source_path or str(path)
        self.set_background(s)
        return True

    def set_background(self, spectrum) -> None:
        self.background = spectrum
        self.bkg_edit.setText("" if spectrum is None else (
            i18n.bidi_path(spectrum.source_path) if spectrum.source_path else spectrum.sample_id))
        self.bkg_edit.setToolTip("" if spectrum is None else (spectrum.source_path or ""))
        self.bkg_edit.setCursorPosition(0)

    def options(self) -> act.ActivityOptions:
        ref = None
        if not self.ref_start.isChecked():
            ref = self.ref_edit.dateTime().toPython()
        q = self.qty_spin.value()
        return act.ActivityOptions(
            nuclides=[n.strip() for n in self.nuc_edit.text().replace(";", ",").split(",") if n.strip()],
            method=self.method_combo.currentData(), ref_date=ref, quantity=q if q > 0 else None,
            quantity_unit=self.unit_combo.currentText(), quantity_rel_unc=self.qty_unc.value() / 100.0,
            attenuation=self.att_spin.value(), bkg_mode=self.bkg_mode.currentData(),
            mda_method=self.mda_combo.currentData(), geometry=self.sample_geometry(),
            allow_geometry_mismatch=False)

    def sample_geometry(self):
        """The sample geometry to check the calibration against (None = not given)."""
        return self.geo.geometry() if self.geo_check.isChecked() else None

    def message(self, text: str) -> None:
        self.last_error = text
        QMessageBox.warning(self, qtr("act_title"), text)

    def confirm_mismatch(self, text: str) -> bool:
        """Ask whether to use a calibration of another geometry anyway (default: Cancel).
        Tests replace this method."""
        box = QMessageBox(QMessageBox.Warning, qtr("act_title"), qtr("act_geo_mismatch", reasons=text),
                          QMessageBox.NoButton, self)
        use = box.addButton(qtr("act_use_anyway"), QMessageBox.AcceptRole)
        cancel = box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(cancel)
        box.exec()
        return box.clickedButton() is use

    def _curve_changed(self, *_):
        path = self.curve_combo.currentData()
        if not path:
            self.curve_status.setText("")
            return
        try:
            c, _rec, _issues = load_curve_file(path)
        except Exception as exc:
            self.curve_status.setText(qtr("act_failed", msg=str(exc)))
            return
        geo = (c.geometry_record or {}).get("name") or c.geometry or qtr("act_geo_not_recorded")
        st = c.validation_status
        self.curve_status.setText(qtr("act_curve_status", status=status_text(st), geometry=geo))
        self.curve_status.setStyleSheet("color: %s;" % ("#2e7d32" if st == "validated" else "#e65100"))

    # ------------------------------------------------------------------ actions
    def calculate(self) -> Optional[act.QuantResults]:
        if self.spectrum is None or not self.spectrum.energy_coeffs:
            QMessageBox.warning(self, qtr("act_title"), qtr("act_no_spectrum"))
            return None
        path = self.curve_combo.currentData()
        if not path:
            QMessageBox.warning(self, qtr("act_title"), qtr("act_no_curve"))
            return None
        try:
            curve, _rec, issues = load_curve_file(path)
            opt = self.options()
        except Exception as exc:
            self.message(qtr("act_failed", msg=f"{type(exc).__name__}: {exc}"))
            return None
        try:
            try:
                self.results = act.compute_activities(self.spectrum, curve, opt, background=self.background)
            except ValueError as exc:
                if not str(exc).startswith(GEOMETRY_REFUSED):
                    raise
                reasons = str(exc).split("): ", 1)[-1]
                if not self.confirm_mismatch(reasons):
                    self.last_error = str(exc)
                    self.notes_label.setText(qtr("act_geo_refused", reasons=reasons))
                    self.notes_label.setStyleSheet("color: #c62828; font-weight: bold;")
                    return None
                opt.allow_geometry_mismatch = True       # the engine records it in the result notes
                self.results = act.compute_activities(self.spectrum, curve, opt, background=self.background)
        except Exception as exc:
            self.message(qtr("act_failed", msg=f"{type(exc).__name__}: {exc}"))
            return None
        self.results.notes.extend(issues)
        if self.settings is not None:
            self.settings.set("quant/curve", str(path))
            self.settings.set("quant/nuclides", ", ".join(opt.nuclides))
        self._show(self.results)
        self.btn_export.setEnabled(True)
        par = self.parent()
        if par is not None and hasattr(par, "quant_results"):
            par.quant_results = self.results
        return self.results

    def _show(self, res: act.QuantResults) -> None:
        header, rows = quant_table(res)
        self.table.setHorizontalHeaderLabels(header)
        self.table.setRowCount(0)
        for r, (vals, nr) in enumerate(zip(rows, res.nuclides)):
            self.table.insertRow(r)
            for c, v in enumerate(vals):
                it = QTableWidgetItem(LTR.format(v) if c in (2, 3, 4, 5, 6) and v else v)
                if c in (2, 3, 4, 5, 6):
                    it.setTextAlignment(Qt.AlignAbsolute | Qt.AlignRight | Qt.AlignVCenter)
                if c == 7:
                    it.setForeground(QBrush(QColor(20, 130, 40) if nr.detected else QColor(120, 120, 120)))
                self.table.setItem(r, c, it)
        lines = []
        for nr in res.nuclides:
            bud = ", ".join(f"{k} {v:.2f}" for k, v in nr.budget.items() if v > 0.005)
            tot = f"  total {100 * nr.u / abs(nr.activity):.2f} %" if nr.u and nr.activity else ""
            lines.append(f"{nr.nuclide}: {bud}{tot}" + (f"   [{nr.note}]" if nr.note else ""))
        lines += [f"note: {n}" for n in res.notes]
        lines.append(qtr("act_notes_tcs"))
        self.details.setPlainText("\n".join(lines))
        self._show_notes(res.notes)

    def _show_notes(self, notes) -> None:
        """The calibration / geometry notes of the results, translated, above the table."""
        out, severe = [], False
        for n in notes:
            if n.startswith("efficiency calibration") and "not independently validated" in n:
                out.append(qtr("act_note_unvalidated"))
            elif n.startswith("geometry mismatch accepted"):
                out.append(qtr("act_note_mismatch", text=n.split("): ", 1)[-1]))
                severe = True
            elif n.startswith("calibration geometry not recorded"):
                out.append(qtr("act_note_geo_unrecorded"))
            elif n.startswith("sample geometry not given"):
                out.append(qtr("act_note_geo_not_given"))
            elif "treated as unvalidated" in n:
                out.append(qtr("act_note_record", text=n))
        self.notes_label.setText("\n".join("\u26a0 " + t for t in out))
        self.notes_label.setStyleSheet("color: %s; font-weight: bold;" % ("#c62828" if severe else "#e65100"))

    def export(self, path: Optional[str] = None) -> Optional[Path]:
        if self.results is None:
            return None
        if not path:
            folder = self.settings.folder("export") if self.settings is not None else ""
            stem = Path(self.spectrum.source_path).stem if self.spectrum is not None and self.spectrum.source_path else "activity"
            path, _ = QFileDialog.getSaveFileName(self, qtr("act_export"), str(Path(folder) / f"{stem}_activity.xlsx"),
                                                  "Excel (*.xlsx);;CSV (*.csv)")
            if not path:
                return None
        return act.export_results(path, self.results)


# ---------------------------------------------------------------------- main-window hook
def install_quant(win) -> None:
    """Add 'Efficiency calibration...' and 'Activity calculation...' to the Analyze menu."""
    win.quant_results = None
    win.act_effcal = QAction(win)
    win.act_activity = QAction(win)
    win.act_effcal.triggered.connect(lambda: open_efficiency_dialog(win))
    win.act_activity.triggered.connect(lambda: open_activity_dialog(win))
    menu = getattr(win, "menu_analyze", None)
    if menu is not None:
        menu.addSeparator()
        menu.addAction(win.act_effcal)
        menu.addAction(win.act_activity)
        menu.aboutToShow.connect(lambda: retranslate_quant(win))
    retranslate_quant(win)


def retranslate_quant(win) -> None:
    for a, k in ((win.act_effcal, "effcal"), (win.act_activity, "activity")):
        a.setText(qtr("act_" + k))
        a.setStatusTip(qtr("tip_" + k))
        a.setToolTip(qtr("tip_" + k))


def _current(win):
    try:
        return win.current_spectrum()
    except Exception:
        return None


def open_efficiency_dialog(win, modal: bool = True):
    from .efficiency_dialog import EfficiencyDialog
    dlg = EfficiencyDialog(win, _current(win), getattr(win, "settings", None))
    if modal:
        dlg.exec()
    return dlg


def open_activity_dialog(win, modal: bool = True):
    dlg = ActivityDialog(win, _current(win), getattr(win, "settings", None))
    if modal:
        dlg.exec()
    return dlg

"""Tools > Detector Acceptance Test... and Tools > Chi-Square Counting Test... (the engine is
analysis/detector_test.py; docs/baseline/detector_acceptance_protocol.md).  Both calculations take
well under 0.1 s and run on the interface thread."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (QDateTimeEdit, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QLabel, QMenu, QPlainTextEdit,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..analysis import detector_test as dt
from . import i18n
from .activity_input import ActivityInput, other_units
from .i18n import is_rtl, tr

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "act_acceptance": "Detector &Acceptance Test...",
        "act_chi2": "C&hi-Square Counting Test...",
        "da_title": "Detector Acceptance Test (Co-60)",
        "da_geometry": "Co-60 point source at 25 cm on the detector axis (IEEE Std 325). The displayed "
                       "spectrum is used.",
        "da_activity": "Source activity (0 = no efficiency):",
        "da_activity_u": "Activity uncertainty (%):",
        "da_ref_date": "Activity reference date:",
        "da_co57": "Co-57 spectrum (122 keV width, optional):",
        "da_co57_choose": "Choose...", "da_co57_none": "none",
        "da_calculate": "Calculate", "da_copy": "Copy",
        "da_quantity": "Quantity", "da_value": "Value",
        "da_fwhm": "FWHM at {e}", "da_fwtm": "FWTM at {e}", "da_ratio": "FWTM / FWHM at {e}",
        "da_pc": "Peak-to-Compton ratio (1332.5 keV / 1040-1096 keV)",
        "da_releff": "Relative efficiency (vs 3x3 inch NaI)",
        "da_eff": "Absolute efficiency at 1332.5 keV",
        "da_net": "Net area at 1332.5 keV",
        "da_act_start": "Activity at the measurement start",
        "da_no_spectrum": "Open a Co-60 spectrum first.",
        "da_failed": "The test could not be calculated:\n{msg}",
        "c2_title": "Chi-Square Counting Test (IAEA-TECDOC-1599)",
        "c2_hint": "Repeated counts of the same source, one per line (10 or 20 counts):",
        "c2_n": "Number of counts", "c2_mean": "Mean", "c2_chi2": "Chi-square", "c2_dof": "Degrees of freedom",
        "c2_limits": "Acceptance range (5 % - 95 %)", "c2_range": "{low} to {high}", "c2_result": "Result",
        "c2_pass": "PASS: the counting system behaves statistically", "c2_fail": "FAIL: outside the acceptance range",
        "c2_bad_input": "Line {n} is not a number: {text}",
        "da_notes": "Notes",
    },
    "ar": {
        "act_acceptance": "اختبار &قبول الكاشف...",
        "act_chi2": "اختبار &مربع كاي للعدّ...",
        "da_title": "اختبار قبول الكاشف (Co-60)",
        "da_geometry": "مصدر نقطي من Co-60 على بعد 25 سم على محور الكاشف (IEEE Std 325). يُستخدم الطيف المعروض.",
        "da_activity": "نشاط المصدر (0 = بلا كفاءة):",
        "da_activity_u": "عدم يقين النشاط (%):",
        "da_ref_date": "التاريخ المرجعي للنشاط:",
        "da_co57": "طيف Co-57 (عرض ‎‪122 keV‬، اختياري):",
        "da_co57_choose": "اختيار...", "da_co57_none": "لا يوجد",
        "da_calculate": "احسب", "da_copy": "نسخ",
        "da_quantity": "الكمية", "da_value": "القيمة",
        "da_fwhm": "FWHM عند {e}", "da_fwtm": "FWTM عند {e}", "da_ratio": "FWTM / FWHM عند {e}",
        "da_pc": "نسبة القمة إلى كومبتون ‎‪(1332.5 keV / 1040-1096 keV)‬",
        "da_releff": "الكفاءة النسبية (مقارنة بكاشف NaI ‏3×3 بوصة)",
        "da_eff": "الكفاءة المطلقة عند ‎‪1332.5 keV‬",
        "da_net": "المساحة الصافية عند ‎‪1332.5 keV‬",
        "da_act_start": "النشاط عند بدء القياس",
        "da_no_spectrum": "افتح طيف Co-60 أولًا.",
        "da_failed": "تعذّر حساب الاختبار:\n{msg}",
        "c2_title": "اختبار مربع كاي للعدّ (IAEA-TECDOC-1599)",
        "c2_hint": "عدّات متكررة للمصدر نفسه، عدّة في كل سطر (10 أو 20 عدّة):",
        "c2_n": "عدد القراءات", "c2_mean": "المتوسط", "c2_chi2": "مربع كاي", "c2_dof": "درجات الحرية",
        "c2_limits": "مجال القبول (من 5 % إلى 95 %)", "c2_range": "من {low} إلى {high}", "c2_result": "النتيجة",
        "c2_pass": "ناجح: نظام العدّ يتصرّف إحصائيًا كما يُتوقَّع", "c2_fail": "مخفق: خارج مجال القبول",
        "c2_bad_input": "السطر {n} ليس رقمًا: {text}",
        "da_notes": "ملاحظات",
    },
}


def register() -> None:
    for lang, table in STRINGS.items():
        target = i18n.STRINGS.setdefault(lang, {})
        for k, v in table.items():
            target.setdefault(k, v)


register()


def _table(rows: list[tuple[str, str]]) -> QTableWidget:
    t = QTableWidget(0, 2)
    t.setHorizontalHeaderLabels([tr("da_quantity"), tr("da_value")])
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
    t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    t.setWordWrap(True)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    _fill(t, rows)
    return t


def _ltr(text: str) -> str:
    """Numbers with units kept left-to-right inside Arabic text: a left-to-right mark and embedding
    (Qt's text layout does not honour the Unicode isolates here)."""
    return "‎‪" + text + "‬"


def _fill(t: QTableWidget, rows: list[tuple[str, str]]) -> None:
    t.setRowCount(len(rows))
    for i, (k, v) in enumerate(rows):
        t.setItem(i, 0, QTableWidgetItem(k))
        t.setItem(i, 1, QTableWidgetItem(v))
    t.resizeRowsToContents()


def _text(rows: list[tuple[str, str]]) -> str:
    return "\n".join(f"{k}\t{v}" for k, v in rows)


def acceptance_rows(res: dt.AcceptanceResult, unit: str = "Bq") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for w in (res.width_1332, res.width_122):
        if w is None:
            continue
        e = _ltr(f"{w.energy:.1f} keV")
        rows.append((tr("da_fwhm", e=e), _ltr(f"{w.fwhm_kev:.3f} keV") if w.fwhm_kev else "-"))
        rows.append((tr("da_fwtm", e=e), _ltr(f"{w.fwtm_kev:.3f} keV") if w.fwtm_kev else "-"))
        rows.append((tr("da_ratio", e=e), f"{w.ratio:.3f}" if w.ratio else "-"))
    rows.append((tr("da_pc"), f"{res.peak_to_compton:.1f}" if res.peak_to_compton else "-"))
    r = res.relative_efficiency
    if r is not None:
        rows.append((tr("da_releff"), _ltr(f"{r.percent:.2f} % ± {r.u_total:.2f} %")))
        rows.append((tr("da_eff"), _ltr(f"{r.efficiency:.4e}")))
        rows.append((tr("da_net"), _ltr(f"{r.net_area:.0f} ± {r.net_unc:.0f}")))
        rows.append((tr("da_act_start"), _ltr(other_units(r.activity_bq, unit))))
    notes = [n for n in res.notes if n != dt.GEOMETRY_NOTE]       # the dialog states the geometry
    if notes:
        rows.append((tr("da_notes"), "; ".join(notes)))
    return rows


class AcceptanceDialog(QDialog):
    def __init__(self, spectrum, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("da_title"))
        self.setLayoutDirection(Qt.RightToLeft if is_rtl() else Qt.LeftToRight)
        self.spectrum = spectrum
        self.co57 = None
        self.outcome: Optional[dt.AcceptanceResult] = None
        lay = QVBoxLayout(self)
        info = QLabel(tr("da_geometry"))
        info.setWordWrap(True)
        lay.addWidget(info)
        form = QFormLayout()
        self.activity = ActivityInput()
        self.activity_u = QDoubleSpinBox()
        self.activity_u.setRange(0.0, 100.0)
        self.activity_u.setDecimals(2)
        self.ref_date = QDateTimeEdit(QDateTime.currentDateTime())
        self.ref_date.setCalendarPopup(True)
        self.ref_date.setDisplayFormat("yyyy-MM-dd HH:mm")
        row = QHBoxLayout()
        self.co57_label = QLabel(tr("da_co57_none"))
        b = QPushButton(tr("da_co57_choose"))
        b.clicked.connect(self._choose_co57)
        row.addWidget(self.co57_label, 1)
        row.addWidget(b)
        form.addRow(tr("da_activity"), self.activity)
        form.addRow(tr("da_activity_u"), self.activity_u)
        form.addRow(tr("da_ref_date"), self.ref_date)
        form.addRow(tr("da_co57"), row)
        lay.addLayout(form)
        self.table = _table([])
        lay.addWidget(self.table, 1)
        box = QDialogButtonBox(QDialogButtonBox.Close)
        self.btn_calc = box.addButton(tr("da_calculate"), QDialogButtonBox.ActionRole)
        self.btn_copy = box.addButton(tr("da_copy"), QDialogButtonBox.ActionRole)
        self.btn_calc.clicked.connect(self.calculate)
        self.btn_copy.clicked.connect(self.copy)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        self.resize(620, 480)

    def load_co57(self, path) -> None:
        from ..convert import read_spectra
        self.co57 = read_spectra(Path(path))[0][0]
        self.co57_label.setText(Path(path).name)

    def _choose_co57(self) -> None:
        p, _f = QFileDialog.getOpenFileName(self, tr("da_co57"))
        if p:
            try:
                self.load_co57(p)
            except Exception as exc:
                self._error(str(exc))

    def calculate(self) -> Optional[dt.AcceptanceResult]:
        a = self.activity.value_bq()
        ref = self.ref_date.dateTime().toPython() if a > 0 else None
        try:
            self.outcome = dt.acceptance_test(self.spectrum, a or None, a * self.activity_u.value() / 100.0, ref,
                                             self.co57)
        except Exception as exc:
            self._error(str(exc))
            return None
        _fill(self.table, acceptance_rows(self.outcome, self.activity.current_unit()))
        return self.outcome

    def copy(self) -> None:
        if self.outcome is not None:
            QGuiApplication.clipboard().setText(_text(acceptance_rows(self.outcome, self.activity.current_unit())))

    def _error(self, msg: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, tr("da_title"), tr("da_failed", msg=msg))


def parse_counts(text: str) -> list[float]:
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip().replace(",", "")
        if not s:
            continue
        try:
            out.append(float(s))
        except ValueError:
            raise ValueError(tr("c2_bad_input", n=n, text=line.strip())) from None
    return out


def chi2_rows(r: dt.ChiSquareResult) -> list[tuple[str, str]]:
    rows = [(tr("c2_n"), str(r.n)), (tr("c2_mean"), f"{r.mean:.6g}"), (tr("c2_chi2"), f"{r.chi2:.3f}"),
            (tr("c2_dof"), str(r.dof)), (tr("c2_limits"), tr("c2_range", low=f"{r.low:.3f}", high=f"{r.high:.3f}")),
            (tr("c2_result"), tr("c2_pass") if r.passed else tr("c2_fail"))]
    if r.note:
        rows.append((tr("da_notes"), r.note))
    return rows


class ChiSquareDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("c2_title"))
        self.setLayoutDirection(Qt.RightToLeft if is_rtl() else Qt.LeftToRight)
        self.outcome: Optional[dt.ChiSquareResult] = None
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr("c2_hint")))
        self.counts = QPlainTextEdit()
        self.counts.setLayoutDirection(Qt.LeftToRight)
        lay.addWidget(self.counts, 1)
        self.table = _table([])
        lay.addWidget(self.table, 1)
        box = QDialogButtonBox(QDialogButtonBox.Close)
        self.btn_calc = box.addButton(tr("da_calculate"), QDialogButtonBox.ActionRole)
        self.btn_copy = box.addButton(tr("da_copy"), QDialogButtonBox.ActionRole)
        self.btn_calc.clicked.connect(self.calculate)
        self.btn_copy.clicked.connect(self.copy)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        self.resize(480, 520)

    def calculate(self) -> Optional[dt.ChiSquareResult]:
        try:
            self.outcome = dt.chi_square_test(parse_counts(self.counts.toPlainText()))
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, tr("c2_title"), str(exc))
            return None
        _fill(self.table, chi2_rows(self.outcome))
        return self.outcome

    def copy(self) -> None:
        if self.outcome is not None:
            QGuiApplication.clipboard().setText(_text(chi2_rows(self.outcome)))


def open_acceptance(main_window) -> Optional[AcceptanceDialog]:
    sp = main_window.current_spectrum()
    if sp is None:
        main_window.show_error(tr("da_no_spectrum"))
        return None
    dlg = AcceptanceDialog(sp, main_window)
    dlg.show()
    main_window._acceptance_dialog = dlg
    return dlg


def open_chi2(main_window) -> ChiSquareDialog:
    dlg = ChiSquareDialog(main_window)
    dlg.show()
    main_window._chi2_dialog = dlg
    return dlg


def install_detector_test_menu(main_window) -> None:
    """Tools > Detector Acceptance Test... and Chi-Square Counting Test... (after Detector QC)."""
    menu = main_window.menuBar().findChild(QMenu, "menu_tools")
    if menu is None:
        return
    a1 = QAction(tr("act_acceptance"), main_window)
    a1.setObjectName("act_acceptance")
    a1.triggered.connect(lambda checked=False: open_acceptance(main_window))
    a2 = QAction(tr("act_chi2"), main_window)
    a2.setObjectName("act_chi2")
    a2.triggered.connect(lambda checked=False: open_chi2(main_window))
    menu.addAction(a1)
    menu.addAction(a2)
    main_window.act_acceptance, main_window.act_chi2 = a1, a2


def retranslate_detector_test_menu(main_window) -> None:
    for name, key in (("act_acceptance", "act_acceptance"), ("act_chi2", "act_chi2")):
        act = getattr(main_window, name, None)
        if act is not None:
            act.setText(tr(key))

"""Peak-search / nuclide-identification results dock and exports.

Codes only against the public contract of ``spectramaster.analysis``
(Peak, NuclideMatch, find_peaks, identify).
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from . import i18n
from . import identification_library as idl
from .i18n import tr

PEAK_COLS = ["pk_col_n", "pk_col_energy", "pk_col_channel", "pk_col_fwhm", "pk_col_net",
             "pk_col_cps", "pk_col_sig", "pk_col_nuclide"]
NUC_COLS = ["nuc_col_name", "nuc_col_conf", "nuc_col_half", "nuc_col_cat", "nuc_col_lines",
            "nuc_col_note"]
CATEGORIES = ("natural", "fission", "activation", "calibration", "medical", "industrial")


def engine_status() -> Optional[str]:
    """None when the analysis engine modules exist, else a short reason (no import done)."""
    try:
        for mod in ("spectramaster.analysis.peaks", "spectramaster.analysis.identify"):
            if importlib.util.find_spec(mod) is None:
                return f"{mod} not installed"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def category_text(cat: str) -> str:
    return i18n.category_label(cat)


class _Num(QTableWidgetItem):
    """Table item that sorts numerically on Qt.UserRole + 1."""

    def __init__(self, text: str, value: Optional[float]):
        super().__init__(text)
        self.setData(Qt.UserRole + 1, value if value is not None else float("-inf"))
        self.setTextAlignment(Qt.AlignAbsolute | Qt.AlignRight | Qt.AlignVCenter)

    def __lt__(self, other):
        try:
            return float(self.data(Qt.UserRole + 1)) < float(other.data(Qt.UserRole + 1))
        except (TypeError, ValueError):
            return super().__lt__(other)


def _fmt(v, f="{:.2f}") -> str:
    return "" if v is None else f.format(v)


def peak_row(i: int, pk) -> list[tuple[str, Optional[float]]]:
    net = "\u2066" + f"{pk.net_area:,.0f} ± {pk.net_area_unc:,.0f}" + "\u2069"   # LTR isolate (RTL UI)
    return [
        (str(i + 1), i + 1),
        (_fmt(pk.energy), pk.energy),
        (_fmt(pk.centroid), pk.centroid),
        (_fmt(pk.fwhm_kev), pk.fwhm_kev),
        (net, pk.net_area),
        (_fmt(pk.count_rate, "{:.4g}"), pk.count_rate),
        (_fmt(pk.significance, "{:.1f}"), pk.significance),
        ((pk.nuclide + (f"  ({pk.note})" if pk.note else "")).strip(), None),
    ]


def peak_info_text(pk) -> str:
    """One status-bar line about a found peak (MAESTRO Peak Info): position, width, net area,
    significance and its assignment."""
    pos = (f"{pk.energy:.2f} keV" if pk.energy is not None else tr("pk_channel", ch=f"{pk.centroid:.1f}"))
    width = (f"{pk.fwhm_kev:.2f} keV" if pk.fwhm_kev else f"{pk.fwhm:.1f} ch")
    text = tr("pk_info", pos=pos, fwhm=width, net=f"{pk.net_area:,.0f}", unc=f"{pk.net_area_unc:,.0f}",
              sig=f"{pk.significance:.1f}")
    if pk.nuclide:
        line = f" {pk.line_energy:.2f} keV" if pk.line_energy is not None else ""
        text += "  —  " + pk.nuclide + line + (f" ({pk.note})" if pk.note else "")
    else:
        text += "  —  " + tr("pk_unassigned")
    return "⁦" + text + "⁩" if i18n.is_rtl() else text


def expected_lines(m) -> list[float]:
    return sorted({float(e) for e, _ in m.matched} | {float(e) for e in m.missing})


def nuclide_row(m) -> list[tuple[str, Optional[float]]]:
    n_match = len(m.matched)
    n_exp = n_match + len(m.missing)
    return [
        (m.nuclide, None),
        (f"{100.0 * m.confidence:.0f} %", m.confidence),
        (i18n.ltr(m.half_life), None),          # "13.517 y" must not become "y 13.517"
        (category_text(m.category), None),
        (i18n.ltr(f"{n_match} / {n_exp}"), n_match / n_exp if n_exp else 0.0),
        (_nuclide_note(m), None),
    ]


def _nuclide_note(m) -> str:
    note = idl.strip_drift(m.note or "")      # the drift note is shown once, above the table
    parts = [note] if note else []
    series = getattr(m, "series", "") or ""
    if series and series not in note:
        parts.append(series)
    if getattr(m, "background", False):
        parts.append(tr("nuc_background"))
    return " · ".join(parts)


# ------------------------------------------------------------------------- export
def _meta_rows(spec, path_hint: str = "") -> list[tuple[str, str]]:
    if spec is None:
        return []
    from .info_panel import format_calibration
    return [
        ("file", spec.source_path or path_hint),
        ("sample_id", spec.sample_id),
        ("description", spec.description),
        ("detector", spec.detector),
        ("start", spec.start_time.isoformat(sep=" ") if spec.start_time else ""),
        ("live_time_s", "" if spec.live_time is None else f"{spec.live_time:g}"),
        ("real_time_s", "" if spec.real_time is None else f"{spec.real_time:g}"),
        ("channels", str(spec.num_channels)),
        ("energy_calibration", format_calibration(spec.energy_coeffs) if spec.energy_coeffs else "none"),
    ]


PEAK_HEADER = ["peak", "centroid_ch", "energy_keV", "fwhm_ch", "fwhm_keV", "net_area", "net_area_unc_1s",
               "gross_area", "background", "left_idx", "right_idx", "significance", "net_cps",
               "nuclide", "line_keV", "note"]
NUC_HEADER = ["nuclide", "confidence", "half_life", "category", "matched_lines", "expected_lines",
              "matched_keV", "missing_keV", "note"]


def _peak_values(i, pk) -> list:
    return [i + 1, round(pk.centroid, 4), None if pk.energy is None else round(pk.energy, 4),
            round(pk.fwhm, 4), None if pk.fwhm_kev is None else round(pk.fwhm_kev, 4),
            round(pk.net_area, 3), round(pk.net_area_unc, 3), round(pk.gross_area, 3),
            round(pk.background, 3), pk.left, pk.right, round(pk.significance, 3),
            None if pk.count_rate is None else pk.count_rate, pk.nuclide,
            pk.line_energy, pk.note]


def _nuc_values(m) -> list:
    return [m.nuclide, round(m.confidence, 4), m.half_life, m.category, len(m.matched),
            len(m.matched) + len(m.missing), " ".join(f"{e:g}" for e, _ in m.matched),
            " ".join(f"{e:g}" for e in m.missing), m.note]


def export_results(path, spectrum, peaks: Sequence, matches: Sequence) -> Path:
    """Write peaks + nuclides + spectrum metadata to .csv or .xlsx (by extension)."""
    path = Path(path)
    meta = _meta_rows(spectrum)
    if path.suffix.lower() == ".xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font
        wb = Workbook()
        ws = wb.active
        ws.title = "Spectrum"
        for k, v in meta:
            ws.append([k, v])
        for title, header, rows in (("Peaks", PEAK_HEADER, [_peak_values(i, p) for i, p in enumerate(peaks)]),
                                    ("Nuclides", NUC_HEADER, [_nuc_values(m) for m in matches])):
            s = wb.create_sheet(title)
            s.append(header)
            for c in s[1]:
                c.font = Font(bold=True)
            for r in rows:
                s.append(r)
            s.freeze_panes = "A2"
            for col in s.columns:
                width = max(len(str(c.value or "")) for c in col) + 2
                s.column_dimensions[col[0].column_letter].width = min(40, max(9, width))
        ws.column_dimensions["A"].width = 20
        ws.column_dimensions["B"].width = 60
        wb.save(path)
        return path
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        for k, v in meta:
            w.writerow([f"# {k}", v])
        w.writerow([])
        w.writerow(PEAK_HEADER)
        for i, pk in enumerate(peaks):
            w.writerow(["" if v is None else v for v in _peak_values(i, pk)])
        w.writerow([])
        w.writerow(NUC_HEADER)
        for m in matches:
            w.writerow(["" if v is None else v for v in _nuc_values(m)])
    return path


# ------------------------------------------------------------------------- widget
class AnalysisPanel(QWidget):
    peakActivated = Signal(object)          # Peak
    nuclideSelected = Signal(object)        # NuclideMatch or None
    exportRequested = Signal()
    libraryChanged = Signal(str)            # application library key

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        self.results_application: Optional[str] = None   # library of the displayed results
        self.peaks: list = []
        self.matches: list = []
        self.identified = True
        self.analysed = False                # True once results (possibly empty) were set
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 6)
        lay.setSpacing(4)
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet("QLabel { background: #fff4e0; border: 1px solid #f0c27a;"
                                  " border-radius: 4px; padding: 5px 8px; color: #6b4a0f; }")
        self.banner.hide()
        lay.addWidget(self.banner)
        top = QHBoxLayout()
        self.library_label = QLabel()
        top.addWidget(self.library_label)
        self.library_combo = QComboBox()
        for key in idl.CHOICES:
            self.library_combo.addItem(key, key)
        self.library_combo.setCurrentIndex(max(0, self.library_combo.findData(idl.stored_library(settings))))
        self.library_combo.currentIndexChanged.connect(self._library_changed)
        top.addWidget(self.library_combo)
        self.summary = QLabel()
        self.summary.setObjectName("infoLabel")
        top.addWidget(self.summary, 1)
        self.export_btn = QPushButton()
        self.export_btn.clicked.connect(self.exportRequested.emit)
        top.addWidget(self.export_btn)
        lay.addLayout(top)
        self.drift_label = QLabel()
        self.drift_label.setObjectName("driftLabel")
        self.drift_label.setWordWrap(True)
        self.drift_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.drift_label.setStyleSheet("QLabel { color: #b23c00; font-weight: bold; }")
        self.drift_label.hide()
        lay.addWidget(self.drift_label)
        self.tabs = QTabWidget()
        self.peak_table = self._table(len(PEAK_COLS))
        self.peak_table.itemDoubleClicked.connect(self._peak_double)
        self.nuc_table = self._table(len(NUC_COLS))
        self.nuc_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.nuc_table.itemSelectionChanged.connect(self._nuc_selected)
        self.tabs.addTab(self.peak_table, "")
        self.tabs.addTab(self.nuc_table, "")
        lay.addWidget(self.tabs, 1)
        self.retranslate()

    @staticmethod
    def _table(ncols: int) -> QTableWidget:
        t = QTableWidget(0, ncols)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        t.horizontalHeader().setStretchLastSection(True)
        t.setAlternatingRowColors(True)
        t.setSortingEnabled(True)
        return t

    def retranslate(self) -> None:
        self.peak_table.setHorizontalHeaderLabels([tr(k) for k in PEAK_COLS])
        self.nuc_table.setHorizontalHeaderLabels([tr(k) for k in NUC_COLS])
        self.export_btn.setText(tr("ana_export"))
        self.export_btn.setToolTip(tr("tip_ana_export"))
        self.library_label.setText(tr("idl_label"))
        self.library_combo.setToolTip(tr("idl_tip"))
        self.library_label.setToolTip(tr("idl_tip"))
        for i in range(self.library_combo.count()):
            self.library_combo.setItemText(i, idl.library_label(self.library_combo.itemData(i)))
        self._update_texts()
        if self.peaks or self.matches:
            self.set_results(self.peaks, self.matches, self.identified, self.results_application)

    def _update_texts(self) -> None:
        self.tabs.setTabText(0, tr("ana_tab_peaks", n=len(self.peaks)))
        self.tabs.setTabText(1, tr("ana_tab_nuclides", n=len(self.matches)))
        if self.peaks or self.matches or self.analysed:
            text = tr("ana_summary", p=len(self.peaks), n=len(self.matches))
            if self.results_application and self.identified:
                text += "   ·   " + tr("idl_header", name=idl.library_label(self.results_application, short=True))
                if self.results_application != self.application():
                    text += " " + tr("idl_rerun")
            self.summary.setText(text)
        else:
            self.summary.setText(tr("ana_none"))
        detail = idl.drift_detail(self.matches)
        self.drift_label.setText(idl.drift_text(detail) if detail is not None else "")
        self.drift_label.setVisible(detail is not None)
        self.export_btn.setEnabled(bool(self.peaks or self.matches))

    def clear(self) -> None:
        self.peaks, self.matches, self.identified = [], [], True
        self.analysed = False
        self.results_application = None
        self.peak_table.setRowCount(0)
        self.nuc_table.setRowCount(0)
        self.banner.hide()
        self._update_texts()

    def show_message(self, text: str) -> None:
        self.banner.setText(text)
        self.banner.setVisible(bool(text))

    # ------------------------------------------------------------ identification library
    def application(self) -> str:
        """The chosen identification library (analysis.library.APPLICATIONS key)."""
        return str(self.library_combo.currentData() or idl.GUI_DEFAULT)

    def set_application(self, application: str) -> None:
        i = self.library_combo.findData(application)
        if i >= 0:
            self.library_combo.setCurrentIndex(i)

    def _library_changed(self, *_):
        app = self.application()
        idl.store_library(self.settings, app)
        self._update_texts()
        self.libraryChanged.emit(app)

    def set_results(self, peaks: Sequence, matches: Sequence, identified: bool = True,
                    application: Optional[str] = None) -> None:
        """`application`: the library the matches were searched in (default: the current choice)."""
        self.results_application = application or self.application()
        self.peaks, self.matches, self.identified = list(peaks), list(matches), identified
        self.analysed = True
        self.banner.hide()
        if not identified:
            self.show_message(tr("ana_uncalibrated"))
        for table, rows, sort in ((self.peak_table, [peak_row(i, p) for i, p in enumerate(self.peaks)],
                                   (0, Qt.AscendingOrder)),
                                  (self.nuc_table, [nuclide_row(m) for m in self.matches],
                                   (1, Qt.DescendingOrder))):
            table.setSortingEnabled(False)
            table.clearSelection()
            table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, (text, val) in enumerate(row):
                    it = _Num(text, val) if val is not None else QTableWidgetItem(text)
                    if c == 0:
                        it.setData(Qt.UserRole, r)
                    table.setItem(r, c, it)
            table.horizontalHeader().setSortIndicator(*sort)
            table.setSortingEnabled(True)
        self.peak_table.setColumnHidden(1, not identified and all(p.energy is None for p in self.peaks))
        self._update_texts()

    def _row_index(self, table: QTableWidget, row: int) -> int:
        it = table.item(row, 0)
        return int(it.data(Qt.UserRole)) if it is not None else -1

    def _peak_double(self, item) -> None:
        i = self._row_index(self.peak_table, item.row())
        if 0 <= i < len(self.peaks):
            self.peakActivated.emit(self.peaks[i])

    def activate_peak_row(self, row: int) -> None:
        it = self.peak_table.item(row, 0)
        if it is not None:
            self._peak_double(it)

    def select_peak(self, peak) -> None:
        """Select (without activating) the table row of `peak` (keyboard peak indexing)."""
        from PySide6.QtCore import QItemSelectionModel
        i = next((k for k, p in enumerate(self.peaks) if p is peak), -1)
        for row in range(self.peak_table.rowCount()):
            if self._row_index(self.peak_table, row) == i:
                idx = self.peak_table.model().index(row, 0)
                self.peak_table.selectionModel().select(
                    idx, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                self.peak_table.scrollTo(idx)
                return

    def select_nuclide_row(self, r: int) -> None:
        from PySide6.QtCore import QItemSelectionModel
        idx = self.nuc_table.model().index(r, 0)
        self.nuc_table.selectionModel().select(idx, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)

    def selected_match(self):
        rows = {i.row() for i in self.nuc_table.selectedIndexes()}
        if not rows:
            return None
        i = self._row_index(self.nuc_table, min(rows))
        return self.matches[i] if 0 <= i < len(self.matches) else None

    def _nuc_selected(self) -> None:
        m = self.selected_match()
        matched_ids = {id(pk) for _, pk in m.matched} if m else set()
        tint = QBrush(QColor(194, 24, 91, 40))
        for r in range(self.peak_table.rowCount()):
            i = self._row_index(self.peak_table, r)
            on = 0 <= i < len(self.peaks) and id(self.peaks[i]) in matched_ids
            for c in range(self.peak_table.columnCount()):
                it = self.peak_table.item(r, c)
                if it is not None:
                    it.setBackground(tint if on else QBrush())
        self.nuclideSelected.emit(m)

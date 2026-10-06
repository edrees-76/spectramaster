"""Archive search window: index the original archive files in place (SQLite, see
``spectramaster.tools.archive_db``) and search them by text (Arabic-normalised), nuclides,
date, detector and folder.

Hooked into the main window by :func:`install_archive_search` (File menu entry) and
:func:`retranslate_archive_search`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtCore import (QAbstractTableModel, QDate, QModelIndex, QObject, QRectF, Qt, QThread, QTimer,
                            QUrl, Signal, Slot)
from PySide6.QtGui import QAction, QColor, QDesktopServices, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QCompleter, QDateEdit, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
                               QProgressBar, QPushButton, QSizePolicy, QSlider, QSplitter, QTableView,
                               QVBoxLayout, QWidget)

from ..tools.archive_db import (ArchiveIndex, ArchiveRow, canonical_nuclide, default_db_path, export_rows,
                                normalize_text, nuclide_names)
from . import i18n
from .i18n import STRINGS, tr

# ------------------------------------------------------------------------ strings
STRINGS["en"].update({
    "act_archive_search": "Archive &Search...",
    "tip_archive_search": "Search the spectrum archive by sample, text, nuclide, date or folder",
    "as_title": "Archive Search",
    "as_roots": "Archive folders",
    "as_add_root": "Add folder...",
    "as_remove_root": "Remove",
    "as_db": "Index database:",
    "as_db_change": "Change...",
    "as_build": "Build / update index",
    "as_cancel": "Cancel",
    "as_build_phase_list": "Listing files...",
    "as_build_phase_scan": "Reading metadata: {done} / {total}",
    "as_build_phase_analyse": "Analysing spectra: {done} / {total}",
    "as_eta": "about {t} left",
    "as_build_done": "Index updated: {new} new/changed spectra, {removed} removed, {analysed} analysed "
                     "({sec} s){cancel}",
    "as_build_cancelled": " — cancelled (run again to resume)",
    "as_build_failed": "Index build failed:\n{msg}",
    "as_no_roots": "Add at least one archive folder first.",
    "as_filters": "Filters",
    "as_text": "Text:",
    "as_text_tip": "Words in sample ID, description, comments, file or folder name (Arabic letter forms "
                   "and diacritics are ignored)",
    "as_nuclides": "Nuclides:",
    "as_nuc_add": "Add",
    "as_nuc_placeholder": "e.g. Cs-137",
    "as_nuc_mode_all": "all of them",
    "as_nuc_mode_any": "any of them",
    "as_confidence": "Min. confidence: {v:.2f}",
    "as_date_from": "From:",
    "as_date_to": "To:",
    "as_detector": "Detector:",
    "as_folder": "Folder contains:",
    "as_min_live": "Min. live time (s):",
    "as_calibrated_only": "Calibrated only",
    "as_include_dups": "Include duplicate copies",
    "as_search": "Search",
    "as_reset": "Reset filters",
    "as_any": "(any)",
    "as_col_date": "Date",
    "as_col_sample": "Sample ID",
    "as_col_desc": "Description",
    "as_col_nuclides": "Nuclides found",
    "as_col_live": "Live time (s)",
    "as_col_file": "File name",
    "as_col_folder": "Folder",
    "as_results": "{n} result(s)",
    "as_results_limited": "{n} result(s) (first {limit} shown)",
    "as_index_info": "{unique} spectra indexed ({dups} duplicate copies), {analysed} analysed, "
                     "{pending} awaiting analysis",
    "as_index_empty": "The index is empty: add the archive folders and press “Build / update index”.",
    "as_open": "Open in main window",
    "as_open_folder": "Open containing folder",
    "as_copy_path": "Copy path",
    "as_overlay": "Add as overlay",
    "as_export": "Export results to Excel / CSV...",
    "as_export_done": "Exported {n} row(s) to {path}",
    "as_not_analysed": "(not analysed)",
    "as_per_year": "Results per year",
})
STRINGS["ar"].update({
    "act_archive_search": "البحث في الأرشيف...",
    "tip_archive_search": "البحث في أرشيف الأطياف حسب العينة أو النص أو النويدة أو التاريخ أو المجلد",
    "as_title": "البحث في الأرشيف",
    "as_roots": "مجلدات الأرشيف",
    "as_add_root": "إضافة مجلد...",
    "as_remove_root": "إزالة",
    "as_db": "قاعدة بيانات الفهرس:",
    "as_db_change": "تغيير...",
    "as_build": "بناء / تحديث الفهرس",
    "as_cancel": "إلغاء",
    "as_build_phase_list": "جارٍ سرد الملفات...",
    "as_build_phase_scan": "قراءة البيانات الوصفية: {done} / {total}",
    "as_build_phase_analyse": "تحليل الأطياف: {done} / {total}",
    "as_eta": "المتبقي نحو {t}",
    "as_build_done": "تم تحديث الفهرس: {new} طيف جديد/معدّل، {removed} محذوف، {analysed} محلَّل ({sec} ث){cancel}",
    "as_build_cancelled": " — أُلغي (أعد التشغيل للاستئناف)",
    "as_build_failed": "فشل بناء الفهرس:\n{msg}",
    "as_no_roots": "أضف مجلد أرشيف واحدًا على الأقل أولًا.",
    "as_filters": "عوامل التصفية",
    "as_text": "نص:",
    "as_text_tip": "كلمات في معرّف العينة أو الوصف أو الملاحظات أو اسم الملف أو المجلد (تُتجاهل أشكال الألف "
                   "والتشكيل)",
    "as_nuclides": "النويدات:",
    "as_nuc_add": "إضافة",
    "as_nuc_placeholder": "مثال: Cs-137",
    "as_nuc_mode_all": "جميعها",
    "as_nuc_mode_any": "أيٌّ منها",
    "as_confidence": "أدنى ثقة: {v:.2f}",
    "as_date_from": "من:",
    "as_date_to": "إلى:",
    "as_detector": "الكاشف:",
    "as_folder": "المجلد يحتوي:",
    "as_min_live": "أدنى زمن حي (ث):",
    "as_calibrated_only": "المعايَرة فقط",
    "as_include_dups": "تضمين النسخ المكررة",
    "as_search": "بحث",
    "as_reset": "إعادة تعيين",
    "as_any": "(الكل)",
    "as_col_date": "التاريخ",
    "as_col_sample": "معرّف العينة",
    "as_col_desc": "الوصف",
    "as_col_nuclides": "النويدات المكتشفة",
    "as_col_live": "الزمن الحي (ث)",
    "as_col_file": "اسم الملف",
    "as_col_folder": "المجلد",
    "as_results": "{n} نتيجة",
    "as_results_limited": "{n} نتيجة (تُعرض أول {limit})",
    "as_index_info": "{unique} طيف مفهرس ({dups} نسخة مكررة)، {analysed} محلَّل، {pending} بانتظار التحليل",
    "as_index_empty": "الفهرس فارغ: أضف مجلدات الأرشيف ثم اضغط «بناء / تحديث الفهرس».",
    "as_open": "فتح في النافذة الرئيسية",
    "as_open_folder": "فتح المجلد الحاوي",
    "as_copy_path": "نسخ المسار",
    "as_overlay": "إضافة كطيف متراكب",
    "as_export": "تصدير النتائج إلى Excel / CSV...",
    "as_export_done": "صُدّر {n} صف إلى {path}",
    "as_not_analysed": "(غير محلَّل)",
    "as_per_year": "النتائج حسب السنة",
})

COLUMNS = ["as_col_date", "as_col_sample", "as_col_desc", "as_col_nuclides", "as_col_live", "as_col_file",
           "as_col_folder"]
RESULT_LIMIT = 5000
EXPORT_COLUMNS = ["as_col_date", "as_col_sample", "as_col_desc", "as_col_nuclides", "as_col_live", "as_x_real",
                  "as_x_detector", "as_col_file", "as_col_folder", "as_x_path", "as_x_copies", "as_x_counts",
                  "as_x_comment"]
STRINGS["en"].update({"as_x_real": "Real time (s)", "as_x_detector": "Detector", "as_x_path": "Path",
                      "as_x_copies": "Copies", "as_x_counts": "Total counts", "as_x_comment": "Comment"})
STRINGS["ar"].update({"as_x_real": "الزمن الحقيقي (ث)", "as_x_detector": "الكاشف", "as_x_path": "المسار",
                      "as_x_copies": "عدد النسخ", "as_x_counts": "إجمالي العدّات", "as_x_comment": "ملاحظات"})


def _fmt_eta(sec: Optional[float]) -> str:
    if sec is None:
        return ""
    sec = int(sec)
    if sec >= 3600:
        return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"
    return f"{sec // 60}:{sec % 60:02d}"


# ------------------------------------------------------------------------ worker
class ArchiveBuildWorker(QObject):
    """Runs ArchiveIndex.build in a QThread (the analysis itself uses a process pool)."""

    progress = Signal(str, int, int, object, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, db_path, roots: Sequence[str], workers: Optional[int] = None, analyse: bool = True):
        super().__init__()
        self.db_path = Path(db_path)
        self.roots = list(roots)
        self.workers = workers
        self.analyse = analyse
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        ix = None
        try:
            ix = ArchiveIndex(self.db_path)
            res = ix.build(self.roots, progress=lambda *a: self.progress.emit(*a) or None,
                           workers=self.workers, analyse=self.analyse, cancel=self.cancel_event)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        finally:
            if ix is not None:
                ix.close()
        self.finished.emit(res)


# ------------------------------------------------------------------------- model
class ResultsModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[ArchiveRow] = []

    def set_rows(self, rows: list[ArchiveRow]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and 0 <= section < len(COLUMNS):
            return tr(COLUMNS[section])
        return None

    def _text(self, r: ArchiveRow, col: int) -> str:
        if col == 0:
            return r.start_time.strftime("%Y-%m-%d %H:%M") if r.start_time else ""
        if col == 1:
            return r.display_id
        if col == 2:
            return " ".join(r.description.split())
        if col == 3:
            if not r.analysed:
                return tr("as_not_analysed")
            return ", ".join(f"{n} {c:.2f}" for n, c in r.nuclides)
        if col == 4:
            return f"{r.live_time:.0f}" if r.live_time is not None else ""
        if col == 5:
            return r.name + (f"  (×{r.copies})" if r.copies > 1 else "")
        if col == 6:
            return r.folder
        return ""

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r = self.rows[index.row()]
        if role == Qt.DisplayRole:
            text = self._text(r, index.column())
            # file names / folders: '.S0' must not detach in the RTL table
            return i18n.bidi_path(text) if index.column() in (5, 6) else text
        if role == Qt.ToolTipRole:
            if index.column() == 3 and r.nuclides:
                return "\n".join(f"{n}: {c:.3f}" for n, c in r.nuclides)
            return r.path
        if role == Qt.TextAlignmentRole and index.column() == 4:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.UserRole:
            return r
        return None

    def sort(self, column, order=Qt.AscendingOrder):
        keys = {
            0: lambda r: (r.start_time is None, r.start_time or 0),
            1: lambda r: r.display_id.lower(),
            2: lambda r: r.description.lower(),
            3: lambda r: (-(r.nuclides[0][1]) if r.nuclides else 1.0, r.nuclide_text),
            4: lambda r: (r.live_time is None, r.live_time or 0.0),
            5: lambda r: r.name.lower(),
            6: lambda r: r.folder.lower(),
        }
        k = keys.get(column)
        if k is None:
            return
        self.layoutAboutToBeChanged.emit()
        try:
            self.rows.sort(key=k, reverse=(order == Qt.DescendingOrder))
        except TypeError:
            pass
        self.layoutChanged.emit()


class YearHistogram(QWidget):
    """Tiny bar chart of results per year."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: list[tuple[str, int]] = []
        self.setMinimumHeight(70)
        self.setLayoutDirection(Qt.LeftToRight)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_data(self, data: list[tuple[str, int]]) -> None:
        self.data = [(k or "?", n) for k, n in data]
        self.setToolTip("\n".join(f"{k}: {n}" for k, n in self.data))
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if not self.data:
            return
        top = max(n for _k, n in self.data) or 1
        n = len(self.data)
        bw = max(4.0, (w - 8) / n)
        fm = p.fontMetrics()
        th = fm.height()
        bar_col = QColor(70, 120, 180)
        for i, (k, c) in enumerate(self.data):
            x = 4 + i * bw
            bh = (h - 2 * th - 4) * c / top
            rect = QRectF(x + 1, h - th - bh, bw - 2, bh)
            p.fillRect(rect, bar_col)
            p.setPen(QPen(self.palette().text().color()))
            if bw >= fm.horizontalAdvance("8888") or i % max(1, int(40 // bw)) == 0:
                p.drawText(QRectF(x, h - th, bw, th), Qt.AlignCenter, k[-2:] if bw < 34 else k)
            if bw >= fm.horizontalAdvance(str(c)) + 2:
                p.drawText(QRectF(x, h - th - bh - th, bw, th), Qt.AlignCenter, str(c))
        p.end()


# ------------------------------------------------------------------------ window
class ArchiveSearchWindow(QMainWindow):
    """Archive search tool window.  `main_window` (optional) receives open/overlay requests."""

    openRequested = Signal(str)

    def __init__(self, main_window=None, settings=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.settings = settings if settings is not None else getattr(main_window, "settings", None)
        self._thread: Optional[QThread] = None
        self._worker: Optional[ArchiveBuildWorker] = None
        self._index: Optional[ArchiveIndex] = None
        self._nuc_names = nuclide_names()
        self.last_build = None
        self.messages: list[str] = []
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._build_ui()
        self._load_settings()
        self.retranslate()
        self.resize(1250, 760)
        QTimer.singleShot(0, self.refresh_info)

    # ------------------------------------------------------------- settings
    def _sget(self, key, default=None):
        if self.settings is None:
            return default
        v = self.settings.get(key, default)
        return default if v is None else v

    def _sset(self, key, value) -> None:
        if self.settings is not None:
            self.settings.set(key, value)

    @property
    def db_path(self) -> Path:
        return Path(str(self._sget("archive/db", "") or default_db_path()))

    def set_db_path(self, path) -> None:
        self._sset("archive/db", str(path))
        if self._index is not None:
            self._index.close()
        self._index = None
        self.db_label.setText(str(self.db_path))
        self.refresh_info()
        self.run_search()

    def index(self) -> ArchiveIndex:
        if self._index is None or self._index.db_path != self.db_path:
            self._index = ArchiveIndex(self.db_path)
        return self._index

    def roots(self) -> list[str]:
        return [self.roots_list.item(i).text() for i in range(self.roots_list.count())]

    def _load_settings(self) -> None:
        try:
            roots = json.loads(str(self._sget("archive/roots", "[]") or "[]"))
        except ValueError:
            roots = []
        for r in roots:
            self.roots_list.addItem(r)
        self.db_label.setText(str(self.db_path))
        try:
            f = json.loads(str(self._sget("archive/filters", "{}") or "{}"))
        except ValueError:
            f = {}
        if f:
            self.set_filters(f)

    def _save_settings(self) -> None:
        self._sset("archive/roots", json.dumps(self.roots(), ensure_ascii=False))
        self._sset("archive/filters", json.dumps(self.filters_state(), ensure_ascii=False))

    # -------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)

        # roots + build
        self.roots_box = QGroupBox()
        rl = QHBoxLayout(self.roots_box)
        self.roots_list = QListWidget()
        self.roots_list.setMaximumHeight(70)
        rl.addWidget(self.roots_list, 1)
        col = QVBoxLayout()
        self.btn_add_root = QPushButton()
        self.btn_add_root.clicked.connect(lambda: self.add_root())
        self.btn_remove_root = QPushButton()
        self.btn_remove_root.clicked.connect(self.remove_selected_root)
        col.addWidget(self.btn_add_root)
        col.addWidget(self.btn_remove_root)
        col.addStretch(1)
        rl.addLayout(col)
        col2 = QVBoxLayout()
        dbrow = QHBoxLayout()
        self.db_caption = QLabel()
        self.db_label = QLabel()
        self.db_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.btn_db = QPushButton()
        self.btn_db.clicked.connect(self.choose_db)
        dbrow.addWidget(self.db_caption)
        dbrow.addWidget(self.db_label, 1)
        dbrow.addWidget(self.btn_db)
        col2.addLayout(dbrow)
        brow = QHBoxLayout()
        self.btn_build = QPushButton()
        self.btn_build.clicked.connect(lambda: self.start_build())
        self.btn_cancel = QPushButton()
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_build)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_label = QLabel()
        brow.addWidget(self.btn_build)
        brow.addWidget(self.btn_cancel)
        brow.addWidget(self.progress_bar, 1)
        col2.addLayout(brow)
        col2.addWidget(self.progress_label)
        rl.addLayout(col2, 2)
        outer.addWidget(self.roots_box)

        split = QSplitter(Qt.Horizontal)
        # filters
        self.filters_box = QGroupBox()
        fl = QFormLayout(self.filters_box)
        self.text_edit = QLineEdit()
        self.text_edit.setClearButtonEnabled(True)
        self.text_edit.returnPressed.connect(self.run_search)
        self.lbl_text = QLabel()
        fl.addRow(self.lbl_text, self.text_edit)
        nucw = QWidget()
        nl = QVBoxLayout(nucw)
        nl.setContentsMargins(0, 0, 0, 0)
        nrow = QHBoxLayout()
        self.nuc_edit = QLineEdit()
        comp = QCompleter(self._nuc_names, self)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        self.nuc_edit.setCompleter(comp)
        self.nuc_edit.returnPressed.connect(self._add_nuclide_from_edit)
        self.btn_nuc_add = QPushButton()
        self.btn_nuc_add.clicked.connect(self._add_nuclide_from_edit)
        nrow.addWidget(self.nuc_edit, 1)
        nrow.addWidget(self.btn_nuc_add)
        nl.addLayout(nrow)
        self.nuc_list = QListWidget()
        self.nuc_list.setMaximumHeight(80)
        self.nuc_list.itemDoubleClicked.connect(lambda it: (self.nuc_list.takeItem(self.nuc_list.row(it)),
                                                             self.run_search()))
        nl.addWidget(self.nuc_list)
        self.nuc_mode = QComboBox()
        self.nuc_mode.addItems(["", ""])
        self.nuc_mode.currentIndexChanged.connect(lambda _i: self.run_search())
        nl.addWidget(self.nuc_mode)
        self.lbl_nuc = QLabel()
        fl.addRow(self.lbl_nuc, nucw)
        self.conf_slider = QSlider(Qt.Horizontal)
        self.conf_slider.setRange(0, 100)
        self.conf_slider.setValue(50)
        self.conf_label = QLabel()
        self.conf_slider.valueChanged.connect(self._conf_changed)
        self.conf_slider.sliderReleased.connect(self.run_search)
        fl.addRow(self.conf_label, self.conf_slider)
        self.chk_from = QCheckBox()
        self.date_from = QDateEdit(QDate(2004, 1, 1))
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.chk_to = QCheckBox()
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        for chk, de in ((self.chk_from, self.date_from), (self.chk_to, self.date_to)):
            de.setEnabled(False)
            chk.toggled.connect(de.setEnabled)
            chk.toggled.connect(lambda _v: self.run_search())
            de.dateChanged.connect(lambda _d: self.run_search())
            row = QHBoxLayout()
            row.addWidget(chk)
            row.addWidget(de, 1)
            fl.addRow(row)
        self.det_combo = QComboBox()
        self.det_combo.setEditable(True)
        self.det_combo.activated.connect(lambda _i: self.run_search())
        self.det_combo.lineEdit().returnPressed.connect(self.run_search)
        self.lbl_det = QLabel()
        fl.addRow(self.lbl_det, self.det_combo)
        self.folder_edit = QLineEdit()
        self.folder_edit.setClearButtonEnabled(True)
        self.folder_edit.returnPressed.connect(self.run_search)
        self.lbl_folder = QLabel()
        fl.addRow(self.lbl_folder, self.folder_edit)
        self.min_live = QDoubleSpinBox()
        self.min_live.setRange(0, 1e7)
        self.min_live.setDecimals(0)
        self.min_live.editingFinished.connect(self.run_search)
        self.lbl_live = QLabel()
        fl.addRow(self.lbl_live, self.min_live)
        self.chk_cal = QCheckBox()
        self.chk_cal.toggled.connect(lambda _v: self.run_search())
        fl.addRow(self.chk_cal)
        self.chk_dups = QCheckBox()
        self.chk_dups.toggled.connect(lambda _v: self.run_search())
        fl.addRow(self.chk_dups)
        brow2 = QHBoxLayout()
        self.btn_search = QPushButton()
        self.btn_search.setDefault(True)
        self.btn_search.clicked.connect(self.run_search)
        self.btn_reset = QPushButton()
        self.btn_reset.clicked.connect(self.reset_filters)
        brow2.addWidget(self.btn_search)
        brow2.addWidget(self.btn_reset)
        fl.addRow(brow2)
        split.addWidget(self.filters_box)

        # results
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.model = ResultsModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setStretchLastSection(True)
        for i, w in enumerate((125, 150, 160, 230, 80, 260)):
            self.table.setColumnWidth(i, w)
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        rv.addWidget(self.table, 1)
        stats = QHBoxLayout()
        self.count_label = QLabel()
        self.index_label = QLabel()
        self.index_label.setWordWrap(True)
        left_stats = QVBoxLayout()
        left_stats.addWidget(self.count_label)
        left_stats.addWidget(self.index_label)
        stats.addLayout(left_stats, 1)
        self.histogram = YearHistogram()
        stats.addWidget(self.histogram, 2)
        rv.addLayout(stats)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([330, 920])
        outer.addWidget(split, 1)
        self.setCentralWidget(central)

        # actions (context menu)
        self.act_open = QAction(self)
        self.act_open.triggered.connect(lambda: self.open_selected())
        self.act_folder = QAction(self)
        self.act_folder.triggered.connect(self.open_containing_folder)
        self.act_copy = QAction(self)
        self.act_copy.triggered.connect(self.copy_paths)
        self.act_overlay = QAction(self)
        self.act_overlay.triggered.connect(lambda: self.add_selected_as_overlay())
        self.act_export = QAction(self)
        self.act_export.triggered.connect(lambda: self.export_results())

    def retranslate(self) -> None:
        self.setWindowTitle(tr("as_title"))
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.roots_box.setTitle(tr("as_roots"))
        self.btn_add_root.setText(tr("as_add_root"))
        self.btn_remove_root.setText(tr("as_remove_root"))
        self.db_caption.setText(tr("as_db"))
        self.btn_db.setText(tr("as_db_change"))
        self.btn_build.setText(tr("as_build"))
        self.btn_cancel.setText(tr("as_cancel"))
        self.filters_box.setTitle(tr("as_filters"))
        self.lbl_text.setText(tr("as_text"))
        self.text_edit.setToolTip(tr("as_text_tip"))
        self.lbl_nuc.setText(tr("as_nuclides"))
        self.btn_nuc_add.setText(tr("as_nuc_add"))
        self.nuc_edit.setPlaceholderText(tr("as_nuc_placeholder"))
        self.nuc_mode.setItemText(0, tr("as_nuc_mode_all"))
        self.nuc_mode.setItemText(1, tr("as_nuc_mode_any"))
        self._conf_changed(self.conf_slider.value())
        self.chk_from.setText(tr("as_date_from"))
        self.chk_to.setText(tr("as_date_to"))
        self.lbl_det.setText(tr("as_detector"))
        self.lbl_folder.setText(tr("as_folder"))
        self.lbl_live.setText(tr("as_min_live"))
        self.chk_cal.setText(tr("as_calibrated_only"))
        self.chk_dups.setText(tr("as_include_dups"))
        self.btn_search.setText(tr("as_search"))
        self.btn_reset.setText(tr("as_reset"))
        self.act_open.setText(tr("as_open"))
        self.act_folder.setText(tr("as_open_folder"))
        self.act_copy.setText(tr("as_copy_path"))
        self.act_overlay.setText(tr("as_overlay"))
        self.act_export.setText(tr("as_export"))
        self.histogram.setStatusTip(tr("as_per_year"))
        self.model.headerDataChanged.emit(Qt.Horizontal, 0, len(COLUMNS) - 1)
        self._update_count_label()

    def _conf_changed(self, v: int) -> None:
        self.conf_label.setText(tr("as_confidence", v=v / 100.0))

    # ----------------------------------------------------------- roots / db
    def add_root(self, path: Optional[str] = None) -> bool:
        if path is None:
            path = QFileDialog.getExistingDirectory(self, tr("as_add_root"))
            if not path:
                return False
        path = str(Path(path))
        if path in self.roots():
            return False
        self.roots_list.addItem(path)
        self._save_settings()
        return True

    def remove_selected_root(self) -> None:
        it = self.roots_list.currentItem()
        if it is None:
            return
        path = it.text()
        self.roots_list.takeItem(self.roots_list.row(it))
        self._save_settings()
        try:
            self.index().remove_root(path, purge=True)
        except Exception as exc:
            self._message(str(exc))
        self.refresh_info()
        self.run_search()

    def choose_db(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, tr("as_db"), str(self.db_path), "SQLite (*.sqlite *.db)")
        if path:
            self.set_db_path(path)

    # ----------------------------------------------------------------- build
    def is_building(self) -> bool:
        return self._thread is not None

    def start_build(self, workers: Optional[int] = None, analyse: bool = True) -> bool:
        if self.is_building():
            return False
        roots = self.roots()
        if not roots:
            self._message(tr("as_no_roots"))
            return False
        self._save_settings()
        if self._index is not None:
            self._index.close()
            self._index = None
        self._thread = QThread(self)
        self._worker = ArchiveBuildWorker(self.db_path, roots, workers, analyse)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self.btn_build.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setRange(0, 0)
        self.progress_label.setText(tr("as_build_phase_list"))
        self._thread.start()
        return True

    def cancel_build(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.btn_cancel.setEnabled(False)

    @Slot(str, int, int, object, str)
    def _on_progress(self, phase, done, total, eta, current) -> None:
        if phase == "list" or not total:
            self.progress_bar.setRange(0, 0)
            self.progress_label.setText(tr("as_build_phase_list"))
            return
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        key = "as_build_phase_scan" if phase == "scan" else "as_build_phase_analyse"
        text = tr(key, done=done, total=total)
        if eta is not None:
            text += "  —  " + tr("as_eta", t=_fmt_eta(eta))
        self.progress_label.setText(text)

    def _end_build(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread.deleteLater()
        if self._worker is not None:
            self._worker.deleteLater()
        self._thread = self._worker = None
        self.btn_build.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)

    @Slot(object)
    def _on_finished(self, res) -> None:
        self._end_build()
        self.last_build = res
        self.progress_label.setText(tr("as_build_done", new=res.new_entries, removed=res.removed,
                                       analysed=res.analysed, sec=round(res.elapsed, 1),
                                       cancel=tr("as_build_cancelled") if res.cancelled else ""))
        self.refresh_info()
        self.run_search()

    @Slot(str)
    def _on_failed(self, msg: str) -> None:
        self._end_build()
        self.progress_label.setText("")
        self._message(tr("as_build_failed", msg=msg))

    # ---------------------------------------------------------------- filters
    def _add_nuclide_from_edit(self) -> None:
        t = self.nuc_edit.text().strip()
        if t:
            self.add_nuclide(t)
            self.nuc_edit.clear()
            self.run_search()

    def add_nuclide(self, name: str) -> str:
        n = canonical_nuclide(name, self._nuc_names)
        if n and n not in self.selected_nuclides():
            self.nuc_list.addItem(QListWidgetItem(n))
        return n

    def selected_nuclides(self) -> list[str]:
        return [self.nuc_list.item(i).text() for i in range(self.nuc_list.count())]

    def filters(self) -> dict:
        """Keyword arguments for ArchiveIndex.search from the filter widgets."""
        det = self.det_combo.currentText().strip()
        return dict(
            text=self.text_edit.text().strip() or None,
            nuclides=self.selected_nuclides() or None,
            min_confidence=self.conf_slider.value() / 100.0,
            nuclide_mode="any" if self.nuc_mode.currentIndex() == 1 else "all",
            date_from=self.date_from.date().toPython() if self.chk_from.isChecked() else None,
            date_to=self.date_to.date().toPython() if self.chk_to.isChecked() else None,
            detector=None if det in ("", tr("as_any")) else det,
            folder_contains=self.folder_edit.text().strip() or None,
            min_live_time=self.min_live.value() or None,
            has_calibration=True if self.chk_cal.isChecked() else None,
            include_duplicates=self.chk_dups.isChecked(),
        )

    def filters_state(self) -> dict:
        f = self.filters()
        f["date_from"] = f["date_from"].isoformat() if f["date_from"] else None
        f["date_to"] = f["date_to"].isoformat() if f["date_to"] else None
        return f

    def set_filters(self, f: dict) -> None:
        widgets = (self.text_edit, self.nuc_list, self.conf_slider, self.nuc_mode, self.chk_from, self.chk_to,
                   self.date_from, self.date_to, self.det_combo, self.folder_edit, self.min_live, self.chk_cal,
                   self.chk_dups)
        for w in widgets:
            w.blockSignals(True)
        try:
            self.text_edit.setText(f.get("text") or "")
            self.nuc_list.clear()
            for n in f.get("nuclides") or []:
                self.add_nuclide(n)
            self.conf_slider.setValue(int(round(100 * float(f.get("min_confidence", 0.5) or 0))))
            self._conf_changed(self.conf_slider.value())
            self.nuc_mode.setCurrentIndex(1 if f.get("nuclide_mode") == "any" else 0)
            for key, chk, de in (("date_from", self.chk_from, self.date_from), ("date_to", self.chk_to, self.date_to)):
                v = f.get(key)
                if isinstance(v, str) and v:
                    v = date.fromisoformat(v[:10])
                chk.setChecked(bool(v))
                de.setEnabled(bool(v))
                if v:
                    de.setDate(QDate(v.year, v.month, v.day))
            self.det_combo.setEditText(f.get("detector") or "")
            self.folder_edit.setText(f.get("folder_contains") or "")
            self.min_live.setValue(float(f.get("min_live_time") or 0))
            self.chk_cal.setChecked(bool(f.get("has_calibration")))
            self.chk_dups.setChecked(bool(f.get("include_duplicates")))
        finally:
            for w in widgets:
                w.blockSignals(False)

    def reset_filters(self) -> None:
        self.set_filters({})
        self.run_search()

    # ----------------------------------------------------------------- search
    def refresh_info(self) -> None:
        try:
            st = self.index().stats()
        except Exception as exc:
            self.index_label.setText(str(exc))
            return
        if st["entries"] == 0:
            self.index_label.setText(tr("as_index_empty"))
        else:
            self.index_label.setText(tr("as_index_info", unique=st["unique"], dups=st["duplicates"],
                                        analysed=st["analysed"], pending=st["pending_analysis"]))
        cur = self.det_combo.currentText()
        self.det_combo.blockSignals(True)
        self.det_combo.clear()
        self.det_combo.addItem(tr("as_any"))
        self.det_combo.addItems(self.index().detectors())
        self.det_combo.setEditText(cur if cur else "")
        self.det_combo.blockSignals(False)
        if not cur:
            self.det_combo.setCurrentIndex(0)

    def run_search(self) -> list[ArchiveRow]:
        f = self.filters()
        try:
            ix = self.index()
            rows = ix.search(**f, limit=RESULT_LIMIT)
            self._total = ix.count(**{k: v for k, v in f.items()}) if len(rows) >= RESULT_LIMIT else len(rows)
            hist = ix.count_by_period("year", **f)
        except Exception as exc:
            self._message(f"{type(exc).__name__}: {exc}")
            return []
        self.model.set_rows(rows)
        hh = self.table.horizontalHeader()
        if hh.sortIndicatorSection() >= 0:
            self.model.sort(hh.sortIndicatorSection(), hh.sortIndicatorOrder())
        self.histogram.set_data(hist)
        self._update_count_label()
        self._save_settings()
        return rows

    def _update_count_label(self) -> None:
        n = len(self.model.rows)
        total = getattr(self, "_total", n)
        if total > n:
            self.count_label.setText(tr("as_results_limited", n=total, limit=n))
        else:
            self.count_label.setText(tr("as_results", n=n))

    # ---------------------------------------------------------------- actions
    def selected_rows(self) -> list[ArchiveRow]:
        idx = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        if not idx and self.table.currentIndex().isValid():
            idx = [self.table.currentIndex().row()]
        return [self.model.rows[i] for i in idx]

    def _on_double_click(self, index: QModelIndex) -> None:
        if index.isValid():
            self.open_row(self.model.rows[index.row()])

    def open_row(self, row: ArchiveRow) -> bool:
        self.openRequested.emit(row.path)
        mw = self.main_window
        if mw is None:
            return False
        ok = mw.load_file(row.path, None)
        if ok:
            if row.spec_index > 1 and hasattr(mw, "show_index"):
                mw.show_index(row.spec_index - 1)
            mw.raise_()
            mw.activateWindow()
        return ok

    def open_selected(self) -> bool:
        rows = self.selected_rows()
        return self.open_row(rows[0]) if rows else False

    def open_containing_folder(self) -> None:
        rows = self.selected_rows()
        if not rows:
            return
        p = Path(rows[0].path)
        if sys.platform == "win32" and p.exists():
            subprocess.Popen(["explorer", "/select,", str(p)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent)))

    def copy_paths(self) -> str:
        text = "\n".join(r.path for r in self.selected_rows())
        QGuiApplication.clipboard().setText(text)
        return text

    def add_selected_as_overlay(self) -> int:
        mw = self.main_window
        if mw is None:
            return 0
        n = 0
        for r in self.selected_rows():
            if mw.current_spectrum() is None:
                if mw.load_file(r.path, None):
                    n += 1
                continue
            if mw.add_overlay_file(r.path):
                n += 1
        return n

    def export_results(self, path: Optional[str] = None, rows: Optional[list[ArchiveRow]] = None) -> Optional[Path]:
        if rows is None:
            rows = self.selected_rows()
            if len(rows) <= 1:
                rows = list(self.model.rows)
        if path is None:
            start = str(Path(self._sget("archive/export_dir", str(Path.home())) or Path.home()) /
                        "archive_search.xlsx")
            path, _ = QFileDialog.getSaveFileName(self, tr("as_export"), start,
                                                  "Excel (*.xlsx);;CSV (*.csv)")
            if not path:
                return None
        out = export_rows(rows, path, lang_headers=[tr(k) for k in EXPORT_COLUMNS])
        self._sset("archive/export_dir", str(Path(path).parent))
        self.progress_label.setText(tr("as_export_done", n=len(rows), path=str(out)))
        return out

    def _context_menu(self, pos) -> None:
        if not self.table.indexAt(pos).isValid():
            return
        m = QMenu(self)
        has_main = self.main_window is not None
        self.act_open.setEnabled(has_main)
        self.act_overlay.setEnabled(has_main)
        for a in (self.act_open, self.act_folder, self.act_copy, self.act_overlay):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.act_export)
        m.exec(self.table.viewport().mapToGlobal(pos))

    def _message(self, text: str) -> None:
        """Modal message (tests replace it)."""
        self.messages.append(text)
        QMessageBox.information(self, tr("as_title"), text)

    def closeEvent(self, ev) -> None:
        if self.is_building():
            self.cancel_build()
            if self._thread is not None:
                self._thread.quit()
                self._thread.wait(60000)
        self._save_settings()
        if self._index is not None:
            self._index.close()
            self._index = None
        super().closeEvent(ev)


# ------------------------------------------------------------------ main-window hook
def install_archive_search(main_window) -> QAction:
    """Create the File-menu action "Archive search..." on `main_window`."""
    act = QAction(main_window)
    act.setShortcut("Ctrl+Shift+F")
    act.triggered.connect(lambda: show_archive_search(main_window))
    menu = getattr(main_window, "menu_file", None)
    if menu is not None:
        before = getattr(main_window, "act_folder", None)
        acts = menu.actions()
        if before is not None and before in acts:
            i = acts.index(before)
            nxt = acts[i + 1] if i + 1 < len(acts) else None
            if nxt is not None:
                menu.insertAction(nxt, act)
            else:
                menu.addAction(act)
        else:
            menu.addAction(act)
    main_window.act_archive_search = act
    retranslate_archive_search(main_window)
    return act


def retranslate_archive_search(main_window) -> None:
    act = getattr(main_window, "act_archive_search", None)
    if act is not None:
        act.setText(tr("act_archive_search"))
        act.setToolTip(tr("tip_archive_search"))
        act.setStatusTip(tr("tip_archive_search"))
    win = getattr(main_window, "archive_search_window", None)
    if win is not None:
        win.retranslate()


def show_archive_search(main_window) -> ArchiveSearchWindow:
    win = getattr(main_window, "archive_search_window", None)
    if win is None:
        win = ArchiveSearchWindow(main_window, getattr(main_window, "settings", None))
        main_window.archive_search_window = win
    win.show()
    win.raise_()
    win.activateWindow()
    return win

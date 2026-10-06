"""Dialogs: format chooser, batch conversion, About, shortcuts, GammaVision/MAESTRO integration."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QSize, Qt, QThread, QUrl, Signal)
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog,
                               QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMessageBox, QProgressBar,
                               QPushButton, QTableView, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from .. import __version__
from ..formats import all_formats, readable_formats, writable_formats
from ..formats.base import FormatSpec
from .i18n import bidi_path, tr
from .icon import app_icon, designer_pixmap, logo_pixmap
from .settings import AUTO, Settings
from .worker import BatchWorker


# ======================================================================= format chooser
class FormatDialog(QDialog):
    """DataMaster 'Open Input Files As...' / 'Save As...' format list."""

    def __init__(self, title: str, prompt: str, formats: Sequence[FormatSpec],
                 current_key: Optional[str], allow_auto: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 460)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(prompt))
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels([tr("col_code"), tr("col_format"), tr("col_ext")])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.itemDoubleClicked.connect(lambda *_: self.accept())
        select = None
        if allow_auto:
            it = QTreeWidgetItem(["", tr("auto_detect"), ""])
            it.setData(0, Qt.UserRole, AUTO)
            f = it.font(1)
            f.setBold(True)
            it.setFont(1, f)
            self.tree.addTopLevelItem(it)
            if current_key in (None, AUTO):
                select = it
        for fmt in formats:
            it = QTreeWidgetItem([str(fmt.code), fmt.name, "‎" + "; ".join("*" + e for e in fmt.extensions)])
            it.setData(0, Qt.UserRole, fmt.key)
            it.setTextAlignment(0, Qt.AlignCenter)
            if fmt.notes:
                for c in range(3):
                    it.setToolTip(c, fmt.notes)
            self.tree.addTopLevelItem(it)
            if fmt.key == current_key:
                select = it
        if select is None and self.tree.topLevelItemCount():
            select = self.tree.topLevelItem(0)
        if select is not None:
            self.tree.setCurrentItem(select)
        hdr = self.tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setStretchLastSection(False)
        lay.addWidget(self.tree, 1)
        if not formats and not allow_auto:
            lay.addWidget(QLabel(tr("no_formats")))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(tr("ok"))
        bb.button(QDialogButtonBox.Cancel).setText(tr("cancel"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def selected_key(self) -> Optional[str]:
        it = self.tree.currentItem()
        return it.data(0, Qt.UserRole) if it else None

    def select_key(self, key: str) -> None:
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.data(0, Qt.UserRole) == key:
                self.tree.setCurrentItem(it)


# ======================================================================= batch model
class BatchModel(QAbstractTableModel):
    def __init__(self, files: Sequence[Path] = ()):
        super().__init__()
        self.files: list[Path] = []
        self.status: list[str] = []
        self.state: list[Optional[bool]] = []
        self.set_files(files)

    def set_files(self, files) -> None:
        self.beginResetModel()
        self.files = [Path(f) for f in files]
        self.status = [tr("batch_pending")] * len(self.files)
        self.state = [None] * len(self.files)
        self._index = {os.path.normcase(str(f)): i for i, f in enumerate(self.files)}
        self.endResetModel()

    def reset_status(self) -> None:
        self.set_files(self.files)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.files)

    def columnCount(self, parent=QModelIndex()):
        return 3

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return [tr("batch_col_file"), tr("batch_col_folder"), tr("batch_col_status")][section]
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return str(section + 1)
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        f = self.files[r]
        if role == Qt.DisplayRole:
            return [bidi_path(f.name), bidi_path(f.parent), self.status[r]][c]
        if role == Qt.ToolTipRole:
            return str(f) if c < 2 else self.status[r]
        if role == Qt.ForegroundRole and c == 2:
            st = self.state[r]
            if st is True:
                return QColor("#1e7b34")
            if st is False:
                return QColor("#b3261e")
            return QColor("#6b7580")
        return None

    def set_result(self, src: str, ok: bool, message: str) -> int:
        row = self._index.get(os.path.normcase(src), -1)
        if row < 0:
            return -1
        self.state[row] = ok
        self.status[row] = (tr("batch_ok") + " → " + message) if ok and message else (
            tr("batch_ok") if ok else message)
        idx = self.index(row, 2)
        self.dataChanged.emit(idx, idx)
        return row


# ======================================================================= batch dialog
def scan_folder(root: Path, recursive: bool, extensions: Optional[set[str]]) -> list[Path]:
    out: list[Path] = []
    root = Path(root)
    if recursive:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort(key=str.lower)
            for name in sorted(filenames, key=str.lower):
                if extensions is None or os.path.splitext(name)[1].lower() in extensions:
                    out.append(Path(dirpath) / name)
    else:
        try:
            names = sorted(os.listdir(root), key=str.lower)
        except OSError:
            names = []
        for name in names:
            p = root / name
            if p.is_file() and (extensions is None or p.suffix.lower() in extensions):
                out.append(p)
    return out


class BatchDialog(QDialog):
    """Converts many files in a background thread.

    ``folder_mode=True`` adds an input-folder picker with *recursive* and
    *keep folder structure* options (toolbar "Convert Folder...").
    """

    conversionFinished = Signal(int, int, int, bool)

    def __init__(self, files: Sequence[Path] = (), settings: Optional[Settings] = None,
                 parent=None, folder_mode: bool = False, folder: Optional[Path] = None):
        super().__init__(parent)
        self.settings = settings or Settings()
        self.folder_mode = folder_mode
        self.setWindowTitle(tr("folder_title") if folder_mode else tr("batch_title"))
        self.resize(860, 600)
        self.setSizeGripEnabled(True)
        self._thread: Optional[QThread] = None
        self._worker: Optional[BatchWorker] = None
        self._last_out_dir: Optional[Path] = None
        self.in_fmt = self.settings.input_format()

        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        lay.addLayout(form)

        # --- input folder (folder mode)
        self.folder_edit = QLineEdit()
        self.folder_edit.setLayoutDirection(Qt.LeftToRight)
        self.recursive_cb = QCheckBox(tr("folder_recursive"))
        self.all_files_cb = QCheckBox(tr("folder_all_files"))
        if folder_mode:
            row = QHBoxLayout()
            row.addWidget(self.folder_edit, 1)
            b = QPushButton(tr("batch_browse"))
            b.clicked.connect(self._browse_in_folder)
            row.addWidget(b)
            self.scan_btn = QPushButton(tr("folder_scan"))
            self.scan_btn.clicked.connect(self.scan)
            row.addWidget(self.scan_btn)
            form.addRow(tr("folder_in"), row)
            opts = QHBoxLayout()
            self.recursive_cb.setChecked(self.settings.get_bool("batch/recursive", True))
            self.all_files_cb.setChecked(self.settings.get_bool("batch/all_files", False))
            self.recursive_cb.toggled.connect(lambda *_: self.scan())
            self.all_files_cb.toggled.connect(lambda *_: self.scan())
            opts.addWidget(self.recursive_cb)
            opts.addWidget(self.all_files_cb)
            opts.addStretch(1)
            form.addRow("", opts)
            self.folder_edit.setText(str(folder) if folder else "")
            self.folder_edit.returnPressed.connect(self.scan)

        # --- input format (display only; changed from the main window)
        self.in_label = QLabel(self.in_fmt.label() if self.in_fmt else tr("auto_detect"))
        form.addRow(tr("batch_input_fmt"), self.in_label)

        # --- output format
        self.out_combo = QComboBox()
        self.out_combo.setMinimumContentsLength(30)
        current = self.settings.output_format()
        for fmt in writable_formats():
            self.out_combo.addItem(f"{fmt.code:>2}  {fmt.label()}", fmt.key)
            if current is not None and fmt.key == current.key:
                self.out_combo.setCurrentIndex(self.out_combo.count() - 1)
        form.addRow(tr("batch_out_fmt"), self.out_combo)

        # --- output folder
        self.same_dir_cb = QCheckBox(tr("batch_same_dir"))
        self.out_edit = QLineEdit(self.settings.get("batch/out_dir", "") or "")
        self.out_edit.setLayoutDirection(Qt.LeftToRight)
        self.out_browse = QPushButton(tr("batch_browse"))
        self.out_browse.clicked.connect(self._browse_out)
        out_row = QHBoxLayout()
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(self.out_browse)
        out_box = QVBoxLayout()
        out_box.addWidget(self.same_dir_cb)
        out_box.addLayout(out_row)
        form.addRow(tr("batch_out_dir"), out_box)
        self.keep_tree_cb = QCheckBox(tr("batch_keep_tree"))
        self.keep_tree_cb.setChecked(self.settings.get_bool("batch/keep_tree", True))
        self.overwrite_cb = QCheckBox(tr("batch_overwrite"))
        self.overwrite_cb.setChecked(self.settings.get_bool("batch/overwrite", True))
        flags = QHBoxLayout()
        if folder_mode:
            flags.addWidget(self.keep_tree_cb)
        flags.addWidget(self.overwrite_cb)
        flags.addStretch(1)
        form.addRow("", flags)
        self.same_dir_cb.toggled.connect(self._same_dir_toggled)
        self.same_dir_cb.setChecked(self.settings.get_bool("batch/same_dir", True))
        self._same_dir_toggled(self.same_dir_cb.isChecked())

        # --- file table
        self.count_label = QLabel()
        lay.addWidget(self.count_label)
        self.model = BatchModel(files)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideMiddle)
        self.table.verticalHeader().setDefaultSectionSize(self.fontMetrics().height() + 8)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setStretchLastSection(True)
        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 300)
        lay.addWidget(self.table, 1)

        # --- progress + buttons
        self.progress = QProgressBar()
        self.progress.setRange(0, max(1, len(files)))
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        lay.addWidget(self.progress)
        self.summary = QLabel(" ")
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        btns = QHBoxLayout()
        self.open_out_btn = QPushButton(tr("batch_open_out"))
        self.open_out_btn.setEnabled(False)
        self.open_out_btn.clicked.connect(self.open_output_folder)
        btns.addWidget(self.open_out_btn)
        btns.addStretch(1)
        self.start_btn = QPushButton(tr("batch_start"))
        self.start_btn.setDefault(True)
        self.start_btn.clicked.connect(self.start)
        self.cancel_btn = QPushButton(tr("batch_cancel"))
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel)
        self.close_btn = QPushButton(tr("batch_close"))
        self.close_btn.clicked.connect(self.close)
        for b in (self.start_btn, self.cancel_btn, self.close_btn):
            btns.addWidget(b)
        lay.addLayout(btns)
        self._update_count()
        if folder_mode and folder:
            self.scan()

    # ----------------------------------------------------------- helpers
    def _update_count(self) -> None:
        n = len(self.model.files)
        self.count_label.setText(tr("folder_found", n=n) if self.folder_mode else tr("batch_files", n=n))
        self.start_btn.setEnabled(n > 0 and self.out_combo.count() > 0 and not self.is_running())
        self.progress.setRange(0, max(1, n))
        self.progress.setValue(0)

    def _same_dir_toggled(self, on: bool) -> None:
        self.out_edit.setEnabled(not on)
        self.out_browse.setEnabled(not on)
        self.keep_tree_cb.setEnabled(not on)

    def _browse_out(self) -> None:
        start = self.out_edit.text() or self.settings.folder("batch_out")
        d = QFileDialog.getExistingDirectory(self, tr("fd_choose_folder"), start)
        if d:
            self.out_edit.setText(os.path.normpath(d))

    def _browse_in_folder(self) -> None:
        start = self.folder_edit.text() or self.settings.folder("folder_in")
        d = QFileDialog.getExistingDirectory(self, tr("fd_choose_folder"), start)
        if d:
            self.folder_edit.setText(os.path.normpath(d))
            self.scan()

    def input_extensions(self) -> Optional[set[str]]:
        if self.all_files_cb.isChecked():
            return None
        fmts = [self.in_fmt] if self.in_fmt else readable_formats()
        exts = {e.lower() for f in fmts for e in f.extensions}
        return exts or None

    def scan(self) -> None:
        if not self.folder_mode or self.is_running():
            return
        text = self.folder_edit.text().strip()
        if not text or not Path(text).is_dir():
            self.model.set_files([])
            self._update_count()
            return
        self.count_label.setText(tr("folder_scanning"))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            QApplication.processEvents()
            files = scan_folder(Path(text), self.recursive_cb.isChecked(), self.input_extensions())
        finally:
            QApplication.restoreOverrideCursor()
        self.model.set_files(files)
        self._update_count()
        if not files:
            self.summary.setText(tr("err_no_files_found", path=text).replace("\n", " "))
        else:
            self.summary.setText(" ")

    def selected_out_format(self) -> Optional[FormatSpec]:
        key = self.out_combo.currentData()
        for f in writable_formats():
            if f.key == key:
                return f
        return None

    def is_running(self) -> bool:
        return self._thread is not None

    # ----------------------------------------------------------- running
    def start(self) -> None:
        if self.is_running() or not self.model.files:
            return
        out_fmt = self.selected_out_format()
        if out_fmt is None:
            QMessageBox.warning(self, tr("err_title"), tr("err_no_writable"))
            return
        out_dir: Optional[Path] = None
        keep_root: Optional[Path] = None
        if not self.same_dir_cb.isChecked():
            text = self.out_edit.text().strip()
            if not text:
                QMessageBox.warning(self, tr("err_title"), tr("batch_need_dir"))
                return
            out_dir = Path(text)
            if self.folder_mode and self.keep_tree_cb.isChecked():
                keep_root = Path(self.folder_edit.text().strip())
        # remember choices
        s = self.settings
        s.set_output_format(out_fmt)
        s.set("batch/same_dir", self.same_dir_cb.isChecked())
        s.set("batch/overwrite", self.overwrite_cb.isChecked())
        s.set("batch/keep_tree", self.keep_tree_cb.isChecked())
        if self.folder_mode:
            s.set("batch/recursive", self.recursive_cb.isChecked())
            s.set("batch/all_files", self.all_files_cb.isChecked())
            if self.folder_edit.text().strip():
                s.set_folder("folder_in", self.folder_edit.text().strip())
        if out_dir is not None:
            s.set("batch/out_dir", str(out_dir))
            s.set_folder("batch_out", out_dir)
        self._last_out_dir = out_dir if out_dir is not None else self.model.files[0].parent

        self.model.reset_status()
        n = len(self.model.files)
        self.progress.setRange(0, n)
        self.progress.setValue(0)
        self.summary.setText(tr("batch_running", i=0, n=n))
        self._set_running_ui(True)

        self._worker = BatchWorker(self.model.files, out_fmt, out_dir, self.in_fmt,
                                   overwrite=self.overwrite_cb.isChecked(), keep_tree_from=keep_root)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _set_running_ui(self, running: bool) -> None:
        self.start_btn.setEnabled(not running and bool(self.model.files))
        self.cancel_btn.setEnabled(running)
        self.close_btn.setEnabled(not running)
        self.out_combo.setEnabled(not running)
        self.same_dir_cb.setEnabled(not running)
        self.overwrite_cb.setEnabled(not running)
        self.recursive_cb.setEnabled(not running)
        self.all_files_cb.setEnabled(not running)
        if running:
            self.out_edit.setEnabled(False)
            self.out_browse.setEnabled(False)
            self.keep_tree_cb.setEnabled(False)
            self.open_out_btn.setEnabled(False)
        else:
            self._same_dir_toggled(self.same_dir_cb.isChecked())

    def _on_progress(self, i: int, n: int, src: str, ok: bool, msg: str) -> None:
        row = self.model.set_result(src, ok, msg)
        self.progress.setValue(i)
        self.summary.setText(tr("batch_running", i=i, n=n))
        if row >= 0 and (i % 25 == 0 or i == n or not ok):
            self.table.scrollTo(self.model.index(row, 0))

    def _on_finished(self, ok: int, bad: int, total: int, cancelled: bool) -> None:
        if cancelled:
            self.summary.setText(tr("batch_cancelled", done=ok + bad, total=total, ok=ok, bad=bad))
        else:
            self.summary.setText(tr("batch_summary", ok=ok, bad=bad, total=total))
        self.conversionFinished.emit(ok, bad, total, cancelled)

    def _cleanup_thread(self) -> None:
        if self._thread is not None:
            self._thread.deleteLater()
        if self._worker is not None:
            self._worker.deleteLater()
        self._thread = None
        self._worker = None
        self._set_running_ui(False)
        self.open_out_btn.setEnabled(self._last_out_dir is not None)

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.cancel_btn.setEnabled(False)

    def wait(self, ms: int = 30000) -> None:
        """Block until the worker thread is done (used on close and in tests)."""
        if self._thread is not None:
            self._thread.wait(ms)
            QApplication.processEvents()

    def open_output_folder(self) -> None:
        if self._last_out_dir is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_out_dir)))

    def closeEvent(self, ev):
        if self.is_running():
            if QMessageBox.question(self, tr("err_title"), tr("batch_confirm_cancel")) != QMessageBox.Yes:
                ev.ignore()
                return
            self.cancel()
            self.wait()
        super().closeEvent(ev)

    def reject(self):
        if self.is_running():
            self.close()
            return
        super().reject()


# ======================================================================= about
DESIGNER_NAME = "Edrees F. Hery"
DESIGNER_YEAR = 2026


def designer_section(logo_height: int = 110) -> QWidget:
    """"Designed & developed by" block: monogram + name (never transliterated) + year."""
    box = QWidget()
    box.setObjectName("designerSection")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 6, 0, 0)
    lay.setSpacing(3)
    cap = QLabel(tr("about_designed_by"))
    cap.setAlignment(Qt.AlignCenter)
    cap.setObjectName("infoLabel")
    lay.addWidget(cap)
    pm = designer_pixmap(logo_height)
    pic = QLabel()
    pic.setObjectName("designerLogo")
    pic.setAlignment(Qt.AlignCenter)
    if pm is not None:
        pic.setPixmap(pm)
        lay.addWidget(pic)
    name = QLabel(f"<b>{DESIGNER_NAME}</b> &nbsp;·&nbsp; {DESIGNER_YEAR}")
    name.setObjectName("designerName")
    name.setTextFormat(Qt.RichText)
    name.setAlignment(Qt.AlignCenter)
    name.setLayoutDirection(Qt.LeftToRight)
    lay.addWidget(name)
    box.designer_logo = pic
    return box


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("about_title"))
        self.resize(560, 660)
        outer = QVBoxLayout(self)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        about = QWidget()
        lay = QVBoxLayout(about)
        logo = logo_pixmap(240)
        if logo is not None:
            pic = QLabel()
            pic.setPixmap(logo)
            pic.setAlignment(Qt.AlignCenter)
            lay.addWidget(pic)
            ver = QLabel(tr("about_version", v=__version__))
            ver.setAlignment(Qt.AlignCenter)
            lay.addWidget(ver)
        else:
            head = QHBoxLayout()
            icon = QLabel()
            icon.setPixmap(app_icon().pixmap(QSize(64, 64)))
            head.addWidget(icon, 0, Qt.AlignTop)
            txt = QVBoxLayout()
            name = QLabel(tr("app_name"))
            f = QFont(self.font())
            f.setPointSizeF(f.pointSizeF() * 1.6)
            f.setBold(True)
            name.setFont(f)
            txt.addWidget(name)
            txt.addWidget(QLabel(tr("app_subtitle")))
            txt.addWidget(QLabel(tr("about_version", v=__version__)))
            head.addLayout(txt, 1)
            lay.addLayout(head)
        self.designer = designer_section(110)
        lay.addWidget(self.designer)
        body = QLabel(tr("about_body") + "\n\n" + tr("about_credits"))
        body.setWordWrap(True)
        lay.addWidget(body)
        lay.addStretch(1)
        self.tabs.addTab(about, tr("about_tab_about"))

        tree = QTreeWidget()
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.setHeaderLabels([tr("col_code"), tr("col_format"), tr("col_ext"),
                              tr("about_read"), tr("about_write")])
        for fmt in all_formats():
            it = QTreeWidgetItem([str(fmt.code), fmt.name, "\u200e" + "; ".join("*" + e for e in fmt.extensions),
                                  tr("yes") if fmt.can_read else tr("no"),
                                  tr("yes") if fmt.can_write else tr("no")])
            for c in (0, 3, 4):
                it.setTextAlignment(c, Qt.AlignCenter)
            tree.addTopLevelItem(it)
        hdr = tree.header()
        hdr.setStretchLastSection(False)
        for c in range(5):
            hdr.setSectionResizeMode(c, QHeaderView.Stretch if c == 1 else QHeaderView.ResizeToContents)
        self.tabs.addTab(tree, tr("about_formats"))
        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.button(QDialogButtonBox.Ok).setText(tr("ok"))
        bb.accepted.connect(self.accept)
        outer.addWidget(bb)


# ======================================================================= shortcuts
class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from . import i18n
        self.setWindowTitle(tr("shortcuts_title"))
        self.resize(620, 560)
        lay = QVBoxLayout(self)
        tree = QTreeWidget()
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.setHeaderLabels([tr("sc_col_keys"), tr("sc_col_action")])
        ar = i18n.language() == "ar"
        for keys, en, arabic in i18n.SHORTCUTS:
            k = i18n.SHORTCUT_KEYS_AR.get(keys, keys) if ar else keys
            it = QTreeWidgetItem(["\u2066" + k + "\u2069" if not any('\u0600' <= ch <= '\u06ff' for ch in k) else k,
                                  arabic if ar else en])
            tree.addTopLevelItem(it)
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        lay.addWidget(tree, 1)
        self.tree = tree
        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.button(QDialogButtonBox.Ok).setText(tr("ok"))
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)


# ======================================================================= GammaVision / MAESTRO
def program_path() -> str:
    """Path to put in GammaVision/MAESTRO's "Program" field."""
    import sys
    if getattr(sys, "frozen", False):
        return sys.executable
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    return str(pyw if pyw.exists() else exe)


def program_arguments_prefix() -> str:
    import sys
    return "" if getattr(sys, "frozen", False) else "-m spectramaster.gui "


# (title key, arguments) -- $(FullName) / $(FullBase) are GammaVision/MAESTRO macros
INTEGRATION_CASES = [
    ("gv_case_import", "-0 $(FullName) -1 $(FullBase).CHN"),
    ("gv_case_export_cnf", "-1 $(FullName) -16 $(FullBase).CNF"),
    ("gv_case_export_spe", "-0 $(FullName) -7 $(FullBase).SPE"),
]


class IntegrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("gv_title"))
        self.resize(720, 560)
        lay = QVBoxLayout(self)
        intro = QLabel(tr("gv_intro"))
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.RichText)
        lay.addWidget(intro)
        form = QFormLayout()
        self.fields: dict[str, QLineEdit] = {}

        def row(label: str, value: str, key: str):
            edit = QLineEdit(value)
            edit.setReadOnly(True)
            edit.setLayoutDirection(Qt.LeftToRight)
            edit.setCursorPosition(0)
            btn = QPushButton(tr("gv_copy"))
            btn.clicked.connect(lambda _=False, v=value: self.copy(v))
            h = QHBoxLayout()
            h.addWidget(edit, 1)
            h.addWidget(btn)
            form.addRow(label, h)
            self.fields[key] = edit

        row(tr("gv_program"), program_path(), "program")
        prefix = program_arguments_prefix()
        for key, args in INTEGRATION_CASES:
            row(tr(key), prefix + args, key)
        lay.addLayout(form)
        notes = QLabel(tr("gv_notes"))
        notes.setWordWrap(True)
        notes.setTextFormat(Qt.RichText)
        lay.addWidget(notes, 1, Qt.AlignTop)
        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.button(QDialogButtonBox.Ok).setText(tr("ok"))
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)

    @staticmethod
    def copy(text: str) -> None:
        QApplication.clipboard().setText(text)

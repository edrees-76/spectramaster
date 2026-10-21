"""Batch analysis dialog (Release F, F3d) over :mod:`spectramaster.lab.batch`.

Files / folder -> ``scan`` + ``group_items`` (worker thread) -> table of groups -> the user assigns
a setup (efficiency curve, sample geometry, geometry-mismatch permission, identification library,
nuclides) to the groups to analyse -> ``run_batch`` (worker thread, progress, cancel) -> result
table -> CSV (``write_csv``).  **No calibration is applied automatically**: a group without a
setup is reported "not analysed" by the engine.  Unreadable files are listed with their error.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QMessageBox, QProgressBar, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from . import i18n
from . import identification_library as idl
from .worker import start_call
from .workflow_strings import wtr


class _Cancelled(Exception):
    pass


class BatchRunWorker(QObject):
    """``run_batch`` in a QThread.  Cancelling raises from the progress callback (called before
    each spectrum), so the engine stops between two spectra.

    Signals: progress(i, n), done(rows), failed(message), cancelled()"""

    progress = Signal(int, int)
    done = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, groups, setups):
        super().__init__()
        self.groups, self.setups = groups, setups
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    @Slot()
    def run(self) -> None:
        from ..lab.batch import run_batch

        def progress(i, n):
            if self._cancel:
                raise _Cancelled()
            self.progress.emit(i, n)
        try:
            rows = run_batch(self.groups, self.setups, progress)
        except _Cancelled:
            self.cancelled.emit()
            return
        except Exception as exc:  # engine error -> message, never a crash
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(rows)


def _scan_and_group(paths, tol):
    from ..lab.batch import group_items, scan
    items = scan(paths)
    return items, group_items(items, tol)


def status_label(status: str) -> str:
    """Translated row status of ``run_batch`` (engine details stay as they are)."""
    for prefix, key in (("not analysed", "st_not_analysed"), ("failed: ", "st_failed"), ("refused: ", "st_refused")):
        if status.startswith(prefix):
            return wtr(key, msg=status[len(prefix):])
    return {"analysed": wtr("st_analysed"), "identified (no efficiency calibration)": wtr("st_identified"),
            "no nuclide identified": wtr("st_none")}.get(status, status)


def _cell(key: str, value) -> str:
    if value is None or value == "":
        return ""
    if key == "status":
        return status_label(str(value))
    if key == "identified":
        return wtr("yes") if value else wtr("no")
    if key == "file":
        return i18n.bidi_path(Path(str(value)).name)
    if isinstance(value, float):
        return i18n.ltr(f"{value:.4g}")
    if key in ("index", "group", "start"):
        return i18n.ltr(value)
    return str(value)


class BatchAnalysisDialog(QDialog):
    """Non-modal; ``message`` / file prompts are methods so tests can replace them."""

    def __init__(self, parent=None, settings=None, paths: Sequence = ()):
        super().__init__(parent)
        from ..lab.batch import CSV_KEYS
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.setWindowTitle(wtr("batch_title"))
        self.resize(1100, 800)
        self.settings = settings
        self.paths: list[Path] = []
        self.items: list = []
        self.groups: list = []
        self.setups: dict = {}          # group id -> lab.batch.BatchSetup
        self.setup_text: dict = {}      # group id -> displayed summary
        self.setup_inputs: dict = {}    # group id -> the editor values it came from
        self.rows: list[dict] = []
        self.keys = list(CSV_KEYS)
        self.busy = False
        self.last_error = ""
        self._thread: Optional[QThread] = None
        self._worker: Optional[BatchRunWorker] = None

        lay = QVBoxLayout(self)
        intro = QLabel(wtr("batch_intro"))
        intro.setWordWrap(True)
        lay.addWidget(intro)

        row = QHBoxLayout()
        b = QPushButton(wtr("batch_add_files"))
        b.clicked.connect(self.browse_files)
        row.addWidget(b)
        b = QPushButton(wtr("batch_add_folder"))
        b.clicked.connect(self.browse_folder)
        row.addWidget(b)
        b = QPushButton(wtr("batch_clear"))
        b.clicked.connect(self.clear_files)
        row.addWidget(b)
        self.files_label = QLabel()
        row.addWidget(self.files_label)
        row.addStretch(1)
        row.addWidget(QLabel(wtr("batch_tol")))
        self.tol_spin = QDoubleSpinBox()
        self.tol_spin.setRange(0.01, 100.0)
        self.tol_spin.setDecimals(2)
        self.tol_spin.setValue(1.0)
        row.addWidget(self.tol_spin)
        self.btn_scan = QPushButton(wtr("batch_scan"))
        self.btn_scan.clicked.connect(self.scan)
        row.addWidget(self.btn_scan)
        lay.addLayout(row)

        split = QSplitter(Qt.Vertical)
        top = QWidget()
        tl = QHBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        gbox = QGroupBox(wtr("batch_groups"))
        gl = QVBoxLayout(gbox)
        self.group_table = QTableWidget(0, 3)
        self.group_table.setHorizontalHeaderLabels([wtr("col_group"), wtr("col_desc"), wtr("col_setup")])
        self.group_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.group_table.horizontalHeader().setStretchLastSection(True)
        self.group_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.group_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.group_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.group_table.itemSelectionChanged.connect(self._group_selected)
        gl.addWidget(self.group_table, 1)
        gl.addWidget(QLabel(wtr("batch_errors")))
        self.error_list = QListWidget()
        self.error_list.setMaximumHeight(90)
        gl.addWidget(self.error_list)
        tl.addWidget(gbox, 3)

        sbox = QGroupBox(wtr("setup_box"))
        form = QFormLayout(sbox)
        self.curve_edit, r = self._path_row("batch_curve_none", self.browse_curve)
        form.addRow(wtr("batch_curve"), r)
        self.geo_edit, r = self._path_row("batch_geometry_none", self.browse_geometry)
        form.addRow(wtr("batch_geometry"), r)
        self.mismatch_check = QCheckBox(wtr("batch_mismatch"))
        form.addRow("", self.mismatch_check)
        self.app_combo = QComboBox()
        for a in idl.CHOICES:
            self.app_combo.addItem(idl.library_label(a), a)
        self.app_combo.setCurrentIndex(max(0, self.app_combo.findData(idl.GUI_DEFAULT)))
        form.addRow(wtr("batch_app"), self.app_combo)
        self.nuc_edit = QLineEdit()
        self.nuc_edit.setLayoutDirection(Qt.LeftToRight)
        self.nuc_edit.setToolTip(wtr("batch_nuclides_tip"))
        self.nuc_edit.setPlaceholderText(wtr("batch_nuclides_tip"))
        form.addRow(wtr("batch_nuclides"), self.nuc_edit)
        br = QHBoxLayout()
        self.btn_assign = QPushButton(wtr("batch_assign"))
        self.btn_assign.clicked.connect(self.assign_from_editor)
        br.addWidget(self.btn_assign)
        self.btn_unassign = QPushButton(wtr("batch_unassign"))
        self.btn_unassign.clicked.connect(self.unassign_selected)
        br.addWidget(self.btn_unassign)
        br.addStretch(1)
        form.addRow("", br)
        tl.addWidget(sbox, 2)
        split.addWidget(top)

        self.result_table = QTableWidget(0, len(self.keys))
        self.result_table.setHorizontalHeaderLabels([wtr("rc_" + k) for k in self.keys])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        split.addWidget(self.result_table)
        split.setSizes([360, 340])
        lay.addWidget(split, 1)

        row = QHBoxLayout()
        self.btn_run = QPushButton(wtr("batch_run"))
        self.btn_run.clicked.connect(self.run)
        row.addWidget(self.btn_run)
        self.btn_cancel = QPushButton(wtr("batch_cancel"))
        self.btn_cancel.clicked.connect(self.cancel)
        self.btn_cancel.setEnabled(False)
        row.addWidget(self.btn_cancel)
        self.progress = QProgressBar()
        self.progress.setLayoutDirection(Qt.LeftToRight)
        row.addWidget(self.progress, 1)
        self.status_label = QLabel()
        row.addWidget(self.status_label, 1)
        self.btn_save = QPushButton(wtr("batch_save"))
        self.btn_save.clicked.connect(lambda: self.save_csv())
        self.btn_save.setEnabled(False)
        row.addWidget(self.btn_save)
        b = QPushButton(wtr("batch_close"))
        b.clicked.connect(self.close)
        row.addWidget(b)
        lay.addLayout(row)
        self.add_paths(paths)
        self._update_buttons()

    # ------------------------------------------------------------------ helpers
    def _path_row(self, placeholder_key: str, browse):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit()
        edit.setLayoutDirection(Qt.LeftToRight)
        edit.setPlaceholderText(wtr(placeholder_key))
        h.addWidget(edit, 1)
        b = QPushButton(wtr("batch_browse"))
        b.clicked.connect(browse)
        h.addWidget(b)
        b = QPushButton(wtr("batch_clear_field"))
        b.clicked.connect(edit.clear)
        h.addWidget(b)
        return edit, w

    def message(self, text: str) -> None:
        self.last_error = text
        QMessageBox.warning(self, wtr("batch_title"), text)

    def _folder(self, name: str) -> str:
        return self.settings.folder(name) if self.settings is not None else ""

    def _update_buttons(self) -> None:
        idle = not self.busy
        self.btn_scan.setEnabled(idle and bool(self.paths))
        self.btn_run.setEnabled(idle and bool(self.groups))
        self.btn_cancel.setEnabled(self.busy and self._worker is not None)
        self.btn_assign.setEnabled(idle and bool(self.groups))
        self.btn_unassign.setEnabled(idle and bool(self.groups))
        self.btn_save.setEnabled(idle and bool(self.rows))
        self.files_label.setText(wtr("batch_n_files", n=i18n.ltr(len(self.paths))))

    # ------------------------------------------------------------------ files
    def browse_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, wtr("batch_add_files"), self._folder("multi"))
        if paths:
            if self.settings is not None:
                self.settings.set_folder("multi", paths[0])
            self.add_paths(paths)

    def browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, wtr("batch_add_folder"), self._folder("folder_in"))
        if folder:
            self.add_folder(folder)

    def add_folder(self, folder, recursive: bool = True) -> None:
        from .dialogs import scan_spectrum_files
        self.add_paths(scan_spectrum_files(Path(folder), recursive))

    def add_paths(self, paths) -> None:
        known = set(self.paths)
        self.paths += [p for p in (Path(x) for x in paths) if p not in known]
        self._update_buttons()

    def clear_files(self) -> None:
        if self.busy:
            return
        self.paths, self.items, self.groups, self.rows = [], [], [], []
        self.setups.clear(), self.setup_text.clear(), self.setup_inputs.clear()
        self._fill_groups()
        self._fill_results()
        self.error_list.clear()
        self._update_buttons()

    # ------------------------------------------------------------------ scan + group (worker)
    def scan(self) -> bool:
        if self.busy:
            return False
        if not self.paths:
            self.message(wtr("batch_no_files"))
            return False
        self._set_busy(True, wtr("batch_scanning"))
        paths, tol = list(self.paths), self.tol_spin.value()
        start_call(self, lambda: _scan_and_group(paths, tol), self._on_scanned, self._on_scan_failed)
        return True

    def _on_scanned(self, result) -> None:
        self.items, self.groups = result
        self.setups.clear(), self.setup_text.clear(), self.setup_inputs.clear()
        self.rows = []
        self._fill_groups()
        self._fill_results()
        self.error_list.clear()
        for it in self.items:
            if it.error:
                self.error_list.addItem(f"{i18n.bidi_path(it.path)}: {it.error}")
        self._set_busy(False)
        if self.groups:
            self.group_table.selectRow(0)

    def _on_scan_failed(self, msg: str) -> None:
        self._set_busy(False)
        self.message(wtr("batch_failed", msg=msg))

    def _fill_groups(self) -> None:
        t = self.group_table
        t.setRowCount(len(self.groups))
        for r, g in enumerate(self.groups):
            vals = [i18n.ltr(g.id), i18n.ltr(g.describe()), self.setup_text.get(g.id, wtr("setup_none"))]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 2 and g.id not in self.setups:
                    it.setForeground(Qt.darkGray)
                t.setItem(r, c, it)

    # ------------------------------------------------------------------ setups
    def selected_group_id(self) -> Optional[int]:
        r = self.group_table.currentRow()
        return self.groups[r].id if 0 <= r < len(self.groups) else None

    def _group_selected(self) -> None:
        gid = self.selected_group_id()
        v = self.setup_inputs.get(gid)
        if v is None:
            return
        self.curve_edit.setText(v["curve_path"] or "")
        self.geo_edit.setText(v["geometry_path"] or "")
        self.mismatch_check.setChecked(v["allow_mismatch"])
        self.app_combo.setCurrentIndex(max(0, self.app_combo.findData(v["application"])))
        self.nuc_edit.setText(", ".join(v["nuclides"]))

    def browse_curve(self) -> None:
        from ..analysis import efficiency as eff
        path, _ = QFileDialog.getOpenFileName(self, wtr("batch_curve"), str(eff.default_curve_dir()), "JSON (*.json)")
        if path:
            self.curve_edit.setText(path)

    def browse_geometry(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, wtr("batch_geometry"), self._folder("open"), "JSON (*.json)")
        if path:
            self.geo_edit.setText(path)

    def assign_from_editor(self) -> bool:
        gid = self.selected_group_id()
        if gid is None:
            self.message(wtr("batch_select_group"))
            return False
        nuclides = [n.strip() for n in self.nuc_edit.text().replace(";", ",").split(",") if n.strip()]
        return self.assign_setup(gid, self.curve_edit.text().strip() or None, self.geo_edit.text().strip() or None,
                                 self.mismatch_check.isChecked(), self.app_combo.currentData(), nuclides)

    def assign_setup(self, group_id: int, curve_path=None, geometry_path=None, allow_mismatch: bool = False,
                     application: str = idl.GUI_DEFAULT, nuclides: Sequence[str] = ()) -> bool:
        """Assign a setup to one group (the user's explicit choice).  The curve is read with the
        validation-aware loader (a calibration record next to it decides its status)."""
        from ..lab.batch import BatchSetup
        from ..lab.detector import MeasurementGeometry
        from .efficiency_dialog import load_curve_file
        curve = geometry = None
        if curve_path:
            try:
                curve, _rec, _issues = load_curve_file(curve_path)
            except Exception as exc:
                self.message(wtr("batch_curve_err", path=i18n.bidi_path(curve_path), msg=f"{type(exc).__name__}: {exc}"))
                return False
        if geometry_path:
            try:
                geometry = MeasurementGeometry.from_dict(json.loads(Path(geometry_path).read_text(encoding="utf-8")))
            except Exception as exc:
                self.message(wtr("batch_geometry_err", path=i18n.bidi_path(geometry_path),
                                 msg=f"{type(exc).__name__}: {exc}"))
                return False
        application = application if idl.valid(application) else idl.GUI_DEFAULT
        self.setups[group_id] = BatchSetup(curve=curve, geometry=geometry, allow_geometry_mismatch=allow_mismatch,
                                           application=application, nuclides=list(nuclides))
        self.setup_inputs[group_id] = {"curve_path": curve_path, "geometry_path": geometry_path,
                                       "allow_mismatch": allow_mismatch, "application": application,
                                       "nuclides": list(nuclides)}
        parts = [wtr("setup_curve", name=i18n.ltr(curve.name or Path(curve_path).stem)) if curve is not None
                 else wtr("setup_no_curve"), idl.library_label(application, short=True)]
        if geometry is not None:
            parts.append(wtr("setup_geometry", name=i18n.ltr(geometry.name)))
        if allow_mismatch:
            parts.append(wtr("setup_mismatch"))
        if nuclides:
            parts.append(i18n.ltr(", ".join(nuclides)))
        self.setup_text[group_id] = "; ".join(parts)
        self._fill_groups()
        return True

    def unassign_selected(self) -> None:
        gid = self.selected_group_id()
        if gid is None:
            return
        for d in (self.setups, self.setup_text, self.setup_inputs):
            d.pop(gid, None)
        self._fill_groups()

    # ------------------------------------------------------------------ run (worker)
    def is_running(self) -> bool:
        """A batch run or a scan is in progress (scans cannot be cancelled, only waited for)."""
        return self._thread is not None or bool(self.__dict__.get("_call_threads"))

    def run(self) -> bool:
        if self.busy:
            return False
        if not self.groups:
            self.message(wtr("batch_no_groups"))
            return False
        self.rows = []
        self._fill_results()
        total = sum(len(g.items) for g in self.groups)
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(0)
        thread = QThread(self)
        worker = BatchRunWorker(list(self.groups), dict(self.setups))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.done.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        for sig in (worker.done, worker.failed, worker.cancelled):
            sig.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)
        self._thread, self._worker = thread, worker
        self._set_busy(True, wtr("batch_running", i=i18n.ltr(0), n=i18n.ltr(total)))
        thread.start()
        return True

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def wait(self, ms: int = 30000) -> None:
        threads = [t for t, _w in self.__dict__.get("_call_threads", [])]
        for t in threads + ([self._thread] if self._thread is not None else []):
            t.wait(ms)

    def _on_progress(self, i: int, n: int) -> None:
        self.progress.setValue(i)
        self.status_label.setText(wtr("batch_running", i=i18n.ltr(i), n=i18n.ltr(n)))

    def _on_done(self, rows) -> None:
        self.rows = list(rows)
        self._fill_results()
        n_na = len({(r["file"], r["index"]) for r in self.rows if str(r.get("status", "")).startswith("not analysed")})
        self.progress.setValue(self.progress.maximum())
        self.status_label.setText(wtr("batch_done", rows=i18n.ltr(len(self.rows)), na=i18n.ltr(n_na)))

    def _on_failed(self, msg: str) -> None:
        self.status_label.setText("")
        self.message(wtr("batch_failed", msg=msg))

    def _on_cancelled(self) -> None:
        self.status_label.setText(wtr("batch_cancelled"))

    def _on_thread_finished(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._thread = self._worker = None
        text = self.status_label.text()
        self._set_busy(False)
        self.status_label.setText(text)

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self.busy = busy
        self.status_label.setText(text if busy else "")
        self._update_buttons()

    def _fill_results(self) -> None:
        t = self.result_table
        t.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            for c, k in enumerate(self.keys):
                it = QTableWidgetItem(_cell(k, row.get(k)))
                if k == "file":
                    it.setToolTip(str(row.get(k, "")))
                if k == "status" and str(row.get(k, "")).startswith("not analysed"):
                    it.setForeground(Qt.darkGray)
                if k in ("activity_bq", "u_bq", "mda_bq", "live_time"):
                    it.setTextAlignment(Qt.AlignAbsolute | Qt.AlignRight | Qt.AlignVCenter)
                t.setItem(r, c, it)

    # ------------------------------------------------------------------ CSV
    def save_csv(self, path=None) -> Optional[Path]:
        from ..lab.batch import write_csv
        if not self.rows:
            return None
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, wtr("batch_save"),
                                                  str(Path(self._folder("export")) / "batch_analysis.csv"),
                                                  "CSV (*.csv)")
            if not path:
                return None
        try:
            out = write_csv(path, self.rows)
        except Exception as exc:
            self.message(wtr("batch_save_err", path=i18n.bidi_path(path), msg=f"{type(exc).__name__}: {exc}"))
            return None
        if self.settings is not None:
            self.settings.set_folder("export", out)
        self.status_label.setText(wtr("batch_saved", path=i18n.bidi_path(out)))
        return out

    def closeEvent(self, ev):
        if self.is_running():
            self.cancel()
            self.wait()
        super().closeEvent(ev)


__all__ = ["BatchAnalysisDialog", "BatchRunWorker", "status_label"]

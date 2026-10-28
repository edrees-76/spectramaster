"""Tools › Detector QC...: QC tracks, control charts, measurement table, exports.

Opened from the main window by :func:`install_qc_menu` (adds the action to the
``Tools`` menu, creating that menu if no other module has yet).
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtCore import QDateTime, QItemSelectionModel, QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateTimeEdit, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout,
                               QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPlainTextEdit,
                               QProgressDialog, QPushButton, QScrollArea, QSpinBox, QSplitter,
                               QTableWidget, QTableWidgetItem, QTabWidget, QToolBar, QVBoxLayout, QWidget)

from ..tools import qc
from . import qc_i18n  # noqa: F401
from .i18n import is_rtl, tr
from .worker import quit_on
from .qc_charts import (ControlChart, METRIC_ORDER, export_qc_pdf, metric_title, ordered_series,
                        save_chart, _fmt)

STATUS_COLORS = {qc.STATUS_FAIL: QColor("#fbe3e4"), qc.STATUS_WARN: QColor("#fff4d6"),
                 qc.STATUS_EXCLUDED: QColor("#eceff1"), qc.STATUS_NA: QColor("#f1f3f5")}


def qc_dir_from_settings(settings) -> Path:
    try:
        v = settings.get("qc/dir", "") if settings is not None else ""
    except Exception:
        v = ""
    return Path(str(v)) if v else qc.default_qc_dir()


# ------------------------------------------------------------------ lines text
def lines_to_text(lines: Sequence[qc.MonitoredLine]) -> str:
    out = []
    for l in lines:
        t = f"{l.energy:g}"
        if l.nuclide or l.fwhm_max:
            t += f":{l.nuclide}"
        if l.fwhm_max:
            t += f":{l.fwhm_max:g}"
        out.append(t)
    return ", ".join(out)


def parse_lines(text: str) -> list[qc.MonitoredLine]:
    """``"661.657:Cs-137, 1332.492:Co-60:2.0"`` -> MonitoredLine list (ValueError if invalid)."""
    out = []
    for part in re.split(r"[,;\n]+", text):
        part = part.strip()
        if not part:
            continue
        bits = [b.strip() for b in part.split(":")]
        e = float(bits[0])
        if e <= 0:
            raise ValueError(part)
        nuc = bits[1] if len(bits) > 1 else ""
        fm = float(bits[2]) if len(bits) > 2 and bits[2] else None
        out.append(qc.MonitoredLine(e, nuc, fm))
    return sorted(out, key=lambda l: l.energy)


# records: a semicolon, a new line, or a comma followed by the next "nuclide=" (a comma inside a number
# is refused by parse_activity, round5_acceptance_protocol.md)
_ACT_SPLIT = re.compile(r";|\n|,(?=\s*[A-Za-z]{1,2}-\d[A-Za-z0-9]*\s*=)")


def _parse_activity(text: str) -> dict[str, float]:
    """{nuclide: Bq} of "Cs-137=37000, Co-60=1 uCi": a unit after the number is optional (Bq).
    A record that is not "nuclide=activity" raises ValueError."""
    from .activity_input import parse_activity
    out = {}
    for part in _ACT_SPLIT.split(text):
        if not part.strip():
            continue
        k, sep, v = part.partition("=")
        if not sep or not k.strip() or not v.strip():
            raise ValueError(f"not nuclide=activity: {part.strip()!r}")
        out[k.strip()] = parse_activity(v)
    return out


# ------------------------------------------------------------------ track dialog
class TrackDialog(QDialog):
    def __init__(self, track: Optional[qc.QCTrack] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("qc_track_dialog"))
        self.setLayoutDirection(Qt.RightToLeft if is_rtl() else Qt.LeftToRight)
        self.track = track or qc.QCTrack(name="")
        if track is None:
            self.track.set_lines_from_preset("Cs-137")
        t = self.track
        form = QFormLayout()
        self.name = QLineEdit(t.name)
        self.detector = QLineEdit(t.detector)
        self.dettype = QComboBox()
        self.dettype.addItems(["HPGe", "NaI", "LaBr3", "CZT"])
        self.dettype.setCurrentText(t.detector_type)
        self.kind = QComboBox()
        self.kind.addItem(tr("qc_kind_source"), "source")
        self.kind.addItem(tr("qc_kind_background"), "background")
        self.kind.setCurrentIndex(1 if t.kind == "background" else 0)
        src_row = QHBoxLayout()
        self.source = QComboBox()
        self.source.setEditable(True)
        self.source.addItems(list(qc.SOURCE_PRESETS))
        self.source.setCurrentText(t.source)
        self.preset_btn = QPushButton(tr("qc_f_preset"))
        self.preset_btn.clicked.connect(self._apply_preset)
        src_row.addWidget(self.source, 1)
        src_row.addWidget(self.preset_btn)
        self.lines = QLineEdit(lines_to_text(t.lines))
        self.lines.setPlaceholderText(tr("qc_lines_hint"))
        self.lines.setToolTip(tr("qc_lines_hint"))
        self.lines.setLayoutDirection(Qt.LeftToRight)
        ref_row = QHBoxLayout()
        self.ref_auto = QCheckBox(tr("qc_f_refdate_auto"))
        self.ref_date = QDateTimeEdit(QDateTime(t.reference_date) if t.reference_date
                                      else QDateTime.currentDateTime())
        self.ref_date.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.ref_date.setCalendarPopup(True)
        self.ref_auto.setChecked(t.reference_date is None)
        self.ref_auto.toggled.connect(lambda on: self.ref_date.setEnabled(not on))
        self.ref_date.setEnabled(t.reference_date is not None)
        ref_row.addWidget(self.ref_date, 1)
        ref_row.addWidget(self.ref_auto)
        self.activity = QLineEdit(", ".join(f"{k}={v:g}" for k, v in t.reference_activity.items()))
        self.activity.setPlaceholderText(tr("qc_activity_hint"))
        self.match = self._dspin(t.match_tol_kev, 0.05, 200, 2)
        self.cmode = QComboBox()
        self.cmode.addItem(tr("qc_cmode_file"), "file")
        self.cmode.addItem(tr("qc_cmode_fixed"), "fixed")
        self.cmode.setCurrentIndex(1 if t.centroid_mode == "fixed" else 0)
        bk = QHBoxLayout()
        self.bkg_lo = self._dspin(t.bkg_window[0] or 0.0, 0, 1e5, 1, special=True)
        self.bkg_hi = self._dspin(t.bkg_window[1] or 0.0, 0, 1e5, 1, special=True)
        bk.addWidget(self.bkg_lo)
        bk.addWidget(QLabel("—"))
        bk.addWidget(self.bkg_hi)
        self.base_n = QSpinBox()
        self.base_n.setRange(2, 10000)
        self.base_n.setValue(t.baseline_n)
        bp = QHBoxLayout()
        self.base_use_period = QCheckBox()
        self.base_from = QDateTimeEdit(QDateTime(t.baseline_start) if t.baseline_start else QDateTime.currentDateTime())
        self.base_to = QDateTimeEdit(QDateTime(t.baseline_end) if t.baseline_end else QDateTime.currentDateTime())
        for w in (self.base_from, self.base_to):
            w.setDisplayFormat("yyyy-MM-dd")
            w.setCalendarPopup(True)
        self.base_use_period.setChecked(bool(t.baseline_start or t.baseline_end))
        bp.addWidget(self.base_use_period)
        bp.addWidget(self.base_from, 1)
        bp.addWidget(QLabel("—"))
        bp.addWidget(self.base_to, 1)
        rules = QHBoxLayout()
        self.rule_boxes = {}
        for r in qc.WESTGARD_RULES:
            cb = QCheckBox(r)
            cb.setChecked(r in t.rules)
            self.rule_boxes[r] = cb
            rules.addWidget(cb)
        self.ctol = self._dspin(t.centroid_tol_kev or 0.0, 0, 100, 2, special=True)
        self.rtol = self._dspin(t.rate_tol_pct or 0.0, 0, 100, 1, special=True)
        self.btol = self._dspin(t.bkg_tol_pct or 0.0, 0, 1000, 1, special=True)
        self.notes = QPlainTextEdit(t.notes)
        self.notes.setMaximumHeight(60)
        form.addRow(tr("qc_f_name"), self.name)
        form.addRow(tr("qc_f_detector"), self.detector)
        form.addRow(tr("qc_f_dettype"), self.dettype)
        form.addRow(tr("qc_f_kind"), self.kind)
        form.addRow(tr("qc_f_source"), src_row)
        form.addRow(tr("qc_f_lines"), self.lines)
        form.addRow(tr("qc_f_refdate"), ref_row)
        form.addRow(tr("qc_f_activity"), self.activity)
        form.addRow(tr("qc_f_match"), self.match)
        form.addRow(tr("qc_f_cmode"), self.cmode)
        form.addRow(tr("qc_f_bkg"), bk)
        form.addRow(tr("qc_f_baseline_n"), self.base_n)
        form.addRow(tr("qc_f_baseline_period"), bp)
        form.addRow(tr("qc_f_rules"), rules)
        form.addRow(tr("qc_f_ctol"), self.ctol)
        form.addRow(tr("qc_f_rtol"), self.rtol)
        form.addRow(tr("qc_f_btol"), self.btol)
        form.addRow(tr("qc_f_notes"), self.notes)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(tr("ok"))
        bb.button(QDialogButtonBox.Cancel).setText(tr("cancel"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(bb)

    def _dspin(self, v, lo, hi, dec, special=False):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(dec)
        s.setValue(float(v))
        if special:
            s.setSpecialValueText(tr("qc_off"))
        return s

    def _apply_preset(self):
        src = self.source.currentText().strip()
        try:
            lines = qc.preset_lines(src)
        except Exception:
            lines = []
        if lines:
            self.lines.setText(lines_to_text(lines))
        if src.lower().startswith("background"):
            self.kind.setCurrentIndex(1)

    def accept(self):
        try:
            lines = parse_lines(self.lines.text())
            act = _parse_activity(self.activity.text())
        except ValueError as exc:
            QMessageBox.warning(self, tr("qc_track_dialog"), tr("qc_bad_lines", msg=str(exc)))
            return
        t = self.track
        t.name = self.name.text().strip() or (self.detector.text().strip() + " " + self.source.currentText()).strip() \
            or "QC"
        t.detector = self.detector.text().strip()
        t.detector_type = self.dettype.currentText()
        t.kind = self.kind.currentData()
        t.source = self.source.currentText().strip()
        t.lines = lines
        t.reference_date = None if self.ref_auto.isChecked() else self.ref_date.dateTime().toPython()
        t.reference_activity = act
        t.match_tol_kev = self.match.value()
        t.centroid_mode = self.cmode.currentData()
        t.bkg_window = (self.bkg_lo.value() or None, self.bkg_hi.value() or None)
        t.baseline_n = self.base_n.value()
        if self.base_use_period.isChecked():
            t.baseline_start = self.base_from.dateTime().toPython().replace(hour=0, minute=0, second=0)
            t.baseline_end = self.base_to.dateTime().toPython().replace(hour=23, minute=59, second=59)
        else:
            t.baseline_start = t.baseline_end = None
        t.rules = [r for r, cb in self.rule_boxes.items() if cb.isChecked()]
        t.centroid_tol_kev = self.ctol.value() or None
        t.rate_tol_pct = self.rtol.value() or None
        t.bkg_tol_pct = self.btol.value() or None
        t.notes = self.notes.toPlainText()
        super().accept()


# ------------------------------------------------------------------ import worker
class ImportWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)

    def __init__(self, track: qc.QCTrack, paths, reanalyse: bool = False):
        super().__init__()
        self.track, self.paths, self.reanalyse = track, list(paths), reanalyse
        self._cancel = False

    def cancel(self):
        self._cancel = True

    @Slot()
    def run(self):
        def cb(i, n, path):
            self.progress.emit(i, n, path)
            return not self._cancel
        try:
            if self.reanalyse:
                res = qc.reanalyse(self.track, cb)
            else:
                res = qc.import_paths(self.track, self.paths, progress=cb)
        except Exception as exc:  # never crash the GUI
            res = qc.ImportResult(errors=[("", f"{type(exc).__name__}: {exc}")])
        self.finished.emit(res)


# ------------------------------------------------------------------ window
class QCWindow(QMainWindow):
    def __init__(self, store: Optional[qc.QCStore] = None, main_window=None, settings=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.settings = settings
        self.store = store or qc.QCStore(qc_dir_from_settings(settings))
        self.track: Optional[qc.QCTrack] = None
        self.ev: Optional[qc.QCEvaluation] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[ImportWorker] = None
        self.last_import: Optional[qc.ImportResult] = None
        self.setWindowTitle(tr("qc_title"))
        self.setLayoutDirection(Qt.RightToLeft if is_rtl() else Qt.LeftToRight)
        self.resize(1250, 820)
        self._build()
        self.reload_tracks()

    # ---------------------------------------------------------------- build
    def _build(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(tb)

        def act(key, slot, shortcut=None):
            a = QAction(tr(key), self)
            a.triggered.connect(lambda checked=False: slot())
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            tb.addAction(a)
            return a

        self.act_add_files = act("qc_add_files", self.add_files_dialog)
        self.act_add_folder = act("qc_add_folder", self.add_folder_dialog)
        self.act_add_current = act("qc_add_current", self.add_current_spectrum)
        self.act_reanalyse = act("qc_reanalyse", self.reanalyse)
        tb.addSeparator()
        self.act_png = act("qc_export_png", lambda: self.export_charts(fmt="png"))
        self.act_svg = act("qc_export_svg", lambda: self.export_charts(fmt="svg"))
        self.act_xlsx = act("qc_export_xlsx", self.export_excel)
        self.act_pdf = act("qc_export_pdf", self.export_pdf, "Ctrl+P")

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 6, 6, 6)
        ll.addWidget(QLabel(f"<b>{tr('qc_tracks')}</b>"))
        self.track_list = QListWidget()
        self.track_list.currentRowChanged.connect(self._on_track_row)
        ll.addWidget(self.track_list, 1)
        row = QHBoxLayout()
        for key, slot in (("qc_new", self.new_track_dialog), ("qc_edit", self.edit_track_dialog),
                          ("qc_delete", self.delete_track)):
            b = QPushButton(tr(key))
            b.clicked.connect(slot)
            row.addWidget(b)
        ll.addLayout(row)

        self.tabs = QTabWidget()
        # charts
        charts = QWidget()
        cl = QVBoxLayout(charts)
        top = QHBoxLayout()
        top.addWidget(QLabel(tr("qc_line")))
        self.line_combo = QComboBox()
        self.line_combo.currentIndexChanged.connect(self._refresh_charts)
        top.addWidget(self.line_combo)
        top.addStretch(1)
        cl.addLayout(top)
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        self.charts: dict[str, ControlChart] = {}
        for i, m in enumerate(METRIC_ORDER):
            c = ControlChart()
            c.setMinimumHeight(250)
            c.pointClicked.connect(self.select_measurement)
            self.charts[m] = c
            grid.addWidget(c, i, 0)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(grid_host)
        cl.addWidget(sc, 1)
        self.tabs.addTab(charts, tr("qc_tab_charts"))
        # measurements
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_menu)
        self.table.itemSelectionChanged.connect(self._on_table_selection)
        self.table.setAlternatingRowColors(False)
        self.tabs.addTab(self.table, tr("qc_tab_table"))
        self.stats_table = QTableWidget()
        self.stats_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabs.addTab(self.stats_table, tr("qc_tab_stats"))
        self.viol_table = QTableWidget()
        self.viol_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.viol_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.viol_table.cellDoubleClicked.connect(self._on_violation_double)
        self.tabs.addTab(self.viol_table, tr("qc_tab_violations"))

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(self.tabs)
        split.setStretchFactor(1, 1)
        split.setSizes([240, 1000])
        self.setCentralWidget(split)
        self.summary = QLabel()
        self.statusBar().addWidget(self.summary, 1)

    # ---------------------------------------------------------------- tracks
    def reload_tracks(self, select_id: Optional[str] = None):
        self.tracks = self.store.list_tracks()
        self.track_list.blockSignals(True)
        self.track_list.clear()
        for t in self.tracks:
            it = QListWidgetItem(f"{t.name}\n{t.detector} · {t.source} · {len(t.measurements)}")
            it.setData(Qt.UserRole, t.id)
            self.track_list.addItem(it)
        self.track_list.blockSignals(False)
        idx = 0
        if select_id:
            idx = next((i for i, t in enumerate(self.tracks) if t.id == select_id), 0)
        if self.tracks:
            self.track_list.setCurrentRow(idx)
            self._on_track_row(idx)
        else:
            self.set_track(None)

    def _on_track_row(self, row: int):
        self.set_track(self.tracks[row] if 0 <= row < len(self.tracks) else None)

    def set_track(self, track: Optional[qc.QCTrack]):
        self.track = track
        self.line_combo.blockSignals(True)
        self.line_combo.clear()
        if track:
            for l in track.lines:
                self.line_combo.addItem(l.label, l.key)
        self.line_combo.blockSignals(False)
        self.refresh()

    def add_track(self, track: qc.QCTrack) -> qc.QCTrack:
        self.store.save(track)
        self.reload_tracks(track.id)
        return track

    def new_track_dialog(self):
        dlg = TrackDialog(None, self)
        if dlg.exec() == QDialog.Accepted:
            self.add_track(dlg.track)

    def edit_track_dialog(self):
        if not self._need_track():
            return
        dlg = TrackDialog(self.track, self)
        if dlg.exec() == QDialog.Accepted:
            self.save_track()
            self.reload_tracks(self.track.id)

    def delete_track(self, confirm: bool = True):
        if not self.track:
            return
        if confirm and QMessageBox.question(self, tr("qc_title"), tr("qc_confirm_delete", name=self.track.name)) \
                != QMessageBox.Yes:
            return
        self.store.delete(self.track)
        self.reload_tracks()

    def save_track(self):
        if self.track:
            self.store.save(self.track)

    def _need_track(self) -> bool:
        if self.track is None:
            QMessageBox.information(self, tr("qc_title"), tr("qc_need_track"))
            return False
        return True

    # ---------------------------------------------------------------- adding
    def add_files_dialog(self):
        if not self._need_track():
            return
        start = self.settings.folder("qc") if self.settings is not None else ""
        files, _ = QFileDialog.getOpenFileNames(self, tr("qc_add_files"), start)
        if files:
            if self.settings is not None:
                self.settings.set_folder("qc", files[0])
            self.add_paths(files)

    def add_folder_dialog(self):
        if not self._need_track():
            return
        start = self.settings.folder("qc") if self.settings is not None else ""
        d = QFileDialog.getExistingDirectory(self, tr("qc_add_folder"), start)
        if d:
            if self.settings is not None:
                self.settings.set_folder("qc", d)
            self.add_paths([d])

    def add_paths(self, paths, background: bool = True, reanalyse: bool = False) -> Optional[qc.ImportResult]:
        """Import files/folders into the current track (worker thread unless background=False)."""
        if not self.track:
            return None
        if not background:
            res = qc.reanalyse(self.track) if reanalyse else qc.import_paths(self.track, paths)
            self._import_done(res, quiet=True)
            return res
        self._progress = QProgressDialog(tr("qc_importing"), tr("act_cancel") if tr("act_cancel") != "act_cancel"
                                         else "Cancel", 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setMinimumDuration(0)
        self._thread = QThread(self)
        self._worker = ImportWorker(self.track, paths, reanalyse)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._import_done)
        quit_on(self._thread, self._worker.finished)
        self._progress.canceled.connect(self._worker.cancel)
        self._thread.start()
        return None

    def _on_progress(self, i, n, path):
        if self._progress is not None:
            self._progress.setMaximum(max(n, 1))
            self._progress.setValue(i)
            self._progress.setLabelText(f"{tr('qc_importing')}\n{Path(path).name if path else ''}")

    def _import_done(self, res: qc.ImportResult, quiet: bool = False):
        self.last_import = res
        if getattr(self, "_progress", None) is not None:
            self._progress.close()
            self._progress = None
        self.save_track()
        self.refresh()
        self._update_list_item()
        msg = tr("qc_import_done", added=len(res.added), dup=len(res.duplicates), err=len(res.errors))
        self.statusBar().showMessage(msg, 10000)
        if not quiet and res.errors:
            QMessageBox.warning(self, tr("qc_title"), msg + "\n\n" + "\n".join(
                f"{Path(p).name}: {e}" for p, e in res.errors[:15]))

    def reanalyse(self):
        if self._need_track():
            self.add_paths([], reanalyse=True)

    def add_current_spectrum(self, spectrum=None) -> Optional[qc.QCMeasurement]:
        if not self._need_track():
            return None
        if spectrum is None and self.main_window is not None:
            try:
                spectrum = self.main_window.current_spectrum()
            except Exception:
                spectrum = None
        if spectrum is None:
            QMessageBox.information(self, tr("qc_title"), tr("qc_no_current"))
            return None
        m = qc.add_spectrum(self.track, spectrum, spectrum.source_path or "")
        if m is None:
            QMessageBox.information(self, tr("qc_title"), tr("qc_duplicate"))
            return None
        self.track.measurements = self.track.sorted_measurements()
        self.save_track()
        self.refresh()
        self._update_list_item()
        return m

    def _update_list_item(self):
        it = self.track_list.currentItem()
        if it is not None and self.track is not None:
            it.setText(f"{self.track.name}\n{self.track.detector} · {self.track.source} · "
                       f"{len(self.track.measurements)}")

    # ---------------------------------------------------------------- refresh
    def current_line(self) -> Optional[qc.MonitoredLine]:
        if not self.track or not self.track.lines:
            return None
        return self.track.line(self.line_combo.currentData()) or self.track.lines[0]

    def refresh(self):
        self.ev = qc.evaluate(self.track) if self.track else None
        self._refresh_charts()
        self._fill_table()
        self._fill_stats()
        self._fill_violations()
        if self.ev:
            c = self.ev.counts()
            self.summary.setText(tr("qc_status_summary", n=len(self.track.measurements), ok=c.get("OK", 0),
                                    warn=c.get("WARN", 0), fail=c.get("FAIL", 0), excl=c.get("EXCL", 0)))
        else:
            self.summary.setText("")

    def _names(self):
        return {m.id: m.file_name for m in self.track.measurements} if self.track else {}

    def _refresh_charts(self):
        line = self.current_line()
        names = self._names()
        for m, chart in self.charts.items():
            s = None
            if self.ev is not None:
                s = self.ev.get("background") if m == "background" else (self.ev.get(m, line) if line else None)
            chart.set_series(s, metric_title(s) if s else "", names)

    def _fill_table(self):
        t, ev = self.track, self.ev
        tab = self.table
        tab.clear()
        if not t or ev is None:
            tab.setRowCount(0)
            tab.setColumnCount(0)
            return
        head = [tr("qc_col_date"), tr("qc_col_file"), tr("qc_col_live"), tr("qc_col_dead")]
        for l in t.lines:
            head += [f"E {l.energy:.1f}", f"FWHM {l.energy:.1f}", f"cps {l.energy:.1f}"]
        head += [tr("qc_col_bkg"), tr("qc_col_status"), tr("qc_col_rules"), tr("qc_col_note")]
        ms = t.sorted_measurements()
        tab.setColumnCount(len(head))
        tab.setHorizontalHeaderLabels(head)
        tab.setRowCount(len(ms))
        for r, m in enumerate(ms):
            vals = [f"{m.date:%Y-%m-%d %H:%M}" if m.date else "—", m.file_name,
                    f"{m.live_time:.1f}" if m.live_time else "—",
                    f"{m.dead_time_pct:.2f}" if m.dead_time_pct is not None else "—"]
            for l in t.lines:
                lr = ev.line_results.get(m.id, {}).get(l.key)
                vals += ([f"{lr.centroid_kev:.3f}" if lr.centroid_kev is not None else "—",
                          f"{lr.fwhm_kev:.3f}" if lr.fwhm_kev is not None else "—", _fmt(lr.rate_corr)]
                         if lr else ["—"] * 3)
            st = ev.status.get(m.id, "")
            vals += [_fmt(m.window_rate), st, ", ".join(ev.flags.get(m.id, [])), m.note]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 0:
                    it.setData(Qt.UserRole, m.id)
                    it.setToolTip(m.source_path)
                if st in STATUS_COLORS:
                    it.setBackground(STATUS_COLORS[st])
                tab.setItem(r, c, it)
        tab.resizeColumnsToContents()
        tab.horizontalHeader().setSectionResizeMode(len(head) - 2, QHeaderView.Interactive)

    def _fill_stats(self):
        tab = self.stats_table
        tab.clear()
        head = [tr("qc_col_series"), tr("qc_col_unit"), tr("qc_col_n"), tr("qc_col_mean"), tr("qc_col_sd"),
                tr("qc_col_cv"), "-3σ", "-2σ", "+2σ", "+3σ", tr("qc_tol"), tr("qc_col_trend"),
                tr("qc_col_fail"), tr("qc_col_warn")]
        tab.setColumnCount(len(head))
        tab.setHorizontalHeaderLabels(head)
        rows = ordered_series(self.ev) if self.ev else []
        tab.setRowCount(len(rows))
        for r, s in enumerate(rows):
            cv = 100 * s.sd / abs(s.mean) if s.sd and s.mean else None
            tol = " / ".join(_fmt(v) for v in (s.tol_lo, s.tol_hi) if v is not None) or "—"
            vals = [metric_title(s), s.unit, str(s.n_baseline), _fmt(s.mean), _fmt(s.sd),
                    f"{cv:.2f}" if cv is not None else "—", *(_fmt(v) for v in (*s.limits(3)[:1], *s.limits(2),
                                                                               *s.limits(3)[1:])),
                    tol, _fmt(s.slope_per_year()),
                    str(sum(1 for p in s.points if p.status == qc.STATUS_FAIL)),
                    str(sum(1 for p in s.points if p.status == qc.STATUS_WARN))]
            for c, v in enumerate(vals):
                tab.setItem(r, c, QTableWidgetItem(v))
        tab.resizeColumnsToContents()

    def _fill_violations(self):
        tab = self.viol_table
        tab.clear()
        head = [tr("qc_col_date"), "→", "N", tr("qc_col_file"), tr("qc_col_series"), tr("qc_col_rule"),
                tr("qc_col_message")]
        tab.setColumnCount(len(head))
        tab.setHorizontalHeaderLabels(head)
        runs = qc.violation_runs(self.ev) if self.ev else []
        names = self._names()
        tab.setRowCount(len(runs))
        for r, v in enumerate(runs):
            vals = [f"{v.first:%Y-%m-%d}" if v.first else "—", f"{v.last:%Y-%m-%d}" if v.n > 1 and v.last else "",
                    str(v.n), names.get(v.first_mid, ""), v.series, v.rule, v.message]
            for c, x in enumerate(vals):
                it = QTableWidgetItem(x)
                if c == 0:
                    it.setData(Qt.UserRole, v.first_mid)
                tab.setItem(r, c, it)
        tab.resizeColumnsToContents()

    # ---------------------------------------------------------------- selection
    def _row_of(self, mid: str) -> int:
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it is not None and it.data(Qt.UserRole) == mid:
                return r
        return -1

    def select_measurement(self, mid: str):
        r = self._row_of(mid)
        if r >= 0:
            sm = self.table.selectionModel()
            sm.blockSignals(True)
            sm.select(self.table.model().index(r, 0),
                      QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
            sm.blockSignals(False)
            self.table.scrollToItem(self.table.item(r, 0))
        for c in self.charts.values():
            c.set_selected(mid)

    def selected_ids(self) -> list[str]:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.table.item(r, 0).data(Qt.UserRole) for r in rows if self.table.item(r, 0)]

    def _on_table_selection(self):
        ids = self.selected_ids()
        for c in self.charts.values():
            c.set_selected(ids[0] if ids else None)

    def _on_violation_double(self, row, _col):
        it = self.viol_table.item(row, 0)
        if it is not None:
            self.tabs.setCurrentIndex(0)
            self.select_measurement(it.data(Qt.UserRole))

    def _table_menu(self, pos):
        ids = self.selected_ids()
        if not ids or not self.track:
            return
        menu = QMenu(self)
        ms = [self.track.measurement(i) for i in ids]
        any_excl = any(m.excluded for m in ms if m)
        a_ex = menu.addAction(tr("qc_include") if any_excl else tr("qc_exclude"))
        a_note = menu.addAction(tr("qc_set_note"))
        a_show = menu.addAction(tr("qc_open_main")) if self.main_window is not None else None
        menu.addSeparator()
        a_rm = menu.addAction(tr("qc_remove"))
        a = menu.exec(self.table.viewport().mapToGlobal(pos))
        if a is a_ex:
            self.set_excluded(ids, not any_excl)
        elif a is a_note:
            text, ok = QInputDialog.getText(self, tr("qc_set_note"), tr("qc_col_note"), text=ms[0].note)
            if ok:
                for m in ms:
                    m.note = text
                self.save_track()
                self.refresh()
        elif a_show is not None and a is a_show and ms[0].source_path:
            try:
                self.main_window.load_file(ms[0].source_path, None)
                self.main_window.raise_()
            except Exception:
                pass
        elif a is a_rm:
            if QMessageBox.question(self, tr("qc_title"), tr("qc_confirm_remove", n=len(ids))) == QMessageBox.Yes:
                self.remove_measurements(ids)

    def set_excluded(self, ids, excluded: bool):
        for i in ids:
            m = self.track.measurement(i)
            if m:
                m.excluded = excluded
        self.save_track()
        self.refresh()

    def remove_measurements(self, ids):
        self.track.measurements = [m for m in self.track.measurements if m.id not in set(ids)]
        self.save_track()
        self.refresh()
        self._update_list_item()

    # ---------------------------------------------------------------- export
    def _ask_save(self, title, filt, default_name) -> Optional[str]:
        start = self.settings.folder("qc_export") if self.settings is not None else ""
        path, _ = QFileDialog.getSaveFileName(self, title, str(Path(start) / default_name) if start else default_name,
                                              filt)
        if path and self.settings is not None:
            self.settings.set_folder("qc_export", path)
        return path or None

    def _safe_name(self) -> str:
        return re.sub(r'[\\/:*?"<>|]+', "_", self.track.name).strip() or "qc"

    def export_charts(self, folder=None, fmt: str = "png") -> list[Path]:
        if not self._need_track():
            return []
        if folder is None:
            start = self.settings.folder("qc_export") if self.settings is not None else ""
            folder = QFileDialog.getExistingDirectory(self, tr(f"qc_export_{fmt}"), start)
            if not folder:
                return []
            if self.settings is not None:
                self.settings.set_folder("qc_export", folder)
        out = []
        for s in ordered_series(self.ev):
            out.append(save_chart(s, Path(folder) / f"{self._safe_name()}_{s.key.replace('@', '_')}.{fmt}"))
        self.statusBar().showMessage(tr("qc_saved", path=folder), 8000)
        return out

    def export_excel(self, path=None) -> Optional[Path]:
        if not self._need_track():
            return None
        path = path or self._ask_save(tr("qc_export_xlsx"), "Excel (*.xlsx)", f"{self._safe_name()}_QC.xlsx")
        if not path:
            return None
        p = qc.export_track_xlsx(self.track, path, self.ev)
        self.statusBar().showMessage(tr("qc_saved", path=p), 8000)
        return p

    def export_pdf(self, path=None) -> Optional[Path]:
        if not self._need_track():
            return None
        path = path or self._ask_save(tr("qc_export_pdf"), "PDF (*.pdf)", f"{self._safe_name()}_QC.pdf")
        if not path:
            return None
        p = export_qc_pdf(self.track, path, self.ev)
        self.statusBar().showMessage(tr("qc_saved", path=p), 8000)
        return p

    def closeEvent(self, ev):
        if self._thread is not None and self._thread.isRunning():
            if self._worker is not None:
                self._worker.cancel()
            self._thread.quit()
            self._thread.wait()                    # never destroy a running thread
        super().closeEvent(ev)


# ------------------------------------------------------------------ main-window hook
def open_qc_window(main_window) -> QCWindow:
    w = getattr(main_window, "_qc_window", None)
    if w is None:
        w = QCWindow(main_window=main_window, settings=getattr(main_window, "settings", None))
        main_window._qc_window = w
    w.show()
    w.raise_()
    w.activateWindow()
    return w


def install_qc_menu(main_window) -> QAction:
    """Add Tools › Detector QC... (creates the Tools menu, objectName "menu_tools", if absent)."""
    mb = main_window.menuBar()
    menu = mb.findChild(QMenu, "menu_tools")
    if menu is None:
        menu = QMenu(tr("menu_tools"), mb)
        menu.setObjectName("menu_tools")
        help_menu = getattr(main_window, "menu_help", None)
        if help_menu is not None:
            mb.insertMenu(help_menu.menuAction(), menu)
        else:
            mb.addMenu(menu)
    act = QAction(tr("act_qc"), main_window)
    act.setObjectName("act_qc")
    act.triggered.connect(lambda checked=False: open_qc_window(main_window))
    menu.addAction(act)
    main_window.act_qc = act
    return act


def retranslate_qc_menu(main_window) -> None:
    act = getattr(main_window, "act_qc", None)
    if act is not None:
        act.setText(tr("act_qc"))
    menu = main_window.menuBar().findChild(QMenu, "menu_tools")
    if menu is not None and not menu.property("owned_elsewhere"):
        menu.setTitle(tr("menu_tools"))

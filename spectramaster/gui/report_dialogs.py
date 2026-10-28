"""Report options dialog, batch report dialog and its worker."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                               QRadioButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from . import i18n
from . import report as rp
from .i18n import tr
from .identification_library import stored_library
from .worker import quit_on
from .plot import Y_MODES

MODES = ("print", "preview", "pdf", "batch")


# ============================================================================ options dialog
class ReportOptionsDialog(QDialog):
    """Choose the report content; remembers the last options and named templates in settings."""

    def __init__(self, settings, mode: str = "pdf", options: Optional[rp.ReportOptions] = None,
                 parent=None):
        super().__init__(parent)
        self.settings = settings
        self.mode = mode if mode in MODES else "pdf"
        self.setWindowTitle(tr("rep_dlg_title"))
        self.setSizeGripEnabled(True)
        self.resize(620, 560)
        lay = QVBoxLayout(self)

        # --- templates
        trow = QHBoxLayout()
        trow.addWidget(QLabel(tr("rep_template")))
        self.template_combo = QComboBox()
        self.template_combo.setMinimumContentsLength(22)
        self.template_combo.activated.connect(self._template_chosen)
        trow.addWidget(self.template_combo, 1)
        self.save_tmpl_btn = QPushButton(tr("rep_tmpl_save"))
        self.save_tmpl_btn.clicked.connect(lambda: self.save_template())
        self.del_tmpl_btn = QPushButton(tr("rep_tmpl_delete"))
        self.del_tmpl_btn.clicked.connect(lambda: self.delete_template())
        trow.addWidget(self.save_tmpl_btn)
        trow.addWidget(self.del_tmpl_btn)
        lay.addLayout(trow)

        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        self._build_header_tab()
        self._build_content_tab()
        self._build_plot_tab()
        self._build_page_tab()

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_key = {"print": "rep_btn_print", "preview": "rep_btn_preview", "pdf": "rep_btn_pdf",
                  "batch": "ok"}[self.mode]
        bb.button(QDialogButtonBox.Ok).setText(tr(ok_key))
        bb.button(QDialogButtonBox.Cancel).setText(tr("cancel"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        self.set_options(options if options is not None else rp.load_options(settings))
        self._fill_templates()

    # ----------------------------------------------------------- building
    def _build_header_tab(self) -> None:
        w = QWidget()
        f = QFormLayout(w)
        f.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.cb_header = QCheckBox(tr("rep_inc_header"))
        f.addRow(self.cb_header)
        self.ed_lab = QLineEdit()
        self.ed_dept = QLineEdit()
        self.ed_address = QPlainTextEdit()
        self.ed_address.setFixedHeight(self.fontMetrics().height() * 3 + 12)
        f.addRow(tr("rep_lab_name"), self.ed_lab)
        f.addRow(tr("rep_department"), self.ed_dept)
        f.addRow(tr("rep_address"), self.ed_address)
        logo_row = QHBoxLayout()
        self.cb_logo = QCheckBox(tr("rep_logo_use"))
        self.logo_preview = QLabel()
        self.logo_preview.setFixedSize(120, 44)
        self.logo_preview.setAlignment(Qt.AlignCenter)
        self.logo_preview.setStyleSheet("QLabel { border: 1px solid #d5dbe1; background: #ffffff; }")
        self.ed_logo = QLineEdit()
        self.ed_logo.setReadOnly(True)
        b1 = QPushButton(tr("rep_logo_browse"))
        b1.clicked.connect(self._browse_logo)
        b2 = QPushButton(tr("rep_logo_clear"))
        b2.clicked.connect(lambda: self._set_logo(""))
        logo_row.addWidget(self.cb_logo)
        logo_row.addWidget(self.logo_preview)
        logo_row.addWidget(b1)
        logo_row.addWidget(b2)
        f.addRow(tr("rep_logo"), logo_row)
        f.addRow("", self.ed_logo)
        self.ed_title = QLineEdit()
        self.ed_title.setPlaceholderText(tr("rep_default_title"))
        self.ed_report_no = QLineEdit()
        self.ed_operator = QLineEdit()
        self.cb_date = QCheckBox(tr("rep_show_date"))
        f.addRow(tr("rep_title"), self.ed_title)
        f.addRow(tr("rep_report_no_lbl"), self.ed_report_no)
        f.addRow(tr("rep_operator_lbl"), self.ed_operator)
        f.addRow("", self.cb_date)
        self.tabs.addTab(w, tr("rep_tab_header"))

    def _build_content_tab(self) -> None:
        w = QWidget()
        g = QGridLayout(w)
        r = 0
        self.cb_info = QCheckBox(tr("rep_inc_info"))
        g.addWidget(self.cb_info, r, 0, 1, 3); r += 1
        self.cb_plot_inc = QCheckBox(tr("rep_inc_plot"))
        g.addWidget(self.cb_plot_inc, r, 0, 1, 3); r += 1
        self.cb_peaks = QCheckBox(tr("rep_inc_peaks"))
        g.addWidget(self.cb_peaks, r, 0, 1, 3); r += 1
        self.cb_peaks_ident = QCheckBox(tr("rep_peaks_identified"))
        g.addWidget(self.cb_peaks_ident, r, 1);
        self.sp_min_sig = QDoubleSpinBox()
        self.sp_min_sig.setRange(0, 1000)
        self.sp_min_sig.setDecimals(1)
        self.sp_min_sig.setSingleStep(0.5)
        sig_row = QHBoxLayout()
        sig_row.addWidget(QLabel(tr("rep_peaks_min_sig")))
        sig_row.addWidget(self.sp_min_sig)
        sig_row.addStretch(1)
        g.addLayout(sig_row, r, 2); r += 1
        self.cb_nuc = QCheckBox(tr("rep_inc_nuclides"))
        g.addWidget(self.cb_nuc, r, 0, 1, 3); r += 1
        self.cb_nuc_bg = QCheckBox(tr("rep_nuc_hide_bg"))
        g.addWidget(self.cb_nuc_bg, r, 1)
        self.sp_min_conf = QSpinBox()
        self.sp_min_conf.setRange(0, 100)
        self.sp_min_conf.setSuffix(" %")
        conf_row = QHBoxLayout()
        conf_row.addWidget(QLabel(tr("rep_nuc_min_conf")))
        conf_row.addWidget(self.sp_min_conf)
        conf_row.addStretch(1)
        g.addLayout(conf_row, r, 2); r += 1
        self.cb_rois = QCheckBox(tr("rep_inc_rois"))
        g.addWidget(self.cb_rois, r, 0, 1, 3); r += 1
        from .context_strings import ctr
        self.cb_context = QCheckBox(ctr("rep_inc"))
        g.addWidget(self.cb_context, r, 0, 1, 3); r += 1
        self.cb_extra = QCheckBox(tr("rep_inc_extra"))
        g.addWidget(self.cb_extra, r, 0, 1, 3); r += 1
        self.cb_notes = QCheckBox(tr("rep_inc_notes"))
        g.addWidget(self.cb_notes, r, 0, 1, 3); r += 1
        self.ed_notes = QPlainTextEdit()
        self.ed_notes.setMinimumHeight(70)
        g.addWidget(self.ed_notes, r, 1, 1, 2); r += 1
        self.cb_sign = QCheckBox(tr("rep_inc_sign"))
        g.addWidget(self.cb_sign, r, 0, 1, 3); r += 1
        self.ed_sig = {}
        for key in ("prepared", "reviewed", "approved"):
            e = QLineEdit()
            self.ed_sig[key] = e
            g.addWidget(QLabel(tr(f"rep_sig_{key}_lbl")), r, 1)
            g.addWidget(e, r, 2); r += 1
        g.setColumnMinimumWidth(0, 18)
        g.setColumnStretch(2, 1)
        g.setRowStretch(r, 1)
        self.cb_peaks.toggled.connect(self._sync_enabled)
        self.cb_nuc.toggled.connect(self._sync_enabled)
        self.cb_notes.toggled.connect(self._sync_enabled)
        self.cb_sign.toggled.connect(self._sync_enabled)
        self.tabs.addTab(w, tr("rep_tab_content"))

    def _combo(self, items: Sequence[tuple[str, str]]) -> QComboBox:
        c = QComboBox()
        for data, key in items:
            c.addItem(tr(key), data)
        return c

    def _build_plot_tab(self) -> None:
        w = QWidget()
        f = QFormLayout(w)
        self.co_view = self._combo([("current", "rep_view_current"), ("full", "rep_view_full")])
        self.co_scale = self._combo([("current", "rep_as_screen")] +
                                    [(m, f"act_y_{m}") for m in Y_MODES])
        for i in range(self.co_scale.count()):
            self.co_scale.setItemText(i, self.co_scale.itemText(i).replace("&", ""))
        self.co_axis = self._combo([("current", "rep_as_screen"), ("energy", "rep_axis_energy"),
                                    ("channel", "rep_axis_channel")])
        self.co_size = self._combo([(k, f"rep_size_{k}") for k in rp.PLOT_SIZES])
        f.addRow(tr("rep_plot_view"), self.co_view)
        f.addRow(tr("rep_plot_scale"), self.co_scale)
        f.addRow(tr("rep_plot_axis"), self.co_axis)
        f.addRow(tr("rep_plot_size"), self.co_size)
        self.cb_labels = QCheckBox(tr("rep_plot_labels"))
        self.cb_plot_rois = QCheckBox(tr("rep_plot_rois"))
        self.cb_overlays = QCheckBox(tr("rep_plot_overlays"))
        self.cb_vector = QCheckBox(tr("rep_plot_vector"))
        for cb in (self.cb_labels, self.cb_plot_rois, self.cb_overlays, self.cb_vector):
            f.addRow("", cb)
        self.tabs.addTab(w, tr("rep_tab_plot"))

    def _build_page_tab(self) -> None:
        w = QWidget()
        f = QFormLayout(w)
        self.co_paper = QComboBox()
        for p in rp.PAPERS:
            self.co_paper.addItem(p, p)
        self.co_orient = self._combo([("portrait", "rep_portrait"), ("landscape", "rep_landscape")])
        self.sp_margin = QDoubleSpinBox()
        self.sp_margin.setRange(5, 40)
        self.sp_margin.setDecimals(0)
        self.sp_margin.setSuffix(" mm")
        self.co_lang = QComboBox()
        self.co_lang.addItem(tr("rep_lang_ui"), "ui")
        for code, name in i18n.LANGUAGES.items():
            self.co_lang.addItem(name, code)
        f.addRow(tr("rep_paper"), self.co_paper)
        f.addRow(tr("rep_orientation"), self.co_orient)
        f.addRow(tr("rep_margins"), self.sp_margin)
        f.addRow(tr("rep_language"), self.co_lang)
        box = QVBoxLayout()
        self.cb_f_pages = QCheckBox(tr("rep_footer_pages"))
        self.cb_f_file = QCheckBox(tr("rep_footer_file"))
        self.cb_f_credit = QCheckBox(tr("rep_footer_credit"))
        self.cb_f_dt = QCheckBox(tr("rep_footer_datetime"))
        for cb in (self.cb_f_pages, self.cb_f_file, self.cb_f_dt, self.cb_f_credit):
            box.addWidget(cb)
        f.addRow(tr("rep_footer"), box)
        self.tabs.addTab(w, tr("rep_tab_page"))

    # ------------------------------------------------------------- state
    @staticmethod
    def _set_combo(c: QComboBox, data) -> None:
        i = c.findData(data)
        if i >= 0:
            c.setCurrentIndex(i)

    def _set_logo(self, path: str) -> None:
        self.ed_logo.setText(path)
        pm = QPixmap(path) if path else QPixmap()
        if pm.isNull():
            self.logo_preview.clear()
        else:
            self.logo_preview.setPixmap(pm.scaled(self.logo_preview.size() * 0.92, Qt.KeepAspectRatio,
                                                  Qt.SmoothTransformation))

    def _browse_logo(self) -> None:
        start = self.ed_logo.text() or self.settings.folder("logo")
        path, _ = QFileDialog.getOpenFileName(self, tr("rep_logo"), start, tr("rep_logo_filter"))
        if path:
            self.settings.set_folder("logo", path)
            self._set_logo(os.path.normpath(path))
            self.cb_logo.setChecked(True)

    def _sync_enabled(self) -> None:
        self.cb_peaks_ident.setEnabled(self.cb_peaks.isChecked())
        self.sp_min_sig.setEnabled(self.cb_peaks.isChecked())
        self.cb_nuc_bg.setEnabled(self.cb_nuc.isChecked())
        self.sp_min_conf.setEnabled(self.cb_nuc.isChecked())
        self.ed_notes.setEnabled(self.cb_notes.isChecked())
        for e in self.ed_sig.values():
            e.setEnabled(self.cb_sign.isChecked())

    def set_options(self, o: rp.ReportOptions) -> None:
        o = o.normalized()
        self.cb_header.setChecked(o.header)
        self.ed_lab.setText(o.lab_name)
        self.ed_dept.setText(o.department)
        self.ed_address.setPlainText(o.address)
        self.cb_logo.setChecked(o.logo)
        self._set_logo(o.logo_path)
        self.ed_title.setText(o.title)
        self.ed_report_no.setText(o.report_no)
        self.ed_operator.setText(o.operator)
        self.cb_date.setChecked(o.show_date)
        self.cb_info.setChecked(o.info)
        self.cb_plot_inc.setChecked(o.plot)
        self.cb_peaks.setChecked(o.peaks)
        self.cb_peaks_ident.setChecked(o.peaks_identified_only)
        self.sp_min_sig.setValue(o.peaks_min_sig)
        self.cb_nuc.setChecked(o.nuclides)
        self.sp_min_conf.setValue(o.nuc_min_conf)
        self.cb_nuc_bg.setChecked(o.nuc_hide_background)
        self.cb_rois.setChecked(o.rois)
        self.cb_context.setChecked(o.context)
        self.cb_extra.setChecked(o.extra)
        self.cb_notes.setChecked(o.notes_on)
        self.ed_notes.setPlainText(o.notes)
        self.cb_sign.setChecked(o.signatures)
        self.ed_sig["prepared"].setText(o.sig_prepared)
        self.ed_sig["reviewed"].setText(o.sig_reviewed)
        self.ed_sig["approved"].setText(o.sig_approved)
        self._set_combo(self.co_view, o.plot_view)
        self._set_combo(self.co_scale, o.plot_scale)
        self._set_combo(self.co_axis, o.plot_axis)
        self._set_combo(self.co_size, o.plot_size)
        self.cb_labels.setChecked(o.plot_labels)
        self.cb_plot_rois.setChecked(o.plot_rois)
        self.cb_overlays.setChecked(o.plot_overlays)
        self.cb_vector.setChecked(o.plot_vector)
        self._set_combo(self.co_paper, o.paper)
        self._set_combo(self.co_orient, "landscape" if o.landscape else "portrait")
        self.sp_margin.setValue(o.margin_mm)
        self._set_combo(self.co_lang, o.language)
        self.cb_f_pages.setChecked(o.footer_pages)
        self.cb_f_file.setChecked(o.footer_file)
        self.cb_f_credit.setChecked(o.footer_credit)
        self.cb_f_dt.setChecked(o.footer_datetime)
        self._sync_enabled()

    def options(self) -> rp.ReportOptions:
        return rp.ReportOptions(
            header=self.cb_header.isChecked(), lab_name=self.ed_lab.text().strip(),
            department=self.ed_dept.text().strip(), address=self.ed_address.toPlainText().strip(),
            logo=self.cb_logo.isChecked(), logo_path=self.ed_logo.text().strip(),
            title=self.ed_title.text().strip(), report_no=self.ed_report_no.text().strip(),
            operator=self.ed_operator.text().strip(), show_date=self.cb_date.isChecked(),
            info=self.cb_info.isChecked(), plot=self.cb_plot_inc.isChecked(),
            plot_view=self.co_view.currentData(), plot_scale=self.co_scale.currentData(),
            plot_axis=self.co_axis.currentData(), plot_labels=self.cb_labels.isChecked(),
            plot_rois=self.cb_plot_rois.isChecked(), plot_overlays=self.cb_overlays.isChecked(),
            plot_size=self.co_size.currentData(), plot_vector=self.cb_vector.isChecked(),
            peaks=self.cb_peaks.isChecked(), peaks_identified_only=self.cb_peaks_ident.isChecked(),
            peaks_min_sig=self.sp_min_sig.value(), nuclides=self.cb_nuc.isChecked(),
            nuc_min_conf=self.sp_min_conf.value(), nuc_hide_background=self.cb_nuc_bg.isChecked(),
            rois=self.cb_rois.isChecked(), context=self.cb_context.isChecked(), extra=self.cb_extra.isChecked(),
            notes_on=self.cb_notes.isChecked(), notes=self.ed_notes.toPlainText().strip(),
            signatures=self.cb_sign.isChecked(), sig_prepared=self.ed_sig["prepared"].text().strip(),
            sig_reviewed=self.ed_sig["reviewed"].text().strip(),
            sig_approved=self.ed_sig["approved"].text().strip(),
            footer_pages=self.cb_f_pages.isChecked(), footer_file=self.cb_f_file.isChecked(),
            footer_credit=self.cb_f_credit.isChecked(), footer_datetime=self.cb_f_dt.isChecked(),
            paper=self.co_paper.currentData(), landscape=self.co_orient.currentData() == "landscape",
            margin_mm=self.sp_margin.value(), language=self.co_lang.currentData(),
        ).normalized()

    # --------------------------------------------------------- templates
    def _fill_templates(self, select: Optional[str] = None) -> None:
        c = self.template_combo
        c.blockSignals(True)
        c.clear()
        c.addItem(tr("rep_tmpl_current"), "")
        for key, label in rp.PRESET_KEYS.items():
            c.addItem("★ " + tr(label), f"preset:{key}")
        for name in rp.template_names(self.settings):
            c.addItem(name, name)
        if select:
            self._set_combo(c, select)
        c.blockSignals(False)
        self.del_tmpl_btn.setEnabled(self._user_template() is not None)

    def _user_template(self) -> Optional[str]:
        data = self.template_combo.currentData()
        return data if data and not str(data).startswith("preset:") else None

    def _template_chosen(self, _i: int = 0) -> None:
        data = self.template_combo.currentData()
        self.del_tmpl_btn.setEnabled(self._user_template() is not None)
        if not data:
            self.set_options(rp.load_options(self.settings))
            return
        o = rp.load_template(self.settings, data, self.options())
        if o is not None:
            self.set_options(o)

    def apply_template(self, name: str) -> bool:
        i = self.template_combo.findData(name)
        if i < 0:
            return False
        self.template_combo.setCurrentIndex(i)
        self._template_chosen(i)
        return True

    def save_template(self, name: Optional[str] = None) -> Optional[str]:
        if name is None:
            name, ok = QInputDialog.getText(self, tr("rep_tmpl_save"), tr("rep_tmpl_name"),
                                            text=self._user_template() or "")
            if not ok:
                return None
            name = name.strip()
            if not name:
                return None
            if name in rp.template_names(self.settings) and QMessageBox.question(
                    self, tr("rep_dlg_title"), tr("rep_tmpl_replace", name=name)) != QMessageBox.Yes:
                return None
        rp.save_template(self.settings, name, self.options())
        self._fill_templates(select=name)
        return name

    def delete_template(self, name: Optional[str] = None, confirm: bool = True) -> bool:
        name = name or self._user_template()
        if not name:
            return False
        if confirm and QMessageBox.question(self, tr("rep_dlg_title"),
                                            tr("rep_tmpl_delete_q", name=name)) != QMessageBox.Yes:
            return False
        ok = rp.delete_template(self.settings, name)
        self._fill_templates()
        return ok

    def accept(self) -> None:
        rp.save_options(self.settings, self.options())
        super().accept()


# ============================================================================ batch worker
class ReportBatchWorker(QObject):
    """Writes report PDFs for many files (move to a QThread; ``thread.started`` -> ``run``).

    Signals
      progress(i, n, source_path, ok, message)   -- after every file (1-based i)
      finished(ok_count, failed_count, total, cancelled)
    """

    progress = Signal(int, int, str, bool, str)
    finished = Signal(int, int, int, bool)

    def __init__(self, files: Sequence[Path], options: rp.ReportOptions, out_dir: Optional[Path] = None,
                 combined: Optional[Path] = None, analyse: bool = True, in_fmt=None,
                 application: str = "all"):
        super().__init__()
        self.application = application            # identification library
        self.files = [Path(f) for f in files]
        self.options = options
        self.out_dir = Path(out_dir) if out_dir else None
        self.combined = Path(combined) if combined else None
        self.analyse = analyse
        self.in_fmt = in_fmt
        self._cancel = False
        self.ok_count = self.failed_count = 0
        self.outputs: list[Path] = []

    def cancel(self) -> None:
        self._cancel = True

    @staticmethod
    def output_path(src: Path, out_dir: Optional[Path]) -> Path:
        return (out_dir or src.parent) / f"{src.stem}_report.pdf"

    @Slot()
    def run(self) -> None:
        from PySide6.QtGui import QPainter
        self.ok_count = self.failed_count = 0
        total = len(self.files)
        writer = painter = None
        pages_written = 0
        if self.combined is not None and total:
            self.combined.parent.mkdir(parents=True, exist_ok=True)
            writer = rp.pdf_writer(self.combined, self.options, self.combined.stem)
            painter = QPainter()
            if not painter.begin(writer):
                writer = painter = None
                self.failed_count = total
                self.progress.emit(total, total, "", False, f"cannot write {self.combined}")
                self.finished.emit(0, total, total, False)
                return
        try:
            for i, src in enumerate(self.files, 1):
                if self._cancel:
                    break
                try:
                    datas = rp.make_batch_data(src, self.analyse, self.in_fmt, lambda: self._cancel,
                                               self.application)
                    n_pages = 0
                    if writer is not None:
                        for d in datas:
                            n_pages += rp.Report(d, self.options).render(writer, painter,
                                                                         new_page=pages_written > 0)
                            pages_written += 1
                        msg = tr("rep_batch_pages", n=n_pages)
                    else:
                        out = self.output_path(src, self.out_dir)
                        out.parent.mkdir(parents=True, exist_ok=True)
                        w = rp.pdf_writer(out, self.options, src.name)
                        p = QPainter()
                        if not p.begin(w):
                            raise OSError(f"cannot write {out}")
                        try:
                            for k, d in enumerate(datas):
                                n_pages += rp.Report(d, self.options).render(w, p, new_page=k > 0)
                        finally:
                            p.end()
                        del w
                        self.outputs.append(out)
                        msg = f"{out.name} · " + tr("rep_batch_pages", n=n_pages)
                    self.ok_count += 1
                    self.progress.emit(i, total, str(src), True, msg)
                except Exception as exc:  # one bad file never stops the batch
                    self.failed_count += 1
                    self.progress.emit(i, total, str(src), False, f"{type(exc).__name__}: {exc}")
        finally:
            if painter is not None:
                painter.end()
                self.outputs.append(self.combined)
        done = self.ok_count + self.failed_count
        self.finished.emit(self.ok_count, self.failed_count, total, self._cancel and done < total)


# ============================================================================ batch dialog
class ReportBatchDialog(QDialog):
    """File > Print Reports for Multiple Files: one PDF per file or one combined PDF."""

    finishedReports = Signal(int, int, int, bool)

    def __init__(self, settings, files: Sequence[Path] = (), parent=None):
        super().__init__(parent)
        self.settings = settings
        self.options = rp.load_options(settings)
        self.setWindowTitle(tr("rep_batch_title"))
        self.resize(780, 580)
        self.setSizeGripEnabled(True)
        self._thread: Optional[QThread] = None
        self._worker: Optional[ReportBatchWorker] = None
        self.files: list[Path] = []
        self.scanning = False
        lay = QVBoxLayout(self)

        brow = QHBoxLayout()
        self.add_btn = QPushButton(tr("rep_batch_add"))
        self.add_btn.clicked.connect(self._add_files)
        self.add_dir_btn = QPushButton(tr("rep_batch_add_folder"))
        self.add_dir_btn.clicked.connect(self._add_folder)
        self.clear_btn = QPushButton(tr("rep_batch_clear"))
        self.clear_btn.clicked.connect(lambda: self.set_files([]))
        for b in (self.add_btn, self.add_dir_btn, self.clear_btn):
            brow.addWidget(b)
        brow.addStretch(1)
        self.count_label = QLabel()
        brow.addWidget(self.count_label)
        lay.addLayout(brow)
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        lay.addWidget(self.list, 1)

        form = QFormLayout()
        trow = QHBoxLayout()
        self.template_combo = QComboBox()
        self.template_combo.addItem(tr("rep_tmpl_current"), "")
        for key, label in rp.PRESET_KEYS.items():
            self.template_combo.addItem("★ " + tr(label), f"preset:{key}")
        for name in rp.template_names(settings):
            self.template_combo.addItem(name, name)
        self.template_combo.activated.connect(self._template_chosen)
        trow.addWidget(self.template_combo, 1)
        self.opts_btn = QPushButton(tr("rep_batch_options"))
        self.opts_btn.clicked.connect(self.edit_options)
        trow.addWidget(self.opts_btn)
        form.addRow(tr("rep_template"), trow)

        self.rb_per_file = QRadioButton(tr("rep_batch_per_file"))
        self.rb_combined = QRadioButton(tr("rep_batch_combined"))
        grp = QButtonGroup(self)
        grp.addButton(self.rb_per_file)
        grp.addButton(self.rb_combined)
        mrow = QHBoxLayout()
        mrow.addWidget(self.rb_per_file)
        mrow.addWidget(self.rb_combined)
        mrow.addStretch(1)
        form.addRow("", mrow)
        self.out_edit = QLineEdit(str(settings.get("report/batch_out_dir", "") or ""))
        ob = QPushButton(tr("batch_browse"))
        ob.clicked.connect(self._browse_out)
        orow = QHBoxLayout()
        orow.addWidget(self.out_edit, 1)
        orow.addWidget(ob)
        self.out_row_label = QLabel(tr("rep_batch_out_dir"))
        form.addRow(self.out_row_label, orow)
        self.combined_edit = QLineEdit(str(settings.get("report/batch_combined", "") or ""))
        cb = QPushButton(tr("batch_browse"))
        cb.clicked.connect(self._browse_combined)
        crow = QHBoxLayout()
        crow.addWidget(self.combined_edit, 1)
        crow.addWidget(cb)
        form.addRow(tr("rep_batch_combined_file"), crow)
        self.cb_analyse = QCheckBox(tr("rep_batch_analyse"))
        self.cb_analyse.setChecked(settings.get_bool("report/batch_analyse", True))
        form.addRow("", self.cb_analyse)
        lay.addLayout(form)
        combined = settings.get_bool("report/batch_combined_mode", False)
        (self.rb_combined if combined else self.rb_per_file).setChecked(True)

        self.progress = QProgressBar()
        lay.addWidget(self.progress)
        self.summary = QLabel(" ")
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.start_btn = QPushButton(tr("rep_batch_start"))
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
        self.set_files(files)

    # ------------------------------------------------------------- files
    def set_files(self, files: Sequence[Path]) -> None:
        self.files = []
        self.list.clear()
        self.add_files(files)

    def add_files(self, files: Sequence[Path]) -> None:
        seen = {os.path.normcase(str(f)) for f in self.files}
        for f in files:
            f = Path(f)
            key = os.path.normcase(str(f))
            if key in seen:
                continue
            seen.add(key)
            self.files.append(f)
            it = QListWidgetItem(f"{i18n.bidi_path(f.name)}    {i18n.bidi_path(f.parent)}")
            it.setToolTip(str(f))
            self.list.addItem(it)
        self.count_label.setText(tr("batch_files", n=len(self.files)))
        self.start_btn.setEnabled(bool(self.files) and not self.is_running() and not self.scanning)
        self.progress.setRange(0, max(1, len(self.files)))
        self.progress.setValue(0)

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, tr("rep_batch_add"), self.settings.folder("multi"))
        if paths:
            self.settings.set_folder("multi", paths[0])
            self.add_files([Path(p) for p in paths])

    def _add_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr("fd_choose_folder"), self.settings.folder("folder_in"))
        if d:
            self.add_folder(Path(d))

    def add_folder(self, folder: Path) -> bool:
        """Add the spectrum files of `folder`, searched on a worker thread (the add buttons and
        Start wait meanwhile)."""
        from .dialogs import scan_spectrum_files
        from .worker import start_call
        if self.scanning:
            return False
        self.scanning = True
        for b in (self.add_btn, self.add_dir_btn, self.clear_btn, self.start_btn):
            b.setEnabled(False)
        self.count_label.setText(tr("scan_folder_running"))
        start_call(self, lambda: scan_spectrum_files(Path(folder), True), self._folder_scanned,
                   self._folder_scan_failed)
        return True

    def _scan_finished(self) -> None:
        self.scanning = False
        for b in (self.add_btn, self.add_dir_btn, self.clear_btn):
            b.setEnabled(True)

    def _folder_scanned(self, files) -> None:
        self._scan_finished()
        self.add_files(files)

    def _folder_scan_failed(self, msg: str) -> None:
        self._scan_finished()
        self.add_files([])
        QMessageBox.warning(self, tr("err_title"), msg)

    def _browse_out(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr("fd_choose_folder"),
                                             self.out_edit.text() or self.settings.folder("export"))
        if d:
            self.out_edit.setText(os.path.normpath(d))

    def _browse_combined(self) -> None:
        start = self.combined_edit.text() or str(Path(self.settings.folder("export")) / "reports.pdf")
        path, _ = QFileDialog.getSaveFileName(self, tr("rep_fd_pdf_title"), start, tr("fd_pdf"))
        if path:
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            self.combined_edit.setText(os.path.normpath(path))
            self.rb_combined.setChecked(True)

    # ----------------------------------------------------------- options
    def _template_chosen(self, _i: int = 0) -> None:
        data = self.template_combo.currentData()
        base = rp.load_options(self.settings)
        o = rp.load_template(self.settings, data, base) if data else base
        self.options = o or base

    def select_template(self, name: str) -> bool:
        i = self.template_combo.findData(name)
        if i < 0:
            return False
        self.template_combo.setCurrentIndex(i)
        self._template_chosen(i)
        return True

    def edit_options(self) -> None:
        dlg = ReportOptionsDialog(self.settings, "batch", self.options, self)
        if dlg.exec() == QDialog.Accepted:
            self.options = dlg.options()

    # ----------------------------------------------------------- running
    def is_running(self) -> bool:
        """Reports being written or a folder being searched (a search cannot be cancelled, only
        waited for: round-6 review, Gemini M1)."""
        return self._thread is not None or self.scanning

    def start(self) -> bool:
        if self.is_running() or not self.files:
            return False
        combined = None
        out_dir = None
        if self.rb_combined.isChecked():
            text = self.combined_edit.text().strip()
            if not text:
                QMessageBox.warning(self, tr("err_title"), tr("rep_batch_need_out"))
                return False
            combined = Path(text if text.lower().endswith(".pdf") else text + ".pdf")
            self.settings.set("report/batch_combined", str(combined))
        else:
            text = self.out_edit.text().strip()
            out_dir = Path(text) if text else None      # empty: next to each input file
            self.settings.set("report/batch_out_dir", text)
        self.settings.set("report/batch_combined_mode", combined is not None)
        self.settings.set("report/batch_analyse", self.cb_analyse.isChecked())
        n = len(self.files)
        self.progress.setRange(0, n)
        self.progress.setValue(0)
        for r in range(self.list.count()):
            self.list.item(r).setForeground(Qt.black)
        self.summary.setText(tr("rep_batch_running", i=0, n=n))
        self._set_running(True)
        self._worker = ReportBatchWorker(self.files, self.options, out_dir, combined,
                                         self.cb_analyse.isChecked(), self.settings.input_format(),
                                         application=stored_library(self.settings))
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        quit_on(self._thread, self._worker.finished)
        self._thread.finished.connect(self._cleanup)
        self._thread.start()
        return True

    def _set_running(self, on: bool) -> None:
        for w in (self.add_btn, self.add_dir_btn, self.clear_btn, self.opts_btn, self.template_combo,
                  self.rb_combined, self.rb_per_file, self.cb_analyse, self.close_btn):
            w.setEnabled(not on)
        self.start_btn.setEnabled(not on and bool(self.files))
        self.cancel_btn.setEnabled(on)

    def _on_progress(self, i: int, n: int, src: str, ok: bool, msg: str) -> None:
        self.progress.setValue(i)
        self.summary.setText(tr("rep_batch_running", i=i, n=n))
        for r, f in enumerate(self.files):
            if os.path.normcase(str(f)) == os.path.normcase(src):
                it = self.list.item(r)
                it.setText(f"{f.name}    {'✔' if ok else '✖'} {msg}")
                it.setForeground(Qt.darkGreen if ok else Qt.red)
                self.list.scrollToItem(it)
                break

    def _on_finished(self, ok: int, bad: int, total: int, cancelled: bool) -> None:
        if cancelled:
            self.summary.setText(tr("rep_batch_cancelled", done=ok + bad, total=total, ok=ok, bad=bad))
        else:
            self.summary.setText(tr("rep_batch_summary", ok=ok, bad=bad, total=total))
        self.last_outputs = list(self._worker.outputs) if self._worker else []
        self.finishedReports.emit(ok, bad, total, cancelled)

    def _cleanup(self) -> None:
        if self._thread is not None:
            self._thread.deleteLater()
        if self._worker is not None:
            self._worker.deleteLater()
        self._thread = self._worker = None
        self._set_running(False)

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.cancel_btn.setEnabled(False)

    def wait(self, ms: Optional[int] = None) -> None:
        """No ``ms``: until the threads end (a running thread is never destroyed)."""
        threads = [t for t, _w in self.__dict__.get("_call_threads", [])]
        for t in threads + ([self._thread] if self._thread is not None else []):
            t.wait() if ms is None else t.wait(ms)
        if threads or self._thread is not None:
            QApplication.processEvents()

    def closeEvent(self, ev):
        if self.is_running():
            self.cancel()
            self.wait()
        super().closeEvent(ev)

    def reject(self):
        if self.is_running():
            return
        super().reject()

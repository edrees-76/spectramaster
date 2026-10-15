"""File > Print / Print Preview / Export Report as PDF / batch reports (MainWindow mix-in).

Kept out of ``app.py``: ``MainWindow`` only creates the actions through
``_create_report_actions`` and puts them in its menus / toolbar.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox, QStyle

from . import report as rp
from .i18n import tr
from .plot import PlotRenderer


class ReportActionsMixin:
    """Needs: settings, plot, analysis_panel, current_spectrum(), _path, _fmt, _index, _spectra,
    show_error(), statusBar(), _ana_reason, _on_analysis_done-like state update."""

    # ------------------------------------------------------------- actions
    def _create_report_actions(self) -> None:
        sp = QStyle.StandardPixmap
        icon = self.style().standardIcon
        self.act_print = QAction(icon(sp.SP_FileDialogDetailedView), "", self)
        self.act_print.setShortcut(QKeySequence.Print)
        self.act_print.triggered.connect(lambda: self.print_report())
        self.act_print_preview = QAction(icon(sp.SP_FileDialogContentsView), "", self)
        self.act_print_preview.triggered.connect(lambda: self.print_preview())
        self.act_export_pdf = QAction(icon(sp.SP_DialogSaveButton), "", self)
        self.act_export_pdf.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.act_export_pdf.triggered.connect(lambda: self.export_report_pdf())
        self.act_batch_reports = QAction(self)
        self.act_batch_reports.triggered.connect(lambda: self.open_report_batch())
        self._report_batch_dialogs: list = []

    def report_actions(self) -> list:
        return [self.act_print, self.act_print_preview, self.act_export_pdf, self.act_batch_reports]

    def _retranslate_report_actions(self) -> None:
        for act, text, icon_text, tip in (
                (self.act_print, "act_print", "tb_print", "tip_print"),
                (self.act_print_preview, "act_print_preview", None, "tip_print_preview"),
                (self.act_export_pdf, "act_export_pdf", None, "tip_export_pdf"),
                (self.act_batch_reports, "act_batch_reports", None, "tip_batch_reports")):
            act.setText(tr(text))
            if icon_text:
                act.setIconText(tr(icon_text))
            act.setToolTip(tr(tip))
            act.setStatusTip(tr(tip))

    def _update_report_actions(self) -> None:
        has = self.current_spectrum() is not None
        for a in (self.act_print, self.act_print_preview, self.act_export_pdf):
            a.setEnabled(has)

    # ---------------------------------------------------------- overridable
    def ask_yes_no(self, text: str) -> bool:
        """Yes/No question (tests replace this)."""
        return QMessageBox.question(self, tr("err_title"), text,
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes

    def ask_report_options(self, mode: str) -> Optional[rp.ReportOptions]:
        """Show the Report Options dialog; None when cancelled (tests replace this)."""
        from .report_dialogs import ReportOptionsDialog
        dlg = ReportOptionsDialog(self.settings, mode, parent=self)
        return dlg.options() if dlg.exec() == QDialog.Accepted else None

    # ------------------------------------------------------------ helpers
    def report_data(self) -> Optional[rp.ReportData]:
        spec = self.current_spectrum()
        if spec is None:
            return None
        panel = self.analysis_panel
        data = rp.ReportData(
            spectrum=spec, path=self._path, fmt_name=self._fmt.name if self._fmt else "",
            peaks=list(panel.peaks), matches=list(panel.matches),
            analysed=bool(getattr(panel, "analysed", False) or panel.peaks or panel.matches),
            identified=panel.identified, plot=PlotRenderer.from_plot(self.plot),
            index=self._index, count=len(self._spectra))
        self._report_context(data, spec)
        return data

    def _report_context(self, data: rp.ReportData, spec) -> None:
        """Library, detector, geometry, concentrations and workflow statuses of the analysis session
        of the displayed spectrum, as stored (nothing is recalculated)."""
        panel = self.analysis_panel
        if data.analysed and data.identified:
            data.library = getattr(panel, "results_application", None)
        ctl = getattr(self, "session_ctl", None)
        s = ctl.session_for(spec) if ctl is not None else None
        if s is None:
            return
        from dataclasses import asdict
        data.has_session = True
        data.library = (s.processing_settings or {}).get("identification_library") or data.library
        data.detector = s.detector
        data.geometry = s.geometry
        data.mass_basis = (s.sample or {}).get("mass_basis")
        data.concentration = ctl.concentrations()
        try:
            data.statuses = [asdict(st) for st in ctl.statuses()]
        except Exception:                  # the report is never blocked by the workflow panel
            data.statuses = []

    def ensure_analysis_for_report(self, opts: rp.ReportOptions) -> None:
        """Peaks / nuclides wanted but not analysed: offer to run the analysis (never blocks)."""
        panel = self.analysis_panel
        if not opts.wants_analysis() or getattr(panel, "analysed", False) or panel.peaks or panel.matches:
            return
        if self._ana_reason is not None or self.current_spectrum() is None:
            return
        if not self.ask_yes_no(tr("rep_ask_analyse")):
            return
        spec = self.current_spectrum()
        QApplication.setOverrideCursor(Qt.BusyCursor)
        try:
            self._ana_application = panel.application()
            peaks, matches, identified = rp.analyse_spectrum(spec, application=self._ana_application)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            panel.show_message(tr("ana_failed", msg=f"{type(exc).__name__}: {exc}"))
            return
        QApplication.restoreOverrideCursor()
        self._ana_token += 1                       # a running background analysis is now stale
        self._on_analysis_done(self._ana_token, peaks, matches, identified)

    def _prepare_report(self, mode: str, opts: Optional[rp.ReportOptions]):
        if self.current_spectrum() is None:
            self.show_info(tr("ana_no_spectrum"))
            return None
        if opts is None:
            opts = self.ask_report_options(mode)
            if opts is None:
                return None
        self.ensure_analysis_for_report(opts)
        return opts, self.report_data()

    def _new_printer(self, opts: rp.ReportOptions):
        from PySide6.QtPrintSupport import QPrinter
        printer = QPrinter(QPrinter.HighResolution)
        printer.setDocName(self._path.name if self._path else "SpectraMaster")
        printer.setCreator("SpectraMaster")
        rp.configure_printer(printer, opts)
        return printer

    # ------------------------------------------------------------ commands
    def print_report(self, opts: Optional[rp.ReportOptions] = None) -> int:
        prep = self._prepare_report("print", opts)
        if prep is None:
            return 0
        opts, data = prep
        from PySide6.QtPrintSupport import QPrintDialog
        printer = self._new_printer(opts)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() != QDialog.Accepted:
            return 0
        try:
            n = rp.Report(data, opts).render(printer)
        except Exception as exc:
            self.show_error(tr("rep_err_pdf", path=printer.printerName(), msg=str(exc)))
            return 0
        self.statusBar().showMessage(tr("rep_status_printed", n=n), 10000)
        return n

    def print_preview(self, opts: Optional[rp.ReportOptions] = None, exec_dialog: bool = True):
        prep = self._prepare_report("preview", opts)
        if prep is None:
            return None
        opts, data = prep
        from PySide6.QtPrintSupport import QPrintPreviewDialog
        printer = self._new_printer(opts)
        dlg = QPrintPreviewDialog(printer, self)
        dlg.setWindowTitle(tr("act_print_preview").replace("&", "").rstrip("."))
        dlg.resize(980, 860)
        dlg.paintRequested.connect(lambda pr: rp.Report(data, opts).render(pr))
        if exec_dialog:
            dlg.exec()
        return dlg

    def export_report_pdf(self, path: Optional[str] = None,
                          opts: Optional[rp.ReportOptions] = None) -> Optional[Path]:
        prep = self._prepare_report("pdf", opts)
        if prep is None:
            return None
        opts, data = prep
        if path is None:
            base = (self._path.stem if self._path else "spectrum") + "_report.pdf"
            path, _ = QFileDialog.getSaveFileName(self, tr("rep_fd_pdf_title"),
                                                  str(Path(self.settings.folder("report")) / base), tr("fd_pdf"))
            if not path:
                return None
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
        out = Path(path)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            n = rp.export_pdf(out, data, opts, title=self._path.name if self._path else "")
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self.show_error(tr("rep_err_pdf", path=str(out), msg=f"{type(exc).__name__}: {exc}"))
            return None
        QApplication.restoreOverrideCursor()
        self.settings.set_folder("report", out)
        self.statusBar().showMessage(tr("rep_status_pdf", path=str(out), n=n), 15000)
        return out

    def open_report_batch(self, files: Sequence[Path] = ()):
        from .report_dialogs import ReportBatchDialog
        if not files and self._path is not None:
            files = [self._path]
        dlg = ReportBatchDialog(self.settings, files, self)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        self._report_batch_dialogs.append(dlg)
        dlg.destroyed.connect(lambda *_: self._report_batch_dialogs.remove(dlg)
                              if dlg in self._report_batch_dialogs else None)
        dlg.show()
        return dlg

"""SpectraMaster main window (DataMaster-style interactive mode)."""
from __future__ import annotations

import io
import math
import os
import re
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtCore import QByteArray, QEvent, QRectF, QSize, Qt, QThread, QTimer
from PySide6.QtGui import (QAction, QActionGroup, QColor, QDoubleValidator, QFont, QIcon,
                           QKeySequence, QPainter, QPalette, QPen, QPixmap)
from PySide6.QtWidgets import (QApplication, QComboBox, QDockWidget, QFileDialog, QFrame, QLabel,
                               QLineEdit, QMainWindow, QMenu, QMessageBox, QScrollArea, QSplashScreen,
                               QSplitter,
                               QStyle, QStyleFactory, QToolBar, QToolButton, QVBoxLayout, QWidget)

from .. import __version__
from ..convert import calibration_note, content_note, nonfinite_channels, output_name, read_spectra, write_spectrum
from ..formats import get_format, load_all, readable_formats, writable_formats
from ..formats.base import FormatSpec
from ..model import Spectrum
from . import analysis_panel as ana
from . import i18n
from .analysis_panel import AnalysisPanel, export_results, peak_info_text
from .dialogs import AboutDialog, BatchDialog, FormatDialog, expand_spectrum_paths
from .i18n import tr
from .icon import app_icon
from .info_panel import InfoPanel
from .number_text import decimal_text
from .plot import Highlight, OverviewStrip, SpectrumPlot, Y_LINEAR, Y_LOG, Y_MODES, Y_SQRT
from .roi_panel import RoiPanel, export_rois_csv
from .settings import AUTO, Settings
from .worker import AnalysisWorker, quit_on
from .report_actions import ReportActionsMixin

UI_FONT_FAMILIES = ["Segoe UI", "Tahoma", "Arial"]

# Go-to window widths: (kind, n)
GOTO_WIDTHS = [("fwhm", 3), ("fwhm", 5), ("fwhm", 10), ("kev", 5), ("kev", 10), ("kev", 25),
               ("kev", 50), ("kev", 100)]
GOTO_DEFAULT_WIDTH = 1


class MainWindow(ReportActionsMixin, QMainWindow):
    def __init__(self, settings: Optional[Settings] = None, parent=None):
        super().__init__(parent)
        load_all()
        self.settings = settings or Settings()
        self._spectra: list[Spectrum] = []
        self._index = 0
        self._fmt: Optional[FormatSpec] = None
        self._path: Optional[Path] = None
        self._batch_dialogs: list[BatchDialog] = []
        self._ana_thread: Optional[QThread] = None
        self._ana_worker: Optional[AnalysisWorker] = None
        self._ana_token = 0
        self._ana_reason: Optional[str] = None
        self._ana_silent = False
        self._roi_count = 0

        self.setWindowIcon(app_icon())
        self.setAcceptDrops(True)
        self.resize(1180, 760)
        self.setDockNestingEnabled(True)

        # ---- central area: plot (+ overview strip) | info panel
        self.plot = SpectrumPlot()
        self.plot.filesDropped.connect(self.handle_dropped)
        self.plot.hovered.connect(self._on_hover)
        self.plot.peakIndexed.connect(self._on_peak_indexed)
        self.plot.historyChanged.connect(self._update_history_actions)
        self.plot.viewChanged.connect(self._update_history_actions)
        self.plot.contextRequested.connect(self._plot_context_menu)
        self.plot.roisChanged.connect(self._on_rois_changed)
        self.plot.overlaysChanged.connect(self._rebuild_overlay_menu)
        self.overview = OverviewStrip(self.plot)
        self.info = InfoPanel()
        self.info.spectrumIndexChanged.connect(self.show_index)
        scroll = QScrollArea()
        scroll.setWidget(self.info)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumWidth(300)
        self.info_scroll = scroll
        self.splitter = QSplitter(Qt.Horizontal)
        plot_frame = QFrame()
        plot_frame.setObjectName("plotFrame")
        plot_frame.setLayoutDirection(Qt.LeftToRight)
        pl = QVBoxLayout(plot_frame)
        pl.setContentsMargins(4, 4, 4, 2)
        pl.setSpacing(0)
        pl.addWidget(self.plot, 1)
        pl.addWidget(self.overview)
        self.splitter.addWidget(plot_frame)
        self.splitter.addWidget(scroll)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setCollapsible(0, False)
        self.splitter.setSizes([840, 340])
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(8, 6, 8, 4)
        cl.addWidget(self.splitter)
        self.setCentralWidget(container)

        # ---- docks
        self.roi_panel = RoiPanel(self.plot)
        self.roi_panel.exportRequested.connect(lambda: self.export_rois())
        self.roi_dock = QDockWidget()
        self.roi_dock.setObjectName("roiDock")
        self.roi_dock.setWidget(self.roi_panel)
        self.analysis_panel = AnalysisPanel(settings=self.settings)
        self.analysis_panel.peakActivated.connect(self.zoom_to_peak)
        self.analysis_panel.nuclideSelected.connect(self._on_nuclide_selected)
        self.analysis_panel.exportRequested.connect(lambda: self.export_analysis())
        self.analysis_dock = QDockWidget()
        self.analysis_dock.setObjectName("analysisDock")
        self.analysis_dock.setWidget(self.analysis_panel)
        for d in (self.analysis_dock, self.roi_dock):
            d.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
            self.addDockWidget(Qt.BottomDockWidgetArea, d)
        self.tabifyDockWidget(self.analysis_dock, self.roi_dock)
        self.analysis_dock.hide()
        self.roi_dock.hide()

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_nav_toolbar()
        self._create_statusbar()
        from .aptec_view_ui import install_view_menu    # View menu in Aptec's order (needs the tool bars)
        install_view_menu(self)
        from .aptec_edit_ui import install_edit_display_menus    # Edit and Display menus (Aptec)
        install_edit_display_menus(self)

        # ---- restore view preferences
        mode = str(self.settings.get("view/y_mode", "") or "")
        if mode not in Y_MODES:
            mode = Y_LOG if self.settings.get_bool("view/log_y", False) else Y_LINEAR
        self.set_y_mode(mode)
        self.act_auto_y.setChecked(self.settings.get_bool("view/auto_y", True))
        self.act_energy.setChecked(self.settings.get_bool("view/energy_axis", True))
        self.act_labels.setChecked(self.settings.get_bool("view/peak_labels", True))
        self.act_overview.setChecked(self.settings.get_bool("view/overview", True))
        self.act_overlay_norm.setChecked(self.settings.get_bool("view/overlay_norm", False))
        self.act_auto_analyze.setChecked(self.settings.get_bool("analysis/auto", False))
        self.act_splash.setChecked(self.settings.get_bool("ui/show_splash", True))
        try:
            w = int(self.settings.get("view/goto_width", GOTO_DEFAULT_WIDTH))
        except (TypeError, ValueError):
            w = GOTO_DEFAULT_WIDTH
        self.goto_width.setCurrentIndex(w if 0 <= w < len(GOTO_WIDTHS) else GOTO_DEFAULT_WIDTH)
        self._default_state = (self.saveState(), self.splitter.saveState())    # View > Default Position
        self._restore_geometry()
        if hasattr(self, "roi_paint_bar"):                   # restoreState may show it: only while painting
            self.roi_paint_bar.setVisible(self.plot.paint is not None)
        self.apply_language(self.settings.language, save=False)
        self.refresh_analysis_available()
        self._update_actions()

    # ================================================================ building
    def _std_icon(self, sp) -> QIcon:
        return self.style().standardIcon(sp)

    def _create_actions(self) -> None:
        sp = QStyle.StandardPixmap
        self.act_open = QAction(self._std_icon(sp.SP_DialogOpenButton), "", self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self.open_spectrum)
        self.act_multi = QAction(self._std_icon(sp.SP_FileDialogDetailedView), "", self)
        self.act_multi.setShortcut(QKeySequence("Ctrl+M"))
        self.act_multi.triggered.connect(self.open_multiple)
        self.act_open_as = QAction(self._std_icon(sp.SP_FileDialogInfoView), "", self)
        self.act_open_as.setShortcut(QKeySequence("Ctrl+I"))
        self.act_open_as.triggered.connect(self.choose_input_format)
        self.act_save = QAction(self._std_icon(sp.SP_DialogSaveButton), "", self)
        self.act_save.setShortcuts([QKeySequence.SaveAs, QKeySequence.Save])
        self.act_save.triggered.connect(self.save_as)
        self.act_folder = QAction(self._std_icon(sp.SP_DirOpenIcon), "", self)
        self.act_folder.setShortcut(QKeySequence("Ctrl+D"))
        self.act_folder.triggered.connect(self.convert_folder)
        self.act_exit = QAction(self)
        self.act_exit.setShortcut(QKeySequence("Alt+F4"))
        self.act_exit.triggered.connect(self.close)
        self.act_about = QAction(self._std_icon(sp.SP_MessageBoxInformation), "", self)
        self.act_about.triggered.connect(self.show_about)
        self.act_shortcuts = QAction(self)
        self.act_shortcuts.triggered.connect(self.show_shortcuts)
        self.act_integration = QAction(self)
        self.act_integration.triggered.connect(self.show_integration)
        self.act_splash = QAction(self, checkable=True)
        self.act_splash.toggled.connect(lambda on: self.settings.set("ui/show_splash", on))
        self.act_log = QAction(self)
        self.act_log.setCheckable(True)
        self.act_log.setShortcut(QKeySequence("Ctrl+L"))
        self.act_log.toggled.connect(self._toggle_log)
        self.act_energy = QAction(self)
        self.act_energy.setCheckable(True)
        self.act_energy.setShortcut(QKeySequence("Ctrl+E"))
        self.act_energy.toggled.connect(self._toggle_energy)
        self.act_reset = QAction(self._std_icon(sp.SP_BrowserReload), "", self)
        self.act_reset.setShortcut(QKeySequence("Ctrl+0"))
        self.act_reset.triggered.connect(self.plot.reset_view)
        # navigation
        self.act_back = QAction(self._std_icon(sp.SP_ArrowBack), "", self)
        self.act_back.setShortcuts([QKeySequence(Qt.Key_Backspace), QKeySequence("Alt+Left")])
        self.act_back.triggered.connect(self.plot.back)
        self.act_forward = QAction(self._std_icon(sp.SP_ArrowForward), "", self)
        self.act_forward.setShortcuts([QKeySequence("Alt+Right"), QKeySequence("Shift+Backspace")])
        self.act_forward.triggered.connect(self.plot.forward)
        self.act_open_preview = QAction(self, checkable=True)
        self.act_open_preview.setChecked(self.settings.get_bool("ui/open_dialog_preview", False))
        self.act_open_preview.toggled.connect(lambda on: self.settings.set("ui/open_dialog_preview", bool(on)))
        self.act_auto_y = QAction(self, checkable=True)
        self.act_auto_y.setShortcut(QKeySequence("Ctrl+Shift+Y"))
        self.act_auto_y.toggled.connect(self._toggle_auto_y)
        self.y_group = QActionGroup(self)
        self.act_y: dict[str, QAction] = {}
        for mode in Y_MODES:
            a = QAction(self, checkable=True)
            a.triggered.connect(lambda _=False, m=mode: self.set_y_mode(m))
            self.y_group.addAction(a)
            self.act_y[mode] = a
        self.act_overview = QAction(self, checkable=True)
        self.act_overview.toggled.connect(self._toggle_overview)
        self.act_labels = QAction(self, checkable=True)
        self.act_labels.setShortcut(QKeySequence("Ctrl+Shift+L"))
        self.act_labels.toggled.connect(self._toggle_labels)
        self.act_goto = QAction(self)
        self.act_goto.setShortcut(QKeySequence("Ctrl+G"))
        self.act_goto.triggered.connect(self._focus_goto)
        self.act_export_img = QAction(self._std_icon(sp.SP_DialogSaveButton), "", self)
        self.act_export_img.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.act_export_img.triggered.connect(lambda: self.export_plot_image())
        self.act_copy_img = QAction(self)
        self.act_copy_img.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.act_copy_img.triggered.connect(self.copy_plot)
        self.act_clear_rois = QAction(self)
        self.act_clear_rois.triggered.connect(self.plot.clear_rois)
        # overlays
        self.act_overlay_add = QAction(self._std_icon(sp.SP_FileDialogNewFolder), "", self)
        self.act_overlay_add.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.act_overlay_add.triggered.connect(lambda: self.add_overlay_file())
        self.act_overlay_clear = QAction(self)
        self.act_overlay_clear.triggered.connect(self.plot.clear_overlays)
        self.act_overlay_norm = QAction(self, checkable=True)
        self.act_overlay_norm.toggled.connect(self._toggle_overlay_norm)
        # analysis
        self.act_analyze = QAction(self._std_icon(sp.SP_FileDialogContentsView), "", self)
        self.act_analyze.setShortcut(QKeySequence("F5"))
        self.act_analyze.triggered.connect(lambda: self.run_analysis())
        self.act_auto_analyze = QAction(self, checkable=True)
        self.act_auto_analyze.toggled.connect(lambda on: self.settings.set("analysis/auto", on))
        self.lang_group = QActionGroup(self)
        self.lang_actions: dict[str, QAction] = {}
        for code, name in i18n.LANGUAGES.items():
            a = QAction(name, self, checkable=True)
            a.setData(code)
            a.triggered.connect(lambda _=False, c=code: self.apply_language(c))
            self.lang_group.addAction(a)
            self.lang_actions[code] = a
        self._create_report_actions()

    def _create_menus(self) -> None:
        mb = self.menuBar()
        self.menu_file = mb.addMenu("")
        self.menu_open = self.menu_file.addMenu("")
        self.menu_open.addAction(self.act_open)
        self.menu_open.addAction(self.act_multi)
        self.menu_file.addAction(self.act_open_as)
        self.menu_file.addAction(self.act_save)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.act_folder)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.act_export_img)
        self.menu_file.addAction(self.act_copy_img)
        self.menu_file.addSeparator()
        for a in self.report_actions():
            self.menu_file.addAction(a)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.act_exit)
        self.menu_view = mb.addMenu("")
        self.menu_view.addAction(self.act_back)
        self.menu_view.addAction(self.act_forward)
        self.menu_view.addAction(self.act_reset)
        self.menu_view.addAction(self.act_goto)
        self.menu_view.addSeparator()
        self.menu_yscale = self.menu_view.addMenu("")
        for a in self.act_y.values():
            self.menu_yscale.addAction(a)
        self.menu_view.addAction(self.act_log)
        self.menu_view.addAction(self.act_auto_y)
        self.menu_view.addAction(self.act_open_preview)
        self.menu_view.addAction(self.act_energy)
        self.menu_view.addSeparator()
        self.menu_view.addAction(self.act_overview)
        self.menu_view.addAction(self.act_labels)
        self.menu_overlays = self.menu_view.addMenu("")
        self.menu_view.addSeparator()
        self.menu_view.addAction(self.roi_dock.toggleViewAction())
        self.menu_view.addAction(self.analysis_dock.toggleViewAction())
        self.menu_view.addAction(self.act_clear_rois)
        self.menu_view.addSeparator()
        self.menu_lang = self.menu_view.addMenu("")
        for a in self.lang_actions.values():
            self.menu_lang.addAction(a)
        self.menu_analyze = mb.addMenu("")
        self.menu_analyze.addAction(self.act_analyze)
        self.menu_analyze.addAction(self.act_auto_analyze)
        self.menu_analyze.addSeparator()
        self.menu_analyze.addAction(self.act_labels)
        from .quant_panel import install_quant    # Analyze > Efficiency / Activity (sets self.quant_results)
        install_quant(self)
        from .calibration_dialog import install_calibration_actions    # Analyze > Energy calibration / drift
        install_calibration_actions(self)
        from .fit_inspection import install_session_actions    # Analyze > Fit inspection & manual refit
        install_session_actions(self)
        from .session_io import install_session_io    # File > sessions, report record; workflow dock (A5, F3)
        install_session_io(self)
        from .aptec_calibration_ui import install_setup_menu    # Setup > Quick / Full calibrations (Aptec)
        install_setup_menu(self)
        from .aptec_roi_ui import install_roi_menu    # ROI menu and Paint bar (Aptec)
        install_roi_menu(self)
        from .aptec_analyze_ui import install_analyze_menu    # Analyze > Setup, P, I, B, Q (Aptec)
        install_analyze_menu(self)
        from .aptec_ops_ui import install_ops_menu    # Analyze > Add Constant ... Position (Aptec)
        install_ops_menu(self)
        self.menu_help = mb.addMenu("")
        self.menu_help.addAction(self.act_shortcuts)
        self.menu_help.addAction(self.act_integration)
        self.menu_help.addSeparator()
        self.menu_help.addAction(self.act_splash)
        self.menu_help.addSeparator()
        self.menu_help.addAction(self.act_about)
        from .manual import install_manual_menu    # Help > User Manual (Arabic / English), F1
        install_manual_menu(self)
        from .archive_search import install_archive_search    # File > Archive search...
        install_archive_search(self)
        from .qc_window import install_qc_menu    # Tools > Detector QC...
        install_qc_menu(self)
        from .detector_test_dialog import install_detector_test_menu    # Tools > acceptance, chi-square
        install_detector_test_menu(self)
        self._rebuild_overlay_menu()

    def _create_toolbar(self) -> None:
        tb = QToolBar("main")
        tb.setObjectName("mainToolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tb.addAction(self.act_open)
        tb.addAction(self.act_multi)
        tb.addAction(self.act_folder)
        tb.addAction(self.act_save)
        tb.addSeparator()
        tb.addAction(self.act_open_as)
        tb.addSeparator()
        tb.addAction(self.act_analyze)
        tb.addAction(self.act_overlay_add)
        tb.addAction(self.act_print)
        self.addToolBar(Qt.TopToolBarArea, tb)
        self.toolbar = tb

    def _create_nav_toolbar(self) -> None:
        self.addToolBarBreak(Qt.TopToolBarArea)
        tb = QToolBar("navigation")
        tb.setObjectName("navToolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tb.addAction(self.act_back)
        tb.addAction(self.act_forward)
        tb.addAction(self.act_reset)
        tb.addSeparator()
        self.yscale_combo = QComboBox()
        for mode in Y_MODES:
            self.yscale_combo.addItem("", mode)
        self.yscale_combo.currentIndexChanged.connect(
            lambda i: self.set_y_mode(self.yscale_combo.itemData(i)))
        tb.addWidget(self.yscale_combo)
        tb.addAction(self.act_auto_y)
        tb.addAction(self.act_energy)
        tb.addSeparator()
        self.goto_label = QLabel()
        self.goto_label.setContentsMargins(4, 0, 4, 0)
        tb.addWidget(self.goto_label)
        self.goto_edit = QLineEdit()
        self.goto_edit.setLayoutDirection(Qt.LeftToRight)
        self.goto_edit.setAlignment(Qt.AlignAbsolute | Qt.AlignLeft | Qt.AlignVCenter)
        self.goto_edit.setFixedWidth(96)
        self.goto_edit.setClearButtonEnabled(True)
        v = QDoubleValidator(-1e9, 1e9, 4, self.goto_edit)
        v.setNotation(QDoubleValidator.StandardNotation)
        v.setLocale(self.locale().c())
        self.goto_edit.setValidator(v)
        self.goto_edit.returnPressed.connect(self.goto_from_toolbar)
        tb.addWidget(self.goto_edit)
        self.goto_unit = QComboBox()
        self.goto_unit.addItem("", "kev")
        self.goto_unit.addItem("", "ch")
        tb.addWidget(self.goto_unit)
        self.goto_width = QComboBox()
        for _ in GOTO_WIDTHS:
            self.goto_width.addItem("")
        self.goto_width.currentIndexChanged.connect(lambda i: self.settings.set("view/goto_width", i))
        tb.addWidget(self.goto_width)
        tb.addSeparator()
        tb.addAction(self.act_export_img)
        self.addToolBar(Qt.TopToolBarArea, tb)
        self.nav_toolbar = tb

    def _create_statusbar(self) -> None:
        sb = self.statusBar()
        self.status_hover = QLabel()
        self.status_hover.setMinimumWidth(260)
        self.status_path = QLabel()
        self.status_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.status_fmt = QLabel()
        self.status_input = QLabel()
        sb.addWidget(self.status_path, 1)
        sb.addPermanentWidget(self.status_hover)
        sb.addPermanentWidget(self.status_fmt)
        sb.addPermanentWidget(self.status_input)
        self.status_credit = QLabel()
        self.status_credit.setObjectName("creditLabel")
        sb.addPermanentWidget(self.status_credit)

    # ============================================================== language
    def apply_language(self, lang: str, save: bool = True) -> None:
        lang = i18n.set_language(lang)
        if save:
            self.settings.language = lang
        direction = Qt.RightToLeft if i18n.is_rtl(lang) else Qt.LeftToRight
        app = QApplication.instance()
        if app is not None:
            app.setLayoutDirection(direction)
            from . import qt_ar
            qt_ar.install(lang)          # Qt's own buttons / file dialog / context menus
        self.setLayoutDirection(direction)
        self.plot.setLayoutDirection(Qt.LeftToRight)
        self.overview.setLayoutDirection(Qt.LeftToRight)
        self.lang_actions[lang].setChecked(True)
        self.retranslate()

    def retranslate(self) -> None:
        def setup(act: QAction, text_key: str, icon_text_key: Optional[str] = None,
                  tip_key: Optional[str] = None):
            act.setText(tr(text_key))
            if icon_text_key:
                act.setIconText(tr(icon_text_key))
            if tip_key:
                act.setToolTip(tr(tip_key))
                act.setStatusTip(tr(tip_key))

        setup(self.act_open, "act_open_spectrum", "tb_open", "tip_open")
        setup(self.act_multi, "act_open_multiple", "tb_multiple", "tip_multiple")
        setup(self.act_open_as, "act_open_as", "tb_input_fmt", "tip_input_fmt")
        setup(self.act_save, "act_save_as", "tb_save", "tip_save")
        setup(self.act_folder, "act_convert_folder", "tb_folder", "tip_folder")
        setup(self.act_exit, "act_exit")
        setup(self.act_about, "act_about")
        setup(self.act_shortcuts, "act_shortcuts")
        setup(self.act_integration, "act_integration")
        setup(self.act_splash, "act_splash")
        self.status_credit.setText(tr("credit_status"))
        setup(self.act_log, "act_log_y", "tb_log", "tip_log")
        setup(self.act_energy, "act_energy_axis", "tb_energy", "tip_energy")
        setup(self.act_reset, "act_reset_zoom", "tb_reset", "tip_reset")
        setup(self.act_back, "act_back", "tb_back", "tip_back")
        setup(self.act_forward, "act_forward", "tb_forward", "tip_forward")
        setup(self.act_auto_y, "act_auto_y", "tb_auto_y", "tip_auto_y")
        setup(self.act_open_preview, "act_open_preview", None, "tip_open_preview")
        for mode, key in ((Y_LINEAR, "act_y_linear"), (Y_LOG, "act_y_log"), (Y_SQRT, "act_y_sqrt")):
            setup(self.act_y[mode], key)
        setup(self.act_overview, "act_overview", None, "tip_overview")
        setup(self.act_labels, "act_labels", None, "tip_labels")
        setup(self.act_goto, "act_goto", None, "tip_goto")
        setup(self.act_export_img, "act_export_image", "tb_export_img", "tip_export_img")
        setup(self.act_copy_img, "act_copy_image")
        setup(self.act_clear_rois, "act_clear_rois")
        setup(self.act_overlay_add, "act_overlay_add", "tb_overlay", "tip_overlay")
        setup(self.act_overlay_clear, "act_overlay_clear")
        setup(self.act_overlay_norm, "act_overlay_norm")
        setup(self.act_analyze, "act_analyze", "tb_analyze", "tip_analyze")
        setup(self.act_auto_analyze, "act_auto_analyze")
        self._retranslate_report_actions()
        self.menu_file.setTitle(tr("menu_file"))
        self.menu_open.setTitle(tr("menu_open"))
        self.menu_view.setTitle(tr("menu_view"))
        self.menu_yscale.setTitle(tr("menu_yscale"))
        self.menu_overlays.setTitle(tr("menu_overlays"))
        self.menu_lang.setTitle(tr("menu_language"))
        self.menu_analyze.setTitle(tr("menu_analyze"))
        self.menu_help.setTitle(tr("menu_help"))
        from .archive_search import retranslate_archive_search
        retranslate_archive_search(self)
        from .qc_window import retranslate_qc_menu
        retranslate_qc_menu(self)
        from .detector_test_dialog import retranslate_detector_test_menu
        retranslate_detector_test_menu(self)
        from .manual import retranslate_manual_menu
        retranslate_manual_menu(self)
        from .calibration_dialog import retranslate_calibration_actions
        retranslate_calibration_actions(self)
        from .aptec_calibration_ui import retranslate_setup_menu
        retranslate_setup_menu(self)
        from .aptec_roi_ui import retranslate_roi_menu
        retranslate_roi_menu(self)
        from .aptec_ops_ui import retranslate_ops_menu
        retranslate_ops_menu(self)
        from .aptec_analyze_ui import retranslate_analyze_menu
        retranslate_analyze_menu(self)
        from .aptec_view_ui import retranslate_view_menu
        retranslate_view_menu(self)
        from .aptec_edit_ui import retranslate_edit_display_menus
        retranslate_edit_display_menus(self)
        from .fit_inspection import retranslate_session_actions
        retranslate_session_actions(self)
        from .session_io import retranslate_session_io
        retranslate_session_io(self)
        for i, mode in enumerate(Y_MODES):
            self.yscale_combo.setItemText(i, tr(f"y_{mode}"))
        self.yscale_combo.setToolTip(tr("tip_yscale"))
        self.goto_label.setText(tr("goto_label"))
        self.goto_edit.setPlaceholderText(tr("goto_placeholder"))
        self.goto_edit.setToolTip(tr("tip_goto"))
        self.goto_unit.setItemText(0, tr("goto_unit_kev"))
        self.goto_unit.setItemText(1, tr("goto_unit_ch"))
        self.goto_unit.setToolTip(tr("tip_goto"))
        for i, (kind, n) in enumerate(GOTO_WIDTHS):
            self.goto_width.setItemText(i, "\u2066" + tr("goto_w_fwhm" if kind == "fwhm" else "goto_w_kev", n=n) + "\u2069")
        self.goto_width.setToolTip(tr("tip_goto_width"))
        self.roi_dock.setWindowTitle(tr("dock_rois"))
        self.analysis_dock.setWindowTitle(tr("dock_analysis"))
        self.roi_panel.retranslate()
        self.analysis_panel.retranslate()
        self.overview.setToolTip(tr("tip_overview"))
        self._rebuild_overlay_menu()
        self.refresh_analysis_available()
        self.info.retranslate()
        self.info.set_spectrum(self.current_spectrum(), self._fmt_display(), keep_combo=True)
        self._update_title()
        self._update_status()
        self.plot.update()

    # ================================================================== state
    def current_spectrum(self) -> Optional[Spectrum]:
        if 0 <= self._index < len(self._spectra):
            return self._spectra[self._index]
        return None

    def _fmt_display(self) -> str:
        return f"{self._fmt.name}  [{self._fmt.code}]" if self._fmt else ""

    def _update_title(self) -> None:
        name = tr("app_name")
        if self._path is not None:
            self.setWindowTitle(f"{self._path.name} — {name}")
        else:
            self.setWindowTitle(name)

    def _update_status(self) -> None:
        self.status_path.setText(i18n.bidi_path(self._path) if self._path else tr("status_ready"))
        self.status_path.setToolTip(str(self._path) if self._path else "")
        self.status_fmt.setText(tr("status_format", name=self._fmt.name) if self._fmt else "")
        self.status_fmt.setVisible(self._fmt is not None)
        in_fmt = self.settings.input_format()
        self.status_input.setText(tr("status_input_mode", name=in_fmt.name if in_fmt else tr("auto_detect")))

    def _update_actions(self) -> None:
        has = self.current_spectrum() is not None
        for a in (self.act_reset, self.act_export_img, self.act_copy_img, self.act_goto,
                  self.act_overlay_add):
            a.setEnabled(has)
        self.goto_edit.setEnabled(has)
        self.act_energy.setEnabled(self.plot.has_energy())
        self.act_analyze.setEnabled(has and self._ana_reason is None and self._ana_thread is None)
        self._update_report_actions()
        self._update_history_actions()
        from .aptec_ops_ui import sync_actions
        sync_actions(self)
        from .aptec_analyze_ui import sync_enabled
        sync_enabled(self)

    def _update_history_actions(self) -> None:
        self.act_back.setEnabled(self.plot.can_go_back())
        self.act_forward.setEnabled(self.plot.can_go_forward())

    def _on_hover(self, text: str) -> None:
        self.status_hover.setText(text)

    def _on_peak_indexed(self, pk) -> None:
        """Ctrl+Left / Right, Space / Tab without ROIs, double-click: the peak's information."""
        self.statusBar().showMessage(peak_info_text(pk))
        if hasattr(self, "analysis_panel"):
            self.analysis_panel.select_peak(pk)

    def set_y_mode(self, mode: str) -> None:
        if mode not in Y_MODES:
            mode = Y_LINEAR
        self.plot.set_y_mode(mode)
        self.act_y[mode].setChecked(True)
        for w, value in ((self.act_log, mode == Y_LOG),):
            w.blockSignals(True)
            w.setChecked(value)
            w.blockSignals(False)
        i = self.yscale_combo.findData(mode)
        if i != self.yscale_combo.currentIndex():
            self.yscale_combo.blockSignals(True)
            self.yscale_combo.setCurrentIndex(i)
            self.yscale_combo.blockSignals(False)
        self.settings.set("view/y_mode", mode)
        self.settings.set("view/log_y", mode == Y_LOG)

    def _toggle_log(self, on: bool) -> None:
        self.set_y_mode(Y_LOG if on else Y_LINEAR)

    def _toggle_auto_y(self, on: bool) -> None:
        self.plot.set_auto_y(on)
        self.settings.set("view/auto_y", on)

    def _toggle_energy(self, on: bool) -> None:
        self.plot.set_energy_axis(on and self.plot.has_energy())
        self.settings.set("view/energy_axis", on)

    def _toggle_overview(self, on: bool) -> None:
        self.overview.setVisible(on)
        self.settings.set("view/overview", on)

    def _toggle_labels(self, on: bool) -> None:
        self.plot.set_show_labels(on)
        self.settings.set("view/peak_labels", on)

    def _toggle_overlay_norm(self, on: bool) -> None:
        self.plot.set_normalize_overlays(on)
        self.settings.set("view/overlay_norm", on)

    # =============================================================== loading
    def show_error(self, text: str) -> None:
        """Modal warning. Tests replace this to avoid blocking."""
        QMessageBox.warning(self, tr("err_title"), text)

    def show_info(self, text: str) -> None:
        QMessageBox.information(self, tr("err_title"), text)

    def load_file(self, path, fmt: Optional[FormatSpec] | str = "settings") -> bool:
        """Read and display a file. On failure the previous spectrum stays on screen."""
        path = Path(path)
        in_fmt = self.settings.input_format() if fmt == "settings" else fmt
        if not path.is_file():
            self.show_error(tr("err_not_found", path=str(path)))
            return False
        ctl = getattr(self, "session_ctl", None)
        if ctl is not None and not ctl.confirm_discard():    # unsaved analysis session
            return False
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            spectra, used = read_spectra(path, in_fmt)
        except Exception as exc:  # any reader failure -> friendly message
            QApplication.restoreOverrideCursor()
            msg = str(exc) or type(exc).__name__
            fmt_name = in_fmt.name if in_fmt else tr("auto_detect")
            text = tr("err_read", path=str(path), fmt=fmt_name, msg=msg)
            if in_fmt is not None:
                text += "\n\n" + tr("err_read_hint_auto")
            self.show_error(text)
            return False
        QApplication.restoreOverrideCursor()
        self.settings.set_folder("open", path)
        self.display(spectra, used, path)
        n_bad = nonfinite_channels(spectra)
        if n_bad:
            self.statusBar().showMessage(tr("counts_nonfinite", n=n_bad), 20000)
        elif content_note(spectra, used):
            self.statusBar().showMessage(tr("fmt_by_content", name=used.name), 15000)
        elif calibration_note(spectra):
            self.statusBar().showMessage(tr("cal_placeholder"), 15000)
        return True

    def display(self, spectra: Sequence[Spectrum], fmt: Optional[FormatSpec], path: Optional[Path]) -> None:
        if getattr(self, "spectrum_ops", None) is not None:
            self.spectrum_ops.reset()                  # another file: no spectrum operation to undo
        self._spectra = list(spectra)
        self._fmt = fmt
        self._path = Path(path) if path else None
        for s in self._spectra:
            if self._path is not None and not s.source_path:
                s.source_path = str(self._path)
        self.info.set_spectra_count(len(self._spectra), 0)
        self._index = -1
        self.show_index(0)
        self._update_title()
        self._update_status()

    def show_index(self, i: int) -> None:
        if not (0 <= i < len(self._spectra)) or i == self._index:
            return
        ctl = getattr(self, "session_ctl", None)
        if self._index >= 0 and ctl is not None and not ctl.can_switch():    # unsaved analysis session
            self.info.spectrum_combo.blockSignals(True)
            self.info.spectrum_combo.setCurrentIndex(self._index)
            self.info.spectrum_combo.blockSignals(False)
            return
        self._index = i
        spec = self._spectra[i]
        self._ana_token += 1               # results of a running analysis are now stale
        self.analysis_panel.clear()
        self.plot.set_spectrum(spec)
        self.plot.set_energy_axis(self.act_energy.isChecked() and self.plot.has_energy())
        self.info.set_spectrum(spec, self._fmt_display(), keep_combo=True)
        if self.info.spectrum_combo.currentIndex() != i:
            self.info.spectrum_combo.blockSignals(True)
            self.info.spectrum_combo.setCurrentIndex(i)
            self.info.spectrum_combo.blockSignals(False)
        self.goto_unit.setCurrentIndex(0 if self.plot.has_energy() else 1)
        self._update_actions()
        if ctl is not None:
            ctl.spectrum_shown(spec)
        # an opened session shows its stored results: never recalculated automatically
        if self.act_auto_analyze.isChecked() and self._ana_reason is None and not (ctl is not None and ctl.restoring):
            self.run_analysis(silent=True)

    # =============================================================== actions
    def _open_filter(self) -> tuple[str, str]:
        fmts = readable_formats()
        exts = sorted({e for f in fmts for e in f.extensions})
        filters = []
        if exts:
            filters.append(f"{tr('fd_all_spectra')} ({' '.join('*' + e for e in exts)})")
        selected = filters[0] if filters else ""
        in_fmt = self.settings.input_format()
        for f in fmts:
            flt = f"{f.name} ({' '.join('*' + e for e in f.extensions) or '*'})"
            filters.append(flt)
            if in_fmt is not None and f.key == in_fmt.key:
                selected = flt
        filters.append(tr("fd_all_files"))
        return ";;".join(filters), selected

    def _ask_open_file(self, title: str, folder_key: str) -> Optional[str]:
        flt, sel = self._open_filter()
        from .preview import get_open_file_name
        path = get_open_file_name(self, title, self.settings.folder(folder_key), flt, sel, self.settings)
        return path or None

    def open_spectrum(self) -> None:
        path = self._ask_open_file(tr("fd_open_title"), "open")
        if path:
            self.load_file(path)

    def open_multiple(self) -> None:
        flt, sel = self._open_filter()
        paths, _ = QFileDialog.getOpenFileNames(self, tr("fd_multi_title"), self.settings.folder("multi"),
                                                flt, sel)
        if paths:
            self.settings.set_folder("multi", paths[0])
            self.open_batch([Path(p) for p in paths])

    def open_batch(self, files: Sequence[Path]) -> BatchDialog:
        dlg = BatchDialog(files, self.settings, self)
        self._show_batch(dlg)
        return dlg

    def convert_folder(self, folder: Optional[Path] = None) -> BatchDialog:
        start = folder
        if start is None:
            remembered = self.settings.get("folders/folder_in", "")
            start = Path(remembered) if remembered and Path(remembered).is_dir() else None
        dlg = BatchDialog([], self.settings, self, folder_mode=True, folder=start)
        self._show_batch(dlg)
        return dlg

    def _show_batch(self, dlg: BatchDialog) -> None:
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        dlg.setWindowModality(Qt.WindowModal)
        self._batch_dialogs.append(dlg)
        dlg.destroyed.connect(lambda *_: self._batch_dialogs.remove(dlg) if dlg in self._batch_dialogs else None)
        dlg.conversionFinished.connect(lambda *_: self._update_status())
        dlg.show()

    def choose_input_format(self) -> None:
        cur = self.settings.input_format()
        dlg = FormatDialog(tr("dlg_input_title"), tr("dlg_input_prompt"), readable_formats(),
                           cur.key if cur else AUTO, allow_auto=True, parent=self)
        if dlg.exec() == FormatDialog.Accepted:
            key = dlg.selected_key()
            self.settings.set_input_format(None if key in (None, AUTO) else get_format(key))
            self._update_status()

    def save_as(self) -> None:
        fmts = writable_formats()
        if not fmts:
            self.show_error(tr("err_no_writable"))
            return
        cur = self.settings.output_format()
        dlg = FormatDialog(tr("dlg_output_title"), tr("dlg_output_prompt"), fmts,
                           cur.key if cur else fmts[0].key, allow_auto=False, parent=self)
        if dlg.exec() != FormatDialog.Accepted or not dlg.selected_key():
            return
        out_fmt = get_format(dlg.selected_key())
        self.settings.set_output_format(out_fmt)
        self.statusBar().showMessage(tr("status_out_fmt", name=out_fmt.name), 4000)
        if self.current_spectrum() is None:
            self.show_info(tr("err_no_spectrum", fmt=out_fmt.name))
            return
        default = self.default_save_path(out_fmt)
        exts = " ".join("*" + e for e in out_fmt.extensions)
        flt = f"{out_fmt.name} ({exts});;{tr('fd_all_files')}"
        path, _ = QFileDialog.getSaveFileName(self, tr("fd_save_title"), str(default), flt)
        if path:
            self.save_current_as(out_fmt, Path(path))

    def default_save_path(self, out_fmt: FormatSpec) -> Path:
        src = self._path or Path("spectrum")
        index = self._index + 1 if len(self._spectra) > 1 else None
        name = output_name(src, out_fmt, index)
        remembered = self.settings.get("folders/save", "")
        folder = Path(remembered) if remembered and Path(remembered).is_dir() else (
            src.parent if self._path else Path(self.settings.folder("save")))
        return folder / name

    def save_current_as(self, out_fmt: FormatSpec, path: Path) -> bool:
        spec = self.current_spectrum()
        if spec is None:
            return False
        path = Path(path)
        if not path.suffix:
            path = path.with_suffix(out_fmt.default_ext)
        try:
            warnings = write_spectrum(spec, path, out_fmt)
        except Exception as exc:
            self.show_error(tr("err_write", path=str(path), fmt=out_fmt.name, msg=str(exc) or type(exc).__name__))
            return False
        self.settings.set_folder("save", path)
        msg = tr("status_saved", path=str(path))
        if warnings:
            msg += "  ⚠ " + "; ".join(warnings)
        self.statusBar().showMessage(msg, 15000)
        return True

    def show_about(self) -> None:
        AboutDialog(self).exec()

    def show_integration(self) -> None:
        from .dialogs import IntegrationDialog
        IntegrationDialog(self).exec()

    def show_shortcuts(self) -> None:
        from .dialogs import ShortcutsDialog
        ShortcutsDialog(self).exec()

    # ============================================================ navigation
    def _focus_goto(self) -> None:
        self.goto_edit.setFocus(Qt.ShortcutFocusReason)
        self.goto_edit.selectAll()

    def goto_from_toolbar(self) -> bool:
        try:
            value = float(decimal_text(self.goto_edit.text()))     # round-8 review, Codex M1
        except ValueError:
            self.statusBar().showMessage(tr("goto_bad"), 5000)
            return False
        ok = self.goto(value, self.goto_unit.currentData(), self.goto_width.currentIndex())
        if ok:
            self.plot.setFocus()
        return ok

    def goto(self, value: float, unit: str = "kev", width_index: int = GOTO_DEFAULT_WIDTH) -> bool:
        """Zoom to an energy (keV) or channel with one of the GOTO_WIDTHS windows."""
        spec = self.current_spectrum()
        if spec is None:
            return False
        kind, n = GOTO_WIDTHS[width_index if 0 <= width_index < len(GOTO_WIDTHS) else GOTO_DEFAULT_WIDTH]
        plot = self.plot
        if unit == "kev":
            pos = plot.pos_of_energy(value)
            if pos is None:
                self.statusBar().showMessage(tr("goto_uncal"), 8000)
                return False
        else:
            pos = plot.pos_of_channel(value)
        if not (0 <= pos <= plot.num_channels()):
            self.statusBar().showMessage(tr("goto_out", v=f"{value:g}"), 6000)
            return False
        if kind == "fwhm":
            plot.zoom_to_pos(pos, n * plot.default_fwhm_channels(pos))
        elif plot.has_energy() and plot.pos_of_energy(0.0) is not None:
            e = plot.energy_at_pos(pos)
            plot.set_view(plot.pos_of_energy(e - n), plot.pos_of_energy(e + n), None)
        else:
            plot.zoom_to_pos(pos, float(n))
        return True

    # ================================================================ export
    def export_plot_image(self, path: Optional[str] = None) -> bool:
        if self.current_spectrum() is None:
            return False
        if path is None:
            base = (self._path.stem if self._path else "spectrum") + ".png"
            folder = self.settings.folder("image")
            flt = f"{tr('fd_png')};;{tr('fd_svg')}"
            path, chosen = QFileDialog.getSaveFileName(self, tr("fd_export_img_title"),
                                                       str(Path(folder) / base), flt)
            if not path:
                return False
            if not Path(path).suffix:
                path += ".svg" if chosen == tr("fd_svg") else ".png"
        p = Path(path)
        if p.suffix.lower() == ".svg":
            ok = self.plot.export_svg(str(p), title=self._path.name if self._path else "")
        else:
            ok = self.plot.export_png(str(p))
        if ok:
            self.settings.set_folder("image", p)
            self.statusBar().showMessage(tr("status_exported", path=str(p)), 10000)
        else:
            self.show_error(tr("err_write", path=str(p), fmt=p.suffix.upper().lstrip("."), msg=""))
        return ok

    def copy_plot(self) -> None:
        if self.current_spectrum() is None:
            return
        self.plot.copy_to_clipboard()
        self.statusBar().showMessage(tr("status_copied"), 4000)

    def export_rois(self, path: Optional[str] = None) -> Optional[Path]:
        if not self.plot.rois:
            return None
        if path is None:
            base = (self._path.stem if self._path else "spectrum") + "_roi.csv"
            path, _ = QFileDialog.getSaveFileName(self, tr("fd_roi_title"),
                                                  str(Path(self.settings.folder("export")) / base), tr("fd_csv"))
            if not path:
                return None
        try:
            out = export_rois_csv(self.plot, path)
        except OSError as exc:
            self.show_error(tr("err_write", path=str(path), fmt="CSV", msg=str(exc)))
            return None
        self.settings.set_folder("export", out)
        self.statusBar().showMessage(tr("status_exported", path=str(out)), 10000)
        return out

    def export_analysis(self, path: Optional[str] = None) -> Optional[Path]:
        panel = self.analysis_panel
        if not (panel.peaks or panel.matches):
            return None
        if path is None:
            base = (self._path.stem if self._path else "spectrum") + "_analysis.xlsx"
            flt = f"{tr('fd_xlsx')};;{tr('fd_csv')}"
            path, chosen = QFileDialog.getSaveFileName(self, tr("fd_ana_title"),
                                                       str(Path(self.settings.folder("export")) / base), flt)
            if not path:
                return None
            if not Path(path).suffix:
                path += ".csv" if chosen == tr("fd_csv") else ".xlsx"
        try:
            out = export_results(path, self.current_spectrum(), panel.peaks, panel.matches)
        except Exception as exc:
            self.show_error(tr("err_write", path=str(path), fmt=Path(path).suffix, msg=str(exc)))
            return None
        self.settings.set_folder("export", out)
        self.statusBar().showMessage(tr("status_exported", path=str(out)), 10000)
        return out

    # ============================================================== overlays
    def add_overlay_file(self, path: Optional[str] = None) -> bool:
        if self.current_spectrum() is None:
            return False
        if path is None:
            path = self._ask_open_file(tr("fd_overlay_title"), "overlay")
            if not path:
                return False
        p = Path(path)
        try:
            spectra, _fmt = read_spectra(p, self.settings.input_format())
        except Exception as exc:
            self.show_error(tr("err_read", path=str(p), fmt=tr("auto_detect"), msg=str(exc) or type(exc).__name__))
            return False
        self.settings.set_folder("overlay", p)
        for k, s in enumerate(spectra[:1] if len(spectra) == 1 else spectra):
            label = p.name if len(spectra) == 1 else f"{p.name} #{k + 1}"
            self.plot.add_overlay(s, label)
        self.statusBar().showMessage(tr("status_overlay", name=p.name), 6000)
        return True

    def _rebuild_overlay_menu(self) -> None:
        m = self.menu_overlays
        m.clear()
        m.addAction(self.act_overlay_add)
        m.addAction(self.act_overlay_norm)
        if self.plot.overlays:
            m.addSeparator()
            for i, ov in enumerate(self.plot.overlays):
                a = m.addAction(tr("act_overlay_remove", name=ov.label))
                a.triggered.connect(lambda _=False, k=i: self.plot.remove_overlay(k))
            m.addSeparator()
            m.addAction(self.act_overlay_clear)
        self.act_overlay_clear.setEnabled(bool(self.plot.overlays))

    # ================================================================== ROIs
    def _on_rois_changed(self) -> None:
        n = len(self.plot.rois)
        self.act_clear_rois.setEnabled(n > 0)
        last = self.plot.last_roi
        if n > self._roi_count and last is not None and last in self.plot.rois and last.stats is not None:
            if self.roi_dock.isHidden():
                self.roi_dock.show()
                self.resizeDocks([self.roi_dock], [max(180, self.height() // 4)], Qt.Vertical)
            self.roi_dock.raise_()
            st = last.stats
            self.statusBar().showMessage(tr("roi_status", n=self.plot.rois.index(last) + 1, g=f"{st.gross:.0f}",
                                            net=f"{st.net:.1f}", unc=f"{st.net_unc:.1f}"), 15000)
        self._roi_count = n
        self.overview.update()
    def _plot_context_menu(self, global_pos, pos: float) -> None:
        menu = QMenu(self)
        menu.addAction(self.act_back)
        menu.addAction(self.act_forward)
        menu.addAction(self.act_reset)
        menu.addSeparator()
        menu.addAction(self.act_auto_y)
        ym = menu.addMenu(tr("menu_yscale"))
        for a in self.act_y.values():
            ym.addAction(a)
        menu.addSeparator()
        if not math.isnan(pos):
            k = self.plot.roi_at(pos)
            if k >= 0:
                a = menu.addAction(tr("act_delete_roi_here", n=k + 1))
                a.triggered.connect(lambda _=False, i=k: self.plot.remove_roi(i))
        menu.addAction(self.act_clear_rois)
        menu.addSeparator()
        menu.addAction(self.act_analyze)
        menu.addAction(self.act_labels)
        menu.addAction(self.act_overlay_add)
        menu.addSeparator()
        menu.addAction(self.act_export_img)
        menu.addAction(self.act_copy_img)
        menu.exec(global_pos)

    # ============================================================== analysis
    def refresh_analysis_available(self) -> None:
        self._ana_reason = ana.engine_status()
        if self._ana_reason is not None:
            tip = tr("tip_analyze_missing") + f"\n({self._ana_reason})"
            self.act_analyze.setToolTip(tip)
            self.act_analyze.setStatusTip(tr("tip_analyze_missing"))
        else:
            self.act_analyze.setToolTip(tr("tip_analyze"))
            self.act_analyze.setStatusTip(tr("tip_analyze"))
        self.act_auto_analyze.setEnabled(self._ana_reason is None)
        if hasattr(self, "goto_edit"):
            self._update_actions()

    def analysis_running(self) -> bool:
        return self._ana_thread is not None

    def _sampling_date(self, spec):
        """End (else start) of sampling of the session's sample information, None if unknown or
        after the acquisition start (identify would refuse it)."""
        from datetime import datetime
        ctl = getattr(self, "session_ctl", None)
        s = ctl.session_for(spec) if ctl is not None else None
        sample = (s.sample or {}) if s is not None else {}
        value = sample.get("sampling_end") or sample.get("sampling_start")
        if not value:
            return None
        try:
            d = datetime.fromisoformat(str(value))
        except ValueError:
            return None
        return None if spec.start_time is not None and d > spec.start_time else d

    def run_analysis(self, silent: bool = False) -> bool:
        spec = self.current_spectrum()
        if spec is None:
            if not silent:
                self.show_info(tr("ana_no_spectrum"))
            return False
        if self._ana_reason is not None:
            if not silent:
                self.show_error(tr("ana_missing", msg=self._ana_reason))
            return False
        if self._ana_thread is not None:
            return False
        self._ana_token += 1
        self._ana_silent = silent
        thread = QThread(self)
        self._ana_application = self.analysis_panel.application()
        worker = AnalysisWorker(spec, self._ana_token, application=self._ana_application,
                                sampled=self._sampling_date(spec))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(self._on_analysis_done)
        worker.failed.connect(self._on_analysis_failed)
        quit_on(thread, worker.done, worker.failed)
        thread.finished.connect(self._on_analysis_thread_finished)
        self._ana_thread, self._ana_worker = thread, worker
        self.act_analyze.setEnabled(False)
        self.statusBar().showMessage(tr("ana_running"))
        QApplication.setOverrideCursor(Qt.BusyCursor)
        thread.start()
        return True

    def _on_analysis_thread_finished(self) -> None:
        QApplication.restoreOverrideCursor()
        if self._ana_thread is not None:
            self._ana_thread.deleteLater()
        if self._ana_worker is not None:
            self._ana_worker.deleteLater()
        self._ana_thread = self._ana_worker = None
        self._update_actions()
        ended, self._ana_ended = getattr(self, "_ana_ended", None), None
        if ended is not None:                     # a report command waiting for this analysis
            self._resume_report(*ended)

    def _on_analysis_done(self, token: int, peaks, matches, identified: bool) -> None:
        if token != self._ana_token:
            return
        self._ana_ended = (token, True)
        self.analysis_panel.set_results(peaks, matches, identified, getattr(self, "_ana_application", None))
        from ..analysis.background import not_poisson_note
        if not_poisson_note(self.current_spectrum()):
            banner = self.analysis_panel.banner
            prev = "" if banner.isHidden() else banner.text() + "\n\n"
            self.analysis_panel.show_message(prev + tr("ana_not_poisson"))
        self.plot.set_peaks(peaks)
        self.plot.set_highlight(None)
        if self.analysis_dock.isHidden():
            self.analysis_dock.show()
            self.resizeDocks([self.analysis_dock], [max(200, self.height() // 3)], Qt.Vertical)
        self.analysis_dock.raise_()
        self.statusBar().showMessage(tr("ana_done", p=len(peaks), n=len(matches)), 10000)
        ctl = getattr(self, "session_ctl", None)
        if ctl is not None:
            ctl.analysis_done(self.current_spectrum(), peaks, matches, getattr(self, "_ana_application", None))

    def _on_analysis_failed(self, token: int, kind: str, msg: str) -> None:
        if token != self._ana_token:
            return
        self._ana_ended = (token, False)
        self.statusBar().clearMessage()
        if kind == "missing":
            self._ana_reason = msg
            self.refresh_analysis_available_from_reason()
            text = tr("ana_missing", msg=msg)
        else:
            text = tr("ana_failed", msg=msg)
        self.analysis_panel.show_message(text)
        if not self._ana_silent:
            self.show_error(text)

    def refresh_analysis_available_from_reason(self) -> None:
        self.act_analyze.setToolTip(tr("tip_analyze_missing") + f"\n({self._ana_reason})")
        self.act_auto_analyze.setEnabled(False)

    def zoom_to_peak(self, peak) -> None:
        fw = peak.fwhm if peak.fwhm and peak.fwhm > 0 else self.plot.default_fwhm_channels(
            self.plot.pos_of_channel(peak.centroid))
        self.plot.zoom_to_channel(peak.centroid, half_channels=5 * fw)

    def _on_nuclide_selected(self, m) -> None:
        if m is None:
            self.plot.set_highlight(None)
            return
        self.plot.set_highlight(Highlight(m.nuclide, ana.expected_lines(m), [pk for _, pk in m.matched]))

    # ============================================================ drag & drop
    def handle_dropped(self, paths: Sequence[str]) -> None:
        items = [Path(p) for p in paths if p]
        if not items:
            return
        if len(items) == 1 and items[0].is_dir():
            self.convert_folder(items[0])
            return
        if len(items) == 1:
            self.load_file(items[0])
            return
        if any(p.is_dir() for p in items):          # folders are searched on a worker thread
            from .worker import call_stop, start_call
            self.statusBar().showMessage(tr("scan_folder_running"))
            stop = call_stop(self)
            start_call(self, lambda: expand_spectrum_paths(items, stop=stop), self._dropped_files_found,
                       self._dropped_scan_failed)
            return
        self._dropped_files_found(expand_spectrum_paths(items))

    def _dropped_files_found(self, files) -> None:
        self.statusBar().clearMessage()
        if files:
            self.open_batch(files)

    def _dropped_scan_failed(self, msg: str) -> None:
        self.statusBar().clearMessage()
        self.show_error(msg)

    def dragEnterEvent(self, ev):
        if SpectrumPlot.local_paths(ev.mimeData()):
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        paths = SpectrumPlot.local_paths(ev.mimeData())
        if paths:
            ev.acceptProposedAction()
            self.handle_dropped(paths)

    # ================================================================ closing
    def _restore_geometry(self) -> None:
        geo = self.settings.get("window/geometry")
        if isinstance(geo, (QByteArray, bytes)) and geo:
            self.restoreGeometry(geo)
        split = self.settings.get("window/splitter")
        if isinstance(split, (QByteArray, bytes)) and split:
            self.splitter.restoreState(split)
        state = self.settings.get("window/state")
        if isinstance(state, (QByteArray, bytes)) and state:
            self.restoreState(state)

    def closeEvent(self, ev):
        ctl = getattr(self, "session_ctl", None)
        if ctl is not None and not ctl.confirm_discard():    # unsaved analysis session
            ev.ignore()
            return
        from .worker import cancel_calls
        cancel_calls(self)                                     # a dropped folder being searched
        for dlg in (list(getattr(self, "_report_batch_dialogs", [])) + list(self._batch_dialogs)
                    + list(getattr(self, "_analysis_batch_dialogs", []))):
            if dlg.is_running():
                dlg.cancel()
                dlg.wait()
        if self._ana_thread is not None:
            self._ana_token += 1
            self._ana_thread.quit()
            self._ana_thread.wait()                    # never destroy a running thread
        from .aptec_view_ui import save_on_exit
        if save_on_exit(self):                                 # View > Save Settings on Exit
            self.settings.set("window/geometry", self.saveGeometry())
            self.settings.set("window/splitter", self.splitter.saveState())
            self.settings.set("window/state", self.saveState())
        self.settings.sync()
        super().closeEvent(ev)


# =================================================================== application
def _pick_font_family() -> str:
    from PySide6.QtGui import QFontDatabase
    families = set(QFontDatabase.families())
    for fam in UI_FONT_FAMILIES:
        if fam in families:
            return fam
    return QApplication.font().family()


def style_application(app: QApplication) -> None:
    app.setStyle(QStyleFactory.create("Fusion"))
    pal = QPalette()
    window = QColor("#f3f5f8")
    pal.setColor(QPalette.Window, window)
    pal.setColor(QPalette.WindowText, QColor("#1f2933"))
    pal.setColor(QPalette.Base, QColor("#ffffff"))
    pal.setColor(QPalette.AlternateBase, QColor("#f6f8fb"))
    pal.setColor(QPalette.ToolTipBase, QColor("#fffef5"))
    pal.setColor(QPalette.ToolTipText, QColor("#1f2933"))
    pal.setColor(QPalette.Text, QColor("#1f2933"))
    pal.setColor(QPalette.Button, QColor("#f7f8fa"))
    pal.setColor(QPalette.ButtonText, QColor("#1f2933"))
    pal.setColor(QPalette.Highlight, QColor("#2f6db3"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.Link, QColor("#2f6db3"))
    pal.setColor(QPalette.PlaceholderText, QColor("#8a96a3"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor("#9aa5b1"))
    app.setPalette(pal)
    font = QFont(_pick_font_family())
    font.setPointSizeF(10)
    app.setFont(font)
    app.setStyleSheet("""
        QGroupBox { font-weight: 600; border: 1px solid #d5dbe1; border-radius: 6px;
                    margin-top: 12px; padding: 10px 8px 8px 8px; background: #ffffff; }
        QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                           left: 10px; right: 10px; padding: 0 4px; color: #1f4e79; }
        QLabel#infoLabel { color: #5b6773; font-weight: 400; }
        QLabel#infoValue { color: #1f2933; font-weight: 400; }
        QFrame#plotFrame { background: #ffffff; border: 1px solid #d5dbe1; border-radius: 6px; }
        QToolBar { border: none; border-bottom: 1px solid #dde2e7; spacing: 4px; padding: 3px 6px; }
        QToolBar QToolButton { padding: 3px 6px; border-radius: 4px; }
        QToolBar QToolButton:hover { background: #e3ebf5; }
        QToolBar QToolButton:checked { background: #d3e2f3; }
        QDockWidget::title { padding: 4px 8px; background: #e9edf2; }
        QStatusBar { border-top: 1px solid #dde2e7; }
        QStatusBar QLabel { padding: 0 6px; }
        QLabel#creditLabel { color: #9aa5b1; font-size: 8.5pt; }
        QProgressBar { border: 1px solid #c8d0d8; border-radius: 4px; text-align: center;
                       background: #ffffff; min-height: 18px; }
        QProgressBar::chunk { background: #3f80c4; border-radius: 3px; }
        QSplitter::handle { background: transparent; }
    """)


def _set_windows_app_id() -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SpectraMaster.GUI")
        except Exception:
            pass


def create_app(argv: Optional[list[str]] = None) -> QApplication:
    app = QApplication.instance()
    if app is None:
        _set_windows_app_id()
        app = QApplication(argv if argv is not None else sys.argv[:1])
    app.setApplicationName("SpectraMaster")
    app.setOrganizationName("SpectraMaster")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(app_icon())
    style_application(app)
    from .window_buttons import install
    install(app)            # maximize / minimize buttons on every dialog
    return app


# ------------------------------------------------------------------------ splash screen
SPLASH_MIN_SECONDS = 1.5


def splash_enabled(settings: Optional[Settings] = None) -> bool:
    """Off with SPECTRAMASTER_NO_SPLASH=1, under pytest, offscreen, or when disabled in settings."""
    if os.environ.get("SPECTRAMASTER_NO_SPLASH") or "PYTEST_CURRENT_TEST" in os.environ:
        return False
    if os.environ.get("QT_QPA_PLATFORM", "") == "offscreen":
        return False
    return settings.get_bool("ui/show_splash", True) if settings is not None else True


def splash_pixmap() -> QPixmap:
    """Product logo + designer monogram + name + version on a white card."""
    from .icon import designer_pixmap, logo_pixmap
    w, h = 560, 360
    pm = QPixmap(w, h)
    pm.fill(QColor("#ffffff"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.setPen(QPen(QColor("#c9d3dd"), 1))
    p.drawRect(0, 0, w - 1, h - 1)
    logo = logo_pixmap(330)
    y = 18
    if logo is not None:
        if logo.height() > 200:
            logo = logo.scaledToHeight(200, Qt.SmoothTransformation)
        p.drawPixmap((w - logo.width()) // 2, y, logo)
        y += logo.height() + 8
    else:
        f = QFont(QApplication.font())
        f.setPointSizeF(22)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#1f4e79"))
        p.drawText(QRectF(0, y, w, 60), Qt.AlignCenter, "SpectraMaster")
        y += 70
    p.setPen(QPen(QColor("#e1e6eb"), 1))
    p.drawLine(40, y, w - 40, y)
    y += 10
    small = designer_pixmap(72)
    f = QFont(QApplication.font())
    f.setPointSizeF(10)
    p.setFont(f)
    text_x = 40
    if small is not None:
        p.drawPixmap(40, y, small)
        text_x = 40 + small.width() + 16
    p.setPen(QColor("#5b6773"))
    p.drawText(QRectF(text_x, y + 6, w - text_x - 30, 20), Qt.AlignLeft | Qt.AlignVCenter,
               "Designed & developed by")
    fb = QFont(f)
    fb.setPointSizeF(13)
    fb.setBold(True)
    p.setFont(fb)
    p.setPen(QColor("#1f2933"))
    p.drawText(QRectF(text_x, y + 26, w - text_x - 30, 26), Qt.AlignLeft | Qt.AlignVCenter, "Edrees F. Hery")
    p.setFont(f)
    p.setPen(QColor("#5b6773"))
    p.drawText(QRectF(text_x, y + 52, w - text_x - 30, 20), Qt.AlignLeft | Qt.AlignVCenter,
               f"Version {__version__}  ·  2026")
    p.end()
    return pm


def make_splash() -> QSplashScreen:
    sp = QSplashScreen(splash_pixmap(), Qt.WindowStaysOnTopHint)
    sp.setObjectName("splash")
    return sp   # QSplashScreen hides itself on a mouse click


# ------------------------------------------------------------- DataMaster single-exe mode
_DM_CODE = re.compile(r"^-\d+$")


def is_datamaster_args(args: Sequence[str]) -> bool:
    """True for ``-i IN -j OUT`` (DataMaster command line; i may be 0 = auto-detect)."""
    return len(args) == 4 and bool(_DM_CODE.match(args[0])) and bool(_DM_CODE.match(args[2]))


def run_datamaster_silent(args: Sequence[str]) -> tuple[int, str]:
    """Run the CLI's DataMaster conversion without a console; returns (exit code, messages)."""
    from ..cli import run_datamaster
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            code = int(run_datamaster(list(args)) or 0)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
    except Exception as exc:  # pragma: no cover - defensive
        buf.write(f"{type(exc).__name__}: {exc}\n")
        code = 1
    return code, buf.getvalue().strip()


SMOKE_FLAG = "--smoke-test"   # start, open the given file(s), exit after 1.5 s: 0 = ok, 3 = load failed


def main(argv: Optional[list[str]] = None) -> int:
    """GUI entry point. Extra arguments are files to open (first one is displayed).

    ``-i IN -j OUT`` (DataMaster syntax) converts silently and exits 0 without a
    window; if the conversion fails the program switches to interactive mode like
    DataMaster: the main window opens with IN loaded (when readable) and the error.
    """
    argv = list(sys.argv if argv is None else argv)
    args = argv[1:]
    smoke = SMOKE_FLAG in args
    if smoke:
        args = [a for a in args if a != SMOKE_FLAG]
    dm_error: Optional[str] = None
    if is_datamaster_args(args):
        code, messages = run_datamaster_silent(args)
        if code == 0:
            return 0
        dm_error = messages or "conversion failed"
    app = create_app(argv[:1])
    settings = Settings()
    splash = None
    if dm_error is None and not smoke and splash_enabled(settings):
        splash = make_splash()
        splash.show()
        app.processEvents()
    t0 = time.monotonic()
    win = MainWindow(settings)
    if splash is not None:
        remaining = max(0.0, SPLASH_MIN_SECONDS - (time.monotonic() - t0))

        def _reveal():
            win.show()
            splash.finish(win)
        QTimer.singleShot(int(remaining * 1000), _reveal)
    else:
        win.show()
    if dm_error is not None:
        open_datamaster_failure(win, args, dm_error)
        return app.exec()
    files = [a for a in args if not a.startswith("-")]
    errors: list[str] = []
    if smoke:
        win.show_error = errors.append        # never block on a modal box in a smoke test
    ok = True
    if len(files) == 1:
        ok = bool(win.load_file(files[0]))
    elif len(files) > 1:
        win.handle_dropped(files)
    if smoke:
        code = 0 if ok and not errors and (not files or win.current_spectrum() is not None) else 3
        QTimer.singleShot(1500, lambda: app.exit(code))
    return app.exec()


def open_datamaster_failure(win: MainWindow, args: Sequence[str], message: str) -> None:
    """Interactive recovery after a failed ``-i IN -j OUT`` conversion."""
    src = Path(args[1])
    in_fmt = None
    try:
        code = int(args[0][1:])
        if code:
            in_fmt = get_format(code)
    except (KeyError, ValueError):
        in_fmt = None
    if src.is_file():
        errors: list[str] = []
        original = win.show_error
        win.show_error = errors.append          # a read failure is reported in the combined message
        try:
            if not win.load_file(src, in_fmt) and in_fmt is not None:
                win.load_file(src, None)
        finally:
            win.show_error = original
    win.show_error(tr("dm_failed", cmd=" ".join(args), msg=message))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

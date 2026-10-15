"""Aptec-style View menu (headless)."""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from spectramaster.analysis import Peak
from spectramaster.gui import i18n
from spectramaster.model import Spectrum


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


def _make(tmp_path):
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.settings import Settings
    w = MainWindow(Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)))
    w.errors, w.infos = [], []
    w.show_error = w.errors.append
    w.show_info = w.infos.append
    return w


@pytest.fixture()
def window(qapp, tmp_path):
    from spectramaster.gui import plot as plotmod
    i18n.set_language("en")
    w = _make(tmp_path)
    yield w
    w.close()
    w.deleteLater()
    QApplication.processEvents()
    plotmod.apply_colors(plotmod.DEFAULT_COLORS)
    i18n.set_language("en")


def _spectrum(n=1024, base=500.0):
    counts = [base + 1000.0 * math.exp(-0.5 * ((i - 300) / 3.0) ** 2) for i in range(n)]
    return Spectrum(counts=counts, energy_coeffs=[0.0, 0.5], live_time=100.0, real_time=110.0, sample_id="v")


def _show(window, spec=None):
    window.display([spec or _spectrum()], None, None)
    window.plot.resize(1000, 400)
    return window.plot


def _items(menu):
    return [a.text().replace("&", "").split(" (")[0] for a in menu.actions() if not a.isSeparator()]


def test_view_menu_like_aptec(window):
    titles = [a.text().replace("&", "") for a in window.menuBar().actions()]
    assert titles.index("View") == titles.index("Analyze") + 1
    items = _items(window.menu_view)
    expected = ["Preferences...", "Color...", "QA Control Bar...", "Default Position", "Save Settings on Exit",
                "Vertical Scale", "Horizontal Scale", "Horizontal Split", "Vertical Split", "Next ROI",
                "Previous ROI", "Plot All Points", "Fill Spc", "Grid", "Show Fitted ROIs", "Fill Normal ROIs",
                "ROI Data", "ROI Display", "Show ROI Labels", "Show Channel Marker", "FWHM Percent",
                "Connect Points", "More View Options", "Language"]
    assert items == expected
    keys = {"act_v_qa": "Ctrl+8", "act_v_hsplit": "H", "act_v_vsplit": "V", "act_v_all_points": "L",
            "act_v_fill_spc": "F", "act_v_grid": "G", "act_v_fitted": "K", "act_v_fill_rois": "Shift+F",
            "act_v_roi_data": "D", "act_v_roi_display": "Shift+D", "act_v_marker": "Shift+J",
            "act_v_connect": "N", "act_v_auto_zero": "Z", "act_v_next_scale": "S", "act_v_prev_scale": "Shift+S",
            "act_v_x_channel": "C", "act_v_x_energy": "E"}
    for attr, key in keys.items():
        assert getattr(window, attr).shortcut() == QKeySequence(key), attr
    assert window.act_v_roi_labels.shortcut() == QKeySequence("J")
    window.act_v_roi_labels.trigger()
    assert not window.act_labels.isChecked() and not window.plot.show_labels
    window.act_labels.trigger()
    assert window.act_v_roi_labels.isChecked()
    assert window.act_auto_y.shortcut() == QKeySequence("A")
    # SpectraMaster's own commands are kept
    more = window.menu_v_more.actions()
    assert window.act_back in more and window.act_goto in more and window.act_open_preview in more
    assert window.act_labels in more
    assert window.menu_lang.menuAction() in window.menu_view.actions()


def test_display_toggles_change_plot_and_are_saved(window, qapp, tmp_path):
    plot = _show(window)
    assert plot.fill_spectrum is False                 # Aptec: points by default
    window.act_v_fill_spc.trigger()
    assert plot.fill_spectrum is True
    assert not plot.grab().isNull()
    assert plot.plot_all_points is False               # Aptec: highest channel per column
    window.act_v_all_points.trigger()
    for attr, pattr in (("act_v_grid", "show_grid"), ("act_v_fill_spc", "fill_spectrum"),
                        ("act_v_all_points", "plot_all_points"), ("act_v_fill_rois", "fill_rois"),
                        ("act_v_roi_display", "show_rois"), ("act_v_marker", "show_marker")):
        assert getattr(plot, pattr) is True
        getattr(window, attr).trigger()
        assert getattr(plot, pattr) is False, attr
    window.act_v_connect.trigger()
    window.act_v_fwhm_pct.trigger()
    assert plot.connect_points and plot.fwhm_percent
    assert not plot.grab().isNull()
    w2 = _make(tmp_path)
    try:
        assert not w2.plot.show_grid and not w2.plot.fill_spectrum and w2.plot.connect_points
        assert not w2.act_v_grid.isChecked()
    finally:
        w2.close()
        w2.deleteLater()


def test_fitted_and_roi_data_cycle(window):
    plot = _show(window)
    assert plot.fitted_mode == "show"
    window.act_v_fitted.trigger()
    assert plot.fitted_mode == "fill" and "Fill" in window.act_v_fitted.text()
    window.act_v_fitted.trigger()
    assert plot.fitted_mode == "hide" and not window.act_v_fitted.isChecked()
    window.act_v_fitted.trigger()
    assert plot.fitted_mode == "show"
    assert plot.roi_data == "stats"
    window.act_v_roi_data.trigger()
    assert plot.roi_data == "background"
    window.act_v_roi_data.trigger()
    assert plot.roi_data == "off"


def test_roi_information_box(window):
    plot = _show(window)
    plot.add_roi(285, 315)
    plot.index_roi(0)
    lines = plot.roi_box_lines()
    assert lines[0] == "ROI 1"
    assert any(s.startswith("Gross = ") for s in lines) and any(s.startswith("FWHM = ") for s in lines)
    window.act_v_fwhm_pct.trigger()
    assert any(s.startswith("FWHM = ") and s.endswith("%\u2069") for s in plot.roi_box_lines())
    window.act_v_roi_data.trigger()                       # background parameters
    lines = plot.roi_box_lines()
    assert lines[1].startswith("BL 282") and lines[2].startswith("B0 = ")
    st = plot.rois[0].stats
    b0, b1 = float(lines[2].split("= ")[1]), float(lines[3].split("= ")[1])
    assert b0 + b1 * 300 == pytest.approx(st.background_at(300), rel=1e-4)
    assert not plot.grab().isNull()


def test_fitted_peaks_are_drawn_and_rendered(window):
    from spectramaster.gui.plot import PlotRenderer
    plot = _show(window)
    pk = Peak(centroid=300.0, energy=150.0, fwhm=7.06, fwhm_kev=3.5, net_area=7520.0, net_area_unc=90.0,
              gross_area=0, background=500.0 * 31, left=285, right=315, significance=80)
    plot.set_peaks([pk])
    for mode in ("show", "fill"):
        plot.fitted_mode = mode
        assert not plot.grab().isNull()
    r = PlotRenderer.from_plot(plot)
    assert r.fitted_mode == "fill"
    assert not r.render_image(400, 200, 1.0).isNull()


def test_split_display(window):
    plot = _show(window)
    window.resize(1200, 800)
    window.show()
    QApplication.processEvents()
    plot.set_view(250, 350)
    window.act_v_hsplit.trigger()
    assert window.split_mode == "h" and window.split_plot.isVisible()
    assert window.plot_splitter.orientation() == Qt.Vertical
    assert window.split_plot.window_band == (250, 350)
    window.act_v_vsplit.trigger()
    assert window.split_mode == "v" and not window.act_v_hsplit.isChecked()
    assert window.plot_splitter.orientation() == Qt.Horizontal
    window.split_plot.jumpRequested.emit(700)
    assert plot.x0 < 700 < plot.x1 and plot.marker == 700
    assert plot.x1 - plot.x0 == pytest.approx(100)
    window.act_v_vsplit.trigger()
    assert window.split_mode is None and not window.split_plot.isVisible()


def test_scales_and_marker_keys(window):
    plot = _show(window)
    window.act_v_x_channel.trigger()
    assert not plot.energy_axis and window.act_v_x_channel.isChecked()
    window.act_v_x_energy.trigger()
    assert plot.energy_axis
    window.act_v_next_scale.trigger()
    assert plot.y_mode == "log"
    window.act_v_next_scale.trigger()
    assert plot.y_mode == "sqrt"
    window.act_v_prev_scale.trigger()
    assert plot.y_mode == "log"
    window.set_y_mode("linear")
    # auto zero: the minimum follows the continuum (500 counts) instead of 0
    assert plot.y_range()[0] == 0.0
    window.act_v_auto_zero.trigger()
    plot._col_cache.clear()
    assert plot.y_range()[0] > 400
    window.act_v_auto_zero.trigger()
    # zoom cycle around the marker: 64, 16, all
    plot.set_marker(300)
    window.act_v_zoom.trigger()
    assert plot.x1 - plot.x0 == pytest.approx(64) and plot.x0 < 300 < plot.x1
    window.act_v_zoom.trigger()
    assert plot.x1 - plot.x0 == pytest.approx(16)
    window.act_v_zoom.trigger()
    assert (plot.x0, plot.x1) == (0, 1024)
    window.act_v_max_expand.trigger()
    assert plot.x1 - plot.x0 == pytest.approx(16)
    window.act_v_contract.trigger()
    assert plot.x1 - plot.x0 == pytest.approx(32)
    window.act_v_expand.trigger()
    assert plot.x1 - plot.x0 == pytest.approx(16)
    # marker keys (plot focus)
    x0 = plot.x0
    QTest.keyClick(plot, Qt.Key_Right)
    assert plot.marker == 301
    QTest.keyClick(plot, Qt.Key_End)
    assert plot.marker == int(math.ceil(plot.x1) - 1)
    QTest.keyClick(plot, Qt.Key_Right)                   # at the edge: the window scrolls
    assert plot.x0 > x0 and plot.x0 <= plot.marker < plot.x1
    QTest.keyClick(plot, Qt.Key_Home)
    assert plot.marker == int(plot.x0)
    QTest.keyClick(plot, Qt.Key_PageUp)
    assert plot.x0 > x0
    QTest.keyClick(plot, Qt.Key_PageDown, Qt.ShiftModifier)
    assert plot.x0 == 0
    QTest.keyClick(plot, Qt.Key_End, Qt.ShiftModifier)
    assert plot.marker == 1023 and plot.x1 == 1024
    ybot = plot.y_range()[0]
    plot.shift_base(1)
    assert plot.y_range()[0] < ybot


def test_colors_quick_access_bar_and_positions(window, monkeypatch, tmp_path):
    from spectramaster.gui import aptec_view_ui as ui
    from spectramaster.gui import plot as plotmod
    _show(window)
    ui.apply_colors(window, plotmod.BW_COLORS)
    assert plotmod.C_LINE.name() == "#000000"
    assert plotmod.current_colors()["roi"] == "#4d4d4d"
    dlg = ui.ColorDialog(plotmod.current_colors(), window)
    dlg.set_colors(plotmod.DEFAULT_COLORS)
    assert dlg.colors["line"] == "#1f5f99"
    dlg.aptec_btn.click()
    assert dlg.colors["bg"] == "#000000" and dlg.colors["line"] == "#ffff00"
    # quick access control bar
    assert window.act_print in window.toolbar.actions()
    ui.apply_qa_bar(window, {"act_print", "act_folder"})
    assert window.act_print not in window.toolbar.actions() and window.act_open in window.toolbar.actions()
    entries = dict(ui._qa_entries(window))
    assert "act_print" in entries and "act_open" in entries
    w2 = _make(tmp_path)
    try:
        assert w2.act_print not in w2.toolbar.actions()
        assert plotmod.C_LINE.name() == "#000000"          # colors restored from the settings
    finally:
        w2.close()
        w2.deleteLater()
    ui.apply_qa_bar(window, set())
    assert window.act_print in window.toolbar.actions()
    # save settings on exit / default position
    window.act_v_save_exit.trigger()
    assert not ui.save_on_exit(window)
    window.resize(700, 500)
    window.act_v_default_pos.trigger()
    assert window.height() == 760 and window.width() < 1400    # 1180 or the tool bars' minimum
    monkeypatch.setattr(ui.PreferencesDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(ui.PreferencesDialog, "apply", lambda self: None)
    assert ui.open_preferences(window)


def test_preferences_dialog_applies(window):
    from spectramaster.gui import aptec_view_ui as ui
    plot = _show(window)
    dlg = ui.PreferencesDialog(window)
    dlg.boxes["act_v_grid"].setChecked(False)
    dlg.boxes["act_roi_labels_alias"].setChecked(False)
    dlg.fitted.setCurrentIndex(2)
    dlg.data.setCurrentIndex(1)
    dlg.apply()
    assert not plot.show_grid and not window.act_labels.isChecked()
    assert plot.fitted_mode == "hide" and plot.roi_data == "background"


def test_double_click_indexes_rois(window):
    plot = _show(window)
    plot.add_roi(285, 315)
    plot.add_roi(600, 620)
    rect = plot.plot_rect()
    px = lambda idx: int(round(rect.left() + idx / 1024 * rect.width()))
    from PySide6.QtCore import QPoint
    QTest.mouseDClick(plot, Qt.LeftButton, Qt.NoModifier, QPoint(px(450), int(rect.center().y())))
    assert plot.roi_index == 1
    QTest.mouseDClick(plot, Qt.LeftButton, Qt.ShiftModifier, QPoint(px(450), int(rect.center().y())))
    assert plot.roi_index == 0


def test_arabic_view_menu(window):
    window.apply_language("ar", save=False)
    assert window.menu_view.title().replace("&", "") == "عرض"
    assert window.act_v_hsplit.text().replace("&", "") == "تقسيم أفقي"
    assert "خيارات" in window.menu_v_more.title()
    window.apply_language("en", save=False)


def test_old_display_settings_start_again_from_aptec_points(qapp, tmp_path):
    from spectramaster.gui.settings import Settings
    s = Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat))
    for key in ("fill_spc", "connect", "all_points", "grid"):
        s.set("aptec_view/" + key, True)            # saved by the first View menu (no version)
    s.set("aptec_view/grid", False)
    s.sync()
    w = _make(tmp_path)
    try:
        p = w.plot
        assert not p.fill_spectrum and not p.connect_points and not p.plot_all_points
        assert not p.show_grid                         # other choices are kept
        w.act_v_fill_spc.trigger()
    finally:
        w.close()
        w.deleteLater()
    w2 = _make(tmp_path)
    try:
        assert w2.plot.fill_spectrum                   # a new choice is remembered
    finally:
        w2.close()
        w2.deleteLater()


def test_paint_bar_hidden_after_restoring_the_window(qapp, tmp_path):
    w = _make(tmp_path)
    w.display([_spectrum()], None, None)
    w.show()
    w.plot.set_marker(300)
    w.plot.start_paint()
    QApplication.processEvents()
    assert w.roi_paint_bar.isVisible()
    w.close()                                          # the window state is saved with the bar shown
    w.deleteLater()
    QApplication.processEvents()
    w2 = _make(tmp_path)
    try:
        assert w2.roi_paint_bar.isHidden()
    finally:
        w2.close()
        w2.deleteLater()

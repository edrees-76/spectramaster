"""Keyboard and mouse navigation between found peaks (MAESTRO / Aptec / Genie style), dialog
window buttons, and coloured nuclide lines."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, QSettings, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from spectramaster.analysis import Peak
from spectramaster.model import Spectrum


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


def _peak(ch, e, nuclide="", line=None, fw=6.0):
    return Peak(centroid=ch, energy=e, fwhm=fw, fwhm_kev=fw * 0.5, net_area=1000.0, net_area_unc=40.0,
                gross_area=2000.0, background=1000.0, left=int(ch - 10), right=int(ch + 10), significance=25.0,
                nuclide=nuclide, line_energy=line)


@pytest.fixture()
def plot(qapp):
    from spectramaster.gui.plot import SpectrumPlot
    p = SpectrumPlot()
    p.resize(1000, 400)
    p.set_spectrum(Spectrum(counts=[100.0] * 1024, energy_coeffs=[0.0, 0.5]))
    p.set_peaks([_peak(600.3, 300.15), _peak(200.4, 100.2, "Am-241", 100.15), _peak(400.0, 200.0)])
    got = []
    p.peakIndexed.connect(got.append)
    p.got = got
    yield p
    p.deleteLater()


def _key(w, key, mods=Qt.NoModifier):
    QTest.keyClick(w, key, mods)


def test_ctrl_arrows_step_through_found_peaks(plot):
    plot.set_marker(0)
    _key(plot, Qt.Key_Right, Qt.ControlModifier)
    assert plot.marker == 200 and plot.got[-1].centroid == 200.4
    _key(plot, Qt.Key_Right, Qt.ControlModifier)
    assert plot.got[-1].centroid == 400.0
    _key(plot, Qt.Key_Right, Qt.ControlModifier)
    assert plot.got[-1].centroid == 600.3
    n = len(plot.got)
    _key(plot, Qt.Key_Right, Qt.ControlModifier)          # no peak further right: nothing moves
    assert len(plot.got) == n and plot.marker == 600
    _key(plot, Qt.Key_Left, Qt.ControlModifier)
    assert plot.got[-1].centroid == 400.0
    plot.set_marker(450)                                   # a click elsewhere: steps from the marker
    _key(plot, Qt.Key_Left, Qt.ControlModifier)
    assert plot.got[-1].centroid == 400.0


def test_space_and_tab_index_peaks_without_rois_and_wrap(plot):
    assert not plot.rois
    plot.set_marker(500)
    plot.index_next()                                      # Space (action) -> the next peak
    assert plot.got[-1].centroid == 600.3
    plot.index_next()                                      # wraps around
    assert plot.got[-1].centroid == 200.4
    plot.index_prev()                                      # Shift+Space wraps back
    assert plot.got[-1].centroid == 600.3
    QApplication.sendEvent(plot, QKeyEvent(QEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier))
    assert plot.got[-1].centroid == 200.4
    QApplication.sendEvent(plot, QKeyEvent(QEvent.KeyPress, Qt.Key_Backtab, Qt.ShiftModifier))
    assert plot.got[-1].centroid == 600.3


def test_space_still_indexes_rois_when_there_are_some(plot):
    plot.add_roi(100, 120)
    plot.set_marker(0)
    n = len(plot.got)
    plot.index_next()
    assert plot.roi_index == 0 and len(plot.got) == n      # ROIs first, as in Aptec


def _double_click(plot, idx_pos):
    rect = plot.plot_rect()
    x = float(plot._x_to_px(idx_pos, rect))
    pt = QPointF(x, rect.center().y())
    ev = QMouseEvent(QEvent.MouseButtonDblClick, pt, plot.mapToGlobal(pt.toPoint()), Qt.LeftButton,
                     Qt.LeftButton, Qt.NoModifier)
    plot.mouseDoubleClickEvent(ev)


def test_double_click_on_a_peak_shows_it_elsewhere_full_spectrum(plot):
    plot.set_view(150, 450)
    _double_click(plot, 402.0)
    assert plot.got and plot.got[-1].centroid == 400.0
    n = len(plot.got)
    _double_click(plot, 300.0)                             # far from every peak
    assert len(plot.got) == n and plot.view()[:2] == (0.0, 1024.0)


def test_line_colours(plot):
    from spectramaster.gui.plot import Highlight, line_has_peak
    peaks = plot.peaks
    assert line_has_peak(100.15, peaks) and not line_has_peak(59.54, peaks)
    plot.set_highlight(Highlight("Am-241", [59.54, 100.15], [peaks[1]]))
    plot.grab()                                            # paints both kinds without error


def test_peak_info_text(qapp):
    from spectramaster.gui import i18n
    from spectramaster.gui.analysis_panel import peak_info_text
    i18n.set_language("en")
    t = peak_info_text(_peak(200.4, 100.2, "Am-241", 100.15))
    assert "100.20 keV" in t and "1,000 ± 40" in t and "Am-241 100.15 keV" in t
    assert "no library match" in peak_info_text(_peak(400.0, 200.0))
    i18n.set_language("ar")
    assert "لا تطابق في المكتبة" in peak_info_text(_peak(400.0, 200.0))
    i18n.set_language("en")


def test_main_window_reports_and_selects_the_peak(qapp, tmp_path):
    from spectramaster.gui import i18n
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.settings import Settings
    i18n.set_language("en")
    w = MainWindow(Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)))
    try:
        w.display([Spectrum(counts=[100.0] * 1024, energy_coeffs=[0.0, 0.5])], None, None)
        peaks = [_peak(200.4, 100.2, "Am-241", 100.15), _peak(400.0, 200.0)]
        w.analysis_panel.set_results(peaks, [], True)
        w.plot.set_peaks(peaks)
        w.plot.set_marker(300)
        w.plot.peak_step(1)
        assert "200.00 keV" in w.statusBar().currentMessage()
        rows = {i.row() for i in w.analysis_panel.peak_table.selectedIndexes()}
        assert len(rows) == 1
        assert w.analysis_panel._row_index(w.analysis_panel.peak_table, rows.pop()) == 1
    finally:
        w.close()
        w.deleteLater()
        QApplication.processEvents()


def test_dialogs_get_maximize_buttons(qapp):
    d = QDialog()
    d.show()
    QApplication.processEvents()
    assert d.windowFlags() & Qt.WindowMaximizeButtonHint
    assert d.windowFlags() & Qt.WindowMinimizeButtonHint
    assert not d.windowFlags() & Qt.WindowContextHelpButtonHint
    assert d.windowFlags() & Qt.WindowCloseButtonHint        # was cleared with the help button
    d.close()
    m = QMessageBox()
    m.setText("x")
    m.show()
    QApplication.processEvents()
    assert m.windowFlags() & Qt.WindowMaximizeButtonHint     # every window the program draws
    assert m.windowFlags() & Qt.WindowCloseButtonHint
    m.close()


def test_every_dialog_class_of_the_program_gets_the_buttons(qapp):
    """The filter decides by class: every QDialog subclass defined in the GUI qualifies."""
    import importlib
    import inspect
    import pkgutil

    import spectramaster.gui as g
    from spectramaster.gui.window_buttons import wants_buttons
    found = []
    for m in pkgutil.iter_modules(g.__path__):
        if m.name.startswith("__"):                        # __main__ would start the program
            continue
        mod = importlib.import_module(f"spectramaster.gui.{m.name}")
        for _n, cls in inspect.getmembers(mod, inspect.isclass):
            if issubclass(cls, QDialog) and cls.__module__ == mod.__name__:
                found.append(cls)
    assert len(found) >= 20
    assert "PreviewFileDialog" in {c.__name__ for c in found}        # the open dialog too
    assert wants_buttons(QDialog()) and wants_buttons(QMessageBox())

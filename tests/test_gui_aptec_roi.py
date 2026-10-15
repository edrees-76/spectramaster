"""Aptec-style ROI menu, ROI Paint bar and indexing (headless)."""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from spectramaster.analysis.aptec_roi import RoiProperties
from spectramaster.gui import i18n
from spectramaster.model import Spectrum


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


@pytest.fixture()
def window(qapp, tmp_path):
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.settings import Settings
    i18n.set_language("en")
    w = MainWindow(Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)))
    w.errors, w.infos = [], []
    w.show_error = w.errors.append
    w.show_info = w.infos.append
    yield w
    w.close()
    w.deleteLater()
    QApplication.processEvents()
    i18n.set_language("en")


def _spectrum(n=1024, peaks=((300.0, 1000.0), (600.0, 800.0)), a=50.0, b=0.05):
    counts = []
    for i in range(n):
        v = a + b * i
        for mu, amp in peaks:
            v += amp * math.exp(-0.5 * ((i - mu) / 3.0) ** 2)
        counts.append(v)
    return Spectrum(counts=counts, energy_coeffs=[0.0, 0.5], live_time=100.0, real_time=110.0,
                    sample_id="roi")


def _show(window, spec=None):
    window.display([spec or _spectrum()], None, None)
    window.plot.resize(1000, 400)
    return window.plot


def test_roi_menu_like_aptec(window):
    titles = [a.text().replace("&", "") for a in window.menuBar().actions()]
    assert titles.index("ROI") == titles.index("Analyze") - 1
    items = [a.text().replace("&", "").split("\t")[0] for a in window.menu_roi.actions() if not a.isSeparator()]
    assert items == ["Properties...", "Paint", "Edit", "Delete Indexed", "Delete All...", "Sort",
                     "Flag Definitions"]
    assert window.act_roi_props.shortcut() == QKeySequence("Shift+R")
    assert window.act_roi_paint.shortcut() == QKeySequence("F3")
    assert window.act_roi_edit.shortcut() == QKeySequence("F4")
    assert window.act_roi_del_indexed.shortcut() == QKeySequence("Del")
    assert window.act_roi_next.shortcut() == QKeySequence("Space")
    assert window.act_roi_prev.shortcut() == QKeySequence("Shift+Space")
    assert "Ctrl-Click" in window.act_roi_paint.text()


def test_plot_rois_use_aptec_rules(window):
    plot = _show(window)
    roi = plot.add_roi(285, 315)
    st = roi.stats
    # end points outside the ROI: the linear continuum is removed exactly
    assert (st.bl, st.bh) == (282, 318)
    assert st.net == pytest.approx(1000 * 3 * math.sqrt(2 * math.pi), rel=1e-3)
    assert st.net_unc == pytest.approx(math.sqrt(st.gross + st.background))
    assert st.centroid == pytest.approx(300.0, abs=0.01)
    assert st.err_pct == pytest.approx(st.net_unc / st.net * 100)
    row = window.roi_panel.table
    assert row.rowCount() == 1
    headers = [row.horizontalHeaderItem(c).text() for c in range(row.columnCount())]
    assert "Background" in headers and "Flags" in headers and "% Err (1σ)" in headers


def test_properties_dialog_recalculates_and_is_saved(window, monkeypatch):
    from spectramaster.gui import aptec_roi_ui as ui
    plot = _show(window)
    plot.add_roi(285, 315)
    new = RoiProperties(bkg_degree=0, end_points=6, centroid_range="all", centroid_weight="net",
                        mda_sigma=2.0, error_sigma=2.0)
    dlg = ui.RoiPropertiesDialog(RoiProperties())
    dlg.set_properties(new)
    assert dlg.properties() == new
    monkeypatch.setattr(ui.RoiPropertiesDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(ui.RoiPropertiesDialog, "properties", lambda self: new)
    assert ui.open_properties(window) == new
    st = plot.rois[0].stats
    assert (st.bl, st.bh) == (279, 321)
    assert plot.roi_props == new
    assert ui.load_properties(window.settings) == new
    headers = [window.roi_panel.table.horizontalHeaderItem(c).text()
               for c in range(window.roi_panel.table.columnCount())]
    assert "% Err (2σ)" in headers


def test_paint_bar_expand_shrink_shift_set(window):
    plot = _show(window)
    plot.set_marker(600)
    window.act_roi_paint.trigger()
    assert plot.paint is not None and not window.roi_paint_bar.isHidden()
    a, b = plot.paint
    assert a < 600 < b
    # while painting, F3-F6 belong to the paint bar
    assert window.act_paint_expand.shortcut() == QKeySequence("F3")
    assert window.act_roi_paint.shortcut().isEmpty()
    assert window.act_e_sample.shortcut().isEmpty()              # F5 = Sample Description
    window.act_paint_expand.trigger()
    assert plot.paint == [a - 1, b + 1]
    window.act_paint_shrink.trigger()
    window.act_paint_shrink.trigger()
    assert plot.paint == [a + 1, b - 1]
    window.act_paint_left.trigger()
    window.act_paint_right.trigger()
    window.act_paint_right.trigger()
    assert plot.paint == [a + 2, b]
    assert "ROI Paint" in window.statusBar().currentMessage()
    window.act_paint_set.trigger()
    assert plot.paint is None and window.roi_paint_bar.isHidden()
    assert [(r.left, r.right) for r in plot.rois] == [(a + 2, b)]
    assert plot.roi_index == 0
    # shortcuts restored
    assert window.act_roi_paint.shortcut() == QKeySequence("F3")
    assert window.act_analyze.shortcut() == QKeySequence("P")
    assert window.act_paint_expand.shortcut().isEmpty()


def test_paint_cancel_and_edit_delete(window):
    plot = _show(window)
    plot.set_marker(300)
    plot.start_paint()
    window.act_paint_cancel.trigger()
    assert plot.paint is None and not plot.rois
    plot.add_roi(285, 315)
    plot.add_roi(590, 610)
    plot.index_roi(1)
    window.act_roi_edit.trigger()
    assert plot.paint == [590, 610] and plot.paint_edit is plot.rois[1]
    plot.paint_expand(2)
    plot.paint_set()
    assert (plot.rois[1].left, plot.rois[1].right) == (588, 612)
    plot.index_roi(0)
    plot.edit_indexed()
    window.act_paint_delete.trigger()
    assert [(r.left, r.right) for r in plot.rois] == [(588, 612)]


def test_ctrl_click_quick_paint(window):
    plot = _show(window)
    rect = plot.plot_rect()
    px = lambda idx: QPoint(int(round(rect.left() + (idx + 0.5) / 1024 * rect.width())), int(rect.center().y()))
    QTest.mouseClick(plot, Qt.LeftButton, Qt.ControlModifier, px(288))
    assert plot.paint is not None and plot.paint[0] == plot.paint[1]
    assert not plot.rois
    QTest.mouseClick(plot, Qt.LeftButton, Qt.ControlModifier, px(312))
    assert plot.paint is None and len(plot.rois) == 1
    r = plot.rois[0]
    assert abs(r.left - 288) <= 1 and abs(r.right - 312) <= 1
    assert r.stats.centroid == pytest.approx(300.0, abs=0.05)


def test_mouse_paints_while_in_paint_mode(window):
    plot = _show(window)
    plot.set_marker(600)
    plot.start_paint()
    rect = plot.plot_rect()
    px = lambda idx: QPoint(int(round(rect.left() + (idx + 0.5) / 1024 * rect.width())), int(rect.center().y()))
    x0, x1 = plot.x0, plot.x1
    QTest.mousePress(plot, Qt.LeftButton, Qt.NoModifier, px(580))
    QTest.mouseMove(plot, px(620))
    QTest.mouseRelease(plot, Qt.LeftButton, Qt.NoModifier, px(620))
    assert (plot.x0, plot.x1) == (x0, x1)          # painted, not zoomed
    assert abs(plot.paint[0] - 580) <= 1 and abs(plot.paint[1] - 620) <= 1
    QTest.keyClick(plot, Qt.Key_Return)
    assert plot.paint is None and len(plot.rois) == 1


def test_index_delete_sort_and_delete_all(window, monkeypatch):
    from spectramaster.gui import aptec_roi_ui as ui
    plot = _show(window)
    for a, b in ((285, 315), (590, 610), (100, 120)):
        plot.add_roi(a, b)
    assert [r.left for r in plot.rois] == [100, 285, 590]
    window.act_roi_next.trigger()
    first = plot.roi_index
    window.act_roi_next.trigger()
    assert plot.roi_index == (first + 1) % 3
    window.act_roi_prev.trigger()
    assert plot.roi_index == first
    plot.index_roi(1)
    assert plot.marker == 300
    assert "ROI 2 of 3" in window.statusBar().currentMessage()
    window.act_roi_del_indexed.trigger()
    assert [r.left for r in plot.rois] == [100, 590]
    assert plot.roi_index == 1                      # the next ROI to the right is indexed
    # Sort renumbers by centroid
    plot.rois.reverse()
    window.act_roi_sort.trigger()
    assert [r.left for r in plot.rois] == [100, 590]
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Cancel)
    window.act_roi_del_all.trigger()
    assert len(plot.rois) == 2
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Ok)
    window.act_roi_del_all.trigger()
    assert not plot.rois and plot.roi_index == -1
    # nothing indexed: Edit / Delete Indexed only explain
    window.act_roi_edit.trigger()
    assert "Index an ROI" in window.statusBar().currentMessage()


def test_flag_definitions_and_arabic(window):
    from spectramaster.gui import aptec_roi_ui as ui
    text = ui.flag_definitions_text()
    for f in ("b", "m", "s", "*", "<", "?", ">"):
        assert f in text
    assert "less than the MDA" in text
    window.apply_language("ar", save=False)
    assert window.menu_roi.title().replace("&", "") == "مناطق ROI"
    assert "الخصائص" in window.act_roi_props.text()
    assert window.act_paint_set.text() == "تثبيت"
    assert "تعريف" in ui.flag_definitions_text()


def test_flag_question_mark_below_mda(window):
    plot = _show(window, _spectrum(peaks=((300.0, 1000.0), (700.0, 2.0))))
    weak = plot.add_roi(690, 710)
    strong = plot.add_roi(285, 315)
    assert weak.stats.flags == "?"
    assert strong.stats.flags == ""
    assert window.roi_panel.table.item(1, window.roi_panel.table.columnCount() - 1).text() == "?"

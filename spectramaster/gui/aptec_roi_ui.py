"""Aptec-style ROI menu: Properties (Shift+R), Paint (F3, Ctrl-click), Edit (F4), Delete Indexed
(Del), Delete All..., Sort, Flag Definitions, and the ROI Paint bar (Set, Delete, Cancel,
<< >> F3, >> << F4, <<-- F5, -->> F6), as in Aptec PCMCA/WIN.

The arithmetic is in ``spectramaster.analysis.aptec_roi``; the plot keeps the ROIs, the indexed
ROI and the ROI being painted (``SpectrumPlot.paint``)."""
from __future__ import annotations

import json
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QRadioButton, QSpinBox, QToolBar,
                               QVBoxLayout)

from ..analysis.aptec_roi import CENTROID_RANGES, FLAGS, MAX_END_POINTS, RoiProperties
from .aptec_roi_strings import rtr

SETTINGS_KEY = "aptec/roi_properties"


def _ltr(text: str) -> str:
    """Left-to-right isolate (formulas such as Net * abs(Net) * Chan in Arabic)."""
    return "⁦" + text + "⁩"


# ------------------------------------------------------------------ properties
def load_properties(settings) -> RoiProperties:
    raw = settings.get(SETTINGS_KEY, "") if settings is not None else ""
    try:
        return RoiProperties.from_dict(json.loads(raw)) if raw else RoiProperties()
    except (TypeError, ValueError):
        return RoiProperties()


def save_properties(settings, props: RoiProperties) -> None:
    if settings is not None:
        settings.set(SETTINGS_KEY, json.dumps(props.to_dict()))


class RoiPropertiesDialog(QDialog):
    """Aptec *Setup ROI Properties*."""

    def __init__(self, props: RoiProperties, parent=None):
        super().__init__(parent)
        self.setWindowTitle(rtr("props_title"))
        lay = QVBoxLayout(self)

        g = QGroupBox(rtr("g_bkg"))
        gl = QVBoxLayout(g)
        self.bkg = QComboBox()
        self.bkg.addItem(rtr("bkg_avg"), 0)
        for k in range(1, 6):
            self.bkg.addItem(rtr("bkg_lsq", k=k), k)
        gl.addWidget(self.bkg)
        lay.addWidget(g)

        g = QGroupBox(rtr("g_end"))
        grid = QGridLayout(g)
        self.end_fixed = QRadioButton(rtr("end_fixed"))
        self.end_var = QRadioButton(rtr("end_var"))
        self.end_x = self._spin()
        self.end_lo = self._spin()
        self.end_hi = self._spin()
        grid.addWidget(self.end_fixed, 0, 0)
        grid.addWidget(QLabel(rtr("end_x")), 0, 1)
        grid.addWidget(self.end_x, 0, 2)
        grid.addWidget(self.end_var, 1, 0)
        grid.addWidget(QLabel(rtr("end_x")), 1, 1)
        grid.addWidget(self.end_lo, 1, 2)
        grid.addWidget(QLabel(rtr("end_y")), 1, 3)
        grid.addWidget(self.end_hi, 1, 4)
        self.end_hint = QLabel(rtr("end_hint"))
        self.end_hint.setWordWrap(True)
        self.end_hint.setObjectName("infoLabel")
        grid.addWidget(self.end_hint, 2, 0, 1, 5)
        self.end_group = QButtonGroup(self)
        self.end_group.addButton(self.end_fixed)
        self.end_group.addButton(self.end_var)
        self.end_fixed.toggled.connect(self._sync)
        lay.addWidget(g)

        row = QHBoxLayout()
        g = QGroupBox(rtr("g_cen"))
        gl = QVBoxLayout(g)
        self.cen = {}
        self.cen_group = QButtonGroup(self)
        for key in CENTROID_RANGES:
            b = QRadioButton(rtr("cen_" + key))
            self.cen[key] = b
            self.cen_group.addButton(b)
            gl.addWidget(b)
        row.addWidget(g)
        g = QGroupBox(rtr("g_wgt"))
        gl = QVBoxLayout(g)
        self.wgt = {"net": QRadioButton(_ltr(rtr("wgt_net"))), "squared": QRadioButton(_ltr(rtr("wgt_squared")))}
        self.wgt_group = QButtonGroup(self)
        for b in self.wgt.values():
            self.wgt_group.addButton(b)
            gl.addWidget(b)
        gl.addStretch(1)
        row.addWidget(g)
        lay.addLayout(row)

        g = QGroupBox(rtr("g_conf"))
        fl = QFormLayout(g)
        self.mda_sigma = self._dspin()
        self.err_sigma = self._dspin()
        fl.addRow(rtr("mda_sigma"), self.mda_sigma)
        fl.addRow(rtr("err_sigma"), self.err_sigma)
        lay.addWidget(g)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.defaults_btn = QPushButton(rtr("defaults"))
        bb.addButton(self.defaults_btn, QDialogButtonBox.ResetRole)
        self.defaults_btn.clicked.connect(lambda: self.set_properties(RoiProperties()))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.bkg.currentIndexChanged.connect(self._sync)
        for w in (self.end_x, self.end_lo, self.end_hi):
            w.valueChanged.connect(self._sync)
        self.set_properties(props)

    @staticmethod
    def _spin() -> QSpinBox:
        s = QSpinBox()
        s.setRange(0, MAX_END_POINTS)
        return s

    @staticmethod
    def _dspin() -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(0.1, 10.0)
        s.setDecimals(3)
        s.setSingleStep(0.1)
        return s

    def set_properties(self, p: RoiProperties) -> None:
        self.bkg.setCurrentIndex(int(p.bkg_degree))
        (self.end_var if p.variable_end_points else self.end_fixed).setChecked(True)
        self.end_x.setValue(int(p.end_points))
        self.end_lo.setValue(int(p.end_points_low))
        self.end_hi.setValue(int(p.end_points_high))
        self.cen[p.centroid_range].setChecked(True)
        self.wgt[p.centroid_weight].setChecked(True)
        self.mda_sigma.setValue(float(p.mda_sigma))
        self.err_sigma.setValue(float(p.error_sigma))
        self._sync()

    def properties(self) -> RoiProperties:
        return RoiProperties(
            bkg_degree=int(self.bkg.currentData()), end_points=self.end_x.value(),
            variable_end_points=self.end_var.isChecked(), end_points_low=self.end_lo.value(),
            end_points_high=self.end_hi.value(),
            centroid_range=next(k for k, b in self.cen.items() if b.isChecked()),
            centroid_weight=next(k for k, b in self.wgt.items() if b.isChecked()),
            mda_sigma=self.mda_sigma.value(), error_sigma=self.err_sigma.value()).validate()

    def _sync(self, *_):
        var = self.end_var.isChecked()
        self.end_x.setEnabled(not var)
        self.end_lo.setEnabled(var)
        self.end_hi.setEnabled(var)
        # Aptec's advice: 2nd order or higher only with at least 10 end points
        n = min(self.end_lo.value(), self.end_hi.value()) if var else self.end_x.value()
        warn = int(self.bkg.currentData() or 0) >= 2 and n < 10
        self.end_hint.setStyleSheet("color: #b45309;" if warn else "")


def flag_definitions_text() -> str:
    lines = [rtr("flags_intro"), ""]
    lines += [f"{_ltr(f)}    {rtr('flag_' + f)}" for f in FLAGS]
    lines += ["", rtr("flags_note")]
    return "\n".join(lines)


# ------------------------------------------------------------------ actions
def _need_spectrum(win) -> bool:
    if win.plot.spectrum() is None or not win.plot.num_channels():
        win.statusBar().showMessage(rtr("need_spectrum"), 6000)
        return False
    return True


def _need_index(win) -> bool:
    if win.plot.roi_index < 0:
        win.statusBar().showMessage(rtr("need_index"), 8000)
        return False
    return True


def open_properties(win) -> Optional[RoiProperties]:
    dlg = RoiPropertiesDialog(win.plot.roi_props, win)
    if dlg.exec() != QDialog.Accepted:
        return None
    props = dlg.properties()
    win.plot.set_roi_props(props)
    save_properties(getattr(win, "settings", None), props)
    if hasattr(win, "roi_panel"):
        win.roi_panel.retranslate()
    return props


def paint(win) -> None:
    if _need_spectrum(win):
        win.plot.start_paint()
        win.plot.setFocus()


def edit(win) -> None:
    if _need_spectrum(win) and _need_index(win):
        win.plot.edit_indexed()
        win.plot.setFocus()


def delete_indexed(win) -> None:
    panel = getattr(win, "roi_panel", None)
    if panel is not None and panel.table.hasFocus() and panel.selected_rows():
        panel.delete_selected()
    elif _need_index(win):
        win.plot.delete_indexed()


def delete_all(win, confirm: bool = True) -> bool:
    n = len(win.plot.rois)
    if not n:
        return False
    if confirm:
        ans = QMessageBox.question(win, rtr("del_all_title"), rtr("del_all_q", n=n),
                                   QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel)
        if ans != QMessageBox.Ok:
            return False
    win.plot.clear_rois()
    return True


def show_flags(win) -> None:
    box = QMessageBox(win)
    box.setWindowTitle(rtr("flags_title"))
    box.setIcon(QMessageBox.Information)
    box.setText(flag_definitions_text())
    box.exec()


def _fmt(v, f="{:.1f}") -> str:
    return "-" if v is None else f.format(v)


def _roi_text(win, st, key: str, **kw) -> str:
    return rtr(key, a=st.start_channel, b=st.end_channel, g=f"{st.gross:.0f}", net=_fmt(st.net),
               unc=_fmt(st.net_unc), cen=_fmt(st.centroid, "{:.2f}"), **kw)


def _on_paint_changed(win) -> None:
    plot = win.plot
    painting = plot.paint is not None
    _swap_shortcuts(win, painting)
    win.roi_paint_bar.setVisible(painting)
    win.roi_paint_bar.setEnabled(painting)
    if painting:
        st = plot.paint_stats()
        if st is not None:
            if plot.paint_edit is not None and plot.paint_edit in plot.rois:
                text = _roi_text(win, st, "edit_status", n=plot.rois.index(plot.paint_edit) + 1)
            else:
                text = _roi_text(win, st, "paint_status")
            win.statusBar().showMessage(text)
    else:
        win.statusBar().clearMessage()


def _on_index_changed(win, i: int) -> None:
    plot = win.plot
    if plot.paint is not None or not 0 <= i < len(plot.rois):
        return
    st = plot.rois[i].stats
    if st is not None:
        win.statusBar().showMessage(_roi_text(win, st, "index_status", n=i + 1, total=len(plot.rois)), 15000)


def _swap_shortcuts(win, painting: bool) -> None:
    """While painting, F3-F6 belong to the ROI Paint bar (as in Aptec's Paint menu bar)."""
    saved = win._roi_saved_shortcuts
    if painting and not saved:
        for a in _all_actions(win):
            if a in win._roi_paint_actions:
                continue
            keys = [k for k in a.shortcuts() if k.toString() in ("F3", "F4", "F5", "F6", "Del", "Space")]
            if keys:
                saved[a] = a.shortcuts()
                a.setShortcuts([k for k in a.shortcuts() if k not in keys])
        for a, sc in win._roi_paint_actions.items():
            a.setShortcut(QKeySequence(sc) if sc else QKeySequence())
    elif not painting and saved:
        for a, sc in saved.items():
            a.setShortcuts(sc)
        saved.clear()
        for a in win._roi_paint_actions:
            a.setShortcut(QKeySequence())


def _all_actions(win) -> list:
    seen, out = set(), []

    def walk(acts):
        for a in acts:
            if id(a) in seen:
                continue
            seen.add(id(a))
            out.append(a)
            if a.menu() is not None:
                walk(a.menu().actions())
    walk(win.menuBar().actions())
    walk(win.actions())
    return out


def install_roi_menu(win) -> None:
    """ROI menu before Analyze, the Paint bar and Space / Shift+Space indexing."""
    plot = win.plot
    plot.set_roi_props(load_properties(getattr(win, "settings", None)))
    mb = win.menuBar()
    win.menu_roi = mb.addMenu("")
    analyze = getattr(win, "menu_analyze", None)
    if analyze is not None:
        mb.insertMenu(analyze.menuAction(), win.menu_roi)
    specs = (("act_roi_props", "props", "Shift+R", lambda: open_properties(win)),
             ("act_roi_paint", "paint", "F3", lambda: paint(win)),
             ("act_roi_edit", "edit", "F4", lambda: edit(win)),
             ("act_roi_del_indexed", "del_indexed", "Del", lambda: delete_indexed(win)),
             ("act_roi_del_all", "del_all", "", lambda: delete_all(win)),
             ("act_roi_sort", "sort", "", plot.sort_rois),
             ("act_roi_flags", "flags", "", lambda: show_flags(win)))
    win._roi_actions = []
    for attr, key, sc, fn in specs:
        a = QAction(win)
        a.setObjectName(attr)
        if sc:
            a.setShortcut(QKeySequence(sc))
        a.triggered.connect(lambda _=False, f=fn: f())
        a._aroi_key = key
        setattr(win, attr, a)
        win._roi_actions.append(a)
    m = win.menu_roi
    m.addAction(win.act_roi_props)
    m.addSeparator()
    for name in ("act_roi_paint", "act_roi_edit", "act_roi_del_indexed", "act_roi_del_all"):
        m.addAction(getattr(win, name))
    m.addSeparator()
    m.addAction(win.act_roi_sort)
    m.addAction(win.act_roi_flags)

    # indexing (Aptec: View > Next ROI Space, Prev ROI Shift+Space)
    win.act_roi_next = QAction(win)
    win.act_roi_next.setShortcut(QKeySequence(Qt.Key_Space))
    win.act_roi_next.triggered.connect(plot.index_next)
    win.act_roi_next._aroi_key = "next"
    win.act_roi_prev = QAction(win)
    win.act_roi_prev.setShortcut(QKeySequence("Shift+Space"))
    win.act_roi_prev.triggered.connect(plot.index_prev)
    win.act_roi_prev._aroi_key = "prev"
    win._roi_actions += [win.act_roi_next, win.act_roi_prev]
    view = getattr(win, "menu_view", None)
    if view is not None:
        view.addSeparator()
        view.addAction(win.act_roi_next)
        view.addAction(win.act_roi_prev)
    else:
        win.addAction(win.act_roi_next)
        win.addAction(win.act_roi_prev)

    # ROI Paint bar (shown while painting / editing)
    bar = win.roi_paint_bar = QToolBar(win)
    bar.setObjectName("roiPaintBar")
    bar.setMovable(False)
    win._roi_paint_actions = {}
    paint_specs = (("set", "p_set", "", plot.paint_set),
                   ("delete", "p_delete", "", plot.paint_delete),
                   ("cancel", "p_cancel", "", plot.paint_cancel),
                   ("expand", "<< >>", "F3", lambda: plot.paint_expand(1)),
                   ("shrink", ">> <<", "F4", lambda: plot.paint_expand(-1)),
                   ("left", "<<--", "F5", lambda: plot.paint_shift(-1)),
                   ("right", "-->>", "F6", lambda: plot.paint_shift(1)))
    for key, label, sc, fn in paint_specs:
        a = QAction(win)
        a.setObjectName("act_paint_" + key)
        a.triggered.connect(lambda _=False, f=fn: f())
        a._aroi_label = label
        a._aroi_tip = "tip_p_" + key
        bar.addAction(a)
        win.addAction(a)
        win._roi_paint_actions[a] = sc
        setattr(win, "act_paint_" + key, a)
    win.addToolBar(Qt.BottomToolBarArea, bar)    # just above the status bar and its read-out
    bar.hide()
    win._roi_saved_shortcuts = {}
    plot.paintChanged.connect(lambda: _on_paint_changed(win))
    plot.roiIndexChanged.connect(lambda i: _on_index_changed(win, i))
    retranslate_roi_menu(win)


def retranslate_roi_menu(win) -> None:
    if not hasattr(win, "menu_roi"):
        return
    win.menu_roi.setTitle(rtr("menu_roi"))
    for a in getattr(win, "_roi_actions", []):
        k = a._aroi_key
        a.setText(rtr("act_" + k))
        a.setToolTip(rtr("tip_" + k))
        a.setStatusTip(rtr("tip_" + k))
    # Aptec shows "Paint  F3,Ctrl-Click"
    win.act_roi_paint.setText(rtr("act_paint") + "\tF3, Ctrl-Click")
    win.roi_paint_bar.setWindowTitle(rtr("paint_bar"))
    for a in win._roi_paint_actions:
        label = a._aroi_label
        # LRM on both sides keeps the arrows' direction in the Arabic (RTL) interface
        a.setText(rtr(label) if label.startswith("p_") else "\u200e" + label + "\u200e")
        a.setToolTip(rtr(a._aroi_tip))
    if hasattr(win, "roi_panel"):
        win.roi_panel.retranslate()


__all__ = ["RoiPropertiesDialog", "install_roi_menu", "retranslate_roi_menu", "load_properties",
           "save_properties", "open_properties", "delete_all", "flag_definitions_text", "SETTINGS_KEY"]

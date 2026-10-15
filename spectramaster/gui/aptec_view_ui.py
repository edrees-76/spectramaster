"""Aptec-style View menu: Preferences, Color, QA Control Bar (Ctrl+8), Default Position, Save
Settings on Exit, Vertical / Horizontal Scale, Horizontal Split (H), Vertical Split (V), Next /
Prev ROI, Plot All Points (L), Fill Spc (F), Grid (G), Show Fitted ROIs (K), Fill Normal ROIs
(Shift+F), ROI Data (D), ROI Display (Shift+D), Show ROI Labels (J), Show Channel Marker
(Shift+J), FWHM Percent (%), Connect Points (N), as in Aptec PCMCA/WIN.

SpectraMaster's own view commands (zoom history, go to, overlays, panels) stay available under
*More View Options*; the language stays at the end of the menu."""
from __future__ import annotations

import json
import math
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QKeySequence
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QGridLayout, QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QSplitter, QVBoxLayout)

from . import plot as plotmod
from .aptec_view_strings import vtr
from .plot import FITTED_MODES, ROI_DATA_MODES, Y_MODES, SpectrumPlot

KEY = "aptec_view/"
# display toggles: (action attribute, plot attribute, string key, shortcut, default)
TOGGLES = (
    ("act_v_all_points", "plot_all_points", "all_points", "L", False),   # Aptec: highest channel
    ("act_v_fill_spc", "fill_spectrum", "fill_spc", "F", False),     # Aptec draws points
    ("act_v_grid", "show_grid", "grid", "G", True),
    ("act_v_fill_rois", "fill_rois", "fill_rois", "Shift+F", True),
    ("act_v_roi_display", "show_rois", "roi_display", "Shift+D", True),
    ("act_v_marker", "show_marker", "marker", "Shift+J", True),
    ("act_v_fwhm_pct", "fwhm_percent", "fwhm_pct", "%", False),
    ("act_v_connect", "connect_points", "connect", "N", False),
    ("act_v_auto_zero", "auto_min", "auto_zero", "Z", False),
)


# ------------------------------------------------------------------ split display
class FullSpectrumView(SpectrumPlot):
    """The whole spectrum beside / below the expanded region (Aptec H / V split); a click
    moves the expanded region there."""
    jumpRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMinimumSize(200, 120)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and len(self._y):
            rect = self.plot_rect()
            if rect.contains(ev.position()):
                self.jumpRequested.emit(int(math.floor(self._px_to_x(ev.position().x(), rect))))

    def mouseReleaseEvent(self, ev):
        pass

    def mouseDoubleClickEvent(self, ev):
        pass

    def wheelEvent(self, ev):
        ev.ignore()

    def keyPressEvent(self, ev):
        ev.ignore()


def _sync_split(win) -> None:
    full = getattr(win, "split_plot", None)
    if full is None or not full.isVisible():
        return
    plot = win.plot
    if full.spectrum() is not plot.spectrum():
        full.set_spectrum(plot.spectrum())
    full.rois = plot.rois
    full.peaks = plot.peaks
    for name in ("y_mode", "energy_axis", "show_labels", "fill_spectrum", "plot_all_points", "show_grid",
                 "connect_points", "fill_rois", "show_rois", "fitted_mode"):
        setattr(full, name, getattr(plot, name))
    full.show_marker = False
    full.roi_data = "off"
    full.window_band = (plot.x0, plot.x1) if (plot.x1 - plot.x0) < plot.num_channels() else None
    full._col_cache.clear()
    full.update()


def set_split(win, mode: Optional[str]) -> None:
    """``"h"``: whole spectrum below the expanded region, ``"v"``: beside it, None: off."""
    win.split_mode = mode
    win.act_v_hsplit.setChecked(mode == "h")
    win.act_v_vsplit.setChecked(mode == "v")
    if mode is None:
        win.split_plot.hide()
    else:
        win.plot_splitter.setOrientation(Qt.Vertical if mode == "h" else Qt.Horizontal)
        win.split_plot.show()
        total = win.plot_splitter.height() if mode == "h" else win.plot_splitter.width()
        win.plot_splitter.setSizes([max(1, total * 2 // 3), max(1, total // 3)])
        _sync_split(win)
    win.settings.set(KEY + "split", mode or "")


def _jump(win, idx: int) -> None:
    plot = win.plot
    w = plot.x1 - plot.x0
    if w >= plot.num_channels():          # not expanded: expand around the click (Aptec zoom)
        w = min(64.0, float(plot.num_channels()))
    plot._view_on(idx + 0.5, w)
    plot.set_marker(idx)


# ------------------------------------------------------------------ dialogs
class PreferencesDialog(QDialog):
    """Aptec *View Preferences*: the display options in one place."""

    def __init__(self, win, parent=None):
        super().__init__(parent or win)
        self.win = win
        self.setWindowTitle(vtr("prefs_title"))
        lay = QVBoxLayout(self)
        grid = QGridLayout()
        self.boxes = {}
        items = [(a, k) for a, _p, k, _s, _d in TOGGLES] + [("act_roi_labels_alias", "roi_labels"),
                                                          ("act_v_save_exit", "save_exit")]
        for i, (attr, key) in enumerate(items):
            b = QCheckBox(vtr("act_" + key).replace("&", ""))
            act = self._action(attr)
            b.setChecked(bool(act and act.isChecked()))
            self.boxes[attr] = b
            grid.addWidget(b, i // 2, i % 2)
        lay.addLayout(grid)
        form = QFormLayout()
        self.fitted = QComboBox()
        for m in FITTED_MODES:
            self.fitted.addItem(vtr("fitted_" + m), m)
        self.fitted.setCurrentIndex(FITTED_MODES.index(win.plot.fitted_mode))
        self.data = QComboBox()
        for m, k in zip(ROI_DATA_MODES, ("stats", "bkg", "off")):
            self.data.addItem(vtr("data_" + k), m)
        self.data.setCurrentIndex(ROI_DATA_MODES.index(win.plot.roi_data))
        form.addRow(vtr("prefs_fitted"), self.fitted)
        form.addRow(vtr("prefs_data"), self.data)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _action(self, attr):
        if attr == "act_roi_labels_alias":
            return getattr(self.win, "act_labels", None)
        return getattr(self.win, attr, None)

    def apply(self) -> None:
        for attr, b in self.boxes.items():
            act = self._action(attr)
            if act is not None and act.isChecked() != b.isChecked():
                act.setChecked(b.isChecked())
        set_fitted_mode(self.win, self.fitted.currentData())
        set_roi_data(self.win, self.data.currentData())


class ColorDialog(QDialog):
    """Aptec *View Color*: display colors, default colors or black & white for printing."""

    def __init__(self, colors: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(vtr("color_title"))
        self.colors = dict(colors)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.buttons = {}
        for role in plotmod.COLOR_ROLES:
            b = QPushButton()
            b.setMinimumWidth(120)
            b.clicked.connect(lambda _=False, r=role: self._pick(r))
            self.buttons[role] = b
            form.addRow(vtr("col_" + role), b)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.default_btn = bb.addButton(vtr("col_default"), QDialogButtonBox.ResetRole)
        self.bw_btn = bb.addButton(vtr("col_bw"), QDialogButtonBox.ResetRole)
        self.aptec_btn = bb.addButton(vtr("col_aptec"), QDialogButtonBox.ResetRole)
        self.aptec_btn.clicked.connect(lambda: self.set_colors(plotmod.APTEC_COLORS))
        self.default_btn.clicked.connect(lambda: self.set_colors(plotmod.DEFAULT_COLORS))
        self.bw_btn.clicked.connect(lambda: self.set_colors(plotmod.BW_COLORS))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.set_colors(self.colors)

    def set_colors(self, colors: dict) -> None:
        self.colors = dict(colors)
        for role, b in self.buttons.items():
            c = QColor(self.colors.get(role, plotmod.DEFAULT_COLORS[role]))
            text = "#000000" if c.lightness() > 140 else "#ffffff"
            b.setText("\u200e" + c.name())          # LRM: "#rrggbb" also in Arabic
            b.setStyleSheet(f"background-color: {c.name()}; color: {text};")

    def _pick(self, role: str) -> None:
        c = QColorDialog.getColor(QColor(self.colors.get(role)), self, vtr("col_" + role))
        if c.isValid():
            self.colors[role] = c.name()
            self.set_colors(self.colors)


class QABarDialog(QDialog):
    """Aptec *Setup Quick Access Control Bar* (Ctrl+8): the buttons of the main tool bar."""

    def __init__(self, entries: list, hidden: set, parent=None):
        super().__init__(parent)
        self.setWindowTitle(vtr("qa_title"))
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(vtr("qa_hint")))
        self.list = QListWidget()
        for name, act in entries:
            label = (act.iconText() or act.text()).replace("&", "")   # as on the tool bar
            it = QListWidgetItem(act.icon(), label)
            it.setToolTip(act.toolTip())
            it.setData(Qt.UserRole, name)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked if name in hidden else Qt.Checked)
            self.list.addItem(it)
        self.list.setMinimumSize(320, 260)
        lay.addWidget(self.list)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        all_btn = bb.addButton(vtr("qa_all"), QDialogButtonBox.ResetRole)
        all_btn.clicked.connect(lambda: [self.list.item(i).setCheckState(Qt.Checked)
                                         for i in range(self.list.count())])
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def hidden(self) -> set:
        return {self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())
                if self.list.item(i).checkState() != Qt.Checked}


# ------------------------------------------------------------------ actions
def _plots(win):
    out = [win.plot]
    if getattr(win, "split_plot", None) is not None:
        out.append(win.split_plot)
    return out


def _refresh(win) -> None:
    for p in _plots(win):
        p._col_cache.clear()
        p.update()
    if hasattr(win, "overview"):
        win.overview.update()
    _sync_split(win)


def _set_toggle(win, plot_attr: str, on: bool, key: str) -> None:
    setattr(win.plot, plot_attr, bool(on))
    win.settings.set(KEY + key, bool(on))
    _refresh(win)


def set_fitted_mode(win, mode: str) -> None:
    win.plot.fitted_mode = mode if mode in FITTED_MODES else "show"
    win.settings.set(KEY + "fitted", win.plot.fitted_mode)
    a = win.act_v_fitted
    a.blockSignals(True)
    a.setChecked(win.plot.fitted_mode != "hide")
    a.blockSignals(False)
    a.setText(f"{vtr('act_fitted')} ({vtr('fitted_' + win.plot.fitted_mode)})")
    _refresh(win)


def set_roi_data(win, mode: str) -> None:
    win.plot.roi_data = mode if mode in ROI_DATA_MODES else "stats"
    win.settings.set(KEY + "roi_data", win.plot.roi_data)
    a = win.act_v_roi_data
    a.blockSignals(True)
    a.setChecked(win.plot.roi_data != "off")
    a.blockSignals(False)
    key = {"stats": "stats", "background": "bkg", "off": "off"}[win.plot.roi_data]
    a.setText(f"{vtr('act_roi_data')} ({vtr('data_' + key)})")
    _refresh(win)


def _set_checked(action, on: bool) -> None:
    if action.isChecked() != bool(on):
        action.blockSignals(True)
        action.setChecked(bool(on))
        action.blockSignals(False)


def _cycle(seq, cur, d=1):
    return seq[(seq.index(cur) + d) % len(seq)]


def open_preferences(win) -> bool:
    dlg = PreferencesDialog(win)
    if dlg.exec() != QDialog.Accepted:
        return False
    dlg.apply()
    return True


def load_colors(settings) -> dict:
    try:
        raw = settings.get(KEY + "colors", "")
        return json.loads(raw) if raw else dict(plotmod.DEFAULT_COLORS)
    except (TypeError, ValueError):
        return dict(plotmod.DEFAULT_COLORS)


def apply_colors(win, colors: dict) -> None:
    plotmod.apply_colors(colors)
    win.settings.set(KEY + "colors", json.dumps(plotmod.current_colors()))
    _refresh(win)


def open_colors(win) -> bool:
    dlg = ColorDialog(plotmod.current_colors(), win)
    if dlg.exec() != QDialog.Accepted:
        return False
    apply_colors(win, dlg.colors)
    return True


def _qa_entries(win) -> list:
    """(attribute name, action) of the main tool bar buttons, in their original order."""
    names = {id(v): k for k, v in vars(win).items() if isinstance(v, QAction)}
    return [(names.get(id(a), a.text()), a) for a in win._qa_order if not a.isSeparator()]


def apply_qa_bar(win, hidden: set) -> None:
    tb = win.toolbar
    for a in list(tb.actions()):
        tb.removeAction(a)
    names = dict((id(a), n) for n, a in _qa_entries(win))
    last_sep = True
    for a in win._qa_order:
        if a.isSeparator():
            if not last_sep:
                tb.addAction(a)
                last_sep = True
        elif names.get(id(a)) not in hidden:
            tb.addAction(a)
            last_sep = False
    win.qa_hidden = set(hidden)
    win.settings.set(KEY + "qa_hidden", json.dumps(sorted(hidden)))


def open_qa_bar(win) -> bool:
    dlg = QABarDialog(_qa_entries(win), getattr(win, "qa_hidden", set()), win)
    if dlg.exec() != QDialog.Accepted:
        return False
    apply_qa_bar(win, dlg.hidden())
    return True


def default_position(win) -> None:
    """Aptec Default Position: window size, panels and tool bars as on a first start."""
    state = getattr(win, "_default_state", None)
    if state is not None:
        win.restoreState(state[0])
        win.splitter.restoreState(state[1])
    win.showNormal()
    win.resize(1180, 760)
    scr = win.screen().availableGeometry() if win.screen() is not None else None
    if scr is not None:
        win.move(scr.center() - win.rect().center())


def save_on_exit(win) -> bool:
    return win.settings.get_bool(KEY + "save_exit", True)


def _act(win, attr, key, fn, shortcut=None, checkable=False, context=None, parent_widget=None):
    a = QAction(win)
    a.setObjectName(attr)
    a._aview_key = key
    if shortcut:
        a.setShortcut(QKeySequence(shortcut))
    if context is not None:
        a.setShortcutContext(context)
    if checkable:
        a.setCheckable(True)
        a.toggled.connect(lambda on, f=fn: f(on))
    else:
        a.triggered.connect(lambda _=False, f=fn: f())
    (parent_widget or win).addAction(a)
    setattr(win, attr, a)
    win._view_actions.append(a)
    return a


def install_view_menu(win) -> None:
    """Rebuild the View menu in Aptec's order and move it after Analyze."""
    plot = win.plot
    s = win.settings
    win._view_actions = []
    win.qa_hidden = set()
    # colors first (they also apply to printed graphs)
    plotmod.apply_colors(load_colors(s))

    # ---- split display: the plot and a whole-spectrum view in a splitter
    frame_layout = plot.parentWidget().layout()
    win.plot_splitter = QSplitter(Qt.Vertical)
    win.plot_splitter.setChildrenCollapsible(False)
    frame_layout.replaceWidget(plot, win.plot_splitter)
    win.plot_splitter.addWidget(plot)
    win.split_plot = FullSpectrumView()
    win.plot_splitter.addWidget(win.split_plot)
    win.split_plot.hide()
    win.split_plot.jumpRequested.connect(lambda i: _jump(win, i))
    win.split_mode = None
    for sig in (plot.viewChanged, plot.roisChanged):
        sig.connect(lambda *_: _sync_split(win))

    # ---- actions
    _act(win, "act_v_prefs", "prefs", lambda: open_preferences(win))
    _act(win, "act_v_color", "color", lambda: open_colors(win))
    _act(win, "act_v_qa", "qa", lambda: open_qa_bar(win), "Ctrl+8")
    _act(win, "act_v_default_pos", "default_pos", lambda: default_position(win))
    _act(win, "act_v_save_exit", "save_exit", lambda on: s.set(KEY + "save_exit", bool(on)), checkable=True)
    win.act_v_save_exit.setChecked(save_on_exit(win))
    _act(win, "act_v_hsplit", "hsplit", lambda on: set_split(win, "h" if on else None), "H", checkable=True)
    _act(win, "act_v_vsplit", "vsplit", lambda on: set_split(win, "v" if on else None), "V", checkable=True)
    for attr, pattr, key, sc, default in TOGGLES:
        on = s.get_bool(KEY + key, default)
        setattr(plot, pattr, on)
        _act(win, attr, key, lambda v, pa=pattr, k=key: _set_toggle(win, pa, v, k), sc, checkable=True)
        getattr(win, attr).setChecked(on)
    _act(win, "act_v_fitted", "fitted",
         lambda: set_fitted_mode(win, _cycle(FITTED_MODES, plot.fitted_mode)), "K")
    win.act_v_fitted.setCheckable(True)
    _act(win, "act_v_roi_data", "roi_data",
         lambda: set_roi_data(win, _cycle(ROI_DATA_MODES, plot.roi_data)), "D")
    win.act_v_roi_data.setCheckable(True)
    # vertical scale
    _act(win, "act_v_next_scale", "next_scale", lambda: win.set_y_mode(_cycle(Y_MODES, plot.y_mode)), "S")
    _act(win, "act_v_prev_scale", "prev_scale", lambda: win.set_y_mode(_cycle(Y_MODES, plot.y_mode, -1)),
         "Shift+S")
    pw, ctx = plot, Qt.WidgetShortcut        # navigation keys act on the plot only
    _act(win, "act_v_raise_spc", "raise_spc", lambda: plot.zoom_y(0.8), "Up", context=ctx, parent_widget=pw)
    _act(win, "act_v_lower_spc", "lower_spc", lambda: plot.zoom_y(1.25), "Down", context=ctx, parent_widget=pw)
    _act(win, "act_v_raise_base", "raise_base", lambda: plot.shift_base(1), "Shift+Up", context=ctx,
         parent_widget=pw)
    _act(win, "act_v_lower_base", "lower_base", lambda: plot.shift_base(-1), "Shift+Down", context=ctx,
         parent_widget=pw)
    # horizontal scale
    _act(win, "act_v_x_channel", "x_channel", lambda: win.act_energy.setChecked(False), "C")
    _act(win, "act_v_x_energy", "x_energy", lambda: win.act_energy.setChecked(True), "E")
    grp = QActionGroup(win)
    for a in (win.act_v_x_channel, win.act_v_x_energy):
        a.setCheckable(True)
        grp.addAction(a)
    nav = (("act_v_zoom", "zoom", plot.zoom_cycle, Qt.KeypadModifier | Qt.Key_5),
           ("act_v_expand", "expand", lambda: plot.expand(0.5), Qt.KeypadModifier | Qt.Key_Plus),
           ("act_v_contract", "contract", lambda: plot.expand(2.0), Qt.KeypadModifier | Qt.Key_Minus),
           ("act_v_max_expand", "max_expand", plot.max_expand, Qt.ShiftModifier | Qt.KeypadModifier | Qt.Key_Plus),
           ("act_v_max_contract", "max_contract", plot.reset_view,
            Qt.ShiftModifier | Qt.KeypadModifier | Qt.Key_Minus),
           ("act_v_mk_left", "mk_left", lambda: plot.marker_step(-1), Qt.Key_Left),
           ("act_v_mk_right", "mk_right", lambda: plot.marker_step(1), Qt.Key_Right),
           ("act_v_mk_left_edge", "mk_left_edge", lambda: plot.marker_to_edge(False), Qt.Key_Home),
           ("act_v_mk_right_edge", "mk_right_edge", lambda: plot.marker_to_edge(True), Qt.Key_End),
           ("act_v_mk_far_left", "mk_far_left", lambda: plot.marker_far(False), Qt.ShiftModifier | Qt.Key_Home),
           ("act_v_mk_far_right", "mk_far_right", lambda: plot.marker_far(True), Qt.ShiftModifier | Qt.Key_End),
           ("act_v_spc_left", "spc_left", lambda: plot.shift_window(-1), Qt.Key_PageDown),
           ("act_v_spc_right", "spc_right", lambda: plot.shift_window(1), Qt.Key_PageUp),
           ("act_v_spc_far_left", "spc_far_left", lambda: plot.shift_window(-1, True),
            Qt.ShiftModifier | Qt.Key_PageDown),
           ("act_v_spc_far_right", "spc_far_right", lambda: plot.shift_window(1, True),
            Qt.ShiftModifier | Qt.Key_PageUp))
    for attr, key, fn, sc in nav:
        a = _act(win, attr, key, fn, context=ctx, parent_widget=pw)
        a.setShortcut(QKeySequence(sc))
    # Aptec keys on existing commands
    win.act_auto_y.setShortcuts([QKeySequence("A"), QKeySequence("Ctrl+Shift+Y")])
    # Show ROI Labels (J): the identification labels, same setting as Analyze > Peak Labels
    _act(win, "act_v_roi_labels", "roi_labels", lambda on: win.act_labels.setChecked(on), "J", checkable=True)
    win.act_v_roi_labels.setChecked(win.act_labels.isChecked())
    win.act_labels.toggled.connect(lambda on: _set_checked(win.act_v_roi_labels, on))
    win.act_energy.toggled.connect(lambda on: _sync_axis(win))
    _sync_axis(win)

    set_fitted_mode(win, s.get(KEY + "fitted", "show"))
    set_roi_data(win, s.get(KEY + "roi_data", "stats"))
    win._qa_order = list(win.toolbar.actions())
    try:
        hidden = set(json.loads(s.get(KEY + "qa_hidden", "") or "[]"))
    except (TypeError, ValueError):
        hidden = set()
    if hidden:
        apply_qa_bar(win, hidden)

    _build_menu(win)
    split = s.get(KEY + "split", "")
    if split in ("h", "v"):
        set_split(win, split)
    retranslate_view_menu(win)


def _sync_axis(win) -> None:
    on = win.act_energy.isChecked() and win.plot.has_energy()
    win.act_v_x_energy.setChecked(on)
    win.act_v_x_channel.setChecked(not on)


def _build_menu(win) -> None:
    m = win.menu_view
    keep_end = getattr(win, "menu_lang", None)
    old = [a for a in m.actions()]
    for a in old:
        m.removeAction(a)
    mb = win.menuBar()
    # View after Analyze (Aptec: ... ROI, Analyze, View, Help)
    mb.removeAction(m.menuAction())
    after = getattr(win, "menu_analyze", None)
    acts = mb.actions()
    idx = acts.index(after.menuAction()) + 1 if after is not None and after.menuAction() in acts else len(acts)
    if idx < len(acts):
        mb.insertMenu(acts[idx], m)
    else:
        mb.addMenu(m)

    for a in (win.act_v_prefs, win.act_v_color, win.act_v_qa, win.act_v_default_pos, win.act_v_save_exit):
        m.addAction(a)
    m.addSeparator()
    win.menu_v_vscale = m.addMenu("")
    vs = win.menu_v_vscale
    vs.addAction(win.act_auto_y)
    vs.addAction(win.act_v_auto_zero)
    vs.addAction(win.act_v_next_scale)
    vs.addAction(win.act_v_prev_scale)
    vs.addSeparator()
    for a in win.act_y.values():
        vs.addAction(a)
    vs.addSeparator()
    for name in ("act_v_raise_spc", "act_v_lower_spc", "act_v_raise_base", "act_v_lower_base"):
        vs.addAction(getattr(win, name))
    win.menu_v_hscale = m.addMenu("")
    hs = win.menu_v_hscale
    hs.addAction(win.act_v_x_channel)
    hs.addAction(win.act_v_x_energy)
    hs.addSeparator()
    for name in ("act_v_zoom", "act_v_expand", "act_v_contract", "act_v_max_expand", "act_v_max_contract"):
        hs.addAction(getattr(win, name))
    hs.addSeparator()
    for name in ("act_v_mk_left", "act_v_mk_left_edge", "act_v_mk_far_left", "act_v_spc_left",
                 "act_v_spc_far_left", "act_v_mk_right", "act_v_mk_right_edge", "act_v_mk_far_right",
                 "act_v_spc_right", "act_v_spc_far_right"):
        hs.addAction(getattr(win, name))
    m.addAction(win.act_v_hsplit)
    m.addAction(win.act_v_vsplit)
    m.addSeparator()
    for name in ("act_roi_next", "act_roi_prev"):
        if hasattr(win, name):
            m.addAction(getattr(win, name))
    m.addSeparator()
    for name in ("act_v_all_points", "act_v_fill_spc", "act_v_grid", "act_v_fitted", "act_v_fill_rois",
                 "act_v_roi_data", "act_v_roi_display"):
        m.addAction(getattr(win, name))
    for name in ("act_v_roi_labels", "act_v_marker", "act_v_fwhm_pct", "act_v_connect"):
        m.addAction(getattr(win, name))
    m.addSeparator()
    # SpectraMaster's own view commands
    win.menu_v_more = m.addMenu("")
    skip = {id(x) for x in (win.act_auto_y, getattr(win, "act_roi_next", None),
                            getattr(win, "act_roi_prev", None))}
    if keep_end is not None:
        skip.add(id(keep_end.menuAction()))
    last_sep = True
    for a in old:
        if id(a) in skip:
            continue
        if a.isSeparator():
            if not last_sep:
                win.menu_v_more.addSeparator()
                last_sep = True
            continue
        win.menu_v_more.addAction(a)
        last_sep = False
    if keep_end is not None:
        m.addSeparator()
        m.addMenu(keep_end)


def retranslate_view_menu(win) -> None:
    if not hasattr(win, "menu_v_more"):
        return
    win.menu_view.setTitle(vtr("menu_view"))
    win.menu_v_vscale.setTitle(vtr("menu_vscale"))
    win.menu_v_hscale.setTitle(vtr("menu_hscale"))
    win.menu_v_more.setTitle(vtr("menu_more"))
    for a in win._view_actions:
        k = a._aview_key
        a.setText(vtr("act_" + k))
        tip = "tip_" + k
        from . import i18n
        if ("aview_" + tip) in i18n.STRINGS.get("en", {}):
            a.setToolTip(vtr(tip))
            a.setStatusTip(vtr(tip))
    set_fitted_mode(win, win.plot.fitted_mode)
    set_roi_data(win, win.plot.roi_data)


__all__ = ["install_view_menu", "retranslate_view_menu", "PreferencesDialog", "ColorDialog", "QABarDialog",
           "FullSpectrumView", "set_split", "set_fitted_mode", "set_roi_data", "apply_colors",
           "apply_qa_bar", "default_position", "save_on_exit", "TOGGLES"]

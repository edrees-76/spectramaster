"""Aptec *Analyze* spectrum operations (lower part of Aptec's Analyze menu): Add Constant,
Normalize, Shift, Smooth, Reduce Channels, Derivative, Compare, Exchange, Combine, Strip and
Position, plus Undo (Ctrl+Z) and Reload Original.

The calculations are in :mod:`spectramaster.tools.spectrum_ops` (no Qt).  Every operation works
on the spectrum on the screen: the file is never changed (File > Save As writes the result).
The compare spectrum is an overlay of the plot marked ``compare`` (Ctrl+Up / Ctrl+Down move it).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
                               QLineEdit, QMessageBox, QRadioButton, QSpinBox, QVBoxLayout)

from ..tools import spectrum_ops as ops
from .aptec_ops_strings import otr

UNDO_DEPTH = 20
COMPARE_COLOR_LIGHT = "#c2185b"
COMPARE_COLOR_DARK = "#ff40ff"


def _rtl(w) -> None:
    from . import i18n
    w.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl(i18n.language()) else Qt.LeftToRight)


def _ltr(text) -> str:
    return "\u2066" + str(text) + "\u2069"


def _displayed(win):
    spectra = getattr(win, "_spectra", None)
    i = getattr(win, "_index", -1)
    if spectra is None or not 0 <= i < len(spectra):
        return None
    return spectra[i]


def _need(win):
    spec = _displayed(win)
    if spec is None:
        win.statusBar().showMessage(otr("need_spectrum"), 6000)
    return spec


def _buttons(dlg: QDialog, lay) -> QDialogButtonBox:
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    return bb


def _hint(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    return lab


def _fmt_time(t) -> str:
    return _ltr(f"{t:.6g} s") if t else otr("unknown")


# ===================================================================== dialogs
class AddConstantDialog(QDialog):
    def __init__(self, parent=None, value: int = 0):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(otr("const_title"))
        lay = QVBoxLayout(self)
        lay.addWidget(_hint(otr("const_hint")))
        form = QFormLayout()
        self.value = QSpinBox()
        self.value.setRange(-2_000_000_000, 2_000_000_000)
        self.value.setValue(int(value))
        self.value.setLayoutDirection(Qt.LeftToRight)
        form.addRow(otr("const_value"), self.value)
        lay.addLayout(form)
        _buttons(self, lay)


class NormalizeDialog(QDialog):
    """Factor typed with up to 16 significant figures (Aptec 6.31); with a compare spectrum the
    live time matching multiplier is the default."""

    def __init__(self, parent=None, ratio: Optional[float] = None):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(otr("norm_title"))
        lay = QVBoxLayout(self)
        lay.addWidget(_hint(otr("norm_hint")))
        lay.addWidget(_hint(otr("norm_ratio", r=_ltr(f"{ratio:.16g}")) if ratio else otr("norm_no_ratio")))
        form = QFormLayout()
        self.factor = QLineEdit(f"{ratio:.16g}" if ratio else "1")
        self.factor.setLayoutDirection(Qt.LeftToRight)
        form.addRow(otr("norm_factor"), self.factor)
        lay.addLayout(form)
        self.error = QLabel("")
        self.error.setStyleSheet("color: #c62828")
        lay.addWidget(self.error)
        self.bb = _buttons(self, lay)
        self.factor.textChanged.connect(self._check)
        self._check()

    def value(self) -> Optional[float]:
        try:
            v = float(self.factor.text().strip().replace(",", "."))
        except ValueError:
            return None
        return v if math.isfinite(v) and abs(v) > 0.0 else None

    def _check(self) -> None:
        ok = self.value() is not None
        self.error.setText("" if ok else otr("norm_bad"))
        self.bb.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)


class ShiftDialog(QDialog):
    def __init__(self, parent=None, n_channels: int = 4096):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(otr("shift_title"))
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.channels = QSpinBox()
        self.channels.setRange(0, max(1, n_channels - 1))
        self.channels.setValue(1)
        self.channels.setLayoutDirection(Qt.LeftToRight)
        form.addRow(otr("shift_channels"), self.channels)
        lay.addLayout(form)
        self.left = QRadioButton(otr("shift_left"))
        self.right = QRadioButton(otr("shift_right"))
        self.right.setChecked(True)
        lay.addWidget(self.left)
        lay.addWidget(self.right)
        lay.addWidget(_hint(otr("shift_hint")))
        _buttons(self, lay)

    def value(self) -> int:
        n = self.channels.value()
        return -n if self.left.isChecked() else n


class SmoothDialog(QDialog):
    def __init__(self, parent=None, points: int = 5):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(otr("smooth_title"))
        lay = QVBoxLayout(self)
        self.group = QButtonGroup(self)
        for n in ops.SMOOTH_POINTS:
            b = QRadioButton(otr("smooth_points", n=n))
            b.setChecked(n == points)
            self.group.addButton(b, n)
            lay.addWidget(b)
        lay.addWidget(_hint(otr("smooth_hint")))
        _buttons(self, lay)

    def value(self) -> int:
        return self.group.checkedId()


class ReduceDialog(QDialog):
    def __init__(self, parent=None, n_channels: int = 4096):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(otr("reduce_title"))
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.factor = QComboBox()
        f = 2
        while f < n_channels and f <= 64:
            self.factor.addItem(otr("reduce_item", f=f, n=n_channels, m=-(-n_channels // f)), f)
            f *= 2
        form.addRow(otr("reduce_by"), self.factor)
        lay.addLayout(form)
        lay.addWidget(_hint(otr("reduce_hint")))
        _buttons(self, lay)

    def value(self) -> int:
        return int(self.factor.currentData() or 2)


class DerivativeDialog(QDialog):
    """Aptec shows the current choice, "Original data" when no derivative was taken."""

    def __init__(self, parent=None, order: int = 0, pre_smooth: int = 5):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(otr("deriv_title"))
        lay = QVBoxLayout(self)
        self.group = QButtonGroup(self)
        for k, key in ((0, "deriv_original"), (1, "deriv_1"), (2, "deriv_2"), (3, "deriv_3")):
            b = QRadioButton(otr(key))
            b.setChecked(k == order)
            self.group.addButton(b, k)
            lay.addWidget(b)
        form = QFormLayout()
        self.smooth = QComboBox()
        self.smooth.addItem(otr("deriv_none"), 0)
        for n in ops.SMOOTH_POINTS:
            self.smooth.addItem(str(n), n)
        self.smooth.setCurrentIndex(max(0, self.smooth.findData(pre_smooth)))
        form.addRow(otr("deriv_smooth"), self.smooth)
        lay.addLayout(form)
        lay.addWidget(_hint(otr("deriv_hint")))
        _buttons(self, lay)

    def value(self) -> tuple[int, int]:
        return self.group.checkedId(), int(self.smooth.currentData() or 0)


class PositionDialog(QDialog):
    def __init__(self, parent=None, offset: int = 0):
        super().__init__(parent)
        _rtl(self)
        self.setWindowTitle(otr("pos_title"))
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.offset = QSpinBox()
        self.offset.setRange(-5000, 5000)
        self.offset.setValue(int(offset))
        self.offset.setLayoutDirection(Qt.LeftToRight)
        form.addRow(otr("pos_offset"), self.offset)
        lay.addLayout(form)
        _buttons(self, lay)


# ===================================================================== controller
class SpectrumOps:
    """State of the spectrum operations of one main window: undo stack, derivative base and the
    compare spectrum.  The ``ask_*`` / ``confirm`` hooks are replaced by tests."""

    def __init__(self, win):
        self.win = win
        self.undo_stack: list[tuple] = []          # (index, spectrum, roi bounds, deriv base, order, label)
        self.deriv_base = None                     # spectrum before the derivative was taken
        self.deriv_order = 0
        self.deriv_smooth = 5
        self.last_constant = 0
        self.last_smooth = 5

    # ---------------------------------------------------------------- compare spectrum
    @property
    def compare(self):
        ov = self.win.plot.compare_overlay()
        return ov.spec if ov is not None else None

    def set_compare(self, spec, label: str = "") -> None:
        plot = self.win.plot
        old = plot.compare_overlay()
        offset = old.offset_px if old is not None else 0.0
        if old is not None:
            plot.remove_overlay(plot.overlays.index(old))
        if spec is None:
            return
        dark = plot.palette().color(plot.backgroundRole()).lightness() < 128
        from . import plot as plot_mod
        dark = dark or plot_mod.C_BG.lightness() < 128
        ov = plot.add_overlay(spec, otr("compare_label", name=label or ops._name(spec)),
                              QColor(COMPARE_COLOR_DARK if dark else COMPARE_COLOR_LIGHT))
        ov.compare = True
        ov.offset_px = offset
        plot.update()

    # ---------------------------------------------------------------- apply / undo
    def apply(self, new, label: str, roi_map: Optional[Callable] = None, view_div: int = 1,
              deriv: bool = False) -> bool:
        win = self.win
        old = _displayed(win)
        if old is None or new is None:
            return False
        plot = win.plot
        bounds = [(r.left, r.right) for r in plot.rois]
        x0, x1, marker = plot.x0, plot.x1, plot.marker
        self.undo_stack.append((win._index, old, bounds, self.deriv_base, self.deriv_order, label))
        del self.undo_stack[:-UNDO_DEPTH]
        if not deriv:
            self.deriv_base, self.deriv_order = None, 0
        self._show(new, [roi_map(*b) for b in bounds] if roi_map else bounds, x0 / view_div, x1 / view_div,
                   None if marker is None else marker // view_div)
        text = otr("done", what=label)
        if not ops.is_poisson(new):
            text += otr("not_poisson")
        win.statusBar().showMessage(text, 15000)
        sync_actions(win)
        return True

    def _show(self, spec, bounds, x0, x1, marker) -> None:
        from .aptec_calibration_ui import apply_to_display
        win = self.win
        plot = win.plot
        apply_to_display(win, spec)
        n = plot.num_channels()
        plot.rois.clear()
        plot.indexed_roi = None
        for lo, hi in bounds:
            if 0 <= lo <= hi < n:
                plot.rois.append(_roi(lo, hi))
        plot.rois.sort(key=lambda r: r.left)
        plot._recompute_rois()
        plot.roisChanged.emit()
        if x1 > x0:
            plot.set_view(max(0.0, x0), min(float(n), x1), None)
        if marker is not None and 0 <= marker < n:
            plot.set_marker(marker)
        plot.update()

    def reset(self) -> None:
        """Another file is displayed: nothing left to undo."""
        self.undo_stack.clear()
        self.deriv_base, self.deriv_order = None, 0
        sync_actions(self.win)

    def undo(self) -> bool:
        if not self.undo_stack or self.undo_stack[-1][0] != self.win._index:
            self.win.statusBar().showMessage(otr("nothing_undo"), 6000)
            return False
        _i, spec, bounds, base, order, label = self.undo_stack.pop()
        plot = self.win.plot
        cur = _displayed(self.win)
        div = 1
        if cur is not None and cur.num_channels and spec.num_channels > cur.num_channels:
            div = spec.num_channels // cur.num_channels          # undo of a reduction: zoom back out
        x0, x1 = plot.x0 * div, plot.x1 * div
        self.deriv_base, self.deriv_order = base, order
        self._show(spec, bounds, x0, x1, None if plot.marker is None else plot.marker * div)
        self.win.statusBar().showMessage(otr("undone", what=label), 8000)
        sync_actions(self.win)
        return True

    def reload_original(self) -> bool:
        win = self.win
        path = getattr(win, "_path", None)
        if path is None:
            win.statusBar().showMessage(otr("no_file"), 6000)
            return False
        index = getattr(win, "_index", 0)
        compare = self.compare
        if not win.load_file(path):
            return False
        if 0 < index < len(win._spectra):
            win.show_index(index)
        self.undo_stack.clear()
        self.deriv_base, self.deriv_order = None, 0
        if compare is not None:
            self.set_compare(compare)
        win.statusBar().showMessage(otr("reloaded"), 8000)
        sync_actions(win)
        return True

    # ---------------------------------------------------------------- the operations
    def _run(self, fn, *args):
        try:
            return fn(*args)
        except (ValueError, ops.SpectrumMathError) as exc:
            self.message(otr("err", msg=str(exc)))
            return None

    def add_constant(self, value: Optional[int] = None) -> bool:
        spec = _need(self.win)
        if spec is None:
            return False
        if value is None:
            d = AddConstantDialog(self.win, self.last_constant)
            if d.exec() != QDialog.Accepted:
                return False
            value = d.value.value()
        self.last_constant = int(value)
        new = self._run(ops.add_constant, spec, int(value))
        return new is not None and self.apply(new, f"{otr('const_title')} {int(value):+d}")

    def normalize(self, factor: Optional[float] = None) -> bool:
        spec = _need(self.win)
        if spec is None:
            return False
        if factor is None:
            ratio = ops.live_time_ratio(spec, self.compare) if self.compare is not None else None
            d = NormalizeDialog(self.win, ratio)
            if d.exec() != QDialog.Accepted or d.value() is None:
                return False
            factor = d.value()
        new = self._run(ops.normalize, spec, float(factor))
        return new is not None and self.apply(new, f"{otr('norm_title')} ×{float(factor):.10g}")

    def shift(self, channels: Optional[int] = None) -> bool:
        spec = _need(self.win)
        if spec is None:
            return False
        if channels is None:
            d = ShiftDialog(self.win, spec.num_channels)
            if d.exec() != QDialog.Accepted:
                return False
            channels = d.value()
        if not channels:
            return False
        new = self._run(ops.shift, spec, int(channels))
        return new is not None and self.apply(new, f"{otr('shift_title')} {int(channels):+d}")

    def smooth(self, points: Optional[int] = None) -> bool:
        spec = _need(self.win)
        if spec is None:
            return False
        if points is None:
            d = SmoothDialog(self.win, self.last_smooth)
            if d.exec() != QDialog.Accepted:
                return False
            points = d.value()
        self.last_smooth = int(points)
        new = self._run(ops.smooth, spec, int(points))
        return new is not None and self.apply(new, f"{otr('smooth_title')} {otr('smooth_points', n=points)}")

    def reduce(self, factor: Optional[int] = None) -> bool:
        spec = _need(self.win)
        if spec is None:
            return False
        if factor is None:
            d = ReduceDialog(self.win, spec.num_channels)
            if d.exec() != QDialog.Accepted:
                return False
            factor = d.value()
        f = int(factor)
        new = self._run(ops.reduce_channels, spec, f)
        if new is None:
            return False
        fc = spec.first_channel
        return self.apply(new, f"{otr('reduce_title')} {f}:1",
                          roi_map=lambda lo, hi: ops.reduce_roi(lo, hi, f, fc), view_div=f)

    def derivative(self, order: Optional[int] = None, pre_smooth: Optional[int] = None) -> bool:
        spec = _need(self.win)
        if spec is None:
            return False
        if order is None:
            d = DerivativeDialog(self.win, self.deriv_order, self.deriv_smooth)
            if d.exec() != QDialog.Accepted:
                return False
            order, pre_smooth = d.value()
        if pre_smooth is not None:
            self.deriv_smooth = int(pre_smooth)
        base = self.deriv_base if self.deriv_base is not None else spec
        if order == 0:                                     # back to the original data
            if self.deriv_base is None:
                return False
            ok = self.apply(base, otr("deriv_original"))
            return ok
        new = self._run(ops.derivative, base, int(order), self.deriv_smooth)
        if new is None:
            return False
        self.deriv_base, self.deriv_order = base, int(order)
        return self.apply(new, otr("deriv_%d" % order).split(" (")[0], deriv=True)

    def toggle_compare(self, path: Optional[str] = None) -> bool:
        win = self.win
        if _need(win) is None:
            return False
        if self.compare is not None and path is None:
            self.set_compare(None)
            win.statusBar().showMessage(otr("compare_off"), 6000)
            sync_actions(win)
            return True
        if path is None:
            path = win._ask_open_file(otr("fd_compare"), "overlay")
            if not path:
                return False
        from ..convert import read_spectra
        p = Path(path)
        try:
            spectra, _fmt = read_spectra(p, win.settings.input_format())
        except Exception as exc:
            self.message(otr("err", msg=str(exc) or type(exc).__name__))
            return False
        if not spectra:
            return False
        win.settings.set_folder("overlay", p)
        s = spectra[0]
        if not s.source_path:
            s.source_path = str(p)
        self.set_compare(s, p.name)
        win.statusBar().showMessage(otr("compare_on", name=p.name), 10000)
        sync_actions(win)
        return True

    def exchange(self) -> bool:
        spec = _need(self.win)
        cmp_ = self.compare
        if spec is None:
            return False
        if cmp_ is None:
            self.message(otr("need_compare"))
            return False
        self.set_compare(spec)
        return self.apply(cmp_, otr("act_exchange").replace("&", "").rstrip("."))

    def _pair(self, op_key: str, fn, sign: str, confirm: bool) -> bool:
        spec = _need(self.win)
        if spec is None:
            return False
        cmp_ = self.compare
        if cmp_ is None:
            self.message(otr("need_compare"))
            return False
        if confirm:
            text = otr("pair_text", op=otr(op_key), sign=sign, a=ops._name(spec), la=_fmt_time(spec.live_time),
                       na=spec.num_channels, b=ops._name(cmp_), lb=_fmt_time(cmp_.live_time), nb=cmp_.num_channels)
            if spec.live_time and cmp_.live_time and abs(spec.live_time - cmp_.live_time) > 1e-9 * spec.live_time:
                text += otr("pair_warn_lt")
            if spec.num_channels == cmp_.num_channels and not ops.same_calibration(spec, cmp_):
                text += otr("pair_warn_cal")
            if not self.confirm(otr(op_key), text):
                return False
        new = self._run(fn, spec, cmp_)
        return new is not None and self.apply(new, otr(op_key))

    def combine(self, confirm: bool = True) -> bool:
        return self._pair("op_combine", ops.combine, "+", confirm)

    def strip(self, confirm: bool = True) -> bool:
        return self._pair("op_strip", ops.strip, "−", confirm)

    def position(self, offset: Optional[int] = None) -> bool:
        plot = self.win.plot
        ov = plot.compare_overlay()
        if ov is None:
            self.message(otr("need_compare"))
            return False
        if offset is None:
            d = PositionDialog(self.win, int(ov.offset_px))
            if d.exec() != QDialog.Accepted:
                return False
            offset = d.offset.value()
        plot.move_compare(int(offset) - ov.offset_px)
        return True

    # ---------------------------------------------------------------- hooks
    def message(self, text: str) -> None:
        QMessageBox.warning(self.win, otr("err", msg="").rstrip(": "), text)

    def confirm(self, title: str, text: str) -> bool:
        box = QMessageBox(QMessageBox.Question, title, text, QMessageBox.Ok | QMessageBox.Cancel, self.win)
        box.setDefaultButton(QMessageBox.Cancel)
        return box.exec() == QMessageBox.Ok


def _roi(lo: int, hi: int):
    from .plot import Roi
    return Roi(int(lo), int(hi))


# ===================================================================== menu
_ITEMS = (("act_o_add_constant", "add_constant", "add_constant", None),
          ("act_o_normalize", "normalize", "normalize", None),
          ("act_o_shift", "shift", "shift", None),
          ("act_o_smooth", "smooth", "smooth", None),
          ("act_o_reduce", "reduce", "reduce", None),
          ("act_o_derivative", "derivative", "derivative", None),
          None,
          ("act_o_compare", "compare", "toggle_compare", None),
          ("act_o_exchange", "exchange", "exchange", None),
          ("act_o_combine", "combine", "combine", None),
          ("act_o_strip", "strip", "strip", None),
          ("act_o_position", "position", "position", None),
          None,
          ("act_o_undo", "undo", "undo", "Ctrl+Z"),
          ("act_o_original", "original", "reload_original", None))


def install_ops_menu(win) -> None:
    """Spectrum operations at the end of the Analyze menu (Aptec's order)."""
    win.spectrum_ops = ctl = SpectrumOps(win)
    win._ops_actions = []
    menu = win.menu_analyze
    menu.addSeparator()
    for item in _ITEMS:
        if item is None:
            menu.addSeparator()
            continue
        attr, key, method, shortcut = item
        a = QAction(win)
        a.setObjectName(attr)
        a._aops_key = key
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(lambda _=False, m=method: getattr(ctl, m)())
        win.addAction(a)
        menu.addAction(a)
        setattr(win, attr, a)
        win._ops_actions.append(a)
    win.act_o_compare.setCheckable(True)
    win.plot.overlaysChanged.connect(lambda: sync_actions(win))
    retranslate_ops_menu(win)
    sync_actions(win)


def sync_actions(win) -> None:
    if not hasattr(win, "spectrum_ops"):
        return
    ctl = win.spectrum_ops
    has = _displayed(win) is not None
    cmp_ = ctl.compare is not None
    for a in win._ops_actions:
        a.setEnabled(has)
    for name in ("act_o_exchange", "act_o_combine", "act_o_strip", "act_o_position"):
        getattr(win, name).setEnabled(has and cmp_)
    win.act_o_compare.setChecked(cmp_)
    win.act_o_undo.setEnabled(bool(ctl.undo_stack) and ctl.undo_stack[-1][0] == getattr(win, "_index", -1))
    win.act_o_original.setEnabled(has and getattr(win, "_path", None) is not None)


def retranslate_ops_menu(win) -> None:
    if not hasattr(win, "_ops_actions"):
        return
    for a in win._ops_actions:
        a.setText(otr("act_" + a._aops_key))
        a.setToolTip(otr("tip_" + a._aops_key))
        a.setStatusTip(otr("tip_" + a._aops_key))


__all__ = ["install_ops_menu", "retranslate_ops_menu", "sync_actions", "SpectrumOps", "AddConstantDialog",
           "NormalizeDialog", "ShiftDialog", "SmoothDialog", "ReduceDialog", "DerivativeDialog", "PositionDialog"]

"""Fast spectrum plot drawn directly with QPainter.

Interaction (see ``SHORTCUTS`` in i18n for the user-facing list)
  * mouse move              : cursor line + channel / energy / counts read-out
  * left drag (horizontal)  : zoom to the dragged channel range (Y auto)
  * left drag (box)         : rubber-band zoom of X and Y
  * Ctrl + left drag        : define a region of interest (ROI)
  * Ctrl + click            : Aptec quick paint -- left side, then right side of a new ROI
                              (in Paint mode: Set)
  * left click              : move the channel marker (``markerMoved``)
  * double-click            : index the next ROI to the right (Shift: to the left); full
                              spectrum when there are no ROIs
  * Left / Right, Home / End : move the channel marker / to the window edge (Aptec)
  * PgDn / PgUp             : shift the spectrum window (Shift: all the way)
  * NumPad 5, +, -          : zoom 64 / 16 / all channels, expand, contract around the marker
  * Shift + left drag, right/middle drag : pan (Y too when Y is zoomed)
  * wheel                   : zoom X around the cursor
  * Ctrl + wheel / Up, Down : zoom Y
  * Shift + wheel           : pan
  * + / -                   : zoom in / out
  * Backspace, Alt+Left / Alt+Right : zoom history back / forward
  * Esc, Ctrl+0             : full spectrum
  * right click             : context menu (``contextRequested``)

Large spectra are decimated to one min/max column per pixel (numpy), so
64k-channel files repaint instantly. The plot always runs left-to-right,
including in the Arabic (RTL) user interface.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
from PySide6.QtCore import QLineF, QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QImage, QLinearGradient, QPainter,
                           QPen, QPolygonF)
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget

from ..model import Spectrum
from . import aptec_view_strings  # noqa: F401  (aview_ strings of the ROI information box)
from .i18n import tr
from ..analysis.aptec_roi import RoiProperties
from .roi import RoiStats, compute_rois_aptec

C_BG = QColor("#ffffff")
C_FRAME = QColor("#b8c2cc")
C_GRID = QColor("#eef1f4")
C_AXIS_TEXT = QColor("#3c4650")
C_LINE = QColor("#1f5f99")
C_FILL_TOP = QColor(54, 128, 196, 150)
C_FILL_BOTTOM = QColor(54, 128, 196, 40)
C_CURSOR = QColor("#d9822b")
C_MARKER = QColor("#c62828")           # channel marker (Aptec style)
C_SELECT = QColor(217, 130, 43, 50)
C_BOX = QColor(47, 109, 179, 40)
C_ROI = QColor(214, 69, 65)
C_LABEL = QColor("#7a2e8e")
C_HILITE = QColor("#c2185b")
C_PAINT = QColor(46, 125, 50)          # ROI being painted / edited (Aptec Paint)
C_FIT = QColor("#2e7d32")              # fitted peaks of the analysis (Aptec Show Fitted ROIs)
C_WINDOW = QColor(47, 109, 179, 45)    # expanded region shown on the split full-spectrum view

# View > Color: the colors a user can change, with the defaults (Aptec View Color...)
COLOR_ROLES = ("line", "fill", "bg", "grid", "text", "roi", "marker", "fit")
DEFAULT_COLORS = {"line": "#1f5f99", "fill": "#3680c4", "bg": "#ffffff", "grid": "#eef1f4",
                  "text": "#3c4650", "roi": "#d64541", "marker": "#c62828", "fit": "#2e7d32"}
APTEC_COLORS = {"line": "#ffff00", "fill": "#808000", "bg": "#000000", "grid": "#303030",
                "text": "#3c4650", "roi": "#e53935", "marker": "#ffffff", "fit": "#00e5ff"}
BW_COLORS = {"line": "#000000", "fill": "#9a9a9a", "bg": "#ffffff", "grid": "#e0e0e0",
             "text": "#000000", "roi": "#4d4d4d", "marker": "#000000", "fit": "#000000"}


def current_colors() -> dict:
    return {"line": C_LINE.name(), "fill": QColor(C_FILL_TOP.red(), C_FILL_TOP.green(), C_FILL_TOP.blue()).name(),
            "bg": C_BG.name(), "grid": C_GRID.name(), "text": C_AXIS_TEXT.name(), "roi": C_ROI.name(),
            "marker": C_MARKER.name(), "fit": C_FIT.name()}


def _set(color: QColor, value: str) -> None:
    q = QColor(value)
    color.setRgb(q.red(), q.green(), q.blue(), q.alpha())


def apply_colors(colors: dict) -> None:
    """Change the display colors in place (every plot, overview and printed graph)."""
    c = dict(DEFAULT_COLORS)
    c.update({k: v for k, v in (colors or {}).items() if k in DEFAULT_COLORS and QColor(v).isValid()})
    _set(C_LINE, c["line"])
    f = QColor(c["fill"])
    C_FILL_TOP.setRgb(f.red(), f.green(), f.blue(), 150)
    C_FILL_BOTTOM.setRgb(f.red(), f.green(), f.blue(), 40)
    _set(C_BG, c["bg"])
    _set(C_GRID, c["grid"])
    _set(C_AXIS_TEXT, c["text"])
    _set(C_ROI, c["roi"])
    _set(C_MARKER, c["marker"])
    _set(C_FIT, c["fit"])


FITTED_MODES = ("show", "fill", "hide")       # Aptec K cycles Show -> Fill -> Hide
ROI_DATA_MODES = ("stats", "background", "off")   # Aptec D: type of ROI information shown
OVERLAY_COLORS = ["#d9822b", "#2e9d4f", "#c2185b", "#6a4fb3", "#00838f", "#8d6e63", "#5d6d7e"]

Y_LINEAR, Y_LOG, Y_SQRT = "linear", "log", "sqrt"
Y_MODES = (Y_LINEAR, Y_LOG, Y_SQRT)
MIN_SPAN = 8.0
BOX_MIN_HEIGHT = 24       # px: a drag shorter than this is a horizontal-only zoom
ROI_MIN_WIDTH = 7         # channels (3 + 1 + 3)
HISTORY_MAX = 100


def _nice_step(span: float, max_ticks: int) -> float:
    if span <= 0 or max_ticks < 1:
        return 1.0
    raw = span / max_ticks
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def format_count(v: float) -> str:
    if v == 0:
        return "0"
    a = abs(v)
    if a >= 1e7:
        exp = int(math.floor(math.log10(a)))
        mant = v / 10 ** exp
        return f"{mant:g}e{exp}"
    if a >= 1:
        return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"
    return f"{v:.3g}"


def _fmt_tick(v: float, step: float) -> str:
    if step >= 1:
        return f"{v:.0f}"
    decimals = min(6, max(0, -int(math.floor(math.log10(step)))))
    return f"{v:.{decimals}f}"


def _scale_font(f: QFont, factor: float, min_pt: float = 0.0) -> None:
    """Scale a font in place, keeping pixel-sized fonts (offscreen renderer) in pixels."""
    if f.pixelSize() > 0:
        f.setPixelSize(max(int(round(min_pt * 96 / 72)), int(round(f.pixelSize() * factor)), 1))
    else:
        f.setPointSizeF(max(min_pt, f.pointSizeF() * factor))


def _round_sig(v: float, sig: int = 1) -> float:
    if v <= 0:
        return 0.0
    mag = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 5, 10):
        if v <= m * mag * 1.2:
            return m * mag
    return 10 * mag


@dataclass
class Overlay:
    spec: Spectrum
    label: str
    color: QColor
    y: np.ndarray = field(default=None, repr=False)          # counts (unscaled)
    edges: np.ndarray = field(default=None, repr=False)      # channel edges in primary index space
    scale: float = 1.0
    by_energy: bool = False


@dataclass(eq=False)
class Roi:
    left: int
    right: int
    stats: Optional[RoiStats] = None


@dataclass
class Highlight:
    name: str
    lines: list[float]                       # keV (expected library lines)
    peaks: list = field(default_factory=list)  # matched analysis Peak objects


@dataclass
class _Cols:
    xl: np.ndarray       # left px of each column / channel
    xr: np.ndarray
    vmax: np.ndarray
    vmin: np.ndarray
    per_pixel: bool


class SpectrumPlot(QWidget):
    hovered = Signal(str)            # read-out text ("" when the mouse leaves)
    filesDropped = Signal(list)      # list[str] of local paths
    viewChanged = Signal()
    historyChanged = Signal()
    roisChanged = Signal()
    overlaysChanged = Signal()
    contextRequested = Signal(QPoint, float)   # global pos, index position (nan outside)
    markerMoved = Signal(int)        # stored-array index of the channel marker
    roiIndexChanged = Signal(int)    # indexed ROI (Space / Shift+Space), -1 = none
    selectionChanged = Signal()      # Edit > Select All / Select Region / Clear Selection
    paintChanged = Signal()          # ROI Paint / Edit started, changed or ended

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(360, 220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setLayoutDirection(Qt.LeftToRight)   # x axis always grows to the right
        self._spec: Optional[Spectrum] = None
        self._y = np.zeros(0)
        self._edges = np.zeros(1)
        self._edge_energy: Optional[np.ndarray] = None   # energy at channel edges (monotonic) or None
        self._energies: Optional[list[float]] = None
        self.x0 = 0.0
        self.x1 = 1.0
        self.y_mode = Y_LINEAR
        self.auto_y = True
        self._ylim: Optional[tuple[float, float]] = None   # manual Y range in transformed units
        self.energy_axis = False
        self.show_labels = True
        self.normalize_overlays = False
        self.overlays: list[Overlay] = []
        self.rois: list[Roi] = []
        self.last_roi: Optional[Roi] = None
        self.roi_props = RoiProperties()     # Aptec ROI Properties (Shift+R)
        self.indexed_roi: Optional[Roi] = None   # Aptec "indexed" ROI (Space / Shift+Space)
        self.paint: Optional[list[int]] = None   # [left, right] of the ROI being painted / edited
        self.paint_edit: Optional[Roi] = None    # the ROI being edited (None: painting a new one)
        self._paint_drag = False
        # Aptec View options
        self.auto_min = False                # Auto Zero Vert: autorange the minimum too
        self.fill_spectrum = True            # Fill Spc (F)
        self.plot_all_points = True          # Plot All Points (L)
        self.show_grid = True                # Grid (G)
        self.connect_points = False          # Connect Points (N)
        self.fill_rois = True                # Fill Normal ROIs (Shift+F)
        self.show_rois = True                # ROI Display (Shift+D)
        self.fitted_mode = "show"            # Show Fitted ROIs (K): show / fill / hide
        self.roi_data = "stats"              # ROI Data (D): stats / background / off
        self.fwhm_percent = False            # FWHM Percent (%)
        self.window_band: Optional[tuple[float, float]] = None   # split view: the expanded region
        self.selection: Optional[QRectF] = None   # Edit selection (widget pixels), shown in reverse video
        self.select_region_mode = False           # Edit > Select Region: the next drag selects a box
        self._select_drag = False
        self.peaks: list = []                # analysis Peak objects (labels)
        self.marker: Optional[int] = None    # channel marker (stored-array index), Aptec style
        self.show_marker = True
        self.highlight: Optional[Highlight] = None
        self._history: list[tuple] = []
        self._hist_idx = -1
        self._commit_timer = QTimer(self)
        self._commit_timer.setSingleShot(True)
        self._commit_timer.setInterval(450)
        self._commit_timer.timeout.connect(self._record)
        self._hover_idx: Optional[int] = None
        self._drag_start: Optional[QPointF] = None
        self._drag_now: Optional[QPointF] = None
        self._drag_roi = False
        self._pan_start: Optional[tuple] = None
        self._right_press: Optional[QPointF] = None
        self._drop_active = False
        self._col_cache: dict = {}
        self._yr_cache = None
        self._margins = (64, 14, 16, 44)   # left, top, right, bottom

    # ================================================================== data
    def set_spectrum(self, spec: Optional[Spectrum]) -> None:
        self._spec = spec
        self._y = np.asarray(spec.counts, dtype=float) if spec else np.zeros(0)
        n = len(self._y)
        if self.marker is not None and self.marker >= n:
            self.marker = None
        self._edges = np.arange(n + 1, dtype=float)
        self._energies = spec.energies() if spec else None
        self._edge_energy = None
        if spec and spec.energy_coeffs and n > 1:
            ee = self._poly(spec.energy_coeffs, spec.first_channel + np.arange(n + 1) - 0.5)
            if np.all(np.diff(ee) > 0):
                self._edge_energy = ee
        self._hover_idx = None
        self._ylim = None
        self._col_cache.clear()
        for ov in self.overlays:
            self._map_overlay(ov)
        # ROIs are kept (same channel windows) and re-evaluated on the new data
        self.rois = [r for r in self.rois if n and r.right < n]
        if self.indexed_roi not in self.rois:
            self.indexed_roi = None
        self._recompute_rois()
        if self.paint is not None:
            self.paint = self.paint_edit = None
            self.paintChanged.emit()
        self.peaks = []
        self.highlight = None
        self._history = []
        self._hist_idx = -1
        self.reset_view()
        self.roisChanged.emit()

    @staticmethod
    def _poly(coeffs: Sequence[float], ch):
        ch = np.asarray(ch, dtype=float)
        out = np.zeros_like(ch)
        for power, c in enumerate(coeffs):
            out = out + c * ch ** power
        return out

    def spectrum(self) -> Optional[Spectrum]:
        return self._spec

    def _tr(self, key: str, **kwargs) -> str:
        """Translation used while painting (PlotRenderer overrides it with a fixed language)."""
        return tr(key, **kwargs)

    def num_channels(self) -> int:
        return len(self._y)

    def has_energy(self) -> bool:
        return self._energies is not None

    # ------------------------------------------------------- coordinate maps
    def energy_at_pos(self, pos: float) -> Optional[float]:
        """Energy (keV) at a fractional index position (index i spans [i, i+1))."""
        if self._spec is None or not self._spec.energy_coeffs:
            return None
        return float(self._poly(self._spec.energy_coeffs, self._spec.first_channel + pos - 0.5))

    def pos_of_energy(self, e: float) -> Optional[float]:
        if self._edge_energy is None:
            return None
        ee = self._edge_energy
        return float(np.interp(e, ee, self._edges, left=-1e9, right=1e9)) \
            if ee[0] <= e <= ee[-1] else self._extrapolate_pos(e)

    def _extrapolate_pos(self, e: float) -> float:
        ee = self._edge_energy
        if e < ee[0]:
            g = ee[1] - ee[0]
            return (e - ee[0]) / g
        g = ee[-1] - ee[-2]
        return len(ee) - 1 + (e - ee[-1]) / g

    def pos_of_channel(self, ch: float) -> float:
        first = self._spec.first_channel if self._spec else 0
        return ch - first + 0.5

    def channel_at_pos(self, pos: float) -> float:
        first = self._spec.first_channel if self._spec else 0
        return first + pos - 0.5

    # ============================================================ view state
    @property
    def log_y(self) -> bool:
        return self.y_mode == Y_LOG

    def set_log_y(self, on: bool) -> None:
        self.set_y_mode(Y_LOG if on else Y_LINEAR)

    def set_y_mode(self, mode: str) -> None:
        if mode not in Y_MODES:
            mode = Y_LINEAR
        if mode != self.y_mode:
            self.y_mode = mode
            self._ylim = None
            self._history = [(a, b, None) for a, b, _ in self._history]
        self.update()
        self.viewChanged.emit()

    def set_auto_y(self, on: bool) -> None:
        self.auto_y = bool(on)
        self._ylim = None
        self.update()
        self.viewChanged.emit()

    def set_energy_axis(self, on: bool) -> None:
        self.energy_axis = bool(on)
        self._update_margins()
        self.update()

    def set_show_labels(self, on: bool) -> None:
        self.show_labels = bool(on)
        self.update()

    def view(self) -> tuple:
        return (self.x0, self.x1, self._ylim)

    def _apply(self, x0: float, x1: float, ylim=None) -> None:
        n = float(max(1, len(self._y)))
        min_span = min(n, MIN_SPAN)
        if x1 - x0 < min_span:
            mid = (x0 + x1) / 2
            x0, x1 = mid - min_span / 2, mid + min_span / 2
        span = x1 - x0
        if span > n:
            x0, x1 = 0.0, n
            span = n
        if x0 < 0:
            x0, x1 = 0.0, span
        if x1 > n:
            x0, x1 = max(0.0, n - span), n
        self.x0, self.x1 = x0, x1
        self._ylim = ylim
        self.update()
        self.viewChanged.emit()

    def set_view(self, x0: float, x1: float, ylim=None, record: bool = True) -> None:
        """Show index range [x0, x1). ``ylim`` is a manual Y range in transformed units."""
        self._apply(x0, x1, ylim)
        if record:
            self._record()
        else:
            self._commit_timer.start()

    def reset_view(self) -> None:
        self._update_margins()
        self.set_view(0.0, float(max(1, len(self._y))), None)

    # --------------------------------------------------------------- history
    def _record(self) -> None:
        self._commit_timer.stop()
        v = self.view()
        if 0 <= self._hist_idx < len(self._history) and self._history[self._hist_idx] == v:
            return
        del self._history[self._hist_idx + 1:]
        self._history.append(v)
        if len(self._history) > HISTORY_MAX:
            del self._history[0]
        self._hist_idx = len(self._history) - 1
        self.historyChanged.emit()

    def can_go_back(self) -> bool:
        pending = self._commit_timer.isActive()
        return self._hist_idx > 0 or (pending and self._hist_idx >= 0)

    def can_go_forward(self) -> bool:
        return 0 <= self._hist_idx < len(self._history) - 1

    def back(self) -> bool:
        if self._commit_timer.isActive():
            self._record()
        if self._hist_idx <= 0:
            return False
        self._hist_idx -= 1
        self._apply(*self._history[self._hist_idx])
        self.historyChanged.emit()
        return True

    def forward(self) -> bool:
        if not self.can_go_forward():
            return False
        self._hist_idx += 1
        self._apply(*self._history[self._hist_idx])
        self.historyChanged.emit()
        return True

    # ------------------------------------------------------- zoom operations
    def zoom_x(self, factor: float, anchor: Optional[float] = None, record: bool = True) -> None:
        if not len(self._y):
            return
        if anchor is None:
            anchor = (self.x0 + self.x1) / 2
        x0 = anchor - (anchor - self.x0) * factor
        x1 = anchor + (self.x1 - anchor) * factor
        if x1 - x0 >= len(self._y):
            x0, x1 = 0.0, float(len(self._y))
        self.set_view(x0, x1, self._ylim, record=record)

    def pan_x(self, fraction: float, record: bool = False) -> None:
        d = (self.x1 - self.x0) * fraction
        self.set_view(self.x0 + d, self.x1 + d, self._ylim, record=record)

    def zoom_y(self, factor: float, record: bool = False) -> None:
        ybot, ytop = self.y_range()
        self.set_view(self.x0, self.x1, (ybot, ybot + (ytop - ybot) * factor), record=record)

    def zoom_box(self, r: QRectF) -> None:
        """Rubber-band zoom: pixel rectangle -> X and Y limits."""
        rect = self.plot_rect()
        ybot, ytop = self.y_range()
        xa = self._px_to_x(max(r.left(), rect.left()), rect)
        xb = self._px_to_x(min(r.right(), rect.right()), rect)
        ya = self.px_to_y(min(r.bottom(), rect.bottom()), rect, (ybot, ytop))
        yb = self.px_to_y(max(r.top(), rect.top()), rect, (ybot, ytop))
        if yb - ya <= 0:
            return
        self.set_view(xa, xb, (ya, yb))

    def zoom_to_pos(self, pos: float, half_width: float) -> None:
        half_width = max(half_width, MIN_SPAN / 2)
        self.set_view(pos - half_width, pos + half_width, None)

    def default_fwhm_channels(self, pos: float) -> float:
        """Best estimate of the FWHM (channels) at an index position."""
        spec = self._spec
        n = len(self._y)
        if self.peaks:
            best = min(self.peaks, key=lambda p: abs(self.pos_of_channel(p.centroid) - pos))
            if best.fwhm and best.fwhm > 0:
                return float(best.fwhm)
        if spec is not None and spec.energy_coeffs:
            ch = self.channel_at_pos(pos)
            e = self.energy_at_pos(pos) or 0.0
            gain = abs((self.energy_at_pos(pos + 0.5) or 0) - (self.energy_at_pos(pos - 0.5) or 0)) or 1.0
            if spec.fwhm_coeffs:
                fk = float(self._poly(spec.fwhm_coeffs, ch))
            else:
                fk = math.sqrt(0.737 + 0.00216 * max(e, 0.0))    # typical coaxial HPGe
            if fk > 0:
                return max(2.0, fk / gain)
        return max(3.0, n * 0.0005)

    def zoom_to_energy(self, e: float, fwhm_mult: Optional[float] = None,
                       half_kev: Optional[float] = None) -> bool:
        pos = self.pos_of_energy(e)
        if pos is None:
            return False
        if half_kev is not None:
            pa = self.pos_of_energy(e - half_kev)
            pb = self.pos_of_energy(e + half_kev)
            self.set_view(pa, pb, None)
        else:
            self.zoom_to_pos(pos, (fwhm_mult or 5.0) * self.default_fwhm_channels(pos))
        return True

    def zoom_to_channel(self, ch: float, fwhm_mult: Optional[float] = None,
                        half_channels: Optional[float] = None) -> None:
        pos = self.pos_of_channel(ch)
        hw = half_channels if half_channels is not None else \
            (fwhm_mult or 5.0) * self.default_fwhm_channels(pos)
        self.zoom_to_pos(pos, hw)

    # ------------------------------------------- Aptec Edit > Select All / Region / Copy
    def select_all(self) -> None:
        self.select_region_mode = False
        self.selection = QRectF(self.rect())
        self.update()
        self.selectionChanged.emit()

    def start_select_region(self) -> None:
        """The next left drag on the plot selects a box (instead of zooming)."""
        self.select_region_mode = True
        self.setCursor(Qt.CrossCursor)

    def clear_selection(self) -> None:
        had = self.selection is not None or self.select_region_mode
        self.selection = None
        self.select_region_mode = self._select_drag = False
        self.unsetCursor()
        self.update()
        if had:
            self.selectionChanged.emit()

    def selection_image(self) -> Optional[QImage]:
        """The selected part of the plot as an image (without the reverse-video marking)."""
        if self.selection is None:
            return None
        sel = self.selection.toRect().intersected(self.rect())
        if sel.isEmpty():
            return None
        keep, self.selection = self.selection, None
        try:
            return self.grab(sel).toImage()
        finally:
            self.selection = keep
            self.update()

    # ------------------------------------------- Aptec View > Horizontal / Vertical Scale
    def _marker_or_center(self) -> int:
        if self.marker is not None:
            return self.marker
        return int((self.x0 + self.x1) / 2)

    def _view_on(self, center: float, width: float) -> None:
        n = float(len(self._y))
        width = min(max(width, MIN_SPAN), n)
        x0 = min(max(center - width / 2, 0.0), n - width)
        self.set_view(x0, x0 + width, None)

    def marker_step(self, d: int) -> None:
        """Marker Left / Right: one channel; the window scrolls at its edge."""
        if not len(self._y):
            return
        m = min(max(self._marker_or_center() + d, 0), len(self._y) - 1)
        if m < self.x0 or m + 1 > self.x1:
            w = self.x1 - self.x0
            x0 = m - w / 2
            self.set_view(x0, x0 + w, self._ylim, record=False)
        self.set_marker(m)

    def marker_to_edge(self, right: bool) -> None:
        """Marker to Left / Right Edge (Home / End)."""
        if len(self._y):
            self.set_marker(int(math.ceil(self.x1) - 1) if right else int(math.floor(self.x0)))

    def marker_far(self, right: bool) -> None:
        """Marker to Far Left / Right (Shift+Home / End): window at the spectrum end."""
        n = len(self._y)
        if not n:
            return
        w = self.x1 - self.x0
        self.set_view(n - w if right else 0.0, n if right else w, self._ylim)
        self.set_marker(n - 1 if right else 0)

    def shift_window(self, d: int, full: bool = False) -> None:
        """Spectrum Left / Right (PgDn / PgUp): half a window; ``full``: to the spectrum end."""
        n = float(len(self._y))
        if not n:
            return
        w = self.x1 - self.x0
        if full:
            x0 = n - w if d > 0 else 0.0
        else:
            x0 = min(max(self.x0 + d * w / 2, 0.0), n - w)
        self.set_view(x0, x0 + w, self._ylim)

    def expand(self, factor: float) -> None:
        """Expand (factor 0.5) / Contract (2) the window around the channel marker."""
        if len(self._y):
            self._view_on(self._marker_or_center() + 0.5, (self.x1 - self.x0) * factor)

    def max_expand(self) -> None:
        if len(self._y):
            self._view_on(self._marker_or_center() + 0.5, 16)

    def zoom_cycle(self) -> None:
        """Zoom (NumPad 5): 64 channels, 16 channels, the whole spectrum, around the marker."""
        n = len(self._y)
        if not n:
            return
        w = self.x1 - self.x0
        if w > 64.5 or w >= n:
            self._view_on(self._marker_or_center() + 0.5, 64)
        elif w > 16.5:
            self._view_on(self._marker_or_center() + 0.5, 16)
        else:
            self.reset_view()

    def shift_base(self, d: int) -> None:
        """Raise Base (d = 1, Shift+Up) / Lower Base (d = -1): move the minimum of the vertical
        scale by a tenth of the range (manual scale, as Aptec)."""
        ybot, ytop = self.y_range()
        step = (ytop - ybot) * 0.1
        nb = ybot - d * step
        if nb < ytop - step / 10:
            self.set_view(self.x0, self.x1, (nb, ytop), record=False)

    # ================================================================= ROIs
    def add_roi(self, left: int, right: int) -> Optional[Roi]:
        n = len(self._y)
        if not n:
            return None
        left, right = sorted((int(left), int(right)))
        if right - left + 1 < ROI_MIN_WIDTH:
            mid = (left + right) // 2
            left, right = mid - ROI_MIN_WIDTH // 2, mid + ROI_MIN_WIDTH // 2
        left, right = max(0, left), min(n - 1, right)
        if right - left + 1 < 3:
            return None
        return self._insert_roi(left, right)

    def _insert_roi(self, left: int, right: int) -> Roi:
        roi = Roi(int(left), int(right))
        self.last_roi = roi
        self.rois.append(roi)
        self.rois.sort(key=lambda r: r.left)
        self._recompute_rois()
        self.update()
        self.roisChanged.emit()
        return roi

    def set_marker(self, idx: Optional[int]) -> None:
        """Move the channel marker to stored-array index `idx` (None removes it)."""
        if idx is not None:
            if not len(self._y):
                return
            idx = int(min(max(int(idx), 0), len(self._y) - 1))
        self.marker = idx
        self.update()
        if idx is not None:
            self.markerMoved.emit(idx)

    def marker_channel(self) -> Optional[float]:
        """Channel number of the marker (first_channel applied), or None."""
        if self.marker is None:
            return None
        return float(self.marker + (self._spec.first_channel if self._spec else 0))

    def marker_roi(self) -> int:
        """Index of the ROI containing the marker, or -1."""
        return self.roi_at(self.marker + 0.5) if self.marker is not None else -1

    def remove_roi(self, i: int) -> None:
        if 0 <= i < len(self.rois):
            gone = self.rois.pop(i)
            if gone is self.indexed_roi:      # Aptec: the next ROI to the right becomes indexed
                self.indexed_roi = self.rois[min(i, len(self.rois) - 1)] if self.rois else None
                self.roiIndexChanged.emit(self.roi_index)
            if gone is self.paint_edit:
                self.paint = self.paint_edit = None
                self.paintChanged.emit()
            self._recompute_rois()
            self.update()
            self.roisChanged.emit()

    def clear_rois(self) -> None:
        if self.rois:
            self.rois.clear()
            if self.indexed_roi is not None:
                self.indexed_roi = None
                self.roiIndexChanged.emit(-1)
            if self.paint_edit is not None:
                self.paint = self.paint_edit = None
                self.paintChanged.emit()
            self.update()
            self.roisChanged.emit()

    # ---------------------------------------------------- Aptec ROI menu
    def set_roi_props(self, props: RoiProperties) -> None:
        """Apply Aptec ROI Properties and recalculate every ROI."""
        self.roi_props = props.validate()
        self._recompute_rois()
        self.update()
        self.roisChanged.emit()
        if self.paint is not None:
            self.paintChanged.emit()

    @property
    def roi_index(self) -> int:
        """Position of the indexed ROI in ``rois`` (-1 when none)."""
        return next((i for i, r in enumerate(self.rois) if r is self.indexed_roi), -1)

    def index_roi(self, i: int) -> None:
        """Index ROI ``i`` (-1: none): the channel marker moves to its centroid, in view."""
        if not 0 <= i < len(self.rois):
            self.indexed_roi = None
            self.update()
            self.roiIndexChanged.emit(-1)
            return
        roi = self.indexed_roi = self.rois[i]
        st = roi.stats
        if st is not None and st.centroid is not None:
            mid = int(round(st.centroid - st.first_channel))
        else:
            mid = (roi.left + roi.right) // 2
        if roi.left < self.x0 or roi.right + 1 > self.x1:
            half = max((self.x1 - self.x0) / 2, roi.right + 1 - roi.left)
            self.set_view(mid + 0.5 - half, mid + 0.5 + half, None)
        self.set_marker(mid)
        self.roiIndexChanged.emit(i)

    def index_next(self) -> None:
        """Space: index the next ROI to the right (wraps around)."""
        if not self.rois:
            return
        i = self.roi_index
        if i < 0:
            ref = self.marker if self.marker is not None else -1
            i = next((k for k, r in enumerate(self.rois) if r.left > ref), 0)
        else:
            i = (i + 1) % len(self.rois)
        self.index_roi(i)

    def index_prev(self) -> None:
        """Shift+Space: index the next ROI to the left (wraps around)."""
        if not self.rois:
            return
        i = self.roi_index
        if i < 0:
            ref = self.marker if self.marker is not None else len(self._y)
            left = [k for k, r in enumerate(self.rois) if r.right < ref]
            i = left[-1] if left else len(self.rois) - 1
        else:
            i = (i - 1) % len(self.rois)
        self.index_roi(i)

    def delete_indexed(self) -> bool:
        """ROI Delete Indexed (no warning, as in Aptec)."""
        i = self.roi_index
        if i < 0:
            return False
        self.remove_roi(i)
        return True

    def sort_rois(self) -> None:
        """ROI Sort: renumber the ROIs by increasing centroid."""
        def key(r):
            st = r.stats
            c = st.centroid if st is not None else None
            return (c if c is not None else r.left + (st.first_channel if st else 0), r.left)
        order = sorted(self.rois, key=key)
        if any(a is not b for a, b in zip(order, self.rois)):
            self.rois[:] = order
            self.update()
            self.roisChanged.emit()
            if self.indexed_roi is not None:
                self.roiIndexChanged.emit(self.roi_index)

    # ---------------------------------------------------- Aptec ROI Paint / Edit
    def start_paint(self, center: Optional[int] = None) -> bool:
        """ROI Paint (F3): a new ROI at the channel marker, about two FWHM wide."""
        n = len(self._y)
        if not n:
            return False
        if center is None:
            center = self.marker if self.marker is not None else int((self.x0 + self.x1) / 2)
        center = int(min(max(center, 0), n - 1))
        half = max(1, int(round(self.default_fwhm_channels(center + 0.5))))
        self.paint = [max(0, center - half), min(n - 1, center + half)]
        self.paint_edit = None
        self.update()
        self.paintChanged.emit()
        return True

    def edit_indexed(self) -> bool:
        """ROI Edit (F4): edit the indexed ROI."""
        i = self.roi_index
        if i < 0:
            return False
        roi = self.rois[i]
        self.paint = [roi.left, roi.right]
        self.paint_edit = roi
        self.update()
        self.paintChanged.emit()
        return True

    def _set_paint(self, left: int, right: int) -> None:
        n = len(self._y)
        left, right = sorted((int(left), int(right)))
        self.paint = [max(0, left), min(n - 1, right)]
        self.update()
        self.paintChanged.emit()

    def paint_expand(self, d: int = 1) -> None:
        """<< >> (F3, d = 1) and >> << (F4, d = -1): one channel on each side."""
        if self.paint is None:
            return
        a, b = self.paint[0] - d, self.paint[1] + d
        if b >= a:
            self._set_paint(a, b)

    def paint_shift(self, d: int) -> None:
        """<<-- (F5, d = -1) and -->> (F6, d = 1): move the painted ROI one channel."""
        if self.paint is None:
            return
        a, b = self.paint[0] + d, self.paint[1] + d
        if a >= 0 and b < len(self._y):
            self._set_paint(a, b)

    def paint_set(self) -> Optional[Roi]:
        """Set (Ctrl-Click): accept the painted ROI."""
        if self.paint is None:
            return None
        a, b = self.paint
        edit = self.paint_edit
        self.paint = self.paint_edit = None
        if edit is not None and edit in self.rois:
            edit.left, edit.right = a, b
            self.rois.sort(key=lambda r: r.left)
            self.last_roi = edit
            self._recompute_rois()
            roi = edit
            self.update()
            self.roisChanged.emit()
        else:
            roi = self._insert_roi(a, b)
        self.paintChanged.emit()
        self.indexed_roi = roi
        self.roiIndexChanged.emit(self.roi_index)
        return roi

    def paint_cancel(self) -> None:
        """Cancel: leave the ROI as it was (or do not create it)."""
        if self.paint is None:
            return
        self.paint = self.paint_edit = None
        self.update()
        self.paintChanged.emit()

    def paint_delete(self) -> None:
        """Delete: remove the ROI being edited (cancels a new one)."""
        edit = self.paint_edit
        self.paint_cancel()
        if edit is not None and edit in self.rois:
            self.remove_roi(self.rois.index(edit))

    def paint_stats(self) -> Optional[RoiStats]:
        """Aptec results of the ROI being painted, with the other ROIs in place."""
        if self.paint is None or not len(self._y):
            return None
        others = [r for r in self.rois if r is not self.paint_edit]
        return self._compute([(r.left, r.right) for r in others] + [tuple(self.paint)])[-1]

    def quick_paint_click(self, idx: int) -> None:
        """Ctrl-click: the first click marks the left side, the second the right side and sets
        the ROI (Aptec quick paint); while painting, a Ctrl-click is Set."""
        if self.paint is None:
            self.set_marker(idx)
            self.paint_edit = None
            self._set_paint(idx, idx)
        elif self.paint[0] == self.paint[1] and self.paint_edit is None:
            self._set_paint(self.paint[0], idx)
            if self.paint[1] > self.paint[0]:
                self.paint_set()
        else:
            self.paint_set()

    def roi_at(self, pos: float) -> int:
        for i, r in enumerate(self.rois):
            if r.left <= pos < r.right + 1:
                return i
        return -1

    def _compute(self, bounds) -> list:
        spec = self._spec
        return compute_rois_aptec(self._y, bounds, spec.first_channel if spec else 0,
                                  spec.energy_of if spec and spec.energy_coeffs else None,
                                  spec.live_time if spec else None, self.roi_props)

    def _recompute_rois(self) -> None:
        """Aptec rules: end points outside the ROI, shared by touching / close ROIs."""
        if not self.rois or not len(self._y):
            return
        for r, st in zip(self.rois, self._compute([(r.left, r.right) for r in self.rois])):
            r.stats = st

    # ============================================================= overlays
    def add_overlay(self, spec: Spectrum, label: str, color: Optional[QColor] = None) -> Overlay:
        if color is None:
            used = {o.color.name() for o in self.overlays}
            free = [c for c in OVERLAY_COLORS if c not in used] or OVERLAY_COLORS
            color = QColor(free[0])
        ov = Overlay(spec=spec, label=label, color=QColor(color))
        self._map_overlay(ov)
        self.overlays.append(ov)
        self._col_cache.clear()
        self.update()
        self.overlaysChanged.emit()
        return ov

    def remove_overlay(self, i: int) -> None:
        if 0 <= i < len(self.overlays):
            del self.overlays[i]
            self._col_cache.clear()
            self.update()
            self.overlaysChanged.emit()

    def clear_overlays(self) -> None:
        if self.overlays:
            self.overlays.clear()
            self._col_cache.clear()
            self.update()
            self.overlaysChanged.emit()

    def set_normalize_overlays(self, on: bool) -> None:
        self.normalize_overlays = bool(on)
        for ov in self.overlays:
            self._map_overlay(ov)
        self._col_cache.clear()
        self.update()
        self.overlaysChanged.emit()

    def _map_overlay(self, ov: Overlay) -> None:
        s = ov.spec
        ov.y = np.asarray(s.counts, dtype=float)
        m = len(ov.y)
        ov.by_energy = False
        edges = np.arange(m + 1, dtype=float) + (s.first_channel - (self._spec.first_channel if self._spec else 0))
        if self._edge_energy is not None and s.energy_coeffs and m > 1:
            oe = self._poly(s.energy_coeffs, s.first_channel + np.arange(m + 1) - 0.5)
            if np.all(np.diff(oe) > 0):
                ee = self._edge_energy
                pos = np.interp(oe, ee, self._edges)
                lo = oe < ee[0]
                hi = oe > ee[-1]
                pos[lo] = (oe[lo] - ee[0]) / (ee[1] - ee[0])
                pos[hi] = len(ee) - 1 + (oe[hi] - ee[-1]) / (ee[-1] - ee[-2])
                edges = pos
                ov.by_energy = True
        ov.edges = edges
        ov.scale = 1.0
        if self.normalize_overlays and self._spec is not None:
            lp, lo_ = self._spec.live_time, s.live_time
            if lp and lo_ and lp > 0 and lo_ > 0:
                ov.scale = lp / lo_

    # ======================================================== analysis marks
    def set_peaks(self, peaks: Sequence) -> None:
        self.peaks = list(peaks or [])
        self.update()

    def set_highlight(self, hl: Optional[Highlight]) -> None:
        self.highlight = hl
        self.update()

    # ============================================================= geometry
    def _update_margins(self) -> None:
        fm = QFontMetrics(self.font())
        ymax = float(self._y.max()) if len(self._y) else 1000.0
        widest = max(fm.horizontalAdvance(format_count(ymax)), fm.horizontalAdvance("100,000"))
        left = widest + fm.height() + 18
        self._margins = (left, 14, 18, fm.height() * 2 + 16)

    def margins(self) -> tuple:
        return self._margins

    def _plot_rect(self, w: float, h: float) -> QRectF:
        l, t, r, b = self._margins
        return QRectF(l, t, max(10, w - l - r), max(10, h - t - b))

    def plot_rect(self) -> QRectF:
        return self._plot_rect(self.width(), self.height())

    def _x_to_px(self, idx, rect: QRectF):
        return rect.left() + (idx - self.x0) / (self.x1 - self.x0) * rect.width()

    def _px_to_x(self, px: float, rect: QRectF) -> float:
        return self.x0 + (px - rect.left()) / rect.width() * (self.x1 - self.x0)

    # transformed Y
    def _t(self, v):
        v = np.asarray(v, dtype=float)
        if self.y_mode == Y_LOG:
            with np.errstate(divide="ignore", invalid="ignore"):
                return np.where(v > 0, np.log10(np.maximum(v, 1e-30)), -99.0)
        if self.y_mode == Y_SQRT:
            return np.sqrt(np.maximum(v, 0.0))
        return v

    def _t_inv(self, t: float) -> float:
        if self.y_mode == Y_LOG:
            return 10 ** t
        if self.y_mode == Y_SQRT:
            return t * t if t > 0 else 0.0
        return t

    def y_to_px(self, tval, rect: QRectF, yr):
        ybot, ytop = yr
        return rect.bottom() - (tval - ybot) / (ytop - ybot) * rect.height()

    def px_to_y(self, py: float, rect: QRectF, yr) -> float:
        ybot, ytop = yr
        return ybot + (rect.bottom() - py) / rect.height() * (ytop - ybot)

    # ---------------------------------------------------------- decimation
    def _columns(self, key, y: np.ndarray, edges: np.ndarray, rect: QRectF) -> Optional[_Cols]:
        width = max(1, int(rect.width()))
        ck = (key, id(y), self.x0, self.x1, width, rect.left())
        hit = self._col_cache.get(key)
        if hit is not None and hit[0] == ck:
            return hit[1]
        res = self._columns_uncached(y, edges, rect, width)
        self._col_cache[key] = (ck, res)
        return res

    def _columns_uncached(self, y, edges, rect, width) -> Optional[_Cols]:
        n = len(y)
        if n == 0:
            return None
        x0, x1 = self.x0, self.x1
        lo, hi = max(x0, edges[0]), min(x1, edges[-1])
        if hi <= lo:
            return None
        i0 = max(0, int(np.searchsorted(edges, lo, "right")) - 1)
        i1 = min(n, int(np.searchsorted(edges, hi, "left")))
        if i1 <= i0:
            return None
        if (i1 - i0) > 2 * width:
            px_l = math.floor(self._x_to_px(lo, rect) - rect.left())
            px_r = math.ceil(self._x_to_px(hi, rect) - rect.left())
            px_l, px_r = max(0, px_l), min(width, px_r)
            if px_r <= px_l:
                return None
            cols = np.arange(px_l, px_r + 1, dtype=float)
            bpos = x0 + cols * (x1 - x0) / width
            k = np.clip(np.searchsorted(edges, bpos, "right") - 1, 0, n - 1)
            starts = k[:-1]
            arr = y[: int(k[-1]) + 1]
            vmax = np.maximum.reduceat(arr, starts)
            vmin = np.minimum.reduceat(arr, starts)
            xl = rect.left() + cols[:-1]
            return _Cols(xl, xl + 1, vmax, vmin, True)
        vals = y[i0:i1]
        xs = self._x_to_px(edges[i0:i1 + 1], rect)
        return _Cols(xs[:-1], xs[1:], vals, vals, False)

    def _series(self):
        """(key, y_scaled, edges, color, label) for primary + overlays."""
        out = [("primary", self._y, self._edges, C_LINE, None)]
        for i, ov in enumerate(self.overlays):
            y = ov.y * ov.scale if ov.scale != 1.0 else ov.y
            if ov.scale != 1.0:
                cache = getattr(ov, "_scaled", None)
                if cache is None or cache[0] != ov.scale:
                    ov._scaled = (ov.scale, y)
                y = ov._scaled[1]
            out.append((f"ov{i}", y, ov.edges, ov.color, ov))
        return out

    def _y_range_for(self, rect: QRectF) -> tuple[float, float]:
        if self._ylim is not None:
            return self._ylim
        vmax = 0.0
        vpos = math.inf
        for key, y, edges, _c, _o in self._series():
            if self.auto_y:
                cols = self._columns(key, y, edges, rect)
                if cols is None or not len(cols.vmax):
                    continue
                vmax = max(vmax, float(cols.vmax.max()))
                pos = cols.vmin[cols.vmin > 0]
            else:
                if not len(y):
                    continue
                vmax = max(vmax, float(y.max()))
                pos = y[y > 0]
            if len(pos):
                vpos = min(vpos, float(pos.min()))
        head = 1.35 if (self.show_labels and self.peaks) else 1.08
        vmin = self._view_min(rect) if getattr(self, "auto_min", False) else None
        if vmin is not None and vmin > 0 and vmax > vmin:
            if self.y_mode == Y_LOG:
                ybot = math.log10(vmin) - 0.05 * (math.log10(vmax) - math.log10(vmin))
                top = math.log10(vmax)
                return ybot, top + (top - ybot) * (head - 1.0) + 0.02
            if self.y_mode == Y_SQRT:
                a, b = math.sqrt(vmin), math.sqrt(vmax)
                return max(0.0, a - 0.05 * (b - a)), b + (b - a) * (head - 1.0)
            return max(0.0, vmin - 0.05 * (vmax - vmin)), vmax + (vmax - vmin) * (head - 1.0)
        if self.y_mode == Y_LOG:
            ybot = 0.0 if vpos >= 1 or vpos == math.inf else max(-3.0, math.floor(math.log10(vpos)))
            top = math.log10(vmax) if vmax > 0 else 0.0
            span = max(1.0, top - ybot)
            ytop = max(ybot + 1.0, top + span * (0.06 if head < 1.2 else 0.3) + (0.1 if head < 1.2 else 0.25))
            return ybot, ytop
        if self.y_mode == Y_SQRT:
            return 0.0, (math.sqrt(vmax) * (1.04 if head < 1.2 else 1.18)) if vmax > 0 else 1.0
        return 0.0, (vmax * head if vmax > 0 else 1.0)

    def _view_min(self, rect: QRectF) -> Optional[float]:
        """Lowest count of the primary spectrum in the view (Aptec Auto Zero Vert)."""
        cols = self._columns("primary", self._y, self._edges, rect)
        if cols is None or not len(cols.vmin):
            return None
        return float(cols.vmin.min())

    def y_range(self) -> tuple[float, float]:
        return self._y_range_for(self.plot_rect())

    # ================================================================= paint
    def paintEvent(self, _event):
        p = QPainter(self)
        self.render_plot(p, self.width(), self.height(), interactive=True)
        p.end()

    def render_plot(self, p: QPainter, w: float, h: float, interactive: bool = False) -> None:
        p.setLayoutDirection(Qt.LeftToRight)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setFont(self.font())
        p.fillRect(QRectF(0, 0, w, h), self.palette().window() if interactive else C_BG)
        rect = self._plot_rect(w, h)
        p.fillRect(rect, C_BG)
        if not len(self._y):
            self._paint_empty(p, rect)
        else:
            self._paint_data(p, rect, interactive)
        p.setPen(QPen(C_FRAME, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(rect)
        sel = getattr(self, "selection", None)
        if interactive and self._select_drag and self._drag_start is not None and self._drag_now is not None:
            sel = QRectF(self._drag_start, self._drag_now).normalized()
        if interactive and sel is not None:                # Aptec: reverse video
            p.save()
            p.setCompositionMode(QPainter.CompositionMode_Difference)
            p.fillRect(sel, QColor("white"))
            p.restore()
        if interactive and self._drop_active:
            p.setPen(QPen(C_CURSOR, 2, Qt.DashLine))
            p.drawRect(rect.adjusted(3, 3, -3, -3))
            p.setPen(C_CURSOR)
            f = QFont(self.font())
            _scale_font(f, 1.3)
            p.setFont(f)
            p.drawText(rect, Qt.AlignCenter, self._tr("plot_drop_hint"))

    def _paint_empty(self, p: QPainter, rect: QRectF) -> None:
        f = QFont(self.font())
        _scale_font(f, 1.25)
        p.setFont(f)
        p.setPen(QColor("#8a96a3"))
        if not self._drop_active:
            p.drawText(rect, Qt.AlignCenter, self._tr("plot_empty"))

    def _step_polygon(self, cols: _Cols, ypx, base: float) -> QPolygonF:
        ys = ypx(cols.vmax)
        xl, xr = cols.xl, cols.xr
        pts = [QPointF(float(xl[0]), base)]
        app = pts.append
        for a, b, y in zip(xl.tolist(), xr.tolist(), ys.tolist()):
            app(QPointF(a, y))
            app(QPointF(b, y))
        app(QPointF(float(xr[-1]), base))
        return QPolygonF(pts)

    def _paint_data(self, p: QPainter, rect: QRectF, interactive: bool) -> None:
        yr = self._y_range_for(rect)
        ybot, ytop = yr
        fm = QFontMetrics(self.font())

        def ypx(v):
            t = self._t(v)
            py = rect.bottom() - (t - ybot) / (ytop - ybot) * rect.height()
            return np.clip(py, rect.top() - 2000, rect.bottom())

        self._paint_y_axis(p, rect, ybot, ytop, fm)
        self._paint_x_axis(p, rect, fm)

        p.save()
        p.setClipRect(rect.adjusted(1, 1, 0, 0))
        base = rect.bottom()
        series = self._series()
        prim = None
        # primary (filled)
        key, y, edges, color, _ = series[0]
        cols = self._columns(key, y, edges, rect)
        if cols is not None and len(cols.vmax):
            prim = cols
            band = getattr(self, "window_band", None)
            if band is not None:
                bl, br = float(self._x_to_px(band[0], rect)), float(self._x_to_px(band[1], rect))
                p.fillRect(QRectF(bl, rect.top(), max(br - bl, 2.0), rect.height()), C_WINDOW)
            poly = self._step_polygon(cols, ypx, base)
            if getattr(self, "fill_spectrum", True):
                grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
                grad.setColorAt(0, C_FILL_TOP)
                grad.setColorAt(1, C_FILL_BOTTOM)
                p.setPen(Qt.NoPen)
                p.setBrush(grad)
                p.drawPolygon(poly)
            self._paint_rois(p, rect, cols, ypx, fm)
            self._paint_fits(p, rect, ypx)
            p.setBrush(Qt.NoBrush)
            self._paint_points(p, cols, ypx, poly)
        # overlays (lines only)
        for key, y, edges, color, ov in series[1:]:
            oc = self._columns(key, y, edges, rect)
            if oc is None or not len(oc.vmax):
                continue
            poly = self._step_polygon(oc, ypx, base)
            p.setPen(QPen(color, 1.2))
            p.drawPolyline(poly)

        if self.highlight is not None:
            self._paint_highlight(p, rect, prim, ypx, fm)
        if self.show_labels and self.peaks:
            self._paint_labels(p, rect, prim, ypx, fm)

        if interactive and self._drag_start is not None and self._drag_now is not None:
            xa = min(self._drag_start.x(), self._drag_now.x())
            xb = max(self._drag_start.x(), self._drag_now.x())
            if self._drag_roi or getattr(self, "_paint_drag", False):
                c = QColor(C_ROI if self._drag_roi else C_PAINT)
                c.setAlpha(45)
                p.fillRect(QRectF(xa, rect.top(), xb - xa, rect.height()), c)
            elif self._is_box_drag():
                ya = min(self._drag_start.y(), self._drag_now.y())
                yb = max(self._drag_start.y(), self._drag_now.y())
                box = QRectF(xa, ya, xb - xa, yb - ya)
                p.fillRect(box, C_BOX)
                p.setPen(QPen(QColor("#2f6db3"), 1, Qt.DashLine))
                p.drawRect(box)
            else:
                p.fillRect(QRectF(xa, rect.top(), xb - xa, rect.height()), C_SELECT)

        if interactive and getattr(self, "paint", None) is not None:
            a, b = self.paint
            pl, pr = float(self._x_to_px(a, rect)), float(self._x_to_px(b + 1, rect))
            c = QColor(C_PAINT)
            c.setAlpha(55)
            p.fillRect(QRectF(pl, rect.top(), max(pr - pl, 1.0), rect.height()), c)
            p.setPen(QPen(C_PAINT, 1.5))
            p.drawLine(QPointF(pl, rect.top()), QPointF(pl, rect.bottom()))
            p.drawLine(QPointF(pr, rect.top()), QPointF(pr, rect.bottom()))
        if (interactive and self.show_marker and self.marker is not None
                and self.x0 - 1 <= self.marker < self.x1):
            mx = float(self._x_to_px(self.marker + 0.5, rect))
            p.setPen(QPen(C_MARKER, 1))
            p.drawLine(QPointF(mx, rect.top()), QPointF(mx, rect.bottom()))
        if interactive and getattr(self, "roi_data", "off") != "off":
            self._paint_roi_box(p, rect, fm)
        if interactive and self._hover_idx is not None and self.x0 - 1 <= self._hover_idx < self.x1:
            cx = float(self._x_to_px(self._hover_idx + 0.5, rect))
            p.setPen(QPen(C_CURSOR, 1, Qt.DashLine))
            p.drawLine(QPointF(cx, rect.top()), QPointF(cx, rect.bottom()))
            text = self.readout(self._hover_idx)
            tw = fm.horizontalAdvance(text) + 14
            th = fm.height() + 8
            bx = cx + 10 if cx + 10 + tw < rect.right() else cx - 10 - tw
            box = QRectF(bx, rect.top() + 6, tw, th)
            p.setPen(QPen(C_FRAME, 1))
            p.setBrush(QColor(255, 255, 255, 235))
            p.drawRoundedRect(box, 4, 4)
            p.setPen(C_AXIS_TEXT)
            p.drawText(box, Qt.AlignCenter, text)
        p.restore()
        if self.overlays:
            self._paint_legend(p, rect, fm)

    def _paint_points(self, p: QPainter, cols: _Cols, ypx, poly: QPolygonF) -> None:
        """The primary spectrum, as Aptec draws it: one point per channel (default), the points
        connected by lines (Connect Points, N) and / or filled to the base line as a histogram
        (Fill Spc, F).  Several channels per screen column: all of them (Plot All Points, L)
        form a vertical min-max segment; otherwise only the highest channel is drawn."""
        fill = getattr(self, "fill_spectrum", True)
        connect = getattr(self, "connect_points", False)
        all_points = getattr(self, "plot_all_points", True)
        p.setPen(QPen(C_LINE, 1))
        if connect:
            ys = ypx(cols.vmax).tolist()
            xs = ((cols.xl + cols.xr) / 2).tolist()
            p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in zip(xs, ys)]))
        elif fill:
            p.drawPolyline(poly)
        else:
            xs = ((cols.xl + cols.xr) / 2).tolist()
            ys = ypx(cols.vmax).tolist()
            pen = QPen(C_LINE, 2 if (not cols.per_pixel and (cols.xr[0] - cols.xl[0]) >= 3) else 1.5)
            pen.setCapStyle(Qt.SquareCap)
            p.setPen(pen)
            p.drawPoints(QPolygonF([QPointF(x, y) for x, y in zip(xs, ys)]))
            p.setPen(QPen(C_LINE, 1))
        if cols.per_pixel and all_points:
            self._paint_minmax(p, cols, ypx)

    def _paint_minmax(self, p: QPainter, cols: _Cols, ypx) -> None:
        mask = cols.vmin < cols.vmax
        if not mask.any():
            return
        xs = (cols.xl[mask] + 0.5).tolist()
        ya = ypx(cols.vmin[mask]).tolist()
        yb = ypx(cols.vmax[mask]).tolist()
        p.setPen(QPen(C_LINE, 1))
        p.drawLines([QLineF(x, a, x, b) for x, a, b in zip(xs, ya, yb)])

    def _paint_rois(self, p, rect, cols: _Cols, ypx, fm) -> None:
        if not self.rois or not getattr(self, "show_rois", True):
            return
        for k, roi in enumerate(self.rois):
            st = roi.stats
            if st is None:
                continue
            pl = float(self._x_to_px(roi.left, rect))
            pr = float(self._x_to_px(roi.right + 1, rect))
            if pr < rect.left() or pl > rect.right():
                continue
            mask = (cols.xr > pl) & (cols.xl < pr)
            if not mask.any():
                continue
            xl = np.maximum(cols.xl[mask], pl)
            xr = np.minimum(cols.xr[mask], pr)
            top = ypx(cols.vmax[mask])
            # background line evaluated at column centres (index space)
            cen = self._px_to_x_arr((xl + xr) / 2, rect)
            bgv = np.array([st.background_at(c - 0.5) for c in cen.tolist()])
            bot = ypx(np.maximum(bgv, 1e-9 if self.y_mode == Y_LOG else 0.0))
            top = np.minimum(top, bot)
            pts = []
            for a, b, t in zip(xl.tolist(), xr.tolist(), top.tolist()):
                pts.append(QPointF(a, t))
                pts.append(QPointF(b, t))
            for a, b, bb in zip(reversed(xl.tolist()), reversed(xr.tolist()), reversed(bot.tolist())):
                pts.append(QPointF(b, bb))
                pts.append(QPointF(a, bb))
            if getattr(self, "fill_rois", True):
                fill = QColor(C_ROI)
                fill.setAlpha(110)
                p.setPen(Qt.NoPen)
                p.setBrush(fill)
                p.drawPolygon(QPolygonF(pts))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(C_ROI.darker(120), 1, Qt.DashLine))
            bl = [QPointF(float(x), float(y)) for x, y in zip(((xl + xr) / 2).tolist(), bot.tolist())]
            if len(bl) > 1:
                p.drawPolyline(QPolygonF(bl))
            # bracket + number along the bottom edge (the top is used by labels)
            yb = rect.bottom() - 3
            indexed = roi is getattr(self, "indexed_roi", None)
            p.setPen(QPen(C_HILITE if indexed else C_ROI, 2.5 if indexed else 1.5))
            p.drawLine(QPointF(pl, yb), QPointF(pr, yb))
            p.drawLine(QPointF(pl, yb), QPointF(pl, yb - 7))
            p.drawLine(QPointF(pr, yb), QPointF(pr, yb - 7))
            tag = str(k + 1)
            tw = max(18, fm.horizontalAdvance(tag) + 10)
            box = QRectF((pl + pr) / 2 - tw / 2, yb - fm.height() - 4, tw, fm.height() + 1)
            p.setBrush(QColor(255, 255, 255, 220))
            p.drawRoundedRect(box, 3, 3)
            p.setBrush(Qt.NoBrush)
            p.drawText(box, Qt.AlignCenter, tag)

    def _paint_fits(self, p, rect, ypx) -> None:
        """Aptec Show Fitted ROIs: the analysis' fitted peaks (centroid, FWHM, net area) drawn
        as Gaussians over the average background of each peak region."""
        mode = getattr(self, "fitted_mode", "hide")
        if mode == "hide" or not self.peaks or not len(self._y):
            return
        first = self._spec.first_channel if self._spec else 0
        fill = QColor(C_FIT)
        fill.setAlpha(70)
        for pk in self.peaks:
            fwhm = getattr(pk, "fwhm", None)
            if not fwhm or fwhm <= 0 or not getattr(pk, "net_area", None):
                continue
            lo, hi = int(getattr(pk, "left", 0)), int(getattr(pk, "right", 0))
            if hi < lo or hi < self.x0 - 1 or lo > self.x1:
                continue
            sigma = fwhm / 2.3548
            cen = pk.centroid - first + 0.5
            width = hi - lo + 1
            base = float(pk.background) / width if getattr(pk, "background", None) else 0.0
            x = np.linspace(lo, hi + 1, max(24, int(width * 4)))
            yv = base + pk.net_area / (sigma * math.sqrt(2 * math.pi)) * np.exp(-0.5 * ((x - cen) / sigma) ** 2)
            xs = self._x_to_px(x, rect)
            ys = ypx(yv)
            pts = [QPointF(float(a), float(b)) for a, b in zip(xs.tolist(), ys.tolist())]
            if mode == "fill":
                yb = ypx(np.array([base]))[0]
                poly = [QPointF(float(xs[0]), float(yb))] + pts + [QPointF(float(xs[-1]), float(yb))]
                p.setPen(Qt.NoPen)
                p.setBrush(fill)
                p.drawPolygon(QPolygonF(poly))
                p.setBrush(Qt.NoBrush)
            p.setPen(QPen(C_FIT, 1.3))
            p.drawPolyline(QPolygonF(pts))

    def roi_box_lines(self) -> list[str]:
        """Text of the Aptec ROI information box (indexed ROI, else the ROI at the marker)."""
        i = self.roi_index if hasattr(self, "indexed_roi") else -1
        if i < 0 and self.marker is not None:
            i = self.roi_at(self.marker + 0.5)
        if i < 0 or i >= len(self.rois) or self.rois[i].stats is None:
            return []
        st = self.rois[i].stats
        t = self._tr
        if self.roi_data == "background":
            out = [t("aview_box_bkg_title", n=i + 1)]
            f = st.first_channel
            bl, bh = getattr(st, "bl", None), getattr(st, "bh", None)
            out.append(f"BL {f + bl if bl is not None else '-'}   RL {st.start_channel}   "
                       f"RH {st.end_channel}   BH {f + bh if bh is not None else '-'}")
            coeffs = list(getattr(st, "coeffs", ()) or ())
            # Aptec's B0..B5 are in channel numbers; ours are in stored-array indices
            if coeffs and f:
                c = np.polynomial.polynomial.Polynomial(coeffs)
                coeffs = list(c(np.polynomial.polynomial.Polynomial([-f, 1.0])).coef)
            coeffs = (coeffs + [0.0] * 6)[:6]
            out += [f"B{k} = {v:.6g}" for k, v in enumerate(coeffs)]
            return out
        e = st.centroid_energy

        def width(ch, kev):
            if ch is None:
                return "-"
            if self.fwhm_percent and kev is not None and e:
                return f"{kev / e * 100:.2f} %"
            if self.energy_axis and kev is not None:
                return f"{kev:.2f} keV"
            return f"{ch:.2f}"
        err = getattr(st, "err_pct", None)
        k = float(self.roi_props.error_sigma) if hasattr(self, "roi_props") else 1.0
        cen = "-" if st.centroid is None else (
            f"{e:.2f} keV" if self.energy_axis and e is not None else f"{st.centroid:.2f}")
        def row(label, value):        # the value reads left to right in Arabic too
            return f"{label} = \u2066{value}\u2069"
        out = [t("aview_box_roi", n=i + 1),
               row(t("aview_box_gross"), f"{st.gross:.0f}"),
               row(t("aview_box_bkgnd"), f"{st.background:.0f}"),
               row(t("aview_box_net"), f"{st.net:.0f}"),
               row(t("aview_box_err"), "-" if err is None else f"{err * k:.2f} %"),
               row(t("aview_box_cntr"), cen),
               row("FWHM", width(st.fwhm, st.fwhm_kev)),
               row("FWTM", width(getattr(st, "fwtm", None), getattr(st, "fwtm_kev", None)))]
        if st.count_rate is not None and abs(st.count_rate) >= 0.001:   # Aptec blanks < 0.001
            out.append(row(t("aview_box_netcps"), f"{st.count_rate:.2f}"))
        if getattr(st, "flags", ""):
            out.append(st.flags)
        return out

    def _paint_roi_box(self, p, rect, fm) -> None:
        lines = self.roi_box_lines()
        if not lines:
            return
        w = max(fm.horizontalAdvance(s) for s in lines) + 16
        h = fm.height() * len(lines) + 10
        box = QRectF(rect.right() - w - 8, rect.top() + 8, w, h)
        p.setPen(QPen(C_FRAME, 1))
        p.setBrush(QColor(255, 255, 255, 230))
        p.drawRoundedRect(box, 4, 4)
        p.setPen(C_AXIS_TEXT)
        from . import i18n
        rtl = i18n.is_rtl(getattr(self, "lang", None) or i18n.language())
        p.save()
        p.setLayoutDirection(Qt.RightToLeft if rtl else Qt.LeftToRight)
        for k, s in enumerate(lines):
            p.drawText(QRectF(box.left() + 8, box.top() + 5 + k * fm.height(), w - 16, fm.height()),
                       Qt.AlignAbsolute | (Qt.AlignRight if rtl else Qt.AlignLeft) | Qt.AlignVCenter, s)
        p.restore()

    def _px_to_x_arr(self, px, rect):
        return self.x0 + (np.asarray(px) - rect.left()) / rect.width() * (self.x1 - self.x0)

    def _top_at(self, cols: Optional[_Cols], px: float, ypx, rect) -> float:
        if cols is None or not len(cols.xl):
            return rect.bottom()
        j = int(np.clip(np.searchsorted(cols.xl, px, "right") - 1, 0, len(cols.xl) - 1))
        a, b = max(0, j - 2), min(len(cols.xl), j + 3)
        return float(ypx(np.array([cols.vmax[a:b].max()]))[0])

    def _paint_labels(self, p, rect, prim, ypx, fm) -> None:
        f = QFont(self.font())
        _scale_font(f, 0.9, 7.0)
        p.setFont(f)
        lfm = QFontMetrics(f)
        taken: list[float] = []
        order = sorted(self.peaks, key=lambda pk: -(getattr(pk, "significance", 0) or 0))
        for pk in order:
            pos = self.pos_of_channel(pk.centroid)
            if not (self.x0 <= pos <= self.x1):
                continue
            px = float(self._x_to_px(pos, rect))
            if any(abs(px - t) < lfm.height() + 1 for t in taken):
                continue
            taken.append(px)
            if pk.nuclide:
                text = pk.nuclide
                col = C_LABEL
            else:
                text = f"{pk.energy:.1f}" if pk.energy is not None else f"{pk.centroid:.1f}"
                col = QColor("#6b7682")
            top = self._top_at(prim, px, ypx, rect)
            tw = lfm.horizontalAdvance(text)
            y1 = top - 4
            top_free = rect.top() + (fm.height() + 6 if self.highlight is not None else 0)
            y2 = max(top_free + tw + 8, top - 22)
            if y2 >= y1:
                y2 = y1 - 1
            p.setPen(QPen(col, 1))
            p.drawLine(QPointF(px, y1), QPointF(px, y2))
            p.save()
            p.translate(px, y2 - 3)
            p.rotate(-90)
            p.drawText(QRectF(0, -lfm.height() / 2 - 1, tw + 4, lfm.height() + 2),
                       Qt.AlignLeft | Qt.AlignVCenter, text)
            p.restore()
        p.setFont(self.font())

    def _paint_highlight(self, p, rect, prim, ypx, fm) -> None:
        hl = self.highlight
        p.setPen(QPen(C_HILITE, 1, Qt.DashLine))
        last_right = -1e9
        for e in sorted(hl.lines):
            pos = self.pos_of_energy(e)
            if pos is None or not (self.x0 <= pos <= self.x1):
                continue
            px = float(self._x_to_px(pos, rect))
            lab = f"{e:.1f}"
            tw = fm.horizontalAdvance(lab)
            labelled = px - tw / 2 - 2 > last_right + 4
            p.drawLine(QPointF(px, rect.top() + (fm.height() + 6 if labelled else 2)), QPointF(px, rect.bottom()))
            if labelled:
                p.drawText(QRectF(px - tw / 2 - 2, rect.top() + 3, tw + 4, fm.height()), Qt.AlignCenter, lab)
                last_right = px + tw / 2 + 2
        p.setBrush(C_HILITE)
        p.setPen(Qt.NoPen)
        for pk in hl.peaks:
            pos = self.pos_of_channel(pk.centroid)
            if not (self.x0 <= pos <= self.x1):
                continue
            px = float(self._x_to_px(pos, rect))
            top = self._top_at(prim, px, ypx, rect)
            tri = QPolygonF([QPointF(px, top - 3), QPointF(px - 5, top - 11), QPointF(px + 5, top - 11)])
            p.drawPolygon(tri)
        p.setBrush(Qt.NoBrush)
        # name tag
        name = hl.name
        tw = fm.horizontalAdvance(name) + 12
        box = QRectF(rect.left() + 8, rect.bottom() - fm.height() - 12, tw, fm.height() + 6)
        p.setPen(QPen(C_HILITE, 1))
        p.setBrush(QColor(255, 255, 255, 230))
        p.drawRoundedRect(box, 3, 3)
        p.drawText(box, Qt.AlignCenter, name)
        p.setBrush(Qt.NoBrush)

    def _paint_legend(self, p, rect, fm) -> None:
        entries = [(C_LINE, self._spec.sample_id or self._tr("legend_displayed") if self._spec else "")]
        if self._spec is not None:
            entries[0] = (C_LINE, self._legend_name(self._spec, self._tr("legend_displayed")))
        for ov in self.overlays:
            lab = ov.label
            if ov.scale != 1.0:
                lab += f"  (×{ov.scale:.3g})"
            entries.append((ov.color, lab))
        w = max(fm.horizontalAdvance(t) for _, t in entries) + 34
        h = len(entries) * (fm.height() + 3) + 8
        box = QRectF(rect.right() - w - 8, rect.top() + 8, w, h)
        if self._hover_idx is not None:
            box.moveTop(rect.top() + fm.height() + 22)
        p.setPen(QPen(C_FRAME, 1))
        p.setBrush(QColor(255, 255, 255, 225))
        p.drawRoundedRect(box, 4, 4)
        y = box.top() + 4
        for color, text in entries:
            p.setPen(QPen(color, 2))
            p.drawLine(QPointF(box.left() + 8, y + fm.height() / 2), QPointF(box.left() + 24, y + fm.height() / 2))
            p.setPen(C_AXIS_TEXT)
            p.drawText(QRectF(box.left() + 30, y, w - 34, fm.height()), Qt.AlignLeft | Qt.AlignVCenter, text)
            y += fm.height() + 3
        p.setBrush(Qt.NoBrush)

    @staticmethod
    def _legend_name(spec: Spectrum, default: str) -> str:
        if spec.source_path:
            from pathlib import Path
            return Path(spec.source_path).name
        return spec.sample_id or default

    # ---------------------------------------------------------------- axes
    def _paint_y_axis(self, p, rect, ybot, ytop, fm) -> None:
        ticks: list[tuple[float, str, bool]] = []   # (value-in-y-space, label, major)
        if self.y_mode == Y_LOG:
            label_minor = (ytop - ybot) < 1.6
            for d in range(int(math.floor(ybot)), int(math.floor(ytop)) + 1):
                if d >= ybot:
                    ticks.append((float(d), format_count(10.0 ** d), True))
                for m in range(2, 10):
                    y = d + math.log10(m)
                    if ybot <= y < ytop:
                        ticks.append((y, format_count(m * 10.0 ** d) if label_minor and m in (2, 5) else "", False))
        elif self.y_mode == Y_SQRT:
            nt = max(2, int(rect.height() / (fm.height() * 2.6)))
            last_px = None
            seen = set()
            for i in range(nt + 1):
                t = ybot + (ytop - ybot) * i / nt
                v = _round_sig(t * t)
                if v in seen:
                    continue
                tv = math.sqrt(v)
                if not (ybot <= tv <= ytop):
                    continue
                py = rect.bottom() - (tv - ybot) / (ytop - ybot) * rect.height()
                if last_px is not None and abs(last_px - py) < fm.height() * 1.2:
                    continue
                seen.add(v)
                last_px = py
                ticks.append((tv, format_count(v), True))
        else:
            step = _nice_step(ytop - ybot, max(2, int(rect.height() / (fm.height() * 2.6))))
            if step < 1 and ytop > 5:
                step = 1.0
            v = math.ceil(ybot / step) * step
            while v <= ytop:
                ticks.append((v, format_count(round(v, 10)) if step >= 1 else _fmt_tick(v, step), True))
                v += step
        for y, label, major in ticks:
            py = rect.bottom() - (y - ybot) / (ytop - ybot) * rect.height()
            if py < rect.top() - 0.5 or py > rect.bottom() + 0.5:
                continue
            if major and getattr(self, "show_grid", True):
                p.setPen(QPen(C_GRID, 1))
                p.drawLine(QPointF(rect.left() + 1, py), QPointF(rect.right() - 1, py))
            p.setPen(QPen(C_FRAME, 1))
            p.drawLine(QPointF(rect.left() - (5 if major else 3), py), QPointF(rect.left(), py))
            if label:
                p.setPen(C_AXIS_TEXT)
                p.drawText(QRectF(0, py - fm.height() / 2, rect.left() - 8, fm.height()),
                           Qt.AlignAbsolute | Qt.AlignRight | Qt.AlignVCenter, label)
        p.save()
        p.setPen(C_AXIS_TEXT)
        p.translate(fm.height() * 0.2, rect.center().y())
        p.rotate(-90)
        title = self._tr("axis_counts")
        if self.y_mode == Y_SQRT:
            title += " (√)"
        p.drawText(QRectF(-rect.height() / 2, 0, rect.height(), fm.height() + 2), Qt.AlignCenter, title)
        p.restore()

    def _paint_x_axis(self, p, rect, fm) -> None:
        max_ticks = max(2, int(rect.width() / (fm.horizontalAdvance("00000") * 1.8)))
        first = self._spec.first_channel if self._spec else 0
        ticks: list[tuple[float, str]] = []      # (index position, label)
        use_energy = self.energy_axis and self._energies is not None
        if use_energy and self._edge_energy is not None:
            e0 = self.energy_at_pos(self.x0)
            e1 = self.energy_at_pos(self.x1)
            step = _nice_step(e1 - e0, max_ticks)
            v = math.ceil(e0 / step) * step
            while v <= e1 + 1e-9:
                pos = self.pos_of_energy(v)
                ticks.append((pos, _fmt_tick(v, step)))
                v += step
        else:
            c0 = first + self.x0
            c1 = first + self.x1
            step = max(1.0, _nice_step(c1 - c0, max_ticks))
            v = math.ceil(c0 / step) * step
            while v <= c1:
                pos = v - first + 0.5
                if use_energy:
                    en = self._spec.energy_of(v) if self._spec else None
                    label = f"{en:.1f}" if en is not None else _fmt_tick(v, step)
                else:
                    label = _fmt_tick(v, step)
                ticks.append((pos, label))
                v += step
        for pos, label in ticks:
            px = float(self._x_to_px(pos, rect))
            if px < rect.left() - 0.5 or px > rect.right() + 0.5:
                continue
            if getattr(self, "show_grid", True):
                p.setPen(QPen(C_GRID, 1))
                p.drawLine(QPointF(px, rect.top() + 1), QPointF(px, rect.bottom() - 1))
            p.setPen(QPen(C_FRAME, 1))
            p.drawLine(QPointF(px, rect.bottom()), QPointF(px, rect.bottom() + 5))
            p.setPen(C_AXIS_TEXT)
            tw = fm.horizontalAdvance(label)
            p.drawText(QRectF(px - tw / 2 - 2, rect.bottom() + 6, tw + 4, fm.height()),
                       Qt.AlignCenter, label)
        p.setPen(C_AXIS_TEXT)
        title = self._tr("axis_energy") if use_energy else self._tr("axis_channel")
        p.drawText(QRectF(rect.left(), rect.bottom() + 8 + fm.height(), rect.width(), fm.height() + 4),
                   Qt.AlignCenter, title)

    # ============================================================= read-out
    def readout(self, idx: int) -> str:
        if not len(self._y) or not (0 <= idx < len(self._y)):
            return ""
        first = self._spec.first_channel if self._spec else 0
        parts = [tr("hover_channel", ch=first + idx)]
        if self._energies is not None:
            parts.append(tr("hover_energy", e=f"{self._energies[idx]:.2f}"))
        parts.append(tr("hover_counts", c=format_count(float(self._y[idx]))))
        return "   ".join(parts)

    # ================================================================ export
    def render_image(self, size: Optional[QSize] = None, scale: float = 2.0) -> QImage:
        size = size or self.size()
        img = QImage(int(size.width() * scale), int(size.height() * scale), QImage.Format_ARGB32)
        img.setDevicePixelRatio(scale)
        img.fill(QColor("white"))
        p = QPainter(img)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        self.render_plot(p, size.width(), size.height(), interactive=False)
        p.end()
        return img

    def export_png(self, path: str, size: Optional[QSize] = None) -> bool:
        return self.render_image(size).save(str(path), "PNG")

    def export_svg(self, path: str, size: Optional[QSize] = None, title: str = "") -> bool:
        from PySide6.QtSvg import QSvgGenerator
        size = size or self.size()
        gen = QSvgGenerator()
        gen.setFileName(str(path))
        gen.setSize(size)
        gen.setViewBox(QRectF(0, 0, size.width(), size.height()))
        gen.setTitle(title or "SpectraMaster")
        gen.setDescription("Spectrum plot exported by SpectraMaster")
        p = QPainter()
        if not p.begin(gen):
            return False
        self.render_plot(p, size.width(), size.height(), interactive=False)
        p.end()
        return True

    def copy_to_clipboard(self) -> None:
        QApplication.clipboard().setImage(self.render_image())

    # ================================================================= mouse
    def _idx_at(self, pos: QPointF) -> Optional[int]:
        rect = self.plot_rect()
        if not len(self._y) or not rect.contains(pos):
            return None
        i = int(math.floor(self._px_to_x(pos.x(), rect)))
        return i if 0 <= i < len(self._y) else None

    def _is_box_drag(self) -> bool:
        if self._drag_start is None or self._drag_now is None:
            return False
        return abs(self._drag_now.y() - self._drag_start.y()) >= BOX_MIN_HEIGHT

    def mouseMoveEvent(self, ev):
        pos = ev.position()
        rect = self.plot_rect()
        if self._right_press is not None and self._pan_start is None:
            if (pos - self._right_press).manhattanLength() > 3:
                self._begin_pan(self._right_press)
        if self._pan_start is not None:
            px0, py0, vx0, vx1, ylim = self._pan_start
            dx = (pos.x() - px0) / rect.width() * (vx1 - vx0)
            new_ylim = ylim
            if ylim is not None:
                dy = (pos.y() - py0) / rect.height() * (ylim[1] - ylim[0])
                new_ylim = (ylim[0] + dy, ylim[1] + dy)
            self.set_view(vx0 - dx, vx1 - dx, new_ylim, record=False)
        elif self._drag_start is not None:
            self._drag_now = QPointF(min(max(pos.x(), rect.left()), rect.right()),
                                     min(max(pos.y(), rect.top()), rect.bottom()))
        idx = self._idx_at(pos)
        if idx != self._hover_idx:
            self._hover_idx = idx
            self.hovered.emit(self.readout(idx) if idx is not None else "")
        self.update()

    def leaveEvent(self, _ev):
        self._hover_idx = None
        self.hovered.emit("")
        self.update()

    def _begin_pan(self, pos: QPointF) -> None:
        self._pan_start = (pos.x(), pos.y(), self.x0, self.x1, self._ylim)
        self.setCursor(Qt.ClosedHandCursor)

    def mousePressEvent(self, ev):
        if not len(self._y):
            return
        pos = ev.position()
        mods = ev.modifiers()
        if ev.button() == Qt.RightButton:
            self._right_press = pos
        elif ev.button() == Qt.MiddleButton or (ev.button() == Qt.LeftButton and mods & Qt.ShiftModifier):
            self._begin_pan(pos)
        elif ev.button() == Qt.LeftButton and self.select_region_mode:
            self._select_drag = True
            self._drag_start = pos
            self._drag_now = pos
            self._drag_roi = self._paint_drag = False
        elif ev.button() == Qt.LeftButton and self.plot_rect().contains(pos):
            self._drag_start = pos
            self._drag_now = pos
            self._drag_roi = bool(mods & Qt.ControlModifier)
            self._paint_drag = self.paint is not None and not self._drag_roi

    def mouseReleaseEvent(self, ev):
        rect = self.plot_rect()
        if self._pan_start is not None:
            self._pan_start = None
            self._right_press = None
            self.unsetCursor()
            self._record()
        elif self._right_press is not None:
            pos = self._right_press
            self._right_press = None
            idx = self._px_to_x(pos.x(), rect) if rect.contains(pos) else float("nan")
            self.contextRequested.emit(self.mapToGlobal(pos.toPoint()), idx)
        elif self._select_drag and self._drag_start is not None and self._drag_now is not None:
            r = QRectF(self._drag_start, self._drag_now).normalized()
            self._drag_start = self._drag_now = None
            self._select_drag = False
            self.select_region_mode = False
            self.unsetCursor()
            if r.width() >= 3 and r.height() >= 3:
                self.selection = r
                self.selectionChanged.emit()
        elif self._drag_start is not None and self._drag_now is not None:
            a, b = self._drag_start, self._drag_now
            box = self._is_box_drag()
            roi = self._drag_roi
            painting = self._paint_drag
            self._drag_start = self._drag_now = None
            self._drag_roi = self._paint_drag = False
            xa, xb = min(a.x(), b.x()), max(a.x(), b.x())
            ia = int(math.floor(self._px_to_x(xa, rect)))
            ib = int(math.floor(self._px_to_x(xb, rect)))
            if roi:
                if xb - xa >= 2 and self.paint is not None:
                    self._set_paint(ia, ib)
                    self.paint_set()
                elif xb - xa >= 2:
                    self.add_roi(ia, ib)
                elif rect.contains(b):                   # Ctrl-click: Aptec quick paint / Set
                    self.quick_paint_click(ib)
            elif painting:                               # Paint mode: the mouse paints the ROI
                if xb - xa >= 2:
                    self._set_paint(ia, ib)
                elif rect.contains(b):
                    self.set_marker(ib)
            elif xb - xa >= 5:
                if box:
                    self.zoom_box(QRectF(QPointF(xa, min(a.y(), b.y())), QPointF(xb, max(a.y(), b.y()))))
                else:
                    self.set_view(self._px_to_x(xa, rect), self._px_to_x(xb, rect), None)
            elif rect.contains(b):                       # a click: move the channel marker
                self.set_marker(int(math.floor(self._px_to_x(b.x(), rect))))
        self.update()

    def mouseDoubleClickEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        if not self.rois:
            self.reset_view()
            return
        # Aptec: double-click to the left of an ROI indexes it (Shift: the ROI to the left)
        pos = self._px_to_x(ev.position().x(), self.plot_rect())
        if ev.modifiers() & Qt.ShiftModifier:
            left = [k for k, r in enumerate(self.rois) if r.right + 1 <= pos]
            self.index_roi(left[-1] if left else len(self.rois) - 1)
        else:
            k = next((k for k, r in enumerate(self.rois) if r.left >= pos or r.left <= pos < r.right + 1), 0)
            self.index_roi(k)

    def wheelEvent(self, ev):
        if not len(self._y):
            return
        rect = self.plot_rect()
        dy = ev.angleDelta().y()
        dx = ev.angleDelta().x()
        mods = ev.modifiers()
        if dy == 0 and dx != 0:
            self.pan_x(-dx / 120.0 * 0.1)
            ev.accept()
            return
        steps = dy / 120.0
        if steps == 0:
            return
        if mods & Qt.ShiftModifier:
            self.pan_x(-steps * 0.1)
        elif mods & Qt.ControlModifier:
            self.zoom_y(0.8 ** steps)
        else:
            px = min(max(ev.position().x(), rect.left()), rect.right())
            self.zoom_x(0.8 ** steps, self._px_to_x(px, rect), record=False)
        ev.accept()

    def keyPressEvent(self, ev):
        k = ev.key()
        mods = ev.modifiers()
        if self._drag_start is not None and k == Qt.Key_Escape:
            self._drag_start = self._drag_now = None
            self._drag_roi = self._paint_drag = False
            self.update()
        elif self.paint is not None and k == Qt.Key_Escape:
            self.paint_cancel()
        elif self.paint is not None and k in (Qt.Key_Return, Qt.Key_Enter):
            self.paint_set()
        elif k == Qt.Key_Escape:
            self.reset_view()
        elif k == Qt.Key_Backspace or (k == Qt.Key_Left and mods & Qt.AltModifier):
            self.back()
        elif k == Qt.Key_Right and mods & Qt.AltModifier:
            self.forward()
        elif k in (Qt.Key_Left, Qt.Key_Right):          # Aptec: Marker Left / Right
            self.marker_step(-1 if k == Qt.Key_Left else 1)
        elif k in (Qt.Key_Home, Qt.Key_End):            # Marker to edge; Shift: far left / right
            if mods & Qt.ShiftModifier:
                self.marker_far(k == Qt.Key_End)
            else:
                self.marker_to_edge(k == Qt.Key_End)
        elif k in (Qt.Key_PageUp, Qt.Key_PageDown):     # Spectrum Right / Left
            self.shift_window(1 if k == Qt.Key_PageUp else -1, bool(mods & Qt.ShiftModifier))
        elif k in (Qt.Key_Up, Qt.Key_Down) and mods & Qt.ShiftModifier:
            self.shift_base(1 if k == Qt.Key_Up else -1)
        elif k in (Qt.Key_Up, Qt.Key_Down):             # Raise / Lower Spectrum
            self.zoom_y(0.8 if k == Qt.Key_Up else 1.25)
        elif k == Qt.Key_5 and mods & Qt.KeypadModifier:
            self.zoom_cycle()
        elif k == Qt.Key_Plus and mods & Qt.KeypadModifier:
            self.max_expand() if mods & Qt.ShiftModifier else self.expand(0.5)
        elif k == Qt.Key_Minus and mods & Qt.KeypadModifier:
            self.reset_view() if mods & Qt.ShiftModifier else self.expand(2.0)
        elif k in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom_x(0.5, self._hover_idx + 0.5 if self._hover_idx is not None else None)
        elif k in (Qt.Key_Minus, Qt.Key_Underscore):
            self.zoom_x(2.0, self._hover_idx + 0.5 if self._hover_idx is not None else None)
        else:
            super().keyPressEvent(ev)

    def resizeEvent(self, ev):
        self._col_cache.clear()
        super().resizeEvent(ev)

    # ============================================================ drag&drop
    @staticmethod
    def local_paths(mime) -> list[str]:
        if not mime.hasUrls():
            return []
        return [u.toLocalFile() for u in mime.urls() if u.isLocalFile() and u.toLocalFile()]

    def dragEnterEvent(self, ev):
        if self.local_paths(ev.mimeData()):
            self._drop_active = True
            self.update()
            ev.acceptProposedAction()
        else:
            ev.ignore()

    def dragMoveEvent(self, ev):
        if self._drop_active:
            ev.acceptProposedAction()

    def dragLeaveEvent(self, _ev):
        self._drop_active = False
        self.update()

    def dropEvent(self, ev):
        self._drop_active = False
        self.update()
        paths = self.local_paths(ev.mimeData())
        if paths:
            ev.acceptProposedAction()
            self.filesDropped.emit(paths)


# ============================================================================ offscreen renderer
class PlotRenderer:
    """Widget-free copy of a spectrum plot that paints with ``SpectrumPlot.render_plot``.

    Used for printing / PDF reports: it does not depend on the on-screen widget
    size, can paint onto any QPainter (QPrinter / QPdfWriter = vector output,
    or a high-DPI QImage) and, having no QWidget, may be used in a worker thread.
    ``lang`` fixes the language of the axis titles (None = current UI language).
    """

    # drawing / coordinate helpers shared with SpectrumPlot (plain functions, properties
    # and staticmethods taken from the class dict so that they bind to this object)
    _SHARED = ("_poly", "num_channels", "has_energy", "energy_at_pos", "pos_of_energy",
               "_extrapolate_pos", "pos_of_channel", "channel_at_pos", "log_y", "_map_overlay",
               "_update_margins", "margins", "_plot_rect", "_x_to_px", "_px_to_x", "_t", "_t_inv",
               "y_to_px", "px_to_y", "_columns", "_columns_uncached", "_series", "_y_range_for",
               "render_plot", "_paint_empty", "_step_polygon", "_paint_data", "_paint_minmax",
               "_paint_rois", "_px_to_x_arr", "_top_at", "_paint_labels", "_paint_highlight",
               "_paint_legend", "_legend_name", "_paint_y_axis", "_paint_x_axis", "_is_box_drag",
               "readout", "_paint_fits", "_view_min", "_paint_points")

    def __init__(self, spec: Optional[Spectrum] = None, font: Optional[QFont] = None,
                 lang: Optional[str] = None):
        self._font = QFont(font) if font is not None else QFont("Segoe UI", 8)
        self.lang = lang
        self.y_mode = Y_LINEAR
        self.auto_y = True
        self._ylim = None
        self.energy_axis = False
        self.show_labels = True
        self.normalize_overlays = False
        self.overlays: list[Overlay] = []
        self.rois: list[Roi] = []
        self.peaks: list = []
        self.highlight: Optional[Highlight] = None
        self._hover_idx = None
        self._drag_start = self._drag_now = None
        self._drag_roi = False
        self._drop_active = False
        self._col_cache: dict = {}
        self._margins = (64, 14, 16, 44)
        self.load(spec)

    # QWidget stand-ins used by the shared painting code
    def font(self) -> QFont:
        return self._font

    def setFont(self, font: QFont) -> None:
        self._font = QFont(font)
        self._update_margins()

    def update(self) -> None:
        self._col_cache.clear()

    def _tr(self, key: str, **kwargs) -> str:
        from . import i18n
        return i18n.tr_in(self.lang, key, **kwargs) if self.lang else tr(key, **kwargs)

    def spectrum(self) -> Optional[Spectrum]:
        return self._spec

    def load(self, spec: Optional[Spectrum]) -> None:
        self._spec = spec
        self._y = np.asarray(spec.counts, dtype=float) if spec else np.zeros(0)
        n = len(self._y)
        self._edges = np.arange(n + 1, dtype=float)
        self._energies = spec.energies() if spec else None
        self._edge_energy = None
        if spec and spec.energy_coeffs and n > 1:
            ee = self._poly(spec.energy_coeffs, spec.first_channel + np.arange(n + 1) - 0.5)
            if np.all(np.diff(ee) > 0):
                self._edge_energy = ee
        self.x0, self.x1 = 0.0, float(max(1, n))
        self._ylim = None
        self._col_cache.clear()
        self._update_margins()

    def set_view(self, x0: float, x1: float, ylim=None) -> None:
        n = float(max(1, len(self._y)))
        x0, x1 = max(0.0, float(x0)), min(n, float(x1))
        if x1 - x0 < min(n, MIN_SPAN):
            x0, x1 = 0.0, n
        self.x0, self.x1, self._ylim = x0, x1, ylim
        self._col_cache.clear()

    def add_overlay(self, spec: Spectrum, label: str, color) -> None:
        ov = Overlay(spec=spec, label=label, color=QColor(color))
        self._map_overlay(ov)
        self.overlays.append(ov)
        self._col_cache.clear()

    @classmethod
    def from_plot(cls, plot: "SpectrumPlot", font: Optional[QFont] = None,
                  lang: Optional[str] = None) -> "PlotRenderer":
        """Snapshot of an on-screen plot (spectrum, zoom, scale, marks, ROIs, overlays)."""
        r = cls(plot.spectrum(), font, lang)
        r.y_mode, r.auto_y = plot.y_mode, plot.auto_y
        r.energy_axis = plot.energy_axis and r.has_energy()
        r.show_labels = plot.show_labels
        r.normalize_overlays = plot.normalize_overlays
        r.peaks = list(plot.peaks)
        r.rois = [Roi(x.left, x.right, x.stats) for x in plot.rois]
        for name in ("auto_min", "fill_spectrum", "plot_all_points", "show_grid", "connect_points",
                     "fill_rois", "show_rois", "fitted_mode"):
            setattr(r, name, getattr(plot, name))
        for ov in plot.overlays:
            r.add_overlay(ov.spec, ov.label, ov.color)
        r.set_view(plot.x0, plot.x1, plot._ylim)
        return r

    def paint(self, p: QPainter, rect: QRectF) -> None:
        """Paint the plot into ``rect`` (painter units) of any paint device."""
        p.save()
        p.translate(rect.topLeft())
        self._col_cache.clear()
        self.render_plot(p, rect.width(), rect.height(), interactive=False)
        p.restore()

    def render_image(self, width: int, height: int, scale: float = 3.0) -> QImage:
        """High-resolution raster copy: ``width`` x ``height`` logical px at ``scale``."""
        img = QImage(int(width * scale), int(height * scale), QImage.Format_ARGB32)
        img.setDevicePixelRatio(scale)
        img.fill(QColor("white"))
        p = QPainter(img)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setRenderHint(QPainter.Antialiasing, True)
        self.render_plot(p, width, height, interactive=False)
        p.end()
        return img


for _name in PlotRenderer._SHARED:
    setattr(PlotRenderer, _name, SpectrumPlot.__dict__[_name])
del _name


# ============================================================================ overview strip
class OverviewStrip(QWidget):
    """Mini-map of the whole spectrum with a draggable / resizable view window."""

    EDGE = 6

    def __init__(self, plot: SpectrumPlot, parent=None):
        super().__init__(parent)
        self.plot = plot
        self.setLayoutDirection(Qt.LeftToRight)
        self.setMouseTracking(True)
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._drag: Optional[tuple] = None     # (mode, start_px, x0, x1)
        self._cache = None
        plot.viewChanged.connect(self.update)
        self.setToolTip(tr("tip_overview"))

    def strip_rect(self) -> QRectF:
        l, _t, r, _b = self.plot.margins()
        return QRectF(l, 4, max(10, self.width() - l - r), self.height() - 8)

    def _n(self) -> int:
        return self.plot.num_channels()

    def x_to_px(self, x: float) -> float:
        r = self.strip_rect()
        return r.left() + x / max(1, self._n()) * r.width()

    def px_to_x(self, px: float) -> float:
        r = self.strip_rect()
        return (px - r.left()) / r.width() * max(1, self._n())

    def window_px(self) -> tuple[float, float]:
        return self.x_to_px(self.plot.x0), self.x_to_px(self.plot.x1)

    def _profile(self, r: QRectF) -> Optional[np.ndarray]:
        y = self.plot._y
        w = max(1, int(r.width()))
        key = (id(y), len(y), w)
        if self._cache and self._cache[0] == key:
            return self._cache[1]
        if not len(y):
            return None
        edges = np.linspace(0, len(y), w + 1).astype(int)
        starts = np.minimum(edges[:-1], len(y) - 1)
        prof = np.maximum.reduceat(y, starts)
        prof = np.log10(np.maximum(prof, 1.0))
        top = prof.max() or 1.0
        prof = prof / top
        self._cache = (key, prof)
        return prof

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(self.rect(), self.palette().window())
        r = self.strip_rect()
        p.fillRect(r, QColor("#fbfcfd"))
        prof = self._profile(r)
        if prof is not None:
            pts = [QPointF(r.left(), r.bottom())]
            for i, v in enumerate(prof.tolist()):
                pts.append(QPointF(r.left() + i, r.bottom() - v * (r.height() - 2)))
            pts.append(QPointF(r.left() + len(prof), r.bottom()))
            p.setPen(QPen(QColor("#7d93a8"), 1))
            p.setBrush(QColor(125, 147, 168, 90))
            p.drawPolygon(QPolygonF(pts))
            # ROIs
            for roi in self.plot.rois:
                a, b = self.x_to_px(roi.left), self.x_to_px(roi.right + 1)
                c = QColor(C_ROI)
                c.setAlpha(120)
                p.fillRect(QRectF(a, r.bottom() - 4, max(1.5, b - a), 4), c)
            a, b = self.window_px()
            shade = QColor(30, 40, 50, 55)
            p.setPen(Qt.NoPen)
            p.fillRect(QRectF(r.left(), r.top(), max(0, a - r.left()), r.height()), shade)
            p.fillRect(QRectF(b, r.top(), max(0, r.right() - b), r.height()), shade)
            win = QRectF(a, r.top(), max(2.0, b - a), r.height())
            p.setBrush(QColor(47, 109, 179, 35))
            p.setPen(QPen(QColor("#2f6db3"), 1.5))
            p.drawRect(win)
            p.setBrush(QColor("#2f6db3"))
            for x in (win.left(), win.right()):
                p.drawRect(QRectF(x - 1.5, win.center().y() - 7, 3, 14))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_FRAME, 1))
        p.drawRect(r)
        p.end()

    def _hit(self, px: float) -> str:
        a, b = self.window_px()
        if abs(px - a) <= self.EDGE:
            return "left"
        if abs(px - b) <= self.EDGE:
            return "right"
        if a < px < b:
            return "move"
        return "outside"

    def mousePressEvent(self, ev):
        if not self._n() or ev.button() != Qt.LeftButton:
            return
        px = ev.position().x()
        mode = self._hit(px)
        if mode == "outside":
            span = self.plot.x1 - self.plot.x0
            c = self.px_to_x(px)
            self.plot.set_view(c - span / 2, c + span / 2, self.plot._ylim, record=False)
            mode = "move"
        self._drag = (mode, px, self.plot.x0, self.plot.x1)

    def mouseMoveEvent(self, ev):
        px = ev.position().x()
        if self._drag is None:
            hit = self._hit(px) if self._n() else "outside"
            self.setCursor(Qt.SizeHorCursor if hit in ("left", "right") else
                           Qt.OpenHandCursor if hit == "move" else Qt.PointingHandCursor)
            return
        mode, px0, x0, x1 = self._drag
        dx = self.px_to_x(px) - self.px_to_x(px0)
        if mode == "move":
            self.plot.set_view(x0 + dx, x1 + dx, self.plot._ylim, record=False)
        elif mode == "left":
            self.plot.set_view(min(x0 + dx, x1 - MIN_SPAN), x1, self.plot._ylim, record=False)
        elif mode == "right":
            self.plot.set_view(x0, max(x1 + dx, x0 + MIN_SPAN), self.plot._ylim, record=False)

    def mouseReleaseEvent(self, _ev):
        if self._drag is not None:
            self._drag = None
            self.plot._record()

    def mouseDoubleClickEvent(self, _ev):
        self.plot.reset_view()

    def wheelEvent(self, ev):
        steps = ev.angleDelta().y() / 120.0
        if steps and self._n():
            self.plot.zoom_x(0.8 ** steps, self.px_to_x(ev.position().x()), record=False)
        ev.accept()

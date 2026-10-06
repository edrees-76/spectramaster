"""Control charts and the printable QC report (QPainter, same palette as ``plot.py``).

Reusable entry points (also for the print module):

``paint_control_chart(painter, rect, series, title="", selected=None)``
    draw one Shewhart / Westgard chart of a ``tools.qc.Series`` into `rect`
    (logical pixels; fonts use pixel sizes so a scaled painter scales everything).
``chart_image(series, width=1000, height=340, title="") -> QImage``
``save_chart(series, path, width=1000, height=340, title="")``     .png / .jpg / .svg
``paint_qc_report(device, track, ev=None, metrics=None) -> int``
    paint the full report (track info, statistics, charts, measurement table,
    violations, signature) onto any QPagedPaintDevice -- a ``QPrinter`` (print /
    preview) or a ``QPdfWriter``; returns the number of pages.
``export_qc_pdf(track, path, ev=None, metrics=None) -> Path``
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSize, QSizeF, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QPageLayout, QPageSize, QPainter,
                           QPainterPath, QPdfWriter, QPen)
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from ..tools import qc
from . import qc_i18n  # noqa: F401  (registers the strings)
from .i18n import is_rtl, tr
from .plot import C_AXIS_TEXT, C_BG, C_FRAME, C_GRID, C_LINE, C_ROI, _nice_step

C_MEAN = QColor("#2e9d4f")
C_2S = QColor("#d9822b")
C_3S = QColor(214, 69, 65)
C_TOL = QColor("#7a2e8e")
C_OK = C_LINE
C_WARN = QColor("#d9822b")
C_FAIL = QColor("#c62828")
C_EXCL = QColor("#9aa5b1")
C_BASE = QColor(54, 128, 196, 22)
C_SEL = QColor("#c2185b")

METRIC_ORDER = ("centroid", "fwhm", "rate", "background")


def metric_title(s: "qc.Series") -> str:
    name = tr(f"qc_metric_{s.metric}")
    return f"{name} — {s.line.label}" if s.line is not None else name


def _font(px: float, bold: bool = False) -> QFont:
    f = QFont()
    f.setPixelSize(max(1, int(round(px))))
    f.setBold(bold)
    return f


def _fmt(v: Optional[float], unit: str = "") -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "—"
    a = abs(v)
    if a >= 1000:
        s = f"{v:.1f}"
    elif a >= 100:
        s = f"{v:.2f}"
    elif a >= 1:
        s = f"{v:.3f}"
    else:
        s = f"{v:.4g}"
    return f"{s} {unit}".strip()


def _date_ticks(t0: datetime, t1: datetime, max_ticks: int) -> tuple[list[datetime], str]:
    span = max((t1 - t0).total_seconds() / 86400.0, 1e-6)
    for days, fmt in ((1, "%Y-%m-%d"), (2, "%Y-%m-%d"), (7, "%Y-%m-%d"), (14, "%Y-%m-%d")):
        if span / days <= max_ticks:
            start = datetime(t0.year, t0.month, t0.day)
            ticks, d = [], start
            while d <= t1:
                if d >= t0:
                    ticks.append(d)
                d += timedelta(days=days)
            return ticks, fmt
    for months in (1, 2, 3, 6, 12, 24, 60):
        if span / (30.44 * months) <= max_ticks:
            y, m = t0.year, t0.month
            ticks = []
            while True:
                d = datetime(y, m, 1)
                if d > t1:
                    break
                ok = (m - 1) % months == 0 if months < 12 else (m == 1 and y % (months // 12) == 0)
                if d >= t0 and ok:
                    ticks.append(d)
                m += 1
                if m > 12:
                    m, y = 1, y + 1
            return ticks, "%Y-%m" if months < 12 else "%Y"
    return [t0, t1], "%Y"


RULE_PRIORITY = ("SPLIT", "1-3s", "R-4s", "2-2s", "TOL", "4-1s", "10-x")


def rule_label(flags: Sequence[str]) -> str:
    """Most severe rule of a point (+ when more fired), for chart annotations."""
    fails = [f for f in flags if f not in qc.WARNING_RULES]
    if not fails:
        return ""
    best = min(fails, key=lambda f: RULE_PRIORITY.index(f) if f in RULE_PRIORITY else 99)
    return best + ("+" if len(set(fails)) > 1 else "")


class _Geom:
    """Data <-> pixel mapping of one chart."""

    def __init__(self, plot: QRectF, t0: float, t1: float, y0: float, y1: float):
        self.plot, self.t0, self.t1, self.y0, self.y1 = plot, t0, t1, y0, y1

    def x(self, t: float) -> float:
        return self.plot.left() + (t - self.t0) / (self.t1 - self.t0) * self.plot.width()

    def y(self, v: float) -> float:
        return self.plot.bottom() - (v - self.y0) / (self.y1 - self.y0) * self.plot.height()


def chart_geometry(rect: QRectF, s: "qc.Series") -> Optional[_Geom]:
    pts = [p for p in s.points if p.value is not None and p.date is not None]
    if not pts:
        return None
    plot = QRectF(rect.left() + 66, rect.top() + 26, rect.width() - 66 - 14, rect.height() - 26 - 34)
    ts = [p.date.timestamp() for p in pts]
    t0, t1 = min(ts), max(ts)
    pad = max((t1 - t0) * 0.03, 43200.0)
    t0, t1 = t0 - pad, t1 + pad
    vals = [p.value for p in pts]
    extra = [v for v in (*s.limits(3), s.mean, s.tol_lo, s.tol_hi) if v is not None]
    lo, hi = min(vals + extra), max(vals + extra)
    # do not let a far-away tolerance squash the data
    dlo, dhi = min(vals), max(vals)
    dspan = max(dhi - dlo, abs(dhi) * 1e-3, 1e-9)
    lo = max(lo, dlo - 2.5 * dspan)
    hi = min(hi, dhi + 2.5 * dspan)
    span = max(hi - lo, abs(hi) * 1e-3, 1e-9)
    return _Geom(plot, t0, t1, lo - 0.08 * span, hi + 0.12 * span)


def paint_control_chart(p: QPainter, rect: QRectF, s: "qc.Series", title: str = "",
                        selected: Optional[str] = None, legend: bool = True) -> Optional[_Geom]:
    """Draw one control chart into `rect` (logical pixels).  Returns the mapping used."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.fillRect(rect, C_BG)
    title = title or metric_title(s)
    p.setFont(_font(13, True))
    p.setPen(C_AXIS_TEXT)
    p.drawText(QRectF(rect.left() + 8, rect.top() + 3, rect.width() - 16, 20),
               Qt.AlignLeft | Qt.AlignVCenter, f"{title}  [{s.unit}]")
    g = chart_geometry(rect, s)
    if g is None:
        p.setFont(_font(12))
        p.drawText(rect, Qt.AlignCenter, tr("qc_no_data"))
        p.restore()
        return None
    plot = g.plot
    # grid + y axis
    p.setFont(_font(10.5))
    fm = QFontMetricsF(p.font())
    step = _nice_step(g.y1 - g.y0, max(2, int(plot.height() / 34)))
    v = math.ceil(g.y0 / step) * step
    dec = max(0, -int(math.floor(math.log10(step))) + (1 if step / 10 ** math.floor(math.log10(step)) == 2.5 else 0))
    while v <= g.y1 + 1e-12:
        y = g.y(v)
        p.setPen(QPen(C_GRID, 1))
        p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        p.setPen(C_AXIS_TEXT)
        p.drawText(QRectF(rect.left(), y - 8, plot.left() - rect.left() - 5, 16),
                   Qt.AlignRight | Qt.AlignVCenter, f"{v:.{dec}f}")
        v += step
    # x axis (dates)
    ticks, dfmt = _date_ticks(datetime.fromtimestamp(g.t0), datetime.fromtimestamp(g.t1),
                              max(2, int(plot.width() / 90)))
    for d in ticks:
        x = g.x(d.timestamp())
        p.setPen(QPen(C_GRID, 1))
        p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
        p.setPen(C_AXIS_TEXT)
        p.drawText(QRectF(x - 45, plot.bottom() + 4, 90, 16), Qt.AlignHCenter | Qt.AlignTop, d.strftime(dfmt))
    # baseline shading
    bpts = [q for q in s.points if q.baseline and q.date is not None]
    if bpts:
        xa = g.x(min(q.date for q in bpts).timestamp()) - 3
        xb = g.x(max(q.date for q in bpts).timestamp()) + 3
        p.fillRect(QRectF(max(xa, plot.left()), plot.top(), min(xb, plot.right()) - max(xa, plot.left()),
                          plot.height()), C_BASE)
    p.setClipRect(plot.adjusted(-1, -1, 1, 1))

    def hline(val, color, style, width=1.2):
        if val is None:
            return
        pen = QPen(color, width, style)
        p.setPen(pen)
        y = g.y(val)
        p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

    hline(s.mean, C_MEAN, Qt.SolidLine, 1.4)
    for k, c in ((2, C_2S), (3, C_3S)):
        lo, hi = s.limits(k)
        hline(lo, c, Qt.DashLine)
        hline(hi, c, Qt.DashLine)
    hline(s.tol_lo, C_TOL, Qt.DashDotLine, 1.4)
    hline(s.tol_hi, C_TOL, Qt.DashDotLine, 1.4)
    hline(s.nominal, QColor("#8a96a3"), Qt.DotLine)
    # data
    good = [q for q in s.points if q.value is not None and q.date is not None and not q.excluded]
    if len(good) > 1:
        p.setPen(QPen(QColor(31, 95, 153, 150), 1.1))
        path = QPainterPath(QPointF(g.x(good[0].date.timestamp()), g.y(good[0].value)))
        for q in good[1:]:
            path.lineTo(g.x(q.date.timestamp()), g.y(q.value))
        p.drawPath(path)
    p.setFont(_font(9.5, True))
    prev_label = ""
    for q in s.points:
        if q.value is None or q.date is None:
            continue
        pt = QPointF(g.x(q.date.timestamp()), g.y(q.value))
        if q.excluded:
            p.setPen(QPen(C_EXCL, 1.2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(pt, 3.5, 3.5)
            continue
        col, r = {qc.STATUS_FAIL: (C_FAIL, 4.6), qc.STATUS_WARN: (C_WARN, 4.0)}.get(q.status, (C_OK, 3.0))
        p.setPen(QPen(col.darker(130), 0.8))
        p.setBrush(col)
        p.drawEllipse(pt, r, r)
        label = rule_label(q.flags) if q.status == qc.STATUS_FAIL else ""
        # label only where the fired rule changes (a run of 10-x points gets one label)
        if label and label != prev_label:
            p.setPen(C_FAIL)
            above = q.z is None or q.z >= 0
            ly = pt.y() - 19 if above else pt.y() + 5
            ly = min(max(ly, plot.top() + 1), plot.bottom() - 15)
            lx = min(max(pt.x() - 30, plot.left() + 1), plot.right() - 61)
            p.drawText(QRectF(lx, ly, 60, 14), Qt.AlignHCenter | Qt.AlignVCenter, label)
        prev_label = label
        if selected and q.mid == selected:
            p.setPen(QPen(C_SEL, 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(pt, r + 4, r + 4)
    p.setClipping(False)
    p.setPen(QPen(C_FRAME, 1))
    p.setBrush(Qt.NoBrush)
    p.drawRect(plot)
    # legend
    if legend:
        items = [(tr("qc_mean"), C_MEAN, Qt.SolidLine)]
        if s.sd:
            items += [(tr("qc_2s"), C_2S, Qt.DashLine), (tr("qc_3s"), C_3S, Qt.DashLine)]
        if s.tol_lo is not None or s.tol_hi is not None:
            items.append((tr("qc_tol"), C_TOL, Qt.DashDotLine))
        p.setFont(_font(10.5))
        fm = QFontMetricsF(p.font())
        x = rect.right() - 12
        y = rect.top() + 13
        stats = f"{tr('qc_mean')} {_fmt(s.mean)}   SD {_fmt(s.sd)}   N={s.n_baseline}"
        for text, col, style in reversed(items):
            w = fm.horizontalAdvance(text)
            p.setPen(C_AXIS_TEXT)
            p.drawText(QPointF(x - w, y + 4), text)
            p.setPen(QPen(col, 1.6, style))
            p.drawLine(QPointF(x - w - 22, y), QPointF(x - w - 4, y))
            x -= w + 34
        w = fm.horizontalAdvance(stats)
        if x - w > rect.left() + fm.horizontalAdvance(title) + 140:
            p.setPen(QColor("#6b7682"))
            p.drawText(QPointF(x - w, y + 4), stats)
    p.restore()
    return g


# ------------------------------------------------------------------ widget
class ControlChart(QWidget):
    """Interactive chart: hover tooltip, click selects a measurement."""

    pointClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.series: Optional[qc.Series] = None
        self.title = ""
        self.selected: Optional[str] = None
        self.names: dict[str, str] = {}
        self._geom: Optional[_Geom] = None
        self.setMouseTracking(True)
        self.setMinimumSize(QSize(360, 190))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setLayoutDirection(Qt.LeftToRight)

    def set_series(self, s: Optional["qc.Series"], title: str = "", names: Optional[dict] = None) -> None:
        self.series, self.title = s, title
        if names is not None:
            self.names = names
        self.update()

    def set_selected(self, mid: Optional[str]) -> None:
        self.selected = mid
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        r = QRectF(self.rect())
        if self.series is None:
            p.fillRect(r, C_BG)
            p.setPen(C_AXIS_TEXT)
            p.drawText(r, Qt.AlignCenter, tr("qc_no_data"))
        else:
            self._geom = paint_control_chart(p, r, self.series, self.title, self.selected)
        p.end()

    def _nearest(self, pos) -> Optional["qc.SeriesPoint"]:
        if self.series is None or self._geom is None:
            return None
        best, bd = None, 12.0 ** 2
        for q in self.series.points:
            if q.value is None or q.date is None:
                continue
            dx = self._geom.x(q.date.timestamp()) - pos.x()
            dy = self._geom.y(q.value) - pos.y()
            if dx * dx + dy * dy < bd:
                best, bd = q, dx * dx + dy * dy
        return best

    def mouseMoveEvent(self, ev):
        q = self._nearest(ev.position())
        if q is None:
            QToolTip.hideText()
            return
        txt = (f"{q.date:%Y-%m-%d %H:%M}  {self.names.get(q.mid, '')}\n"
               f"{_fmt(q.value, self.series.unit)}" + (f"  (z = {q.z:+.2f})" if q.z is not None else "")
               + f"\n{q.status}" + (f": {', '.join(q.flags)}" if q.flags else ""))
        QToolTip.showText(ev.globalPosition().toPoint(), txt, self)

    def mousePressEvent(self, ev):
        q = self._nearest(ev.position())
        if q is not None and ev.button() == Qt.LeftButton:
            self.selected = q.mid
            self.update()
            self.pointClicked.emit(q.mid)


# ------------------------------------------------------------------ images
def chart_image(s: "qc.Series", width: int = 1000, height: int = 340, title: str = "") -> QImage:
    img = QImage(width, height, QImage.Format_ARGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    paint_control_chart(p, QRectF(0, 0, width, height), s, title)
    p.end()
    return img


def save_chart(s: "qc.Series", path, width: int = 1000, height: int = 340, title: str = "") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".svg":
        from PySide6.QtSvg import QSvgGenerator
        gen = QSvgGenerator()
        gen.setFileName(str(path))
        gen.setSize(QSize(width, height))
        gen.setViewBox(QRectF(0, 0, width, height))
        gen.setTitle(title or metric_title(s))
        p = QPainter(gen)
        paint_control_chart(p, QRectF(0, 0, width, height), s, title)
        p.end()
    else:
        if not chart_image(s, width, height, title).save(str(path)):
            raise OSError(f"cannot write {path}")
    return path


def ordered_series(ev: "qc.QCEvaluation", metrics: Optional[Sequence[str]] = None) -> list["qc.Series"]:
    metrics = list(metrics or METRIC_ORDER)
    out = []
    for l in ev.track.lines:
        for m in metrics:
            if m != "background":
                s = ev.get(m, l)
                if s is not None:
                    out.append(s)
    if "background" in metrics:
        s = ev.get("background")
        if s is not None and s.valid_points():
            out.append(s)
    return out


# ------------------------------------------------------------------ report
PAGE_W, PAGE_H = 794.0, 1123.0      # A4 in logical px (96 dpi)
MARGIN = 46.0


class _Report:
    def __init__(self, device, track, ev):
        self.dev, self.track, self.ev = device, track, ev
        self.rtl = is_rtl()
        self.p = QPainter(device)
        self.p.setRenderHint(QPainter.Antialiasing, True)
        self.p.setRenderHint(QPainter.TextAntialiasing, True)
        self.page = 1
        self._apply_scale()
        self.y = MARGIN
        self.generated = datetime.now()

    def _apply_scale(self):
        sx = self.dev.width() / PAGE_W
        sy = self.dev.height() / PAGE_H
        sc = min(sx, sy)
        self.p.resetTransform()
        self.p.scale(sc, sc)

    @property
    def content_w(self) -> float:
        return PAGE_W - 2 * MARGIN

    def footer(self):
        p = self.p
        p.setFont(_font(9))
        p.setPen(QColor("#6b7682"))
        r = QRectF(MARGIN, PAGE_H - MARGIN + 12, self.content_w, 14)
        p.drawLine(QPointF(MARGIN, r.top() - 4), QPointF(PAGE_W - MARGIN, r.top() - 4))
        left = f"SpectraMaster — {tr('qc_report_title')} — {self.track.name}"
        right = tr("qc_r_page", n=self.page)
        p.drawText(r, (Qt.AlignRight if self.rtl else Qt.AlignLeft) | Qt.AlignVCenter, left)
        p.drawText(r, (Qt.AlignLeft if self.rtl else Qt.AlignRight) | Qt.AlignVCenter, right)

    def new_page(self):
        self.footer()
        self.dev.newPage()
        self.page += 1
        self._apply_scale()
        self.y = MARGIN

    def ensure(self, h: float):
        if self.y + h > PAGE_H - MARGIN:
            self.new_page()

    def text(self, s: str, px: float = 11, bold: bool = False, color=C_AXIS_TEXT, gap: float = 4):
        self.p.setFont(_font(px, bold))
        fm = QFontMetricsF(self.p.font())
        flags = (Qt.AlignRight if self.rtl else Qt.AlignLeft) | Qt.TextWordWrap
        br = fm.boundingRect(QRectF(0, 0, self.content_w, 10000), flags, s)
        self.ensure(br.height())
        self.p.setPen(color)
        self.p.drawText(QRectF(MARGIN, self.y, self.content_w, br.height() + 2), flags, s)
        self.y += br.height() + gap

    def heading(self, s: str):
        self.ensure(40)
        self.y += 6
        self.text(s, 14, True, QColor("#1f5f99"), 2)
        self.p.setPen(QPen(QColor("#1f5f99"), 1))
        self.p.drawLine(QPointF(MARGIN, self.y), QPointF(PAGE_W - MARGIN, self.y))
        self.y += 6

    def kv(self, rows: list[tuple[str, str]]):
        p = self.p
        kw = 150.0
        for k, v in rows:
            p.setFont(_font(10.5))
            fm = QFontMetricsF(p.font())
            vw = self.content_w - kw - 8
            h = max(16.0, fm.boundingRect(QRectF(0, 0, vw, 1000), Qt.TextWordWrap, v).height() + 3)
            self.ensure(h)
            if self.rtl:
                kr = QRectF(PAGE_W - MARGIN - kw, self.y, kw, h)
                vr = QRectF(MARGIN, self.y, vw, h)
                ka, va = Qt.AlignRight, Qt.AlignRight
            else:
                kr = QRectF(MARGIN, self.y, kw, h)
                vr = QRectF(MARGIN + kw + 8, self.y, vw, h)
                ka, va = Qt.AlignLeft, Qt.AlignLeft
            p.setFont(_font(10.5, True))
            p.setPen(C_AXIS_TEXT)
            p.drawText(kr, ka | Qt.AlignTop | Qt.TextWordWrap, k)
            p.setFont(_font(10.5))
            p.drawText(vr, va | Qt.AlignTop | Qt.TextWordWrap, v)
            self.y += h

    def table(self, header: list[str], rows: list[list[str]], widths: list[float],
              colors: Optional[list[Optional[QColor]]] = None, px: float = 9):
        p = self.p
        tot = sum(widths)
        widths = [w * self.content_w / tot for w in widths]
        rh = px + 7

        def xs():
            out, x = [], MARGIN
            for w in widths:
                out.append(x)
                x += w
            if self.rtl:
                out = [PAGE_W - MARGIN - (x0 - MARGIN) - w for x0, w in zip(out, widths)]
            return out

        cols = xs()

        def draw_header():
            p.fillRect(QRectF(MARGIN, self.y, self.content_w, rh + 2), QColor("#e8eef5"))
            p.setFont(_font(px, True))
            p.setPen(C_AXIS_TEXT)
            for x, w, h in zip(cols, widths, header):
                p.drawText(QRectF(x + 2, self.y, w - 4, rh + 2), Qt.AlignHCenter | Qt.AlignVCenter, h)
            self.y += rh + 2

        self.ensure(2 * rh + 4)
        draw_header()
        for i, row in enumerate(rows):
            if self.y + rh > PAGE_H - MARGIN:
                self.new_page()
                draw_header()
            if colors and colors[i] is not None:
                p.fillRect(QRectF(MARGIN, self.y, self.content_w, rh), colors[i])
            elif i % 2:
                p.fillRect(QRectF(MARGIN, self.y, self.content_w, rh), QColor("#f7f9fb"))
            p.setFont(_font(px))
            p.setPen(C_AXIS_TEXT)
            for x, w, c in zip(cols, widths, row):
                fm = QFontMetricsF(p.font())
                c = fm.elidedText(c, Qt.ElideRight, w - 4)
                p.drawText(QRectF(x + 2, self.y, w - 4, rh), Qt.AlignHCenter | Qt.AlignVCenter, c)
            self.y += rh
        p.setPen(QPen(C_FRAME, 0.8))
        p.drawLine(QPointF(MARGIN, self.y), QPointF(PAGE_W - MARGIN, self.y))
        self.y += 6

    def chart(self, s, h: float = 255):
        self.ensure(h + 8)
        r = QRectF(MARGIN, self.y, self.content_w, h)
        paint_control_chart(self.p, r, s)
        self.p.setPen(QPen(C_FRAME, 0.8))
        self.p.setBrush(Qt.NoBrush)
        self.p.drawRect(r)
        self.y += h + 10

    def finish(self):
        self.footer()
        self.p.end()


def _short_flag(f: str) -> str:
    key, _, rule = f.partition(":")
    metric, _, e = key.partition("@")
    letter = {"centroid": "C", "fwhm": "F", "rate": "R", "background": "B"}.get(metric, metric[:1].upper())
    return f"{letter}{float(e):.0f}:{rule}" if e else f"{letter}:{rule}"


def track_info_rows(track: "qc.QCTrack", ev: "qc.QCEvaluation") -> list[tuple[str, str]]:
    ms = track.sorted_measurements()
    dates = [m.date for m in ms if m.date]
    period = f"{min(dates):%Y-%m-%d} — {max(dates):%Y-%m-%d}" if dates else "—"
    base = (f"{track.baseline_start or '…'} — {track.baseline_end or '…'}"
            if track.baseline_start or track.baseline_end else tr("qc_r_first_n", n=track.baseline_n))
    tols = []
    if track.centroid_tol_kev is not None:
        tols.append(f"centroid ±{track.centroid_tol_kev:g} keV")
    tols += [f"FWHM@{l.energy:.1f} ≤ {l.fwhm_max:g} keV" for l in track.lines if l.fwhm_max]
    if track.rate_tol_pct is not None:
        tols.append(f"rate ±{track.rate_tol_pct:g} %")
    if track.bkg_tol_pct is not None:
        tols.append(f"background ±{track.bkg_tol_pct:g} %")
    act = ", ".join(f"{k} {v:g} Bq" for k, v in track.reference_activity.items())
    c = ev.counts()
    summary = tr("qc_status_summary", n=len(ms), ok=c.get("OK", 0), warn=c.get("WARN", 0),
                 fail=c.get("FAIL", 0), excl=c.get("EXCL", 0))
    return [
        (tr("qc_r_track"), track.name),
        (tr("qc_r_detector"), f"{track.detector} ({track.detector_type})"),
        (tr("qc_r_source"), f"{track.source}" + (f" — {act}" if act else "")),
        (tr("qc_r_lines"), ", ".join(l.label for l in track.lines) or "—"),
        (tr("qc_r_refdate"), f"{ev.reference_date:%Y-%m-%d %H:%M}" if ev.reference_date else "—"),
        (tr("qc_r_period"), period),
        (tr("qc_r_baseline"), base),
        (tr("qc_r_rules"), "1-2s (warning), " + ", ".join(track.rules)),
        (tr("qc_r_tol"), "; ".join(tols) or "—"),
        (tr("qc_r_summary"), summary),
    ]


def paint_qc_report(device, track: "qc.QCTrack", ev: Optional["qc.QCEvaluation"] = None,
                    metrics: Optional[Sequence[str]] = None) -> int:
    """Paint the QC report on a QPagedPaintDevice (QPrinter / QPdfWriter). Returns pages."""
    ev = ev or qc.evaluate(track)
    R = _Report(device, track, ev)
    R.text(tr("qc_report_title"), 20, True, QColor("#1f5f99"), 2)
    R.text(f"{tr('qc_r_generated')}: {R.generated:%Y-%m-%d %H:%M}", 9.5, False, QColor("#6b7682"), 8)
    R.kv(track_info_rows(track, ev))
    if track.notes:
        R.text(track.notes, 10, False, QColor("#3c4650"), 6)
    R.heading(tr("qc_r_stats"))
    rows = []
    for s in ordered_series(ev, metrics):
        cv = 100 * s.sd / abs(s.mean) if s.sd and s.mean else None
        tr_ = s.slope_per_year()
        rows.append([metric_title(s), s.unit, str(s.n_baseline), _fmt(s.mean), _fmt(s.sd),
                     f"{cv:.2f}" if cv is not None else "—", _fmt(tr_),
                     str(sum(1 for q in s.points if q.status == qc.STATUS_FAIL)),
                     str(sum(1 for q in s.points if q.status == qc.STATUS_WARN))])
    R.table([tr("qc_col_series"), tr("qc_col_unit"), tr("qc_col_n"), tr("qc_col_mean"), tr("qc_col_sd"),
             tr("qc_col_cv"), tr("qc_col_trend"), tr("qc_col_fail"), tr("qc_col_warn")],
            rows, [30, 5, 6, 10, 9, 7, 10, 6, 6])
    for s in ordered_series(ev, metrics):
        R.chart(s)
    # measurement table
    R.heading(tr("qc_r_measurements"))
    header = [tr("qc_col_date"), tr("qc_col_file"), "Live s", "DT %"]
    widths = [12, 16, 7, 6]
    for l in track.lines:
        header += [f"E {l.energy:.0f}", f"FW {l.energy:.0f}", f"cps {l.energy:.0f}"]
        widths += [8, 6, 7]
    header += [tr("qc_col_bkg"), tr("qc_col_status"), tr("qc_col_rules")]
    widths += [7, 6, 16]
    rows, colors = [], []
    fills = {qc.STATUS_FAIL: QColor("#fbe3e4"), qc.STATUS_WARN: QColor("#fff4d6"),
             qc.STATUS_EXCLUDED: QColor("#eceff1")}
    for m in track.sorted_measurements():
        row = [f"{m.date:%Y-%m-%d %H:%M}" if m.date else "—", m.file_name,
               f"{m.live_time:.0f}" if m.live_time else "—",
               f"{m.dead_time_pct:.2f}" if m.dead_time_pct is not None else "—"]
        for l in track.lines:
            r = ev.line_results.get(m.id, {}).get(l.key)
            row += ([f"{r.centroid_kev:.2f}" if r.centroid_kev is not None else "—",
                     f"{r.fwhm_kev:.2f}" if r.fwhm_kev is not None else "—",
                     _fmt(r.rate_corr)] if r else ["—"] * 3)
        st = ev.status.get(m.id, "")
        row += [_fmt(m.window_rate), st, " ".join(_short_flag(f) for f in ev.flags.get(m.id, [])
                                                  if not f.endswith(":1-2s"))]
        rows.append(row)
        colors.append(fills.get(st))
    R.table(header, rows, widths, colors, px=8)
    # violations
    R.heading(tr("qc_r_violations"))
    runs = qc.violation_runs(ev)
    if not runs:
        R.text(tr("qc_r_none"), 10.5)
    else:
        names = {m.id: m.file_name for m in track.measurements}
        R.table([tr("qc_col_date"), "→", "N", tr("qc_col_file"), tr("qc_col_series"), tr("qc_col_rule"),
                 tr("qc_col_message")],
                [[f"{r.first:%Y-%m-%d}" if r.first else "—",
                  f"{r.last:%Y-%m-%d}" if r.last and r.n > 1 else "", str(r.n), names.get(r.first_mid, ""),
                  r.series, r.rule, r.message] for r in runs], [10, 10, 4, 16, 13, 6, 41], px=8)
    R.y += 18
    R.text(tr("qc_r_signature"), 11, False, C_AXIS_TEXT, 4)
    pages = R.page
    R.finish()
    return pages


def export_qc_pdf(track: "qc.QCTrack", path, ev: Optional["qc.QCEvaluation"] = None,
                  metrics: Optional[Sequence[str]] = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    w = QPdfWriter(str(path))
    w.setResolution(300)
    w.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(0, 0, 0, 0)))
    w.setTitle(f"{tr('qc_report_title')} — {track.name}")
    w.setCreator("SpectraMaster")
    paint_qc_report(w, track, ev, metrics)
    return path

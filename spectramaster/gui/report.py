"""Printable spectrum reports: print, print preview and PDF export.

The report is a ``QTextDocument`` (HTML: header, information table, analysis
tables with header rows repeated on every page, notes, signature block) laid
out in CSS pixels (96 per inch) and painted page by page onto any paged paint
device (``QPrinter`` for paper / preview / PDF, ``QPdfWriter`` in the batch
worker thread) with a footer (page X of Y, file name, credit, print time).

The spectrum plot is painted by a :class:`~.plot.PlotRenderer` - independent
of the on-screen widget size - either as vector graphics (custom text object
painted straight onto the printer) or as a >= 300 dpi image.

Nothing here touches QWidgets, so reports can be produced in a worker thread.
"""
from __future__ import annotations

import html
import json
import math
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Sequence

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt, QUrl
from PySide6.QtGui import (QAbstractTextDocumentLayout, QColor, QFont, QFontDatabase, QFontMetricsF,
                           QImage, QPageLayout, QPageSize, QPainter, QPen, QPyTextObject,
                           QTextCharFormat, QTextDocument, QTextFormat, QTextImageFormat, QTextOption)

from .. import __version__
from ..model import Spectrum
from . import context_strings, i18n, identification_library  # noqa: F401 (strings merged into i18n)
from .plot import PlotRenderer, Y_LINEAR, Y_LOG, Y_MODES, Y_SQRT, format_count

CSS_DPI = 96.0                       # document units: CSS pixels
IMAGE_DPI = 300.0                    # raster plot resolution
CREDIT = "Edrees F. Hery"
PLOT_SIZES = {"small": 0.24, "medium": 0.36, "large": 0.50, "page": 1.0}
PAPERS = {"A4": QPageSize.A4, "Letter": QPageSize.Letter}
LANG_CHOICES = ("ui", "ar", "en")
FONT_FAMILIES = ("Segoe UI", "Tahoma", "Arial", "DejaVu Sans")
CATEGORIES = ("natural", "fission", "activation", "calibration", "medical", "industrial")
_LRI, _PDI = "⁦", "⁩"
PLOT_MARKER = "@@SPECTRAMASTER_PLOT@@"
PLOT_OBJECT_TYPE = QTextFormat.UserObject + 17
PROP_W, PROP_H = QTextFormat.UserProperty + 1, QTextFormat.UserProperty + 2

C_ACCENT = "#1f4e79"
C_RULE = "#9aa5b1"
C_HEAD_BG = "#e3ebf5"
C_ALT_BG = "#f5f7fa"
C_MUTED = "#5b6773"


# ============================================================================ options
@dataclass
class ReportOptions:
    """Everything the user can choose for a report (persisted as JSON in QSettings)."""
    # header
    header: bool = True
    lab_name: str = ""
    department: str = ""
    address: str = ""
    logo: bool = True
    logo_path: str = ""
    title: str = ""                   # "" = default title in the report language
    report_no: str = ""               # report number / sample reference
    operator: str = ""
    show_date: bool = True
    # sections
    info: bool = True
    plot: bool = True
    plot_view: str = "current"        # current | full
    plot_scale: str = "current"       # current | linear | log | sqrt
    plot_axis: str = "current"        # current | energy | channel
    plot_labels: bool = True
    plot_rois: bool = True
    plot_overlays: bool = True
    plot_size: str = "medium"         # small | medium | large | page
    plot_vector: bool = True          # False: 300 dpi image
    peaks: bool = True
    peaks_identified_only: bool = False
    peaks_min_sig: float = 0.0
    nuclides: bool = True
    nuc_min_conf: int = 0             # percent
    nuc_hide_background: bool = False
    rois: bool = True
    context: bool = True              # library, detector, concentrations, workflow status (session)
    extra: bool = False
    notes_on: bool = False
    notes: str = ""
    signatures: bool = True
    sig_prepared: str = ""
    sig_reviewed: str = ""
    sig_approved: str = ""
    # footer
    footer_pages: bool = True
    footer_file: bool = True
    footer_credit: bool = True
    footer_datetime: bool = True
    # page
    paper: str = "A4"
    landscape: bool = False
    margin_mm: float = 15.0
    language: str = "ui"              # ui | ar | en

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "ReportOptions":
        base = cls()
        if not isinstance(d, dict):
            return base
        kw = {}
        for f in fields(cls):
            if f.name not in d:
                continue
            default = getattr(base, f.name)
            v = d[f.name]
            try:
                if isinstance(default, bool):
                    v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes")
                elif isinstance(default, int):
                    v = int(float(v))
                elif isinstance(default, float):
                    v = float(v)
                else:
                    v = "" if v is None else str(v)
            except (TypeError, ValueError):
                continue
            kw[f.name] = v
        o = replace(base, **kw)
        return o.normalized()

    def normalized(self) -> "ReportOptions":
        o = replace(self)
        if o.plot_view not in ("current", "full"):
            o.plot_view = "current"
        if o.plot_scale not in ("current",) + Y_MODES:
            o.plot_scale = "current"
        if o.plot_axis not in ("current", "energy", "channel"):
            o.plot_axis = "current"
        if o.plot_size not in PLOT_SIZES:
            o.plot_size = "medium"
        if o.paper not in PAPERS:
            o.paper = "A4"
        if o.language not in LANG_CHOICES:
            o.language = "ui"
        o.margin_mm = min(40.0, max(5.0, o.margin_mm))
        o.nuc_min_conf = min(100, max(0, o.nuc_min_conf))
        o.peaks_min_sig = max(0.0, o.peaks_min_sig)
        return o

    def report_language(self) -> str:
        return i18n.language() if self.language == "ui" else self.language

    def wants_analysis(self) -> bool:
        return self.peaks or self.nuclides

    def page_layout(self) -> QPageLayout:
        m = self.margin_mm
        return QPageLayout(QPageSize(PAPERS.get(self.paper, QPageSize.A4)),
                           QPageLayout.Landscape if self.landscape else QPageLayout.Portrait,
                           QMarginsF(m, m, m, m), QPageLayout.Millimeter)


# built-in templates: they only switch sections; header identity / page fields are kept
_SECTIONS_ALL = dict(header=True, info=True, plot=True, peaks=True, nuclides=True, rois=True,
                     extra=False, notes_on=False, signatures=True)
PRESETS: dict[str, dict] = {
    "full": dict(_SECTIONS_ALL, extra=True, plot_size="medium", peaks_identified_only=False),
    "plot_only": dict(header=True, info=False, plot=True, peaks=False, nuclides=False, rois=False,
                      extra=False, notes_on=False, signatures=False, plot_size="page"),
    "nuclides": dict(header=True, info=True, plot=False, peaks=False, nuclides=True, rois=False,
                     extra=False, notes_on=False, signatures=True),
}
PRESET_KEYS = {"full": "rep_preset_full", "plot_only": "rep_preset_plot", "nuclides": "rep_preset_nuc"}

KEY_OPTIONS = "report/options"
KEY_TEMPLATES = "report/templates"


def apply_preset(opts: ReportOptions, preset: str) -> ReportOptions:
    return replace(opts, **PRESETS[preset]).normalized()


def _json_load(raw, default):
    if raw in (None, ""):
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (TypeError, ValueError):
        return default


def load_options(settings) -> ReportOptions:
    return ReportOptions.from_dict(_json_load(settings.get(KEY_OPTIONS, ""), {}))


def save_options(settings, opts: ReportOptions) -> None:
    settings.set(KEY_OPTIONS, json.dumps(opts.to_dict(), ensure_ascii=False))


def _templates(settings) -> dict:
    d = _json_load(settings.get(KEY_TEMPLATES, ""), {})
    return d if isinstance(d, dict) else {}


def template_names(settings) -> list[str]:
    """Names of the user's saved templates (built-in presets are not included)."""
    return sorted(_templates(settings), key=str.lower)


def save_template(settings, name: str, opts: ReportOptions) -> None:
    name = name.strip()
    if not name:
        raise ValueError("empty template name")
    t = _templates(settings)
    t[name] = opts.to_dict()
    settings.set(KEY_TEMPLATES, json.dumps(t, ensure_ascii=False))


def load_template(settings, name: str, base: Optional[ReportOptions] = None) -> Optional[ReportOptions]:
    """A user template by name, or a built-in preset ``"preset:<key>"`` applied to ``base``."""
    if name.startswith("preset:"):
        key = name.split(":", 1)[1]
        if key not in PRESETS:
            return None
        return apply_preset(base or ReportOptions(), key)
    d = _templates(settings).get(name)
    return ReportOptions.from_dict(d) if isinstance(d, dict) else None


def delete_template(settings, name: str) -> bool:
    t = _templates(settings)
    if name not in t:
        return False
    del t[name]
    settings.set(KEY_TEMPLATES, json.dumps(t, ensure_ascii=False))
    return True


# ============================================================================ data
@dataclass
class ReportData:
    """What is reported: one spectrum plus its analysis results and plot state."""
    spectrum: Spectrum
    path: Optional[Path] = None
    fmt_name: str = ""
    peaks: list = field(default_factory=list)
    matches: list = field(default_factory=list)
    analysed: bool = False
    identified: bool = True
    analysis_error: str = ""
    plot: Optional[PlotRenderer] = None     # snapshot of the on-screen plot (zoom, ROIs, overlays)
    index: int = 0                          # spectrum number inside a multi-spectrum file
    count: int = 1
    # laboratory context, as stored / computed in the GUI (nothing is recalculated for the report)
    library: Optional[str] = None           # identification library (analysis.library.APPLICATIONS key)
    has_session: bool = False               # an analysis session belongs to the spectrum
    detector: Optional[dict] = None         # DetectorProfile snapshot of the session
    geometry: Optional[dict] = None         # MeasurementGeometry snapshot of the session
    mass_basis: Optional[str] = None        # sample mass basis (dry / wet) of the concentrations
    concentration: Optional[dict] = None    # activity.concentrations() of the session's activities
    statuses: list = field(default_factory=list)   # workflow statuses {code, level, message}

    @property
    def file_name(self) -> str:
        if self.path is not None:
            return Path(self.path).name
        return Path(self.spectrum.source_path).name if self.spectrum.source_path else ""

    @property
    def file_path(self) -> str:
        return str(self.path) if self.path is not None else (self.spectrum.source_path or "")


# ============================================================================ helpers
def pick_font_family() -> str:
    try:
        fams = set(QFontDatabase.families())
    except Exception:  # pragma: no cover - font database unavailable
        fams = set()
    for f in FONT_FAMILIES:
        if f in fams:
            return f
    return "Sans Serif"


def esc(text) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def ltr(text: str) -> str:
    """Left-to-right isolate: numbers with ± / units / paths stay readable in RTL tables."""
    return f"{_LRI}{text}{_PDI}" if text else text


def _f(v, fmt="{:.2f}") -> str:
    return "" if v is None else fmt.format(v)


def _superscript(n: int) -> str:
    return str(n).translate(str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹"))


def format_poly(coeffs: Sequence[float], var: str = "ch", lhs: str = "E", unit: str = "keV") -> str:
    terms: list[str] = []
    for power, c in enumerate(coeffs):
        if power and c == 0:
            continue
        num = f"{abs(c):.6g}" if terms else f"{c:.6g}"
        term = num if power == 0 else (f"{num}·{var}" if power == 1 else f"{num}·{var}{_superscript(power)}")
        terms.append((("− " if c < 0 else "+ ") + term) if terms else term)
    return f"{lhs} = " + " ".join(terms) + (f" {unit}" if unit else "")


# ============================================================================ plot object
class PlotTextObject(QPyTextObject):
    """Custom QTextDocument object painting the spectrum plot as vector graphics."""

    def __init__(self, renderer: PlotRenderer, parent=None):
        super().__init__(parent)
        self.renderer = renderer

    def intrinsicSize(self, doc, pos, fmt):  # noqa: N802 (Qt API)
        return QSizeF(float(fmt.property(PROP_W) or 600), float(fmt.property(PROP_H) or 300))

    def drawObject(self, painter, rect, doc, pos, fmt):  # noqa: N802 (Qt API)
        painter.save()
        painter.setPen(QPen(QColor(C_RULE), 0.8))
        self.renderer.paint(painter, QRectF(rect))
        painter.restore()


# ============================================================================ report
class Report:
    """Builds and paints one report.  ``render(device)`` prints all pages."""

    def __init__(self, data: ReportData, options: ReportOptions, now: Optional[datetime] = None):
        self.data = data
        self.opts = options.normalized()
        self.lang = self.opts.report_language()
        self.rtl = i18n.is_rtl(self.lang)
        self.now = now or datetime.now()
        self.family = pick_font_family()
        self.doc: Optional[QTextDocument] = None
        self.page_count = 0
        self._plot_object: Optional[PlotTextObject] = None
        self._logo_size: Optional[QSizeF] = None
        self.body = QSizeF()

    # ------------------------------------------------------------------ text
    def t(self, key: str, **kw) -> str:
        return i18n.tr_in(self.lang, key, **kw)

    def ltr(self, text: str) -> str:
        return ltr(text) if self.rtl else text

    def num(self, text: str) -> str:
        return esc(self.ltr(text))

    # ------------------------------------------------------------- geometry
    @staticmethod
    def body_size(layout: QPageLayout) -> QSizeF:
        """Paintable area of a page in CSS pixels."""
        r = layout.paintRect(QPageLayout.Point)
        k = CSS_DPI / 72.0
        return QSizeF(r.width() * k, r.height() * k)

    def footer_height(self) -> float:
        any_footer = (self.opts.footer_pages or self.opts.footer_file or self.opts.footer_credit
                      or self.opts.footer_datetime)
        if not any_footer:
            return 0.0
        return QFontMetricsF(self._footer_font()).height() * 2 + 12

    def _footer_font(self) -> QFont:
        return self.px_font(7.0)

    def px_font(self, pt: float, bold: bool = False) -> QFont:
        """Font sized in document pixels: painter fonts must not be re-scaled by the printer DPI."""
        f = QFont(self.family)
        f.setPixelSize(max(6, round(pt * CSS_DPI / 72.0)))
        f.setBold(bold)
        return f

    # ------------------------------------------------------------ document
    def build(self, layout: Optional[QPageLayout] = None) -> QTextDocument:
        layout = layout or self.opts.page_layout()
        full = self.body_size(layout)
        self.body = QSizeF(full.width(), full.height() - self.footer_height())
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setUseDesignMetrics(True)
        font = QFont(self.family)
        font.setPointSizeF(9.0)
        doc.setDefaultFont(font)
        opt = QTextOption()
        opt.setTextDirection(Qt.RightToLeft if self.rtl else Qt.LeftToRight)
        opt.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        doc.setDefaultTextOption(opt)
        doc.setPageSize(self.body)
        doc.setDefaultStyleSheet(self._css())
        self._add_logo(doc)
        doc.setHtml(self.html())
        self._insert_plot(doc)
        # inserting the plot object only re-lays out part of the document: force a full layout
        doc.markContentsDirty(0, doc.characterCount())
        self.doc = doc
        self.page_count = doc.pageCount()
        return doc

    def _css(self) -> str:
        return (f"h1 {{ font-size: 15pt; color: {C_ACCENT}; margin-top: 4px; margin-bottom: 2px; }}"
                f"h2 {{ font-size: 11pt; color: {C_ACCENT}; margin-top: 12px; margin-bottom: 4px; }}"
                f"th {{ background-color: {C_HEAD_BG}; font-weight: 600; }}"
                f".muted {{ color: {C_MUTED}; }}"
                f".note {{ color: #8a5a00; }}")

    def _add_logo(self, doc: QTextDocument) -> None:
        self._logo_size: Optional[QSizeF] = None
        o = self.opts
        if not (o.header and o.logo and o.logo_path):
            return
        img = QImage(o.logo_path)
        if img.isNull():
            return
        h = 64.0
        w = img.width() * h / max(1, img.height())
        if w > 170:
            w, h = 170.0, img.height() * 170.0 / max(1, img.width())
        self._logo_size = QSizeF(w, h)
        doc.addResource(QTextDocument.ImageResource, QUrl("report://logo"), img)

    def _plot_size(self) -> QSizeF:
        w = self.body.width()
        frac = PLOT_SIZES.get(self.opts.plot_size, 0.36)
        if self.opts.plot_size == "page":
            h = self.body.height() - 90
        else:
            h = self.body.height() * frac
            h = min(h, w * 0.75)
        return QSizeF(w - 2, max(140.0, h))

    def make_renderer(self) -> PlotRenderer:
        d, o = self.data, self.opts
        font = self.px_font(8.0)
        if d.plot is not None:
            src = d.plot
            r = PlotRenderer(d.spectrum, font, self.lang)
            r.y_mode, r.auto_y = src.y_mode, src.auto_y
            r.energy_axis = src.energy_axis and r.has_energy()
            r.show_labels = src.show_labels
            r.normalize_overlays = src.normalize_overlays
            r.peaks = list(src.peaks) or list(d.peaks)
            r.rois = list(src.rois)
            for ov in src.overlays:
                r.add_overlay(ov.spec, ov.label, ov.color)
            r.set_view(src.x0, src.x1, src._ylim)
        else:
            r = PlotRenderer(d.spectrum, font, self.lang)
            r.peaks = list(d.peaks)
            r.energy_axis = r.has_energy()
            r.y_mode = Y_LOG
        if not r.peaks and d.peaks:
            r.peaks = list(d.peaks)
        if o.plot_view == "full":
            r.set_view(0, r.num_channels(), None)
        if o.plot_scale != "current" and o.plot_scale != r.y_mode:
            r.y_mode = o.plot_scale
            r._ylim = None
        if o.plot_axis == "energy":
            r.energy_axis = r.has_energy()
        elif o.plot_axis == "channel":
            r.energy_axis = False
        r.show_labels = o.plot_labels
        if not o.plot_rois:
            r.rois = []
        if not o.plot_overlays:
            r.overlays = []
        r.highlight = None
        r._update_margins()
        return r

    def _insert_plot(self, doc: QTextDocument) -> None:
        cur = doc.find(PLOT_MARKER)
        if cur.isNull():
            return
        renderer = self.make_renderer()
        size = self._plot_size()
        if self.opts.plot_size == "page":
            # full page: use what is left of the page the plot starts on
            h = self.body.height()
            top = doc.documentLayout().blockBoundingRect(cur.block()).top() % h
            size.setHeight(max(220.0, h - top - 24))
        if self.opts.plot_vector:
            self._plot_object = PlotTextObject(renderer)
            doc.documentLayout().registerHandler(PLOT_OBJECT_TYPE, self._plot_object)
            fmt = QTextCharFormat()
            fmt.setObjectType(PLOT_OBJECT_TYPE)
            fmt.setProperty(PROP_W, size.width())
            fmt.setProperty(PROP_H, size.height())
            cur.insertText("￼", fmt)
        else:
            scale = IMAGE_DPI / CSS_DPI
            img = renderer.render_image(int(size.width()), int(size.height()), scale)
            doc.addResource(QTextDocument.ImageResource, QUrl("report://plot"), img)
            fmt = QTextImageFormat()
            fmt.setName("report://plot")
            fmt.setWidth(size.width())
            fmt.setHeight(size.height())
            cur.insertImage(fmt)

    # --------------------------------------------------------------- html
    def html(self) -> str:
        o = self.opts
        parts = [f'<html><body dir="{"rtl" if self.rtl else "ltr"}">']
        if o.header:
            parts.append(self._html_header())
        if o.info:
            parts.append(self._html_info())
        if o.plot:
            parts.append(self._html_plot())
        if o.peaks:
            parts.append(self._html_peaks())
        if o.nuclides:
            parts.append(self._html_nuclides())
        if o.rois:
            parts.append(self._html_rois())
        if o.context:
            parts.append(self._html_context())
        if o.extra:
            parts.append(self._html_extra())
        if o.notes_on and o.notes.strip():
            parts.append(self._html_notes())
        if o.signatures:
            parts.append(self._html_signatures())
        parts.append("</body></html>")
        return "".join(p for p in parts if p)

    def _dir(self) -> str:
        return "rtl" if self.rtl else "ltr"

    def _align_start(self) -> str:
        return "right" if self.rtl else "left"

    def _align_end(self) -> str:
        return "left" if self.rtl else "right"

    def _h2(self, key: str, extra: str = "", page_break: bool = False) -> str:
        style = ' style="page-break-before: always;"' if page_break else ""
        text = esc(self.t(key)) + (f' <span class="muted" style="font-size:8.5pt; font-weight:400;">'
                                   f'{extra}</span>' if extra else "")
        return f'<h2 dir="{self._dir()}" align="{self._align_start()}"{style}>{text}</h2>'

    def _table(self, headers: Sequence[str], rows: Sequence[Sequence[str]], widths: Sequence[int] = (),
               aligns: Sequence[str] = (), font_pt: float = 8.0) -> str:
        """Bordered table; header row repeated on every page (``<thead>``). Cells are HTML."""
        out = [f'<table dir="{self._dir()}" width="100%" border="1" cellspacing="0" cellpadding="3" '
               f'style="border-collapse: collapse; border-color: {C_RULE}; border-style: solid; '
               f'font-size: {font_pt}pt;">']
        ths = []
        for i, h in enumerate(headers):
            w = f' width="{widths[i]}%"' if i < len(widths) and widths[i] else ""
            ths.append(f'<th{w} align="center" bgcolor="{C_HEAD_BG}">{esc(h)}</th>')
        out.append("<thead><tr>" + self._cells(ths) + "</tr></thead><tbody>")
        for r, row in enumerate(rows):
            bg = f' bgcolor="{C_ALT_BG}"' if r % 2 else ""
            tds = []
            for i, cell in enumerate(row):
                a = aligns[i] if i < len(aligns) else "center"
                a = {"start": self._align_start(), "end": self._align_end()}.get(a, a)
                tds.append(f'<td align="{a}">{cell}</td>')
            out.append(f"<tr{bg}>" + self._cells(tds) + "</tr>")
        out.append("</tbody></table>")
        return "".join(out)

    def _cells(self, cells: Sequence[str]) -> str:
        """Qt rich text does not mirror table columns: reverse them for right-to-left reports."""
        return "".join(reversed(cells) if self.rtl else cells)

    def _note(self, text: str) -> str:
        return f'<p dir="{self._dir()}" class="note">{esc(text)}</p>'

    # header -------------------------------------------------------------
    def _html_header(self) -> str:
        o = self.opts
        lab = []
        if o.lab_name.strip():
            lab.append(f'<span style="font-size:13pt; font-weight:700; color:{C_ACCENT};">'
                       f'{esc(o.lab_name.strip())}</span>')
        if o.department.strip():
            lab.append(f'<span style="font-size:10pt;">{esc(o.department.strip())}</span>')
        for line in o.address.strip().splitlines():
            if line.strip():
                lab.append(f'<span class="muted" style="font-size:8.5pt;">{esc(line.strip())}</span>')
        meta = []

        def kv(key: str, value: str, isnum: bool = False):
            if value:
                v = self.num(value) if isnum else esc(value)
                meta.append(f'<span class="muted">{esc(self.t(key))}:</span> <b>{v}</b>')
        kv("rep_report_no", o.report_no.strip())
        kv("rep_operator", o.operator.strip())
        if o.show_date:
            kv("rep_date_printed", self.now.strftime("%Y-%m-%d  %H:%M"), True)
        cells = []
        if self._logo_size is not None:
            w, h = self._logo_size.width(), self._logo_size.height()
            cells.append(f'<td width="{int(w) + 12}" valign="middle">'
                         f'<img src="report://logo" width="{w:.0f}" height="{h:.0f}"></td>')
        cells.append(f'<td valign="middle" align="{self._align_start()}">{"<br>".join(lab) or "&nbsp;"}</td>')
        if meta:
            cells.append(f'<td valign="middle" align="{self._align_end()}" style="font-size:8.5pt;">'
                         f'{"<br>".join(meta)}</td>')
        out = [f'<table dir="{self._dir()}" width="100%" cellspacing="0" cellpadding="2" border="0">'
               f'<tr>{self._cells(cells)}</tr></table>']
        title = o.title.strip() or self.t("rep_default_title")
        out.append(f'<hr><h1 dir="{self._dir()}" align="center">{esc(title)}</h1>')
        d = self.data
        sub = d.spectrum.sample_id.strip() or d.file_name
        if sub:
            out.append(f'<p align="center" class="muted" dir="{self._dir()}">{esc(sub)}</p>')
        return "".join(out)

    # information ---------------------------------------------------------
    def info_items(self) -> list[tuple[str, str, bool]]:
        """(label, html value, wide) rows of the spectrum-information table."""
        d, s, t = self.data, self.data.spectrum, self.t
        none = "—"

        def secs(v):
            return self.num(t("seconds", v=f"{v:,.2f}")) if v is not None else none
        items: list[tuple[str, str, bool]] = []
        items.append((t("info_file"), esc(d.file_name) or none, False))
        items.append((t("info_format"), esc(d.fmt_name or s.source_format) or none, False))
        if d.file_path:
            items.append((t("rep_path"), esc(i18n.bidi_path(d.file_path)), True))
        items.append((t("info_sample_id"), esc(s.sample_id.strip()) or none, False))
        if d.count > 1:
            items.append((t("info_spectrum"), self.num(f"{d.index + 1} / {d.count}"), False))
        items.append((t("info_detector"), esc(s.detector.strip()) or none, False))
        items.append((t("info_start"), self.num(s.start_time.strftime("%Y-%m-%d  %H:%M:%S"))
                      if s.start_time else none, False))
        items.append((t("info_live_time"), secs(s.live_time), False))
        items.append((t("info_real_time"), secs(s.real_time), False))
        dt = s.dead_time_percent
        items.append((t("info_dead_time"), self.num(f"{dt:.2f} %") if dt is not None else none, False))
        ch = f"{s.num_channels:,}"
        if s.first_channel:
            ch += f"  ({s.first_channel} – {s.first_channel + s.num_channels - 1})"
        items.append((t("info_channels"), self.num(ch), False))
        items.append((t("info_total"), self.num(format_count(s.total_counts)), False))
        if s.live_time:
            items.append((t("rep_total_rate"), self.num(f"{s.total_counts / s.live_time:,.4g} cps"), False))
        items.append((t("info_calibration"), self.num(format_poly(s.energy_coeffs)) if s.energy_coeffs
                      else esc(t("uncalibrated")), True))
        items.append((t("rep_fwhm_cal"), self.num(format_poly(s.fwhm_coeffs, lhs="FWHM"))
                      if s.fwhm_coeffs else none, True))
        if s.description.strip():
            items.append((t("info_description"), esc(s.description.strip()).replace("\n", "<br>"), True))
        return items

    def _html_info(self) -> str:
        items = self.info_items()
        rows: list[str] = []
        pending: list[tuple[str, str]] = []
        lab_style = f'bgcolor="{C_HEAD_BG}" align="{self._align_start()}"'
        val_align = f'align="{self._align_start()}"'

        def flush():
            if not pending:
                return
            cells = []
            for k, v in pending:
                cells += [f'<td width="17%" {lab_style}>{esc(k)}</td>', f'<td width="33%" {val_align}>{v}</td>']
            if len(pending) == 1:
                cells += ['<td width="17%"></td>', '<td width="33%"></td>']
            rows.append(f"<tr>{self._cells(cells)}</tr>")
            pending.clear()
        for label, value, wide in items:
            if wide:
                flush()
                rows.append("<tr>" + self._cells([f'<td width="17%" {lab_style}>{esc(label)}</td>',
                                                  f'<td colspan="3" {val_align}>{value}</td>']) + "</tr>")
            else:
                pending.append((label, value))
                if len(pending) == 2:
                    flush()
        flush()
        return (self._h2("info_title") +
                f'<table dir="{self._dir()}" width="100%" border="1" cellspacing="0" cellpadding="3" '
                f'style="border-collapse: collapse; border-color: {C_RULE}; border-style: solid; '
                f'font-size: 8.5pt;">{"".join(rows)}</table>')

    # plot ----------------------------------------------------------------
    def _plot_caption(self) -> str:
        r = self.make_renderer()
        t = self.t
        parts = []
        full = r.x0 <= 0 and r.x1 >= r.num_channels()
        if r.energy_axis and r.has_energy():
            e0, e1 = r.energy_at_pos(r.x0), r.energy_at_pos(r.x1)
            # each end is its own LTR isolate; in Arabic the range reads "من 2.8 إلى 2771.7 keV" so the
            # order is unambiguous for a right-to-left reader (a bare "a – b" isolate reads b first)
            rng = t("rep_range", a=self.num(f"{e0:.1f}"), b=self.num(f"{e1:.1f} keV"))
        else:
            c0, c1 = r.channel_at_pos(r.x0), r.channel_at_pos(r.x1)
            rng = esc(t("axis_channel")) + " " + t("rep_range", a=self.num(f"{c0:.0f}"), b=self.num(f"{c1:.0f}"))
        parts.append(esc(t("rep_full_view") if full else t("rep_zoom_view")) + ": " + rng)
        parts.append(esc(t({Y_LINEAR: "rep_scale_linear", Y_LOG: "rep_scale_log",
                            Y_SQRT: "rep_scale_sqrt"}.get(r.y_mode, "rep_scale_linear"))))
        if r.overlays:
            parts.append(esc(t("rep_overlays", n=len(r.overlays))))
        return " · ".join(parts)

    def _html_plot(self) -> str:
        page = self.opts.plot_size == "page" and self.opts.info
        return (self._h2("rep_plot", self._plot_caption(), page_break=page) +
                f'<p align="center" dir="ltr" style="margin-top:2px; margin-bottom:2px;">{PLOT_MARKER}</p>')

    # analysis --------------------------------------------------------------
    def filtered_peaks(self) -> list:
        o = self.opts
        out = []
        for pk in self.data.peaks:
            if o.peaks_identified_only and not (pk.nuclide or "").strip():
                continue
            if o.peaks_min_sig and (pk.significance or 0) < o.peaks_min_sig:
                continue
            out.append(pk)
        return out

    def filtered_matches(self) -> list:
        o = self.opts
        out = []
        for m in self.data.matches:
            if 100.0 * (m.confidence or 0) + 1e-9 < o.nuc_min_conf:
                continue
            if o.nuc_hide_background and getattr(m, "background", False):
                continue
            out.append(m)
        return out

    def _not_analysed(self) -> str:
        d = self.data
        if d.analysis_error:
            return self._note(self.t("rep_analysis_failed", msg=d.analysis_error))
        return self._note(self.t("rep_not_analysed"))

    def _html_peaks(self) -> str:
        d, t = self.data, self.t
        if not d.analysed:
            return self._h2("rep_peaks") + self._not_analysed()
        peaks = self.filtered_peaks()
        filt = []
        if self.opts.peaks_identified_only:
            filt.append(t("rep_identified_only"))
        if self.opts.peaks_min_sig:
            filt.append(t("rep_min_sig", v=f"{self.opts.peaks_min_sig:g}"))
        extra = esc(t("rep_shown_of", n=len(peaks), m=len(d.peaks)) + (" · " + " · ".join(filt) if filt else ""))
        if not peaks:
            return self._h2("rep_peaks", extra) + self._note(t("rep_no_peaks"))
        headers = [t("pk_col_n"), t("pk_col_energy"), t("pk_col_channel"), t("pk_col_fwhm"),
                   t("pk_col_net"), t("rep_col_unc_pct"), t("pk_col_cps"), t("pk_col_sig"), t("pk_col_nuclide")]
        rows = []
        for i, pk in enumerate(peaks):
            unc = 100.0 * pk.net_area_unc / pk.net_area if pk.net_area > 0 else None
            nuc = (pk.nuclide or "") + (f" ({pk.line_energy:.1f})" if pk.nuclide and pk.line_energy else "")
            nuc = self.num(nuc)
            if pk.note:
                nuc += f' <span class="muted">{esc(pk.note)}</span>'
            rows.append([
                str(self.data.peaks.index(pk) + 1),
                self.num(_f(pk.energy)), self.num(_f(pk.centroid)), self.num(_f(pk.fwhm_kev)),
                self.num(f"{pk.net_area:,.0f} ± {pk.net_area_unc:,.0f}"),
                self.num(_f(unc, "{:.1f}")), self.num(_f(pk.count_rate, "{:.4g}")),
                self.num(_f(pk.significance, "{:.1f}")), nuc])
        return self._h2("rep_peaks", extra) + self._table(
            headers, rows, widths=(4, 10, 10, 8, 16, 8, 9, 12, 23),
            aligns=("center",) * 8 + ("start",))

    def _category(self, cat: str) -> str:
        return i18n.category_label(cat, self.lang)

    def _html_nuclides(self) -> str:
        d, t, o = self.data, self.t, self.opts
        if not d.analysed:
            return self._h2("rep_nuclides") + self._not_analysed()
        if not d.identified:
            return self._h2("rep_nuclides") + self._note(t("rep_uncalibrated"))
        ms = self.filtered_matches()
        filt = []
        if o.nuc_min_conf:
            filt.append(t("rep_min_conf", v=o.nuc_min_conf))
        if o.nuc_hide_background:
            filt.append(t("rep_no_background"))
        if d.library:
            filt.insert(0, t("idl_header", name=self.library_name(d.library)))
        extra = esc(t("rep_shown_of", n=len(ms), m=len(d.matches)) + (" · " + " · ".join(filt) if filt else ""))
        if not ms:
            return self._h2("rep_nuclides", extra) + self._note(t("rep_no_nuclides"))
        headers = [t("nuc_col_name"), t("nuc_col_conf"), t("nuc_col_half"), t("nuc_col_cat"),
                   t("nuc_col_lines"), t("rep_col_matched_kev"), t("nuc_col_note")]
        rows = []
        for m in ms:
            n_match = len(m.matched)
            n_exp = n_match + len(m.missing)
            kev = ", ".join(f"{e:.1f}" for e, _ in sorted(m.matched, key=lambda x: x[0]))
            notes = []
            if getattr(m, "background", False):
                notes.append(esc(t("nuc_background")))
            lib = [m.note] if m.note else []         # library notes are English: keep them LTR
            series = getattr(m, "series", "") or ""
            if series and series not in (m.note or ""):
                lib.append(series)
            if lib:
                notes.append(self.num("; ".join(lib)))
            rows.append([f"<b>{esc(m.nuclide)}</b>", self.num(f"{100.0 * m.confidence:.0f} %"),
                         self.num(m.half_life or ""), esc(self._category(m.category)),
                         self.num(f"{n_match} / {n_exp}"), self.num(kev), " · ".join(notes)])
        return self._h2("rep_nuclides", extra) + self._table(
            headers, rows, widths=(11, 9, 11, 13, 10, 22, 24),
            aligns=("center", "center", "center", "center", "center", "center", "start"))

    def roi_list(self) -> list:
        p = self.data.plot
        return [r for r in (p.rois if p is not None else []) if r.stats is not None]

    def _html_rois(self) -> str:
        t = self.t
        rois = self.roi_list()
        if not rois:
            return self._h2("rep_rois") + self._note(t("rep_no_rois"))
        headers = [t("roi_col_n"), t("roi_col_start"), t("roi_col_end"), t("roi_col_centroid"),
                   t("roi_col_energy"), t("roi_col_fwhm_kev"), t("roi_col_gross"), t("rep_col_net_unc"),
                   t("roi_col_cps")]
        rows = []
        for i, roi in enumerate(rois):
            st = roi.stats
            cps = "" if st.count_rate is None else f"{st.count_rate:.4g} ± {st.count_rate_unc:.2g}"
            rows.append([str(i + 1), self.num(str(st.start_channel)), self.num(str(st.end_channel)),
                         self.num(_f(st.centroid)), self.num(_f(st.centroid_energy)), self.num(_f(st.fwhm_kev)),
                         self.num(f"{st.gross:,.0f}"), self.num(f"{st.net:,.1f} ± {st.net_unc:,.1f}"),
                         self.num(cps)])
        return self._h2("rep_rois") + self._table(headers, rows, widths=(5, 10, 10, 11, 11, 10, 12, 17, 14))

    # laboratory context ---------------------------------------------------
    def library_name(self, application: str) -> str:
        key = "idl_short_" + application
        return self.t(key) if key in i18n.STRINGS.get("en", {}) else application

    def reportable(self) -> Optional[bool]:
        """False when a workflow status is an error, None without a session."""
        if not self.data.has_session:
            return None
        return not any(s.get("level") == "error" for s in self.data.statuses)

    def _c(self, key: str, **kw) -> str:
        from .context_strings import ctr_in
        return ctr_in(self.lang, key, **kw)

    def context_items(self) -> list[tuple[str, str]]:
        """(label, html value) rows: library, detector, geometry, reportable."""
        d, c = self.data, self._c
        none = "—"
        items = [(c("rep_library"), esc(self.library_name(d.library)) if d.library else esc(c("rep_library_none")))]
        if d.has_session:
            det = d.detector or {}
            if det:
                txt = det.get("name") or det.get("id", "")
                extra = [x for x in (det.get("type"), det.get("serial")) if x]
                if extra:
                    txt += " (" + ", ".join(extra) + ")"
                items.append((c("rep_detector"), self.num(txt)))
            else:
                items.append((c("rep_detector"), none))
            geo = d.geometry or {}
            items.append((c("rep_geometry"), self.num(geo.get("name") or geo.get("id", "")) if geo else none))
            ok = self.reportable()
            colour = "#2e7d32" if ok else "#c62828"
            items.append((c("rep_reportable"), f'<b style="color:{colour};">'
                          f'{esc(c("rep_reportable_yes" if ok else "rep_reportable_no"))}</b>'))
        return items

    def concentration_unit(self) -> str:
        conc = self.data.concentration or {}
        unit = conc.get("unit", "") or ""
        basis = self.data.mass_basis
        if unit.startswith("Bq/kg (") and basis:
            key = "quant_conc_basis_" + basis
            if key in i18n.STRINGS.get("en", {}):
                return f"Bq/kg ({self.t(key).split(' (')[0]})"
        return unit.replace("m3", "m³")

    def concentration_rows(self) -> list[list[str]]:
        """(nuclide, result text, decision, decay factor) rows, as computed (HTML cells)."""
        rows = []
        for r in (self.data.concentration or {}).get("rows", []):
            detected = r.get("value") is not None
            dec = self.t("quant_res_detected" if detected else "quant_res_lt_mda")
            colour = "#14822a" if detected else C_MUTED
            factor = r.get("factor")
            rows.append([f"<b>{esc(r.get('nuclide', ''))}</b>", self.num(r.get("text") or ""),
                         f'<span style="color:{colour};">{esc(dec)}</span>',
                         self.num(f"{factor:.4g}") if isinstance(factor, (int, float)) else ""])
        return rows

    def missing_inputs(self) -> list[str]:
        from .sample_panel import MISSING_KEYS
        out = []
        for m in (self.data.concentration or {}).get("missing", []):
            out.append(self.t("quant_" + MISSING_KEYS[m]) if m in MISSING_KEYS else m)
        return out

    def status_rows(self) -> list[list[str]]:
        from ..lab.workflow import WorkflowStatus
        from .session_io import LEVEL_COLORS, code_title, level_title, status_text
        rows = []
        for st in self.data.statuses:
            ws = WorkflowStatus(st.get("code", ""), st.get("level", "info"), st.get("message", ""))
            colour = LEVEL_COLORS.get(ws.level, C_MUTED)
            rows.append([f'<span style="color:{colour};"><b>{esc(level_title(ws.level, self.lang))}</b></span>',
                         esc(code_title(ws.code, self.lang)), esc(status_text(ws, self.lang))])
        return rows

    def _html_context(self) -> str:
        d, c = self.data, self._c
        lab_style = f'bgcolor="{C_HEAD_BG}" align="{self._align_start()}"'
        rows = "".join("<tr>" + self._cells([f'<td width="30%" {lab_style}>{esc(k)}</td>',
                                             f'<td align="{self._align_start()}">{v}</td>']) + "</tr>"
                       for k, v in self.context_items())
        out = [f'<h2 dir="{self._dir()}" align="{self._align_start()}">{esc(c("rep_title"))}</h2>',
               f'<table dir="{self._dir()}" width="100%" border="1" cellspacing="0" cellpadding="3" '
               f'style="border-collapse: collapse; border-color: {C_RULE}; border-style: solid; '
               f'font-size: 8.5pt;">{rows}</table>']
        if not d.has_session:
            out.append(self._note(c("rep_no_session")))
            return "".join(out)
        conc = d.concentration
        if conc:
            unit = self.concentration_unit()
            out.append(f'<p dir="{self._dir()}"><b>{esc(c("rep_conc", unit=self.ltr(unit)))}</b></p>')
            missing = self.missing_inputs()
            if missing:
                out.append(self._note(c("rep_conc_missing", items="; ".join(missing))))
            notes = [n for n in conc.get("notes", []) if not n.startswith("concentration not computed")]
            if notes:
                out.append(f'<p dir="{self._dir()}" class="muted">{esc(c("rep_conc_notes", notes=""))}'
                           f'{self.num("; ".join(notes))}</p>')
            rows = self.concentration_rows()
            if rows:
                out.append(self._table([c("rep_col_nuclide"), c("rep_col_result"), c("rep_col_decision"),
                                        c("rep_col_factor")], rows, widths=(16, 48, 18, 18)))
        else:
            out.append(f'<p dir="{self._dir()}" class="muted">{esc(c("rep_conc_none"))}</p>')
        if d.statuses:
            out.append(f'<p dir="{self._dir()}"><b>{esc(c("rep_statuses"))}</b></p>')
            out.append(self._table([c("rep_col_level"), c("rep_col_status"), c("rep_col_message")],
                                   self.status_rows(), widths=(14, 26, 60), aligns=("center", "start", "start")))
        out.append(f'<p dir="{self._dir()}" class="muted" style="font-size:7.5pt;">'
                   f'{esc(c("rep_not_recalculated"))}</p>')
        return "".join(out)

    def _html_extra(self) -> str:
        t = self.t
        extra = self.data.spectrum.extra or {}
        if not extra:
            return self._h2("info_extra") + self._note(t("rep_no_extra"))
        rows = []
        for k, val in extra.items():
            if isinstance(val, float):
                text = f"{val:.6g}"
            elif isinstance(val, (list, tuple)):
                text = ", ".join(f"{x:.6g}" if isinstance(x, float) else str(x) for x in val)
            else:
                text = str(val)
            if len(text) > 400:
                text = text[:400] + " …"
            has_arabic = any("؀" <= ch <= "ۿ" for ch in text)
            rows.append([esc(k), esc(text if has_arabic else self.ltr(text))])
        return self._h2("info_extra") + self._table([t("col_key"), t("col_value")], rows,
                                                    widths=(30, 70), aligns=("start", "start"))

    def _html_notes(self) -> str:
        body = "<br>".join(esc(line) for line in self.opts.notes.strip().splitlines())
        return (self._h2("rep_notes") +
                f'<table dir="{self._dir()}" width="100%" border="1" cellspacing="0" cellpadding="6" '
                f'style="border-collapse: collapse; border-color: {C_RULE}; border-style: solid;">'
                f'<tr><td align="{self._align_start()}">{body}</td></tr></table>')

    def _html_signatures(self) -> str:
        o, t = self.opts, self.t
        cols = [("rep_sig_prepared", o.sig_prepared or o.operator), ("rep_sig_reviewed", o.sig_reviewed),
                ("rep_sig_approved", o.sig_approved)]
        line = "_" * 26
        cells = []
        for key, name in cols:
            cells.append(
                f'<td width="33%" valign="top" align="{self._align_start()}">'
                f'<b style="color:{C_ACCENT};">{esc(t(key))}</b><br><br>'
                f'{esc(t("rep_sig_name"))}: {esc(name.strip()) if name.strip() else line}<br><br><br>'
                f'{esc(t("rep_sig_signature"))}: {line}<br><br>'
                f'{esc(t("rep_sig_date"))}: {line}</td>')
        return (self._h2("rep_signatures") +
                f'<table dir="{self._dir()}" width="100%" border="0" cellspacing="0" cellpadding="6" '
                f'style="font-size: 8.5pt;"><tr>{self._cells(cells)}</tr></table>')

    # -------------------------------------------------------------- painting
    def render(self, device, painter: Optional[QPainter] = None, new_page: bool = False) -> int:
        """Paint every page on ``device`` (QPrinter / QPdfWriter). Returns the page count.

        Pass an active ``painter`` (and ``new_page=True``) to append to a combined document.
        """
        layout = device.pageLayout()
        self.build(layout)
        own = painter is None
        if own:
            painter = QPainter()
            if not painter.begin(device):
                raise OSError("cannot start painting on the output device")
        try:
            dpi = float(device.logicalDpiX()) or 300.0
            scale = dpi / CSS_DPI
            n = max(1, self.doc.pageCount())
            self.page_count = n
            w, h = self.body.width(), self.body.height()
            for i in range(n):
                if i > 0 or new_page:
                    device.newPage()
                painter.save()
                painter.scale(scale, scale)
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setRenderHint(QPainter.TextAntialiasing, True)
                painter.save()
                clip = QRectF(0, i * h, w, h)
                painter.translate(0, -i * h)
                painter.setClipRect(clip)
                ctx = QAbstractTextDocumentLayout.PaintContext()
                ctx.clip = clip
                self.doc.documentLayout().draw(painter, ctx)
                painter.restore()
                self._paint_footer(painter, i + 1, n, w, h)
                painter.restore()
        finally:
            if own:
                painter.end()
        return self.page_count

    def footer_texts(self, page: int, pages: int) -> tuple[str, str, str]:
        """(start, centre, end) footer strings for a page."""
        o, t = self.opts, self.t
        start = []
        if o.footer_file and self.data.file_name:
            start.append(self.data.file_name)
        if o.footer_datetime:
            start.append(t("rep_printed_at", dt=self.now.strftime("%Y-%m-%d %H:%M")))
        centre = f"SpectraMaster v{__version__} — {CREDIT}" if o.footer_credit else ""
        end = t("rep_page_of", i=page, n=pages) if o.footer_pages else ""
        return "   ·   ".join(self.ltr(s) for s in start), centre, end

    def _paint_footer(self, p: QPainter, page: int, pages: int, w: float, h: float) -> None:
        if self.footer_height() <= 0:
            return
        start, centre, end = self.footer_texts(page, pages)
        f = self._footer_font()
        fm = QFontMetricsF(f)
        y = h + 6
        p.setPen(QPen(QColor(C_RULE), 0.6))
        p.drawLine(QRectF(0, y, w, 0).topLeft(), QRectF(0, y, w, 0).topRight())
        p.setFont(f)
        p.setPen(QColor(C_MUTED))
        box = QRectF(0, y + 3, w, fm.height() + 2)
        p.setLayoutDirection(Qt.RightToLeft if self.rtl else Qt.LeftToRight)
        a_start = Qt.AlignRight if self.rtl else Qt.AlignLeft
        a_end = Qt.AlignLeft if self.rtl else Qt.AlignRight
        if start:
            p.drawText(box, int(Qt.AlignAbsolute | a_start | Qt.AlignVCenter), start)
        if end:
            p.drawText(box, int(Qt.AlignAbsolute | a_end | Qt.AlignVCenter), end)
        if centre:
            box2 = QRectF(0, y + 3 + fm.height(), w, fm.height() + 2)
            p.setFont(self.px_font(6.5))
            p.setPen(QColor("#8a96a3"))
            p.drawText(box2, int(Qt.AlignHCenter | Qt.AlignVCenter), centre)


# ============================================================================ convenience
def configure_printer(printer, opts: ReportOptions) -> None:
    """Paper size, orientation and margins of a QPrinter / QPdfWriter from the options."""
    printer.setPageLayout(opts.page_layout())


def export_pdf(path, data: ReportData, opts: ReportOptions, title: str = "") -> int:
    """Write one report to a PDF file (QPrinter in PdfFormat; no physical printer needed)."""
    from PySide6.QtPrintSupport import QPrinter
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(str(path))
    printer.setCreator(f"SpectraMaster {__version__}")
    printer.setDocName(title or data.file_name or "SpectraMaster report")
    configure_printer(printer, opts)
    return Report(data, opts).render(printer)


def pdf_writer(path, opts: ReportOptions, title: str = ""):
    """QPdfWriter (usable in worker threads) configured for the options."""
    from PySide6.QtGui import QPdfWriter
    w = QPdfWriter(str(path))
    w.setResolution(600)
    w.setCreator(f"SpectraMaster {__version__}")
    w.setTitle(title or "SpectraMaster report")
    w.setPageLayout(opts.page_layout())
    return w


def analyse_spectrum(spec: Spectrum, application: str = "all") -> tuple[list, list, bool]:
    """Peak search + identification with the engine functions looked up at call time;
    `application`: the identification library (analysis.library.APPLICATIONS)."""
    import types
    from .. import analysis as engine
    find_peaks, identify = engine.find_peaks, engine.identify
    if isinstance(find_peaks, types.ModuleType):
        find_peaks = find_peaks.find_peaks
    if isinstance(identify, types.ModuleType):
        identify = identify.identify
    peaks = list(find_peaks(spec) or [])
    identified = bool(spec.energy_coeffs)
    matches = list(identify(spec, peaks, application=application) or []) if identified else []
    return peaks, matches, identified


def make_batch_data(path: Path, analyse: bool, in_fmt=None,
                    cancelled: Callable[[], bool] = lambda: False,
                    application: str = "all") -> list[ReportData]:
    """Read a file and (optionally) analyse each spectrum in it, for batch reports."""
    from ..convert import read_spectra
    spectra, used = read_spectra(Path(path), in_fmt)
    out = []
    for k, s in enumerate(spectra):
        if cancelled():
            break
        if not s.source_path:
            s.source_path = str(path)
        d = ReportData(spectrum=s, path=Path(path), fmt_name=used.name if used else "",
                       index=k, count=len(spectra))
        if analyse:
            try:
                d.peaks, d.matches, d.identified = analyse_spectrum(s, application)
                d.analysed = True
                d.library = application if d.identified else None
            except Exception as exc:  # report the failure in the PDF, never abort the batch
                d.analysis_error = f"{type(exc).__name__}: {exc}"
        out.append(d)
    return out

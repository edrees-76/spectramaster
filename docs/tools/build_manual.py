"""Build the user manuals: docs/manual_{ar,en}.html and docs/SpectraMaster_User_Manual_{AR,EN}.pdf.

    python docs/tools/build_manual.py [ar|en ...] [--html-only]

Sources: docs/tools/src/manual_{ar,en}.html (body only, with {{PLACEHOLDERS}}).  Tables that
must match the program (formats, shortcuts, CLI help, version) are generated from the code.

PDF: printed by headless Chrome / Edge (Chromium renders Arabic shaping, bidi and RTL tables
correctly and supports @page margin boxes for page numbers).  Two passes: the first finds the
page of every heading (invisible markers), the second fills the table-of-contents page numbers.
PDF bookmarks and metadata are added with PyMuPDF.  Sample pages are rendered to PNG in
scratch_manual/ for checking.
"""
from __future__ import annotations

import argparse
import html
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
SRC = DOCS / "tools" / "src"
PREVIEW = ROOT / "scratch_manual"   # sample page renderings for checking (not shipped)
sys.path.insert(0, str(ROOT))

from spectramaster import __version__  # noqa: E402
from spectramaster.formats import all_formats, load_all  # noqa: E402

PDF_NAMES = {"ar": "SpectraMaster_User_Manual_AR.pdf", "en": "SpectraMaster_User_Manual_EN.pdf"}
CHROME_CANDIDATES = [
    os.environ.get("SM_CHROME", ""),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

T = {
    "en": {"code": "Code", "key": "Key", "name": "Format", "ext": "Extensions", "read": "Read",
           "write": "Write", "yes": "✓", "no": "—", "keys": "Keys / mouse", "action": "Action",
           "toc": "Contents", "title": "SpectraMaster — User Manual", "page": "Page",
           "footer": "SpectraMaster {v} — User Manual"},
    "ar": {"code": "الرمز", "key": "المفتاح", "name": "الصيغة", "ext": "الامتدادات", "read": "قراءة",
           "write": "كتابة", "yes": "✓", "no": "—", "keys": "المفاتيح / الفأرة", "action": "الإجراء",
           "toc": "المحتويات", "title": "SpectraMaster — دليل المستخدم", "page": "صفحة",
           "footer": "SpectraMaster {v} — دليل المستخدم"},
}

# extra keyboard shortcuts of the menus (not in i18n.SHORTCUTS, which lists the plot gestures)
MENU_SHORTCUTS = [
    ("Ctrl + O", "Open a spectrum (with preview)", "فتح طيف (مع المعاينة)"),
    ("Ctrl + M", "Select multiple files to convert", "تحديد عدة ملفات للتحويل"),
    ("Ctrl + D", "Convert a folder", "تحويل مجلد"),
    ("Ctrl + I", "Open input files as (input format)", "فتح ملفات الإدخال بصيغة (صيغة الإدخال)"),
    ("Ctrl + S, Ctrl + Shift + S", "Save As (choose the output format)", "حفظ باسم (اختيار صيغة الإخراج)"),
    ("Ctrl + P", "Print report", "طباعة التقرير"),
    ("Ctrl + Shift + P", "Export report as PDF", "تصدير التقرير بصيغة PDF"),
    ("Ctrl + Shift + F", "Archive search", "البحث في الأرشيف"),
    ("F1", "User manual in the interface language", "دليل المستخدم بلغة الواجهة"),
    ("Alt + F4", "Exit", "خروج"),
]


# ------------------------------------------------------------------ generated blocks
def formats_table(lang: str) -> str:
    load_all()
    t = T[lang]
    rows = []
    for f in all_formats():
        ext = " ".join("*" + e for e in f.extensions)
        rows.append(
            f"<tr><td class='num'>{f.code}</td><td class='ltr'><code>{html.escape(f.key)}</code></td>"
            f"<td class='ltr'>{html.escape(f.name)}</td><td class='ltr'>{html.escape(ext)}</td>"
            f"<td class='c'>{t['yes'] if f.can_read else t['no']}</td>"
            f"<td class='c'>{t['yes'] if f.can_write else t['no']}</td></tr>")
    head = (f"<tr><th>{t['code']}</th><th>{t['key']}</th><th>{t['name']}</th><th>{t['ext']}</th>"
            f"<th>{t['read']}</th><th>{t['write']}</th></tr>")
    n_r = sum(1 for f in all_formats() if f.can_read)
    n_w = sum(1 for f in all_formats() if f.can_write)
    cap = (f"{len(all_formats())} formats — {n_r} readable, {n_w} writable" if lang == "en"
           else f"{len(all_formats())} صيغة — {n_r} قابلة للقراءة، و{n_w} قابلة للكتابة")
    return (f"<table class='grid formats'><caption>{cap}</caption><thead>{head}</thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def shortcuts_table(lang: str) -> str:
    from spectramaster.gui.i18n import SHORTCUT_KEYS_AR, SHORTCUTS
    t = T[lang]
    rows = []
    for keys, en, ar in list(SHORTCUTS) + MENU_SHORTCUTS:
        k = SHORTCUT_KEYS_AR.get(keys, keys) if lang == "ar" else keys
        rows.append(f"<tr><td class='keys'><span class='ltr-i'>{html.escape(k)}</span></td>"
                    f"<td>{html.escape(ar if lang == 'ar' else en)}</td></tr>")
    return (f"<table class='grid shortcuts'><thead><tr><th>{t['keys']}</th><th>{t['action']}</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def cli_reference() -> str:
    from spectramaster.cli import build_parser
    p = build_parser()
    out = [f"<pre class='cli'>{html.escape(_strip_prog(p.format_help()))}</pre>"]
    sub = next(a for a in p._actions if a.__class__.__name__ == "_SubParsersAction")
    for name, sp in sub.choices.items():
        out.append(f"<h4 class='cli-h' id='cli-{name}'><code>{name}</code></h4>"
                   f"<pre class='cli'>{html.escape(_strip_prog(sp.format_help()))}</pre>")
    return "\n".join(out)


def _strip_prog(text: str) -> str:
    return text.replace("usage: spectramaster", "usage: smconvert")


def substitute(src: str, lang: str) -> str:
    rep = {
        "{{VERSION}}": __version__,
        "{{BUILD_DATE}}": date.today().isoformat(),
        "{{FORMATS_TABLE}}": formats_table(lang),
        "{{SHORTCUTS_TABLE}}": shortcuts_table(lang),
        "{{CLI_REFERENCE}}": cli_reference(),
    }
    for k, v in rep.items():
        src = src.replace(k, v)
    # key combinations (<kbd>Ctrl</kbd>+<kbd>O</kbd>) stay left-to-right inside Arabic text
    src = re.sub(r"(<kbd>[^<]*</kbd>(?:\s*\+\s*<kbd>[^<]*</kbd>)+)", r"<span class='ltr-i'>\1</span>", src)
    return src


# ------------------------------------------------------------------ TOC
HEAD_RE = re.compile(r"<h([23])([^>]*)\sid=\"([^\"]+)\"([^>]*)>(.*?)</h\1>", re.S)


def headings(body: str) -> list[tuple[int, str, str]]:
    out = []
    for m in HEAD_RE.finditer(body):
        text = re.sub(r"<[^>]+>", "", m.group(5)).strip()
        out.append((int(m.group(1)), m.group(3), text))
    return out


def toc_html(body: str, lang: str, pages: dict[str, int] | None) -> str:
    items = []
    for level, hid, text in headings(body):
        pg = pages.get(hid, "") if pages else "00"
        items.append(f"<li class='toc{level}'><a href='#{hid}'><span class='t'>{html.escape(text)}</span>"
                     f"<span class='dots'></span><span class='pg'>{pg}</span></a></li>")
    return f"<nav class='toc' id='toc'><h2 class='toc-title'>{T[lang]['toc']}</h2><ol>{''.join(items)}</ol></nav>"


def add_markers(body: str) -> str:
    def rep(m):
        return (f"<h{m.group(1)}{m.group(2)} id=\"{m.group(3)}\"{m.group(4)}>"
                f"<span class='mk'>@@{m.group(3)}@@</span>{m.group(5)}</h{m.group(1)}>")
    return HEAD_RE.sub(rep, body)


# ------------------------------------------------------------------ page assembly
CSS_FILE = DOCS / "tools" / "manual.css"


def page(lang: str, body: str, pages: dict[str, int] | None, markers: bool) -> str:
    css = CSS_FILE.read_text(encoding="utf-8")
    t = T[lang]
    css = css.replace("{{FOOTER}}", t["footer"].format(v=__version__)).replace("{{PAGE}}", t["page"])
    css = css.replace("{{OF}}", "من" if lang == "ar" else "of")
    toc = toc_html(body, lang, pages)
    main = body.replace("{{TOC}}", toc)
    if markers:
        main = add_markers(main)
    d = "rtl" if lang == "ar" else "ltr"
    return (f"<!doctype html>\n<html lang='{lang}' dir='{d}'>\n<head>\n<meta charset='utf-8'>\n"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
            f"<title>{t['title']}</title>\n<meta name='author' content='Edrees F. Hery'>\n"
            f"<style>\n{css}\n</style>\n</head>\n<body class='{lang}'>\n{main}\n</body>\n</html>\n")


# ------------------------------------------------------------------ PDF
def chrome() -> str:
    for c in CHROME_CANDIDATES:
        if c and Path(c).is_file():
            return c
    raise SystemExit("Chrome / Edge not found (set SM_CHROME to chrome.exe or msedge.exe)")


def print_pdf(html_path: Path, pdf_path: Path) -> None:
    # Chrome does not always overwrite an existing PDF (the old file was then read back as the
    # new one): print to a fresh file and replace
    prof = Path(tempfile.mkdtemp(prefix="sm_chrome_"))
    new = pdf_path.with_name(pdf_path.stem + ".printing.pdf")
    new.unlink(missing_ok=True)
    try:
        cmd = [chrome(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
               "--allow-file-access-from-files", f"--user-data-dir={prof}",
               f"--print-to-pdf={new}", html_path.resolve().as_uri()]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    if not new.is_file():
        raise SystemExit(f"PDF not written: {pdf_path}")
    new.replace(pdf_path)


def marker_pages(pdf_path: Path) -> dict[str, int]:
    import pymupdf
    doc = pymupdf.open(str(pdf_path))
    pages: dict[str, int] = {}
    for i, pg in enumerate(doc, start=1):
        for m in re.finditer(r"@@([A-Za-z0-9_.:-]+)@@", pg.get_text()):
            pages.setdefault(m.group(1), i)
    doc.close()
    return pages


def finish_pdf(pdf_path: Path, body: str, pages: dict[str, int], lang: str) -> int:
    import pymupdf
    doc = pymupdf.open(str(pdf_path))
    toc = [[lvl - 1, text, pages[hid]] for lvl, hid, text in headings(body) if hid in pages]
    if toc:
        doc.set_toc(toc)
    doc.set_metadata({"title": T[lang]["title"] + f" v{__version__}", "author": "Edrees F. Hery",
                      "subject": "SpectraMaster user manual", "creator": "SpectraMaster docs/tools/build_manual.py",
                      "keywords": "gamma spectrometry, spectrum conversion, DataMaster, SpectraMaster"})
    tmp = pdf_path.with_suffix(".tmp.pdf")
    doc.save(str(tmp), garbage=3, deflate=True)
    n = doc.page_count
    doc.close()
    tmp.replace(pdf_path)
    return n


def render_previews(pdf_path: Path, lang: str, pages: list[int], dpi: int = 80) -> list[Path]:
    import pymupdf
    PREVIEW.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(pdf_path))
    outs = []
    for p in pages:
        if 1 <= p <= doc.page_count:
            out = PREVIEW / f"{lang}_p{p:02d}.png"
            doc[p - 1].get_pixmap(dpi=dpi).save(str(out))
            outs.append(out)
    doc.close()
    return outs


def build(lang: str, html_only: bool = False) -> None:
    src = (SRC / f"manual_{lang}.html").read_text(encoding="utf-8")
    body = substitute(src, lang)
    out_html = DOCS / f"manual_{lang}.html"
    if html_only:
        out_html.write_text(page(lang, body, None, False), encoding="utf-8")
        print(out_html)
        return
    # pass 1: markers -> page numbers
    tmp_html = DOCS / f"_tmp_manual_{lang}.html"
    tmp_pdf = DOCS / f"_tmp_manual_{lang}.pdf"
    try:
        tmp_html.write_text(page(lang, body, None, True), encoding="utf-8")
        print_pdf(tmp_html, tmp_pdf)
        pages = marker_pages(tmp_pdf)
    finally:
        tmp_html.unlink(missing_ok=True)
        tmp_pdf.unlink(missing_ok=True)
    missing = [h for _, h, _ in headings(body) if h not in pages]
    if missing:
        print("  warning: headings without page:", missing)
    # pass 2: final
    out_html.write_text(page(lang, body, pages, False), encoding="utf-8")
    pdf = DOCS / PDF_NAMES[lang]
    print_pdf(out_html, pdf)
    check = marker_pages(pdf)   # no markers expected in the final file
    if check:
        print("  warning: markers left in the PDF:", list(check)[:5])
    n = finish_pdf(pdf, body, pages, lang)
    print(f"{out_html.name}  {pdf.name}: {n} pages")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("langs", nargs="*", default=["ar", "en"])
    ap.add_argument("--html-only", action="store_true")
    ap.add_argument("--preview", default="", help="comma separated page numbers to render to PNG")
    a = ap.parse_args()
    for lg in a.langs:
        build(lg, a.html_only)
        if a.preview and not a.html_only:
            pp = [int(x) for x in a.preview.split(",") if x.strip()]
            for o in render_previews(DOCS / PDF_NAMES[lg], lg, pp):
                print("  preview", o)

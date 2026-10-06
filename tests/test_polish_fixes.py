"""Regression tests for the manual-writing polish pass (bidi, wording, CLI output, archive article)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from spectramaster import cli
from spectramaster.analysis.library import load_library
from spectramaster.model import Spectrum
from spectramaster.tools.archive_db import ArchiveIndex, normalize_text, strip_article

LRI, PDI, LRM = "\u2066", "\u2069", "\u200e"


# ------------------------------------------------------------------ 2 / 3 / 4: bidi helpers
def test_bidi_path_keeps_arabic_segments_in_order():
    from spectramaster.gui import i18n
    p = "D:\\مجلد أول\\مجلد ثان\\شاي.S0"
    shown = i18n.bidi_path(p)
    assert shown.startswith(LRI) and shown.endswith(PDI)
    assert shown.count(LRM) == p.count("\\")          # one LRM after every separator
    assert i18n.strip_bidi(shown) == p
    assert i18n.bidi_path("") == "" and i18n.ltr("") == ""
    assert i18n.ltr("+0.67") == LRI + "+0.67" + PDI


def test_bidi_path_visual_order():
    """Rendered with Qt in an RTL paragraph, the folders appear left-to-right in path order."""
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QTextLayout, QTextOption
    from PySide6.QtWidgets import QApplication
    from spectramaster.gui import i18n
    QApplication.instance() or QApplication([])
    text = "ملف " + i18n.bidi_path("D:\\أب\\جد\\x.S0")

    def x_of(s, i):
        lay = QTextLayout(s, QFont("Segoe UI", 12))
        o = QTextOption()
        o.setTextDirection(Qt.RightToLeft)
        lay.setTextOption(o)
        lay.beginLayout()
        lay.createLine().setLineWidth(2000)
        lay.endLayout()
        runs = lay.glyphRuns(i, 1)
        return runs[0].positions()[0].x() + runs[0].boundingRect().x() * 0 if runs else None

    xa, xj, xd = x_of(text, text.index("أ")), x_of(text, text.index("ج")), x_of(text, text.index("D"))
    if None in (xa, xj, xd):
        pytest.skip("no glyphs (fonts unavailable)")
    assert xd < xa < xj        # D: then أب then جد, left to right


def test_report_caption_range_isolated():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from spectramaster.gui import report as rp
    s = Spectrum(counts=[10.0] * 2048, energy_coeffs=[2.8, 1.35], live_time=100, real_time=101,
                 source_path="D:\\أ ب\\ج د\\x.S0")
    ar = rp.Report(rp.ReportData(spectrum=s), rp.ReportOptions(language="ar"))
    cap = ar._plot_caption()
    assert "من " in cap and " إلى " in cap
    import re
    assert re.search(LRI + r"\d+\.\d" + PDI + " إلى " + LRI + r"\d+\.\d keV" + PDI, cap), cap
    en = rp.Report(rp.ReportData(spectrum=s), rp.ReportOptions(language="en"))
    assert re.search(r"\d+\.\d – \d+\.\d keV", en._plot_caption())
    assert LRM in ar.html()                           # full path shown with separator marks


def test_nuclide_row_isolates_half_life_and_fraction():
    pytest.importorskip("PySide6")
    from spectramaster.analysis import NuclideMatch
    from spectramaster.gui import analysis_panel as ap
    m = NuclideMatch(nuclide="Cs-137", confidence=0.9, matched=[(661.7, None)], missing=[1.0],
                     half_life="30.08 y", category="fission/calibration")
    row = ap.nuclide_row(m)
    assert row[2][0] == LRI + "30.08 y" + PDI
    assert row[4][0] == LRI + "1 / 2" + PDI


# ------------------------------------------------------------------ 5: Qt strings in Arabic
def test_qt_arabic_translator_buttons():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QDialogButtonBox
    QApplication.instance() or QApplication([])
    from spectramaster.gui import qt_ar
    try:
        assert qt_ar.install("ar")
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        assert bb.button(QDialogButtonBox.Cancel).text() == "إلغاء"
        assert bb.button(QDialogButtonBox.Ok).text() == "موافق"
        from PySide6.QtCore import QCoreApplication     # unknown strings must pass through untouched
        assert QCoreApplication.translate("QPlatformTheme", "No such text") == "No such text"
        assert QCoreApplication.translate("SomeContext", "Hello") == "Hello"
    finally:
        qt_ar.install("en")
    bb2 = QDialogButtonBox(QDialogButtonBox.Cancel)
    assert bb2.button(QDialogButtonBox.Cancel).text() == "Cancel"


def test_efficiency_summary_translated():
    from spectramaster.gui import i18n
    from spectramaster.gui.quant_strings import qtr
    pytest.importorskip("PySide6")
    from spectramaster.gui.efficiency_dialog import describe_curve

    class C:
        model, e_ref, order, order_high = "two_branch", 200.0, 3, 2
    old = i18n.language()
    try:
        i18n.set_language("ar")
        text = describe_curve(C())
        assert "two-branch" not in text and "Ec = 200 keV" in text
        assert "two-branch" not in qtr("eff_summary", model=text, chi2=1.0, n=5, e661=0.01, u661=2.0)
        i18n.set_language("en")
        assert describe_curve(C()).startswith("two-branch log-log")
    finally:
        i18n.set_language(old)


# ------------------------------------------------------------------ 6 / 8: strings
def test_integration_intro_has_no_ignored_span_and_wording():
    from spectramaster.gui import i18n
    for lang in ("ar", "en"):
        intro = i18n.STRINGS[lang]["gv_intro"]
        assert "<span dir" not in intro and LRI + "-i input -j output" + PDI in intro
    norm = i18n.STRINGS["ar"]["act_overlay_norm"]
    assert "تسوية" in norm and "معايرة" not in norm


def test_efficiency_dialog_meta_fields_wide(qapp_fixture=None):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from spectramaster.gui.efficiency_dialog import EfficiencyDialog
    d = EfficiencyDialog()
    d.show()
    QApplication.processEvents()
    assert d.geom_edit.width() >= 200 and d.det_edit.width() >= 160
    d.close()


# ------------------------------------------------------------------ 9 / 10 / 12: CLI
def test_cli_no_args_without_gui_prints_help(monkeypatch, capsys):
    monkeypatch.setattr(cli, "gui_available", lambda: False)
    assert cli.main([]) == 0
    out = capsys.readouterr()
    assert "usage" in out.out.lower() and "SpectraMaster.exe" in out.out
    assert "PySide6/PyQt" not in out.out + out.err


def test_cli_sum_time_formatting(tmp_path, capsys):
    from spectramaster.convert import resolve_format, write_spectrum
    from spectramaster.tools.cli_tools import fmt_seconds
    assert fmt_seconds(6261.040000000001) == "6261.04 s"
    assert fmt_seconds(6500.0) == "6500 s" and fmt_seconds(None) == "-"
    fmt = resolve_format("iaea_spe")
    for name, lt in (("a.spe", 3130.52), ("b.spe", 3130.520000000001)):
        write_spectrum(Spectrum(counts=[1.0] * 64, energy_coeffs=[0, 1], live_time=lt, real_time=3200.1),
                       tmp_path / name, fmt)
    cli.main(["sum", str(tmp_path / "a.spe"), str(tmp_path / "b.spe"), "-o", str(tmp_path / "s.spe")])
    out = capsys.readouterr().out
    assert "live 6261.04 s" in out and "0000000" not in out


def test_library_categories_dual_origin():
    lib = load_library()
    assert lib["Cs-137"].category == "fission/calibration"
    assert lib["Co-60"].category == "activation/calibration"
    assert lib["Am-241"].category.startswith("actinide")
    from spectramaster.gui import i18n
    assert i18n.category_label("fission/calibration", "en") == "Fission product / Calibration source"
    assert "انشطار" in i18n.category_label("fission/calibration", "ar")
    assert i18n.category_label("unknownthing", "en") == "unknownthing"


def test_cli_table_left_aligned_column(capsys):
    cli._print_table([("Cs-137", "0.92", "661.7"), ("Ba-140", "0.86", "162.7, 241.9, 328.8")],
                     ("Nuclide", "Conf.", "Matched lines keV"), left=(2,))
    lines = capsys.readouterr().out.splitlines()
    col = lines[0].index("Matched")
    assert lines[2][col:].startswith("661.7") and lines[3][col:].startswith("162.7")


# ------------------------------------------------------------------ 11: Arabic article
@pytest.mark.parametrize("word, stem", [("الشاي", "شاي"), ("والحليب", "حليب"), ("بالزيتون", "زيتون"),
                                        ("للحليب", "حليب"), ("الف", "الف"), ("Cs-137", "cs-137")])
def test_strip_article(word, stem):
    assert strip_article(normalize_text(word)) == stem


def test_archive_search_finds_with_article(tmp_path):
    ix = ArchiveIndex(tmp_path / "a.sqlite")
    con = ix._conn()
    cur = con.execute("INSERT INTO entries(path, norm_text, error) VALUES(?, ?, 0)",
                      (str(tmp_path / "x.S0"), normalize_text("عينة شاي اسود")))
    con.execute("INSERT INTO entries_fts(rowid, text) VALUES(?, ?)", (cur.lastrowid, normalize_text("عينة شاي اسود")))
    con.commit()
    for q in ("شاي", "الشاى", "بالشاي"):
        assert ix.count(text=q, min_confidence=0.0) == 1, q
    assert ix.count(text="الحليب", min_confidence=0.0) == 0

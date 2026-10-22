"""Printing / PDF report tests (headless)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import re
from datetime import datetime
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pypdf = pytest.importorskip("pypdf")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from spectramaster.analysis import NuclideMatch, Peak
from spectramaster.model import Spectrum

from test_gui import fake_format, make_file, qapp, settings, wait_until, window  # noqa: F401 (fixtures)

FONT_FILES = ("segoeui.ttf", "segoeuib.ttf", "tahoma.ttf", "arial.ttf", "DejaVuSans.ttf")


@pytest.fixture(autouse=True)
def _fonts(qapp):
    """The offscreen platform may start without any font: register system fonts for the PDFs."""
    from PySide6.QtGui import QFontDatabase
    if not QFontDatabase.families():
        dirs = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts", Path("/usr/share/fonts/truetype/dejavu")]
        for d in dirs:
            for name in FONT_FILES:
                if (d / name).is_file():
                    QFontDatabase.addApplicationFont(str(d / name))
    if not QFontDatabase.families():
        pytest.skip("no fonts available for PDF text")
    yield


ARABIC = re.compile(r"[\u0600-\u06ff\ufb50-\ufdff\ufe70-\ufeff]")


def _spectrum(n=1024, sid="SAMPLE-XYZ-42") -> Spectrum:
    counts = [200.0 / (1 + i / 80) + (900 if 300 <= i <= 304 else 0) + (400 if 700 <= i <= 703 else 0)
              for i in range(n)]
    return Spectrum(counts=counts, energy_coeffs=[0.0, 1.5], fwhm_coeffs=[1.2, 0.001], live_time=1000.0,
                    real_time=1010.0, start_time=datetime(2025, 1, 2, 3, 4, 5), sample_id=sid,
                    description="soil sample", detector="HPGe-2",
                    extra={"geometry": "Marinelli 1 L", "operator": "تجربة"}, source_path="C:/data/soil.spe")


def _peaks(k=60) -> list[Peak]:
    out = []
    for i in range(k):
        ch = 10 + i * 15.0
        out.append(Peak(centroid=ch, energy=ch * 1.5, fwhm=2.0, fwhm_kev=3.0, net_area=1000.0 + i,
                        net_area_unc=40.0, gross_area=1500.0, background=500.0, left=int(ch) - 4,
                        right=int(ch) + 4, significance=3.0 + i % 7, count_rate=1.0,
                        nuclide="Cs-137" if i % 3 == 0 else "", line_energy=661.66 if i % 3 == 0 else None))
    return out


def _matches(peaks) -> list[NuclideMatch]:
    return [NuclideMatch("Cs-137", 0.93, [(661.66, peaks[0])], [], "30.08 y", "fission"),
            NuclideMatch("K-40", 0.71, [(1460.8, peaks[3])], [], "1.25E9 y", "natural", background=True),
            NuclideMatch("Co-60", 0.20, [(1173.2, peaks[6])], [1332.5], "5.27 y", "activation")]


def _data(analysed=True):
    from spectramaster.gui import report as rp
    pk = _peaks()
    return rp.ReportData(spectrum=_spectrum(), path=Path("C:/data/soil.spe"), fmt_name="IAEA SPE",
                         peaks=pk if analysed else [], matches=_matches(pk) if analysed else [],
                         analysed=analysed)


def _pdf_text(path) -> tuple[int, list[str], object]:
    r = pypdf.PdfReader(str(path))
    return len(r.pages), [re.sub(r"\s+", " ", p.extract_text() or "") for p in r.pages], r


# ------------------------------------------------------------------------- report module
def test_pdf_export_multipage_english(qapp, tmp_path):
    from spectramaster.gui import report as rp
    out = tmp_path / "r_en.pdf"
    opts = rp.ReportOptions(language="en", lab_name="Radiation Lab", report_no="R-77", extra=True,
                            notes_on=True, notes="checked twice", plot_vector=False)
    n = rp.export_pdf(out, _data(), opts)
    pages, texts, reader = _pdf_text(out)
    assert pages == n >= 2
    alltext = "\n".join(texts)
    assert "SAMPLE-XYZ-42" in alltext and "Radiation Lab" in alltext and "R-77" in alltext
    assert "Cs-137" in alltext and "checked twice" in alltext
    assert f"Page 1 of {pages}" in texts[0] and f"Page {pages} of {pages}" in texts[-1]
    assert "Edrees F. Hery" in texts[0]
    # the peaks table header row is repeated on the following page
    assert sum("Centroid Ch" in t for t in texts) >= 2
    # 300 dpi plot image embedded
    imgs = [im for p in reader.pages for im in p.images]
    assert imgs and max(im.image.width for im in imgs) >= 2000


def test_pdf_export_arabic_vector(qapp, tmp_path):
    from spectramaster.gui import report as rp
    out = tmp_path / "r_ar.pdf"
    n = rp.export_pdf(out, _data(), rp.ReportOptions(language="ar", plot_vector=True))
    pages, texts, _ = _pdf_text(out)
    assert pages == n >= 2
    alltext = "\n".join(texts)
    assert ARABIC.search(alltext)
    assert "SAMPLE-XYZ-42" in alltext
    assert "keV" in alltext                      # vector plot: axis text is real PDF text


def test_report_filters_and_sections(qapp):
    from spectramaster.gui import report as rp
    r = rp.Report(_data(), rp.ReportOptions(language="en", peaks_identified_only=True, peaks_min_sig=5,
                                            nuc_min_conf=50, nuc_hide_background=True))
    assert r.filtered_peaks() and all(p.nuclide and p.significance >= 5 for p in r.filtered_peaks())
    assert [m.nuclide for m in r.filtered_matches()] == ["Cs-137"]
    html = r.html()
    assert "Identified Nuclides" in html and "K-40" not in html.split("Identified Nuclides")[1]
    off = rp.Report(_data(), rp.ReportOptions(language="en", header=False, info=False, plot=False,
                                              peaks=False, nuclides=False, rois=False, signatures=False))
    assert "Peaks" not in off.html() and "Spectrum Information" not in off.html()


def test_no_analysis_noted(qapp, tmp_path):
    from spectramaster.gui import report as rp
    out = tmp_path / "na.pdf"
    rp.export_pdf(out, _data(analysed=False), rp.ReportOptions(language="en"))
    _, texts, _ = _pdf_text(out)
    assert "Not analysed" in "\n".join(texts)


def test_rtl_tables_mirrored(qapp):
    from spectramaster.gui import report as rp
    r = rp.Report(_data(), rp.ReportOptions(language="ar"))
    html = r._table(["A", "B"], [["1", "2"]])
    assert html.index(">B<") < html.index(">A<")          # first column on the right
    assert "\u2066" in r.num("12 ± 3")                       # numbers isolated left-to-right


def test_options_roundtrip_and_persistence(qapp, settings):
    from spectramaster.gui import report as rp
    o = rp.ReportOptions(lab_name="مختبر", plot_size="large", nuc_min_conf=40, landscape=True,
                         paper="Letter", language="en", notes="a\nb")
    rp.save_options(settings, o)
    assert rp.load_options(settings) == o
    assert rp.ReportOptions.from_dict({"plot_size": "bogus", "margin_mm": "500", "peaks": "false"}) == \
        rp.ReportOptions(margin_mm=40.0, peaks=False)
    from spectramaster.gui.report_dialogs import ReportOptionsDialog
    dlg = ReportOptionsDialog(settings, "pdf")
    assert dlg.options() == o
    dlg.ed_operator.setText("Analyst Z")
    dlg.cb_extra.setChecked(True)
    dlg.accept()
    again = rp.load_options(settings)
    assert again.operator == "Analyst Z" and again.extra and again.lab_name == "مختبر"


def test_templates_save_load_delete(qapp, settings):
    from spectramaster.gui import report as rp
    from spectramaster.gui.report_dialogs import ReportOptionsDialog
    dlg = ReportOptionsDialog(settings, "print", rp.ReportOptions(lab_name="Lab A"))
    dlg.cb_plot_inc.setChecked(False)
    assert dlg.save_template("Mine") == "Mine"
    assert rp.template_names(settings) == ["Mine"]
    dlg.cb_plot_inc.setChecked(True)
    assert dlg.apply_template("Mine") and not dlg.cb_plot_inc.isChecked()
    # built-in preset keeps the header identity
    assert dlg.apply_template("preset:plot_only")
    o = dlg.options()
    assert o.plot and not o.peaks and not o.nuclides and o.plot_size == "page" and o.lab_name == "Lab A"
    assert rp.load_template(settings, "preset:nuclides").nuclides
    assert dlg.delete_template("Mine", confirm=False)
    assert rp.template_names(settings) == []
    assert rp.load_template(settings, "Mine") is None


# ------------------------------------------------------------------------- batch
def _real_like_files(tmp_path, fake_format):
    return [make_file(tmp_path / "in", "a.fak", sid="ALPHA"), make_file(tmp_path / "in", "b.fak", sid="BETA")]


def test_batch_worker_per_file_and_combined(qapp, tmp_path, fake_format):
    from spectramaster.gui import report as rp
    from spectramaster.gui.report_dialogs import ReportBatchWorker
    files = _real_like_files(tmp_path, fake_format)
    opts = rp.ReportOptions(language="en")
    w = ReportBatchWorker(files, opts, tmp_path / "out", None, analyse=True)
    got = []
    w.progress.connect(lambda *a: got.append(a))
    w.run()
    assert w.ok_count == 2 and w.failed_count == 0, got
    for f, sid in zip(files, ("ALPHA", "BETA")):
        out = tmp_path / "out" / f"{f.stem}_report.pdf"
        _, texts, _ = _pdf_text(out)
        assert sid in "\n".join(texts)
    comb = tmp_path / "all.pdf"
    w2 = ReportBatchWorker(files + [tmp_path / "missing.fak"], opts, None, comb, analyse=False)
    w2.run()
    assert (w2.ok_count, w2.failed_count) == (2, 1)
    _, texts, _ = _pdf_text(comb)
    t = "\n".join(texts)
    assert "ALPHA" in t and "BETA" in t and "Not analysed" in t


def test_batch_dialog_runs_in_thread(qapp, settings, tmp_path, fake_format):
    from spectramaster.gui.report_dialogs import ReportBatchDialog
    files = _real_like_files(tmp_path, fake_format)
    dlg = ReportBatchDialog(settings, files)
    assert dlg.select_template("preset:nuclides") and not dlg.options.plot
    dlg.rb_per_file.setChecked(True)
    dlg.out_edit.setText(str(tmp_path / "pdfs"))
    done = []
    dlg.finishedReports.connect(lambda *a: done.append(a))
    assert dlg.start()
    assert wait_until(lambda: done and not dlg.is_running(), 60)
    assert done[0][:3] == (2, 0, 2)
    assert sorted(p.name for p in (tmp_path / "pdfs").glob("*.pdf")) == ["a_report.pdf", "b_report.pdf"]
    dlg.close()


# ------------------------------------------------------------------------- main window
def test_window_export_pdf_offers_analysis(window, tmp_path, monkeypatch):
    from spectramaster.gui import report as rp
    p = make_file(tmp_path, "w.fak", sid="WIN-SAMPLE")
    assert window.load_file(p)
    assert window.act_print.isEnabled() and window.act_export_pdf.isEnabled()
    asked = []
    window.ask_yes_no = lambda text: asked.append(text) or False
    out = window.export_report_pdf(str(tmp_path / "no.pdf"), rp.ReportOptions(language="en"))
    assert out is not None and asked
    _, texts, _ = _pdf_text(out)
    assert "WIN-SAMPLE" in "\n".join(texts) and "Not analysed" in "\n".join(texts)
    assert not window.analysis_panel.analysed
    # yes: the analysis runs first (synchronously) and the report contains it
    window.ask_yes_no = lambda text: True
    out2 = window.export_report_pdf(str(tmp_path / "yes.pdf"), rp.ReportOptions(language="en"))
    assert out2 is not None and window.analysis_panel.analysed
    assert "Not analysed" not in "\n".join(_pdf_text(out2)[1])
    # cancelled options dialog -> nothing written
    window.ask_report_options = lambda mode: None
    assert window.export_report_pdf(str(tmp_path / "x.pdf")) is None
    assert not (tmp_path / "x.pdf").exists()



def test_window_report_command_analyses_on_the_worker_thread(window, tmp_path):
    """The menu command (threaded) runs the analysis like Analyze, then writes the report."""
    from spectramaster.gui import report as rp
    assert window.load_file(make_file(tmp_path, "t.fak", sid="THR-SAMPLE"))
    window.ask_yes_no = lambda text: True
    out = tmp_path / "thr.pdf"
    assert window.export_report_pdf(str(out), rp.ReportOptions(language="en"), threaded=True) is None
    assert window.analysis_running() and not out.exists()
    assert wait_until(lambda: out.exists() and not window.analysis_running(), 60)
    assert window.analysis_panel.analysed and window._report_resume is None
    assert "Not analysed" not in "\n".join(_pdf_text(out)[1])
    # declined: written at once without analysis, nothing waits
    assert window.load_file(make_file(tmp_path, "u.fak", sid="NO-ANA"))
    window.ask_yes_no = lambda text: False
    out2 = window.export_report_pdf(str(tmp_path / "no.pdf"), rp.ReportOptions(language="en"), threaded=True)
    assert out2 is not None and not window.analysis_running() and window._report_resume is None
    # an analysis that fails: the report is not written
    assert window.load_file(make_file(tmp_path, "v.fak", sid="FAIL"))
    window.ask_yes_no = lambda text: True
    window._report_resume = None
    window._resume_report(window._ana_token + 1, False)          # nothing pending: no-op
    called = []
    window._report_resume = (7, lambda: called.append(1))
    window._resume_report(7, False)
    assert not called and window._report_resume is None
    window._report_resume = (9, lambda: called.append(1))
    window._resume_report(8, True)                               # an older analysis: keeps waiting
    assert window._report_resume is not None and not called
    window._resume_report(9, True)
    assert called == [1]

def test_window_report_uses_current_view(window, tmp_path):
    from spectramaster.gui import report as rp
    p = make_file(tmp_path, "v.fak", n=512)
    window.load_file(p)
    window.plot.set_view(100, 150)
    window.plot.add_roi(98, 108)
    d = window.report_data()
    r = rp.Report(d, rp.ReportOptions(plot_view="current"))
    ren = r.make_renderer()
    assert (ren.x0, ren.x1) == (100, 150) and len(ren.rois) == 1
    assert rp.Report(d, rp.ReportOptions(plot_view="full")).make_renderer().x1 == 512
    assert rp.Report(d, rp.ReportOptions(plot_rois=False)).make_renderer().rois == []
    assert len(r.roi_list()) == 1


def test_print_preview_dialog_builds(window, tmp_path):
    from spectramaster.gui import report as rp
    window.load_file(make_file(tmp_path, "pp.fak"))
    window.ask_yes_no = lambda text: False
    dlg = window.print_preview(rp.ReportOptions(language="en"), exec_dialog=False)
    assert dlg is not None
    dlg.deleteLater()
    assert window.open_report_batch() is not None
    QApplication.processEvents()

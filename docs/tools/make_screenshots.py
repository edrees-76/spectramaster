"""Generate the user-manual screenshots (docs/images/{ar,en}/) offscreen from real lab spectra.

    set QT_QPA_PLATFORM=offscreen & set QT_QPA_FONTDIR=C:\\Windows\\Fonts
    python docs/tools/make_screenshots.py [ar|en ...]

Reads the Aptec reference spectra read-only; the archive index and the QC store are copied to a
temporary folder first, so nothing outside docs/images is modified.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
os.environ["SPECTRAMASTER_NO_SPLASH"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="sm_manual_"))
os.environ["SPECTRAMASTER_EFF_DIR"] = str(TMP / "eff")
os.environ["SPECTRAMASTER_DETECTOR_DIR"] = str(TMP / "detectors")

from PySide6.QtCore import QPoint, QRect, QSettings, QSize, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from spectramaster.gui.app import MainWindow, create_app, splash_pixmap  # noqa: E402
from spectramaster.gui.settings import Settings  # noqa: E402

REF = Path(r"D:\الاسس و المفاهيم العامة فى استخدام برامج الطيف الجامى\اطياف مرجعية"
           r"\4- أطياف المختبر (Aptec)\الملفات الأصلية S0")
EU, CHERN, BKG, QCY = (REF / n for n in ("Eu-152.S0", "CHERN.S0", "CHERNBKG.S0", "QCY48CAL.S0"))
def _data(rel: str) -> Path:
    """A scratch data folder of the repository (a worktree falls back to the main checkout)."""
    p = ROOT / rel
    if not p.exists():
        main = Path(r"D:\DSpectraMaster") / rel
        if main.exists():
            return main
    return p


ARCHIVE_DB = _data("scratch_search/archive.sqlite")
ARCHIVE_ROOT = r"D:\مختبر التحاليل و القياسات الاشعاعية\04_القياسات_والبيانات_الفنية"
QC_STORE = _data("scratch_qc/store")
APTEC_LIB = Path(r"C:\APTEC\APTEC\isotope.lib")
IMG = ROOT / "docs" / "images"

app = create_app(["manual"])
import spectramaster.gui.window_buttons as _wb  # noqa: E402
_wb.fit_to_screen = lambda w: None   # the offscreen screen is 800 x 800: keep the sizes set here
from spectramaster.gui import i18n  # noqa: E402

GEOM: dict = {}     # lang -> {name: QRect} for the annotation step


def pump(n: int = 3) -> None:
    for _ in range(n):
        QApplication.processEvents()


def save(widget, lang: str, name: str) -> Path:
    pump()
    out = IMG / lang / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    widget.grab().save(str(out))
    print("  ", out.relative_to(ROOT))
    return out


def wait_for(pred, seconds: float = 120.0) -> bool:
    """Process events until `pred()` is true (background workers of the dialogs)."""
    import time
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QApplication.processEvents()
        if pred():
            return True
        time.sleep(0.02)
    return False


def wait_analysis(w) -> None:
    while w.analysis_running():
        QApplication.processEvents()
    pump()


def rect_in(widget, top) -> QRect:
    p = widget.mapTo(top, QPoint(0, 0))
    return QRect(p, widget.size())


def report_options(lang: str, **kw):
    from spectramaster.gui import report as rp
    en = lang == "en"
    return rp.ReportOptions(
        lab_name="Radiation Measurement Laboratory" if en else "مختبر القياسات الإشعاعية",
        department="Gamma Spectrometry Unit" if en else "وحدة مطيافية غاما",
        address="Tripoli · Tel +218 21 000 0000",
        logo_path=str(ROOT / "spectramaster" / "gui" / "assets" / "logo_full.png"),
        report_no="GS-2026-0142", operator="Edrees F. Hery", language=lang, notes_on=True,
        notes=("Calibration source spectrum, analysed with the built-in library." if en
               else "طيف مصدر المعايرة، حُلِّل بالمكتبة المدمجة."),
        sig_reviewed="—", **kw)


def pdf_page_png(pdf: Path, page: int, out: Path, dpi: int = 100) -> None:
    from PySide6.QtPdf import QPdfDocument
    doc = QPdfDocument()
    doc.load(str(pdf))
    sz = doc.pagePointSize(page)
    img = doc.render(page, QSize(int(sz.width() * dpi / 72), int(sz.height() * dpi / 72)))
    bg = QImage(img.size(), QImage.Format_RGB32)
    bg.fill(QColor("white"))
    p = QPainter(bg)
    p.drawImage(0, 0, img)
    p.setPen(QColor("#b8c2cc"))
    p.drawRect(0, 0, bg.width() - 1, bg.height() - 1)
    p.end()
    bg.save(str(out))
    print("  ", out.relative_to(ROOT))


def menu_shot(w, menu, lang: str, name: str) -> None:
    menu.popup(w.mapToGlobal(QPoint(40, 40)))
    pump(5)
    save(menu, lang, name)
    menu.hide()
    pump()


def shoot(lang: str) -> None:
    print(f"[{lang}]")
    i18n.set_language(lang)
    ini = TMP / f"settings_{lang}.ini"
    st = Settings(QSettings(str(ini), QSettings.IniFormat))
    st.language = lang
    st.set("archive/db", str(TMP / "archive.sqlite"))
    st.set("archive/roots", '["%s"]' % ARCHIVE_ROOT.replace("\\", "\\\\"))
    st.set("qc/dir", str(TMP / f"qc_{lang}"))
    st.set("folders/open", str(REF))
    w = MainWindow(st)
    w.resize(1366, 840)
    errors = []
    w.show_error = errors.append
    w.show_info = errors.append
    w.ask_yes_no = lambda text: True
    w.show()
    pump()
    save(w, lang, "main_empty")

    # ---------------------------------------------------------------- main window
    w.load_file(EU)
    w.set_y_mode("log")
    pump()
    g = {}
    for key, wid in (("menubar", w.menuBar()), ("toolbar", w.toolbar), ("navbar", w.nav_toolbar),
                     ("plot", w.plot), ("overview", w.overview), ("info", w.info_scroll),
                     ("status", w.statusBar())):
        g[key] = rect_in(wid, w)
    GEOM[lang] = g
    save(w, lang, "main")

    # menus
    for name, menu in (("menu_file", w.menu_file), ("menu_edit", w.menu_edit), ("menu_display", w.menu_display),
                       ("menu_setup", w.menu_setup), ("menu_roi", w.menu_roi), ("menu_view", w.menu_view),
                       ("menu_analyze", w.menu_analyze), ("menu_help", w.menu_help)):
        menu_shot(w, menu, lang, name)
    from PySide6.QtWidgets import QMenu
    tools = w.menuBar().findChild(QMenu, "menu_tools")
    if tools is not None:
        menu_shot(w, tools, lang, "menu_tools")

    # ---------------------------------------------------------------- analysis
    w.run_analysis()
    wait_analysis(w)
    if w.analysis_panel.matches:
        w.analysis_panel.select_nuclide_row(0)
    pump()
    save(w, lang, "analysis_peaks")
    w.analysis_panel.tabs.setCurrentIndex(1)
    save(w, lang, "analysis")
    save(w.analysis_dock, lang, "analysis_dock")

    # ---------------------------------------------------------------- overlay + ROI + zoom
    w.act_overlay_norm.setChecked(True)
    w.add_overlay_file(str(BKG))
    w.goto(344.28, "kev", 4)
    pos = w.plot.pos_of_energy(344.28)
    if pos is not None:
        w.plot.add_roi(int(pos - 7), int(pos + 7))
    pump()
    save(w, lang, "zoom_roi_overlay")
    save(w.roi_dock, lang, "roi_dock")

    # ---------------------------------------------------------------- dialogs
    from spectramaster.formats import readable_formats, writable_formats
    from spectramaster.gui.dialogs import (AboutDialog, BatchDialog, FormatDialog, IntegrationDialog,
                                           ShortcutsDialog)
    from spectramaster.gui.i18n import tr
    from spectramaster.gui.preview import PreviewFileDialog
    d = FormatDialog(tr("dlg_input_title"), tr("dlg_input_prompt"), readable_formats(), "auto", True, w)
    d.resize(640, 560)
    d.show()
    save(d, lang, "input_format")
    d.close()
    d = FormatDialog(tr("dlg_output_title"), tr("dlg_output_prompt"), writable_formats(), "ortec_chn", False, w)
    d.resize(640, 560)
    d.show()
    save(d, lang, "output_format")
    d.close()
    import spectramaster.gui.dialogs as dlgmod      # show what the installed SpectraMaster.exe displays
    dlgmod.program_path = lambda: r"C:\Program Files\SpectraMaster\SpectraMaster.exe"
    dlgmod.program_arguments_prefix = lambda: ""
    for cls, name in ((AboutDialog, "about"), (IntegrationDialog, "integration"), (ShortcutsDialog, "shortcuts")):
        d = cls(w)
        d.show()
        save(d, lang, name)
        d.close()
    pv = PreviewFileDialog(w, tr("fd_open_title"), str(REF), "Aptec (*.S0);;" + tr("fd_all_files"), "", st)
    pv.show()
    pump()
    pv.selectFile(str(EU))
    pv.preview.show_file(str(EU))
    pump(10)
    save(pv, lang, "open_preview")
    pv.close()
    b = BatchDialog([EU, CHERN, BKG, QCY], st, w)
    b.show()
    save(b, lang, "batch_files")
    b.close()
    b = BatchDialog([], st, w, folder_mode=True, folder=REF)
    b.recursive_cb.setChecked(False)
    b.scan()
    pump(20)
    save(b, lang, "batch_folder")
    b.close()

    # ---------------------------------------------------------------- reports
    from spectramaster.gui import report as rp
    from spectramaster.gui.report_dialogs import ReportBatchDialog, ReportOptionsDialog
    opts = report_options(lang)
    rp.save_options(st, opts)
    rd = ReportOptionsDialog(st, "pdf", opts, w)
    rd.show()
    for i, name in enumerate(("report_opt_header", "report_opt_content", "report_opt_plot", "report_opt_page")):
        rd.tabs.setCurrentIndex(i)
        save(rd, lang, name)
    rd.close()
    w.plot.clear_rois()
    w.plot.clear_overlays()
    w.load_file(EU)
    w.run_analysis()
    wait_analysis(w)
    w.plot.reset_view()
    pdf = TMP / f"report_{lang}.pdf"
    out = w.export_report_pdf(str(pdf), rp.apply_preset(report_options(lang, plot_scale="log"), "full"))
    if out:
        pdf_page_png(out, 0, IMG / lang / "report_page1.png")
        pdf_page_png(out, 1, IMG / lang / "report_page2.png")
    rb = ReportBatchDialog(st, [EU, CHERN, BKG], w)
    rb.show()
    save(rb, lang, "report_batch")
    rb.close()

    # ---------------------------------------------------------------- efficiency + activity
    from spectramaster.gui.efficiency_dialog import EfficiencyDialog
    from spectramaster.gui.quant_panel import ActivityDialog
    w.load_file(QCY)
    ed = EfficiencyDialog(w, w.current_spectrum(), st)
    ed._msg = lambda text, error=True: print("   eff:", text)
    ed.show()
    ed.load_aptec_records()
    ed.measure_and_fit()
    pump()
    save(ed, lang, "efficiency")
    from PySide6.QtWidgets import QTabWidget
    etabs = ed.findChild(QTabWidget)
    if etabs is not None and etabs.count() > 1:
        etabs.setCurrentIndex(1)
        pump()
        save(ed, lang, "efficiency_geometry")
        etabs.setCurrentIndex(etabs.count() - 1)
        pump()
        save(ed, lang, "efficiency_validation")
        etabs.setCurrentIndex(0)
    curve = ed.save_curve(str(TMP / "eff" / "QCY48_Bottle_10cm.json"))
    ed.close()
    w.load_file(CHERN)
    ad = ActivityDialog(w, w.current_spectrum(), st)
    ad.show()
    if curve:
        ad.set_curve_path(curve)
    ad.load_background(str(BKG))
    ad.nuc_edit.setText("Cs-137, Cs-134, I-131, Ru-103, K-40")
    ad.qty_spin.setValue(1.0)
    ad.sample_box._num["mass_kg"].setText("1.0")           # Bq/kg on a dry basis
    ad.sample_box.basis_combo.setCurrentIndex(ad.sample_box.basis_combo.findData("dry"))
    res = ad.calculate()
    print("   activity:", None if res is None else len(res.nuclides))
    ad.resize(1180, 1240)
    save(ad, lang, "activity")
    ad.close()

    shoot_release_b(w, lang, st)
    shoot_aptec(w, lang, st)
    if not (TMP / "archive.sqlite").exists() or not QC_STORE.exists():
        print("   archive / QC data not found: those screenshots are kept as they are")
        w.close()
        return

    # ---------------------------------------------------------------- archive search
    from spectramaster.gui.archive_search import ArchiveSearchWindow
    aw = ArchiveSearchWindow(w, st)
    aw.resize(1366, 820)
    aw.show()
    pump()
    aw.refresh_info()
    if lang == "ar":
        aw.set_filters({"text": "زيتون", "min_confidence": 0.5})
    else:
        aw.set_filters({"nuclides": ["Cs-137"], "min_confidence": 0.5})
    aw.run_search()
    aw.db_label.setText("⁦" + r"%APPDATA%\SpectraMaster\archive.sqlite" + "⁩")   # default location (a copy is used)
    pump(5)
    save(aw, lang, "archive_search")
    aw.close()

    # ---------------------------------------------------------------- QC
    from spectramaster.gui.qc_window import QCWindow, TrackDialog
    from spectramaster.tools.qc import QCStore
    qdir = TMP / f"qc_{lang}"
    shutil.copytree(QC_STORE, qdir, dirs_exist_ok=True)
    qw = QCWindow(store=QCStore(qdir), main_window=w, settings=st)
    qw.resize(1366, 900)
    qw.show()
    pump()
    for i, t in enumerate(qw.tracks):
        if "fixed" in t.name:
            qw.track_list.setCurrentRow(i)
    pump(5)
    save(qw, lang, "qc_charts")
    for i in range(qw.tabs.count()):
        if qw.tabs.tabText(i) == tr("qc_tab_violations"):
            qw.tabs.setCurrentIndex(i)
    save(qw, lang, "qc_violations")
    for i in range(qw.tabs.count()):
        if qw.tabs.tabText(i) == tr("qc_tab_stats"):
            qw.tabs.setCurrentIndex(i)
    save(qw, lang, "qc_stats")
    cur = qw.tracks[qw.track_list.currentRow()] if qw.track_list.currentRow() >= 0 else None
    td = TrackDialog(cur, qw)
    td.show()
    save(td, lang, "qc_track")
    td.close()
    qw.close()
    if errors:
        print("   messages:", [e[:120] for e in errors])
    w.close()


def shoot_release_b(w, lang: str, st) -> None:
    """Calibration from a source, drift check, fit inspection, batch analysis, review, detectors."""
    from spectramaster.gui import calibration_dialog as cd
    from spectramaster.gui import fit_inspection as fi
    from spectramaster.gui import session_io as si
    from spectramaster.gui.detector_picker import DetectorManagerDialog
    from spectramaster.gui.detector_registry import DetectorRegistry
    from spectramaster.lab.detector import DetectorProfile

    w.load_file(EU)
    pump()
    d = cd.open_calibration_dialog(w, modal=False)
    d.message = lambda text: print("   cal:", text[:100])
    d.resize(1100, 760)
    d.source_edit.setText("Eu-152")
    d.propose()
    wait_for(lambda: not d.busy)
    pump()
    save(d, lang, "calibration")
    d.close()

    w.load_file(CHERN)
    pump()
    d = cd.open_drift_dialog(w, modal=False)
    d.message = lambda text: print("   drift:", text[:100])
    d.resize(980, 640)
    d.check()
    wait_for(lambda: not d.busy)
    pump()
    save(d, lang, "drift")
    d.close()

    w.load_file(EU)
    pump()
    d = fi.open_fit_inspection(w, show=False)
    d.message = lambda text: print("   fit:", text[:100])
    d.resize(1280, 820)
    d.show()
    wait_for(lambda: not d.busy)
    pump()
    for row in range(d.group_list.count()):              # the Eu-152 doublet 1085.8 / 1089.7 keV
        if "108" in d.group_list.item(row).text():
            d.group_list.setCurrentRow(row)
            break
    pump(5)
    save(d, lang, "fit_inspection")
    d.close()

    b = si.open_batch_analysis(w, show=False)
    b.resize(1280, 760)
    b.show()
    b.add_paths([EU, CHERN, BKG, QCY])
    b.scan()
    wait_for(lambda: not b.busy, 60)
    pump(5)
    save(b, lang, "batch_analysis")
    b.close()

    rv = si.ReviewDialog(w, "Edrees F. Hery")
    rv.show()
    save(rv, lang, "review")
    rv.close()

    reg = DetectorRegistry(TMP / "detectors")
    for name, kind, rel in (("G4 HPGe 40 %", "HPGe", 40.0), ("NaI 3x3", "NaI", None)):
        if not any(p.name == name for p in reg.list()):
            reg.save(DetectorProfile(name=name, type=kind, relative_efficiency_pct=rel))
    dm = DetectorManagerDialog(w, reg)
    dm.list.setCurrentRow(0)
    dm.show()
    save(dm, lang, "detectors")
    dm.close()

    w.workflow_dock.show()
    pump()
    save(w.workflow_dock, lang, "workflow")


def shoot_aptec(w, lang: str, st) -> None:
    """The Aptec-style menus and windows (Setup, ROI, Analyze, MultiFit, spectrum operations)."""
    from spectramaster.analysis.aptec_analyze import IdentifySetup
    from spectramaster.gui import aptec_analyze_ui as aau
    from spectramaster.gui import aptec_calibration_ui as acu
    from spectramaster.gui import aptec_edit_ui as aeu
    from spectramaster.gui import aptec_view_ui as avu
    from spectramaster.gui import plot as plotmod
    from spectramaster.gui.aptec_roi_ui import RoiPropertiesDialog
    w.plot.clear_rois()
    w.plot.clear_overlays()
    menu_shot(w, w.menu_a_setup, lang, "menu_analyze_setup")
    ctl = w.aptec_analysis

    # P, I, Q on a soil sample with Aptec's own library
    w.load_file(CHERN)
    w.set_y_mode("log")
    ctl.ident = IdentifySetup(library=str(APTEC_LIB) if APTEC_LIB.exists() else "", fraction_limit=40.0)
    ctl.run_peak()
    ctl.run_identify()
    ctl.run_quant()
    w.roi_dock.show()
    w.roi_dock.raise_()
    w.plot.reset_view()
    pump()
    save(w, lang, "aptec_analysis")
    save(w.roi_dock, lang, "aptec_roi_list")

    # MultiFit: the Eu-152 doublet 1085.8 / 1089.7 keV
    w.load_file(EU)
    w.set_y_mode("linear")
    w.plot.clear_rois()
    pos = w.plot.pos_of_energy(1087.8)
    if pos is not None:
        w.plot.add_roi(int(pos - 13), int(pos + 13))
        ctl.run_multifit()
        w.plot.set_view(pos - 40, pos + 40, None)
    pump()
    save(w, lang, "aptec_multifit")

    # Paint bar (F3)
    w.plot.clear_fits()
    w.plot.clear_rois()
    w.set_y_mode("log")
    w.goto(344.28, "kev", 4)
    pos = w.plot.pos_of_energy(344.28)
    if pos is not None:
        w.plot.set_marker(int(pos))
        w.plot.start_paint()
        for _ in range(6):
            w.plot.paint_expand(1)
    pump()
    save(w, lang, "aptec_paint")
    w.plot.paint_cancel()

    # dialogs
    spec = w.current_spectrum()
    dialogs = (("aptec_dlg_roi_props", lambda: RoiPropertiesDialog(w.plot.roi_props, w)),
               ("aptec_dlg_peak", lambda: aau.PeakSearchDialog(ctl.peak, spec.num_channels, w, w)),
               ("aptec_dlg_multifit", lambda: aau.MultifitDialog(ctl.multifit, w)),
               ("aptec_dlg_ident", lambda: aau.IdentifyDialog(ctl.ident, w)),
               ("aptec_dlg_quant", lambda: aau.QuantifyDialog(ctl.quant, "", w)),
               ("aptec_dlg_sample", lambda: aeu.SampleDescriptionDialog(spec, w)),
               ("aptec_dlg_quick_energy", lambda: acu.QuickEnergyDialog(w, spec, w)))
    for name, make in dialogs:
        try:
            d = make()
            d.show()
            save(d, lang, name)
            d.close()
        except Exception as exc:                    # keep going: report it
            print("   ", name, "failed:", exc)

    # Compare mode with Aptec's colours
    w.load_file(CHERN)
    w.set_y_mode("log")
    w.spectrum_ops.toggle_compare(str(BKG))
    w.spectrum_ops.position(40)
    old = plotmod.current_colors()
    avu.apply_colors(w, plotmod.APTEC_COLORS)
    pump()
    save(w, lang, "aptec_compare")
    avu.apply_colors(w, old)
    w.spectrum_ops.toggle_compare()
    w.plot.clear_rois()


def annotate(lang: str) -> None:
    """Numbered callouts on main.png -> main_annotated.png."""
    from PIL import Image, ImageDraw, ImageFont
    src = IMG / lang / "main.png"
    g = GEOM.get(lang)
    if not g or not src.exists():
        return
    im = Image.open(src).convert("RGB")
    dr = ImageDraw.Draw(im)
    font = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 18)
    order = ["menubar", "toolbar", "navbar", "plot", "overview", "info", "status"]
    rtl = lang == "ar"
    for n, key in enumerate(order, start=1):
        r = g[key]
        x0, y0, x1, y1 = r.x(), r.y(), r.x() + r.width() - 1, r.y() + r.height() - 1
        dr.rectangle([x0 + 1, y0 + 1, x1 - 1, y1 - 1], outline=(214, 69, 65), width=2)
        if key in ("menubar", "toolbar", "navbar"):
            cx, cy = (x1 - 30 if not rtl else x0 + 30), (y0 + y1) // 2
        elif key in ("status", "overview"):
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        elif key == "plot":
            cx, cy = (x0 + x1) // 2, y0 + 30
        else:   # info panel: lower middle (empty area)
            cx, cy = (x0 + x1) // 2, y1 - 60
        rad = 14
        dr.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(214, 69, 65), outline="white", width=2)
        tw = dr.textlength(str(n), font=font)
        dr.text((cx - tw / 2, cy - 12), str(n), fill="white", font=font)
    out = IMG / lang / "main_annotated.png"
    im.save(out)
    print("  ", out.relative_to(ROOT))


if __name__ == "__main__":
    if ARCHIVE_DB.exists():
        shutil.copy2(ARCHIVE_DB, TMP / "archive.sqlite")
    langs = sys.argv[1:] or ["ar", "en"]
    for lg in langs:
        shoot(lg)
        annotate(lg)
    for lg in langs:
        splash_pixmap().save(str(IMG / lg / "splash.png"))
    shutil.rmtree(TMP, ignore_errors=True)
    print("done")

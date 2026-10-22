"""GUI: detector registry and picker (D5), the activity dialog's detector line and the laboratory
context of the printed report (library, concentrations, workflow statuses)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import re

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from spectramaster.gui import i18n
from spectramaster.lab.detector import DetectorProfile, MeasurementGeometry

from test_gui_session_io import analyse, spectrum_file


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


@pytest.fixture()
def window(qapp, tmp_path, monkeypatch):
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.settings import Settings
    monkeypatch.setenv("SPECTRAMASTER_EFF_DIR", str(tmp_path / "curves"))
    monkeypatch.setenv("SPECTRAMASTER_DETECTOR_DIR", str(tmp_path / "detectors"))
    i18n.set_language("en")
    w = MainWindow(Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)))
    w.errors, w.infos = [], []
    w.show_error = w.errors.append
    w.show_info = w.infos.append
    yield w
    w.session_ctl.ask_save_changes = lambda: "discard"
    w.close()
    w.deleteLater()
    QApplication.processEvents()
    i18n.set_language("en")


def _codes(win):
    return {code for _lv, code, _t in win.session_ctl.panel.rows()}


def _registry():
    from spectramaster.gui.detector_registry import DetectorRegistry
    return DetectorRegistry()


# ------------------------------------------------------------------ registry
def test_registry_crud_round_trip(tmp_path, monkeypatch):
    from spectramaster.gui.detector_registry import FORMAT, DetectorRegistry, default_detector_dir
    monkeypatch.setenv("SPECTRAMASTER_DETECTOR_DIR", str(tmp_path / "det"))
    assert default_detector_dir() == tmp_path / "det"
    reg = DetectorRegistry()
    assert reg.list() == [] and reg.get("nope") is None and reg.get(None) is None
    a = DetectorProfile(name="GeHP-2", type="HPGe", serial="S-123", relative_efficiency_pct=40)
    b = DetectorProfile(name="aNaI", type="NaI")
    reg.save(a), reg.save(b)
    f = tmp_path / "det" / f"{a.id}.json"
    doc = json.loads(f.read_text(encoding="utf-8"))
    assert doc["format"] == FORMAT and doc["id"] == a.id and doc["serial"] == "S-123"
    assert [p.name for p in reg.list()] == ["aNaI", "GeHP-2"]          # sorted by name
    assert reg.get(a.id) == a
    # renaming keeps the id (the link of calibrations and sessions)
    a.name = "GeHP-2 (lab 3)"
    reg.save(a)
    assert reg.get(a.id).name == "GeHP-2 (lab 3)" and len(reg.list()) == 2
    # unreadable files are skipped and reported, never deleted
    (tmp_path / "det" / "junk.json").write_text("{not json", encoding="utf-8")
    assert len(reg.list()) == 2 and reg.problems and (tmp_path / "det" / "junk.json").exists()
    assert reg.delete(b.id) and not reg.delete(b.id) and reg.get(b.id) is None
    with pytest.raises(ValueError):
        reg.save(DetectorProfile(name="  "))
    with pytest.raises(ValueError):
        reg.path_for("../evil")


def test_manager_dialog_new_edit_delete(qapp, tmp_path, monkeypatch):
    from spectramaster.gui.detector_picker import DetectorEditor, DetectorManagerDialog
    from spectramaster.gui.detector_registry import DetectorRegistry
    reg = DetectorRegistry(tmp_path / "det")
    dlg = DetectorManagerDialog(None, reg)
    ed = DetectorEditor(None)
    ed.name_edit.setText("Ge-1")
    ed.type_combo.setCurrentIndex(ed.type_combo.findData("HPGe"))
    ed.edits["serial"].setText("SN 9")
    ed.edits["crystal_diameter_mm"].setText("62,5")
    p = ed.profile()
    assert p.crystal_diameter_mm == 62.5 and p.crystal_length_mm is None       # empty = unknown
    dlg.ask_profile = lambda base: p
    pid = dlg.new_profile()
    assert pid == p.id and dlg.ids() == [p.id] and dlg.selected_id() == p.id
    # edit keeps the id and the linked calibrations
    p.efficiency_calibration_ids.append("cal-1")
    reg.save(p)
    ed2 = DetectorEditor(None, reg.get(p.id))
    ed2.name_edit.setText("Ge-1 renamed")
    dlg.ask_profile = lambda base: ed2.profile()
    assert dlg.edit_selected() == p.id
    got = reg.get(p.id)
    assert got.name == "Ge-1 renamed" and got.efficiency_calibration_ids == ["cal-1"] and got.serial == "SN 9"
    # invalid input is refused with a translated message
    ed2.edits["crystal_length_mm"].setText("abc")
    with pytest.raises(ValueError):
        ed2.profile()
    ed2.name_edit.setText("")
    with pytest.raises(ValueError):
        ed2.profile()
    # delete asks first
    dlg.confirm = lambda title, text: False
    assert not dlg.delete_selected() and reg.get(p.id) is not None
    dlg.confirm = lambda title, text: True
    assert dlg.delete_selected() and reg.list() == [] and dlg.ids() == []


# ------------------------------------------------------------------ picker in the session
def test_picker_records_detector_in_session_and_undo_restores(window, tmp_path):
    reg = _registry()
    ge = DetectorProfile(name="Ge-A", type="HPGe", serial="111")
    nai = DetectorProfile(name="NaI-B", type="NaI")
    reg.save(ge), reg.save(nai)
    path = spectrum_file(tmp_path / "data")
    window.load_file(path)
    ctl, bar = window.session_ctl, window.session_ctl.context
    s = window.session
    assert s.detector is None and bar.selected_id() is None
    ids = [bar.det_combo.itemData(i) for i in range(bar.det_combo.count())]
    assert ids == [None, ge.id, nai.id]
    file_label = (window.current_spectrum().detector or "").strip()
    if file_label:
        assert file_label in i18n.strip_bidi(bar.file_label.text())
    analyse(window)
    assert not s.status["results_stale"]
    before_label = window.current_spectrum().detector
    assert bar.choose(ge.id)
    assert s.detector_id == ge.id and s.detector["name"] == "Ge-A" and s.detector["serial"] == "111"
    assert s.status["results_stale"]                       # the engine marks the results stale
    assert "results_stale" in _codes(window)
    assert window.current_spectrum().detector == before_label     # the file's label is never overwritten
    assert bar.selected_id() == ge.id and bar.btn_undo.isEnabled()
    # choosing again the same profile is not an edit
    n = len(s.history.ops)
    assert not ctl.set_detector(ge.id) and len(s.history.ops) == n
    assert bar.choose(nai.id) and s.detector_id == nai.id
    assert ctl.undo_context() and s.detector_id == ge.id and bar.selected_id() == ge.id
    assert ctl.undo_context() and s.detector is None and bar.selected_id() is None
    assert not s.status["results_stale"]                   # undo gives back the previous state
    assert not bar.btn_undo.isEnabled()
    # a profile deleted from the registry stays visible as the session's snapshot
    assert bar.choose(nai.id)
    reg.delete(nai.id)
    ctl.refresh()
    assert bar.selected_id() == nai.id and "NaI-B" in bar.det_combo.currentText()
    # the choice is saved with the session
    out = tmp_path / "a.smsession"
    assert ctl.save_session_to(out)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["detector_id"] == nai.id and doc["detector"]["name"] == "NaI-B"


def test_geometry_recorded_through_the_context_bar(window, tmp_path):
    window.load_file(spectrum_file(tmp_path / "data"))
    ctl = window.session_ctl
    g = MeasurementGeometry(name="Marinelli 1 L", kind="marinelli", container_id="MB-1000", fill_volume_ml=1000,
                            matrix="soil", density_g_cm3=1.3)
    ctl.ask_geometry = lambda current: g
    assert ctl.edit_geometry()
    assert window.session.geometry_id == g.id
    assert "Marinelli 1 L" in i18n.strip_bidi(ctl.context.geo_value.text())
    assert not ctl.edit_geometry()                         # unchanged: no edit
    assert ctl.undo_context() and window.session.geometry is None


def _curve_with_record(tmp_path, detector_id):
    from spectramaster.gui.efficiency_dialog import record_path_for
    from spectramaster.lab.calibration import CalibrationRecord
    from spectramaster.lab.common import to_plain
    from spectramaster.validation.benchmark import _flat_curve
    c = _flat_curve()
    p = c.save(tmp_path / "curves" / "flat.json")
    rec = CalibrationRecord.from_efficiency_curve(c, detector_id=detector_id, source="measured")
    record_path_for(p).write_text(json.dumps(to_plain(rec.to_dict())), encoding="utf-8")
    return p


def test_calibration_of_another_detector_is_incompatible(window, tmp_path):
    from spectramaster.gui.context_strings import ctr
    from spectramaster.gui.quant_panel import ActivityDialog
    from spectramaster.gui.workflow_strings import wtr
    reg = _registry()
    mine, other = DetectorProfile(name="Ge-mine"), DetectorProfile(name="Ge-other")
    reg.save(mine), reg.save(other)
    curve = _curve_with_record(tmp_path, other.id)
    window.load_file(spectrum_file(tmp_path / "data"))
    analyse(window)
    assert window.session_ctl.context.choose(mine.id)
    ad = ActivityDialog(window, window.current_spectrum(), window.settings)
    ad.message = lambda text: setattr(ad, "last_error", text)
    ad.set_curve_path(curve)
    text = i18n.strip_bidi(ad.detector_status.text())
    assert "Ge-mine" in text and "Ge-other" in text and ctr("act_det_mismatch") in text
    ad.nuc_edit.setText("Cs-137")
    assert ad.calculate() is not None, ad.last_error
    s = window.session
    eff = [c for c in s.calibrations if c["kind"] == "efficiency"]
    assert eff and eff[0]["detector_id"] == other.id
    rows = window.session_ctl.panel.rows()
    inc = [r for r in rows if r[1] == "incompatible_calibration"]
    assert inc and inc[0][0] == "error"
    assert i18n.strip_bidi(inc[0][2]).startswith(wtr("msg_other_detector").split("{")[0])
    # the same calibration for the right detector: compatible
    assert window.session_ctl.context.choose(other.id)
    assert "incompatible_calibration" not in _codes(window)
    ad.close()


def test_efficiency_wizard_offers_the_session_detector(window, tmp_path):
    from spectramaster.gui.efficiency_dialog import EfficiencyDialog, load_curve_file
    from spectramaster.validation.benchmark import _flat_curve
    reg = _registry()
    ge = DetectorProfile(name="Ge-W")
    reg.save(ge)
    window.load_file(spectrum_file(tmp_path / "data"))
    assert window.session_ctl.context.choose(ge.id)
    dlg = EfficiencyDialog(window, window.current_spectrum(), window.settings)
    assert dlg.detector_id() == ge.id
    dlg.curve = _flat_curve()
    rec = dlg.make_record()
    assert rec.detector_id == ge.id
    out = dlg.save_curve(str(tmp_path / "curves" / "w.json"))
    _c, rec2, _issues = load_curve_file(out)
    assert rec2 is not None and rec2.detector_id == ge.id
    # a loaded curve selects the detector of its record
    dlg.set_detector_id(None)
    assert dlg.detector_id() is None
    assert dlg.load_curve_dialog(str(out)) and dlg.detector_id() == ge.id
    dlg.close()


# ------------------------------------------------------------------ report
def test_report_html_has_library_concentrations_and_statuses(window, tmp_path):
    from spectramaster.gui import report as rp
    from spectramaster.gui.context_strings import ctr_in
    from spectramaster.gui.quant_panel import ActivityDialog
    from spectramaster.validation.benchmark import _flat_curve
    reg = _registry()
    ge = DetectorProfile(name="Ge-Report", serial="R-77")
    reg.save(ge)
    curve = _flat_curve().save(tmp_path / "curves" / "flat.json")
    window.load_file(spectrum_file(tmp_path / "data"))
    analyse(window)
    window.session_ctl.context.choose(ge.id)
    analyse(window)                                          # fresh results with the detector recorded
    ad = ActivityDialog(window, window.current_spectrum(), window.settings)
    ad.message = lambda text: setattr(ad, "last_error", text)
    ad.set_curve_path(curve)
    ad.nuc_edit.setText("Cs-137, K-40")
    ad.sample_box.set_matrix("soil")
    ad.sample_box.set_value("mass_kg", 1.0)
    assert ad.calculate() is not None, ad.last_error
    conc = window.quant_concentration
    assert conc is not None
    data = window.report_data()
    s = window.session
    assert data.has_session and data.library == s.processing_settings["identification_library"]
    assert data.concentration is conc and data.detector["id"] == ge.id
    assert {st["code"] for st in data.statuses} == _codes(window)
    # nothing is recalculated: the report uses the computed dict as it is
    before = json.dumps(conc, sort_keys=True, default=str)
    for lang in ("en", "ar"):
        opts = rp.ReportOptions(language=lang, plot=False)
        html = i18n.strip_bidi(rp.Report(data, opts).html())
        lib = i18n.tr_in(lang, "idl_short_" + data.library)
        assert ctr_in(lang, "rep_title") in html and lib in html
        assert "Ge-Report" in html and "R-77" in html
        for row in conc["rows"]:
            assert row["text"].replace("+-", "+-") in html.replace("&lt;", "<")
        for code in {st["code"] for st in data.statuses}:
            from spectramaster.gui.session_io import code_title
            assert code_title(code, lang) in html
        reportable = not any(st["level"] == "error" for st in data.statuses)
        assert ctr_in(lang, "rep_reportable_yes" if reportable else "rep_reportable_no") in html
    assert json.dumps(conc, sort_keys=True, default=str) == before
    # missing inputs are listed
    data.concentration = {"unit": "Bq/kg (dry)", "missing": ["sample mass (kg)"], "rows": [],
                          "notes": ["concentration not computed: missing sample mass (kg)"]}
    html = i18n.strip_bidi(rp.Report(data, rp.ReportOptions(language="en", plot=False)).html())
    assert ctr_in("en", "rep_conc_missing", items="sample mass (kg)") in html
    # the section can be switched off, and without a session it says so
    assert ctr_in("en", "rep_title") not in rp.Report(data, rp.ReportOptions(context=False, plot=False)).html()
    bare = rp.ReportData(spectrum=window.current_spectrum())
    html = rp.Report(bare, rp.ReportOptions(language="en", plot=False)).html()
    assert ctr_in("en", "rep_no_session") in html
    ad.close()


def test_report_pdf_with_context_renders(window, tmp_path):
    from spectramaster.gui import report as rp
    window.load_file(spectrum_file(tmp_path / "data"))
    analyse(window)
    data = window.report_data()
    assert data.has_session and data.statuses
    out = tmp_path / "r.pdf"
    assert rp.export_pdf(out, data, rp.ReportOptions(language="ar", plot=False)) >= 1
    assert out.stat().st_size > 1000


def test_context_strings_parity_and_arabic(window):
    from spectramaster.gui import context_strings as cs
    assert set(cs.EN) == set(cs.AR)
    for k in cs.EN:
        assert cs.AR[k].strip(), k
        assert set(re.findall(r"{(\w+)}", cs.EN[k])) == set(re.findall(r"{(\w+)}", cs.AR[k])), k
    window.apply_language("ar")
    bar = window.session_ctl.context
    assert bar.det_label.text() == cs.AR["detector"] and bar.btn_manage.text() == cs.AR["manage"]
    window.apply_language("en")
    assert bar.det_label.text() == cs.EN["detector"]


def test_fwhm_status_is_translated():
    from spectramaster.gui import workflow_strings as ws
    from spectramaster.gui.session_io import status_text
    from spectramaster.lab.workflow import WorkflowStatus
    msg = "no FWHM calibration: the default detector resolution is used, weak-peak areas may be biased by a few %"
    st = WorkflowStatus("outside_validated_scope", "warning", msg)
    assert status_text(st, "en") == ws.EN["msg_no_fwhm_cal"]
    assert status_text(st, "ar") == ws.AR["msg_no_fwhm_cal"]


def _tailed_cal_file(folder, name, seed):
    from spectramaster.convert import resolve_format, write_spectrum
    from spectramaster.validation import scenarios
    from spectramaster.validation.synthetic import HPGE, TruePeak, make_spectrum
    peaks = [TruePeak(e, 1.0e5, tail_frac=0.04, tail_slope=1.5, step_frac=0.001)
             for e in scenarios._energies(HPGE, "strong")]
    s = make_spectrum(HPGE, peaks, scenarios.base_continuum(HPGE), seed).spectrum
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    write_spectrum(s, p, resolve_format("aptec_s0"))
    return str(p)


def test_peak_shape_measured_in_the_registry_and_used_by_the_session(window, tmp_path):
    from spectramaster.analysis.peaks import peak_tail_of
    from spectramaster.gui.detector_picker import DetectorManagerDialog, peak_shape_text
    reg = _registry()
    ge = DetectorProfile(name="Ge-T", type="HPGe")
    reg.save(ge)
    dlg = DetectorManagerDialog(None, reg)
    dlg.select(ge.id)
    assert dlg.btn_shape.isEnabled()
    files = [_tailed_cal_file(tmp_path / "cal", f"c{i}.s0", 960000 + i) for i in range(2)]
    asked = []
    dlg.confirm = lambda title, text: asked.append(text) or True
    shape = dlg.measure_shape_selected(files)
    assert shape and shape["eta"] > 0 and shape["sources"] == ["c0.s0", "c1.s0"] and shape["measured"]
    assert asked and "Ge-T" in i18n.strip_bidi(asked[0])
    saved = reg.get(ge.id).peak_shape
    assert saved["eta"] == shape["eta"] and saved["tau"] == shape["tau"]
    assert "tail" in peak_shape_text(saved)
    # editing the profile keeps the shape
    from spectramaster.gui.detector_picker import DetectorEditor
    ed = DetectorEditor(None, reg.get(ge.id))
    ed.edits["serial"].setText("SN 1")
    assert ed.profile().peak_shape == saved
    # a detector measured without a significant tail: recorded as Gaussian (eta = 0)
    weak = DetectorProfile(name="Ge-W", type="HPGe")
    reg.save(weak)
    dlg.refresh_list(weak.id)
    g = dlg.measure_shape_selected([str(spectrum_file(tmp_path / "w"))])
    assert g["eta"] == 0.0 and g["n_peaks"] >= 2 and "Gaussian" in peak_shape_text(g)
    # too few strong peaks: refused, nothing recorded
    from spectramaster.convert import resolve_format, write_spectrum
    from spectramaster.validation.synthetic import HPGE, Continuum, TruePeak, make_spectrum
    one = make_spectrum(HPGE, [TruePeak(661.657, 2e4)], Continuum(300, 400, 10), 7).spectrum
    p1 = tmp_path / "one.s0"
    write_spectrum(one, p1, resolve_format("aptec_s0"))
    other = DetectorProfile(name="Ge-1pk", type="HPGe")
    reg.save(other)
    dlg.refresh_list(other.id)
    errs = []
    dlg.show_error = errs.append
    assert dlg.measure_shape_selected([str(p1)]) is None
    assert errs and reg.get(other.id).peak_shape == {}
    # the session with this detector fits the displayed spectrum with the shape
    window.load_file(spectrum_file(tmp_path / "data"))
    ctl = window.session_ctl
    spec = window.current_spectrum()
    assert peak_tail_of(spec) is None
    assert ctl.context.choose(ge.id)
    assert peak_tail_of(spec) == (saved["eta"], saved["tau"])
    analyse(window)
    assert window.session.detector["peak_shape"]["eta"] == saved["eta"]      # snapshot in the session
    # a detector measured as Gaussian: no tail term, but the shape is calibrated (residual search)
    from spectramaster.analysis.peaks import shape_calibrated
    assert ctl.context.choose(weak.id)
    assert peak_tail_of(spec) is None and shape_calibrated(spec)
    # a detector never measured: Gaussian peaks, not calibrated
    assert ctl.context.choose(other.id)
    assert not shape_calibrated(spec) and "peak_tail_source" not in spec.extra


def test_peak_shape_button_measures_on_a_worker_thread(window, tmp_path):
    import time

    from PySide6.QtWidgets import QApplication

    from spectramaster.gui.detector_picker import DetectorManagerDialog
    reg = _registry()
    ge = DetectorProfile(name="Ge-Th", type="HPGe")
    reg.save(ge)
    dlg = DetectorManagerDialog(None, reg)
    dlg.select(ge.id)
    files = [_tailed_cal_file(tmp_path / "cal", f"c{i}.s0", 961000 + i) for i in range(2)]
    dlg.ask_spectrum_files = lambda: files
    asked = []
    dlg.confirm = lambda title, text: asked.append(text) or True
    dlg.btn_shape.click()                                   # the button: threaded
    assert dlg.busy and dlg.busy_label.text() and not dlg.btn_shape.isEnabled()
    assert dlg.measure_shape_selected(files) is None       # refused while one is running
    end = time.monotonic() + 60
    while dlg.busy and time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.01)
    assert not dlg.busy and dlg.busy_label.text() == "" and dlg.btn_shape.isEnabled()
    assert len(asked) == 1 and reg.get(ge.id).peak_shape["eta"] > 0
    # an unreadable file: the error comes back to the dialog, nothing recorded
    bad = tmp_path / "bad.xyz"
    bad.write_text("not a spectrum", encoding="utf-8")
    other = DetectorProfile(name="Ge-Bad", type="HPGe")
    reg.save(other)
    dlg.refresh_list(other.id)
    errs = []
    dlg.show_error = errs.append
    dlg.ask_spectrum_files = lambda: [str(bad)]
    dlg.btn_shape.click()
    end = time.monotonic() + 30
    while dlg.busy and time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.01)
    assert errs and "_ReadError" not in errs[0] and reg.get(other.id).peak_shape == {}

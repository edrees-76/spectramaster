"""Efficiency-calibration wizard and the activity dialog's geometry check (Release D4, GUI; headless)."""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from spectramaster.analysis import efficiency as eff
from spectramaster.gui import i18n
from spectramaster.validation.scenarios import efficiency_calibration, true_efficiency
from spectramaster.validation.synthetic import HPGE

MARINELLI = dict(container="MB-1000", nominal="1000", diameter="130", fill_volume="1000", matrix="water",
                 density="1.0")


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


@pytest.fixture(scope="module")
def realisations():
    return list(efficiency_calibration(HPGE, 2))


@pytest.fixture()
def settings(tmp_path, monkeypatch):
    from spectramaster.gui.settings import Settings
    monkeypatch.setenv("SPECTRAMASTER_EFF_DIR", str(tmp_path / "curves"))
    i18n.set_language("en")
    yield Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat))
    i18n.set_language("en")


def wait_idle(dlg, timeout=120.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QApplication.processEvents()
        if not dlg.busy:
            QApplication.processEvents()
            return True
        time.sleep(0.01)
    return False


def cert_entries(lines, suffix=""):
    """CertNuclide rows (explicit lines and half-lives) of the scenario's certificate lines."""
    by = {}
    for ln in lines:
        by.setdefault(ln.nuclide, []).append(ln)
    return [eff.CertNuclide(nm + suffix, ls[0].activity, ls[0].activity_unc, ls[0].ref_date, ls[0].half_life_s,
                            [(l.energy, l.intensity) for l in ls]) for nm, ls in by.items()]


def make_dialog(settings, syn, cert, geometry=None, messages=None):
    from spectramaster.gui.efficiency_dialog import EfficiencyDialog
    dlg = EfficiencyDialog(None, syn.spectrum, settings)
    msgs = messages if messages is not None else []
    dlg._msg = lambda text, error=True: msgs.append(text)
    dlg.messages = msgs
    dlg.set_certificate(cert_entries(cert))
    if geometry:
        fill_marinelli(dlg.geo, "1 L Marinelli", **geometry)
    return dlg


def fill_marinelli(geo, name, container="", nominal="", diameter="", fill_volume="", fill_height="",
                   matrix="", density=""):
    geo.name_edit.setText(name)
    geo.kind_combo.setCurrentIndex(geo.kind_combo.findData("marinelli"))
    geo.container_edit.setText(container)
    geo.nominal_edit.setText(nominal)
    geo.dim_edits["diameter_mm"].setText(diameter)
    geo.fill_volume_edit.setText(fill_volume)
    geo.fill_height_edit.setText(fill_height)
    geo.matrix_edit.setText(matrix)
    geo.density_edit.setText(density)


# ------------------------------------------------------------------ geometry
def test_geometry_editor_round_trip_keeps_unknowns_none(qapp, settings, realisations, tmp_path):
    syn, cert = realisations[0]
    dlg = make_dialog(settings, syn, cert)
    fill_marinelli(dlg.geo, "1 L Marinelli", container="MB-1000", nominal="1000", diameter="130",
                   fill_volume="1000", matrix="water")                  # density, fill height unknown
    dlg.model_combo.setCurrentIndex(dlg.model_combo.findData("loglog"))
    assert dlg.measure_and_fit()
    rec = dlg.curve.geometry_record
    assert rec["kind"] == "marinelli" and rec["name"] == "1 L Marinelli" == dlg.curve.geometry
    assert rec["container_id"] == "MB-1000" and rec["nominal_volume_ml"] == 1000.0
    assert rec["dimensions"] == {"diameter_mm": 130.0}                  # empty dimensions are absent
    assert rec["density_g_cm3"] is None and rec["fill_height_mm"] is None
    assert rec["source_distance_mm"] is None and rec["filter_dimensions"] == {}
    # file round trip into a fresh dialog: empty fields stay empty
    path = dlg.save_curve(str(tmp_path / "geo.json"))
    from spectramaster.gui.efficiency_dialog import EfficiencyDialog
    d2 = EfficiencyDialog(None, None, settings)
    d2._msg = lambda *a, **k: None
    assert d2.load_curve_dialog(str(path))
    assert d2.geo.kind() == "marinelli" and d2.geom_edit.text() == "1 L Marinelli"
    assert d2.geo.density_edit.text() == "" and d2.geo.fill_height_edit.text() == ""
    assert d2.geo.geometry().to_dict() == rec                           # same id and values
    # a typing error is reported, never stored as 0
    dlg.geo.density_edit.setText("abc")
    assert not dlg.refit()
    assert dlg.messages and "abc" in dlg.messages[-1]
    # nothing entered -> geometry "not recorded"
    dlg.geo.set_geometry(None)
    assert dlg.refit() and dlg.curve.geometry_record == {}
    dlg.close(), d2.close()


# ------------------------------------------------------------------ exclusions, model
def test_exclusion_requires_a_reason(qapp, settings, realisations):
    syn, cert = realisations[0]
    dlg = make_dialog(settings, syn, cert)
    assert dlg.measure_and_fit()
    row = next(i for i, p in enumerate(dlg.points) if p.nuclide == "Cs-137")
    n_used = sum(p.use for p in dlg.curve.points)
    dlg.ask_reason = lambda label: ""                                   # no reason -> refused
    assert not dlg.set_point_used(row, False)
    assert dlg.points[row].use and dlg.pt_table.item(row, 0).checkState() == Qt.Checked
    assert dlg.messages[-1] == i18n.tr("quant_eff_reason_required")
    dlg.ask_reason = lambda label: None                                 # cancelled -> refused, no message
    n_msg = len(dlg.messages)
    assert not dlg.set_point_used(row, False) and len(dlg.messages) == n_msg
    dlg.ask_reason = lambda label: "suspected; pile-up"
    assert dlg.set_point_used(row, False)
    p = dlg.points[row]
    assert not p.use and p.note.startswith("excluded by user: suspected, pile-up")
    assert sum(q.use for q in dlg.curve.points) == n_used - 1
    assert dlg.pt_table.item(row, 0).checkState() == Qt.Unchecked
    assert dlg.pt_table.item(row, 8).text().startswith("excluded by user")
    assert "1" in dlg.warn_label.text()                                  # "1 point(s) excluded by the user"
    assert dlg.set_point_used(row, True) and "excluded by user" not in dlg.points[row].note
    # unticking in the table asks for the reason and refits on the worker thread
    reasons = []
    dlg.ask_reason = lambda label: reasons.append(label) or "peak shape"
    dlg.pt_table.item(row, 0).setCheckState(Qt.Unchecked)
    assert wait_idle(dlg)
    assert reasons and "Cs-137" in reasons[0]
    assert not dlg.points[row].use and dlg.points[row].note.startswith("excluded by user: peak shape")
    assert not next(q for q in dlg.curve.points if q is dlg.points[row]).use
    # summing warnings of cascade emitters are shown in the notes
    co = next(i for i, q in enumerate(dlg.points) if q.nuclide == "Co-60")
    assert eff.TCS_NOTE in dlg.pt_table.item(co, 8).text()
    dlg.close()


def test_auto_model_shows_selection_and_outliers(qapp, settings, realisations):
    syn, cert = realisations[0]
    dlg = make_dialog(settings, syn, cert)
    assert dlg.order_mode.currentData() == "auto"
    assert dlg.measure_and_fit(threaded=True)
    assert dlg.busy and wait_idle(dlg) and dlg.curve is not None
    c = dlg.curve
    assert "cross-validation" in c.selection and c.selection in dlg.selection_label.text()
    assert "χ²" in dlg.summary.text() and "dof" in dlg.summary.text()
    assert c.efficiency(661.66) == pytest.approx(true_efficiency(HPGE, 661.66), rel=0.03)
    assert dlg.order_spin.value() == c.order                            # chosen orders shown
    # explicit orders keep working
    dlg.order_mode.setCurrentIndex(dlg.order_mode.findData("explicit"))
    dlg.model_combo.setCurrentIndex(dlg.model_combo.findData("loglog"))
    dlg.order_spin.setValue(3)
    assert dlg.refit()
    assert dlg.curve.model == "loglog" and dlg.curve.order == 3 and dlg.curve.selection == ""
    assert dlg.selection_label.text() == i18n.tr("quant_eff_selection_explicit")
    # common standard uncertainty: empty = not stated, else passed as u_sys_rel
    assert dlg.curve.u_common_rel == 0.0
    dlg.u_common_edit.setText("1.5")
    assert dlg.refit() and dlg.curve.u_common_rel == pytest.approx(0.015)
    dlg.u_common_edit.setText("x")
    assert not dlg.refit()
    dlg.u_common_edit.setText("")
    # a point far from the curve is listed prominently
    cs = next(p for p in dlg.points if p.nuclide == "Cs-137")
    cs.efficiency *= 1.5
    assert dlg.refit() and dlg.curve.warnings
    assert dlg.warn_list.count() == len(dlg.curve.warnings) and not dlg.warn_list.isHidden()
    assert "3 σ" in dlg.warn_label.text()
    dlg.plot.resize(500, 400)
    dlg.plot.grab()
    dlg.close()


# ------------------------------------------------------------------ validation, record
def test_independent_validation_and_record(qapp, settings, realisations, tmp_path):
    from spectramaster.gui.efficiency_dialog import load_curve_file, record_path_for
    (syn, cert), (syn2, cert2) = realisations
    dlg = make_dialog(settings, syn, cert, geometry=MARINELLI)
    assert dlg.measure_and_fit()
    assert dlg.curve.validation_status == "unvalidated" and not dlg.btn_mark.isEnabled()
    assert not dlg.mark_validated("x")                                  # no check yet
    # an inconsistent check (certificate activities wrong by a factor 2) cannot validate
    dlg.set_validation_spectrum(syn2.spectrum)
    bad = cert_entries(cert2, " (check)")
    for c in bad:
        c.activity *= 0.5
        c.activity_unc *= 0.5
    dlg.val_cert.set_certificate(bad)
    assert dlg.measure_validation()
    assert dlg.validation["n"] > 0 and not dlg.validation["consistent"]
    assert not dlg.btn_mark.isEnabled() and not dlg.mark_validated("x")
    # the second realisation with independent (renamed) nuclides is consistent
    dlg.val_cert.set_certificate(cert_entries(cert2, " (check)"))
    assert dlg.measure_validation(threaded=True) and wait_idle(dlg)
    v = dlg.validation
    assert v["consistent"] and v["n"] == dlg.val_table.rowCount() and v["message"] == dlg.val_message.text()
    assert dlg.btn_mark.isEnabled()
    dlg.ask_validation_note = lambda: ""
    assert not dlg.mark_validated("")                                   # a note is required
    assert dlg.curve.validation_status == "unvalidated"
    assert dlg.mark_validated("second source, checked by EF")
    assert dlg.curve.validation_status == "validated"
    assert i18n.tr("quant_eff_status_validated") in dlg.status_label.text()
    assert i18n.tr("quant_eff_status_validated") in dlg.summary.text()
    path = dlg.save_curve(str(tmp_path / "curves" / "marinelli.json"))
    rp = record_path_for(path)
    assert path.is_file() and rp.is_file() and dlg.record_path == rp
    d = json.loads(rp.read_text(encoding="utf-8"))
    assert d["kind"] == "efficiency" and d["validation_status"] == "validated" and d["source"] == "measured"
    assert "second source, checked by EF" in d["validation_note"] and "consistent" in d["validation_note"]
    assert d["geometry_id"] == dlg.curve.geometry_record["id"]
    curve, rec, issues = load_curve_file(path)
    assert curve.validation_status == "validated" and rec is not None and rec.integrity_ok() and not issues
    curve2, _r, _i = load_curve_file(rp)                                 # the record itself loads too
    assert curve2.validation_status == "validated" and curve2.params == curve.params
    # the existing curve format still loads on its own
    assert eff.load_curve(path).params == dlg.curve.params
    # a new fit is a new, unvalidated curve
    assert dlg.refit() and dlg.curve.validation_status == "unvalidated"
    assert dlg.btn_mark.isEnabled()                                     # re-checked automatically
    # a curve claiming "validated" without its record is not trusted
    lone = tmp_path / "lone.json"
    dd = json.loads(path.read_text(encoding="utf-8"))
    lone.write_text(json.dumps(dd), encoding="utf-8")
    c3, r3, iss3 = load_curve_file(lone)
    assert dd["validation_status"] == "validated" and c3.validation_status == "unvalidated" and r3 is None and iss3
    dlg.close()


# ------------------------------------------------------------------ activity dialog
def _calibration(settings, realisations, tmp_path, validated=False):
    (syn, cert), (syn2, cert2) = realisations
    dlg = make_dialog(settings, syn, cert, geometry=MARINELLI)
    assert dlg.measure_and_fit()
    if validated:
        dlg.set_validation_spectrum(syn2.spectrum)
        dlg.val_cert.set_certificate(cert_entries(cert2, " (check)"))
        assert dlg.measure_validation() and dlg.mark_validated("ok")
    path = dlg.save_curve(str(eff.default_curve_dir() / "marinelli.json"))
    dlg.close()
    return path


def _activity_dialog(settings, spectrum, path):
    from spectramaster.gui.quant_panel import ActivityDialog
    ad = ActivityDialog(None, spectrum, settings)
    ad.message = lambda text: setattr(ad, "last_error", text)
    ad.set_curve_path(path)
    ad.nuc_edit.setText("Cs-137, Co-60")
    return ad


def test_activity_refuses_incompatible_geometry_unless_overridden(qapp, settings, realisations, tmp_path):
    path = _calibration(settings, realisations, tmp_path)
    syn2 = realisations[1][0]
    ad = _activity_dialog(settings, syn2.spectrum, path)
    # the curve list hides the record file; its status is shown with the curve
    assert ad.curve_combo.count() == 1
    assert i18n.tr("quant_eff_status_unvalidated") in ad.curve_status.text()
    assert "1 L Marinelli" in ad.curve_status.text()
    ad.geo_check.setChecked(True)
    ad.geo.name_edit.setText("point source 10 cm")
    ad.geo.kind_combo.setCurrentIndex(ad.geo.kind_combo.findData("point"))
    ad.geo.distance_edit.setText("100")
    asked = []
    ad.confirm_mismatch = lambda text: asked.append(text) or False
    assert ad.calculate() is None and ad.results is None
    assert asked and "different geometry kind" in asked[0]
    assert "different geometry kind" in ad.notes_label.text()
    ad.confirm_mismatch = lambda text: True                              # explicit "use anyway"
    res = ad.calculate()
    assert res is not None
    assert any(n.startswith("geometry mismatch accepted by the user") for n in res.notes)
    assert i18n.tr("quant_act_note_mismatch", text="").split(":")[0] in ad.notes_label.text()
    assert i18n.tr("quant_act_note_unvalidated") in ad.notes_label.text()
    # the same geometry passes without asking
    ad.geo.set_geometry(None)
    fill_marinelli(ad.geo, "soil sample", **MARINELLI)
    ad.confirm_mismatch = lambda text: pytest.fail("must not ask for a compatible geometry")
    res = ad.calculate()
    assert res is not None and not any("geometry" in n for n in res.notes)
    cs = next(r for r in res.nuclides if r.nuclide == "Cs-137")
    assert cs.detected and cs.activity == pytest.approx(500.0, rel=0.15)
    # a different fill volume is a different geometry
    ad.geo.fill_volume_edit.setText("500")
    ad.confirm_mismatch = lambda text: asked.append(text) or False
    assert ad.calculate() is None and "fill volume" in asked[-1]
    # sample geometry unchecked: calculated, the note says it was not checked
    ad.geo_check.setChecked(False)
    res = ad.calculate()
    assert res is not None and any(n.startswith("sample geometry not given") for n in res.notes)
    assert i18n.tr("quant_act_note_geo_not_given") in ad.notes_label.text()
    ad.close()


def test_activity_shows_validated_calibration(qapp, settings, realisations, tmp_path):
    path = _calibration(settings, realisations, tmp_path, validated=True)
    ad = _activity_dialog(settings, realisations[1][0].spectrum, path)
    assert i18n.tr("quant_eff_status_validated") in ad.curve_status.text()
    ad.geo_check.setChecked(True)
    fill_marinelli(ad.geo, "soil sample", **MARINELLI)
    res = ad.calculate()
    assert res is not None and not any("validated" in n for n in res.notes)
    assert i18n.tr("quant_act_note_unvalidated") not in ad.notes_label.text()
    ad.close()


def test_background_spectrum_is_passed_to_the_engine(qapp, settings, realisations, monkeypatch):
    (syn, cert), (syn2, _c2) = realisations
    dlg = make_dialog(settings, syn, cert)
    seen = []
    real = eff.measure_efficiency
    monkeypatch.setattr(eff, "measure_efficiency",
                        lambda spec, lines, background=None, **kw: seen.append(background) or real(spec, lines, **kw))
    assert dlg.measure_and_fit() and seen[-1] is None
    dlg.set_background(syn2.spectrum)
    assert dlg.bkg_edit.text()
    dlg.measure_and_fit()
    assert seen[-1] is syn2.spectrum
    dlg.set_background(None)
    assert dlg.background is None and dlg.bkg_edit.text() == ""
    dlg.close()


# ------------------------------------------------------------------ Arabic
def test_arabic_wizard_renders(qapp, settings, realisations, tmp_path):
    from spectramaster.gui.efficiency_dialog import EfficiencyDialog
    from spectramaster.gui.quant_panel import ActivityDialog
    syn, cert = realisations[0]
    i18n.set_language("ar")
    dlg = make_dialog(settings, syn, cert, geometry=MARINELLI)
    assert dlg.layoutDirection() == Qt.RightToLeft
    assert dlg.tabs.tabText(3) == i18n.STRINGS["ar"]["quant_eff_tab_validation"]
    assert dlg.geo.kind_combo.currentText() == i18n.STRINGS["ar"]["quant_geo_kind_marinelli"]
    assert dlg.measure_and_fit()
    assert i18n.STRINGS["ar"]["quant_eff_status_unvalidated"] in dlg.status_label.text()
    assert dlg.selection_label.text().startswith("اختيار النموذج")
    dlg.show()
    for i in range(dlg.tabs.count()):
        dlg.tabs.setCurrentIndex(i)
        QApplication.processEvents()
        dlg.grab()
    path = dlg.save_curve(str(tmp_path / "ar.json"))
    dlg.close()
    ad = ActivityDialog(None, syn.spectrum, settings)
    ad.message = lambda text: None
    ad.set_curve_path(path)
    ad.nuc_edit.setText("Cs-137")
    assert ad.calculate() is not None
    assert i18n.STRINGS["ar"]["quant_act_note_unvalidated"] in ad.notes_label.text()
    ad.geo_check.setChecked(True)
    ad.show()
    QApplication.processEvents()
    ad.grab()
    ad.close()
    EfficiencyDialog(None, None, settings).close()

"""Workflow statuses, review and the traceable report record (Release F, F1)."""
from __future__ import annotations

import json

import pytest

from spectramaster.analysis import find_peaks, identify
from spectramaster.analysis import efficiency as eff
from spectramaster.analysis.activity import ActivityOptions, compute_activities, concentrations
from spectramaster.lab.calibration import CalibrationRecord
from spectramaster.lab.detector import DetectorProfile, MeasurementGeometry
from spectramaster.lab.sample import SampleInfo
from spectramaster.lab.session import AnalysisSession
from spectramaster.lab.workflow import mark_reviewed, report_record, workflow_status, write_report_json
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE


def _codes(st):
    return {s.code for s in st}


@pytest.fixture()
def setup():
    syn, cert = next(scenarios.efficiency_calibration(HPGE, 1))
    curve = eff.fit_efficiency(eff.measure_efficiency(syn.spectrum, cert), "two_branch", crossover="auto")
    mar = MeasurementGeometry("Marinelli 1 L", kind="marinelli", container_id="M-1000", fill_volume_ml=1000.0,
                              matrix="soil", density_g_cm3=1.3)
    curve.geometry_record = mar.to_dict()
    rec = CalibrationRecord.from_efficiency_curve(curve, source="measured", geometry_id=mar.id)
    s = AnalysisSession()
    return syn, curve, mar, rec, s


def test_statuses_follow_the_workflow(setup):
    syn, curve, mar, rec, s = setup
    st = workflow_status(s, syn.spectrum)
    assert {"calibration_required", "no_results"} <= _codes(st)
    s.set_geometry(mar)
    s.set_calibration(rec)
    st = workflow_status(s, syn.spectrum)
    assert "calibration_required" not in _codes(st)
    assert any(x.code == "outside_validated_scope" and "unvalidated" in x.message for x in st)
    pk = find_peaks(syn.spectrum)
    q = compute_activities(syn.spectrum, curve, ActivityOptions(nuclides=["Cs-137"], geometry=mar))
    s.set_results(pk, identify(syn.spectrum, pk), q, spectrum=syn.spectrum)
    assert "not_reviewed" in _codes(workflow_status(s, syn.spectrum))
    with pytest.raises(ValueError):
        mark_reviewed(s, " ")
    mark_reviewed(s, "A. Analyst", "peaks checked")
    assert "reviewed" in _codes(workflow_status(s, syn.spectrum))
    s.mark_stale("efficiency calibration changed")
    st = workflow_status(s, syn.spectrum)
    assert "results_stale" in _codes(st) and "reviewed" not in _codes(st)
    with pytest.raises(ValueError):
        mark_reviewed(s, "A. Analyst")


def test_calibration_of_another_geometry_is_an_error(setup):
    syn, _curve, _mar, rec, s = setup
    s.set_geometry(MeasurementGeometry("point source", kind="point", source_distance_mm=100.0))
    s.set_calibration(rec)
    st = workflow_status(s, syn.spectrum)
    assert any(x.code == "incompatible_calibration" and x.level == "error" for x in st)


def test_report_record_traces_everything(setup, tmp_path):
    syn, curve, mar, rec, s = setup
    s.set_detector(DetectorProfile("HPGe 40 %", type="HPGe"))
    s.set_geometry(mar)
    sample = SampleInfo(matrix_type="soil", mass_kg=1.3, mass_basis="dry")
    s.set_sample(sample)
    s.set_calibration(rec)
    pk = find_peaks(syn.spectrum)
    q = compute_activities(syn.spectrum, curve, ActivityOptions(nuclides=["Cs-137"], geometry=mar))
    s.set_results(pk, identify(syn.spectrum, pk), q, spectrum=syn.spectrum)
    conc = concentrations(q, sample, "Bq/kg")
    d = json.loads(write_report_json(tmp_path / "r.json", s, conc, syn.spectrum).read_text(encoding="utf-8"))
    assert d["application"]["session_id"] == s.session_id and d["application"]["app_version"]
    assert d["calibrations"][0]["content_hash"] == rec.content_hash
    assert d["calibrations"][0]["validation_status"] == "unvalidated"
    assert d["results"]["concentrations"]["unit"] == "Bq/kg (dry)"
    assert d["conventions"]["weight_basis"] == "dry" and "never as zero" in d["conventions"]["non_detects"]
    assert d["reportable"] is True and any(st["code"] == "not_reviewed" for st in d["statuses"])
    assert d["edits"] and all(e["time"] for e in d["edits"])

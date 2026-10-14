"""Experimental efficiency calibration (Release D): uncertainty components counted once and
with their correlations (D1); coincidence-summing warnings, geometry guard and validation status
(D2)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from spectramaster.analysis import efficiency as eff
from spectramaster.analysis.activity import ActivityOptions, compute_activities
from spectramaster.lab.calibration import CalibrationRecord
from spectramaster.lab.detector import MeasurementGeometry
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE


def _pt(e, nuclide, ua=0.02, uc=0.01, ui=0.0):
    t = float(scenarios.true_efficiency(HPGE, e))
    return eff.EfficiencyPoint(e, t, t * math.sqrt(ua ** 2 + uc ** 2 + ui ** 2), nuclide, u_count_rel=uc,
                               u_ref_rel=math.hypot(ua, ui), u_act_rel=ua, u_int_rel=ui, group=nuclide)


@pytest.fixture(scope="module")
def cal():
    syn, cert = next(scenarios.efficiency_calibration(HPGE, 1))
    pts = eff.measure_efficiency(syn.spectrum, cert)
    return syn, pts, eff.fit_efficiency(pts, "two_branch", crossover="auto")


# ------------------------------------------------------------------ D1
def test_lines_of_one_nuclide_share_the_activity_component():
    pts = [_pt(1173.2, "Co-60"), _pt(1332.5, "Co-60"), _pt(661.7, "Cs-137")]
    V = eff.point_covariance(pts)
    assert V[0, 1] == pytest.approx(0.02 ** 2)
    assert V[0, 2] == 0.0
    assert V[0, 0] == pytest.approx(0.02 ** 2 + 0.01 ** 2)
    Vc = eff.point_covariance(pts, u_common=0.01)
    assert Vc[0, 2] == pytest.approx(0.01 ** 2)


def test_certificate_uncertainty_is_not_added_twice(cal):
    _syn, pts, c = cal
    assert c.cov_method == "gls" and c.u_sys_rel == 0.0
    c2 = eff.fit_efficiency(pts, "two_branch", crossover="auto", u_sys_rel=0.03)
    # a stated common component is a floor of the curve uncertainty (it cannot average down)
    assert c2.rel_uncertainty(661.7) >= 0.03 * 0.99
    assert c2.u_common_rel == 0.03


def test_curves_saved_before_release_d_keep_their_uncertainty():
    old = {"model": "loglog", "params": [math.log(0.01), -0.9, 0.0, 0.0], "order": 3, "e_ref": 1000.0,
           "cov": [[1e-6 if i == j else 0.0 for j in range(4)] for i in range(4)], "u_sys_rel": 0.02,
           "e_min": 60.0, "e_max": 1800.0, "points": []}
    c = eff.EfficiencyCurve.from_dict(old)
    assert c.rel_uncertainty(661.7) == pytest.approx(math.sqrt(1e-6 * (1 + math.log(0.6617) ** 2) + 0.02 ** 2),
                                                     rel=0.05)


# ------------------------------------------------------------------ D2
def test_cascade_emitter_points_carry_a_summing_warning(cal):
    _syn, pts, _c = cal
    co = [p for p in pts if p.nuclide in ("Co-60", "Y-88")]
    assert co and all("summing" in p.note for p in co)
    assert not any("summing" in p.note for p in pts if p.nuclide == "Cs-137")


def test_calibration_of_another_geometry_is_refused_unless_overridden(cal):
    syn, _pts, c = cal
    c.geometry_record = MeasurementGeometry("point source 10 cm", kind="point", source_distance_mm=100.0).to_dict()
    mar = MeasurementGeometry("Marinelli 1 L", kind="marinelli")
    with pytest.raises(ValueError, match="another measurement geometry"):
        compute_activities(syn.spectrum, c, ActivityOptions(nuclides=["Cs-137"], geometry=mar))
    q = compute_activities(syn.spectrum, c, ActivityOptions(nuclides=["Cs-137"], geometry=mar,
                                                            allow_geometry_mismatch=True))
    assert any("geometry mismatch accepted" in n for n in q.notes)
    same = MeasurementGeometry("point source 10 cm", kind="point", source_distance_mm=100.0)
    q = compute_activities(syn.spectrum, c, ActivityOptions(nuclides=["Cs-137"], geometry=same))
    assert not any("geometry" in n for n in q.notes)


def test_validation_status_is_reported_and_does_not_change_the_record_hash(cal):
    syn, _pts, c = cal
    rec = CalibrationRecord.from_efficiency_curve(c, source="measured")
    h = rec.content_hash
    q = compute_activities(syn.spectrum, rec.to_efficiency_curve(), ActivityOptions(nuclides=["Cs-137"]))
    assert any("unvalidated" in n for n in q.notes)
    rec.set_validation("validated", "checked against an independent Eu-152 source")
    assert rec.content_hash == h
    q = compute_activities(syn.spectrum, rec.to_efficiency_curve(), ActivityOptions(nuclides=["Cs-137"]))
    assert not any("unvalidated" in n for n in q.notes)


# ------------------------------------------------------------------ D3
def test_orders_are_chosen_by_cross_validation_and_explicit_orders_are_kept(cal):
    _syn, pts, c = cal
    assert "leave-one-out" in c.selection
    fixed = eff.fit_efficiency(pts, "two_branch", order=3, order_high=2, crossover=200.0)
    assert (fixed.order, fixed.order_high, fixed.e_ref) == (3, 2, 200.0) and fixed.selection == ""


def test_model_error_appears_when_the_truth_is_outside_the_model():
    syn, cert = next(scenarios.efficiency_calibration(HPGE, 1, shape="kinked"))
    pts = eff.measure_efficiency(syn.spectrum, cert)
    kinked = eff.fit_efficiency(pts, "loglog", order=2)
    syn2, cert2 = next(scenarios.efficiency_calibration(HPGE, 1))
    smooth = eff.fit_efficiency(eff.measure_efficiency(syn2.spectrum, cert2), "loglog", order=3)
    assert kinked.u_model_rel > smooth.u_model_rel
    assert kinked.u_model_rel > 0.02


def test_points_far_from_the_curve_are_listed_for_review():
    pts = [_pt(e, nm) for e, nm in ((60, "Am-241"), (122, "Co-57"), (166, "Ce-139"), (279, "Hg-203"),
                                     (392, "Sn-113"), (662, "Cs-137"), (898, "Y-88"), (1173, "Co-60"),
                                     (1332, "Co-60"), (1836, "Y-88"))]
    bad = _pt(514.0, "Sr-85")
    bad.efficiency *= 1.2
    c = eff.fit_efficiency(pts + [bad], "loglog", order=3)
    assert any(w.startswith("Sr-85 514.0 keV") for w in c.warnings)


def test_independent_validation_accepts_a_consistent_source_and_rejects_a_wrong_curve(cal):
    _syn, _pts, c = cal
    # a second, independent measurement of the same true efficiency
    syn2, cert2 = list(scenarios.efficiency_calibration(HPGE, 2))[1]
    other = eff.measure_efficiency(syn2.spectrum, cert2)
    for p in other:
        p.nuclide = p.nuclide + " (check source)"
    v = eff.validate_curve(c, other)
    assert v["n"] >= 8 and v["consistent"], v["message"]
    wrong = eff.EfficiencyCurve.from_dict(c.to_dict())
    wrong.params = list(wrong.params)
    wrong.params[0] += math.log(1.10)                     # curve 10 % too high
    assert not eff.validate_curve(wrong, other)["consistent"]
    assert eff.validate_curve(c, c.points)["n"] == 0      # the fit's own points are not a check

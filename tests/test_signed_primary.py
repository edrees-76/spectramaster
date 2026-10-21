"""Signed primary result of lines without a search peak (docs/baseline/signed_primary_protocol.md).
The statistical criteria are evaluated by spectramaster.validation.primary; these tests check the
mechanics."""
from __future__ import annotations

import math

import numpy as np
import pytest

from spectramaster.analysis import activity as act
from spectramaster.validation import primary as pr
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE, TruePeak, area_for_snr, continuum_counts, make_spectrum


@pytest.fixture(scope="module")
def curve():
    return pr._flat_curve()


def _spectrum(peaks=(), seed=1, det=HPGE):
    return make_spectrum(det, list(peaks), scenarios.base_continuum(det), seed).spectrum


def _cs(res):
    return pr._line(res, "Cs-137", pr.CS)


def test_window_net_is_the_estimator_of_the_decision_threshold():
    sp = _spectrum()
    fw = np.full(len(sp.counts), 3.0)
    lo, hi, m, frac = act.line_window(sp, pr.CS, fw)
    y = np.asarray(sp.counts, float)
    g, side = y[lo:hi + 1].sum(), y[lo - m:lo].sum() + y[hi + 1:hi + 1 + m].sum()
    r = (hi - lo + 1) / (2 * m)
    net, var = act.window_net(sp, pr.CS, fw)
    assert net == pytest.approx(g - side * r) and var == pytest.approx(g + side * r * r)
    b, n, mm, f = act.continuum_under(sp, pr.CS, fw)
    assert (n, mm, f) == (hi - lo + 1, m, frac) and b == pytest.approx(side * r)


def test_line_without_peak_gets_a_signed_window_result(curve):
    res = act.compute_activities(_spectrum(), curve, act.ActivityOptions(nuclides=["Cs-137"],
                                                                          mda_method="iso11929"))
    r, ln = _cs(res)
    assert not ln.peak_found and ln.activity is None and not r.detected
    assert ln.primary_method == "window" and ln.primary is not None and ln.primary_net_unc > 0
    assert r.primary == ln.primary and r.primary_u >= ln.primary_u_count
    assert r.best_estimate is not None and r.best_estimate >= 0 and r.coverage_low <= r.coverage_high
    assert any("decision rule: a search peak" in n for n in res.notes)
    row = act.result_row(r)
    assert row["primary_bq"] == r.primary and row["primary_method"] == "window" and row["activity_bq"] is None


def test_found_peak_primary_is_the_activity(curve):
    cy = continuum_counts(HPGE, scenarios.base_continuum(HPGE))
    sp = _spectrum([TruePeak(pr.CS, area_for_snr(HPGE, cy, pr.CS, 30.0))])
    r, ln = _cs(act.compute_activities(sp, curve, act.ActivityOptions(nuclides=["Cs-137"])))
    assert ln.peak_found and ln.primary_method == "fit"
    assert (ln.primary, ln.primary_u_count) == (ln.activity, ln.u_count_bq)
    assert (r.primary, r.primary_u, r.primary_method) == (r.activity, r.u, "fit")


@pytest.mark.parametrize("mode", ["spectrum", "peak"])
def test_negative_net_m2(curve, mode):
    smp = _spectrum([TruePeak(pr.K40, 5000.0)], seed=2)
    bkg = _spectrum([TruePeak(pr.K40, 10000.0)], seed=3)
    res = act.compute_activities(smp, curve, act.ActivityOptions(nuclides=["K-40"], bkg_mode=mode,
                                                                  mda_method="iso11929"), background=bkg)
    r, ln = pr._line(res, "K-40", pr.K40)
    assert ln.primary_net < 0 and r.primary < 0
    assert r.activity is None and not r.detected
    assert r.best_estimate >= 0 and r.coverage_high > 0


def test_interfered_window_is_reported_not_used(curve):
    cy = continuum_counts(HPGE, scenarios.base_continuum(HPGE))
    e = pr.CS + float(HPGE.fwhm_kev(pr.CS))
    sp = _spectrum([TruePeak(e, area_for_snr(HPGE, cy, e, 40.0))])
    res = act.compute_activities(sp, curve, act.ActivityOptions(nuclides=["Cs-137"], mda_method="iso11929",
                                                                 decision="iso11929"))
    r, ln = _cs(res)
    assert ln.primary_method == "interfered" and ln.primary is not None
    assert not r.detected and r.best_estimate is None and "primary result not used" in ln.note


def test_iso_decision_detects_a_window_result(curve):
    cy = continuum_counts(HPGE, scenarios.base_continuum(HPGE))
    hits = {"search": 0, "iso11929": 0}
    for seed in range(20):
        sp = _spectrum([TruePeak(pr.CS, area_for_snr(HPGE, cy, pr.CS, 2.45))], seed=100 + seed)
        for rule in hits:
            r, ln = _cs(act.compute_activities(sp, curve, act.ActivityOptions(nuclides=["Cs-137"], decision=rule)))
            hits[rule] += r.detected
            if rule == "iso11929" and r.detected and not ln.peak_found:
                assert ln.activity == ln.primary and "decision rule ISO 11929" in ln.note
    assert hits["iso11929"] >= hits["search"] and hits["iso11929"] > 0
    with pytest.raises(ValueError):
        act.compute_activities(_spectrum(), curve, act.ActivityOptions(nuclides=["Cs-137"], decision="x"))


def test_session_round_trip_and_old_sessions(curve):
    from spectramaster.lab.session import quant_to_dict
    res = act.compute_activities(_spectrum(), curve, act.ActivityOptions(nuclides=["Cs-137"], decision="iso11929"))
    d = quant_to_dict(res)
    back = act.QuantResults.from_dict(d)
    assert back.options.decision == "iso11929"
    assert back.nuclides[0].primary == pytest.approx(res.nuclides[0].primary)
    assert back.nuclides[0].lines[0].primary_method == res.nuclides[0].lines[0].primary_method
    d["options"].pop("decision")
    for n in d["nuclides"]:
        for k in ("primary", "primary_u", "primary_method"):
            n.pop(k)
        for ln in n["lines"]:
            for k in ("primary", "primary_u_count", "primary_net", "primary_net_unc", "primary_method"):
                ln.pop(k)
    old = act.QuantResults.from_dict(d)
    assert old.options.decision == "search" and old.nuclides[0].primary is None


def test_table_column_only_for_not_detected(curve, qapp=None):
    pytest.importorskip("PySide6")
    from spectramaster.gui.quant_panel import RES_COLS, quant_table
    res = act.compute_activities(_spectrum(), curve, act.ActivityOptions(nuclides=["Cs-137"]))
    header, rows = quant_table(res, "en")
    j = RES_COLS.index("res_col_primary")
    assert "Primary" in header[j] and rows[0][j].count("±") == 1
    assert rows[0][3].startswith("<")             # the activity column still shows "< MDA"
    assert math.isfinite(res.nuclides[0].primary)

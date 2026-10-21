"""True-coincidence summing fixes (docs/baseline/tcs_fixes_protocol.md): daughter cascades, calibration
points the correction cannot treat, refit to convergence, curves without points.  R2 was withdrawn
(protocol results), so TF.C3 has no test."""
from __future__ import annotations

import json

import numpy as np
import pytest

from spectramaster.analysis import activity as act
from spectramaster.analysis import coincidence as co
from spectramaster.analysis import efficiency as eff
from spectramaster.analysis.library import lines_of
from spectramaster.validation import tcs_mc
from test_activity import LIVE, SAMPLE_REF, START, cal_curve, lib_line, make_spectrum  # noqa: F401


def ep(e):
    return tcs_mc.eps_peak(e, 0.02)


pt = tcs_mc.peak_to_total


# ------------------------------------------------------------------ TF.C1 Bi-207
def _hand_coi(energy):
    """Summing-out of `energy` from the raw table records of Bi-207 and Pb-207m, weighted by hand."""
    tab = json.loads(co.TABLE.read_text(encoding="utf-8"))["nuclides"]
    lib = json.loads(co.LIBRARY.read_text(encoding="utf-8"))["nuclides"]["Bi-207"]
    f = dict(zip(lib["includes"], lib["include_factors"]))
    num = wsum = 0.0
    for name, w in (("Bi-207", 1.0), ("Pb-207m", f["Pb-207m"])):
        for rec in tab[name]:
            g = np.array(rec["g"], dtype=float).reshape(-1, 2)
            k = int(np.argmin(np.abs(g[:, 0] - energy)))
            if abs(g[k, 0] - energy) > 1.0:
                continue
            p = {}
            for i, j, prob in rec["c"]:
                p[(int(i), int(j))] = float(prob)
            out = 0.0
            for j in range(len(g)):
                pj = p.get((k, j), 0.0) + (g[j, 1] * p.get((j, k), 0.0) / g[k, 1] if g[k, 1] > 0 else 0.0)
                out += pj * min(float(ep(g[j, 0])) / float(pt(g[j, 0])), 1.0)
            wk = w * float(rec["br"]) * g[k, 1]
            num += wk * out
            wsum += wk
    return 1.0 - num / wsum


def test_bi207_lines_are_corrected():
    lib = {round(l.energy, 1): l.intensity / 100 for l in lines_of("Bi-207") if l.kind == "g"}
    for e in (569.698, 1063.656):
        c = co.coi("Bi-207", e, ep, pt, e_min=59.5, intensity=lib[round(e, 1)])
        assert c.found and not c.reason and c.summing_in == 0.0
        assert c.factor == pytest.approx(_hand_coi(e), abs=1e-9)
    assert co.has_cascades("Bi-207")


# ------------------------------------------------------------------ TF.C4 calibration points
def _pt(nuc, e, eps):
    return eff.EfficiencyPoint(e, eps, 0.01 * eps, nuc, intensity=None, u_count_rel=0.005, u_ref_rel=0.008)


def _points(extra):
    base = [("Am-241", 59.54), ("Ce-139", 165.86), ("Hg-203", 279.2), ("Cs-137", 661.66), ("Mn-54", 834.85),
            ("Zn-65", 1115.54)]
    return [_pt(n, e, float(ep(e))) for n, e in base] + [_pt(n, e, float(ep(e))) for n, e in extra]


def test_bi207_calibration_point_is_corrected_and_untreatable_point_refused():
    pts = _points([("Bi-207", 569.698), ("Bi-207", 1063.656)])
    pts = [eff.EfficiencyPoint(**{**p.__dict__, "intensity": {569.698: 0.9775, 1063.656: 0.745}.get(p.energy,
                                                                                               p.intensity)})
           for p in pts]
    curve = eff.fit_efficiency(pts, "loglog", order=2)
    free = eff.summing_free_curve(curve, pt)
    assert free.summing_corrected and "Bi-207" in free.note and "()" not in free.note
    bad = eff.fit_efficiency(_points([("Ir-192", 484.575)]), "loglog", order=2)
    bad.points = [eff.EfficiencyPoint(**{**p.__dict__, "intensity": 0.0319 if p.nuclide == "Ir-192"
                                         else p.intensity}) for p in bad.points]
    with pytest.raises(ValueError, match="Ir-192 484.6"):
        eff.summing_free_curve(bad, pt)


def test_note_without_any_factor_has_no_empty_parentheses():
    pts = [_pt(n, e, 1e-7) for n, e in (("Am-241", 59.54), ("Cs-137", 661.66), ("Co-60", 1173.228),
                                        ("Co-60", 1332.492), ("Zn-65", 1115.54))]
    free = eff.summing_free_curve(eff.fit_efficiency(pts, "loglog", order=1), pt)
    assert "()" not in free.note and "no factor differs from 1" in free.note


# ------------------------------------------------------------------ TF.C5 / C6 convergence
E_REF, EPS_REF, PT_CONST = 1250.0, 0.11, 0.24


def _true(e, eps_ref=EPS_REF):
    return eps_ref * (np.asarray(e, dtype=float) / E_REF) ** -0.8


def _apparent_curve(eps_ref):
    ptc = lambda e: co.peak_to_total(e, PT_CONST, 0.0)                    # noqa: E731
    pts = []
    for n, e in (("Hg-203", 279.2), ("Sr-85", 514.0), ("Cs-137", 661.66), ("Mn-54", 834.85),
                 ("Zn-65", 1115.54), ("Co-60", 1173.228), ("Co-60", 1332.492)):
        t = float(_true(e, eps_ref))
        c = co.coi(n, e, lambda x: _true(x, eps_ref), ptc)
        a = t * (c.factor if c.found else 1.0)
        pts.append(eff.EfficiencyPoint(e, a, 0.005 * a, n, u_count_rel=0.004, u_ref_rel=0.003))
    return eff.fit_efficiency(pts, "loglog", order=1), ptc


def test_codex_h4_case_converges_to_the_true_efficiency():
    curve, ptc = _apparent_curve(EPS_REF)
    free = eff.summing_free_curve(curve, ptc)
    for e in (1173.228, 1332.492):
        assert float(free.efficiency(e)) == pytest.approx(float(_true(e)), rel=1e-4)
    # a Co-60 sample counted in the same geometry, with the same first-order summing loss
    peaks = []
    for e0 in (1173.228, 1332.492):
        e, i, hl = lib_line("Co-60", e0)
        d = eff.decay_factor(hl, (START - SAMPLE_REF).total_seconds())
        c = co.coi("Co-60", e, _true, ptc)
        peaks.append((e, 2e4 * d * eff.counting_decay_factor(hl, LIVE) * float(_true(e)) * i * LIVE * c.factor))
    q = act.compute_activities(make_spectrum(peaks), curve, act.ActivityOptions(
        nuclides=["Co-60"], ref_date=SAMPLE_REF, method="mean", tcs={"peak_to_total": [PT_CONST, 0.0]}))
    assert q.nuclides[0].activity == pytest.approx(2e4, rel=0.001)


def test_no_convergence_is_refused():
    curve, ptc = _apparent_curve(0.15)        # eps_t 0.63 at the fixed point: the iteration diverges
    with pytest.raises(ValueError, match="converge|validity"):
        eff.summing_free_curve(curve, ptc)


# ------------------------------------------------------------------ TF.C7 curve without points
def _lnpoly():
    e = np.geomspace(60.0, 2000.0, 30)
    x = e / 1000.0
    params = np.polyfit(x, np.log(_true(e) / 5), 4)[::-1]
    return eff.EfficiencyCurve(model="lnpoly", params=list(params), order=4, e_ref=1000.0, e_min=60.0,
                               e_max=2000.0, name="aptec")


def test_curve_without_points_is_refused_unless_declared_free():
    curve = _lnpoly()
    spec = make_spectrum([(1173.228, 1e4), (1332.492, 1e4)])
    tcs = {"peak_to_total": [PT_CONST, 0.0]}
    with pytest.raises(ValueError, match="no calibration points"):
        act.compute_activities(spec, curve, act.ActivityOptions(nuclides=["Co-60"], tcs=tcs))
    q = act.compute_activities(spec, curve, act.ActivityOptions(nuclides=["Co-60"],
                                                                tcs={**tcs, "curve_summing_free": True}))
    assert q.nuclides[0].activity is not None
    assert any("declared free of true-coincidence summing" in n for n in q.notes)


def test_cli_declaration_flag():
    import argparse
    from spectramaster.tools.quant_cli import _tcs
    a = argparse.Namespace(tcs_pt="0.24,0", tcs_pt_unc=10.0, tcs_curve_summing_free=True)
    assert _tcs(a)["curve_summing_free"] is True

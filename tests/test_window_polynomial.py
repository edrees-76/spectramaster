"""Quadratic continuum for curved window results (docs/baseline/window_polynomial_protocol.md)."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from spectramaster.analysis import activity as act
from spectramaster.analysis.activity import ActivityOptions, compute_activities
from spectramaster.validation import primary as pr
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE, NAI, continuum_counts, make_spectrum


@pytest.fixture(scope="module")
def curve():
    return pr._flat_curve()


def _spectrum(det, cont=None, seed=7):
    cont = cont or scenarios.base_continuum(det)
    return make_spectrum(det, pr._co60(det, continuum_counts(det, cont)), cont, seed).spectrum


def _cs_line(det, curve, cont=None, seed=7, **opt):
    res = compute_activities(_spectrum(det, cont, seed), curve, ActivityOptions(nuclides=["Cs-137"], **opt))
    return pr._line(res, "Cs-137", pr.CS)[1]


def test_quadratic_window_is_exact_on_a_quadratic_continuum():
    x = np.arange(400, dtype=float)
    y = 500.0 + 2.0 * (x - 200) - 0.01 * (x - 200) ** 2
    q = act.quadratic_window(y, 190, 210, 6)
    assert q.b == pytest.approx(y[190:211].sum(), rel=1e-9)
    assert q.c @ y[q.idx] == pytest.approx(q.b) and len(q.idx) == 2 * act.QUAD_SIDE_FACTOR * 6
    assert q.p_chi2 > 0.999
    assert act.quadratic_window(y, 5, 20, 6) is None          # the 2m sides leave the spectrum


def test_nai_curved_line_gets_a_quadratic_window_with_its_own_threshold(curve):
    ln = _cs_line(NAI, curve)
    assert ln.primary_method == "window" and ln.window_continuum == "quadratic"
    assert 1.05 < ln.window_lc_counts / _linear_lc(ln) < 1.35   # wider estimator, own threshold
    assert "quadratic continuum" in ln.note


def _linear_lc(ln):
    """L_C of the linear window, the line's limit before round7_quad_limits_protocol.md."""
    _b, n, m, _f = act.continuum_under(_spectrum(NAI), pr.CS, _fw(NAI))
    return act.K_DEFAULT * np.sqrt(ln.continuum * (1 + n / (2 * m)))


def test_line_reports_the_limits_of_the_quadratic_window(curve):
    """round7_quad_limits_protocol.md: the limits of the estimator used (were the linear ones)."""
    ln = _cs_line(NAI, curve)
    assert ln.lc_counts == ln.window_lc_counts and ln.decision_threshold == ln.window_decision_threshold
    assert ln.ld_counts == pytest.approx(act.currie_limits(ln.lc_counts / act.K_DEFAULT)[1], rel=1e-12)
    assert ln.mda == pytest.approx(ln.ld_counts * ln.decision_threshold / ln.lc_counts, rel=1e-12)


def _fw(det):
    from spectramaster.analysis.peaks import fwhm_model
    sp = _spectrum(det)
    return fwhm_model(sp, np.asarray(sp.counts, dtype=float))[0]


def test_hpge_window_stays_linear(curve):
    ln = _cs_line(HPGE, curve)
    assert ln.primary_method == "window" and ln.window_continuum == "linear" and ln.window_lc_counts is None


def test_compton_edge_window_is_never_used(curve):
    """Near the edge the search sees a peak (interfered) or the sides fail the smoothness check."""
    lines = [_cs_line(NAI, curve, cont=pr.edge_continuum(NAI), seed=s) for s in range(3)]
    assert all(ln.primary_method in ("curved", "interfered") for ln in lines)


def test_rough_sides_keep_the_line_curved(curve, monkeypatch):
    monkeypatch.setattr(act, "QUAD_CHI2_P", 1.1)            # every fit fails the check
    ln = _cs_line(NAI, curve)
    assert ln.primary_method == "curved" and "not smooth enough for a polynomial window" in ln.note


def test_d2_decides_with_the_quadratic_threshold(curve, monkeypatch):
    """A window result between the linear and the quadratic threshold is not detected."""
    ln = _cs_line(NAI, curve, decision="iso11929")
    fwin = act.line_window(_spectrum(NAI), pr.CS, _fw(NAI))[3]
    assert ln.detected == (ln.primary_net * fwin > ln.window_lc_counts)
    target = 0.5 * (_linear_lc(ln) + ln.window_lc_counts)           # window counts between the two
    shift = target - ln.primary_net * fwin
    real = act.quadratic_window
    monkeypatch.setattr(act, "quadratic_window",
                        lambda y, lo, hi, m: (lambda q: q and dataclasses.replace(q, b=q.b - shift))(real(y, lo, hi, m)))
    ln2 = _cs_line(NAI, curve, decision="iso11929")
    assert _linear_lc(ln2) < ln2.primary_net * fwin < ln2.window_lc_counts and not ln2.detected


def test_new_fields_survive_a_result_round_trip(curve):
    ln = _cs_line(NAI, curve)
    names = {f.name for f in dataclasses.fields(act.LineResult)}
    back = act.LineResult(**{k: v for k, v in dataclasses.asdict(ln).items() if k in names})
    assert back.window_continuum == "quadratic" and back.window_lc_counts == ln.window_lc_counts

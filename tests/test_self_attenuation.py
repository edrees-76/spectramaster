"""Self-attenuation correction for sample density, finding F5 (docs/baseline/self_attenuation_protocol.md)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from spectramaster.analysis import attenuation as A
from spectramaster.analysis.activity import ActivityOptions, QuantResults, compute_activities
from spectramaster.lab.session import quant_to_dict
from spectramaster.validation import primary as pr
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE, make_spectrum, continuum_counts

SA = A.SelfAttenuation("organic", 1.6, "organic", 1.15, 35.3)


@pytest.mark.parametrize("matrix", A.MATRICES)
def test_table_values_are_reproduced(matrix):
    for e_mev, mu in A.MU_RHO[matrix]:
        assert A.mass_attenuation(matrix, e_mev * 1000.0) == pytest.approx(mu, rel=1e-9)


def test_out_of_range_and_unknown_matrix():
    with pytest.raises(ValueError):
        A.mass_attenuation("water", 5.0)
    with pytest.raises(ValueError):
        A.SelfAttenuation("lead", 1.0, "water", 1.0, 10.0)


def test_factor_limits():
    assert A.SelfAttenuation("water", 1.2, "water", 1.2, 40.0).factor(122.0) == pytest.approx(1.0, abs=1e-15)
    assert A.SelfAttenuation("water", 1.6, "water", 1.0, 1e-6).factor(122.0) == pytest.approx(1.0, abs=1e-6)
    e = np.geomspace(30.0, 3000.0, 60)
    f = [SA.factor(x) for x in e]
    assert all(v > 1 for v in f) and all(a > b for a, b in zip(f, f[1:]))


def test_slab_transmission_closed_form():
    assert A.slab_transmission(0.2, 3.0) == pytest.approx((1 - math.exp(-0.6)) / 0.6, rel=1e-12)
    assert A.slab_transmission(0.0, 3.0) == 1.0


def _spectrum():
    cont = scenarios.base_continuum(HPGE)
    return make_spectrum(HPGE, pr._co60(HPGE, continuum_counts(HPGE, cont)), cont, 5).spectrum


def test_activity_line_scales_by_the_factor_and_round_trips():
    sp, curve = _spectrum(), pr._flat_curve()
    base = compute_activities(sp, curve, ActivityOptions(nuclides=["Co-60"]))
    res = compute_activities(sp, curve, ActivityOptions(nuclides=["Co-60"], self_attenuation=SA))
    for l0, l1 in zip(base.nuclides[0].lines, res.nuclides[0].lines):
        k = SA.factor(l0.energy)
        assert l1.self_attenuation == pytest.approx(k, rel=1e-12)
        assert l1.mda == pytest.approx(l0.mda * k, rel=1e-9)
        if l0.activity is not None:
            assert l1.activity == pytest.approx(l0.activity * k, rel=1e-9)
    back = QuantResults.from_dict(quant_to_dict(res))
    assert back.options.self_attenuation == SA


def test_model_uncertainty_adds_in_quadrature():
    sp, curve = _spectrum(), pr._flat_curve()
    sa = A.SelfAttenuation("organic", 1.6, "organic", 1.15, 35.3, rel_unc=0.05)
    r0 = compute_activities(sp, curve, ActivityOptions(nuclides=["Co-60"], self_attenuation=SA)).nuclides[0]
    r1 = compute_activities(sp, curve, ActivityOptions(nuclides=["Co-60"], self_attenuation=sa)).nuclides[0]
    assert r1.activity == pytest.approx(r0.activity, rel=1e-12)
    assert r1.u ** 2 == pytest.approx(r0.u ** 2 + (0.05 * r0.activity) ** 2, rel=1e-6)

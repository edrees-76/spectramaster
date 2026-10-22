"""True-coincidence summing: limits of validity found by the second external review."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from spectramaster.analysis import activity as act
from spectramaster.analysis import coincidence as co
from spectramaster.analysis import efficiency as eff
from test_activity import (LIVE, START, cal_certificate, cal_curve, lib_line, make_spectrum,  # noqa: F401
                           true_eff)
from test_tcs import A_CO60, PT, co60_spectrum, opts

TCS = {"peak_to_total": list(PT), "pt_rel_unc": 0.10}


def true_eps(e):
    return np.array([true_eff(x) for x in np.atleast_1d(np.asarray(e, dtype=float))])


def pt(e):
    return co.peak_to_total(e, *PT)


def test_partner_below_the_curve_is_ignored():
    # Mg-28 1342.2 keV: its 30.6 keV cascade partner (P 0.94) cannot reach the detector's calibrated
    # range (U-235 185.7 keV until the ENSDF table, ensdf_coincidence_protocol.md)
    def steep(e):                      # a close geometry: 2 % at 1 MeV, rising to 22 % at 59.5 keV
        return 0.02 * (np.clip(np.asarray(e, dtype=float), 59.5, 2000.0) / 1000.0) ** -0.85
    old = co.coi("Mg-28", 1342.2, steep, pt)
    new = co.coi("Mg-28", 1342.2, steep, pt, e_min=59.5)
    assert old.factor < 0.9
    assert new.factor > 0.97 and new.ignored > 0.5


def test_line_not_described_by_the_table_is_not_corrected():
    # In-114m 558.4 keV: 4.4 % in the library, 3.27 % in the ENSDF table (Ir-192 484.6 keV, missing
    # from the SandiaDecay table, until ensdf_coincidence_protocol.md)
    c = co.coi("In-114m", 558.43, true_eps, pt, intensity=0.044)
    assert not c.found and c.factor == 1.0 and "library" in c.reason
    ok = co.coi("Co-60", 1173.228, true_eps, pt, intensity=0.9985)
    assert ok.found and ok.factor == pytest.approx(co.coi("Co-60", 1173.228, true_eps, pt).factor)


def test_unphysical_coi_refuses_the_line(cal_curve):
    _pts, curve = cal_curve
    curve = dataclasses.replace(curve, summing_corrected=True)
    peaks = []
    for e0 in (604.721, 795.864):
        e, i, _hl = lib_line("Cs-134", e0)
        peaks.append((e, 2e4 * true_eff(e) * i * LIVE))
    q = act.compute_activities(make_spectrum(peaks), curve,
                               act.ActivityOptions(nuclides=["Cs-134"], tcs={"peak_to_total": [0.01, 0.0]}))
    r = q.nuclides[0]
    assert all(ln.coi <= 0 or not ln.coi_applied for ln in r.lines)
    assert all("validity" in ln.note for ln in r.lines)
    assert r.activity is None and "true-coincidence summing corrected" not in r.note


def apparent_points():
    """Calibration measured in the sample's geometry: cascade lines lose counts by summing."""
    cert = cal_certificate()
    peaks = []
    for c in cert:
        a0 = c.activity * eff.decay_factor(c.half_life_s, (START - c.ref_date).total_seconds())
        n = true_eff(c.energy) * c.intensity * a0 * eff.counting_decay_factor(c.half_life_s, LIVE) * LIVE
        f = co.coi(c.nuclide, c.energy, true_eps, pt, e_min=50.0)
        peaks.append((c.energy, n * (f.factor if f.found else 1.0)))
    return eff.measure_efficiency(make_spectrum(peaks), cert)


def test_calibration_with_cascade_emitters_is_not_corrected_twice():
    apparent = eff.fit_efficiency(apparent_points(), "loglog", order=3, name="apparent")
    assert not apparent.summing_corrected
    spec = co60_spectrum(summing=True)
    q = act.compute_activities(spec, apparent, opts(tcs=TCS))
    assert q.nuclides[0].activity == pytest.approx(A_CO60, rel=0.01)
    assert any("calibration points" in n and "Co-60" in n for n in q.notes)
    # the corrected curve is the summing-free one: corrected again it does not move
    free = eff.summing_free_curve(apparent, pt)
    assert free.summing_corrected and free.note
    for e in (122.06, 661.66, 1173.23, 1836.06):
        assert float(free.efficiency(e)) == pytest.approx(true_eff(e), rel=0.01)
    assert eff.summing_free_curve(free, pt) is free


def test_summing_free_curve_used_as_it_is(cal_curve):
    _pts, curve = cal_curve
    free = dataclasses.replace(curve, summing_corrected=True)
    q = act.compute_activities(co60_spectrum(summing=True), free, opts(tcs=TCS))
    assert q.nuclides[0].activity == pytest.approx(A_CO60, rel=0.01)
    assert not any("calibration points" in n for n in q.notes)
    d = free.to_dict()
    assert eff.EfficiencyCurve.from_dict(d).summing_corrected


def test_curve_that_cannot_be_refitted_is_refused(cal_curve):
    _pts, curve = cal_curve
    aptec = dataclasses.replace(curve, model="lnpoly")
    with pytest.raises(ValueError, match="summing"):
        act.compute_activities(co60_spectrum(summing=True), aptec, opts(tcs=TCS))

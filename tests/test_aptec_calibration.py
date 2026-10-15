"""Aptec-compatible calibration methods (spectramaster.analysis.aptec_calibration).

Synthetic tests always run.  The comparison with calibrations computed by Aptec itself uses the
sample spectra installed with Aptec PCMCA/WIN (``C:\\APTEC\\APTEC`` or ``SPECTRAMASTER_APTEC_DIR``)
and is skipped when they are not on the machine (they are not part of the repository).
"""
from __future__ import annotations

import math
import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from spectramaster.analysis import aptec_calibration as ac
from spectramaster.analysis import efficiency as eff

APTEC_DIR = Path(os.environ.get("SPECTRAMASTER_APTEC_DIR", r"C:\APTEC\APTEC"))
SAMPLES = sorted(APTEC_DIR.glob("*.s0")) if APTEC_DIR.is_dir() else []


# ---------------------------------------------------------------- energy / resolution
def test_polynomial_recovers_exact_curve_and_reduces_degree():
    ch = [100.0, 900.0, 2500.0, 4000.0, 7000.0]
    c = [12.5, 0.37, 2.1e-7]
    e = [c[0] + c[1] * x + c[2] * x * x for x in ch]
    cal = ac.fit_polynomial(ch, e, 2)
    assert cal.degree == 2
    assert np.allclose(cal.coeffs, c, rtol=1e-9, atol=1e-12)
    assert cal.average_deviation < 1e-9
    # two points with max degree 3 -> straight line (Aptec: highest degree the points allow)
    cal = ac.fit_polynomial(ch[:2], e[:2], 3)
    assert cal.degree == 1 and len(cal.coeffs) == 2


def test_single_energy_point_goes_through_origin():
    cal = ac.fit_polynomial([2000.0], [661.66], 2)
    assert cal.degree == 1
    assert cal.coeffs[0] == pytest.approx(0.0, abs=1e-9)
    assert cal.evaluate(2000.0) == pytest.approx(661.66)


def test_polynomial_rejects_bad_input():
    with pytest.raises(ValueError):
        ac.fit_polynomial([1.0, 1.0], [2.0, 3.0], 1)
    with pytest.raises(ValueError):
        ac.fit_polynomial([1.0, 2.0], [2.0, 3.0], 6)
    with pytest.raises(ValueError):
        ac.fit_polynomial([], [], 2)


def test_high_degree_is_well_conditioned_at_16k_channels():
    ch = np.linspace(50, 16000, 12)
    c = [3.0, 0.1, 1e-6, -2e-11, 1e-15, -1e-20]
    v = np.polynomial.polynomial.polyval(ch, c)
    cal = ac.fit_polynomial(ch, v, 5)
    assert np.allclose(cal.evaluate(ch), v, rtol=1e-9)


def test_fwhm_channel_keV_round_trip():
    energy = [10.0, 0.5, 1e-6]
    res = [1.5, 2e-4]
    kev = ac.fwhm_channels_to_kev(res, energy)
    ch = [500.0, 3000.0]
    back = ac.fwhm_kev_to_channels(kev, energy, ch)
    assert np.allclose(back, np.polynomial.polynomial.polyval(ch, res))


# ---------------------------------------------------------------- efficiency points
def test_point_formula_units_decay_and_error():
    t0 = datetime(2020, 1, 1)
    p = ac.EffPoint(energy=661.66, isotope="Cs-137", yield_=0.851, half_life_s=30.08 * 365.25 * 86400,
                    activity=1.0, activity_err=3.0, activity_units="uCi", activity_time=t0,
                    net_rate=50.0, net_rate_err=4.0, rate_time=t0 + timedelta(days=3650))
    p.calculate()
    dec = math.exp(-math.log(2) * 3650 * 86400 / p.half_life_s)
    assert p.efficiency == pytest.approx(50.0 / (37000.0 * 0.851 * dec))
    assert p.efficiency_err == pytest.approx(5.0)
    # emission-rate units: the yield is not applied
    q = ac.EffPoint(energy=661.66, yield_=0.851, activity=1000.0, activity_units="gamma/s", net_rate=10.0)
    assert q.calculate().efficiency == pytest.approx(0.01)
    with pytest.raises(ValueError):
        ac.EffPoint(energy=100, yield_=1, activity=1, activity_units="furlongs", net_rate=1).calculate()


def _points(fn, energies, err=2.0):
    return [ac.EffPoint(energy=e, isotope="X", efficiency=float(fn(e)), efficiency_err=err, manual=True)
            for e in energies]


@pytest.mark.parametrize("t", ["A", "B", "C", "D"])
def test_efficiency_types_recover_their_own_form(t):
    form, deg = ac.EFF_TYPES[t]
    rng = np.random.default_rng(3)
    a = rng.normal(0, 0.3, deg + 1) / (np.arange(deg + 1) + 1.0) ** 2
    a[0] = -4.0
    x_of = (lambda e: np.log(e / 1000.0)) if form == "lnln" else (lambda e: e / 1000.0)
    true = lambda e: np.exp(np.polynomial.polynomial.polyval(x_of(e), a))
    energies = np.geomspace(60, 2000, 12)
    cal = ac.fit_efficiency(_points(true, energies), t)
    assert np.allclose(cal.efficiency(energies), true(energies), rtol=1e-8)
    assert len(cal.coeffs) == 6 and len(cal.cov) == deg + 1


def test_efficiency_weights_and_covariance_are_aptec_convention():
    e = np.array([60, 120, 300, 660, 1170, 1330, 1800.0])
    y = 0.05 * (e / 100) ** -0.9 * (1 + 0.02 * np.sin(e))
    err = np.array([5, 3, 2, 2, 1, 1, 3.0])
    pts = [ac.EffPoint(energy=float(a), efficiency=float(b), efficiency_err=float(c), manual=True)
           for a, b, c in zip(e, y, err)]
    pts[2].efficiency_err = 0.0                       # no error -> weight of 100 %
    cal = ac.fit_efficiency(pts, "B")
    u = np.where(np.array([p.efficiency_err for p in pts]) > 0, [p.efficiency_err for p in pts], 100.0) / 100
    a = np.vander(np.log(e), 4, increasing=True) / u[:, None]
    par = np.linalg.solve(a.T @ a, a.T @ (np.log(y) / u))
    assert np.allclose(cal.coeffs[:4], par, rtol=1e-8)
    assert np.allclose(cal.cov, np.linalg.inv(a.T @ a), rtol=1e-6)


def test_efficiency_needs_enough_points():
    with pytest.raises(ValueError, match="at least 6"):
        ac.fit_efficiency(_points(lambda e: 0.01, [100, 200, 300, 400, 500]), "A")


def test_spline_passes_through_points_and_is_undefined_outside():
    energies = [59.5, 122.1, 344.3, 661.7, 1173.2, 1332.5]
    vals = [0.04, 0.09, 0.05, 0.03, 0.02, 0.018]
    pts = [ac.EffPoint(energy=a, efficiency=b, efficiency_err=2.0, manual=True) for a, b in zip(energies, vals)]
    cal = ac.fit_efficiency(pts, "S")
    assert np.allclose(cal.efficiency(np.array(energies)), vals, rtol=1e-12)
    assert cal.average_deviation_pct == pytest.approx(0.0, abs=1e-9)
    assert math.isnan(cal.efficiency(30.0)) and math.isnan(cal.efficiency(2000.0))
    assert 0.0 < cal.rel_uncertainty(500.0) < 0.05


@pytest.mark.parametrize("t", ["A", "D", "S"])
def test_conversion_to_quantification_curve(t, tmp_path):
    energies = np.geomspace(60, 1800, 9)
    true = lambda e: 0.06 * (e / 100) ** -0.8
    cal = ac.fit_efficiency(_points(true, energies), t, detector_id="HPGe-1", geometry_id="Mar-1L")
    curve = ac.to_efficiency_curve(cal, name="test")
    loaded = eff.load_curve(curve.save(tmp_path / "c.json"))
    probe = np.array([100.0, 500.0, 1500.0])
    assert np.allclose(loaded.efficiency(probe), cal.efficiency(probe), rtol=1e-10)
    assert np.allclose(loaded.rel_uncertainty(probe), cal.rel_uncertainty(probe), rtol=1e-8)
    assert loaded.detector == "HPGe-1" and loaded.geometry == "Mar-1L"
    assert "Aptec" in loaded.selection


def test_reports_mention_method_and_range():
    cal = ac.fit_polynomial([100, 1000, 3000], [30, 300, 900], 2)
    rep = ac.poly_report(cal)
    assert "Average deviation" in rep and "Valid range" in rep
    ecal = ac.fit_efficiency(_points(lambda e: 0.01 * (e / 100) ** -0.7, np.geomspace(60, 1800, 8)), "S")
    assert "not verified" in ac.eff_report(ecal)


# ---------------------------------------------------------------- against Aptec's own results
@pytest.mark.skipif(not SAMPLES, reason="Aptec sample spectra not installed")
def test_refit_reproduces_the_equations_aptec_stored():
    n_en = n_res = n_eff = 0
    for path in SAMPLES:
        r = ac.read_aptec_calibrations(path)
        st = r["stored"]
        for kind in ("energy", "resolution"):
            cal = r[kind]
            if cal is None:
                continue
            stored = st[kind + "_coeffs"][:cal.degree + 1]
            ch = np.array(cal.channels)
            # compare the curves at the points (coefficients of high powers are tiny)
            mine = cal.evaluate(ch)
            theirs = np.polynomial.polynomial.polyval(ch, stored)
            assert np.allclose(mine, theirs, rtol=2e-6, atol=1e-6), (path.name, kind)
            n_en += kind == "energy"
            n_res += kind == "resolution"
        cal = r["efficiency"]
        if cal is not None and st["eff_type"] in ac.VERIFIED_TYPES:
            deg = cal.degree
            assert np.allclose(cal.coeffs[:deg + 1], st["eff_coeffs"][:deg + 1], rtol=1e-4), path.name
            stored_cov = ac.upper_to_matrix(st["eff_cov_upper"], deg + 1)
            assert np.allclose(cal.cov, stored_cov, rtol=1e-3), path.name
            n_eff += 1
    assert n_en >= 5 and n_res >= 3 and n_eff >= 2


@pytest.mark.skipif(not SAMPLES, reason="Aptec sample spectra not installed")
def test_point_formula_reproduces_aptec_efficiencies():
    checked = 0
    for path in SAMPLES:
        cal = ac.read_aptec_calibrations(path)["efficiency"]
        if cal is None:
            continue
        for p in cal.points:
            if p.manual or p.net_rate <= 0 or p.activity <= 0:
                continue
            stored, stored_err = p.efficiency, p.efficiency_err
            q = ac.EffPoint(**{k: getattr(p, k) for k in ac.EffPoint.__dataclass_fields__})
            q.calculate()
            assert q.efficiency == pytest.approx(stored, rel=2e-3), (path.name, p.isotope, p.energy)
            assert q.efficiency_err == pytest.approx(stored_err, rel=2e-3, abs=0.01)
            checked += 1
    assert checked >= 10

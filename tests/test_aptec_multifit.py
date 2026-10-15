"""Aptec-style MultiFit (Gaussian decomposition of ROIs)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from spectramaster.analysis.aptec_multifit import MultifitSetup, auto_resolution, multifit_roi
from spectramaster.analysis.aptec_roi import RoiProperties, analyze_rois

FW = 6.0
S = FW / 2.3548200450309493


def _y(peaks, seed=1, bkg=50.0, n=4096):
    rng = np.random.default_rng(seed)
    x = np.arange(n)
    mu = np.full(n, bkg)
    for c, a in peaks:
        mu = mu + a / (S * math.sqrt(2 * math.pi)) * np.exp(-0.5 * ((x - c) / S) ** 2)
    return rng.poisson(mu).astype(float)


def _fit(y, rl, rh, setup=None, **kw):
    st = analyze_rois(y, [(rl, rh)], RoiProperties(), 1000.0)[0]
    ep = list(range(st.bl, rl)) + list(range(rh + 1, st.bh + 1))
    return multifit_roi(y, rl, rh, st.coeffs, lambda c: FW, setup, st.fwhm, ep, **kw)


def test_singlet_area_and_uncertainty():
    y = _y([(2000.0, 2000.0)])
    r = _fit(y, 1988, 2012)
    assert len(r.components) == 1 and not r.multiplet
    c = r.components[0]
    assert c.centroid == pytest.approx(2000.0, abs=0.3)
    assert c.area == pytest.approx(2000.0, rel=0.08)
    assert 40 < c.area_unc < 120 and 0.5 < r.reduced_chi2 < 2.0


def test_doublet_resolved():
    y = _y([(1994.0, 2000.0), (2006.0, 2000.0)], seed=3)          # 2 FWHM apart
    r = _fit(y, 1982, 2018)
    assert r.multiplet and len(r.components) == 2
    for c, true in zip(r.components, (1994.0, 2006.0)):
        assert c.centroid == pytest.approx(true, abs=0.6)
        assert c.area == pytest.approx(2000.0, rel=0.12)


def test_multiplets_only_skips_singlet_and_weak_peak_rejected():
    y = _y([(2000.0, 2000.0)])
    r = _fit(y, 1988, 2012, MultifitSetup(fit_singlets=False))
    assert not r.fitted and r.components == []
    flat = _y([], seed=7)
    r = _fit(flat, 1988, 2012)
    assert len(r.components) <= 1


def test_varying_width_and_background():
    y = _y([(2000.0, 4000.0)], seed=4)
    r = _fit(y, 1985, 2015, MultifitSetup(width_fixed=False, background_fixed=False))
    assert r.components[0].fwhm == pytest.approx(FW, rel=0.1)
    assert np.polynomial.polynomial.polyval(2000.0, r.background) == pytest.approx(50.0, rel=0.2)


def test_511_forces_varying_width():
    y = _y([(1022.0, 4000.0)], seed=4)
    r = _fit(y, 1007, 1037, energy_of=lambda i: 0.5 * i)          # 511 keV at index 1022
    assert r.width_scale != 1.0


def test_auto_resolution():
    assert auto_resolution([100.0, 1000.0], [4.0, 6.0]) == pytest.approx([34 / 9, 1 / 450], rel=1e-9)
    assert auto_resolution([500.0], [5.0]) == [5.0]
    assert auto_resolution([], []) is None


def test_setup_validation():
    with pytest.raises(ValueError):
        MultifitSetup(detector="x").validate()
    assert MultifitSetup.from_dict({"max_overlaps": 99}).max_overlaps == 8

"""Fit model of the engine (Release C, increment C3): Poisson likelihood for raw counts,
log-linear continuum for scintillators, and the measured-background estimator staying exact
with both."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from spectramaster.analysis import find_peaks
from spectramaster.analysis.background import BackgroundFitter
from spectramaster.analysis.peaks import F2S, SQRT2PI, FitReport, _fit_group, _Model, loglinear_continuum
from spectramaster.validation.synthetic import HPGE, NAI, Continuum, TruePeak, make_spectrum


def _mean_area(irls_iter, n=300, area=60.0, bkg=0.5, fw=6.0):
    import spectramaster.analysis.peaks as P
    old = P.POISSON_IRLS_ITER
    P.POISSON_IRLS_ITER = irls_iter
    try:
        rng = np.random.default_rng(7)
        x = np.arange(80, dtype=float)
        lam = bkg + area / (fw * F2S * SQRT2PI) * np.exp(-0.5 * ((x - 40) / (fw * F2S)) ** 2)
        m = _Model(np.full(80, fw))
        out = []
        for _ in range(n):
            y = rng.poisson(lam).astype(float)
            r = _fit_group(y, m, [40.0], 25, 55, free_width=False, step=False)
            out.append(r.areas[0])
        return float(np.mean(out))
    finally:
        P.POISSON_IRLS_ITER = old


def test_poisson_likelihood_reduces_low_count_area_bias():
    """60 counts on 0.5 counts/channel: Neyman weights (1/data) bias the area low (~ -12 %)."""
    neyman, poisson = _mean_area(0), _mean_area(3)
    assert neyman < 0.95 * 60.0
    assert abs(poisson - 60.0) < 0.03 * 60.0


def test_continuum_shape_by_detector():
    hp = make_spectrum(HPGE, [TruePeak(662.0, 1e4)], Continuum(300, 400, 10), 1).spectrum
    na = make_spectrum(NAI, [TruePeak(662.0, 1e4)], Continuum(300, 400, 10), 1).spectrum
    assert not loglinear_continuum(hp)
    assert loglinear_continuum(na)
    rep = FitReport()
    find_peaks(na, report=rep)
    assert rep.groups and rep.groups[0].continuum_columns is not None


@pytest.mark.parametrize("det", [HPGE, NAI], ids=["HPGe", "NaI"])
def test_identical_background_cancels_exactly_with_the_fit_continuum(det):
    s = make_spectrum(det, [TruePeak(662.0, 2e4), TruePeak(1460.8, 5e3)], Continuum(300, 400, 10), 3).spectrum
    rep = FitReport()
    pk = find_peaks(s, report=rep)
    under = BackgroundFitter(s, replace(s, sample_id="copy")).under_peaks(pk, rep)
    # exact for the linear continuum (HPGe); for the log-linear one (NaI) up to the convergence
    # tolerance of the non-linear fit
    tol = 1e-6 if det is HPGE else 1e-3
    for p in pk:
        assert under[id(p)][0] == pytest.approx(p.net_area, rel=tol, abs=1e-6)


def test_log_continuum_curvature_from_the_wide_region():
    """NaI peak on exp + flat (docs/baseline/medium_peaks_protocol.md), noise-free expectation:
    the pure exponential continuum misses the curvature; b2 measured on the wider region does not."""
    syn = make_spectrum(NAI, [TruePeak(1173.0, 3000.0)], Continuum(1800.0, 400.0, 60.0), 1)
    y = syn.expected
    t = syn.truth[0]
    m = _Model(np.array([float(NAI.fwhm_ch(NAI.energy(c))) for c in range(NAI.n_channels)]))
    m.loglinear = True
    lo, hi = int(t.centroid - 2.2 * t.fwhm_ch), int(t.centroid + 2.2 * t.fwhm_ch)
    flat = _fit_group(y, m, [t.centroid], lo, hi, curvature=0.0)
    wide = _fit_group(y, m, [t.centroid], lo, hi)
    assert abs(flat.areas[0] / t.area - 1) > 0.01
    assert abs(wide.areas[0] / t.area - 1) < 0.3 * abs(flat.areas[0] / t.area - 1)
    assert wide.b2 > 0                       # exp + flat is convex in log

"""Low-energy tail in the peak model (docs/baseline/peak_tail_protocol.md)."""
from __future__ import annotations

import math

import numpy as np
import pytest

import spectramaster.analysis.peaks as P
from spectramaster.validation import scenarios
from spectramaster.validation.benchmark import match
from spectramaster.validation.synthetic import HPGE, NAI, TruePeak, make_spectrum


@pytest.mark.parametrize("tau", [0.5, 1.0, 1.5, 3.0])
def test_tail_shape_normalised_and_derivative(tau):
    T = np.linspace(-80.0, 12.0, 400001)
    k = P._tail_k(T, tau)
    assert np.isfinite(k).all()
    assert k.sum() * (T[1] - T[0]) == pytest.approx(math.sqrt(2.0 * math.pi), rel=1e-6)
    t, h = np.linspace(-8.0, 6.0, 57), 1e-6
    num = (P._tail_k(t + h, tau) - P._tail_k(t - h, tau)) / (2.0 * h)
    assert num == pytest.approx((P._tail_k(t, tau) - np.exp(-0.5 * t * t)) / tau, abs=1e-8)


def test_peak_shape_area_independent_of_eta():
    T = np.linspace(-80.0, 12.0, 400001)
    g = P.peak_shape(T, None)
    assert np.array_equal(g, np.exp(-0.5 * T * T)) and np.array_equal(P.peak_shape(T, (0.0, 1.5)), g)
    for eta in (0.05, 0.3):
        assert P.peak_shape(T, (eta, 1.5)).sum() == pytest.approx(g.sum(), rel=1e-6)


def _strong(det, tail_frac, seed):
    es = scenarios._energies(det, "strong")
    peaks = [TruePeak(e, 1.0e5, tail_frac=tail_frac, tail_slope=1.5, step_frac=0.001 if tail_frac else 0.0)
             for e in es]
    return make_spectrum(det, peaks, scenarios.base_continuum(det), seed)


@pytest.mark.parametrize("det", [HPGE, NAI], ids=["HPGe", "NaI"])
def test_no_tail_invented(det):
    cal = P.shape_calibration([_strong(det, 0.0, seed).spectrum for seed in (950000, 950001, 950002)])
    assert cal["eta"] == 0.0 and cal["n_peaks"] >= P.TAIL_MIN_PEAKS and "not significant" in cal["note"]
    sp = _strong(det, 0.0, 950003).spectrum
    P.set_peak_tail(sp, cal)
    assert "peak_tail" not in sp.extra and P.peak_tail_of(sp) is None


def test_without_calibration_results_are_unchanged():
    """No shape calibration on the spectrum: the Gaussian engine, bit for bit."""
    syn = _strong(HPGE, 0.04, 950005)
    a = [(p.centroid, p.net_area, p.net_area_unc) for p in P.find_peaks(syn.spectrum)]
    P.set_peak_tail(syn.spectrum, None)
    b = [(p.centroid, p.net_area, p.net_area_unc) for p in P.find_peaks(syn.spectrum)]
    assert a == b


def test_hpge_shape_calibration_removes_area_bias():
    cal = P.shape_calibration([_strong(HPGE, 0.04, s).spectrum for s in (950010, 950011, 950012)])
    assert 0.0 < cal["eta"] <= P.TAIL_MAX_ETA and cal["tau"] in P.TAIL_TAUS
    bias = {True: [], False: []}
    for seed in (950013, 950014, 950015):
        syn = _strong(HPGE, 0.04, seed)
        for on in (False, True):
            P.set_peak_tail(syn.spectrum, cal if on else None)
            rep = P.FitReport()
            pk = P.find_peaks(syn.spectrum, report=rep)
            assert (rep.tail is not None) == on
            m, _ = match(syn, pk)
            bias[on] += [pk[j].net_area / syn.truth[i].area - 1.0 for i, j in m.items()]
    assert abs(np.mean(bias[True])) < 0.005 < abs(np.mean(bias[False]))


def test_calibration_travels_with_the_spectrum():
    """Background subtraction keeps the calibration; the manual refit and the fit report use it."""
    from spectramaster.analysis.manual import refit_region
    from spectramaster.tools.arithmetic import subtract_background
    cal = P.shape_calibration([_strong(HPGE, 0.04, s).spectrum for s in (950020, 950021)])
    syn = _strong(HPGE, 0.04, 950022)
    P.set_peak_tail(syn.spectrum, cal)
    tail = P.peak_tail_of(syn.spectrum)
    assert tail == (cal["eta"], cal["tau"])
    rep = P.FitReport()
    pk = P.find_peaks(syn.spectrum, report=rep)
    assert rep.tail == tail and all(c.tail == tail for g in rep.groups for c in g.components)
    net, _sigma = subtract_background(syn.spectrum, _strong(HPGE, 0.0, 950023).spectrum)
    assert P.peak_tail_of(net) == tail
    p0 = max(pk, key=lambda p: p.net_area)
    fw = p0.fwhm
    rf = refit_region(syn.spectrum, p0.centroid - 3 * fw, p0.centroid + 3 * fw, [p0.centroid])
    assert rf.peaks and rf.peaks[0].net_area == pytest.approx(p0.net_area, rel=0.01)

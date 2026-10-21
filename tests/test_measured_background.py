"""Measured-background subtraction (Release C, increment C1): explicit variance of net
spectra, the shared linear estimator for peak-by-peak subtraction, negative net areas kept,
double subtraction refused."""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from spectramaster.analysis import find_peaks
from spectramaster.analysis.activity import ActivityOptions, compute_activities
from spectramaster.analysis.background import BackgroundFitter, net_spectrum
from spectramaster.analysis.peaks import FitReport
from spectramaster.tools.arithmetic import SpectrumMathError, subtract_background
from spectramaster.validation.benchmark import _flat_curve
from spectramaster.validation.synthetic import HPGE, NAI, Continuum, TruePeak, make_spectrum

CONT = Continuum(exp_amp=300, exp_scale_kev=400, flat=10)


def _pair(det=HPGE, cs_sample=2e4, cs_bkg=2e3, k_time=2.0, seed=1):
    smp = make_spectrum(det, [TruePeak(661.657, cs_sample + cs_bkg), TruePeak(1460.82, 5e3)], CONT, seed)
    bcont = Continuum(CONT.exp_amp * k_time, CONT.exp_scale_kev, CONT.flat * k_time)
    bkg = make_spectrum(det, [TruePeak(661.657, cs_bkg * k_time), TruePeak(1460.82, 5e3 * k_time)], bcont,
                        seed + 1000, live_time=3600.0 * k_time)
    return smp.spectrum, bkg.spectrum


# ------------------------------------------------------------------ explicit variance
def test_find_peaks_with_variance_keeps_negative_channels_and_uses_it():
    s, b = _pair()
    net, var, k = net_spectrum(s, b)
    assert k == pytest.approx(0.5)
    assert min(net.counts) < 0                        # nothing clipped
    pk = find_peaks(net, variance=var)
    cs = min(pk, key=lambda p: abs(p.energy - 661.657))
    assert abs(cs.energy - 661.657) < 1.0
    # the uncertainty reflects S + k^2 B, not sqrt(net counts)
    roi = slice(cs.left, cs.right + 1)
    assert cs.net_area_unc >= 0.7 * math.sqrt(float(var[roi].sum())) - 1e-9
    assert cs.net_area_unc > math.sqrt(max(cs.net_area, 0))
    # K-40 is in both spectra at the same rate: no significant net peak
    assert not any(abs(p.energy - 1460.82) < 3 for p in pk)


def test_variance_must_match_the_channels():
    s, b = _pair()
    net, var, _k = net_spectrum(s, b)
    with pytest.raises(ValueError):
        find_peaks(net, variance=var[:-1])


# ------------------------------------------------------------------ double subtraction
def test_double_subtraction_is_refused():
    s, b = _pair()
    net, _sig = subtract_background(s, b)
    with pytest.raises(SpectrumMathError):
        subtract_background(net, b)
    subtract_background(net, b, allow_repeat=True)          # explicit override still possible
    with pytest.raises(ValueError):
        compute_activities(net, _flat_curve(), ActivityOptions(nuclides=["Cs-137"]), background=b)


def test_subtracted_spectrum_without_background_is_flagged():
    s, b = _pair()
    net, _sig = subtract_background(s, b)
    q = compute_activities(net, _flat_curve(), ActivityOptions(nuclides=["Cs-137"]))
    assert any("background subtracted" in n for n in q.notes)


# ------------------------------------------------------------------ peak-by-peak estimator
def test_identical_background_gives_exactly_zero_net():
    """N_s - k N_b = L (S - k B): with B = S and k = 1 every net area is exactly zero."""
    s, _b = _pair()
    rep = FitReport()
    pk = find_peaks(s, report=rep)
    under = BackgroundFitter(s, replace(s, sample_id="copy")).under_peaks(pk, rep)
    assert len(under) == len(pk)
    for p in pk:
        assert under[id(p)][0] == pytest.approx(p.net_area, rel=1e-6, abs=1e-6)


def test_background_line_stronger_than_in_the_sample():
    """Background line stronger than in the sample.  Peak mode fits the peaks on S - kB
    (docs/baseline/bkg_peak_protocol.md): no peak is found there, the line is not detected and the
    background under it is reported and enters its detection limit."""
    s = make_spectrum(HPGE, [TruePeak(1460.82, 3e3)], CONT, 5).spectrum
    b = make_spectrum(HPGE, [TruePeak(1460.82, 6e3)], CONT, 6).spectrum        # same live time
    q = compute_activities(s, _flat_curve(), ActivityOptions(nuclides=["K-40"]), background=b)
    ln = next(l for l in q.nuclides[0].lines if abs(l.energy - 1460.82) < 1)
    assert not ln.peak_found and not ln.detected
    assert ln.bkg_peak == pytest.approx(6e3, rel=0.1)
    q0 = compute_activities(s, _flat_curve(), ActivityOptions(nuclides=["K-40"]),
                            background=make_spectrum(HPGE, [], CONT, 6).spectrum)
    ln0 = next(l for l in q0.nuclides[0].lines if abs(l.energy - 1460.82) < 1)
    assert ln.mda > ln0.mda


def test_unresolved_background_line_does_not_bias_a_sample_peak():
    """NaI: Bi-214 1377 keV (background) 45 keV from Co-60 1332 keV (sample)."""
    from spectramaster.validation import scenarios
    rel = []
    for smp, bkg, truth in scenarios.background_pairs(NAI, 12):
        q = compute_activities(smp.spectrum, _flat_curve(), ActivityOptions(nuclides=["Co-60"], bkg_mode="peak"),
                               background=bkg.spectrum)
        ln = next(l for l in q.nuclides[0].lines if abs(l.energy - 1332.49) < 1)
        rel.append(ln.net_area / truth[("Co-60", 1332.492)] - 1.0)
    assert abs(np.mean(rel)) < 0.04                  # was +9 %


@pytest.mark.parametrize("mode", ["peak", "spectrum"])
@pytest.mark.parametrize("det", [HPGE, NAI], ids=["HPGe", "NaI"])
def test_net_area_recovers_the_sample_only_signal(det, mode):
    s, b = _pair(det=det, seed=21)
    q = compute_activities(s, _flat_curve(), ActivityOptions(nuclides=["Cs-137"], bkg_mode=mode),
                           background=b)
    ln = next(l for l in q.nuclides[0].lines if abs(l.energy - 661.657) < 1)
    assert ln.peak_found
    assert abs(ln.net_area - 2e4) < 4 * ln.net_unc


def test_background_with_different_layout_needs_calibration():
    s, b = _pair()
    b2 = replace(b, counts=list(b.counts[:2048]), energy_coeffs=[])
    with pytest.raises(ValueError):
        BackgroundFitter(s, b2)


def test_background_mismatches_are_reported():
    from datetime import datetime, timedelta
    from spectramaster.analysis.background import compatibility
    s, b = _pair()
    t0 = datetime(2026, 1, 1)
    s = replace(s, detector="HPGe-1", start_time=t0)
    b2 = replace(b, detector="HPGe-2", start_time=t0 - timedelta(days=400), live_time=1800.0)
    w = " | ".join(compatibility(s, b2))
    assert "different detector" in w and "shorter" in w and "400 days" in w
    assert compatibility(s, replace(b, detector="HPGe-1", start_time=t0)) == []

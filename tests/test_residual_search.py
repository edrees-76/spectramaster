"""Residual search in every fit region (docs/baseline/residual_search_protocol.md)."""
from __future__ import annotations

import pytest

import spectramaster.analysis.peaks as P
from spectramaster.validation import scenarios
from spectramaster.validation.benchmark import match
from spectramaster.validation.synthetic import HPGE, NAI, TruePeak, make_spectrum

E0 = 662.0
GAUSSIAN = {"eta": 0.0, "tau": 0.0, "n_peaks": P.TAIL_MIN_PEAKS}     # a measured Gaussian shape


def _satellite(det, sep_fwhm, ratio, seed, side=1.0, shape=GAUSSIAN):
    fw = float(det.fwhm_kev(E0))
    peaks = [TruePeak(E0, 1.0e5, tag="main"), TruePeak(E0 + side * sep_fwhm * fw, 1.0e5 / ratio, tag="sat")]
    syn = make_spectrum(det, peaks, scenarios.base_continuum(det), seed)
    P.set_peak_tail(syn.spectrum, shape)
    return syn


def _peaks(syn, search: bool):
    old = P.RESIDUAL_SEARCH
    P.RESIDUAL_SEARCH = search
    try:
        return P.find_peaks(syn.spectrum)
    finally:
        P.RESIDUAL_SEARCH = old


def test_gaussian_calibration_is_recorded():
    syn = _satellite(HPGE, 2.0, 30.0, 905000)
    assert P.shape_calibrated(syn.spectrum) and P.peak_tail_of(syn.spectrum) is None
    P.set_peak_tail(syn.spectrum, {"eta": 0.0, "tau": 0.0, "n_peaks": 1})    # too few peaks
    assert not P.shape_calibrated(syn.spectrum)
    P.set_peak_tail(syn.spectrum, GAUSSIAN)
    P.set_peak_tail(syn.spectrum, None)
    assert not P.shape_calibrated(syn.spectrum)


@pytest.mark.parametrize("sep, ratio, side", [(2.0, 30.0, 1.0), (2.0, 100.0, 1.0), (1.5, 100.0, -1.0)])
def test_hpge_satellite_found(sep, ratio, side):
    found_before = found_after = 0
    for seed in range(910000, 910006):
        syn = _satellite(HPGE, sep, ratio, seed, side)
        found_before += 1 in match(syn, _peaks(syn, False))[0]
        after = _peaks(syn, True)
        m, _ = match(syn, after)
        assert 0 in m                                     # the strong peak stays
        found_after += 1 in m
        main = syn.truth[0]
        window = [p for p in after if abs(p.centroid - main.centroid) < (sep + 2.0) * main.fwhm_ch]
        assert len(window) <= 2                           # no split beyond the true pair
    assert found_after == 6 and found_after > found_before


def test_no_search_without_shape_calibration():
    """Uncalibrated spectra are fitted exactly as before (the unmodelled tail would look like a
    satellite)."""
    for seed in (915000, 915001):
        syn = _satellite(HPGE, 2.0, 30.0, seed, shape=None)
        a = [(p.centroid, p.net_area) for p in _peaks(syn, False)]
        b = [(p.centroid, p.net_area) for p in _peaks(syn, True)]
        assert a == b


def test_tailed_peak_not_split_with_tail_calibration():
    """A strong HPGe peak with a pronounced low-energy tail (stronger than the benchmark's 4 %),
    fitted with the detector's tailed shape calibration: the tail is not a component."""
    def tailed(seed):
        es = scenarios._energies(HPGE, "strong")
        return make_spectrum(HPGE, [TruePeak(e, 2.0e5, tail_frac=0.10, tail_slope=1.0, step_frac=0.001)
                                    for e in es], scenarios.base_continuum(HPGE), seed)
    cal = P.shape_calibration([tailed(s).spectrum for s in (920100, 920101, 920102)])
    assert cal["eta"] > 0
    for seed in range(920000, 920004):
        syn = tailed(seed)
        P.set_peak_tail(syn.spectrum, cal)
        pk = _peaks(syn, True)
        for t in syn.truth:
            assert len([p for p in pk if abs(p.centroid - t.centroid) < 4.0 * t.fwhm_ch]) == 1


def test_nai_unchanged():
    """Low resolution: the search does not run, the peaks are those of the previous engine."""
    for seed in (930000, 930001):
        syn = _satellite(NAI, 1.5, 30.0, seed)
        a = [(p.centroid, p.net_area) for p in _peaks(syn, False)]
        b = [(p.centroid, p.net_area) for p in _peaks(syn, True)]
        assert a == b

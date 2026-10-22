"""FWHM calibration of calibrate_from_source from measured widths, not the search's width model
(docs/baseline/mix_peak_areas_protocol.md)."""
from __future__ import annotations

import math

import pytest

from spectramaster.analysis import peaks as pk
from spectramaster.tools import calibrate as cb
from spectramaster.tools.calibrate import NUCLIDE_LINES, calibrate_from_source
from test_tools import poisson_spec

GAIN = 0.34


def sigma_ch(ch):                       # a strongly energy-dependent resolution: x3 over the range
    return 0.9 + ch / 2000.0


def eu_spectrum(wide=(), extra=(), seed=5):
    """Eu-152 without any calibration; lines in `wide` (keV) 1.6x wider; `extra` = (keV, area, x width)."""
    peaks = []
    for e, i in NUCLIDE_LINES["Eu-152"]:
        ch = e / GAIN
        peaks.append((ch, 6000 * i, sigma_ch(ch) * (1.6 if any(abs(e - w) < 0.5 for w in wide) else 1.0)))
    for e, a, k in extra:
        peaks.append((e / GAIN, a, sigma_ch(e / GAIN) * k))
    return poisson_spec(n=8192, coeffs=[], peaks=peaks, seed=seed, bg=40)


def true_fwhm_kev(ch):
    return 2.0 * math.sqrt(2.0 * math.log(2.0)) * sigma_ch(ch) * GAIN


def test_measured_widths_follow_the_resolution():
    spec = eu_spectrum()
    sc = calibrate_from_source(spec, "Eu-152")
    ff = sc.fwhm_fit
    assert ff is not None and len(ff.values) >= 6
    for ch in ff.channels:
        assert ff.evaluate(ch) == pytest.approx(true_fwhm_kev(ch), rel=0.03)
    # the search's width model of an uncalibrated spectrum is not what is fitted
    lo, hi = min(ff.channels), max(ff.channels)
    assert ff.evaluate(hi) / ff.evaluate(lo) == pytest.approx(true_fwhm_kev(hi) / true_fwhm_kev(lo), rel=0.05)


def test_annihilation_line_and_an_outlier_are_left_out():
    spec = eu_spectrum(wide=(344.28,), extra=((511.0, 40000.0, 1.8),))
    sc = calibrate_from_source(spec, ["Eu-152", "Na-22"])
    labels = sc.fwhm_fit.labels
    assert not any("511" in label for label in labels)
    assert not any("344.28" in label for label in labels)
    for ch in sc.fwhm_fit.channels:
        assert sc.fwhm_fit.evaluate(ch) == pytest.approx(true_fwhm_kev(ch), rel=0.03)


def test_no_fwhm_calibration_from_fewer_than_two_widths(monkeypatch):
    spec = eu_spectrum()
    monkeypatch.setattr(pk, "line_widths", lambda s, cents: [None] * (len(cents) - 1) + [3.0])
    sc = calibrate_from_source(spec, "Eu-152")
    assert sc.fwhm_fit is None and len(sc.matches) >= 6


def test_line_widths_of_a_split_peak_and_bounds():
    spec = eu_spectrum()
    ch = 1408.01 / GAIN
    w = pk.line_widths(spec, [ch, ch + 1.0])            # a centroid off by a fraction of the width
    assert w[0] == pytest.approx(w[1], rel=1e-9)
    assert w[0] == pytest.approx(true_fwhm_kev(ch) / GAIN, rel=0.05)
    assert pk.line_widths(spec, [50.0])[0] is None       # nothing there: no measured width
    assert cb.FWHM_OUTLIER_REL == 0.10 and pk.LINE_WIDTH_BOUNDS == (1.0 / 3.0, 3.0)

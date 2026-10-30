"""Round-8 review, Gemini H2: in the peak background mode the limits of a line without a sample peak
use the window estimator of its primary result on the background
(docs/baseline/round8_peak_mode_protocol.md)."""
from __future__ import annotations

import math

import pytest

from spectramaster.analysis import activity as act
from spectramaster.validation import round8_peak_mode as r8


def _lines(name, mode="peak", mda_method="currie"):
    spec = {n: (kind, area, extra, blank) for n, kind, area, extra, blank in r8.CASES}[name]
    return spec, r8._case(*spec, mode, mda_method)["lines"]


@pytest.mark.parametrize("name", ["hpge_bkg1500", "hpge_nobkgpeak", "hpge_bkg1500_blank"])
@pytest.mark.parametrize("mda_method", ["currie", "iso11929"])
def test_linear_window_limits_use_the_window_background(name, mda_method):
    spec, lines = _lines(name, mda_method=mda_method)
    ln = lines[0]
    assert not ln["peak_found"] and ln["primary_method"] == "window" and ln["window_continuum"] == "linear"
    v, _cont = r8._window_sigma0_sq(*spec, ln)
    assert ln["lc_counts"] == pytest.approx(act.K_DEFAULT * math.sqrt(v), rel=1e-9)


def test_quadratic_window_limits_use_the_quadratic_background():
    spec, lines = _lines("nai_co60")
    quad = [ln for ln in lines if r8._no_peak_window(ln) and ln["window_continuum"] == "quadratic"]
    assert quad
    for ln in quad:
        v, _cont = r8._window_sigma0_sq(*spec, ln)
        assert ln["lc_counts"] == pytest.approx(act.K_DEFAULT * math.sqrt(v), rel=1e-9)


def test_primary_result_same_in_both_modes():
    _spec, peak = _lines("hpge_bkg1500")
    _spec, full = _lines("hpge_bkg1500", mode="spectrum")
    assert (peak[0]["primary"], peak[0]["primary_u_count"]) == (full[0]["primary"], full[0]["primary_u_count"])

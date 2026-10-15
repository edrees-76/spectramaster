"""Aptec Analyze spectrum operations (pure functions)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from spectramaster.model import Spectrum
from spectramaster.tools import spectrum_ops as ops


def _spec(n=64, **kw):
    counts = [10.0 + 500.0 * math.exp(-0.5 * ((i - 30) / 2.0) ** 2) for i in range(n)]
    base = dict(counts=counts, energy_coeffs=[1.0, 0.5], fwhm_coeffs=[2.0, 0.01], live_time=100.0,
                real_time=120.0, sample_id="S", extra={"fwhm_units": "keV"})
    base.update(kw)
    return Spectrum(**base)


def test_add_constant_and_status():
    s = _spec()
    r = ops.add_constant(s, -3)
    assert np.allclose(r.counts, np.asarray(s.counts) - 3)
    assert ops.status_of(r) == ["ConstantAdded -3"]
    assert not ops.is_poisson(r) and ops.is_poisson(s)
    assert s.counts[0] == pytest.approx(10.0 + 500.0 * math.exp(-0.5 * 225))   # input untouched
    with pytest.raises(ValueError):
        ops.add_constant(s, 1.5)


def test_normalize_scales_counts_and_times():
    s = _spec()
    r = ops.normalize(s, 0.25)
    assert np.allclose(r.counts, np.asarray(s.counts) * 0.25)
    assert r.live_time == pytest.approx(25.0) and r.real_time == pytest.approx(30.0)
    inv = ops.normalize(s, -1)                      # Aptec tip: -1 inverts about zero
    assert np.allclose(inv.counts, -np.asarray(s.counts)) and inv.live_time == 100.0
    with pytest.raises(ValueError):
        ops.normalize(s, 0)
    other = _spec(live_time=400.0)
    assert ops.live_time_ratio(s, other) == pytest.approx(4.0)
    assert ops.normalize(s, ops.live_time_ratio(s, other)).live_time == pytest.approx(other.live_time)


def test_shift_moves_data_not_calibration():
    s = _spec()
    r = ops.shift(s, 5)
    c = np.asarray(s.counts)
    assert np.allclose(r.counts[5:], c[:-5]) and np.all(np.asarray(r.counts[:5]) == 0)
    assert r.energy_coeffs == s.energy_coeffs
    assert float(r.extra["shift_counts_lost"]) == pytest.approx(c[-5:].sum())
    l = ops.shift(s, -5)
    assert np.allclose(l.counts[:-5], c[5:]) and ops.status_of(l) == ["LeftShifted 5"]


@pytest.mark.parametrize("points", ops.SMOOTH_POINTS)
def test_smooth_binomial(points):
    w = ops.smooth_weights(points)
    assert w.sum() == pytest.approx(1.0) and len(w) == points and np.allclose(w, w[::-1])
    flat = Spectrum(counts=[7.0] * 40)
    assert np.allclose(ops.smooth(flat, points).counts, 7.0)        # ends renormalised too
    s = _spec()
    r = ops.smooth(s, points)
    inner = slice(points, len(s.counts) - points)
    assert sum(r.counts[inner]) == pytest.approx(sum(s.counts[inner]), rel=2e-3)
    assert max(r.counts) < max(s.counts) and not ops.is_poisson(r)
    with pytest.raises(ValueError):
        ops.smooth_weights(4)


def test_smooth_5_point_weights():
    assert np.allclose(ops.smooth_weights(5), np.array([1, 4, 6, 4, 1]) / 16)


def test_reduce_channels_conserves_counts_and_calibration():
    s = _spec(extra={"energy_cal_points": "30:16; 50:26", "fwhm_units": "keV"})
    r = ops.reduce_channels(s, 4)
    assert r.num_channels == 16 and sum(r.counts) == pytest.approx(sum(s.counts))
    for j in range(16):            # new channel j covers old 4j .. 4j+3: same energy at its centre
        assert r.energy_of(j) == pytest.approx(s.energy_of(4 * j + 1.5))
    ch, e = r.extra["energy_cal_points"].split(";")[0].split(":")
    assert r.energy_of(float(ch)) == pytest.approx(float(e))
    assert ops.status_of(r) == ["Packed /4"] and ops.is_poisson(r)
    assert ops.reduce_roi(28, 33, 4) == (7, 8)
    with pytest.raises(ValueError):
        ops.reduce_channels(s, 3)


def test_reduce_channels_fwhm_in_channels():
    s = _spec(fwhm_coeffs=[4.0], extra={"fwhm_units": "channels"})
    assert ops.reduce_channels(s, 2).fwhm_coeffs == pytest.approx([2.0])


def test_derivative_zero_crossing_at_peak():
    s = _spec()
    d1 = ops.derivative(s, 1)
    y = np.asarray(d1.counts)
    assert y[28] > 0 and y[32] < 0 and abs(y[30]) < 1e-6
    d2 = ops.derivative(s, 2, pre_smooth=3)
    assert int(np.argmin(d2.counts)) == 30
    assert ops.status_of(d2) == ["Derivative 2 (smoothed 3)"] and not ops.is_poisson(d2)
    with pytest.raises(ValueError):
        ops.derivative(s, 4)


def test_combine_and_strip():
    a, b = _spec(), _spec(live_time=50.0, real_time=60.0)
    c = ops.combine(a, b)
    assert np.allclose(c.counts, 2 * np.asarray(a.counts))
    assert c.live_time == 150.0 and c.real_time == 180.0 and ops.is_poisson(c)
    st = ops.strip(a, b)
    assert np.allclose(st.counts, 0.0) and st.live_time == 100.0 and not ops.is_poisson(st)
    with pytest.raises(ops.SpectrumMathError):
        ops.strip(a, _spec(n=32))
    assert "combine_warning" in ops.combine(a, _spec(energy_coeffs=[0.0, 0.7])).extra

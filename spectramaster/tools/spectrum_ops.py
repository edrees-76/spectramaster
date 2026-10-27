"""Aptec *Analyze* spectrum operations: Add Constant, Normalize, Shift, Smooth, Reduce Channels,
Derivative and, with a compare spectrum, Combine and Strip.

What each operation does follows the Aptec PCMCA/WIN 6.31 help (``aptec.hlp``):

* Add Constant: a positive or negative integer is added to every channel.
* Normalize: every channel *and the counting times* are multiplied by the factor; with a compare
  spectrum the default factor is the live-time ratio compare / active ("Live Time Matching
  Multiplier").  A factor of -1 inverts the spectrum about zero.
* Shift: the data move left or right by an integer number of channels.
* Smooth: weighted average over 3, 5, 7 or 9 channels.
* Reduce Channels: binary reduction, adjacent channels are added (gross counts unchanged); the
  calibrations and ROI end points are divided to stay valid.
* Derivative: 1st, 2nd or 3rd derivative, a visual aid for peaks and multiplets.
* Combine: compare spectrum added channel by channel (live and true times added).
* Strip: compare spectrum subtracted channel by channel.

Not documented by Aptec, hence our own documented choices (not verified against Aptec output):

* Smooth weights are binomial, (1 2 1)/4, (1 4 6 4 1)/16, ...; at the spectrum ends the weights
  that fall outside are dropped and the rest renormalised.
* Derivatives are central differences, optionally of the data smoothed first (binomial weights).
* Shift leaves the calibrations unchanged (the data move under the channel axis) and fills the
  vacated channels with zero; counts shifted past the end are reported in ``extra``.
* Normalize multiplies the times by ``abs(factor)`` (a time cannot be negative).

Every result is a new :class:`~spectramaster.model.Spectrum` (inputs untouched).  The operations
done are listed in ``extra["aptec_status"]`` with Aptec's wAnalyzeStatus names, and any operation
after which channel contents are no longer Poisson counts sets ``extra["counts_are_poisson"] = "no"``:
uncertainties computed as sqrt(counts) are then not valid.
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Optional

import numpy as np

from ..model import Spectrum
from .arithmetic import SpectrumMathError, rebin, same_calibration

__all__ = ["SpectrumMathError", "STATUS", "SMOOTH_POINTS", "DERIVATIVE_ORDERS", "status_of", "is_poisson",
           "add_constant", "normalize", "live_time_ratio", "shift", "smooth_weights", "smooth", "reduce_channels",
           "derivative", "combine", "strip", "reduce_roi"]

# Aptec .S0 header wAnalyzeStatus flags (help file, fileheader_struct)
STATUS = {"Derivative": 0x0003, "ConstantAdded": 0x0004, "Normalized": 0x0008, "LeftShifted": 0x0010,
          "RightShifted": 0x0020, "Combined": 0x0040, "Stripped": 0x0080, "Smoothed": 0x0100,
          "Packed": 0x0200}
SMOOTH_POINTS = (3, 5, 7, 9)
DERIVATIVE_ORDERS = (1, 2, 3)


def status_of(spec: Spectrum) -> list[str]:
    """Operations done on `spec` (oldest first), e.g. ["Normalized x0.5", "Smoothed 5"]."""
    text = str(spec.extra.get("aptec_status", ""))
    return [t.strip() for t in text.split(";") if t.strip()]


def is_poisson(spec: Spectrum) -> bool:
    return str(spec.extra.get("counts_are_poisson", "yes")) != "no"


def _result(spec: Spectrum, counts, entry: str, poisson: bool, variance=None, **changes) -> Spectrum:
    """The changed spectrum; `variance` is its per-channel variance when the operation propagates
    it (otherwise it is unknown: docs/baseline/round4_calibration_protocol.md)."""
    from ..analysis.background import set_channel_variance
    extra = dict(spec.extra)
    extra["aptec_status"] = "; ".join(status_of(spec) + [entry])
    if not poisson:
        extra["counts_are_poisson"] = "no"
    extra.update(changes.pop("extra_items", {}))
    out = replace(spec, counts=[float(x) for x in counts], extra=extra, source_path="", source_format="",
                  **changes)
    set_channel_variance(out, variance)
    return out


def _variance(spec: Spectrum):
    from ..analysis.background import known_variance
    return known_variance(spec)


def _sum_variance(a: Spectrum, b: Spectrum):
    va, vb = _variance(a), _variance(b)
    return None if va is None or vb is None else va + vb


def _counts(spec: Spectrum) -> np.ndarray:
    return np.asarray(spec.counts, dtype=float)


def _num(x: float) -> str:
    return f"{x:.10g}"


# ------------------------------------------------------------------------------- one spectrum
def add_constant(spec: Spectrum, constant: int) -> Spectrum:
    """Add the integer `constant` (may be negative) to every channel."""
    if constant != int(constant):
        raise ValueError("the constant must be an integer")
    k = int(constant)
    return _result(spec, _counts(spec) + k, f"ConstantAdded {k:+d}", poisson=(k == 0) and is_poisson(spec))


def live_time_ratio(active: Spectrum, compare: Spectrum) -> Optional[float]:
    """Aptec's Live Time Matching Multiplier: compare live time / active live time."""
    if not active.live_time or not compare.live_time or active.live_time <= 0 or compare.live_time <= 0:
        return None
    return compare.live_time / active.live_time


def normalize(spec: Spectrum, factor: float) -> Spectrum:
    """Multiply every channel and the live / true times by `factor` (times by its absolute value)."""
    f = float(factor)
    if f == 0.0 or not math.isfinite(f):
        raise ValueError("the normalizing factor must be a non-zero number")
    a = abs(f)
    lt = spec.live_time * a if spec.live_time else spec.live_time
    rt = spec.real_time * a if spec.real_time else spec.real_time
    extra = {}
    for key in ("equipment_live_time",):
        if spec.extra.get(key) not in (None, ""):
            try:
                extra[key] = float(spec.extra[key]) * a
            except (TypeError, ValueError):
                pass
    v = _variance(spec)
    return _result(spec, _counts(spec) * f, f"Normalized x{_num(f)}", poisson=(f == 1.0) and is_poisson(spec),
                   variance=None if v is None else v * (f * f), live_time=lt, real_time=rt, extra_items=extra)


def shift(spec: Spectrum, channels: int) -> Spectrum:
    """Move the data by `channels` (positive = right, to higher channels; negative = left)."""
    n = int(channels)
    if n != channels:
        raise ValueError("the shift must be a whole number of channels")
    c = _counts(spec)
    out = np.zeros_like(c)
    v = _variance(spec)
    var = None if v is None else np.zeros_like(c)
    m = len(c)
    if abs(n) < m:
        if n >= 0:
            out[n:] = c[:m - n]
            if var is not None:
                var[n:] = v[:m - n]
            lost = c[m - n:].sum() if n else 0.0
        else:
            out[:m + n] = c[-n:]
            if var is not None:
                var[:m + n] = v[-n:]
            lost = c[:-n].sum()
    else:
        lost = c.sum()
    name = "RightShifted" if n >= 0 else "LeftShifted"
    return _result(spec, out, f"{name} {abs(n)}", poisson=is_poisson(spec), variance=var,
                   extra_items={"shift_counts_lost": _num(float(lost))})


def smooth_weights(points: int) -> np.ndarray:
    """Binomial weights over `points` channels (sum 1)."""
    if points not in SMOOTH_POINTS:
        raise ValueError(f"smoothing must use one of {SMOOTH_POINTS} points")
    w = np.array([math.comb(points - 1, k) for k in range(points)], dtype=float)
    return w / w.sum()


def _smooth_array(c: np.ndarray, points: int) -> np.ndarray:
    w = smooth_weights(points)
    num = np.convolve(c, w, mode="same")
    norm = np.convolve(np.ones_like(c), w, mode="same")     # < 1 near the ends: renormalise
    return num / norm


def smooth(spec: Spectrum, points: int) -> Spectrum:
    """Weighted (binomial) average of each channel with its neighbours over `points` channels."""
    return _result(spec, _smooth_array(_counts(spec), points), f"Smoothed {points}", poisson=False)


def derivative(spec: Spectrum, order: int, pre_smooth: int = 0) -> Spectrum:
    """`order`-th derivative (1, 2 or 3, central differences, counts per channel^order) of the
    data, first smoothed over `pre_smooth` points (0 = not smoothed)."""
    if order not in DERIVATIVE_ORDERS:
        raise ValueError("derivative order must be 1, 2 or 3")
    c = _counts(spec)
    if pre_smooth:
        c = _smooth_array(c, pre_smooth)
    for _ in range(order):
        c = np.gradient(c) if len(c) > 1 else np.zeros_like(c)
    tag = f"Derivative {order}" + (f" (smoothed {pre_smooth})" if pre_smooth else "")
    return _result(spec, c, tag, poisson=False, extra_items={"derivative_order": order})


def _points_text(text: str, a: float, f: int) -> str:
    """Re-number "ch:value; ch:value" calibration points for a reduction: J = (ch - a) / f."""
    out = []
    for item in str(text).split(";"):
        if ":" not in item:
            continue
        ch, val = item.split(":", 1)
        try:
            out.append(f"{_num((float(ch) - a) / f)}:{val.strip()}")
        except ValueError:
            continue
    return "; ".join(out)


def reduce_channels(spec: Spectrum, factor: int) -> Spectrum:
    """Add `factor` (2, 4, 8, ...) adjacent channels together; gross counts are unchanged and the
    energy and resolution calibrations are rewritten for the new channel numbering (the
    resolution calibration also in new-channel units when it is in channels)."""
    f = int(factor)
    if f < 2 or f & (f - 1):
        raise ValueError("the reduction must be a power of two (2, 4, 8, ...)")
    if f >= spec.num_channels:
        raise ValueError("the reduction leaves less than one channel")
    out = rebin(spec, f)
    a = spec.first_channel - f * out.first_channel + (f - 1) / 2.0
    extra = {}
    for key in ("energy_cal_points", "fwhm_cal_points"):
        if spec.extra.get(key):
            extra[key] = _points_text(spec.extra[key], a, f)
    fw = list(out.fwhm_coeffs)
    if fw and str(spec.extra.get("fwhm_units", "")).lower().startswith("chan"):
        fw = [c / f for c in fw]            # a FWHM in old channels is FWHM/f new channels
    return _result(out, out.counts, f"Packed /{f}", poisson=is_poisson(spec), fwhm_coeffs=fw,
                   extra_items=extra)


def reduce_roi(left: int, right: int, factor: int, first_channel: int = 0) -> tuple[int, int]:
    """ROI end points (array indices) after :func:`reduce_channels` with the same `factor`."""
    f = int(factor)
    new_fc = first_channel // f if first_channel % f == 0 else 0
    lo = (first_channel + left) // f - new_fc
    hi = (first_channel + right) // f - new_fc
    return max(lo, 0), max(hi, lo)


# ------------------------------------------------------------------------------- two spectra
def _check_pair(active: Spectrum, compare: Spectrum) -> None:
    if active.num_channels != compare.num_channels:
        raise SpectrumMathError(f"the spectra have different numbers of channels "
                                f"({active.num_channels} and {compare.num_channels})")


def _name(spec: Spectrum) -> str:
    return spec.source_path or spec.sample_id or spec.description or "?"


def combine(active: Spectrum, compare: Spectrum) -> Spectrum:
    """Add the compare spectrum channel by channel; live and true times are added."""
    _check_pair(active, compare)
    lt = active.live_time + compare.live_time if active.live_time is not None and compare.live_time is not None \
        else None
    rt = active.real_time + compare.real_time if active.real_time is not None and compare.real_time is not None \
        else None
    extra = {"combined_with": _name(compare)}
    if not same_calibration(active, compare):
        extra["combine_warning"] = "the energy calibrations differ: channels were added as they are"
    return _result(active, _counts(active) + _counts(compare), "Combined",
                   poisson=is_poisson(active) and is_poisson(compare), variance=_sum_variance(active, compare),
                   live_time=lt, real_time=rt, extra_items=extra)


def strip(active: Spectrum, compare: Spectrum) -> Spectrum:
    """Subtract the compare spectrum channel by channel (times and metadata of `active` kept).

    As Aptec, the counts are subtracted as they are: normalize the compare spectrum first
    (live time ratio) when the live times differ; the result then records a warning."""
    _check_pair(active, compare)
    extra = {"stripped_with": _name(compare)}
    la, lb = active.live_time, compare.live_time
    if la and lb and abs(la - lb) > 1e-9 * la:
        extra["strip_live_time_warning"] = (f"the live times differ ({la:g} s and {lb:g} s): "
                                            "counts were subtracted without live-time scaling")
    if not same_calibration(active, compare):
        extra["strip_warning"] = "the energy calibrations differ: channels were subtracted as they are"
    return _result(active, _counts(active) - _counts(compare), "Stripped", poisson=False,
                   variance=_sum_variance(active, compare), extra_items=extra)

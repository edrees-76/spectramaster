"""Spectrum arithmetic: sum, background subtraction, scaling, rebinning, truncation.

All functions are pure: they never modify their inputs and return new
:class:`~spectramaster.model.Spectrum` objects (metadata copied from the first /
sample spectrum, provenance recorded in ``extra``).

Energy alignment method (used by :func:`sum_spectra` and
:func:`subtract_background` when the calibrations differ)
------------------------------------------------------------------------------
Every source channel ``c`` is treated as a bin covering ``[c-0.5, c+0.5]`` in
channel space (channel-centre convention of the model), i.e. the energy interval
``[E(c-0.5), E(c+0.5)]``.  Its counts are assumed uniformly distributed over that
interval and are shared between the target channels in proportion to the energy
overlap (linear-overlap / "histogram" rebinning).  This conserves the counts
exactly for every part of the source spectrum that lies inside the target energy
range; counts falling outside it are reported in ``extra['counts_outside_range']``.
The result counts are in general non-integer.
"""
from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime
from typing import Optional, Sequence

import numpy as np
from numpy.polynomial import polynomial as P

from ..model import Spectrum

__all__ = [
    "SpectrumMathError", "same_calibration", "channel_edges_energy", "rebin_to_energy",
    "align_to", "sum_spectra", "subtract_background", "scale_spectrum", "rebin",
    "truncate", "truncate_energy",
]


class SpectrumMathError(ValueError):
    """Incompatible spectra for the requested operation."""


# ----------------------------------------------------------------- helpers
def _clean(coeffs: Sequence[float]) -> list[float]:
    c = [float(x) for x in coeffs]
    while c and c[-1] == 0.0:
        c.pop()
    return c


def _channels(spec: Spectrum) -> np.ndarray:
    return np.arange(spec.first_channel, spec.first_channel + spec.num_channels, dtype=float)


def same_calibration(a: Spectrum, b: Spectrum, tol_kev: float = 0.01) -> bool:
    """True if both spectra have the same channel layout and their energy
    calibrations agree within `tol_kev` at every channel (both uncalibrated
    also counts as "same")."""
    if a.num_channels != b.num_channels or a.first_channel != b.first_channel:
        return False
    ca, cb = _clean(a.energy_coeffs), _clean(b.energy_coeffs)
    if not ca and not cb:
        return True
    if not ca or not cb:
        return False
    ch = _channels(a)
    return float(np.max(np.abs(P.polyval(ch, ca) - P.polyval(ch, cb)))) <= tol_kev


def channel_edges_energy(spec: Spectrum) -> np.ndarray:
    """Energy (keV) of the num_channels+1 channel boundaries (ch-0.5 ... ch+0.5)."""
    if not spec.energy_coeffs:
        raise SpectrumMathError("spectrum is not energy calibrated")
    edges = np.arange(spec.first_channel, spec.first_channel + spec.num_channels + 1, dtype=float) - 0.5
    e = P.polyval(edges, spec.energy_coeffs)
    if np.any(np.diff(e) <= 0):
        raise SpectrumMathError("energy calibration is not monotonic over the spectrum")
    return e


def rebin_to_energy(counts: Sequence[float], src_edges: np.ndarray, dst_edges: np.ndarray
                    ) -> tuple[np.ndarray, float]:
    """Linear-overlap rebinning of a histogram from `src_edges` to `dst_edges`
    (both increasing, len = nbins+1).  Returns (new_counts, counts_outside)."""
    c = np.asarray(counts, dtype=float)
    src_edges = np.asarray(src_edges, dtype=float)
    dst_edges = np.asarray(dst_edges, dtype=float)
    # cumulative counts as a piecewise-linear function of energy -> exact overlap
    cum = np.concatenate([[0.0], np.cumsum(c)])
    at = np.interp(dst_edges, src_edges, cum, left=0.0, right=cum[-1])
    out = np.diff(at)
    outside = float(cum[-1] - (at[-1] - at[0]))
    return out, outside


def align_to(spec: Spectrum, reference: Spectrum) -> Spectrum:
    """Re-express `spec` on the channel/energy grid of `reference` (counts conserved
    inside the common energy range, see module docstring)."""
    if same_calibration(spec, reference):
        return replace(spec, counts=list(spec.counts), extra=dict(spec.extra))
    new, outside = rebin_to_energy(spec.counts, channel_edges_energy(spec), channel_edges_energy(reference))
    extra = dict(spec.extra)
    extra["aligned_to"] = reference.source_path or reference.sample_id or "reference"
    extra["counts_outside_range"] = round(outside, 6)
    return replace(spec, counts=[float(x) for x in new], energy_coeffs=list(reference.energy_coeffs),
                   first_channel=reference.first_channel, fwhm_coeffs=list(reference.fwhm_coeffs),
                   extra=extra)


def _add_opt(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a + b


# ---------------------------------------------------------------- operations
def sum_spectra(spectra: Sequence[Spectrum], align: str = "auto",
                reference: Optional[Spectrum] = None) -> Spectrum:
    """Sum spectra channel by channel.

    align = "channel": require identical channel layout and calibration
            (error otherwise); "energy": rebin every spectrum onto the energy grid of
            `reference` (default: the first spectrum) before adding; "auto": channel
            sum when the calibrations agree, energy alignment otherwise.

    Live and real times are added; start time is the earliest; metadata comes
    from the first spectrum.  Total counts are conserved exactly in channel mode
    and inside the reference energy range in energy mode.
    """
    if not spectra:
        raise SpectrumMathError("nothing to sum")
    if align not in ("auto", "channel", "energy"):
        raise ValueError(f"align must be auto, channel or energy, not {align!r}")
    ref = reference or spectra[0]
    parts: list[Spectrum] = []
    aligned = False
    for s in spectra:
        if same_calibration(s, ref):
            parts.append(s)
        elif align == "channel":
            raise SpectrumMathError(
                f"{s.source_path or s.sample_id or 'spectrum'}: different channel count or calibration "
                "(use align='energy')")
        else:
            parts.append(align_to(s, ref))
            aligned = True
    total = np.zeros(ref.num_channels)
    for s in parts:
        total += np.asarray(s.counts, dtype=float)
    live = real = 0.0
    for s in spectra:
        live = _add_opt(live, s.live_time)
        real = _add_opt(real, s.real_time)
    starts = [s.start_time for s in spectra if s.start_time]
    extra = dict(ref.extra)
    extra["operation"] = f"sum of {len(spectra)} spectra" + (" (energy aligned)" if aligned else "")
    extra["sum_sources"] = "; ".join(s.source_path or s.sample_id or "?" for s in spectra)
    outside = sum(float(p.extra.get("counts_outside_range", 0.0)) for p in parts if p is not ref)
    if aligned:
        extra["counts_outside_range"] = round(outside, 6)
    return replace(ref, counts=[float(x) for x in total], live_time=live, real_time=real,
                   start_time=min(starts) if starts else None, extra=extra,
                   source_path="", source_format="")


def subtract_background(sample: Spectrum, background: Spectrum, scale: Optional[float] = None,
                        align: str = "auto", clip_negative: bool = False, allow_repeat: bool = False
                        ) -> tuple[Spectrum, list[float]]:
    """Net = sample - k * background, with k = LT_sample / LT_background unless
    `scale` is given.  Returns (net_spectrum, sigma) where sigma[i] is the
    propagated 1-sigma Poisson uncertainty sqrt(S_i + k^2 B_i) of each net channel.

    The net spectrum keeps the sample's times and metadata; k and the background
    source are recorded in ``extra``.  Negative net channels are kept unless
    `clip_negative` (uncertainties are unaffected by clipping).  A sample that is itself
    a background-subtracted spectrum is refused unless `allow_repeat` (double subtraction).
    """
    if sample.extra.get("operation") == "background subtracted" and not allow_repeat:
        raise SpectrumMathError("the sample is already background subtracted "
                                f"(background: {sample.extra.get('background_source', '?')})")
    if scale is None:
        if not sample.live_time or not background.live_time:
            raise SpectrumMathError("live time missing: give an explicit scale factor")
        scale = sample.live_time / background.live_time
    if same_calibration(sample, background):
        bkg = background
    elif align == "channel":
        raise SpectrumMathError("sample and background have different channel layout or calibration")
    else:
        bkg = align_to(background, sample)
    s = np.asarray(sample.counts, dtype=float)
    b = np.asarray(bkg.counts, dtype=float)
    net = s - scale * b
    sigma = np.sqrt(np.clip(s, 0, None) + scale * scale * np.clip(b, 0, None))
    if clip_negative:
        net = np.clip(net, 0, None)
    extra = dict(sample.extra)
    extra["operation"] = "background subtracted"
    extra["background_source"] = background.source_path or background.sample_id or "?"
    extra["background_scale"] = float(scale)
    out = replace(sample, counts=[float(x) for x in net], extra=extra, source_path="", source_format="")
    from ..analysis.background import set_channel_variance
    set_channel_variance(out, sigma * sigma)          # S + k^2 B, for the manual fit
    return out, [float(x) for x in sigma]


def scale_spectrum(spec: Spectrum, factor: float, scale_times: bool = False) -> Spectrum:
    """Multiply all counts by `factor` (times are scaled too if `scale_times`)."""
    extra = dict(spec.extra)
    extra["scale_factor"] = float(factor)
    return replace(spec, counts=[float(c) * factor for c in spec.counts], extra=extra,
                   live_time=spec.live_time * factor if scale_times and spec.live_time else spec.live_time,
                   real_time=spec.real_time * factor if scale_times and spec.real_time else spec.real_time,
                   source_path="", source_format="")


def _compose(coeffs: Sequence[float], a: float, b: float) -> list[float]:
    """Coefficients of p(a + b*x) given those of p(x) (same number of terms)."""
    n = len(coeffs)
    if n == 0:
        return []
    res = np.zeros(n)
    power = np.zeros(n)
    power[0] = 1.0
    for c in coeffs:
        res += c * power
        nxt = np.zeros(n)               # power * (a + b x), truncated to n terms
        nxt += a * power
        nxt[1:] += b * power[:-1]
        power = nxt
    return [float(x) for x in res]


def rebin(spec: Spectrum, factor: int) -> Spectrum:
    """Compress channels by an integer `factor` (2, 4, ...): new channel j is the
    sum of old channels factor*j .. factor*j+factor-1.  A trailing partial group is
    kept (so total counts are always conserved exactly).  The energy and FWHM
    calibrations are rewritten for the new channel numbering:
    E_new(J) = E_old(factor*J + offset + (factor-1)/2)."""
    factor = int(factor)
    if factor < 1:
        raise ValueError("rebin factor must be >= 1")
    if factor == 1:
        return replace(spec, counts=list(spec.counts), extra=dict(spec.extra))
    c = np.asarray(spec.counts, dtype=float)
    n_new = math.ceil(len(c) / factor)
    padded = np.zeros(n_new * factor)
    padded[: len(c)] = c
    new = padded.reshape(n_new, factor).sum(axis=1)
    fc = spec.first_channel
    new_fc = fc // factor if fc % factor == 0 else 0
    # old channel centre of new channel J
    a = fc - factor * new_fc + (factor - 1) / 2.0
    extra = dict(spec.extra)
    extra["rebin_factor"] = factor
    if len(c) % factor:
        extra["rebin_last_channel_partial"] = len(c) % factor
    return replace(spec, counts=[float(x) for x in new], first_channel=new_fc,
                   energy_coeffs=_compose(_clean(spec.energy_coeffs), a, factor),
                   fwhm_coeffs=_compose(_clean(spec.fwhm_coeffs), a, factor),
                   extra=extra, source_path="", source_format="")


def truncate(spec: Spectrum, start: int, stop: Optional[int] = None, renumber: bool = False) -> Spectrum:
    """Keep channel numbers start <= ch < stop.  With renumber=False the kept
    channels keep their numbers (first_channel = start, calibration unchanged);
    with renumber=True they become 0..n-1 and the calibrations are shifted."""
    lo_idx = max(0, int(start) - spec.first_channel)
    hi_idx = spec.num_channels if stop is None else min(spec.num_channels, int(stop) - spec.first_channel)
    if hi_idx <= lo_idx:
        raise SpectrumMathError("empty channel range")
    new_fc = spec.first_channel + lo_idx
    extra = dict(spec.extra)
    extra["truncated_channels"] = f"{new_fc}-{spec.first_channel + hi_idx - 1}"
    out = replace(spec, counts=list(spec.counts[lo_idx:hi_idx]), first_channel=new_fc, extra=extra,
                  source_path="", source_format="")
    if renumber and new_fc:
        out = replace(out, first_channel=0,
                      energy_coeffs=_compose(_clean(spec.energy_coeffs), new_fc, 1.0),
                      fwhm_coeffs=_compose(_clean(spec.fwhm_coeffs), new_fc, 1.0))
    return out


def truncate_energy(spec: Spectrum, e_low: float, e_high: float, renumber: bool = False) -> Spectrum:
    """Keep the channels whose centre energy lies in [e_low, e_high] keV."""
    e = spec.energies()
    if e is None:
        raise SpectrumMathError("spectrum is not energy calibrated")
    idx = [i for i, x in enumerate(e) if e_low <= x <= e_high]
    if not idx:
        raise SpectrumMathError("no channel in the energy range")
    return truncate(spec, spec.first_channel + idx[0], spec.first_channel + idx[-1] + 1, renumber)

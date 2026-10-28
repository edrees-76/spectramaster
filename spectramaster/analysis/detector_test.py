"""HPGe detector acceptance test from a Co-60 spectrum (FWHM, FWTM, peak-to-Compton ratio, relative
efficiency; IEEE Std 325, the Canberra Germanium Detectors manual chapter 7, IAEA MRNI-507) and the
chi-square test of repeated counts (IAEA-TECDOC-1599).  docs/baseline/detector_acceptance_protocol.md.

The relative efficiency is that of the standard geometry: a Co-60 point source at 25 cm on the
detector axis, compared with 1.2e-3, the 1332.5 keV full-energy efficiency of a 3 x 3 inch NaI
detector in that geometry.  No true-coincidence summing correction is applied, as in the standard.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Sequence

import numpy as np

CO60_1332 = 1332.492
CO57_122 = 122.0606
COMPTON_KEV = (1040.0, 1096.0)
NAI_REF_EFFICIENCY = 1.2e-3          # 3 x 3 inch NaI, Co-60 1332.5 keV, point source at 25 cm
ROI_FWHM = 3.0                       # ROI half-width in FWHM
MIN_WIDTH_CH = 3.0                   # narrower peaks are sampled too coarsely for the widths
CHI2_LOW, CHI2_HIGH = 0.05, 0.95     # TECDOC-1599 acceptance points
CHI2_N = (10, 20)                    # numbers of counts of TECDOC-1599
GEOMETRY_NOTE = ("relative efficiency for a Co-60 point source at 25 cm on the detector axis "
                 "(vs 1.2e-3 of a 3 x 3 inch NaI); no coincidence-summing correction")


@dataclass
class PeakWidth:
    energy: float                    # keV, nominal
    centroid_kev: Optional[float] = None
    fwhm_kev: Optional[float] = None
    fwtm_kev: Optional[float] = None
    roi: Optional[tuple[int, int]] = None          # count indices
    linear_crossings: int = 0                      # crossings by linear interpolation (fallback)
    note: str = ""

    @property
    def ratio(self) -> Optional[float]:
        return self.fwtm_kev / self.fwhm_kev if self.fwhm_kev and self.fwtm_kev else None


@dataclass
class RelativeEfficiency:
    net_area: float
    net_unc: float
    activity_bq: float               # at the start of the measurement
    efficiency: float                # absolute, 1332.5 keV
    percent: float
    u_counting: float                # percent points
    u_total: float                   # percent points (counting and activity)
    decay_factor: float
    note: str = ""


@dataclass
class AcceptanceResult:
    width_1332: PeakWidth
    width_122: Optional[PeakWidth] = None
    peak_to_compton: Optional[float] = None
    relative_efficiency: Optional[RelativeEfficiency] = None
    notes: list[str] = field(default_factory=list)


@dataclass
class ChiSquareResult:
    n: int
    mean: float
    chi2: float
    dof: int
    low: float
    high: float
    passed: bool
    note: str = ""


def _channel(spectrum, energy: float) -> Optional[float]:
    from .activity import _channel_of_energy
    return _channel_of_energy(spectrum, energy)


def _kev_per_channel(spectrum, ch: float) -> float:
    return abs(float(spectrum.energy_of(ch + 0.5)) - float(spectrum.energy_of(ch - 0.5)))


def _roi(spectrum, energy: float) -> Optional[tuple[int, int, float]]:
    """(lo, hi, fwhm in channels) of the ROI +-ROI_FWHM FWHM around `energy`, or None."""
    from .peaks import checked_fwhm_model
    c = _channel(spectrum, energy)
    if c is None:
        return None
    y = np.asarray(spectrum.counts, dtype=float)
    fw, _src = checked_fwhm_model(spectrum, np.maximum(y, 0.0))
    w = float(fw[int(min(max(round(c), 0), len(fw) - 1))])
    half = max(int(math.ceil(ROI_FWHM * w)), 3)
    lo, hi = int(round(c)) - half, int(round(c)) + half
    if lo < 1 or hi >= len(y) - 1:
        return None
    return lo, hi, w


def _log_parabola(net: np.ndarray, below: int, above: int, inner: int, level: float) -> Optional[float]:
    """Crossing of `level` between channels `below` and `above` by the parabola through the logarithms
    of the net counts at below, above and inner (exact for a Gaussian); None when not usable."""
    xs = np.array([below, above, inner], dtype=float)
    ys = net[[below, above, inner]]
    if np.any(ys <= 0):
        return None
    a, b, c = np.polyfit(xs, np.log(ys), 2)
    roots = np.roots([a, b, c - math.log(level)]) if a != 0 else np.array([-(c - math.log(level)) / b])
    lo, hi = min(below, above), max(below, above)
    ok = [float(r.real) for r in np.atleast_1d(roots) if abs(r.imag) < 1e-12 and lo <= r.real <= hi]
    return ok[0] if ok else None


def _width(net: np.ndarray, rl: int, rh: int, imax: int, level: float) -> tuple[Optional[float], int]:
    """(width in channels, crossings by linear interpolation) at `level` of the net counts
    (detector_acceptance_amendment_protocol.md); None when a side does not fall below the level."""
    i = imax
    while i > rl and net[i - 1] >= level:
        i -= 1
    j = imax
    while j < rh and net[j + 1] >= level:
        j += 1
    if i <= rl or j >= rh:
        return None, 0
    lin = 0
    lo = _log_parabola(net, i - 1, i, i + 1, level) if i + 1 <= rh else None
    if lo is None:
        lo, lin = i - 1 + (level - net[i - 1]) / (net[i] - net[i - 1]), lin + 1
    hi = _log_parabola(net, j + 1, j, j - 1, level) if j - 1 >= rl else None
    if hi is None:
        hi, lin = j + (net[j] - level) / (net[j] - net[j + 1]), lin + 1
    return float(hi - lo), lin


def peak_width(spectrum, energy: float = CO60_1332) -> PeakWidth:
    """FWHM and FWTM (keV) of the peak at `energy`: the net counts of the Aptec ROI analysis (linear
    background between the end points), half and tenth maximum crossings by log-parabolic
    interpolation (detector_acceptance_amendment_protocol.md)."""
    from .aptec_roi import analyze_rois
    out = PeakWidth(energy)
    r = _roi(spectrum, energy)
    if r is None:
        out.note = f"{energy:.1f} keV outside the spectrum or its energy calibration"
        return out
    lo, hi, _w = r
    a = analyze_rois(spectrum.counts, [(lo, hi)])[0]
    out.roi = (lo, hi)
    if a.centroid is None or a.fwhm is None:
        out.note = f"no peak at {energy:.1f} keV"
        return out
    y = np.asarray(spectrum.counts, dtype=float)
    net = np.zeros_like(y)
    net[lo:hi + 1] = y[lo:hi + 1] - a.background_at(np.arange(lo, hi + 1))
    imax = lo + int(np.argmax(net[lo:hi + 1]))
    fh, n_h = _width(net, lo, hi, imax, net[imax] / 2.0)
    ft, n_t = _width(net, lo, hi, imax, net[imax] / 10.0)
    if fh is None:
        out.note = f"no peak at {energy:.1f} keV"
        return out
    out.linear_crossings = n_h + n_t
    c_abs = int(spectrum.first_channel or 0) + a.centroid     # energy_of takes the absolute channel
    k = _kev_per_channel(spectrum, c_abs)
    out.centroid_kev = float(spectrum.energy_of(c_abs))
    out.fwhm_kev = fh * k
    out.fwtm_kev = ft * k if ft is not None else None
    if fh < MIN_WIDTH_CH:
        out.note = (f"FWHM {fh:.1f} channels: too few channels for an accurate width "
                    f"(at least {MIN_WIDTH_CH:g} needed)")
    return out


def peak_to_compton(spectrum, roi: Optional[tuple[int, int]] = None) -> Optional[float]:
    """Highest gross count among the channels of the 1332.5 keV ROI divided by the mean gross
    counts of the channels whose energy lies in 1040-1096 keV (IEEE Std 325); None when the
    spectrum does not reach both ends of that window."""
    from .aptec_roi import check_finite
    y = np.asarray(spectrum.counts, dtype=float)
    check_finite(y)                               # round6_inputs_protocol.md
    if roi is None:
        r = _roi(spectrum, CO60_1332)
        if r is None:
            return None
        roi = r[:2]
    e = np.asarray(spectrum.energies(), dtype=float)
    if e.min() > COMPTON_KEV[0] or e.max() < COMPTON_KEV[1]:
        return None
    sel = (e >= COMPTON_KEV[0]) & (e <= COMPTON_KEV[1])
    if not sel.any():
        return None
    mean = float(y[sel].mean())
    return float(y[roi[0]:roi[1] + 1].max()) / mean if mean > 0 else None


def net_area(spectrum, energy: float = CO60_1332) -> Optional[tuple[float, float]]:
    """(net counts, standard uncertainty) of the ROI at `energy`: gross minus a straight
    continuum through the means of FWHM-wide side regions; variance G + (n / 2m)^2 (S_L + S_R)."""
    from .aptec_roi import check_finite
    y = np.asarray(spectrum.counts, dtype=float)
    check_finite(y)                               # round6_inputs_protocol.md
    r = _roi(spectrum, energy)
    if r is None:
        return None
    lo, hi, w = r
    m = max(3, int(math.ceil(w)))
    if lo - m < 0 or hi + m >= len(y):
        return None
    n = hi - lo + 1
    g = float(y[lo:hi + 1].sum())
    s_l, s_r = float(y[lo - m:lo].sum()), float(y[hi + 1:hi + 1 + m].sum())
    f = n / (2.0 * m)
    return g - f * (s_l + s_r), math.sqrt(max(g, 0.0) + f * f * max(s_l + s_r, 0.0))


def _co60():
    from .library import load_library
    nd = load_library().get("Co-60")
    line = min((l for l in nd.lines if l.kind == "g"), key=lambda l: abs(l.energy - CO60_1332))
    return nd.half_life_s, line.intensity / 100.0


def relative_efficiency(spectrum, activity_bq: float, activity_u_bq: float = 0.0,
                        reference_date: Optional[datetime] = None) -> RelativeEfficiency:
    """Relative efficiency (%) at 1332.5 keV of a Co-60 point source at 25 cm on the axis."""
    if not activity_bq or not math.isfinite(activity_bq) or activity_bq <= 0:
        raise ValueError("the source activity must be a positive number")
    if not math.isfinite(activity_u_bq or 0.0) or (activity_u_bq or 0.0) < 0:
        raise ValueError("the activity uncertainty must be a non-negative number")
    t = float(spectrum.live_time or 0.0)
    if not math.isfinite(t) or t <= 0:
        raise ValueError("the spectrum has no valid live time")
    na = net_area(spectrum)
    if na is None:
        raise ValueError("the 1332.5 keV peak is outside the spectrum or its energy calibration")
    hl, inten = _co60()
    note, k = "", 1.0
    if reference_date is not None:
        if spectrum.start_time is None:
            note = "measurement start unknown: activity not decay-corrected"
        else:
            dt = (spectrum.start_time - reference_date).total_seconds()
            k = math.exp(-math.log(2.0) * dt / hl)
    a = activity_bq * k
    n, un = na
    eps = n / (t * a * inten)
    pct = 100.0 * eps / NAI_REF_EFFICIENCY
    u_c = abs(pct) * un / abs(n) if n else float("inf")
    u_a = abs(pct) * (activity_u_bq / activity_bq if activity_u_bq else 0.0)
    return RelativeEfficiency(n, un, a, eps, pct, u_c, math.hypot(u_c, u_a), k, note)


def acceptance_test(spectrum, activity_bq: Optional[float] = None, activity_u_bq: float = 0.0,
                    reference_date: Optional[datetime] = None, co57_spectrum=None) -> AcceptanceResult:
    """FWHM / FWTM at 1332.5 keV (and 122.1 keV with a Co-57 spectrum), peak-to-Compton ratio and,
    with the source activity, the relative efficiency."""
    if not spectrum.energy_coeffs:
        raise ValueError("the spectrum has no energy calibration")
    w = peak_width(spectrum, CO60_1332)
    res = AcceptanceResult(w)
    if w.note:
        res.notes.append(w.note)
    if w.fwhm_kev is not None:
        res.peak_to_compton = peak_to_compton(spectrum, w.roi)
        if res.peak_to_compton is None:
            res.notes.append("the 1040-1096 keV Compton window is not fully inside the spectrum: "
                             "no peak-to-Compton ratio")
    if co57_spectrum is not None:
        res.width_122 = peak_width(co57_spectrum, CO57_122)
        if res.width_122.note:
            res.notes.append(res.width_122.note)
    if activity_bq:
        res.relative_efficiency = relative_efficiency(spectrum, activity_bq, activity_u_bq, reference_date)
        if res.relative_efficiency.note:
            res.notes.append(res.relative_efficiency.note)
        res.notes.append(GEOMETRY_NOTE)
    return res


def chi_square_test(counts: Sequence[float]) -> ChiSquareResult:
    """Chi-square test of n repeated counts of one source (IAEA-TECDOC-1599): accepted when
    sum (x - mean)^2 / mean lies between the 5 % and 95 % points with n - 1 degrees of freedom."""
    from scipy.stats import chi2
    x = np.asarray([float(v) for v in counts], dtype=float)
    if len(x) < 3:
        raise ValueError("at least 3 counts are needed")
    if not np.all(np.isfinite(x)):
        raise ValueError("the counts must be numbers")
    mean = float(x.mean())
    if mean <= 0:
        raise ValueError("the mean count must be positive")
    dof = len(x) - 1
    c2 = float(((x - mean) ** 2).sum() / mean)
    low, high = float(chi2.ppf(CHI2_LOW, dof)), float(chi2.ppf(CHI2_HIGH, dof))
    notes = []
    if len(x) not in CHI2_N:
        notes.append(f"{len(x)} counts; TECDOC-1599 uses 10 or 20")
    if np.any(x <= 0):
        notes.append("a count is zero or negative")
    return ChiSquareResult(len(x), mean, c2, dof, low, high, bool(low <= c2 <= high), "; ".join(notes))


__all__ = ["PeakWidth", "RelativeEfficiency", "AcceptanceResult", "ChiSquareResult", "peak_width",
           "peak_to_compton", "net_area", "relative_efficiency", "acceptance_test", "chi_square_test",
           "NAI_REF_EFFICIENCY"]

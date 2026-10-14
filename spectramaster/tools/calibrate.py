"""Energy / FWHM re-calibration.

* :func:`fit_energy_calibration` -- polynomial (order 1-3) through (channel, keV)
  pairs with a residual report.
* :func:`fit_fwhm_calibration` -- polynomial FWHM(ch) in keV through
  (channel, FWHM keV) pairs.
* :func:`find_peaks` -- a deliberately simple, self-contained peak search
  (smoothed local maximum above a running-minimum baseline, background-subtracted
  centroid, half-maximum FWHM).  Independent of :mod:`spectramaster.analysis`.
* :func:`calibrate_from_source` -- find the peaks of a known calibration source
  (``"Eu-152"``, ``"Co-60,Cs-137"`` ...) and propose a calibration.
* :func:`apply_calibration` / :func:`apply_calibration_batch` -- write the new
  calibration into a copy of the spectrum / of many files.
* :func:`fit_points` / :func:`validate_calibration` -- weighted fit of reviewed points with
  F-test order selection and outlier exclusion, and the validation report attached to every
  :class:`SourceCalibration` (``.validation``; ``ok`` is False for a likely wrong source).
* :func:`check_drift` -- compare a stored calibration with known lines in the spectrum and
  propose (never apply) a correction.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

import numpy as np
from numpy.polynomial import polynomial as P

from ..model import Spectrum

__all__ = [
    "NUCLIDE_LINES", "CalibrationFit", "Peak", "PeakMatch", "SourceCalibration",
    "parse_pairs", "fit_energy_calibration", "fit_fwhm_calibration", "find_peaks",
    "source_lines", "calibrate_from_source", "apply_calibration", "apply_calibration_batch",
    "BACKGROUND_LINES", "CalibrationPoint", "CalibrationValidation", "DriftCheck", "check_drift",
    "fit_points", "validate_calibration", "f_test_pvalue",
]

# Gamma lines (keV, emission probability %) of common calibration sources and
# natural-background nuclides (DDEP / NNDC recommended values, rounded).
NUCLIDE_LINES: dict[str, list[tuple[float, float]]] = {
    "Am-241": [(59.541, 35.9)],
    "Cd-109": [(88.034, 3.64)],
    "Co-57": [(122.061, 85.6), (136.474, 10.7)],
    "Ce-139": [(165.857, 79.9)],
    "Hg-203": [(279.195, 81.5)],
    "Sn-113": [(391.698, 64.97)],
    "Sr-85": [(514.005, 96.0)],
    "Cs-137": [(661.657, 85.1)],
    "Mn-54": [(834.848, 99.98)],
    "Y-88": [(898.042, 93.7), (1836.063, 99.2)],
    "Zn-65": [(1115.539, 50.04)],
    "Co-60": [(1173.228, 99.85), (1332.492, 99.98)],
    "Na-22": [(511.0, 180.7), (1274.537, 99.94)],
    "K-40": [(1460.822, 10.66)],
    "Ba-133": [(80.998, 33.3), (276.399, 7.16), (302.851, 18.34), (356.013, 62.05), (383.848, 8.94)],
    "Cs-134": [(563.246, 8.34), (569.331, 15.37), (604.721, 97.62), (795.864, 85.46), (801.953, 8.69),
               (1365.185, 3.02)],
    "Eu-152": [(121.782, 28.53), (244.697, 7.55), (344.279, 26.59), (411.116, 2.24), (443.965, 2.83),
               (778.904, 12.93), (867.380, 4.23), (964.079, 14.51), (1085.837, 10.11),
               (1112.076, 13.67), (1408.013, 20.87)],
    "Ra-226": [(186.211, 3.56), (295.224, 18.42), (351.932, 35.60), (609.312, 45.49),
               (1120.287, 14.91), (1764.494, 15.31)],
    "Th-232": [(238.632, 43.6), (338.320, 11.27), (583.187, 30.6), (911.204, 25.8), (968.971, 15.8),
               (2614.511, 35.8)],
}
_ALIASES = {"mixed": ["Am-241", "Cd-109", "Co-57", "Ce-139", "Hg-203", "Sn-113", "Sr-85", "Cs-137",
                      "Y-88", "Co-60"],
            "background": ["K-40", "Ra-226", "Th-232"]}


# ------------------------------------------------------------------ fitting
@dataclass
class CalibrationFit:
    kind: str                              # "energy" or "fwhm"
    order: int
    coeffs: list[float]                    # c0 + c1*ch + ...
    channels: list[float]
    values: list[float]                    # keV (energy or FWHM)
    fitted: list[float]
    labels: list[str] = field(default_factory=list)

    @property
    def residuals(self) -> list[float]:
        return [v - f for v, f in zip(self.values, self.fitted)]

    @property
    def rms(self) -> float:
        r = self.residuals
        return math.sqrt(sum(x * x for x in r) / len(r)) if r else 0.0

    @property
    def max_abs_residual(self) -> float:
        return max((abs(x) for x in self.residuals), default=0.0)

    @property
    def dof(self) -> int:
        return len(self.values) - (self.order + 1)

    def evaluate(self, channel: float) -> float:
        return float(P.polyval(channel, self.coeffs))

    def report(self) -> str:
        unit = "keV" if self.kind == "energy" else "keV FWHM"
        lines = [f"{self.kind.capitalize()} calibration, order {self.order}: "
                 + "  ".join(f"c{i}={c:.9g}" for i, c in enumerate(self.coeffs)),
                 f"{'#':>3} {'channel':>11} {'given':>11} {'fitted':>11} {'residual':>10}  {''}"]
        for i, (ch, v, f) in enumerate(zip(self.channels, self.values, self.fitted), start=1):
            lab = self.labels[i - 1] if i - 1 < len(self.labels) else ""
            lines.append(f"{i:>3} {ch:>11.3f} {v:>11.3f} {f:>11.3f} {v - f:>+10.4f}  {lab}")
        lines.append(f"RMS residual {self.rms:.4f} {unit}, max |residual| {self.max_abs_residual:.4f} {unit}, "
                     f"{self.dof} degree(s) of freedom" + ("  (exact fit: no redundancy)" if self.dof == 0 else ""))
        return "\n".join(lines)


def parse_pairs(text: str) -> list[tuple[float, float]]:
    """'1893.7:661.66, 3364:1173.2' -> [(1893.7, 661.66), (3364.0, 1173.2)]."""
    out = []
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        a, sep, b = part.partition(":")
        if not sep:
            a, sep, b = part.partition("=")
        if not sep:
            raise ValueError(f"bad pair {part!r} (expected channel:value)")
        out.append((float(a), float(b)))
    return out


def _fit(kind: str, pairs: Sequence[tuple[float, float]], order: int,
         weights: Optional[Sequence[float]], labels: Sequence[str]) -> CalibrationFit:
    if order < 0 or order > 3:
        raise ValueError("order must be 0..3")
    if len(pairs) < order + 1:
        raise ValueError(f"order {order} needs at least {order + 1} points, got {len(pairs)}")
    ch = np.array([p[0] for p in pairs], dtype=float)
    v = np.array([p[1] for p in pairs], dtype=float)
    w = None if weights is None else np.asarray(weights, dtype=float)
    coeffs = P.polyfit(ch, v, order, w=w)
    fitted = P.polyval(ch, coeffs)
    return CalibrationFit(kind, order, [float(c) for c in coeffs], ch.tolist(), v.tolist(),
                          fitted.tolist(), list(labels))


def fit_energy_calibration(pairs: Sequence[tuple[float, float]], order: int = 1,
                           weights: Optional[Sequence[float]] = None,
                           labels: Sequence[str] = ()) -> CalibrationFit:
    """Least-squares E(ch) polynomial (order 1-3) through (channel, keV) pairs."""
    if order < 1:
        raise ValueError("energy calibration order must be 1..3")
    return _fit("energy", pairs, order, weights, labels)


def fit_fwhm_calibration(pairs: Sequence[tuple[float, float]], order: int = 1,
                         weights: Optional[Sequence[float]] = None,
                         labels: Sequence[str] = ()) -> CalibrationFit:
    """Least-squares FWHM(ch) polynomial (keV, order 0-3) through (channel, FWHM keV)
    pairs -- the representation stored in ``Spectrum.fwhm_coeffs``."""
    return _fit("fwhm", pairs, order, weights, labels)


# -------------------------------------------------------------- peak search
@dataclass
class Peak:
    index: int             # stored-array index of the maximum
    centroid: float        # channel number (first_channel applied), background subtracted
    height: float          # net counts at the maximum
    area: float            # net counts in +-1.5 FWHM
    fwhm: float            # channels
    significance: float    # net area / sqrt(background in the same window)

    def energy(self, spec: Spectrum) -> Optional[float]:
        return spec.energy_of(self.centroid)


def _smooth(c: np.ndarray, width: int) -> np.ndarray:
    if width <= 1:
        return c.copy()
    k = np.ones(width) / width
    return np.convolve(c, k, mode="same")


def _baseline(c: np.ndarray, half: int) -> np.ndarray:
    """Morphological opening (running min, then running max) of the smoothed
    spectrum, smoothed again: a 'rolling ball' continuum under the peaks."""
    n = len(c)
    sw = np.lib.stride_tricks.sliding_window_view

    def run(x, fn):
        pad = np.concatenate([np.full(half, x[0]), x, np.full(half, x[-1])])
        return fn(sw(pad, 2 * half + 1), axis=1)[:n]
    opened = run(run(c, np.min), np.max)
    return np.minimum(_smooth(opened, 2 * half + 1), c)


def find_peaks(spec_or_counts, min_significance: float = 5.0, max_peaks: int = 60,
               fwhm_guess: Optional[float] = None, start_channel: int = 5) -> list[Peak]:
    """Simple peak search.  Returns peaks sorted by decreasing net area.

    Steps: smooth (box of ~FWHM/2), baseline = running min/max-of-min over ~4
    FWHM, local maxima of the smoothed net spectrum, then for each candidate a
    background-subtracted centroid and half-maximum width on the raw counts.
    `fwhm_guess` (channels) defaults to ~ n/2000 + 2.
    """
    if isinstance(spec_or_counts, Spectrum):
        counts, fc = spec_or_counts.counts, spec_or_counts.first_channel
    else:
        counts, fc = spec_or_counts, 0
    c = np.asarray(counts, dtype=float)
    n = len(c)
    if n < 16:
        return []
    fw = fwhm_guess or max(2.0, n / 2000.0 + 2.0)
    sm = _smooth(c, max(1, int(round(fw / 2))) | 1)
    base = _baseline(sm, max(3, int(round(2.5 * fw))))
    net = sm - base
    cand = np.where((net[1:-1] > net[:-2]) & (net[1:-1] >= net[2:]) & (net[1:-1] > 0))[0] + 1
    peaks: list[Peak] = []
    for i in cand:
        if i < start_channel:
            continue
        h = net[i]
        bg = max(base[i], 1.0)
        half = max(2, int(round(1.5 * fw)))
        lo, hi = max(0, i - half), min(n, i + half + 1)
        seg = c[lo:hi] - base[lo:hi]
        area = float(seg.sum())
        bsum = float(max(base[lo:hi].sum(), 1.0))
        sig = area / math.sqrt(bsum + max(area, 0.0))
        if area <= 0 or sig < min_significance:
            continue
        w = np.clip(seg, 0, None)
        cen = float((np.arange(lo, hi) * w).sum() / w.sum()) if w.sum() > 0 else float(i)
        # FWHM from raw net counts at half maximum (linear interpolation)
        rh = c[i] - base[i]
        hm = rh / 2.0
        left = i
        while left > 0 and c[left] - base[left] > hm:
            left -= 1
        right = i
        while right < n - 1 and c[right] - base[right] > hm:
            right += 1

        def interp(a, b):
            ya, yb = c[a] - base[a] - hm, c[b] - base[b] - hm
            return a + (ya / (ya - yb) if ya != yb else 0.5) * (b - a)
        width = (interp(right - 1, right) if right > i else right) - (interp(left + 1, left) if left < i else left)
        peaks.append(Peak(int(i), cen + fc, float(h), area, float(abs(width)), float(sig)))
    # remove near-duplicates (keep the larger)
    peaks.sort(key=lambda p: -p.area)
    kept: list[Peak] = []
    for p in peaks:
        if all(abs(p.centroid - q.centroid) > max(1.0, 0.8 * fw) for q in kept):
            kept.append(p)
        if len(kept) >= max_peaks:
            break
    return kept


# ----------------------------------------------------- source calibration
@dataclass
class PeakMatch:
    nuclide: str
    energy: float          # library keV
    intensity: float       # %
    peak: Peak
    residual: float = 0.0  # keV, library - fitted


@dataclass
class SourceCalibration:
    fit: CalibrationFit
    matches: list[PeakMatch]
    unmatched: list[tuple[str, float]]     # lines in range without a peak
    peaks: list[Peak]
    fwhm_fit: Optional[CalibrationFit] = None
    method: str = ""
    points: list = field(default_factory=list)          # CalibrationPoint, used and excluded
    validation: Optional["CalibrationValidation"] = None

    @property
    def coeffs(self) -> list[float]:
        return self.fit.coeffs

    def report(self) -> str:
        out = [f"Source calibration ({self.method}): {len(self.matches)} line(s) matched"]
        out.append(self.fit.report())
        if self.fwhm_fit:
            out.append(self.fwhm_fit.report())
        if self.unmatched:
            out.append("Lines in range not found: " + ", ".join(f"{n} {e:.1f}" for n, e in self.unmatched))
        if self.validation is not None:
            out.append(self.validation.report())
        return "\n".join(out)


def source_lines(nuclides: Iterable[str] | str) -> list[tuple[str, float, float]]:
    """['Eu-152'] or 'Co-60,Cs-137' -> [(nuclide, keV, intensity%), ...] by energy."""
    if isinstance(nuclides, str):
        nuclides = [x for x in nuclides.replace(";", ",").replace("+", ",").split(",") if x.strip()]
    lookup = {k.lower().replace("-", ""): k for k in NUCLIDE_LINES}
    names: list[str] = []
    for raw in nuclides:
        key = raw.strip()
        if key.lower() in _ALIASES:
            names.extend(_ALIASES[key.lower()])
            continue
        k = lookup.get(key.lower().replace("-", "").replace(" ", ""))
        if k is None:
            raise KeyError(f"unknown nuclide {raw!r}; known: {', '.join(NUCLIDE_LINES)}")
        names.append(k)
    out = [(n, e, i) for n in dict.fromkeys(names) for e, i in NUCLIDE_LINES[n]]
    return sorted(out, key=lambda t: t[1])


def _match(lines, peaks, coeffs, tol_fn):
    """Greedy one-to-one assignment of lines to the nearest peak (in energy)."""
    used = set()
    res = []
    for name, e, inten in sorted(lines, key=lambda t: -t[2]):
        best, bd = None, None
        for k, p in enumerate(peaks):
            if k in used:
                continue
            d = abs(float(P.polyval(p.centroid, coeffs)) - e)
            if d <= tol_fn(e) and (bd is None or d < bd):
                best, bd = k, d
        if best is not None:
            used.add(best)
            res.append(PeakMatch(name, e, inten, peaks[best]))
    return sorted(res, key=lambda m: m.energy)


def calibrate_from_source(spec: Spectrum, nuclides, order: Optional[int] = None,
                          initial_coeffs: Optional[Sequence[float]] = None,
                          tolerance_kev: Optional[float] = None, max_offset_kev: float = 40.0,
                          min_significance: float = 5.0, use_existing: bool = True) -> SourceCalibration:
    """Propose an energy (and FWHM) calibration from a spectrum of known sources.

    Peak identification:
    * if an initial calibration is available (`initial_coeffs`, or the spectrum's
      own when `use_existing`), each library line is matched to the nearest found
      peak within `tolerance_kev` (default 1% of E, at least 5 keV);
    * otherwise (or if that matches fewer than 2 lines) a pattern search tries every
      pair of strong peaks against every pair of library lines, derives a linear
      gain/offset (|offset| <= `max_offset_kev`), and keeps the hypothesis that
      matches the most intense lines (ties: larger net areas, smaller offset).
    The matched (centroid, keV) pairs are then fitted with `order` (default:
    1 for <= 3 points, 2 otherwise) and the residuals reported.
    """
    lines = source_lines(nuclides)
    peaks = _engine_search(spec, min_significance) or find_peaks(spec, min_significance=min_significance)
    if len(peaks) < 1:
        raise ValueError("no peaks found")
    n_last = spec.first_channel + spec.num_channels - 1
    init = list(initial_coeffs) if initial_coeffs else (list(spec.energy_coeffs) if use_existing else [])
    candidates: list[tuple[str, list[PeakMatch]]] = []
    if init:
        tol = (lambda e: tolerance_kev) if tolerance_kev else (lambda e: max(5.0, 0.01 * e))
        emax = float(P.polyval(n_last, init))
        m0 = _match([l for l in lines if l[1] <= emax], peaks, init, tol)
        if len(m0) >= 2:
            candidates.append(("matched with existing calibration", m0))
    m1 = _pattern_search(lines, peaks, n_last, max_offset_kev, tolerance_kev)
    if len(m1) >= 2:
        candidates.append(("pattern search", m1))
    if not candidates:
        raise ValueError(f"could not identify at least 2 lines of {', '.join(sorted({l[0] for l in lines}))}")
    best = None
    for method, ms in candidates:
        ms, fit = _refine(ms, lines, peaks, n_last, order, tolerance_kev)
        key = (len(ms), -fit.rms)
        if best is None or key > best[0]:
            best = (key, method, ms, fit)
    _, method, matches, fit = best
    # B1: fitted centroids with uncertainties, weighted fit, order by F-test, outlier exclusion
    points, fitted = _build_points(spec, matches, fit.coeffs)
    fit, p_order, chi2r = fit_points(points, order=order)
    used = {(p.nuclide, p.energy): p for p in points if p.used}
    matches = [m for m in matches if (m.nuclide, m.energy) in used]
    for m in matches:
        m.residual = used[(m.nuclide, m.energy)].residual_kev
    matched_e = {m.energy for m in matches}
    emin = float(P.polyval(spec.first_channel, fit.coeffs))
    emax = float(P.polyval(n_last, fit.coeffs))
    unmatched = [(n, e) for n, e, _ in lines if emin <= e <= emax and e not in matched_e]
    fw_pairs = [(m.peak.centroid, m.peak.fwhm * abs(float(P.polyval(m.peak.centroid, P.polyder(fit.coeffs)))))
                for m in matches if m.peak.fwhm > 0]
    fwhm_fit = None
    if len(fw_pairs) >= 2:
        fwhm_fit = fit_fwhm_calibration(fw_pairs, 1 if len(fw_pairs) < 4 else 2,
                                        labels=[f"{m.nuclide} {m.energy:.2f}" for m in matches if m.peak.fwhm > 0])
    validation = validate_calibration(spec, fit, points, lines, p_order, chi2r, fitted)
    return SourceCalibration(fit, matches, unmatched, peaks, fwhm_fit, method, points, validation)


def _engine_search(spec: Spectrum, min_significance: float) -> list[Peak]:
    """Peaks of the analysis engine as :class:`Peak` (largest first), [] if it fails.

    Preferred over :func:`find_peaks` for line assignment: its width model follows the data
    (energy-dependent, also for broad NaI peaks on 4096-channel MCAs) and it fits multiplets.
    """
    from ..analysis.peaks import find_peaks as engine_find_peaks
    try:
        pk = engine_find_peaks(spec, min_sig=min_significance)
    except Exception:
        return []
    fc = spec.first_channel
    out = [Peak(int(round(p.centroid - fc)), float(p.centroid), 0.0, float(p.net_area), float(p.fwhm),
                float(p.significance)) for p in pk if p.net_area > 0]
    return sorted(out, key=lambda p: -p.area)


def _auto_order(order, n):
    if order is None:
        order = 1 if n <= 3 else 2
    return max(1, min(order, n - 1, 3))


def _refine(matches, lines, peaks, n_last, order, tolerance_kev, rounds: int = 4):
    """Fit -> re-match with a tightening tolerance -> fit ..., until stable."""
    fit = None
    for k in range(rounds):
        fit = fit_energy_calibration([(m.peak.centroid, m.energy) for m in matches],
                                     _auto_order(1 if k == 0 else order, len(matches)),
                                     labels=[f"{m.nuclide} {m.energy:.2f}" for m in matches])
        emax = float(P.polyval(n_last, fit.coeffs))
        tol = (lambda e: tolerance_kev) if tolerance_kev else (
            lambda e, f=(4.0, 2.0, 1.5, 1.5)[min(k, 3)]: max(f, 0.003 * e if k == 0 else 0.0015 * e))
        again = _match([l for l in lines if l[1] <= emax], peaks, fit.coeffs, tol)
        if len(again) < 2 or (k > 0 and [m.energy for m in again] == [m.energy for m in matches]):
            break
        matches = again
    fit = fit_energy_calibration([(m.peak.centroid, m.energy) for m in matches], _auto_order(order, len(matches)),
                                 labels=[f"{m.nuclide} {m.energy:.2f}" for m in matches])
    return matches, fit


def _pattern_search(lines, peaks, n_last, max_offset, tolerance_kev):
    strong_peaks = sorted(peaks, key=lambda p: -p.area)[:25]
    strong_lines = sorted(lines, key=lambda l: -l[2])[:12]
    total_int = sum(l[2] for l in lines) or 1.0
    best_key, best_h = None, None
    cent = np.array([p.centroid for p in peaks])
    areas = np.array([p.area for p in peaks])
    lim_e = np.array([l[1] for l in lines])
    lim_i = np.array([l[2] for l in lines])
    for p1, p2 in itertools.combinations(sorted(strong_peaks, key=lambda p: p.centroid), 2):
        for l1, l2 in itertools.combinations(strong_lines, 2):
            if l1[1] > l2[1]:
                l1, l2 = l2, l1
            if l2[1] - l1[1] < 1.0 or p2.centroid - p1.centroid < 2:
                continue
            gain = (l2[1] - l1[1]) / (p2.centroid - p1.centroid)
            off = l1[1] - gain * p1.centroid
            if gain <= 0 or abs(off) > max_offset:
                continue
            emax = off + gain * n_last
            if emax < 100 or emax > 20000:
                continue
            tol_arr = np.full(len(lim_e), tolerance_kev) if tolerance_kev else np.maximum(
                np.maximum(3 * gain, 0.002 * lim_e), 1.0)
            pe = off + gain * cent
            inrange = lim_e <= emax
            hit = (np.abs(lim_e[:, None] - pe[None, :]).min(axis=1) <= tol_arr) & inrange
            nh = int(hit.sum())
            if nh < 2 or (best_key is not None and nh + 1.0 < best_key[0]):
                continue
            score_int = float(lim_i[hit].sum()) / total_int
            near = np.abs(lim_e[:, None] - pe[None, :]).argmin(axis=1)[hit]
            score_area = float(np.log10(np.maximum(areas[near], 1.0)).sum())
            key = (nh + score_int, score_area, -abs(off))
            if best_key is None or key > best_key:
                best_key, best_h = key, (off, gain, emax)
    if best_key is None:
        return []
    off, gain, emax = best_h
    tol = (lambda e: tolerance_kev) if tolerance_kev else (lambda e, g=gain: max(3 * g, 0.002 * e, 1.0))
    best = _match([l for l in lines if l[1] <= emax], peaks, [off, gain], tol)
    return best


# ------------------------------------------------- weighted fit, model choice, validation
# Release B (B1).  The simple peak search above proposes the line-to-peak assignment; the
# positions used in the fit are the analysis engine's fitted centroids with their 1-sigma
# uncertainties.  The polynomial order is raised only when an F-test justifies it, points whose
# residual is inconsistent with their uncertainty are excluded with the reason recorded, and the
# result carries a validation report (independent-line check, monotonicity, calibrated range,
# expected lines that were not found, width consistency).

CENTROID_FLOOR_CH = 0.02      # systematic floor added in quadrature to fitted centroid sigmas
ORDER_TEST_ALPHA = 0.05       # F-test level for raising the polynomial order
OUTLIER_SIGMA = 5.0           # |residual| / sigma above which a point is excluded ...
OUTLIER_MIN_FWHM = 0.1        # ... if the residual is also larger than this fraction of the FWHM
STRONG_LINE_FRACTION = 0.25   # "strong" line: emission probability >= 25 % of the source's largest
MIN_STRONG_MATCHED = 0.5      # fewer strong lines matched than this -> wrong source / assignment
LOO_ERROR_FWHM = 0.5          # an independent line predicted further off than this is an error:
                              # it would fall outside any usable identification window
EXPECTED_SIG_ERROR = 10.0     # a missing line expected at >= this significance is an error
EFFICIENCY_MARGIN = 0.5       # conservative factor for unknown efficiency/background differences
WIDTH_ERROR_RANGE = (0.4, 2.5)  # measured/typical FWHM outside this: no detector of that type

# Natural-background lines (keV) used to flag possible interferences and for the drift check.
BACKGROUND_LINES: list[tuple[str, float]] = [
    ("Pb-212", 238.632), ("Pb-214", 241.997), ("Pb-214", 295.224), ("Pb-214", 351.932),
    ("Tl-208", 583.187), ("Bi-214", 609.312), ("Ac-228", 911.204), ("Ac-228", 968.971),
    ("Bi-214", 1120.287), ("K-40", 1460.822), ("Bi-214", 1764.494), ("Tl-208", 2614.511),
]


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction of the incomplete beta function (Numerical Recipes betacf)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(c) > 1e-300 else 1e300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(c) > 1e-300 else 1e300
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def f_test_pvalue(f: float, d1: int, d2: int) -> float:
    """P(F > f) for an F(d1, d2) distribution."""
    if not f > 0 or d2 <= 0:
        return 1.0
    return _betai(0.5 * d2, 0.5 * d1, d2 / (d2 + d1 * f))


def _wfit(x: np.ndarray, y: np.ndarray, sig: np.ndarray, order: int):
    """Weighted polynomial fit: coeffs (c0..), chi2, covariance (from the stated sigmas)."""
    A = np.vander(x, order + 1, increasing=True)
    w = 1.0 / sig
    Aw = A * w[:, None]
    coeffs, *_ = np.linalg.lstsq(Aw, y * w, rcond=None)
    chi2 = float(np.sum(((y - A @ coeffs) * w) ** 2))
    try:
        cov = np.linalg.inv(Aw.T @ Aw)
    except np.linalg.LinAlgError:
        cov = np.full((order + 1, order + 1), np.nan)
    return coeffs, chi2, cov


def _choose_order(x, y, sig, max_order: int = 3) -> tuple[int, Optional[float]]:
    """Lowest order not significantly improved by the next one (F-test, ORDER_TEST_ALPHA).
    Returns (order, p-value of the last test performed)."""
    n = len(x)
    order, p_last = 1, None
    while order < max_order and n - (order + 2) >= 1:
        _, chi_a, _ = _wfit(x, y, sig, order)
        _, chi_b, _ = _wfit(x, y, sig, order + 1)
        d2 = n - (order + 2)
        f = (chi_a - chi_b) / max(chi_b / d2, 1e-300)
        p_last = f_test_pvalue(f, 1, d2)
        if p_last >= ORDER_TEST_ALPHA:
            break
        order += 1
    return order, p_last


@dataclass
class CalibrationPoint:
    nuclide: str
    energy: float                   # library keV
    channel: float                  # fitted centroid (first_channel convention of the file)
    channel_unc: Optional[float]    # 1-sigma, channels (None: simple-search centroid only)
    fwhm_ch: float                  # fitted FWHM (channels; simple-search width if not fitted), 0 = unknown
    significance: float
    used: bool = True
    reason: str = ""                # why it was excluded
    residual_kev: float = 0.0       # library - fitted
    loo_residual_kev: Optional[float] = None   # library - fit without this point (independent check)

    @property
    def label(self) -> str:
        return f"{self.nuclide} {self.energy:.2f}"


@dataclass
class CalibrationValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    order: int = 1
    order_test_p: Optional[float] = None
    chi2_reduced: Optional[float] = None
    n_used: int = 0
    range_kev: Optional[tuple[float, float]] = None     # energies of the outermost used lines
    range_channels: Optional[tuple[float, float]] = None
    extrapolated_fraction: float = 0.0                  # of the spectrum's channels outside the range
    monotonic: bool = True
    loo_max_fwhm: Optional[float] = None                # worst leave-one-out deviation / FWHM
    missing_strong: list[tuple[str, float]] = field(default_factory=list)
    fwhm_ratio_to_type: Optional[float] = None          # measured / typical FWHM of the guessed type
    detector_type: str = ""

    def report(self) -> str:
        out = [f"Validation: {'OK' if self.ok else 'NOT OK'} - {self.n_used} point(s), order {self.order}"
               + (f" (F-test p = {self.order_test_p:.3g} for the next order)" if self.order_test_p is not None else "")
               + (f", chi2/dof = {self.chi2_reduced:.3g}" if self.chi2_reduced is not None else "")]
        if self.range_kev:
            out.append(f"Calibrated range {self.range_kev[0]:.1f} - {self.range_kev[1]:.1f} keV; "
                       f"{100 * self.extrapolated_fraction:.0f} % of the channels lie outside it (extrapolated)")
        if self.loo_max_fwhm is not None:
            out.append(f"Independent-line check (leave one out): worst deviation {self.loo_max_fwhm:.3f} FWHM")
        out += [f"ERROR: {e}" for e in self.errors] + [f"Warning: {w}" for w in self.warnings]
        return "\n".join(out)


def _inverse(coeffs, energy: float, lo: float, hi: float) -> Optional[float]:
    """Channel with E(ch) = energy inside [lo, hi] (monotonic calibration), or None."""
    grid = np.linspace(lo, hi, 4001)
    e = P.polyval(grid, coeffs)
    if not np.all(np.diff(e) > 0) or not e[0] <= energy <= e[-1]:
        return None
    return float(np.interp(energy, e, grid))


def _fitted_peaks(spec: Spectrum, coeffs):
    """Analysis-engine peaks of `spec` under the provisional calibration `coeffs`."""
    from ..analysis.peaks import find_peaks as engine_find_peaks
    return engine_find_peaks(replace(spec, energy_coeffs=list(coeffs), fwhm_coeffs=[]), min_sig=3.0)


def _build_points(spec: Spectrum, matches: list[PeakMatch], coeffs) -> tuple[list[CalibrationPoint], list]:
    """Replace simple-search centroids by fitted ones (nearest within 0.5 FWHM).
    Returns the points and the engine peaks."""
    try:
        fitted = _fitted_peaks(spec, coeffs)
    except Exception:          # the engine must never prevent a calibration proposal
        fitted = []
    pts = []
    for m in matches:
        sp = m.peak
        best = None
        for q in fitted:
            d = abs(q.centroid - sp.centroid)
            if d <= 0.5 * max(q.fwhm, sp.fwhm, 1.0) and (best is None or d < abs(best.centroid - sp.centroid)):
                best = q
        if best is not None and best.centroid_unc:
            # fitted width (free width scale per fit group) is a better measurement than the
            # half-maximum width of the simple search, which is poor for broad NaI peaks
            pts.append(CalibrationPoint(m.nuclide, m.energy, float(best.centroid), float(best.centroid_unc),
                                        float(best.fwhm), float(best.significance)))
        else:
            pts.append(CalibrationPoint(m.nuclide, m.energy, sp.centroid, None, sp.fwhm, sp.significance))
    return pts, fitted


def _sigma_kev(p: CalibrationPoint, gain: float) -> float:
    cu = p.channel_unc if p.channel_unc else max(0.1 * (p.fwhm_ch or 2.0), CENTROID_FLOOR_CH)
    return abs(gain) * math.hypot(cu, CENTROID_FLOOR_CH)


def _fwhm_kev_at(points: list[CalibrationPoint], coeffs, energy: float, det: str) -> float:
    """Measured FWHM (keV) near `energy` from the points, else the detector-type default."""
    from ..analysis.peaks import default_fwhm_kev
    meas = [(p.energy, p.fwhm_ch * abs(float(P.polyval(p.channel, P.polyder(coeffs)))))
            for p in points if p.fwhm_ch > 0]
    if len(meas) >= 2:
        e, f = np.array(meas).T
        o = np.argsort(e)
        return float(np.interp(energy, e[o], f[o]))
    return float(default_fwhm_kev(energy, det or "HPGe"))


def fit_points(points: list[CalibrationPoint], order: Optional[int] = None, det: str = "",
               max_order: int = 3) -> tuple[CalibrationFit, Optional[float], Optional[float]]:
    """Weighted fit of the used points with order selection and outlier exclusion.

    Mutates `points` (used / reason / residuals).  Returns (fit, F-test p, chi2/dof).
    """
    while True:
        use = [p for p in points if p.used]
        if len(use) < 2:
            raise ValueError("fewer than 2 usable calibration points")
        x = np.array([p.channel for p in use])
        y = np.array([p.energy for p in use])
        gain0 = (y.max() - y.min()) / max(x.max() - x.min(), 1e-9)
        sig = np.array([_sigma_kev(p, gain0) for p in use])
        if order is None:
            o, p_test = _choose_order(x, y, sig, min(max_order, len(use) - 1))
        else:
            o, p_test = max(1, min(order, len(use) - 1, 3)), None
        coeffs, chi2, _cov = _wfit(x, y, sig, o)
        res = y - P.polyval(x, coeffs)
        z = np.abs(res) / sig
        # worst point inconsistent with its uncertainty AND relevant on the resolution scale
        fw = np.array([_fwhm_kev_at(points, coeffs, p.energy, det) for p in use])
        bad = (z > OUTLIER_SIGMA) & (np.abs(res) > OUTLIER_MIN_FWHM * fw)
        if bad.any() and len(use) > o + 2:
            k = int(np.argmax(np.where(bad, z, -1)))
            p = use[k]
            near = [f"{n} {e:.1f} keV" for n, e in BACKGROUND_LINES if abs(e - p.energy) < 1.5 * fw[k]]
            p.used = False
            p.reason = (f"residual {res[k]:+.3f} keV = {z[k]:.1f} sigma ({abs(res[k]) / fw[k]:.2f} FWHM)"
                        + (f"; possible interference: {', '.join(near)}" if near else ""))
            continue
        break
    for p in points:
        p.residual_kev = float(p.energy - P.polyval(p.channel, coeffs))
    # leave-one-out residuals (independent-line check)
    if len(use) >= o + 2:
        for k, p in enumerate(use):
            keep = np.arange(len(use)) != k
            c_k, _, _ = _wfit(x[keep], y[keep], sig[keep], o)
            p.loo_residual_kev = float(p.energy - P.polyval(p.channel, c_k))
    dof = len(use) - (o + 1)
    fit = CalibrationFit("energy", o, [float(c) for c in coeffs], x.tolist(), y.tolist(),
                         P.polyval(x, coeffs).tolist(), [p.label for p in use])
    return fit, p_test, (chi2 / dof if dof > 0 else None)


def validate_calibration(spec: Spectrum, fit: CalibrationFit, points: list[CalibrationPoint],
                         lines: list[tuple[str, float, float]], order_test_p: Optional[float] = None,
                         chi2_reduced: Optional[float] = None, fitted_peaks: Optional[list] = None
                         ) -> CalibrationValidation:
    """Checks of a proposed energy calibration (see module notes).

    `fitted_peaks` (analysis-engine peaks, centroids in channels) enables the check for lines
    that should have been detected but have no peak at their predicted position."""
    from ..analysis.peaks import default_fwhm_kev, guess_detector
    use = [p for p in points if p.used]
    v = CalibrationValidation(ok=True, order=fit.order, order_test_p=order_test_p,
                              chi2_reduced=chi2_reduced, n_used=len(use))
    c = fit.coeffs
    first = spec.first_channel
    last = spec.first_channel + spec.num_channels - 1
    # monotonic over the whole spectrum (boundary behaviour of order >= 2)
    grid = np.linspace(first, last, 2001)
    deriv = P.polyval(grid, P.polyder(c))
    v.monotonic = bool(np.all(deriv > 0))
    if not v.monotonic:
        bad = grid[deriv <= 0]
        v.errors.append(f"energy is not increasing with channel between channels {bad.min():.0f} and {bad.max():.0f}")
    ens = [p.energy for p in use]
    chs = [p.channel for p in use]
    v.range_kev = (min(ens), max(ens))
    v.range_channels = (min(chs), max(chs))
    outside = (grid < min(chs)) | (grid > max(chs))
    v.extrapolated_fraction = float(outside.mean())
    if v.extrapolated_fraction > 0.2:
        v.warnings.append(f"{100 * v.extrapolated_fraction:.0f} % of the spectrum lies outside the calibrated range "
                          f"{v.range_kev[0]:.0f}-{v.range_kev[1]:.0f} keV; energies there are extrapolated")
    if len(use) <= fit.order + 1:
        v.warnings.append("no redundant points: the fit passes exactly through the points, residuals say nothing")
    elif len(use) < fit.order + 3:
        v.warnings.append("only one redundant point: add lines to check the calibration")
    det = guess_detector(replace(spec, energy_coeffs=list(c), fwhm_coeffs=[]))
    v.detector_type = det
    # independent-line check
    loo = [(abs(p.loo_residual_kev) / _fwhm_kev_at(points, c, p.energy, det))
           for p in use if p.loo_residual_kev is not None]
    if loo:
        v.loo_max_fwhm = float(max(loo))
        if v.loo_max_fwhm > LOO_ERROR_FWHM:
            v.errors.append(f"an independent line (left out of the fit) is predicted {v.loo_max_fwhm:.2f} FWHM away "
                            "from its peak: the line assignment is inconsistent")
        elif v.loo_max_fwhm > 0.25:
            v.warnings.append(f"leaving one line out moves its predicted energy by up to {v.loo_max_fwhm:.2f} FWHM: "
                              "the calibration depends strongly on single points")
    if chi2_reduced is not None and chi2_reduced > 10:
        v.warnings.append(f"scatter of the points is {math.sqrt(chi2_reduced):.1f}x their centroid uncertainties")
    # expected strong lines that were not found (wrong source or wrong assignment)
    e_lo, e_hi = float(P.polyval(first, c)), float(P.polyval(last, c))
    by_nuc: dict[str, float] = {}
    for n, e, i in lines:
        by_nuc[n] = max(by_nuc.get(n, 0.0), i)
    strong = [(n, e) for n, e, i in lines
              if i >= STRONG_LINE_FRACTION * by_nuc[n] and max(e_lo, 40.0) <= e <= e_hi
              and not (n == "Na-22" and e == 511.0)]      # annihilation: not a nuclide line
    found = {(p.nuclide, p.energy) for p in use}
    v.missing_strong = [(n, e) for n, e in strong if (n, e) not in found]
    if strong and (len(strong) - len(v.missing_strong)) / len(strong) < MIN_STRONG_MATCHED:
        v.errors.append(f"only {len(strong) - len(v.missing_strong)} of {len(strong)} strong source lines in range were "
                        "matched (" + ", ".join(f"{n} {e:.1f}" for n, e in v.missing_strong[:6])
                        + (" ..." if len(v.missing_strong) > 6 else "") + " missing): wrong source or wrong line assignment")
    elif v.missing_strong:
        v.warnings.append("strong lines in range not matched: "
                          + ", ".join(f"{n} {e:.1f}" for n, e in v.missing_strong))
    # the strongest peaks of a source spectrum must be explained by the source (or background)
    if fitted_peaks:
        known = [e for _n, e, _i in lines] + [e for _n, e in BACKGROUND_LINES] + [511.0]
        top = sorted((q for q in fitted_peaks if float(P.polyval(q.centroid, c)) >= 40.0),
                     key=lambda q: -q.significance)[:3]
        def explained(q) -> bool:
            eq = float(P.polyval(q.centroid, c))
            return min(abs(eq - e) for e in known) <= 0.5 * _fwhm_kev_at(points, c, eq, det)
        if top and not any(explained(q) for q in top):
            v.errors.append("none of the three strongest peaks is a line of the claimed source or of the natural "
                            "background under this calibration: wrong source or wrong line assignment")
    # lines that should be clearly visible, judged from a found line of the same nuclide
    if fitted_peaks is not None:
        inten = {(n, e): i for n, e, i in lines}
        pk_e = [float(P.polyval(q.centroid, c)) for q in fitted_peaks]
        for n, e, i in lines:
            if (n, e) in found or not max(e_lo, 40.0) <= e <= e_hi or (n == "Na-22" and e == 511.0):
                continue
            fw = _fwhm_kev_at(points, c, e, det)
            if any(abs(x - e) <= fw for x in pk_e):
                continue                              # a peak is there (maybe merged / not assigned)
            refs = [p for p in use if p.nuclide == n and 0.5 <= p.energy / e <= 2.0]
            if not refs:
                continue
            ref = max(refs, key=lambda p: p.significance)
            exp_sig = ref.significance * i / inten[(n, ref.energy)] * EFFICIENCY_MARGIN
            if exp_sig >= EXPECTED_SIG_ERROR:
                v.errors.append(f"{n} {e:.1f} keV should be visible (significance ~{exp_sig:.0f} expected from "
                                f"{ref.label}) but no peak is there: wrong source or wrong line assignment")
    # FWHM consistent with the detector type
    fr = [p.fwhm_ch * abs(float(P.polyval(p.channel, P.polyder(c)))) / float(default_fwhm_kev(p.energy, det or "HPGe"))
          for p in use if p.fwhm_ch > 0]
    if fr:
        v.fwhm_ratio_to_type = float(np.median(fr))
        if not WIDTH_ERROR_RANGE[0] <= v.fwhm_ratio_to_type <= WIDTH_ERROR_RANGE[1]:
            v.errors.append(f"measured peak widths are {v.fwhm_ratio_to_type:.2f}x the typical {det or 'HPGe'} "
                            "resolution under this calibration: the gain is implausible (wrong line assignment)")
        elif not 0.5 <= v.fwhm_ratio_to_type <= 2.0:
            v.warnings.append(f"measured peak widths are {v.fwhm_ratio_to_type:.2f}x the typical {det or 'HPGe'} "
                              "resolution: check the detector type or the line assignment")
    excluded = [p for p in points if not p.used]
    for p in excluded:
        v.warnings.append(f"excluded {p.label}: {p.reason}")
    v.ok = not v.errors
    return v


# ------------------------------------------------------------------------ drift check
@dataclass
class DriftCheck:
    detected: bool
    message: str
    proposed_coeffs: Optional[list[float]] = None      # E_new(ch) = a + b * E_old(ch), as coefficients
    correction: Optional[tuple[float, float]] = None   # (a keV, b)
    max_shift_kev: float = 0.0                         # largest |E_new - E_old| over the reference lines
    max_shift_fwhm: float = 0.0
    max_shift_sigma: float = 0.0
    points: list[tuple[str, float, float, float]] = field(default_factory=list)  # name, E_ref, E_measured, sigma
    excluded: list[tuple[str, float, str]] = field(default_factory=list)

    def report(self) -> str:
        out = [self.message]
        for n, er, em, s in self.points:
            out.append(f"  {n:8s} {er:9.3f} keV  measured {em:9.3f}  ({em - er:+.3f} +- {s:.3f})")
        out += [f"  excluded {n} {e:.1f}: {r}" for n, e, r in self.excluded]
        if self.proposed_coeffs is not None:
            out.append("Proposed coefficients (apply only after review): "
                       + "  ".join(f"c{i}={x:.9g}" for i, x in enumerate(self.proposed_coeffs)))
        return "\n".join(out)


def _neighbour_lines(nuclides) -> set[float]:
    """Energies (keV) of all lines >= 5 % of the given nuclides in the shared nuclear library."""
    try:
        from ..analysis.library import load_library
        lib = load_library()
    except Exception:
        return set()
    out = set()
    for n in nuclides:
        nd = lib.get(n)
        if nd is not None:
            out.update(float(g.energy) for g in nd.gammas(5.0))
    return out


def check_drift(spec: Spectrum, lines: Optional[Sequence[tuple[str, float]]] = None, max_drift: float = 0.03,
                threshold_fwhm: float = 0.1, threshold_sigma: float = 3.0, peaks=None) -> DriftCheck:
    """Compare the stored energy calibration with known lines in the spectrum itself.

    `lines` defaults to natural-background lines (:data:`BACKGROUND_LINES`); a nuclide string
    ("Co-60,Cs-137") selects calibration-source lines.  A relative gain error up to `max_drift`
    is searched first (most lines within 0.5 FWHM), then E_ref = a + b * E_measured is fitted
    with the centroid uncertainties.  Drift is reported when the implied shift exceeds both
    `threshold_fwhm` of the resolution and `threshold_sigma` standard uncertainties somewhere
    in the range of the lines.  Nothing is changed: the corrected coefficients are a proposal.
    `peaks`: the engine's peaks of `spec` when already found (avoids a second search).
    """
    from ..analysis.peaks import find_peaks as engine_find_peaks
    if not spec.energy_coeffs:
        raise ValueError("the spectrum has no energy calibration to check")
    if lines is None:
        ref = list(BACKGROUND_LINES)
    elif isinstance(lines, str):
        ref = [(n, e) for n, e, _i in source_lines(lines) if not (n == "Na-22" and e == 511.0)]
    else:
        ref = list(lines)
    # every known line of these nuclides (shared library, >= 5 % emission), to recognise blends
    others = _neighbour_lines({n for n, _e in ref}) | {e for _n, e in ref}
    pk = [p for p in (peaks if peaks is not None else engine_find_peaks(spec))
          if p.energy is not None and p.significance >= 5 and p.fwhm_kev]
    if not pk:
        return DriftCheck(False, "no significant peaks: drift cannot be checked")
    pe = np.array([p.energy for p in pk])
    pf = np.array([p.fwhm_kev for p in pk])
    e_lo, e_hi = pe.min() - 3 * pf.max(), pe.max() + 3 * pf.max()
    ref = [(n, e) for n, e in ref if e_lo <= e <= e_hi]
    if len(ref) < 2:
        return DriftCheck(False, "fewer than 2 reference lines in the spectrum's range: drift not checked")
    # 1) coarse gain search
    step = max(min(0.25 * float(np.median(pf)) / e for _n, e in ref), 1e-5)
    best_k, best_key = 0.0, None
    for k in np.arange(-max_drift, max_drift + step / 2, step):
        hits = 0
        for _n, e in ref:
            d = np.abs(pe / (1.0 + k) - e)
            j = int(np.argmin(d))
            hits += d[j] <= 0.5 * pf[j]
        key = (hits, -abs(k))
        if best_key is None or key > best_key:
            best_k, best_key = float(k), key
    # 2) assignment at the best gain, then weighted linear fit with outlier exclusion.
    # A line with another known line within 1 FWHM is an unresolved blend: its peak centroid lies
    # between the lines (by unknown intensities), so it cannot serve as a reference energy.
    pts, excl = [], []
    for n, e in ref:
        d = np.abs(pe / (1.0 + best_k) - e)
        j = int(np.argmin(d))
        if d[j] > 0.5 * pf[j]:
            continue
        p = pk[j]
        blend = sorted({round(o, 1) for o in others if 0.05 < abs(o - e) <= float(p.fwhm_kev)})
        if blend:
            excl.append((n, e, "unresolved from " + ", ".join(f"{o:.1f}" for o in blend) + " keV"))
            continue
        gain = p.fwhm_kev / p.fwhm if p.fwhm else 1.0
        s = gain * math.hypot(p.centroid_unc or 0.1 * p.fwhm, CENTROID_FLOOR_CH)
        pts.append((n, e, float(p.energy), s, float(p.fwhm_kev)))
    while True:
        if len(pts) < 2:
            return DriftCheck(False, "fewer than 2 reference lines found: drift not checked",
                              excluded=excl)
        er = np.array([q[1] for q in pts])
        em = np.array([q[2] for q in pts])
        sg = np.array([q[3] for q in pts])
        fw = np.array([q[4] for q in pts])
        # gain-only correction (ADC zero stable, amplifier/PMT gain drifts) unless an offset is
        # justified by an F-test at ORDER_TEST_ALPHA with >= 3 lines
        w = 1.0 / sg ** 2
        b1 = float(np.sum(w * em * er) / np.sum(w * em * em))
        chi_1 = float(np.sum(w * (er - b1 * em) ** 2))
        a, b = 0.0, b1
        cov = np.array([[0.0, 0.0], [0.0, 1.0 / float(np.sum(w * em * em))]])
        offset_p = None
        if len(pts) >= 3:
            (a2, b2), chi_2, cov2 = _wfit(em, er, sg, 1)
            d2 = len(pts) - 2
            offset_p = f_test_pvalue((chi_1 - chi_2) / max(chi_2 / d2, 1e-300), 1, d2)
            if offset_p < ORDER_TEST_ALPHA:
                a, b, cov = float(a2), float(b2), cov2
        res = er - (a + b * em)
        z = np.abs(res) / sg
        bad = (z > OUTLIER_SIGMA) & (np.abs(res) > OUTLIER_MIN_FWHM * fw)
        if bad.any() and len(pts) > 3:
            k = int(np.argmax(np.where(bad, z, -1)))
            excl.append((pts[k][0], pts[k][1], f"residual {res[k]:+.3f} keV ({z[k]:.1f} sigma): interference or "
                                               "not present"))
            pts.pop(k)
            continue
        break
    # shift E_new - E_old over the range of the lines, with its uncertainty
    eg = np.linspace(em.min(), em.max(), 50)
    shift = a + (b - 1.0) * eg
    J = np.vstack([np.ones_like(eg), eg]).T
    s_shift = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", J, cov, J), 0.0))
    fwg = np.interp(eg, np.sort(em), fw[np.argsort(em)])
    k = int(np.argmax(np.abs(shift) / fwg))
    r = DriftCheck(False, "", correction=(float(a), float(b)),
                   max_shift_kev=float(np.max(np.abs(shift))), max_shift_fwhm=float(np.abs(shift[k]) / fwg[k]),
                   max_shift_sigma=float(np.max(np.abs(shift) / np.maximum(s_shift, 1e-12))),
                   points=[(q[0], q[1], q[2], q[3]) for q in pts], excluded=excl)
    r.detected = r.max_shift_fwhm > threshold_fwhm and r.max_shift_sigma > threshold_sigma
    new = [b * x for x in spec.energy_coeffs]
    new[0] += a
    r.proposed_coeffs = [float(x) for x in new]
    rel = (b - 1.0) * 100
    r.message = (f"{'DRIFT DETECTED' if r.detected else 'No significant drift'}: {len(pts)} reference line(s), "
                 f"gain {rel:+.3f} %, offset {a:+.2f} keV"
                 + (" (fixed: not justified by the lines)" if a == 0.0 else "") + f"; largest shift {r.max_shift_kev:.2f} keV = "
                 f"{r.max_shift_fwhm:.2f} FWHM ({r.max_shift_sigma:.1f} sigma)")
    return r


# -------------------------------------------------------------- applying
def apply_calibration(spec: Spectrum, energy_coeffs: Optional[Sequence[float]] = None,
                      fwhm_coeffs: Optional[Sequence[float]] = None, note: str = "") -> Spectrum:
    """Copy of `spec` with the new calibration(s); the previous energy calibration
    is preserved in ``extra['previous_energy_coeffs']``."""
    extra = dict(spec.extra)
    if energy_coeffs is not None:
        if spec.energy_coeffs:
            extra["previous_energy_coeffs"] = ", ".join(f"{c:.10g}" for c in spec.energy_coeffs)
        extra["recalibrated"] = note or "energy calibration replaced"
    return replace(spec,
                   energy_coeffs=list(energy_coeffs) if energy_coeffs is not None else list(spec.energy_coeffs),
                   fwhm_coeffs=list(fwhm_coeffs) if fwhm_coeffs is not None else list(spec.fwhm_coeffs),
                   extra=extra)


@dataclass
class BatchCalibrationResult:
    source: Path
    output: Optional[Path]
    coeffs: list[float]
    error: Optional[str] = None
    report: str = ""


def apply_calibration_batch(paths: Iterable[Path], out_dir: Path,
                            energy_coeffs: Optional[Sequence[float]] = None,
                            fwhm_coeffs: Optional[Sequence[float]] = None,
                            source: Optional[str] = None, order: Optional[int] = None,
                            out_fmt=None, only_uncalibrated: bool = False,
                            progress: Optional[Callable[[int, int, Path], Optional[bool]]] = None
                            ) -> list[BatchCalibrationResult]:
    """Write recalibrated copies of `paths` into `out_dir` (never in place).

    Either a fixed calibration (`energy_coeffs` / `fwhm_coeffs`) is applied to all
    files, or each file is calibrated from its own peaks with `source`
    (e.g. "Co-60,Cs-137").  `out_fmt` (FormatSpec/key) defaults to the input
    format when writable, else IAEA SPE.  `only_uncalibrated` skips files that
    already carry an energy calibration.
    """
    from ..convert import output_name, read_spectra, resolve_format, write_spectrum

    paths = [Path(p) for p in paths]
    out_dir = Path(out_dir)
    results: list[BatchCalibrationResult] = []
    for k, path in enumerate(paths, start=1):
        try:
            spectra, fmt_in = read_spectra(path)
            fmt = resolve_format(out_fmt) if out_fmt is not None else (
                fmt_in if fmt_in.can_write else resolve_format("iaea_spe"))
            for i, s in enumerate(spectra, start=1):
                if only_uncalibrated and s.energy_coeffs:
                    results.append(BatchCalibrationResult(path, None, list(s.energy_coeffs),
                                                          "skipped: already calibrated"))
                    continue
                rep = ""
                coeffs, fwhm = energy_coeffs, fwhm_coeffs
                if source:
                    sc = calibrate_from_source(s, source, order=order)
                    coeffs, rep = sc.coeffs, sc.report()
                    if fwhm is None and sc.fwhm_fit:
                        fwhm = sc.fwhm_fit.coeffs
                new = apply_calibration(s, coeffs, fwhm, note=f"SpectraMaster calibrate ({source or 'coefficients'})")
                target = out_dir / output_name(path, fmt, i if len(spectra) > 1 else None)
                write_spectrum(new, target, fmt)
                results.append(BatchCalibrationResult(path, target, list(coeffs or []), None, rep))
        except Exception as exc:
            results.append(BatchCalibrationResult(path, None, [], f"{type(exc).__name__}: {exc}"))
        if progress is not None and progress(k, len(paths), path) is False:
            break
    return results

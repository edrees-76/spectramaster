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
    peaks = find_peaks(spec, min_significance=min_significance)
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
    for m, r in zip(matches, fit.residuals):
        m.residual = r
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
    return SourceCalibration(fit, matches, unmatched, peaks, fwhm_fit, method)


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

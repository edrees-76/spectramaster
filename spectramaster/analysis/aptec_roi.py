"""Aptec-compatible region-of-interest (ROI) arithmetic.

Pure functions, no GUI imports.  The rules are those of Aptec PCMCA/WIN 6.31 as described in
its help file (ROI Properties, ROI Information, Statistical Error, MDA Definition), checked
against the ROI records Aptec stored in its spectrum files (79 ROIs in the Aptec sample files,
``tests/test_aptec_roi.py``):

* **Background end points** -- ``X`` channels outside each side of the ROI: ``BL = RL - X``,
  ``BH = RH + X`` (or ``X`` varying linearly from a low-energy to a high-energy value).
  When the end points of an ROI would fall inside its neighbour (touching ROIs of a painted
  multiplet, or two ROIs less than ``X`` channels apart) the ROIs form a group with one shared
  background: end points outside the whole group plus the channels between its ROIs
  (``chern.s0``: a 3-channel gap with X = 5 is grouped; ``co60cal.s0``: a 2-channel gap with
  X = 2 is not).                                                               79/79 ROIs
* **Background line** -- degree 0: the straight line joining the average of the left end points
  (placed at channel ``RL - 1``) and of the right end points (at ``RH + 1``); degree 1-5:
  unweighted least-squares polynomial through the end-point channels.  The ROI background is
  the sum of the line over ``RL..RH``.
* **Gross** = sum of ``RL..RH``; **Net** = Gross - Background;
  **% error (1 sigma)** = sqrt(Gross + Background) / Net * 100.
  Gross 79/79.  Background, net and error 73/79: the other six are the ROIs of ``nai1x1.s0``,
  whose stored background cannot be reproduced from its stored counts with any end-point
  window or weighting, so they were presumably computed from an earlier state of that file.
* **FWHM / FWTM points** -- from the channel of maximum net counts, outward to the first channel
  below 1/2 (1/10) of that maximum, linear interpolation between the two channels.  When no
  such channel exists inside the ROI Aptec stores the opposite ROI edge (``RH`` for the low
  point, ``RL`` for the high one); the width is then reported as not found.
  FWHM 72/73, FWTM 64/73 (outside ``nai1x1.s0``; the differences are weak, noisy peaks)
* **Centroid** -- weighted mean of the channel numbers with weight ``Net`` or ``Net*|Net|``,
  over the channels between the gross half-maximum points, the net FWHM or FWTM points
  (rounded to whole channels) or the whole ROI.                                 69/73
* **MDA** (counts per second) = ``(K^2 + 2 K sqrt(2 B)) / live time``, K = MDA sigma
  (help file; not stored per ROI in the examples, so not verified).
* **Flags** -- Aptec's letters (S_List "Activity Flags"); here only ``?`` (net rate below the
  MDA) is set, the others come with background subtraction, MultiFit and quantification.

Channels here are indices into the stored counts (``Spectrum.counts``); add
``Spectrum.first_channel`` for channel numbers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Optional, Sequence

import numpy as np

CENTROID_RANGES = ("ghm", "fwhm", "fwtm", "all")      # gross half max, net half/tenth max, whole ROI
CENTROID_WEIGHTS = ("net", "squared")                # Net*Chan, Net*|Net|*Chan
MAX_END_POINTS = 32


@dataclass
class RoiProperties:
    """Aptec *ROI Properties* (Shift+R)."""
    bkg_degree: int = 1                 # 0 = straight line between end-point averages; 1-5 least squares
    end_points: int = 3                 # X channels on each side
    variable_end_points: bool = False   # X varies from end_points_low (channel 0) to end_points_high
    end_points_low: int = 2
    end_points_high: int = 12
    centroid_range: str = "fwhm"
    centroid_weight: str = "squared"
    mda_sigma: float = 1.645
    error_sigma: float = 1.0

    def validate(self) -> "RoiProperties":
        if not 0 <= int(self.bkg_degree) <= 5:
            raise ValueError("background degree must be 0..5")
        for v in (self.end_points, self.end_points_low, self.end_points_high):
            if not 0 <= int(v) <= MAX_END_POINTS:
                raise ValueError(f"end points must be 0..{MAX_END_POINTS}")
        if self.centroid_range not in CENTROID_RANGES:
            raise ValueError(f"centroid range must be one of {CENTROID_RANGES}")
        if self.centroid_weight not in CENTROID_WEIGHTS:
            raise ValueError(f"centroid weighting must be one of {CENTROID_WEIGHTS}")
        if self.bkg_degree >= 2 and self.end_points < 5 and not self.variable_end_points:
            pass                        # Aptec only advises 10+ end points for 2nd order and above
        return self

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "RoiProperties":
        known = set(cls.__dataclass_fields__)
        out = cls(**{k: v for k, v in (d or {}).items() if k in known})
        try:
            return out.validate()
        except (ValueError, TypeError):
            return cls()


@dataclass
class AptecRoi:
    """Results for one ROI (indices into the counts)."""
    rl: int
    rh: int
    bl: int
    bh: int
    group_lo: int                       # first / last channel of the ROI group sharing the background
    group_hi: int
    coeffs: list[float]                 # background per channel = polynomial in the index
    gross: float
    background: float
    net: float
    err_pct: Optional[float]            # 1 sigma, percent of net (None when net = 0)
    centroid: Optional[float]
    fwhm_points: tuple[float, float]
    fwtm_points: tuple[float, float]
    fwhm: Optional[float]               # channels; None when a half-maximum point was not found
    fwtm: Optional[float]
    live_time: Optional[float] = None
    mda_cps: Optional[float] = None
    net_cps: Optional[float] = None
    flags: str = ""
    grouped: bool = False               # shares its background with a neighbouring ROI

    @property
    def net_unc(self) -> float:
        """1-sigma uncertainty of the net counts (Aptec's statistical error)."""
        return math.sqrt(max(self.gross + self.background, 0.0))

    def background_at(self, idx) -> np.ndarray:
        return np.polynomial.polynomial.polyval(np.asarray(idx, dtype=float), self.coeffs)


def end_point_width(props: RoiProperties, channel: float, n_channels: int) -> int:
    if not props.variable_end_points:
        return int(props.end_points)
    f = min(max(channel / max(n_channels - 1, 1), 0.0), 1.0)
    return int(round(props.end_points_low + (props.end_points_high - props.end_points_low) * f))


def groups(rois: Sequence[tuple[int, int]], gap=0) -> list[list[int]]:
    """Indices of ROIs grouped when they are at most ``gap`` channels apart (sorted by left edge).

    ``gap`` is a number or a function ``gap(hi, lo)`` of the two facing edges."""
    order = sorted(range(len(rois)), key=lambda i: (rois[i][0], rois[i][1]))
    out: list[list[int]] = []
    hi = None
    for i in order:
        lo_i, hi_i = rois[i]
        g = gap(hi, lo_i) if callable(gap) and hi is not None else (gap if not callable(gap) else 0)
        if out and hi is not None and lo_i <= hi + 1 + g:
            out[-1].append(i)
            hi = max(hi, hi_i)
        else:
            out.append([i])
            hi = hi_i
    return out


def background_coeffs(counts: np.ndarray, bl: int, lo: int, hi: int, bh: int, degree: int,
                      inner: Sequence[int] = ()) -> list[float]:
    """Background line through the end points ``bl..lo-1``, ``hi+1..bh`` and the ``inner`` channels
    between the ROIs of a group (see module docstring)."""
    left = np.arange(bl, lo)
    right = np.arange(hi + 1, bh + 1)
    inner = np.asarray(inner, dtype=int)
    if degree == 0 or len(left) + len(right) + len(inner) <= degree:
        if len(left) and len(right):
            ya, yb = float(counts[left].mean()), float(counts[right].mean())
            xa, xb = lo - 1.0, hi + 1.0
            b1 = (yb - ya) / (xb - xa)
            return [ya - b1 * xa, b1]
        side = left if len(left) else right
        return [float(counts[side].mean())] if len(side) else [0.0]
    idx = np.r_[left, inner, right]
    ch = idx.astype(float)
    y = counts[idx].astype(float)
    scale = max(abs(ch).max(), 1.0)
    c = np.polynomial.polynomial.polyfit(ch / scale, y, degree)
    return [float(v) for v in c / scale ** np.arange(degree + 1)]


def _crossing(net: np.ndarray, rl: int, rh: int, imax: int, level: float) -> tuple[float, float, bool]:
    i = imax
    while i > rl and net[i - 1] >= level:
        i -= 1
    found_lo = i > rl
    lo = (i - 1 + (level - net[i - 1]) / (net[i] - net[i - 1])) if found_lo else float(rh)
    i = imax
    while i < rh and net[i + 1] >= level:
        i += 1
    found_hi = i < rh
    hi = (i + (net[i] - level) / (net[i] - net[i + 1])) if found_hi else float(rl)
    return float(lo), float(hi), found_lo and found_hi


def _gross_half_max(counts: np.ndarray, rl: int, rh: int) -> tuple[int, int]:
    imax = rl + int(np.argmax(counts[rl:rh + 1]))
    half = counts[imax] / 2.0
    a = imax
    while a > rl and counts[a] >= half:
        a -= 1
    b = imax
    while b < rh and counts[b] >= half:
        b += 1
    return a, b


def analyze_rois(counts: Sequence[float], rois: Sequence[tuple[int, int]],
                 props: Optional[RoiProperties] = None, live_time: Optional[float] = None,
                 end_points: Optional[Sequence[tuple[int, int]]] = None) -> list[AptecRoi]:
    """Aptec ROI results for every ``(RL, RH)``; returned in the order given.

    ``end_points`` overrides the computed ``(BL, BH)`` per ROI (e.g. those stored in a file)."""
    props = (props or RoiProperties()).validate()
    y = np.asarray(counts, dtype=float)
    n = len(y)
    norm = [(max(0, min(int(a), int(b))), min(n - 1, max(int(a), int(b)))) for a, b in rois]
    out: list[Optional[AptecRoi]] = [None] * len(norm)
    if end_points is not None:          # stored end points: the ROIs of a group have the same ones
        same: dict = {}
        for i, (a, b) in enumerate(end_points):
            same.setdefault((min(int(a), int(b)), max(int(a), int(b))), []).append(i)
        grouped = list(same.values())
    else:                               # end points that would fall inside the neighbouring ROI
        grouped = groups(norm, gap=lambda h, l: max(end_point_width(props, h, n), end_point_width(props, l, n)) - 1)
    for grp in grouped:
        lo = min(norm[i][0] for i in grp)
        hi = max(norm[i][1] for i in grp)
        if end_points is not None:
            bl = min(min(end_points[i]) for i in grp)
            bh = max(max(end_points[i]) for i in grp)
        else:
            bl = max(0, lo - end_point_width(props, lo, n))
            bh = min(n - 1, hi + end_point_width(props, hi, n))
        inside = np.zeros(n, dtype=bool)
        for i in grp:
            inside[norm[i][0]:norm[i][1] + 1] = True
        inner = [c for c in range(lo, hi + 1) if not inside[c]]
        coeffs = background_coeffs(y, bl, lo, hi, bh, int(props.bkg_degree), inner)
        for i in grp:
            out[i] = _one(y, norm[i][0], norm[i][1], bl, bh, lo, hi, coeffs, props, live_time, len(grp) > 1)
    return out  # type: ignore[return-value]


def _one(y, rl, rh, bl, bh, lo, hi, coeffs, props, live_time, grouped) -> AptecRoi:
    ch = np.arange(rl, rh + 1)
    bkg_ch = np.polynomial.polynomial.polyval(ch, coeffs)
    gross = float(y[rl:rh + 1].sum())
    background = float(bkg_ch.sum())
    net_total = gross - background
    err = math.sqrt(max(gross + background, 0.0)) / abs(net_total) * 100.0 if net_total else None
    net = y - np.polynomial.polynomial.polyval(np.arange(len(y)), coeffs)
    flags = ""
    if rh - rl < 2:
        cen = float(rl + rh) / 2.0
        hm = tm = (float(rl), float(rh))
        fwhm = fwtm = None
    else:
        imax = rl + int(np.argmax(net[rl:rh + 1]))
        peak = net[imax]
        if peak <= 0:
            hm = tm = (float(rh), float(rl))
            ok_h = ok_t = False
        else:
            *hm, ok_h = _crossing(net, rl, rh, imax, peak / 2.0)
            *tm, ok_t = _crossing(net, rl, rh, imax, peak / 10.0)
        hm, tm = tuple(hm), tuple(tm)
        fwhm = hm[1] - hm[0] if ok_h else None
        fwtm = tm[1] - tm[0] if ok_t else None
        if props.centroid_range == "ghm":
            a, b = _gross_half_max(y, rl, rh)
        elif props.centroid_range == "all":
            a, b = rl, rh
        else:
            pts = hm if props.centroid_range == "fwhm" else tm
            a, b = int(round(min(pts))), int(round(max(pts)))
        a, b = max(a, rl), min(b, rh)
        x = np.arange(a, b + 1)
        v = net[x]
        w = v * np.abs(v) if props.centroid_weight == "squared" else v
        cen = float((w * x).sum() / w.sum()) if w.sum() != 0 else None
    net_cps = mda = None
    if live_time and live_time > 0:
        net_cps = net_total / live_time
        k = float(props.mda_sigma)
        mda = (k * k + 2.0 * k * math.sqrt(2.0 * max(background, 0.0))) / live_time
        if net_cps < mda:
            flags += "?"
    return AptecRoi(rl, rh, bl, bh, lo, hi, list(coeffs), gross, background, net_total, err, cen,
                    (float(hm[0]), float(hm[1])), (float(tm[0]), float(tm[1])), fwhm, fwtm, live_time,
                    mda, net_cps, flags, grouped)


def read_aptec_rois(data) -> list[tuple[int, int, int, int]]:
    """``(BL, RL, RH, BH)`` of the ROIs stored in an Aptec ``.S0`` file (bytes or path), from the
    published Version 6.3 layout: header 1024 B, efficiency records 130 B, energy and resolution
    points 8 B each, then ROI records 256 B.  Channels are as stored (indices into the counts)."""
    import struct
    from pathlib import Path
    d = Path(data).read_bytes() if not isinstance(data, (bytes, bytearray)) else bytes(data)
    if len(d) < 1024 or not d[:7].startswith(b"VERSION"):
        raise ValueError("not an Aptec Version 6.x spectrum file")
    i16 = lambda o: struct.unpack_from("<h", d, o)[0]          # noqa: E731
    n_eff, n_en, n_res, n_roi = i16(330), i16(618), i16(694), i16(782)
    o = 1024 + 130 * max(n_eff, 0) + 8 * max(n_en, 0) + 8 * max(n_res, 0)
    out = []
    for k in range(max(n_roi, 0)):
        if o + 256 * (k + 1) > len(d):
            break
        bl, rl, rh, bh = struct.unpack_from("<4h", d, o + 256 * k)
        out.append((int(bl), int(rl), int(rh), int(bh)))
    return out


# Aptec's flag letters and meanings (S_List / S_CSV "Activity Flags")
FLAGS = ("b", "m", "s", "*", "<", "?", ">")
FLAG_TEXT = {
    "b": "Background subtracted",
    "m": "Fitted peak (MultiFit)",
    "s": "Fitted singlet",
    "*": "MDA ROI assigned by peak identification",
    "<": "MDA activity (listing only)",
    "?": "Activity shown is less than the MDA value",
    ">": "Half life is too great, activity overflow occurred when back decay corrected",
}


__all__ = ["RoiProperties", "AptecRoi", "analyze_rois", "background_coeffs", "groups", "end_point_width",
           "CENTROID_RANGES", "CENTROID_WEIGHTS", "FLAGS", "read_aptec_rois", "FLAG_TEXT", "MAX_END_POINTS"]

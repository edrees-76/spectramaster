"""Manual peak refits (Release B, increment B3).  No Qt.

The user chooses the region and the peak positions; the fit is the engine's own model
(Gaussians with a shared width scale, linear background, optional erfc step, Poisson
weights) with the engine's resolution model for the spectrum, so a manual result differs
from the automatic one only by the user's choices, which are recorded with it.

* :func:`refit_region` -- fit channels ``lo..hi`` with peaks at the given channels.
  Options: ``width="free"`` (scale fitted within x0.5..x2 of the resolution model),
  ``"model"`` (held at the model) or a number (held at that multiple of the model);
  ``fix_centroids`` (hold chosen centroids); ``step`` (peak-related step background).
  Every requested component is reported, also when it is not significant: removing a
  component is the user's decision, and its significance is shown.
* :func:`compare_peaks` -- before/after table of two peak lists (dicts or Peak objects).

The session layer (:mod:`spectramaster.lab.session`) records refits as undoable edits and
marks dependent results (identification, activity) as requiring an update.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass, field
from typing import Optional, Sequence, Union

import numpy as np

from . import Peak
from .peaks import F2S, FitGroup, FitReport, _fit_group, _make_peak, _Model, _record_group, width_model

MANUAL_NOTE = "manual fit"
WIDTH_BOUNDS_FREE = (0.5, 2.0)


@dataclass
class RegionFit:
    peaks: list                     # Peak, sorted by centroid
    group: Optional[FitGroup]       # data, components, background, residuals, warnings
    options: dict = field(default_factory=dict)   # everything needed to repeat the fit

    @property
    def ok(self) -> bool:
        return self.group is not None


def counts_sha256(spectrum) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.asarray(spectrum.counts, dtype=float)).tobytes()).hexdigest()


def refit_region(spectrum, lo: int, hi: int, centroids: Sequence[float],
                 width: Union[str, float] = "free", step: bool = True,
                 fix_centroids: Optional[Sequence[bool]] = None, min_sig: float = 3.0) -> RegionFit:
    """Fit absolute channels ``lo..hi`` with peaks starting at ``centroids`` (absolute channels).

    `min_sig` only labels weak components ("below decision threshold" in ``Peak.note``); they
    are still returned.
    """
    y = np.maximum(np.asarray(spectrum.counts, dtype=float), 0.0)
    n = len(y)
    f0 = spectrum.first_channel
    lo_i, hi_i = int(max(min(lo, hi) - f0, 0)), int(min(max(lo, hi) - f0, n - 1))
    cents = sorted(float(c) - f0 for c in centroids)
    if not cents:
        raise ValueError("at least one peak position is required")
    if any(not lo_i <= c <= hi_i for c in cents):
        raise ValueError("every peak position must lie inside the fit region")
    if hi_i - lo_i + 1 < 5 + 2 * len(cents):
        raise ValueError("the fit region is too narrow for the number of peaks")
    fix = list(fix_centroids) if fix_centroids is not None else [False] * len(cents)
    if len(fix) != len(cents):
        raise ValueError("fix_centroids must have one entry per peak")
    f, src, _start = width_model(spectrum, y)
    if width == "free":
        model, free, bounds = _Model(f), True, WIDTH_BOUNDS_FREE
    elif width == "model":
        model, free, bounds = _Model(f), False, (1.0, 1.0)
    else:
        k = float(width)
        if not 0.2 <= k <= 5.0:
            raise ValueError("a fixed width scale must lie between 0.2 and 5")
        model, free, bounds = _Model(f * k), False, (1.0, 1.0)
    options = {"lo": int(lo_i + f0), "hi": int(hi_i + f0), "centroids": [c + f0 for c in cents],
               "width": width, "step": bool(step), "fix_centroids": fix, "fwhm_model": src,
               "counts_sha256": counts_sha256(spectrum)}
    r = _fit_group(y, model, cents, lo_i, hi_i, free_width=free, step=step, width_bounds=bounds,
                   fix_centroids=fix)
    if r is None:
        return RegionFit([], None, options)
    peaks = []
    kept, reasons = {}, {}
    for j in range(len(r.centroids)):
        c, fw = float(r.centroids[j]), float(r.fwhms[j])
        area, unc = float(r.areas[j]), max(float(r.area_unc[j]), 1.0)
        roi_l = int(max(math.floor(c - 1.25 * fw), 0))
        roi_r = int(min(math.ceil(c + 1.25 * fw), n - 1))
        xr = np.arange(roi_l, roi_r + 1)
        gross = float(y[roi_l:roi_r + 1].sum())
        bkg = float(np.maximum(r.bkg(xr), 0).sum())
        # same Poisson floor as the automatic search, so manual and automatic areas compare
        unc = max(unc, math.sqrt(max(area, 0) + 2.0 * bkg) * 0.7)
        sig = area / unc
        p = _make_peak(spectrum, c, float(r.cent_unc[j]), fw, area, unc, gross, bkg, roi_l, roi_r, sig,
                       len(r.centroids))
        p.note = MANUAL_NOTE + ("; below decision threshold" if sig < min_sig else "")
        peaks.append(p)
        kept[j] = True
        if sig < min_sig:
            reasons[j] = f"kept by the user; significance {sig:.1f} < {min_sig:g}"
    rep = FitReport(fwhm_source=src)
    _record_group(rep, spectrum, y, r, "manual", kept, reasons)
    return RegionFit(sorted(peaks, key=lambda p: p.centroid), rep.groups[0], options)


def region_around(peaks: Sequence, channel: float, fwhm: float) -> tuple[int, int, list[float]]:
    """Fit region and existing peak positions to refit when a peak is added at `channel`:
    the peaks within 3 FWHM (chained) of it, plus 2.2 FWHM margin, as the engine groups them."""
    cs = sorted(_centroid(p) for p in peaks)
    group = [channel]
    changed = True
    while changed:
        changed = False
        for c in cs:
            if c not in group and any(abs(c - g) < 3.0 * fwhm for g in group):
                group.append(c)
                changed = True
    others = sorted(c for c in group if c != channel)
    lo = int(math.floor(min(group) - 2.2 * fwhm))
    hi = int(math.ceil(max(group) + 2.2 * fwhm))
    return lo, hi, others


def _centroid(p) -> float:
    return float(p["centroid"] if isinstance(p, dict) else p.centroid)


def _get(p, k):
    return p.get(k) if isinstance(p, dict) else getattr(p, k, None)


def compare_peaks(before: Sequence, after: Sequence, tol_fwhm: float = 0.5) -> list[dict]:
    """Rows {status, centroid_before, centroid_after, area_before, area_after, d_area, d_area_sigma}
    pairing peaks whose centroids agree within `tol_fwhm`; status 'changed'/'unchanged'/'added'/
    'removed'."""
    rows, used = [], set()
    for b in sorted(before, key=_centroid):
        best, bd = None, None
        for j, a in enumerate(after):
            if j in used:
                continue
            d = abs(_centroid(a) - _centroid(b))
            if d <= tol_fwhm * max(_get(b, "fwhm") or 1.0, 1e-9) and (bd is None or d < bd):
                best, bd = j, d
        if best is None:
            rows.append({"status": "removed", "centroid_before": _centroid(b), "centroid_after": None,
                         "area_before": _get(b, "net_area"), "area_after": None, "d_area": None,
                         "d_area_sigma": None})
            continue
        used.add(best)
        a = after[best]
        ab, aa = float(_get(b, "net_area")), float(_get(a, "net_area"))
        s = math.hypot(float(_get(b, "net_area_unc") or 0), float(_get(a, "net_area_unc") or 0))
        same = abs(aa - ab) <= 1e-9 * max(abs(ab), 1.0) and abs(_centroid(a) - _centroid(b)) < 1e-9
        rows.append({"status": "unchanged" if same else "changed", "centroid_before": _centroid(b),
                     "centroid_after": _centroid(a), "area_before": ab, "area_after": aa, "d_area": aa - ab,
                     "d_area_sigma": (aa - ab) / s if s > 0 else None})
    for j, a in enumerate(after):
        if j not in used:
            rows.append({"status": "added", "centroid_before": None, "centroid_after": _centroid(a),
                         "area_before": None, "area_after": _get(a, "net_area"), "d_area": None,
                         "d_area_sigma": None})
    return sorted(rows, key=lambda r: r["centroid_after"] if r["centroid_after"] is not None else r["centroid_before"])


__all__ = ["RegionFit", "refit_region", "region_around", "compare_peaks", "counts_sha256", "MANUAL_NOTE"]

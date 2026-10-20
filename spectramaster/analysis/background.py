"""Measured laboratory background (Release C, increment C1).  No Qt.

Two ways of removing a measured background spectrum B (live time t_b) from a sample S
(live time t_s), k = t_s / t_b (live-time normalisation; no uncertainty on k, the live
times are taken as exact):

* **peak by peak** (:class:`BackgroundFitter`): the sample's own fit of each group of
  peaks (region, centroids, widths, step height, continuum shape and weights) defines a
  linear estimator L of the peak amplitudes and continuum.  At the fitted non-linear
  parameters the sample areas are exactly ``L S``; the same L applied to the background
  counts on the sample's channel grid gives ``N_b = L B`` with ``var(N_b) = L diag(B) L^T``.
  Each sample peak gets ``N = N_s - k N_b`` and ``u^2 = u_s^2 + k^2 var(N_b)``.  Because the
  same operator acts on both spectra, ``N_s - k N_b = L (S - k B)``: whatever share of an
  unresolved neighbour (NaI: Bi-214 609 keV next to a Cs-137 contamination at 662 keV) the
  model attributes to a peak is attributed identically in the background and cancels.
  Independent peak searches in the two spectra, matched by energy, do not have that
  property.  Background areas are never clipped at zero.  Lines without a sample peak get
  the same estimator built for a peak at the expected energy and width
  (:meth:`BackgroundFitter.at_energy`, used for detection limits).
* **full spectrum** (:func:`net_spectrum`): ``S - k B`` channel by channel (energy-aligned
  if the calibrations differ, counts conserved by :func:`tools.arithmetic.align_to`) with
  the per-channel variance ``S + k^2 B``.  The net counts are not Poisson: the peak search
  and fit use that variance explicitly (``find_peaks(..., variance=...)``) and negative net
  channels are kept.  Approximation: re-binning an energy-misaligned background correlates
  neighbouring channels; that correlation is ignored (channels treated as independent).

A spectrum whose ``extra["operation"]`` says it is already background subtracted cannot be
subtracted again (:func:`check_not_subtracted`).
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

import numpy as np

SUBTRACTED = "background subtracted"
GROUP_GAP_FWHM = 3.5          # same grouping as the automatic search (peaks.find_peaks)
REGION_MARGIN_FWHM = 2.2


def check_not_subtracted(spectrum) -> None:
    """Refuse a second background subtraction."""
    if (getattr(spectrum, "extra", None) or {}).get("operation") == SUBTRACTED:
        src = spectrum.extra.get("background_source", "?")
        raise ValueError(f"the spectrum is already background subtracted (background: {src}); "
                         "subtracting a background again would remove it twice")


BACKGROUND_AGE_DAYS = 180         # older backgrounds are reported (shielding/radon conditions change)


def compatibility(sample, background) -> list[str]:
    """Warnings about using `background` for `sample` (reported, never fixed silently)."""
    from ..tools.arithmetic import same_calibration
    out = []
    ds, db = (sample.detector or "").strip(), (background.detector or "").strip()
    if ds and db and ds.lower() != db.lower():
        out.append(f"background measured with a different detector ('{db}' vs '{ds}')")
    if not same_calibration(sample, background):
        out.append("background has a different channel layout or energy calibration: it is re-binned "
                   "to the sample energies")
    if sample.live_time and background.live_time and background.live_time < sample.live_time:
        out.append(f"background live time ({background.live_time:g} s) is shorter than the sample's "
                   f"({sample.live_time:g} s): its counting uncertainty is amplified (k = "
                   f"{sample.live_time / background.live_time:.3g})")
    if sample.start_time and background.start_time:
        days = abs((sample.start_time - background.start_time).total_seconds()) / 86400.0
        if days > BACKGROUND_AGE_DAYS:
            out.append(f"background measured {days:.0f} days apart from the sample")
    elif not background.start_time:
        out.append("background acquisition date unknown")
    return out


def live_time_ratio(sample, background) -> float:
    if not sample.live_time or not background.live_time:
        raise ValueError("live time missing for the sample or the background spectrum")
    return float(sample.live_time) / float(background.live_time)


def net_spectrum(sample, background, scale: Optional[float] = None):
    """(net spectrum, per-channel variance S + k^2 B, k).  Negative channels are kept."""
    from ..tools.arithmetic import subtract_background
    check_not_subtracted(sample)
    net, sigma = subtract_background(sample, background, scale=scale)
    k = float(net.extra["background_scale"])
    return net, np.asarray(sigma, dtype=float) ** 2, k


class BackgroundFitter:
    """Background areas under sample peaks with the sample fit's own linear estimator."""

    def __init__(self, sample, background, scale: Optional[float] = None):
        from ..tools.arithmetic import align_to, same_calibration
        check_not_subtracted(sample)
        self.note = ""
        if not same_calibration(sample, background):
            if not sample.energy_coeffs or not background.energy_coeffs:
                raise ValueError("the sample and background spectra have different channel layouts and "
                                 "cannot be aligned without energy calibrations")
            background = align_to(background, sample)
            self.note = ("background re-binned to the sample energy grid (counts conserved; the "
                         "correlation between neighbouring re-binned channels is ignored)")
        self.k = float(scale) if scale is not None else live_time_ratio(sample, background)
        self.f0 = sample.first_channel
        self.s = np.asarray(sample.counts, dtype=float)
        self.b = np.maximum(np.asarray(background.counts, dtype=float), 0.0)

    def _apply(self, lo: int, hi: int, cents, sigmas, step_h: float = 0.0, cont=None, w2=None, tails=None):
        """Linear estimator of the amplitudes for components at `cents` (index channels) with
        Gaussian `sigmas` on lo..hi; returns [(k*N_b, k*u_b)] or None.  `cont` (continuum
        columns) and `w2` (weights) default to a straight line and 1/max(S, 1); the sample's
        FitReport supplies the fit's own ones (log-linear continuum, model weights, peak tail)."""
        from .peaks import SQRT2PI, erfc, peak_shape
        n = len(self.s)
        lo, hi = max(int(lo), 0), min(int(hi), n - 1)
        if hi - lo + 1 < 3 + len(cents):
            return None
        x = np.arange(lo, hi + 1, dtype=float)
        xm = 0.5 * (x[0] + x[-1])
        if cont is not None and cont.shape[1] != len(x):
            cont = w2 = None
        cols = list(cont) if cont is not None else [np.ones_like(x), x - xm]
        nc = len(cols)
        for j, (c, sg) in enumerate(zip(cents, sigmas)):
            col = peak_shape((x - c) / sg, tails[j] if tails else None)
            if step_h:
                col = col + step_h * 0.5 * erfc((x - c) / (sg * math.sqrt(2.0)))
            cols.append(col)
        X = np.vstack(cols).T
        w = w2 if w2 is not None else 1.0 / np.maximum(self.s[lo:hi + 1], 1.0)
        try:
            L = np.linalg.solve(X.T @ (X * w[:, None]), (X * w[:, None]).T)   # (p, m)
        except np.linalg.LinAlgError:
            return None
        bb = self.b[lo:hi + 1]
        amp = L @ bb
        var = (L * L) @ bb
        out = []
        for j, sg in enumerate(sigmas):
            a = sg * SQRT2PI
            out.append((self.k * a * float(amp[nc + j]), self.k * a * math.sqrt(max(float(var[nc + j]), 0.0))))
        return out

    # ------------------------------------------------------------ public API
    def under_peaks(self, peaks, report=None) -> dict:
        """{id(peak): (k*N_b, k*u_b)}.  With the sample's FitReport (find_peaks(report=...)) the
        estimator is exactly the sample fit's; otherwise it is rebuilt from the peaks (grouped
        as the search groups them, no step), which is close but not identical."""
        from .peaks import F2S
        out = {}
        todo = list(peaks)
        if report is not None:
            for g in report.groups:
                comps = g.components
                if not comps:
                    continue
                cents = [c.centroid - self.f0 for c in comps]
                res = self._apply(g.lo - self.f0, g.hi - self.f0, cents, [c.fwhm * F2S for c in comps],
                                  g.step_height, g.continuum_columns, g.weights, [c.tail for c in comps])
                if res is None:
                    continue
                for c, r in zip(comps, res):
                    for p in todo:
                        if c.kept and abs(p.centroid - c.centroid) < 1e-6 and id(p) not in out:
                            out[id(p)] = r
            todo = [p for p in todo if id(p) not in out]
        todo.sort(key=lambda p: p.centroid)
        groups: list[list] = []
        for p in todo:
            if groups and p.centroid - groups[-1][-1].centroid < GROUP_GAP_FWHM * max(p.fwhm,
                                                                                   groups[-1][-1].fwhm):
                groups[-1].append(p)
            else:
                groups.append([p])
        for g in groups:
            lo = math.floor(g[0].centroid - self.f0 - REGION_MARGIN_FWHM * g[0].fwhm)
            hi = math.ceil(g[-1].centroid - self.f0 + REGION_MARGIN_FWHM * g[-1].fwhm)
            res = self._apply(lo, hi, [p.centroid - self.f0 for p in g], [p.fwhm * F2S for p in g])
            if res is not None:
                for p, r in zip(g, res):
                    out[id(p)] = r
        return out

    def at_energy(self, index: float, fwhm_ch: float) -> Optional[tuple[float, float]]:
        """(k*N_b, k*u_b) for a peak at channel index `index` (0-based) of width `fwhm_ch`
        where the sample has no peak (detection limits)."""
        from .peaks import F2S
        if not fwhm_ch or fwhm_ch <= 0:
            return None
        res = self._apply(math.floor(index - REGION_MARGIN_FWHM * fwhm_ch),
                          math.ceil(index + REGION_MARGIN_FWHM * fwhm_ch), [index], [fwhm_ch * F2S])
        return res[0] if res else None


__all__ = ["BackgroundFitter", "net_spectrum", "compatibility", "check_not_subtracted", "live_time_ratio", "SUBTRACTED"]

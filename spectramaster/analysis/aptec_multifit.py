"""Aptec-style MultiFit (Analyze > Multifit, ``M``): decomposition of an ROI into Gaussian peaks
by Marquardt-Levenberg non-linear least squares.  Pure functions, no GUI.

What the Aptec help documents and is followed here:

* Gaussian peaks; the peak width is fixed from the resolution calibration (default) or varies
  (one common scale factor); it is always allowed to vary when 511 keV lies in the region.
* Background fixed (the ROI background from its end points, default) or varying (the ROI
  background polynomial fitted with the peaks).
* An ROI is a multiplet when its peak is wider than the resolution calibration expects (we
  also count an ROI with several significant centroid guesses);
  "Multiplets only" fits only those, "Multiplets and singlets" fits all.
* First centroid guesses: negative-to-positive crossings of the third derivative ("Overlapped
  close peaks") or maxima of the net counts ("Separated overlaps").
* Peaks are kept when their amplitude is at least K times its standard uncertainty
  (default K = 1.645); at most *Maximum Overlaps* peaks are fitted together.
* Stops after *Max Iterations*, when chi-square changes by less than *Percent Change*, or when the
  reduced chi-square reaches *Min Reduced Chi Square*.
* Without a resolution calibration Aptec makes one from the ROIs (auto resolution calibration,
  polynomial degree 1): :func:`auto_resolution`.

Our choices (not documented): weights 1 / max(counts, 1); a peak is "wider than expected" when
its FWHM is more than 20 % above the calibration (or was not found); the third derivative is
taken from the net counts smoothed with a Gaussian of 0.7 sigma.  With a fixed background the
reported area uncertainty includes the uncertainty of the background line through its end
points (propagated through the fit), which Aptec's help does not mention.

No Aptec file available to us contains a MultiFit result, so this fit is validated on synthetic
spectra (``docs/baseline/aptec_multifit_protocol.md``), not against Aptec.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import numpy as np

__all__ = ["MultifitSetup", "Component", "MultifitResult", "multifit_roi", "auto_resolution", "WIDER_THAN_EXPECTED"]

SQRT2PI = math.sqrt(2.0 * math.pi)
FWHM_PER_SIGMA = 2.0 * math.sqrt(2.0 * math.log(2.0))
WIDER_THAN_EXPECTED = 1.2


@dataclass
class MultifitSetup:
    """Aptec *Multifit Fitting Parameters* (Shift+M)."""
    detector: str = "hpge"              # "hpge" or "nai" (NaI: at most 512 channels)
    centroid_search: str = "overlapped"  # "overlapped" (close peaks) or "separated"
    fit_singlets: bool = True           # multiplets and singlets (else multiplets only)
    k_sigma: float = 1.645
    width_fixed: bool = True
    background_fixed: bool = True
    max_iterations: int = 20
    percent_change: float = 0.5
    min_reduced_chi2: float = 1.0
    max_overlaps: int = 8

    def validate(self) -> "MultifitSetup":
        if self.detector not in ("hpge", "nai") or self.centroid_search not in ("overlapped", "separated"):
            raise ValueError("unknown detector or centroid search")
        if not 0 < float(self.k_sigma) <= 10 or not 1 <= int(self.max_iterations) <= 1000:
            raise ValueError("K sigma or iterations out of range")
        if not 0 < float(self.percent_change) <= 100 or float(self.min_reduced_chi2) < 0:
            raise ValueError("percent change / reduced chi-square out of range")
        if not 1 <= int(self.max_overlaps) <= 32:
            raise ValueError("maximum overlaps must be 1..32")
        return self

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "MultifitSetup":
        known = set(cls.__dataclass_fields__)
        try:
            return cls(**{k: v for k, v in (d or {}).items() if k in known}).validate()
        except (ValueError, TypeError):
            return cls()


@dataclass
class Component:
    centroid: float                     # index into the counts (fractional)
    centroid_unc: float
    fwhm: float                         # channels
    amplitude: float                    # counts at the centroid
    area: float
    area_unc: float                     # 1 sigma (statistics; + fixed background line)


@dataclass
class MultifitResult:
    rl: int
    rh: int
    components: list[Component]
    background: list[float]             # polynomial in the index (as fitted or fixed)
    reduced_chi2: float
    iterations: int
    multiplet: bool
    width_scale: float = 1.0
    note: str = ""
    fitted: bool = True

    def model(self, x) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        out = np.polynomial.polynomial.polyval(x, self.background) if self.background else np.zeros_like(x)
        for c in self.components:
            s = c.fwhm / FWHM_PER_SIGMA
            out = out + c.amplitude * np.exp(-0.5 * ((x - c.centroid) / s) ** 2)
        return out


def auto_resolution(centroids: Sequence[float], fwhms: Sequence[Optional[float]]) -> Optional[list[float]]:
    """Linear FWHM(channel) from the ROIs' measured widths (Aptec's auto resolution calibration
    when the spectrum has none); None with fewer than two usable ROIs."""
    pts = [(float(c), float(w)) for c, w in zip(centroids, fwhms) if c is not None and w and w > 0]
    if len(pts) < 2:
        return [pts[0][1]] if pts else None
    x, y = np.array(pts).T
    if np.ptp(x) == 0:
        return [float(np.median(y))]
    c = np.polynomial.polynomial.polyfit(x, y, 1)
    return [float(v) for v in c]


def _smooth_gauss(v: np.ndarray, s: float) -> np.ndarray:
    h = max(1, int(math.ceil(3 * s)))
    k = np.exp(-0.5 * (np.arange(-h, h + 1) / s) ** 2)
    k /= k.sum()
    return np.convolve(v, k, mode="same") / np.convolve(np.ones_like(v), k, mode="same")


def _guesses(x: np.ndarray, net: np.ndarray, var: np.ndarray, sigma: float, setup: MultifitSetup) -> list[float]:
    n = len(x)
    if n < 3:
        return [float(x[int(np.argmax(net))])]
    sm = _smooth_gauss(net, max(0.7 * sigma, 0.5))
    noise = np.sqrt(np.maximum(var, 1.0))
    cands: list[tuple[float, float]] = []
    if setup.centroid_search == "overlapped" and n >= 7:
        d3 = np.gradient(np.gradient(np.gradient(sm)))
        for i in range(n - 1):
            if d3[i] < 0 <= d3[i + 1]:
                xc = x[i] + (-d3[i]) / (d3[i + 1] - d3[i])
                j = min(max(int(round(xc - x[0])), 0), n - 1)
                cands.append((float(xc), float(sm[j] / noise[j])))
    else:
        for i in range(1, n - 1):
            if sm[i] > sm[i - 1] and sm[i] >= sm[i + 1]:
                cands.append((float(x[i]), float(sm[i] / noise[i])))
    cands = [c for c in cands if c[1] >= setup.k_sigma]
    if not cands:
        i = int(np.argmax(sm))
        return [float(x[i])]
    cands.sort(key=lambda c: -c[1])
    return sorted(c[0] for c in cands[: int(setup.max_overlaps)])


def _bkg_design(x: np.ndarray, degree: int) -> np.ndarray:
    return np.vander(x, degree + 1, increasing=True)


def multifit_roi(counts: Sequence[float], rl: int, rh: int, bkg_coeffs: Sequence[float],
                 fwhm_of: Callable[[float], float], setup: Optional[MultifitSetup] = None,
                 measured_fwhm: Optional[float] = None, end_points: Sequence[int] = (),
                 energy_of: Optional[Callable[[float], Optional[float]]] = None) -> MultifitResult:
    """Fit the ROI ``rl..rh`` (indices) with Gaussians over its background.

    ``bkg_coeffs``: ROI background polynomial in the index (from the ROI end points);
    ``fwhm_of(index)``: expected FWHM in channels (resolution calibration);
    ``measured_fwhm``: the ROI's FWHM in channels (None if not found) -- multiplet test;
    ``end_points``: the end-point channels the background was fitted to (for its uncertainty);
    ``energy_of(index)``: keV, to force a varying width when 511 keV is in the region."""
    setup = (setup or MultifitSetup()).validate()
    y_all = np.asarray(counts, dtype=float)
    rl, rh = int(rl), int(rh)
    x = np.arange(rl, rh + 1, dtype=float)
    y = y_all[rl:rh + 1]
    centre = 0.5 * (rl + rh)
    sig0 = max(float(fwhm_of(centre)), 0.5) / FWHM_PER_SIGMA
    expected = sig0 * FWHM_PER_SIGMA
    multiplet = measured_fwhm is None or measured_fwhm > WIDER_THAN_EXPECTED * expected
    coeffs = [float(c) for c in bkg_coeffs] or [0.0]
    deg = len(coeffs) - 1
    width_free = not setup.width_fixed
    if energy_of is not None:
        ea, eb = energy_of(rl), energy_of(rh)
        if ea is not None and eb is not None and min(ea, eb) <= 511.0 <= max(ea, eb):
            width_free = True                   # Aptec: varying width when 511 keV is fitted
    bkg_free = not setup.background_fixed
    B = _bkg_design(x, deg)
    bkg = B @ np.asarray(coeffs)
    w = 1.0 / np.maximum(y, 1.0)
    cents = _guesses(x, y - bkg, np.maximum(y, 1.0), sig0, setup)
    multiplet = multiplet or len(cents) > 1     # several significant centroids in the ROI
    if not multiplet and not setup.fit_singlets:
        return MultifitResult(rl, rh, [], coeffs, float("nan"), 0, False, note="singlet not fitted", fitted=False)

    def fit(cents: list[float]):
        k = len(cents)
        sg = np.array([max(float(fwhm_of(c)), 0.5) / FWHM_PER_SIGMA for c in cents])
        amp = [max(float(np.interp(c, x, y - bkg)), 1.0) for c in cents]
        p = np.array([v for pair in zip(amp, cents) for v in pair] + ([1.0] if width_free else [])
                     + (list(coeffs) if bkg_free else []), dtype=float)

        def unpack(p):
            a = p[0:2 * k:2]
            c = p[1:2 * k:2]
            s = p[2 * k] if width_free else 1.0
            b = p[2 * k + (1 if width_free else 0):] if bkg_free else np.asarray(coeffs)
            return a, c, s, b

        def model_jac(p):
            a, c, s, b = unpack(p)
            m = B @ b
            J = np.zeros((len(x), len(p)))
            ds = np.zeros(len(x))
            for i in range(k):
                si = sg[i] * s
                u = (x - c[i]) / si
                g = np.exp(-0.5 * u * u)
                m = m + a[i] * g
                J[:, 2 * i] = g
                J[:, 2 * i + 1] = a[i] * g * u / si
                ds += a[i] * g * u * u / s
            col = 2 * k
            if width_free:
                J[:, col] = ds
                col += 1
            if bkg_free:
                J[:, col:col + deg + 1] = B
            return m, J

        lam = 1e-3
        m, J = model_jac(p)
        chi2 = float(np.sum(w * (y - m) ** 2))
        dof = max(len(x) - len(p), 1)
        it = 0
        for it in range(1, int(setup.max_iterations) + 1):
            JTW = J.T * w
            A = JTW @ J
            g = JTW @ (y - m)
            improved = False
            for _ in range(10):
                M = A + lam * np.diag(np.diag(A) + 1e-12)
                try:
                    step = np.linalg.solve(M, g)
                except np.linalg.LinAlgError:
                    lam *= 10
                    continue
                q = p + step
                q[0:2 * k:2] = np.maximum(q[0:2 * k:2], 0.0)
                q[1:2 * k:2] = np.clip(q[1:2 * k:2], rl, rh)
                if width_free:
                    q[2 * k] = min(max(q[2 * k], 0.5), 2.0)
                m2, J2 = model_jac(q)
                c2 = float(np.sum(w * (y - m2) ** 2))
                if c2 <= chi2:
                    change = (chi2 - c2) / max(chi2, 1e-300) * 100.0
                    p, m, J, chi2 = q, m2, J2, c2
                    lam = max(lam / 10.0, 1e-9)
                    improved = True
                    break
                lam *= 10.0
            if not improved or change < float(setup.percent_change) or chi2 / dof <= float(setup.min_reduced_chi2):
                break
        A = (J.T * w) @ J
        try:
            cov = np.linalg.inv(A)
        except np.linalg.LinAlgError:
            cov = np.linalg.pinv(A)
        if not bkg_free and len(end_points) > deg:
            # uncertainty of the fixed background line, propagated through the fit
            ep = np.asarray(end_points, dtype=int)
            ye = np.maximum(y_all[ep], 1.0)
            Be = _bkg_design(ep.astype(float), deg)
            try:
                cov_b = np.linalg.inv((Be.T / ye) @ Be)
                Mb = -cov @ ((J.T * w) @ B)
                cov = cov + Mb @ cov_b @ Mb.T
            except np.linalg.LinAlgError:
                pass
        return p, cov, chi2 / dof, it, sg, unpack

    while True:
        if not cents:
            return MultifitResult(rl, rh, [], coeffs, float("nan"), 0, multiplet, note="no peak found", fitted=False)
        p, cov, red, it, sg, unpack = fit(cents)
        k = len(cents)
        a, c, s, b = unpack(p)
        sa = np.sqrt(np.maximum(np.diag(cov)[0:2 * k:2], 0.0))
        weak = [i for i in range(k) if a[i] < float(setup.k_sigma) * sa[i]]
        if not weak or k == 1:
            break
        drop = min(weak, key=lambda i: a[i] / max(sa[i], 1e-300))
        cents = [float(c[i]) for i in range(k) if i != drop]
    comps = []
    for i in range(k):
        si = sg[i] * s
        area = a[i] * si * SQRT2PI
        # d(area) / d(a_i, s) -> variance
        gi = np.zeros(len(p))
        gi[2 * i] = si * SQRT2PI
        if width_free:
            gi[2 * k] = a[i] * sg[i] * SQRT2PI
        var = float(gi @ cov @ gi)
        comps.append(Component(float(c[i]), float(math.sqrt(max(cov[2 * i + 1, 2 * i + 1], 0.0))),
                               float(si * FWHM_PER_SIGMA), float(a[i]), float(area), float(math.sqrt(max(var, 0.0)))))
    comps.sort(key=lambda q: q.centroid)
    return MultifitResult(rl, rh, comps, [float(v) for v in b], float(red), int(it), multiplet, float(s))

"""Automatic peak search and fitting for gamma spectra (NaI ... HPGe).

Algorithm
---------
1. **Resolution model** FWHM(channel): from ``Spectrum.fwhm_coeffs`` (keV) when present,
   otherwise from the energy calibration plus a detector-type guess (metadata text, else the
   type whose typical resolution matches the strongest isolated peaks, else channel count and
   keV/channel), otherwise estimated from the data (strong peaks
   fitted with a free width).  In every case the model is then rescaled to the widths of
   the strongest isolated peaks actually present (robust median, clamped to x0.5..x2).
2. **Search**: matched filter = zero-area Gaussian ("smoothed second difference",
   Mariscotti 1967 / Robinson) whose width follows the FWHM model (the spectrum is cut into
   bands with ~15 % FWHM variation, one kernel per band).  Significance of the filter
   response S/sqrt(var S) assuming Poisson channels.  Local maxima above ``min_sig``.
3. **Fit**: neighbouring peaks (< 3.5 FWHM apart) are fitted together (multiplet) with
   Gaussians + linear background + a small erfc step, all widths tied to the FWHM model
   with one free scale factor per group (scipy.optimize.least_squares, Poisson weights).
   A single-peak fit with a significant residual bump is retried as a doublet.
   Near the Compton edge expected for a strong peak (calibrated spectra), the group is also
   fitted with a continuum step (erfc, free height, position and width >= the resolution) and
   that model is kept when it improves the fit significantly; a component that the step
   alone explains is then discarded with that reason, not reported as a peak.
   Net area, centroid and their 1-sigma uncertainties come from the covariance matrix.
   ``find_peaks(..., variance=v)`` replaces the Poisson variance by an explicit per-channel
   variance (e.g. S + k^2 B of a background-subtracted spectrum, which may be negative and is
   not Poisson); the counts are then neither clipped nor floored.
4. **Flags** (``Peak.note``): annihilation (511 keV), single/double escape of a stronger
   high-energy peak, sum peaks of two strong peaks (e.g. Co-60 2505 keV), Pb/X-ray region.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from . import Peak

SQRT2PI = math.sqrt(2.0 * math.pi)
F2S = 1.0 / (2.0 * math.sqrt(2.0 * math.log(2.0)))   # FWHM -> sigma


# ------------------------------------------------------------------ helpers
_ERFC_X = np.linspace(-6.0, 6.0, 4801)


def _erfc_exact(z):
    """Numerical Recipes erfcc (|rel err| < 1.2e-7), vectorised."""
    z = np.asarray(z, dtype=float)
    a = np.abs(z)
    t = 1.0 / (1.0 + 0.5 * a)
    r = t * np.exp(-a * a - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (
        -0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (
            -0.82215223 + t * 0.17087277)))))))))
    return np.where(z >= 0, r, 2.0 - r)


_ERFC_Y = _erfc_exact(_ERFC_X)


def erfc(z):
    """Complementary error function by table interpolation (abs err < 2e-6; no scipy import)."""
    return np.interp(z, _ERFC_X, _ERFC_Y)


def _poly(coeffs, x):
    x = np.asarray(x, dtype=float)
    out = np.zeros_like(x)
    for c in reversed(list(coeffs)):
        out = out * x + c
    return out


def _dpoly(coeffs, x):
    d = [k * c for k, c in enumerate(coeffs)][1:]
    return _poly(d, x) if d else np.zeros_like(np.asarray(x, dtype=float))


def guess_detector(spectrum) -> str:
    """'HPGe', 'NaI', 'LaBr3', 'CZT' or '' (unknown), from metadata, channel count and gain."""
    # the file's own detector-type field first (e.g. N42 <DetectorType>), then free text
    text = " ".join(str(v) for v in ((getattr(spectrum, "extra", None) or {}).get("detector_type", ""),
                                     spectrum.detector, spectrum.sample_id, spectrum.description)).lower()
    for key, det in (("hpge", "HPGe"), ("ge(li)", "HPGe"), ("germanium", "HPGe"), ("nai", "NaI"),
                     ("labr", "LaBr3"), ("czt", "CZT"), ("cdznte", "CZT"),
                     ("cdte", "CZT")):       # CdTe: same room-temperature semiconductor resolution class
        if key in text:
            return det
    n = len(spectrum.counts)
    if not spectrum.energy_coeffs:
        return "HPGe" if n >= 4096 else ("NaI" if n <= 1024 else "")
    # Channel count and gain do not separate HPGe from NaI (a NaI on a 4096-channel MCA at
    # 0.75 keV/ch looks like HPGe), so measured peak widths decide when strong peaks exist.
    det = _cached_width_guess(spectrum)
    if det:
        return det
    ch = spectrum.first_channel + n / 2.0
    gain = abs(float(_dpoly(spectrum.energy_coeffs, ch)))
    if n >= 4096 or gain < 0.75:
        return "HPGe"
    if n <= 1024 or gain > 2.0:
        return "NaI"
    return "LaBr3" if gain > 1.0 else "HPGe"


_WIDTH_GUESS_CACHE: dict = {}


def _cached_width_guess(spectrum) -> str:
    """_guess_from_widths memoised on the counts and calibration (peak search and
    identification both ask for the type of the same spectrum)."""
    import hashlib
    y = np.ascontiguousarray(np.asarray(spectrum.counts, dtype=float))
    key = (hashlib.sha1(y.tobytes(), usedforsecurity=False).hexdigest(), tuple(float(c) for c in spectrum.energy_coeffs),
           int(spectrum.first_channel))
    if key not in _WIDTH_GUESS_CACHE:
        if len(_WIDTH_GUESS_CACHE) >= 64:
            _WIDTH_GUESS_CACHE.clear()
        _WIDTH_GUESS_CACHE[key] = _guess_from_widths(spectrum)
    return _WIDTH_GUESS_CACHE[key]


def _guess_from_widths(spectrum) -> str:
    """Detector type whose typical resolution matches the strong peaks, or ''.

    Each candidate type's default FWHM model is tried: strong peaks found with that model are
    fitted in groups (neighbours within 3.5 FWHM fitted jointly, one free width scale per group,
    bounds x0.5..x2).  A group "matches" when the scale lies within x1/1.5..x1.5, i.e. closer
    to that type than to a neighbouring one (typical resolutions step by ~2.3x:
    HPGe << LaBr3 < NaI).  The type with the most matching groups wins, ties broken by the
    median scale closest to 1.
    """
    y = np.maximum(np.asarray(spectrum.counts, dtype=float), 0.0)
    n = len(y)
    if n < 16 or not np.isfinite(y).all() or y.sum() <= 0:
        return ""
    ch = spectrum.first_channel + np.arange(n, dtype=float)
    gain = np.abs(_dpoly(spectrum.energy_coeffs, ch))
    if not np.all(np.isfinite(gain)) or np.any(gain < 1e-9):
        return ""
    e = _poly(spectrum.energy_coeffs, ch)
    best, best_key = "", None
    for det in ("HPGe", "LaBr3", "NaI"):
        f = np.clip(default_fwhm_kev(e, det) / gain, 1.0, n / 4)
        scales = [k for k in _group_width_scales(y, f, _start_index(y, f)) if 1 / 1.5 <= k <= 1.5]
        if not scales:
            continue
        key = (len(scales), -abs(math.log(float(np.median(scales)))))
        if best_key is None or key > best_key:
            best, best_key = det, key
    return best


def _group_width_scales(y, f, start, max_peaks=8) -> list[float]:
    """Free width scale of each group of strong peaks (fits at a width bound are dropped)."""
    cands = sorted(sorted(_candidates(y, f, 12.0, start), key=lambda c: -c[1])[:max_peaks])
    m = _Model(f)
    groups: list[list[float]] = []
    for c, _z in cands:
        if groups and c - groups[-1][-1] < 3.5 * m.at(c) and len(groups[-1]) < 4:
            groups[-1].append(c)
        else:
            groups.append([c])
    out = []
    for g in groups:
        lo = int(max(g[0] - 2.5 * m.at(g[0]), 0))
        hi = int(min(g[-1] + 2.5 * m.at(g[-1]), len(y) - 1))
        r = _fit_group(y, m, g, lo, hi, free_width=True, step=True, width_bounds=(0.5, 2.0))
        if r is None or r.at_bound or r.chi2r > 20:
            continue
        sig = r.areas / np.maximum(r.area_unc, 1e-12)
        if not np.any((r.area_unc > 0) & (sig >= 10)):
            continue
        out.append(float(r.scale))
    return out


def default_fwhm_kev(energy, detector: str):
    """Typical resolution (keV) of a detector type at `energy` keV."""
    e = np.maximum(np.asarray(energy, dtype=float), 5.0)
    if detector == "NaI":          # 7 % @ 662 keV, ~ sqrt(E)
        return 1.80 * np.sqrt(e) + 0.5
    if detector == "LaBr3":        # 3 % @ 662
        return 0.77 * np.sqrt(e) + 0.3
    if detector == "CZT":          # 2 % @ 662
        return np.sqrt(4.0 + 0.25 * e)
    return np.sqrt(0.75 + 0.00185 * e)   # HPGe 1.0 keV @ 122, 1.8 keV @ 1332


@dataclass
class _Model:
    a: np.ndarray       # FWHM in channels for each index

    def at(self, idx: float) -> float:
        i = int(min(max(round(idx), 0), len(self.a) - 1))
        return float(self.a[i])


def fwhm_model(spectrum, y: np.ndarray) -> tuple[np.ndarray, str]:
    """FWHM (channels) per index, and the source of the model."""
    n = len(y)
    ch = spectrum.first_channel + np.arange(n, dtype=float)
    if spectrum.energy_coeffs:
        gain = np.abs(_dpoly(spectrum.energy_coeffs, ch))
        gain = np.where(gain > 1e-9, gain, np.nan)
        if spectrum.fwhm_coeffs:
            fk = _poly(spectrum.fwhm_coeffs, ch)
            f = fk / gain
            ok = np.isfinite(f) & (f > 0.8) & (f < n / 4)
            if ok.mean() > 0.8:
                f = np.where(ok, f, np.nan)
                return _fill(f), "fwhm calibration"
        det = guess_detector(spectrum)
        e = _poly(spectrum.energy_coeffs, ch)
        f = default_fwhm_kev(e, det or "HPGe") / gain
        f = np.where(np.isfinite(f), f, np.nan)
        return _fill(np.clip(f, 1.0, n / 4)), f"default {det or 'HPGe'} resolution"
    return np.full(n, np.nan), "none"


def _fill(f):
    f = np.asarray(f, dtype=float)
    if np.all(np.isnan(f)):
        return np.full(len(f), 4.0)
    idx = np.arange(len(f))
    ok = ~np.isnan(f)
    return np.interp(idx, idx[ok], f[ok])


# ------------------------------------------------------------------- search
def _kernel(fwhm: float) -> np.ndarray:
    s = max(fwhm * F2S, 0.5)
    m = max(int(math.ceil(1.5 * fwhm)), 2)
    x = np.arange(-m, m + 1, dtype=float)
    g = np.exp(-0.5 * (x / s) ** 2)
    return g - g.mean()


def _filter(y: np.ndarray, f: np.ndarray, var: Optional[np.ndarray] = None) -> tuple[np.ndarray, np.ndarray]:
    """Zero-area-Gaussian response S and its standard deviation, width following f."""
    n = len(y)
    S = np.zeros(n)
    V = np.ones(n)
    var = np.maximum(y if var is None else var, 1.0)
    fq = np.clip(f, 1.0, None)
    # bands of ~15 % width variation
    logf = np.log(fq)
    band = np.floor((logf - logf.min()) / math.log(1.15)).astype(int)
    for b in np.unique(band):
        sel = band == b
        w = float(np.median(fq[sel]))
        k = _kernel(w)
        idx = np.nonzero(sel)[0]
        lo, hi = idx[0], idx[-1] + 1
        m = len(k) // 2
        a, z = max(lo - m, 0), min(hi + m, n)
        s = np.convolve(y[a:z], k[::-1], mode="same")
        v = np.convolve(var[a:z], (k * k)[::-1], mode="same")
        S[lo:hi] = s[lo - a:hi - a]
        V[lo:hi] = v[lo - a:hi - a]
    return S, np.sqrt(np.maximum(V, 1e-12))


def _start_index(y: np.ndarray, f: np.ndarray) -> int:
    """Skip leading empty channels and the LLD/noise edge."""
    nz = np.nonzero(y > 0)[0]
    if len(nz) == 0:
        return len(y)
    first = int(nz[0])
    # LLD cut-off: the first channels after the threshold rise steeply
    return min(len(y) - 1, first + max(3, int(math.ceil(1.0 * f[first]))))


def _candidates(y, f, min_sig, start, stop=None, var=None):
    S, sd = _filter(y, f, var)
    z = S / sd
    n = len(y)
    stop = n if stop is None else stop
    zz = z.copy()
    zz[:start] = 0
    zz[stop:] = 0
    # local maxima
    lm = np.nonzero((zz[1:-1] > zz[:-2]) & (zz[1:-1] >= zz[2:]) & (zz[1:-1] >= min_sig))[0] + 1
    lm = lm[np.argsort(-zz[lm])]
    taken = np.zeros(n, dtype=bool)
    out = []
    for i in lm:
        half = max(1, int(round(0.5 * f[i])))
        if taken[max(i - half, 0):i + half + 1].any():
            continue
        taken[i] = True
        # parabolic refinement of the filter maximum
        c = float(i)
        if 0 < i < n - 1:
            d = zz[i - 1] - 2 * zz[i] + zz[i + 1]
            if d < 0:
                c = i + 0.5 * (zz[i - 1] - zz[i + 1]) / d
        out.append((c, float(zz[i])))
    out.sort()
    return out


# ---------------------------------------------------------------------- fit
@dataclass
class _Fit:
    centroids: np.ndarray
    cent_unc: np.ndarray
    areas: np.ndarray
    area_unc: np.ndarray
    fwhms: np.ndarray
    bkg: Callable[[np.ndarray], np.ndarray]
    chi2r: float
    lo: int
    hi: int


# ------------------------------------------------------------ fit inspection (Release B, B2)
@dataclass
class FitComponent:
    """One Gaussian of a fit group (channels, first_channel convention of the spectrum)."""
    centroid: float
    centroid_unc: float
    fwhm: float
    area: float
    area_unc: float
    amplitude: float          # counts/channel at the centroid
    kept: bool                # reported as a peak
    reason: str = ""          # why it was not reported


@dataclass
class FitGroup:
    """Everything needed to display and judge one fitted region."""
    lo: int                   # first channel of the fit region (absolute channel number)
    hi: int
    data: np.ndarray
    total: np.ndarray         # fitted model (peaks + background + step)
    background: np.ndarray    # linear background + step
    components: list
    chi2_reduced: float
    dof: int
    width_scale: float        # fitted / model FWHM (1 when the width was fixed)
    width_free: bool
    width_at_bound: bool
    step_height: float
    retry: str = ""           # doublet retry: "", "tried", "accepted"
    warnings: list = field(default_factory=list)
    continuum_columns: Optional[np.ndarray] = None   # (k, channels): the fit's continuum terms
    weights: Optional[np.ndarray] = None             # the fit's channel weights (1/variance)

    @property
    def channels(self) -> np.ndarray:
        return np.arange(self.lo, self.hi + 1)

    def component_curve(self, j: int) -> np.ndarray:
        c = self.components[j]
        s = c.fwhm * F2S
        return c.amplitude * np.exp(-0.5 * ((self.channels - c.centroid) / s) ** 2)

    @property
    def residuals(self) -> np.ndarray:
        """(data - fit) / sqrt(max(data, 1)), the quantity the fit minimised."""
        return (self.data - self.total) / np.sqrt(np.maximum(self.data, 1.0))


@dataclass
class FitReport:
    fwhm_source: str = ""
    groups: list = field(default_factory=list)

    def group_at(self, channel: float) -> Optional[FitGroup]:
        for g in self.groups:
            if g.lo <= channel <= g.hi:
                return g
        return None

    def discarded(self) -> list:
        """(group, component) pairs that were fitted but not reported, with the reason."""
        return [(g, c) for g in self.groups for c in g.components if not c.kept]


def _record_group(rec: FitReport, spectrum, y, r, retry: str, kept: dict, reasons: dict) -> None:
    f0 = spectrum.first_channel
    x = np.arange(r.lo, r.hi + 1, dtype=float)
    bk = r.bkg(x)
    tot = bk.copy()
    comps = []
    for j in range(len(r.centroids)):
        a, sg, c = float(r.amps[j]), float(r.sigmas[j]), float(r.centroids[j])
        tot = tot + a * np.exp(-0.5 * ((x - c) / sg) ** 2)
        comps.append(FitComponent(c + f0, float(r.cent_unc[j]), float(r.fwhms[j]), float(r.areas[j]),
                                  float(r.area_unc[j]), a, j in kept, reasons.get(j, "")))
    g = FitGroup(r.lo + f0, r.hi + f0, y[r.lo:r.hi + 1].copy(), tot, bk, comps, float(r.chi2r), r.dof,
                 float(r.scale) if r.free_width else 1.0, r.free_width, bool(r.at_bound), r.step_h, retry)
    if hasattr(r, "cont_cols"):
        g.continuum_columns, g.weights = r.cont_cols(x), r.weights2.copy()
    if getattr(r, "edge", None) is not None:
        g.warnings.append(f"continuum step fitted at channel {r.edge[1] + f0:.1f} (Compton edge of the "
                          f"{getattr(r, 'edge_source_kev', 0):.0f} keV line): areas near it depend on the "
                          "edge shape")
    if r.chi2r > 3.0:
        g.warnings.append(f"poor fit: chi2/dof = {r.chi2r:.1f} (shape, background or a missing component)")
    if r.at_bound:
        g.warnings.append(f"width scale at its bound ({r.scale:.2f} x model): the peak shape is not the "
                          "expected resolution")
    for j in range(len(comps) - 1):
        d = abs(comps[j + 1].centroid - comps[j].centroid)
        if d < 1.0 * max(comps[j].fwhm, comps[j + 1].fwhm):
            g.warnings.append(f"components at {comps[j].centroid:.1f} and {comps[j + 1].centroid:.1f} are "
                              f"{d / comps[j].fwhm:.2f} FWHM apart: separation is poorly determined")
    rec.groups.append(g)


BKG_LOGLINEAR = False            # default continuum shape when the model does not say
LOGLINEAR_DETECTORS = ("NaI", "LaBr3", "CZT")   # wide fit regions: continuum curvature matters
POISSON_IRLS_ITER = 3            # model-weighted refits (Poisson likelihood) for raw counts
POISSON_MODEL_FLOOR = 0.25       # counts/channel floor of the model in the weights


def _fit_group(y, model: _Model, cents: list[float], lo: int, hi: int, free_width=True,
               step=True, width_bounds=(0.7, 1.4), fix_centroids=None, var=None,
               edge: Optional[tuple] = None, loglinear: Optional[bool] = None) -> Optional[_Fit]:
    """Gaussians (shared width scale) + linear background + erfc step, Poisson-weighted
    (or weighted by the explicit channel variance `var`).  For raw counts of scintillators
    (``model.loglinear``, set by find_peaks) the continuum is log-linear, exp(b0 + b1 (x - xm)):
    over their wide fit regions a straight line under a peak on a convex (falling) continuum
    overestimates the background and biases weak areas low; the exponential has the same two
    parameters.  HPGe fit regions are a few keV wide and keep the straight line.  Raw counts are fitted by Poisson
    maximum likelihood (iteratively reweighted with the model, POISSON_IRLS_ITER).

    `edge` = (x0, xmin, xmax[, smax]) adds a continuum step E * erfc((x - xe) / (s_e sqrt 2)) / 2
    (Compton edge, falling with energy) with E >= 0, xe in [xmin, xmax] and s_e from 1 to smax
    (default 6) times the resolution sigma at x0; it belongs to the background.

    Small dense Levenberg-Marquardt with analytic Jacobian and box constraints
    (projected steps) - ~20x faster than scipy.optimize.least_squares for these sizes.
    """
    x = np.arange(lo, hi + 1, dtype=float)
    d = y[lo:hi + 1]
    if len(x) < 5:
        return None
    w = 1.0 / np.sqrt(np.maximum(d if var is None else var[lo:hi + 1], 1.0))
    k = len(cents)
    base_f = np.array([model.at(c) for c in cents])
    xm = 0.5 * (x[0] + x[-1])
    e = max(2, min(4, len(x) // 6))
    yl, yr = float(np.mean(d[:e])), float(np.mean(d[-e:]))
    b0 = 0.5 * (yl + yr)
    b1 = (yr - yl) / max(x[-1] - x[0], 1.0)
    p = [b0, b1, 1.0, 0.0]
    off = 4                       # index of the first peak amplitude
    sig_e0 = 0.0
    if edge is not None:
        x0e = float(min(max(edge[0], x[0]), x[-1]))
        sig_e0 = model.at(x0e) * F2S
        p += [max(yl - yr, 0.0), x0e, 1.5]
        off = 7
    for c in cents:
        i = min(max(int(round(c)) - lo, 0), len(d) - 1)
        p += [max(float(d[i]) - (b0 + b1 * (c - xm)), 1.0), float(c)]
    p = np.array(p, dtype=float)
    if loglinear is None:
        loglinear = getattr(model, "loglinear", BKG_LOGLINEAR)
    loglin = bool(loglinear) and var is None
    if loglin:
        p[0], p[1] = math.log(max(b0, 0.5)), b1 / max(b0, 0.5)
    # linear pre-solve: background + amplitudes at the search centroids / model widths
    try:
        sg = base_f * F2S
        G = np.exp(-0.5 * ((x[None, :] - np.array(cents)[:, None]) / sg[:, None]) ** 2)
        cols = [np.ones_like(x), x - xm]
        if edge is not None:
            cols.append(0.5 * erfc((x - p[5]) / (1.5 * sig_e0 * math.sqrt(2.0))))
        A0 = np.vstack(cols + list(G)).T * w[:, None]
        sol = np.linalg.lstsq(A0, d * w, rcond=None)[0]
        p[0], p[1] = sol[0], sol[1]
        if loglin:
            lev = max(sol[0], 0.5)
            p[0], p[1] = math.log(lev), sol[1] / lev
        if edge is not None:
            p[4] = max(sol[2], 0.0)
        p[off::2] = np.maximum(sol[len(cols):], 1.0)
    except np.linalg.LinAlgError:
        pass
    if step and float(np.max(p[off::2])) * float(np.max(base_f)) < 300.0:
        step = False          # step background only matters for large peaks
    npar = len(p)
    lb = np.full(npar, -np.inf)
    ub = np.full(npar, np.inf)
    if free_width:
        lb[2], ub[2] = width_bounds
    else:
        lb[2] = ub[2] = 1.0
    lb[3], ub[3] = 0.0, (0.3 if step else 0.0)
    if edge is not None:
        lb[4], ub[4] = 0.0, np.inf
        lb[5], ub[5] = max(float(edge[1]), x[0]), min(float(edge[2]), x[-1])
        if lb[5] > ub[5]:
            lb[5] = ub[5] = p[5]
        p[5] = min(max(p[5], lb[5]), ub[5])
        lb[6], ub[6] = 1.0, max(float(edge[3]) if len(edge) > 3 else 6.0, 1.0)
    for j, (c, f) in enumerate(zip(cents, base_f)):
        lb[off + 2 * j] = 0.0
        if fix_centroids is not None and fix_centroids[j]:
            lb[off + 1 + 2 * j] = ub[off + 1 + 2 * j] = c   # manual edit: centroid held at the given channel
        else:
            lb[off + 1 + 2 * j], ub[off + 1 + 2 * j] = c - 0.6 * f, c + 0.6 * f
    fixed = lb == ub
    xs = x - xm
    R2 = math.sqrt(2.0)

    use_step = ub[3] > 0
    ia = np.arange(off, npar, 2)
    ic = ia + 1
    J = np.empty((len(x), npar))
    J[:, 0] = 1.0
    J[:, 1] = xs

    def evaluate(p, want_jac=True):
        sc, h = p[2], p[3]
        a, c = p[ia], p[ic]
        s = base_f * (sc * F2S)
        T = (x[None, :] - c[:, None]) / s[:, None]
        EX = np.exp(-0.5 * T * T)
        if loglin:
            B = np.exp(np.clip(p[0] + p[1] * xs, -50.0, 50.0))
            m = B + a @ EX
        else:
            m = p[0] + p[1] * xs + a @ EX
        if use_step:
            EC = 0.5 * erfc(T / R2)
            m = m + h * (a @ EC)
        if edge is not None:
            sE = p[6] * sig_e0
            U = (x - p[5]) / (sE * R2)
            EE = 0.5 * erfc(U)
            m = m + p[4] * EE
        if not want_jac:
            return m, None
        if edge is not None:
            gE = np.exp(-U * U) / (sE * SQRT2PI)
            J[:, 4] = EE
            J[:, 5] = p[4] * gE
            J[:, 6] = p[4] * gE * (x - p[5]) / p[6]
        aEX = a[:, None] * EX
        dc = aEX * T / s[:, None]
        dsc = (aEX * T * T).sum(axis=0) / sc
        J[:, ia] = EX.T
        J[:, ic] = dc.T
        if use_step:
            gp = aEX / (s[:, None] * SQRT2PI)          # a * gaussian density
            J[:, ia] += h * EC.T
            J[:, ic] += h * gp.T
            dsc = dsc + h * (gp * T * s[:, None]).sum(axis=0) / sc
            J[:, 3] = a @ EC
        else:
            J[:, 3] = 0.0
        J[:, 2] = dsc
        if loglin:
            J[:, 0] = B
            J[:, 1] = B * xs
        return m, J

    def lm(p, w):
        lam = 1e-3
        m, J = evaluate(p)
        r = (m - d) * w
        chi2 = float(r @ r)
        for _it in range(30):
            Jw = J * w[:, None]
            g0 = Jw.T @ r
            # active set: parameters sitting on a bound with the gradient pushing outwards
            frz = fixed | ((p <= lb) & (g0 > 0)) | ((p >= ub) & (g0 < 0))
            Jw[:, frz] = 0.0
            A = Jw.T @ Jw
            g = Jw.T @ r
            dg = np.diag(A).copy()
            dg[dg <= 0] = 1.0
            improved = False
            for _try in range(6):
                M = A + lam * np.diag(dg)
                M[frz, :] = 0.0
                M[:, frz] = 0.0
                M[frz, frz] = 1.0
                try:
                    step_ = -np.linalg.solve(M, g)
                except np.linalg.LinAlgError:
                    lam *= 10
                    continue
                pn = np.minimum(np.maximum(p + step_, lb), ub)
                mn, _ = evaluate(pn, want_jac=False)
                rn = (mn - d) * w
                c2 = float(rn @ rn)
                if c2 < chi2:
                    rel = (chi2 - c2) / max(chi2, 1e-12)
                    p, chi2 = pn, c2
                    lam = max(lam / 4.0, 1e-7)
                    improved = True
                    break
                lam *= 5.0
            if not improved:
                break
            m, J = evaluate(p)
            r = (m - d) * w
            if rel < 1e-4:
                break
        return p, chi2, m, J

    p, chi2, m, J = lm(p, w)
    if var is None:
        # Poisson maximum likelihood for raw counts: weights from the model, not the data
        # (Neyman weights 1/d favour downward fluctuations and bias weak areas low).  At the
        # fixed point sum (d - m)/m dm/dtheta = 0, the Poisson likelihood equations.
        for _k in range(POISSON_IRLS_ITER):
            m, _ = evaluate(p, want_jac=False)
            w = 1.0 / np.sqrt(np.maximum(m, POISSON_MODEL_FLOOR))
            p, chi2, m, J = lm(p, w)
    dof = max(len(x) - int(npar - fixed.sum()), 1)
    chi2r = chi2 / dof
    Jw = J * w[:, None]
    Jw[:, fixed] = 0.0
    try:
        cov = np.linalg.pinv(Jw.T @ Jw) * max(chi2r, 1.0)
    except np.linalg.LinAlgError:
        return None
    sc = p[2]
    cent = np.array([p[off + 1 + 2 * j] for j in range(k)])
    amp = np.array([p[off + 2 * j] for j in range(k)])
    sig = base_f * sc * F2S
    area = amp * sig * SQRT2PI
    area_unc = np.zeros(k)
    cent_unc = np.zeros(k)
    for j in range(k):
        ia = off + 2 * j
        gv = np.zeros(npar)
        gv[ia] = sig[j] * SQRT2PI
        if not fixed[2]:
            gv[2] = amp[j] * base_f[j] * F2S * SQRT2PI
        area_unc[j] = math.sqrt(max(float(gv @ cov @ gv), 0.0))
        cent_unc[j] = math.sqrt(max(float(cov[ia + 1, ia + 1]), 0.0))
    b0f, b1f, hst = p[0], p[1], p[3]
    loglin_f = loglin
    cents_f, amps_f, sig_f = cent.copy(), amp.copy(), sig.copy()
    edge_f = (float(p[4]), float(p[5]), float(p[6] * sig_e0)) if edge is not None else None

    def bkg(xx):
        xx = np.asarray(xx, dtype=float)
        out = (np.exp(np.clip(b0f + b1f * (xx - xm), -50.0, 50.0)) if loglin_f
               else b0f + b1f * (xx - xm))
        for c, a, s in zip(cents_f, amps_f, sig_f):
            out = out + hst * a * 0.5 * erfc((xx - c) / (s * R2))
        if edge_f is not None:
            out = out + edge_f[0] * 0.5 * erfc((xx - edge_f[1]) / (edge_f[2] * R2))
        return out

    fit = _Fit(cent, cent_unc, area, area_unc, base_f * sc, bkg, chi2r, lo, hi)
    fit.scale = float(sc)
    fit.at_bound = bool(free_width and (sc >= width_bounds[1] - 1e-6 or sc <= width_bounds[0] + 1e-6))
    # parameters kept for fit inspection (FitReport); not used by the search itself
    fit.amps, fit.sigmas, fit.step_h = amp, sig, float(hst)
    fit.free_width, fit.dof, fit.width_bounds = bool(free_width), int(dof), tuple(width_bounds)
    fit.edge = edge_f              # (height, position, sigma) of the continuum step, or None
    fit.loglinear = bool(loglin)
    fit.weights2 = w * w            # final fit weights 1/variance (model-based for raw counts)

    def cont_cols(xx):
        """Continuum columns of the fit (linear in their coefficients at the fitted shape)."""
        xx = np.asarray(xx, dtype=float)
        if loglin_f:
            B = np.exp(np.clip(b0f + b1f * (xx - xm), -50.0, 50.0))
            cols = [B, B * (xx - xm)]
        else:
            cols = [np.ones_like(xx), xx - xm]
        if edge_f is not None:
            cols.append(0.5 * erfc((xx - edge_f[1]) / (edge_f[2] * R2)))
        return np.vstack(cols)

    fit.cont_cols = cont_cols
    fit.chi2 = float(chi2)
    return fit


# --------------------------------------------------------------- main entry
def loglinear_continuum(spectrum) -> bool:
    """Log-linear continuum under fitted peaks for scintillator spectra (see _fit_group)."""
    return guess_detector(spectrum) in LOGLINEAR_DETECTORS


def width_model(spectrum, y: np.ndarray, fwhm: Optional[float] = None, min_energy: Optional[float] = None,
                var: Optional[np.ndarray] = None) -> tuple[np.ndarray, str, int]:
    """FWHM (channels) per index used by the search and fit, its source, and the first index
    analysed.  Shared by :func:`find_peaks` and manual refits (analysis.manual)."""
    n = len(y)
    if fwhm is not None and fwhm > 0:
        f = np.full(n, float(fwhm))
        src = "user"
    else:
        f, src = fwhm_model(spectrum, y)
        if src == "none":
            f = _estimate_fwhm_from_data(y)
            src = "data"
    start = _start_index(y, f)
    if min_energy is not None and spectrum.energy_coeffs:
        e = _poly(spectrum.energy_coeffs, spectrum.first_channel + np.arange(n))
        above = np.nonzero(e >= min_energy)[0]
        start = max(start, int(above[0]) if len(above) else n)
    # refine the model with the strongest isolated peaks of this spectrum
    if src not in ("user",):
        f = _rescale_model(y, f, start, var)
    return f, src, start


def find_peaks(spectrum, min_sig: float = 3.0, fwhm: Optional[float] = None, fit: bool = True,
               min_energy: Optional[float] = None, max_peaks: int = 400,
               report: Optional[FitReport] = None, variance=None, **_ignored) -> list[Peak]:
    """Search, fit and flag peaks.

    min_sig     : significance threshold (net area / its 1-sigma uncertainty); default 3.
    fwhm        : force a constant FWHM (channels) for the search.
    fit         : False returns search results with simple ROI-sum areas (faster).
    min_energy  : ignore peaks below this energy (keV), calibrated spectra only.
    report      : a FitReport to fill with every fitted group (data, components, background,
                  residuals, warnings, discarded components with reasons).  The results are the
                  same with or without it.
    variance    : per-channel variance of the counts when they are not raw Poisson counts
                  (a background-subtracted spectrum: S + k^2 B).  The counts are then used as
                  they are (negative channels kept) and every weight and uncertainty uses it.
    """
    y = np.asarray(spectrum.counts, dtype=float)
    n = len(y)
    var = None
    if variance is not None:
        var = np.asarray(variance, dtype=float)
        if var.shape != y.shape or not np.isfinite(var).all():
            raise ValueError("variance must have one finite value per channel")
        var = np.maximum(var, 0.0)
    if n < 16 or not np.isfinite(y).all() or (var is None and y.sum() <= 0):
        return []
    if var is None:
        y = np.maximum(y, 0.0)
    f0 = spectrum.first_channel
    f, src, start = width_model(spectrum, y, fwhm, min_energy, var)
    if report is not None:
        report.fwhm_source = src
    model = _Model(f)
    model.loglinear = loglinear_continuum(spectrum)
    cands = _candidates(y, f, min_sig * 0.8, start, var=var)
    if not cands:
        return []
    if len(cands) > max_peaks:
        cands = sorted(sorted(cands, key=lambda c: -c[1])[:max_peaks])
    peaks: list[Peak] = []
    if not fit:
        for c, z in cands:
            peaks.append(_roi_peak(spectrum, y, model, c, z))
        return [p for p in peaks if p.significance >= min_sig]

    edges = _expected_edges(spectrum, cands, n, f)
    # group candidates
    groups: list[list[tuple[float, float]]] = []
    for c, z in cands:
        if groups and c - groups[-1][-1][0] < 3.5 * model.at(c) and len(groups[-1]) < 8:
            groups[-1].append((c, z))
        else:
            groups.append([(c, z)])
    # an expected Compton edge is fitted with everything within EDGE_REGION_FWHM of it, so the
    # continuum on both sides of the step is part of the fit (no region cut at a strong peak)
    for xe, _src, _k in edges:
        span = EDGE_REGION_FWHM * model.at(xe)
        hit = [i for i, g in enumerate(groups)
               if g[0][0] - 2.2 * model.at(g[0][0]) <= xe + span and g[-1][0] + 2.2 * model.at(g[-1][0]) >= xe - span]
        if len(hit) > 1 and sum(len(groups[i]) for i in hit) <= EDGE_MAX_COMPONENTS:
            merged = [cz for i in hit for cz in groups[i]]
            groups = groups[:hit[0]] + [merged] + groups[hit[-1] + 1:]
    for g in groups:
        peaks.extend(_fit_and_make(spectrum, y, model, [c for c, _ in g], start, min_sig, g, rec=report,
                                   var=var, edges=edges, others=[c for c, _ in cands]))
    peaks.sort(key=lambda p: p.centroid)
    peaks = _dedupe(peaks, model, f0)
    if report is not None:
        final = {round(p.centroid, 6) for p in peaks}
        for grp in report.groups:
            for c in grp.components:
                if c.kept and round(c.centroid, 6) not in final:
                    c.kept, c.reason = False, "duplicate of a peak fitted in a neighbouring region"
    _flag(peaks, spectrum)
    return peaks


EDGE_SOURCE_MIN_Z = 30.0        # candidates strong enough to give a visible Compton edge
EDGE_SOURCE_MIN_KEV = 200.0
EDGE_ACCEPT_DCHI2 = 15.0        # chi2 decrease (scaled by chi2/dof) needed to keep the edge term
EDGE_REGION_FWHM = 6.0          # fit region extends this far on each side of an expected edge
RESIDUAL_MIN_Z = 4.0             # residual excess (matched Gaussian) worth trying as a component
RESIDUAL_ACCEPT_DCHI2 = 9.0      # chi2 decrease (scaled) needed to keep it
RESIDUAL_MAX_ADDED = 2
EDGE_MAX_REL_FWHM = 0.02         # edge model only for high-resolution spectra (HPGe ~0.2 %, NaI ~7 %)
EDGE_MAX_COMPONENTS = 10         # largest group formed by merging the groups around an edge
EDGE_MAX_EXTRA_SIGMA_KEV = 10.0 # edge smearing beyond the resolution (electron momentum, geometry)


def compton_edge_kev(e: float) -> float:
    """Compton edge of a line of energy e (keV): e * 2a / (1 + 2a), a = e / 511."""
    a = e / 510.999
    return e * 2.0 * a / (1.0 + 2.0 * a)


def _expected_edges(spectrum, cands, n, f=None) -> list[tuple[float, float, float]]:
    """(index channel of the Compton edge, source energy, keV per channel there) for the
    strongest candidates of a calibrated spectrum (none for uncalibrated spectra).

    Only for high-resolution spectra (FWHM / E at the edge below EDGE_MAX_REL_FWHM): with NaI
    the edge extends over several FWHM of curved continuum (backscatter peak, X-rays, the
    source line itself), where a linear continuum plus one step is not an adequate model and
    created false peaks on real NaI calibration spectra."""
    if not spectrum.energy_coeffs:
        return []
    e = _poly(spectrum.energy_coeffs, spectrum.first_channel + np.arange(n))
    if not np.all(np.diff(e) > 0):
        return []
    out = []
    for c, z in sorted(cands, key=lambda c: -c[1])[:10]:
        if z < EDGE_SOURCE_MIN_Z:
            break
        ek = float(np.interp(c, np.arange(n), e))
        if ek < EDGE_SOURCE_MIN_KEV:
            continue
        ee = compton_edge_kev(ek)
        if e[0] <= ee <= e[-1]:
            xe = float(np.interp(ee, e, np.arange(n)))
            i = int(min(max(round(xe), 1), n - 2))
            kev_ch = float(e[i + 1] - e[i - 1]) / 2.0
            if f is not None and f[i] * kev_ch / ee > EDGE_MAX_REL_FWHM:
                continue
            out.append((xe, ek, kev_ch))
    return out


def _width_ratios(y, f, start, var=None) -> list[float]:
    """Fitted/model FWHM of up to 8 strong isolated peaks (free width x0.5..x2, not at bound)."""
    cands = _candidates(y, f, 12.0, start, var=var)
    if len(cands) < 1:
        return []
    cands = sorted(cands, key=lambda c: -c[1])[:8]
    allc = sorted(c for c, _ in cands)
    m = _Model(f)
    ratios = []
    for c, z in cands:
        fw = m.at(c)
        if any(0 < abs(o - c) < 4 * fw for o in allc):
            continue
        lo, hi = int(max(c - 2.5 * fw, 0)), int(min(c + 2.5 * fw, len(y) - 1))
        r = _fit_group(y, m, [c], lo, hi, free_width=True, step=True, width_bounds=(0.5, 2.0), var=var)
        if r is None or r.at_bound or r.chi2r > 20 or r.area_unc[0] <= 0 or r.areas[0] / r.area_unc[0] < 10:
            continue
        ratios.append(r.fwhms[0] / fw)
    return ratios if (len(ratios) >= 2 or (len(ratios) == 1 and len(cands) <= 3)) else []


def _rescale_model(y, f, start, var=None):
    """Scale FWHM model to the widths of strong isolated peaks (median ratio)."""
    ratios = _width_ratios(y, f, start, var)
    if ratios:
        k = float(np.clip(np.median(ratios), 0.5, 2.0))
        if abs(k - 1.0) > 0.08:
            return f * k
    return f


def _estimate_fwhm_from_data(y) -> np.ndarray:
    """Uncalibrated spectrum without FWHM info: fit strong peaks found at several widths."""
    n = len(y)
    pts = []
    for w in (4.0, 2.5, 8.0, 16.0, 32.0, 64.0):   # 64: NaI on 4096+ channels
        if sum(1 for _c, fw in pts if 0.7 * w <= fw <= 1.4 * w) >= 4:
            break    # the previous kernel width already matched the peaks
        f = np.full(n, w)
        start = _start_index(y, f)
        cands = sorted(_candidates(y, f, 15.0, start), key=lambda c: -c[1])[:6]
        m = _Model(f)
        for c, z in cands:
            lo, hi = int(max(c - 2.5 * w, 0)), int(min(c + 2.5 * w, n - 1))
            r = _fit_group(y, m, [c], lo, hi, free_width=True, step=False, width_bounds=(0.4, 2.5))
            if r is None or r.chi2r > 10:
                continue
            fw = float(r.fwhms[0])
            if 0.6 * w <= fw <= 1.6 * w and r.areas[0] > 10 * r.area_unc[0] > 0:
                pts.append((float(r.centroids[0]), fw))
    if not pts:
        return np.full(n, 4.0)
    pts = np.array(sorted(set((round(c, 1), round(fw, 2)) for c, fw in pts)))
    # consistent widths: FWHM^2 = a + b*ch (b >= 0), fitted robustly.  Points are rejected by
    # their ratio to the current fit, not to the overall median, so the strong energy dependence
    # of NaI widths (x4 over the spectrum on a 4096-channel MCA) survives.
    c, fw = pts[:, 0], pts[:, 1]
    med = float(np.median(fw))
    if len(c) >= 3 and np.ptp(c) > n / 4:
        keep = np.ones(len(c), dtype=bool)
        model = None
        for _ in range(4):
            if keep.sum() < 3 or np.ptp(c[keep]) <= n / 4:
                break
            A = np.vstack([np.ones(int(keep.sum())), c[keep]]).T
            (a, b), *_ = np.linalg.lstsq(A, fw[keep] ** 2, rcond=None)
            if b < 0:
                break
            m = np.sqrt(np.maximum(a + b * c, 1e-6))
            new_keep = (fw > 0.7 * m) & (fw < 1.4 * m)
            model = (a, b)
            if np.array_equal(new_keep, keep):
                break
            keep = new_keep
        if model is not None and keep.sum() >= 3:
            a, b = model
            floor = 0.5 * float(fw[keep].min())
            return np.sqrt(np.maximum(a + b * np.arange(n), floor * floor))
    ok = (fw > 0.6 * med) & (fw < 1.6 * med)
    return np.full(n, float(np.median(fw[ok])) if ok.any() else med)


def _fit_and_make(spectrum, y, model, cents, start, min_sig, zs=(), rec: Optional[FitReport] = None,
                  var=None, edges=(), others=()) -> list[Peak]:
    n = len(y)
    fl, fr = model.at(cents[0]), model.at(cents[-1])
    lo = int(max(math.floor(cents[0] - 2.2 * fl), start - 1, 0))
    hi = int(min(math.ceil(cents[-1] + 2.2 * fr), n - 1))
    # free width only where the data constrain it (strong peaks); weak peaks use the model width
    free = sum(y[int(c)] for c in cents) > 200 and max(z for _c, z in zs) > 25 if zs else False
    r = _fit_group(y, model, cents, lo, hi, free_width=free, step=True, var=var)
    if r is None:
        return []
    # continuum step at an expected Compton edge inside the region.  The region is widened
    # (up to EDGE_REGION_FWHM beyond the edge, stopping short of other candidates) so that the
    # levels on both sides of the step are measured; both models are compared on that region.
    edge = None
    for xe, src_kev, kev_ch in edges:
        fe = model.at(xe)
        if lo - fe <= xe <= hi + fe:
            lo2 = int(max(min(lo, math.floor(xe - EDGE_REGION_FWHM * fe)), start - 1, 0))
            hi2 = int(min(max(hi, math.ceil(xe + EDGE_REGION_FWHM * fe)), n - 1))
            for o in others:
                if o < cents[0] - 0.5 and o + 2.5 * model.at(o) > lo2:
                    lo2 = min(lo, int(math.ceil(o + 2.5 * model.at(o))))
                if o > cents[-1] + 0.5 and o - 2.5 * model.at(o) < hi2:
                    hi2 = max(hi, int(math.floor(o - 2.5 * model.at(o))))
            s_res = fe * F2S * kev_ch                         # resolution sigma at the edge, keV
            smax = math.sqrt(1.0 + (EDGE_MAX_EXTRA_SIGMA_KEV / max(s_res, 1e-9)) ** 2)
            ed = (xe, xe - 2.0 * fe, xe + 2.0 * fe, smax)
            r0 = r if (lo2, hi2) == (lo, hi) else _fit_group(y, model, cents, lo2, hi2, free_width=free,
                                                             step=True, var=var)
            re = _fit_group(y, model, cents, lo2, hi2, free_width=free, step=True, var=var, edge=ed)
            if (r0 is not None and re is not None
                    and (r0.chi2 - re.chi2) / max(re.chi2r, 1.0) > EDGE_ACCEPT_DCHI2):
                r, edge, lo, hi = re, ed, lo2, hi2
                r.edge_source_kev = src_kev
            break
    # residual search in an edge region: the edge curvature masks the search filter there, so a
    # peak on or next to the edge may have no candidate.  A Gaussian matched to the residuals
    # adds one component at a time, kept only when the fit improves significantly.
    if edge is not None:
        for _ in range(RESIDUAL_MAX_ADDED):
            add = _residual_candidate(y, r, model, var)
            if add is None:
                break
            new = sorted([float(c) for c in r.centroids] + [add])
            rn = _fit_group(y, model, new, lo, hi, free_width=free, step=True, var=var, edge=edge)
            if rn is None or (r.chi2 - rn.chi2) / max(rn.chi2r, 1.0) < RESIDUAL_ACCEPT_DCHI2:
                break
            rn.edge_source_kev = r.edge_source_kev
            r, cents = rn, new
    retry = ""
    # doublet retry on single peaks with bad fit
    if len(cents) == 1 and r.chi2r > 4.0 and hi - lo > 8:
        retry = "tried"
        x = np.arange(lo, hi + 1)
        g = r.areas[0] / (r.fwhms[0] * F2S * SQRT2PI) * np.exp(
            -0.5 * ((x - r.centroids[0]) / (r.fwhms[0] * F2S)) ** 2)
        res = y[lo:hi + 1] - r.bkg(x) - g
        j = int(np.argmax(res))
        c2 = float(x[j])
        c0 = float(r.centroids[0])
        starts = []
        if abs(c2 - c0) > 0.4 * r.fwhms[0]:
            starts.append(sorted([c0, c2]))
        # An unresolved doublet ~1 FWHM apart is fitted as one over-wide peak whose residual
        # maximum lies close to its centroid; the residual start then collapses back onto one
        # centroid, and the singlet would be discarded below as a "Compton hump".  Only in that
        # case (width scale at its upper bound) also try symmetric starts at +-0.3 model FWHM;
        # merely asymmetric (tailed) peaks stay below the bound and keep the old behaviour.
        if getattr(r, "at_bound", False) and r.scale > 1.3:
            h = 0.3 * model.at(c0)
            starts.append([c0 - h, c0 + h])
        best = None
        for st in starts:
            cand = _fit_group(y, model, st, lo, hi, free_width=free, step=True, var=var, edge=edge)
            if cand is not None and (best is None or cand.chi2r < best.chi2r):
                best = cand
        if best is not None:
            r2 = best
            if r2.chi2r < 0.6 * r.chi2r and np.all(r2.areas > 3 * r2.area_unc) and (
                    min(r2.areas) >= 0.1 * max(r2.areas)
                    or abs(r2.centroids[1] - r2.centroids[0]) >= 1.0 * r2.fwhms[0]):
                # (a weak component very close to a big peak is usually peak tailing, not a doublet)
                r = r2
                retry = "accepted"
    out = []
    kept: dict = {}
    reasons: dict = {}
    k = len(r.centroids)
    for j in range(k):
        c = float(r.centroids[j])
        if not (r.lo <= c <= r.hi):
            reasons[j] = "centroid moved outside the fit region"
            continue
        area, unc = float(r.areas[j]), float(r.area_unc[j])
        fw = float(r.fwhms[j])
        if area <= 0:
            reasons[j] = "fitted area <= 0"
            continue
        if k == 1 and getattr(r, "at_bound", False) and r.scale > 1.3 and area / max(unc, 1e-9) < 30:
            reasons[j] = (f"discarded as a Compton edge / backscatter hump: {r.scale:.2f} x the resolution "
                          f"width, significance {area / max(unc, 1e-9):.0f} < 30")
            continue   # much broader than the resolution: Compton edge / backscatter hump, not a peak
        roi_l = int(max(math.floor(c - 1.25 * fw), 0))
        roi_r = int(min(math.ceil(c + 1.25 * fw), n - 1))
        xr = np.arange(roi_l, roi_r + 1)
        gross = float(y[roi_l:roi_r + 1].sum())
        bkg = float(np.maximum(r.bkg(xr), 0).sum())
        # Poisson floor for the uncertainty (fit covariance can be optimistic for tiny peaks):
        # var(gross) + var(background) = (A + B) + B; with an explicit variance V of the
        # region, var(gross) = V and var(background) ~ V - A
        if var is None:
            unc = max(unc, math.sqrt(max(area, 0) + 2.0 * bkg) * 0.7, 1.0)
        else:
            v_roi = float(var[roi_l:roi_r + 1].sum())
            unc = max(unc, math.sqrt(max(2.0 * v_roi - max(area, 0.0), v_roi)) * 0.7, 1.0)
        sig = area / unc
        if sig < min_sig:
            reasons[j] = f"significance {sig:.1f} below the threshold {min_sig:g}"
            if r.edge is not None and abs(c - r.edge[1]) < 2.0 * max(r.edge[2] / F2S, fw):
                reasons[j] += (f"; the continuum step of the Compton edge of the "
                               f"{getattr(r, 'edge_source_kev', 0):.0f} keV line explains it")
            continue
        kept[j] = True
        out.append(_make_peak(spectrum, c, float(r.cent_unc[j]), fw, area, unc, gross, bkg,
                              roi_l, roi_r, sig, k))
    if rec is not None and hasattr(r, "amps"):
        _record_group(rec, spectrum, y, r, retry, kept, reasons)
    return out


def _residual_candidate(y, r, model, var=None) -> Optional[float]:
    """Channel of the most significant Gaussian-shaped excess in the residuals of fit `r`
    (z > RESIDUAL_MIN_Z, at least 1 FWHM from the fitted components and the region ends)."""
    x = np.arange(r.lo, r.hi + 1, dtype=float)
    tot = r.bkg(x)
    for a_, c_, s_ in zip(r.amps, r.centroids, r.sigmas):
        tot = tot + a_ * np.exp(-0.5 * ((x - c_) / s_) ** 2)
    d = y[r.lo:r.hi + 1]
    v = np.maximum(d if var is None else var[r.lo:r.hi + 1], 1.0)
    res = d - tot
    best, bz = None, RESIDUAL_MIN_Z
    for x0 in x:
        fw = model.at(x0)
        if x0 - r.lo < fw or r.hi - x0 < fw or any(abs(x0 - c) < fw for c in r.centroids):
            continue
        g = np.exp(-0.5 * ((x - x0) / (fw * F2S)) ** 2)
        den = float(np.sum(g * g / v))
        z = float(np.sum(g * res / v)) / math.sqrt(den) if den > 0 else 0.0
        if z > bz:
            best, bz = float(x0), z
    return best


def _make_peak(spectrum, c_idx, c_unc, fw, area, unc, gross, bkg, l, r, sig, mult) -> Peak:
    ch = spectrum.first_channel + c_idx
    energy = fwhm_kev = None
    if spectrum.energy_coeffs:
        energy = float(_poly(spectrum.energy_coeffs, ch))
        fwhm_kev = float(abs(_dpoly(spectrum.energy_coeffs, ch)) * fw)
    rate = area / spectrum.live_time if spectrum.live_time else None
    p = Peak(centroid=float(ch), energy=energy, fwhm=float(fw), fwhm_kev=fwhm_kev, net_area=float(area),
             net_area_unc=float(unc), gross_area=float(gross), background=float(bkg), left=int(l), right=int(r),
             significance=float(sig), count_rate=rate)
    p.centroid_unc = float(c_unc)
    p.multiplet = int(mult)
    return p


def _roi_peak(spectrum, y, model, c, z) -> Peak:
    fw = model.at(c)
    n = len(y)
    l = int(max(math.floor(c - 1.25 * fw), 0))
    r = int(min(math.ceil(c + 1.25 * fw), n - 1))
    m = max(1, int(round(fw / 2)))
    bl = float(np.mean(y[max(l - m, 0):l + 1]))
    br = float(np.mean(y[r:min(r + m + 1, n)]))
    gross = float(y[l:r + 1].sum())
    bkg = 0.5 * (bl + br) * (r - l + 1)
    net = gross - bkg
    unc = math.sqrt(max(gross + bkg, 1.0))
    return _make_peak(spectrum, c, 0.0, fw, net, unc, gross, bkg, l, r, net / unc if unc else 0.0, 1)


def _dedupe(peaks, model, f0):
    out: list[Peak] = []
    for p in peaks:
        if out and abs(p.centroid - out[-1].centroid) < 0.35 * model.at(p.centroid - f0):
            if p.significance > out[-1].significance:
                out[-1] = p
            continue
        out.append(p)
    return out


# --------------------------------------------------------------------- flags
def _add_note(p: Peak, text: str):
    if text and text not in p.note:
        p.note = f"{p.note}; {text}" if p.note else text


def _flag(peaks: list[Peak], spectrum) -> None:
    if not spectrum.energy_coeffs:
        return
    cal = [p for p in peaks if p.energy is not None]
    if not cal:
        return

    def tol(p):
        return max(0.6 * (p.fwhm_kev or 1.0), 0.5)

    def find(e, ref):
        best = None
        for q in cal:
            if abs(q.energy - e) <= max(tol(q), tol(ref)):
                if best is None or abs(q.energy - e) < abs(best.energy - e):
                    best = q
        return best

    for p in cal:
        if abs(p.energy - 511.0) <= tol(p) + 0.5:
            _add_note(p, "annihilation")
        if 10.0 <= p.energy <= 90.0:
            _add_note(p, "X-ray region")
    strong = sorted(cal, key=lambda p: -p.net_area)
    for p in strong[:15]:
        if p.energy > 1300:
            se = find(p.energy - 511.0, p)
            if se is not None and se.net_area < 0.5 * p.net_area:
                _add_note(se, f"single escape of {p.energy:.0f} keV")
            de = find(p.energy - 1022.0, p)
            if de is not None and de.net_area < 0.5 * p.net_area:
                _add_note(de, f"double escape of {p.energy:.0f} keV")
    for p in strong[:6]:
        ec = p.energy - p.energy / (1.0 + 2.0 * p.energy / 511.0)      # Compton edge
        ebs = p.energy / (1.0 + 2.0 * p.energy / 511.0)                # 180 deg backscatter
        for q in cal:
            if q is p or q.net_area > 0.5 * p.net_area:
                continue
            # scattering features are broad: only low-resolution detectors or wide peaks
            qf = q.fwhm_kev or 0.0
            if not (qf > 0.03 * q.energy or qf > 1.5 * (p.fwhm_kev or 0.0)):
                continue
            w = max(q.fwhm_kev or 1.0, 0.04 * q.energy)
            if p.energy > 200 and abs(q.energy - ebs) <= 1.2 * w:
                _add_note(q, f"possible backscatter of {p.energy:.0f} keV")
            elif p.energy > 300 and abs(q.energy - ec) <= 1.2 * w and (q.fwhm_kev or 0) > 5.0:
                _add_note(q, f"possible Compton edge of {p.energy:.0f} keV")
    top = strong[:8]
    for i, a in enumerate(top):
        for b in top[i + 1:]:
            s = find(a.energy + b.energy, a)
            if s is None or s is a or s is b or s.net_area >= 0.2 * min(a.net_area, b.net_area):
                continue
            if _cascade(a.energy, b.energy, s.energy, max(tol(a), tol(b), tol(s))):
                _add_note(s, f"sum peak ({a.energy:.0f}+{b.energy:.0f})")


def _cascade(ea: float, eb: float, es: float, tol: float) -> bool:
    """True if some library nuclide emits both ea and eb strongly (true-coincidence summing
    possible) and has no own line at the sum energy es (else it is a real line)."""
    try:
        from .library import load_library
        lib = load_library()
    except Exception:
        return False
    for nd in lib.values():
        has_a = has_b = has_s = False
        for l in nd.lines:
            if l.kind == "x":
                continue
            if abs(l.energy - ea) <= tol and l.intensity >= 5:
                has_a = True
            if abs(l.energy - eb) <= tol and l.intensity >= 5:
                has_b = True
            if abs(l.energy - es) <= tol and l.intensity >= 0.3:
                has_s = True
        if has_a and has_b and not has_s:
            return True
    return False

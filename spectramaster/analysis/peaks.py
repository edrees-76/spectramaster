"""Automatic peak search and fitting for gamma spectra (NaI ... HPGe).

Algorithm
---------
1. **Resolution model** FWHM(channel): from ``Spectrum.fwhm_coeffs`` (keV) when present,
   otherwise from the energy calibration plus a detector-type guess (HPGe / NaI / LaBr3 /
   CZT from channel count and keV/channel), otherwise estimated from the data (strong peaks
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
   Net area, centroid and their 1-sigma uncertainties come from the covariance matrix.
4. **Flags** (``Peak.note``): annihilation (511 keV), single/double escape of a stronger
   high-energy peak, sum peaks of two strong peaks (e.g. Co-60 2505 keV), Pb/X-ray region.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
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
    text = " ".join(str(v) for v in (spectrum.detector, spectrum.sample_id, spectrum.description)).lower()
    for key, det in (("hpge", "HPGe"), ("ge(li)", "HPGe"), ("germanium", "HPGe"), ("nai", "NaI"),
                     ("labr", "LaBr3"), ("czt", "CZT"), ("cdznte", "CZT")):
        if key in text:
            return det
    n = len(spectrum.counts)
    if not spectrum.energy_coeffs:
        return "HPGe" if n >= 4096 else ("NaI" if n <= 1024 else "")
    ch = spectrum.first_channel + n / 2.0
    gain = abs(float(_dpoly(spectrum.energy_coeffs, ch)))
    if n >= 4096 or gain < 0.75:
        return "HPGe"
    if n <= 1024 or gain > 2.0:
        return "NaI"
    return "LaBr3" if gain > 1.0 else "HPGe"


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


def _filter(y: np.ndarray, f: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Zero-area-Gaussian response S and its standard deviation, width following f."""
    n = len(y)
    S = np.zeros(n)
    V = np.ones(n)
    var = np.maximum(y, 1.0)
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


def _candidates(y, f, min_sig, start, stop=None):
    S, sd = _filter(y, f)
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


def _fit_group(y, model: _Model, cents: list[float], lo: int, hi: int, free_width=True,
               step=True, width_bounds=(0.7, 1.4)) -> Optional[_Fit]:
    """Gaussians (shared width scale) + linear background + erfc step, Poisson-weighted.

    Small dense Levenberg-Marquardt with analytic Jacobian and box constraints
    (projected steps) - ~20x faster than scipy.optimize.least_squares for these sizes.
    """
    x = np.arange(lo, hi + 1, dtype=float)
    d = y[lo:hi + 1]
    if len(x) < 5:
        return None
    w = 1.0 / np.sqrt(np.maximum(d, 1.0))
    k = len(cents)
    base_f = np.array([model.at(c) for c in cents])
    xm = 0.5 * (x[0] + x[-1])
    e = max(2, min(4, len(x) // 6))
    yl, yr = float(np.mean(d[:e])), float(np.mean(d[-e:]))
    b0 = 0.5 * (yl + yr)
    b1 = (yr - yl) / max(x[-1] - x[0], 1.0)
    p = [b0, b1, 1.0, 0.0]
    for c in cents:
        i = min(max(int(round(c)) - lo, 0), len(d) - 1)
        p += [max(float(d[i]) - (b0 + b1 * (c - xm)), 1.0), float(c)]
    p = np.array(p, dtype=float)
    # linear pre-solve: background + amplitudes at the search centroids / model widths
    try:
        sg = base_f * F2S
        G = np.exp(-0.5 * ((x[None, :] - np.array(cents)[:, None]) / sg[:, None]) ** 2)
        A0 = np.vstack([np.ones_like(x), x - xm, G]).T * w[:, None]
        sol = np.linalg.lstsq(A0, d * w, rcond=None)[0]
        p[0], p[1] = sol[0], sol[1]
        p[4::2] = np.maximum(sol[2:], 1.0)
    except np.linalg.LinAlgError:
        pass
    if step and float(np.max(p[4::2])) * float(np.max(base_f)) < 300.0:
        step = False          # step background only matters for large peaks
    npar = len(p)
    lb = np.full(npar, -np.inf)
    ub = np.full(npar, np.inf)
    if free_width:
        lb[2], ub[2] = width_bounds
    else:
        lb[2] = ub[2] = 1.0
    lb[3], ub[3] = 0.0, (0.3 if step else 0.0)
    for j, (c, f) in enumerate(zip(cents, base_f)):
        lb[4 + 2 * j] = 0.0
        lb[5 + 2 * j], ub[5 + 2 * j] = c - 0.6 * f, c + 0.6 * f
    fixed = lb == ub
    xs = x - xm
    R2 = math.sqrt(2.0)

    use_step = ub[3] > 0
    ia = np.arange(4, npar, 2)
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
        m = p[0] + p[1] * xs + a @ EX
        if use_step:
            EC = 0.5 * erfc(T / R2)
            m = m + h * (a @ EC)
        if not want_jac:
            return m, None
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
        return m, J

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
    dof = max(len(x) - int(npar - fixed.sum()), 1)
    chi2r = chi2 / dof
    Jw = J * w[:, None]
    Jw[:, fixed] = 0.0
    try:
        cov = np.linalg.pinv(Jw.T @ Jw) * max(chi2r, 1.0)
    except np.linalg.LinAlgError:
        return None
    sc = p[2]
    cent = np.array([p[5 + 2 * j] for j in range(k)])
    amp = np.array([p[4 + 2 * j] for j in range(k)])
    sig = base_f * sc * F2S
    area = amp * sig * SQRT2PI
    area_unc = np.zeros(k)
    cent_unc = np.zeros(k)
    for j in range(k):
        ia = 4 + 2 * j
        gv = np.zeros(npar)
        gv[ia] = sig[j] * SQRT2PI
        if not fixed[2]:
            gv[2] = amp[j] * base_f[j] * F2S * SQRT2PI
        area_unc[j] = math.sqrt(max(float(gv @ cov @ gv), 0.0))
        cent_unc[j] = math.sqrt(max(float(cov[ia + 1, ia + 1]), 0.0))
    b0f, b1f, hst = p[0], p[1], p[3]
    cents_f, amps_f, sig_f = cent.copy(), amp.copy(), sig.copy()

    def bkg(xx):
        xx = np.asarray(xx, dtype=float)
        out = b0f + b1f * (xx - xm)
        for c, a, s in zip(cents_f, amps_f, sig_f):
            out = out + hst * a * 0.5 * erfc((xx - c) / (s * R2))
        return out

    fit = _Fit(cent, cent_unc, area, area_unc, base_f * sc, bkg, chi2r, lo, hi)
    fit.scale = float(sc)
    fit.at_bound = bool(free_width and (sc >= width_bounds[1] - 1e-6 or sc <= width_bounds[0] + 1e-6))
    return fit


# --------------------------------------------------------------- main entry
def find_peaks(spectrum, min_sig: float = 3.0, fwhm: Optional[float] = None, fit: bool = True,
               min_energy: Optional[float] = None, max_peaks: int = 400, **_ignored) -> list[Peak]:
    """Search, fit and flag peaks.

    min_sig     : significance threshold (net area / its 1-sigma uncertainty); default 3.
    fwhm        : force a constant FWHM (channels) for the search.
    fit         : False returns search results with simple ROI-sum areas (faster).
    min_energy  : ignore peaks below this energy (keV), calibrated spectra only.
    """
    y = np.asarray(spectrum.counts, dtype=float)
    n = len(y)
    if n < 16 or not np.isfinite(y).all() or y.sum() <= 0:
        return []
    y = np.maximum(y, 0.0)
    f0 = spectrum.first_channel
    calibrated = bool(spectrum.energy_coeffs)

    if fwhm is not None and fwhm > 0:
        f = np.full(n, float(fwhm))
        src = "user"
    else:
        f, src = fwhm_model(spectrum, y)
        if src == "none":
            f = _estimate_fwhm_from_data(y)
            src = "data"
    start = _start_index(y, f)
    if min_energy is not None and calibrated:
        e = _poly(spectrum.energy_coeffs, f0 + np.arange(n))
        above = np.nonzero(e >= min_energy)[0]
        start = max(start, int(above[0]) if len(above) else n)
    # refine the model with the strongest isolated peaks of this spectrum
    if src not in ("user",):
        f = _rescale_model(y, f, start)
    model = _Model(f)
    cands = _candidates(y, f, min_sig * 0.8, start)
    if not cands:
        return []
    if len(cands) > max_peaks:
        cands = sorted(sorted(cands, key=lambda c: -c[1])[:max_peaks])
    peaks: list[Peak] = []
    if not fit:
        for c, z in cands:
            peaks.append(_roi_peak(spectrum, y, model, c, z))
        return [p for p in peaks if p.significance >= min_sig]

    # group candidates
    groups: list[list[tuple[float, float]]] = []
    for c, z in cands:
        if groups and c - groups[-1][-1][0] < 3.5 * model.at(c) and len(groups[-1]) < 8:
            groups[-1].append((c, z))
        else:
            groups.append([(c, z)])
    for g in groups:
        peaks.extend(_fit_and_make(spectrum, y, model, [c for c, _ in g], start, min_sig, g))
    peaks.sort(key=lambda p: p.centroid)
    peaks = _dedupe(peaks, model, f0)
    _flag(peaks, spectrum)
    return peaks


def _rescale_model(y, f, start):
    """Scale FWHM model to the widths of strong isolated peaks (median ratio)."""
    cands = _candidates(y, f, 12.0, start)
    if len(cands) < 1:
        return f
    cands = sorted(cands, key=lambda c: -c[1])[:8]
    allc = sorted(c for c, _ in cands)
    m = _Model(f)
    ratios = []
    for c, z in cands:
        fw = m.at(c)
        if any(0 < abs(o - c) < 4 * fw for o in allc):
            continue
        lo, hi = int(max(c - 2.5 * fw, 0)), int(min(c + 2.5 * fw, len(y) - 1))
        r = _fit_group(y, m, [c], lo, hi, free_width=True, step=True, width_bounds=(0.5, 2.0))
        if r is None or r.at_bound or r.chi2r > 20 or r.area_unc[0] <= 0 or r.areas[0] / r.area_unc[0] < 10:
            continue
        ratios.append(r.fwhms[0] / fw)
    if len(ratios) >= 2 or (len(ratios) == 1 and len(cands) <= 3):
        k = float(np.clip(np.median(ratios), 0.5, 2.0))
        if abs(k - 1.0) > 0.08:
            return f * k
    return f


def _estimate_fwhm_from_data(y) -> np.ndarray:
    """Uncalibrated spectrum without FWHM info: fit strong peaks found at several widths."""
    n = len(y)
    pts = []
    for w in (4.0, 2.5, 8.0, 16.0, 32.0):
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
    # keep consistent widths: FWHM^2 = a + b*ch (b >= 0), robust
    c, fw = pts[:, 0], pts[:, 1]
    med = np.median(fw)
    ok = (fw > 0.6 * med) & (fw < 1.6 * med)
    c, fw = c[ok], fw[ok]
    if len(c) >= 3 and np.ptp(c) > n / 4:
        A = np.vstack([np.ones_like(c), c]).T
        sol, *_ = np.linalg.lstsq(A, fw ** 2, rcond=None)
        a, b = sol
        if b >= 0 and a + b * n > 0 and a > 0:
            return np.sqrt(a + b * np.arange(n))
    return np.full(n, float(np.median(fw)))


def _fit_and_make(spectrum, y, model, cents, start, min_sig, zs=()) -> list[Peak]:
    n = len(y)
    fl, fr = model.at(cents[0]), model.at(cents[-1])
    lo = int(max(math.floor(cents[0] - 2.2 * fl), start - 1, 0))
    hi = int(min(math.ceil(cents[-1] + 2.2 * fr), n - 1))
    # free width only where the data constrain it (strong peaks); weak peaks use the model width
    free = sum(y[int(c)] for c in cents) > 200 and max(z for _c, z in zs) > 25 if zs else False
    r = _fit_group(y, model, cents, lo, hi, free_width=free, step=True)
    if r is None:
        return []
    # doublet retry on single peaks with bad fit
    if len(cents) == 1 and r.chi2r > 4.0 and hi - lo > 8:
        x = np.arange(lo, hi + 1)
        g = r.areas[0] / (r.fwhms[0] * F2S * SQRT2PI) * np.exp(
            -0.5 * ((x - r.centroids[0]) / (r.fwhms[0] * F2S)) ** 2)
        res = y[lo:hi + 1] - r.bkg(x) - g
        j = int(np.argmax(res))
        c2 = float(x[j])
        if abs(c2 - r.centroids[0]) > 0.4 * r.fwhms[0]:
            r2 = _fit_group(y, model, sorted([float(r.centroids[0]), c2]), lo, hi, free_width=free, step=True)
            if r2 is not None and r2.chi2r < 0.6 * r.chi2r and np.all(r2.areas > 3 * r2.area_unc) and (
                    min(r2.areas) >= 0.1 * max(r2.areas)
                    or abs(r2.centroids[1] - r2.centroids[0]) >= 1.0 * r2.fwhms[0]):
                # (a weak component very close to a big peak is usually peak tailing, not a doublet)
                r = r2
    out = []
    k = len(r.centroids)
    for j in range(k):
        c = float(r.centroids[j])
        if not (r.lo <= c <= r.hi):
            continue
        area, unc = float(r.areas[j]), float(r.area_unc[j])
        fw = float(r.fwhms[j])
        if area <= 0:
            continue
        if k == 1 and getattr(r, "at_bound", False) and r.scale > 1.3 and area / max(unc, 1e-9) < 30:
            continue   # much broader than the resolution: Compton edge / backscatter hump, not a peak
        roi_l = int(max(math.floor(c - 1.25 * fw), 0))
        roi_r = int(min(math.ceil(c + 1.25 * fw), n - 1))
        xr = np.arange(roi_l, roi_r + 1)
        gross = float(y[roi_l:roi_r + 1].sum())
        bkg = float(np.maximum(r.bkg(xr), 0).sum())
        # Poisson floor for the uncertainty (fit covariance can be optimistic for tiny peaks)
        unc = max(unc, math.sqrt(max(area, 0) + 2.0 * bkg) * 0.7, 1.0)
        sig = area / unc
        if sig < min_sig:
            continue
        out.append(_make_peak(spectrum, c, float(r.cent_unc[j]), fw, area, unc, gross, bkg,
                              roi_l, roi_r, sig, k))
    return out


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

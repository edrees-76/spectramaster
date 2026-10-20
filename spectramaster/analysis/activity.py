"""Activity, specific activity, uncertainty budget and detection limits.

Pure functions, no GUI imports.  Formulas (all uncertainties standard, k = 1)
-----------------------------------------------------------------------------
Per gamma line (energy E, emission probability I as a fraction)::

    A_line = N / (eps(E) * I * t_live * C * D * F_att)
    D      = exp(-lambda * (t_start - t_ref))      decay from the reference (sampling) date to the start
    C      = (1 - exp(-lambda * t_real)) / (lambda * t_real)   decay during counting
    N      = net peak area, minus the live-time-normalised background-spectrum peak
             (peak-by-peak mode, N = N_s - (t_s/t_b) N_b, the background fitted at the sample
             peaks' energies and widths, analysis.background) or measured on the net spectrum
             S - kB with its variance S + k^2 B (full-spectrum mode).  Negative N is kept.
    F_att  = 1 / (self-attenuation correction factor)  (user value, default 1)

    u_rel^2 = u_count^2 + u_eff^2 + u_I^2 + u_mass^2 + u_att^2

Nuclide activity: the chosen key line, or the inverse-variance weighted mean of the lines
(weights fixed from the line uncertainties without the efficiency part; the efficiency
component is treated as fully correlated between lines).  Natural-series parents are
derived from daughters assuming secular equilibrium: A_parent = A_daughter / b
(b = branching, e.g. 0.3594 for Tl-208 in the Th-232 chain).

Specific activity a = A / m (Bq/kg, Bq/L ...); expanded uncertainty U = 2 u.

Detection limits (counts), continuum B under the expected peak region of n channels
(+-1.25 FWHM from the FWHM model), estimated from m channels on each side::

    sigma0^2 = B (1 + n / (2 m)) + k N_b + k^2 u(N_b)^2        (blank variance, peak mode)
    sigma0^2 = B (1 + n / (2 m)) + k^2 B_b (1 + n / (2 m))     (full-spectrum mode, B_b = background
                                                                counts in the window)
    Currie:  L_C = k * sigma0,   L_D = k^2 + 2 L_C   (k = 1.645, alpha = beta = 5 %)
    MDA      = L_D / (f_w * eps * I * t_live * C * D * F_att)   f_w = window fraction of the peak

ISO 11929 (simple formulation, activity domain, w = 1/(eps I t C D F_att)):

    decision threshold  y* = k_{1-a} * w * sigma0
    detection limit     y# = y* + k_{1-b} * sqrt( w^2 (y#/w + sigma0^2) + y#^2 u_rel(w)^2 )  (iterated)

With ISO 11929 the best estimate of the (non-negative) true value and the probabilistically
symmetric coverage interval are also given (ISO 11929-1:2019), from the primary result y
with standard uncertainty u = u(y), omega = Phi(y/u) and the coverage probability 1 - gamma::

    y_hat    = y + u exp(-y^2 / (2 u^2)) / (omega sqrt(2 pi))
    u(y_hat) = sqrt( u^2 - (y_hat - y) y_hat )
    lower    = y - k_p u,  p = omega (1 - gamma/2)       upper = y + k_q u,  q = 1 - omega gamma/2

(k_x = Phi^-1(x); computed in log space so a strongly negative y stays finite).

True-coincidence summing (``options.tcs = {"peak_to_total": [a, b], "pt_rel_unc": u}``): every
line of a cascade emitter in the coincidence table (analysis.coincidence) is divided by its
first-order COI = 1 - sum_j P(j|i) eps_t(E_j) + summing-in of crossover pairs, with eps_p from the
efficiency curve (energies clamped to its range) and eps_t = eps_p / PT,
PT(E) = min(1, a (E/1000)^b) a stated assumption.  u_rel(COI) = summing-out x u / COI is a
"coincidence summing" budget component (correlated between lines).  Gamma-gamma only, no angular
correlation (docs/baseline/tcs_protocol.md).

Reference peak correction (``options.reference_peak``: a pulser, or a fixed reference source
of known rate), for losses the live time does not correct (random summing, pile-up)::

    K = r_exp / r_meas,  r_meas = N_ref / t_live,  r_exp = rate exp(-lambda (t_start - t_ref))
    u_rel(K)^2 = (u(N_ref) / N_ref)^2 + u_rel(rate)^2

K multiplies w (every activity, threshold and MDA); u_rel(K) is a correlated relative component
("reference peak" in the budget).  A reference peak that is not found refuses the calculation.

Reagent blank (``blank=``, the results of a blank sample prepared and counted like the samples,
analysed with the same curve, options and laboratory background), per line::

    A      = A_gross - A_b exp(-lambda (t_ref - t_ref,blank))     (Bq, before dividing by the quantity)
    u_count(A)^2 = u_count(A_gross)^2 + u_count(A_b')^2
    sigma0^2    += (u_count(A_b') f_w / w)^2                       (the blank is part of the null hypothesis)

Efficiency, emission probability and attenuation stay relative to the net value (the same curve,
line and geometry: fully correlated).  A line without a peak in the blank is not corrected (noted).

A nuclide is "detected" when its activity exceeds the decision threshold (Currie L_C or
ISO y*); otherwise "< MDA" is reported.  True-coincidence summing is NOT corrected
(a note is attached to cascade emitters).
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, Union

import numpy as np

from . import coincidence
from .efficiency import (TCS_NUCLIDES, EfficiencyCurve, counting_decay_factor, decay_factor, match_peak)

K_DEFAULT = 1.645

# Default definitions: reported nuclide -> list of (library nuclide, energy keV, factor b).
# factor b = activity of the line's nuclide relative to the reported parent at equilibrium.
KEY_LINES: dict[str, dict] = {
    "Cs-137": {"lines": [("Cs-137", 661.657, 1.0)]},
    "K-40": {"lines": [("K-40", 1460.82, 1.0)]},
    "Cs-134": {"lines": [("Cs-134", 604.721, 1.0), ("Cs-134", 795.864, 1.0)]},
    "Co-60": {"lines": [("Co-60", 1173.228, 1.0), ("Co-60", 1332.492, 1.0)]},
    "I-131": {"lines": [("I-131", 364.489, 1.0)]},
    "Be-7": {"lines": [("Be-7", 477.603, 1.0)]},
    "Am-241": {"lines": [("Am-241", 59.541, 1.0)]},
    "Ra-226": {"lines": [("Pb-214", 351.932, 1.0), ("Bi-214", 609.321, 1.0), ("Pb-214", 295.224, 1.0),
                         ("Bi-214", 1764.491, 1.0)],
               "note": "via Pb-214/Bi-214: assumes Ra-226/Rn-222 equilibrium (sealed container >= 3-4 weeks)"},
    "Th-232": {"lines": [("Ac-228", 911.204, 1.0), ("Pb-212", 238.632, 1.0), ("Tl-208", 583.187, 0.3594),
                         ("Ac-228", 968.971, 1.0)],
               "note": "via Ac-228 (Ra-228) / Pb-212, Tl-208 (Th-228, branching 0.3594): assumes Th-232 series equilibrium"},
    "Ra-228": {"lines": [("Ac-228", 911.204, 1.0), ("Ac-228", 968.971, 1.0)],
               "note": "via Ac-228 (equilibrium Ra-228/Ac-228)"},
    "Th-228": {"lines": [("Pb-212", 238.632, 1.0), ("Tl-208", 583.187, 0.3594)],
               "note": "via Pb-212 / Tl-208 (equilibrium Th-228 daughters)"},
    "U-235": {"lines": [("U-235", 143.76, 1.0), ("U-235", 185.715, 1.0)],
              "note": "185.7 keV interferes with Ra-226 186.2 keV"},
    "Pb-210": {"lines": [("Pb-210", 46.539, 1.0)], "note": "46.5 keV: strong self-attenuation"},
}

DEFAULT_NUCLIDES = ["Cs-137", "K-40", "Ra-226", "Th-232", "Cs-134", "Co-60", "I-131", "Be-7", "Am-241"]

# cascade emitters (true-coincidence summing relevant in close geometries)

UNIT_FACTORS = {"kg": 1.0, "g": 1e-3, "l": 1.0, "ml": 1e-3, "m3": 1.0}   # quantity -> base unit (kg or L)


def _base_unit(unit: str) -> str:
    u = (unit or "").strip().lower()
    return "kg" if u in ("kg", "g") else ("L" if u in ("l", "ml") else ("m3" if u == "m3" else unit))


# ------------------------------------------------------------------ results


@dataclass
class LineResult:
    nuclide: str                 # library nuclide of the line (e.g. "Bi-214")
    energy: float
    intensity: float             # fraction
    factor: float = 1.0          # b: parent activity = line activity / b
    net_area: float = 0.0
    net_unc: float = 0.0
    bkg_peak: float = 0.0        # subtracted background-spectrum peak (scaled)
    continuum: float = 0.0       # B counts under the window
    efficiency: float = 0.0
    eff_rel_unc: float = 0.0
    activity: Optional[float] = None       # parent Bq at reference date
    u_count_rel: float = 0.0
    lc_counts: float = 0.0
    ld_counts: float = 0.0
    decision_threshold: float = 0.0        # Bq (parent)
    mda: float = 0.0                       # Bq (parent)
    detected: bool = False
    peak_found: bool = False
    in_range: bool = True
    int_rel_unc: float = 0.0     # library emission-probability uncertainty of this line (relative)
    coi: float = 1.0             # true-coincidence summing factor (observed / summing-free), divided out
    coi_rel_unc: float = 0.0
    coi_applied: bool = False    # the line was corrected for true-coincidence summing
    blank_activity: Optional[float] = None  # reagent blank subtracted, Bq (parent) at the reference date
    blank_unc: float = 0.0                  # its counting standard uncertainty, Bq
    gross_activity: Optional[float] = None  # activity before the blank correction
    note: str = ""


@dataclass
class NuclideResult:
    nuclide: str
    lines: list[LineResult] = field(default_factory=list)
    key_energy: Optional[float] = None
    method: str = "key"
    activity: Optional[float] = None       # Bq at reference date
    u: Optional[float] = None              # k=1, Bq
    budget: dict = field(default_factory=dict)   # component -> relative % (k=1)
    used_energies: list[float] = field(default_factory=list)   # lines entering the value
    decision_threshold: float = 0.0        # Bq
    mda: float = 0.0                       # Bq
    detected: bool = False
    specific: Optional[float] = None       # Bq/unit
    specific_u: Optional[float] = None     # k=1
    specific_mda: Optional[float] = None
    unit: str = ""
    half_life_s: Optional[float] = None
    note: str = ""
    # ISO 11929 only (mda_method "iso11929"): best estimate, its standard uncertainty and the
    # coverage interval (probability ActivityOptions.coverage), in Bq and in the specific unit
    best_estimate: Optional[float] = None
    best_u: Optional[float] = None
    coverage_low: Optional[float] = None
    coverage_high: Optional[float] = None
    specific_best: Optional[float] = None
    specific_best_u: Optional[float] = None
    specific_low: Optional[float] = None
    specific_high: Optional[float] = None

    @property
    def U(self) -> Optional[float]:
        return None if self.u is None else 2.0 * self.u

    @property
    def specific_U(self) -> Optional[float]:
        return None if self.specific_u is None else 2.0 * self.specific_u

    @property
    def decision(self) -> str:
        return "detected" if self.detected else "< MDA"

    @property
    def lines_text(self) -> str:
        es = self.used_energies or ([self.key_energy] if self.key_energy is not None else [])
        return ", ".join(f"{e:.1f}" for e in es)

    @property
    def net_area(self) -> Optional[float]:
        k = self.key_line
        return k.net_area if k else None

    @property
    def key_line(self) -> Optional[LineResult]:
        return next((l for l in self.lines if self.key_energy is not None and abs(l.energy - self.key_energy) < 1e-6),
                    self.lines[0] if self.lines else None)


@dataclass
class ActivityOptions:
    nuclides: Sequence[str] = tuple(DEFAULT_NUCLIDES)
    method: str = "key"                  # "key" | "mean"
    key_lines: dict = field(default_factory=dict)   # nuclide -> energy override
    ref_date: Optional[datetime] = None  # None = acquisition start
    quantity: Optional[float] = None
    quantity_unit: str = "kg"
    quantity_rel_unc: float = 0.0        # fraction
    attenuation: Union[float, dict] = 1.0   # correction factor(s) (multiplies the activity), per nuclide dict ok
    attenuation_rel_unc: float = 0.0
    intensity_rel_unc: float = 0.0       # optional extra; each line's library (ENSDF) uncertainty is added
    bkg_mode: str = "peak"               # "peak" | "spectrum"
    mda_method: str = "currie"           # "currie" | "iso11929"
    k_alpha: float = K_DEFAULT
    k_beta: float = K_DEFAULT
    coverage: float = 0.95               # ISO 11929 coverage interval probability 1 - gamma
    min_sig: float = 3.0
    min_intensity_pct: float = 1.0       # generic nuclides: lines used
    geometry: Optional[object] = None    # lab.detector.MeasurementGeometry of the sample
    allow_geometry_mismatch: bool = False    # use an incompatible calibration anyway (reported)
    # reference peak correction: {"energy": keV, "rate": cps, "rate_rel_unc": fraction,
    # "half_life_s": s or None (pulser), "ref_date": datetime of the rate or None}
    reference_peak: Optional[dict] = None
    # true-coincidence summing: {"peak_to_total": [a, b], "pt_rel_unc": fraction}, PT(E) = min(1, a (E/1000)^b)
    tcs: Optional[dict] = None


@dataclass
class QuantResults:
    """Everything a report needs (``MainWindow.quant_results``)."""
    sample: str
    source_path: str
    start_time: Optional[datetime]
    live_time: float
    real_time: Optional[float]
    ref_date: Optional[datetime]
    curve_name: str
    curve_model: str
    background: str
    options: ActivityOptions
    nuclides: list[NuclideResult]
    notes: list[str] = field(default_factory=list)
    blank: str = ""                      # reagent blank sample (empty: no blank correction)
    reference_factor: Optional[float] = None    # reference peak correction K (None: not applied)
    reference_u_rel: float = 0.0

    def rows(self) -> list[dict]:
        return [result_row(r) for r in self.nuclides]

    @classmethod
    def from_dict(cls, d: dict) -> "QuantResults":
        """Rebuild stored results (``lab.session.quant_to_dict``) exactly as saved - nothing is
        recalculated; unknown keys are ignored (forward-tolerant)."""
        import dataclasses

        def known(c, x):
            names = {f.name for f in dataclasses.fields(c)}
            return {k: v for k, v in (x or {}).items() if k in names}

        def when(v):
            return datetime.fromisoformat(v) if isinstance(v, str) and v else None

        o = known(ActivityOptions, d.get("options"))
        if o.get("ref_date"):
            o["ref_date"] = when(o["ref_date"])
        if isinstance(o.get("geometry"), dict):
            from ..lab.detector import MeasurementGeometry
            o["geometry"] = MeasurementGeometry.from_dict(o["geometry"])
        if "nuclides" in o:
            o["nuclides"] = tuple(o["nuclides"])
        nucl = []
        for n in d.get("nuclides") or []:
            kw = known(NuclideResult, n)
            kw["lines"] = [LineResult(**known(LineResult, ln)) for ln in n.get("lines") or []]
            nucl.append(NuclideResult(**kw))
        top = known(cls, d)
        top.update(start_time=when(d.get("start_time")), ref_date=when(d.get("ref_date")),
                   options=ActivityOptions(**o), nuclides=nucl, notes=list(d.get("notes") or []))
        for k in ("sample", "source_path", "curve_name", "curve_model", "background", "blank"):
            top.setdefault(k, "")
        top.setdefault("live_time", 0.0)
        top.setdefault("real_time", None)
        return cls(**top)


# ------------------------------------------------------------------ helpers


def _channel_of_energy(spectrum, energy: float) -> Optional[float]:
    e = np.asarray(spectrum.energies(), dtype=float)
    if len(e) < 2 or not (min(e[0], e[-1]) <= energy <= max(e[0], e[-1])):
        return None
    if e[-1] < e[0]:
        e = e[::-1]
        return float(len(e) - 1 - np.interp(energy, e, np.arange(len(e))))
    return float(np.interp(energy, e, np.arange(len(e))))


def continuum_under(spectrum, energy: float, fwhm_ch: np.ndarray, counts=None
                    ) -> Optional[tuple[float, int, int, float]]:
    """(B, n, m, window_fraction) for the region E +- 1.25 FWHM; m side channels each side."""
    idx = _channel_of_energy(spectrum, energy)
    if idx is None:
        return None
    y = np.asarray(spectrum.counts if counts is None else counts, dtype=float)
    fw = float(fwhm_ch[int(min(max(round(idx), 0), len(fwhm_ch) - 1))])
    half = max(1.25 * fw, 1.0)
    lo, hi = int(math.floor(idx - half + 0.5)), int(math.floor(idx + half + 0.5))
    m = max(2, int(round(1.5 * fw)))
    if lo - m < 0 or hi + m >= len(y):
        return None
    n = hi - lo + 1
    side = float(y[lo - m:lo].sum() + y[hi + 1:hi + 1 + m].sum())
    b = max(side * n / (2.0 * m), 0.0)
    s = fw / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    r2 = s * math.sqrt(2.0)
    frac = 0.5 * (math.erf((idx - (lo - 0.5)) / r2) + math.erf((hi + 0.5 - idx) / r2))
    return b, n, m, min(max(frac, 0.5), 1.0)


def currie_limits(sigma0: float, k_alpha: float = K_DEFAULT, k_beta: float = K_DEFAULT) -> tuple[float, float]:
    """(L_C, L_D) in counts from the blank standard deviation sigma0."""
    lc = k_alpha * sigma0
    if abs(k_alpha - k_beta) < 1e-12:
        return lc, k_beta ** 2 + 2.0 * lc
    # general Currie: L_D = L_C + k_b sqrt(L_D + sigma0^2) (solve quadratic)
    a = k_beta ** 2
    ld = lc + (a + math.sqrt(a * a + 4 * a * (lc + sigma0 ** 2))) / 2.0
    return lc, ld


def iso11929_limits(sigma0: float, w: float, w_rel_unc: float, k_alpha: float = K_DEFAULT,
                    k_beta: float = K_DEFAULT) -> tuple[float, float]:
    """(decision threshold y*, detection limit y#) in activity units (simple formulation)."""
    ys = k_alpha * w * sigma0
    yd = 2.0 * ys if ys > 0 else w * k_beta ** 2
    for _ in range(200):
        u = math.sqrt(w * w * (yd / w + sigma0 ** 2) + (yd * w_rel_unc) ** 2)
        new = ys + k_beta * u
        if abs(new - yd) < 1e-12 * max(new, 1e-300):
            yd = new
            break
        yd = new
    if k_beta * w_rel_unc >= 1:
        yd = float("inf")
    return ys, yd


def iso11929_best_estimate(y: Optional[float], u: Optional[float], coverage: float = 0.95
                           ) -> Optional[tuple[float, float, float, float]]:
    """(best estimate, its standard uncertainty, lower, upper) of a non-negative measurand from
    the primary result `y` with standard uncertainty `u` (ISO 11929-1:2019, probabilistically
    symmetric coverage interval of probability `coverage`).  None when y or u is unusable."""
    if y is None or u is None or not (math.isfinite(y) and math.isfinite(u)) or u <= 0:
        return None
    if not 0.0 < coverage < 1.0:
        raise ValueError(f"coverage probability must be between 0 and 1, not {coverage}")
    from scipy.special import log_ndtr, ndtri_exp
    gamma = 1.0 - coverage
    x = y / u
    log_omega = float(log_ndtr(x))                      # ln Phi(y/u), finite for strongly negative y
    # phi(x) / Phi(x) without underflow
    ratio = math.exp(-0.5 * x * x - 0.5 * math.log(2.0 * math.pi) - log_omega)
    best = y + u * ratio
    u_best = math.sqrt(max(u * u - (best - y) * best, 0.0))
    k_p = float(ndtri_exp(log_omega + math.log1p(-gamma / 2.0)))
    k_q = -float(ndtri_exp(log_omega + math.log(gamma / 2.0)))     # Phi^-1(1 - omega gamma / 2)
    lower = max(y - k_p * u, 0.0)                       # >= 0 analytically; clip rounding only
    upper = y + k_q * u
    return best, u_best, lower, upper


def nuclide_lines(name: str, curve: Optional[EfficiencyCurve] = None, min_intensity_pct: float = 1.0
                  ) -> tuple[list[tuple[str, float, float, float]], str]:
    """[(line nuclide, energy, intensity fraction, factor)] and a note for a reported nuclide."""
    from .library import load_library
    lib = load_library()
    if name in KEY_LINES:
        out = []
        for ln, e, b in KEY_LINES[name]["lines"]:
            nd = lib.get(ln)
            if nd is None:
                continue
            l = min(nd.lines, key=lambda q: abs(q.energy - e))
            if abs(l.energy - e) < 1.0:
                out.append((ln, l.energy, l.intensity / 100.0, b))
        return out, KEY_LINES[name].get("note", "")
    nd = lib.get(name)
    if nd is None:
        raise KeyError(f"{name}: not in the nuclide library")
    lines = [l for l in nd.gammas(min_intensity_pct) if l.energy >= 30.0]
    if curve is not None:
        inr = [l for l in lines if curve.in_range(l.energy, 0.1)]
        lines = inr or lines
    lines.sort(key=lambda l: -l.intensity * (curve.efficiency(l.energy) if curve else 1.0))
    return [(name, l.energy, l.intensity / 100.0, 1.0) for l in lines[:6]], ""


def _half_life(name: str) -> Optional[float]:
    from .library import load_library
    nd = load_library().get(name)
    return nd.half_life_s if nd else None


def _as_float(v) -> float:
    return float(v) if v is not None else 0.0


# ------------------------------------------------------------------ main entry


def calibration_checks(curve: EfficiencyCurve, opt: "ActivityOptions") -> list[str]:
    """Notes on the efficiency calibration used; raises ValueError for a calibration of an
    incompatible geometry unless ``opt.allow_geometry_mismatch``."""
    out = []
    status = getattr(curve, "validation_status", "") or "unvalidated"
    if status != "validated":
        out.append(f"efficiency calibration {status}: not independently validated")
    rec = getattr(curve, "geometry_record", None) or {}
    if opt.geometry is not None and rec:
        from ..lab.detector import MeasurementGeometry
        reasons = MeasurementGeometry.from_dict(rec).compatibility(opt.geometry)
        if reasons:
            text = "; ".join(reasons)
            if not opt.allow_geometry_mismatch:
                raise ValueError("the efficiency calibration belongs to another measurement geometry "
                                 f"({rec.get('name', '?')} vs {opt.geometry.name}): {text}")
            out.append(f"geometry mismatch accepted by the user ({rec.get('name', '?')} vs "
                       f"{opt.geometry.name}): {text}")
    elif opt.geometry is not None:
        out.append("calibration geometry not recorded: compatibility with the sample geometry not checked")
    elif rec:
        out.append(f"sample geometry not given: compatibility with the calibration geometry "
                   f"({rec.get('name', '?')}) not checked")
    return out


def compute_activities(spectrum, curve: EfficiencyCurve, options: Optional[ActivityOptions] = None,
                       background=None, peaks=None, bkg_peaks=None,
                       blank: Optional["QuantResults"] = None) -> QuantResults:
    """Activities / MDAs for ``options.nuclides`` in ``spectrum`` (see module docstring).
    ``blank``: results of the reagent blank (:func:`compute_activities` on the blank sample)."""
    from .peaks import find_peaks, fwhm_model
    opt = options or ActivityOptions()
    if not spectrum.energy_coeffs:
        raise ValueError("the spectrum has no energy calibration")
    if not spectrum.live_time:
        raise ValueError("the spectrum has no live time")
    t_live = float(spectrum.live_time)
    t_real = float(spectrum.real_time or spectrum.live_time)
    ref = opt.ref_date or spectrum.start_time
    notes: list[str] = []
    notes.extend(calibration_checks(curve, opt))
    k_b = 0.0
    work = spectrum
    net_var = None          # full-spectrum mode: variance S + k^2 B of the net channels
    bcounts = None          # full-spectrum mode: background counts on the sample grid
    bfit = None             # peak mode: background fitted at the sample peaks
    bkg_under: dict = {}
    from .background import SUBTRACTED, BackgroundFitter, check_not_subtracted, compatibility, net_spectrum
    if background is not None:
        check_not_subtracted(spectrum)
        if not background.live_time:
            raise ValueError("the background spectrum has no live time")
        notes.extend(compatibility(spectrum, background))
        k_b = t_live / float(background.live_time)
        if opt.bkg_mode == "spectrum":
            from ..tools.arithmetic import align_to, same_calibration
            work, net_var, _k = net_spectrum(spectrum, background)
            bal = background if same_calibration(spectrum, background) else align_to(background, spectrum)
            bcounts = np.clip(np.asarray(bal.counts, dtype=float), 0, None)
            peaks = find_peaks(work, min_sig=opt.min_sig, variance=net_var)
        elif bkg_peaks is None:
            bfit = BackgroundFitter(spectrum, background)
            if bfit.note:
                notes.append(bfit.note)
    elif (spectrum.extra or {}).get("operation") == SUBTRACTED:
        notes.append("the spectrum is background subtracted: its counts are treated as Poisson, which "
                     "underestimates the uncertainties; analyse the sample with the background instead")
    fit_report = None
    if peaks is None:
        from .peaks import FitReport
        fit_report = FitReport() if bfit is not None else None
        peaks = find_peaks(work, min_sig=opt.min_sig, report=fit_report)
    if bfit is not None:
        bkg_under = bfit.under_peaks(peaks, fit_report)
    y = np.asarray(spectrum.counts, dtype=float)
    fw_ch, _src = fwhm_model(spectrum, y)
    if spectrum.start_time is None and opt.ref_date is not None:
        notes.append("acquisition start unknown: no decay correction")
    dt = (spectrum.start_time - ref).total_seconds() if (spectrum.start_time and ref) else 0.0
    ref_k, ref_u = 1.0, 0.0
    if opt.reference_peak:
        ref_k, ref_u, note = reference_correction(spectrum, peaks, opt.reference_peak, t_live)
        notes.append(note)
    tcs_on = bool(opt.tcs)
    if tcs_on:
        pa, pb = (float(v) for v in opt.tcs["peak_to_total"])
        if not pa > 0:
            raise ValueError("true-coincidence summing: the peak-to-total ratio must be positive")
        tcs_u = float(opt.tcs.get("pt_rel_unc") or 0.0)
        tcs_pt = lambda en: coincidence.peak_to_total(en, pa, pb)                    # noqa: E731
        eps_peak = lambda en: np.clip(curve.efficiency(np.clip(np.asarray(en, dtype=float),     # noqa: E731
                                                               curve.e_min, curve.e_max)), 0.0, 1.0)
        notes.append(f"true-coincidence summing corrected (first order, gamma-gamma, no angular correlation): "
                     f"peak-to-total PT(E) = min(1, {pa:g} (E/1000 keV)^{pb:g}) +- {100 * tcs_u:g} % (assumed), "
                     "efficiencies of the curve clamped to its range")
    blank_dt = 0.0          # seconds from the blank's reference date to the sample's
    if blank is not None:
        notes.extend(_blank_checks(blank, curve, opt))
        if blank.ref_date is not None and ref is not None:
            blank_dt = (ref - blank.ref_date).total_seconds()
        elif blank.ref_date is not None or ref is not None:
            notes.append("reagent blank: a reference date is unknown, no decay correction of the blank")

    used_peaks: dict[int, list[str]] = {}
    results = []
    for name in opt.nuclides:
        name = name.strip()
        if not name:
            continue
        try:
            lines, note = nuclide_lines(name, curve, opt.min_intensity_pct)
        except KeyError as exc:
            results.append(NuclideResult(nuclide=name, note=str(exc).strip("'\"")))
            continue
        hl = _half_life(name)
        D =decay_factor(hl, dt)
        C = counting_decay_factor(hl, t_real)
        att = opt.attenuation.get(name, 1.0) if isinstance(opt.attenuation, dict) else float(opt.attenuation or 1.0)
        res = NuclideResult(nuclide=name, method=opt.method, half_life_s=hl, note=note)
        if D < 1e-3:
            res.note = (res.note + f"; decay correction factor {1 / D:.3g} - check the reference date "
                        "and parent/daughter equilibrium").strip("; ")
        for ln_name, e, inten, b in lines:
            lr = LineResult(ln_name, e, inten, b)
            lr.int_rel_unc = _line_int_unc(ln_name, e)
            eff = float(curve.efficiency(e))
            lr.efficiency = eff
            lr.eff_rel_unc = float(curve.rel_uncertainty(e))
            lr.in_range = curve.in_range(e)
            if not lr.in_range:
                lr.note = "efficiency extrapolated"
            w = ref_k * att / (eff * inten * t_live * C * D) / b       # Bq (parent) per net count
            if tcs_on:
                c = coincidence.coi(ln_name, e, eps_peak, tcs_pt)
                if c.found and c.factor > 0:
                    lr.coi = c.factor
                    lr.coi_applied = True
                    lr.coi_rel_unc = c.summing_out * tcs_u / c.factor
                    w /= c.factor
            # blank (continuum) under the expected peak
            cu = continuum_under(spectrum, e, fw_ch)
            if cu is None:
                lr.note = (lr.note + "; outside spectrum").strip("; ")
                res.lines.append(lr)
                continue
            B, n, m, fwin = cu
            lr.continuum = B
            var0 = B * (1.0 + n / (2.0 * m))
            p = match_peak(peaks, e)
            bnet = None           # (k N_b, k u_b) under this line
            if bfit is not None:
                if p is not None:
                    bnet = bkg_under.get(id(p))
                else:
                    idx = _channel_of_energy(spectrum, e)
                    if idx is not None:
                        bnet = bfit.at_energy(idx, float(fw_ch[int(min(max(round(idx), 0), len(fw_ch) - 1))]))
            elif bkg_peaks and opt.bkg_mode == "peak":      # legacy: caller-supplied background peaks
                bp = match_peak(bkg_peaks, e)
                if bp is not None:
                    bnet = (k_b * bp.net_area, k_b * bp.net_area_unc)
            if bnet is not None:
                lr.bkg_peak = bnet[0]
                var0 += max(bnet[0], 0.0) + bnet[1] ** 2
            blank_counts = 0.0
            if blank is not None:
                bl = _blank_line(blank, name, e)
                if bl is None:
                    lr.note = (lr.note + "; not corrected for the blank (no peak in the blank)").strip("; ")
                else:
                    kd = decay_factor(hl, blank_dt)
                    lr.blank_activity = bl.activity * kd
                    lr.blank_unc = abs(bl.activity) * bl.u_count_rel * kd
                    blank_counts = lr.blank_activity / w
                    var0 += (lr.blank_unc * fwin / w) ** 2
            if bcounts is not None:
                cb = continuum_under(spectrum, e, fw_ch, counts=bcounts)
                if cb is not None:
                    idx = _channel_of_energy(spectrum, e)
                    h = max(1, int(round(1.25 * fw_ch[int(round(idx))])))
                    bwin = float(bcounts[max(0, int(round(idx)) - h):int(round(idx)) + h + 1].sum())
                    var0 += k_b ** 2 * bwin * (1.0 + cb[1] / (2.0 * cb[2]))
            sigma0 = math.sqrt(max(var0, 0.0))
            w_rel = math.sqrt(lr.eff_rel_unc ** 2 + opt.intensity_rel_unc ** 2 + lr.int_rel_unc ** 2
                              + opt.attenuation_rel_unc ** 2 + ref_u ** 2 + lr.coi_rel_unc ** 2)
            if opt.mda_method == "iso11929":
                ys, yd = iso11929_limits(sigma0, w / fwin, w_rel, opt.k_alpha, opt.k_beta)
                lr.lc_counts, lr.ld_counts = ys / w * fwin, yd / w * fwin
                lr.decision_threshold, lr.mda = ys, yd
            else:
                lc, ld = currie_limits(sigma0, opt.k_alpha, opt.k_beta)
                lr.lc_counts, lr.ld_counts = lc, ld
                lr.decision_threshold, lr.mda = lc * w / fwin, ld * w / fwin
            if p is not None:
                lr.peak_found = True
                nnet, unet = float(p.net_area), float(p.net_area_unc)
                if bnet is not None:          # not clipped: a negative net area is kept
                    nnet -= bnet[0]
                    unet = math.hypot(unet, bnet[1])
                lr.net_area, lr.net_unc = nnet, unet
                used_peaks.setdefault(id(p), []).append(name)
                lr.activity = nnet * w
                lr.u_count_rel = unet / abs(nnet) if nnet else float("inf")
                if lr.blank_activity is not None:
                    lr.gross_activity = lr.activity
                    nnet -= blank_counts
                    unet = math.hypot(unet, lr.blank_unc / w)
                    lr.activity = nnet * w
                    lr.u_count_rel = unet / abs(nnet) if nnet else float("inf")
                lr.detected = nnet > lr.lc_counts
            else:
                lr.note = (lr.note + "; no peak").strip("; ")
            res.lines.append(lr)
        _combine(res, opt, ref_u)
        results.append(res)
    # shared peaks
    shared: dict[str, set] = {}
    for names in used_peaks.values():
        for n in set(names):
            shared.setdefault(n, set()).update(set(names) - {n})
    for r in results:
        if shared.get(r.nuclide):
            r.note = (r.note + "; peak shared with " + ", ".join(sorted(shared[r.nuclide]))).strip("; ")
    # specific activity
    q = opt.quantity
    unit = _base_unit(opt.quantity_unit)
    for r in results:
        corrected = [l for l in r.lines if l.coi_applied]
        if corrected:
            k = r.key_line
            r.note = (r.note + "; true-coincidence summing corrected"
                      + (f" (COI {k.coi:.4f} at {k.energy:g} keV)" if k is not None and k.coi_applied else "")).strip("; ")
        elif r.nuclide in TCS_NUCLIDES:
            r.note = (r.note + "; true-coincidence summing not corrected").strip("; ")
        if q and q > 0:
            qb = q * UNIT_FACTORS.get((opt.quantity_unit or "").lower(), 1.0)
            r.unit = f"Bq/{unit}"
            if r.activity is not None:
                r.specific = r.activity / qb
                # u(a/q)/(a/q) = sqrt(u_rel(a)^2 + u_rel(q)^2): quantity uncertainty added here only
                r.specific_u = math.hypot((r.u or 0.0) / qb, abs(r.specific) * opt.quantity_rel_unc)
            r.specific_mda = r.mda / qb if r.mda else None
        if opt.mda_method == "iso11929":
            be = iso11929_best_estimate(r.activity, r.u, opt.coverage)
            if be is not None:
                r.best_estimate, r.best_u, r.coverage_low, r.coverage_high = be
            be = iso11929_best_estimate(r.specific, r.specific_u, opt.coverage)
            if be is not None:
                r.specific_best, r.specific_best_u, r.specific_low, r.specific_high = be
    if background is not None:
        notes.append(f"background: {background.source_path or background.sample_id or '?'} "
                     f"({'peak-by-peak' if opt.bkg_mode == 'peak' else 'full spectrum'}, k = {k_b:.4g})")
    blank_name = ""
    if blank is not None:
        blank_name = blank.source_path or blank.sample or "?"
        notes.append(f"reagent blank subtracted: {blank_name}")
    return QuantResults(sample=spectrum.sample_id, source_path=spectrum.source_path,
                        start_time=spectrum.start_time, live_time=t_live, real_time=spectrum.real_time,
                        ref_date=ref, curve_name=curve.name or curve.geometry, curve_model=curve.describe(),
                        background=(background.source_path or background.sample_id) if background is not None else "",
                        options=opt, nuclides=results, notes=notes, blank=blank_name,
                        reference_factor=ref_k if opt.reference_peak else None, reference_u_rel=ref_u)


def reference_rate(spectrum, energy: float, min_sig: float = 3.0) -> tuple[float, float]:
    """(rate, standard uncertainty) in counts per live second of the peak at `energy` in a
    reference (low-rate) measurement of a fixed reference source."""
    from .peaks import find_peaks
    if not spectrum.live_time:
        raise ValueError("the reference spectrum has no live time")
    p = match_peak(find_peaks(spectrum, min_sig=min_sig), energy)
    if p is None:
        raise ValueError(f"reference peak at {energy:g} keV not found in the reference spectrum")
    t = float(spectrum.live_time)
    return float(p.net_area) / t, float(p.net_area_unc) / t


def reference_correction(spectrum, peaks, ref: dict, t_live: float) -> tuple[float, float, str]:
    """(K, u_rel(K), note) of the reference peak correction (module docstring)."""
    energy = float(ref["energy"])
    rate = float(ref["rate"])
    if rate <= 0:
        raise ValueError("reference peak correction: the expected rate must be positive")
    p = match_peak(peaks, energy)
    if p is None:
        raise ValueError(f"reference peak at {energy:g} keV not found: the reference peak correction "
                         "cannot be applied")
    hl, t_ref = ref.get("half_life_s"), ref.get("ref_date")
    if hl and t_ref is not None and spectrum.start_time is not None:
        rate *= decay_factor(float(hl), (spectrum.start_time - t_ref).total_seconds())
    measured = float(p.net_area) / t_live
    k = rate / measured
    u = math.hypot(float(p.net_area_unc) / float(p.net_area), float(ref.get("rate_rel_unc") or 0.0))
    note = (f"reference peak correction at {energy:g} keV: expected {rate:.5g} cps, measured {measured:.5g} cps, "
            f"K = {k:.4f} +- {100 * u:.2f} %")
    return k, u, note


def _blank_line(blank: "QuantResults", nuclide: str, energy: float) -> Optional[LineResult]:
    """The blank's result for this nuclide's line (a peak was found in the blank), or None."""
    for r in blank.nuclides:
        if r.nuclide != nuclide:
            continue
        for ln in r.lines:
            if abs(ln.energy - energy) < 0.05 and ln.peak_found and ln.activity is not None:
                return ln
    return None


def _blank_checks(blank: "QuantResults", curve: EfficiencyCurve, opt: ActivityOptions) -> list[str]:
    """Warnings when the blank was not analysed like the sample."""
    out = []
    name = curve.name or curve.geometry
    if blank.curve_name and name and blank.curve_name != name:
        out.append(f"reagent blank analysed with another efficiency curve ({blank.curve_name})")
    if blank.blank:
        out.append("the reagent blank's results are themselves blank-corrected")
    missing = [n for n in opt.nuclides if n.strip() and not any(r.nuclide == n.strip() for r in blank.nuclides)]
    if missing:
        out.append("not analysed in the reagent blank: " + ", ".join(missing))
    return out


def _combine(res: NuclideResult, opt: ActivityOptions, ref_u: float = 0.0) -> None:
    lines = [l for l in res.lines if l.mda > 0]
    if not lines:
        res.note = (res.note + "; no usable line").strip("; ")
        return
    want = opt.key_lines.get(res.nuclide)
    if want is not None:
        key = min(lines, key=lambda l: abs(l.energy - float(want)))
    else:
        found = [l for l in lines if l.activity is not None and l.detected]
        if res.nuclide in KEY_LINES:
            key = found[0] if found else lines[0]
        else:
            key = min(found or lines, key=lambda l: l.mda)
    res.key_energy = key.energy
    ui, ua, um = opt.intensity_rel_unc, opt.attenuation_rel_unc, opt.quantity_rel_unc
    ut = 0.0
    if opt.method == "mean":
        cand = [l for l in lines if l.activity is not None and l.detected and l.net_area > 0]
        if not cand:
            cand = [key] if key.activity is not None else []
    else:
        cand = [key] if key.activity is not None else []
    res.mda = key.mda
    res.decision_threshold = key.decision_threshold
    if not cand:
        res.detected = False
        return
    res.used_energies = [l.energy for l in cand]
    if len(cand) == 1:
        l = cand[0]
        a = l.activity
        uc, ue = abs(a) * l.u_count_rel, abs(a) * l.eff_rel_unc
        ul = abs(a) * l.int_rel_unc
        ut = abs(a) * l.coi_rel_unc
        res.detected = l.detected
    else:
        # weights from the uncorrelated part (counting + intensity, incl. each line's library
        # emission-probability uncertainty)
        var_unc = [(l.activity * l.u_count_rel) ** 2 + (l.activity * ui) ** 2 + (l.activity * l.int_rel_unc) ** 2
                   for l in cand]
        wts = [1.0 / v if v > 0 else 0.0 for v in var_unc]
        sw = sum(wts)
        a = sum(w * l.activity for w, l in zip(wts, cand)) / sw
        uc = math.sqrt(sum((w * l.activity * l.u_count_rel) ** 2 for w, l in zip(wts, cand))) / sw
        ul = math.sqrt(sum((w * l.activity * l.int_rel_unc) ** 2 for w, l in zip(wts, cand))) / sw
        ue = sum(w * abs(l.activity) * l.eff_rel_unc for w, l in zip(wts, cand)) / sw
        ut = sum(w * abs(l.activity) * l.coi_rel_unc for w, l in zip(wts, cand)) / sw   # P/T: correlated
        # decision threshold of the combination
        s0 = [l.decision_threshold / opt.k_alpha for l in cand]
        res.decision_threshold = opt.k_alpha / math.sqrt(sum(1.0 / (s * s) for s in s0 if s > 0))
        res.mda = min(l.mda for l in cand)
        res.detected = a > res.decision_threshold
        chi2 = sum((l.activity - a) ** 2 / v for l, v in zip(cand, var_unc) if v > 0)
        if chi2 / (len(cand) - 1) > 4.0:
            res.note = (res.note + f"; lines inconsistent (chi2/dof = {chi2 / (len(cand) - 1):.1f})").strip("; ")
    a_abs = abs(a) if a else 0.0
    # Budget of the activity in Bq.  The mass/volume uncertainty does not belong here: it only
    # enters the specific activity (Bq/kg, Bq/L, ...), see compute_activities.
    comp = {"counting": uc, "efficiency": ue, "intensity": math.hypot(a_abs * ui, ul), "attenuation": a_abs * ua}
    if ref_u:
        comp["reference peak"] = a_abs * ref_u
    if ut:
        comp["coincidence summing"] = ut
    res.activity = a
    res.u = math.sqrt(sum(v * v for v in comp.values()))
    res.budget = {k: (100.0 * v / a_abs if a_abs else 0.0) for k, v in comp.items()}


def _line_int_unc(nuclide: str, energy: float) -> float:
    """Relative emission-probability uncertainty of a library line (0 when not stated)."""
    from .library import intensity_rel_unc
    try:
        return float(intensity_rel_unc(nuclide, energy) or 0.0)
    except Exception:
        return 0.0


# ------------------------------------------------------------------ table / export

ROW_KEYS = ["nuclide", "lines", "net_area", "net_unc", "activity_bq", "u_bq", "specific", "specific_U2",
            "unit", "mda_bq", "mda_specific", "decision", "best_bq", "best_u_bq", "coverage_low_bq",
            "coverage_high_bq", "best_specific", "best_u_specific", "coverage_low_specific",
            "coverage_high_specific", "blank_bq", "blank_u_bq", "budget", "note"]


def sampling_decay_factor(half_life_s: Optional[float], sampling_s: Optional[float]) -> float:
    """K = lambda t_s / (1 - exp(-lambda t_s)): mean air concentration over a sampling time t_s
    from the activity on the filter at the END of sampling (constant concentration assumed)."""
    if not half_life_s or not sampling_s or sampling_s <= 0:
        return 1.0
    x = math.log(2.0) / half_life_s * sampling_s
    return x / (-math.expm1(-x)) if x > 1e-9 else 1.0


def concentrations(res: "QuantResults", sample, unit: str, quantity_rel_unc: float = 0.0) -> dict:
    """Express the activities of `res` in `unit` ("Bq", "Bq/kg", "Bq/L", "Bq/m3") with the
    sample information `sample` (lab.sample.SampleInfo).

    Nothing is computed when an input is missing: ``{"missing": [...], "rows": []}`` - a
    missing mass is never 1 kg.  Bq/kg is labelled with its basis ("Bq/kg (dry)").  Bq/m3:
    C = A_end K / (V f eta) with A_end the activity at the END of sampling (the results are
    decay-corrected from their reference date), K = sampling_decay_factor, f the measured filter
    fraction and eta the stated collection efficiency (an assumption, reported as such).
    ``quantity_rel_unc`` is the relative uncertainty of the mass / volume / air volume; it is
    added to the activity's relative uncertainty in quadrature (not to the MDA).  A nuclide not
    detected is reported as "< MDA" in the same unit, never as zero.
    """
    missing = sample.concentration_unit_inputs(unit)
    out = {"unit": unit, "missing": missing, "rows": [], "notes": []}
    if missing:
        out["notes"].append("concentration not computed: missing " + "; ".join(missing))
        return out
    label = unit
    notes = out["notes"]
    if res.reference_factor is not None:
        notes.append(f"reference peak correction K = {res.reference_factor:.4f} +- "
                     f"{100 * res.reference_u_rel:.2f} % applied to every result")
    tcs = getattr(res.options, "tcs", None)
    if tcs and any(l.coi_applied for r in res.nuclides for l in r.lines):
        a, b = tcs["peak_to_total"]
        notes.append(f"true-coincidence summing corrected (first order, gamma-gamma) with an assumed "
                     f"peak-to-total PT(E) = min(1, {a:g} (E/1000 keV)^{b:g}) +- "
                     f"{100 * float(tcs.get('pt_rel_unc') or 0):g} %")
    if unit == "Bq":
        q = 1.0
    elif unit == "Bq/kg":
        q = sample.mass_kg
        label = f"Bq/kg ({sample.mass_basis})"
    elif unit == "Bq/L":
        q = sample.volume_l
    else:
        q = sample.air_volume() * sample.filter_fraction * sample.collection_efficiency
        notes.append(f"air volume {sample.air_volume():.4g} m3, measured filter fraction {sample.filter_fraction:g}, "
                     f"collection efficiency {sample.collection_efficiency:g} (assumption"
                     + (f": {sample.collection_efficiency_note}" if sample.collection_efficiency_note else "") + ")")
    out["unit"] = label
    t_end = datetime.fromisoformat(sample.sampling_end) if (unit == "Bq/m3" and sample.sampling_end) else None
    hours = sample.sampling_hours() if unit == "Bq/m3" else None
    if unit == "Bq/m3":
        if t_end is not None and res.ref_date is None:
            notes.append("acquisition start unknown: activities NOT decay-corrected to the end of sampling "
                         "(underestimated for short-lived nuclides measured after sampling)")
        if t_end is None:
            notes.append("sampling end not given: activities used at their reference date, no decay during sampling")
        elif hours is None:
            notes.append("sampling duration not given: no correction for decay during sampling")
    for r in res.nuclides:
        hl = r.half_life_s
        f = 1.0
        if t_end is not None and res.ref_date is not None and hl:
            f *= decay_factor(hl, (t_end - res.ref_date).total_seconds())       # reference -> end of sampling
        if unit == "Bq/m3" and hours:
            f *= sampling_decay_factor(hl, hours * 3600.0)
        row = {"nuclide": r.nuclide, "unit": label, "decision": r.decision, "factor": f}
        if r.activity is not None and r.detected:
            v = r.activity * f / q
            urel = math.hypot((r.u or 0.0) / r.activity if r.activity else 0.0, quantity_rel_unc)
            row.update(value=v, u=abs(v) * urel, U=2.0 * abs(v) * urel)
        else:
            row.update(value=None, u=None, U=None)
        row["mda"] = r.mda * f / q if r.mda else None
        row["text"] = (f"{row['value']:.4g} +- {row['U']:.2g} (k=2) {label}" if row["value"] is not None
                       else (f"< {row['mda']:.3g} {label} (MDA)" if row["mda"] else "not determined"))
        if res.options.mda_method == "iso11929" and r.activity is not None and r.u:
            y = r.activity * f / q
            uy = math.hypot(r.u * f / q, abs(y) * quantity_rel_unc)
            be = iso11929_best_estimate(y, uy, res.options.coverage)
            if be is not None:
                row.update(best=be[0], best_u=be[1], coverage_low=be[2], coverage_high=be[3])
                row["best_text"] = (f"ISO 11929: {be[0]:.3g} +- {be[1]:.2g} (k=1), "
                                    f"{100 * res.options.coverage:g} % [{be[2]:.3g}, {be[3]:.3g}] {label}")
        k = r.key_line
        if k is not None and k.blank_activity is not None:
            row["blank_text"] = f"reagent blank subtracted: {k.blank_activity:.3g} +- {k.blank_unc:.2g} Bq"
        out["rows"].append(row)
    return out


def result_row(r: NuclideResult) -> dict:
    k = r.key_line
    bud = ", ".join(f"{name} {v:.1f}%" for name, v in r.budget.items() if v > 0.005)
    return {"nuclide": r.nuclide, "lines": r.lines_text, "net_area": k.net_area if k and k.peak_found else None,
            "net_unc": k.net_unc if k and k.peak_found else None,
            "activity_bq": r.activity if r.detected else None, "u_bq": r.u if r.detected else None,
            "specific": r.specific if r.detected else None,
            "specific_U2": r.specific_U if r.detected else None, "unit": r.unit,
            "mda_bq": r.mda or None, "mda_specific": r.specific_mda, "decision": r.decision,
            "best_bq": r.best_estimate, "best_u_bq": r.best_u, "coverage_low_bq": r.coverage_low,
            "coverage_high_bq": r.coverage_high, "best_specific": r.specific_best,
            "best_u_specific": r.specific_best_u, "coverage_low_specific": r.specific_low,
            "coverage_high_specific": r.specific_high,
            "blank_bq": k.blank_activity if k else None, "blank_u_bq": k.blank_unc if k and k.blank_activity is not None
            else None, "budget": bud, "note": r.note}


def _fmt(v, digits=4) -> str:
    if v is None:
        return ""
    if v == 0 or not math.isfinite(v):
        return f"{v:g}"
    return f"{v:.{digits}g}"


def format_table(res: QuantResults) -> str:
    unit = next((r.unit for r in res.nuclides if r.unit), "")
    hdr = ["Nuclide", "Line(s) keV", "Net area", "Activity Bq (k=1)", f"{unit or 'Specific'} (k=2)",
           "MDA Bq", f"MDA {unit}".strip(), "Decision"]
    rows = []
    for r in res.nuclides:
        k = r.key_line
        net = f"{k.net_area:.0f} ± {k.net_unc:.0f}" if k and k.peak_found else "-"
        if r.detected and r.activity is not None:
            act = f"{_fmt(r.activity)} ± {_fmt(r.u, 2)}"
            spec = f"{_fmt(r.specific)} ± {_fmt(r.specific_U, 2)}" if r.specific is not None else ""
        else:
            act = f"< {_fmt(r.mda, 3)}" if r.mda else "-"
            spec = f"< {_fmt(r.specific_mda, 3)}" if r.specific_mda else ""
        rows.append([r.nuclide, r.lines_text, net, act, spec, _fmt(r.mda, 3), _fmt(r.specific_mda, 3), r.decision])
    w = [max(len(str(x)) for x in col) for col in zip(hdr, *rows)]
    out = ["  ".join(str(x).ljust(n) for x, n in zip(hdr, w))]
    out += ["  ".join(str(x).ljust(n) for x, n in zip(row, w)) for row in rows]
    return "\n".join(out)


def export_results(path, res: QuantResults) -> Path:
    """CSV (utf-8-sig) or XLSX (by extension): metadata, results, per-line details."""
    path = Path(path)
    meta = [("Sample", res.sample), ("File", res.source_path),
            ("Acquisition start", res.start_time.isoformat(sep=" ") if res.start_time else ""),
            ("Live time s", res.live_time), ("Real time s", res.real_time or ""),
            ("Reference date", res.ref_date.isoformat(sep=" ") if res.ref_date else ""),
            ("Efficiency curve", f"{res.curve_name} ({res.curve_model})"), ("Background", res.background),
            ("Quantity", f"{res.options.quantity or ''} {res.options.quantity_unit if res.options.quantity else ''}"),
            ("Method", res.options.method), ("Detection limit", res.options.mda_method),
            ("Coverage probability", res.options.coverage if res.options.mda_method == "iso11929" else ""),
            ("Notes", "; ".join(res.notes))]
    header = ROW_KEYS
    rows = [[result_row(r)[k] for k in header] for r in res.nuclides]
    lhead = ["nuclide", "line_nuclide", "energy_keV", "intensity_%", "factor", "net_area", "net_unc",
             "bkg_peak", "continuum", "efficiency", "eff_rel_unc_%", "COI", "COI_rel_unc_%", "activity_Bq",
             "LC_counts", "LD_counts", "decision_threshold_Bq", "MDA_Bq", "detected", "note"]
    lrows = [[r.nuclide, l.nuclide, round(l.energy, 3), 100 * l.intensity, l.factor, l.net_area, l.net_unc,
              l.bkg_peak, l.continuum, l.efficiency, 100 * l.eff_rel_unc, l.coi, 100 * l.coi_rel_unc, l.activity,
              l.lc_counts, l.ld_counts, l.decision_threshold, l.mda, l.detected, l.note]
             for r in res.nuclides for l in r.lines]
    if path.suffix.lower() == ".xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font
        wb = Workbook()
        ws = wb.active
        ws.title = "Sample"
        for kv in meta:
            ws.append(list(kv))
        for title, h, rr in (("Activity", header, rows), ("Lines", lhead, lrows)):
            s = wb.create_sheet(title)
            s.append(h)
            for c in s[1]:
                c.font = Font(bold=True)
            for r in rr:
                s.append(r)
            s.freeze_panes = "A2"
        wb.save(path)
        return path
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        for k, v in meta:
            w.writerow([f"# {k}", v])
        w.writerow([])
        w.writerow(header)
        for r in rows:
            w.writerow(["" if v is None else v for v in r])
        w.writerow([])
        w.writerow(lhead)
        for r in lrows:
            w.writerow(["" if v is None else v for v in r])
    return path

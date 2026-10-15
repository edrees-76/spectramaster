"""Aptec-compatible detector calibration (energy, resolution, efficiency).

Pure functions, no GUI imports.  These are the methods of the Aptec PCMCA/WIN 6.31 calibration
programs (APTEC.EXE *Quick Energy Cal* and S_CALIB.EXE *Full Energy / Resolution / Efficiency
Calibration*) as described in Aptec's own help file, and checked against the calibrations that
Aptec stored in its spectrum files: the points are in the file next to the equation Aptec
computed from them, so each method below was confirmed by refitting the stored points and
comparing with the stored equation (see ``tests/test_aptec_calibration.py``).

Verified against Aptec's stored results
---------------------------------------
* **Energy** E(ch) and **resolution** FWHM(ch) (FWHM in channels): unweighted least-squares
  polynomial through the (channel, value) points, degree = min(max degree, points - 1);
  channels are 0-based.  10 sample files, all coefficients equal to 6 significant digits.
  With a single point the energy line goes through channel 0 = 0 keV (Aptec release note).
* **Efficiency point**: ``eff = net rate / (A * Y * Q * exp(-lambda * (t_rate - t_activity)))``
  with the activity A converted to Bq (``uCi`` = 37000 Bq ...), Y the gamma yield and Q the
  quantity.  Activity given as an emission rate (``gamma/s``) is used without the yield.
  ``err% = sqrt(rate err%^2 + activity err%^2)``.
* **Efficiency curve**, ln(eff) as a polynomial, weighted least squares with weight
  ``1 / (err%/100)^2`` (a point without an error counts as 100 %):

  ====  =========================================  =================================
  A     ln eff = sum_{i<=5} a_i (ln E)^i            5th order ln-ln (HPGe)
  B     ln eff = sum_{i<=3} a_i (ln E)^i            3rd order ln-ln (HPGe)
  C     ln eff = sum_{i<=5} a_i E^i                 5th order polynomial (NaI)
  D     ln eff = sum_{i<=3} a_i E^i                 3rd order polynomial (NaI)
  S     cubic spline through every point           (see below)
  ====  =========================================  =================================

  E in keV.  The parameter covariance is ``(A^T W A)^-1`` without any rescaling, as Aptec
  stores it.  Types A and D were confirmed on the Aptec sample files (coefficients and the
  whole covariance matrix), type B on three laboratory files.

Not verified (no Aptec example available)
-----------------------------------------
* Type C (same rule as D with degree 5; assumed).
* Type S: Aptec only documents that the spline passes through every point and is undefined
  outside them.  A natural cubic spline of ln eff against ln E is used here; reports say so.
* The quantity uncertainty in the point error (zero in every example) is added in quadrature.

Everything is returned as plain data; :func:`to_efficiency_curve` converts an Aptec efficiency
calibration into the :class:`~spectramaster.analysis.efficiency.EfficiencyCurve` used for
quantification.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Sequence

import numpy as np

MAX_DEGREE = 5
MAX_QUICK_POINTS = 16          # Aptec quick energy calibration
MAX_POINTS = 256               # S_Calib
DEFAULT_DEGREE = 2             # S_Calib default for energy and resolution

EFF_TYPES = {
    "A": ("lnln", 5), "B": ("lnln", 3), "C": ("lnpoly", 5), "D": ("lnpoly", 3), "S": ("spline", 0),
}
EFF_TYPE_TEXT = {"A": "5th order ln-ln", "B": "3rd order ln-ln", "C": "5th order polynomial",
                 "D": "3rd order polynomial", "S": "cubic spline"}
VERIFIED_TYPES = {"A", "B", "D"}

# activity unit -> Bq factor; "emission" units already include the yield
ACTIVITY_UNITS: dict[str, float] = {
    "Bq": 1.0, "kBq": 1e3, "MBq": 1e6, "GBq": 1e9, "dps": 1.0, "dpm": 1.0 / 60.0,
    "Ci": 3.7e10, "mCi": 3.7e7, "uCi": 3.7e4, "nCi": 37.0, "pCi": 0.037,
    "gamma/s": 1.0, "gamma/m": 1.0 / 60.0,
}
EMISSION_UNITS = {"gamma/s", "gamma/m"}


def activity_factor(units: str) -> Optional[float]:
    """Bq per unit (case-insensitive; ``µ`` accepted for ``u``); None if unknown."""
    u = (units or "").strip().replace("µ", "u").replace("μ", "u")
    for k, v in ACTIVITY_UNITS.items():
        if k.lower() == u.lower():
            return v
    return None


def is_emission_unit(units: str) -> bool:
    u = (units or "").strip().lower()
    return u in {k.lower() for k in EMISSION_UNITS}


# ====================================================================== polynomial calibrations
@dataclass
class PolyCalibration:
    """Energy (keV vs channel) or resolution (FWHM channels vs channel) calibration."""
    kind: str                                  # "energy" | "resolution"
    max_degree: int
    degree: int
    coeffs: list[float]                        # c0 + c1*ch + ... (degree + 1 values)
    channels: list[float]
    values: list[float]
    units: str = "keV"
    time: Optional[datetime] = None

    def evaluate(self, ch):
        return np.polynomial.polynomial.polyval(np.asarray(ch, dtype=float), self.coeffs)

    @property
    def fitted(self) -> list[float]:
        return [float(v) for v in self.evaluate(self.channels)]

    @property
    def deviations(self) -> list[float]:
        return [v - f for v, f in zip(self.values, self.fitted)]

    @property
    def average_deviation(self) -> float:
        """Mean absolute deviation of the points from the equation (same units as the values)."""
        d = self.deviations
        return float(np.mean(np.abs(d))) if d else 0.0

    @property
    def range(self) -> tuple[float, float]:
        return (min(self.channels), max(self.channels)) if self.channels else (0.0, 0.0)


def fit_polynomial(channels: Sequence[float], values: Sequence[float], max_degree: int,
                   kind: str = "energy", units: str = "keV",
                   time: Optional[datetime] = None) -> PolyCalibration:
    """Aptec's calibration fit: unweighted least squares, degree = min(max_degree, n - 1).

    One energy point: the line through channel 0 = 0 and that point."""
    if not 1 <= int(max_degree) <= MAX_DEGREE:
        raise ValueError(f"maximum degree must be 1..{MAX_DEGREE}")
    ch = [float(c) for c in channels]
    v = [float(x) for x in values]
    if len(ch) != len(v):
        raise ValueError("channels and values differ in length")
    if not ch:
        raise ValueError("no calibration points")
    if len(set(ch)) < len(ch):
        raise ValueError("two points have the same channel")
    if len(ch) == 1:
        if kind != "energy":
            return PolyCalibration(kind, int(max_degree), 0, [v[0]], ch, v, units, time)
        ch, v = [0.0] + ch, [0.0] + v
        out = fit_polynomial(ch, v, 1, kind, units, time)
        out.channels, out.values, out.max_degree = ch[1:], v[1:], int(max_degree)
        return out
    deg = min(int(max_degree), len(ch) - 1)
    x = np.asarray(ch)
    scale = max(abs(x).max(), 1.0)                 # conditioning only; result in raw channels
    c = np.polynomial.polynomial.polyfit(x / scale, np.asarray(v), deg)
    c = c / scale ** np.arange(deg + 1)
    return PolyCalibration(kind, int(max_degree), deg, [float(a) for a in c], ch, v, units, time)


def fwhm_channels_to_kev(res: Sequence[float], energy: Sequence[float]) -> list[float]:
    """FWHM(ch) in channels -> FWHM(ch) in keV (polynomial product with dE/dch), the
    convention of ``Spectrum.fwhm_coeffs``."""
    e = np.asarray(energy, dtype=float)
    if len(e) < 2:
        return []
    deriv = np.polynomial.polynomial.polyder(e)
    out = np.polynomial.polynomial.polymul(np.asarray(res, dtype=float), deriv)
    return [float(a) for a in out]


def fwhm_kev_to_channels(fwhm_kev_coeffs: Sequence[float], energy: Sequence[float],
                         channels: Sequence[float]) -> list[float]:
    """FWHM in channels at `channels` from keV coefficients (for loading stored calibrations)."""
    ch = np.asarray(channels, dtype=float)
    fk = np.polynomial.polynomial.polyval(ch, fwhm_kev_coeffs)
    slope = np.polynomial.polynomial.polyval(ch, np.polynomial.polynomial.polyder(energy))
    return [float(a) for a in np.where(slope > 0, fk / np.where(slope > 0, slope, 1.0), np.nan)]


# ====================================================================== efficiency points
@dataclass
class EffPoint:
    """One efficiency calibration point (the fields of Aptec's efficiency record)."""
    energy: float                              # keV
    isotope: str = ""
    yield_: float = 0.0                        # gammas per decay (fraction)
    half_life_s: Optional[float] = None
    activity: float = 0.0                      # in `activity_units`
    activity_err: float = 0.0                  # 1 sigma, percent
    activity_units: str = "Bq"
    activity_time: Optional[datetime] = None   # certificate (reference) date
    net_rate: float = 0.0                      # net counts / live s
    net_rate_err: float = 0.0                  # 1 sigma, percent
    rate_time: Optional[datetime] = None       # start of the counting
    quantity: float = 1.0
    quantity_err: float = 0.0                  # percent
    efficiency: float = 0.0
    efficiency_err: float = 0.0                # 1 sigma, percent
    use: bool = True
    manual: bool = False                       # efficiency typed in, not calculated
    note: str = ""

    def decay_factor(self) -> float:
        if not (self.half_life_s and self.activity_time and self.rate_time):
            return 1.0
        dt = (self.rate_time - self.activity_time).total_seconds()
        return math.exp(-math.log(2.0) * dt / self.half_life_s)

    def calculate(self) -> "EffPoint":
        """Fill ``efficiency`` / ``efficiency_err`` from activity and rate (Aptec's formula)."""
        if self.manual:
            return self
        f = activity_factor(self.activity_units)
        if f is None:
            raise ValueError(f"unknown activity units {self.activity_units!r}")
        y = 1.0 if is_emission_unit(self.activity_units) else self.yield_
        denom = self.activity * f * y * (self.quantity or 1.0) * self.decay_factor()
        if denom <= 0 or self.net_rate <= 0:
            raise ValueError(f"{self.isotope} {self.energy:g} keV: activity, yield and net rate "
                             "must be positive")
        self.efficiency = self.net_rate / denom
        self.efficiency_err = math.sqrt(self.net_rate_err ** 2 + self.activity_err ** 2
                                        + self.quantity_err ** 2)
        return self


# ====================================================================== efficiency curve
def _natural_spline_matrix(x: np.ndarray) -> np.ndarray:
    """M (n x n) with y'' = M @ y for the natural cubic spline through (x, y)."""
    n = len(x)
    h = np.diff(x)
    a = np.zeros((n, n))
    b = np.zeros((n, n))
    a[0, 0] = a[-1, -1] = 1.0
    for i in range(1, n - 1):
        a[i, i - 1], a[i, i], a[i, i + 1] = h[i - 1], 2 * (h[i - 1] + h[i]), h[i]
        b[i, i - 1], b[i, i], b[i, i + 1] = 6 / h[i - 1], -6 / h[i - 1] - 6 / h[i], 6 / h[i]
    return np.linalg.solve(a, b)


def spline_design(knots_lnE: Sequence[float], ln_e) -> np.ndarray:
    """Rows mapping the knot values ln eff_i to ln eff(E) (natural cubic spline, linear in the
    knot values); NaN outside the knots (the spline is undefined there)."""
    x = np.asarray(knots_lnE, dtype=float)
    t = np.atleast_1d(np.asarray(ln_e, dtype=float))
    n = len(x)
    m = _natural_spline_matrix(x)
    out = np.full((len(t), n), np.nan)
    for r, v in enumerate(t):
        if not (x[0] - 1e-12 <= v <= x[-1] + 1e-12):
            continue
        i = int(min(max(np.searchsorted(x, v) - 1, 0), n - 2))
        h = x[i + 1] - x[i]
        a, b = (x[i + 1] - v) / h, (v - x[i]) / h
        row = np.zeros(n)
        row[i], row[i + 1] = a, b
        row += ((a ** 3 - a) * m[i] + (b ** 3 - b) * m[i + 1]) * h * h / 6.0
        out[r] = row
    return out


@dataclass
class EffCalibration:
    """Aptec efficiency calibration: type, coefficients (6, zero-padded), covariance."""
    eff_type: str
    coeffs: list[float]
    cov: list[list[float]]
    points: list[EffPoint] = field(default_factory=list)
    units: str = "keV"
    detector_id: str = ""
    geometry_id: str = ""
    time: Optional[datetime] = None
    knots: list[float] = field(default_factory=list)       # spline: ln E of the knots

    @property
    def form(self) -> str:
        return EFF_TYPES[self.eff_type][0]

    @property
    def degree(self) -> int:
        return EFF_TYPES[self.eff_type][1]

    def design(self, energy) -> np.ndarray:
        e = np.atleast_1d(np.asarray(energy, dtype=float))
        if self.form == "spline":
            return spline_design(self.knots, np.log(e))
        x = np.log(e) if self.form == "lnln" else e
        return np.vander(x, self.degree + 1, increasing=True)

    def efficiency(self, energy):
        p = np.asarray(self.coeffs[:self.design(np.array([100.0])).shape[1]], dtype=float)
        v = np.exp(self.design(energy) @ p)
        return float(v[0]) if np.ndim(energy) == 0 else v

    def rel_uncertainty(self, energy):
        """Relative 1-sigma uncertainty of eff(E) from the parameter covariance."""
        g = self.design(energy)
        c = np.asarray(self.cov, dtype=float)
        v = np.einsum("ij,jk,ik->i", g, c, g)
        r = np.sqrt(np.maximum(v, 0.0))
        return float(r[0]) if np.ndim(energy) == 0 else r

    @property
    def used(self) -> list[EffPoint]:
        return [p for p in self.points if p.use]

    @property
    def energy_range(self) -> tuple[float, float]:
        e = [p.energy for p in self.used]
        return (min(e), max(e)) if e else (0.0, 0.0)

    def deviations_pct(self) -> list[float]:
        out = []
        for p in self.points:
            f = self.efficiency(p.energy)
            out.append(100.0 * (p.efficiency - f) / f if f and math.isfinite(f) else float("nan"))
        return out

    @property
    def average_deviation_pct(self) -> float:
        d = [abs(x) for p, x in zip(self.points, self.deviations_pct()) if p.use and math.isfinite(x)]
        return float(np.mean(d)) if d else 0.0

    @property
    def chi2(self) -> float:
        use = self.used
        if not use:
            return 0.0
        y = np.log([p.efficiency for p in use])
        f = self.design([p.energy for p in use]) @ np.asarray(self.coeffs[:self.design(np.array([100.0])).shape[1]])
        u = np.array([_rel_err(p) for p in use])
        return float(np.sum(((y - f) / u) ** 2))

    @property
    def dof(self) -> int:
        return len(self.used) - (len(self.knots) if self.form == "spline" else self.degree + 1)


def _rel_err(p: EffPoint) -> float:
    return p.efficiency_err / 100.0 if p.efficiency_err > 0 else 1.0     # Aptec: none -> 100 %


def fit_efficiency(points: Sequence[EffPoint], eff_type: str = "A", units: str = "keV",
                   detector_id: str = "", geometry_id: str = "",
                   time: Optional[datetime] = None) -> EffCalibration:
    """Aptec's efficiency fit (see the module docstring) through the points with ``use``."""
    t = (eff_type or "").upper()
    if t not in EFF_TYPES:
        raise ValueError(f"unknown efficiency calibration type {eff_type!r} (A, B, C, D or S)")
    use = sorted((p for p in points if p.use), key=lambda p: p.energy)
    bad = [p for p in use if p.efficiency <= 0 or p.energy <= 0]
    if bad:
        raise ValueError(f"{bad[0].isotope} {bad[0].energy:g} keV: efficiency and energy must be positive")
    form, deg = EFF_TYPES[t]
    cal = EffCalibration(t, [], [], list(points), units, detector_id, geometry_id, time)
    y = np.log([p.efficiency for p in use])
    u = np.array([_rel_err(p) for p in use])
    if form == "spline":
        if len(use) < 3:
            raise ValueError("a cubic spline needs at least 3 points")
        x = np.log([p.energy for p in use])
        if np.any(np.diff(x) <= 0):
            raise ValueError("two points have the same energy")
        cal.knots = [float(v) for v in x]
        cal.coeffs = [float(v) for v in y]                      # knot values: passes through all
        cal.cov = np.diag(u ** 2).tolist()
        return cal
    if len(use) < deg + 1:
        raise ValueError(f"type {t} ({EFF_TYPE_TEXT[t]}) needs at least {deg + 1} points, "
                         f"{len(use)} selected")
    e = np.array([p.energy for p in use])
    x = np.log(e) if form == "lnln" else e
    scale = max(abs(x).max(), 1.0)
    a = np.vander(x / scale, deg + 1, increasing=True) / u[:, None]
    par, *_ = np.linalg.lstsq(a, y / u, rcond=None)
    cov = np.linalg.inv(a.T @ a)
    s = scale ** np.arange(deg + 1)
    par = par / s
    cov = cov / np.outer(s, s)
    cal.coeffs = [float(v) for v in par] + [0.0] * (MAX_DEGREE - deg)
    cal.cov = [[float(v) for v in row] for row in cov]
    return cal


def calculate_efficiency(cal: EffCalibration, energy: float) -> tuple[float, float, bool]:
    """(efficiency, relative uncertainty %, inside the calibrated range) - S_Calib F8."""
    lo, hi = cal.energy_range
    inside = lo <= energy <= hi
    return cal.efficiency(energy), 100.0 * cal.rel_uncertainty(energy), inside


def to_efficiency_curve(cal: EffCalibration, name: str = "", source: str = ""):
    """Convert to :class:`~spectramaster.analysis.efficiency.EfficiencyCurve` (quantification)."""
    from . import efficiency as eff
    pts = []
    for p in cal.points:
        if p.efficiency <= 0:
            continue
        pts.append(eff.EfficiencyPoint(p.energy, p.efficiency, p.efficiency * _rel_err(p), p.isotope,
                                       use=p.use, manual=p.manual, note=p.note,
                                       u_count_rel=p.net_rate_err / 100.0,
                                       u_act_rel=p.activity_err / 100.0, group=p.isotope))
    lo, hi = cal.energy_range
    common = dict(params=[], cov=cal.cov, chi2=cal.chi2, dof=cal.dof, e_min=lo, e_max=hi, points=pts,
                  geometry=cal.geometry_id, detector=cal.detector_id, name=name, source=source,
                  cov_method="aptec", date=(cal.time or datetime.now()).strftime("%Y-%m-%d %H:%M"))
    if cal.form == "spline":
        c = eff.EfficiencyCurve(model="spline_lnln", order=0, e_ref=1.0, knots=list(cal.knots), **common)
        c.params = list(cal.coeffs)
    else:
        c = eff.EfficiencyCurve(model="loglog" if cal.form == "lnln" else "lnpoly", order=cal.degree,
                                e_ref=1.0, **common)
        c.params = list(cal.coeffs[:cal.degree + 1])
    c.selection = f"Aptec type {cal.eff_type}: {EFF_TYPE_TEXT[cal.eff_type]}"
    c.note = ("" if cal.eff_type in VERIFIED_TYPES
              else "fit rule not verified against an Aptec result")
    if cal.dof > 0 and cal.chi2 / cal.dof > 1.0:
        c.warnings.append(f"chi2/dof = {cal.chi2 / cal.dof:.2f} > 1: the curve uncertainty (Aptec "
                          "convention, not rescaled) may be underestimated")
    return c


# ====================================================================== reports (S_Calib style)
def _ts(t: Optional[datetime]) -> str:
    return t.strftime("%d-%b-%Y %H:%M:%S") if t else "-"


def poly_report(cal: PolyCalibration, energy_coeffs: Sequence[float] = ()) -> str:
    title = "Energy Calibration" if cal.kind == "energy" else "Resolution Calibration"
    unit = cal.units or ("keV" if cal.kind == "energy" else "channels")
    lines = [title, "=" * len(title),
             f"Calibration time : {_ts(cal.time)}",
             f"Units            : {unit}",
             f"Maximum degree   : {cal.max_degree}    degree used: {cal.degree}",
             "Equation         : " + "  ".join(f"c{i}={c:.9g}" for i, c in enumerate(cal.coeffs)),
             "", f"{'Point':>5} {'Channel':>11} {'Value':>12} {'Calculated':>12} {'Deviation':>11}"]
    for i, (ch, v, f) in enumerate(zip(cal.channels, cal.values, cal.fitted), start=1):
        extra = ""
        if cal.kind == "resolution" and len(energy_coeffs) >= 2:
            slope = float(np.polynomial.polynomial.polyval(ch, np.polynomial.polynomial.polyder(energy_coeffs)))
            extra = f"   ({v * slope:.3f} keV)"
        lines.append(f"{i:>5} {ch:>11.2f} {v:>12.4f} {f:>12.4f} {v - f:>+11.4f}{extra}")
    lines += ["", f"Average deviation: {cal.average_deviation:.4f} {unit}"]
    lo, hi = cal.range
    lines.append(f"Valid range      : channel {lo:.1f} to {hi:.1f} (do not use the equation outside)")
    return "\n".join(lines)


def eff_report(cal: EffCalibration) -> str:
    title = "Efficiency Calibration"
    lines = [title, "=" * len(title),
             f"Calibration time : {_ts(cal.time)}",
             f"Detector ID      : {cal.detector_id or '-'}    Geometry ID: {cal.geometry_id or '-'}",
             f"Energy units     : {cal.units}",
             f"Method           : {cal.eff_type} = {EFF_TYPE_TEXT[cal.eff_type]}"
             + ("" if cal.eff_type in VERIFIED_TYPES else "  (fit rule not verified against Aptec)")]
    if cal.form != "spline":
        lines.append("Equation         : ln(eff) = " + "  ".join(
            f"a{i}={c:.9g}" for i, c in enumerate(cal.coeffs[:cal.degree + 1]))
            + ("  with x = ln(E)" if cal.form == "lnln" else "  with x = E"))
    lines += ["", f"{'Pt':>3} {'Isotope':<9} {'Energy':>9} {'Efficiency':>12} {'Err%':>7} "
                  f"{'Calculated':>12} {'Dev%':>8}  Use"]
    for i, (p, d) in enumerate(zip(cal.points, cal.deviations_pct()), start=1):
        f = cal.efficiency(p.energy)
        lines.append(f"{i:>3} {p.isotope:<9} {p.energy:>9.2f} {p.efficiency:>12.6g} {p.efficiency_err:>7.2f} "
                     f"{f:>12.6g} {d:>+8.2f}  {'yes' if p.use else 'no'}")
    lo, hi = cal.energy_range
    lines += ["", f"Average deviation: {cal.average_deviation_pct:.2f} %",
              f"Chi-square       : {cal.chi2:.3f} for {max(cal.dof, 0)} degree(s) of freedom",
              f"Valid range      : {lo:.1f} to {hi:.1f} keV (do not quantify outside)"]
    if cal.form == "spline":
        lines.append("Note             : the spline passes through every point (0 % deviation by "
                     "construction); it is undefined outside the points.")
    return "\n".join(lines)


# ====================================================================== Aptec .S0 calibration sections
def _dt(d: bytes, o: int) -> Optional[datetime]:
    import struct
    t, s, m, h, day, mon = d[o:o + 6]
    y = struct.unpack_from("<h", d, o + 6)[0]
    if not y or not mon or not day:
        return None
    try:
        return datetime(y, mon, day, h, m, s, min(t, 99) * 10000)
    except ValueError:
        return None


def read_aptec_calibrations(data) -> dict:
    """Calibration sections of an Aptec PCMCA/WIN v6.3 ``.S0`` file (bytes or path).

    Layout from Aptec's help file ("Spectrum File Format Version 6.3").  Returns
    ``{"energy": PolyCalibration|None, "resolution": PolyCalibration|None,
    "efficiency": EffCalibration|None, "stored": {...}}``; ``stored`` keeps the equations Aptec
    saved (energy / resolution coefficients and degree, efficiency type, coefficients and the
    upper-triangle covariance) so they can be compared with a refit."""
    import struct
    from pathlib import Path
    d = data if isinstance(data, (bytes, bytearray)) else Path(data).read_bytes()
    if not bytes(d[:8]) == b"VERSION6":
        raise ValueError("not an Aptec v6 spectrum file")

    def f32(o): return struct.unpack_from("<f", d, o)[0]
    def f64(o): return struct.unpack_from("<d", d, o)[0]
    def i16(o): return struct.unpack_from("<h", d, o)[0]
    def text(o, n): return bytes(d[o:o + n]).split(b"\0")[0].decode("cp1252", "replace").strip()

    n_eff, n_en, n_res = max(i16(330), 0), max(i16(618), 0), max(i16(694), 0)
    t_code = struct.unpack_from("<H", d, 356)[0]
    eff_type = chr(t_code) if 65 <= t_code <= 90 else ""
    stored = {"energy_degree": i16(644), "energy_coeffs": [f64(646 + 8 * k) for k in range(6)],
              "resolution_degree": i16(720), "resolution_coeffs": [f64(722 + 8 * k) for k in range(6)],
              "eff_type": eff_type, "eff_coeffs": [f64(358 + 8 * k) for k in range(6)],
              "eff_cov_upper": [f64(450 + 8 * k) for k in range(21)]}
    o = 1024
    pts = []
    for k in range(n_eff):
        r = o + 130 * k
        hl = f64(r + 26)
        pts.append(EffPoint(energy=float(f32(r + 18)), isotope=text(r + 2, 16), yield_=float(f32(r + 22)),
                            half_life_s=hl if hl > 0 else None, activity=float(f32(r + 46)),
                            activity_err=float(f32(r + 50)), activity_units=text(r + 54, 16) or "Bq",
                            activity_time=_dt(d, r + 38), quantity=float(f32(r + 70)) or 1.0,
                            quantity_err=float(f32(r + 74)), net_rate=float(f64(r + 94)),
                            net_rate_err=float(f32(r + 102)), rate_time=_dt(d, r + 122),
                            efficiency=float(f32(r + 106)), efficiency_err=float(f32(r + 110)),
                            manual=not text(r + 2, 16)))
    o += 130 * n_eff
    en = [(float(f32(o + 8 * k)), float(f32(o + 8 * k + 4))) for k in range(n_en)]
    o += 8 * n_en
    res = [(float(f32(o + 8 * k)), float(f32(o + 8 * k + 4))) for k in range(n_res)]
    out = {"energy": None, "resolution": None, "efficiency": None, "stored": stored}
    if en:
        out["energy"] = fit_polynomial([c for c, _ in en], [v for _, v in en], max(1, min(stored["energy_degree"], 5)),
                                       "energy", text(628, 16) or "keV", _dt(d, 620))
    if res:
        out["resolution"] = fit_polynomial([c for c, _ in res], [v for _, v in res],
                                           max(1, min(stored["resolution_degree"], 5)), "resolution",
                                           text(704, 16) or "channels", _dt(d, 696))
    if pts and eff_type in EFF_TYPES:
        try:
            out["efficiency"] = fit_efficiency(pts, eff_type, text(340, 16) or "keV", text(418, 16),
                                               text(434, 16), _dt(d, 332))
        except ValueError:
            out["efficiency"] = None
    return out


def upper_to_matrix(upper: Sequence[float], n: int) -> np.ndarray:
    """Aptec stores the symmetric covariance as the upper triangle, row by row."""
    m = np.zeros((n, n))
    k = 0
    for i in range(n):
        for j in range(i, n):
            m[i, j] = m[j, i] = upper[k]
            k += 1
    return m


__all__ = ["read_aptec_calibrations", "upper_to_matrix", "MAX_DEGREE", "MAX_QUICK_POINTS", "MAX_POINTS", "DEFAULT_DEGREE", "EFF_TYPES", "EFF_TYPE_TEXT",
           "VERIFIED_TYPES", "ACTIVITY_UNITS", "activity_factor", "is_emission_unit", "PolyCalibration",
           "fit_polynomial", "fwhm_channels_to_kev", "fwhm_kev_to_channels", "EffPoint", "EffCalibration",
           "fit_efficiency", "calculate_efficiency", "to_efficiency_curve", "spline_design", "poly_report",
           "eff_report"]

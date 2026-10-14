"""Full-energy-peak (FEP) efficiency calibration.

Pure functions, no GUI imports.  Conventions
--------------------------------------------
* Activities in Bq, energies in keV, times in s, dates naive local ``datetime``.
* Gamma intensities ``I`` are *fractions* per decay (the bundled library stores percent;
  :func:`certificate_lines` converts).
* Measured efficiency point of a certified line::

      eps = N / (t_live * A(t0) * C * I)
      A(t0) = A_ref * exp(-lambda * (t0 - t_ref))          decay to the measurement start t0
      C     = (1 - exp(-lambda * t_real)) / (lambda * t_real)  decay during counting

  relative uncertainty  u(eps)/eps = sqrt( (uN/N)^2 + (uA/A)^2 + (uI/I)^2 ).
* Fit models (weighted linear least squares on ln eps, weights 1/u_rel^2):

  - ``loglog``      ln eps = sum_i a_i * x^i,          x = ln(E / E0)   (order 1..5, E0 = 1000 keV)
  - ``two_branch``  ln eps = a_0 + sum_i b_i x^i  (E <  Ec)
                    ln eps = a_0 + sum_i c_i x^i  (E >= Ec),  x = ln(E / Ec)
                    the shared a_0 makes the curve continuous at the crossover Ec.

  Generalised least squares with the full covariance of the points (relative, on ln eps)::

      V_ij = delta_ij (u_count_i^2 + u_I_i^2)          independent: counting, emission probability
           + [nuclide_i = nuclide_j] u_A_i u_A_j       certificate activity, shared by the lines
                                                       of one nuclide
           + u_common^2                                common to the whole standard (e.g.
                                                       gravimetric preparation), if stated

  The parameter covariance is (A^T V^-1 A)^-1, multiplied by chi^2/dof when that is > 1
  (Birge scaling); u(eps(E))/eps = sqrt(g^T C g), g = d ln eps / d a.  Every component is
  counted once: the certificate activity enters only through V (before Release D it was
  in each point's independent weight *and* again added to the curve as ``u_sys``).
  Points without a component breakdown (manual points, curves saved earlier) are treated as
  independent with their total uncertainty; ``u_sys_rel`` of a loaded older curve is still
  added to its uncertainty as it was.
* Curves are saved as JSON (``EfficiencyCurve.save`` / ``load_curve``), by default in
  :func:`default_curve_dir`.

Aptec ``.S0`` files carry Aptec's own efficiency/source records (130 bytes each, see
:func:`aptec_source_records`), which can serve as the certificate.
"""
from __future__ import annotations

import csv
import json
import math
import os
import struct
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np

LN2 = math.log(2.0)
# cascade emitters: their full-energy peaks lose (and sum-peaks gain) counts by true-coincidence
# summing, which grows as the source gets closer to the detector; not corrected
TCS_NUCLIDES = {"Co-60", "Cs-134", "Bi-214", "Tl-208", "Ac-228", "Eu-152", "Y-88", "Ba-133",
                "Ra-226", "Th-232", "Th-228", "Ra-228", "Na-22", "Sb-125", "Eu-154", "Co-58"}
TCS_NOTE = "cascade emitter: true-coincidence summing not corrected (biased in close geometries)"
YEAR_S = 365.2422 * 86400.0
E0_LOGLOG = 1000.0

# ------------------------------------------------------------------ decay helpers


def decay_constant(half_life_s: Optional[float]) -> float:
    return LN2 / half_life_s if half_life_s and half_life_s > 0 else 0.0


def decay_factor(half_life_s: Optional[float], dt_s: float) -> float:
    """exp(-lambda * dt): fraction left after dt seconds (dt may be negative)."""
    return math.exp(-decay_constant(half_life_s) * dt_s)


def counting_decay_factor(half_life_s: Optional[float], t_real: Optional[float]) -> float:
    """Mean activity during counting / activity at the start: (1-e^-lt)/(lt) (1 if stable)."""
    lam = decay_constant(half_life_s)
    if not t_real or lam * t_real < 1e-9:
        return 1.0
    x = lam * t_real
    return -math.expm1(-x) / x


def parse_date(text) -> Optional[datetime]:
    """ISO-like date/time ('2004-07-22', '2004-07-22 11:02', '22/07/2004', '22.07.2004 11:02')."""
    if text is None or isinstance(text, datetime):
        return text
    s = str(text).strip()
    if not s:
        return None
    s = s.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
                "%d/%m/%Y", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        raise ValueError(f"unrecognised date: {text!r}") from None


# ------------------------------------------------------------------ certificate


@dataclass
class CertLine:
    """One certified gamma line of a calibration standard."""
    nuclide: str
    energy: float                   # keV
    intensity: float                # photons per decay (fraction)
    activity: float                 # Bq at ref_date
    activity_unc: float             # Bq, 1 sigma
    ref_date: Optional[datetime]
    half_life_s: Optional[float]
    intensity_unc: float = 0.0      # absolute, fraction
    use: bool = True


@dataclass
class CertNuclide:
    """Certificate entry per nuclide (what the user types in)."""
    nuclide: str
    activity: float                 # Bq
    activity_unc: float = 0.0       # Bq, 1 sigma
    ref_date: Optional[datetime] = None
    half_life_s: Optional[float] = None    # None = from the library
    lines: Optional[list[tuple[float, float]]] = None   # (keV, fraction); None = library lines


def _library():
    from .library import load_library
    return load_library()


def half_life_of(nuclide: str) -> Optional[float]:
    nd = _library().get(nuclide)
    return nd.half_life_s if nd else None


def certificate_lines(entries: Iterable[CertNuclide], min_intensity_pct: float = 2.0,
                      e_min: float = 40.0, e_max: float = 3000.0) -> list[CertLine]:
    """Expand nuclide entries into lines using the bundled library (gammas >= min_intensity_pct)."""
    lib = _library()
    out: list[CertLine] = []
    for c in entries:
        nd = lib.get(c.nuclide)
        hl = c.half_life_s if c.half_life_s else (nd.half_life_s if nd else None)
        if c.lines:
            lines = list(c.lines)
        elif nd:
            lines = [(l.energy, l.intensity / 100.0) for l in nd.gammas(min_intensity_pct)
                     if e_min <= l.energy <= e_max]
        else:
            raise KeyError(f"{c.nuclide}: not in the nuclide library - give the lines explicitly")
        for e, i in lines:
            if any(o.nuclide == c.nuclide and abs(o.energy - float(e)) < 0.01 for o in out):
                continue        # duplicated row
            out.append(CertLine(c.nuclide, float(e), float(i), float(c.activity), float(c.activity_unc),
                                c.ref_date, hl))
    return sorted(out, key=lambda l: l.energy)


def read_certificate_csv(path) -> list[CertNuclide]:
    """CSV certificate.  Header names (case-insensitive, any order)::

        nuclide, activity_bq, unc_percent | unc_bq, ref_date [, half_life_s] [, energy_kev, intensity_percent]

    Without a header the column order is nuclide, activity_bq, unc_percent, ref_date.
    Rows of the same nuclide that give energy+intensity define that nuclide's lines explicitly.
    """
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.reader(fh):
            r = [c.strip() for c in r]
            if r and r[0] and not r[0].startswith("#"):
                rows.append(r)
    if not rows:
        return []
    try:
        float(rows[0][1])
        header = ["nuclide", "activity_bq", "unc_percent", "ref_date", "half_life_s", "energy_kev",
                  "intensity_percent"]
    except (ValueError, IndexError):
        header = [h.lower().replace(" ", "_") for h in rows.pop(0)]
    by: dict[str, CertNuclide] = {}
    for r in rows:
        d = {header[i]: r[i] for i in range(min(len(header), len(r)))}
        name = d.get("nuclide", "")
        act = float(d.get("activity_bq") or d.get("activity") or 0)
        if d.get("unc_bq"):
            unc = float(d["unc_bq"])
        else:
            unc = act * float(d.get("unc_percent") or d.get("unc_%") or 0) / 100.0
        c = by.get(name)
        if c is None:
            hl = d.get("half_life_s")
            c = by[name] = CertNuclide(name, act, unc, parse_date(d.get("ref_date")),
                                       float(hl) if hl else None)
        if d.get("energy_kev") and d.get("intensity_percent"):
            c.lines = (c.lines or []) + [(float(d["energy_kev"]), float(d["intensity_percent"]) / 100.0)]
    return list(by.values())


def write_certificate_csv(path, entries: Sequence[CertNuclide]) -> Path:
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["nuclide", "activity_bq", "unc_percent", "ref_date", "half_life_s", "energy_kev",
                    "intensity_percent"])
        for c in entries:
            pct = 100.0 * c.activity_unc / c.activity if c.activity else 0.0
            base = [c.nuclide, f"{c.activity:.6g}", f"{pct:.4g}",
                    c.ref_date.strftime("%Y-%m-%d %H:%M") if c.ref_date else "",
                    f"{c.half_life_s:.6g}" if c.half_life_s else ""]
            if c.lines:
                for e, i in c.lines:
                    w.writerow(base + [f"{e:.3f}", f"{100 * i:.5g}"])
            else:
                w.writerow(base + ["", ""])
    return path


# Editable presets (activities are *examples* - always type the values of your certificate).
PRESETS: dict[str, dict] = {
    "QCY48 (typical mixed standard)": {
        "note": "Amersham QCY48-type mixture; activities = the lab's QCY48CAL.S0 record (10 ml, ref 1988-02-01)",
        "ref_date": "1988-02-01 12:00",
        "nuclides": [("Am-241", 671.1, 3.0), ("Cd-109", 3654.0, 4.0), ("Co-57", 148.4, 2.5),
                     ("Ce-139", 177.8, 2.5), ("Hg-203", 556.6, 5.0), ("Sn-113", 717.0, 5.0),
                     ("Sr-85", 873.6, 2.5), ("Cs-137", 619.8, 3.5), ("Y-88", 1430.0, 3.0),
                     ("Co-60", 743.1, 1.0)],
    },
    "QCRB1241 (lab, 1 L Marinelli)": {
        "note": "the lab's QCRB1241 solution as stored in EFF-GOOD.S0 (Bq/ml x 1000 ml, ref 2003-04-01)",
        "ref_date": "2003-04-01 12:00",
        "nuclides": [("Ba-133", 1980.0, 3.0), ("Co-57", 2040.0, 3.0), ("Ce-139", 2050.0, 3.0),
                     ("Sr-85", 9950.0, 3.0), ("Cs-137", 4000.0, 3.0), ("Mn-54", 4010.0, 3.0),
                     ("Y-88", 9930.0, 3.0), ("Zn-65", 10000.0, 3.0)],
    },
    "Eu-152 point source": {"note": "", "ref_date": "", "nuclides": [("Eu-152", 10000.0, 2.0)]},
}


def preset_entries(name: str) -> list[CertNuclide]:
    p = PRESETS[name]
    ref = parse_date(p.get("ref_date"))
    return [CertNuclide(n, a, a * u / 100.0, ref) for n, a, u in p["nuclides"]]


# ------------------------------------------------------------------ Aptec source records

_APTEC_UNITS = {"bq": 1.0, "kbq": 1e3, "mbq": 1e6, "uci": 3.7e4, "µci": 3.7e4, "mci": 3.7e7,
                "nci": 37.0, "pci": 0.037, "ci": 3.7e10, "dps": 1.0, "gamma/s": None, "gps": None}


@dataclass
class AptecSourceRecord:
    """One 130-byte efficiency/source record of an Aptec ``.S0`` file.

    Layout (decoded from the lab's QCY48CAL/EFF/EFF-GOOD/EFFNEW/Eu-152 files and verified
    arithmetically, e.g. efficiency = rate / (activity * quantity * decay * yield))::

        +0x02 c16 nuclide        +0x12 f32 energy keV     +0x16 f32 gamma yield (fraction)
        +0x1A f64 half-life s    +0x26 DT reference date  +0x2E f32 activity (per quantity unit)
        +0x32 f32 activity unc % +0x36 c16 activity units ('Bq', 'uCi', 'gamma/s' ...)
        +0x46 f32 quantity (multiplier, e.g. 1000 ml)     +0x4A f32 (unknown)  +0x4E c16 quantity units
        +0x5E f64 net count rate (cps)                    +0x66 f32 rate unc %
        +0x6A f32 efficiency     +0x6E f32 efficiency unc % = sqrt(rate%^2 + activity%^2)
        +0x7A DT measurement (acquisition start) of the calibration spectrum
    """
    nuclide: str
    energy: float
    yield_: float
    half_life_s: float
    ref_date: Optional[datetime]
    activity: float
    activity_unc_pct: float
    activity_units: str
    quantity: float
    quantity_units: str
    rate_cps: float
    rate_unc_pct: float
    efficiency: float
    efficiency_unc_pct: float
    measured: Optional[datetime]

    @property
    def total_activity_bq(self) -> Optional[float]:
        """Total source activity in Bq at ref_date (activity x quantity, units converted)."""
        q = self.quantity if self.quantity and math.isfinite(self.quantity) and self.quantity > 0 else 1.0
        u = self.activity_units.strip().lower()
        f = _APTEC_UNITS.get(u, 1.0 if not u else -1)
        if f is None:   # emission rate
            return self.activity * q / self.yield_ if self.yield_ > 0 else None
        if f < 0:
            return None
        return self.activity * q * f


def aptec_source_records(data) -> list[AptecSourceRecord]:
    """Decode the efficiency/source records of an Aptec ``.S0`` file (path or bytes)."""
    from ..formats.aptec import EFF_REC, HEADER_SIZE, MAGIC, O_NEFF, _dt, _f32, _str, _u16
    if not isinstance(data, (bytes, bytearray)):
        data = Path(data).read_bytes()
    d = bytes(data)
    if not d.startswith(MAGIC) or len(d) < HEADER_SIZE:
        return []
    out = []
    for i in range(_u16(d, O_NEFF)):
        o = HEADER_SIZE + EFF_REC * i
        if o + EFF_REC > len(d):
            break
        out.append(AptecSourceRecord(
            nuclide=_str(d, o + 0x02, 16), energy=_f32(d, o + 0x12), yield_=_f32(d, o + 0x16),
            half_life_s=struct.unpack_from("<d", d, o + 0x1A)[0], ref_date=_dt(d, o + 0x26),
            activity=_f32(d, o + 0x2E), activity_unc_pct=_f32(d, o + 0x32),
            activity_units=_str(d, o + 0x36, 16), quantity=_f32(d, o + 0x46),
            quantity_units=_str(d, o + 0x4E, 16), rate_cps=struct.unpack_from("<d", d, o + 0x5E)[0],
            rate_unc_pct=_f32(d, o + 0x66), efficiency=_f32(d, o + 0x6A),
            efficiency_unc_pct=_f32(d, o + 0x6E), measured=_dt(d, o + 0x7A)))
    return out


def certificate_from_aptec(records: Sequence[AptecSourceRecord]) -> list[CertLine]:
    """Certificate lines (Aptec's own energies, yields, half-lives and activities)."""
    out = []
    for r in records:
        a = r.total_activity_bq
        if not r.nuclide or not a or a <= 0 or r.yield_ <= 0:
            continue
        out.append(CertLine(r.nuclide, float(r.energy), float(r.yield_), float(a),
                            float(a) * max(r.activity_unc_pct, 0.0) / 100.0, r.ref_date,
                            r.half_life_s if r.half_life_s > 0 else None))
    return sorted(out, key=lambda l: l.energy)


# ------------------------------------------------------------------ measured points


@dataclass
class EfficiencyPoint:
    energy: float
    efficiency: float
    unc: float                       # absolute, 1 sigma
    nuclide: str = ""
    net_area: Optional[float] = None
    net_unc: Optional[float] = None
    activity_t0: Optional[float] = None   # Bq at measurement start
    intensity: Optional[float] = None
    u_count_rel: float = 0.0
    u_ref_rel: float = 0.0           # certificate activity + intensity
    use: bool = True
    manual: bool = False
    note: str = ""
    u_act_rel: float = 0.0           # certificate activity (shared by the lines of `group`)
    u_int_rel: float = 0.0           # emission probability (independent per line)
    group: str = ""                  # correlation group of the activity component (nuclide)

    @property
    def rel_unc(self) -> float:
        return self.unc / self.efficiency if self.efficiency > 0 else float("inf")


def _peak_tolerance(p, energy: float) -> float:
    fw = p.fwhm_kev or 0.0
    return max(1.0, 0.6 * fw, 0.002 * energy)


def match_peak(peaks, energy: float, used: Optional[set] = None):
    """Nearest fitted peak to `energy` within tolerance, or None."""
    best, bd = None, None
    for p in peaks:
        if p.energy is None or p.net_area <= 0:
            continue
        dd = abs(p.energy - energy)
        if dd <= _peak_tolerance(p, energy) and (bd is None or dd < bd):
            best, bd = p, dd
    return best


def measure_efficiency(spectrum, cert: Sequence[CertLine], peaks=None,
                       background=None, min_sig: float = 3.0) -> list[EfficiencyPoint]:
    """Measured FEP efficiency points of the certified lines found in `spectrum`.

    `background`: optional background spectrum, subtracted peak by peak (live-time
    normalised) with the sample fit's own estimator (analysis.background.BackgroundFitter),
    so blends are split identically in both spectra.  Lines without a matching peak are skipped.
    Lines of different nuclides falling on the same peak are flagged and not used.
    """
    from .peaks import find_peaks
    if not spectrum.energy_coeffs:
        raise ValueError("the calibration spectrum has no energy calibration")
    if not spectrum.live_time:
        raise ValueError("the calibration spectrum has no live time")
    from .background import BackgroundFitter
    from .peaks import FitReport
    rep = None
    if peaks is None:
        rep = FitReport() if background is not None else None
        peaks = find_peaks(spectrum, min_sig=min_sig, report=rep)
    bkg_under: dict = {}
    if background is not None:
        bkg_under = BackgroundFitter(spectrum, background).under_peaks(peaks, rep)
    t0 = spectrum.start_time
    owners: dict[int, list[CertLine]] = {}
    found = []
    for ln in cert:
        if not ln.use:
            continue
        p = match_peak(peaks, ln.energy)
        if p is None:
            continue
        owners.setdefault(id(p), []).append(ln)
        found.append((ln, p))
    pts = []
    for ln, p in found:
        others = {o.nuclide for o in owners[id(p)]} - {ln.nuclide}
        n, un = float(p.net_area), float(p.net_area_unc)
        note = ""
        if id(p) in bkg_under:
            nb, ub = bkg_under[id(p)]
            n -= nb
            un = math.hypot(un, ub)
            note = "background peak subtracted"
        # sum of intensities of lines of the same nuclide on that peak (unresolved doublets)
        same = [o for o in owners[id(p)] if o.nuclide == ln.nuclide]
        if same and same[0] is not ln:
            continue
        inten = sum(o.intensity for o in same)
        dt = (t0 - ln.ref_date).total_seconds() if (t0 and ln.ref_date) else 0.0
        a0 = ln.activity * decay_factor(ln.half_life_s, dt)
        c = counting_decay_factor(ln.half_life_s, spectrum.real_time or spectrum.live_time)
        if n <= 0 or a0 <= 0 or inten <= 0:
            continue
        eff = n / (spectrum.live_time * a0 * c * inten)
        ur = (un / n) if n > 0 else 1.0
        ua = ln.activity_unc / ln.activity if ln.activity else 0.0
        ui = (math.sqrt(sum(o.intensity_unc ** 2 for o in same)) / inten) if inten else 0.0
        uref = math.hypot(ua, ui)
        pt = EfficiencyPoint(ln.energy if len(same) == 1 else p.energy, eff, eff * math.hypot(ur, uref),
                             ln.nuclide, n, un, a0, inten, ur, uref, note=note,
                             u_act_rel=ua, u_int_rel=ui, group=ln.nuclide)
        if others:
            pt.use = False
            pt.note = ("interference: " + ", ".join(sorted(others)) + "; " + pt.note).strip("; ")
        if not ln.ref_date or not t0:
            pt.note = (pt.note + "; no decay correction (date missing)").strip("; ")
        if ln.nuclide in TCS_NUCLIDES:
            pt.note = (pt.note + "; " + TCS_NOTE).strip("; ")
        pts.append(pt)
    return sorted(pts, key=lambda q: q.energy)


# ------------------------------------------------------------------ curve


@dataclass
class EfficiencyCurve:
    model: str = "loglog"            # "loglog" | "two_branch"
    params: list[float] = field(default_factory=list)
    cov: list[list[float]] = field(default_factory=list)
    order: int = 3                   # loglog order, or low branch order
    order_high: int = 2              # two_branch: high branch order
    e_ref: float = E0_LOGLOG         # E0 (loglog) or crossover Ec (two_branch), keV
    u_sys_rel: float = 0.0           # added to the curve uncertainty (older curves only)
    u_common_rel: float = 0.0        # common standard component included in the fit covariance
    cov_method: str = ""             # "gls" (Release D) or "" (older: independent weights + u_sys)
    selection: str = ""              # how the model orders were chosen
    u_model_rel: float = 0.0         # model (interpolation) error from leave-one-out residuals
    warnings: list = field(default_factory=list)   # points to review (large residuals ...)
    chi2: float = 0.0
    dof: int = 0
    e_min: float = 0.0
    e_max: float = 0.0
    points: list[EfficiencyPoint] = field(default_factory=list)
    geometry: str = ""
    detector: str = ""
    geometry_record: dict = field(default_factory=dict)   # lab.detector.MeasurementGeometry.to_dict()
    validation_status: str = "unvalidated"                 # "validated" only after an explicit check
    date: str = ""
    name: str = ""
    source: str = ""
    note: str = ""

    # --- evaluation
    def _design(self, e) -> np.ndarray:
        e = np.atleast_1d(np.asarray(e, dtype=float))
        x = np.log(e / self.e_ref)
        if self.model == "two_branch":
            lo, hi = self.order, self.order_high
            m = np.zeros((len(e), 1 + lo + hi))
            m[:, 0] = 1.0
            low = e < self.e_ref
            for i in range(1, lo + 1):
                m[:, i] = np.where(low, x ** i, 0.0)
            for i in range(1, hi + 1):
                m[:, lo + i] = np.where(low, 0.0, x ** i)
            return m
        return np.vander(x, self.order + 1, increasing=True)

    def efficiency(self, energy):
        v = np.exp(self._design(energy) @ np.asarray(self.params, dtype=float))
        return float(v[0]) if np.ndim(energy) == 0 else v

    def rel_uncertainty(self, energy):
        """Relative 1-sigma uncertainty of eps(E) (fit covariance + u_sys)."""
        g = self._design(energy)
        c = np.asarray(self.cov, dtype=float) if self.cov else np.zeros((g.shape[1], g.shape[1]))
        v = np.einsum("ij,jk,ik->i", g, c, g) + self.u_sys_rel ** 2 + self.u_model_rel ** 2
        r = np.sqrt(np.maximum(v, 0.0))
        return float(r[0]) if np.ndim(energy) == 0 else r

    def uncertainty(self, energy):
        return self.efficiency(energy) * self.rel_uncertainty(energy)

    def in_range(self, energy: float, margin: float = 0.05) -> bool:
        return self.e_min * (1 - margin) <= energy <= self.e_max * (1 + margin)

    def residuals(self) -> list[tuple[EfficiencyPoint, float, float]]:
        """(point, residual %, normalised residual) for every point."""
        out = []
        for p in self.points:
            f = self.efficiency(p.energy)
            out.append((p, 100.0 * (p.efficiency - f) / f, (p.efficiency - f) / p.unc if p.unc > 0 else 0.0))
        return out

    @property
    def reduced_chi2(self) -> float:
        return self.chi2 / self.dof if self.dof > 0 else 0.0

    def describe(self) -> str:
        if self.model == "two_branch":
            return f"two-branch log-log, Ec = {self.e_ref:g} keV, orders {self.order}/{self.order_high}"
        return f"log-log polynomial, order {self.order}"

    # --- persistence
    def to_dict(self) -> dict:
        d = asdict(self)
        d["format"] = "spectramaster-efficiency-1"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "EfficiencyCurve":
        d = dict(d)
        d.pop("format", None)
        pts = [EfficiencyPoint(**p) for p in d.pop("points", [])]
        known = {f for f in cls.__dataclass_fields__}
        c = cls(**{k: v for k, v in d.items() if k in known})
        c.points = pts
        return c

    def save(self, path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=1, ensure_ascii=False), encoding="utf-8")
        return path


def load_curve(path) -> EfficiencyCurve:
    return EfficiencyCurve.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def default_curve_dir() -> Path:
    """User folder for efficiency curves (env SPECTRAMASTER_EFF_DIR overrides)."""
    env = os.environ.get("SPECTRAMASTER_EFF_DIR")
    if env:
        return Path(env)
    base = os.environ.get("APPDATA")
    return (Path(base) / "SpectraMaster" / "efficiency") if base else (Path.home() / ".spectramaster" / "efficiency")


def list_curves(folder=None) -> list[Path]:
    f = Path(folder) if folder else default_curve_dir()
    return sorted(f.glob("*.json")) if f.is_dir() else []


def fit_efficiency(points: Sequence[EfficiencyPoint], model: str = "loglog", order: Optional[int] = None,
                   crossover: float = 200.0, order_high: Optional[int] = None, u_sys_rel: Optional[float] = None,
                   birge: bool = True, **meta) -> EfficiencyCurve:
    """Generalised least-squares fit of ln(eps); see the module docstring.

    Orders left as None (and ``crossover="auto"`` for the two-branch model) are chosen by
    leave-one-out cross-validation (:func:`select_orders`): the simplest model that predicts
    each point best from the others, so a branch with few points does not get a polynomial
    that swings between them.  Explicit orders are used as given.

    ``u_sys_rel``: relative uncertainty common to every point of the standard (e.g. the
    gravimetric preparation of a mixed standard) when the certificate states one; it enters
    the covariance of the points, not the curve afterwards.  None or 0 = not stated.
    """
    use = [p for p in points if p.use and p.efficiency > 0 and p.energy > 0]
    auto_x = model == "two_branch" and (crossover is None or str(crossover).lower() == "auto")
    selection = ""
    if order is None or (model == "two_branch" and order_high is None):
        fixed_x = None if (auto_x or model != "two_branch") else float(crossover)
        order, order_high, crossover, score = select_orders(points, model, fixed_x, order, order_high)
        selection = (f"orders chosen by leave-one-out cross-validation (mean squared normalised "
                     f"prediction error {score:.2f})")
    elif auto_x:
        crossover = auto_crossover(points, order, order_high)
    if model not in ("loglog", "two_branch"):
        raise ValueError(f"unknown efficiency model {model!r}")
    if model == "loglog":
        if not 1 <= order <= 5:
            raise ValueError("log-log order must be 1..5")
        curve = EfficiencyCurve(model="loglog", order=order, e_ref=E0_LOGLOG)
    else:
        curve = EfficiencyCurve(model="two_branch", order=order, order_high=order_high, e_ref=float(crossover))
    npar = curve._design(np.array([100.0])).shape[1]
    if len(use) < npar:
        raise ValueError(f"{len(use)} usable points for {npar} parameters - lower the order or add points")
    if model == "two_branch":
        nlo = sum(1 for p in use if p.energy < crossover)
        nhi = len(use) - nlo
        if nlo < order or nhi < order_high:
            raise ValueError(f"crossover {crossover:g} keV leaves {nlo} points below / {nhi} above")
    e = np.array([p.energy for p in use])
    y = np.log([p.efficiency for p in use])
    u_common = float(u_sys_rel or 0.0)
    V = point_covariance(use, u_common)
    a = curve._design(e)
    try:
        L = np.linalg.cholesky(V)
    except np.linalg.LinAlgError:
        L = np.linalg.cholesky(V + np.eye(len(use)) * 1e-12)
    aw = np.linalg.solve(L, a)                 # whitened design and data
    yw = np.linalg.solve(L, y)
    params, *_ = np.linalg.lstsq(aw, yw, rcond=None)
    cov = np.linalg.pinv(aw.T @ aw)
    res = yw - aw @ params
    chi2 = float(res @ res)
    dof = len(use) - npar
    if birge and dof > 0 and chi2 / dof > 1.0:
        cov = cov * (chi2 / dof)
    curve.params = [float(v) for v in params]
    curve.cov = [[float(v) for v in row] for row in cov]
    curve.chi2, curve.dof = chi2, dof
    curve.u_sys_rel = 0.0
    curve.u_common_rel = u_common
    curve.cov_method = "gls"
    curve.selection = selection
    curve.u_model_rel = model_error(points, model, order, order_high, float(crossover) if model == "two_branch"
                                    else 200.0)
    curve.e_min, curve.e_max = float(e.min()), float(e.max())
    curve.points = list(points)
    curve.warnings = []
    for p, r_pct, z in curve.residuals():
        if p.use and abs(z) > OUTLIER_Z:
            curve.warnings.append(f"{p.nuclide} {p.energy:.1f} keV: {r_pct:+.1f} % from the curve "
                                  f"({z:+.1f} sigma) - check interferences, summing and the peak fit")
    curve.date = meta.pop("date", "") or datetime.now().strftime("%Y-%m-%d %H:%M")
    for k, v in meta.items():
        if hasattr(curve, k):
            setattr(curve, k, v)
    return curve


OUTLIER_Z = 3.0                  # calibration points this far from the curve are listed for review
LOO_ORDERS = {"loglog": [(o, None) for o in (1, 2, 3, 4)],
              "two_branch": [(lo, hi) for lo in (1, 2, 3) for hi in (1, 2, 3)]}


def loo_score(points: Sequence[EfficiencyPoint], model: str, order: int, order_high: int = 2,
              crossover: float = 200.0) -> Optional[float]:
    """Mean squared normalised leave-one-out prediction error of ln(eps) (None if a point
    cannot be left out: too few points for the parameters or for a branch)."""
    use = [p for p in points if p.use and p.efficiency > 0 and p.energy > 0]
    probe = EfficiencyCurve(model=model, order=order, order_high=order_high or 0,
                            e_ref=E0_LOGLOG if model == "loglog" else float(crossover))
    e = np.array([p.energy for p in use])
    y = np.log([p.efficiency for p in use])
    s = np.array([max(p.rel_unc, 1e-6) if math.isfinite(p.rel_unc) else 1.0 for p in use])
    a = probe._design(e)
    npar = a.shape[1]
    errs = []
    for i in range(len(use)):
        keep = np.arange(len(use)) != i
        if keep.sum() <= npar:
            return None
        if model == "two_branch":
            lo = int(np.sum(e[keep] < crossover))
            if lo < order or keep.sum() - lo < order_high:
                return None
        aw = a[keep] / s[keep, None]
        par, *_ = np.linalg.lstsq(aw, y[keep] / s[keep], rcond=None)
        errs.append(((y[i] - a[i] @ par) / s[i]) ** 2)
    return float(np.mean(errs))


def _loo_residuals(points, model, order, order_high, crossover):
    use = [p for p in points if p.use and p.efficiency > 0 and p.energy > 0]
    probe = EfficiencyCurve(model=model, order=order, order_high=order_high or 0,
                            e_ref=E0_LOGLOG if model == "loglog" else float(crossover))
    e = np.array([p.energy for p in use])
    y = np.log([p.efficiency for p in use])
    s = np.array([max(p.rel_unc, 1e-6) if math.isfinite(p.rel_unc) else 1.0 for p in use])
    a = probe._design(e)
    out = []
    for i in range(len(use)):
        keep = np.arange(len(use)) != i
        if keep.sum() <= a.shape[1]:
            return None
        if model == "two_branch":
            lo = int(np.sum(e[keep] < crossover))
            if lo < order or keep.sum() - lo < (order_high or 0):
                return None
        aw = a[keep] / s[keep, None]
        par, *_ = np.linalg.lstsq(aw, y[keep] / s[keep], rcond=None)
        # prediction variance of the left-out point from the reduced fit
        try:
            cov = np.linalg.inv(aw.T @ aw)
            vp = float(a[i] @ cov @ a[i])
        except np.linalg.LinAlgError:
            vp = 0.0
        out.append((float(y[i] - a[i] @ par), float(s[i]), vp))
    return out


def model_error(points: Sequence[EfficiencyPoint], model: str, order: int, order_high: Optional[int] = 2,
                crossover: float = 200.0) -> float:
    """Relative interpolation (model) error: the part of the leave-one-out prediction errors
    not explained by the point uncertainties and the prediction uncertainty,
    u_model^2 = max(0, mean(r_i^2 - s_i^2 - v_i)).  Added to the curve uncertainty; 0 when the
    points do not allow leaving one out."""
    res = _loo_residuals(points, model, order, order_high, crossover)
    if not res:
        return 0.0
    ex = float(np.mean([r * r - s * s - v for r, s, v in res]))
    return math.sqrt(ex) if ex > 0 else 0.0


def select_orders(points: Sequence[EfficiencyPoint], model: str, crossover: Optional[float] = None,
                  order: Optional[int] = None, order_high: Optional[int] = None):
    """(order, order_high, crossover, score) with the smallest leave-one-out error; fixed
    arguments are kept; ``crossover`` None searches between measured points (two-branch)."""
    if model not in LOO_ORDERS:
        raise ValueError(f"unknown efficiency model {model!r}")
    cands = [(o, h) for o, h in LOO_ORDERS[model] if (order is None or o == order)
             and (order_high is None or model == "loglog" or h == order_high)]
    if model == "two_branch" and crossover is None:
        es = sorted({p.energy for p in points if p.use and p.efficiency > 0})
        xs = [math.sqrt(a * b) for a, b in zip(es, es[1:]) if 80.0 <= math.sqrt(a * b) <= 600.0]
    else:
        xs = [crossover if crossover is not None else 200.0]
    best = None
    for o, h in cands:
        npar = 1 + o + (h or 0) if model == "two_branch" else o + 1
        for x in xs:
            sc = loo_score(points, model, o, h or 2, x)
            if sc is None:
                continue
            key = (sc, npar)                      # ties go to the simpler model
            if best is None or key < best[0]:
                best = (key, o, h, x)
    if best is None:
        raise ValueError("too few points to choose the model orders - give them explicitly")
    (sc, _n), o, h, x = best
    return o, (h if h is not None else 2), (round(float(x), 1) if model == "two_branch" else x), sc


def point_covariance(points: Sequence[EfficiencyPoint], u_common: float = 0.0) -> np.ndarray:
    """Covariance of ln(eps) of the points (see the module docstring)."""
    n = len(points)
    V = np.zeros((n, n))
    for i, p in enumerate(points):
        tot = max(p.rel_unc, 1e-6) if math.isfinite(p.rel_unc) else 1.0
        if p.manual or not (p.u_act_rel or p.u_int_rel or p.u_count_rel):
            V[i, i] = tot ** 2                       # no breakdown: independent
            continue
        V[i, i] = p.u_count_rel ** 2 + p.u_int_rel ** 2 + p.u_act_rel ** 2
        for j in range(i + 1, n):
            q = points[j]
            if p.group and q.group == p.group and not q.manual:
                V[i, j] = V[j, i] = p.u_act_rel * q.u_act_rel
    if u_common:
        V += u_common ** 2
    return V


def auto_crossover(points: Sequence[EfficiencyPoint], order: int = 2, order_high: int = 2,
                   e_lo: float = 80.0, e_hi: float = 600.0) -> float:
    """Crossover energy (between two measured points) giving the smallest reduced chi^2."""
    es = sorted({p.energy for p in points if p.use and p.efficiency > 0})
    cands = [math.sqrt(a * b) for a, b in zip(es, es[1:]) if e_lo <= math.sqrt(a * b) <= e_hi]
    best, bc = None, None
    for c in cands:
        try:
            cv = fit_efficiency(points, "two_branch", order=order, crossover=c, order_high=order_high,
                                birge=False)
        except (ValueError, np.linalg.LinAlgError):
            continue
        score = cv.reduced_chi2 if cv.dof > 0 else cv.chi2
        if bc is None or score < bc - 1e-12:
            best, bc = c, score
    if best is None:
        raise ValueError("no valid crossover energy for the two-branch model - use the log-log model")
    return float(round(best, 1))


VALIDATION_MAX_Z = 3.0           # independent check: no point further than this
VALIDATION_MAX_MEAN_Z2 = 2.0     # and mean z^2 at most this (chi^2/n; ~ 95 % for a few points)


def validate_curve(curve: EfficiencyCurve, points: Sequence[EfficiencyPoint]) -> dict:
    """Independent check of a curve with points NOT used in its fit (another source, the same
    detector and geometry).  z = (eps_point - eps_curve) / sqrt(u_point^2 + u_curve^2).

    Returns {"rows": [...], "n": n, "max_abs_z", "mean_z2", "consistent": bool, "message"}.
    ``consistent`` applies VALIDATION_MAX_Z and VALIDATION_MAX_MEAN_Z2; the decision to mark the
    calibration as validated stays with the user (CalibrationRecord.set_validation)."""
    rows = []
    used = {(round(p.energy, 3), p.nuclide) for p in curve.points if p.use}
    for p in points:
        if not p.use or p.efficiency <= 0:
            continue
        f = float(curve.efficiency(p.energy))
        u = math.hypot(p.unc, float(curve.uncertainty(p.energy)))
        rows.append({"nuclide": p.nuclide, "energy": p.energy, "point": p.efficiency, "curve": f,
                     "dev_pct": 100.0 * (p.efficiency / f - 1.0), "z": (p.efficiency - f) / u if u > 0 else 0.0,
                     "in_range": curve.in_range(p.energy, margin=0.0),
                     "also_in_fit": (round(p.energy, 3), p.nuclide) in used})
    indep = [r for r in rows if not r["also_in_fit"]]
    if not indep:
        return {"rows": rows, "n": 0, "max_abs_z": None, "mean_z2": None, "consistent": False,
                "message": "no independent points (every point was used in the fit)"}
    zs = [r["z"] for r in indep]
    mz = max(abs(z) for z in zs)
    m2 = sum(z * z for z in zs) / len(zs)
    ok = mz <= VALIDATION_MAX_Z and m2 <= VALIDATION_MAX_MEAN_Z2
    msg = (f"{len(indep)} independent point(s): largest |z| = {mz:.1f}, mean z^2 = {m2:.2f} -> "
           + ("consistent with the curve" if ok else "NOT consistent with the curve"))
    if any(not r["in_range"] for r in indep):
        msg += "; some points lie outside the calibrated range"
    return {"rows": rows, "n": len(indep), "max_abs_z": mz, "mean_z2": m2, "consistent": ok, "message": msg}


def manual_point(energy: float, efficiency: float, rel_unc_pct: float = 2.0, note: str = "") -> EfficiencyPoint:
    return EfficiencyPoint(float(energy), float(efficiency), float(efficiency) * rel_unc_pct / 100.0,
                           nuclide="manual", u_count_rel=rel_unc_pct / 100.0, manual=True, note=note)


def compare_with_aptec(points: Sequence[EfficiencyPoint], records: Sequence[AptecSourceRecord],
                       tol_kev: float = 1.5) -> list[dict]:
    """Our measured points vs Aptec's stored efficiencies (same energies)."""
    out = []
    for r in records:
        if r.efficiency <= 0:
            continue
        p = min(points, key=lambda q: abs(q.energy - r.energy), default=None)
        if p is None or abs(p.energy - r.energy) > tol_kev:
            out.append({"nuclide": r.nuclide, "energy": r.energy, "aptec": r.efficiency, "ours": None,
                        "diff_pct": None, "aptec_unc_pct": r.efficiency_unc_pct})
            continue
        out.append({"nuclide": r.nuclide, "energy": r.energy, "aptec": r.efficiency, "ours": p.efficiency,
                    "ours_unc_pct": 100 * p.rel_unc, "aptec_unc_pct": r.efficiency_unc_pct,
                    "diff_pct": 100.0 * (p.efficiency - r.efficiency) / r.efficiency,
                    "aptec_rate": r.rate_cps, "ours_rate": None})
    return out

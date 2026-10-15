"""Aptec-style analysis: Peak Search (P), Identify (I), Background Subtract (B) and Quantify (Q).

Pure functions, no GUI.  What each step does follows the Aptec PCMCA/WIN 6.31 help (Peak
Calculation Setup, S_Ident Setup Identification, Setup Background Subtract, Setup
Quantification, MDA Definition); details the help does not give were taken from what Aptec stored
in its spectrum files and are marked below.  Comparison protocols and results:
``docs/baseline/aptec_*_protocol.md``.

Peak Search
-----------
The help describes a multi-pass search: "peaks" are found with a rate-of-change-of-slope
algorithm, ROIs are set around them, their backgrounds are calculated from the end points of
the ROI Properties, and ROIs whose statistical precision is worse than *Max Peak Error* are
rejected, the backgrounds and statistics being recalculated as ROIs are rejected.

* Acceptance: 1-sigma net error (%) below Max Peak Error.  The help says "Net Error * Error
  Sigma"; the stored ROIs (97 % of 35 000 in the lab archive below the limit at 1 sigma, 68 %
  at the error sigma) show that the 1-sigma error is compared.
* ROI edges: each edge is the channel of lowest count between it and the peak top (outermost of
  equal minima) -- true of 86 % of the stored edges.
* Our choices (tuned on a development set, not documented by Aptec): peak tops are the maxima of
  the 5-point binomial-smoothed data; the search window of each edge runs down the smoothed
  slope to its foot; neighbouring ROIs share the edge channel; ROIs narrower than 8 channels
  are dropped.  Agreement with the stored ROIs is about 76 % found / 64 % precision: this
  search does **not** reproduce Aptec's ROIs exactly.

Identify
--------
Library lines within the match tolerance of the ROI centroid energy are candidates.  The
tolerance is ``FWHM fraction x ROI FWHM`` (the fixed tolerance when the ROI has no valid FWHM,
or when the fixed match type is chosen).  An isotope is accepted when the yields of its lines
with an ROI add up to at least *Fraction Limit* % of the yields of all its lines inside the
spectrum's energy range (S_Ident).  Among accepted candidates an ROI takes the line of the
isotope with most lines found, then the nearest energy (taken from the stored identifications;
not documented).

Quantify
--------
``activity = net rate / (efficiency x yield)`` (yield omitted for emission-rate units such as
gamma/s), divided by the sample quantity when selected, multiplied by the W / X / Y constants
when selected, decay-corrected to the activity time, converted to the activity units.  ROIs not
quantified carry their net count rate (as Aptec stores).  The efficiency is taken at the ROI
centroid energy, not at the library line energy: with it all 49 activities Aptec stored in the
quantified files agree within 0.003 %; at the line energy only 45 agree within 0.5 % (found
after the pre-registered comparison, which used the line energy and failed).
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np

from .aptec_roi import AptecRoi, RoiProperties, analyze_rois

__all__ = ["PeakSearchSetup", "peak_search", "LibraryLine", "read_aptec_library", "lines_from_library", "IdentifySetup", "identify",
           "Identification", "MIN_ROI_WIDTH", "SEARCH_SMOOTH"]

MIN_ROI_WIDTH = 8           # channels (our choice, see module docstring)
SEARCH_SMOOTH = 5           # binomial smoothing used to find the peak tops (our choice)


# ============================================================================ peak search
@dataclass
class PeakSearchSetup:
    """Aptec *Peak Search* setup (Shift+P)."""
    max_error: float = 30.0             # Max Peak Error, % (1 sigma, see module docstring)
    partial: bool = False               # search only start..stop
    start: int = 0
    stop: int = 0

    def validate(self) -> "PeakSearchSetup":
        if not 0 < float(self.max_error) <= 1000:
            raise ValueError("Max Peak Error must be a positive percentage")
        if self.partial and int(self.stop) <= int(self.start):
            raise ValueError("the stop channel must be above the start channel")
        return self

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "PeakSearchSetup":
        known = set(cls.__dataclass_fields__)
        try:
            return cls(**{k: v for k, v in (d or {}).items() if k in known}).validate()
        except (ValueError, TypeError):
            return cls()


def _smooth(y: np.ndarray, points: int) -> np.ndarray:
    w = np.array([math.comb(points - 1, k) for k in range(points)], dtype=float)
    w /= w.sum()
    return np.convolve(y, w, mode="same") / np.convolve(np.ones_like(y), w, mode="same")


def _candidates(y: np.ndarray) -> list[tuple[int, int]]:
    s = _smooth(y, SEARCH_SMOOTH)
    n = len(s)
    rois: list[tuple[int, int]] = []
    for i in range(1, n - 1):
        if not (s[i] > s[i - 1] and s[i] >= s[i + 1]):
            continue
        a = i
        while a > 0 and s[a - 1] < s[a]:
            a -= 1
        b = i
        while b < n - 1 and s[b + 1] < s[b]:
            b += 1
        seg = y[a:i + 1]
        a = a + int(np.flatnonzero(seg == seg.min())[0])
        seg = y[i:b + 1]
        b = i + int(np.flatnonzero(seg == seg.min())[-1])
        rois.append((a, b))
    out: list[tuple[int, int]] = []
    for a, b in rois:                       # neighbours share their edge channel
        if out and a < out[-1][1]:
            a = out[-1][1]
        if b > a:
            out.append((a, b))
    return out


def peak_search(counts: Sequence[float], setup: Optional[PeakSearchSetup] = None,
                props: Optional[RoiProperties] = None, live_time: Optional[float] = None,
                progress: Optional[Callable[[int], None]] = None) -> list[AptecRoi]:
    """Aptec-style peak search: the accepted ROIs with their statistics (indices into counts)."""
    setup = (setup or PeakSearchSetup()).validate()
    props = (props or RoiProperties()).validate()
    y = np.asarray(counts, dtype=float)
    rois = [r for r in _candidates(y) if r[1] - r[0] + 1 >= MIN_ROI_WIDTH]
    if setup.partial:
        rois = [r for r in rois if r[0] >= setup.start and r[1] <= setup.stop]
    stats: list[AptecRoi] = []
    for k in range(100):                    # reject, recalculate backgrounds, until stable
        if progress is not None:
            progress(k)
        if not rois:
            return []
        stats = analyze_rois(y, rois, props, live_time)
        keep = [i for i, st in enumerate(stats)
                if st.net > 0 and st.err_pct is not None and st.err_pct < float(setup.max_error)]
        if len(keep) == len(rois):
            break
        rois = [rois[i] for i in keep]
    return stats


# ============================================================================ library
@dataclass
class LibraryLine:
    isotope: str
    energy: float                       # library energy units (keV)
    yield_: float                       # fraction per decay
    half_life_s: float
    convert_factor: float = 1.0
    identify_only: bool = False
    force_mda: bool = False


def read_aptec_library(path) -> tuple[list[LibraryLine], str]:
    """Lines and energy units of an Aptec isotope library (``.lib``, Version 6.31).

    Layout as found in the libraries installed with Aptec 6.31 (not published): header of 128
    bytes ("VERSION6.31", line count at byte 16, energy units at byte 18), then 64-byte line
    records -- isotope name (12 bytes), energy (float), yield (float), half-life in seconds
    (double), convert factor (float at byte 32).  The flag bits of the records are not decoded
    (all zero in the installed libraries)."""
    d = Path(path).read_bytes()
    if not d.startswith(b"VERSION"):
        raise ValueError("not an Aptec isotope library")
    n = struct.unpack_from("<h", d, 16)[0]
    units = d[18:26].split(b"\0", 1)[0].decode("latin-1").strip() or "keV"
    if n < 0 or 128 + 64 * n > len(d):
        raise ValueError("truncated Aptec isotope library")
    lines = []
    for k in range(n):
        o = 128 + 64 * k
        name = d[o:o + 12].split(b"\0", 1)[0].decode("latin-1").strip()
        e, y = struct.unpack_from("<2f", d, o + 12)
        hl = struct.unpack_from("<d", d, o + 20)[0]
        cf = struct.unpack_from("<f", d, o + 32)[0]
        if name and e > 0:
            lines.append(LibraryLine(name, float(e), float(y), float(hl), float(cf) or 1.0))
    lines.sort(key=lambda l: l.energy)
    return lines, units


def lines_from_library(source=None, min_intensity: float = 0.0) -> list[LibraryLine]:
    """Gamma lines of a SpectraMaster library (bundled by default) as identification lines
    (yield = intensity / 100)."""
    from .library import load_library
    out = []
    for nd in load_library(source).values():
        for l in nd.gammas(min_intensity):
            if l.intensity > 0:
                out.append(LibraryLine(nd.name, float(l.energy), float(l.intensity) / 100.0,
                                       float(nd.half_life_s or 0.0)))
    out.sort(key=lambda l: l.energy)
    return out


# ============================================================================ identify
@dataclass
class IdentifySetup:
    """Aptec *Setup Identification* (Shift+I, S_Ident)."""
    library: str = ""                   # path of an Aptec .lib ("" = SpectraMaster library)
    match_by_fwhm: bool = True          # tolerance = fwhm_fraction x ROI FWHM (else fixed)
    fwhm_fraction: float = 0.5
    fixed_tolerance: float = 0.75       # keV
    fraction_limit: float = 40.0        # %
    half_life_limit: float = 7.0
    half_life_reject: bool = False

    def validate(self) -> "IdentifySetup":
        if not 0 < float(self.fwhm_fraction) <= 10 or not 0 < float(self.fixed_tolerance) <= 1000:
            raise ValueError("the match tolerance must be positive")
        if not 0 <= float(self.fraction_limit) <= 100:
            raise ValueError("the fraction limit is a percentage")
        if float(self.half_life_limit) <= 0:
            raise ValueError("the half-life limit must be positive")
        return self

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "IdentifySetup":
        known = set(cls.__dataclass_fields__)
        try:
            return cls(**{k: v for k, v in (d or {}).items() if k in known}).validate()
        except (ValueError, TypeError):
            return cls()


@dataclass
class Identification:
    line: LibraryLine
    roi_energy: float
    tolerance: float
    fraction: float                     # % of the isotope's yield found
    lines_found: int


def identify(energies: Sequence[Optional[float]], fwhm_kev: Sequence[Optional[float]],
             lines: Sequence[LibraryLine], setup: Optional[IdentifySetup] = None,
             energy_range: Optional[tuple[float, float]] = None,
             elapsed_s: Optional[float] = None) -> list[Optional[Identification]]:
    """Line assigned to each ROI (None = not identified).

    ``energies``: ROI centroid energies; ``fwhm_kev``: ROI FWHM in energy units (None when not
    found); ``energy_range``: energies of the first and last channel (lines outside do not count
    in the fraction test); ``elapsed_s``: decay time used by the half-life test."""
    setup = (setup or IdentifySetup()).validate()
    tol = []
    for fw in fwhm_kev:
        if setup.match_by_fwhm and fw is not None and fw > 0:
            tol.append(float(setup.fwhm_fraction) * float(fw))
        else:
            tol.append(float(setup.fixed_tolerance))
    E = [None if e is None else float(e) for e in energies]
    lo, hi = energy_range if energy_range else (-math.inf, math.inf)

    def hit(line: LibraryLine) -> bool:
        return any(e is not None and abs(line.energy - e) <= t for e, t in zip(E, tol))

    by_iso: dict[str, list[LibraryLine]] = {}
    for line in lines:
        by_iso.setdefault(line.isotope, []).append(line)
    cand = [[l for l in lines if e is not None and abs(l.energy - e) <= t] for e, t in zip(E, tol)]
    score: dict[str, tuple[bool, float, int]] = {}
    for iso in {l.isotope for c in cand for l in c}:
        on = [l for l in by_iso[iso] if lo <= l.energy <= hi]
        total = sum(l.yield_ for l in on)
        found = [l for l in on if hit(l)]
        frac = 100.0 * sum(l.yield_ for l in found) / total if total > 0 else 0.0
        ok = total > 0 and frac >= float(setup.fraction_limit)
        hl = by_iso[iso][0].half_life_s
        if ok and setup.half_life_reject and elapsed_s and hl > 0 and elapsed_s / hl > float(setup.half_life_limit):
            ok = False
        score[iso] = (ok, frac, len(found))
    out: list[Optional[Identification]] = []
    for e, t, c in zip(E, tol, cand):
        c = [l for l in c if score[l.isotope][0]]
        if not c:
            out.append(None)
            continue
        best = min(c, key=lambda l: (-score[l.isotope][2], abs(l.energy - e)))
        s = score[best.isotope]
        out.append(Identification(best, e, t, s[1], s[2]))
    return out


# ============================================================================ quantify
@dataclass
class QuantifySetup:
    """Aptec *Setup Quantification* (Shift+Q)."""
    activity_units: str = "Bq"
    use_quantity: bool = True           # concentration: divide by the sample quantity
    use_total_quantity: bool = False    # total activity: x total quantity (with use_quantity)
    use_w: bool = False                 # multiply by the W / X / Y constants (Quantity Description)
    use_x: bool = False
    use_y: bool = False
    true_time_decay: bool = False       # correct the decay during the count (see quantify)

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "QuantifySetup":
        known = set(cls.__dataclass_fields__)
        try:
            return cls(**{k: v for k, v in (d or {}).items() if k in known})
        except TypeError:
            return cls()


@dataclass
class QuantResult:
    activity: Optional[float]           # in the activity units (per quantity when divided)
    activity_err_pct: Optional[float]   # 1 sigma, counting statistics and efficiency
    mda: Optional[float]
    factor: Optional[float]             # activity per net count rate
    flags: str = ""
    note: str = ""


def quantify(net_cps: float, net_err_pct: Optional[float], mda_cps: Optional[float], line: LibraryLine,
             efficiency: Optional[float], setup: QuantifySetup, *, live_time: Optional[float] = None,
             true_time: Optional[float] = None, start_time=None, activity_time=None,
             quantity: Optional[float] = None, total_quantity: Optional[float] = None,
             w: Optional[float] = None, x: Optional[float] = None, y: Optional[float] = None,
             efficiency_err_pct: float = 0.0) -> QuantResult:
    """Activity of one identified ROI (Aptec Quantify).

    ``activity = net rate / (efficiency x yield)`` in Bq (no yield for emission-rate units),
    decay-corrected from the count start to the activity time (``exp(ln2 / T1/2 x (start -
    activity time))``; flag ``>`` when that exceeds the float range), optionally for the decay
    during the count (``lambda T / (1 - exp(-lambda T))``, not applied when the count lasted more
    than 7 half-lives: flag ``t``), converted to the activity units, divided by the sample
    quantity, multiplied by the total quantity and the W / X / Y constants as selected.  The MDA
    is the ROI MDA count rate converted with the same factor.  ``efficiency`` is the efficiency at
    the ROI centroid energy (as Aptec, see the module docstring)."""
    from .aptec_calibration import activity_factor, is_emission_unit
    units = (setup.activity_units or "Bq").strip()
    per_bq = activity_factor(units)
    if per_bq is None:
        return QuantResult(None, None, None, None, note=f"unknown activity units {units!r}")
    if efficiency is None or efficiency <= 0:
        return QuantResult(None, None, None, None, note="no efficiency at this energy")
    emission = is_emission_unit(units)
    if not emission and line.yield_ <= 0:
        return QuantResult(None, None, None, None, note="line yield is zero")
    f = 1.0 / (efficiency * (1.0 if emission else line.yield_))
    flags = ""
    lam = math.log(2.0) / line.half_life_s if line.half_life_s and line.half_life_s > 0 else 0.0
    if lam and start_time is not None and activity_time is not None:
        arg = lam * (start_time - activity_time).total_seconds()
        if arg > 700:
            flags += ">"
            return QuantResult(None, None, None, None, flags=flags, note="decay correction overflow")
        f *= math.exp(arg)
    if lam and setup.true_time_decay and true_time:
        lt = lam * true_time
        if lt > 7 * math.log(2.0):
            flags += "t"
        elif lt > 1e-12:
            f *= lt / (1.0 - math.exp(-lt))
    f /= per_bq
    if setup.use_quantity:
        if not quantity:
            return QuantResult(None, None, None, None, note="sample quantity is missing")
        f /= quantity
        if setup.use_total_quantity and total_quantity:
            f *= total_quantity
    for use, c in ((setup.use_w, w), (setup.use_x, x), (setup.use_y, y)):
        if use and c:
            f *= c
    err = None
    if net_err_pct is not None:
        err = math.sqrt(net_err_pct ** 2 + efficiency_err_pct ** 2)
    act = net_cps * f
    mda = mda_cps * f if mda_cps is not None else None
    if mda is not None and act < mda:
        flags += "?"
    return QuantResult(act, err, mda, f, flags)


__all__ += ["QuantifySetup", "QuantResult", "quantify"]

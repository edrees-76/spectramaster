"""Nuclide identification from fitted peaks.

Scoring (per nuclide, all its library lines):

* Library lines closer than ~0.5 FWHM are merged (essential for NaI and for X-ray groups).
* Expected relative response of each line = intensity x approximate full-energy-peak
  efficiency shape (HPGe or NaI; low-energy roll-off, E^-alpha above the maximum).
* A peak matches a line within an energy tolerance derived from the peak FWHM and a
  calibration uncertainty term; match quality decays as a Gaussian of the offset.
* The activity scale k is estimated from the matched lines; for every unmatched line the
  expected area k x response is compared with the local detection limit (Currie L_D from
  the continuum around the line).  Only lines that should clearly have been seen count as
  "missing" - weak lines below the detection limit are never punished.
* confidence = explained fraction of the detectable response x energy-match quality x
  statistical evidence x penalties (strongest line missing, area ratios inconsistent).
* Interferences: greedy explanation - the best nuclide claims its peaks (expected areas);
  a later nuclide gets full credit for a shared peak only when a significant residual area
  is left, otherwise reduced credit.
* Natural series members get notes ("Bi-214 (U-238 series, Ra-226 daughter)") and a small
  mutual boost when several members are seen; background-typical nuclides are flagged.

Returns [] for an uncalibrated spectrum.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from . import NuclideMatch, Peak
from .library import Line, NuclideData, load_library
from .peaks import _dpoly, _poly, default_fwhm_kev, guess_detector

_INCLUDES: dict[str, tuple] = {}

SERIES_LABEL = {
    "Ra-226": "Ra-226 daughter", "U-238": "", "Th-228": "Th-228 daughter", "Ra-228": "Ra-228 daughter",
}


# ------------------------------------------------------------------ helpers
def efficiency_shape(energy, detector: str):
    """Approximate relative full-energy-peak efficiency (max ~1)."""
    e = np.maximum(np.asarray(energy, dtype=float), 1.0)
    if detector == "NaI":
        ec, ep, alpha = 25.0, 150.0, 0.9
    elif detector in ("LaBr3", "CZT"):
        ec, ep, alpha = 25.0, 120.0, 1.0
    else:   # HPGe p-type coaxial (conservative for low energies)
        ec, ep, alpha = 45.0, 130.0, 0.85
    roll = 1.0 - np.exp(-(e / ec) ** 3)
    return roll * np.minimum(1.0, (e / ep) ** (-alpha))


@dataclass
class _ELine:                 # effective (merged) library line
    energy: float
    rel: float                # intensity x efficiency (fraction)
    intensity: float          # % sum
    kind: str
    members: list[Line]


@dataclass
class _Cand:
    nd: NuclideData
    lines: list[_ELine]
    matches: dict = field(default_factory=dict)    # line idx -> (peak idx, quality)
    missing: list[int] = field(default_factory=list)
    k: float = 0.0
    conf: float = 0.0
    detail: str = ""
    evidence: float = 0.0
    slope: tuple = (0.0, 0.0)
    expected: object = None


class _Context:
    def __init__(self, spectrum, peaks: list[Peak], detector: str):
        self.s = spectrum
        self.det = detector
        y = np.asarray(spectrum.counts, dtype=float)
        self.y = y
        self.cs = np.concatenate([[0.0], np.cumsum(y)])
        n = len(y)
        ch = spectrum.first_channel + np.arange(n)
        self.e = _poly(spectrum.energy_coeffs, ch)
        self.emin = float(np.nanmin(self.e))
        self.emax = float(np.nanmax(self.e))
        self.increasing = bool(self.e[-1] > self.e[0])
        self.peaks = peaks
        self.application = "all"
        self.decayed: dict = {}        # nuclide -> half-lives elapsed since sampling (penalised only)
        self._ld: dict = {}
        self._fw: dict = {}
        self.pe = np.array([p.energy if p.energy is not None else -1e9 for p in peaks])
        # lowest usable energy: first peak region / LLD
        nz = np.nonzero(y > 0)[0]
        first = int(nz[0]) if len(nz) else 0
        self.start_idx = first + 3
        self.e_start = float(self.e[min(first + 3, n - 1)]) if self.increasing else self.emin
        # resolution model in keV
        widths = [(p.energy, p.fwhm_kev) for p in peaks if p.energy and p.fwhm_kev and p.significance > 8]
        base = default_fwhm_kev(np.array([100.0, 1000.0]), detector or "HPGe")
        self.fw_scale = 1.0
        if widths:
            r = [fw / float(default_fwhm_kev(e, detector or "HPGe")) for e, fw in widths]
            self.fw_scale = float(np.clip(np.median(r), 0.3, 5.0))
        del base

    def fwhm_kev(self, e: float) -> float:
        key = round(e, 1)
        v = self._fw.get(key)
        if v is None:
            v = self._fw[key] = self._fwhm_kev(e)
        return v

    def _fwhm_kev(self, e: float) -> float:
        if self.s.fwhm_coeffs:
            ch = self.channel_of(e)
            if ch is not None:
                # the FWHM calibration is a function of the absolute channel, as the energy one
                f = float(_poly(self.s.fwhm_coeffs, ch + self.s.first_channel))
                if 0 < f < 0.5 * max(e, 10.0) + 50:
                    return f
        return float(default_fwhm_kev(e, self.det or "HPGe")) * self.fw_scale

    def channel_of(self, e: float) -> Optional[float]:
        if not (self.emin <= e <= self.emax):
            return None
        if self.increasing:
            i = float(np.interp(e, self.e, np.arange(len(self.e))))
        else:
            i = float(np.interp(e, self.e[::-1], np.arange(len(self.e))[::-1]))
        return i

    def detection_limit(self, e: float) -> float:
        """Currie L_D (counts) for a peak at e from the local continuum (memoised)."""
        key = round(e, 2)
        v = self._ld.get(key)
        if v is None:
            v = self._ld[key] = self._detection_limit(e)
        return v

    def _detection_limit(self, e: float) -> float:
        i = self.channel_of(e)
        if i is None:
            return math.inf
        f_ch = self.fwhm_kev(e) / max(abs(float(_dpoly(self.s.energy_coeffs, self.s.first_channel + i))), 1e-9)
        f_ch = max(f_ch, 1.0)
        n = len(self.y)
        half = 1.25 * f_ch
        w = max(1.5 * f_ch, 2.0)

        def mean(a, b):
            a, b = int(max(a, 0)), int(min(b, n))
            if b <= a:
                return math.inf
            return (self.cs[b] - self.cs[a]) / (b - a)

        if i - half - w < self.start_idx:
            return math.inf       # at the LLD edge: no reliable continuum, no information
        left = mean(i - half - w, i - half)
        right = mean(i + half + 1, i + half + 1 + w)
        bpc = min(left, right)
        if not math.isfinite(bpc):
            bpc = max(left if math.isfinite(left) else 0.0, right if math.isfinite(right) else 0.0)
        B = bpc * 2 * half
        return 2.71 + 4.65 * math.sqrt(max(B, 0.0))

    def tolerance(self, e: float, peak: Optional[Peak] = None) -> float:
        fw = (peak.fwhm_kev if peak is not None and peak.fwhm_kev else None) or self.fwhm_kev(e)
        cal = 0.25 + 0.0006 * e if self.det != "NaI" else 0.01 * e
        return math.sqrt((0.45 * fw) ** 2 + cal ** 2)


def _effective_lines(nd: NuclideData, ctx: _Context, include_x: bool) -> list[_ELine]:
    lines = [l for l in nd.lines if (include_x or l.kind != "x") and ctx.e_start <= l.energy <= ctx.emax]
    eff = efficiency_shape([l.energy for l in lines], ctx.det) if lines else []
    groups: list[_ELine] = []
    for l, ef in sorted(zip(lines, eff), key=lambda t: t[0].energy):
        rel = l.intensity / 100.0 * float(ef)
        if l.kind == "x":
            rel *= 0.5          # X-ray yields/efficiency are uncertain; shared by many nuclides
        if l.kind == "a":
            rel *= 0.5          # annihilation depends on positron stopping around the source
        if groups and l.energy - groups[-1].energy < 0.7 * ctx.fwhm_kev(l.energy) and \
                (groups[-1].kind == l.kind or l.kind == "g" and groups[-1].kind == "g"):
            g = groups[-1]
            tot = g.rel + rel
            if tot > 0:
                g.energy = (g.energy * g.rel + l.energy * rel) / tot
            g.rel = tot
            g.intensity += l.intensity
            g.members.append(l)
        else:
            groups.append(_ELine(l.energy, rel, l.intensity, l.kind, [l]))
    return [g for g in groups if g.rel > 0]


def _peak_weight(p: Peak, kind: str = "g") -> float:
    note = p.note or ""
    if "escape" in note or "sum peak" in note or "backscatter" in note or "Compton edge" in note:
        return 0.3
    if "annihilation" in note and kind != "a":
        return 0.3     # a 511 keV peak is weak evidence for a gamma line at ~511
    return 1.0


def _match_candidate(nd: NuclideData, ctx: _Context, include_x: bool) -> Optional[_Cand]:
    lines = _effective_lines(nd, ctx, include_x)
    if not lines:
        return None
    cand = _Cand(nd, lines)
    for li, ln in enumerate(lines):
        if len(ctx.pe) == 0:
            break
        j = int(np.argmin(np.abs(ctx.pe - ln.energy)))
        p = ctx.peaks[j]
        d = abs(ctx.pe[j] - ln.energy)
        tol = ctx.tolerance(ln.energy, p)
        if d <= tol:
            q = math.exp(-0.5 * (d / ((0.9 if ctx.det == 'NaI' else 0.6) * tol)) ** 2)
            cand.matches[li] = (j, q)
    if not cand.matches:
        return None
    # at least one of the 3 strongest (gamma) lines must be matched
    order = sorted(range(len(lines)), key=lambda i: -lines[i].rel)
    top = [i for i in order if lines[i].kind == "g"][:3] or order[:3]
    if not any(i in cand.matches for i in top):
        return None
    return cand


# nuclides commonly met in a gamma lab: no prior penalty
COMMON = {
    "Am-241", "Ba-133", "Cd-109", "Ce-139", "Co-57", "Co-60", "Cs-137", "Eu-152", "Eu-154", "Eu-155",
    "Hg-203", "Mn-54", "Na-22", "Sn-113", "Sr-85", "Y-88", "Zn-65", "Bi-207", "Cr-51", "Co-58", "Fe-59",
    "K-40", "Th-234", "Pa-234m", "Ra-226", "Pb-214", "Bi-214", "Pb-210", "U-235", "Ac-228", "Th-228",
    "Ra-224", "Pb-212", "Bi-212", "Tl-208", "Be-7", "Cs-134", "Cs-136", "I-131", "I-132", "I-133",
    "Te-132", "Ba-140", "La-140", "Ce-141", "Ce-144", "Ru-103", "Ru-106", "Zr-95", "Nb-95", "Mo-99",
    "Sb-124", "Sb-125", "Ag-110m", "Sc-46", "Tc-99m", "F-18", "Ga-67", "Ga-68", "In-111", "Tl-201",
    "Lu-177", "I-123", "I-125", "Ir-192", "Se-75", "Np-239", "Pu-239", "U-238", "Th-232", "Na-24",
    "Ar-41", "Co-56", "Gd-153", "Ce-143", "Ba-131",
}
# radiopharmaceuticals and their generator parents: common only with the medical library
COMMON_MEDICAL = {"Mo-99", "Tc-99m", "F-18", "Ga-67", "Ga-68", "In-111", "Tl-201", "Lu-177", "I-123", "I-125"}
COMMON -= COMMON_MEDICAL

DECAYED_HALF_LIVES = 10.0        # more half-lives than this since sampling: activity < 0.1 %
DECAYED_PRIOR = 0.25
SINGLE_LINE_MIN_INTENSITY = 1.0  # % : library gamma lines counted by the single-line note


def _common(name: str, ctx) -> bool:
    return name in COMMON or (name in COMMON_MEDICAL and getattr(ctx, "application", "all") == "medical")


def decayed_nuclides(libd: dict, elapsed_s: float) -> dict:
    """Nuclides of `libd` with more than DECAYED_HALF_LIVES half-lives in `elapsed_s` seconds
    (name -> half-lives).  Members of a natural series and nuclides included by a parent that is
    itself not decayed (Tc-99m with Mo-99) are supported and left out."""
    def n_half(nd):
        return elapsed_s / nd.half_life_s if nd.half_life_s and nd.half_life_s > 0 else 0.0
    supported = {d for nd in libd.values() if n_half(nd) <= DECAYED_HALF_LIVES for d in (nd.includes or ())}
    return {n: n_half(nd) for n, nd in libd.items()
            if n_half(nd) > DECAYED_HALF_LIVES and not nd.series and n not in supported}


WEAK_EMITTER_MAX_LINES = 2       # the weak-emitter penalty applies to so few matched gamma lines
MISSING_MIN_KEV = 30.0           # unmatched lines below this are not counted as missing


def _prior(nd: NuclideData, ctx: _Context, used: dict, lines: list) -> float:
    """Plausibility prior: uncommon nuclides, weak emitters and very short half-lives.

    The weak-emitter penalty (matched gamma lines summing to < 10 % per decay) applies only
    when at most WEAK_EMITTER_MAX_LINES gamma lines are matched: one or two weak lines easily
    coincide with unrelated peaks, but several lines with consistent areas are evidence in
    their own right (e.g. Pu-239: lines of 1e-5 to 1e-4 per decay, very high activity)."""
    f = 1.0
    if not _common(nd.name, ctx):
        f *= 0.65 if ctx.det == "NaI" else 0.8
    ng = sum(1 for li in used if lines[li].kind == "g")
    gsum = sum(lines[li].intensity for li in used if lines[li].kind == "g")
    if gsum < 10.0 and ng <= WEAK_EMITTER_MAX_LINES:
        f *= (max(gsum, 0.05) / 10.0) ** 0.25
    if nd.half_life_s and nd.half_life_s < 3600 and not nd.series and not _common(nd.name, ctx):
        f *= 0.8
    if nd.name in getattr(ctx, "decayed", {}):
        f *= DECAYED_PRIOR
    return f


def _score(c: _Cand, ctx: _Context, claimed: dict) -> float:
    """Confidence 0..1. `claimed[peak idx] = {nuclide: explained area}` by accepted nuclides."""
    lines = c.lines
    used = {}
    credits = {}
    related = set(c.nd.includes) | {c.nd.name}
    for li, (j, q) in c.matches.items():
        p = ctx.peaks[j]
        credit = 1.0
        cl = claimed.get(j)
        if cl:
            # claims by a nuclide in the same equilibrium pair (Ba-140/La-140) do not compete
            others = {n: a for n, a in cl.items() if n not in related and c.nd.name not in _INCLUDES.get(n, ())}
            if others:
                resid = p.net_area - sum(others.values())
                # residual must exceed counting noise AND the efficiency-shape uncertainty
                credit = 1.0 if resid > max(3 * max(p.net_area_unc, 1.0), 0.35 * p.net_area) else 0.25
                if "annihilation" in (p.note or ""):
                    credit = 0.25     # 511 keV is fully explained once one positron emitter is accepted
        w = _peak_weight(p, lines[li].kind)
        if ctx.det == "NaI" and "X-ray region" in (p.note or ""):
            w *= 0.6                  # NaI below 90 keV: Pb X-rays, backscatter, iodine escape
        used[li] = (j, q, credit * w)
        credits[li] = credit * math.sqrt(w)
    # activity scale from the matched gamma lines with full credit (weighted by area significance)
    num = den = 0.0
    for li, (j, q, cr) in used.items():
        if cr < 0.5 or lines[li].kind == "a":
            continue
        p = ctx.peaks[j]
        wgt = (p.net_area / max(p.net_area_unc, 1.0)) ** 2
        num += wgt * p.net_area / lines[li].rel
        den += wgt
    if den == 0:
        for li, (j, q, cr) in used.items():
            p = ctx.peaks[j]
            wgt = (p.net_area / max(p.net_area_unc, 1.0)) ** 2
            num += wgt * p.net_area / lines[li].rel
            den += wgt
    k = num / den if den > 0 else 0.0
    c.k = k
    # per-nuclide efficiency-slope correction: log(area/expected) linear in log(E), fitted on
    # the well-measured matched gamma lines (corrects the generic efficiency shape)
    c.slope = (0.0, 0.0)
    pts = [(math.log(lines[li].energy), math.log(ctx.peaks[j].net_area / (k * lines[li].rel)),
            ctx.peaks[j].significance)
           for li, (j, q, cr) in used.items()
           if cr >= 0.5 and lines[li].kind == "g" and lines[li].energy > 100 and k > 0
           and ctx.peaks[j].net_area > 0 and ctx.peaks[j].significance > 5]
    if len(pts) >= 3:
        X = np.array([p_[0] for p_ in pts])
        Y = np.array([p_[1] for p_ in pts])
        W = np.minimum(np.array([p_[2] for p_ in pts]), 50.0)
        if np.ptp(X) > 0.4:
            b, a = np.polyfit(X, Y, 1, w=W)
            b = float(np.clip(b, -1.0, 1.0))
            a = float(np.average(Y - b * X, weights=W))
            c.slope = (a, b)

    def expected(ln):
        if ln.kind == "g" and ln.energy > 100:
            a, b = c.slope
            return k * ln.rel * math.exp(a + b * math.log(ln.energy))
        return k * ln.rel

    c.expected = expected
    detectable = 0.0
    explained = 0.0
    missing = []
    ratio_pen = 1.0
    strongest = max(range(len(lines)), key=lambda i: lines[i].rel if lines[i].kind == "g" else 0.0)
    strong_missing = False
    hard_missing = 0
    max_rel = max(l.rel for l in lines)
    evid = 0.0
    qsum = qw = 0.0
    for li, ln in enumerate(lines):
        exp_area = expected(ln)
        if li in used:
            j, q, cr = used[li]
            p = ctx.peaks[j]
            detectable += ln.rel
            explained += ln.rel * credits[li]
            evid += min(p.significance, 50.0) ** 2 * cr
            qsum += q * ln.rel
            qw += ln.rel
            # area consistency (efficiency shape is approximate: allow a factor ~3)
            if exp_area > 0 and p.net_area > 0 and cr >= 0.5:
                r = p.net_area / exp_area
                if ln.kind == "a" and r < 0.1:
                    ratio_pen *= 0.5          # far too little annihilation for this positron emitter
                if r < 0.2 and ln.kind == "g" and ln.energy > 150 and                         exp_area > 3 * ctx.detection_limit(ln.energy):
                    ratio_pen *= 0.85
            continue
        if ln.energy < MISSING_MIN_KEV:
            continue        # L X-rays / very soft lines: absorbers and dead layer make them unpredictable
        ld = ctx.detection_limit(ln.energy)
        if not math.isfinite(ld) or exp_area <= 0:
            continue
        # unresolved blend with a peak just outside the match window: no information
        fw = ctx.fwhm_kev(ln.energy)
        if any(abs(ctx.pe[j] - ln.energy) < 1.2 * fw for j, _q, _c in used.values()):
            continue
        x = exp_area / ld
        if x < 1.5:
            continue                               # below detection limit: no information
        weight = min((x - 1.5) / 3.0, 1.0)         # ramps up to full weight at 4.5 x L_D
        if ln.kind != "g" or ln.energy < 100.0:
            weight *= 0.3      # low-energy efficiency (absorbers, dead layer) is poorly known
        detectable += ln.rel * weight
        if weight > 0.5:
            missing.append(li)
        if x >= 8.0 and ln.kind == "g" and ln.energy >= 100.0 and ln.rel >= 0.02 * max_rel:
            hard_missing += 1
        if li == strongest and weight > 0.5:
            strong_missing = True
    c.missing = missing
    if detectable <= 0:
        return 0.0
    frac = explained / detectable
    stat = 1.0 - math.exp(-math.sqrt(evid) / 6.0)
    qual = qsum / qw if qw > 0 else 0.0
    conf = frac ** 2 * (0.6 + 0.4 * qual) * stat * ratio_pen * _prior(c.nd, ctx, used, lines)
    c.evidence = sum(min(ctx.peaks[j].significance, 100.0) ** 2 * credits[li] ** 2 * q
                     for li, (j, q, cr) in used.items() if lines[li].kind == "g")
    if strong_missing:
        conf *= 0.3
    conf *= 0.75 ** hard_missing     # lines that should stand far above L_D but are absent
    # only annihilation / X-ray evidence -> weak
    if all(lines[li].kind != "g" for li in used):
        conf *= 0.3
    c.detail = (f"frac={frac:.2f} stat={stat:.2f} qual={qual:.2f} ratio={ratio_pen:.2f} "
                f"strong_missing={strong_missing} k={k:.3g}")
    return float(max(0.0, min(conf, 1.0)))


RANK_LINES_POWER = 0.5           # weight of the number of matched peaks in the ranking
PARSIMONY_MAX_REL_FWHM = 0.04    # ... applied only when FWHM/E at 662 keV is at most this


def _n_gamma_matched(c) -> int:
    """Distinct peaks matched well by gamma lines (two lines on one broad peak count once)."""
    peaks = {j for li, (j, q) in c.matches.items() if c.lines[li].kind == "g" and q >= 0.5}
    return max(1, min(len(peaks), 6))


DRIFT_ACCEPT_GAIN = 1.05         # the drift-corrected identification must explain 5 % more
# ... and only at germanium resolution: with CZT / LaBr3 / NaI peaks the natural-line fit is
# too loose and the correction lowered U-235 recall on IAEA IDB CZT and LaBr3 spectra
DRIFT_MAX_REL_FWHM = 0.01        # FWHM / E at 662 keV


def _explained_score(ctx, claimed: dict) -> float:
    """Significance-weighted share of the peaks explained by accepted nuclides."""
    tot = 0.0
    for j, d in claimed.items():
        p = ctx.peaks[j]
        frac = min(sum(d.values()) / p.net_area, 1.0) if p.net_area > 0 else 0.0
        tot += frac * min(p.significance, 100.0)
    return tot


def _explain(ctx, libd, include_xrays, min_confidence):
    cands = []
    for nd in libd.values():
        c = _match_candidate(nd, ctx, include_xrays)
        if c is not None:
            cands.append(c)

    # greedy explanation with interference handling.  Parsimony (several matched peaks rank
    # first) only at good resolution: with NaI each broad peak covers tens of keV, so a nuclide
    # with many lines matches unrelated peaks by chance (Ag-110m took Cs-137's 662 keV peak).
    rank_power = RANK_LINES_POWER if ctx.fwhm_kev(662.0) / 662.0 <= PARSIMONY_MAX_REL_FWHM else 0.0
    claimed: dict[int, dict] = {}
    accepted: list[_Cand] = []
    pool = cands[:]
    for c in pool:
        c.conf = _score(c, ctx, claimed)
    while pool:
        ok = [c for c in pool if c.conf >= min_confidence]
        if not ok:
            break
        # explain the strongest evidence first (resolves shared lines in favour of the
        # nuclide that accounts for more of the spectrum), confidence as tie-breaker; a nuclide
        # whose several lines are matched comes before one that matches a single peak
        # (parsimony: one nuclide explaining five peaks beats five explaining one each)
        best = max(ok, key=lambda c: c.conf * max(c.evidence, 1.0) ** 0.1 * _n_gamma_matched(c) ** rank_power)
        pool.remove(best)
        accepted.append(best)
        touched = set()
        for li, (j, q) in best.matches.items():
            d = claimed.setdefault(j, {})
            # an accepted nuclide explains its matched peak unless the peak is far larger than
            # predicted (expected area from the per-nuclide efficiency-corrected scale, +30 %)
            area = ctx.peaks[j].net_area
            d[best.nd.name] = d.get(best.nd.name, 0.0) + min(area, 1.3 * best.expected(best.lines[li]))
            touched.add(j)
        for c in pool:     # only candidates sharing a peak need rescoring
            if any(j in touched for j, _q in c.matches.values()):
                c.conf = _score(c, ctx, claimed)

    # second pass: members of a natural series already seen are accepted at half threshold
    seen_series = {c.nd.series for c in accepted if c.nd.series}
    for c in sorted(pool, key=lambda c: -c.conf):
        if c.nd.series in seen_series and c.conf >= 0.5 * min_confidence:
            c.conf = _score(c, ctx, claimed)
            if c.conf >= 0.5 * min_confidence:
                accepted.append(c)

    return accepted, claimed


def _calibration_correction(ctx: _Context, accepted: list):
    """Linear (or quadratic) correction E_lib = f(E_peak) from well-identified strong lines,
    returned only when it changes energies by more than ~0.25 FWHM somewhere."""
    pts = []
    for c in accepted:
        if c.conf < 0.6:
            continue
        for li, (j, q) in c.matches.items():
            ln = c.lines[li]
            p = ctx.peaks[j]
            if len(ln.members) == 1 and ln.kind == "g" and p.significance >= 8 and                     "annihilation" not in (p.note or ""):
                pts.append((ctx.pe[j], ln.energy, p.significance))
    pts = sorted(set(pts))
    if len(pts) < 4:
        return None
    x = np.array([p[0] for p in pts])
    yv = np.array([p[1] for p in pts])
    w = np.sqrt(np.array([p[2] for p in pts]))
    deg = 2 if len(pts) >= 8 and np.ptp(x) > 0.4 * (ctx.emax - ctx.emin) else 1
    if np.ptp(x) < 50:
        deg = 0
    coef = np.polyfit(x, yv - x, deg, w=w)
    resid_before = float(np.sqrt(np.mean((yv - x) ** 2)))
    resid_after = float(np.sqrt(np.mean((yv - x - np.polyval(coef, x)) ** 2)))
    grid = np.linspace(max(ctx.emin, x.min() - 100), min(ctx.emax, x.max() + 100), 50)
    shift = np.abs(np.polyval(coef, grid))
    fw = np.array([ctx.fwhm_kev(e) for e in grid])
    if resid_after >= 0.8 * resid_before or not np.any(shift > 0.25 * fw):
        return None
    # never extrapolate wildly: clamp the correction to the fitted range
    lo, hi = float(x.min()), float(x.max())
    return lambda e: e + np.polyval(coef, np.clip(e, lo, hi))


def _single_line(c, ctx) -> bool:
    """One gamma line matched although the library has several gamma lines (>= 1 %) in range."""
    if sum(1 for li in c.matches if c.lines[li].kind == "g") != 1:
        return False
    n = sum(1 for ln in c.nd.lines if ln.kind == "g" and ln.intensity >= SINGLE_LINE_MIN_INTENSITY
            and ctx.emin <= ln.energy <= ctx.emax)
    return n >= 2


def identify(spectrum, peaks: Optional[list[Peak]] = None, library=None, lib=None,
             min_confidence: float = 0.25, include_xrays: bool = True, max_results: int = 40,
             correct_drift: bool = True, application: str = "all", sampled=None, _debug: bool = False,
             **_ignored) -> list[NuclideMatch]:
    """Identify nuclides. `library`/`lib`: path or parsed library (default: bundled).

    `correct_drift`: first compare the stored energy calibration with the natural-background
    lines in the spectrum (tools.calibrate.check_drift); when a drift is detected, the peak
    energies are corrected for the identification only and every result says so (germanium
    resolution only, DRIFT_MAX_REL_FWHM).  The stored
    calibration is never changed (review and apply it with the drift check).
    `application`: the application library searched ("all", "environmental", "calibration",
    "safeguards", "medical"; analysis.library.APPLICATIONS) - as with commercial programs,
    restricting the candidates to the kind of work avoids coincidental matches.
    `sampled`: end of sampling (datetime, naive local time like ``Spectrum.start_time``).  A
    nuclide with more than DECAYED_HALF_LIVES half-lives between it and the acquisition start gets
    a low plausibility and a note, unless a natural series or a parent of the library supports it
    (docs/baseline/round4_identify_protocol.md)."""
    if not spectrum.energy_coeffs:
        return []
    elapsed = None
    if sampled is not None and spectrum.start_time is not None:
        elapsed = (spectrum.start_time - sampled).total_seconds()
        if elapsed < 0:
            raise ValueError("the sampling date is after the start of the acquisition")
    if peaks is None:
        from .peaks import find_peaks
        peaks = find_peaks(spectrum)
    cal_peaks = [p for p in peaks if p.energy is not None and p.net_area > 0]
    for p in peaks:
        p.nuclide, p.line_energy = "", None
    if not cal_peaks:
        return []
    from .library import application_library
    libd = application_library(load_library(library if library is not None else lib), application)
    det = guess_detector(spectrum)
    ctx = _Context(spectrum, cal_peaks, det)
    ctx.application = application
    if elapsed is not None:
        ctx.decayed = decayed_nuclides(libd, elapsed)

    _INCLUDES.clear()
    _INCLUDES.update({n: tuple(nd.includes) for n, nd in libd.items() if nd.includes})
    accepted, claimed = _explain(ctx, libd, include_xrays, min_confidence)
    drift_note = ""
    if correct_drift and ctx.fwhm_kev(662.0) / 662.0 <= DRIFT_MAX_REL_FWHM:
        try:
            from ..tools.calibrate import check_drift
            dc = check_drift(spectrum, peaks=peaks)
        except Exception:          # no calibration lines, too few peaks ...: identify as stored
            dc = None
        if dc is not None and dc.detected and dc.correction:
            # keep the correction only if it explains the significant peaks better: a drift check
            # can be fooled where few natural lines exist (U/Pu spectra), and identification must
            # not get worse because of it
            a, b = dc.correction
            pe0 = ctx.pe
            ctx.pe = a + b * pe0
            ctx._ld.clear()
            acc2, cl2 = _explain(ctx, libd, include_xrays, min_confidence)
            if _explained_score(ctx, cl2) > DRIFT_ACCEPT_GAIN * _explained_score(ctx, claimed):
                accepted, claimed = acc2, cl2
                drift_note = (f"calibration drift detected (gain {100 * (b - 1):+.2f} %, offset {a:+.2f} keV): "
                              "energies corrected for identification only, stored calibration unchanged")
            else:
                ctx.pe = pe0
                ctx._ld.clear()
    # energy-calibration refinement from confidently identified lines, then a second pass
    corr = _calibration_correction(ctx, accepted)
    if corr is not None:
        ctx.pe = corr(ctx.pe)
        ctx._ld.clear()
        accepted, claimed = _explain(ctx, libd, include_xrays, min_confidence)

    # 186 keV: Ra-226 (186.2) vs U-235 (185.7).  Without the other U-235 lines (143.8, 163.4,
    # 205.3) and with U-238-series members present the peak is attributed to Ra-226.
    extra_note: dict[str, str] = {}
    u235 = next((c for c in accepted if c.nd.name == "U-235"), None)
    if u235 is not None and "Ra-226" in libd:
        g_hi = [c_ln.energy for li, c_ln in enumerate(u235.lines) if li in u235.matches and
                c_ln.kind == "g" and c_ln.energy > 100]
        if all(abs(e - 185.7) < 2 for e in g_hi) and any(c.nd.series == "U-238 series" for c in accepted):
            ra = _match_candidate(libd["Ra-226"], ctx, include_xrays)
            if ra is not None:
                ra.conf = _score(ra, ctx, {})
                ra.conf = max(ra.conf, 0.5 * u235.conf)
                accepted[accepted.index(u235)] = ra
                extra_note["Ra-226"] = "186 keV peak: U-235 (185.7 keV) interference not excluded"
    elif any(c.nd.name == "Ra-226" for c in accepted):
        extra_note["Ra-226"] = "186 keV peak: U-235 (185.7 keV) interference not excluded"

    # natural-series boost and notes
    members = {}
    for c in accepted:
        if c.nd.series:
            members.setdefault(c.nd.series, []).append(c)
    for series, lst in members.items():
        if len(lst) > 1:
            for c in lst:
                c.conf = min(1.0, c.conf * (1.0 + 0.1 * (len(lst) - 1)))

    # fold in how much of the spectrum each nuclide explains (dominant vs. minor component)
    emax = max([c.evidence for c in accepted] or [1.0]) or 1.0
    for c in accepted:
        c.conf *= 0.85 + 0.15 * (max(c.evidence, 0.0) / emax) ** 0.3

    results: list[NuclideMatch] = []
    for c in sorted(accepted, key=lambda c: -c.conf)[:max_results]:
        nd = c.nd
        matched = []
        for li in sorted(c.matches):
            j, _q = c.matches[li]
            ln = c.lines[li]
            lib_e = max(ln.members, key=lambda m: m.intensity).energy
            matched.append((round(lib_e, 3), ctx.peaks[j]))
        missing = [round(c.lines[li].energy, 2) for li in sorted(c.missing)]
        notes = []
        if nd.series:
            sub = nd.subgroup
            label = nd.series
            if sub and sub != nd.name and sub not in nd.series:
                label += f", {sub} daughter"
            notes.append(label)
        if nd.background:
            notes.append("typical background")
        if nd.note:
            notes.append(nd.note)
        if nd.name in extra_note:
            notes.append(extra_note[nd.name])
        if nd.name in ctx.decayed:
            notes.append(f"{ctx.decayed[nd.name]:.0f} half-lives since sampling: present only if produced "
                         "after sampling (check the sampling date)")
        if _single_line(c, ctx):
            notes.append("one line matched (the other lines are below the detection limit): confirm")
        if drift_note:
            notes.append(drift_note)
        if _debug:
            notes.append("[" + c.detail + "]")
        results.append(NuclideMatch(nuclide=nd.name, confidence=round(c.conf, 3), matched=matched,
                                    missing=missing, half_life=nd.half_life, category=nd.category,
                                    note="; ".join(notes), background=nd.background, series=nd.series))

    # best assignment per peak: the reported nuclide expected to contribute most counts to it
    # (K-40 rather than the 0.9 % Ac-228 line for a 1460 keV peak), confidence as tie-breaker
    reported = {m.nuclide for m in results}
    best_for: dict[int, tuple] = {}
    for c in accepted:
        if c.nd.name not in reported:
            continue
        for li, (j, q) in c.matches.items():
            ln = c.lines[li]
            p = ctx.peaks[j]
            exp_area = c.expected(ln) if c.expected else c.k * ln.rel
            contrib = min(exp_area, p.net_area) * q * _peak_weight(p, ln.kind)
            lib_e = max(ln.members, key=lambda m: m.intensity).energy
            score = (contrib, c.conf)
            key = id(p)
            if key not in best_for or score > best_for[key][0]:
                best_for[key] = (score, round(lib_e, 3), c.nd.name)
    for p in peaks:
        b = best_for.get(id(p))
        if b:
            p.nuclide, p.line_energy = b[2], b[1]
    return results

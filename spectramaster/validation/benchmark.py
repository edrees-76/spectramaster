"""Run the analysis-engine baseline and write ``baseline.json`` + ``baseline.md``.

    python -m spectramaster.validation.benchmark --out docs/baseline [--quick] [--refdata DIR]

``--quick`` uses fewer realisations (for the unit tests); the reported baseline uses the
default counts.  Results depend only on the code and the seeds, plus the optional external
reference spectra.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from .. import __version__
from ..lab.session import ENGINE_VERSION
from ..analysis import find_peaks, identify
from ..analysis.peaks import guess_detector
from ..analysis.library import load_library
from . import acceptance, reference, scenarios
from .synthetic import HPGE, HPGE_NL, NAI, NAI_4K, DetectorSpec, SyntheticSpectrum

MATCH_TOL_FWHM = 0.5


# ------------------------------------------------------------------------------ matching
def match(syn: SyntheticSpectrum, peaks) -> tuple[dict[int, int], list[int]]:
    """Greedy nearest unique matching of true -> reported peaks within 0.5 FWHM."""
    pairs = []
    for i, t in enumerate(syn.truth):
        for j, p in enumerate(peaks):
            d = abs(p.centroid - t.centroid)
            if d <= MATCH_TOL_FWHM * t.fwhm_ch:
                pairs.append((d, i, j))
    pairs.sort()
    m, ut, up = {}, set(), set()
    for _d, i, j in pairs:
        if i not in ut and j not in up:
            m[i] = j
            ut.add(i)
            up.add(j)
    return m, [j for j in range(len(peaks)) if j not in up]


def _near_truth(syn, p, width_fwhm=1.0) -> bool:
    return any(abs(p.centroid - t.centroid) <= width_fwhm * t.fwhm_ch for t in syn.truth)


def _mean(x):
    x = list(x)
    return float(np.mean(x)) if x else None


def _frac(x):
    x = list(x)
    return float(np.mean(x)) if x else None


class Collector:
    """Per-peak records for one (detector, category)."""

    def __init__(self):
        self.rows: list[dict] = []
        self.spectra = 0
        self.false = 0          # unmatched reported peaks not within 1 FWHM of any true peak
        self.split = 0          # unmatched reported peaks within 1 FWHM of a true peak
        self.times: list[float] = []
        self.res_elements = 0.0
        self.extra: list[dict] = []

    def add(self, syn: SyntheticSpectrum, peaks, dt: float):
        self.spectra += 1
        self.times.append(dt)
        m, un = match(syn, peaks)
        for i, t in enumerate(syn.truth):
            row = {"tag": t.tag, "energy": t.energy, "area": t.area, "fwhm_ch": t.fwhm_ch,
                   "found": i in m, **{k: v for k, v in syn.meta.items() if not isinstance(v, list)}}
            if i in m:
                p = peaks[m[i]]
                row.update(area_rep=p.net_area, unc=p.net_area_unc, rel=(p.net_area - t.area) / t.area,
                           z=(p.net_area - t.area) / p.net_area_unc if p.net_area_unc > 0 else None,
                           cdev_fwhm=(p.centroid - t.centroid) / t.fwhm_ch,
                           fwhm_ratio=p.fwhm / t.fwhm_ch, multiplet=p.multiplet)
            self.rows.append(row)
        for j in un:
            if _near_truth(syn, peaks[j]):
                self.split += 1
            else:
                self.false += 1
        det = syn.detector
        e = det.energy(np.arange(det.n_channels))
        sel = e >= 40.0
        self.res_elements += float(np.sum(1.0 / det.fwhm_ch(e[sel])))
        return m, un


def _zcov(rows, k):
    z = [abs(r["z"]) for r in rows if r.get("z") is not None]
    return float(np.mean(np.array(z) <= k)) if z else None


def summarise_basic(c: Collector, rows=None) -> dict:
    rows = c.rows if rows is None else rows
    f = [r for r in rows if r["found"]]
    return {"n_true": len(rows), "n_found": len(f), "recall": _frac(r["found"] for r in rows),
            "area_bias": _mean(r["rel"] for r in f), "area_rel_sd": float(np.std([r["rel"] for r in f])) if f else None,
            "centroid_bias_fwhm": _mean(r["cdev_fwhm"] for r in f),
            "fwhm_ratio_mean": _mean(r["fwhm_ratio"] for r in f),
            "z_mean": _mean(r["z"] for r in f if r.get("z") is not None),
            "z_sd": float(np.std([r["z"] for r in f if r.get("z") is not None])) if f else None,
            "z_cov1": _zcov(f, 1), "z_cov2": _zcov(f, 2),
            "false_per_spectrum": c.false / max(c.spectra, 1), "spectra": c.spectra,
            "split_fraction": c.split / max(len(rows), 1)}


# ------------------------------------------------------------------------------ categories
def run_peaks(gen: Iterable[SyntheticSpectrum]) -> Collector:
    c = Collector()
    for syn in gen:
        t0 = time.perf_counter()
        peaks = find_peaks(syn.spectrum)
        c.add(syn, peaks, time.perf_counter() - t0)

    return c


def cat_isolated(det, n, tail=False) -> tuple[dict, Collector]:
    c = run_peaks(scenarios.isolated_strong(det, n, tail=tail))
    return summarise_basic(c), c


def cat_shape_calibrated(det, n, tail: bool = True, n_cal: int = 3) -> tuple[dict, Collector]:
    """Isolated strong peaks fitted with the detector's peak-shape calibration measured on
    `n_cal` separate calibration spectra (with / without a low-energy tail in the truth)."""
    from ..analysis.peaks import set_peak_tail, shape_calibration
    cal = shape_calibration([s.spectrum for s in scenarios.shape_calibration_spectra(det, n_cal, tail)])

    def gen():
        for syn in scenarios.isolated_strong(det, n, tail=tail):
            set_peak_tail(syn.spectrum, cal)
            yield syn
    c = run_peaks(gen())
    out = summarise_basic(c)
    out.update(cal_eta=cal["eta"], cal_u_eta=cal["u_eta"], cal_tau=cal["tau"], cal_peaks=cal["n_peaks"])
    return out, c


def cat_weak(det, n) -> tuple[dict, Collector]:
    c = run_peaks(scenarios.isolated_weak(det, n))
    out = summarise_basic(c)
    for s in scenarios.SNR_LEVELS:
        rows = [r for r in c.rows if r.get("s") == s]
        out[f"pdet_s{s:g}"] = _frac(r["found"] for r in rows)
        out[f"area_bias_s{s:g}"] = _mean(r["rel"] for r in rows if r["found"])
    return out, c


def cat_medium(det, n_each) -> tuple[dict, Collector]:
    """Medium-signal isolated peaks (docs/baseline/medium_peaks_protocol.md)."""
    c = run_peaks(scenarios.medium_peaks(det, n_each))
    out = summarise_basic(c)
    for s in scenarios.MEDIUM_SNR_LEVELS:
        f = [r for r in c.rows if r.get("s") == s and r["found"]]
        out[f"found_s{s:g}"] = _frac(r["found"] for r in c.rows if r.get("s") == s)
        out[f"area_bias_s{s:g}"] = _mean(r["rel"] for r in f)
        out[f"sd_s{s:g}"] = float(np.std([r["rel"] for r in f])) if f else None
        out[f"cov1_s{s:g}"] = _zcov(f, 1)
        out[f"cov2_s{s:g}"] = _zcov(f, 2)
    return out, c


def cat_background(det, n) -> tuple[dict, Collector]:
    c = run_peaks(scenarios.background_only(det, n))
    return {"spectra": c.spectra, "false_per_spectrum": c.false / max(c.spectra, 1),
            "resolution_elements_per_spectrum": c.res_elements / max(c.spectra, 1),
            "false_per_1000_res": 1000.0 * c.false / max(c.res_elements, 1e-9)}, c


def cat_doublets(det, n_each) -> tuple[dict, Collector]:
    c = Collector()
    groups: dict[tuple, list] = defaultdict(list)
    for syn in scenarios.doublets(det, n_each):
        t0 = time.perf_counter()
        peaks = find_peaks(syn.spectrum)
        dt = time.perf_counter() - t0
        m, _un = c.add(syn, peaks, dt)
        lo, hi = syn.truth
        w0, w1 = lo.centroid - lo.fwhm_ch, hi.centroid + hi.fwhm_ch
        inside = [p for p in peaks if w0 <= p.centroid <= w1]
        resolved = 0 in m and 1 in m
        rec = {"resolved": resolved,
               "total_rel": (sum(p.net_area for p in inside) - lo.area - hi.area) / (lo.area + hi.area),
               "n_inside": len(inside)}
        if resolved:
            rec["rel_lo"] = (peaks[m[0]].net_area - lo.area) / lo.area
            rec["rel_hi"] = (peaks[m[1]].net_area - hi.area) / hi.area
        groups[(syn.meta["sep_fwhm"], syn.meta["ratio"])].append(rec)
    out: dict = {"by_case": {}}
    for (d, r), recs in sorted(groups.items()):
        out["by_case"][f"sep={d:g}FWHM ratio={r:g}"] = {
            "resolved": _frac(x["resolved"] for x in recs),
            "total_area_bias": _mean(x["total_rel"] for x in recs),
            "lo_area_bias": _mean(x["rel_lo"] for x in recs if x["resolved"]),
            "hi_area_bias": _mean(x["rel_hi"] for x in recs if x["resolved"]),
            "mean_reported": _mean(x["n_inside"] for x in recs)}

    def sel(f):
        return [x for (d, r), recs in groups.items() if f(d, r) for x in recs]
    wide = sel(lambda d, r: d >= 1.5 and r <= 3)
    out["resolved_ge1.5fwhm_ratio_le3"] = _frac(x["resolved"] for x in wide)
    comp = [x[k] for x in sel(lambda d, r: d >= 1.5) if x["resolved"] for k in ("rel_lo", "rel_hi")]
    out["component_area_bias_ge1.5fwhm"] = _mean(comp)
    out["resolved_1.0fwhm_ratio1"] = _frac(x["resolved"] for x in sel(lambda d, r: d == 1.0 and r == 1))
    close = sel(lambda d, r: d <= 0.75)
    out["total_area_bias_le0.75fwhm"] = _mean(x["total_rel"] for x in close)
    out["resolved_le0.75fwhm"] = _frac(x["resolved"] for x in close)
    return out, c


def cat_satellites(det, n_each, tail: bool = False, n_cal: int = 3) -> tuple[dict, Collector]:
    """Strong peak + satellite, fitted with the detector's peak-shape calibration measured on
    `n_cal` separate calibration spectra (the residual search needs a measured shape)."""
    from ..analysis.peaks import set_peak_tail, shape_calibration
    cal = shape_calibration([s.spectrum for s in scenarios.shape_calibration_spectra(det, n_cal, tail)])
    c = Collector()
    groups: dict[float, list] = defaultdict(list)
    for syn in scenarios.satellites(det, n_each, tail=tail):
        set_peak_tail(syn.spectrum, cal)
        t0 = time.perf_counter()
        peaks = find_peaks(syn.spectrum)
        dt = time.perf_counter() - t0
        m, _un = c.add(syn, peaks, dt)
        main, sat = syn.truth
        w0 = min(main.centroid, sat.centroid) - 2.0 * main.fwhm_ch
        w1 = max(main.centroid, sat.centroid) + 2.0 * main.fwhm_ch
        inside = [p for p in peaks if w0 <= p.centroid <= w1]
        rec = {"found": 1 in m, "extra": max(len(inside) - len(m), 0)}
        if 0 in m:
            rec["main_rel"] = (peaks[m[0]].net_area - main.area) / main.area
        if 1 in m:
            rec["sat_rel"] = (peaks[m[1]].net_area - sat.area) / sat.area
        groups[syn.meta["ratio"]].append(rec)
    out: dict = {}
    for r, recs in sorted(groups.items()):
        out[f"found_ratio{r:g}"] = _frac(x["found"] for x in recs)
    allr = [x for recs in groups.values() for x in recs]
    out["found_ratio_le30"] = _frac(x["found"] for r, recs in groups.items() if r <= 30 for x in recs)
    out["extra_per_spectrum"] = _mean(x["extra"] for x in allr)
    out["main_area_bias"] = _mean(x["main_rel"] for x in allr if "main_rel" in x)
    out["sat_area_bias_ratio10"] = _mean(x["sat_rel"] for x in groups.get(10.0, []) if "sat_rel" in x)
    out.update(cal_eta=cal["eta"], cal_tau=cal["tau"], cal_peaks=cal["n_peaks"])
    return out, c


def cat_edge(det, n, extra_sigma_kev: float = 0.0) -> tuple[dict, Collector]:
    c = Collector()
    rows, spurious = [], 0
    for syn in scenarios.compton_edge(det, n, extra_sigma_kev):
        t0 = time.perf_counter()
        peaks = find_peaks(syn.spectrum)
        m, un = c.add(syn, peaks, time.perf_counter() - t0)
        ec = syn.meta["edge_kev"]
        fw_edge = float(det.fwhm_ch(ec))
        c_edge = det.channel(ec)
        spurious += sum(1 for j in un if abs(peaks[j].centroid - c_edge) <= 3 * fw_edge)
    test_rows = [r for r in c.rows if r["tag"].startswith("edge")]
    out = summarise_basic(c, test_rows)
    out["spurious_near_edge_per_spectrum"] = spurious / max(c.spectra, 1)
    out["by_offset"] = {}
    for off in scenarios.EDGE_OFFSETS[1:]:
        rr = [r for r in test_rows if r.get("offset") == off]
        out["by_offset"][f"{off:+g}FWHM"] = {"recall": _frac(r["found"] for r in rr),
                                             "area_bias": _mean(r["rel"] for r in rr if r["found"])}
    return out, c


def cat_low(det, n) -> tuple[dict, Collector]:
    c = run_peaks(scenarios.low_counts(det, n))
    out = summarise_basic(c)
    big = [r for r in c.rows if r["A"] >= 100 and r["found"]]
    out["area_bias_A_ge100"] = _mean(r["rel"] for r in big)
    out["z_cov1"] = _zcov(big, 1)
    out["z_cov2"] = _zcov(big, 2)
    out["by_area"] = {f"A={a:g}": {"recall": _frac(r["found"] for r in c.rows if r["A"] == a),
                                   "area_bias": _mean(r["rel"] for r in c.rows if r["A"] == a and r["found"]),
                                   "z_mean": _mean(r["z"] for r in c.rows if r["A"] == a and r["found"]
                                                   and r.get("z") is not None)}
                      for a in scenarios.LOW_AREAS}
    return out, c


def _series_alias(lib) -> dict[str, str]:
    return {n: (nd.series or n) for n, nd in lib.items()}


def cat_identification(det, n_seeds) -> dict:
    lib = load_library()
    alias = _series_alias(lib)
    by_drift: dict[float, dict] = defaultdict(lambda: {"tp": 0, "n": 0, "fp": 0, "spectra": 0})
    by_mix: dict[str, dict] = defaultdict(lambda: {"tp": 0, "n": 0, "fp": 0, "spectra": 0, "false": defaultdict(int),
                                                   "missed": defaultdict(int)})
    times = []
    from ..analysis.library import application_library
    env_names = set(application_library(lib, "environmental"))
    env = {"tp": 0, "n": 0, "fp": 0, "spectra": 0}       # informational: environmental library, drift 0
    for syn in scenarios.identification(det, n_seeds):
        t0 = time.perf_counter()
        peaks = find_peaks(syn.spectrum)
        res = identify(syn.spectrum, peaks)
        times.append(time.perf_counter() - t0)
        reported = {r.nuclide for r in res}
        present = set(syn.meta["present"])
        allowed_groups = {alias.get(n, n) for n in present | set(syn.meta["weak"])}
        if syn.meta["drift"] == 0:
            rep_env = {r.nuclide for r in identify(syn.spectrum, peaks, application="environmental")}
            pres_env = present & env_names
            env["tp"] += sum(n in rep_env or (lib[n].series and any(alias.get(r) == lib[n].series for r in rep_env))
                             or any(n in lib[r].includes for r in rep_env if r in lib) for n in pres_env)
            env["n"] += len(pres_env)
            env["fp"] += sum(1 for r in rep_env if alias.get(r, r) not in allowed_groups
                             and not any(r in lib[n].includes for n in present | set(syn.meta["weak"])))
            env["spectra"] += 1
        # a present nuclide counts as found if it or a member of the same decay chain is reported
        # (e.g. Bi-214 present, "Ra-226" reported); includes (Cs-137 -> Ba-137m) count too
        def found(n):
            if n in reported:
                return True
            if lib[n].series:
                return any(alias.get(r) == lib[n].series for r in reported)
            return any(n in lib[r].includes for r in reported if r in lib)
        tp = sum(found(n) for n in present)
        false = [r for r in reported if alias.get(r, r) not in allowed_groups
                 and not any(r in lib[n].includes for n in present | set(syn.meta["weak"]))]
        for agg in (by_drift[syn.meta["drift"]], by_mix[syn.meta["mixture"]] if syn.meta["drift"] == 0 else None):
            if agg is None:
                continue
            agg["tp"] += tp
            agg["n"] += len(present)
            agg["fp"] += len(false)
            agg["spectra"] += 1
        if syn.meta["drift"] == 0:
            for r in false:
                by_mix[syn.meta["mixture"]]["false"][r] += 1
            for n in present:
                if not found(n):
                    by_mix[syn.meta["mixture"]]["missed"][n] += 1
    d0 = by_drift[0.0]
    d3 = by_drift.get(0.003)
    return {"recall": d0["tp"] / max(d0["n"], 1), "false_per_spectrum": d0["fp"] / max(d0["spectra"], 1),
            "recall_at_drift_0.3": (d3["tp"] / max(d3["n"], 1)) if d3 else None,
            "recall_by_drift": {f"{d * 100:g}%": v["tp"] / max(v["n"], 1) for d, v in sorted(by_drift.items())},
            "false_by_drift": {f"{d * 100:g}%": v["fp"] / max(v["spectra"], 1) for d, v in sorted(by_drift.items())},
            "by_mixture": {k: {"recall": v["tp"] / max(v["n"], 1), "false_per_spectrum": v["fp"] / max(v["spectra"], 1),
                               "false_nuclides": dict(v["false"]), "missed": dict(v["missed"])}
                           for k, v in by_mix.items()},
            "false_per_spectrum_environmental_library": env["fp"] / max(env["spectra"], 1),
            "recall_environmental_library": env["tp"] / max(env["n"], 1),
            "median_time_s": statistics.median(times) if times else None}


def cat_detector_guess(det, n) -> dict:
    """Fraction of unlabelled spectra whose detector type the engine infers correctly."""
    def frac(gen):
        got = [guess_detector(syn.spectrum) for syn in gen]
        return (sum(g == det.name for g in got) / max(len(got), 1),
                {k: got.count(k) for k in sorted(set(got))})
    fs, gs = frac(scenarios.isolated_strong(det, n))
    fl, gl = frac(scenarios.low_counts(det, n))
    return {"correct_fraction_strong": fs, "correct_fraction_low": fl,
            "guesses_strong": gs, "guesses_low": gl}


# ------------------------------------------------------------------- energy calibration (Release B)
CAL_SOURCE = {"HPGe": "Eu-152", "NaI": "Am-241,Cs-137,Co-60"}
DRIFT_LIMIT = {"HPGe": 0.003, "NaI": 0.01}
DRIFT_LEVELS = (0.0, 0.001, 0.003, 0.01)


def _cal_error_fwhm(det: DetectorSpec, coeffs, e_lo: float, e_hi: float) -> float:
    """max |E_fit - E_true| / FWHM_true over [e_lo, e_hi] keV (true energy scale)."""
    ch = np.linspace(det.channel(e_lo), det.channel(e_hi), 200)
    et = det.energy(ch)
    ef = np.polynomial.polynomial.polyval(ch, list(coeffs))
    return float(np.max(np.abs(ef - et) / det.fwhm_kev(et)))


def _flagged(sc) -> bool:
    v = getattr(sc, "validation", None)
    return bool(v is not None and not v.ok)


def cat_calibration(det: DetectorSpec, true_det: DetectorSpec, n: int) -> dict:
    from ..tools.calibrate import calibrate_from_source
    src = CAL_SOURCE[det.name]
    errs, ok, orders, fails = [], [], [], 0
    for syn in scenarios.calibration_source(true_det, src, n):
        try:
            sc = calibrate_from_source(syn.spectrum, src)
        except ValueError:
            fails += 1
            ok.append(False)
            continue
        es = [m.energy for m in sc.matches]
        e = _cal_error_fwhm(true_det, sc.coeffs, min(es), max(es))
        errs.append(e)
        ok.append(e <= 0.1 and not _flagged(sc))
        orders.append(sc.fit.order)
    out = {"source": src, "true_quadratic_kev_per_ch2": true_det.quad_kev,
           "recover_ok_fraction": _frac(ok), "max_error_fwhm_median": statistics.median(errs) if errs else None,
           "max_error_fwhm_worst": max(errs) if errs else None, "failures": fails,
           "orders": {str(k): orders.count(k) for k in sorted(set(orders))}}
    flagged = []
    for syn in scenarios.calibration_source(det, "Co-60,Cs-137", n, category="cal_wrong_source"):
        try:
            flagged.append(_flagged(calibrate_from_source(syn.spectrum, "Eu-152")))
        except ValueError:
            flagged.append(True)
    out["wrong_source_flagged_fraction"] = _frac(flagged)
    if det.name == "HPGe":
        lin = []
        for syn in scenarios.calibration_source(det, src, n, category="cal_linear"):
            try:
                lin.append(calibrate_from_source(syn.spectrum, src).fit.order == 1)
            except ValueError:
                lin.append(False)
        out["linear_truth_order1_fraction"] = _frac(lin)
    return out


def cat_drift(det: DetectorSpec, n: int) -> dict:
    try:
        from ..tools.calibrate import check_drift
    except ImportError:
        return {"note": "no drift check available in this version"}
    emax = float(det.energy(det.n_channels - 20))
    det_by, corr_ok = {}, []
    for lvl in DRIFT_LEVELS:
        hits = []
        for syn in scenarios.calibration_drift(det, lvl, n):
            r = check_drift(syn.spectrum)
            hits.append(bool(r.detected))
            if lvl == DRIFT_LIMIT[det.name]:
                corr_ok.append(bool(r.detected) and r.proposed_coeffs is not None
                               and _cal_error_fwhm(det, r.proposed_coeffs, 300.0, min(2600.0, emax)) <= 0.1)
        det_by[f"{lvl * 100:g}%"] = _frac(hits)
    return {"detected_fraction_by_level": det_by,
            "detected_fraction_at_limit": det_by[f"{DRIFT_LIMIT[det.name] * 100:g}%"],
            "false_alarm_fraction": det_by["0%"], "corrected_ok_fraction_at_limit": _frac(corr_ok),
            "limit": DRIFT_LIMIT[det.name]}


# ------------------------------------------------------------------- measured background (Release C)
def _flat_curve():
    """Any smooth efficiency curve: net areas and decisions do not depend on it."""
    from ..analysis.efficiency import fit_efficiency, manual_point
    pts = [manual_point(e, 0.05 * scenarios.rel_efficiency(e), 2.0) for e in
           (60, 90, 122, 200, 344, 500, 662, 900, 1173, 1408, 1836, 2600)]
    return fit_efficiency(pts, order=3)


def cat_measured_background(det: DetectorSpec, n: int, mode: str) -> dict:
    from ..analysis.activity import ActivityOptions, compute_activities
    curve = _flat_curve()
    names = list(scenarios.BKG_PRESENT) + list(scenarios.BKG_ABSENT)
    pres, absent = [], []
    for smp, bkg, truth in scenarios.background_pairs(det, n):
        q = compute_activities(smp.spectrum, curve, ActivityOptions(nuclides=names, bkg_mode=mode,
                                                                   min_intensity_pct=1.0),
                               background=bkg.spectrum)
        for r in q.nuclides:
            for ln in r.lines:
                key = next((k for k in truth if k[0] in (r.nuclide, ln.nuclide) and abs(k[1] - ln.energy) < 1.0),
                           None)
                if key is None:
                    continue
                row = {"true": truth[key], "net": ln.net_area if ln.peak_found else None,
                       "unc": ln.net_unc if ln.peak_found else None, "detected": bool(ln.detected),
                       "found": bool(ln.peak_found), "key": f"{key[0]} {key[1]:.0f}"}
                (pres if truth[key] > 0 else absent).append(row)
    fp = [r for r in pres if r["found"] and r["unc"]]
    z = [(r["net"] - r["true"]) / r["unc"] for r in fp]
    return {"mode": mode, "n_present": len(pres), "n_absent": len(absent),
            "net_area_bias": _mean((r["net"] - r["true"]) / r["true"] for r in fp),
            "z_cov1": _frac(abs(x) <= 1 for x in z) if z else None,
            "z_cov2": _frac(abs(x) <= 2 for x in z) if z else None,
            "z_mean": _mean(z),
            "present_detected_fraction": _frac(r["detected"] for r in pres),
            "present_found_fraction": _frac(r["found"] for r in pres),
            "false_detection_fraction": _frac(r["detected"] for r in absent),
            "absent_found_fraction": _frac(r["found"] for r in absent),
            "absent_z_mean_when_found": _mean(r["net"] / r["unc"] for r in absent if r["found"] and r["unc"])}


def cat_reagent_blank(det: DetectorSpec, n: int, mode: str = "spectrum") -> dict:
    """Reagent blank correction (docs/baseline/reagent_blank_protocol.md)."""
    from ..analysis.activity import ActivityOptions, compute_activities
    curve = _flat_curve()
    opt = ActivityOptions(nuclides=["Cs-137", "Co-60", "Mn-54"], bkg_mode=mode, min_intensity_pct=1.0)
    pres, mn, mn_raw = [], [], []
    for smp, blk, bkg, truth in scenarios.blank_triples(det, n):
        qb = compute_activities(blk.spectrum, curve, opt, background=bkg.spectrum)
        q0 = compute_activities(smp.spectrum, curve, opt, background=bkg.spectrum)
        q = compute_activities(smp.spectrum, curve, opt, background=bkg.spectrum, blank=qb)
        for r, r0 in zip(q.nuclides, q0.nuclides):
            for ln, ln0 in zip(r.lines, r0.lines):
                key = next((k for k in truth if k[0] == r.nuclide and abs(k[1] - ln.energy) < 1.0), None)
                if key is None:
                    continue
                if key[0] == "Mn-54":
                    mn_raw.append(bool(ln0.detected))
                    z = (ln.activity / (abs(ln.activity) * ln.u_count_rel)
                         if ln.activity and ln.peak_found and ln.u_count_rel not in (0.0, float("inf")) else None)
                    mn.append({"detected": bool(ln.detected), "z": z})
                    continue
                if not (ln.peak_found and ln.activity is not None and ln0.net_area):
                    pres.append({"found": False})
                    continue
                w = ln0.activity / ln0.net_area
                a_true = truth[key] * w
                u = abs(ln.activity) * ln.u_count_rel
                pres.append({"found": True, "rel": ln.activity / a_true - 1.0,
                             "z": (ln.activity - a_true) / u if u else None,
                             "corrected": ln.blank_activity is not None})
    fp = [r for r in pres if r["found"]]
    z = [r["z"] for r in fp if r["z"] is not None]
    return {"mode": mode, "n_present": len(pres), "n_mn54": len(mn),
            "bias": _mean(r["rel"] for r in fp),
            "z_cov1": _frac(abs(x) <= 1 for x in z) if z else None,
            "z_cov2": _frac(abs(x) <= 2 for x in z) if z else None,
            "z_mean": _mean(z),
            "present_found_fraction": _frac(r["found"] for r in pres),
            "cs137_blank_applied": _frac(r["corrected"] for r in fp),
            "false_detect": _frac(r["detected"] for r in mn),
            "uncorrected_detect": _frac(mn_raw),
            "mn54_z_mean": _mean(r["z"] for r in mn if r["z"] is not None)}


def cat_reference_peak(det: DetectorSpec, n: int) -> dict:
    """Reference peak correction (docs/baseline/reference_peak_protocol.md)."""
    from ..analysis.activity import ActivityOptions, compute_activities
    curve = _flat_curve()
    ref = {"energy": scenarios.REF_PULSER_KEV[det.name], "rate": scenarios.REF_PULSER_CPS, "rate_rel_unc": 0.0}
    names = ["Cs-137", "Co-60"]
    rows, k_err = [], []
    for syn, truth, loss in scenarios.reference_peak_spectra(det, n):
        q0 = compute_activities(syn.spectrum, curve, ActivityOptions(nuclides=names))
        q = compute_activities(syn.spectrum, curve, ActivityOptions(nuclides=names, reference_peak=ref))
        k_err.append(q.reference_factor * (1.0 - loss) - 1.0)       # K recovers 1/(1-L) exactly when 0
        for r, r0 in zip(q.nuclides, q0.nuclides):
            for ln, ln0 in zip(r.lines, r0.lines):
                key = next((k for k in truth if k[0] == r.nuclide and abs(k[1] - ln.energy) < 1.0), None)
                if key is None:
                    continue
                if not (ln.peak_found and ln0.net_area and ln.activity is not None):
                    rows.append({"found": False, "loss": loss})
                    continue
                a_true = truth[key] * ln0.activity / ln0.net_area
                u = abs(ln.activity) * math.hypot(ln.u_count_rel, q.reference_u_rel)
                rows.append({"found": True, "loss": loss, "rel": ln.activity / a_true - 1.0,
                             "fit": ln0.net_area / (truth[key] * (1.0 - loss)) - 1.0,
                             "rel0": ln0.activity / a_true - 1.0, "z": (ln.activity - a_true) / u if u else None})
    refused = []
    for syn, _truth, _loss in scenarios.reference_peak_spectra(det, 3, with_pulser=False):
        try:
            compute_activities(syn.spectrum, curve, ActivityOptions(nuclides=names, reference_peak=ref))
            refused.append(False)
        except ValueError:
            refused.append(True)
    fp = [r for r in rows if r["found"]]
    z = [r["z"] for r in fp if r["z"] is not None]
    return {"n_lines": len(rows), "found_fraction": _frac(r["found"] for r in rows),
            "bias": _mean(r["rel"] for r in fp),
            "no_loss_bias": _mean(r["rel"] for r in fp if math.isclose(r["loss"], 0.0, abs_tol=1e-12)),
            "bias_by_loss": {f"{lv:g}": _mean(r["rel"] for r in fp if math.isclose(r["loss"], lv, abs_tol=1e-12))
                             for lv in scenarios.REF_LOSSES},
            "uncorrected_bias": _mean(r["rel0"] for r in fp),
            "z_cov1": _frac(abs(x) <= 1 for x in z) if z else None,
            "z_cov2": _frac(abs(x) <= 2 for x in z) if z else None,
            "z_mean": _mean(z), "missing_refused": _mean(refused),
            # added after the first results (report only): the two parts of `bias`
            "k_bias": _mean(k_err), "fit_bias": _mean(r["fit"] for r in fp)}


TCS_GEOMETRIES = {"far": 0.005, "mid": 0.02, "close": 0.05}
TCS_DECAYS = 20_000_000
TCS_MIN_INTENSITY = 0.005


def cat_tcs(det: DetectorSpec, n_decays: int = TCS_DECAYS) -> dict:
    """True-coincidence summing correction against an event-by-event cascade simulation
    (docs/baseline/tcs_protocol.md)."""
    from ..analysis import coincidence as co
    from . import tcs_mc
    out: dict = {"decays": n_decays}
    for geo, e1000 in TCS_GEOMETRIES.items():
        ep = lambda e, e1000=e1000: tcs_mc.eps_peak(e, e1000)       # noqa: E731
        rows = []
        for nuc in tcs_mc.SCHEMES:
            sch = tcs_mc.scheme(nuc)
            mc = tcs_mc.simulate(nuc, e1000, n_decays, scenarios.seed_of(det, f"tcs/{nuc}/{e1000:g}", 0))
            for e, inten in zip(sch.gammas, sch.intensity):
                if inten < TCS_MIN_INTENSITY:
                    continue
                c_mc, s_mc = mc[float(e)]
                c_f = co.coi(nuc, float(e), ep, tcs_mc.peak_to_total).factor
                rows.append({"nuclide": nuc, "energy": float(e), "coi_mc": c_mc, "sigma": s_mc / c_mc,
                             "coi": c_f, "d": c_f / c_mc - 1.0})
        out[geo] = {"lines": {f"{r['nuclide']} {r['energy']:g}": {k: r[k] for k in ("coi", "coi_mc", "d", "sigma")}
                              for r in rows},
                    "max_excess": max(abs(r["d"]) - 3.0 * r["sigma"] for r in rows),
                    "max_uncorrected": max(abs(r["coi_mc"] - 1.0) for r in rows),
                    "co60_max_d": max(abs(r["d"]) for r in rows if r["nuclide"] == "Co-60"),
                    "sum_in_max_excess": max(abs(r["d"]) - 3.0 * r["sigma"] for r in rows
                                             if r["nuclide"] == "Cs-134" and round(r["energy"]) in (1168, 1365))}
        for k in ("max_excess", "max_uncorrected", "co60_max_d", "sum_in_max_excess"):
            out[f"{geo}_{k}"] = out[geo][k]          # flat keys for the acceptance criteria
    return out


# ------------------------------------------------------------- efficiency calibration (Release D)
EFF_TCS = ("Co-60", "Y-88")
EFF_OUTSIDE = (("Pb-210", 46.5), ("Tl-208", 2614.5))      # lines below / above a 59-1836 keV calibration


def _activity_supports(name: str) -> bool:
    import inspect
    from ..analysis.activity import ActivityOptions, compute_activities
    return name in inspect.signature(compute_activities).parameters or name in ActivityOptions.__dataclass_fields__


def cat_efficiency(det: DetectorSpec, n: int, shape: str = "smooth") -> dict:
    """Recovery and coverage of a fitted efficiency curve, plus the functional guards."""
    from ..analysis import efficiency as eff
    from ..analysis.activity import ActivityOptions, compute_activities
    devs, zs, maxdev, tcs_pts, tcs_flag, outside, outside_flag = [], [], [], 0, 0, 0, 0
    guard, shown = [], []
    for k, (syn, cert) in enumerate(scenarios.efficiency_calibration(det, n, shape=shape)):
        pts = eff.measure_efficiency(syn.spectrum, cert)
        try:
            curve = eff.fit_efficiency(pts, "two_branch", crossover="auto")
        except (ValueError, np.linalg.LinAlgError):
            continue
        used = [p for p in pts if p.use]
        lo, hi = min(p.energy for p in used), max(p.energy for p in used)
        test_e = np.geomspace(lo * 1.15, hi / 1.15, 12)
        f = np.asarray(curve.efficiency(test_e), dtype=float)
        u = np.asarray(curve.uncertainty(test_e), dtype=float)
        t = scenarios.true_efficiency(det, test_e, shape)
        d = f / t - 1.0
        devs.extend(d.tolist())
        zs.extend(((f - t) / u).tolist())
        maxdev.append(float(np.max(np.abs(d))))
        for p in pts:
            if p.nuclide in EFF_TCS:
                tcs_pts += 1
                tcs_flag += ("summing" in (p.note or "").lower())
        if k < 3:
            q = compute_activities(syn.spectrum, curve, ActivityOptions(nuclides=[nm for nm, _ in EFF_OUTSIDE]))
            for r in q.nuclides:
                for ln in r.lines:
                    if any(abs(ln.energy - e) < 1.0 for _nm, e in EFF_OUTSIDE):
                        outside += 1
                        outside_flag += ("extrapolat" in (ln.note or "").lower())
            # geometry guard: the curve belongs to a point source; the sample is a Marinelli beaker
            ok = 0
            if _activity_supports("geometry"):
                from ..lab.detector import MeasurementGeometry
                curve.geometry_record = MeasurementGeometry("point source 10 cm", kind="point",
                                                            source_distance_mm=100.0).to_dict()
                try:
                    q = compute_activities(syn.spectrum, curve, ActivityOptions(
                        nuclides=["Cs-137"], geometry=MeasurementGeometry("Marinelli 1 L", kind="marinelli")))
                    ok = int(any("geometry" in nt.lower() for nt in q.notes))
                except ValueError:
                    ok = 1
            guard.append(ok)
            # validation status: an imported, unvalidated calibration must be reported
            curve.validation_status = "unvalidated"
            q = compute_activities(syn.spectrum, curve, ActivityOptions(nuclides=["Cs-137"]))
            shown.append(int(any("unvalidated" in nt.lower() for nt in q.notes)))
    z = np.asarray(zs)
    return {"realisations": n, "mean_rel_dev": _mean(devs),
            "median_max_rel_dev": float(np.median(maxdev)) if maxdev else None,
            "z_cov1": _frac(abs(x) <= 1 for x in z) if len(z) else None,
            "z_cov2": _frac(abs(x) <= 2 for x in z) if len(z) else None,
            "z_mean": _mean(z), "z_sd": float(np.std(z)) if len(z) else None,
            "tcs_flagged": tcs_flag / tcs_pts if tcs_pts else None,
            "extrapolation_flagged": outside_flag / outside if outside else None,
            "geometry_guard": _mean(guard), "validation_shown": _mean(shown)}


# ------------------------------------------------------------ IAEA IDB real spectra (Release E)
IDB_U_CHAIN = {"U-235", "U-238", "Th-234", "Pa-234m", "Th-231", "U-234", "U-232", "Th-228", "Pa-231", "Ac-227",
               "Th-227", "Ra-223"}
IDB_PU = {"Pu-238", "Pu-239", "Pu-240", "Pu-241", "Pu-242", "Am-241", "U-237", "Np-237", "Pa-233"}
IDB_BACKGROUND = {"K-40", "Ra-226", "Pb-214", "Bi-214", "Pb-210", "Th-232", "Ac-228", "Pb-212", "Bi-212", "Tl-208",
                  "Ra-228", "Rn-222", "Be-7", "Cs-137"}
IDB_STEP = 10           # every 10th file of each detector type (deterministic subset)


def idb_folder() -> Optional[Path]:
    import os
    root = Path(os.environ.get("SPECTRAMASTER_PUBLIC_DATA", "D:/SpectraMaster_public_data"))
    f = root / "iaea_idb" / "IDB-all-spectra"
    return f if (f / "1.spe").is_file() else None


def _idb_kind(text: str) -> str:
    t = text.lower()
    for key, k in (("hpge", "HPGe"), ("cdznte", "CZT"), ("czt", "CZT"), ("cdte", "CdTe"), ("labr", "LaBr3"),
                   ("nai", "NaI")):
        if key in t:
            return k
    return "other"


def cat_idb(folder: Path) -> dict:
    """Identification on IAEA IDB spectra (material type and isotopics from the file remarks)."""
    import re
    files = sorted(folder.glob("*.spe"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0))
    by_kind: dict[str, list] = defaultdict(list)
    meta = {}
    for f in files:
        txt = f.read_text(encoding="latin-1")
        m = re.search(r"Detector:\s*([^\n]*)", txt)
        mt = re.search(r"Material type:\s*([^\n]*)", txt)
        e5 = re.search(r"235U\s+([\d.]+)", txt)
        k = _idb_kind(m.group(1) if m else "")
        by_kind[k].append(f)
        meta[f] = ((mt.group(1).strip() if mt else ""), float(e5.group(1)) if e5 else 0.0)
    out = {}
    implaus_names: dict[str, int] = defaultdict(int)
    for k, fs in by_kind.items():
        agg = {"n": 0, "u": 0, "u_found": 0, "pu": 0, "pu_found": 0, "implausible": 0, "implausible_sg": 0}
        for f in fs[::IDB_STEP]:
            from ..convert import read_spectra
            s = read_spectra(f)[0][0]
            ids = {r.nuclide for r in identify(s, find_peaks(s))}
            mat, e235 = meta[f]
            agg["n"] += 1
            if mat in ("U", "MOX") and e235 >= 0.7:
                agg["u"] += 1
                agg["u_found"] += "U-235" in ids
            if mat in ("Pu", "MOX"):
                agg["pu"] += 1
                agg["pu_found"] += "Pu-239" in ids
            bad = ids - IDB_U_CHAIN - IDB_PU - IDB_BACKGROUND
            agg["implausible"] += len(bad)
            # informational: the same spectrum searched with the safeguards application library
            ids_sg = {r.nuclide for r in identify(s, find_peaks(s), application="safeguards")}
            agg["implausible_sg"] += len(ids_sg - IDB_U_CHAIN - IDB_PU - IDB_BACKGROUND)
            for b in bad:
                implaus_names[f"{k} {b}"] += 1
        out[f"{k}_spectra"] = agg["n"]
        out[f"{k}_U235_recall"] = agg["u_found"] / agg["u"] if agg["u"] else None
        out[f"{k}_Pu239_recall"] = agg["pu_found"] / agg["pu"] if agg["pu"] else None
        out[f"{k}_implausible_per_spectrum"] = agg["implausible"] / agg["n"] if agg["n"] else None
        out[f"{k}_implausible_per_spectrum_safeguards_library"] = (agg["implausible_sg"] / agg["n"]
                                                                   if agg["n"] else None)
    out["most_frequent_implausible"] = dict(sorted(implaus_names.items(), key=lambda kv: -kv[1])[:15])
    return out


# ------------------------------------------------------------------------------ driver
def run(quick: bool = False, refdata: Optional[str] = None, log=print) -> dict:
    q = (lambda full, small: small if quick else full)
    results: dict = {"detectors": {}, "meta": {
        "spectramaster_version": __version__, "engine_version": ENGINE_VERSION, "python": sys.version.split()[0], "numpy": np.__version__,
        "platform": platform.platform(), "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quick": quick, "match_tolerance_fwhm": MATCH_TOL_FWHM}}
    for det in (HPGE, NAI):
        log(f"[{det.name}] synthetic categories ...")
        r: dict = {}
        times = []
        r["isolated_strong"], c = cat_isolated(det, q(40, 6)); times += c.times
        r["tailed"], c = cat_isolated(det, q(40, 6), tail=True); times += c.times
        r["tailed_shape_cal"], c = cat_shape_calibrated(det, q(40, 6)); times += c.times
        r["strong_shape_cal"], c = cat_shape_calibrated(det, q(40, 6), tail=False); times += c.times
        r["isolated_weak"], c = cat_weak(det, q(80, 8)); times += c.times
        r["medium_peaks"], c = cat_medium(det, q(40, 2)); times += c.times
        r["background_only"], c = cat_background(det, q(40, 4)); times += c.times
        r["doublets"], c = cat_doublets(det, q(8, 1)); times += c.times
        r["satellites"], c = cat_satellites(det, q(8, 2)); times += c.times
        r["satellites_tailed"], c = cat_satellites(det, q(8, 2), tail=True); times += c.times
        r["compton_edge"], c = cat_edge(det, q(48, 6)); times += c.times
        r["low_counts"], c = cat_low(det, q(80, 8)); times += c.times
        log(f"[{det.name}] identification ...")
        r["identification"] = cat_identification(det, q(3, 1))
        r["detector_guess"] = cat_detector_guess(det, q(20, 4))
        log(f"[{det.name}] energy calibration and drift ...")
        r["calibration"] = cat_calibration(det, HPGE_NL if det.name == "HPGe" else det, q(20, 3))
        r["drift"] = cat_drift(det, q(20, 3))
        log(f"[{det.name}] efficiency calibration ...")
        r["efficiency"] = cat_efficiency(det, q(40, 3))
        log(f"[{det.name}] measured background ...")
        for mode in ("peak", "spectrum"):
            r[f"background_{mode}"] = cat_measured_background(det, q(40, 3), mode)
        r["reagent_blank"] = cat_reagent_blank(det, q(40, 3))
        r["reference_peak"] = cat_reference_peak(det, q(40, 3))
        if det.name == "HPGe":
            log(f"[{det.name}] true-coincidence summing ...")
            r["tcs"] = cat_tcs(det, TCS_DECAYS if q(1, 0) else 200_000)
        r["runtime"] = {"median_s": statistics.median(times), "max_s": max(times), "n": len(times),
                        "channels": det.n_channels}
        results["detectors"][det.name] = r
    # NaI(Tl) on a 4096-channel MCA, unlabelled (informational until A8, criteria pre-registered
    # in acceptance.py before the P2 fix)
    log("[NaI 4096 ch, unlabelled] ...")
    r = {}
    r["isolated_strong"], _c = cat_isolated(NAI_4K, q(20, 4))
    r["identification"] = cat_identification(NAI_4K, q(3, 1))
    r["detector_guess"] = cat_detector_guess(NAI_4K, q(20, 4))
    results["detectors"]["NaI_4096"] = r
    results["informational"] = {}
    # added after the first run (no acceptance limit): edge smeared by an extra 8 keV (HPGe) /
    # 15 keV (NaI) sigma, closer to measured Compton edges than the resolution-only worst case
    for det, xs in ((HPGE, 8.0), (NAI, 15.0)):
        info, _c = cat_edge(det, q(48, 6), extra_sigma_kev=xs)
        info.pop("by_offset", None)
        results["informational"][f"{det.name}_compton_edge_broad_{xs:g}keV"] = info
        # first-run efficiency truth with a corner at 120 keV (not physical; kept for reference)
        results["informational"][f"{det.name}_efficiency_kinked_truth"] = cat_efficiency(det, q(40, 3), "kinked")
    idb = idb_folder()
    if idb is not None:
        log("[IAEA IDB] identification ...")
        results["IDB"] = cat_idb(idb)
    root = reference.find_refdata(refdata)
    results["reference_data_dir"] = str(root) if root else None
    if root:
        log("[reference] IAEA G-1 ...")
        results["G1"] = reference.run_g1(root)
        log("[reference] EML Sanderson ...")
        results["EML"] = reference.run_eml(root)
    results["criteria"] = evaluate_all(results)
    return results


def _lookup(results, cr: acceptance.Criterion):
    if cr.category in ("G1", "EML", "IDB"):
        return (results.get(cr.category) or {}).get(cr.metric)
    d = results["detectors"].get(cr.detector, {})
    return d.get(cr.category, {}).get(cr.metric)


def evaluate_all(results) -> list[dict]:
    out = []
    for cr in acceptance.CRITERIA:
        v = _lookup(results, cr)
        ok = acceptance.evaluate(cr, v)
        status = "REPORT" if cr.op == "report" else ("MISSING" if v is None else ("PASS" if ok else "FAIL"))
        out.append({"id": cr.id, "value": v, "op": cr.op, "limit": cr.limit, "status": status,
                    "rationale": cr.rationale})
    return out


# ------------------------------------------------------------------------------ report
def _fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.4g}"
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {_fmt(x)}" for k, x in v.items()) + "}"
    return str(v)


def markdown(res: dict) -> str:
    m = res["meta"]
    L = [f"# Analysis-engine baseline (generated)", "",
         f"SpectraMaster {m['spectramaster_version']} (engine {m.get('engine_version', '?')}), Python {m['python']}, NumPy {m['numpy']}, "
         f"{m['platform']}, {m['utc']}{' (QUICK run)' if m['quick'] else ''}.", "",
         "Generated by `python -m spectramaster.validation.benchmark`; limits from "
         "`spectramaster/validation/acceptance.py` (fixed before the first run).", "",
         "## Acceptance criteria", "", "| Criterion | Value | Limit | Status |", "|---|---|---|---|"]
    for c in res["criteria"]:
        lim = "-" if c["op"] == "report" else f"{c['op']} {_fmt(c['limit'])}"
        L.append(f"| `{c['id']}` | {_fmt(c['value'])} | {lim} | {c['status']} |")
    counts = defaultdict(int)
    for c in res["criteria"]:
        counts[c["status"]] += 1
    L += ["", "Totals: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())), ""]
    for det, r in res["detectors"].items():
        L += [f"## {det} details", ""]
        for cat, d in r.items():
            L.append(f"### {cat}")
            L.append("")
            for k, v in d.items():
                if isinstance(v, dict) and v and all(isinstance(x, dict) for x in v.values()):
                    L.append(f"- **{k}**:")
                    for kk, vv in v.items():
                        L.append(f"  - {kk}: {_fmt(vv)}")
                else:
                    L.append(f"- {k}: {_fmt(v)}")
            L.append("")
    L += ["## Informational", ""]
    for k, d in res.get("informational", {}).items():
        L.append(f"- **{k}**: {_fmt(d)}")
    for name in ("G1", "EML", "IDB"):
        if res.get(name):
            L += ["", f"## Reference set {name}", ""]
            for k, v in res[name].items():
                if isinstance(v, list):
                    L.append(f"- **{k}**:")
                    for x in v:
                        L.append(f"  - {_fmt(x)}")
                elif isinstance(v, dict):
                    L.append(f"- **{k}**:")
                    for kk, vv in v.items():
                        L.append(f"  - {kk}: {_fmt(vv)}")
                else:
                    L.append(f"- {k}: {_fmt(v)}")
    if not res.get("reference_data_dir"):
        L += ["", "Reference spectra (IAEA G-1, EML) were NOT available for this run."]
    return "\n".join(L) + "\n"


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m spectramaster.validation.benchmark")
    ap.add_argument("--out", default="docs/baseline", help="output directory")
    ap.add_argument("--quick", action="store_true", help="few realisations (smoke test)")
    ap.add_argument("--refdata", help="directory with IAEA G-1 / EML reference spectra")
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    res = run(quick=a.quick, refdata=a.refdata, log=lambda s: print(s, flush=True))
    res["meta"]["wall_time_s"] = round(time.perf_counter() - t0, 1)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "baseline.json").write_text(json.dumps(_jsonable(res), indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "baseline.md").write_text(markdown(res), encoding="utf-8")
    fails = [c["id"] for c in res["criteria"] if c["status"] == "FAIL"]
    print(f"wrote {out / 'baseline.md'}; {len(fails)} criteria failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

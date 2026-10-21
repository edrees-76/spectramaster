"""Signed primary result of lines without a search peak: evaluation harness of
docs/baseline/signed_primary_protocol.md, its amendment (version 2) and
docs/baseline/window_polynomial_protocol.md (version 3; synthetic spectra only, fixed seeds).

    python -m spectramaster.validation.primary [--out folder]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from ..analysis.activity import ActivityOptions, compute_activities
from . import scenarios
from .benchmark import _flat_curve
from .synthetic import HPGE, NAI, Continuum, TruePeak, area_for_snr, continuum_counts, make_spectrum

CS = 661.657
K40 = 1460.82
N_ZERO, N_WEAK, N_H3B, N_INTERF, N_M2, N_PAIRS, N_EDGE = 200, 100, 100, 50, 20, 40, 100
EDGE_LINE = 850.0        # Compton edge at 653.6 keV, under the Cs-137 window (window_polynomial_protocol.md)
WEAK_S = (1.0, 2.0, 3.0)
H3B_S = 2.45


def _line(res, nuclide: str, energy: float):
    r = next(r for r in res.nuclides if r.nuclide == nuclide)
    return r, next(l for l in r.lines if abs(l.energy - energy) < 0.5)


def _co60(det, cy):
    return [TruePeak(e, area_for_snr(det, cy, e, 40.0), tag="Co-60") for e in (1173.228, 1332.492)]


def edge_continuum(det) -> Continuum:
    k = det.gain_kev / 0.5
    base = scenarios.base_continuum(det)
    return Continuum(exp_amp=base.exp_amp, exp_scale_kev=base.exp_scale_kev, flat=base.flat,
                     compton_line_kev=EDGE_LINE, compton_level=40.0 * k)


def _cs_spectra(det, category: str, n: int, extra, cont=None):
    cont = cont or scenarios.base_continuum(det)
    cy = continuum_counts(det, cont)
    for i in range(n):
        peaks = _co60(det, cy) + extra(cy)
        syn = make_spectrum(det, peaks, cont, scenarios.seed_of(det, f"primary/{category}", i))
        true = sum(p.area for p in syn.truth if abs(p.energy - CS) < 0.01)
        yield syn.spectrum, true


USED = ("window",)        # "used" lines of the amendment protocol: window results only


def _z_stats(z: list[float]) -> dict:
    z = [x for x in z if math.isfinite(x)]
    if not z:
        return {"n": 0, "mean_z": math.nan, "cov2": math.nan}
    return {"n": len(z), "mean_z": float(np.mean(z)), "cov2": float(np.mean([abs(x) <= 2 for x in z]))}


def _methods(rows) -> dict:
    return {m: sum(r["method"] == m for r in rows) for m in ("fit", "window", "interfered", "curved")}


def _quadratic(rows) -> int:
    return sum(r.get("continuum") == "quadratic" for r in rows)


def _area_at_sigma0(det, x: float) -> float:
    """True Cs-137 area whose window result is x sigma_0 (amendment A4), sigma_0 from the noiseless
    continuum: sqrt(B_lin (1 + n / 2m)) in window counts, divided by the window fraction."""
    from ..analysis import activity as act
    from ..analysis.peaks import fwhm_model
    from ..model import Spectrum
    cy = continuum_counts(det, scenarios.base_continuum(det))
    sp = Spectrum(counts=list(cy), energy_coeffs=[det.offset_kev, det.gain_kev] + ([det.quad_kev] if det.quad_kev
                                                                                   else []),
                  live_time=3600.0, real_time=3600.0)
    fw, _src = fwhm_model(sp, np.asarray(cy))
    b, n, m, frac = act.continuum_under(sp, CS, fw)
    return x * math.sqrt(b * (1.0 + n / (2.0 * m))) / frac


def _cs_run(det, curve, category, n, extra, cont=None, **opt):
    rows = []
    for sp, true in _cs_spectra(det, category, n, extra, cont):
        res = compute_activities(sp, curve, ActivityOptions(nuclides=["Cs-137"], **opt))
        r, ln = _line(res, "Cs-137", CS)
        z = (ln.primary_net - true) / ln.primary_net_unc if ln.primary_net is not None and ln.primary_net_unc else math.nan
        per_count = ln.primary / ln.primary_net if ln.primary_net else math.nan
        true_bq = true * per_count
        rows.append({"z": z, "method": ln.primary_method, "detected": bool(r.detected), "line_detected": ln.detected,
                     "best": r.best_estimate, "low": r.coverage_low, "high": r.coverage_high, "true_bq": true_bq,
                     "activity": r.activity, "primary": r.primary, "continuum": ln.window_continuum,
                     "lc_ratio": (ln.window_lc_counts / ln.lc_counts if ln.window_lc_counts and ln.lc_counts
                                  else None)})
    return rows


def run_detector(det) -> dict:
    curve = _flat_curve()
    out = {}
    zero = _cs_run(det, curve, "zero", N_ZERO, lambda cy: [])
    out["zero"] = {**_z_stats([r["z"] for r in zero]), "methods": _methods(zero),
                   "used": _z_stats([r["z"] for r in zero if r["method"] in USED])}
    if det.name == "NaI":
        out["zero"]["quadratic"] = _quadratic(zero)
        ratios = [r["lc_ratio"] for r in zero if r["lc_ratio"]]
        out["zero"]["lc_ratio_mean"] = float(np.mean(ratios)) if ratios else None
    zero_iso = _cs_run(det, curve, "zero", N_ZERO, lambda cy: [], decision="iso11929")
    out["zero_iso_false_detect"] = float(np.mean([r["detected"] for r in zero_iso]))
    for s in WEAK_S:
        rows = _cs_run(det, curve, f"weak{s:g}", N_WEAK, lambda cy, s=s: [TruePeak(CS, area_for_snr(det, cy, CS, s))],
                       mda_method="iso11929")
        cover = [r["low"] is not None and r["low"] <= r["true_bq"] <= r["high"] for r in rows]
        out[f"weak_s{s:g}"] = {**_z_stats([r["z"] for r in rows]), "interval_coverage": float(np.mean(cover)),
                               "found": float(np.mean([r["method"] == "fit" for r in rows])),
                               "methods": _methods(rows),
                               "used": _z_stats([r["z"] for r in rows if r["method"] in USED])}
        if det.name == "NaI":
            out[f"weak_s{s:g}"]["quadratic"] = _quadratic(rows)
    a_h3b = _area_at_sigma0(det, H3B_S)
    h3b = lambda cy: [TruePeak(CS, a_h3b)]     # noqa: E731
    d1 = _cs_run(det, curve, "h3b", N_H3B, h3b, mda_method="iso11929")
    d2 = _cs_run(det, curve, "h3b", N_H3B, h3b, mda_method="iso11929", decision="iso11929")
    out["h3b"] = {"primary_present": all(r["primary"] is not None for r in d1),
                  "best_present": all(r["best"] is not None for r in d1),
                  "d1_detected": float(np.mean([r["detected"] for r in d1])),
                  "d2_detected": float(np.mean([r["detected"] for r in d2])), "methods": _methods(d1)}
    fw_kev = float(det.fwhm_kev(CS))
    interf = lambda cy: [TruePeak(CS + fw_kev, area_for_snr(det, cy, CS + fw_kev, 40.0))]   # noqa: E731
    rows = _cs_run(det, curve, "interference", N_INTERF, interf, mda_method="iso11929", decision="iso11929")
    out["interference"] = {"interfered": sum(r["method"] == "interfered" for r in rows), "n": len(rows),
                           "detected": sum(r["detected"] for r in rows),
                           "best_from_it": sum(r["best"] is not None for r in rows if r["method"] == "interfered")}
    out["m2"] = {mode: _m2(det, curve, mode) for mode in ("spectrum", "peak")}
    out["bkg_absent"] = {mode: _bkg_absent(det, curve, mode) for mode in ("spectrum", "peak")}
    if det.name == "NaI":
        rows = _cs_run(det, curve, "edge", N_EDGE, lambda cy: [], cont=edge_continuum(det), decision="iso11929")
        out["edge"] = {"false_detect": float(np.mean([r["detected"] for r in rows])), "methods": _methods(rows),
                       "quadratic": _quadratic(rows), "n": len(rows),
                       "used": _z_stats([r["z"] for r in rows if r["method"] in USED])}
    return out


def _m2(det, curve, mode: str) -> dict:
    cont = scenarios.base_continuum(det)
    neg, ok_best, none_act, flagged, best_flagged = 0, 0, 0, 0, 0
    for i in range(N_M2):
        smp = make_spectrum(det, [TruePeak(K40, 5000.0)], cont, scenarios.seed_of(det, "primary/m2/sample", i))
        bkg = make_spectrum(det, [TruePeak(K40, 10000.0)], cont, scenarios.seed_of(det, "primary/m2/bkg", i))
        res = compute_activities(smp.spectrum, curve, ActivityOptions(nuclides=["K-40"], bkg_mode=mode,
                                                                      mda_method="iso11929"),
                                 background=bkg.spectrum)
        r, ln = _line(res, "K-40", K40)
        neg += ln.primary_net is not None and ln.primary_net < 0
        ok_best += r.best_estimate is not None and r.best_estimate >= 0 and r.coverage_high is not None
        none_act += r.activity is None and not r.detected
        if ln.primary_method in ("curved", "interfered"):
            flagged += 1
            best_flagged += r.best_estimate is not None
    return {"negative": neg, "best_and_interval": ok_best, "no_activity_not_detected": none_act, "n": N_M2,
            "flagged": flagged, "best_from_flagged": best_flagged}


def _bkg_absent(det, curve, mode: str) -> dict:
    names = list(scenarios.BKG_ABSENT)
    z, methods = [], []
    for smp, bkg, _truth in scenarios.background_pairs(det, N_PAIRS):
        res = compute_activities(smp.spectrum, curve, ActivityOptions(nuclides=names, bkg_mode=mode,
                                                                      min_intensity_pct=1.0),
                                 background=bkg.spectrum)
        for nm, es in scenarios.BKG_ABSENT.items():
            for e in es:
                _r, ln = _line(res, nm, e)
                methods.append(ln.primary_method)
                if ln.primary_net is not None and ln.primary_net_unc and ln.primary_method in USED:
                    z.append(ln.primary_net / ln.primary_net_unc)
    return {**_z_stats(z), "methods": {m: methods.count(m) for m in sorted(set(methods))}, "lines": len(methods)}


def criteria(name: str, m: dict) -> list[dict]:
    def c(cid, value, ok, limit):
        return {"id": f"{name}.{cid}", "value": value, "pass": bool(ok), "limit": limit}
    out = [c("PR.C1.mean_z", m["zero"]["mean_z"], abs(m["zero"]["mean_z"]) <= 0.2, "abs <= 0.2"),
           c("PR.C1.cov2", m["zero"]["cov2"], 0.91 <= m["zero"]["cov2"] <= 0.99, "in [0.91, 0.99]")]
    for mode, v in m["bkg_absent"].items():
        out += [c(f"PR.C2.{mode}.mean_z", v["mean_z"], abs(v["mean_z"]) <= 0.3, "abs <= 0.3"),
                c(f"PR.C2.{mode}.cov2", v["cov2"], v["cov2"] >= 0.90, ">= 0.90")]
    for s in WEAK_S:
        v = m[f"weak_s{s:g}"]
        out += [c(f"PR.C3.s{s:g}.mean_z", v["mean_z"], abs(v["mean_z"]) <= 0.3, "abs <= 0.3"),
                c(f"PR.C3.s{s:g}.cov2", v["cov2"], 0.90 <= v["cov2"] <= 0.99, "in [0.90, 0.99]"),
                c(f"PR.C3.s{s:g}.interval", v["interval_coverage"], v["interval_coverage"] >= 0.89, ">= 0.89")]
    h = m["h3b"]
    out += [c("PR.C4.present", float(h["primary_present"] and h["best_present"]),
              h["primary_present"] and h["best_present"], "all"),
            c("PR.C4.d2_detected", h["d2_detected"], 0.65 <= h["d2_detected"] <= 0.92, "in [0.65, 0.92]"),
            c("PR.C4.d1_le_d2", h["d1_detected"], h["d1_detected"] <= h["d2_detected"], "<= D2")]
    for mode, v in m["m2"].items():
        out += [c(f"PR.C5.{mode}.negative", v["negative"], v["negative"] >= 18, ">= 18 of 20"),
                c(f"PR.C5.{mode}.best", v["best_and_interval"], v["best_and_interval"] == v["n"], "all"),
                c(f"PR.C5.{mode}.no_activity", v["no_activity_not_detected"],
                  v["no_activity_not_detected"] == v["n"], "all")]
    i = m["interference"]
    out += [c("PR.C6.interfered", i["interfered"], i["interfered"] == i["n"], "all 50"),
            c("PR.C6.detected", i["detected"], i["detected"] == 0, "0"),
            c("PR.C6.best", i["best_from_it"], i["best_from_it"] == 0, "0"),
            c("PR.C7.false_detect", m["zero_iso_false_detect"], 0.010 <= m["zero_iso_false_detect"] <= 0.090,
              "in [0.010, 0.090]")]
    return out


def criteria_v2(name: str, m: dict) -> list[dict]:
    """docs/baseline/signed_primary_amendment_protocol.md (PA.*)."""
    def c(cid, value, ok, limit):
        return {"id": f"{name}.{cid}", "value": value, "pass": bool(ok), "limit": limit}
    out = []
    if name == "HPGe":
        out += [c("PA.C1.mean_z", m["zero"]["mean_z"], abs(m["zero"]["mean_z"]) <= 0.2, "abs <= 0.2"),
                c("PA.C1.cov2", m["zero"]["cov2"], 0.91 <= m["zero"]["cov2"] <= 0.99, "in [0.91, 0.99]")]
        for mode, v in m["bkg_absent"].items():
            out += [c(f"PA.C2.{mode}.mean_z", v["mean_z"], abs(v["mean_z"]) <= 0.3, "abs <= 0.3"),
                    c(f"PA.C2.{mode}.cov2", v["cov2"], v["cov2"] >= 0.90, ">= 0.90")]
        for s in WEAK_S:
            v = m[f"weak_s{s:g}"]
            out += [c(f"PA.C3.s{s:g}.mean_z", v["mean_z"], abs(v["mean_z"]) <= 0.3, "abs <= 0.3"),
                    c(f"PA.C3.s{s:g}.cov2", v["cov2"], 0.90 <= v["cov2"] <= 0.99, "in [0.90, 0.99]"),
                    c(f"PA.C3.s{s:g}.interval", v["interval_coverage"], v["interval_coverage"] >= 0.89, ">= 0.89")]
        h = m["h3b"]
        out += [c("PA.C4.present", float(h["primary_present"] and h["best_present"]),
                  h["primary_present"] and h["best_present"], "all"),
                c("PA.C4.d2_detected", h["d2_detected"], 0.65 <= h["d2_detected"] <= 0.92, "in [0.65, 0.92]"),
                c("PA.C4.d1_le_d2", h["d1_detected"], h["d1_detected"] <= h["d2_detected"], "<= D2"),
                c("PA.C9.own_peak_interfered", h["methods"]["interfered"], h["methods"]["interfered"] <= 2,
                  "<= 2 of 100")]
    for mode, v in m["m2"].items():
        out += [c(f"PA.C5.{mode}.negative", v["negative"], v["negative"] >= 18, ">= 18 of 20"),
                c(f"PA.C5.{mode}.no_activity", v["no_activity_not_detected"],
                  v["no_activity_not_detected"] == v["n"], "all")]
        if name == "HPGe":
            out.append(c(f"PA.C5.{mode}.best", v["best_and_interval"], v["best_and_interval"] == v["n"], "all"))
        else:
            ok = v["best_and_interval"] + v["flagged"] >= v["n"] and v["best_from_flagged"] == 0
            out.append(c(f"PA.C5.{mode}.best_or_flagged", v["best_and_interval"] + v["flagged"], ok,
                         "all; none from a flagged line"))
    i = m["interference"]
    out += [c("PA.C6.interfered", i["interfered"], i["interfered"] >= 45, ">= 45 of 50"),
            c("PA.C6.detected", i["detected"], i["detected"] == 0, "0"),
            c("PA.C6.best", i["best_from_it"], i["best_from_it"] == 0, "0")]
    fd = m["zero_iso_false_detect"]
    out.append(c("PA.C7.false_detect", fd, (0.010 <= fd <= 0.090) if name == "HPGe" else fd <= 0.090,
                 "in [0.010, 0.090]" if name == "HPGe" else "<= 0.090"))
    if name == "NaI":
        sets = [("zero", m["zero"]["used"])] + [(f"weak_s{s:g}", m[f"weak_s{s:g}"]["used"]) for s in WEAK_S] + [
            (f"bkg_absent.{k}", v) for k, v in m["bkg_absent"].items()]
        for key, v in sets:
            if v["n"] >= 20:
                out.append(c(f"PA.C8.{key}", v["mean_z"], abs(v["mean_z"]) <= 0.3 and v["cov2"] >= 0.90,
                             f"used n={v['n']}: abs mean z <= 0.3, cov2 >= 0.90 (cov2 {v['cov2']:.3f})"))
            else:
                out.append(c(f"PA.C8.{key}", float(v["n"]), True, "fewer than 20 used lines: reported"))
    return out


V2_RESULTS = Path(__file__).resolve().parents[2] / "docs" / "baseline" / "after_PR1" / "signed_primary_results_v2.md"


def _v2_measured() -> dict:
    text = V2_RESULTS.read_text(encoding="utf-8")
    return json.loads(text.split("## Measured values", 1)[1].split("```", 2)[1])


def _same(old, new, path="") -> list[str]:
    """Paths of `old` whose value differs in `new` (keys added in `new` are ignored)."""
    if isinstance(old, dict):
        if not isinstance(new, dict):
            return [path]
        return [d for k, v in old.items() for d in _same(v, new.get(k), f"{path}/{k}")]
    if isinstance(old, float) and isinstance(new, float) and math.isnan(old) and math.isnan(new):
        return []
    return [] if old == new else [path]


def criteria_v3(name: str, m: dict) -> list[dict]:
    """docs/baseline/window_polynomial_protocol.md (WP.*)."""
    def c(cid, value, ok, limit):
        return {"id": f"{name}.{cid}", "value": value, "pass": bool(ok), "limit": limit}
    if name == "HPGe":
        diff = _same(_v2_measured()["HPGe"], json.loads(json.dumps(m, default=float)))
        return [c("WP.C9.identical_to_v2", float(len(diff)), not diff, "0 differences" + (
            f" ({', '.join(diff[:5])})" if diff else ""))]
    out = []
    z = m["zero"]
    used = z["used"]
    frac = used["n"] / N_ZERO
    out += [c("WP.C1.used", frac, frac >= 0.90, ">= 0.90"),
            c("WP.C1.mean_z", used["mean_z"], abs(used["mean_z"]) <= 0.2, "abs <= 0.2"),
            c("WP.C1.cov2", used["cov2"], 0.91 <= used["cov2"] <= 0.99, "in [0.91, 0.99]")]
    for mode, v in m["bkg_absent"].items():
        f = v["n"] / v["lines"] if v["lines"] else 0.0
        out += [c(f"WP.C2.{mode}.used", f, f >= 0.80, ">= 0.80"),
                c(f"WP.C2.{mode}.mean_z", v["mean_z"], abs(v["mean_z"]) <= 0.3, "abs <= 0.3"),
                c(f"WP.C2.{mode}.cov2", v["cov2"], v["cov2"] >= 0.90, ">= 0.90")]
    for s in WEAK_S:
        v = m[f"weak_s{s:g}"]
        u = v["used"]
        if u["n"] >= 20:
            out += [c(f"WP.C3.s{s:g}.mean_z", u["mean_z"], abs(u["mean_z"]) <= 0.3, f"abs <= 0.3 (used n={u['n']})"),
                    c(f"WP.C3.s{s:g}.cov2", u["cov2"], 0.90 <= u["cov2"] <= 0.99, "in [0.90, 0.99]")]
        else:
            out.append(c(f"WP.C3.s{s:g}.used", float(u["n"]), True, "fewer than 20 used: reported"))
        out.append(c(f"WP.C3.s{s:g}.interval", v["interval_coverage"], v["interval_coverage"] >= 0.89, ">= 0.89"))
    h = m["h3b"]
    out += [c("WP.C4.present", float(h["primary_present"] and h["best_present"]),
              h["primary_present"] and h["best_present"], "all"),
            c("WP.C4.d2_detected", h["d2_detected"], h["d2_detected"] >= 0.50, ">= 0.50"),
            c("WP.C4.d1_le_d2", h["d1_detected"], h["d1_detected"] <= h["d2_detected"], "<= D2")]
    for mode, v in m["m2"].items():
        out += [c(f"WP.C5.{mode}.negative", v["negative"], v["negative"] >= 18, ">= 18 of 20"),
                c(f"WP.C5.{mode}.best", v["best_and_interval"], v["best_and_interval"] == v["n"], "all"),
                c(f"WP.C5.{mode}.no_activity", v["no_activity_not_detected"],
                  v["no_activity_not_detected"] == v["n"], "all")]
    i = m["interference"]
    out += [c("WP.C6.interfered", i["interfered"], i["interfered"] >= 45, ">= 45 of 50"),
            c("WP.C6.detected", i["detected"], i["detected"] == 0, "0"),
            c("WP.C6.best", i["best_from_it"], i["best_from_it"] == 0, "0")]
    fd = m["zero_iso_false_detect"]
    out.append(c("WP.C7.false_detect", fd, 0.010 <= fd <= 0.090, "in [0.010, 0.090]"))
    ed = m["edge"]
    out.append(c("WP.C8.false_detect", ed["false_detect"], ed["false_detect"] <= 0.090, "<= 0.090"))
    if ed["used"]["n"] >= 20:
        ok = abs(ed["used"]["mean_z"]) <= 0.3 and ed["used"]["cov2"] >= 0.90
        out.append(c("WP.C8.used", ed["used"]["mean_z"], ok,
                     f"used n={ed['used']['n']}: abs mean z <= 0.3, cov2 >= 0.90 (cov2 {ed['used']['cov2']:.3f})"))
    else:
        out.append(c("WP.C8.used", float(ed["used"]["n"]), True, "fewer than 20 used: reported"))
    return out


def run_all() -> dict:
    return {det.name: run_detector(det) for det in (HPGE, NAI)}


def report(results: dict) -> str:
    lines = ["# Signed primary result: results", "",
             "Protocol: `window_polynomial_protocol.md` (harness version 3; version 2 criteria in `criteria_v2`, "
             "version 1 in `criteria`).", "", "| id | value | limit | status |", "|---|---|---|---|"]
    for name, m in results.items():
        for c in criteria_v3(name, m):
            v = c["value"]
            lines.append(f"| {c['id']} | {v:.4g} | {c['limit']} | {'PASS' if c['pass'] else 'FAIL'} |")
    lines += ["", "## Measured values", "", "```", json.dumps(results, indent=1, default=float), "```", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    text = report(run_all())
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "signed_primary_results.md").write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

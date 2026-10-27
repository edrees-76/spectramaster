"""Round-4 review, calibration and manual-fit findings (R4-D).

Harness of ``docs/baseline/round4_calibration_protocol.md``.  ``--collect`` writes the raw
observations of the current code to ``after_R4D/round4_calibration_before.json`` (before the
change); without it the observations are compared with that file and the results are written to
``after_R4D/round4_calibration.{md,json}``.  The IAEA 2002 test spectra stay outside the
repository: only names and calibration coefficients are recorded.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "baseline" / "after_R4D"
BEFORE_JSON = OUT / "round4_calibration_before.json"
REL = 1e-9


def _close(a, b, rel=REL) -> bool:
    if a is None or b is None:
        return a is None and b is None
    a, b = list(a), list(b)
    return len(a) == len(b) and all(math.isclose(x, y, rel_tol=rel, abs_tol=1e-15) for x, y in zip(a, b))


def _fwhm_range(coeffs, lo: float, hi: float):
    """(min, max) of the FWHM polynomial (keV) over channels lo..hi."""
    ch = np.linspace(lo, hi, 2001)
    v = np.polynomial.polynomial.polyval(ch, list(coeffs))
    return float(v.min()), float(v.max())


# ------------------------------------------------------------------ C1: dialog refit of the FWHM
def _c1() -> list[dict]:
    from ..tools import calibrate as cal
    from .scenarios import calibration_source
    from .synthetic import HPGE
    out = []
    for syn in calibration_source(HPGE, "Eu-152", 3):
        spec = syn.spectrum
        sc = cal.calibrate_from_source(spec, "Eu-152")
        row = {"seed": syn.seed, "proposal_fwhm": list(sc.fwhm_fit.coeffs) if sc.fwhm_fit else None,
               "proposal_labels": list(sc.fwhm_fit.labels) if sc.fwhm_fit else []}
        refit = getattr(cal, "fwhm_from_widths", None)
        if refit is not None and sc.fwhm_fit is not None:
            rng = (spec.first_channel, spec.first_channel + spec.num_channels - 1)
            used = [(p.nuclide, p.energy) for p in sc.points if p.used]
            same, _note = refit(sc.line_widths, used, sc.coeffs, rng)
            row["refit_all"] = list(same.coeffs) if same else None
            # exclude the line of the FWHM fit with the largest width residual, refit energy and FWHM
            # as the dialog does (user exclusion kept, automatic exclusions re-tested)
            k = int(np.argmax([abs(r) for r in sc.fwhm_fit.residuals]))
            gone = sc.fwhm_fit.labels[k]
            pts = copy.deepcopy(sc.points)
            for p in pts:
                p.used, p.reason = (False, "excluded by the user: R4-D check") if p.label == gone else (True, "")
                p.loo_residual_kev = None
            det = sc.validation.detector_type if sc.validation is not None else ""
            fit, _p, _c = cal.fit_points(pts, order=None, det=det)
            keep = [(p.nuclide, p.energy) for p in pts if p.used]
            new, _note = refit(sc.line_widths, keep, fit.coeffs, rng)
            row.update(excluded=gone, refit_excluded=list(new.coeffs) if new else None,
                       refit_excluded_labels=list(new.labels) if new else [])
        out.append(row)
    return out


# ------------------------------------------------------------------ C2: positive, rising FWHM
WIDTH_CASES = {
    # Gemini's case: 6.0 keV at channel 100 (a doublet), 2.5 keV at channel 1000, E = 0.5 keV/ch
    "gemini_falling": [(100.0, 12.0), (1000.0, 5.0)],
    "rising_two": [(200.0, 2.0), (3000.0, 3.2)],
    # rises over the lines but the quadratic through them is negative at both ends of 0..8191
    "quadratic_negative": [(1000.0, 2.0), (1500.0, 3.0), (2000.0, 3.8), (2500.0, 4.4)],
}
WIDTH_COEFFS = [0.0, 0.5]
WIDTH_RANGE = (0, 8191)


def _old_widths_fit(pts):
    """The FWHM fit of engine 1.17.0 (_fwhm_from_lines after the width measurement)."""
    from ..tools import calibrate as cal
    from numpy.polynomial import polynomial as P
    pts = [(c, w * abs(float(P.polyval(c, P.polyder(WIDTH_COEFFS)))), f"L{i}") for i, (c, w) in enumerate(pts)]
    while len(pts) >= 2:
        pairs = [(c, v) for c, v, _l in pts]
        ff = cal.fit_fwhm_calibration(pairs, 1, labels=[l for *_cv, l in pts])
        if len(pts) >= 4:
            q = cal.fit_fwhm_calibration(pairs, 2, labels=[l for *_cv, l in pts])
            ch = np.linspace(min(c for c, _v in pairs), max(c for c, _v in pairs), 200)
            if np.all(np.diff(P.polyval(ch, q.coeffs)) > 0):
                ff = q
        rel = [abs(v / f - 1.0) if f > 0 else math.inf for v, f in zip(ff.values, ff.fitted)]
        worst = int(np.argmax(rel))
        if rel[worst] <= cal.FWHM_OUTLIER_REL or len(pts) <= 3:
            return ff
        del pts[worst]
    return None


def _c2() -> dict:
    from ..tools import calibrate as cal
    out = {}
    new_api = getattr(cal, "fwhm_from_widths", None)
    for name, pts in WIDTH_CASES.items():
        if new_api is None:
            ff, note = _old_widths_fit(pts), ""
        else:
            widths = {(f"L{i}", float(i)): (c, w) for i, (c, w) in enumerate(pts)}
            ff, note = new_api(widths, list(widths), WIDTH_COEFFS, WIDTH_RANGE)
        out[name] = {"coeffs": list(ff.coeffs) if ff else None, "order": ff.order if ff else None,
                     "range_kev": _fwhm_range(ff.coeffs, *WIDTH_RANGE) if ff else None, "note": note}
    return out


# ------------------------------------------------------------------ C3: regression on real and synthetic sources
def _iaea_list():
    from . import iaea2002 as ia
    bkg = list(ia.BKG_NUCLIDES)
    calib = [n for n in ia.CAL_NUCLIDES if n != "Cr-51"]
    test = [n for n in ia.TEST_NUCLIDES if n != "Cr-51"]
    return ([(n, bkg) for n in ("BGSMALLMARI", "BGSMALLPOINT", "BGBIGPOINT", "mix2neqlong")]
            + [(n, calib) for n in ("maricsmall", "picbig")]
            + [(n, test) for n in ("maritsmall", "maritsmall60", "PITBIG", "PITBIG60")])


def _c3() -> dict:
    from ..tools import calibrate as cal
    from . import iaea2002 as ia
    from .benchmark import CAL_SOURCE
    from .scenarios import calibration_source
    from .synthetic import HPGE, NAI
    rows = {}
    for name, nucs in _iaea_list():
        try:
            spec = ia.read(ia.DEFAULT_DATA, name)
        except (FileNotFoundError, OSError):
            rows[f"iaea:{name}"] = {"missing": True}
            continue
        sc = cal.calibrate_from_source(spec, nucs, use_existing=False)
        rows[f"iaea:{name}"] = {"energy": list(sc.coeffs), "fwhm": list(sc.fwhm_fit.coeffs) if sc.fwhm_fit else None,
                                "range": [spec.first_channel, spec.first_channel + spec.num_channels - 1]}
    for det in (HPGE, NAI):
        for syn in calibration_source(det, CAL_SOURCE[det.name], 5):
            spec = syn.spectrum
            sc = cal.calibrate_from_source(spec, CAL_SOURCE[det.name])
            rows[f"synthetic:{det.name}:{syn.seed}"] = {
                "energy": list(sc.coeffs), "fwhm": list(sc.fwhm_fit.coeffs) if sc.fwhm_fit else None,
                "range": [spec.first_channel, spec.first_channel + spec.num_channels - 1]}
    return rows


# ------------------------------------------------------------------ C4: variance of the net spectrum in the manual fit
def _spectra():
    from ..model import Spectrum
    rng = np.random.default_rng(4)
    ch = np.arange(1024)
    peak = np.exp(-0.5 * ((ch - 500) / 2.5) ** 2) / (2.5 * math.sqrt(2 * math.pi))
    s = rng.poisson(50.0 + 1000.0 * peak).astype(float)
    b = rng.poisson(80.0 + 400.0 * peak).astype(float)      # background: twice the live time
    sample = Spectrum(counts=[float(x) for x in s], live_time=1000.0, real_time=1010.0, energy_coeffs=[0.0, 0.5])
    bkg = Spectrum(counts=[float(x) for x in b], live_time=2000.0, real_time=2010.0, energy_coeffs=[0.0, 0.5])
    return sample, bkg


def _fit(spec, variance=None) -> dict:
    from ..analysis.manual import refit_region
    rf = refit_region(spec, 480, 520, [500.0], variance=variance)
    p = rf.peaks[0]
    return {"area": float(p.net_area), "unc": float(p.net_area_unc),
            "not_poisson": rf.options.get("not_poisson", ""), "variance": rf.options.get("variance", "")}


def _gui_variance(spec):
    """What the manual-fit window passes as ``variance=`` (nothing in engine 1.17.0)."""
    from ..analysis import background as bg
    f = getattr(bg, "channel_variance", None)
    return None if f is None else f(spec)


def _c4() -> dict:
    from dataclasses import replace

    from ..tools import spectrum_ops as ops
    from ..tools.arithmetic import subtract_background
    sample, bkg = _spectra()
    k = sample.live_time / bkg.live_time
    explicit = np.asarray(sample.counts) + k * k * np.asarray(bkg.counts)
    out = {}
    net, sigma = subtract_background(sample, bkg)
    v = _gui_variance(net)
    out["subtracted"] = {"explicit": _fit(net, explicit), "gui": _fit(net, v),
                         "gui_variance_equal": v is not None
                         and bool(np.allclose(v, np.asarray(sigma) ** 2, rtol=REL, atol=0))}
    stripped = ops.strip(sample, ops.normalize(bkg, k))
    v = _gui_variance(stripped)
    out["stripped"] = {"explicit": _fit(stripped, explicit), "gui": _fit(stripped, v),
                       "gui_variance_equal": v is not None and bool(np.allclose(v, explicit, rtol=REL, atol=0))}
    edited = replace(net, counts=list(net.counts))
    edited.counts[500] += 1.0
    out["stale"] = {"smoothed": _gui_variance(ops.smooth(net, 3)) is not None,
                    "edited": _gui_variance(edited) is not None}
    out["raw"] = {"gui": _fit(sample, _gui_variance(sample)), "plain": _fit(sample)}
    return out


def collect() -> dict:
    from ..lab.session import ENGINE_VERSION
    return {"engine": ENGINE_VERSION, "C1": _c1(), "C2": _c2(), "C3": _c3(), "C4": _c4()}


# ------------------------------------------------------------------ criteria
def criteria(res: dict, before: dict) -> dict:
    c = {}
    rows = res["C1"]
    ok = bool(rows) and len(rows) == len(before["C1"])
    ok = ok and all(r.get("refit_all") is not None and _close(r["refit_all"], r["proposal_fwhm"])
                    and _close(r["proposal_fwhm"], b["proposal_fwhm"]) for r, b in zip(rows, before["C1"]))
    ok = ok and all(r.get("refit_excluded") is not None and r["excluded"] not in r["refit_excluded_labels"]
                    and not _close(r["refit_excluded"], r["proposal_fwhm"]) for r in rows)
    c["RD.C1"] = (ok, "; ".join(f"proposal {len(r['proposal_labels'])} widths, refit without exclusion "
                                f"{'identical' if _close(r.get('refit_all'), r['proposal_fwhm']) else 'DIFFERENT'}; "
                                f"without {r.get('excluded')}: {len(r.get('refit_excluded_labels') or [])} widths"
                                for r in rows))
    c2, b2 = res["C2"], before["C2"]
    g, r2, q = c2["gemini_falling"], c2["rising_two"], c2["quadratic_negative"]
    ok = g["coeffs"] is None and "decreas" in g["note"]
    ok = ok and _close(r2["coeffs"], b2["rising_two"]["coeffs"])
    ok = ok and q["order"] == 1 and q["range_kev"] is not None and q["range_kev"][0] > 0
    c["RD.C2"] = (ok, f"Gemini's case: {g['coeffs']} {g['note']!r} (before {b2['gemini_falling']['coeffs']}, "
                      f"FWHM {b2['gemini_falling']['range_kev']} keV); rising case {r2['coeffs']}; quadratic case "
                      f"order {q['order']} FWHM {q['range_kev']} keV (before order "
                      f"{b2['quadratic_negative']['order']}, {b2['quadratic_negative']['range_kev']} keV)")
    c3, b3 = res["C3"], before["C3"]
    changed, bad = [], []
    for name, r in b3.items():
        a = c3.get(name, {})
        if r.get("missing") or a.get("missing"):
            continue
        if not _close(a.get("energy"), r.get("energy")):
            bad.append(f"{name} energy")
        if not _close(a.get("fwhm"), r.get("fwhm")):
            old_min = _fwhm_range(r["fwhm"], *r["range"])[0] if r.get("fwhm") else None
            changed.append(f"{name} (old FWHM min {old_min})")
            if old_min is None or old_min > 0:
                bad.append(name)
    n = sum(1 for r in b3.values() if not r.get("missing"))
    c["RD.C3"] = (not bad and n > 0, f"{n} source calibrations; FWHM changed: {changed or 'none'}; "
                                     f"not allowed: {bad or 'none'}")
    c4, bs = res["C4"], before["C4"]
    ok = True
    for key in ("subtracted", "stripped"):
        e, gu = c4[key]["explicit"], c4[key]["gui"]
        ok = (ok and c4[key]["gui_variance_equal"] and math.isclose(gu["area"], e["area"], rel_tol=REL)
              and math.isclose(gu["unc"], e["unc"], rel_tol=REL) and not gu["not_poisson"])
    ok = ok and not c4["stale"]["smoothed"] and not c4["stale"]["edited"]
    ok = ok and c4["raw"]["gui"] == bs["raw"]["gui"] == c4["raw"]["plain"]
    c["RD.C4"] = (ok, f"net spectrum: manual fit u {c4['subtracted']['gui']['unc']:.4f}, explicit S + k2 B "
                      f"{c4['subtracted']['explicit']['unc']:.4f} (before {bs['subtracted']['gui']['unc']:.4f}, "
                      f"not-Poisson note {bool(bs['subtracted']['gui']['not_poisson'])}); Aptec strip: u "
                      f"{c4['stripped']['gui']['unc']:.4f}, explicit {c4['stripped']['explicit']['unc']:.4f} "
                      f"(before {bs['stripped']['gui']['unc']:.4f}); stale variance used {c4['stale']}; "
                      f"raw spectrum unchanged {c4['raw']['gui'] == bs['raw']['gui']}")
    return {k: {"pass": bool(v[0]), "detail": v[1]} for k, v in c.items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true",
                    help=f"write the raw observations to {BEFORE_JSON.name} (before the change) and stop")
    a = ap.parse_args(argv)
    res = collect()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.collect:
        BEFORE_JSON.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8", newline="\n")
        return 0
    before = json.loads(BEFORE_JSON.read_text(encoding="utf-8"))
    res["criteria"] = criteria(res, before)
    n_pass = sum(v["pass"] for v in res["criteria"].values())
    res["summary"] = {"pass": n_pass, "fail": len(res["criteria"]) - n_pass}
    (OUT / "round4_calibration.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8",
                                                 newline="\n")
    lines = ["# Round-4 calibration and manual-fit findings (after_R4D)", "",
             "Protocol: `docs/baseline/round4_calibration_protocol.md`. Synthetic spectra and the IAEA 2002 test "
             "spectra (names and coefficients only).", "",
             f"**{n_pass} PASS / {res['summary']['fail']} FAIL** (RD.C1-C4; RD.C5 is the test suite and the "
             "benchmark, reported in the protocol)", "", "| ID | result | detail |", "|---|---|---|"]
    lines += [f"| {k} | {'PASS' if v['pass'] else 'FAIL'} | {v['detail']} |" for k, v in res["criteria"].items()]
    (OUT / "round4_calibration.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(res["summary"]))
    return 1 if res["summary"]["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())

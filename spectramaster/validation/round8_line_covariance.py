"""Round-8 review, Gemini M3: covariance of the window results of a nuclide's lines
(docs/baseline/round8_line_covariance_protocol.md).

    python -m spectramaster.validation.round8_line_covariance [--collect] [--rerun]

Synthetic data only.  ``--collect`` writes the observations only, to
``docs/baseline/after_R8H/round8_line_covariance_before.json`` (the "before" values); without it
the criteria are evaluated against that file.
``--rerun`` writes the results to RERUN (in the temporary folder) instead of the committed folder.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

from spectramaster.analysis import activity as act
from spectramaster.analysis.background import BackgroundFitter
from spectramaster.analysis.peaks import checked_fwhm_model, find_peaks
from spectramaster.validation import primary as pr, round5_combined as r5, round6_combined as r6, scenarios
from spectramaster.validation.round7_combined import _root
from spectramaster.validation.synthetic import NAI, TruePeak, area_for_snr, continuum_counts, make_spectrum

OUT = r5.OUT.parent / "after_R8H"
RERUN = Path(tempfile.gettempdir()) / "spectramaster_round8_line_covariance"
BEFORE_JSON = OUT / "round8_line_covariance_before.json"
REL, REL_CTRL = 1e-9, 1e-12
UC, BUC, UR = 0.10, 0.10, 0.03            # reference peak: sample and blank counting, expected rate
MC_N, MC_SEED0 = 400, 1000
LIMIT_LO, LIMIT_HI = 0.909, 1.091
BA_LINES = (79.614, 80.998, 276.399, 302.851, 356.013, 383.849)
# (name, mode): the NaI Ba-133 cases; each with Currie and ISO 11929
CASES = (("none", None), ("spectrum", "spectrum"), ("peak", "peak"), ("ref_blank", None))
LINE_FIELDS = ("energy", "primary", "primary_u_count", "decision_threshold", "mda", "ref_unc_bq",
               "window_continuum", "primary_method", "detected")


def _base():
    cont = scenarios.base_continuum(NAI)
    return cont, continuum_counts(NAI, cont)


def _sample(seed=7):
    cont, cy = _base()
    return make_spectrum(NAI, pr._co60(NAI, cy), cont, seed).spectrum


def _background():
    cont, _cy = _base()
    return make_spectrum(NAI, [], cont, 8).spectrum


def _blank_spectrum():
    """The base continuum with Co-60 and the Ba-133 lines (the blank carries the nuclide)."""
    cont, cy = _base()
    ba = [TruePeak(e, area_for_snr(NAI, cy, e, 15.0), tag="Ba-133") for e in BA_LINES]
    return make_spectrum(NAI, pr._co60(NAI, cy) + ba, cont, 9).spectrum


def _opts(nuclide, mda, mode, ref=False, method="mean"):
    kw = {"bkg_mode": mode} if mode else {}
    r = {"energy": r6.REF_E, "rate": 10000.0 / r5.LIVE, "rate_rel_unc": UR} if ref else None
    return act.ActivityOptions(nuclides=[nuclide], method=method, mda_method=mda, reference_peak=r, **kw)


def _with_ref(sp, u_rel):
    return find_peaks(sp) + [r6._ref_peak(u_rel)]


def run_case(name, mode, mda, nuclide="Ba-133", method="mean"):
    """(nuclide result, options, background spectrum or None)."""
    curve = r5._flat_curve()
    sp = _sample()
    if name == "ref_blank":
        o = _opts(nuclide, mda, None, ref=True, method=method)
        bl = act.compute_activities(_blank_spectrum(), curve, o, peaks=_with_ref(_blank_spectrum(), BUC))
        q = act.compute_activities(sp, curve, o, peaks=_with_ref(sp, UC), blank=bl)
        return q.nuclides[0], o, None
    o = _opts(nuclide, mda, mode, method=method)
    bg = _background() if mode else None
    q = act.compute_activities(sp, curve, o, background=bg)
    return q.nuclides[0], o, bg


def _usable(res):
    return [l for l in res.lines if l.mda > 0 and l.primary is not None and l.primary_method == "window"]


def _vec(n, lo, c):
    v = np.zeros(n)
    v[lo:lo + len(c)] = c
    return v


def _estimator(counts, lo, hi, m, quadratic):
    """Coefficients (full length) of the window estimator G - B on `counts`, built here: the linear
    continuum from the two m-channel sides, or the quadratic continuum's c over its sides."""
    n = len(counts)
    if not quadratic:
        c = np.full(hi - lo + 1 + 2 * m, -(hi - lo + 1) / (2.0 * m))
        c[m:m + hi - lo + 1] = 1.0
        return _vec(n, lo - m, c)
    q = act.quadratic_window(counts, lo, hi, m)
    v = np.zeros(n)
    v[lo:hi + 1] = 1.0
    np.subtract.at(v, np.asarray(q.idx, dtype=int), np.asarray(q.c, dtype=float))
    return v


def covariance(res, o, sp, bg, mode):
    """(lines, normalised weights, C) with C_ii = primary_u_count^2 and C_ij of the protocol."""
    use = _usable(res)
    y = np.asarray(sp.counts, dtype=float)
    fw_ch, _src = checked_fwhm_model(sp, np.maximum(y, 0.0))
    b, k = None, 0.0
    if mode == "spectrum":
        b, k = np.clip(np.asarray(bg.counts, dtype=float), 0, None), sp.live_time / bg.live_time
    elif mode == "peak":
        bf = BackgroundFitter(sp, bg)
        b, k = bf.b, bf.k
    a_vec, b_vec = [], []
    for l in use:
        lo, hi, m, _f = act.line_window(sp, l.energy, fw_ch)
        fwin = act.continuum_under(sp, l.energy, fw_ch)[3]
        w = l.primary_u_count / l.primary_net_unc          # Bq per count (the result may be 0)
        quad = l.window_continuum == "quadratic"
        a_vec.append(w / fwin * _estimator(y, lo, hi, m, quad))
        b_vec.append(-k * w / fwin * _estimator(b, lo, hi, m, quad) if b is not None else None)
    n = len(use)
    cmat = np.zeros((n, n))
    yp = np.maximum(y, 0.0)
    for i in range(n):
        for j in range(n):
            if i == j:
                cmat[i, j] = use[i].primary_u_count ** 2
                continue
            c = float(np.sum(a_vec[i] * a_vec[j] * yp))
            if b is not None:
                c += float(np.sum(b_vec[i] * b_vec[j] * np.maximum(b, 0.0)))
            cmat[i, j] = c
    ui = o.intensity_rel_unc
    v = [l.primary_u_count ** 2 + (l.primary * ui) ** 2 + (l.primary * l.int_rel_unc) ** 2 for l in use]
    lam = np.array([1.0 / x for x in v])
    return use, lam / lam.sum(), cmat


def expected(res, o, sp, bg, mode, ref):
    """primary_u, decision threshold and limit of the weighted mean from the protocol's formulas."""
    use, lam, cmat = covariance(res, o, sp, bg, mode)
    if len(use) < 2:
        return {"n": len(use)}
    a = float(sum(x * l.primary for x, l in zip(lam, use)))
    aa = abs(a)
    uc2 = float(lam @ cmat @ lam)
    ue = sum(x * abs(l.primary) * l.eff_rel_unc for x, l in zip(lam, use))
    ut = sum(x * abs(l.primary) * l.coi_rel_unc for x, l in zip(lam, use))
    ul = math.sqrt(sum((x * l.primary * l.int_rel_unc) ** 2 for x, l in zip(lam, use)))
    g = np.zeros(3)
    if ref:
        for x, l in zip(lam, use):
            ab = l.blank_activity or 0.0
            gross = l.primary + ab
            g += x * np.array([gross * UC, ab * BUC, gross * UR - ab * UR])
    ur = float(np.linalg.norm(g))
    u = math.sqrt(uc2 + ue ** 2 + math.hypot(aa * o.intensity_rel_unc, ul) ** 2
                  + (aa * o.attenuation_rel_unc) ** 2 + ur ** 2 + ut ** 2)
    ka, kb = o.k_alpha, o.k_beta
    s0 = np.array([l.decision_threshold / ka for l in use])
    c0 = cmat.copy()
    np.fill_diagonal(c0, s0 ** 2)
    iso = o.mda_method == "iso11929"
    slope = float(sum(x * x * l.limit_slope for x, l in zip(lam, use)))
    for i, li in enumerate(use):
        for j, lj in enumerate(use):
            if i != j and li.ref_dg and lj.ref_dg:
                c0[i, j] += float(np.dot(li.ref_g0, lj.ref_g0))
                if iso:
                    slope += lam[i] * lam[j] * float(np.dot(li.ref_dg, lj.ref_g0) + np.dot(li.ref_g0, lj.ref_dg))
    s0sq = float(lam @ c0 @ lam)
    big_r = 0.0
    if iso:
        eff = sum(x * l.eff_rel_unc for x, l in zip(lam, use))
        coi = sum(x * l.coi_rel_unc for x, l in zip(lam, use))
        rr = sum(x * l.ref_rel_unc for x, l in zip(lam, use))
        intens = math.hypot(o.intensity_rel_unc, math.sqrt(sum((x * l.int_rel_unc) ** 2 for x, l in zip(lam, use))))
        big_r = math.sqrt(eff ** 2 + intens ** 2 + o.attenuation_rel_unc ** 2 + rr ** 2 + coi ** 2)
    ys = ka * math.sqrt(s0sq)
    off = [abs(cmat[i, j]) for i in range(len(use)) for j in range(len(use)) if i != j]
    return {"n": len(use), "primary": a, "primary_u": u, "ref_term": ur, "threshold": ys,
            "limit": _root(ys, kb, slope, s0sq, big_r), "max_offdiag": max(off) if off else 0.0}


def _row(r) -> dict:
    return {"threshold": r.decision_threshold, "mda": r.mda, "activity": r.activity, "u": r.u,
            "primary": r.primary, "primary_u": r.primary_u, "primary_method": r.primary_method,
            "detected": r.detected, "note": r.note,
            "lines": [[getattr(l, f) for f in LINE_FIELDS] for l in r.lines]}


def monte_carlo() -> dict:
    cont, cy = _base()
    curve = r5._flat_curve()
    o = _opts("Ba-133", "currie", None)
    p, u, d = [], [], []
    for i in range(MC_N):
        sp = make_spectrum(NAI, pr._co60(NAI, cy), cont, MC_SEED0 + i).spectrum
        nr = act.compute_activities(sp, curve, o).nuclides[0]
        if nr.primary_method == "window" and nr.activity is None and nr.primary is not None:
            p.append(nr.primary)
            u.append(nr.primary_u)
            d.append(nr.decision_threshold)
    p, u, d = np.array(p), np.array(u), np.array(d)
    sd = float(p.std(ddof=1))
    return {"n": len(p), "mean": float(p.mean()), "sd": sd, "mean_u": float(u.mean()),
            "u_ratio": float(u.mean()) / sd, "dt_ratio": float(d.mean()) / (o.k_alpha * sd),
            "false": float(np.mean(p > d))}


def collect(mc=True) -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    out = {"engine": ENGINE_VERSION, "cases": {}, "controls": {}}
    for name, mode in CASES:
        for mda in ("currie", "iso11929"):
            r, o, bg = run_case(name, mode, mda)
            out["cases"][f"{name}_{mda}"] = {**_row(r), "expected": expected(r, o, _sample(), bg, mode,
                                                                            name == "ref_blank")}
    for mda in ("currie", "iso11929"):
        out["controls"][f"key_{mda}"] = _row(run_case("none", None, mda, method="key")[0])
        out["controls"][f"co60_detected_{mda}"] = _row(run_case("none", None, mda, nuclide="Co-60")[0])
        out["controls"][f"cs137_{mda}"] = _row(run_case("none", None, mda, nuclide="Cs-137")[0])
        o = act.ActivityOptions(nuclides=["Co-60"], method="mean", mda_method=mda)
        r = act.compute_activities(r5._spectrum("sample"), r5._flat_curve(), o, peaks=[]).nuclides[0]
        out["controls"][f"co60_flat_{mda}"] = _row(r)
    if mc:
        out["monte_carlo"] = monte_carlo()
    return out


def _close(a, b, rel=REL) -> bool:
    return a is not None and b is not None and math.isclose(a, b, rel_tol=rel, abs_tol=0.0)


def _same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return a == b or math.isclose(a, b, rel_tol=REL_CTRL, abs_tol=0.0)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    return a == b


def criteria(res: dict, before: dict) -> dict:
    out = {}
    bad1, bad2, bad3, n_used = [], [], [], 0
    for name, c in res["cases"].items():
        e = c["expected"]
        if e["n"] < 2:
            bad1.append(f"{name}: {e['n']} usable lines")
            continue
        n_used += 1
        target = bad3 if name.startswith("ref_blank") else bad1
        if not _close(c["primary_u"], e["primary_u"]):
            target.append(f"{name}: {c['primary_u']:.6g} vs {e['primary_u']:.6g} Bq")
        if not (_close(c["threshold"], e["threshold"]) and _close(c["mda"], e["limit"])):
            bad2.append(f"{name}: {c['threshold']:.6g} / {c['mda']:.6g} vs {e['threshold']:.6g} / "
                        f"{e['limit']:.6g} Bq")
    out["RH8.C1"] = {"value": "; ".join(bad1) or f"primary_u equals W'CW and the other components ({n_used} cases)",
                     "pass": not bad1}
    out["RH8.C2"] = {"value": "; ".join(bad2) or "decision threshold and MDA equal the recomputation",
                     "pass": not bad2}
    out["RH8.C3"] = {"value": "; ".join(bad3) or "reference term equals the norm of the summed components",
                     "pass": not bad3}
    bad4 = [k for k, c in res["controls"].items() if not _same(c, before["controls"][k])]
    bad4 += [f"{k} lines" for k, c in res["cases"].items() if not _same(c["lines"], before["cases"][k]["lines"])]
    out["RH8.C4"] = {"value": "; ".join(bad4) or "controls and every line field identical to before",
                     "pass": not bad4}
    mc = res["monte_carlo"]
    ok5 = LIMIT_LO <= mc["u_ratio"] <= LIMIT_HI and LIMIT_LO <= mc["dt_ratio"] <= LIMIT_HI
    out["RH8.C5"] = {"value": f"{mc['n']} spectra: u / sd {mc['u_ratio']:.4f}, threshold / (1.645 sd) "
                              f"{mc['dt_ratio']:.4f}, false detections {mc['false']:.4f} (reported), mean "
                              f"{mc['mean']:.4g} Bq", "pass": ok5}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--collect", action="store_true", help="write the observations only (the 'before' values)")
    ap.add_argument("--rerun", action="store_true", help=f"write the results to {RERUN}, not the committed folder")
    a = ap.parse_args(argv)
    out = RERUN if a.rerun else OUT
    res = json.loads(json.dumps(collect(), default=float))
    out.mkdir(parents=True, exist_ok=True)
    if a.collect:
        BEFORE_JSON.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {BEFORE_JSON}")
        crit = criteria(res, res)
    else:
        crit = criteria(res, json.loads(BEFORE_JSON.read_text(encoding="utf-8")))
        (out / "round8_line_covariance.json").write_text(json.dumps({"results": res, "criteria": crit}, indent=1,
                                                                    ensure_ascii=False), encoding="utf-8")
    lines = ["# Round-8 covariance of a nuclide's window results (Gemini M3)", "", f"engine {res['engine']}", "",
             "| ID | value | result |", "|---|---|---|"]
    lines += [f"| {k} | {v['value']} | {'PASS' if v['pass'] else 'FAIL'} |" for k, v in crit.items()]
    if not a.collect:
        (out / "round8_line_covariance.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(v["pass"] for v in crit.values())
    print("\n".join(lines))
    print(f"{n} PASS / {len(crit) - n} FAIL")
    return 0 if n == len(crit) else 1


if __name__ == "__main__":
    sys.exit(main())

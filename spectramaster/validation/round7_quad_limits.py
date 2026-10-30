"""Round-7 review, Gemini H3: the limits of a line on the quadratic window
(docs/baseline/round7_quad_limits_protocol.md).

    python -m spectramaster.validation.round7_quad_limits [--collect] [--rerun]

Synthetic data only.  ``--collect`` writes the observations only, to
``docs/baseline/after_R7D/round7_quad_limits_before.json`` (the "before" values); without it the
criteria are evaluated against that file.
``--rerun`` writes the results to RERUN (in the temporary folder) instead of the committed folder,
which a re-run on a later engine then leaves as committed (round8_rerun_protocol.md).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

from spectramaster.analysis import activity as act
from spectramaster.validation import primary as pr
from spectramaster.validation import round5_combined as r5
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE, NAI, continuum_counts, make_spectrum

OUT = r5.OUT.parent / "after_R7D"
RERUN = Path(tempfile.gettempdir()) / "spectramaster_round7_quad_limits"     # --rerun: results here, OUT left as committed
BEFORE_JSON = OUT / "round7_quad_limits_before.json"
N_MC = 200
REL = 1e-12
LIMITS = ("lc_counts", "ld_counts", "decision_threshold", "mda")
METHODS = ("currie", "iso11929")
# (name, detector, continuum, seed, nuclides, method)
CASES = (("nai_cs", NAI, None, 7, ["Cs-137"], "key"), ("nai_ba_mean", NAI, None, 7, ["Ba-133"], "mean"),
         ("hpge_cs", HPGE, None, 7, ["Cs-137"], "key"), ("nai_co", NAI, None, 7, ["Co-60"], "key"),
         ("nai_edge", NAI, "edge", 0, ["Cs-137"], "key"))


def _spectrum(det, cont=None, seed=7):
    cont = pr.edge_continuum(det) if cont == "edge" else scenarios.base_continuum(det)
    return make_spectrum(det, pr._co60(det, continuum_counts(det, cont)), cont, seed).spectrum


def _opt(nuclides, mda_method, **kw):
    return act.ActivityOptions(nuclides=nuclides, mda_method=mda_method, **kw)


def _w_rel(ln, opt) -> float:
    """The relative uncertainty of w the engine uses for this line (flat curve, no attenuation, no
    reference peak)."""
    return math.sqrt(ln.eff_rel_unc ** 2 + opt.intensity_rel_unc ** 2 + ln.int_rel_unc ** 2 + ln.coi_rel_unc ** 2)


def _case(det, cont, seed, nuclides, method, mda_method) -> dict:
    curve = pr._flat_curve()
    sp = _spectrum(det, cont, seed)
    opt = _opt(nuclides, mda_method, method=method)
    res = act.compute_activities(sp, curve, opt)
    out = {"nuclides": [], "lines": []}
    for nr in res.nuclides:
        out["nuclides"].append({"name": nr.nuclide, "decision_threshold": nr.decision_threshold, "mda": nr.mda,
                                "primary": nr.primary, "primary_u": nr.primary_u, "activity": nr.activity, "u": nr.u, "detected": nr.detected,
                                "key_energy": nr.key_energy})
        usable = [l for l in nr.lines if l.mda > 0 and l.primary is not None and l.primary_method == "window"]
        if method == "mean" and len(usable) > 1:
            # the weighted mean's limits from the quadratic windows' own line limits (protocol, change 2)
            own = []
            for l in usable:
                d = dataclasses.asdict(l)
                d["w_rel"] = _w_rel(l, opt)
                if _quad(d):
                    _ld, mda = _expected_limits(d, mda_method)
                    l = _replace(l, decision_threshold=l.window_decision_threshold, mda=mda)
                own.append(l)
            out["nuclides"][-1]["recombined"] = list(act.combined_limits(own, act._primary_weights(own, opt), opt))
        for ln in nr.lines:
            d = dataclasses.asdict(ln)
            d["w_rel"] = _w_rel(ln, opt)
            out["lines"].append(d)
    out["notes"] = list(res.notes)
    return out


def _replace(ln, **kw):
    """`dataclasses.replace` keeping the line's in-memory attributes (the window coefficients
    `_cov_res` / `_ref_vec` of engine 1.34.0, which `combined_limits` uses; round9_harness_protocol.md)."""
    out = dataclasses.replace(ln, **kw)
    for k, v in vars(ln).items():
        if k.startswith("_"):
            setattr(out, k, v)
    return out


def _mc() -> list:
    """Null realisations of the NaI Cs-137 line (seeds 1000 + i), Currie: (window continuum, method,
    primary, reported threshold, quadratic threshold)."""
    curve = pr._flat_curve()
    rows = []
    for i in range(N_MC):
        sp = _spectrum(NAI, None, 1000 + i)
        res = act.compute_activities(sp, curve, _opt(["Cs-137"], "currie"))
        ln = pr._line(res, "Cs-137", pr.CS)[1]
        rows.append([ln.window_continuum, ln.primary_method, ln.primary, ln.decision_threshold,
                     ln.window_decision_threshold])
    return rows


def collect() -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    cases = {f"{name}_{m}": _case(det, cont, seed, nucl, meth, m)
             for name, det, cont, seed, nucl, meth in CASES for m in METHODS}
    return {"engine": ENGINE_VERSION, "cases": cases, "mc": _mc()}


def _close(a, b, rel=REL) -> bool:
    return a is not None and b is not None and math.isclose(a, b, rel_tol=rel, abs_tol=0.0)


def _same(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _covariance_engine(engine: str) -> bool:
    """Engine 1.34.0 or later: window lines carry the covariance of shared channels."""
    return tuple(int(x) for x in engine.split(".")[:3]) >= (1, 34, 0)


def _quad(ln) -> bool:
    return ln["window_continuum"] == "quadratic" and ln["primary_method"] == "window"


def _expected_limits(ln, m) -> tuple:
    """(L_D counts, MDA Bq) of the quadratic window's L_C, recomputed from the protocol's formulas."""
    lc, dt = ln["window_lc_counts"], ln["window_decision_threshold"]
    scale = dt / lc                                   # w / f_w, Bq per window count (Currie)
    sigma0 = lc / act.K_DEFAULT if m == "currie" else None
    if m == "currie":
        _lc, ld = act.currie_limits(sigma0)
        return ld, ld * scale
    w_fw = ln["limit_slope"]                          # w / f_w (no reference peak)
    # ISO 11929: y* = k sigma(0) with the w uncertainty; sigma0 in counts from L_C = y* f_w / w
    lo, hi = 0.0, lc
    for _ in range(200):                             # sigma0 such that the engine's y* equals dt
        mid = 0.5 * (lo + hi)
        ys, _yd = act.iso11929_limits(mid, w_fw, ln["w_rel"])
        lo, hi = (mid, hi) if ys < dt else (lo, mid)
    ys, yd = act.iso11929_limits(0.5 * (lo + hi), w_fw, ln["w_rel"])
    return yd / w_fw, yd


def criteria(res: dict, before: dict) -> dict:
    out = {}
    vals, ok, n_quad = [], True, 0
    for m in METHODS:
        for ln, lb in zip(res["cases"][f"nai_cs_{m}"]["lines"], before["cases"][f"nai_cs_{m}"]["lines"]):
            if not _quad(ln):
                continue
            n_quad += 1
            ld, mda = _expected_limits(ln, m)
            good = (_close(ln["lc_counts"], ln["window_lc_counts"]) and _close(ln["decision_threshold"],
                    ln["window_decision_threshold"]) and _close(ln["ld_counts"], ld, 1e-9) and _close(ln["mda"], mda, 1e-9)
                    and _close(ln["window_lc_counts"], lb["window_lc_counts"]))
            ok &= good
            vals.append(f"{m}: threshold {lb['decision_threshold']:.4g} -> {ln['decision_threshold']:.4g} Bq "
                        f"(quadratic {ln['window_decision_threshold']:.4g}), MDA {lb['mda']:.4g} -> {ln['mda']:.4g} Bq "
                        f"(expected {mda:.4g})")
    out["RD.C1"] = {"value": "; ".join(vals) or "no quadratic line", "pass": ok and n_quad == len(METHODS)}
    vals, ok = [], True
    for m in METHODS:
        c = res["cases"][f"nai_cs_{m}"]
        nr = c["nuclides"][0]
        key = [l for l in c["lines"] if l["energy"] == nr["key_energy"]][0]
        ok &= (_quad(key) and _close(nr["decision_threshold"], key["window_decision_threshold"])
               and _close(nr["mda"], _expected_limits(key, m)[1], 1e-9))
        nb = before["cases"][f"nai_cs_{m}"]["nuclides"][0]
        vals.append(f"{m}: Cs-137 {nb['decision_threshold']:.4g} / {nb['mda']:.4g} -> {nr['decision_threshold']:.4g} / "
                    f"{nr['mda']:.4g} Bq")
        c = res["cases"][f"nai_ba_mean_{m}"]
        nr, nb = c["nuclides"][0], before["cases"][f"nai_ba_mean_{m}"]["nuclides"][0]
        rc = nr.get("recombined")
        ok &= (rc is not None and _close(nr["decision_threshold"], rc[0], 1e-9) and _close(nr["mda"], rc[1], 1e-9)
               and sum(_quad(l) for l in c["lines"]) >= 2)
        vals.append(f"{m}: Ba-133 mean {nb['decision_threshold']:.4g} / {nb['mda']:.4g} -> {nr['decision_threshold']:.4g} / "
                    f"{nr['mda']:.4g} Bq")
    out["RD.C2"] = {"value": "; ".join(vals), "pass": ok}
    bad, changed = [], []
    for name, c in res["cases"].items():
        b = before["cases"][name]
        for ln, lb in zip(c["lines"], b["lines"]):
            keys = [k for k in lb if not (_quad(lb) and k in LIMITS)]
            if not _same({k: ln[k] for k in keys}, {k: lb[k] for k in keys}):
                bad.append(f"{name} {ln['energy']:.1f} keV")
        quad_nucl = any(_quad(l) for l in b["lines"])
        for nr, nb in zip(c["nuclides"], b["nuclides"]):
            skip = ("decision_threshold", "mda", "recombined") if quad_nucl else ()
            if name.startswith("nai_ba_mean") and _covariance_engine(res["engine"]):
                skip += ("primary_u",)          # engine 1.34.0: cross terms of shared window channels
                changed.append(f"{name} {nr['name']} primary_u {nb['primary_u']:.5g} -> {nr['primary_u']:.5g} Bq")
            keys = [k for k in nb if k not in skip]
            if not _same({k: nr[k] for k in keys}, {k: nb[k] for k in keys}):
                bad.append(f"{name} {nr['name']}")
        if not _same(c["notes"], b["notes"]):
            bad.append(f"{name} notes")
    txt = "; ".join(bad) or "every other number, decision and note identical to before"
    if changed:
        txt += " (excepted, the intended change of round8_line_covariance_protocol.md: " + "; ".join(changed) + ")"
    out["RD.C3"] = {"value": txt, "pass": not bad}
    rows = [r for r in res["mc"] if r[0] == "quadratic" and r[1] == "window"]
    rows_b = [r for r in before["mc"] if r[0] == "quadratic" and r[1] == "window"]
    p = np.array([r[2] for r in rows], dtype=float)
    sd = float(p.std(ddof=1))
    k = act.K_DEFAULT

    def ratio(rr, i):
        return float(np.mean([r[i] for r in rr])) / (k * sd)
    same = len(rows) == len(rows_b) and all(_close(r[4], b[4]) and r[2] == b[2] for r, b in zip(rows, rows_b))
    eq = all(_close(r[3], r[4]) for r in rows)
    out["RD.C4"] = {"value": f"{len(rows)} of {N_MC} quadratic; reported threshold / (k sd) {ratio(rows_b, 3):.3f} -> "
                             f"{ratio(rows, 3):.3f}; fraction above the reported threshold "
                             f"{np.mean(p > np.array([r[3] for r in rows_b])):.4f} -> {np.mean(p > np.array([r[3] for r in rows])):.4f}",
                    "pass": bool(rows) and eq and same}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--collect", action="store_true", help="write the observations only (the 'before' values)")
    ap.add_argument("--rerun", action="store_true",
                    help=f"write the results to {RERUN}, not the committed folder")
    a = ap.parse_args(argv)
    out = RERUN if a.rerun else OUT
    res = json.loads(json.dumps(collect(), default=float))
    out.mkdir(parents=True, exist_ok=True)
    if a.collect:
        BEFORE_JSON.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {BEFORE_JSON}")
        return 0
    before = json.loads(BEFORE_JSON.read_text(encoding="utf-8"))
    crit = criteria(res, before)
    (out / "round7_quad_limits.json").write_text(json.dumps({"results": res, "criteria": crit}, indent=1,
                                                           ensure_ascii=False), encoding="utf-8")
    lines = ["# Round-7 limits of the quadratic window (Gemini H3)", "", f"engine {res['engine']}", "",
             "| ID | value | result |", "|---|---|---|"]
    lines += [f"| {k} | {v['value']} | {'PASS' if v['pass'] else 'FAIL'} |" for k, v in crit.items()]
    (out / "round7_quad_limits.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(v["pass"] for v in crit.values())
    print("\n".join(lines))
    print(f"{n} PASS / {len(crit) - n} FAIL")
    return 0 if n == len(crit) else 1


if __name__ == "__main__":
    sys.exit(main())

"""Round-7 review, Codex H2 and Gemini M1: limits of the weighted mean of the lines
(docs/baseline/round7_combined_protocol.md).

    python -m spectramaster.validation.round7_combined [--collect] [--rerun]

Synthetic data only.  ``--collect`` writes the observations only, to
``docs/baseline/after_R7B/round7_combined_before.json`` (the "before" values); without it the
criteria are evaluated against that file.
``--rerun`` writes the results to RERUN (in the temporary folder) instead of the committed folder,
which a re-run on a later engine then leaves as committed (round8_rerun_protocol.md).
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
from spectramaster.validation import round5_combined as r5
from spectramaster.validation import round6_combined as r6

OUT = r5.OUT.parent / "after_R7B"
RERUN = Path(tempfile.gettempdir()) / "spectramaster_round7_combined"     # --rerun: results here, OUT left as committed
BEFORE_JSON = OUT / "round7_combined_before.json"
CO, BA = r5.CO, r5.BA
REL = 1e-9
SAMPLE = [(CO[0], 16000.0, 170.0), (CO[1], 15500.0, 170.0)]
UC, BUC = 0.10, 0.10
BUMP = 0.9                          # RB.C4: each line's Gaussian, in units of its L_C counts
NOTE = "weighted mean of the window results above its decision threshold"

# RB.C1 / RB.C2: (name, mda method, blank areas (None: no blank peak at that line), rate uncertainty)
ONE_BLANK = (
    ("blank_1173_iso", "iso11929", [10000.0, None], 0.0),
    ("blank_1173_rate_iso", "iso11929", [10000.0, None], 0.03),
    ("blank_1332_rate_iso", "iso11929", [None, 10000.0], 0.03),
    ("blank_1173_rate_currie", "currie", [10000.0, None], 0.03),
    ("blank_1332_currie", "currie", [None, 10000.0], 0.0),
)
# RB.C3: (name, nuclide, mda method)
UNDETECTED = (("co60_iso", "Co-60", "iso11929"), ("co60_currie", "Co-60", "currie"),
              ("ba133_iso", "Ba-133", "iso11929"), ("ba133_currie", "Ba-133", "currie"))


ROW = ("threshold", "mda", "activity", "u", "primary", "primary_u", "detected", "note", "used")


def _row(r) -> dict:
    return {"threshold": r.decision_threshold, "mda": r.mda, "activity": r.activity, "u": r.u,
            "primary": r.primary, "primary_u": r.primary_u, "detected": r.detected, "note": r.note,
            "used": list(r.used_energies)}


def _one_blank(mda, blank_areas, ur):
    curve = r5._flat_curve()
    o = act.ActivityOptions(nuclides=["Co-60"], method="mean", mda_method=mda, intensity_rel_unc=0.01,
                            attenuation_rel_unc=0.02,
                            reference_peak={"energy": r6.REF_E, "rate": 10000.0 / r5.LIVE, "rate_rel_unc": ur})
    bpk = [r5._peak(e, a, math.sqrt(a + 800.0)) for (e, _a, _u), a in zip(SAMPLE, blank_areas) if a is not None]
    bl = act.compute_activities(r5._spectrum("blank"), curve, o, peaks=bpk + [r6._ref_peak(BUC)])
    q = act.compute_activities(r5._spectrum("sample"), curve, o, peaks=[r5._peak(*l) for l in SAMPLE]
                               + [r6._ref_peak(UC)], blank=bl)
    return q.nuclides[0], o


def full_covariance(res, o, mda, ur) -> dict:
    """Threshold and limit of the weighted mean from the full covariance: each line's own variance
    plus, for every pair, the reference peak cross terms (g0_i + y dg_i).(g0_j + y dg_j), with
    g0 = ab (u_c, u_b, 0) (the blank analysed with the same rate) and dg = (u_c, 0, u_r)."""
    cand = [l for l in res.lines if l.energy in res.used_energies]
    lam = np.array(r5._weights(cand, o))
    ka, kb = o.k_alpha, o.k_beta
    ab = np.array([l.blank_activity or 0.0 for l in cand])
    s0 = np.array([l.decision_threshold / ka for l in cand])
    g = np.array([UC, BUC, 0.0])
    dg = np.array([UC, 0.0, ur])
    cov0 = np.outer(ab, ab) * float(g @ g)
    np.fill_diagonal(cov0, s0 ** 2)
    s0sq = float(lam @ cov0 @ lam)
    ys = ka * math.sqrt(s0sq)
    iso = mda == "iso11929"
    cross = np.add.outer(ab, ab) * float(g @ dg) if iso else np.zeros((len(cand), len(cand)))
    np.fill_diagonal(cross, [r5._slope(l, r6._rel(l, o, mda, UC, ur), ka, kb) for l in cand])
    slope = float(lam @ cross @ lam)
    if iso:
        eff = float(sum(x * l.eff_rel_unc for x, l in zip(lam, cand)))
        ref = math.hypot(UC, ur) * float(lam.sum())
        intens = math.hypot(o.intensity_rel_unc, math.sqrt(sum((x * l.int_rel_unc) ** 2 for x, l in zip(lam, cand))))
        big_r = math.sqrt(eff ** 2 + intens ** 2 + o.attenuation_rel_unc ** 2 + ref ** 2)
    else:
        big_r = 0.0
    return {"threshold": ys, "limit": _root(ys, kb, slope, s0sq, big_r)}


def _root(ys, kb, slope, s0sq, big_r) -> float:
    def f(y):
        return y - ys - kb * math.sqrt(max(slope * y + s0sq + (y * big_r) ** 2, 0.0))
    lo, hi = ys, 2.0 * ys + 10.0
    while f(hi) < 0:
        hi *= 2.0
    for _ in range(200):          # bisection, independent of the engine's closed form
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return 0.5 * (lo + hi)


def _undetected(nuclide, mda, method="mean", counts=None):
    curve = r5._flat_curve()
    o = act.ActivityOptions(nuclides=[nuclide], method=method, mda_method=mda, intensity_rel_unc=0.01,
                            attenuation_rel_unc=0.02)
    sp = r5._spectrum("sample")
    if counts is not None:
        sp.counts = list(counts)
    q = act.compute_activities(sp, curve, o, peaks=[])
    return q.nuclides[0], o


def weighted_mean_limits(res, o, mda) -> dict:
    """Independent threshold and limit of the weighted mean of the usable window results, with the
    weights of the primary result (counting + intensity of each line's window result)."""
    use = [l for l in res.lines if l.mda > 0 and l.primary is not None and l.primary_method == "window"]
    ui = o.intensity_rel_unc
    v = [l.primary_u_count ** 2 + (l.primary * ui) ** 2 + (l.primary * l.int_rel_unc) ** 2 for l in use]
    lam = np.array([1.0 / x for x in v])
    lam /= lam.sum()
    ka, kb = o.k_alpha, o.k_beta
    s0sq = float(sum((x * l.decision_threshold / ka) ** 2 for x, l in zip(lam, use)))
    slope = float(sum(x * x * r5._slope(l, r5._rel(l, o, mda), ka, kb) for x, l in zip(lam, use)))
    if mda == "iso11929":
        eff = float(sum(x * l.eff_rel_unc for x, l in zip(lam, use)))
        intens = math.hypot(ui, math.sqrt(sum((x * l.int_rel_unc) ** 2 for x, l in zip(lam, use))))
        big_r = math.sqrt(eff ** 2 + intens ** 2 + o.attenuation_rel_unc ** 2)
    else:
        big_r = 0.0
    ys = ka * math.sqrt(s0sq)
    return {"n": len(use), "threshold": ys, "limit": _root(ys, kb, slope, s0sq, big_r)}


def _bumped_counts():
    """Flat spectrum plus, at each Co-60 line, a Gaussian of BUMP x that line's L_C counts."""
    res0, _o = _undetected("Co-60", "iso11929")
    sp = r5._spectrum("sample")
    y = np.array(sp.counts, dtype=float)
    ch = np.arange(len(y), dtype=float)
    from scipy.special import ndtr
    for l in res0.lines:
        fw = math.sqrt(0.75 + 0.00185 * l.energy) / r5.GAIN
        s = fw / (2.0 * math.sqrt(2.0 * math.log(2.0)))
        c = l.energy / r5.GAIN
        y += BUMP * l.lc_counts * (ndtr((ch + 0.5 - c) / s) - ndtr((ch - 0.5 - c) / s))
    return y


def collect() -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    out = {"engine": ENGINE_VERSION, "one_blank": {}, "undetected": {}, "controls": {}}
    for name, mda, blank, ur in ONE_BLANK:
        r, o = _one_blank(mda, blank, ur)
        out["one_blank"][name] = {**_row(r), "independent": full_covariance(r, o, mda, ur),
                                  "lines": [[l.energy, l.blank_activity, l.ref_g0, l.ref_dg] for l in r.lines]}
    for name, nuc, mda in UNDETECTED:
        r, o = _undetected(nuc, mda)
        k, _o = _undetected(nuc, mda, method="key")
        out["undetected"][name] = {**_row(r), "independent": weighted_mean_limits(r, o, mda), "key": _row(k)}
    r, o = _undetected("Co-60", "iso11929", counts=_bumped_counts())
    out["bump"] = {**_row(r), "independent": weighted_mean_limits(r, o, "iso11929"),
                   "lines": [[l.energy, l.primary, l.decision_threshold, l.detected] for l in r.lines]}
    for name, nuc, lines, mda, blank in r5.CASES:
        out["controls"]["r5_" + name] = _row(r5._run(nuc, lines, mda, blank)[0])
    for name, mda, lines, blank, uc, buc, ur in r6.CASES:
        out["controls"]["r6_" + name] = _row(r6._run(mda, lines, blank, uc, buc, ur)[0])
    single, _o = _undetected("Cs-137", "iso11929")
    out["controls"]["single_line"] = _row(single)
    return out


def _close(a, b) -> bool:
    return a is not None and b is not None and math.isclose(a, b, rel_tol=REL, abs_tol=0.0)


def criteria(res: dict, before: dict) -> dict:
    out = {}
    bad1, bad2 = [], []
    for name, c in res["one_blank"].items():
        if "currie" in name:
            # the results (_row); `lines` holds the ref_g0 / ref_dg fields the change sets by design
            if json.dumps({k: c[k] for k in ROW}, sort_keys=True)                     != json.dumps({k: before["one_blank"][name][k] for k in ROW}, sort_keys=True):
                bad2.append(name)
        elif not (_close(c["threshold"], c["independent"]["threshold"]) and _close(c["mda"], c["independent"]["limit"])):
            bad1.append(f"{name}: {c['threshold']:.6g} / {c['mda']:.6g} vs {c['independent']['threshold']:.6g} / "
                        f"{c['independent']['limit']:.6g} Bq")
    out["RB.C1"] = {"value": "; ".join(bad1) or "ISO 11929 threshold and limit equal the full-covariance computation",
                    "pass": not bad1}
    out["RB.C2"] = {"value": "; ".join(bad2) or "Currie cases identical to before", "pass": not bad2}
    bad3 = []
    for name, c in res["undetected"].items():
        b, ind = before["undetected"][name], c["independent"]
        if ind["n"] < 2 or not (_close(c["threshold"], ind["threshold"]) and _close(c["mda"], ind["limit"])):
            bad3.append(f"{name}: {c['threshold']:.6g} / {c['mda']:.6g} vs {ind['threshold']:.6g} / "
                        f"{ind['limit']:.6g} Bq ({ind['n']} lines)")
        if [c["primary"], c["primary_u"], c["detected"]] != [b["primary"], b["primary_u"], b["detected"]]:
            bad3.append(f"{name}: primary changed")
    out["RB.C3"] = {"value": "; ".join(bad3) or "limits of the weighted mean of the window results, primary unchanged",
                    "pass": not bad3}
    bp = res["bump"]
    above = bp["primary"] is not None and bp["primary"] > bp["threshold"]
    noted = NOTE in (bp["note"] or "")
    ok4 = not bp["detected"] and noted == above and not any(d for *_x, d in bp["lines"])
    out["RB.C4"] = {"value": f"primary {bp['primary']:.4g} Bq, threshold {bp['threshold']:.4g} Bq, detected "
                             f"{bp['detected']}, note {'present' if noted else 'absent'}", "pass": ok4 and above}
    bad5 = [k for k, c in res["controls"].items() if json.dumps(c, sort_keys=True)
            != json.dumps(before["controls"][k], sort_keys=True)]
    bad5 += [f"{n} key" for n, c in res["undetected"].items()
             if json.dumps(c["key"], sort_keys=True) != json.dumps(before["undetected"][n]["key"], sort_keys=True)]
    out["RB.C5"] = {"value": "; ".join(bad5) or "detected cases, key-line runs and the single line identical to before",
                    "pass": not bad5}
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
    (out / "round7_combined.json").write_text(json.dumps({"results": res, "criteria": crit}, indent=1,
                                                         ensure_ascii=False), encoding="utf-8")
    lines = ["# Round-7 limits of the weighted mean (Codex H2, Gemini M1)", "", f"engine {res['engine']}", "",
             "| ID | value | result |", "|---|---|---|"]
    lines += [f"| {k} | {v['value']} | {'PASS' if v['pass'] else 'FAIL'} |" for k, v in crit.items()]
    (out / "round7_combined.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(v["pass"] for v in crit.values())
    print("\n".join(lines))
    print(f"{n} PASS / {len(crit) - n} FAIL")
    return 0 if n == len(crit) else 1


if __name__ == "__main__":
    sys.exit(main())

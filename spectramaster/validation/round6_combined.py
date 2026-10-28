"""Round-6 review, Codex H1: limits of the line combination with a reagent blank and a reference
peak correction (docs/baseline/round6_combined_protocol.md).

    python -m spectramaster.validation.round6_combined [--collect]

Synthetic data only.  ``--collect`` writes the observations only, to
``docs/baseline/after_R6D/round6_combined_before.json`` (the "before" values); without it the
criteria are evaluated against that file.
"""
from __future__ import annotations

import argparse
import json
import math
import sys

import numpy as np

from spectramaster.analysis import activity as act
from spectramaster.validation import round5_combined as r5

OUT = r5.OUT.parent / "after_R6D"
BEFORE_JSON = OUT / "round6_combined_before.json"
REF_E = 1460.82                       # reference peak (any line the samples do not carry)
MC_DRAWS, MC_SEED = r5.MC_DRAWS, r5.MC_SEED
CO = r5.CO

# (name, mda method, sample line areas, blank areas, reference peak relative counting uncertainty of
#  the sample and of the blank, relative uncertainty of the expected rate)
CASES = (
    ("co60_ref_blank_iso", "iso11929", [(CO[0], 16000.0, 170.0), (CO[1], 15500.0, 170.0)],
     [10000.0, 10000.0], 0.10, 0.10, 0.0),
    ("co60_ref_blank_currie", "currie", [(CO[0], 16000.0, 170.0), (CO[1], 15500.0, 170.0)],
     [10000.0, 10000.0], 0.10, 0.10, 0.0),
    ("co60_ref_blank_rate_iso", "iso11929", [(CO[0], 13000.0, 160.0), (CO[1], 12000.0, 160.0)],
     [10000.0, 10000.0], 0.05, 0.08, 0.03),
    ("co60_ref_only_iso", "iso11929", [(CO[0], 3000.0, 60.0), (CO[1], 900.0, 450.0)], None, 0.10, 0.0, 0.0),
)


def _ref_peak(u_rel):
    area = 10000.0
    return r5._peak(REF_E, area, area * u_rel)


def _run(mda, lines, blank_areas, uc, buc, ur, method="mean"):
    curve = r5._flat_curve()
    rate = 10000.0 / r5.LIVE
    o = act.ActivityOptions(nuclides=["Co-60"], method=method, mda_method=mda, intensity_rel_unc=0.01,
                            attenuation_rel_unc=0.02,
                            reference_peak={"energy": REF_E, "rate": rate, "rate_rel_unc": ur})
    bl = None
    if blank_areas is not None:
        bpk = [r5._peak(e, a, math.sqrt(a + 800.0)) for (e, _a, _u), a in zip(lines, blank_areas)]
        bl = act.compute_activities(r5._spectrum("blank"), curve, o, peaks=bpk + [_ref_peak(buc)])
    q = act.compute_activities(r5._spectrum("sample"), curve, o, peaks=[r5._peak(*l) for l in lines]
                               + [_ref_peak(uc)], blank=bl)
    return q.nuclides[0], o


def independent(res, o, mda, uc, buc, ur):
    """Threshold and limit of the weighted mean from the full covariance of the line results:
    each line's own variance (its fields, as round5_combined) plus the covariance the shared
    reference peak corrections give two lines (the inputs uc, buc, ur and each line's blank)."""
    cand = [l for l in res.lines if l.energy in res.used_energies]
    lam = np.array(r5._weights(cand, o))
    ka, kb = o.k_alpha, o.k_beta
    bur = ur if res.lines and cand[0].blank_activity is not None else 0.0   # blank analysed with the same rate
    ab = np.array([l.blank_activity or 0.0 for l in cand])
    s0 = np.array([l.decision_threshold / ka for l in cand])
    g = np.array([uc, buc, ur - bur])                      # per Bq of blank activity, at zero net activity
    cov0 = np.outer(ab, ab) * float(g @ g)
    np.fill_diagonal(cov0, s0 ** 2)
    S0sq = float(lam @ cov0 @ lam)
    ys = ka * math.sqrt(S0sq)
    slope_diag = np.array([r5._slope(l, _rel(l, o, mda, uc, ur), ka, kb) for l in cand])
    iso = mda == "iso11929"
    cross = (np.add.outer(ab, ab) * (uc * uc + ur * (ur - bur))) if iso else np.zeros((len(cand), len(cand)))
    np.fill_diagonal(cross, slope_diag)
    slope = float(lam @ cross @ lam)
    if iso:
        eff = float(sum(x * l.eff_rel_unc for x, l in zip(lam, cand)))
        coi = float(sum(x * l.coi_rel_unc for x, l in zip(lam, cand)))
        ref = math.hypot(uc, ur) * float(lam.sum())
        intens = math.hypot(o.intensity_rel_unc, math.sqrt(sum((x * l.int_rel_unc) ** 2 for x, l in zip(lam, cand))))
        R = math.sqrt(eff ** 2 + intens ** 2 + o.attenuation_rel_unc ** 2 + coi ** 2 + ref ** 2)
    else:
        R = 0.0

    def f(y):
        return y - ys - kb * math.sqrt(slope * y + S0sq + (y * R) ** 2)
    lo, hi = ys, 2.0 * ys + 10.0
    while f(hi) < 0:
        hi *= 2.0
    for _ in range(200):          # bisection, independent of the engine's closed form
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return {"weights": lam.tolist(), "s0": s0.tolist(), "ab": ab.tolist(), "g": g.tolist(), "threshold": ys,
            "limit": 0.5 * (lo + hi)}


def _rel(line, o, mda, uc, ur):
    """Relative uncertainty of the line's calibration factor in its own limit (incl. the reference peak)."""
    if mda != "iso11929":
        return 0.0
    return math.sqrt(r5._rel(line, o, mda) ** 2 + uc * uc + ur * ur)


def false_positive_rate(ind, threshold):
    """Fraction of zero-activity weighted means above the threshold: each line's own Gaussian
    counting part plus the shared reference peak corrections (one draw each per measurement)."""
    rng = np.random.default_rng(MC_SEED)
    lam, s0, ab, g = (np.array(ind[k]) for k in ("weights", "s0", "ab", "g"))
    own = np.sqrt(np.maximum(s0 ** 2 - (ab ** 2) * float(g @ g), 0.0))
    shared = rng.normal(size=(MC_DRAWS, 3)) @ g            # uc z_s - buc z_b + (ur - bur) z_r, per Bq of blank
    y = sum(x * (rng.normal(0.0, s, MC_DRAWS) + a * shared) for x, s, a in zip(lam, own, ab))
    return float(np.mean(y > threshold))


def measure():
    out = {}
    for name, mda, lines, blank, uc, buc, ur in CASES:
        res, o = _run(mda, lines, blank, uc, buc, ur)
        ind = independent(res, o, mda, uc, buc, ur)
        out[name] = {"activity": res.activity, "u": res.u, "used": res.used_energies, "detected": res.detected,
                     "threshold": res.decision_threshold, "mda": res.mda,
                     "line_limits": [[l.decision_threshold, l.mda] for l in res.lines if l.energy in res.used_energies],
                     "ind_threshold": ind["threshold"], "ind_limit": ind["limit"], "weights": ind["weights"],
                     "fpr_engine": false_positive_rate(ind, res.decision_threshold),
                     "fpr_ind": false_positive_rate(ind, ind["threshold"])}
    # controls: the round-5 cases (no reference peak) and one line
    out["round5"] = {k: {kk: v[kk] for kk in ("activity", "u", "threshold", "mda", "used", "budget")}
                     for k, v in r5.measure().items() if not k.startswith("key_")}
    for mda in ("iso11929", "currie"):
        res, _o = _run(mda, *CASES[0][2:4], *CASES[0][4:], method="key")
        out[f"key_{mda}"] = {"threshold": res.decision_threshold, "mda": res.mda, "activity": res.activity, "u": res.u}
    return out


def collect():
    from spectramaster.lab.session import ENGINE_VERSION
    return {"engine": ENGINE_VERSION, "measured": measure()}


def criteria(m, b):
    alpha = 1.0 - 0.5 * (1.0 + math.erf(act.K_DEFAULT / math.sqrt(2.0)))
    names = [n for n, *_ in CASES]

    def rel(x, y):
        return abs(x - y) / abs(y)
    c = {}
    c["RD.C1"] = (all(rel(m[n]["threshold"], m[n]["ind_threshold"]) <= 1e-9 for n in names),
                  "; ".join(f"{n}: {m[n]['threshold']:.6g} / {m[n]['ind_threshold']:.6g}" for n in names))
    c["RD.C2"] = (all(rel(m[n]["mda"], m[n]["ind_limit"]) <= 1e-9 for n in names),
                  "; ".join(f"{n}: {m[n]['mda']:.6g} / {m[n]['ind_limit']:.6g}" for n in names))
    c["RD.C3"] = (all(abs(m[n]["fpr_engine"] - alpha) <= 0.002 for n in names),
                  "; ".join(f"{n}: {m[n]['fpr_engine']:.5f} (before {b[n]['fpr_engine']:.5f})" for n in names))
    keys = ("activity", "u", "used", "detected")
    c["RD.C4"] = (all(all(m[n][k] == b[n][k] for k in keys) and m[n]["line_limits"] == b[n]["line_limits"]
                      for n in names), "activity, uncertainty, lines used, detection and each line's limits as before")
    same5 = m["round5"] == b["round5"]
    same_key = all(m[f"key_{x}"] == b[f"key_{x}"] for x in ("iso11929", "currie"))
    c["RD.C5"] = (same5 and same_key, f"round-5 cases identical: {same5}; one line (key): {same_key}")
    return c, alpha


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true", help="write the before values (fixed file)")
    a = ap.parse_args(argv)
    res = collect()
    OUT.mkdir(parents=True, exist_ok=True)
    res = json.loads(json.dumps(res, default=str))
    if a.collect:
        BEFORE_JSON.write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
        return 0
    b = json.loads(BEFORE_JSON.read_text(encoding="utf-8"))["measured"]
    c, alpha = criteria(res["measured"], b)
    (OUT / "round6_combined.json").write_text(json.dumps({"result": res, "criteria": c, "alpha": alpha}, indent=1),
                                              encoding="utf-8", newline="\n")
    lines = ["# Round-6 review, H1: limits of the line combination with a blank and a reference peak", "",
             "Protocol: `docs/baseline/round6_combined_protocol.md`. Synthetic data only.", "",
             "| ID | result | value |", "|---|---|---|"]
    lines += [f"| {k} | {'PASS' if ok else 'FAIL'} | {v} |" for k, (ok, v) in c.items()]
    (OUT / "round6_combined.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(", ".join(f"{k}:{'PASS' if ok else 'FAIL'}" for k, (ok, _v) in c.items()))
    return 0 if all(ok for ok, _v in c.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

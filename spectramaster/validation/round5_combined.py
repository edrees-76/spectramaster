"""Round-5 review, H1: decision threshold and detection limit of the line combination
(docs/baseline/round5_combined_protocol.md).

    python -m spectramaster.validation.round5_combined

Synthetic data only.  Writes ``round5_combined.json`` and ``round5_combined.md`` to
docs/baseline/after_R5C.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from spectramaster.analysis import Peak
from spectramaster.analysis import activity as act
from spectramaster.analysis.efficiency import fit_efficiency, manual_point
from spectramaster.model import Spectrum

OUT = Path(__file__).resolve().parents[2] / "docs" / "baseline" / "after_R5C"
GAIN, NCH, LIVE = 0.25, 12000, 20000.0
START = datetime(2024, 3, 1, 10, 0, 0)
CO = (1173.228, 1332.492)
BA = (356.0129, 302.8508, 383.8485)
MC_DRAWS, MC_SEED = 1_000_000, 20261028
# engine 1.22.0 (96cfb90), before the change: the protocol's reference values
BEFORE = {'co60_iso': {'activity': 14.793885286841443,
              'u': 0.4656067511725265,
              'used': [1173.228, 1332.492],
              'budget': {'counting': 2.014204289091936,
                         'efficiency': 0.9206174652604079,
                         'intensity': 1.000445289134919,
                         'attenuation': 2.0},
              'threshold': 0.2175986732656645,
              'mda': 0.6252427757949661,
              'detected': True},
 'co60_currie': {'activity': 14.793885286841443,
                 'u': 0.4656067511725265,
                 'used': [1173.228, 1332.492],
                 'budget': {'counting': 2.014204289091936,
                            'efficiency': 0.9206174652604079,
                            'intensity': 1.000445289134919,
                            'attenuation': 2.0},
                 'threshold': 0.21759867326566448,
                 'mda': 0.6242533480071402,
                 'detected': True},
 'ba133_iso_blank': {'activity': 37.041354149434746,
                     'u': 1.1259053397634122,
                     'used': [356.013, 302.851, 383.849],
                     'budget': {'counting': 1.887943219825391,
                                'efficiency': 0.7636972625279791,
                                'intensity': 1.0447702936846897,
                                'attenuation': 2.0},
                     'threshold': 0.5858828757082608,
                     'mda': 1.268805446955539,
                     'detected': True},
 'key_iso11929': {'threshold': 0.30533664258545584,
                  'mda': 0.6252427757949661,
                  'activity': 15.023159790190412,
                  'u': 0.47144842993189007},
 'key_currie': {'threshold': 0.3053366425854558,
                'mda': 0.6242533480071402,
                'activity': 15.023159790190412,
                'u': 0.47144842993189007}}


def _spectrum(sid: str, level: float = 40.0) -> Spectrum:
    return Spectrum(counts=[level] * NCH, live_time=LIVE, real_time=LIVE, start_time=START,
                    energy_coeffs=[0.0, GAIN], sample_id=sid)


def _peak(e: float, area: float, unc: float) -> Peak:
    fw = math.sqrt(0.75 + 0.00185 * e)
    return Peak(centroid=e / GAIN, energy=e, fwhm=fw / GAIN, fwhm_kev=fw, net_area=area, net_area_unc=unc,
                gross_area=area + 400.0, background=400.0, left=int(e / GAIN - 2 * fw / GAIN),
                right=int(e / GAIN + 2 * fw / GAIN), significance=area / unc)


def _flat_curve():
    return fit_efficiency([manual_point(e, 0.01, 2.0) for e in (50, 100, 200, 500, 1000, 2000, 3000)],
                          "loglog", order=1)


# (name, nuclide, [(energy, area, area unc)], mda method, blank areas or None)
CASES = (
    ("co60_iso", "Co-60", [(CO[0], 3000.0, 60.0), (CO[1], 900.0, 450.0)], "iso11929", None),
    ("co60_currie", "Co-60", [(CO[0], 3000.0, 60.0), (CO[1], 900.0, 450.0)], "currie", None),
    ("ba133_iso_blank", "Ba-133", [(BA[0], 5000.0, 80.0), (BA[1], 1500.0, 300.0), (BA[2], 600.0, 240.0)],
     "iso11929", [400.0, 150.0, 60.0]),
)


def _run(nuclide, lines, mda, blank_areas, method="mean"):
    curve = _flat_curve()
    o = act.ActivityOptions(nuclides=[nuclide], method=method, mda_method=mda, intensity_rel_unc=0.01,
                            attenuation_rel_unc=0.02)
    bl = None
    if blank_areas is not None:
        bpk = [_peak(e, a, math.sqrt(a + 800.0)) for (e, _a, _u), a in zip(lines, blank_areas)]
        bl = act.compute_activities(_spectrum("blank"), curve, o, peaks=bpk)
    q = act.compute_activities(_spectrum("sample"), curve, o, peaks=[_peak(*l) for l in lines], blank=bl)
    return q.nuclides[0], o


def _rel(line, o, mda):
    """Relative uncertainty of a line's calibration factor, as its detection limit uses it."""
    if mda != "iso11929":
        return 0.0
    return math.sqrt(line.eff_rel_unc ** 2 + o.intensity_rel_unc ** 2 + line.int_rel_unc ** 2
                     + o.attenuation_rel_unc ** 2 + line.coi_rel_unc ** 2)


def _slope(line, r, k_alpha, k_beta):
    """Variance term linear in the activity, solved back from the line's own limits:
    y# = y* + k_b sqrt(slope y# + s0^2 + y#^2 r^2)."""
    ys, yd = line.decision_threshold, line.mda
    s0 = ys / k_alpha
    return ((yd - ys) ** 2 / k_beta ** 2 - s0 ** 2 - (yd * r) ** 2) / yd


def _weights(cand, o):
    v = [l.u_count_bq ** 2 + (l.activity * o.intensity_rel_unc) ** 2 + (l.activity * l.int_rel_unc) ** 2
         for l in cand]
    w = [1.0 / x for x in v]
    return [x / sum(w) for x in w]


def independent(res, o, mda):
    """Decision threshold and detection limit of the weighted mean, from the line fields only."""
    cand = [l for l in res.lines if l.energy in res.used_energies]
    lam = _weights(cand, o)
    ka, kb = o.k_alpha, o.k_beta
    s0 = [l.decision_threshold / ka for l in cand]
    S0 = math.sqrt(sum((x * s) ** 2 for x, s in zip(lam, s0)))
    ys = ka * S0
    slope = sum(x * x * _slope(l, _rel(l, o, mda), ka, kb) for x, l in zip(lam, cand))
    if mda == "iso11929":
        eff = sum(x * l.eff_rel_unc for x, l in zip(lam, cand))
        coi = sum(x * l.coi_rel_unc for x, l in zip(lam, cand))
        intens = math.hypot(o.intensity_rel_unc, math.sqrt(sum((x * l.int_rel_unc) ** 2 for x, l in zip(lam, cand))))
        R = math.sqrt(eff ** 2 + intens ** 2 + o.attenuation_rel_unc ** 2 + coi ** 2)
    else:
        R = 0.0

    def f(y):
        return y - ys - kb * math.sqrt(slope * y + S0 ** 2 + (y * R) ** 2)
    lo, hi = ys, 2.0 * ys + 10.0
    while f(hi) < 0:
        hi *= 2.0
    for _ in range(200):          # bisection, independent of the engine's closed form
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return {"weights": lam, "s0": s0, "threshold": ys, "limit": 0.5 * (lo + hi), "slope": slope, "R": R}


def false_positive_rate(lam, s0, threshold):
    """Fraction of zero-activity weighted means above the threshold (Gaussian line estimators)."""
    rng = np.random.default_rng(MC_SEED)
    y = sum(x * rng.normal(0.0, s, MC_DRAWS) for x, s in zip(lam, s0))
    return float(np.mean(y > threshold))


def measure():
    out = {}
    for name, nuc, lines, mda, blank in CASES:
        res, o = _run(nuc, lines, mda, blank)
        ind = independent(res, o, mda)
        out[name] = {"activity": res.activity, "u": res.u, "budget": res.budget, "used": res.used_energies,
                     "detected": res.detected, "threshold": res.decision_threshold, "mda": res.mda,
                     "line_mda": [l.mda for l in res.lines if l.energy in res.used_energies],
                     "ind_threshold": ind["threshold"], "ind_limit": ind["limit"], "weights": ind["weights"],
                     "fpr_engine": false_positive_rate(ind["weights"], ind["s0"], res.decision_threshold),
                     "fpr_ind": false_positive_rate(ind["weights"], ind["s0"], ind["threshold"])}
    # one line ("key"): the combination is the line itself
    for mda in ("iso11929", "currie"):
        res, o = _run("Co-60", [(CO[0], 3000.0, 60.0), (CO[1], 900.0, 450.0)], mda, None, method="key")
        k = res.key_line
        one = act.combined_limits([k], [1.0], o) if hasattr(act, "combined_limits") else None
        out[f"key_{mda}"] = {"threshold": res.decision_threshold, "mda": res.mda, "activity": res.activity,
                             "u": res.u, "line_threshold": k.decision_threshold, "line_mda": k.mda,
                             "one_line": one}
    return out


def criteria(m):
    alpha = 1.0 - 0.5 * (1.0 + math.erf(act.K_DEFAULT / math.sqrt(2.0)))
    c = {}
    names = [n for n, *_ in CASES]

    def rel(a, b):
        return abs(a - b) / abs(b)
    c["RC.C1"] = all(rel(m[n]["threshold"], m[n]["ind_threshold"]) <= 1e-9 for n in names)
    c["RC.C2"] = all(rel(m[n]["mda"], m[n]["ind_limit"]) <= 1e-9 for n in names)
    c["RC.C3"] = all(abs(m[n]["fpr_engine"] - alpha) <= 0.002 for n in names)
    ok = True
    for n in names:
        b = BEFORE.get(n)
        if b is None:
            ok = False
            continue
        ok &= (m[n]["activity"] == b["activity"] and m[n]["u"] == b["u"] and m[n]["used"] == b["used"]
               and m[n]["budget"] == b["budget"])
    c["RC.C4"] = ok
    ok = True
    for mda in ("iso11929", "currie"):
        k, b = m[f"key_{mda}"], BEFORE.get(f"key_{mda}")
        one = k["one_line"]
        ok &= (b is not None and k["threshold"] == b["threshold"] and k["mda"] == b["mda"]
               and k["activity"] == b["activity"] and k["u"] == b["u"] and one is not None
               and rel(one[0], k["line_threshold"]) <= 1e-12 and rel(one[1], k["line_mda"]) <= 1e-12)
    c["RC.C5"] = ok
    return c, alpha


def main(argv=None) -> int:
    m = measure()
    if argv and "--before" in argv:
        print(json.dumps(m, indent=1, default=str))
        return 0
    c, alpha = criteria(m)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "round5_combined.json").write_text(json.dumps({"measured": m, "criteria": c, "alpha": alpha},
                                                         indent=1, default=str), encoding="utf-8")
    lines = ["# Round-5 review, H1: limits of the line combination", "",
             "Protocol: `docs/baseline/round5_combined_protocol.md`. Synthetic data only.", "",
             "| ID | result |", "|---|---|"]
    lines += [f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in c.items()]
    lines += ["", "| case | threshold | independent | limit | independent | min line limit | P(false positive) |",
              "|---|---|---|---|---|---|---|"]
    for n, *_ in CASES:
        x = m[n]
        lines.append(f"| {n} | {x['threshold']:.6g} | {x['ind_threshold']:.6g} | {x['mda']:.6g} | "
                     f"{x['ind_limit']:.6g} | {min(x['line_mda']):.6g} | {x['fpr_engine']:.5f} |")
    lines.append(f"\nalpha = {alpha:.5f}")
    (OUT / "round5_combined.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(", ".join(f"{k}:{'PASS' if v else 'FAIL'}" for k, v in c.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Round-8 review, Gemini M1: calibration points already corrected for true-coincidence summing on a
curve not marked corrected (docs/baseline/round8_coi_guard_protocol.md).

    python -m spectramaster.validation.round8_coi_guard [--collect] [--rerun]

Synthetic data and the bundled coincidence table only.  ``--collect`` writes the observations only,
to ``docs/baseline/after_R8C/round8_coi_guard_before.json`` (the "before" values); without it the
criteria are evaluated against that file.  ``--rerun`` writes the results to RERUN (in the
temporary folder) instead of ``after_R8C``, which a re-run then leaves as committed.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import numpy as np

from spectramaster.analysis import activity as act
from spectramaster.analysis import efficiency as ef
from spectramaster.validation import round5_tcs as r5
from spectramaster.validation import round6_tcs_state as r6

OUT = r6.OUT.parent / "after_R8C"
BEFORE_JSON = OUT / "round8_coi_guard_before.json"
RERUN = Path(tempfile.gettempdir()) / "spectramaster_round8_coi_guard"
REL = 1e-12
ENERGIES = [float(e) for e in np.geomspace(60.0, 1800.0, 20)]
# calibration points of nuclides without cascades in the coincidence table
EXTRA = (("Cd-109", 88.03), ("Hg-203", 279.2), ("Cr-51", 320.08), ("Sn-113", 391.7),
         ("Cs-137", 661.657), ("Mn-54", 834.85), ("K-40", 1460.8))
RAW_CASCADE = ("Co-60", 1173.228)        # a cascade point not corrected (mixed case)
EU121 = 121.78


def _point(curve, nuc, e):
    v = float(curve.efficiency(e))
    return ef.EfficiencyPoint(energy=e, efficiency=v, unc=0.02 * v, nuclide=nuc, u_count_rel=0.02)


def _curves() -> dict:
    """The curves of the cases: Eu-152 corrected for summing plus points without cascades; the
    Eu-152 points excluded and the curve refitted (not marked corrected), then included again
    without a refit (Gemini's sequence); the explicit refit of those points; controls."""
    raw_eu = ef.fit_efficiency(r5._cal_points(r5.EU, "Eu-152"), "loglog", order=2)
    free_eu = ef.summing_free_curve(raw_eu, r5._pt, 0.1)
    pts = list(free_eu.points) + [_point(free_eu, n, e) for n, e in EXTRA]
    off = ef.fit_efficiency([replace(p, use=False) if p.nuclide == "Eu-152" else p for p in pts], "loglog", order=2)
    reenabled = ef.fit_efficiency([replace(p, use=False) if p.nuclide == "Eu-152" else p for p in pts], "loglog",
                                  order=2)
    for p in reenabled.points:
        p.use = True
    refit = ef.fit_efficiency([replace(p, use=True) for p in off.points], "loglog", order=2)
    mixed = ef.fit_efficiency([replace(p, use=False) if p.nuclide == "Eu-152" else p for p in pts], "loglog",
                              order=2)
    mixed.points.append(_point(free_eu, *RAW_CASCADE))
    for p in mixed.points:
        p.use = True
    raw_mix = ef.fit_efficiency(r5._cal_points(r5.EU, "Eu-152") + [_point(raw_eu, n, e) for n, e in EXTRA],
                                "loglog", order=2)
    return {"reenabled": reenabled, "refit": refit, "mixed": mixed, "off": off, "raw": raw_mix,
            "corrected": free_eu}


def _state(c) -> dict:
    d = c.to_dict()
    d["eps"] = [float(c.efficiency(e)) for e in ENERGIES]
    d["eps121"] = float(c.efficiency(EU121))
    return d


def _free(c, declared=False) -> dict:
    try:
        f = ef.summing_free_curve(c, r5._pt, 0.1, declared_free=declared)
        return {"same_object": f is c, "state": _state(f), "error": None}
    except ValueError as exc:
        return {"same_object": False, "state": None, "error": str(exc)}


def _quant(c) -> dict:
    o = act.ActivityOptions(nuclides=["Cs-137"], method="mean", intensity_rel_unc=0.01,
                            tcs={"peak_to_total": list(r5.PT), "pt_rel_unc": 0.1})
    try:
        q = act.compute_activities(r5._spectrum(), c, o, peaks=[r5._peak(r6.CS_E, r6.CS_AREA)])
    except ValueError as exc:
        return {"error": str(exc)}
    r = q.nuclides[0]
    return {"activity": r.activity, "u": r.u, "mda": r.mda, "notes": list(q.notes), "error": None}


def collect() -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    cs = _curves()
    free = {name: _free(c) for name, c in cs.items()}
    free["reenabled_declared"] = _free(cs["reenabled"], declared=True)
    return {"engine": ENGINE_VERSION, "input": {name: _state(c) for name, c in cs.items()}, "free": free,
            "quant": {name: _quant(cs[name]) for name in ("reenabled", "refit", "raw", "corrected")}}


def _same(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _pt121(state) -> dict:
    return [p for p in state["points"] if p["nuclide"] == "Eu-152" and abs(p["energy"] - EU121) < 0.1][0]


def _no_date(x):
    """`x` without the curves' "date" (the time of the fit, not a result)."""
    if isinstance(x, dict):
        return {k: _no_date(v) for k, v in x.items() if k != "date"}
    if isinstance(x, list):
        return [_no_date(v) for v in x]
    return x


def criteria(res: dict, before: dict) -> dict:
    res, before = _no_date(res), _no_date(before)
    out = {}
    f, inp, ref = res["free"]["reenabled"], res["input"]["reenabled"], res["input"]["refit"]
    fb = before["free"]["reenabled"]
    good = (f["error"] is None and f["state"]["summing_corrected"]
            and _same(f["state"]["points"], inp["points"])
            and all(math.isclose(a, b, rel_tol=REL) for a, b in zip(f["state"]["eps"] + [f["state"]["eps121"]],
                                                                   ref["eps"] + [ref["eps121"]]))
            and _same(f["state"].get("tcs_partial", []), ref.get("tcs_partial", [])))
    p_in, p_b = _pt121(inp), _pt121(fb["state"])
    now = (f"{_pt121(f['state'])['efficiency']:.6g}, curve at {EU121} keV {f['state']['eps121']:.6g}, marked "
           f"corrected {f['state']['summing_corrected']}") if f["state"] else f"refused ({f['error']})"
    out["RC8.C1"] = {"value": f"Eu-152 {EU121} keV point: input {p_in['efficiency']:.6g}; before {p_b['efficiency']:.6g} "
                     f"({100 * (p_b['efficiency'] / p_in['efficiency'] - 1):+.2f} %), curve {fb['state']['eps121']:.6g}; "
                     f"now {now}; explicit refit curve {ref['eps121']:.6g}",
                     "pass": good}
    q, qr, qb = res["quant"]["reenabled"], res["quant"]["refit"], before["quant"]["reenabled"]
    good = (q["error"] is None and qr["error"] is None
            and all(math.isclose(q[k], qr[k], rel_tol=REL) for k in ("activity", "u", "mda"))
            and any("not corrected again" in n for n in q["notes"]))
    out["RC8.C2"] = {"value": f"Cs-137 activity with TCS: before {qb.get('activity', float('nan')):.6g} Bq, now "
                     f"{q.get('activity') or float('nan'):.6g} Bq, explicit refit {qr.get('activity') or float('nan'):.6g} Bq",
                     "pass": good}
    m = res["free"]["mixed"]
    mb = before["free"]["mixed"]
    out["RC8.C3"] = {"value": f"mixed corrected and uncorrected cascade points: before "
                     f"{'refused' if mb['error'] else 'corrected'}; now {m['error'] or 'not refused'}",
                     "pass": m["error"] is not None and "not" in m["error"]}
    bad = []
    for name in ("off", "raw", "corrected", "refit", "reenabled_declared"):
        if not _same(res["free"][name], before["free"][name]):
            bad.append(f"summing_free_curve {name}")
    for name in ("raw", "corrected", "refit"):
        if not _same(res["quant"][name], before["quant"][name]):
            bad.append(f"activity {name}")
    if not _same(res["input"], before["input"]):
        bad.append("input curves")
    out["RC8.C4"] = {"value": "; ".join(bad) or "uncorrected, corrected, excluded and declared-free curves, and their "
                     "activities, identical to before", "pass": not bad}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--collect", action="store_true", help="write the observations only (the 'before' values)")
    ap.add_argument("--rerun", action="store_true", help=f"write the results to {RERUN}, not after_R8C")
    a = ap.parse_args(argv)
    res = json.loads(json.dumps(collect(), default=float))
    if a.collect:
        OUT.mkdir(parents=True, exist_ok=True)
        BEFORE_JSON.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {BEFORE_JSON}")
        return 0
    before = json.loads(BEFORE_JSON.read_text(encoding="utf-8"))
    crit = criteria(res, before)
    out = RERUN if a.rerun else OUT
    out.mkdir(parents=True, exist_ok=True)
    (out / "round8_coi_guard.json").write_text(json.dumps({"results": res, "criteria": crit}, indent=1,
                                                         ensure_ascii=False), encoding="utf-8")
    lines = ["# Round-8 calibration points already corrected for summing (Gemini M1)",
             "", f"engine {res['engine']}", "", "| ID | value | result |", "|---|---|---|"]
    lines += [f"| {k} | {v['value']} | {'PASS' if v['pass'] else 'FAIL'} |" for k, v in crit.items()]
    (out / "round8_coi_guard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(v["pass"] for v in crit.values())
    print("\n".join(lines))
    print(f"{n} PASS / {len(crit) - n} FAIL")
    return 0 if n == len(crit) else 1


if __name__ == "__main__":
    sys.exit(main())

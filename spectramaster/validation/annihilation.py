"""511 keV annihilation summing in the true-coincidence correction: criteria AN.C1-AN.C4.

    python -m spectramaster.validation.annihilation [--out docs/baseline/after_AN1]

Protocol and limits: ``docs/baseline/annihilation_summing_protocol.md``.  AN.C5-AN.C9 are the IAEA
2002 re-run (``spectramaster.validation.iaea2002``), the benchmark and the test suite.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from ..analysis import coincidence as co
from ..lab.session import ENGINE_VERSION
from . import tcs_mc

C1_EXPECTED = [("Na-22", 1274.54, 0.90326 / 0.99941), ("Co-58", 810.76, 0.149 / 0.9945), ("Co-58", 863.95, 0.0),
               ("Zn-65", 1115.54, 0.0), ("Y-88", 1836.063, 0.0021 / 0.9924), ("Y-88", 898.042, 0.0),
               ("Cu-64", 1345.77, 0.0)]
C1_TOL = 0.002
C3_DECAYS = 20_000_000
C3_SEED = 20261021
C3_LIMITS = {0.005: 0.005, 0.02: 0.01, 0.05: None}          # e1000 -> limit of |d| - 3 sigma (None: report)
C3_LINES = [("Na-22", 1274.537), ("Co-58", 810.7593)]
C4_TOL = 1e-12


def table_ann(nuclide: str, energy: float) -> float:
    """P(beta+ | gamma) of the bundled table (emission-weighted over transitions), 0 when absent."""
    num = den = 0.0
    for t in co.transitions(nuclide):
        i = t.index(energy, co.LINE_TOL_KEV)
        if i is None:
            continue
        w = t.br * t.intensities[i]
        num += w * float(t.ann[i])
        den += w
    return num / den if den else 0.0


def c1() -> dict:
    rows = [{"nuclide": n, "energy": e, "expected": x, "table": table_ann(n, e)} for n, e, x in C1_EXPECTED]
    for r in rows:
        r["diff"] = r["table"] - r["expected"]
    worst = max(abs(r["diff"]) for r in rows)
    return {"id": "AN.C1", "rows": rows, "value": worst, "limit": f"<= {C1_TOL}", "pass": bool(worst <= C1_TOL)}


def c3(n_decays: int = C3_DECAYS) -> dict:
    rows = []
    for e1000, lim in C3_LIMITS.items():
        def ep(e, e1000=e1000):
            return tcs_mc.eps_peak(e, e1000)
        for nuc, energy in C3_LINES:
            mc = tcs_mc.simulate(nuc, e1000, n_decays, C3_SEED + int(1e4 * e1000) + int(energy))
            c_mc, s_mc = mc[float(energy)]
            c_f = co.coi(nuc, energy, ep, tcs_mc.peak_to_total)
            d = c_f.factor / c_mc - 1.0
            sigma = s_mc / c_mc
            rows.append({"e1000": e1000, "nuclide": nuc, "energy": energy, "coi": c_f.factor, "coi_mc": c_mc,
                         "annihilation": c_f.annihilation, "d": d, "sigma": sigma, "excess": abs(d) - 3 * sigma,
                         "limit": lim, "pass": None if lim is None else bool(abs(d) - 3 * sigma <= lim)})
    judged = [r for r in rows if r["pass"] is not None]
    return {"id": "AN.C3", "rows": rows, "pass": all(r["pass"] for r in judged),
            "value": max(r["excess"] for r in judged), "limit": "far <= 0.005, mid <= 0.01; close reported"}


def c4() -> dict:
    ep_const, pt_const = 0.03, 0.25
    c = co.coi("Na-22", 1274.537, lambda e: np.full(np.shape(e), ep_const), lambda e: np.full(np.shape(e), pt_const))
    expected = 1.0 - table_ann("Na-22", 1274.537) * 2.0 * ep_const / pt_const
    diff = abs(c.factor - expected)
    return {"id": "AN.C4", "coi": c.factor, "expected": expected, "value": diff, "limit": f"<= {C4_TOL}",
            "pass": bool(diff <= C4_TOL)}


def run(n_decays: int = C3_DECAYS) -> dict:
    return {"engine": ENGINE_VERSION, "C1": c1(), "C3": c3(n_decays), "C4": c4()}


def report(r: dict) -> str:
    out = ["# Annihilation summing: AN.C1-AN.C4", "", f"Engine {r['engine']}. Protocol: "
           "`docs/baseline/annihilation_summing_protocol.md`.", "",
           "| ID | Value | Limit | Result |", "|---|---|---|---|"]
    for k in ("C1", "C3", "C4"):
        c = r[k]
        out.append(f"| {c['id']} | {c['value']:.3g} | {c['limit']} | {'PASS' if c['pass'] else 'FAIL'} |")
    out += ["", "## AN.C1: P(beta+ | gamma) of the rebuilt table", "",
            "| Nuclide | keV | expected | table | difference |", "|---|---|---|---|---|"]
    for x in r["C1"]["rows"]:
        out.append(f"| {x['nuclide']} | {x['energy']} | {x['expected']:.5f} | {x['table']:.5f} | {x['diff']:+.5f} |")
    out += ["", "## AN.C3: COI against the event-by-event simulation", "",
            "| e1000 | Line | COI | COI_MC | 511 keV part of summing-out | d | sigma | \\|d\\| - 3 sigma | limit |",
            "|---|---|---|---|---|---|---|---|---|"]
    for x in r["C3"]["rows"]:
        out.append(f"| {x['e1000']} | {x['nuclide']} {x['energy']} | {x['coi']:.5f} | {x['coi_mc']:.5f} | "
                   f"{x['annihilation']:.5f} | {x['d']:+.5f} | {x['sigma']:.5f} | {x['excess']:+.5f} | "
                   f"{x['limit'] if x['limit'] is not None else 'report'} |")
    c = r["C4"]
    out += ["", "## AN.C4: analytic check", "", f"COI {c['coi']:.15f}, expected {c['expected']:.15f}, "
            f"difference {c['value']:.3g}."]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--decays", type=int, default=C3_DECAYS)
    a = ap.parse_args(argv)
    r = run(a.decays)
    text = report(r)
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "annihilation_results.md").write_text(text, encoding="utf-8")
        (a.out / "annihilation_results.json").write_text(json.dumps(r, indent=1, default=float), encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Round-4 review, activity findings (docs/baseline/round4_activity_protocol.md).

    python -m spectramaster.validation.round4_activity

Synthetic data only.  Writes ``round4_activity.json`` and ``round4_activity.md`` to
docs/baseline/after_R4A.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from spectramaster.analysis import Peak, coincidence
from spectramaster.analysis import activity as act
from spectramaster.analysis.attenuation import SelfAttenuation
from spectramaster.analysis.efficiency import fit_efficiency, manual_point
from spectramaster.lab.sample import SampleInfo
from spectramaster.model import Spectrum

OUT = Path(__file__).resolve().parents[2] / "docs" / "baseline" / "after_R4A"
GAIN, NCH, LIVE = 0.25, 12000, 20000.0
START = datetime(2024, 3, 1, 10, 0, 0)
CS, REF_KEV = 661.657, 1950.0
CODEX_LD = 31.461            # Codex, round-4 review, independent solution (Bq)
BEFORE_RUN = (Path(__file__).resolve().parents[2] / "docs" / "baseline" / "after_R5F"
              / "round4_activity_engine_1.14.0_a8d5346.json")


def _before() -> dict:
    """The protocol's reference values at full precision: this harness run on engine 1.14.0
    (a8d5346), before the change (docs/baseline/round5_precision_protocol.md)."""
    b = json.loads(BEFORE_RUN.read_text(encoding="utf-8"))
    return {"C1_threshold": b["C1"]["decision_threshold"], "C2_no_blank": tuple(b["C2"]["no_blank"]),
            "C2_no_reference": tuple(b["C2"]["no_reference"]), "C3_currie": tuple(b["C3"]["currie"]),
            "C4": tuple(x[2] for x in b["C4"]["same_matrix"]), "C6_cs_best": b["C6"]["cs_row"]["best"]}


BEFORE = _before()
SA_SAME = SelfAttenuation("water", 1.0, "water", 1.0, 50.0)
SA_SOIL = SelfAttenuation("mineral", 1.6, "water", 1.0, 50.0)
PT = (0.25, -0.3)


def _spectrum(sid: str) -> Spectrum:
    return Spectrum(counts=[40] * NCH, live_time=LIVE, real_time=LIVE, start_time=START,
                    energy_coeffs=[0.0, GAIN], sample_id=sid)


def _peak(e: float, area: float, unc: float) -> Peak:
    fw = math.sqrt(0.75 + 0.00185 * e)
    return Peak(centroid=e / GAIN, energy=e, fwhm=fw / GAIN, fwhm_kev=fw, net_area=area, net_area_unc=unc,
                gross_area=area + 400.0, background=400.0, left=int(e / GAIN - 2 * fw / GAIN),
                right=int(e / GAIN + 2 * fw / GAIN), significance=area / unc)


def _flat_curve():
    return fit_efficiency([manual_point(e, 0.01, 2.0) for e in (50, 100, 200, 500, 1000, 2000, 3000)],
                          "loglog", order=1)


def _opts(ref=True, **kw):
    r = {"energy": REF_KEV, "rate": 10000.0 / LIVE, "rate_rel_unc": 0.0} if ref else None
    return act.ActivityOptions(nuclides=["Cs-137"], reference_peak=r, **kw)


def _limits(ref=True, blank=True, mda="iso11929"):
    curve = _flat_curve()
    o = _opts(ref, mda_method=mda)
    rp = [_peak(REF_KEV, 10000.0, 1000.0)] if ref else []
    bl = None
    if blank:
        bl = act.compute_activities(_spectrum("blank"), curve, o, peaks=[_peak(CS, 10000.0, 100.0)] + rp)
    q = act.compute_activities(_spectrum("sample"), curve, o, peaks=[_peak(CS, 11000.0, 105.0)] + rp, blank=bl)
    k = q.nuclides[0].key_line
    return k.decision_threshold, k.mda


C4_LINES = (("Co-60", 1173.228), ("Co-60", 1332.492), ("Ba-133", 356.0129), ("Ba-133", 302.8508))
C5_LINES = (("Co-60", 1332.492), ("Ba-133", 80.9979))      # no summing-in: 1 - COI is the summing-out


def _tcs_case(sa, lines=C4_LINES):
    """(nuclide, line, COI) with TCS on a flat curve."""
    curve = _flat_curve()
    out = []
    for nuc, e in lines:
        o = act.ActivityOptions(nuclides=[nuc], tcs={"peak_to_total": PT, "pt_rel_unc": 0.0,
                                                     "curve_summing_free": True}, self_attenuation=sa)
        q = act.compute_activities(_spectrum("tcs"), curve, o, peaks=[])
        line = min(q.nuclides[0].lines, key=lambda l: abs(l.energy - e))
        out.append((nuc, e, line.coi))
    return out


def _summing_out_independent(nuc: str, e: float, sa) -> float:
    curve = _flat_curve()
    num = wsum = 0.0
    for t in coincidence.transitions(nuc):
        i = t.index(e, coincidence.LINE_TOL_KEV)
        if i is None or t.intensities[i] <= 0:
            continue
        s = 0.0
        for j, ej in enumerate(t.energies):
            p = float(t.coincident[i, j])
            if p <= 0 or ej < coincidence.BELOW_CURVE * curve.e_min:
                continue
            eps = float(curve.efficiency(min(max(ej, curve.e_min), curve.e_max)))
            if sa is not None:
                eps /= sa.factor(float(ej))
            s += p * min(1.0, eps / float(coincidence.peak_to_total(ej, *PT)))
        w = t.br * t.intensities[i]
        num += w * s
        wsum += w
    return num / wsum


def _concentration_rows():
    curve = _flat_curve()
    o = act.ActivityOptions(nuclides=["Cs-137", "Co-60"], mda_method="iso11929")
    q = act.compute_activities(_spectrum("conc"), curve, o, peaks=[_peak(CS, 5000.0, 90.0)])
    conc = act.concentrations(q, SampleInfo(matrix_type="soil", mass_kg=0.5, mass_basis="dry"), "Bq/kg")
    rows = {r["nuclide"]: r for r in conc["rows"]}
    co = next(r for r in q.nuclides if r.nuclide == "Co-60")
    expect = act.iso11929_best_estimate(co.primary / 0.5, co.primary_u / 0.5) if co.primary is not None else None
    return rows, expect, q


def run() -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    res: dict = {"engine": ENGINE_VERSION}
    ys, yd = _limits()
    res["C1"] = {"decision_threshold": ys, "detection_limit": yd, "codex": CODEX_LD,
                 "rel_to_codex": yd / CODEX_LD - 1.0}
    res["C2"] = {"no_blank": _limits(blank=False), "no_reference": _limits(ref=False)}
    res["C3"] = {"currie": _limits(mda="currie")}
    res["C4"] = {"same_matrix": _tcs_case(SA_SAME), "no_self_attenuation": _tcs_case(None)}
    c5 = []
    for (nuc, e, coi_soil), (_n, _e, coi_none) in zip(_tcs_case(SA_SOIL, C5_LINES), _tcs_case(None, C5_LINES)):
        c5.append({"nuclide": nuc, "energy": e, "coi_soil": coi_soil, "coi_no_sa": coi_none,
                   "summing_out_program": None if coi_soil is None else 1.0 - coi_soil,
                   "summing_out_independent": _summing_out_independent(nuc, e, SA_SOIL)})
    res["C5"] = c5
    rows, expect, _q = _concentration_rows()
    res["C6"] = {"cs_row": rows["Cs-137"], "co_row": rows["Co-60"], "co_expected": expect}
    return res


def _close(a, b, rel) -> bool:
    return a is not None and b is not None and abs(a - b) <= rel * abs(b)


def criteria(res: dict) -> dict:
    """PASS / FAIL of RA.C1-C6, "as before" against the full-precision values of engine 1.14.0 at
    the protocol's limits (relative 1e-6 for the RA.C1 threshold, 1e-9 otherwise)."""
    c = {}
    c1 = res["C1"]
    c["RA.C1"] = (abs(c1["rel_to_codex"]) <= 0.01 and _close(c1["decision_threshold"], BEFORE["C1_threshold"], 1e-6),
                  f"y# {c1['detection_limit']:.4f} Bq ({100 * c1['rel_to_codex']:+.3f} % from Codex), "
                  f"y* {c1['decision_threshold']:.6f} Bq")
    pairs = [(res["C2"]["no_blank"], BEFORE["C2_no_blank"]), (res["C2"]["no_reference"], BEFORE["C2_no_reference"])]
    ok = all(_close(a, b, 1e-9) for got, ref in pairs for a, b in zip(got, ref))
    c["RA.C2"] = (ok, "no blank {:.6f} / {:.6f}, no reference {:.6f} / {:.6f} Bq".format(*pairs[0][0], *pairs[1][0]))
    got = res["C3"]["currie"]
    c["RA.C3"] = (all(_close(a, b, 1e-9) for a, b in zip(got, BEFORE["C3_currie"])),
                  "{:.6f} / {:.6f} Bq".format(*got))
    cois = [x[2] for x in res["C4"]["same_matrix"]]
    c["RA.C4"] = (all(_close(a, b, 1e-9) for a, b in zip(cois, BEFORE["C4"]))
                  and cois == [x[2] for x in res["C4"]["no_self_attenuation"]],
                  "COI " + ", ".join(f"{v:.6f}" for v in cois))
    ok = all(_close(r["summing_out_program"], r["summing_out_independent"], 1e-9)
             and r["summing_out_program"] < 1.0 - r["coi_no_sa"] for r in res["C5"])
    c["RA.C5"] = (ok, "; ".join(f"{r['nuclide']} {r['energy']:.1f} keV: {r['summing_out_program']:.6f} "
                                f"(independent {r['summing_out_independent']:.6f}, without self-attenuation "
                                f"{1.0 - r['coi_no_sa']:.6f})" for r in res["C5"]))
    co, exp = res["C6"]["co_row"], res["C6"]["co_expected"]
    ok = exp is not None and all(_close(co.get(k), v, 1e-12) for k, v in
                                 zip(("best", "best_u", "coverage_low", "coverage_high"), exp))
    ok = ok and _close(res["C6"]["cs_row"].get("best"), BEFORE["C6_cs_best"], 1e-9)
    c["RA.C6"] = (ok, f"Co-60 not detected: best {co.get('best')}, interval [{co.get('coverage_low')}, "
                      f"{co.get('coverage_high')}] Bq/kg; Cs-137 best {res['C6']['cs_row'].get('best'):.6f}")
    return {k: {"pass": bool(v[0]), "detail": v[1]} for k, v in c.items()}


def main(argv=None) -> int:
    res = run()
    res["criteria"] = criteria(res)
    n_pass = sum(v["pass"] for v in res["criteria"].values())
    res["summary"] = {"pass": n_pass, "fail": len(res["criteria"]) - n_pass}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "round4_activity.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8",
                                              newline="\n")
    lines = ["# Round-4 activity findings (after_R4A)", "",
             "Protocol: `docs/baseline/round4_activity_protocol.md`. Synthetic data only.", "",
             f"**{n_pass} PASS / {res['summary']['fail']} FAIL** (RA.C1-C6; RA.C7 is the test suite and "
             "the benchmark, reported in the protocol)", "", "| ID | result | detail |", "|---|---|---|"]
    lines += [f"| {k} | {'PASS' if v['pass'] else 'FAIL'} | {v['detail']} |" for k, v in res["criteria"].items()]
    (OUT / "round4_activity.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(res["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

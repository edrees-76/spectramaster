"""Round-6 review, Codex H3 and L1: the partial true-coincidence summing state of an efficiency
calibration, carried to the results and the report (docs/baseline/round6_tcs_state_protocol.md).

    python -m spectramaster.validation.round6_tcs_state [--collect]

Synthetic data and the bundled coincidence table only.  ``--collect`` writes the observations only,
to ``docs/baseline/after_R6E/round6_tcs_state_before.json`` (the "before" values); without it the
criteria are evaluated against that file.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

from spectramaster.analysis import activity as act
from spectramaster.analysis import coincidence as co
from spectramaster.analysis import efficiency as ef
from spectramaster.validation import round5_tcs as r5

OUT = r5.OUT.parent / "after_R6E"
BEFORE_JSON = OUT / "round6_tcs_state_before.json"
CS_E, CS_AREA = 661.657, 20000.0
BA_HIGH = {e: i for e, i in r5.BA.items() if e > 200}


def _curves() -> dict:
    """The calibration of Codex's example (Eu-152 and Ba-133 from 121.8 keV) and a control without
    partial points (Eu-152 alone), each before and after the summing correction."""
    out = {}
    for name, pts in (("eu_ba_121.8", r5._cal_points(r5.EU, "Eu-152") + r5._cal_points(BA_HIGH, "Ba-133")),
                      ("eu_only", r5._cal_points(r5.EU, "Eu-152"))):
        raw = ef.fit_efficiency(pts, "loglog", order=2)
        free = ef.summing_free_curve(raw, r5._pt, 0.1)
        with tempfile.TemporaryDirectory() as tmp:
            loaded = ef.load_curve(free.save(Path(tmp) / "curve.json"))
        legacy = free.to_dict()
        legacy.pop("tcs_partial", None)            # a curve saved by engine 1.25.0 and earlier
        out[name] = {"raw": raw, "free": free, "loaded": loaded, "legacy": ef.EfficiencyCurve.from_dict(legacy)}
    return out


def _quant(curve, tcs: bool):
    o = act.ActivityOptions(nuclides=["Cs-137"], method="mean", intensity_rel_unc=0.01,
                            tcs={"peak_to_total": list(r5.PT), "pt_rel_unc": 0.1} if tcs else None)
    return act.compute_activities(r5._spectrum(), curve, o, peaks=[r5._peak(CS_E, CS_AREA)])


def _report(curve, quant) -> dict:
    from spectramaster.lab.calibration import CalibrationRecord
    from spectramaster.lab.session import AnalysisSession, quant_to_dict
    from spectramaster.lab.workflow import report_record
    s = AnalysisSession()
    s.calibrations = [CalibrationRecord.from_efficiency_curve(curve).to_dict()]
    s.set_results(quant=quant_to_dict(quant))
    rec = report_record(s)
    return {"calibration": rec["calibrations"][0], "statuses": rec["statuses"], "notes": rec["results"]["notes"],
            "tcs_partial": rec["results"].get("curve_tcs_partial")}


# (case, curve set, which curve, TCS correction of the sample)
CASES = (("fresh_tcs", "eu_ba_121.8", "raw", True),
         ("loaded_tcs", "eu_ba_121.8", "loaded", True),
         ("loaded_no_tcs", "eu_ba_121.8", "loaded", False),
         ("legacy_no_tcs", "eu_ba_121.8", "legacy", False),
         ("control_fresh_tcs", "eu_only", "raw", True),
         ("control_loaded_no_tcs", "eu_only", "loaded", False))


def collect() -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    curves = _curves()
    out = {"engine": ENGINE_VERSION, "curves": {}, "cases": {}}
    for name, cs in curves.items():
        out["curves"][name] = {k: {"tcs_partial": getattr(c, "tcs_partial", None), "warnings": list(c.warnings),
                                   "note": c.note, "summing_corrected": c.summing_corrected,
                                   "eps_500": float(c.efficiency(500.0))}
                               for k, c in cs.items()}
    for case, cset, which, tcs in CASES:
        curve = curves[cset][which]
        q = _quant(curve, tcs)
        r = q.nuclides[0]
        rep = _report(curve, q)
        out["cases"][case] = {
            "activity": r.activity, "u": r.u, "mda": r.mda, "decision_threshold": r.decision_threshold,
            "detected": r.detected, "nuclide_note": r.note, "notes": list(q.notes),
            "curve_tcs_partial": getattr(q, "curve_tcs_partial", None),
            "lines": [[l.energy, l.coi, l.coi_applied, l.efficiency, l.activity, l.note] for l in r.lines],
            "report_calibration": rep["calibration"], "report_statuses": rep["statuses"], "report_notes": rep["notes"],
            "report_tcs_partial": rep["tcs_partial"]}
    c = co.coi("Ba-133", 356.0129, r5._flat(0.02), r5._flat(0.24), e_min=122.0)
    out["wording"] = {"ignored": c.ignored, "partial_reason": c.partial_reason, "factor": c.factor}
    out["round5"] = {"calibration": r5._calibration(), "activity": r5._activity()}
    return out


def _numbers(case: dict) -> list:
    return [case["activity"], case["u"], case["mda"], case["decision_threshold"], case["detected"],
            [ln[:5] for ln in case["lines"]]]


def _named(text: str, nuc: str, e: float) -> bool:
    return f"{nuc} {e:g} keV" in text


def criteria(res: dict, before: dict) -> dict:
    out = {}
    cur = res["curves"]["eu_ba_121.8"]
    want = cur["free"]["tcs_partial"] or []
    pts = [(p[0], p[1]) for p in want]
    warn_pts = sorted({(w.split(" ")[0], float(w.split(" ")[1])) for w in cur["free"]["warnings"]
                       if " keV: partial" in w})
    ok1 = (bool(want) and sorted(pts) == warn_pts and cur["loaded"]["tcs_partial"] == want
           and cur["legacy"]["tcs_partial"] == want and cur["raw"]["tcs_partial"] == []
           and all(v["tcs_partial"] == [] for v in res["curves"]["eu_only"].values()))
    out["RE.C1"] = {"value": f"partial points of the corrected curve {pts}; same after save/reload "
                             f"{cur['loaded']['tcs_partial'] == want}, from a 1.25.0 file {cur['legacy']['tcs_partial'] == want}",
                    "pass": ok1}
    bad2 = []
    for case in ("fresh_tcs", "loaded_tcs", "loaded_no_tcs", "legacy_no_tcs"):
        c = res["cases"][case]
        if c["curve_tcs_partial"] != want:
            bad2.append(f"{case}: field {c['curve_tcs_partial']}")
        for nuc, e in pts:
            n = sum(_named(t, nuc, e) for t in c["notes"])
            if n != 1:
                bad2.append(f"{case}: {nuc} {e:g} keV named in {n} result notes")
        if "partial true-coincidence summing correction" not in c["nuclide_note"]:
            bad2.append(f"{case}: Cs-137 note {c['nuclide_note']!r}")
    for case in ("control_fresh_tcs", "control_loaded_no_tcs"):
        c, b = res["cases"][case], before["cases"][case]
        if c["curve_tcs_partial"] != [] or c["notes"] != b["notes"] or c["nuclide_note"] != b["nuclide_note"]:
            bad2.append(f"{case}: control changed")
    out["RE.C2"] = {"value": "; ".join(bad2) or "the four cases carry the field, one note per partial point and "
                                                 "the Cs-137 note; controls unchanged", "pass": not bad2}
    bad3 = []
    for case in ("fresh_tcs", "loaded_tcs", "loaded_no_tcs", "legacy_no_tcs"):
        c = res["cases"][case]
        if c["report_tcs_partial"] != want:
            bad3.append(f"{case}: report results {c['report_tcs_partial']}")
        cal = c["report_calibration"]
        if case != "fresh_tcs" and (cal.get("tcs_partial") != want or not cal.get("note")
                                    or cal.get("warnings") != cur["free"]["warnings"]):
            bad3.append(f"{case}: report calibration {sorted(cal)}")
        st = [s for s in c["report_statuses"] if s["code"] == "outside_validated_scope"
              and "partial true-coincidence summing" in s["message"]]
        if len(st) != 1 or not all(_named(st[0]["message"], n, e) for n, e in pts):
            bad3.append(f"{case}: {len(st)} review statuses")
    for case in ("control_fresh_tcs", "control_loaded_no_tcs"):
        c = res["cases"][case]
        if (c["report_calibration"].get("tcs_partial") or c["report_tcs_partial"]
                or any("partial" in s["message"] for s in c["report_statuses"])):
            bad3.append(f"{case}: control reports a partial correction")
    out["RE.C3"] = {"value": "; ".join(bad3) or "the report's results carry the list, its calibration summary "
                                                 "the list, note and warnings (saved curves); one review status "
                                                 "names the points; controls without it",
                    "pass": not bad3}
    w = res["wording"]
    ok4 = ("% of decays" not in w["partial_reason"] and f"{w['ignored']:.2g} per emission" in w["partial_reason"]
           and w["factor"] == before["wording"]["factor"] and w["ignored"] == before["wording"]["ignored"])
    out["RE.C4"] = {"value": f"{w['partial_reason']!r} (ignored {w['ignored']:.6g})", "pass": ok4}
    bad5 = [case for case in res["cases"] if _numbers(res["cases"][case]) != _numbers(before["cases"][case])]
    bad5 += [f"curve {n} {k}" for n, cs in res["curves"].items() for k, v in cs.items()
             if v["eps_500"] != before["curves"][n][k]["eps_500"]]
    r5c, r5b = res["round5"]["calibration"], before["round5"]["calibration"]
    bad5 += [f"round5 calibration {n}" for n in r5b if {k: v for k, v in r5c[n].items() if k != "note"}
             != {k: v for k, v in r5b[n].items() if k != "note"}]
    ra, rb = res["round5"]["activity"], before["round5"]["activity"]
    bad5 += [f"round5 activity {n}" for n in rb if [ra[n]["activity"], ra[n]["u"]] != [rb[n]["activity"], rb[n]["u"]]
             or [ln[:5] + ln[6:] for ln in ra[n]["lines"]] != [ln[:5] + ln[6:] for ln in rb[n]["lines"]]]
    out["RE.C5"] = {"value": "; ".join(bad5) or "activities, uncertainties, limits, COI factors and efficiencies "
                                                 "identical to before", "pass": not bad5}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--collect", action="store_true", help="write the observations only (the 'before' values)")
    a = ap.parse_args(argv)
    res = json.loads(json.dumps(collect(), default=float))
    OUT.mkdir(parents=True, exist_ok=True)
    if a.collect:
        BEFORE_JSON.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {BEFORE_JSON}")
        return 0
    before = json.loads(BEFORE_JSON.read_text(encoding="utf-8"))
    crit = criteria(res, before)
    (OUT / "round6_tcs_state.json").write_text(json.dumps({"results": res, "criteria": crit}, indent=1,
                                                          ensure_ascii=False), encoding="utf-8")
    lines = ["# Round-6 TCS state (H3, L1)", "", f"engine {res['engine']}", "", "| ID | value | result |",
             "|---|---|---|"]
    lines += [f"| {k} | {v['value']} | {'PASS' if v['pass'] else 'FAIL'} |" for k, v in crit.items()]
    (OUT / "round6_tcs_state.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(v["pass"] for v in crit.values())
    print("\n".join(lines))
    print(f"{n} PASS / {len(crit) - n} FAIL")
    return 0 if n == len(crit) else 1


if __name__ == "__main__":
    sys.exit(main())

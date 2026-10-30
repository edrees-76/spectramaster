"""Round-7 review, H1 (Codex and Gemini): the true-coincidence summing state of an efficiency curve
kept through a refit (docs/baseline/round7_tcs_refit_protocol.md).

    python -m spectramaster.validation.round7_tcs_refit [--collect] [--rerun]

Synthetic data and the bundled coincidence table only.  ``--collect`` writes the observations only,
to ``docs/baseline/after_R7A/round7_tcs_refit_before.json`` (the "before" values); without it the
criteria are evaluated against that file.  RA.C3 uses the efficiency dialog offscreen (PySide6).
``--rerun`` writes the results to RERUN (in the temporary folder) instead of the committed folder,
which a re-run on a later engine then leaves as committed (round8_rerun_protocol.md).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

from spectramaster.analysis import efficiency as ef
from spectramaster.validation import round6_tcs_state as r6

OUT = r6.OUT.parent / "after_R7A"
RERUN = Path(tempfile.gettempdir()) / "spectramaster_round7_tcs_refit"     # --rerun: results here, OUT left as committed
BEFORE_JSON = OUT / "round7_tcs_refit_before.json"
ENERGIES = list(np.geomspace(60.0, 1800.0, 20))
REL = 1e-12
CO60 = ("Co-60", 1332.492)
CS137 = ("Cs-137", 661.657)


def _refit(c, points=None):
    kw = {"order": c.order}
    if c.model == "two_branch":
        kw.update(order_high=c.order_high, crossover=c.e_ref)
    return ef.fit_efficiency(list(c.points) if points is None else points, c.model, **kw)


def _state(c) -> dict:
    return {"summing_corrected": c.summing_corrected, "tcs_partial": [list(x) for x in c.tcs_partial],
            "eps": [float(c.efficiency(e)) for e in ENERGIES]}


def _quant_row(curve, tcs: bool) -> dict:
    q = r6._quant(curve, tcs)
    r = q.nuclides[0]
    return {"activity": r.activity, "u": r.u, "mda": r.mda, "notes": list(q.notes), "nuclide_note": r.note,
            "curve_tcs_partial": [list(x) for x in getattr(q, "curve_tcs_partial", [])]}


def _extra(c, nuc, e):
    v = float(c.efficiency(e))
    return ef.EfficiencyPoint(energy=e, efficiency=v, unc=0.02 * v, nuclide=nuc, u_count_rel=0.02)


def _try(fn):
    try:
        return {"state": _state(fn()), "error": None}
    except ValueError as exc:
        return {"state": None, "error": str(exc)}


def _dialog(curve) -> dict:
    """RA.C3: load the saved corrected curve in the efficiency dialog, Refit, keep and save it."""
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QSettings
        from spectramaster.gui.app import create_app
        from spectramaster.gui.efficiency_dialog import EfficiencyDialog
        from spectramaster.gui.settings import Settings
    except ImportError as exc:
        return {"error": f"not run: {exc}"}
    create_app(["round7"])
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(QSettings(str(Path(tmp) / "s.ini"), QSettings.IniFormat))
        path = curve.save(Path(tmp) / "corrected.json")
        dlg = EfficiencyDialog(None, None, settings)
        loaded = dlg.load_curve_dialog(str(path))
        refit = dlg.refit()
        out = {"error": None, "loaded": loaded, "refit": refit,
               "state": _state(dlg.curve) if dlg.curve is not None else None}
        saved = dlg.save_curve(str(Path(tmp) / "refitted.json")) if refit else None
        out["saved_state"] = _state(ef.load_curve(saved)) if saved else None
        dlg.deleteLater()
    return out


def collect() -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    curves = r6._curves()
    out = {"engine": ENGINE_VERSION, "curves": {}, "quant": {}, "mixed": {}, "files": {}, "control": {}}
    for name, cs in curves.items():
        free, raw = cs["free"], cs["raw"]
        refit = _refit(free)
        out["curves"][name] = {"source": _state(free), "refit": _state(refit)}
        out["quant"][name] = {f"{k}_{'tcs' if t else 'no_tcs'}": _quant_row(c, t)
                              for k, c in (("source", free), ("refit", refit)) for t in (True, False)}
        out["files"][name] = {"raw": raw.to_dict(), "legacy_corrected": free.to_dict()}
        out["control"][name] = {"raw_refit": _state(_refit(raw)), "raw_quant_no_tcs": _quant_row(raw, False)}
    free = curves["eu_ba_121.8"]["free"]
    out["mixed"] = {"cascade": _try(lambda: _refit(free, list(free.points) + [_extra(free, *CO60)])),
                    "non_cascade": _try(lambda: _refit(free, list(free.points) + [_extra(free, *CS137)]))}
    out["dialog"] = _dialog(free)
    cases = {}
    for case, cset, which, tcs in r6.CASES:
        q = r6._quant(curves[cset][which], tcs)
        r = q.nuclides[0]
        cases[case] = [r.activity, r.u, r.mda, r.decision_threshold, r.detected,
                       [[l.energy, l.coi, l.coi_applied, l.efficiency, l.activity] for l in r.lines]]
    out["control"]["round6_cases"] = cases
    return out


def _close(a, b) -> bool:
    return len(a) == len(b) and all(math.isclose(x, y, rel_tol=REL, abs_tol=0.0) for x, y in zip(a, b))


def _same_state(got, want) -> bool:
    return (got is not None and got["summing_corrected"] == want["summing_corrected"]
            and got["tcs_partial"] == want["tcs_partial"] and _close(got["eps"], want["eps"]))


def criteria(res: dict, before: dict) -> dict:
    out = {}
    bad1 = [n for n, c in res["curves"].items() if not (c["source"]["summing_corrected"]
                                                        and _same_state(c["refit"], c["source"]))]
    out["RA.C1"] = {"value": "; ".join(f"{n}: {res['curves'][n]['refit']['summing_corrected']}, "
                                       f"{len(res['curves'][n]['refit']['tcs_partial'])} partial" for n in bad1)
                    or "both corrected curves keep summing_corrected, tcs_partial and their efficiencies",
                    "pass": not bad1}
    bad2 = []
    for n, q in res["quant"].items():
        for t in ("tcs", "no_tcs"):
            s, r = q[f"source_{t}"], q[f"refit_{t}"]
            if not _close([r["activity"], r["u"], r["mda"]], [s["activity"], s["u"], s["mda"]]):
                bad2.append(f"{n} {t}: {r['activity']:.6g} vs {s['activity']:.6g} Bq")
            if r["curve_tcs_partial"] != s["curve_tcs_partial"] or r["notes"] != s["notes"]:
                bad2.append(f"{n} {t}: partial state or notes differ")
    out["RA.C2"] = {"value": "; ".join(bad2) or "activities, u and MDA from the refitted curves equal the source's, "
                                                 "partial notes kept", "pass": not bad2}
    d = res["dialog"]
    want = res["curves"]["eu_ba_121.8"]["source"]
    ok3 = (d.get("error") is None and d["loaded"] and d["refit"] and _same_state(d["state"], want)
           and _same_state(d["saved_state"], want))
    out["RA.C3"] = {"value": "dialog refit and save keep the state" if ok3 else f"dialog: {d}", "pass": ok3}
    m = res["mixed"]
    ok4a = m["cascade"]["error"] is not None and "Co-60 1332.5 keV" in m["cascade"]["error"]
    ok4b = m["non_cascade"]["error"] is None and m["non_cascade"]["state"]["summing_corrected"] \
        and m["non_cascade"]["state"]["tcs_partial"] == want["tcs_partial"]
    out["RA.C4"] = {"value": f"raw cascade point: {m['cascade']['error'] or 'accepted'}; raw non-cascade point: "
                             f"{m['non_cascade']['error'] or 'fitted, state ' + str(m['non_cascade']['state']['summing_corrected'])}",
                    "pass": ok4a and ok4b}
    bad5 = []
    for n, f in res["files"].items():
        if _undated(f["raw"]) != _undated(before["files"][n]["raw"]):
            bad5.append(f"{n}: uncorrected curve file changed")
        leg = ef.EfficiencyCurve.from_dict(before["files"][n]["legacy_corrected"])
        cas = [p for p in leg.points if p.use and not p.manual and _cascade(p.nuclide)]
        if not cas or any(getattr(p, "summing_coi", None) is None for p in cas):
            bad5.append(f"{n}: legacy points without summing_coi")
        else:
            try:
                st = _state(_refit(leg))
            except ValueError as exc:
                st = None
                bad5.append(f"{n}: legacy refit refused ({exc})")
            if st is not None and not _same_state(st, res["curves"][n]["source"]):
                bad5.append(f"{n}: legacy refit state {st['summing_corrected']}, {len(st['tcs_partial'])} partial")
    out["RA.C5"] = {"value": "; ".join(bad5) or "uncorrected files unchanged; 1.26.0 corrected files load with the "
                                                 "point fields and refit as corrected", "pass": not bad5}
    bad6 = [n for n in res["curves"] if json.dumps(res["control"][n], sort_keys=True)
            != json.dumps(before["control"][n], sort_keys=True)]
    if res["control"]["round6_cases"] != before["control"]["round6_cases"]:
        bad6.append("round6_tcs_state cases")
    out["RA.C6"] = {"value": "; ".join(bad6) or "uncorrected curves and round-6 cases identical to before",
                    "pass": not bad6}
    return out


def _undated(d: dict) -> dict:
    """A curve's file content without its fit time (``date``, set when the curve is fitted)."""
    return {k: v for k, v in d.items() if k != "date"}


def _cascade(nuc) -> bool:
    from spectramaster.analysis import coincidence
    return coincidence.has_cascades(nuc)


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
    (out / "round7_tcs_refit.json").write_text(json.dumps({"results": res, "criteria": crit}, indent=1,
                                                          ensure_ascii=False), encoding="utf-8")
    lines = ["# Round-7 TCS state through a refit (H1)", "", f"engine {res['engine']}", "",
             "| ID | value | result |", "|---|---|---|"]
    lines += [f"| {k} | {v['value']} | {'PASS' if v['pass'] else 'FAIL'} |" for k, v in crit.items()]
    (out / "round7_tcs_refit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(v["pass"] for v in crit.values())
    print("\n".join(lines))
    print(f"{n} PASS / {len(crit) - n} FAIL")
    return 0 if n == len(crit) else 1


if __name__ == "__main__":
    sys.exit(main())

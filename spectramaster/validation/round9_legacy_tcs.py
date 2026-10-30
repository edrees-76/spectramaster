"""Round-9 review, Codex H1: summing state of efficiency curves saved by engine 1.26.0 and earlier
(docs/baseline/round9_legacy_tcs_protocol.md).

    python -m spectramaster.validation.round9_legacy_tcs [--collect] [--amendment] [--rerun]

Synthetic data and the bundled coincidence table only.  The files of engine 1.26.0 and earlier are
made from current curves by removing the per-point summing fields, as those engines wrote them.
``--collect`` writes the observations only, to ``docs/baseline/after_R9A/round9_legacy_tcs_before.json``
(the "before" values); without it the criteria are evaluated against that file.  ``--rerun`` writes
the results to RERUN (in the temporary folder) instead of ``after_R9A``.  ``--amendment`` evaluates
RA9.C2a of round9_legacy_tcs_amendment_protocol.md in place of RA9.C2, results to ``after_R9A2``.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from dataclasses import asdict, replace
from pathlib import Path

from spectramaster.analysis import efficiency as ef
from spectramaster.validation import round5_tcs as r5
from spectramaster.validation import round8_coi_guard as r8

OUT = r8.OUT.parent / "after_R9A"
BEFORE_JSON = OUT / "round9_legacy_tcs_before.json"
OUT2 = OUT.parent / "after_R9A2"
RERUN = Path(tempfile.gettempdir()) / "spectramaster_round9_legacy_tcs"
COI_NOTE_TOL = 5e-5                  # RA9.C2a: half the last decimal of "summing corrected, COI x.xxxx"
REL = 1e-12
EXCLUDED = (121.78, 344.28)          # Eu-152 points excluded in the "excluded" case (keV)


def _legacy(d: dict, corrected: bool = None) -> dict:
    """`d` as engine 1.26.0 and earlier saved it: no per-point summing fields; optionally the curve
    flag as a refit of those engines left it."""
    d = json.loads(json.dumps(d))
    for p in d["points"]:
        p.pop("summing_coi", None)
        p.pop("summing_partial", None)
    if corrected is not None:
        d["summing_corrected"] = corrected
        if not corrected:
            d["tcs_partial"] = []
    return d


def _resaved(d: dict) -> dict:
    """A legacy file opened and saved again by engines 1.27.0-1.34.0: fields written as None."""
    d = json.loads(json.dumps(d))
    for p in d["points"]:
        p.setdefault("summing_coi", None)
        p.setdefault("summing_partial", "")
    return d


def _files() -> dict:
    """The saved curves (dicts) of the cases."""
    cs = r8._curves()
    corr = cs["corrected"]                                   # Eu-152 corrected, all used, marked corrected
    pts = list(corr.points) + [r8._point(corr, n, e) for n, e in r8.EXTRA]
    full = ef.fit_efficiency(pts, "loglog", order=2)         # corrected points plus non-cascade ones
    excl = ef.fit_efficiency([replace(p, use=False) if p.nuclide == "Eu-152" and
                              any(abs(p.energy - e) < 0.1 for e in EXCLUDED) else p for p in pts],
                             "loglog", order=2)
    mixed = full.to_dict()
    mixed["points"].append(asdict(r8._point(corr, *r8.RAW_CASCADE)))
    return {
        # a refit by engine <= 1.26.0 lost the flag: corrected values and notes, not marked corrected
        "lost_flag": _legacy(full.to_dict(), corrected=False),
        "lost_flag_resaved": _resaved(_legacy(full.to_dict(), corrected=False)),
        # marked corrected, two corrected points excluded
        "excluded": _legacy(excl.to_dict()),
        # lost flag plus an uncorrected cascade point in use: cannot be decided
        "lost_flag_mixed": _legacy(mixed, corrected=False),
        # controls
        "legacy_corrected": _legacy(full.to_dict()),
        "legacy_raw": _legacy(cs["raw"].to_dict()),
        "modern_corrected": full.to_dict(),
        "modern_excluded": excl.to_dict(),
        "modern_raw": cs["raw"].to_dict(),
    }


def _load(d):
    return ef.EfficiencyCurve.from_dict(json.loads(json.dumps(d)))


def _points(c) -> list:
    return [[p.nuclide, p.energy, p.use, p.efficiency, p.summing_coi, p.summing_partial] for p in c.points]


def _include_all_refit(c):
    """Every point included again and the curve refitted (the dialog's include + refit)."""
    try:
        f = ef.fit_efficiency([replace(p, use=True) for p in c.points], c.model, order=c.order)
        return {"state": r8._state(f), "error": None}
    except ValueError as exc:
        return {"state": None, "error": str(exc)}


def collect() -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    files = _files()
    out = {"engine": ENGINE_VERSION, "files": files, "loaded": {}, "free": {}, "quant": {}, "include": {}}
    for name, d in files.items():
        c = _load(d)
        out["loaded"][name] = {"summing_corrected": c.summing_corrected, "points": _points(c)}
        out["free"][name] = r8._free(c)
        out["quant"][name] = r8._quant(c)
        if name in ("excluded", "modern_excluded"):
            out["include"][name] = _include_all_refit(c)
    # the refit of the lost-flag file's points as they are (what a correct load gives)
    c = _load(files["lost_flag"])
    ref = ef.fit_efficiency(list(c.points), c.model, order=c.order)
    out["refit_as_is"] = {"state": r8._state(ref), "quant": r8._quant(ref)}
    return out


def _close(a, b) -> bool:
    return a is not None and b is not None and math.isclose(a, b, rel_tol=REL, abs_tol=0.0)


def _eps(s) -> list:
    return s["eps"] + [s["eps121"]]


def criteria(res: dict, before: dict, amendment: bool = False) -> dict:
    res, before = r8._no_date(res), r8._no_date(before)
    out = {}
    ref = res["refit_as_is"]
    bad = []
    for name in ("lost_flag", "lost_flag_resaved"):
        f, q = res["free"][name], res["quant"][name]
        if f["error"] is not None or not f["state"]["summing_corrected"]:
            bad.append(f"{name}: {f['error'] or 'not marked corrected'}")
            continue
        if not all(_close(a, b) for a, b in zip(_eps(f["state"]), _eps(ref["state"]))):
            bad.append(f"{name}: curve at {r8.EU121} keV {f['state']['eps121']:.6g} vs refit as is "
                       f"{ref['state']['eps121']:.6g}")
        if q.get("error") or not all(_close(q[k], ref["quant"][k]) for k in ("activity", "u", "mda")):
            bad.append(f"{name}: Cs-137 {q.get('activity')} vs {ref['quant']['activity']} Bq")
    fb = before["free"]["lost_flag"]
    was = f"before: curve at {r8.EU121} keV {fb['state']['eps121']:.6g}" if fb["state"] else f"before: {fb['error']}"
    out["RA9.C1"] = {"value": "; ".join(bad) or f"lost-flag files (as saved and re-saved) refitted as they are, not "
                     f"corrected again ({was}; refit as is {ref['state']['eps121']:.6g})", "pass": not bad}
    bad = []
    pts = res["loaded"]["excluded"]["points"]
    modern = res["loaded"]["modern_excluded"]["points"]
    if amendment:
        if [p[4] is None for p in pts] != [p[4] is None for p in modern] or any(
                abs(a[4] - b[4]) > COI_NOTE_TOL for a, b in zip(pts, modern) if a[4] is not None):
            bad.append("excluded points' summing_coi differ from the modern file's beyond the note's rounding")
    elif [p[4] for p in pts] != [p[4] for p in modern]:
        bad.append("excluded points' summing_coi differ from the modern file's")
    inc, incm = res["include"]["excluded"], res["include"]["modern_excluded"]
    if inc["error"] is not None:
        bad.append(f"include + refit refused: {inc['error']}")
    elif not (inc["state"]["summing_corrected"] and all(_close(a, b) for a, b in zip(_eps(inc["state"]),
                                                                                   _eps(incm["state"])))):
        bad.append("include + refit differs from the modern file's")
    out["RA9.C2a" if amendment else "RA9.C2"] = {"value": "; ".join(bad) or "excluded corrected points carry their correction; included again "
                     "and refitted as the modern file", "pass": not bad}
    m = res["free"]["lost_flag_mixed"]
    out["RA9.C3"] = {"value": f"lost flag with an uncorrected cascade point: before "
                     f"{'refused' if before['free']['lost_flag_mixed']['error'] else 'corrected'}; now "
                     f"{m['error'] or 'not refused'}", "pass": m["error"] is not None}
    bad = []
    for name in ("legacy_corrected", "legacy_raw", "modern_corrected", "modern_excluded", "modern_raw"):
        for part in ("loaded", "free", "quant"):
            if not r8._same(res[part][name], before[part][name]):
                bad.append(f"{name} {part}")
    if not r8._same(res["include"]["modern_excluded"], before["include"]["modern_excluded"]):
        bad.append("modern_excluded include")
    out["RA9.C4"] = {"value": "; ".join(bad) or "legacy corrected and raw files, modern files: identical to before",
                     "pass": not bad}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--collect", action="store_true", help="write the observations only (the 'before' values)")
    ap.add_argument("--amendment", action="store_true", help="RA9.C2a in place of RA9.C2, results to after_R9A2")
    ap.add_argument("--rerun", action="store_true", help=f"write the results to {RERUN}, not after_R9A")
    a = ap.parse_args(argv)
    res = json.loads(json.dumps(collect(), default=float))
    if a.collect:
        OUT.mkdir(parents=True, exist_ok=True)
        BEFORE_JSON.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {BEFORE_JSON}")
        crit = criteria(res, res)
    else:
        crit = criteria(res, json.loads(BEFORE_JSON.read_text(encoding="utf-8")), a.amendment)
        out = RERUN if a.rerun else (OUT2 if a.amendment else OUT)
        out.mkdir(parents=True, exist_ok=True)
        (out / "round9_legacy_tcs.json").write_text(json.dumps({"results": res, "criteria": crit}, indent=1,
                                                               ensure_ascii=False), encoding="utf-8")
    lines = ["# Round-9 summing state of curves saved by engine 1.26.0 and earlier (Codex H1)",
             "", f"engine {res['engine']}", "", "| ID | value | result |", "|---|---|---|"]
    lines += [f"| {k} | {v['value']} | {'PASS' if v['pass'] else 'FAIL'} |" for k, v in crit.items()]
    if not a.collect:
        (out / "round9_legacy_tcs.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(v["pass"] for v in crit.values())
    print("\n".join(lines))
    print(f"{n} PASS / {len(crit) - n} FAIL")
    return 0 if n == len(crit) else 1


if __name__ == "__main__":
    sys.exit(main())

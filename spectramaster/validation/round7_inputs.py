"""Round-7 review, input validation (docs/baseline/round7_inputs_protocol.md): Codex M1, Gemini M4.

    python -m spectramaster.validation.round7_inputs [--collect]

``--collect`` writes the observations only, to ``docs/baseline/after_R7E/round7_inputs_before.json``
(the "before" values); without it the criteria (RE.C1-C5) are evaluated against that file.
RE.C6 is the benchmark and the test suite.  Needs PySide6 (offscreen) for RE.C1 and RE.C5.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from .round6_inputs import _app, _refused, _try

OUT = Path(__file__).resolve().parents[2] / "docs" / "baseline" / "after_R7E"
BEFORE_JSON = OUT / "round7_inputs_before.json"


# ------------------------------------------------------------------ RE.C1 manual efficiency points
MANUAL = [(100.0, 0.05, 2.0), (300.0, 0.03, 2.0), (600.0, 0.018, 2.0), (1000.0, 0.012, 2.0), (1500.0, 0.009, 2.0)]
# (column, text): each must be refused; column 2 energy, 4 efficiency, 5 uncertainty %
POINT_BAD = [(4, "0,02"), (4, "-0.01"), (4, "nan"), (4, "0"), (4, "abc"), (4, ""), (2, "inf"), (2, "-100"),
             (2, "1,5"), (5, "1,5"), (5, "-2"), (5, "nan"), (5, "0"), (5, "")]
POINT_GOOD = [(4, "0.02"), (2, "120"), (5, "3.5")]


def _dialog(tmp: str):
    _app()
    from PySide6.QtCore import QSettings
    from ..gui.efficiency_dialog import EfficiencyDialog
    from ..gui.settings import Settings
    dlg = EfficiencyDialog(None, None, Settings(QSettings(str(Path(tmp) / "s.ini"), QSettings.IniFormat)))
    dlg.messages = []
    dlg._msg = lambda text, error=True: dlg.messages.append(text)
    for e, v, u in MANUAL:
        dlg.add_manual_point(e, v, u)
    dlg.model_combo.setCurrentIndex(dlg.model_combo.findData("loglog"))
    if not dlg.refit():
        raise RuntimeError(f"the clean manual points do not fit: {dlg.messages}")
    return dlg


def _point_case(col: int, text: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="r7e_") as tmp:
        dlg = _dialog(tmp)
        dlg.pt_table.item(0, col).setText(text)
        ok = dlg.refit()
        p = dlg.points[0]
        saved = dlg.save_curve(str(Path(tmp) / "c.json"))
        out = {"refit": bool(ok), "curve": dlg.curve is not None, "messages": list(dlg.messages),
               "point": [p.energy, p.efficiency, p.u_count_rel], "saved": saved is not None,
               "shown": dlg.pt_table.item(0, col).text()}
        dlg.close()
        return out


def c1() -> dict:
    return {f"{c}:{t}": _point_case(c, t) for c, t in POINT_BAD + POINT_GOOD}


# ------------------------------------------------------------------ RE.C2 QC monitored lines
QC_BAD = ["inf:Cs-137", "nan:Cs-137", "661.657:Cs-137:nan", "661.657:Cs-137:inf", "661.657:Cs-137:-5",
          "661.657:Cs-137:0", "661,657:Cs-137", "661.657:Cs-137:1,5", "abc:Cs-137"]
QC_GOOD = ["661.657:Cs-137, 1332.492:Co-60:2.0", "661.657; 1332.492", "1460.82:K-40:3\n661.657:Cs-137"]


def c2() -> dict:
    from ..gui.qc_window import parse_lines

    def read(text):
        return [[l.energy, l.nuclide, l.fwhm_max] for l in parse_lines(text)]
    return {t: _try(read, t) for t in QC_BAD + QC_GOOD}


# ------------------------------------------------------------------ RE.C3 certificate CSV
CSV_HEAD = "nuclide,activity_bq,unc_percent,ref_date,half_life_s,energy_kev,intensity_percent\n"
ROW1 = "Eu-152,1000,2,2020-01-01 12:00,4.27e8,121.78,28.5\n"
CSV_BAD = {
    "second row other activity": CSV_HEAD + ROW1 + "Eu-152,2000,2,2020-01-01 12:00,4.27e8,344.28,26.6\n",
    "second row other uncertainty": CSV_HEAD + ROW1 + "Eu-152,1000,5,2020-01-01 12:00,4.27e8,344.28,26.6\n",
    "second row other date": CSV_HEAD + ROW1 + "Eu-152,1000,2,2021-01-01 12:00,4.27e8,344.28,26.6\n",
    "second row invalid date": CSV_HEAD + ROW1 + "Eu-152,1000,2,INVALID_DATE,4.27e8,344.28,26.6\n",
    "second row other half-life": CSV_HEAD + ROW1 + "Eu-152,1000,2,2020-01-01 12:00,1e8,344.28,26.6\n",
    "second row invalid half-life": CSV_HEAD + ROW1 + "Eu-152,1000,2,2020-01-01 12:00,-50,344.28,26.6\n",
    "unknown column": "nuclide,activity_bq,uncertainty_pct,ref_date\nCs-137,1000,2,2020-01-01\n",
    "no uncertainty column": "nuclide,activity_bq,ref_date\nCs-137,1000,2020-01-01\n",
    "intensity above 100": CSV_HEAD + "Cs-137,1000,2,2020-01-01,9.49e8,661.657,185.1\n",
    "energy without intensity": CSV_HEAD + "Cs-137,1000,2,2020-01-01,9.49e8,661.657,\n",
    "intensity without energy": CSV_HEAD + "Cs-137,1000,2,2020-01-01,9.49e8,,85.1\n",
}
CSV_GOOD = {
    "two lines, same data": CSV_HEAD + ROW1 + "Eu-152,1000,2,2020-01-01 12:00,4.27e8,344.28,26.6\n",
    "library lines": CSV_HEAD + "Cs-137,1000,2,2020-01-01 12:00,9.49e8,,\nCo-60,2000,1.5,2020-01-01,,,\n",
    "no header": "Cs-137,1000,2,2020-01-01\nCo-60,2000,1.5,2020-01-01\n",
    "unc in Bq": "nuclide,activity_bq,unc_bq,ref_date\nCs-137,1000,20,2020-01-01\n",
    "second row date written otherwise": CSV_HEAD + ROW1 + "Eu-152,1000,2,01/01/2020 12:00,4.27e8,344.28,26.6\n",
}


def c3() -> dict:
    from ..analysis import efficiency as eff

    def read(text):
        with tempfile.TemporaryDirectory(prefix="r7e_") as d:
            p = Path(d) / "c.csv"
            p.write_text(text, encoding="utf-8")
            r = eff.read_certificate_csv(p)
            return [[c.nuclide, c.activity, c.activity_unc, str(c.ref_date), c.half_life_s, c.lines] for c in r]
    out = {k: _try(read, v) for k, v in CSV_BAD.items()}
    out.update({k: _try(read, v) for k, v in CSV_GOOD.items()})
    # a file written by the program reads back as written
    with tempfile.TemporaryDirectory(prefix="r7e_") as d:
        entries = [eff.CertNuclide("Eu-152", 1000.0, 20.0, datetime(2020, 1, 1, 12), 4.27e8,
                                   [(121.78, 0.285), (344.28, 0.266)]),
                   eff.CertNuclide("Cs-137", 500.0, 10.0, datetime(2020, 1, 1), None)]
        p = eff.write_certificate_csv(Path(d) / "w.csv", entries)
        out["written by the program"] = _try(lambda: [[c.nuclide, c.activity, c.activity_unc, str(c.ref_date),
                                                       c.half_life_s, c.lines] for c in eff.read_certificate_csv(p)])
    return out


# ------------------------------------------------------------------ RE.C4 Aptec source records
def _rec(**kw):
    from ..analysis.efficiency import AptecSourceRecord
    base = dict(nuclide="Cs-137", energy=661.657, yield_=0.851, half_life_s=9.49e8, ref_date=datetime(2020, 1, 1),
                activity=1000.0, activity_unc_pct=2.0, activity_units="Bq", quantity=1.0, quantity_units="",
                rate_cps=10.0, rate_unc_pct=1.0, efficiency=0.01, efficiency_unc_pct=2.2, measured=None)
    base.update(kw)
    return AptecSourceRecord(**base)


APTEC_BAD = {"nan energy": dict(energy=math.nan), "inf energy": dict(energy=math.inf),
             "negative energy": dict(energy=-661.657), "nan yield": dict(yield_=math.nan),
             "inf yield": dict(yield_=math.inf), "yield above 1": dict(yield_=1.5),
             "nan activity": dict(activity=math.nan), "inf activity": dict(activity=math.inf),
             "nan uncertainty": dict(activity_unc_pct=math.nan), "negative uncertainty": dict(activity_unc_pct=-2.0),
             "nan half-life": dict(half_life_s=math.nan), "inf half-life": dict(half_life_s=math.inf)}
APTEC_SKIP = {"empty slot": dict(nuclide="", activity=0.0, yield_=0.0, energy=0.0),
              "zero activity": dict(activity=0.0), "zero yield": dict(yield_=0.0)}


def c4() -> dict:
    from ..analysis.efficiency import certificate_from_aptec

    def lines(recs):
        return [[l.nuclide, l.energy, l.intensity, l.activity, l.activity_unc, l.half_life_s]
                for l in certificate_from_aptec(recs)]
    good = _rec()
    out = {"good": _try(lines, [good]), "no half-life": _try(lines, [_rec(half_life_s=0.0)])}
    out.update({k: _try(lines, [good, _rec(**kw)]) for k, kw in APTEC_BAD.items()})
    out.update({k: _try(lines, [good, _rec(**kw)]) for k, kw in APTEC_SKIP.items()})
    return out


# ------------------------------------------------------------------ RE.C5 ActivityInput.set_bq
SET_BAD = [-5.0, -1e-9]
SET_GOOD = [0.0, 12345.678, 1e-3]


def c5() -> dict:
    _app()
    from ..gui.activity_input import ActivityInput
    w = ActivityInput()
    out = {}
    for v in SET_BAD + SET_GOOD:
        w.set_bq(12345.678)
        out[repr(v)] = _try(lambda x=v: (w.set_bq(x), w.value_bq())[1])
    w.set_bq(12345.678)
    _try(w.set_bq, -5.0)
    out["after a refusal"] = w.value_bq()
    return out


def collect() -> dict:
    return {"C1": c1(), "C2": c2(), "C3": c3(), "C4": c4(), "C5": c5()}


def criteria(m: dict, b: dict) -> list[dict]:
    rows = []
    r1, b1 = m["C1"], b["C1"]
    bad = []
    for c, t in POINT_BAD:
        v = r1[f"{c}:{t}"]
        refused = (not v["refit"] and not v["curve"] and not v["saved"] and v["messages"]
                   and any("row 1" in s for s in v["messages"]) and v["shown"] == t
                   and v["point"] == b1[f"{c}:{t}"]["point"])
        if not refused:
            bad.append(f"{c}:{t!r}")
    good = all(r1[f"{c}:{t}"]["refit"] and r1[f"{c}:{t}"]["saved"] and not r1[f"{c}:{t}"]["messages"]
               and r1[f"{c}:{t}"] == b1[f"{c}:{t}"] for c, t in POINT_GOOD)
    rows.append({"id": "RE.C1", "pass": not bad and good,
                 "value": f"refused with the row named, nothing fitted or saved: {len(POINT_BAD) - len(bad)} of "
                          f"{len(POINT_BAD)} (not: {bad}); valid edits as before: {good}"})
    r2, b2 = m["C2"], b["C2"]
    bad = [t for t in QC_BAD if not _refused(r2[t])]
    good = all(r2[t] == b2[t] and not _refused(r2[t]) for t in QC_GOOD)
    rows.append({"id": "RE.C2", "pass": not bad and good,
                 "value": f"refused {len(QC_BAD) - len(bad)} of {len(QC_BAD)} (not: {bad}); valid as before: {good}"})
    r3, b3 = m["C3"], b["C3"]
    bad = [k for k in CSV_BAD if not _refused(r3[k])]
    keep = list(CSV_GOOD) + ["written by the program"]
    good = all(r3[k] == b3[k] and not _refused(r3[k]) for k in keep)
    rows.append({"id": "RE.C3", "pass": not bad and good,
                 "value": f"refused {len(CSV_BAD) - len(bad)} of {len(CSV_BAD)} (not: {bad}); valid files as before: "
                          f"{good}"})
    r4, b4 = m["C4"], b["C4"]
    bad = [k for k in APTEC_BAD if not _refused(r4[k])]
    good = all(r4[k] == b4[k] and not _refused(r4[k]) for k in ["good", "no half-life", *APTEC_SKIP])
    rows.append({"id": "RE.C4", "pass": not bad and good,
                 "value": f"refused {len(APTEC_BAD) - len(bad)} of {len(APTEC_BAD)} (not: {bad}); valid records and "
                          f"skipped empty slots as before: {good}"})
    r5, b5 = m["C5"], b["C5"]
    bad = [repr(v) for v in SET_BAD if not _refused(r5[repr(v)])]
    good = all(r5[repr(v)] == b5[repr(v)] for v in SET_GOOD) and r5["after a refusal"] == 12345.678
    rows.append({"id": "RE.C5", "pass": not bad and good,
                 "value": f"refused {len(SET_BAD) - len(bad)} of {len(SET_BAD)} (not: {bad}); valid as before and "
                          f"the previous value kept: {good}"})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--collect", action="store_true", help="write the observations only (the 'before' values)")
    a = ap.parse_args(argv)
    m = json.loads(json.dumps(collect(), default=str))
    OUT.mkdir(parents=True, exist_ok=True)
    if a.collect:
        BEFORE_JSON.write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {BEFORE_JSON}")
        return 0
    b = json.loads(BEFORE_JSON.read_text(encoding="utf-8"))
    rows = criteria(m, b)
    (OUT / "round7_inputs.json").write_text(json.dumps({"observations": m, "criteria": rows}, indent=1,
                                                       ensure_ascii=False), encoding="utf-8")
    lines = ["# Round-7 input validation (Codex M1, Gemini M4)", "", "| ID | value | result |", "|---|---|---|"]
    lines += [f"| {r['id']} | {r['value']} | {'PASS' if r['pass'] else 'FAIL'} |" for r in rows]
    (OUT / "round7_inputs.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(r["pass"] for r in rows)
    print("\n".join(lines))
    print(f"{n} PASS / {len(rows) - n} FAIL")
    return 0 if n == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())

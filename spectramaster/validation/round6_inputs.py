"""Round-6 review, input validation (docs/baseline/round6_inputs_protocol.md): Codex H2 / M1,
Gemini H1 / M2.

    python -m spectramaster.validation.round6_inputs [--collect]

``--collect`` writes the observations only, to ``docs/baseline/after_R6C/round6_inputs_before.json``
(the "before" values); without it the criteria (RC.C1-C8) are evaluated against that file.
RC.C9 is the benchmark and the test suite.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np

from ..model import Spectrum

OUT = Path(__file__).resolve().parents[2] / "docs" / "baseline" / "after_R6C"
BEFORE_JSON = OUT / "round6_inputs_before.json"


def _try(fn, *a, **kw):
    """The value, or "ValueError: ..." when fn raises ValueError."""
    try:
        return fn(*a, **kw)
    except ValueError as exc:
        return f"ValueError: {exc}"[:200]


def _refused(v) -> bool:
    return isinstance(v, str) and v.startswith("ValueError")


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(["round6"])


# ------------------------------------------------------------------ RC.C1 / C2 certificate table
def _cert_values(ed):
    return [[c.nuclide, c.activity, c.activity_unc, c.half_life_s, c.lines] for c in ed.certificate()]


def c1() -> dict:
    _app()
    from ..analysis import efficiency as eff
    from ..gui.efficiency_dialog import CertificateEditor
    ed = CertificateEditor()
    ed.set_certificate([eff.CertNuclide("Cs-137", 1000.0, 20.0, None)])
    ed.cert_table.item(0, 1).setText("2000")
    edited = _try(_cert_values, ed)
    ed.set_activity_unit("kBq")
    switched = _try(_cert_values, ed)
    ed2 = CertificateEditor()
    ed2.set_certificate([eff.CertNuclide("Cs-137", 12345.678, 246.91356, None)])
    for u in ("Ci", "µCi", "Bq"):
        ed2.set_activity_unit(u)
    return {"edited": edited, "edited_then_kBq": switched, "round_trip": _try(_cert_values, ed2)}


# column, text: each must be refused
CERT_BAD = [(1, "1e309"), (1, "nan"), (1, "inf"), (1, "-5"), (1, "0"), (1, "1,5"), (1, "1,000"),
            (2, "1e309"), (2, "-1"), (2, "nan"), (4, "inf"), (4, "-3"), (4, "0"), (4, "nan"),
            (5, "661.657:85,1"), (5, "661.657:inf"), (5, "inf:85.1"), (5, "661.657:-85.1"), (5, "661.657:0"),
            (5, "661.657")]


def c2() -> dict:
    _app()
    from ..analysis import efficiency as eff
    from ..gui.efficiency_dialog import CertificateEditor
    out = {}
    for col, text in CERT_BAD:
        ed = CertificateEditor()
        ed.set_certificate([eff.CertNuclide("Cs-137", 1000.0, 20.0, None, 9.49e8)])
        ed.cert_table.item(0, col).setText(text)
        out[f"col{col}={text}"] = _try(_cert_values, ed)
    ed = CertificateEditor()
    ed.add_cert_row()
    for col, text in ((0, "Co-60"), (1, "1000"), (2, "2"), (4, "1.66e8"), (5, "1173.228:99.85; 1332.492:99.9826")):
        ed.cert_table.item(0, col).setText(text)
    out["typed valid"] = _try(_cert_values, ed)
    return out


# ------------------------------------------------------------------ RC.C3 certificate CSV
CSV_HEAD = "nuclide,activity_bq,unc_percent,ref_date,half_life_s,energy_kev,intensity_percent\n"
CSV_GOOD = CSV_HEAD + "Cs-137,1000,2,2020-01-01 12:00,9.49e8,661.657,85.1\nCo-60,2000,1.5,2020-01-01 12:00,1.663e8,,\n"
CSV_BAD = {"inf activity": "Cs-137,inf,2,2020-01-01,9.49e8,,\n",
           "nan activity": "Cs-137,nan,2,2020-01-01,9.49e8,,\n",
           "1e309 activity": "Cs-137,1e309,2,2020-01-01,9.49e8,,\n",
           "negative activity": "Cs-137,-1000,2,2020-01-01,9.49e8,,\n",
           "zero activity": "Cs-137,0,2,2020-01-01,9.49e8,,\n",
           "negative uncertainty": "Cs-137,1000,-2,2020-01-01,9.49e8,,\n",
           "nan uncertainty": "Cs-137,1000,nan,2020-01-01,9.49e8,,\n",
           "inf half-life": "Cs-137,1000,2,2020-01-01,inf,,\n",
           "negative half-life": "Cs-137,1000,2,2020-01-01,-5,,\n",
           "inf energy": "Cs-137,1000,2,2020-01-01,9.49e8,inf,85.1\n",
           "inf intensity": "Cs-137,1000,2,2020-01-01,9.49e8,661.657,inf\n",
           "negative intensity": "Cs-137,1000,2,2020-01-01,9.49e8,661.657,-85.1\n"}


def c3() -> dict:
    from ..analysis import efficiency as eff

    def read(text):
        with tempfile.TemporaryDirectory(prefix="r6c_") as d:
            p = Path(d) / "c.csv"
            p.write_text(text, encoding="utf-8")
            r = eff.read_certificate_csv(p)
            return [[c.nuclide, c.activity, c.activity_unc, str(c.ref_date), c.half_life_s, c.lines] for c in r]
    out = {"good": _try(read, CSV_GOOD)}
    for k, row in CSV_BAD.items():
        out[k] = _try(read, CSV_HEAD + row)
    return out


# ------------------------------------------------------------------ RC.C4 measure_efficiency
def _cs_spectrum() -> Spectrum:
    rng = np.random.default_rng(20261028)
    ch = np.arange(4096)
    mu, sig = 661.657 / 0.5, 1.2 / 0.5 / 2.3548
    y = 200.0 * np.exp(-ch / 1500.0) + 2.0e4 / (sig * math.sqrt(2 * math.pi)) * np.exp(-0.5 * ((ch - mu) / sig) ** 2)
    return Spectrum(counts=[int(v) for v in rng.poisson(y)], live_time=3600.0, real_time=3610.0,
                    energy_coeffs=[0.0, 0.5], start_time=datetime(2024, 1, 1, 12))


LINE_BAD = {"nan activity": {"activity": math.nan}, "inf activity": {"activity": math.inf},
            "negative activity": {"activity": -1000.0}, "nan uncertainty": {"activity_unc": math.nan},
            "negative uncertainty": {"activity_unc": -20.0}, "nan intensity": {"intensity": math.nan},
            "inf intensity": {"intensity": math.inf}, "nan half-life": {"half_life_s": math.nan},
            "zero half-life": {"half_life_s": 0.0}, "negative half-life": {"half_life_s": -9.49e8}}


def c4() -> dict:
    from dataclasses import replace

    from ..analysis import efficiency as eff
    sp = _cs_spectrum()
    good = eff.CertLine("Cs-137", 661.657, 0.851, 1000.0, 20.0, datetime(2020, 1, 1, 12), 9.49e8, 0.002)

    def run(line):
        pts = eff.measure_efficiency(sp, [line])
        return [[p.energy, p.efficiency, p.unc, p.use, p.note] for p in pts]
    out = {"good": _try(run, good)}
    for k, kw in LINE_BAD.items():
        out[k] = _try(run, replace(good, **kw))
    return out


# ------------------------------------------------------------------ RC.C5 detector test
def _co60_spectrum() -> Spectrum:
    ch = np.arange(6000)
    mu, sig = 1332.5 / 0.5, 2.0 / 0.5 / 2.3548
    y = 120.0 - 0.01 * ch + 1e5 / (sig * math.sqrt(2 * math.pi)) * np.exp(-0.5 * ((ch - mu) / sig) ** 2)
    return Spectrum(counts=[float(v) for v in y], live_time=3600.0, real_time=3600.0, energy_coeffs=[0.0, 0.5])


def c5() -> dict:
    from ..analysis import detector_test as dt

    def values(sp):
        w = dt.peak_width(sp)
        return {"peak_width": [w.centroid_kev, w.fwhm_kev, w.fwtm_kev, w.note],
                "peak_to_compton": _try(dt.peak_to_compton, sp), "net_area": _try(dt.net_area, sp),
                "relative_efficiency": _try(lambda: dt.relative_efficiency(sp, 37000.0).percent)}
    clean = _co60_spectrum()
    out = {"clean": values(clean)}
    for label, where in (("nan in the 1332 ROI", int(1332.5 / 0.5) + 1), ("nan in the Compton window", int(1060 / 0.5)),
                         ("inf in the 1332 ROI", int(1332.5 / 0.5) - 1)):
        sp = _co60_spectrum()
        sp.counts[where] = math.nan if label.startswith("nan") else math.inf
        out[label] = {"peak_width": _try(lambda s=sp: [dt.peak_width(s).fwhm_kev]),
                      "peak_to_compton": _try(dt.peak_to_compton, sp), "net_area": _try(dt.net_area, sp),
                      "relative_efficiency": _try(lambda s=sp: dt.relative_efficiency(s, 37000.0).percent)}
    return out


# ------------------------------------------------------------------ RC.C6 / C7 / C8 GUI parsers
COUNTS_BAD = ["100\n1,5\n", "100\n1,000\n", "100\ninf\n", "100\nnan\n", "100\n1e309\n"]
COUNTS_GOOD = "100\n 105 \n\n98.5\n1e2\n-3\n"
QC_BAD = ["Cs-137=-1000", "Cs-137=0", "Cs-137=-1 uCi"]
QC_READ = [("Cs-137=37000", {"Cs-137": 37000.0}),
           ("Cs-137=37000, Co-60=1 uCi", {"Cs-137": 37000.0, "Co-60": 37000.0}),
           ("Cs-137=1 µCi; Co-60=2 kBq", {"Cs-137": 37000.0, "Co-60": 2000.0}),
           ("Cs137=37000, Co60=1 uCi", {"Cs-137": 37000.0, "Co-60": 37000.0}),
           ("cs137=37000; Am241=500", {"Cs-137": 37000.0, "Am-241": 500.0})]
QC_REFUSED_BEFORE = ["Cs-137=1,000 Bq", "Cs-137=1,5 Bq", "Cs-137=1e309", "Cs-137=abc", "Cs-137"]


def c678() -> dict:
    _app()
    from ..gui.activity_input import ActivityInput
    from ..gui.detector_test_dialog import parse_counts
    from ..gui.qc_window import _parse_activity
    counts = {"bad": {t: _try(parse_counts, t) for t in COUNTS_BAD}, "good": _try(parse_counts, COUNTS_GOOD)}
    qc = {"bad": {t: _try(_parse_activity, t) for t in QC_BAD},
          "read": [[t, _try(_parse_activity, t)] for t, _e in QC_READ],
          "refused": {t: _try(_parse_activity, t) for t in QC_REFUSED_BEFORE}}
    w = ActivityInput()
    bq = {}
    for label, v in (("inf", math.inf), ("nan", math.nan), ("-inf", -math.inf)):
        w.set_bq(12345.678)
        bq[label] = _try(lambda x=v: (w.set_bq(x), w.value_bq())[1])
    w.set_bq(12345.678)
    bq["12345.678"] = w.value_bq()
    w.set_bq(0.0)
    bq["0"] = [w.value_bq(), w.number.text()]
    return {"counts": counts, "qc": qc, "set_bq": bq}


def collect() -> dict:
    from ..lab.session import ENGINE_VERSION
    return {"engine": ENGINE_VERSION, "C1": c1(), "C2": c2(), "C3": c3(), "C4": c4(), "C5": c5(), "C678": c678()}


def criteria(m: dict, b: dict) -> list[dict]:
    r1 = m["C1"]
    exact = (r1["edited"] == [["Cs-137", 2000.0, 40.0, None, None]] and r1["edited_then_kBq"] == [["Cs-137", 2000.0, 40.0, None, None]]
             and r1["round_trip"] == [["Cs-137", 12345.678, 246.91356, None, None]])
    r2 = m["C2"]
    bad2 = [k for k, v in r2.items() if k != "typed valid" and not _refused(v)]
    c2_ok = not bad2 and r2["typed valid"] == b["C2"]["typed valid"] and not _refused(r2["typed valid"])
    r3 = m["C3"]
    bad3 = [k for k in CSV_BAD if not _refused(r3[k])]
    c3_ok = not bad3 and r3["good"] == b["C3"]["good"] and not _refused(r3["good"])
    r4 = m["C4"]
    bad4 = [k for k in LINE_BAD if not _refused(r4[k])]
    c4_ok = not bad4 and r4["good"] == b["C4"]["good"] and bool(r4["good"]) and not _refused(r4["good"])
    r5 = m["C5"]
    bad5 = [f"{k}/{f}" for k, v in r5.items() if k != "clean" for f, x in v.items() if not _refused(x)]
    c5_ok = not bad5 and r5["clean"] == b["C5"]["clean"]
    q = m["C678"]
    bad6 = [t for t, v in q["counts"]["bad"].items() if not _refused(v)]
    c6_ok = not bad6 and q["counts"]["good"] == b["C678"]["counts"]["good"]
    qc = q["qc"]
    bad7 = [t for t, v in qc["bad"].items() if not _refused(v)]
    read_ok = [t for (t, got), (_t, exp) in zip(qc["read"], QC_READ) if got == exp]
    c7_ok = (not bad7 and len(read_ok) == len(QC_READ) and all(_refused(v) for v in qc["refused"].values()))
    sb = q["set_bq"]
    c8_ok = (all(_refused(sb[k]) for k in ("inf", "nan", "-inf")) and sb["12345.678"] == 12345.678
             and sb["0"] == b["C678"]["set_bq"]["0"])
    return [
        {"id": "RC.C1", "pass": exact, "value": f"edited {r1['edited']}; then kBq {r1['edited_then_kBq']}; "
                                                f"round trip {r1['round_trip']}"},
        {"id": "RC.C2", "pass": c2_ok, "value": f"refused {len(CERT_BAD) - len(bad2)} of {len(CERT_BAD)} (not: {bad2}); "
                                                f"typed valid row {r2['typed valid']}"},
        {"id": "RC.C3", "pass": c3_ok, "value": f"refused {len(CSV_BAD) - len(bad3)} of {len(CSV_BAD)} (not: {bad3}); "
                                                f"valid file as before: {r3['good'] == b['C3']['good']}"},
        {"id": "RC.C4", "pass": c4_ok, "value": f"refused {len(LINE_BAD) - len(bad4)} of {len(LINE_BAD)} (not: {bad4}); "
                                                f"valid line as before: {r4['good'] == b['C4']['good']}"},
        {"id": "RC.C5", "pass": c5_ok, "value": f"not refused: {bad5}; clean spectrum as before: "
                                                f"{r5['clean'] == b['C5']['clean']}"},
        {"id": "RC.C6", "pass": c6_ok, "value": f"refused {len(COUNTS_BAD) - len(bad6)} of {len(COUNTS_BAD)}; "
                                                f"valid text {q['counts']['good']}"},
        {"id": "RC.C7", "pass": c7_ok, "value": f"refused {len(QC_BAD) - len(bad7)} of {len(QC_BAD)}; read as registered "
                                                f"{len(read_ok)} of {len(QC_READ)}; round-5 refusals kept: "
                                                f"{all(_refused(v) for v in qc['refused'].values())}"},
        {"id": "RC.C8", "pass": c8_ok, "value": f"set_bq: {sb}"},
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true", help="write the before values (fixed file)")
    a = ap.parse_args(argv)
    m = collect()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.collect:
        BEFORE_JSON.write_text(json.dumps(m, indent=1, ensure_ascii=False, default=str), encoding="utf-8", newline="\n")
        return 0
    b = json.loads(BEFORE_JSON.read_text(encoding="utf-8"))
    cs = criteria(m, b)
    (OUT / "round6_inputs.json").write_text(json.dumps({"measured": m, "criteria": cs}, indent=1, ensure_ascii=False,
                                                       default=str), encoding="utf-8", newline="\n")
    lines = ["# Round-6 review: input validation", "", "Protocol: `docs/baseline/round6_inputs_protocol.md`.", "",
             "| ID | result | value |", "|---|---|---|"]
    lines += [f"| {c['id']} | {'PASS' if c['pass'] else 'FAIL'} | {c['value']} |" for c in cs]
    (OUT / "round6_inputs.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(", ".join(f"{c['id']}:{'PASS' if c['pass'] else 'FAIL'}" for c in cs))
    return 1 if any(not c["pass"] for c in cs) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Round-5 review, detector acceptance test and activity entry: evaluation harness of
docs/baseline/round5_acceptance_protocol.md (RB.C1-C6; RB.C7 is the benchmark and the test suite).

    python -m spectramaster.validation.round5_acceptance

Writes ``round5_acceptance.json`` and ``round5_acceptance.md`` to docs/baseline/after_R5B.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy.special import ndtr

from ..analysis import detector_test as dt
from ..model import Spectrum

OUT = Path(__file__).resolve().parents[2] / "docs" / "baseline" / "after_R5B"
DA2 = OUT.parent / "after_DA2" / "detector_acceptance.json"
CALS = {"linear": [0.0, 0.5], "quadratic": [0.0, 0.3, 5e-5]}
CUT = 1000
PEAK_KEV = 1332.5           # the protocol's peak energy (BEFORE was recorded with it)
# full spectra, commit 865c1ec (before the change): centroid, FWHM, FWTM (keV), FWTM/FWHM, P/C
BEFORE = {"linear": [1332.5, 2.0290541514755205, 3.697680701578065, 1.8223666918347772, 235.64978197988242],
          "quadratic": [1332.5130274007079, 2.0611789609121796, 3.730729825747318, 1.809998013998879,
                        286.6314956682205]}


def build(coeffs, cut: int = 0, n: int = 6000) -> Spectrum:
    """Gaussian peak (FWHM 2.0 keV, area 1e5) at 1332.5 keV integrated over each channel, continuum
    max(120 - 0.01 i, 0); with `cut`, the first `cut` channels removed and first_channel = cut."""
    i = np.arange(n, dtype=float)
    e = np.polyval(list(coeffs)[::-1], i)
    c = float(np.interp(PEAK_KEV, e, i))
    k = float(np.polyval(np.polyder(np.array(list(coeffs)[::-1])), c))
    s = 2.0 / k / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    y = 1e5 * (ndtr((i + 0.5 - c) / s) - ndtr((i - 0.5 - c) / s)) + np.maximum(120.0 - 0.01 * i, 0.0)
    return Spectrum(counts=list(y[cut:]), energy_coeffs=list(coeffs), live_time=3600.0, real_time=3600.0,
                    first_channel=cut)


def _values(sp) -> list:
    w = dt.peak_width(sp)
    return [w.centroid_kev, w.fwhm_kev, w.fwtm_kev, w.ratio, dt.peak_to_compton(sp)]


def _rel(a, b) -> float:
    return abs(a / b - 1.0) if b else abs(a)


def c1_c2() -> dict:
    out = {}
    for name, co in CALS.items():
        full, cut = _values(build(co)), _values(build(co, CUT))
        out[name] = {"full": full, "cut": cut, "before": BEFORE[name],
                     "cut_vs_full": max(_rel(a, b) for a, b in zip(cut, full)),
                     "full_vs_before": max(_rel(a, b) for a, b in zip(full, BEFORE[name]))}
    return out


def da2() -> dict:
    from . import detector_acceptance as da
    now = da.criteria(da.run())
    rec = json.loads(DA2.read_text(encoding="utf-8"))["criteria"]
    return {"now": now, "recorded": rec, "equal": now == rec}


def c3() -> dict:
    co = CALS["linear"]
    full = dt.peak_to_compton(build(co))
    out = {}
    for kev in (1060.0, 1030.0):
        cut = int(round(kev / co[1]))
        sp = build(co, cut)
        res = dt.acceptance_test(sp)
        out[str(kev)] = {"p_to_c": res.peak_to_compton, "notes": res.notes, "full": full}
    return out


QC_CASES = [("Cs-137=37000", {"Cs-137": 37000.0}), ("Cs-137=37000, Co-60=1 uCi", {"Cs-137": 37000.0, "Co-60": 37000.0}),
            ("Cs-137=1 µCi; Co-60=2 kBq", {"Cs-137": 37000.0, "Co-60": 2000.0}),
            ("Cs-137=1,000 Bq", None), ("Cs-137=1,5 Bq", None), ("Cs-137=1e309", None),
            ("Cs-137=abc", None), ("Cs-137", None)]
PARSE_REFUSED = ["1,000", "1,5 Bq", "1e309", "nan", "inf"]
PARSE_READ = [("37 kBq", 37000.0), ("1uCi", 37000.0), ("1 µCi", 37000.0), (".5e3", 500.0), ("-2 Bq", -2.0)]


def _try(fn, *a):
    try:
        return fn(*a)
    except ValueError:
        return None


def c4_c5() -> dict:
    from ..gui.activity_input import parse_activity
    from ..gui.qc_window import _parse_activity
    qc = [{"text": t, "expected": e, "got": _try(_parse_activity, t)} for t, e in QC_CASES]
    refused = {t: _try(parse_activity, t) for t in PARSE_REFUSED}
    read = [{"text": t, "expected": e, "got": _try(parse_activity, t)} for t, e in PARSE_READ]
    sp = build(CALS["linear"])
    raises = {}
    for label, act, live in (("inf activity", math.inf, 3600.0), ("nan activity", math.nan, 3600.0),
                             ("inf live time", 37000.0, math.inf)):
        sp.live_time = live
        try:
            dt.relative_efficiency(sp, act)
            raises[label] = False
        except ValueError:
            raises[label] = True
    sp.live_time = 3600.0
    return {"qc": qc, "refused": refused, "read": read, "relative_efficiency_raises": raises}


def c6() -> dict:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from ..analysis import efficiency as eff
    from ..gui.efficiency_dialog import CertificateEditor
    _app = QApplication.instance() or QApplication(["round5"])
    ed = CertificateEditor()
    ed.set_certificate([eff.CertNuclide("Cs-137", 12345.678, 246.91356, None)])
    for u in ("Ci", "µCi", "Bq"):
        ed.set_activity_unit(u)
    c = ed.certificate()[0]
    ed.set_activity_unit("kBq")
    ed.cert_table.item(0, 1).setText("2")
    e = ed.certificate()[0]
    return {"round_trip": [c.activity, c.activity_unc], "edited_bq": e.activity}


def criteria(m: dict) -> list[dict]:
    a = m["C1_C2"]
    c1 = all(v["cut_vs_full"] <= 1e-9 for v in a.values())
    c2 = all(v["full_vs_before"] <= 1e-12 for v in a.values()) and m["DA2"]["equal"]
    r3 = m["C3"]
    c3 = (r3["1060.0"]["p_to_c"] is None and any("not fully inside" in n for n in r3["1060.0"]["notes"])
          and r3["1030.0"]["p_to_c"] is not None and _rel(r3["1030.0"]["p_to_c"], r3["1030.0"]["full"]) <= 1e-12)
    q = m["C4_C5"]
    c4 = all(x["got"] == x["expected"] for x in q["qc"])
    c5 = (all(v is None for v in q["refused"].values()) and all(x["got"] == x["expected"] for x in q["read"])
          and all(q["relative_efficiency_raises"].values()))
    r6 = m["C6"]
    exact = [(r6["round_trip"][0], 12345.678), (r6["round_trip"][1], 246.91356), (r6["edited_bq"], 2000.0)]
    c6_ok = all(math.isclose(a, b, rel_tol=0.0, abs_tol=0.0) for a, b in exact)    # exact, as registered
    fmt = lambda k: max(v[k] for v in a.values())   # noqa: E731
    return [
        {"id": "RB.C1", "pass": c1, "value": f"largest relative difference cut / full {fmt('cut_vs_full'):.3g}"},
        {"id": "RB.C2", "pass": c2, "value": f"largest relative difference full / before {fmt('full_vs_before'):.3g}; "
                                             f"DA.C1-C7 equal to after_DA2: {m['DA2']['equal']}"},
        {"id": "RB.C3", "pass": c3, "value": f"from 1060 keV: {r3['1060.0']['p_to_c']}; from 1030 keV: "
                                             f"{r3['1030.0']['p_to_c']} (full {r3['1030.0']['full']})"},
        {"id": "RB.C4", "pass": c4, "value": f"{sum(x['got'] == x['expected'] for x in q['qc'])} of {len(q['qc'])} QC texts as registered"},
        {"id": "RB.C5", "pass": c5, "value": f"refused {sum(v is None for v in q['refused'].values())} of {len(q['refused'])}, "
                                             f"read {sum(x['got'] == x['expected'] for x in q['read'])} of {len(q['read'])}, "
                                             f"relative efficiency refuses {sum(q['relative_efficiency_raises'].values())} of 3"},
        {"id": "RB.C6", "pass": c6_ok, "value": f"round trip {r6['round_trip']}, edited {r6['edited_bq']} Bq"},
    ]


def run() -> dict:
    return {"C1_C2": c1_c2(), "DA2": {"equal": da2()["equal"]}, "C3": c3(), "C4_C5": c4_c5(), "C6": c6()}


def main(argv=None) -> int:
    m = run()
    cs = criteria(m)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "round5_acceptance.json").write_text(json.dumps({"measured": m, "criteria": cs}, indent=1, default=str),
                                                encoding="utf-8", newline="\n")
    lines = ["# Round-5 review: detector acceptance test and activity entry", "",
             "Protocol: `docs/baseline/round5_acceptance_protocol.md`.", "",
             "| ID | result | value |", "|---|---|---|"]
    lines += [f"| {c['id']} | {'PASS' if c['pass'] else 'FAIL'} | {c['value']} |" for c in cs]
    lines += ["", "## Measured", "", "```", json.dumps(m, indent=1, default=str, ensure_ascii=False), "```", ""]
    (OUT / "round5_acceptance.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(json.dumps(cs))
    return 1 if any(not c["pass"] for c in cs) else 0


if __name__ == "__main__":
    sys.exit(main())

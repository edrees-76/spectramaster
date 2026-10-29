"""Round-7 review, Gemini H2: background spectrum shared by the sample and its reagent blank
(docs/baseline/round7_shared_background_protocol.md).

    python -m spectramaster.validation.round7_shared_background [--collect]

Synthetic data only.  ``--collect`` writes the observations only, to
``docs/baseline/after_R7C/round7_shared_background_before.json`` (the "before" values); without it
the criteria are evaluated against that file.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys

import numpy as np

from spectramaster.analysis import activity as act
from spectramaster.validation import round5_combined as r5
from spectramaster.validation.benchmark import _flat_curve
from spectramaster.validation.synthetic import HPGE, Continuum, TruePeak, make_spectrum

OUT = r5.OUT.parent / "after_R7C"
BEFORE_JSON = OUT / "round7_shared_background_before.json"
E = 661.657
CONT = Continuum(flat=20.0)
LIVE = 1000.0
BKG_AREA, BLANK_AREA = 1500.0, 2000.0
N_MC = 400
REL = 1e-9
INDEP_NOTE = "counted as independent"
# 99 % sampling limits of 400 realisations (protocol, Criteria)
RATIO = (0.88, 1.12)
FALSE = (0.022, 0.078)
COV1, COV2 = (0.623, 0.743), (0.927, 0.981)

# (name, background mode or None (no background spectrum), sample's net counts)
MC = (("peak_null", "peak", 0.0), ("spectrum_null", "spectrum", 0.0),
      ("peak_net", "peak", 3000.0), ("spectrum_net", "spectrum", 3000.0), ("no_bkg_null", None, 0.0))


def _spec(area, seed, live=LIVE):
    return make_spectrum(HPGE, [TruePeak(E, area)], CONT, seed, live_time=live).spectrum


def _opt(mode):
    return act.ActivityOptions(nuclides=["Cs-137"], bkg_mode=mode or "peak")


def _mc(mode, s_net) -> dict:
    curve = _flat_curve()
    o = _opt(mode)
    rows = []
    for i in range(N_MC):
        bkg = _spec(BKG_AREA, 10_000 + i) if mode else None
        blk = _spec(BLANK_AREA, 20_000 + i)
        smp = _spec(BLANK_AREA + s_net, 30_000 + i)
        qb = act.compute_activities(blk, curve, o, background=bkg)
        ln = act.compute_activities(smp, curve, o, background=bkg, blank=qb).nuclides[0].lines[0]
        rows.append([ln.primary_net, ln.primary_net_unc, bool(ln.detected), ln.lc_counts])
    return {"true": s_net, "rows": rows}


def _stats(c) -> dict:
    net = np.array([r[0] for r in c["rows"]], dtype=float)
    u = np.array([r[1] for r in c["rows"]], dtype=float)
    z = (net - c["true"]) / u
    sd = float(net.std(ddof=1))
    return {"ratio": float(u.mean()) / sd, "detected": float(np.mean([r[2] for r in c["rows"]])),
            "cov1": float(np.mean(np.abs(z) <= 1.0)), "cov2": float(np.mean(np.abs(z) <= 2.0)),
            "lc_ratio": float(np.mean([r[3] for r in c["rows"]])) / (1.645 * sd)}


def _identity(mode) -> dict:
    """RC.C1: the blank is the sample's own spectrum; u_s and its background part u_B from the
    sample alone, the background part rebuilt with the sample fit's estimator."""
    from spectramaster.analysis.background import BackgroundFitter, net_spectrum
    from spectramaster.analysis.efficiency import match_peak
    from spectramaster.analysis.peaks import FitReport, find_peaks
    curve = _flat_curve()
    o = _opt(mode)
    bkg, smp = _spec(BKG_AREA, 10_000), _spec(BLANK_AREA + 3000.0, 30_000)
    blk = dataclasses.replace(smp, sample_id="blank copy")
    alone = act.compute_activities(smp, curve, o, background=bkg).nuclides[0].lines[0]
    qb = act.compute_activities(blk, curve, o, background=bkg)
    ln = act.compute_activities(smp, curve, o, background=bkg, blank=qb).nuclides[0].lines[0]
    work, var, _k = net_spectrum(smp, bkg)
    rep = FitReport()
    peaks = find_peaks(work, min_sig=o.min_sig, variance=var, report=rep)
    p = match_peak(peaks, E)
    u_b = BackgroundFitter(smp, bkg).under_peaks(peaks, rep)[id(p)][1] * alone.activity / alone.net_area
    return {"net": ln.activity, "u": ln.u_count_bq, "u_s": alone.u_count_bq, "u_B": u_b}


def _line_dict(ln) -> dict:
    return dataclasses.asdict(ln)


def _controls() -> dict:
    from spectramaster.lab.session import quant_to_dict
    curve = _flat_curve()
    out = {}
    smp, bkg = _spec(BLANK_AREA + 3000.0, 30_000), _spec(BKG_AREA, 10_000)
    for mode in ("peak", "spectrum"):
        q = act.compute_activities(smp, curve, _opt(mode), background=bkg)
        out[f"no_blank_{mode}"] = {"lines": [_line_dict(l) for l in q.nuclides[0].lines], "notes": q.notes}
    q = act.compute_activities(smp, curve, _opt(None))
    out["no_blank_no_bkg"] = {"lines": [_line_dict(l) for l in q.nuclides[0].lines], "notes": q.notes}
    o = _opt("peak")
    qb = act.compute_activities(_spec(BLANK_AREA, 20_000), curve, o, background=bkg)
    loaded = act.QuantResults.from_dict(quant_to_dict(qb))
    q = act.compute_activities(smp, curve, o, background=bkg, blank=loaded)
    ln = q.nuclides[0].lines[0]
    out["loaded_blank"] = {"u_count": ln.u_count_bq, "notes": q.notes}
    return out


def collect() -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    return {"engine": ENGINE_VERSION, "mc": {name: _mc(mode, s) for name, mode, s in MC},
            "identity": {m: _identity(m) for m in ("peak", "spectrum")}, "controls": _controls()}


def _in(x, lim) -> bool:
    return lim[0] <= x <= lim[1]


def _same(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def criteria(res: dict, before: dict) -> dict:
    out = {}
    vals, ok = [], True
    for m, c in res["identity"].items():
        want = math.sqrt(max(2.0 * (c["u_s"] ** 2 - c["u_B"] ** 2), 0.0))
        good = abs(c["net"]) < 1e-9 * c["u_s"] and math.isclose(c["u"], want, rel_tol=REL)
        ok &= good
        vals.append(f"{m}: u {c['u']:.6g} Bq, expected {want:.6g} Bq")
    out["RC.C1"] = {"value": "; ".join(vals), "pass": ok}
    st = {k: _stats(c) for k, c in res["mc"].items()}
    sb = {k: _stats(c) for k, c in before["mc"].items()}
    vals, ok = [], True
    for k in ("peak_null", "spectrum_null"):
        ok &= _in(st[k]["ratio"], RATIO) and _in(st[k]["detected"], FALSE)
        vals.append(f"{k}: ratio {st[k]['ratio']:.3f} (before {sb[k]['ratio']:.3f}), detected "
                    f"{st[k]['detected']:.4f} (before {sb[k]['detected']:.4f})")
    out["RC.C2"] = {"value": "; ".join(vals), "pass": ok}
    vals, ok = [], True
    for k in ("peak_net", "spectrum_net"):
        ok &= _in(st[k]["ratio"], RATIO) and _in(st[k]["cov1"], COV1) and _in(st[k]["cov2"], COV2)
        vals.append(f"{k}: ratio {st[k]['ratio']:.3f} (before {sb[k]['ratio']:.3f}), |z|<=1 {st[k]['cov1']:.4f}, "
                    f"|z|<=2 {st[k]['cov2']:.4f}")
    out["RC.C3"] = {"value": "; ".join(vals), "pass": ok}
    k = "no_bkg_null"
    same_u = [r[1] for r in res["mc"][k]["rows"]] == [r[1] for r in before["mc"][k]["rows"]]
    out["RC.C4"] = {"value": f"detected {st[k]['detected']:.4f} (before {sb[k]['detected']:.4f}), L_C / (1.645 sd) "
                             f"{st[k]['lc_ratio']:.3f} (before {sb[k]['lc_ratio']:.3f}), u_count "
                             f"{'identical' if same_u else 'changed'}",
                    "pass": _in(st[k]["detected"], FALSE) and same_u}
    bad = []
    for name, c in res["controls"].items():
        b = before["controls"][name]
        if name == "loaded_blank":
            if c["u_count"] != b["u_count"]:
                bad.append("loaded blank: u_count changed")
            if not any(INDEP_NOTE in n for n in c["notes"]):
                bad.append("loaded blank: no note")
            continue
        # the fields saved before the change; a new field is not a change of the results
        lines = [{f: l[f] for f in bl} for l, bl in zip(c["lines"], b["lines"])]
        if not (_same(lines, b["lines"]) and _same(c["notes"], b["notes"])):
            bad.append(name)
    out["RC.C5"] = {"value": "; ".join(bad) or "no blank identical to before; loaded blank unchanged, noted",
                    "pass": not bad}
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
    (OUT / "round7_shared_background.json").write_text(json.dumps({"results": res, "criteria": crit}, indent=1,
                                                                  ensure_ascii=False), encoding="utf-8")
    lines = ["# Round-7 background shared by the sample and its blank (Gemini H2)", "", f"engine {res['engine']}", "",
             "| ID | value | result |", "|---|---|---|"]
    lines += [f"| {k} | {v['value']} | {'PASS' if v['pass'] else 'FAIL'} |" for k, v in crit.items()]
    (OUT / "round7_shared_background.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(v["pass"] for v in crit.values())
    print("\n".join(lines))
    print(f"{n} PASS / {len(crit) - n} FAIL")
    return 0 if n == len(crit) else 1


if __name__ == "__main__":
    sys.exit(main())

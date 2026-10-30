"""Round-8 review, Gemini H2: the detection limits of a line without a sample peak in the peak
background mode (docs/baseline/round8_peak_mode_protocol.md).

    python -m spectramaster.validation.round8_peak_mode [--collect] [--rerun]

Synthetic data only.  ``--collect`` writes the observations only, to
``docs/baseline/after_R8B/round8_peak_mode_before.json`` (the "before" values); without it the
criteria are evaluated against that file.  ``--rerun`` writes the results to RERUN (in the
temporary folder) instead of ``after_R8B``, which a re-run then leaves as committed.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

from spectramaster.analysis import activity as act
from spectramaster.analysis.background import BackgroundFitter
from spectramaster.analysis.peaks import checked_fwhm_model
from spectramaster.validation import primary as pr
from spectramaster.validation import round5_combined as r5
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE, NAI, Continuum, TruePeak, continuum_counts, make_spectrum

OUT = r5.OUT.parent / "after_R8B"
BEFORE_JSON = OUT / "round8_peak_mode_before.json"
RERUN = Path(tempfile.gettempdir()) / "spectramaster_round8_peak_mode"
METHODS = ("currie", "iso11929")
MODES = ("peak", "spectrum")
CS = 661.657
FLAT = Continuum(flat=20.0)
LIVE = 1000.0
REL = 1e-9
N_MC = 400
# 99 % sampling limits: false-detection fraction of about 400 null results at 5 %, and the ratio of
# the mean decision threshold to k_alpha times the standard deviation of the result (1 +- 2.576 /
# sqrt(2 (n - 1)))
FALSE = (0.022, 0.078)
LC_RATIO = (0.909, 1.091)
BLANK_NET = 2000.0           # the blank's own Cs-137 counts above the background's
# (name, kind, background's Cs-137 peak area, the sample's own Cs-137 counts, with a blank sharing
# the background); kind "flat": HPGe flat continuum, the sample and the blank counting the
# background's Cs-137 peak; "nai": NaI base continuum with the Co-60 peaks in the sample (seed 7)
# and the background (seed 8), Cs-137 and Co-60 asked
CASES = (("hpge_bkg1500", "flat", 1500.0, 0.0, False), ("hpge_bkg20000", "flat", 20000.0, 0.0, False),
         ("hpge_nobkgpeak", "flat", 0.0, 0.0, False), ("hpge_bkg1500_blank", "flat", 1500.0, 0.0, True),
         ("hpge_sample_peak", "flat", 1500.0, 3000.0, False), ("nai_co60", "nai", 0.0, 0.0, False))
MC = (("mc_bkg1500", 1500.0), ("mc_bkg20000", 20000.0))


def _flat(area, seed):
    return make_spectrum(HPGE, [TruePeak(CS, area)] if area else [], FLAT, seed, live_time=LIVE).spectrum


def _nai(seed):
    cont = scenarios.base_continuum(NAI)
    return make_spectrum(NAI, pr._co60(NAI, continuum_counts(NAI, cont)), cont, seed).spectrum


def _spectra(kind, area, extra, blank):
    """(sample, background, blank spectrum or None)."""
    if kind == "nai":
        return _nai(7), _nai(8), None
    return (_flat(area + extra, 30_000), _flat(area, 10_000),
            _flat(area + BLANK_NET, 20_000) if blank else None)


def _line(ln) -> dict:
    d = dataclasses.asdict(ln)
    return {k: v for k, v in d.items() if not k.startswith("_")}


def _case(kind, area, extra, blank, mode, mda_method) -> dict:
    curve = pr._flat_curve()
    s, b, bl = _spectra(kind, area, extra, blank)
    nucl = ["Cs-137", "Co-60"] if kind == "nai" else ["Cs-137"]
    opt = act.ActivityOptions(nuclides=nucl, bkg_mode=mode, mda_method=mda_method)
    qb = act.compute_activities(bl, curve, opt, background=b) if bl is not None else None
    res = act.compute_activities(s, curve, opt, background=b, blank=qb)
    return {"lines": [_line(ln) for nr in res.nuclides for ln in nr.lines],
            "nuclides": [{k: v for k, v in dataclasses.asdict(nr).items() if k != "lines"} for nr in res.nuclides],
            "notes": list(res.notes)}


def _mc(area) -> dict:
    curve = pr._flat_curve()
    opt = act.ActivityOptions(nuclides=["Cs-137"], bkg_mode="peak")
    rows = []
    for i in range(N_MC):
        ln = act.compute_activities(_flat(area, 30_000 + i), curve, opt,
                                    background=_flat(area, 10_000 + i)).nuclides[0].lines[0]
        rows.append([bool(ln.peak_found), ln.primary_method, ln.primary, ln.decision_threshold])
    return {"rows": rows}


def collect() -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    cases = {f"{name}_{mode}_{m}": _case(kind, area, extra, blank, mode, m)
             for name, kind, area, extra, blank in CASES for mode in MODES for m in METHODS}
    return {"engine": ENGINE_VERSION, "cases": cases, "mc": {name: _mc(area) for name, area in MC}}


def _same(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _window_sigma0_sq(kind, area, extra, blank, ln) -> tuple[float, str]:
    """The registered sigma0^2 (window counts) of a peak-mode line without a sample peak, from the
    window estimator of its primary result on the sample and on the background fitter's counts."""
    s, b, _bl = _spectra(kind, area, extra, blank)
    fw_ch, _src = checked_fwhm_model(s, np.maximum(np.asarray(s.counts, dtype=float), 0.0))
    bf = BackgroundFitter(s, b)
    e = ln["energy"]
    lo, hi, m, fwin = act.line_window(s, e, fw_ch)
    bs, n, mm, _f = act.continuum_under(s, e, fw_ch)
    if ln["window_continuum"] == "quadratic":
        y, yb = np.asarray(s.counts, dtype=float), bf.b
        q, qb = act.quadratic_window(y, lo, hi, m), act.quadratic_window(yb, lo, hi, m)
        gb = float(yb[lo:hi + 1].sum())
        v = (max(q.b, 0.0) + q.var_fit + bf.k * max(gb - qb.b, 0.0)
             + bf.k ** 2 * (max(gb, 0.0) + qb.var_data))
    else:
        bw0, bw1 = act.window_net(s, e, fw_ch, counts=bf.b)
        v = bs * (1.0 + n / (2.0 * mm)) + bf.k * max(bw0, 0.0) + bf.k ** 2 * bw1
    if ln["blank_activity"] is not None:
        w = ln["limit_slope"] * fwin
        v += (ln["blank_unc"] * fwin / w) ** 2 + max(ln["blank_activity"], 0.0) * fwin / w
        v -= 2.0 * ln["blank_bkg_cov"] * (fwin / w) ** 2
    return v, ln["window_continuum"]


def _no_peak_window(ln) -> bool:
    return not ln["peak_found"] and ln["primary_method"] == "window"


def criteria(res: dict, before: dict) -> dict:
    out = {}
    spec = {name: (kind, area, extra, blank) for name, kind, area, extra, blank in CASES}
    vals, ok, n, nq = [], True, 0, 0
    for name in spec:
        for m in METHODS:
            c = res["cases"][f"{name}_peak_{m}"]
            for ln in c["lines"]:
                if not _no_peak_window(ln):
                    continue
                v, cont = _window_sigma0_sq(*spec[name], ln)
                lc = act.K_DEFAULT * math.sqrt(max(v, 0.0))
                good = math.isclose(ln["lc_counts"], lc, rel_tol=REL)
                ok &= good
                n += 1
                nq += cont == "quadratic"
                vals.append(f"{name} {m} {ln['energy']:.1f} keV ({cont}): L_C {ln['lc_counts']:.5g} vs {lc:.5g} counts")
    out["RB8.C1"] = {"value": "; ".join(vals), "pass": ok and n > 0 and nq > 0}
    vals, ok = [], True
    for name in spec:
        for m in METHODS:
            c, b = res["cases"][f"{name}_peak_{m}"], before["cases"][f"{name}_peak_{m}"]
            for ln, lb in zip(c["lines"], b["lines"]):
                if not _no_peak_window(ln):
                    continue
                keys = [k for k in lb if k not in ("lc_counts", "ld_counts", "decision_threshold", "mda",
                                                   "window_lc_counts", "window_decision_threshold", "note",
                                                   "limit_slope")]
                if not _same({k: ln[k] for k in keys}, {k: lb[k] for k in keys}):
                    ok = False
                    vals.append(f"{name} {m} {ln['energy']:.1f} keV changed")
    out["RB8.C2"] = {"value": "; ".join(vals) or "primary result, its uncertainty, method and every other line "
                     "field identical to before", "pass": ok}
    bad = []
    for key, c in res["cases"].items():
        b = before["cases"][key]
        if "_peak_" in key:
            lines = [(ln, lb) for ln, lb in zip(c["lines"], b["lines"]) if not _no_peak_window(lb)]
            if not all(_same(ln, lb) for ln, lb in lines):
                bad.append(f"{key} lines with a peak or not usable")
        elif not _same(c, b):
            bad.append(key)
    out["RB8.C3"] = {"value": "; ".join(bad) or "spectrum mode, and the peak-mode lines with a sample peak or "
                     "without a usable window result, identical to before", "pass": not bad}
    vals, ok = [], True
    for name, _area in MC:
        rows = [r for r in res["mc"][name]["rows"] if not r[0] and r[1] == "window"]
        prim = np.array([r[2] for r in rows])
        dt = np.array([r[3] for r in rows])
        false = float(np.mean(prim > dt))
        ratio = float(dt.mean()) / (act.K_DEFAULT * float(prim.std(ddof=1)))
        ok &= FALSE[0] <= false <= FALSE[1] and LC_RATIO[0] <= ratio <= LC_RATIO[1]
        vals.append(f"{name}: {len(rows)} results without a peak, false detections {false:.4f}, "
                    f"threshold ratio {ratio:.4f}")
    out["RB8.C4"] = {"value": "; ".join(vals), "pass": ok}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--collect", action="store_true", help="write the observations only (the 'before' values)")
    ap.add_argument("--rerun", action="store_true", help=f"write the results to {RERUN}, not after_R8B")
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
    (out / "round8_peak_mode.json").write_text(json.dumps({"results": res, "criteria": crit}, indent=1,
                                                         ensure_ascii=False), encoding="utf-8")
    lines = ["# Round-8 limits of a line without a sample peak, peak background mode (Gemini H2)",
             "", f"engine {res['engine']}", "", "| ID | value | result |", "|---|---|---|"]
    lines += [f"| {k} | {v['value']} | {'PASS' if v['pass'] else 'FAIL'} |" for k, v in crit.items()]
    (out / "round8_peak_mode.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(v["pass"] for v in crit.values())
    print("\n".join(lines))
    print(f"{n} PASS / {len(crit) - n} FAIL")
    return 0 if n == len(crit) else 1


if __name__ == "__main__":
    sys.exit(main())

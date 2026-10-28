"""Round-6 review, Gemini M3: the channel binning bias of the acceptance test's FWHM and FWTM, noted
and not corrected (docs/baseline/round6_fwhm_protocol.md).

    python -m spectramaster.validation.round6_fwhm [--collect]

Synthetic data only.  ``--collect`` writes the observations only, to
``docs/baseline/after_R6G/round6_fwhm_before.json`` (the "before" values); without it the criteria
are evaluated against that file.
"""
from __future__ import annotations

import argparse
import json
import math
import sys

import numpy as np
from scipy.special import ndtr

from spectramaster.analysis import detector_test as dt
from spectramaster.model import Spectrum
from spectramaster.validation import round5_acceptance as r5

OUT = r5.OUT.parent / "after_R6G"
BEFORE_JSON = OUT / "round6_fwhm_before.json"
KEV_PER_CH, CENTRE = 0.5, 2665.0
WIDTHS = (3.0, 3.5, 4.0, 5.0, 6.0, 7.0)          # FWHM in channels where the range is checked
WIDE = (12.0,)                                   # no note expected
FRACS = (0.0, 0.1, 0.25, 0.4, 0.5)               # centroid offset within a channel
TENTH = math.sqrt(math.log(10.0) / math.log(2.0))    # FWTM / FWHM of a Gaussian
TOL_PP = 0.05                                    # percentage points


def build(fw_ch: float, frac: float, n: int = 6000) -> Spectrum:
    """Gaussian peak (area 1e5, FWHM `fw_ch` channels) at 1332.5 keV + frac channel, integrated over
    each channel, on the continuum of round5_acceptance, 0.5 keV per channel."""
    i = np.arange(n, dtype=float)
    c = CENTRE + frac
    s = fw_ch / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    y = 1e5 * (ndtr((i + 0.5 - c) / s) - ndtr((i - 0.5 - c) / s)) + np.maximum(120.0 - 0.01 * i, 0.0)
    return Spectrum(counts=list(y), energy_coeffs=[1332.5 - KEV_PER_CH * CENTRE, KEV_PER_CH],
                    live_time=3600.0, real_time=3600.0)


def _row(w) -> dict:
    return {"centroid_kev": w.centroid_kev, "fwhm_kev": w.fwhm_kev, "fwtm_kev": w.fwtm_kev, "note": w.note,
            "fwhm_bin_bias": getattr(w, "fwhm_bin_bias", None), "fwtm_bin_bias": getattr(w, "fwtm_bin_bias", None)}


def collect() -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    out = {"engine": ENGINE_VERSION, "cases": {}, "round5": {}}
    for fw in WIDTHS + WIDE:
        for f in FRACS:
            sp = build(fw, f)
            out["cases"][f"{fw:g} ch, +{f:g}"] = {"fw_ch": fw, "frac": f, **_row(dt.peak_width(sp)),
                                                   "p_c": dt.peak_to_compton(sp)}
    for name, co in r5.CALS.items():
        sp = r5.build(co)
        a = dt.acceptance_test(sp)
        out["round5"][name] = {**_row(a.width_1332), "p_c": a.peak_to_compton, "notes": list(a.notes)}
    return out


def _inside(x: float, rng) -> bool:
    return rng is not None and min(rng) - TOL_PP / 100 <= x <= max(rng) + TOL_PP / 100


def criteria(res: dict, before: dict) -> dict:
    out = {}
    bad1, bad2, worst = [], [], 0.0
    for k, c in res["cases"].items():
        if c["fw_ch"] not in WIDTHS:
            continue
        b_h = c["fwhm_kev"] / (c["fw_ch"] * KEV_PER_CH) - 1.0
        b_t = c["fwtm_kev"] / (c["fw_ch"] * KEV_PER_CH * TENTH) - 1.0
        if not _inside(b_h, c["fwhm_bin_bias"]):
            bad1.append(f"{k}: {100 * b_h:.2f} % vs {c['fwhm_bin_bias']}")
        if not _inside(b_t, c["fwtm_bin_bias"]):
            bad2.append(f"{k}: {100 * b_t:.2f} % vs {c['fwtm_bin_bias']}")
        worst = max(worst, b_h)
    out["RG.C1"] = {"value": "; ".join(bad1) or f"measured FWHM overestimates (up to {100 * worst:.2f} %) inside the "
                                                 "stated range for every case", "pass": not bad1}
    out["RG.C2"] = {"value": "; ".join(bad2) or "measured FWTM overestimates inside the stated range for every case",
                    "pass": not bad2}
    bad3 = []
    for k, c in res["cases"].items():
        hi = max(c["fwhm_bin_bias"]) if c["fwhm_bin_bias"] else None
        noted = "channel binning" in (c["note"] or "")
        if hi is None or noted != (hi >= dt.BIN_NOTE_BIAS):
            bad3.append(f"{k}: bias {c['fwhm_bin_bias']}, noted {noted}")
        if c["fw_ch"] in WIDE and noted:
            bad3.append(f"{k}: noted at {c['fw_ch']:g} channels")
    for name, c in res["round5"].items():
        if not any("channel binning" in n for n in c["notes"]):
            bad3.append(f"round5 {name}: not in the acceptance notes")
    out["RG.C3"] = {"value": "; ".join(bad3) or "note present exactly when the upper bound is >= 1 %, also in the "
                                                 "acceptance test notes; absent at 12 channels", "pass": not bad3}
    keys = ("centroid_kev", "fwhm_kev", "fwtm_kev", "p_c")
    bad4 = [k for k, c in res["cases"].items() if [c[x] for x in keys] != [before["cases"][k][x] for x in keys]]
    bad4 += [f"round5 {n}" for n, c in res["round5"].items()
             if [c[x] for x in keys] != [before["round5"][n][x] for x in keys]]
    bad4 += [f"round5 {n} vs recorded" for n, c in res["round5"].items()
             if [c["centroid_kev"], c["fwhm_kev"], c["fwtm_kev"]] != r5.BEFORE[n][:3]]
    out["RG.C4"] = {"value": "; ".join(bad4) or "centroids, FWHM, FWTM and P/C identical to before", "pass": not bad4}
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
    (OUT / "round6_fwhm.json").write_text(json.dumps({"results": res, "criteria": crit}, indent=1,
                                                     ensure_ascii=False), encoding="utf-8")
    lines = ["# Round-6 FWHM binning note (Gemini M3)", "", f"engine {res['engine']}", "",
             "| ID | value | result |", "|---|---|---|"]
    lines += [f"| {k} | {v['value']} | {'PASS' if v['pass'] else 'FAIL'} |" for k, v in crit.items()]
    (OUT / "round6_fwhm.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(v["pass"] for v in crit.values())
    print("\n".join(lines))
    print(f"{n} PASS / {len(crit) - n} FAIL")
    return 0 if n == len(crit) else 1


if __name__ == "__main__":
    sys.exit(main())

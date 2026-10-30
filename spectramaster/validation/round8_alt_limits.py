"""Round-8 review, Codex H1 / Gemini H1: the limits of a nuclide whose primary result comes from
another line than its key line (docs/baseline/round8_alt_limits_protocol.md).

    python -m spectramaster.validation.round8_alt_limits [--collect] [--rerun]

Synthetic data only.  ``--collect`` writes the observations only, to
``docs/baseline/after_R8A/round8_alt_limits_before.json`` (the "before" values); without it the
criteria are evaluated against that file.  ``--rerun`` writes the results to RERUN (in the
temporary folder) instead of ``after_R8A``, which a re-run then leaves as committed.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
import tempfile
from pathlib import Path

from spectramaster.analysis import activity as act
from spectramaster.validation import compare
from spectramaster.validation import primary as pr
from spectramaster.validation import round5_combined as r5
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE, NAI, Continuum, TruePeak, area_for_snr, continuum_counts, make_spectrum

OUT = r5.OUT.parent / "after_R8A"
BEFORE_JSON = OUT / "round8_alt_limits_before.json"
RERUN = Path(tempfile.gettempdir()) / "spectramaster_round8_alt_limits"
METHODS = ("currie", "iso11929")
NUCLIDE_LIMITS = ("decision_threshold", "mda", "specific_mda")
# (name, detector, spectrum, seed, combination method); spectrum: ("peak", keV) an interfering peak
# (SNR 30) on the base continuum, ("edge", keV of the line whose Compton edge is added, level)
CASES = (("hpge_int_s0_key", HPGE, ("peak", 1176.5), 0, "key"),
         ("hpge_int_s0_mean", HPGE, ("peak", 1176.5), 0, "mean"),
         ("hpge_int_s1_key", HPGE, ("peak", 1176.5), 1, "key"),
         ("hpge_edge_key", HPGE, ("edge", 1390.0, 40.0), 0, "key"),
         ("nai_curved_key", NAI, ("edge", 1550.0, 40.0), 0, "key"),
         ("hpge_ctrl_s0_key", HPGE, ("peak", 1180.0), 0, "key"),
         ("hpge_ctrl_s0_mean", HPGE, ("peak", 1180.0), 0, "mean"),
         ("hpge_plain_key", HPGE, ("none",), 3, "key"),
         ("nai_co60_key", NAI, ("co60",), 7, "key"))
SUBSTITUTED = ("hpge_int_s0_key", "hpge_int_s0_mean", "hpge_int_s1_key", "hpge_edge_key")
UNUSABLE = ("nai_curved_key",)
QUANTITY = 0.5                  # kg: the specific MDA follows the MDA


def _spectrum(det, kind, seed):
    base = scenarios.base_continuum(det)
    if kind[0] == "edge":
        k = det.gain_kev / 0.5
        cont = Continuum(exp_amp=base.exp_amp, exp_scale_kev=base.exp_scale_kev, flat=base.flat,
                         compton_line_kev=kind[1], compton_level=kind[2] * k)
        return make_spectrum(det, [], cont, seed).spectrum
    cy = continuum_counts(det, base)
    if kind[0] == "peak":
        peaks = [TruePeak(kind[1], area_for_snr(det, cy, kind[1], 30.0), tag="x")]
    elif kind[0] == "co60":
        peaks = pr._co60(det, cy)
    else:
        peaks = []
    return make_spectrum(det, peaks, base, seed).spectrum


def _case(det, kind, seed, method, mda_method) -> dict:
    sp = _spectrum(det, kind, seed)
    opt = act.ActivityOptions(nuclides=["Co-60"], method=method, mda_method=mda_method,
                             quantity=QUANTITY, quantity_unit="kg")
    res = act.compute_activities(sp, pr._flat_curve(), opt)
    nr = res.nuclides[0]
    d = dataclasses.asdict(nr)
    lines = d.pop("lines")
    return {"nuclide": d, "lines": lines, "notes": list(res.notes)}


def collect() -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    cases = {f"{name}_{m}": _case(det, kind, seed, meth, m)
             for name, det, kind, seed, meth in CASES for m in METHODS}
    return {"engine": ENGINE_VERSION, "cases": cases}


def _same(a, b) -> bool:
    """Equal, numbers within relative 1e-12 (round9_harness_protocol.md)."""
    return compare.same(a, b)


def _usable(c) -> list:
    return [l for l in c["lines"] if l["mda"] > 0 and l["primary"] is not None and l["primary_method"] == "window"]


def _key(c) -> dict:
    return [l for l in c["lines"] if l["energy"] == c["nuclide"]["key_energy"]][0]


def _alt(c) -> dict:
    """The line the engine takes the primary result from (key method: the usable line of smallest
    MDA; mean with one usable line: that line)."""
    return min(_usable(c), key=lambda l: l["mda"])


def criteria(res: dict, before: dict) -> dict:
    out = {}
    vals, ok, n = [], True, 0
    for name in SUBSTITUTED:
        for m in METHODS:
            c, b = res["cases"][f"{name}_{m}"], before["cases"][f"{name}_{m}"]
            nr, nb = c["nuclide"], b["nuclide"]
            key, alt = _key(c), _alt(c)
            n += 1
            q = QUANTITY
            good = (key["primary_method"] != "window" and alt is not key and len(_usable(c)) == 1
                    and nr["decision_threshold"] == alt["decision_threshold"] and nr["mda"] == alt["mda"]
                    and nr["specific_mda"] is not None and math.isclose(nr["specific_mda"], alt["mda"] / q, rel_tol=1e-12)
                    and _same([nr[k] for k in ("key_energy", "primary", "primary_u")],
                              [nb[k] for k in ("key_energy", "primary", "primary_u")]) and not nr["detected"]
                    and f"limits from the {alt['energy']:.1f} keV line" in nr["note"])
            ok &= good
            vals.append(f"{name} {m}: threshold {nb['decision_threshold']:.4g} -> {nr['decision_threshold']:.4g} Bq, "
                        f"MDA {nb['mda']:.4g} -> {nr['mda']:.4g} Bq (key {key['energy']:.1f} keV "
                        f"{key['primary_method']} {key['decision_threshold']:.4g} / {key['mda']:.4g}; "
                        f"{alt['energy']:.1f} keV {alt['decision_threshold']:.4g} / {alt['mda']:.4g})")
    out["RA8.C1"] = {"value": "; ".join(vals), "pass": ok and n == len(SUBSTITUTED) * len(METHODS)}
    vals, ok = [], True
    for name in SUBSTITUTED:
        for m in METHODS:
            b = before["cases"][f"{name}_{m}"]
            key = _key(b)
            ok &= (b["nuclide"]["decision_threshold"] == key["decision_threshold"]
                   and b["nuclide"]["mda"] == key["mda"] and key["mda"] != _alt(b)["mda"])
            vals.append(f"{name} {m}: {b['nuclide']['decision_threshold']:.4g} / {b['nuclide']['mda']:.4g} Bq")
    out["RA8.C2"] = {"value": "before, the key line's limits: " + "; ".join(vals), "pass": ok}
    vals, ok = [], True
    for name in UNUSABLE:
        for m in METHODS:
            c, b = res["cases"][f"{name}_{m}"], before["cases"][f"{name}_{m}"]
            ok &= (not _usable(c) and c["nuclide"]["primary_method"] == "curved" and _same(c, b))
            vals.append(f"{name} {m}: {c['nuclide']['primary_method']}, {c['nuclide']['decision_threshold']:.4g} / "
                        f"{c['nuclide']['mda']:.4g} Bq")
    out["RA8.C3"] = {"value": "no usable line, as before: " + "; ".join(vals), "pass": ok}
    bad = []
    for name, c in res["cases"].items():
        b = before["cases"][name]
        sub = name.rsplit("_", 1)[0] in SUBSTITUTED
        if not _same(c["lines"], b["lines"]):
            bad.append(f"{name} lines")
        keys = [k for k in b["nuclide"] if not (sub and (k in NUCLIDE_LIMITS or k == "note"))]
        if not _same({k: c["nuclide"][k] for k in keys}, {k: b["nuclide"][k] for k in keys}):
            bad.append(f"{name} nuclide")
        if not _same(c["notes"], b["notes"]):
            bad.append(f"{name} notes")
    out["RA8.C4"] = {"value": "; ".join(bad) or "every line, every other nuclide field and the notes identical to before",
                     "pass": not bad}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--collect", action="store_true", help="write the observations only (the 'before' values)")
    ap.add_argument("--rerun", action="store_true", help=f"write the results to {RERUN}, not after_R8A")
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
    (out / "round8_alt_limits.json").write_text(json.dumps({"results": res, "criteria": crit}, indent=1,
                                                          ensure_ascii=False), encoding="utf-8")
    lines = ["# Round-8 limits of a nuclide whose primary result comes from another line (Codex H1 / Gemini H1)",
             "", f"engine {res['engine']}", "", "| ID | value | result |", "|---|---|---|"]
    lines += [f"| {k} | {v['value']} | {'PASS' if v['pass'] else 'FAIL'} |" for k, v in crit.items()]
    (out / "round8_alt_limits.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(v["pass"] for v in crit.values())
    print("\n".join(lines))
    print(f"{n} PASS / {len(crit) - n} FAIL")
    return 0 if n == len(crit) else 1


if __name__ == "__main__":
    sys.exit(main())

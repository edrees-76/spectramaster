"""Signed primary result of nuclides not detected (round-4 review, Gemini H2): evaluation harness of
docs/baseline/round4_primary_protocol.md (synthetic HPGe and NaI spectra, fixed seeds).

    python -m spectramaster.validation.round4_primary [--collect]

Writes ``round4_primary.json`` and ``round4_primary.md`` to docs/baseline/after_R4H; ``--collect``
writes the observations before the change to ``round4_primary_before.json`` in the same folder.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from ..analysis.activity import ActivityOptions, compute_activities
from .benchmark import _flat_curve
from .primary import _cs_spectra, _z_stats
from .synthetic import HPGE, NAI, TruePeak, area_for_snr


def _zs(z) -> dict:
    out = _z_stats(z)
    out["n_z"] = out.pop("n")
    return out

OUT = Path(__file__).resolve().parents[2] / "docs" / "baseline" / "after_R4H"
BEFORE_JSON = OUT / "round4_primary_before.json"
N_MEAN, N_KEY = 200, 100
CS134_KEY = 604.721
REL = 1e-9


def _usable(r) -> list:
    return [l for l in r.lines if l.mda > 0 and l.primary is not None and l.primary_method == "window"]


def _weighted_mean(lines, opt: ActivityOptions) -> float:
    """The activity combination's weighted mean (_combine_activity) applied to the window results."""
    ui = opt.intensity_rel_unc
    var = [l.primary_u_count ** 2 + (l.primary * ui) ** 2 + (l.primary * l.int_rel_unc) ** 2 for l in lines]
    wts = [1.0 / v if v > 0 else 0.0 for v in var]
    return sum(w * l.primary for w, l in zip(wts, lines)) / sum(wts)


def _close(a, b) -> bool:
    return a is not None and b is not None and math.isclose(a, b, rel_tol=REL, abs_tol=1e-12)


def mean_set(det, n: int = N_MEAN) -> dict:
    """RH.C1: Ba-133 absent, weighted mean of the usable lines (method "mean")."""
    curve = _flat_curve()
    opt = ActivityOptions(nuclides=["Ba-133"], method="mean", mda_method="iso11929")
    z, exact, multi, best_ok, with_usable, n_usable, methods = [], 0, 0, 0, 0, [], {}
    for sp, _true in _cs_spectra(det, "r4h/ba133", n, lambda cy: []):
        res = compute_activities(sp, curve, opt)
        r = next(x for x in res.nuclides if x.nuclide == "Ba-133")
        use = _usable(r)
        n_usable.append(len(use))
        methods[r.primary_method] = methods.get(r.primary_method, 0) + 1
        if r.primary is not None and r.primary_u:
            z.append(r.primary / r.primary_u)
        if use:
            with_usable += 1
            best_ok += r.best_estimate is not None and r.coverage_low is not None
        if len(use) >= 2 and r.activity is None:      # the change applies to nuclides without an activity
            multi += 1
            exact += _close(r.primary, _weighted_mean(use, opt))
    return {"n": n, **_zs(z), "multi_line": multi, "exact": exact, "with_usable": with_usable,
            "best_present": best_ok, "mean_usable_lines": sum(n_usable) / n if n else 0.0, "methods": methods}


def key_set(det, n: int = N_KEY) -> dict:
    """RH.C2: Cs-134 absent, a strong peak 1 FWHM above the key line."""
    curve = _flat_curve()
    fw = float(det.fwhm_kev(CS134_KEY))
    extra = lambda cy: [TruePeak(CS134_KEY + fw, area_for_snr(det, cy, CS134_KEY + fw, 40.0))]   # noqa: E731
    z, eligible, ok, methods = [], 0, 0, {}
    for sp, _true in _cs_spectra(det, "r4h/cs134", n, extra):
        res = compute_activities(sp, curve, ActivityOptions(nuclides=["Cs-134"], mda_method="iso11929"))
        r = next(x for x in res.nuclides if x.nuclide == "Cs-134")
        methods[r.primary_method] = methods.get(r.primary_method, 0) + 1
        key = next((l for l in r.lines if r.key_energy is not None and abs(l.energy - r.key_energy) < 1e-6), None)
        use = _usable(r)
        if r.activity is not None or key is None or key.primary_method == "window" or not use:
            continue
        eligible += 1
        pick = min(use, key=lambda l: l.mda)
        good = r.primary_method == "window" and _close(r.primary, pick.primary) and r.best_estimate is not None
        ok += good
        if good and r.primary_u:
            z.append(r.primary / r.primary_u)
    return {"n": n, "eligible": eligible, "ok": ok, **_zs(z), "methods": methods}


def collect() -> dict:
    return {"HPGe": {"mean": mean_set(HPGE), "key": key_set(HPGE)}, "NaI": {"mean": mean_set(NAI)}}


def criteria(m: dict) -> list[dict]:
    a, b = m["HPGe"]["mean"], m["HPGe"]["key"]
    c1 = (a["exact"] == a["multi_line"] > 0 and abs(a["mean_z"]) <= 0.2 and 0.91 <= a["cov2"] <= 0.99
          and a["best_present"] == a["with_usable"])
    c2 = (b["eligible"] > 0 and b["ok"] >= 0.9 * b["eligible"] and abs(b["mean_z"]) <= 0.3 and b["cov2"] >= 0.90)
    return [{"id": "RH.C1", "pass": bool(c1),
             "value": f"{a['exact']}/{a['multi_line']} exact; mean z {a['mean_z']:.3f}, cov2 {a['cov2']:.3f} "
                      f"(n {a['n']}); best estimate {a['best_present']}/{a['with_usable']}"},
            {"id": "RH.C2", "pass": bool(c2),
             "value": f"{b['ok']}/{b['eligible']} from the usable line; mean z {b['mean_z']:.3f}, "
                      f"cov2 {b['cov2']:.3f} (n {b['n']})"}]


def report(m: dict, before: dict | None) -> str:
    lines = ["# Round-4 review, signed primary result of nuclides not detected (R4-H2)", "",
             "Protocol: `docs/baseline/round4_primary_protocol.md`.", "",
             "| ID | result | value |", "|---|---|---|"]
    for c in criteria(m):
        lines.append(f"| {c['id']} | {'PASS' if c['pass'] else 'FAIL'} | {c['value']} |")
    lines += ["", "## Measured", "", "```", json.dumps(m, indent=1), "```"]
    if before is not None:
        lines += ["", "## Before the change", "", "```", json.dumps(before, indent=1), "```"]
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--collect", action="store_true", help=f"write the observations before the change to {BEFORE_JSON}")
    a = ap.parse_args(argv)
    m = collect()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.collect:
        BEFORE_JSON.write_text(json.dumps(m, indent=1), encoding="utf-8", newline="\n")
        print(json.dumps(m))
        return 0
    before = json.loads(BEFORE_JSON.read_text(encoding="utf-8")) if BEFORE_JSON.exists() else None
    (OUT / "round4_primary.json").write_text(json.dumps({"measured": m, "criteria": criteria(m)}, indent=1),
                                             encoding="utf-8", newline="\n")
    (OUT / "round4_primary.md").write_text(report(m, before), encoding="utf-8", newline="\n")
    cs = criteria(m)
    print(json.dumps(cs))
    return 1 if any(not c["pass"] for c in cs) else 0


if __name__ == "__main__":
    sys.exit(main())

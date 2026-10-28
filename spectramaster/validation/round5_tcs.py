"""Round-5 review, H5/H6: partial true-coincidence summing corrections
(docs/baseline/round5_tcs_protocol.md, with its second amendment).

    python -m spectramaster.validation.round5_tcs [--collect]

Synthetic data and the bundled coincidence table only.  ``--collect`` writes the raw observations
to ``docs/baseline/after_R5E/round5_tcs_before.json`` (the "before" values); without it the
criteria of the second amendment are evaluated against that file and ``round5_tcs.json`` /
``round5_tcs.md`` are written to ``after_R5E3`` (the earlier runs are kept in ``after_R5E`` and
``after_R5E2``).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from spectramaster.analysis import Peak
from spectramaster.analysis import activity as act
from spectramaster.analysis import coincidence as co
from spectramaster.analysis import efficiency as ef
from spectramaster.model import Spectrum

REPO = Path(__file__).resolve().parents[2]
BEFORE_JSON = REPO / "docs" / "baseline" / "after_R5E" / "round5_tcs_before.json"
OUT = REPO / "docs" / "baseline" / "after_R5E3"
PT = (0.24, 0.0)
GAIN, NCH, LIVE = 0.25, 12000, 20000.0
START = datetime(2024, 3, 1, 10, 0, 0)
BA = {53.1622: 0.0214, 80.9979: 0.329, 276.3989: 0.0716, 302.8508: 0.1834, 356.0129: 0.6205, 383.8485: 0.0894}
EU = {121.7817: 0.2853, 244.6974: 0.0755, 344.2785: 0.2659, 778.904: 0.1293, 964.079: 0.1451,
      1085.837: 0.1011, 1112.076: 0.1367, 1408.013: 0.2087}
E_MINS = (40.0, 122.0)


def _flat(v):
    return lambda e: np.full(np.shape(e), v) if np.ndim(e) else v


def _steep(e):
    """A close geometry: 2 % at 1 MeV, rising to 22 % at 59.5 keV."""
    return 0.02 * (np.clip(np.asarray(e, dtype=float), 59.5, 2000.0) / 1000.0) ** -0.85


def _pt(e):
    return co.peak_to_total(e, *PT)


def _coi_row(c) -> list:
    return [c.factor, c.summing_out, c.summing_in, c.ignored, c.found, c.reason, c.annihilation, c.note,
            getattr(c, "partial", None), getattr(c, "inconsistent", None), getattr(c, "partial_reason", None)]


def _examples() -> dict:
    out = {}
    for em in (50.0, 122.0):
        out[f"Ba-133 356.0129 e_min {em:g}"] = _coi_row(co.coi("Ba-133", 356.0129, _flat(0.02), _flat(0.24),
                                                               e_min=em))
    for e in (880.76, 338.32, 911.204, 968.971, 278.95):
        out[f"Ac-228 {e:g}"] = _coi_row(co.coi("Ac-228", e, _flat(0.02), _flat(0.24), e_min=40.0))
        for cname, curve in (("flat", _flat(0.02)), ("steep", _steep)):
            out[f"inconsistent Ac-228 {e:g} {cname}"] = [
                getattr(co.coi("Ac-228", e, curve, _pt, e_min=40.0), "inconsistent", None),
                _independent_inconsistent("Ac-228", e, curve, 40.0)]
    return out


def _independent_inconsistent(nuc: str, energy: float, eps, e_min: float) -> float:
    """The amendment's measure from the raw table records, without coincidence.coi or Transition."""
    num = den = 0.0
    for rec in co._table()["nuclides"].get(nuc, []):
        g = np.array(rec["g"], dtype=float).reshape(-1, 2)
        e, inten = g[:, 0], g[:, 1]
        k = int(np.argmin(np.abs(e - energy)))
        if abs(e[k] - energy) > co.LINE_TOL_KEV or inten[k] <= 0:
            continue
        w = float(rec["br"]) * inten[k]
        den += w
        if "gs" not in rec:
            continue
        gs = np.array(rec["gs"], dtype=float)
        for hi, lo, p in rec["c"]:
            if int(lo) != k:
                continue
            j = int(hi)
            if e[j] < co.BELOW_CURVE * e_min:
                continue
            ep = float(np.ravel(eps(np.array([e[j]])))[0])
            et = min(ep / float(np.ravel(_pt(np.array([e[j]])))[0]), 1.0)
            num += w * abs(gs[j] * float(p) / gs[k] - inten[j] * float(p) / inten[k]) * et
    return num / den if den else 0.0


def _all_lines() -> dict:
    """Every gamma of every nuclide of the coincidence table, two curves, two lower curve limits."""
    out = {}
    for nuc in sorted(co._table()["nuclides"]):
        energies = sorted({round(float(e), 4) for t in co.transitions(nuc) for e in t.energies})
        for e in energies:
            for em in E_MINS:
                for cname, curve in (("flat", _flat(0.02)), ("steep", _steep)):
                    out[f"{nuc} {e:g} {cname} {em:g}"] = _coi_row(co.coi(nuc, e, curve, _pt, e_min=em))
    return out


def _cal_points(lines: dict, nuc: str) -> list:
    out = []
    for e, inten in lines.items():
        eps = 0.03 * (e / 300.0) ** -0.7
        out.append(ef.EfficiencyPoint(e, eps, 0.01 * eps, nuc, intensity=inten, u_count_rel=0.005, u_ref_rel=0.008))
    return out


def _calibration(warnings: dict | None = None) -> dict:
    ba_high = {e: i for e, i in BA.items() if e > 200}
    cases = {"eu152_ba133_from_121.8": _cal_points(EU, "Eu-152") + _cal_points(ba_high, "Ba-133"),
             "eu152_ba133_from_53.2": _cal_points(EU, "Eu-152") + _cal_points(BA, "Ba-133"),
             "eu152_only": _cal_points(EU, "Eu-152")}
    out = {}
    for name, pts in cases.items():
        curve = ef.fit_efficiency(pts, "loglog", order=2)
        try:
            free = ef.summing_free_curve(curve, _pt, 0.1)
        except ValueError as exc:
            out[name] = {"error": str(exc)}
            continue
        if warnings is not None:
            warnings[name] = list(free.warnings)
        out[name] = {"e_min": free.e_min, "points": [[p.nuclide, p.energy, p.efficiency, p.unc] for p in free.points],
                     "eps_500": float(free.efficiency(500.0)), "note": free.note}
    return out


def _spectrum() -> Spectrum:
    return Spectrum(counts=[40.0] * NCH, live_time=LIVE, real_time=LIVE, start_time=START,
                    energy_coeffs=[0.0, GAIN], sample_id="r5e")


def _peak(e: float, area: float) -> Peak:
    fw = math.sqrt(0.75 + 0.00185 * e)
    u = math.sqrt(area + 800.0)
    return Peak(centroid=e / GAIN, energy=e, fwhm=fw / GAIN, fwhm_kev=fw, net_area=area, net_area_unc=u,
                gross_area=area + 400.0, background=400.0, left=int(e / GAIN - 2 * fw / GAIN),
                right=int(e / GAIN + 2 * fw / GAIN), significance=area / u)


def _activity() -> dict:
    out = {}
    lines = [(356.0129, 5000.0), (302.8508, 1500.0), (383.8485, 600.0), (276.3989, 600.0)]
    for e_lo in (50.0, 122.0):
        curve = ef.fit_efficiency([ef.manual_point(e, 0.01, 2.0) for e in (e_lo, 200, 500, 1000, 2000)],
                                  "loglog", order=1)
        o = act.ActivityOptions(nuclides=["Ba-133"], method="mean", intensity_rel_unc=0.01,
                                tcs={"peak_to_total": list(PT), "pt_rel_unc": 0.1})
        r = act.compute_activities(_spectrum(), curve, o, peaks=[_peak(e, a) for e, a in lines]).nuclides[0]
        out[f"e_min {e_lo:g}"] = {
            "activity": r.activity, "u": r.u, "note": r.note,
            "lines": [[l.energy, l.coi, l.coi_applied, l.coi_rel_unc, l.activity, l.note,
                       getattr(l, "coi_partial", None)] for l in r.lines]}
    return out


def collect() -> dict:
    from spectramaster.lab.session import ENGINE_VERSION
    warnings = {}
    return {"engine": ENGINE_VERSION, "examples": _examples(), "lines": _all_lines(),
            "calibration": _calibration(warnings), "calibration_warnings": warnings, "activity": _activity()}


def _same_values(a: list, b: list) -> bool:
    """The correction itself (factor ... note), without the new partial fields."""
    return a[:8] == b[:8]


def criteria(res: dict, before: dict) -> dict:
    c = {}
    x, xb = res["examples"], before["examples"]
    xb = {**xb, **{k: v for k, v in x.items() if k.startswith("inconsistent ")}}
    hi, lo = x["Ba-133 356.0129 e_min 122"], x["Ba-133 356.0129 e_min 50"]
    ok = (hi[8] is True and lo[8] is False and _same_values(hi, xb["Ba-133 356.0129 e_min 122"])
          and _same_values(lo, xb["Ba-133 356.0129 e_min 50"]) and "below the efficiency curve" in hi[10]
          and not lo[10])
    c["RE3.C1"] = (ok, f"Ba-133 356 keV, e_min 122: partial {hi[8]}, ignored {hi[3]:.6f}, factor {hi[0]:.7f}, "
                      f"text '{hi[10]}'; e_min 50: partial {lo[8]}, factor {lo[0]:.7f}")
    part = {k: v for k, v in x.items() if k.startswith("Ac-228")}
    ind = {k: v for k, v in x.items() if k.startswith("inconsistent ")}
    ok = (part["Ac-228 880.76"][8] is True and "intensit" in part["Ac-228 880.76"][10]
          and part["Ac-228 911.204"][8] is False and part["Ac-228 968.971"][8] is False
          and all(_same_values(v, xb[k]) for k, v in part.items())
          and all(a is not None and (a == b or abs(a - b) <= 1e-12 * abs(b)) for a, b in ind.values()))
    c["RE3.C2"] = (ok, "; ".join(f"{k}: partial {v[8]}, inconsistent {v[9]:.6g}, factor {v[0]:.7f}"
                                 for k, v in part.items())
                   + "; engine / independent: " + ", ".join(f"{k[13:]} {a:.6g}/{b:.6g}" for k, (a, b) in ind.items()))
    la, lb = res["lines"], before["lines"]
    diff = sorted(k for k in set(la) | set(lb) if k not in la or k not in lb or not _same_values(la[k], lb[k]))
    n_part = sum(1 for v in la.values() if v[8])
    n_found = sum(1 for v in la.values() if v[4])
    c["RE3.C3"] = (not diff, f"{len(la)} line evaluations: correction changed for {len(diff)} {diff[:5]}; "
                            f"partial {n_part} of {n_found} corrected")
    ca, cb = res["calibration"], before["calibration"]
    part, pb = ca["eu152_ba133_from_121.8"], cb["eu152_ba133_from_121.8"]
    warn = res["calibration_warnings"].get("eu152_ba133_from_121.8", [])
    ba = [e for e in BA if e > 200]
    ok = ("error" not in part and all(part[k] == pb[k] for k in ("e_min", "points", "eps_500"))
          and "partial correction" in part["note"] and "Ba-133" in part["note"]
          and all(any(w.startswith(f"Ba-133 {round(e, 1):g} keV") for w in warn) for e in ba)
          and ca["eu152_ba133_from_53.2"] == cb["eu152_ba133_from_53.2"] and ca["eu152_only"] == cb["eu152_only"])
    c["RE3.C4"] = (ok, f"curve from 121.8 keV with Ba-133 points: {part.get('error') or 'corrected'}, points, "
                       f"eps(500) and e_min identical: {all(part.get(k) == pb[k] for k in ('e_min', 'points', 'eps_500'))}; "
                       f"note '{part.get('note', '')}'; {len(warn)} warnings; from 53.2 keV and Eu-152 only "
                       f"identical to before: {ca['eu152_ba133_from_53.2'] == cb['eu152_ba133_from_53.2']}, "
                       f"{ca['eu152_only'] == cb['eu152_only']}")
    aa, ab = res["activity"], before["activity"]
    ok = True
    for k in aa:
        ok &= aa[k]["activity"] == ab[k]["activity"] and aa[k]["u"] == ab[k]["u"]
        ok &= all(l[:5] == m[:5] for l, m in zip(aa[k]["lines"], ab[k]["lines"]))
    hi_lines = [l for l in aa["e_min 122"]["lines"] if l[2]]
    lo_lines = [l for l in aa["e_min 50"]["lines"] if l[2]]
    ok &= (all(l[6] is True and "partial" in l[5] for l in hi_lines)
           and all(l[6] is False for l in lo_lines) and "partial" in aa["e_min 122"]["note"]
           and "partial" not in aa["e_min 50"]["note"])
    c["RE3.C5"] = (ok, f"e_min 122: activity {aa['e_min 122']['activity']:.6g} +- {aa['e_min 122']['u']:.4g} Bq "
                      f"(before {ab['e_min 122']['activity']:.6g}), partial lines "
                      f"{[l[0] for l in hi_lines if l[6]]}, note '{aa['e_min 122']['note']}'; e_min 50: "
                      f"partial lines {[l[0] for l in lo_lines if l[6]]}")
    return c


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true", help="write the before values (fixed file)")
    a = ap.parse_args(argv)
    res = collect()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.collect:
        BEFORE_JSON.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        return 0
    before = json.loads(BEFORE_JSON.read_text(encoding="utf-8"))
    res = json.loads(json.dumps(res, default=str))      # same representation as the stored before values
    c = criteria(res, before)
    (OUT / "round5_tcs.json").write_text(json.dumps({"result": res, "criteria": c}, indent=1, ensure_ascii=False,
                                                    default=str), encoding="utf-8")
    lines = ["# Round-5 review, H5/H6: partial true-coincidence summing corrections (second amendment)", "",
             "Protocol: `docs/baseline/round5_tcs_protocol.md`, second amendment.", "", "| ID | result | value |", "|---|---|---|"]
    lines += [f"| {k} | {'PASS' if ok else 'FAIL'} | {v} |" for k, (ok, v) in c.items()]
    (OUT / "round5_tcs.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(", ".join(f"{k}:{'PASS' if ok else 'FAIL'}" for k, (ok, _v) in c.items()))
    return 0 if all(ok for ok, _v in c.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

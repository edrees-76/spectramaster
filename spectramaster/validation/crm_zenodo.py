"""Activity concentrations of certified reference materials (pre-registered check).

    python -m spectramaster.validation.crm_zenodo [--data FILE] [--out docs/baseline]

Protocol, selection and limits: ``docs/baseline/crm_validation_protocol.md``.  Data: Truong & Huynh,
doi:10.5281/zenodo.23093533 (CC BY 4.0), kept outside the repository
(``SPECTRAMASTER_PUBLIC_DATA``/zenodo_23093533 or ``--data``).  The ``.npz`` is read with
``allow_pickle=False``.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from ..analysis import efficiency as ef
from ..analysis.activity import ActivityOptions, compute_activities
from ..lab.session import ENGINE_VERSION
from ..model import Spectrum

DEFAULT_DATA = (Path(os.environ.get("SPECTRAMASTER_PUBLIC_DATA", "D:/SpectraMaster_public_data"))
                / "zenodo_23093533" / "Pub6_dataset_v1.0" / "pub6_hpge_crm_v1.npz")
DATA_MD5 = "64aa9d4786c3e0a65a0355d563e75d09"      # of Pub6_dataset_v1.0.zip

YEAR_S = 365.2422 * 86400.0
RA228_HALF_LIFE_S = 5.75 * YEAR_S       # ENSDF; Ra-228 is not in the gamma library (no gamma lines)
TL208_BRANCHING = 0.3594
E_MIN_CAL = 200.0
MIN_REF_BQ = 1.0                         # quantitative pair: label x mass >= 1 Bq

BACKGROUND = "background Feb-2016.Chn"

CYLINDER_CAL = {"S189": "RGU-1", "S136": "RGTh-1", "S112": "RGK-1"}
CYLINDER_TEST = ["S018", "S021", "S047", "S059", "S067", "S086", "S332"]
MARINELLI_CAL = {"S180": "RGU-1", "S131": "RGTh-1", "S104": "RGK-1"}
MARINELLI_TEST = ["S080"]

TESTED = {"Ra-226": "Pb-214/Bi-214", "Ra-228": "Ra-228/Ac-228", "Th-228": "Th-228/Pb-212",
          "K-40": "K-40", "Cs-137": "Cs-137"}

LIMITS = {"CRM.C1": 0.90, "CRM.C2": 0.80, "CRM.C3": (0.90, 1.10), "CRM.C4": 2.0}
Z_LIMIT = 2.58
BIAS_LIMIT = 0.20


class Dataset:
    def __init__(self, path: Path):
        z = np.load(path, allow_pickle=False)
        self.path = path
        self.edges = z["energy_edges_keV"]
        self.counts = z["counts"]
        self.labels = z["labels_Bq_per_kg"]
        self.labels_u = z["labels_u"]
        self.nuclides = [str(n) for n in z["nuclides"]]
        self.meta = json.loads(str(z["meta_json"]))
        self.bkg_counts = z["bkg_counts"]
        self.bkg_meta = json.loads(str(z["bkg_meta_json"]))
        self.index = {m["ID"]: i for i, m in enumerate(self.meta)}
        step = float(self.edges[1] - self.edges[0])
        self.coeffs = [float(self.edges[0]) + step / 2.0, step]

    def spectrum(self, sid: str) -> Spectrum:
        i = self.index[sid]
        m = self.meta[i]
        return Spectrum(counts=[float(c) for c in self.counts[i]], energy_coeffs=list(self.coeffs),
                        live_time=float(m["lt_s"]), real_time=float(m["rt_s"]),
                        start_time=datetime.fromisoformat(m["start"]), sample_id=sid,
                        description=f"{m['material']} ({m['file']})")

    def background(self, name: str = BACKGROUND) -> Spectrum:
        i = next(k for k, b in enumerate(self.bkg_meta) if b["file"] == name)
        b = self.bkg_meta[i]
        return Spectrum(counts=[float(c) for c in self.bkg_counts[i]], energy_coeffs=list(self.coeffs),
                        live_time=float(b["lt_s"]), real_time=None,
                        start_time=datetime.fromisoformat(b["start"]), sample_id=name)

    def label(self, sid: str, key: str) -> tuple[Optional[float], Optional[float]]:
        i, j = self.index[sid], self.nuclides.index(key)
        v, u = float(self.labels[i, j]), float(self.labels_u[i, j])
        return (v, u) if math.isfinite(v) else (None, None)

    def mass_kg(self, sid: str) -> float:
        return float(self.meta[self.index[sid]]["mass_g"]) / 1000.0


def certificate(ds: Dataset, sid: str, material: str) -> list[ef.CertNuclide]:
    """Certificate entries of a calibration spectrum (activity = label x mass)."""
    m = ds.mass_kg(sid)
    t0 = ds.spectrum(sid).start_time

    def entry(nuc, key, hl, factor=1.0):
        v, u = ds.label(sid, key)
        return ef.CertNuclide(nuc, v * m * factor, (u or 0.0) * m * factor, t0, hl)

    ra226 = ef.half_life_of("Ra-226")
    th228 = ef.half_life_of("Th-228")
    if material == "RGU-1":
        return [entry("Pb-214", "Pb-214/Bi-214", ra226), entry("Bi-214", "Pb-214/Bi-214", ra226)]
    if material == "RGTh-1":
        return [entry("Ac-228", "Ra-228/Ac-228", RA228_HALF_LIFE_S),
                entry("Pb-212", "Th-228/Pb-212", th228), entry("Bi-212", "Th-228/Pb-212", th228),
                entry("Tl-208", "Th-228/Pb-212", th228, TL208_BRANCHING)]
    if material == "RGK-1":
        return [entry("K-40", "K-40", ef.half_life_of("K-40"))]
    raise ValueError(material)


def calibration_points(ds: Dataset, cal: dict, bkg: Spectrum) -> list[ef.EfficiencyPoint]:
    pts = []
    for sid, material in cal.items():
        lines = ef.certificate_lines(certificate(ds, sid, material), e_min=E_MIN_CAL)
        got = ef.measure_efficiency(ds.spectrum(sid), lines, background=bkg)
        for p in got:
            p.group = material          # one certificate value per material: correlated activity
            p.note = (f"{material} {sid}; " + p.note).strip("; ")
        pts += got
    return sorted(pts, key=lambda p: p.energy)


def test_pairs(ds: Dataset, curve, tests: list, bkg: Spectrum) -> tuple[list[dict], list[dict]]:
    pairs, lines = [], []
    for sid in tests:
        m = ds.mass_kg(sid)
        sp = ds.spectrum(sid)
        wanted = [n for n, key in TESTED.items() if ds.label(sid, key)[0] is not None]
        try:
            res = compute_activities(sp, curve, ActivityOptions(nuclides=wanted), background=bkg)
            by = {r.nuclide: r for r in res.nuclides}
            error = ""
        except Exception as exc:                                   # noqa: BLE001 - reported as failure
            by, error = {}, f"{type(exc).__name__}: {exc}"
        for nuc in wanted:
            ref, uref = ds.label(sid, TESTED[nuc])
            row = {"id": sid, "material": ds.meta[ds.index[sid]]["material"], "nuclide": nuc, "ref": ref,
                   "u_ref": uref, "ref_bq": ref * m, "quantitative": ref * m >= MIN_REF_BQ,
                   "value": None, "u": None, "ratio": None, "z": None, "detected": False, "lines": "",
                   "note": error}
            r = by.get(nuc)
            if r is not None:
                row["detected"] = bool(r.detected)
                row["lines"] = r.lines_text
                row["note"] = r.note
                row["mda"] = r.mda / m if r.mda else None
                if r.detected and r.activity is not None:
                    c, u = r.activity / m, (r.u or 0.0) / m
                    row.update(value=c, u=u, ratio=c / ref, z=(c - ref) / math.hypot(u, uref or 0.0))
                for ln in r.lines:
                    lines.append({"id": sid, "nuclide": nuc, "line": ln.nuclide, "energy": ln.energy,
                                  "peak_found": ln.peak_found, "net_area": ln.net_area, "net_unc": ln.net_unc,
                                  "efficiency": ln.efficiency,
                                  "c_line": (ln.activity / m) if ln.activity is not None else None,
                                  "ref": ref, "note": ln.note})
            pairs.append(row)
    return pairs, lines


def criteria(pairs: list[dict]) -> list[dict]:
    q = [p for p in pairs if p["quantitative"]]
    n = len(q)
    zok = sum(1 for p in q if p["z"] is not None and abs(p["z"]) <= Z_LIMIT)
    bok = sum(1 for p in q if p["ratio"] is not None and abs(p["ratio"] - 1.0) <= BIAS_LIMIT)
    zs = [p["z"] for p in q if p["z"] is not None]
    out = [
        {"id": "CRM.C1", "value": zok / n, "limit": f">= {LIMITS['CRM.C1']}", "pass": zok / n >= LIMITS["CRM.C1"],
         "detail": f"{zok}/{n} pairs with |z| <= {Z_LIMIT}"},
        {"id": "CRM.C2", "value": bok / n, "limit": f">= {LIMITS['CRM.C2']}", "pass": bok / n >= LIMITS["CRM.C2"],
         "detail": f"{bok}/{n} pairs with |ratio - 1| <= {BIAS_LIMIT}"},
    ]
    lo, hi = LIMITS["CRM.C3"]
    for nuc in TESTED:
        rs = [p["ratio"] for p in q if p["nuclide"] == nuc]
        if len(rs) < 3:
            continue
        # a missing value is a failure: it enters the median as 0
        med = statistics.median([r if r is not None else 0.0 for r in rs])
        out.append({"id": f"CRM.C3.{nuc}", "value": med, "limit": f"in [{lo}, {hi}]", "pass": lo <= med <= hi,
                    "detail": f"median ratio of {len(rs)} pairs"})
    rms = math.sqrt(sum(z * z for z in zs) / len(zs)) if zs else float("inf")
    missing = n - len(zs)
    out.append({"id": "CRM.C4", "value": rms, "limit": f"<= {LIMITS['CRM.C4']}",
                "pass": rms <= LIMITS["CRM.C4"] and missing == 0,
                "detail": f"rms z of {len(zs)} pairs" + (f"; {missing} pair(s) without a value" if missing else "")})
    return out


def run(ds: Dataset, cal: dict, tests: list, model: str) -> dict:
    bkg = ds.background()
    pts = calibration_points(ds, cal, bkg)
    curve = ef.fit_efficiency(pts, model, crossover="auto" if model == "two_branch" else 200.0,
                              name=f"CRM {model}")
    pairs, lines = test_pairs(ds, curve, tests, bkg)
    return {"model": model, "curve": curve, "points": pts, "pairs": pairs, "lines": lines,
            "criteria": criteria(pairs)}


# ------------------------------------------------------------------------------ report
def _f(v, fmt=".4g"):
    return "-" if v is None else format(v, fmt)


def _curve_md(r: dict) -> list[str]:
    cv = r["curve"]
    out = [f"Model `{cv.model}`, order {cv.order}" + (f"/{cv.order_high}, crossover {cv.e_ref:g} keV"
                                                    if cv.model == "two_branch" else "")
           + f", chi^2/dof = {cv.chi2:.2f}/{cv.dof}, model error {100 * cv.u_model_rel:.2f} %, "
           f"range {cv.e_min:.0f}-{cv.e_max:.0f} keV. {cv.selection}", "",
           "| line | keV | eps | u % | used | residual % | note |", "|---|---|---|---|---|---|---|"]
    res = {id(p): (rp, z) for p, rp, z in cv.residuals()}
    for p in r["points"]:
        rp = res.get(id(p), (None, None))[0]
        out.append(f"| {p.nuclide} | {p.energy:.1f} | {p.efficiency:.5f} | {100 * p.rel_unc:.1f} | "
                   f"{'yes' if p.use else 'no'} | {_f(rp, '+.1f')} | {p.note} |")
    if cv.warnings:
        out += ["", "Warnings: " + "; ".join(cv.warnings)]
    return out


def _pairs_md(pairs: list[dict]) -> list[str]:
    out = ["| ID | material | nuclide | ref Bq/kg | ours Bq/kg | ratio | z | lines | note |",
           "|---|---|---|---|---|---|---|---|---|"]
    for p in pairs:
        ref = f"{p['ref']:.4g} +- {p['u_ref']:.2g}"
        ours = (f"{p['value']:.4g} +- {p['u']:.2g}" if p["value"] is not None
                else ("< " + _f(p.get("mda"), ".3g") + " (not detected)"))
        tag = "" if p["quantitative"] else " (detection check)"
        out.append(f"| {p['id']} | {p['material']} | {p['nuclide']}{tag} | {ref} | {ours} | {_f(p['ratio'], '.3f')} | "
                   f"{_f(p['z'], '+.2f')} | {p['lines']} | {p['note']} |")
    return out


def report(ds: Dataset, results: dict) -> str:
    main = results["cylinder_loglog"]
    n_pass = sum(c["pass"] for c in main["criteria"])
    out = ["# Certified reference materials: results", "",
           f"Protocol: `crm_validation_protocol.md`. Engine {ENGINE_VERSION}. "
           f"Data: doi:10.5281/zenodo.23093533 (zip MD5 {DATA_MD5}).", "",
           f"## Criteria (cylinder, log-log): {n_pass} of {len(main['criteria'])} pass", "",
           "| id | value | limit | status | detail |", "|---|---|---|---|---|"]
    for c in main["criteria"]:
        out.append(f"| {c['id']} | {c['value']:.3f} | {c['limit']} | {'PASS' if c['pass'] else 'FAIL'} | {c['detail']} |")
    out += ["", "## Pairs (cylinder, log-log)", ""] + _pairs_md(main["pairs"])
    out += ["", "## Calibration (cylinder, log-log)", ""] + _curve_md(main)
    out += ["", "## Lines (cylinder, log-log)", "",
            "| ID | nuclide | line | keV | found | net | eff | c (line) Bq/kg | ref | note |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for ln in main["lines"]:
        out.append(f"| {ln['id']} | {ln['nuclide']} | {ln['line']} | {ln['energy']:.1f} | "
                   f"{'yes' if ln['peak_found'] else 'no'} | {ln['net_area']:.0f} +- {ln['net_unc']:.0f} | "
                   f"{ln['efficiency']:.5f} | {_f(ln['c_line'])} | {ln['ref']:.4g} | {ln['note']} |")
    for key, title in (("cylinder_two_branch", "Report: cylinder, two-branch model"),
                       ("marinelli_loglog", "Report: Marinelli, log-log")):
        r = results[key]
        out += ["", f"## {title}", "", "Criteria values (not criteria here): "
                + "; ".join(f"{c['id']} {c['value']:.3f}" for c in r["criteria"]), ""]
        out += _pairs_md(r["pairs"]) + [""] + _curve_md(r)
    return "\n".join(out) + "\n"


def _json(results: dict) -> dict:
    def pt(p):
        return {"nuclide": p.nuclide, "energy": p.energy, "efficiency": p.efficiency, "rel_unc": p.rel_unc,
                "use": p.use, "note": p.note}
    return {k: {"model": r["model"], "criteria": r["criteria"], "pairs": r["pairs"], "lines": r["lines"],
                "points": [pt(p) for p in r["points"]],
                "curve": {"order": r["curve"].order, "order_high": r["curve"].order_high, "e_ref": r["curve"].e_ref,
                          "chi2": r["curve"].chi2, "dof": r["curve"].dof, "u_model_rel": r["curve"].u_model_rel}}
            for k, r in results.items()} | {"engine_version": ENGINE_VERSION, "data_md5": DATA_MD5}


def run_all(path: Path = DEFAULT_DATA) -> tuple[Dataset, dict]:
    ds = Dataset(path)
    results = {"cylinder_loglog": run(ds, CYLINDER_CAL, CYLINDER_TEST, "loglog"),
               "cylinder_two_branch": run(ds, CYLINDER_CAL, CYLINDER_TEST, "two_branch"),
               "marinelli_loglog": run(ds, MARINELLI_CAL, MARINELLI_TEST, "loglog")}
    return ds, results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--out", type=Path, default=None, help="folder for crm_validation_results.md/.json")
    a = ap.parse_args(argv)
    ds, results = run_all(a.data)
    text = report(ds, results)
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "crm_validation_results.md").write_text(text, encoding="utf-8")
        (a.out / "crm_validation_results.json").write_text(json.dumps(_json(results), indent=1, default=str),
                                                          encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Activities of the IAEA 2002 low-level test sources (pre-registered check).

    python -m spectramaster.validation.iaea2002 [--data DIR] [--out docs/baseline/after_IA1]

Protocol, decisions and limits: ``docs/baseline/iaea2002_validation_protocol.md``.  Data: the IAEA
2002 test spectra for low-level gamma-ray spectrometry (Arnold et al., NIM A 536 (2005) 196), kept
outside the repository (``SPECTRAMASTER_PUBLIC_DATA``/iaea_2002_testspectra or ``--data``).  The
certificate values below are those of the Analytics certificates in the set's documentation.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from ..analysis import coincidence
from ..analysis import efficiency as ef
from ..analysis.activity import ActivityOptions, compute_activities
from ..analysis.background import net_spectrum
from ..analysis.peaks import find_peaks
from ..convert import read_spectra
from ..lab.session import ENGINE_VERSION
from ..tools.calibrate import apply_calibration, calibrate_from_source

DEFAULT_DATA = (Path(os.environ.get("SPECTRAMASTER_PUBLIC_DATA", "D:/SpectraMaster_public_data"))
                / "iaea_2002_testspectra" / "extracted" / "IAEA_2002_testspectra" / "iaea2002")
ZIP_SHA256 = "361a09e350976c0e32407d182d77bb4c492fcf74bf5fa29d91024dd2dd184c51"

K99 = 2.576                                   # certificates: total uncertainty at 99 % confidence
CERT_DATE = datetime(2002, 11, 1, 18, 0)      # 12:00 EST read in the spectrum clock (CET), D-b
CERT_DATE_EST = datetime(2002, 11, 1, 12, 0)  # S4
MARIC_CHN_START = datetime(2002, 11, 20, 12, 0)   # S3: start time of maricsmall.chn
E_MIN_CAL = 50.0
PT_REL_UNC = 0.10
PT_LINES = [("Co57", "Co-57", 122.06), ("Sn113", "Sn-113", 391.70), ("Cs137", "Cs-137", 661.66),
            ("Mn54", "Mn-54", 834.85), ("Zn65", "Zn-65", 1115.54)]
PT_E_LOW = 40.0
PT_E_FLAT = 60.0

CAL_NUCLIDES = ["Am-241", "Cd-109", "Ce-139", "Co-57", "Cs-134", "Cs-137", "Hg-203", "Mn-54", "Sn-113",
                "Y-88", "Zn-65"]
TEST_NUCLIDES = ["Ba-133", "Co-60", "Eu-152", "Cr-51", "Na-22"]
CAL_U99 = {n: 5.0 for n in CAL_NUCLIDES} | {"Cs-137": 4.8}
CERT = {
    "64921A": dict(zip(CAL_NUCLIDES, [3353, 39214, 1325, 884, 5529, 1106, 2666, 1564, 2391, 3914, 3191])),
    "64922A": dict(zip(CAL_NUCLIDES, [5403, 63190, 2136, 1424, 8909, 1782, 4297, 2519, 3853, 6306, 5142])),
    "64923": dict(zip(TEST_NUCLIDES, [1713, 1076, 3739, 7903, 1073])),     # "Cr-52" read as Cr-51
    "64924A": dict(zip(TEST_NUCLIDES, [1253, 799, 2827, 7827, 1063])),
}
TEST_U99 = 5.0

GEOMETRIES = {
    "marinelli": {"detector": "SMALL", "cal": "maricsmall", "cal_cert": "64921A", "bkg": "BGSMALLMARI",
                  "tests": ["maritsmall", "maritsmall60"], "test_cert": "64923", "pt_bkg": "BGSMALLPOINT",
                  "pt_suffix": "SMALL"},
    "pillbox": {"detector": "BIG", "cal": "picbig", "cal_cert": "64922A", "bkg": "BGBIGPOINT",
                "tests": ["PITBIG", "PITBIG60"], "test_cert": "64924A", "pt_bkg": "BGBIGPOINT",
                "pt_suffix": "BIG"},
}
LONG = {"maritsmall", "PITBIG"}
BKG_NUCLIDES = ["K-40", "Ra-226", "Th-232"]

Z_LIMIT = 2.58
LIMITS = {"IA.C1": 0.90, "IA.C2": (0.10, 0.80), "IA.C3": (0.15, 0.80), "IA.C4": (0.93, 1.07), "IA.C5": 2.0}


# ------------------------------------------------------------------------------ data
def read(data: Path, name: str):
    p = data / "spectra" / f"{name}.spe"
    if not p.exists():
        p = next((q for q in (data / "spectra").iterdir() if q.name.lower() == f"{name}.spe".lower()), p)
    return read_spectra(p)[0][0]


def calibrated(spec, nuclides, label: str):
    """The spectrum with the energy (and FWHM) calibration proposed from its own known nuclides."""
    sc = calibrate_from_source(spec, [n for n in nuclides if n != "Cr-51"], use_existing=False)
    out = apply_calibration(spec, sc.coeffs, sc.fwhm_fit.coeffs if sc.fwhm_fit is not None else None,
                            note=f"IAEA 2002 check: {sc.method}")
    info = {"spectrum": label, "method": sc.method, "lines": len(sc.matches), "rms_kev": sc.fit.rms,
            "coeffs": list(sc.coeffs), "unmatched": [f"{n} {e:.1f}" for n, e in sc.unmatched]}
    return out, info


def calibration_certificate(cert_id: str, ref: datetime) -> list[ef.CertNuclide]:
    return [ef.CertNuclide(n, float(a), float(a) * CAL_U99[n] / 100.0 / K99, ref)
            for n, a in CERT[cert_id].items()]


# ------------------------------------------------------------------------------ peak-to-total
def peak_to_total_points(data: Path, geo: dict) -> tuple[list[dict], tuple[float, float]]:
    bkg, _ = calibrated(read(data, geo["pt_bkg"]), BKG_NUCLIDES, geo["pt_bkg"])
    pts = []
    for stem, nuc, energy in PT_LINES:
        name = f"{stem}{geo['pt_suffix']}"
        sp = apply_calibration(read(data, name), bkg.energy_coeffs, bkg.fwhm_coeffs,
                               note=f"calibration of {geo['pt_bkg']}")
        net, var, _k = net_spectrum(sp, bkg)
        peaks = find_peaks(net, min_sig=3.0, variance=var)
        near = [p for p in peaks if abs(p.energy - energy) <= max(1.0, 1.5 * (p.fwhm_kev or 0.0))]
        e = np.asarray(sp.energies())
        c = np.asarray(net.counts, dtype=float)
        above = e >= PT_E_LOW
        flat = c[(e >= PT_E_LOW) & (e < PT_E_FLAT)].mean()
        total = float(c[above].sum() + flat * int(((e >= 0) & (e < PT_E_LOW)).sum()))
        row = {"spectrum": name, "nuclide": nuc, "energy": energy, "total": total, "area": None, "pt": None}
        if near:
            pk = min(near, key=lambda p: abs(p.energy - energy))
            row.update(area=float(pk.net_area), pt=float(pk.net_area) / total)
        pts.append(row)
    good = [r for r in pts if r["pt"] and r["pt"] > 0]
    x = np.log([r["energy"] / 1000.0 for r in good])
    y = np.log([r["pt"] for r in good])
    b, ln_a = np.polyfit(x, y, 1)
    return pts, (float(math.exp(ln_a)), float(b))


# ------------------------------------------------------------------------------ one geometry
def run_geometry(data: Path, key: str, model: str = "two_branch", tcs: bool = True,
                 cert_date: datetime = CERT_DATE, cal_start: Optional[datetime] = None,
                 pt: Optional[tuple] = None, self_attenuation=None) -> dict:
    geo = GEOMETRIES[key]
    cals = []
    bkg, info = calibrated(read(data, geo["bkg"]), BKG_NUCLIDES, geo["bkg"])
    cals.append(info)
    cal, info = calibrated(read(data, geo["cal"]), CAL_NUCLIDES, geo["cal"])
    cals.append(info)
    if cal_start is not None:
        cal = replace(cal, start_time=cal_start)
    lines = ef.certificate_lines(calibration_certificate(geo["cal_cert"], cert_date), e_min=E_MIN_CAL)
    points = ef.measure_efficiency(cal, lines, background=bkg)
    for p in points:
        p.group = geo["cal_cert"]
    curve = ef.fit_efficiency(points, model, crossover="auto" if model == "two_branch" else 200.0,
                              name=f"IAEA 2002 {key} {model}")
    pt_points = None
    if pt is None and tcs:
        pt_points, pt = peak_to_total_points(data, geo)
    options = ActivityOptions(nuclides=list(TEST_NUCLIDES), ref_date=cert_date, self_attenuation=self_attenuation)
    if tcs:
        a, b = pt
        curve = ef.summing_free_curve(curve, lambda e: coincidence.peak_to_total(e, a, b), PT_REL_UNC)
        options = replace(options, tcs={"peak_to_total": [a, b], "pt_rel_unc": PT_REL_UNC})
    pairs, line_rows = [], []
    for name in geo["tests"]:
        sp, info = calibrated(read(data, name), TEST_NUCLIDES, name)
        cals.append(info)
        try:
            res = compute_activities(sp, curve, options, background=bkg)
            by, error = {r.nuclide: r for r in res.nuclides}, ""
        except Exception as exc:                                   # noqa: BLE001 - reported as failure
            by, error = {}, f"{type(exc).__name__}: {exc}"
        for nuc in TEST_NUCLIDES:
            ref = float(CERT[geo["test_cert"]][nuc])
            uref = ref * TEST_U99 / 100.0 / K99
            row = {"geometry": key, "spectrum": name, "long": name in LONG, "nuclide": nuc, "ref": ref,
                   "u_ref": uref, "value": None, "u": None, "ratio": None, "z": None, "detected": False,
                   "lines": "", "note": error}
            r = by.get(nuc)
            if r is not None:
                row.update(detected=bool(r.detected), lines=r.lines_text, note=r.note)
                if r.activity is not None:
                    row.update(value=r.activity, u=r.u or 0.0, ratio=r.activity / ref,
                               z=(r.activity - ref) / math.hypot(r.u or 0.0, uref))
                for ln in r.lines:
                    line_rows.append({"spectrum": name, "nuclide": nuc, "energy": ln.energy,
                                      "peak_found": ln.peak_found, "net_area": ln.net_area,
                                      "net_unc": ln.net_unc, "efficiency": ln.efficiency,
                                      "activity": ln.activity, "note": ln.note})
            pairs.append(row)
    return {"geometry": key, "model": model, "tcs": tcs, "pt": pt, "pt_points": pt_points, "curve": curve,
            "points": points, "calibrations": cals, "pairs": pairs, "lines": line_rows}


# ------------------------------------------------------------------------------ criteria
def criteria(pairs: list[dict]) -> list[dict]:
    n = len(pairs)
    zok = sum(1 for p in pairs if p["z"] is not None and abs(p["z"]) <= Z_LIMIT)
    out = [{"id": "IA.C1", "value": zok / n, "limit": f">= {LIMITS['IA.C1']}", "pass": zok / n >= LIMITS["IA.C1"],
            "detail": f"{zok}/{n} pairs with |z| <= {Z_LIMIT}"}]
    for cid, geo in (("IA.C2", "marinelli"), ("IA.C3", "pillbox")):
        tol, need = LIMITS[cid]
        g = [p for p in pairs if p["geometry"] == geo]
        ok = sum(1 for p in g if p["ratio"] is not None and abs(p["ratio"] - 1.0) <= tol)
        out.append({"id": cid, "value": ok / len(g), "limit": f">= {need}", "pass": ok / len(g) >= need,
                    "detail": f"{geo}: {ok}/{len(g)} pairs with |ratio - 1| <= {tol}"})
    lo, hi = LIMITS["IA.C4"]
    for suffix, geo in (("M", "marinelli"), ("P", "pillbox")):
        rs = [p["ratio"] if p["ratio"] is not None else 0.0 for p in pairs if p["geometry"] == geo and p["long"]]
        med = statistics.median(rs)
        out.append({"id": f"IA.C4.{suffix}", "value": float(med), "limit": f"in [{lo}, {hi}]",
                    "pass": bool(lo <= med <= hi),
                    "detail": f"{geo}: median ratio of {len(rs)} long-spectrum pairs"})
    zs = [p["z"] for p in pairs if p["z"] is not None]
    rms = math.sqrt(sum(z * z for z in zs) / len(zs)) if zs else float("inf")
    missing = n - len(zs)
    out.append({"id": "IA.C5", "value": rms, "limit": f"<= {LIMITS['IA.C5']}, none missing",
                "pass": bool(rms <= LIMITS["IA.C5"] and missing == 0),
                "detail": f"rms z of {len(zs)} pairs" + (f"; {missing} without a value" if missing else "")})
    det = sum(1 for p in pairs if p["detected"])
    out.append({"id": "IA.C6", "value": det, "limit": f"{n} / {n}", "pass": det == n,
                "detail": f"{det}/{n} pairs reported as detected"})
    return out


# ------------------------------------------------------------------------------ S5: peak areas of mix2neq6
CMPSPEC_RATIO = 239.0


def mix2neq6_areas(data: Path) -> dict:
    """CMPSPEC definitions (2002 READ_ME) re-implemented; report only."""
    ref = []
    for line in (data / "refrsl" / "mix2neq6ref.txt").read_text(encoding="latin-1").splitlines():
        f = line.split()
        if len(f) >= 5:
            ref.append({"E": float(f[0]), "dE": float(f[1]), "A": float(f[2]), "dA": float(f[3]),
                        "use": f[4] == "1"})
    long_sp, info = calibrated(read(data, "mix2neqlong"), BKG_NUCLIDES, "mix2neqlong")
    sp = apply_calibration(read(data, "mix2neq6"), long_sp.energy_coeffs, long_sp.fwhm_coeffs,
                           note="calibration of mix2neqlong")
    peaks = find_peaks(sp, min_sig=3.0)
    c = math.sqrt(CMPSPEC_RATIO)
    used, rows = set(), []
    for r in ref:
        best = None
        for k, p in enumerate(peaks):
            if k in used:
                continue
            de = abs(p.energy - r["E"])
            tol = max(2.0 * math.hypot(r["dE"], 0.0), 0.5 * (p.fwhm_kev or 0.0))
            if de < tol and (best is None or de < best[0]):
                best = (de, k)
        row = dict(r, kind="", z=None, Am=None, dAm=None, Em=None)
        if best is not None:
            used.add(best[1])
            p = peaks[best[1]]
            row.update(Am=p.net_area, dAm=p.net_area_unc, Em=p.energy)
            if r["use"]:
                row.update(kind="match", z=(p.net_area - r["A"]) / math.hypot(p.net_area_unc, r["dA"]))
        elif r["use"]:
            row.update(kind="miss", z=r["A"] / (c * r["dA"]) if r["dA"] > 0 else None)
        rows.append(row)
    false_hits = [{"Em": p.energy, "Am": p.net_area, "dAm": p.net_area_unc,
                   "z": p.net_area / p.net_area_unc if p.net_area_unc else None}
                  for k, p in enumerate(peaks) if k not in used and p.energy >= min(r["E"] for r in ref)]

    def chi(zs):
        zs = [z for z in zs if z is not None]
        return (sum(z * z for z in zs) / len(zs), len(zs)) if zs else (None, 0)

    matches = [r for r in rows if r["kind"] == "match"]
    high = [r["z"] for r in matches if r["A"] / max(r["dA"], 1e-12) > 10]
    low = [r["z"] for r in matches if r["A"] / max(r["dA"], 1e-12) <= 10]
    misses = [r["z"] for r in rows if r["kind"] == "miss"]
    fh = [f["z"] for f in false_hits]
    every = [r["z"] for r in matches] + misses + fh
    return {"calibration": info, "rows": rows, "false_hits": false_hits, "groups": {
        "matches, high peaks (A/dA > 10)": chi(high), "matches, small peaks": chi(low),
        "misses": chi(misses), "false hits": chi(fh), "total": chi(every)}}


# ------------------------------------------------------------------------------ run + report
def run_all(data: Path = DEFAULT_DATA) -> dict:
    main_ = {k: run_geometry(data, k) for k in GEOMETRIES}
    pairs = main_["marinelli"]["pairs"] + main_["pillbox"]["pairs"]
    pts = {k: main_[k]["pt"] for k in GEOMETRIES}
    variants = {
        "S1 no summing correction": {k: run_geometry(data, k, tcs=False) for k in GEOMETRIES},
        "S2 loglog model": {k: run_geometry(data, k, model="loglog", pt=pts[k]) for k in GEOMETRIES},
        "S3 maricsmall.chn start time": {"marinelli": run_geometry(data, "marinelli", cal_start=MARIC_CHN_START,
                                                                   pt=pts["marinelli"])},
        "S4 certificate time read as EST": {k: run_geometry(data, k, cert_date=CERT_DATE_EST, pt=pts[k])
                                            for k in GEOMETRIES},
    }
    return {"main": main_, "pairs": pairs, "criteria": criteria(pairs), "variants": variants,
            "S5": mix2neq6_areas(data)}


def _f(v, fmt=".4g"):
    return "—" if v is None else format(v, fmt)


def report(results: dict) -> str:
    out = ["# IAEA 2002 test spectra: activity check results", "",
           f"Engine {ENGINE_VERSION}. Protocol: `docs/baseline/iaea2002_validation_protocol.md`.", "",
           "## Criteria (main analysis)", "", "| ID | Value | Limit | Result | Detail |", "|---|---|---|---|---|"]
    for c in results["criteria"]:
        out.append(f"| {c['id']} | {_f(c['value'])} | {c['limit']} | {'PASS' if c['pass'] else 'FAIL'} | "
                   f"{c['detail']} |")
    out += ["", "## Pairs (main analysis)", "",
            "| Geometry | Spectrum | Nuclide | Certificate Bq | Result Bq | u (k=1) | Ratio | z | Detected | Lines |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for p in results["pairs"]:
        out.append(f"| {p['geometry']} | {p['spectrum']} | {p['nuclide']} | {p['ref']:.0f} | {_f(p['value'])} | "
                   f"{_f(p['u'])} | {_f(p['ratio'], '.3f')} | {_f(p['z'], '.2f')} | "
                   f"{'yes' if p['detected'] else 'no'} | {p['lines']} |")
    for k, r in results["main"].items():
        c = r["curve"]
        out += ["", f"## {k}: calibration", "",
                f"Efficiency curve: {c.describe()}; model error {100 * c.u_model_rel:.2f} %; "
                f"warnings {len(c.warnings)}; "
                f"points used {sum(1 for p in r['points'] if p.use)}/{len(r['points'])}.",
                f"Peak-to-total: a = {r['pt'][0]:.4f}, b = {r['pt'][1]:.4f} (PT(E) = a (E/1000)^b).", "",
                "| Spectrum | Method | Lines | rms keV | Unmatched |", "|---|---|---|---|---|"]
        for ci in r["calibrations"]:
            out.append(f"| {ci['spectrum']} | {ci['method']} | {ci['lines']} | {ci['rms_kev']:.3f} | "
                       f"{', '.join(ci['unmatched']) or '—'} |")
        if r["pt_points"]:
            out += ["", "| P/T spectrum | Line keV | Peak area | Total | P/T |", "|---|---|---|---|---|"]
            for q in r["pt_points"]:
                out.append(f"| {q['spectrum']} | {q['energy']} | {_f(q['area'])} | {q['total']:.4g} | "
                           f"{_f(q['pt'])} |")
        out += ["", "| Efficiency point | keV | eps | u % | used | note |", "|---|---|---|---|---|---|"]
        for p in r["points"]:
            out.append(f"| {p.nuclide} | {p.energy:.2f} | {p.efficiency:.5g} | "
                       f"{100 * p.unc / p.efficiency if p.efficiency else 0:.2f} | "
                       f"{'yes' if p.use else 'no'} | {p.note} |")
    out += ["", "## Sensitivity variants (report only)", "",
            "| Variant | Geometry | Spectrum | Nuclide | Ratio | z |", "|---|---|---|---|---|---|"]
    for name, per in results["variants"].items():
        for k, r in per.items():
            for p in r["pairs"]:
                out.append(f"| {name} | {k} | {p['spectrum']} | {p['nuclide']} | {_f(p['ratio'], '.3f')} | "
                           f"{_f(p['z'], '.2f')} |")
    s5 = results["S5"]
    out += ["", "## S5: peak areas of mix2neq6 against the IRI reference (report only)", "",
            "| Group | reduced chi2 | n |", "|---|---|---|"]
    for g, (v, n) in s5["groups"].items():
        out.append(f"| {g} | {_f(v, '.2f')} | {n} |")
    return "\n".join(out) + "\n"


def _json(results: dict) -> dict:
    def geo(r):
        return {"model": r["model"], "tcs": r["tcs"], "pt": r["pt"], "pt_points": r["pt_points"],
                "curve": r["curve"].describe(), "calibrations": r["calibrations"], "pairs": r["pairs"],
                "lines": r["lines"]}
    return {"engine": ENGINE_VERSION, "criteria": results["criteria"], "pairs": results["pairs"],
            "main": {k: geo(r) for k, r in results["main"].items()},
            "variants": {n: {k: [{"spectrum": p["spectrum"], "nuclide": p["nuclide"], "ratio": p["ratio"],
                                  "z": p["z"]} for p in r["pairs"]] for k, r in per.items()}
                         for n, per in results["variants"].items()},
            "S5": {"groups": results["S5"]["groups"], "rows": results["S5"]["rows"],
                   "false_hits": results["S5"]["false_hits"]}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--out", type=Path, default=None, help="folder for iaea2002_results.md/.json")
    a = ap.parse_args(argv)
    results = run_all(a.data)
    text = report(results)
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "iaea2002_results.md").write_text(text, encoding="utf-8")
        (a.out / "iaea2002_results.json").write_text(json.dumps(_json(results), indent=1, default=str),
                                                     encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

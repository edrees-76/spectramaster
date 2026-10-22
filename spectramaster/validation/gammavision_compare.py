"""Laboratory HPGe spectra compared with the peak tables of GammaVision reports
(docs/baseline/gammavision_compare_protocol.md).

    python -m spectramaster.validation.gammavision_compare

The spectra are read from ``SPECTRAMASTER_GV_DIR`` (default ``D:/specter mohamed``, laboratory data
kept outside the repository).  Writes ``gammavision_compare.json`` and ``gammavision_compare.md`` to
OUT (docs/baseline/after_GV1, a fixed folder of the repository): derived numbers only.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
from pathlib import Path

from spectramaster.analysis import find_peaks, identify
from spectramaster.convert import read_spectra

OUT = Path(__file__).resolve().parents[2] / "docs" / "baseline" / "after_GV1"
DEFAULT_DIR = Path("D:/specter mohamed")

SPECTRA = ("sand sample 2.Spc", "sand sample 2.An1", "oil sample 1.An1", "Oil sample 6.Spc",
           "sludge sample 4.Spc", "Sludg Sample 7.Spc", "SLUDG SAMPIL 13.Spc", "SLUDG SAMPIL 15.Spc",
           "Water  Sample 11.Spc")
SAND = "sand sample 2.An1"
OIL = "oil sample 1.An1"
# sand sample 2.rpt, identified-peak summary: nuclide, energy keV, net area, 1 sigma %, FWHM keV
GV_SAND = (("Pb-214", 295.25, 14771, 1.17, 1.054), ("Pb-214", 352.00, 25322, 0.80, 1.128),
           ("Tl-208", 583.45, 5335, 2.49, 1.206), ("Bi-214", 609.61, 19368, 0.89, 1.317),
           ("Ac-228", 911.63, 3619, 2.68, 1.467), ("K-40", 1461.44, 25119, 0.68, 1.823),
           ("Bi-214", 1765.26, 3269, 2.02, 1.955))
# oil sample 1.rpt: energy keV, net area, FWHM keV (all flagged as failing the shape test)
GV_OIL = ((186.03, 111, 0.197), (295.21, 137, 0.236), (352.18, 138, 0.475), (1120.11, 59, 0.195),
          (1763.48, 39, 0.413))
SAND_NUCLIDES = ("K-40", "Pb-212", "Pb-214", "Bi-214", "Ac-228", "Tl-208")
MATCH_KEV = 1.0


def _read(folder: Path, name: str):
    spectra, _fmt = read_spectra(folder / name)
    return spectra[0]


def _nearest(peaks, energy):
    best = None
    for p in peaks:
        if p.energy is not None and abs(p.energy - energy) <= MATCH_KEV:
            if best is None or abs(p.energy - energy) < abs(best.energy - energy):
                best = p
    return best


def analyse(folder: Path) -> dict:
    spectra, rows = {}, []
    for name in SPECTRA:
        s = _read(folder, name)
        peaks = find_peaks(s, min_sig=3.0)
        matches = identify(s, peaks)
        spectra[name] = (s, peaks)
        rows.append({"file": name, "live_time_s": round(s.live_time, 2), "total_counts": int(sum(s.counts)),
                     "peaks": len(peaks), "nuclides": [m.nuclide for m in matches],
                     "oil_energies": [_peak_info(_nearest(peaks, e)) for e, _a, _w in GV_OIL]})
    return {"spectra": rows, "_data": spectra}


def _peak_info(p):
    if p is None:
        return None
    return {"energy": round(p.energy, 3), "net": round(p.net_area, 1),
            "unc_pct": round(100 * p.net_area_unc / p.net_area, 2) if p.net_area > 0 else None,
            "fwhm_kev": None if p.fwhm_kev is None else round(p.fwhm_kev, 3), "sig": round(p.significance, 1)}


def criteria(res: dict) -> dict:
    data = res.pop("_data")
    s_sand, sand_peaks = data[SAND]
    comp = []
    for nuc, e_gv, a_gv, u_gv, w_gv in GV_SAND:
        p = _nearest(sand_peaks, e_gv)
        row = {"nuclide": nuc, "e_gv": e_gv, "a_gv": a_gv, "u_gv_pct": u_gv, "w_gv": w_gv, "sm": _peak_info(p)}
        if p is not None:
            u_sm = p.net_area_unc / p.net_area
            ratio = p.net_area / a_gv
            row.update(de_kev=round(p.energy - e_gv, 3), area_ratio=round(ratio, 4),
                       area_limit=round(max(0.05, 2 * math.hypot(u_sm, u_gv / 100)), 4),
                       width_ratio=None if p.fwhm_kev is None else round(p.fwhm_kev / w_gv, 4))
        comp.append(row)
    found = [r for r in comp if r["sm"] is not None]
    g1 = len(found) == len(comp) and all(abs(r["de_kev"]) <= 0.10 for r in found)
    area_ok = [abs(r["area_ratio"] - 1) <= r["area_limit"] for r in found]
    median = statistics.median(r["area_ratio"] for r in found) if found else None
    g2 = sum(area_ok) >= 6 and median is not None and 0.97 <= median <= 1.03
    width_ok = [r["width_ratio"] is not None and abs(r["width_ratio"] - 1) <= 0.10 for r in found]
    g3 = sum(width_ok) >= 6
    sand_row = next(r for r in res["spectra"] if r["file"] == SAND)
    missing = [n for n in SAND_NUCLIDES if n not in sand_row["nuclides"]]
    g4 = not missing
    oil_row = next(r for r in res["spectra"] if r["file"] == OIL)
    narrow = [i for i in oil_row["oil_energies"] if i is not None and i["fwhm_kev"] is not None and i["fwhm_kev"] < 0.5]
    g5 = not narrow
    a, b = data["sand sample 2.Spc"][0], s_sand
    g6 = (list(a.counts) == list(b.counts) and a.live_time == b.live_time
          and list(a.energy_coeffs) == list(b.energy_coeffs))
    res["sand_comparison"] = comp
    res["criteria"] = {
        "G1": {"pass": g1, "detail": f"{len(found)}/{len(comp)} matched, max |dE| "
               + (f"{max(abs(r['de_kev']) for r in found):.3f} keV" if found else "-")},
        "G2": {"pass": g2, "detail": f"{sum(area_ok)}/{len(comp)} within limit, median ratio "
               + ("-" if median is None else f"{median:.4f}")},
        "G3": {"pass": g3, "detail": f"{sum(width_ok)}/{len(comp)} within 10 %"},
        "G4": {"pass": g4, "detail": "all identified" if g4 else "missing: " + ", ".join(missing)},
        "G5": {"pass": g5, "detail": f"{len(narrow)} narrow peak(s) at the oil-sample energies"},
        "G6": {"pass": g6, "detail": "identical" if g6 else "different"},
    }
    res["summary"] = {"pass": sum(c["pass"] for c in res["criteria"].values()),
                      "fail": sum(not c["pass"] for c in res["criteria"].values())}
    return res


def write_md(res: dict, path: Path) -> None:
    lines = ["# Laboratory HPGe spectra compared with GammaVision reports (after_GV1)", "",
             "Protocol: `docs/baseline/gammavision_compare_protocol.md`. Spectra outside the repository; "
             "derived numbers only.", "",
             f"**{res['summary']['pass']} PASS / {res['summary']['fail']} FAIL**", "",
             "| ID | result | detail |", "|---|---|---|"]
    for k, c in res["criteria"].items():
        lines.append(f"| {k} | {'PASS' if c['pass'] else 'FAIL'} | {c['detail']} |")
    lines += ["", "## Sand sample 2: peaks", "",
              "| nuclide | E GV | E SM | dE | area GV | area SM | ratio | limit | FWHM GV | FWHM SM | ratio |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in res["sand_comparison"]:
        sm = r["sm"]
        if sm is None:
            lines.append(f"| {r['nuclide']} | {r['e_gv']} | - | - | {r['a_gv']} | - | - | - | {r['w_gv']} | - | - |")
            continue
        lines.append(f"| {r['nuclide']} | {r['e_gv']} | {sm['energy']} | {r['de_kev']:+.3f} | {r['a_gv']} "
                     f"| {sm['net']:.0f} ± {sm['unc_pct']} % | {r['area_ratio']:.4f} | {r['area_limit']:.3f} "
                     f"| {r['w_gv']} | {sm['fwhm_kev']} | {r['width_ratio']} |")
    lines += ["", "## All spectra", "", "| file | live s | counts | peaks | nuclides |", "|---|---|---|---|---|"]
    for r in res["spectra"]:
        lines.append(f"| {r['file']} | {r['live_time_s']} | {r['total_counts']} | {r['peaks']} "
                     f"| {', '.join(r['nuclides']) or '-'} |")
    lines += ["", "## Oil sample 1: SpectraMaster near the GammaVision energies", "",
              "| GV keV | GV area | GV FWHM | SM peak |", "|---|---|---|---|"]
    oil = next(r for r in res["spectra"] if r["file"] == OIL)
    for (e, a, w), i in zip(GV_OIL, oil["oil_energies"]):
        sm = "none (significance >= 3)" if i is None else (
            f"{i['energy']} keV, net {i['net']:.0f}, FWHM {i['fwhm_kev']} keV, sig {i['sig']}")
        lines.append(f"| {e} | {a} | {w} | {sm} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    folder = Path(os.environ.get("SPECTRAMASTER_GV_DIR", str(DEFAULT_DIR)))
    if not folder.is_dir():
        print(f"data folder not found: {folder}", file=sys.stderr)
        return 2
    res = criteria(analyse(folder))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "gammavision_compare.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    write_md(res, OUT / "gammavision_compare.md")
    print(json.dumps(res["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

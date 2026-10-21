"""Cross-check of the bundled library emission probabilities (IAEA ENSDF) against the
independent LNHB/DDEP recommended data (LARA text files, kept outside the repository).

    python -m spectramaster.validation.ddep_check [LARA_DIR]

LARA files: https://www.lnhb.fr/nuclides/<nuclide>.lara.txt (one per nuclide; the folder is
``SPECTRAMASTER_DDEP_DIR`` or D:/SpectraMaster_public_data/lnhb_lara).  Only single library
lines are compared (merged library groups, X-ray groups and chain sums are skipped): a gamma
line of the library entry nuclide >= 1 % matched to a DDEP gamma within 0.1 keV.

``gross``: every such line matched to the nearest DDEP gamma within 0.5 keV instead, listing
intensity ratios outside [0.67, 1.5] (and |z| > 3 where both uncertainties are stated), and the
lines with no DDEP gamma or X-ray within 0.5 keV (the 0.1 keV match above misses those silently).
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Optional


def ddep_folder() -> Optional[Path]:
    root = Path(os.environ.get("SPECTRAMASTER_DDEP_DIR", "D:/SpectraMaster_public_data/lnhb_lara"))
    return root if root.is_dir() and any(root.glob("*.lara.txt")) else None


def read_lara(path: Path) -> dict:
    """{"reference": str, "lines": [(keV, intensity %, unc % or None, type)]}"""
    out = {"reference": "", "lines": []}
    for raw in path.read_text(encoding="latin-1").splitlines():
        parts = [p.strip() for p in raw.split(";")]
        if parts[0] == "Reference" and len(parts) > 1:
            out["reference"] = parts[1]
        if len(parts) < 5:
            continue
        try:
            e, i = float(parts[0]), float(parts[2])
        except ValueError:
            continue
        try:
            u = float(parts[3]) if parts[3] else None
        except ValueError:
            u = None
        out["lines"].append((e, i, u, parts[4]))
    return out


def compare(folder: Path, min_pct: float = 1.0) -> dict:
    from ..analysis.library import load_library
    lib = load_library()
    rows = []
    for name, nd in lib.items():
        f = folder / f"{name}.lara.txt"
        if not f.is_file() or nd.includes:
            continue          # chain sums (daughter lines included) are not comparable line by line
        dd = read_lara(f)
        dg = [l for l in dd["lines"] if l[3] == "g"]
        for l in nd.gammas(min_pct):
            close = [d for d in dg if abs(d[0] - l.energy) <= 0.1]
            if len(close) != 1 or l.intensity_unc is None or close[0][2] is None:
                continue
            e, i, u, _t = close[0]
            s = math.hypot(l.intensity_unc, u)
            z = (l.intensity - i) / s if s > 0 else 0.0
            rows.append({"nuclide": name, "energy": l.energy, "ensdf": l.intensity, "u_ensdf": l.intensity_unc,
                         "ddep": i, "u_ddep": u, "z": z, "rel_diff": l.intensity / i - 1.0,
                         "ddep_reference": dd["reference"]})
    zs = [abs(r["z"]) for r in rows]
    return {"lines": len(rows), "nuclides": len({r["nuclide"] for r in rows}),
            "within_2u": sum(z <= 2 for z in zs) / max(len(zs), 1),
            "within_3u": sum(z <= 3 for z in zs) / max(len(zs), 1),
            "worst": sorted(rows, key=lambda r: -abs(r["z"]))[:15], "rows": rows}


GROSS_RATIO = (0.67, 1.5)
GROSS_Z = 3.0
GROSS_TOL_KEV = 0.5


def gross(folder: Path, min_pct: float = 1.0) -> dict:
    """{"gross": [...], "unmatched": [...]} (see the module docstring)."""
    from ..analysis.library import load_library
    lib = load_library()
    big, lone = [], []
    for name, nd in lib.items():
        f = folder / f"{name}.lara.txt"
        if not f.is_file() or nd.includes:
            continue
        dd = read_lara(f)["lines"]
        dg = [l for l in dd if l[3] == "g"]
        for l in nd.gammas(min_pct):
            near = [d for d in dg if abs(d[0] - l.energy) <= GROSS_TOL_KEV]
            if not near:
                if not any(abs(d[0] - l.energy) <= GROSS_TOL_KEV for d in dd):
                    lone.append({"nuclide": name, "energy": l.energy, "intensity": l.intensity})
                continue
            e, i, u, _t = min(near, key=lambda d: abs(d[0] - l.energy))
            ratio = l.intensity / i if i > 0 else math.inf
            z = None
            if l.intensity_unc is not None and u is not None and math.hypot(l.intensity_unc, u) > 0:
                z = (l.intensity - i) / math.hypot(l.intensity_unc, u)
            if not GROSS_RATIO[0] <= ratio <= GROSS_RATIO[1] and (z is None or abs(z) > GROSS_Z):
                big.append({"nuclide": name, "energy": l.energy, "library": l.intensity, "ddep_energy": e,
                            "ddep": i, "ratio": ratio, "z": z})
    return {"gross": big, "unmatched": lone}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    folder = Path(argv[0]) if argv else ddep_folder()
    if folder is None:
        print("no LARA folder (set SPECTRAMASTER_DDEP_DIR)")
        return 1
    r = compare(folder)
    print(f"{r['lines']} lines of {r['nuclides']} nuclides: |z| <= 2: {100 * r['within_2u']:.1f} %, "
          f"|z| <= 3: {100 * r['within_3u']:.1f} %")
    for w in r["worst"]:
        print(f"  {w['nuclide']:8s} {w['energy']:9.3f} keV  ENSDF {w['ensdf']:.4g}({w['u_ensdf']:.2g})  "
              f"DDEP {w['ddep']:.4g}({w['u_ddep']:.2g})  z = {w['z']:+.1f}  [{w['ddep_reference']}]")
    g = gross(folder)
    print(f"gross differences (nearest DDEP gamma within {GROSS_TOL_KEV} keV, ratio outside {GROSS_RATIO}): "
          f"{len(g['gross'])}")
    for w in g["gross"]:
        zt = "" if w["z"] is None else f"  z = {w['z']:+.1f}"
        print(f"  {w['nuclide']:8s} {w['energy']:9.3f} keV  library {w['library']:.4g} %  "
              f"DDEP {w['ddep_energy']:.3f} keV {w['ddep']:.4g} %  ratio {w['ratio']:.3g}{zt}")
    print(f"library lines >= 1 % with no DDEP gamma or X-ray within {GROSS_TOL_KEV} keV: {len(g['unmatched'])}")
    for w in g["unmatched"]:
        print(f"  {w['nuclide']:8s} {w['energy']:9.3f} keV  {w['intensity']:.4g} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

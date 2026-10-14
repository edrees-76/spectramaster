"""Public reference spectra with documented truth: IAEA G-1 and EML (Sanderson, 1990).

The spectra are not redistributed here; point ``SPECTRAMASTER_REFDATA`` (or ``--refdata``)
at a directory containing ``1- IAEA G-1/الأطياف ASCII/G1*.ASC`` and
``2- Sanderson/الأطياف/*.DAT`` (the layout used on the development machine), or at any
directory where the files can be found recursively.

Truth tables are transcribed from the documentation distributed with the spectra
(G1_DATA.TXT: shifts and attenuation ratios; Sanderson README: multipliers and shifts).
G-1 areas are *ratios* to the G1100 reference spectrum analysed by the same engine, so they
test consistency (search, area linearity, deconvolution), not absolute peak-area accuracy.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Optional

import numpy as np

from ..analysis import find_peaks
from ..convert import read_spectra

DEFAULT_REFDATA = Path("D:/الاسس و المفاهيم العامة فى استخدام برامج الطيف الجامى/اطياف مرجعية")

# --------------------------------------------------------------------------- IAEA G-1
G1_REF = [130, 207, 306, 361, 563, 655, 818, 863, 924, 1011, 1095, 1196, 1300, 1430, 1522, 1574,
          1734, 1823, 1904, 1947]
# (reference position, shift, ratio = G1100 area / test area)
G1200 = [(130, -11, 240.196), (207, 7, 78.652), (306, -21, 133.540), (361, -8, 261.628),
         (563, -42, 58.886), (655, -23, 146.530), (818, -51, 83.879), (818, 9, 138.229),
         (863, 7, 164.773), (924, 3, 109.641), (1011, -44, 142.857), (1095, 12, 283.582),
         (1196, -8, 261.628), (1300, 9, 1014.493), (1430, -32, 963.855), (1430, 37, 1005.578),
         (1522, -5, 2618.182), (1574, -8, 261.628), (1734, 9, 1014.493), (1823, 11, 2222.222),
         (1904, -5, 2618.182), (1947, 14, 616.822)]
G1300 = [(130, 0, 5.309), (207, 0, 24.138), (306, 0, 6.342), (361, 0, 23.316), (563, 0, 8.475),
         (655, 0, 34.337), (818, -43, 8.477), (818, 0, 40.506), (863, 0, 7.592), (924, 0, 38.926),
         (1011, 0, 11.776), (1095, 0, 211.111), (1196, 0, 23.316), (1300, 0, 271.552),
         (1430, 0, 25.442), (1430, 54, 257.143), (1522, 0, 38.919), (1574, 0, 23.316),
         (1734, 0, 271.552), (1823, 0, 336.634), (1904, 0, 38.919), (1947, 0, 55.562)]
# G1400 doublets: (reference, left shift, left ratio, right shift, right ratio)
G1400 = [(1011, -25, 35.241, -24, 3.524), (1011, 21, 9.162, 22, 3.054), (1095, -18, 3.082, -17, 3.082),
         (1095, 23, 55.474, 26, 5.547), (1430, -26, 21.845, -23, 7.282), (1430, 22, 7.767, 25, 7.767),
         (1823, -34, 81.388, -28, 8.139), (1823, 23, 18.314, 29, 6.104), (1947, -19, 8.258, -13, 8.258)]
G1_IGNORE = (1015.0, 1035.0)     # pseudo-Compton-edge artefact region (G-1 notes)
G1_TOL = 2.5                     # channels


def find_refdata(root: Optional[str] = None) -> Optional[Path]:
    for cand in (root, os.environ.get("SPECTRAMASTER_REFDATA"), str(DEFAULT_REFDATA)):
        if cand and Path(cand).is_dir():
            return Path(cand)
    return None


def _find(root: Path, name: str) -> Optional[Path]:
    hits = sorted(root.rglob(name))
    return hits[0] if hits else None


def _match(peaks, positions: list[float], tol: float):
    """Greedy nearest unique matching; returns ({position index: peak index}, unmatched peak indices)."""
    pairs = sorted((abs(p.centroid - x), i, j) for i, x in enumerate(positions)
                   for j, p in enumerate(peaks) if abs(p.centroid - x) <= tol)
    used_t, used_p, m = set(), set(), {}
    for _d, i, j in pairs:
        if i in used_t or j in used_p:
            continue
        m[i] = j
        used_t.add(i)
        used_p.add(j)
    return m, [j for j in range(len(peaks)) if j not in used_p]


def run_g1(root: Path) -> Optional[dict]:
    files = {n: _find(root, f"{n}.ASC") for n in
             ["G1100", "G1200", "G1300", "G1301", "G1302", "G1303", "G1304", "G1305", "G1400"]}
    if not files["G1100"]:
        return None
    spec = {n: read_spectra(p)[0][0] for n, p in files.items() if p}
    ref_peaks = find_peaks(spec["G1100"])
    m, extra = _match(ref_peaks, [float(r) for r in G1_REF], G1_TOL)
    ref = {G1_REF[i]: ref_peaks[j] for i, j in m.items()}
    out: dict = {"G1100_found": len(ref),
                 "G1100_false": sum(1 for j in extra if not G1_IGNORE[0] <= ref_peaks[j].centroid <= G1_IGNORE[1])}

    def score(name, table):
        peaks = find_peaks(spec[name])
        pos = [float(r + s) for r, s, _ in table]
        mm, un = _match(peaks, pos, G1_TOL)
        devs, zs = [], []
        for i, j in mm.items():
            r, _s, ratio = table[i]
            if r not in ref:
                continue
            p, q = peaks[j], ref[r]
            expect = q.net_area / ratio
            dev = p.net_area / expect - 1.0
            rel = math.hypot(p.net_area_unc / max(p.net_area, 1e-9), q.net_area_unc / q.net_area)
            devs.append(dev)
            zs.append(dev / max(rel * (1 + dev), 1e-12))
        false = sum(1 for j in un if not G1_IGNORE[0] <= peaks[j].centroid <= G1_IGNORE[1])
        return len(mm), false, devs, zs

    if "G1200" in spec:
        f, fp, devs, _ = score("G1200", G1200)
        out.update(G1200_found=f, G1200_false=fp,
                   G1200_area_dev_median_abs=float(np.median(np.abs(devs))) if devs else None)
    rec, devs_all, zs_all, fps = [], [], [], []
    for k in range(6):
        n = f"G130{k}"
        if n in spec:
            f, fp, devs, zs = score(n, G1300)
            rec.append(f / len(G1300))
            fps.append(fp)
            devs_all += devs
            zs_all += zs
    if rec:
        za = np.abs(zs_all)
        out.update(G1300_recall_mean=float(np.mean(rec)), G1300_false_total=int(sum(fps)),
                   G1300_area_ratio_bias=float(np.mean(devs_all)),
                   G1300_area_dev_median_abs=float(np.median(np.abs(devs_all))),
                   G1300_z_cov1=float(np.mean(za <= 1)), G1300_z_cov2=float(np.mean(za <= 2)),
                   G1300_n=len(devs_all))
    if "G1400" in spec:
        peaks = find_peaks(spec["G1400"])
        by_sep: dict[int, int] = {}
        detail = []
        for r, ls, lr, rs, rr in G1400:
            sep = rs - ls
            lo, hi = r + ls - 1.5, r + rs + 1.5
            inside = [p for p in peaks if lo <= p.centroid <= hi]
            ok = len(inside) >= 2
            by_sep[sep] = by_sep.get(sep, 0) + int(ok)
            row = {"left": r + ls, "right": r + rs, "sep": sep, "ratio_LR": round(lr and rr / lr, 3),
                   "n_reported": len(inside), "resolved": ok}
            if ok and r in ref:
                a = sorted(inside, key=lambda p: p.centroid)
                row["area_dev_left"] = a[0].net_area / (ref[r].net_area / lr) - 1
                row["area_dev_right"] = a[-1].net_area / (ref[r].net_area / rr) - 1
            detail.append(row)
        out.update(G1400_resolved_sep_ge6=by_sep.get(6, 0), G1400_resolved_sep3=by_sep.get(3, 0),
                   G1400_resolved_sep1=by_sep.get(1, 0), G1400_detail=detail)
    return out


# --------------------------------------------------------------------------- EML / Sanderson
EML_CAL_LINES = [59.5, 88.0, 122.0, 166.0, 279.0, 392.0, 514.0, 662.0, 898.0, 1173.0, 1332.0, 1836.0]
EML_TEST_LINES = [122.0, 662.0, 1332.0]
EML_MULT = {1: 0.1, 2: 0.05, 3: 0.01, 4: 0.005, 5: 0.001, 6: 0.0005, 7: 0.00025, 8: 0.0001, 9: 0.0}
EML_DOUBLE_EQ = {k: k - 9 for k in range(10, 20)}           # TEST10..19: shift 1..10, equal 0.01
EML_DOUBLE_RATIO = {20: (0.1, 0.1), 21: (0.1, 0.08), 22: (0.1, 0.06), 23: (0.1, 0.04), 24: (0.1, 0.02),
                    25: (0.1, 0.01), 26: (0.1, 0.005), 27: (0.08, 0.1), 28: (0.06, 0.1),
                    29: (0.04, 0.1), 30: (0.02, 0.1), 31: (0.01, 0.1), 32: (0.005, 0.1)}   # shift 4


def _eml_calibration(cal_spec) -> Optional[np.ndarray]:
    """Linear channel->keV from CALIBR01 (certificate energies, nearest-peak iteration)."""
    peaks = sorted(find_peaks(cal_spec), key=lambda p: -p.net_area)[:25]
    if len(peaks) < 6:
        return None
    gain, off = 0.5, 0.0                      # starting guess: documented ~0.5 keV/channel
    for tol in (25.0, 6.0, 3.0):
        pairs = []
        for e in EML_CAL_LINES:
            c = min(peaks, key=lambda p: abs(off + gain * p.centroid - e))
            if abs(off + gain * c.centroid - e) <= tol:
                pairs.append((c.centroid, e))
        if len(pairs) < 4:
            return None
        x, y = np.array(pairs).T
        gain, off = np.polyfit(x, y, 1)
    return np.array([off, gain])


def run_eml(root: Path) -> Optional[dict]:
    cal = _find(root, "CALIBR01.DAT")
    if not cal:
        return None
    coef = _eml_calibration(read_spectra(cal)[0][0])
    if coef is None:
        return {"error": "CALIBR01 calibration failed"}
    off, gain = coef
    chan = {e: (e - off) / gain for e in EML_TEST_LINES}
    out: dict = {"calibration_keV": [float(off), float(gain)]}
    areas: dict[int, dict] = {}
    detected: dict[float, list] = {e: [] for e in EML_TEST_LINES}
    for k, mult in EML_MULT.items():
        p = _find(root, f"TEST{k:02d}.DAT")
        if not p:
            continue
        peaks = find_peaks(read_spectra(p)[0][0])
        row = {}
        for e, c in chan.items():
            near = [q for q in peaks if abs(q.centroid - c) <= 3.0]
            if near:
                q = min(near, key=lambda q: abs(q.centroid - c))
                row[e] = (q.net_area, q.net_area_unc)
                if mult > 0:
                    detected[e].append(mult)
        areas[k] = row
    bkg = _find(root, "BKG.DAT")
    bkg_peaks = find_peaks(read_spectra(bkg)[0][0]) if bkg else []
    in_bkg = {e for e, c in chan.items() if any(abs(q.centroid - c) <= 3.0 for q in bkg_peaks)}
    out["TEST09_false_at_lines"] = sum(1 for e in areas.get(9, {}) if e not in in_bkg)
    out["lines_in_BKG"] = sorted(in_bkg)
    devs = []
    lin = {}
    for e in EML_TEST_LINES:
        if e not in areas.get(1, {}):
            continue
        a1, u1 = areas[1][e]
        r1 = a1 / EML_MULT[1]
        rows = []
        for k in range(2, 9):
            if e in areas.get(k, {}):
                a, u = areas[k][e]
                r = a / EML_MULT[k]
                sig = math.hypot(u / EML_MULT[k], u1 / EML_MULT[1])
                rows.append({"test": k, "ratio_to_TEST01": r / r1, "dev_sigma": (r - r1) / sig})
                if k <= 5:
                    devs.append(abs((r - r1) / sig))
        lin[str(e)] = rows
    out["linearity"] = lin
    out["linearity_dev_max_sig"] = max(devs) if devs else None
    out["lowest_multiplier_detected"] = {str(e): (min(v) if v else None) for e, v in detected.items()}

    def doublet_found(k, sep):
        p = _find(root, f"TEST{k:02d}.DAT")
        if not p:
            return None
        peaks = find_peaks(read_spectra(p)[0][0])
        res = {}
        for e, c in chan.items():
            inside = [q for q in peaks if c - 2.0 <= q.centroid <= c + sep + 2.0]
            res[str(e)] = len(inside)
        return res

    out["doublet_resolved_by_shift"] = {f"TEST{k:02d} shift={s}": doublet_found(k, s)
                                        for k, s in EML_DOUBLE_EQ.items()}
    out["doublet_ratio_shift4"] = {f"TEST{k:02d} {a:g}:{b:g}": doublet_found(k, 4)
                                   for k, (a, b) in EML_DOUBLE_RATIO.items()}
    return out

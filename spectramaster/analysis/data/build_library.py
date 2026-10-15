"""Build the bundled gamma-line library ``gamma_library.json``.

Reproducible, offline-capable builder.  Inputs (see SOURCES.md):

* ``source/sandia.decay.nocoinc.min.xml`` - SandiaDecay (ENSDF-derived, decay chains,
  LGPL-2.1).  Always required.
* IAEA ENSDF decay radiations, taken from the IAEA-NDS "ndlab" SQLite database (the
  data behind LiveChart).  Either pass ``--ndlab path/to/ndlab_db.s3db`` (the extract
  ``source/iaea_ndlab_extract.json`` is then regenerated) or rely on that cached
  extract.

Usage::

    python spectramaster/analysis/data/build_library.py [--ndlab ndlab_db.s3db] [-v]

Intensity convention written to the JSON
----------------------------------------
``lines`` = ``[energy_keV, intensity_percent, kind, src]`` where intensity is the
number of photons per 100 decays of the *entry* nuclide, **including** the short-lived
daughters listed in ``includes`` weighted by their decay branching and their
equilibrium activity ratio ``lambda_d / (lambda_d - lambda_p)`` (secular or transient
equilibrium, e.g. Cs-137 -> Ba-137m, Ce-144 -> Pr-144, Ba-140 -> La-140).
Natural-series members (Pb-214, Bi-214, Tl-208 ...) are separate entries with their own
per-decay intensities; ``series`` names the chain and ``series_factor`` is the activity of
the member relative to the series head at secular equilibrium (Tl-208: 0.3594).
``kind``: "g" gamma, "x" X-ray, "a" annihilation (511 keV from positrons).
``src``: "I" value from IAEA ENSDF (preferred), "S" from SandiaDecay only.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDIA_XML = HERE / "source" / "sandia.decay.nocoinc.min.xml"
IAEA_EXTRACT = HERE / "source" / "iaea_ndlab_extract.json"
OUT = HERE / "gamma_library.json"

MIN_INTENSITY = 0.05      # % per decay, gammas kept
MIN_XRAY = 1.0            # % per decay, X-rays kept (K lines >= 10 keV, L lines only if big)
MAX_LINES = 40
EMIN, EMAX = 10.0, 3600.0
AUTO_INCLUDE_HL = 600.0   # s: daughters shorter than this are folded into the parent

# name, category, explicit includes, note
# Categories: calibration, natural, fission, activation, medical, industrial, cosmogenic, actinide.
# Nuclides with two common origins use "primary/secondary" (Cs-137 "fission/calibration").
SPECS: list[tuple[str, str, list[str], str]] = [
    # --- calibration / check sources
    ("Am-241", "actinide/calibration", [], ""),
    ("Ba-133", "calibration/activation", [], ""),
    ("Cd-109", "calibration", ["Ag-109m"], ""),
    ("Ce-139", "calibration", [], ""),
    ("Co-57", "calibration", [], ""),
    ("Co-60", "activation/calibration", [], ""),
    ("Cs-137", "fission/calibration", ["Ba-137m"], ""),
    ("Eu-152", "activation/calibration", [], ""),
    ("Eu-154", "activation/calibration", [], ""),
    ("Eu-155", "fission/calibration", [], ""),
    ("Hg-203", "calibration", [], ""),
    ("Mn-54", "activation/calibration", [], ""),
    ("Na-22", "calibration/cosmogenic", [], ""),
    ("Sn-113", "calibration", ["In-113m"], ""),
    ("Sr-85", "calibration", [], ""),
    ("Y-88", "calibration", [], ""),
    ("Zn-65", "activation/calibration", [], ""),
    ("Bi-207", "calibration", [], ""),
    ("Co-56", "calibration", [], ""),
    ("Gd-153", "calibration", [], ""),
    ("Ti-44", "calibration", ["Sc-44"], ""),
    ("Ba-131", "activation", [], ""),
    # --- natural: primordial, U-238 series
    ("K-40", "natural", [], "primordial"),
    ("Th-234", "natural", [], ""),
    ("Pa-234m", "natural", [], ""),
    ("Pa-234", "natural", [], ""),
    ("U-234", "natural", [], ""),
    ("Th-230", "natural", [], ""),
    ("Ra-226", "natural", [], ""),
    ("Pb-214", "natural", [], ""),
    ("Bi-214", "natural", [], ""),
    ("Pb-210", "natural", [], ""),
    # U-235 (actinium) series
    ("U-235", "natural", [], ""),
    ("Th-231", "natural", [], ""),
    ("Pa-231", "natural", [], ""),
    ("Th-227", "natural", [], ""),
    ("Ra-223", "natural", [], ""),
    ("Rn-219", "natural", [], ""),
    ("Pb-211", "natural", [], ""),
    ("Bi-211", "natural", [], ""),
    ("Tl-207", "natural", [], ""),
    # Th-232 series
    ("Th-232", "natural", [], ""),
    ("Ac-228", "natural", [], ""),
    ("Th-228", "natural", [], ""),
    ("Ra-224", "natural", [], ""),
    ("Pb-212", "natural", [], ""),
    ("Bi-212", "natural", [], ""),
    ("Tl-208", "natural", [], ""),
    # other natural / cosmogenic
    ("La-138", "natural", [], "primordial"),
    ("Lu-176", "natural", [], "primordial"),
    ("Be-7", "cosmogenic", [], ""),
    ("Na-24", "activation", [], ""),
    # --- fission products
    ("Cs-134", "fission", [], "activation of Cs-133 in reactors"),
    ("Cs-136", "fission", [], ""),
    ("Cs-138", "fission", [], ""),
    ("I-131", "fission/medical", [], ""),
    ("I-132", "fission", [], ""),
    ("I-133", "fission", [], ""),
    ("I-134", "fission", [], ""),
    ("I-135", "fission", [], ""),
    ("Te-132", "fission", ["I-132"], "with I-132 in transient equilibrium"),
    ("Te-129m", "fission", [], ""),
    ("Te-131m", "fission", [], ""),
    ("Ba-140", "fission", ["La-140"], "with La-140 in transient equilibrium"),
    ("La-140", "fission", [], ""),
    ("Ce-141", "fission", [], ""),
    ("Ce-143", "fission", [], ""),
    ("Ce-144", "fission", ["Pr-144"], "with Pr-144"),
    ("Ru-103", "fission", ["Rh-103m"], ""),
    ("Ru-106", "fission", ["Rh-106"], "with Rh-106"),
    ("Rh-105", "fission", [], ""),
    ("Zr-95", "fission", [], ""),
    ("Nb-95", "fission", [], ""),
    ("Zr-97", "fission", ["Nb-97"], ""),
    ("Mo-99", "fission/medical", ["Tc-99m"], "with Tc-99m"),
    ("Sb-125", "fission", ["Te-125m"], ""),
    ("Sb-127", "fission", [], ""),
    ("Sb-126", "fission", [], ""),
    ("Sn-126", "fission", [], ""),
    ("Nd-147", "fission", [], ""),
    ("Pm-151", "fission", [], ""),
    ("Sr-91", "fission", [], ""),
    ("Sr-92", "fission", [], ""),
    ("Y-91", "fission", [], ""),
    ("Y-93", "fission", [], ""),
    ("Eu-156", "fission", [], ""),
    ("Xe-133", "fission/medical", [], ""),
    ("Xe-133m", "fission", [], ""),
    ("Xe-135", "fission", [], ""),
    ("Xe-131m", "fission", [], ""),
    ("Kr-85", "fission", [], ""),
    ("Kr-85m", "fission", [], ""),
    ("Kr-87", "fission", [], ""),
    ("Kr-88", "fission", ["Rb-88"], ""),
    ("Ba-139", "fission", [], ""),
    ("La-141", "fission", [], ""),
    ("Ag-111", "fission", [], ""),
    ("Pd-112", "fission", ["Ag-112"], ""),
    ("Np-239", "actinide", [], ""),
    ("U-237", "actinide", [], "Pu-241 daughter"),
    # --- activation products
    ("Ag-110m", "activation", [], ""),
    ("Ag-108m", "activation", [], ""),
    ("Sb-124", "activation", [], ""),
    ("Sb-122", "activation", [], ""),
    ("Co-58", "activation", [], ""),
    ("Fe-59", "activation", [], ""),
    ("Cr-51", "activation", [], ""),
    ("Sc-46", "activation", [], ""),
    ("Sc-47", "activation", [], ""),
    ("Sc-48", "activation", [], ""),
    ("Mn-56", "activation", [], ""),
    ("Mn-52", "activation", [], ""),
    ("Mg-27", "activation", [], ""),
    ("Mg-28", "activation", ["Al-28"], ""),
    ("Al-26", "activation", [], ""),
    ("Al-28", "activation", [], ""),
    ("Ar-41", "activation", [], ""),
    ("Cl-38", "activation", [], ""),
    ("K-42", "activation", [], ""),
    ("K-43", "activation", [], ""),
    ("Ca-47", "activation", ["Sc-47"], ""),
    ("V-48", "activation", [], ""),
    ("Ni-57", "activation", [], ""),
    ("Ni-65", "activation", [], ""),
    ("Cu-64", "activation", [], ""),
    ("Zn-69m", "activation", [], ""),
    ("Ga-72", "activation", [], ""),
    ("As-74", "activation", [], ""),
    ("As-76", "activation", [], ""),
    ("Se-75", "industrial", [], ""),
    ("Br-82", "activation", [], ""),
    ("Rb-84", "activation", [], ""),
    ("Rb-86", "activation", [], ""),
    ("Sr-87m", "activation", [], ""),
    ("Y-87", "activation", [], ""),
    ("Nb-94", "activation", [], ""),
    ("Cd-115", "activation", ["In-115m"], ""),
    ("In-114m", "activation", [], ""),
    ("In-116m", "activation", [], ""),
    ("Sn-117m", "activation", [], ""),
    ("Sn-123m", "activation", [], ""),
    ("Te-123m", "activation", [], ""),
    ("Cs-132", "activation", [], ""),
    ("Ce-143", "fission", [], ""),
    ("Pr-142", "activation", [], ""),
    ("Sm-153", "medical", [], ""),
    ("Eu-152m", "activation", [], ""),
    ("Tb-160", "activation", [], ""),
    ("Dy-165", "activation", [], ""),
    ("Ho-166", "medical", [], ""),
    ("Ho-166m", "activation", [], ""),
    ("Er-171", "activation", [], ""),
    ("Tm-170", "industrial", [], ""),
    ("Yb-169", "industrial", [], ""),
    ("Yb-175", "activation", [], ""),
    ("Hf-175", "activation", [], ""),
    ("Hf-181", "activation", [], ""),
    ("Ta-182", "activation", [], ""),
    ("W-187", "activation", [], ""),
    ("Re-186", "medical", [], ""),
    ("Re-188", "medical", [], ""),
    ("Os-191", "activation", [], ""),
    ("Ir-192", "industrial", [], ""),
    ("Ir-194", "activation", [], ""),
    ("Au-198", "activation", [], ""),
    ("Au-199", "activation", [], ""),
    ("Hg-197", "activation", [], ""),
    ("Pt-197", "activation", [], ""),
    ("Fe-52", "activation", ["Mn-52m"], ""),
    ("Co-55", "activation", [], ""),
    ("Zr-89", "medical", [], ""),
    ("Zn-62", "activation", [], ""),
    # --- medical
    ("Tc-99m", "medical", [], ""),
    ("F-18", "medical", [], ""),
    ("C-11", "medical", [], ""),
    ("N-13", "medical", [], ""),
    ("Ga-67", "medical", [], ""),
    ("Ga-68", "medical", [], ""),
    ("Ge-68", "medical", ["Ga-68"], "with Ga-68"),
    ("In-111", "medical", [], ""),
    ("Tl-201", "medical", [], ""),
    ("Lu-177", "medical", [], ""),
    ("Lu-177m", "activation", [], ""),
    ("I-123", "medical", [], ""),
    ("I-124", "medical", [], ""),
    ("I-125", "medical", [], ""),
    ("Xe-127", "medical", [], ""),
    ("Rb-81", "medical", ["Kr-81m"], ""),
    ("Sr-82", "medical", ["Rb-82"], "with Rb-82"),
    ("Cu-67", "medical", [], ""),
    ("Y-90", "medical", [], "pure beta (bremsstrahlung only)"),
    # --- actinides / industrial
    ("Pu-238", "actinide", [], ""),
    ("Pu-239", "actinide", [], ""),
    ("Pu-240", "actinide", [], ""),
    ("Am-243", "actinide", ["Np-239"], "with Np-239"),
    ("Np-237", "actinide", ["Pa-233"], "with Pa-233"),
    ("Pa-233", "actinide", [], ""),
    ("U-232", "actinide", [], ""),
    ("U-233", "actinide", [], ""),
    ("Cm-244", "actinide", [], ""),
    ("Cf-252", "actinide", [], ""),
]

SERIES = {
    "U-238 series": {"Th-234": 1.0, "Pa-234m": 1.0, "Pa-234": 0.0016, "U-234": 1.0, "Th-230": 1.0,
                     "Ra-226": 1.0, "Pb-214": 1.0, "Bi-214": 1.0, "Pb-210": 1.0},
    "U-235 series": {"U-235": 1.0, "Th-231": 1.0, "Pa-231": 1.0, "Th-227": 0.986, "Ra-223": 1.0,
                     "Rn-219": 1.0, "Pb-211": 1.0, "Bi-211": 1.0, "Tl-207": 1.0},
    "Th-232 series": {"Th-232": 1.0, "Ac-228": 1.0, "Th-228": 1.0, "Ra-224": 1.0, "Pb-212": 1.0,
                      "Bi-212": 1.0, "Tl-208": 0.3594},
}
SERIES_SUBGROUP = {  # how a lab usually names the sub-chain the member belongs to
    "Pb-214": "Ra-226", "Bi-214": "Ra-226", "Ra-226": "Ra-226", "Pb-210": "Pb-210",
    "Th-234": "U-238", "Pa-234m": "U-238", "Pa-234": "U-238", "U-234": "U-234", "Th-230": "Th-230",
    "Ac-228": "Ra-228", "Pb-212": "Th-228", "Bi-212": "Th-228", "Tl-208": "Th-228",
    "Th-228": "Th-228", "Ra-224": "Th-228",
}
BACKGROUND = {"K-40", "Bi-214", "Pb-214", "Ra-226", "Pb-210", "Ac-228", "Pb-212", "Bi-212", "Tl-208",
              "Th-234", "Pa-234m", "U-235", "Be-7", "Th-228", "Ra-224", "Cs-137"}


# ---------------------------------------------------------------- name helpers
def sandia_name(n: str) -> str:
    return n.replace("-", "")


def iaea_key(n: str) -> tuple[str, bool]:
    el, rest = n.split("-")
    m = re.match(r"(\d+)(m\d?)?$", rest)
    return f"{m.group(1)}{el.upper()}", bool(m.group(2))


def fmt_half_life(sec: float) -> str:
    if sec is None or math.isinf(sec):
        return "stable"
    for unit, div in (("y", 31557600.0), ("d", 86400.0), ("h", 3600.0), ("min", 60.0), ("s", 1.0)):
        if sec >= div or unit == "s":
            v = sec / div
            return f"{v:.4g} {unit}" if v < 1e5 else f"{v:.3e} {unit}"
    return f"{sec} s"


# ------------------------------------------------------------------- Sandia
class Sandia:
    def __init__(self, path: Path):
        root = ET.parse(path).getroot()
        ns = "{sandia.decay.xsd}"
        self.hl: dict[str, float] = {}
        for n in root.iter(ns + "n"):
            hl = n.get("hl")
            self.hl[n.get("s")] = float("inf") if hl in (None, "INF") else float(hl)
        self.trans: dict[str, list[dict]] = {}
        for t in root.iter(ns + "t"):
            rec = {"child": t.get("c"), "br": float(t.get("br", "1")), "mode": t.get("m"),
                   "g": [], "x": [], "pos": 0.0}
            for ch in t:
                tag = ch.tag.replace(ns, "")
                if tag == "g":
                    rec["g"].append((float(ch.get("e")), float(ch.get("i"))))
                elif tag == "x":
                    rec["x"].append((float(ch.get("e")), float(ch.get("i")), ch.get("l", "")))
                elif tag == "p":
                    rec["pos"] += float(ch.get("i"))
            self.trans.setdefault(t.get("p"), []).append(rec)

    def own_lines(self, s: str) -> list[tuple[float, float, str]]:
        """Per decay of s (fractions)."""
        out: list[tuple[float, float, str]] = []
        pos = 0.0
        xr: dict[str, list[tuple[float, float]]] = {}
        for t in self.trans.get(s, []):
            br = t["br"]
            for e, i in t["g"]:
                out.append((e, br * i, "g"))
            for e, i, lab in t["x"]:
                grp = "KA1" if lab == "Ka1" else "KA2" if lab == "Ka2" else "KB" if lab.startswith("Kb") else "L"
                xr.setdefault(grp, []).append((e, br * i))
            pos += br * t["pos"]
        for grp, items in xr.items():
            tot = sum(i for _, i in items)
            if tot > 0:
                out.append((sum(e * i for e, i in items) / tot, tot, "x"))
        if pos > 0:
            out.append((510.999, 2 * pos, "a"))
        return out

    def children(self, s: str) -> list[tuple[str, float]]:
        res: dict[str, float] = {}
        for t in self.trans.get(s, []):
            if t["child"]:
                res[t["child"]] = res.get(t["child"], 0.0) + t["br"]
        return list(res.items())


def eq_factor(hl_parent: float, hl_daughter: float) -> float:
    if math.isinf(hl_parent) or hl_parent > 1e3 * hl_daughter:
        return 1.0
    lp, ld = math.log(2) / hl_parent, math.log(2) / hl_daughter
    if ld <= lp:
        return 1.0   # no equilibrium; caller should not include such daughters
    return ld / (ld - lp)


def chain_members(sd: Sandia, name: str, includes: list[str], entry_names: set[str]
                  ) -> list[tuple[str, float]]:
    """[(nuclide, activity per decay of `name`)] including `name` itself (factor 1)."""
    s0 = sandia_name(name)
    explicit = {sandia_name(x) for x in includes}
    entries = {sandia_name(x) for x in entry_names}
    out = [(s0, 1.0)]
    stack = [(s0, 1.0)]
    while stack:
        p, f = stack.pop()
        for c, br in sd.children(p):
            hl_c = sd.hl.get(c, float("inf"))
            if math.isinf(hl_c):
                continue
            if c in explicit or (hl_c < AUTO_INCLUDE_HL and c not in entries):
                fac = f * br * eq_factor(sd.hl.get(p, float("inf")), hl_c)
                out.append((c, fac))
                stack.append((c, fac))
    return out


# --------------------------------------------------------------------- IAEA
def extract_iaea(db: Path, wanted: list[tuple[str, bool, float]]) -> dict:
    con = sqlite3.connect(str(db))
    res: dict = {}
    for key, meta, hl_ref in wanted:
        nucid = key
        if meta:
            rows = con.execute("select l_seqno, half_life, half_life_units, half_life_sec from levels "
                               "where nucid=? and metastable like 'M%' and half_life_sec>0", (nucid,)).fetchall()
            # several isomers: take the one whose half-life is closest to SandiaDecay's
            rows.sort(key=lambda r: abs(math.log(r[3] / hl_ref)) if hl_ref and r[3] else 1e9)
        else:
            rows = con.execute("select l_seqno, half_life, half_life_units, half_life_sec from levels "
                               "where nucid=? and l_seqno=0", (nucid,)).fetchall()
        if not rows:
            continue
        lseq, hl, hlu, hls = rows[0]
        rads = con.execute(
            "select type_b, type_c, energy, intensity, intensity_unc from decay_radiations "
            "where parent_nucid=? and parent_l_seqno=? and type_a='G' and energy is not null "
            "and intensity is not null", (nucid, lseq)).fetchall()
        res[key + ("m" if meta else "")] = {
            "half_life": f"{hl} {hlu}".strip(), "half_life_s": hls,
            "rad": [[tb or "", tc or "", e, i, u] for tb, tc, e, i, u in rads],
        }
    return res


def iaea_own_lines(rec: dict) -> list[tuple[float, float, str]]:
    out = []
    agg: dict[tuple[float, str], float] = {}
    for tb, tc, e, i, _u in rec["rad"]:
        kind = "x" if tb == "X" else "a" if tb == "AN" else "g"
        k = (round(e, 3), kind)
        agg[k] = agg.get(k, 0.0) + i / 100.0
    for (e, kind), i in agg.items():
        out.append((e, i, kind))
    return out


def iaea_own_lines_u(rec: dict) -> list[tuple[float, float, str, float | None]]:
    """As iaea_own_lines, with the absolute intensity uncertainty (fraction per decay) combined in
    quadrature over the aggregated entries; None when an entry has no stated uncertainty."""
    agg: dict[tuple[float, str], list] = {}
    for tb, tc, e, i, u in rec["rad"]:
        kind = "x" if tb == "X" else "a" if tb == "AN" else "g"
        a = agg.setdefault((round(e, 3), kind), [0.0, 0.0])
        a[0] += i / 100.0
        if a[1] is not None:
            a[1] = None if u is None else a[1] + (u / 100.0) ** 2
    return [(e, i, kind, None if v is None else v ** 0.5) for (e, kind), (i, v) in agg.items()]


def merge_close_u(lines, tol=0.05):
    """merge_close carrying the uncertainty (quadrature; None stays None)."""
    lines = sorted(lines, key=lambda r: r[:3])
    out = []
    for e, i, k, u in lines:
        if out and abs(out[-1][0] - e) < tol and out[-1][2] == k:
            pe, pi, pk, pu = out[-1]
            nu = None if (pu is None or u is None) else (pu * pu + u * u) ** 0.5
            out[-1] = ((pe * pi + e * i) / (pi + i) if pi + i > 0 else e, pi + i, k, nu)
        else:
            out.append((e, i, k, u))
    return out


def iaea_rec_for(iaea: dict, sandia_sym: str) -> dict | None:
    m = re.match(r"([A-Z][a-z]?)(\d+)(m\d?)?$", sandia_sym)
    if not m:
        return None
    key = f"{m.group(2)}{m.group(1).upper()}" + ("m" if m.group(3) else "")
    return iaea.get(key)


# -------------------------------------------------------------------- build
def merge_close(lines, tol=0.05):
    lines = sorted(lines)
    out = []
    for e, i, k in lines:
        if out and abs(out[-1][0] - e) < tol and out[-1][2] == k:
            pe, pi, pk = out[-1]
            out[-1] = ((pe * pi + e * i) / (pi + i) if pi + i > 0 else e, pi + i, k)
        else:
            out.append((e, i, k))
    return out


_GMIN = [MIN_INTENSITY]


def keep(e, i, k):
    if not (EMIN <= e <= EMAX):
        return False
    if k == "x":
        return i * 100 >= MIN_XRAY
    return i * 100 >= _GMIN[0]


def build(verbose=False):
    sd = Sandia(SANDIA_XML)
    iaea = json.loads(IAEA_EXTRACT.read_text(encoding="utf-8"))["nuclides"] if IAEA_EXTRACT.exists() else {}
    names = [s[0] for s in SPECS]
    entry_names = set(names)
    library: dict = {}
    n_flags = 0
    seen = set()
    for name, cat, includes, note in SPECS:
        if name in seen:
            continue
        seen.add(name)
        s0 = sandia_name(name)
        if s0 not in sd.hl:
            print(f"WARNING: {name} not in SandiaDecay", file=sys.stderr)
            continue
        members = chain_members(sd, name, includes, entry_names - {name} - set(includes))
        # Sandia lines
        s_lines = []
        for m, f in members:
            for e, i, k in sd.own_lines(m):
                s_lines.append((e, i * f, k))
        s_lines = merge_close(s_lines)
        # IAEA lines: parent dataset first, daughters only for lines the parent does not list
        i_lines: list[tuple[float, float, str]] = []
        i_lines_u: list = []
        have_iaea = False
        for idx, (m, f) in enumerate(members):
            rec = iaea_rec_for(iaea, m)
            if rec is None:
                continue
            have_iaea = True
            for (e, i, k), (_e, _i, _k, u) in zip(iaea_own_lines(rec), iaea_own_lines_u(rec)):
                if idx > 0 and any(abs(e - pe) < 0.5 and pk == k for pe, _, pk in i_lines):
                    continue
                i_lines.append((e, i * f, k))
                i_lines_u.append((e, i * f, k, None if u is None else u * f))
        i_lines = merge_close(i_lines)
        i_lines_u = merge_close_u(i_lines_u)
        # the uncertainty-carrying merge must reproduce the values exactly
        assert [(round(a, 9), round(b, 12), c) for a, b, c in i_lines] == \
            [(round(a, 9), round(b, 12), c) for a, b, c, _u in i_lines_u], name
        unc_of = {(round(e, 3), k): u for e, i, k, u in i_lines_u}
        # weak emitters (Pu-239, U-238 ...): keep lines down to 2 % of the strongest gamma
        gmax = max([i for e, i, k in s_lines + i_lines if k == "g" and EMIN <= e <= EMAX] or [0.0])
        _GMIN[0] = min(MIN_INTENSITY, max(0.02 * gmax * 100, 1e-4))
        # merge with provenance
        flags = []
        final = []
        pairs = []
        for a, (e, i, k) in enumerate(s_lines):
            tol = 1.0 if k != "g" else 0.3
            for j, (ie, ii, ik) in enumerate(i_lines):
                if ik == k and abs(ie - e) <= tol:
                    pairs.append((abs(ie - e) - 1e-3 * min(1.0, min(i, ii) / max(i, ii, 1e-12)), a, j))
        pairs.sort()
        s_match: dict[int, int] = {}
        used_i: set[int] = set()
        for _d, a, j in pairs:
            if a in s_match or j in used_i:
                continue
            s_match[a] = j
            used_i.add(j)
        for a, (e, i, k) in enumerate(s_lines):
            if a in s_match:
                ie, ii, ik = i_lines[s_match[a]]
                if keep(ie, max(ii, i), k):
                    final.append((ie, ii, k, "I"))
                    big = max(ii, i) * 100 >= 1.0
                    if k == "g" and big and (abs(ie - e) > 0.1 or abs(ii - i) > 0.05 * max(ii, i)):
                        flags.append(f"{ie:.3f} keV: IAEA {ii*100:.4g}% vs Sandia {e:.3f} keV {i*100:.4g}%")
            elif keep(e, i, k):
                if have_iaea and (e < 40.0 or k == "x"):
                    continue   # low-energy Sandia-only lines (often conversion/L-shell artefacts): trust IAEA
                final.append((e, i, k, "S"))
                if have_iaea and k == "g" and i * 100 >= 1.0:
                    flags.append(f"{e:.3f} keV {i*100:.4g}%: Sandia only (no IAEA line)")
        for j, (ie, ii, ik) in enumerate(i_lines):
            if j not in used_i and keep(ie, ii, ik):
                final.append((ie, ii, ik, "I"))
                if ik == "g" and ii * 100 >= 1.0:
                    flags.append(f"{ie:.3f} keV {ii*100:.4g}%: IAEA only (no Sandia line)")
        final.sort(key=lambda r: -r[1])
        final = final[:MAX_LINES]
        final.sort(key=lambda r: r[0])
        n_flags += len(flags)
        rec0 = iaea_rec_for(iaea, s0)
        hl_s = sd.hl[s0]
        if rec0 and rec0.get("half_life"):
            val, _, unit = rec0["half_life"].partition(" ")
            unit = {"Y": "y", "D": "d", "H": "h", "M": "min", "m": "min", "S": "s"}.get(unit, unit)
            hl_txt = f"{val} {unit}"
        else:
            hl_txt = fmt_half_life(hl_s)
        series = ""
        sfac = 1.0
        for sname, mem in SERIES.items():
            if name in mem:
                series, sfac = sname, mem[name]
        entry = {
            "half_life": hl_txt,
            "half_life_s": (rec0.get("half_life_s") if rec0 and rec0.get("half_life_s") else
                            (None if math.isinf(hl_s) else hl_s)),
            "category": cat,
            "lines": [[round(e, 3), float(f"{i*100:.4g}"), k, src]
                      + ([float(f"{unc_of[(round(e, 3), k)] * 100:.3g}")]
                         if src == "I" and unc_of.get((round(e, 3), k)) else [])
                      for e, i, k, src in final],
        }
        inc: dict[str, float] = {}
        for m, f in members[1:]:
            nm = re.sub(r"([A-Z][a-z]?)(\d+)(m?\d?)", r"\1-\2\3", m)
            inc[nm] = inc.get(nm, 0.0) + f
        if inc:
            entry["includes"] = list(inc)
            entry["include_factors"] = [round(f, 5) for f in inc.values()]
        if series:
            entry["series"] = series
            entry["series_factor"] = sfac
            if name in SERIES_SUBGROUP:
                entry["subgroup"] = SERIES_SUBGROUP[name]
        if name in BACKGROUND:
            entry["background"] = True
        if note:
            entry["note"] = note
        entry["provenance"] = {"sandia": True, "iaea": have_iaea, "flags": flags}
        library[name] = entry
        if verbose:
            print(f"{name:9s} {len(final):3d} lines  flags={len(flags)}  {hl_txt}")
    doc = {
        "format": 1,
        "description": "SpectraMaster gamma-line library (curated)",
        "convention": ("intensity = photons per 100 decays of the entry nuclide including the listed "
                       "short-lived daughters (branching x equilibrium activity ratio). Natural-series "
                       "members are separate entries; series_factor = activity relative to series head "
                       "at secular equilibrium. kind g=gamma x=X-ray a=annihilation; src I=IAEA ENSDF "
                       "(ndlab/LiveChart), S=SandiaDecay; optional 5th value = standard uncertainty of "
                       "the intensity (photons per 100 decays, ENSDF, combined in quadrature over merged "
                       "entries and scaled like the intensity; absent when not stated or for S lines)"),
        "sources": {
            "sandia": "SandiaDecay sandia.decay.nocoinc.min.xml, github.com/sandialabs/SandiaDecay "
                      "commit cd75314b56e12b80497531a1fbeed9c8e9968403, LGPL-2.1",
            "iaea": "IAEA-NDS ndlab database (ENSDF decay radiations, LiveChart backend), "
                    "github.com/IAEA-NDS/ndlab commit cf7fc2182cb112ae7502da0e243b30a58149fcdf, MIT",
        },
        "nuclides": library,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} : {len(library)} nuclides, {sum(len(v['lines']) for v in library.values())} lines, "
          f"{n_flags} provenance flags, {OUT.stat().st_size/1024:.0f} kB")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ndlab", help="path to ndlab_db.s3db (IAEA-NDS) to refresh the IAEA extract")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    if a.ndlab:
        sd = Sandia(SANDIA_XML)
        wanted = set()
        entry_names = {s[0] for s in SPECS}
        for name, _c, inc, _n in SPECS:
            for m, _f in chain_members(sd, name, inc, entry_names - {name} - set(inc)):
                mm = re.match(r"([A-Z][a-z]?)(\d+)(m\d?)?$", m)
                if mm:
                    wanted.add((f"{mm.group(2)}{mm.group(1).upper()}", bool(mm.group(3)),
                                sd.hl.get(m) if not math.isinf(sd.hl.get(m, math.inf)) else None))
        data = extract_iaea(Path(a.ndlab), sorted(wanted))
        IAEA_EXTRACT.write_text(json.dumps({
            "source": "IAEA-NDS ndlab_db.s3db (github.com/IAEA-NDS/ndlab @ cf7fc218), tables levels + "
                      "decay_radiations, type_a='G' (gamma, X, annihilation); intensity per 100 parent decays",
            "nuclides": data}, separators=(",", ":")), encoding="utf-8")
        print(f"IAEA extract: {len(data)} nuclides -> {IAEA_EXTRACT}")
    build(a.verbose)


if __name__ == "__main__":
    main()

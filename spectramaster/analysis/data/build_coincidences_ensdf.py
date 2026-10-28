"""Build the bundled coincidence table ``coincidence_table.json`` from ENSDF decay schemes.

Input (see SOURCES.md): the IAEA LiveChart of Nuclides decay radiation tables (ENSDF), one CSV file
per nuclide and radiation type, downloaded from ``https://nds.iaea.org/relnsd/v1/data?fields=
decay_rads&nuclides=<A><el>&rad_types=<g|bp|bm>`` and kept outside the repository like the other
large sources::

    python spectramaster/analysis/data/build_coincidences_ensdf.py path/to/livechart/raw

with ``decay_rads_g/``, ``decay_rads_bp/`` and ``decay_rads_bm/`` below it.  The SHA-256 of every
file read is recorded in the table (``source.files_sha256``) and one digest of them all.

It replaces the SandiaDecay coincidence tables (``build_coincidences.py``), whose probabilities
are wrong for 80 of the 191 transitions of the library, mostly far too small: Sc-48 1312 -> 983.5
keV is 0.1001 in the source instead of 1, Eu-152 (EC) 1408 -> 121.8 keV 0.1716 instead of 0.464
(docs/baseline/ensdf_coincidence_protocol.md).

Method, per parent (ground state or isomer) and decay mode (``B-``, ``EC+B+``, ``EC``, ``IT``, ``A``):

* the gammas placed in the level scheme (start and end level), their absolute intensities I and
  total conversion coefficients a; the transition intensity is I (1 + a);
* a level de-excites through the transitions that leave it in proportion to their transition
  intensities (branching b);
* ``reach_j(L)``: the probability that the de-excitation path from level L passes through
  transition j, summed over the paths; a level whose half-life exceeds MAX_LEVEL_HALF_LIFE_S
  ends the path (an isomer: what follows it is not coincident);
* ``P(j | i) = reach_j(end level of i) / (1 + a_j)`` for gamma j below gamma i, which does not
  depend on how the levels are fed;
* annihilation: ``P(beta+ | i) = sum_L f_L reach_i(L) / (1 + a_i) / I_i`` with f_L the beta+
  intensity feeding level L (``decay_rads_bp``); probabilities above ANN_MAX (inconsistent
  intensities) leave the transition ``ann_unresolved``;
* scheme intensities (docs/baseline/ensdf_level_balance_protocol.md): level populations from the
  direct feeding max(0, out - in) and the gamma inflow, top down; ``I^s_k = I_k P(S_k) / out(S_k)``.
  Where a level receives more than it emits (negative implied feeding), I^s exceeds I.  Stored as
  ``gs`` when some line differs from ``g`` by more than GS_TOL; the upward probability of the
  correction is ``I^s_i P(j | i) / I^s_j``.

Output: the format of ``build_coincidences.py`` (format 1); ``br`` is the decay mode's branching,
``g`` the gammas per decay of that mode.  Gammas below MIN_GAMMA per decay and coincidences below
MIN_COINC are dropped, so are pairs with a reverse probability above REVERSE_TOL (inconsistent
intensities; counted as ``dropped``).  No X-ray coincidences.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIBRARY = HERE / "gamma_library.json"
OUT = HERE / "coincidence_table.json"
MIN_GAMMA = 1.0e-5          # gammas per decay of the transition
MIN_COINC = 1.0e-4          # P(j | i)
REVERSE_TOL = 1.02          # I_i P(j|i) / I_j above this: inconsistent intensities, pair dropped
MAX_LEVEL_HALF_LIFE_S = 1.0e-6   # a longer-lived level ends the coincident cascade
LEVEL_TOL_KEV = 0.6         # end level of a gamma <-> start level of the next
ANN_MIN = 1.0e-4
ANN_MAX = 1.001
HALF_LIFE_TOL = 0.05        # isomer parent: ENSDF half-life within 5 % of the library's
MERGE_KEV = 0.05            # gammas this close (same tabulated energy) are one spectral line
MODES = ("B-", "EC+B+", "EC", "IT", "A")       # the names used by LiveChart
GS_TOL = 1.0e-4             # relative difference of a scheme intensity from the tabulated one to store gs


def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def lc_name(nuclide: str) -> tuple[str, str]:
    """('152eu', '' | 'm' | 'm2') of a library name such as Eu-152m."""
    m = re.fullmatch(r"([A-Z][a-z]?)-(\d+)(m\d?)?", nuclide)
    if not m:
        raise ValueError(f"unexpected nuclide name {nuclide!r}")
    return f"{m.group(2)}{m.group(1).lower()}", m.group(3) or ""


def library() -> dict:
    return json.loads(LIBRARY.read_text(encoding="utf-8"))["nuclides"]


def library_nuclides(lib: dict) -> list[str]:
    names = set(lib)
    for rec in lib.values():
        names.update(rec.get("includes", []) or [])
    return sorted(names)


def parent_energy(rows: list[dict], iso: str, half_life_s) -> float | None:
    """ENSDF parent level energy of the library nuclide: 0 for a ground state; for an isomer the
    excited parent whose half-life matches the library's (or, without one, the lowest)."""
    if not iso:
        return 0.0
    cands = {}
    for r in rows:
        pe = fnum(r.get("p_energy"))
        if pe is not None and pe > 0:
            cands[round(pe, 4)] = fnum(r.get("half_life_sec"))
    if not cands:
        return None
    if half_life_s:
        ok = [pe for pe, hl in cands.items() if hl and abs(hl / half_life_s - 1.0) <= HALF_LIFE_TOL]
        if ok:
            return min(ok)
    return min(cands)


def same(a, b) -> bool:
    return a is not None and b is not None and abs(a - b) < 0.5


class Scheme:
    """Gammas of one parent and decay mode placed in the daughter's level scheme."""

    def __init__(self, gammas: list[dict], level_hl: dict[float, float]):
        self.g = gammas
        self.out = defaultdict(list)                # start level -> gamma indices
        for k, x in enumerate(gammas):
            if x["S"] is not None and x["L"] is not None:
                self.out[x["S"]].append(k)
        self.level_hl = level_hl
        self._memo: dict = {}

    def level(self, energy):
        if energy is None:
            return None
        best = min(self.out, key=lambda s: abs(s - energy), default=None)
        return best if best is not None and abs(best - energy) <= LEVEL_TOL_KEV else None

    def long_lived(self, energy) -> bool:
        hl = self.level_hl.get(energy)
        return hl is not None and hl > MAX_LEVEL_HALF_LIFE_S

    def reach(self, energy, j: int) -> float:
        """Probability that the de-excitation from the level at `energy` passes through gamma j."""
        s = self.level(energy)
        if s is None or self.long_lived(s):
            return 0.0
        key = (s, j)
        if key not in self._memo:
            self._memo[key] = 0.0                     # cycles (inconsistent schemes) count once
            ks = self.out[s]
            tot = sum(self.g[k]["T"] for k in ks)
            p = 0.0
            if tot > 0:
                for k in ks:
                    p += self.g[k]["T"] / tot * (1.0 if k == j else self.reach(self.g[k]["L"], j))
            self._memo[key] = p
        return self._memo[key]

    def populations(self) -> dict:
        """{start level: P(L) / out(L)}: population from the direct feeding max(0, out - in) and the
        gamma inflow, top down, over the emission rate the tabulated intensities give (1 when the
        level is fed at least as fast as it de-excites, which the whole scheme then shares)."""
        out = {s: sum(self.g[k]["T"] for k in ks) for s, ks in self.out.items()}
        into = defaultdict(list)
        for k, x in enumerate(self.g):
            lv = self.level(x["L"])
            if x["S"] is not None and lv is not None and lv < x["S"]:
                into[lv].append(k)
        pop = {}
        for s in sorted(out, reverse=True):
            inflow = sum(self.g[k]["T"] for k in into[s])
            fed = sum(pop[self.g[k]["S"]] * self.g[k]["T"] / out[self.g[k]["S"]]
                      for k in into[s] if out.get(self.g[k]["S"], 0.0) > 0)
            pop[s] = max(out[s] - inflow, 0.0) + fed
        return {s: (pop[s] / out[s] if out[s] > 0 else 1.0) for s in out}

    def after(self, i: int, j: int) -> float:
        """P(gamma j | gamma i), j below i."""
        xi, xj = self.g[i], self.g[j]
        if xi["L"] is None or xj["S"] is None:
            return 0.0
        return self.reach(xi["L"], j) / (1.0 + xj["a"])


def mode_records(gdir: Path, bpdir: Path, nuclide: str, half_life_s) -> list[dict] | None:
    """Table records (one per decay mode with gammas) of a library nuclide; None without data."""
    lc, iso = lc_name(nuclide)
    gfile = gdir / f"{lc}.csv"
    if not gfile.exists():
        return None
    rows = read_csv(gfile)
    pe = parent_energy(rows, iso, half_life_s)
    if pe is None:
        return None
    feeds = read_csv(bpdir / f"{lc}.csv") if (bpdir / f"{lc}.csv").exists() else []
    recs = []
    for mode in MODES:
        mrows = [r for r in rows if r.get("decay") == mode and same(fnum(r.get("p_energy")) or 0.0, pe)]
        if not mrows:
            continue
        br = fnum(mrows[0].get("decay_%"))
        br = (br / 100.0) if br and br > 0 else 1.0
        gam, level_hl = [], {}
        for r in mrows:
            e, i = fnum(r.get("energy")), fnum(r.get("intensity"))
            if e is None or i is None or i <= 0:
                continue
            s, lv = fnum(r.get("start_level_energy")), fnum(r.get("end_level_energy"))
            a = fnum(r.get("conversion_coeff")) or 0.0
            gam.append({"E": e, "I": i / 100.0, "S": None if s is None else round(s, 4),
                        "L": None if lv is None else round(lv, 4), "a": a, "T": i / 100.0 * (1.0 + a)})
            for lev, hl in ((s, fnum(r.get("start_level_hl"))), (lv, fnum(r.get("end_level_hl")))):
                if lev is not None and hl is not None:
                    level_hl[round(lev, 4)] = hl
        if not gam:
            continue
        sch = Scheme(gam, level_hl)
        keep = [k for k, x in enumerate(gam) if x["I"] / br >= MIN_GAMMA]
        ann, ok = annihilation(sch, keep, feeds, pe) if mode == "EC+B+" else ({}, True)   # "EC": no beta+
        # gammas of the same energy from different levels (Te-131m 852.21 keV: 19.9 % and 0.37 %) are
        # one line for the spectrum: merged, rows weighted by intensity, columns summed
        groups: list[list[int]] = []
        for k in sorted(keep, key=lambda q: gam[q]["E"]):
            if groups and abs(gam[k]["E"] - gam[groups[-1][0]]["E"]) <= MERGE_KEV:
                groups[-1].append(k)
            else:
                groups.append([k])
        inten = [sum(gam[k]["I"] for k in grp) for grp in groups]
        pairs, dropped = [], 0
        for a, ga in enumerate(groups):
            for b, gb in enumerate(groups):
                if a == b:
                    continue
                p = sum(gam[k]["I"] * sum(sch.after(k, q) for q in gb) for k in ga) / inten[a]
                if p < MIN_COINC:
                    continue
                if p > 1.0 + 1e-6 or inten[a] * p / inten[b] > REVERSE_TOL:
                    dropped += 1
                    continue
                pairs.append([a, b, round(p, 6)])
        # a merged line above and below another (Te-131m 852.21 around 296.8 keV) gives both
        # directions; together above REVERSE_TOL, only the larger contribution is kept
        both = {(a, b): p for a, b, p in pairs}
        for a, b, p in list(pairs):
            q = both.get((b, a))
            if q is None or a > b:
                continue
            if p + inten[b] * q / inten[a] > REVERSE_TOL or q + inten[a] * p / inten[b] > REVERSE_TOL:
                weak = (b, a) if inten[b] * q / inten[a] < p else (a, b)
                pairs = [x for x in pairs if (x[0], x[1]) != weak]
                dropped += 1
        energy = [sum(gam[k]["E"] * gam[k]["I"] for k in grp) / inten[n] for n, grp in enumerate(groups)]
        rec = {"br": round(br, 6), "mode": mode,
               "g": [[round(energy[n], 4), float(f"{inten[n] / br:.6g}")] for n in range(len(groups))], "c": pairs}
        ratio = sch.populations()
        gs = [sum(gam[k]["I"] * ratio.get(gam[k]["S"], 1.0) for k in grp) for grp in groups]
        if any(abs(gs[n] / inten[n] - 1.0) > GS_TOL for n in range(len(groups))):
            rec["gs"] = [float(f"{gs[n] / br:.6g}") for n in range(len(groups))]
        if dropped:
            rec["dropped"] = dropped
        a_m = [[n, round(sum(gam[k]["I"] * ann.get(k, 0.0) for k in grp) / inten[n], 6)]
               for n, grp in enumerate(groups)]
        a_m = [x for x in a_m if x[1] >= ANN_MIN]
        if a_m:
            rec["ann"] = a_m
        if not ok:
            rec["ann_unresolved"] = True
        if rec["c"] or rec.get("ann") or rec.get("ann_unresolved"):
            recs.append(rec)
    return recs


def annihilation(sch: Scheme, keep: list[int], feeds: list[dict], pe: float) -> tuple[dict[int, float], bool]:
    """({gamma index: P(beta+ | gamma)}, resolved) from the beta+ feeding of the levels."""
    fb = defaultdict(float)
    for r in feeds:
        if r.get("decay") != "EC+B+" or not same(fnum(r.get("p_energy")) or 0.0, pe):
            continue
        ib, lev = fnum(r.get("intensity_beta")), fnum(r.get("daughter_level_energy"))
        if ib and ib > 0 and lev is not None:
            fb[round(lev, 4)] += ib / 100.0
    if not fb:
        return {}, True
    out = {}
    for k in keep:
        x = sch.g[k]
        if x["I"] <= 0:
            continue
        s = sum(f * sch.reach(lev, k) for lev, f in fb.items()) / (1.0 + x["a"])
        p = s / x["I"]
        if p > ANN_MAX:
            return {}, False
        if p >= ANN_MIN:
            out[k] = min(p, 1.0)
    return out, True


def daughters_listed_by_parent(lib: dict, gdir: Path) -> dict[str, list[str]]:
    """{parent: [included daughters]} whose gammas the parent's ENSDF decay already lists: the
    daughter is an isomer of the parent's decay product (Pb-207m of Bi-207, Ba-137m of Cs-137)
    and the parent's decay has gammas starting from that isomer's level.  coincidence.transitions
    must not add their transitions again (docs/baseline/ensdf_coincidence_protocol.md)."""
    out = {}
    for parent, rec in lib.items():
        incl = [d for d in rec.get("includes", []) or [] if lc_name(d)[1]]
        if not incl:
            continue
        plc, piso = lc_name(parent)
        if not (gdir / f"{plc}.csv").exists():
            continue
        prow = read_csv(gdir / f"{plc}.csv")
        ppe = parent_energy(prow, piso, rec.get("half_life_s"))
        names = []
        for d in incl:
            dlc, diso = lc_name(d)
            if not (gdir / f"{dlc}.csv").exists():
                continue
            dpe = parent_energy(read_csv(gdir / f"{dlc}.csv"), diso, (lib.get(d) or {}).get("half_life_s"))
            symbol = re.match(r"([A-Z][a-z]?)", d).group(1)
            if dpe and any(r.get("d_symbol") == symbol and same(fnum(r.get("p_energy")) or 0.0, ppe)
                           and same(fnum(r.get("start_level_energy")), dpe) for r in prow):
                names.append(d)
        if names:
            out[parent] = sorted(names)
    return out


def manifest(raw: Path) -> dict[str, str]:
    return {f"{d}/{p.name}": hashlib.sha256(p.read_bytes()).hexdigest()
            for d in ("decay_rads_g", "decay_rads_bp") for p in sorted((raw / d).glob("*.csv"))}


def build(raw, out: Path = OUT) -> dict:
    raw = Path(raw).resolve(strict=True)
    gdir, bpdir = raw / "decay_rads_g", raw / "decay_rads_bp"
    lib = library()
    table, missing = {}, []
    for name in library_nuclides(lib):
        hl = (lib.get(name) or {}).get("half_life_s")
        recs = mode_records(gdir, bpdir, name, hl)
        if recs is None:
            missing.append(name)
        elif recs:
            table[name] = recs
    listed = daughters_listed_by_parent(lib, gdir)
    files = manifest(raw)
    digest = hashlib.sha256("".join(f"{k}:{v}\n" for k, v in sorted(files.items())).encode()).hexdigest()
    doc = {"format": 1,
           "description": ("Gamma-gamma and annihilation coincidence probabilities for true-coincidence "
                           "summing corrections, computed from ENSDF decay schemes"),
           "convention": "per transition: br, g = [[keV, gammas per decay of the transition]], "
                         "c = [[i, j, P(j emitted | i emitted)]], i above j in the cascade; "
                         "ann = [[i, P(beta+ in the same decay | i emitted)]] (two 511 keV photons per "
                         "beta+), ann_unresolved = beta+ feeding inconsistent; no X-ray coincidences",
           "source": {"project": "ENSDF via IAEA LiveChart of Nuclides https://nds.iaea.org/relnsd/v1/data "
                                 "(fields=decay_rads, rad_types=g, bp)",
                      "digest_sha256": digest, "files": len(files), "files_sha256": files,
                      "min_gamma": MIN_GAMMA, "min_coinc": MIN_COINC, "reverse_tol": REVERSE_TOL,
                      "max_level_half_life_s": MAX_LEVEL_HALF_LIFE_S, "ann_min": ANN_MIN,
                      "no_ensdf_data": missing},
           "daughters_listed_by_parent": listed,
           "nuclides": table}
    out.write_text(json.dumps(doc, indent=0, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("raw", help="folder with decay_rads_g/ and decay_rads_bp/ LiveChart CSV files")
    a = ap.parse_args(argv)
    doc = build(a.raw)
    print(f"{len(doc['nuclides'])} nuclides with gamma cascades -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

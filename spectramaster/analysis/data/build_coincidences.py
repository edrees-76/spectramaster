"""Build the bundled gamma-gamma coincidence table ``coincidence_table.json``.

Input (see SOURCES.md): ``sandia.decay.min.xml`` of SandiaDecay (LGPL-2.1), the same commit as the
bundled ``sandia.decay.nocoinc.min.xml`` but WITH the coincidence tables.  The 16 MB file is kept
outside the repository, like the IAEA ndlab database; pass its path::

    python spectramaster/analysis/data/build_coincidences.py path/to/sandia.decay.min.xml

Output, for every nuclide of ``gamma_library.json`` and its included daughters that has gamma
cascades, one record per decay transition::

    {"br": branching ratio of the transition,
     "g": [[energy_keV, gammas per decay of the transition], ...],
     "c": [[i, j, P(j | i)], ...]}

``P(j | i)`` is SandiaDecay's ``coincidentGamma`` intensity: the probability that gamma j is
emitted in the same decay given that gamma i is (cascade order, i above j; the reverse
probability is I_i P(j|i) / I_j).  Only gamma-gamma coincidences are tabulated by the source:
X-ray (and annihilation) coincidences are not, so X-ray - gamma summing (EC nuclides such as
Ba-133) is outside this table.  Gammas below MIN_GAMMA per decay and coincidences below
MIN_COINC are dropped.  So are physically impossible pairs of the source (P(j|i) > 1, or a reverse
probability I_i P(j|i) / I_j > REVERSE_TOL, found for weak lines of a few nuclides); their number is
kept per transition as ``"dropped"``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIBRARY = HERE / "gamma_library.json"
OUT = HERE / "coincidence_table.json"
SOURCE_COMMIT = "cd75314b56e12b80497531a1fbeed9c8e9968403"
MIN_GAMMA = 1.0e-5        # gammas per decay of the transition
MIN_COINC = 1.0e-4        # P(j | i)
REVERSE_TOL = 1.02        # I_i P(j|i) / I_j above this is impossible: the pair is dropped


def sandia_name(n: str) -> str:
    return n.replace("-", "")


def library_nuclides(path: Path = LIBRARY) -> list[str]:
    lib = json.loads(path.read_text(encoding="utf-8"))["nuclides"]
    names = set(lib)
    for rec in lib.values():
        names.update(rec.get("includes", []) or [])
    return sorted(names)


def read_transitions(path: Path) -> dict[str, list[dict]]:
    """{sandia parent symbol: [transition records]} with the raw gamma ids and coincidences."""
    ns = "{sandia.decay.xsd}"
    out: dict[str, list[dict]] = {}
    for t in ET.parse(path).getroot().iter(ns + "t"):
        gammas = []
        for g in t.findall(ns + "g"):
            co = [(c.get("id"), float(c.get("i"))) for c in g.findall(ns + "c")]
            gammas.append({"e": float(g.get("e")), "i": float(g.get("i")), "id": g.get("id"), "c": co})
        if gammas:
            out.setdefault(t.get("p"), []).append({"br": float(t.get("br", "1")), "g": gammas})
    return out


def compact(tr: dict) -> dict:
    """Keep gammas >= MIN_GAMMA, re-index, resolve coincidence ids (within the transition)."""
    keep = [g for g in tr["g"] if g["i"] >= MIN_GAMMA]
    by_id = {g["id"]: k for k, g in enumerate(keep) if g["id"] is not None}
    pairs, dropped = [], 0
    for i, g in enumerate(keep):
        for cid, p in g["c"]:
            j = by_id.get(cid)
            if j is None or j == i or p < MIN_COINC:
                continue
            if p > 1.0 + 1e-6 or g["i"] * p / keep[j]["i"] > REVERSE_TOL:
                dropped += 1
                continue
            pairs.append([i, j, round(p, 6)])
    rec = {"br": tr["br"], "g": [[round(g["e"], 4), float(f"{g['i']:.6g}")] for g in keep], "c": pairs}
    if dropped:
        rec["dropped"] = dropped
    return rec


def build(src: Path, out: Path = OUT) -> dict:
    trans = read_transitions(src)
    table = {}
    for name in library_nuclides():
        recs = [compact(t) for t in trans.get(sandia_name(name), [])]
        recs = [r for r in recs if r["c"]]
        if recs:
            table[name] = recs
    doc = {"format": 1,
           "description": "Gamma-gamma coincidence probabilities for true-coincidence summing corrections",
           "convention": "per transition: br, g = [[keV, gammas per decay of the transition]], "
                         "c = [[i, j, P(j emitted | i emitted)]], i above j in the cascade; "
                         "gamma-gamma only (no X-ray coincidences)",
           "source": {"file": "sandia.decay.min.xml", "project": "SandiaDecay https://github.com/sandialabs/SandiaDecay",
                      "commit": SOURCE_COMMIT, "sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
                      "license": "LGPL-2.1", "min_gamma": MIN_GAMMA, "min_coinc": MIN_COINC,
                      "reverse_tol": REVERSE_TOL},
           "nuclides": table}
    out.write_text(json.dumps(doc, indent=0, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", type=Path, help="SandiaDecay sandia.decay.min.xml (with coincidences)")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build(a.source, a.out)
    print(f"{len(doc['nuclides'])} nuclides with gamma cascades -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

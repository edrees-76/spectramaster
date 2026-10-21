"""Build the bundled gamma-gamma coincidence table ``coincidence_table.json``.

Input (see SOURCES.md): ``sandia.decay.min.xml`` of SandiaDecay (LGPL-2.1), the same commit as the
bundled ``sandia.decay.nocoinc.min.xml`` but WITH the coincidence tables.  The 16 MB file is kept
outside the repository, like the IAEA ndlab database; pass its path::

    python spectramaster/analysis/data/build_coincidences.py path/to/sandia.decay.min.xml

The source is accepted only with its name and SHA-256 (SOURCE_SHA256, the file of SOURCE_COMMIT);
the table is always written next to this script.

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
SOURCE_NAME = "sandia.decay.min.xml"
SOURCE_SHA256 = "ef9dcdb7e598c999cebab3fdcbfc968c851d191ae0e7600b3fc019fb11a6fb06"
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


def read_transitions(data: bytes) -> dict[str, list[dict]]:
    """{sandia parent symbol: [transition records]} with the raw gamma ids and coincidences, and
    the EC / beta+ branches (endpoint keV, intensity per decay of the transition)."""
    ns = "{sandia.decay.xsd}"
    out: dict[str, list[dict]] = {}
    for t in ET.fromstring(data).iter(ns + "t"):
        gammas = []
        for g in t.findall(ns + "g"):
            co = [(c.get("id"), float(c.get("i"))) for c in g.findall(ns + "c")]
            gammas.append({"e": float(g.get("e")), "i": float(g.get("i")), "id": g.get("id"), "c": co})
        if gammas:
            out.setdefault(t.get("p"), []).append({
                "br": float(t.get("br", "1")), "g": gammas,
                "ec": [(float(x.get("e")), float(x.get("i"))) for x in t.findall(ns + "ec")],
                "p": [(float(x.get("e")), float(x.get("i"))) for x in t.findall(ns + "p")]})
    return out


# ------------------------------------------------------------------ annihilation (beta+) coincidences
# docs/baseline/annihilation_summing_protocol.md: the source gives no level of the EC / beta+ branches;
# it is reconstructed from the cascade (top level of each gamma), Q from the branch endpoints.
ME2_KEV = 1021.998        # 2 m_e c^2: beta+ endpoint = Q - 2 m_e c^2 - level
ANN_LEVEL_TOL = 6.0       # keV, branch level <-> cascade level (one source endpoint is off by 5 keV)
ANN_MIN = 1.0e-4          # P(beta+ | gamma) below this is not tabulated
ANN_MAX = 1.001           # above: the reconstruction does not describe the transition


def gamma_tops(gammas: list[dict]) -> list[float | None]:
    """Top level of each gamma: its energy plus the highest top among the gammas following it
    (a gamma followed by none ends on the ground state); None inside an inconsistent loop."""
    by_id = {g["id"]: k for k, g in enumerate(gammas) if g["id"] is not None}
    succ = [[by_id[c] for c, p in g["c"] if c in by_id and p > 0] for g in gammas]
    top: list[float | None] = [None] * len(gammas)
    for _ in range(len(gammas) + 1):
        for i, g in enumerate(gammas):
            if top[i] is None and all(top[j] is not None for j in succ[i]):
                top[i] = g["e"] + max((top[j] for j in succ[i]), default=0.0)
    return top


def annihilation(tr: dict) -> tuple[dict[int, float], bool]:
    """({raw gamma index: P(beta+ | gamma)}, resolved) of one transition.  Unresolved when a beta+
    branch matches no level or a probability exceeds ANN_MAX; then nothing is returned."""
    pos = [(e, i) for e, i in tr.get("p", []) if i > 0]
    if not pos:
        return {}, True
    gammas = tr["g"]
    top = gamma_tops(gammas)
    levels = sorted({0.0} | {t for t in top if t is not None})
    ec = [(e, i) for e, i in tr.get("ec", []) if i > 0]

    def implied(q):
        return [(q - e, i) for e, i in ec] + [(q - ME2_KEV - e, i) for e, i in pos]

    def near(x):
        best = min(levels, key=lambda lv: abs(x - lv))
        return best if abs(x - best) <= ANN_LEVEL_TOL else None

    cands = sorted({e + lv for e, _ in ec for lv in levels} | {e + ME2_KEV + lv for e, _ in pos for lv in levels})
    q = max(cands, key=lambda c: (sum(i for x, i in implied(c) if near(x) is not None), -c))
    feed: dict[float, float] = {}
    for e, i in pos:
        lv = near(q - ME2_KEV - e)
        if lv is None:
            return {}, False
        feed[lv] = feed.get(lv, 0.0) + i
    by_id = {g["id"]: k for k, g in enumerate(gammas) if g["id"] is not None}
    after = [{by_id[c]: p for c, p in g["c"] if c in by_id} for g in gammas]
    leaving = {lv: [m for m, t in enumerate(top) if t is not None and abs(t - lv) <= 1e-6] for lv in feed}
    out = {}
    for k, g in enumerate(gammas):
        if g["i"] <= 0:
            continue
        s = 0.0
        for lv, f in feed.items():
            flux = sum(gammas[m]["i"] for m in leaving[lv])
            if flux <= 0:
                continue
            for m in leaving[lv]:
                s += f * gammas[m]["i"] / flux * (1.0 if m == k else after[m].get(k, 0.0))
        p = s / g["i"]
        if p > ANN_MAX:
            return {}, False
        if p >= ANN_MIN:
            out[k] = min(p, 1.0)
    return out, True


def compact(tr: dict) -> dict:
    """Keep gammas >= MIN_GAMMA, re-index, resolve coincidence ids (within the transition); add the
    annihilation entries ``ann`` = [[i, P(beta+ | i)]] or ``ann_unresolved``."""
    ann, resolved = annihilation(tr)
    ann_keep = {id(tr["g"][k]): p for k, p in ann.items()}
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
    a = [[k, round(ann_keep[id(g)], 6)] for k, g in enumerate(keep) if id(g) in ann_keep]
    if a:
        rec["ann"] = a
    if not resolved:
        rec["ann_unresolved"] = True
    return rec


def checked_source(path) -> tuple[bytes, str]:
    """The source file's bytes and SHA-256, only for the exact SandiaDecay file of SOURCE_COMMIT
    (a regular file named SOURCE_NAME with SOURCE_SHA256); anything else is refused."""
    src = Path(path).resolve(strict=True)
    if src.name != SOURCE_NAME or not src.is_file():
        raise ValueError(f"expected the SandiaDecay file {SOURCE_NAME}, got {src.name}")
    data = src.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(f"{SOURCE_NAME}: SHA-256 {digest} is not the one of commit {SOURCE_COMMIT}")
    return data, digest


def build(src, out: Path = OUT) -> dict:
    """Build the table from the checked source; written to `out` (the bundled table by default)."""
    data, digest = checked_source(src)
    trans = read_transitions(data)
    table = {}
    for name in library_nuclides():
        recs = [compact(t) for t in trans.get(sandia_name(name), [])]
        recs = [r for r in recs if r["c"] or r.get("ann") or r.get("ann_unresolved")]
        if recs:
            table[name] = recs
    doc = {"format": 1,
           "description": ("Gamma-gamma and annihilation coincidence probabilities for true-coincidence "
                           "summing corrections"),
           "convention": "per transition: br, g = [[keV, gammas per decay of the transition]], "
                         "c = [[i, j, P(j emitted | i emitted)]], i above j in the cascade; "
                         "ann = [[i, P(beta+ in the same decay | i emitted)]] (two 511 keV photons per "
                         "beta+), ann_unresolved = beta+ feeding not reconstructed; no X-ray coincidences",
           "source": {"file": "sandia.decay.min.xml", "project": "SandiaDecay https://github.com/sandialabs/SandiaDecay",
                      "commit": SOURCE_COMMIT, "sha256": digest,
                      "license": "LGPL-2.1", "min_gamma": MIN_GAMMA, "min_coinc": MIN_COINC,
                      "reverse_tol": REVERSE_TOL, "ann_level_tol_kev": ANN_LEVEL_TOL, "ann_min": ANN_MIN},
           "nuclides": table}
    out.write_text(json.dumps(doc, indent=0, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", help=f"SandiaDecay {SOURCE_NAME} (with coincidences), commit {SOURCE_COMMIT}")
    a = ap.parse_args(argv)
    doc = build(a.source)
    print(f"{len(doc['nuclides'])} nuclides with gamma cascades -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

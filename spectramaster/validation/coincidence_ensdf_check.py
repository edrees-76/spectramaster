"""Independent check of the bundled coincidence table (built from ENSDF by
``analysis/data/build_coincidences_ensdf.py``) against a Monte Carlo simulation of the decay
cascades, written separately from the builder: its own reading of the LiveChart CSV files, level
feeding from the intensity balance, and a random walk down the levels instead of the analytic
path sums (docs/baseline/ensdf_coincidence_protocol.md).

    python -m spectramaster.validation.coincidence_ensdf_check [--raw DIR] [--old OLD_TABLE] --out DIR

``DIR`` of the LiveChart files: ``SPECTRAMASTER_LIVECHART_DIR`` or
D:/SpectraMaster_public_data/livechart/raw (kept outside the repository).  Writes
``coincidence_check.json`` and ``coincidence_check.md``; no ENSDF data is copied.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

from spectramaster.analysis import coincidence as co
from spectramaster.analysis.library import lines_of

# ground-state parents with simple to complex schemes, beta-, EC and beta+
MC_SET = ("Co-60", "Sc-48", "Y-88", "Na-22", "Cs-134", "Ba-133", "Eu-152", "Bi-207", "Se-75",
          "Ir-192", "Co-56", "Sb-124", "La-140", "Bi-214", "Pb-214", "Tl-208", "Ac-228", "Co-57")
MC_DECAYS = 200_000
MC_SEED = 12345
MIN_LINE = 0.005            # gammas per decay of the mode, for the compared lines
MIN_P = 0.01                # compared pairs: table or simulation at least this
ABS_TOL = 0.005
SIGMAS = 4.0
# single-path cascades: P(j | i) = 1 / (1 + a_j), a_j from the same ENSDF rows
ANALYTIC = (("Co-60", "B-", 1173.228, 1332.492), ("Sc-48", "B-", 1312.12, 983.526),
            ("Y-88", "EC+B+", 898.042, 1836.063), ("Eu-152", "EC+B+", 1408.006, 121.7817))
ANALYTIC_TOL = 5.0e-4
LEVEL_TOL = 0.6
LONG_LIVED_S = 1.0e-6
GROUP_KEV = 0.06


def raw_folder(arg=None) -> Path:
    return Path(arg or os.environ.get("SPECTRAMASTER_LIVECHART_DIR", "D:/SpectraMaster_public_data/livechart/raw"))


def _f(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _rows(raw: Path, kind: str, nuclide: str) -> list[dict]:
    el, a = nuclide.split("-")
    p = raw / f"decay_rads_{kind}" / f"{a}{el.lower()}.csv"
    if not p.exists():
        return []
    with open(p, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _gammas(raw: Path, nuclide: str, mode: str):
    """[(E, I per decay of the mode, start, end, alpha)], level half-lives, beta+ per level."""
    out, hl = [], {}
    for r in _rows(raw, "g", nuclide):
        if r.get("decay") != mode or abs(_f(r.get("p_energy")) or 0.0) > 0.5:
            continue
        e, i, s, l = (_f(r.get(k)) for k in ("energy", "intensity", "start_level_energy", "end_level_energy"))
        if None in (e, i, s, l) or i <= 0:
            continue
        out.append((e, i / 100.0, s, l, _f(r.get("conversion_coeff")) or 0.0))
        for lev, h in ((s, _f(r.get("start_level_hl"))), (l, _f(r.get("end_level_hl")))):
            if h is not None:
                hl[round(lev, 3)] = h
    bplus = defaultdict(float)
    if mode == "EC+B+":
        for r in _rows(raw, "bp", nuclide):
            if r.get("decay") == mode and abs(_f(r.get("p_energy")) or 0.0) <= 0.5:
                ib, lev = _f(r.get("intensity_beta")), _f(r.get("daughter_level_energy"))
                if ib and lev is not None:
                    bplus[round(lev, 3)] += ib / 100.0
    return out, hl, bplus


def simulate(gam, hl, bplus, n: int, rng: random.Random):
    """Counts of each gamma, of each ordered pair in one prompt cascade and of gamma with beta+."""
    starts = sorted({round(g[2], 3) for g in gam})

    def level(e):
        best = min(starts, key=lambda s: abs(s - e), default=None)
        return best if best is not None and abs(best - e) <= LEVEL_TOL else None

    leave = defaultdict(list)
    for k, g in enumerate(gam):
        leave[round(g[2], 3)].append(k)
    t = [g[1] * (1.0 + g[4]) for g in gam]
    feed = {}
    for s in starts:
        inflow = sum(t[k] for k, g in enumerate(gam) if level(g[3]) == s)
        feed[s] = max(sum(t[k] for k in leave[s]) - inflow, 0.0)
    tot = sum(feed.values())
    if tot <= 0:
        return None
    levels, weights = list(feed), [feed[s] / tot for s in feed]
    scale = tot                    # decays of the mode that end in a gamma-emitting level, per decay
    n_g = defaultdict(int)
    n_pair = defaultdict(int)
    n_b = defaultdict(int)
    for _ in range(n):
        s = rng.choices(levels, weights)[0]
        b = rng.random() < min(bplus.get(s, 0.0) / feed[s], 1.0) if s in bplus and feed[s] > 0 else False
        prompt = []
        while s is not None:
            ks = leave.get(s)
            if not ks:
                break
            k = rng.choices(ks, [t[q] for q in ks])[0]
            if rng.random() < 1.0 / (1.0 + gam[k][4]):
                n_g[k] += 1
                if b:
                    n_b[k] += 1
                for q in prompt:
                    n_pair[(q, k)] += 1
                prompt.append(k)
            nxt = level(gam[k][3])
            if nxt is not None and hl.get(nxt, 0.0) > LONG_LIVED_S:
                prompt, b = [], False                      # the isomer ends the coincident cascade
            s = nxt
    return {"n_g": n_g, "n_pair": n_pair, "n_b": n_b, "scale": scale, "n": n}


def compare(nuclide: str, raw: Path, rng: random.Random) -> list[dict]:
    out = []
    for rec in co._table()["nuclides"].get(nuclide, []):
        mode = rec.get("mode")
        gam, hl, bplus = _gammas(raw, nuclide, mode)
        sim = simulate(gam, hl, bplus, MC_DECAYS, rng) if gam else None
        if sim is None:
            out.append({"mode": mode, "status": "no simulation"})
            continue
        tab = [(e, i) for e, i in rec["g"]]
        idx = {}
        for k, g in enumerate(gam):
            m = min(range(len(tab)), key=lambda q: abs(tab[q][0] - g[0]))
            if abs(tab[m][0] - g[0]) <= GROUP_KEV:
                idx[k] = m
        cnt = defaultdict(int)
        for k, m in idx.items():
            cnt[m] += sim["n_g"][k]
        pair = defaultdict(int)
        for (a, b), v in sim["n_pair"].items():
            if a in idx and b in idx:
                pair[(idx[a], idx[b])] += v
        bcnt = defaultdict(int)
        for k, v in sim["n_b"].items():
            if k in idx:
                bcnt[idx[k]] += v
        table_c = {(int(a), int(b)): p for a, b, p in rec["c"]}
        strong = {m for m, (_, i) in enumerate(tab) if i >= MIN_LINE and cnt[m] > 0}
        rows = []
        for a in strong:
            for b in strong:
                if a == b:
                    continue
                pm = pair[(a, b)] / cnt[a]
                pt = table_c.get((a, b), 0.0)
                if max(pm, pt) < MIN_P:
                    continue
                sig = math.sqrt(max(pm * (1 - pm), 1e-12) / cnt[a])
                rows.append({"i": tab[a][0], "j": tab[b][0], "table": pt, "mc": round(pm, 5),
                             "sigma": round(sig, 5), "ok": abs(pt - pm) <= max(ABS_TOL, SIGMAS * sig)})
        ann_t = {int(a): p for a, p in rec.get("ann", [])}
        anns = []
        if mode == "EC+B+":
            for a in strong:
                pm = bcnt[a] / cnt[a]
                pt = ann_t.get(a, 0.0)
                if max(pm, pt) < MIN_P:
                    continue
                sig = math.sqrt(max(pm * (1 - pm), 1e-12) / cnt[a])
                anns.append({"i": tab[a][0], "table": pt, "mc": round(pm, 5), "sigma": round(sig, 5),
                             "ok": abs(pt - pm) <= max(ABS_TOL, SIGMAS * sig)})
        out.append({"mode": mode, "status": "ok", "pairs": rows, "ann": anns,
                    "worst": max((abs(r["table"] - r["mc"]) for r in rows + anns), default=0.0)})
    return out


def analytic(raw: Path) -> list[dict]:
    res = []
    for nuc, mode, ei, ej in ANALYTIC:
        gam, _, _ = _gammas(raw, nuc, mode)
        aj = min(gam, key=lambda g: abs(g[0] - ej))[4] if gam else None
        p = None
        for rec in co._table()["nuclides"].get(nuc, []):
            if rec.get("mode") != mode:
                continue
            e = [x[0] for x in rec["g"]]
            a = min(range(len(e)), key=lambda q: abs(e[q] - ei))
            b = min(range(len(e)), key=lambda q: abs(e[q] - ej))
            p = {(int(x), int(y)): v for x, y, v in rec["c"]}.get((a, b), 0.0)
        exp = None if aj is None else 1.0 / (1.0 + aj)
        res.append({"nuclide": nuc, "i": ei, "j": ej, "table": p, "expected": exp,
                    "ok": p is not None and exp is not None and abs(p - exp) <= ANALYTIC_TOL})
    return res


def described(table_path=None) -> dict:
    """Library gamma lines >= 1 % that the table's transitions describe (intensity 0.75-1.33 x)."""
    if table_path:
        co.TABLE = Path(table_path)
    co._table.cache_clear()
    co._daughters.cache_clear()
    lib = json.loads((Path(co.__file__).parent / "data" / "gamma_library.json").read_text(encoding="utf-8"))["nuclides"]
    yes, no = set(), set()
    for n in lib:
        for ln in lines_of(n):
            if ln.kind != "g" or ln.intensity < 1:
                continue
            w = 0.0
            for t in co.transitions(n):
                i = t.index(ln.energy, co.LINE_TOL_KEV)
                if i is not None:
                    w += t.br * t.intensities[i]
            if w > 0:
                (yes if 0.75 <= w / (ln.intensity / 100) <= 1.33 else no).add(f"{n} {ln.energy:.1f}")
    return {"described": sorted(yes), "not_described": sorted(no)}


def run(raw: Path, old=None) -> dict:
    rng = random.Random(MC_SEED)
    mc = {n: compare(n, raw, rng) for n in MC_SET}
    pairs = [r for v in mc.values() for t in v if t["status"] == "ok" for r in t["pairs"] + t["ann"]]
    unresolved = sorted(n for n, recs in co._table()["nuclides"].items() for r in recs if r.get("ann_unresolved"))
    new_cov = described()
    res = {"monte_carlo": mc, "analytic": analytic(raw), "coverage": new_cov,
           "no_ensdf_data": co._table()["source"].get("no_ensdf_data", []),
           "ann_unresolved": unresolved,
           "summary": {"mc_compared": len(pairs), "mc_failed": sum(not r["ok"] for r in pairs),
                       "mc_worst_abs": max((abs(r["table"] - r["mc"]) for r in pairs), default=0.0),
                       "described": len(new_cov["described"]), "not_described": len(new_cov["not_described"])}}
    if old:
        prev = described(old)
        res["coverage_old"] = {"described": len(prev["described"]), "not_described": len(prev["not_described"]),
                               "lost": sorted(set(prev["described"]) - set(new_cov["described"])),
                               "gained": sorted(set(new_cov["described"]) - set(prev["described"]))}
        co.TABLE = Path(co.__file__).parent / "data" / "coincidence_table.json"
        co._table.cache_clear()
        co._daughters.cache_clear()
    return res


def write_md(res: dict, path: Path) -> None:
    s = res["summary"]
    lines = ["# Coincidence table: independent checks", "",
             "Protocol: `docs/baseline/ensdf_coincidence_protocol.md`.", "",
             "## Single-path cascades (P = 1 / (1 + alpha))", "",
             "| Nuclide | i keV | j keV | table | expected | ok |", "|---|---|---|---|---|---|"]
    for a in res["analytic"]:
        lines.append(f"| {a['nuclide']} | {a['i']} | {a['j']} | {a['table']} | "
                     f"{a['expected'] if a['expected'] is None else round(a['expected'], 6)} | {a['ok']} |")
    lines += ["", f"## Monte Carlo ({MC_DECAYS} decays per mode, seed {MC_SEED})", "",
              f"{s['mc_compared']} pairs and annihilation probabilities compared, {s['mc_failed']} outside "
              f"max({ABS_TOL}, {SIGMAS:g} sigma); largest |table - simulation| {s['mc_worst_abs']:.4f}.", "",
              "| Nuclide | mode | compared | failed | worst |", "|---|---|---|---|---|"]
    for n, recs in res["monte_carlo"].items():
        for t in recs:
            if t["status"] != "ok":
                lines.append(f"| {n} | {t['mode']} | {t['status']} | | |")
                continue
            rows = t["pairs"] + t["ann"]
            lines.append(f"| {n} | {t['mode']} | {len(rows)} | {sum(not r['ok'] for r in rows)} | {t['worst']:.4f} |")
    lines += ["", "## Library coverage", "",
              f"Library gamma lines >= 1 % described: {s['described']}; in the table but not described: "
              f"{s['not_described']} ({', '.join(res['coverage']['not_described'])})."]
    if "coverage_old" in res:
        o = res["coverage_old"]
        lines.append(f"Previous table: {o['described']} described, {o['not_described']} not described; "
                     f"lost: {', '.join(o['lost']) or 'none'}.")
    lines += [f"No ENSDF data: {', '.join(res['no_ensdf_data']) or 'none'}. "
              f"Unresolved annihilation: {', '.join(res['ann_unresolved']) or 'none'}.", ""]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def out_folder(arg: str) -> Path:
    """The output folder, which must lie inside the current working directory."""
    base = Path(os.path.realpath(os.getcwd()))
    out = Path(os.path.realpath(os.path.join(base, arg)))
    if os.path.commonpath([base, out]) != str(base):
        raise ValueError(f"output folder {arg!r} is outside the working directory")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", default=None)
    ap.add_argument("--old", default=None, help="previous coincidence table, for the coverage comparison")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    raw = raw_folder(a.raw)
    if not (raw / "decay_rads_g").is_dir():
        print(f"no LiveChart files in {raw}", file=sys.stderr)
        return 2
    try:
        out = out_folder(a.out)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    res = run(raw, a.old)
    out.mkdir(parents=True, exist_ok=True)
    (out / "coincidence_check.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    write_md(res, out / "coincidence_check.md")
    print(json.dumps(res["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

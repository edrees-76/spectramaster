"""Event-by-event cascade simulation for the true-coincidence summing benchmark
(docs/baseline/tcs_protocol.md).

Independent of the correction formula and of the coincidence table: hand-coded ENSDF level
schemes with the gamma intensities of the bundled library; the beta / EC feeding of each level is
the intensity balance (out - in, >= 0), a level decays by its gammas in proportion to their
intensities.  Each photon independently deposits its full energy (eps_p), part of it
(eps_t - eps_p) or nothing; an event counts in the peak of line i when it has no partial deposit
and its full-energy deposits sum to E_i (0.5 keV).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

LIB = Path(__file__).resolve().parents[1] / "analysis" / "data" / "gamma_library.json"

# ENSDF level energies (keV) and gamma transitions (library energy, initial level, final level)
SCHEMES = {
    "Co-60": ([0.0, 1332.514, 2505.753],
              [(1173.228, 2, 1), (1332.492, 1, 0)]),
    "Cs-134": ([0.0, 604.721, 1167.968, 1400.587, 1643.304, 1969.886],
               [(475.365, 4, 2), (563.246, 2, 1), (569.331, 5, 3), (604.721, 1, 0), (795.864, 3, 1),
                (801.953, 5, 2), (1038.61, 4, 1), (1167.968, 2, 0), (1365.185, 5, 1)]),
    "Y-88": ([0.0, 1836.087, 2734.141, 3584.8],
             [(850.6, 3, 2), (898.042, 2, 1), (1836.063, 1, 0), (2734.0, 2, 0)]),
}
MAX_GAMMAS = 8            # longest cascade simulated (levels - 1 suffice)


def eps_peak(e, e1000: float):
    return e1000 * (np.asarray(e, dtype=float) / 1000.0) ** -0.85


def peak_to_total(e, a: float = 0.24, b: float = -0.63):
    return np.minimum(1.0, a * (np.asarray(e, dtype=float) / 1000.0) ** b)


@dataclass
class Scheme:
    levels: np.ndarray
    gammas: np.ndarray          # keV
    initial: np.ndarray         # level index
    final: np.ndarray
    intensity: np.ndarray       # library photons per decay
    feeding: np.ndarray         # per decay, normalised
    emission: np.ndarray        # photons per decay implied by the scheme


def scheme(nuclide: str) -> Scheme:
    levels, trans = SCHEMES[nuclide]
    lib = json.loads(LIB.read_text(encoding="utf-8"))["nuclides"][nuclide]["lines"]
    e = np.array([t[0] for t in trans])
    ini = np.array([t[1] for t in trans])
    fin = np.array([t[2] for t in trans])
    inten = np.array([next(ln[1] for ln in lib if abs(ln[0] - g) < 0.5) / 100.0 for g in e])
    nl = len(levels)
    out = np.array([inten[ini == k].sum() for k in range(nl)])
    inn = np.array([inten[fin == k].sum() for k in range(nl)])
    feed = np.maximum(out - inn, 0.0)
    feed[0] = 0.0
    feed /= feed.sum()
    # population of each level per decay (top-down), then photons per decay
    pop = feed.copy()
    emission = np.zeros(len(e))
    for k in range(nl - 1, 0, -1):
        sel = np.nonzero(ini == k)[0]
        if not len(sel) or out[k] <= 0:
            continue
        br = inten[sel] / out[k]
        emission[sel] = pop[k] * br
        for g, b in zip(sel, br):
            pop[fin[g]] += pop[k] * b
    return Scheme(np.array(levels), e, ini, fin, inten, feed, emission)


def simulate(nuclide: str, e1000: float, n: int, seed: int, pt=(0.24, -0.63), chunk: int = 1_000_000) -> dict:
    """{line energy: (COI_MC, sigma)} from n simulated decays."""
    s = scheme(nuclide)
    rng = np.random.default_rng(seed)
    ep = eps_peak(s.gammas, e1000)
    et = np.minimum(ep / peak_to_total(s.gammas, *pt), 1.0)
    nl = len(s.levels)
    # per level: cumulative branching over its gammas
    branches = []
    for k in range(nl):
        sel = np.nonzero(s.initial == k)[0]
        tot = s.intensity[sel].sum()
        branches.append((sel, np.cumsum(s.intensity[sel]) / tot if len(sel) else None))
    counts = np.zeros(len(s.gammas))
    done = 0
    while done < n:
        m = min(chunk, n - done)
        done += m
        level = rng.choice(nl, size=m, p=s.feeding)
        esum = np.zeros(m)
        partial = np.zeros(m, dtype=bool)
        for _step in range(MAX_GAMMAS):
            alive = level > 0
            if not alive.any():
                break
            g = np.full(m, -1)
            u = rng.random(m)
            for k in range(1, nl):
                sel, cum = branches[k]
                at = alive & (level == k)
                if cum is None or not at.any():
                    continue
                g[at] = sel[np.minimum(np.searchsorted(cum, u[at]), len(sel) - 1)]
            idx = np.nonzero(g >= 0)[0]
            gi = g[idx]
            r = rng.random(len(idx))
            full = r < ep[gi]
            part = (~full) & (r < et[gi])
            esum[idx[full]] += s.gammas[gi[full]]
            partial[idx[part]] = True
            level[idx] = s.final[gi]
        ok = ~partial
        for i, eg in enumerate(s.gammas):
            counts[i] += np.count_nonzero(ok & (np.abs(esum - eg) <= 0.5))
    out = {}
    for i, eg in enumerate(s.gammas):
        expected = n * s.emission[i] * ep[i]
        out[float(eg)] = (counts[i] / expected, np.sqrt(max(counts[i], 1.0)) / expected)
    return out

"""Gamma-gamma coincidence data for true-coincidence summing (TCS).

The table ``data/coincidence_table.json`` is built by ``data/build_coincidences.py`` from
SandiaDecay (ENSDF-derived, LGPL-2.1; see data/SOURCES.md).  For each decay transition of a
nuclide it gives the gammas (energy, gammas per decay of the transition) and the cascade
coincidence probabilities P(j | i): gamma j is emitted in the same decay given that gamma i is,
i above j.  The reverse probability is P(i | j) = I_i P(j | i) / I_j.

Limits of the data: gamma-gamma only (no X-ray or annihilation coincidences, so X-ray - gamma
summing of EC nuclides and 511 keV summing of positron emitters are not described), no angular
correlation, and a few physically impossible pairs of the source were dropped (``dropped``).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

TABLE = Path(__file__).resolve().parent / "data" / "coincidence_table.json"


@dataclass
class Transition:
    """One decay branch of a nuclide: gammas and their pairwise cascade probabilities."""
    br: float                       # branching ratio of the transition
    energies: np.ndarray            # keV
    intensities: np.ndarray         # gammas per decay of the transition
    after: np.ndarray               # after[i, j] = P(j | i), j below i in the cascade (0 otherwise)
    dropped: int = 0                # inconsistent source pairs left out
    coincident: np.ndarray = field(init=False)   # coincident[i, j] = P(j | i) in either order

    def __post_init__(self):
        rev = (self.intensities[:, None] * self.after / np.where(self.intensities > 0, self.intensities, 1.0)[None, :]).T
        self.coincident = self.after + rev

    def index(self, energy: float, tol: float = 1.0) -> int | None:
        """Index of the gamma nearest `energy` within `tol` keV, or None."""
        if not len(self.energies):
            return None
        k = int(np.argmin(np.abs(self.energies - energy)))
        return k if abs(self.energies[k] - energy) <= tol else None


@lru_cache(maxsize=1)
def _table() -> dict:
    return json.loads(TABLE.read_text(encoding="utf-8"))


def source() -> dict:
    """Provenance of the bundled table (file, commit, SHA-256, license, thresholds)."""
    return dict(_table()["source"])


def has_cascades(nuclide: str) -> bool:
    return nuclide in _table()["nuclides"]


def transitions(nuclide: str) -> list[Transition]:
    """The nuclide's decay transitions that have gamma cascades ([] when it has none)."""
    out = []
    for rec in _table()["nuclides"].get(nuclide, []):
        g = np.array(rec["g"], dtype=float).reshape(-1, 2)
        after = np.zeros((len(g), len(g)))
        for i, j, p in rec["c"]:
            after[int(i), int(j)] = float(p)
        out.append(Transition(float(rec["br"]), g[:, 0].copy(), g[:, 1].copy(), after, int(rec.get("dropped", 0))))
    return out


# ------------------------------------------------------------------ correction (first order)
SUM_TOL_KEV = 1.0          # a + b = i (summing-in) within this
LINE_TOL_KEV = 1.0         # library line <-> table gamma


def peak_to_total(energy, a: float, b: float):
    """Peak-to-total model PT(E) = min(1, a (E / 1000 keV)^b) (user-supplied assumption)."""
    return np.minimum(1.0, a * (np.maximum(np.asarray(energy, dtype=float), 1.0) / 1000.0) ** b)


@dataclass
class Coi:
    factor: float = 1.0          # observed / summing-free counts of the line (divide the activity by it)
    summing_out: float = 0.0     # sum_j P(j|i) eps_t(E_j)
    summing_in: float = 0.0      # relative gain from crossover pairs
    found: bool = False          # the line is in the table (a cascade member)


def coi(nuclide: str, energy: float, eps_peak, pt) -> Coi:
    """First-order coincidence summing correction of the line at `energy` keV
    (docs/baseline/tcs_protocol.md):

        COI = 1 - sum_j P(j|i) eps_t(E_j) + sum_(a,b) I_a P(b|a) eps_p(E_a) eps_p(E_b) / I_i

    with eps_t = eps_p / PT, the pairs a above b with |E_a + E_b - E_i| <= SUM_TOL_KEV.  `eps_peak`
    and `pt` are callables of energy (keV).  A line emitted by several transitions takes their
    emission-weighted mean; a line of no cascade gives COI = 1 (found False)."""
    num_out = num_in = wsum = 0.0
    for t in transitions(nuclide):
        i = t.index(energy, LINE_TOL_KEV)
        if i is None or t.intensities[i] <= 0:
            continue
        ep = np.asarray(eps_peak(t.energies), dtype=float)
        et = np.minimum(ep / np.asarray(pt(t.energies), dtype=float), 1.0)
        out = float(t.coincident[i] @ et)
        gain = 0.0
        a_idx, b_idx = np.nonzero(t.after > 0)
        for a, b in zip(a_idx, b_idx):
            if abs(t.energies[a] + t.energies[b] - t.energies[i]) <= SUM_TOL_KEV:
                gain += t.intensities[a] * t.after[a, b] * ep[a] * ep[b]
        w = t.br * t.intensities[i]
        num_out += w * out
        num_in += t.br * gain / ep[i] if ep[i] > 0 else 0.0
        wsum += w
    if wsum <= 0:
        return Coi()
    so, si = num_out / wsum, num_in / wsum
    return Coi(1.0 - so + si, so, si, True)

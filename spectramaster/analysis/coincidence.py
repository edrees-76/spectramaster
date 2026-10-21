"""Gamma-gamma coincidence data for true-coincidence summing (TCS).

The table ``data/coincidence_table.json`` is built by ``data/build_coincidences.py`` from
SandiaDecay (ENSDF-derived, LGPL-2.1; see data/SOURCES.md).  For each decay transition of a
nuclide it gives the gammas (energy, gammas per decay of the transition) and the cascade
coincidence probabilities P(j | i): gamma j is emitted in the same decay given that gamma i is,
i above j.  The reverse probability is P(i | j) = I_i P(j | i) / I_j.

Limits of the data: gamma-gamma only (no X-ray or annihilation coincidences, so X-ray - gamma
summing of EC nuclides and 511 keV summing of positron emitters are not described), no angular
correlation, and a few physically impossible pairs of the source were dropped (``dropped``).

Short-lived daughters that the gamma library folds into their parent (``includes`` and
``include_factors`` of ``data/gamma_library.json``: Bi-207 -> Pb-207m, Ce-144 -> Pr-144 ...) are
separate nuclides of the table; :func:`transitions` adds their transitions to the parent's,
weighted by the include factor (docs/baseline/tcs_fixes_protocol.md).  Gammas of the parent's
decay and of the daughter's decay are not coincident.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

TABLE = Path(__file__).resolve().parent / "data" / "coincidence_table.json"
LIBRARY = Path(__file__).resolve().parent / "data" / "gamma_library.json"


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


@lru_cache(maxsize=1)
def _daughters() -> dict:
    """{parent: [(daughter, include factor)]} of the bundled library, daughters in the table only."""
    nucs = json.loads(LIBRARY.read_text(encoding="utf-8"))["nuclides"]
    table = _table()["nuclides"]
    out = {}
    for name, e in nucs.items():
        inc = [(d, float(f)) for d, f in zip(e.get("includes", []), e.get("include_factors", []))
               if d in table and float(f) > 0 and d != name]
        if inc:
            out[name] = inc
    return out


def source() -> dict:
    """Provenance of the bundled table (file, commit, SHA-256, license, thresholds)."""
    return dict(_table()["source"])


def has_cascades(nuclide: str) -> bool:
    return nuclide in _table()["nuclides"] or nuclide in _daughters()


def transitions(nuclide: str) -> list[Transition]:
    """The nuclide's decay transitions that have gamma cascades, with those of the short-lived
    daughters the library folds into it (branching x include factor); [] when it has none."""
    out = []
    for name, f in [(nuclide, 1.0)] + _daughters().get(nuclide, []):
        for rec in _table()["nuclides"].get(name, []):
            g = np.array(rec["g"], dtype=float).reshape(-1, 2)
            after = np.zeros((len(g), len(g)))
            for i, j, p in rec["c"]:
                after[int(i), int(j)] = float(p)
            out.append(Transition(f * float(rec["br"]), g[:, 0].copy(), g[:, 1].copy(), after,
                                  int(rec.get("dropped", 0))))
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
    found: bool = False          # the line is in the table (a cascade member) and the table describes it
    ignored: float = 0.0         # sum_j P(j|i) of partners well below e_min (left out: eps = 0)
    reason: str = ""             # why a cascade line is not corrected


INTENSITY_RANGE = (0.75, 1.33)   # table / library emission probability for the table to describe the line
BELOW_CURVE = 0.8                # partners below BELOW_CURVE x e_min are left out (eps = 0)


def coi(nuclide: str, energy: float, eps_peak, pt, e_min: float | None = None,
        intensity: float | None = None) -> Coi:
    """First-order coincidence summing correction of the line at `energy` keV
    (docs/baseline/tcs_protocol.md):

        COI = 1 - sum_j P(j|i) eps_t(E_j) + sum_(a,b) I_a P(b|a) eps_p(E_a) eps_p(E_b) / (I_i eps_p(E_i))

    with eps_t = eps_p / PT, the pairs a above b with |E_a + E_b - E_i| <= SUM_TOL_KEV.  `eps_peak`
    and `pt` are callables of energy (keV).  A line emitted by several transitions takes their
    emission-weighted mean; a line of no cascade gives COI = 1 (found False).

    ``e_min``: partners well below it (under BELOW_CURVE x e_min: outside the efficiency
    calibration, e.g. strongly converted transitions of a few tens of keV) get eps = 0 and are
    reported in ``ignored``; the curve would otherwise lend them the efficiency of its lowest
    point.  Partners just below e_min keep the clamped efficiency.  ``intensity``: the library
    emission probability of the line (fraction).  When the table's (sum over transitions of
    br I) is outside INTENSITY_RANGE times it, the table does not describe that line (a weak
    neighbour within LINE_TOL_KEV, a dropped branch) and the line is not corrected."""
    num_out = num_in = num_ign = wsum = 0.0
    for t in transitions(nuclide):
        i = t.index(energy, LINE_TOL_KEV)
        if i is None or t.intensities[i] <= 0:
            continue
        ep = np.asarray(eps_peak(t.energies), dtype=float)
        low = np.zeros(len(t.energies), dtype=bool) if e_min is None else t.energies < BELOW_CURVE * e_min
        ep = np.where(low, 0.0, ep)
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
        num_ign += w * float(t.coincident[i] @ low)
        wsum += w
    if wsum <= 0:
        return Coi()
    if intensity is not None and intensity > 0:
        r = wsum / intensity
        if not INTENSITY_RANGE[0] <= r <= INTENSITY_RANGE[1]:
            return Coi(reason=f"the coincidence data do not describe this line (emission probability "
                              f"{100 * wsum:.3g} % in the table, {100 * intensity:.3g} % in the library)")
    so, si = num_out / wsum, num_in / wsum
    return Coi(1.0 - so + si, so, si, True, num_ign / wsum)

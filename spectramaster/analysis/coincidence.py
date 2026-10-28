"""Gamma-gamma coincidence data for true-coincidence summing (TCS).

The table ``data/coincidence_table.json`` is built by ``data/build_coincidences_ensdf.py`` from the
ENSDF decay schemes of the IAEA LiveChart of Nuclides (see data/SOURCES.md and
docs/baseline/ensdf_coincidence_protocol.md; SandiaDecay until engine 1.14.0).  For each decay mode
of a nuclide it gives the gammas (energy, gammas per decay of the transition) and the cascade
coincidence probabilities P(j | i): gamma j is emitted in the same decay given that gamma i is,
i above j.  The reverse probability is P(i | j) = I_i P(j | i) / I_j.

Annihilation: per gamma, ``ann`` gives P(beta+ | gamma), the probability that a positron, and so two
511 keV photons, comes with it in the same decay (from the beta+ feeding of the levels,
docs/baseline/annihilation_summing_protocol.md).  Transitions whose beta+ feeding is inconsistent
are marked ``ann_unresolved``: their lines are corrected for gamma-gamma summing only.

Limits of the data: no X-ray coincidences (X-ray - gamma summing of EC nuclides is not described),
no angular correlation, and pairs with inconsistent intensities were dropped (``dropped``).

Short-lived daughters that the gamma library folds into their parent (``includes`` and
``include_factors`` of ``data/gamma_library.json``: Bi-207 -> Pb-207m, Ce-144 -> Pr-144 ...) are
separate nuclides of the table; :func:`transitions` adds their transitions to the parent's,
weighted by the include factor (docs/baseline/tcs_fixes_protocol.md).  Gammas of the parent's
decay and of the daughter's decay are not coincident.  A daughter whose gammas the parent's ENSDF
decay already lists (``daughters_listed_by_parent``: Ba-137m of Cs-137, Pb-207m of Bi-207) is not
added again.
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
    ann: np.ndarray = None          # ann[i] = P(beta+ in the same decay | gamma i), zeros when none
    ann_unresolved: bool = False    # beta+ feeding of this transition not reconstructed
    scheme: np.ndarray = None       # scheme intensities (levels fed by their gamma inflow); None: intensities
    coincident: np.ndarray = field(init=False)   # coincident[i, j] = P(j | i) in either order

    def __post_init__(self):
        # upward P(i | j) = I_i P(j | i) / I_j with the scheme intensities, so that a level receiving more
        # than it emits does not give probabilities above 1 (docs/baseline/ensdf_level_balance_protocol.md)
        s = self.intensities if self.scheme is None else self.scheme
        rev = (s[:, None] * self.after / np.where(s > 0, s, 1.0)[None, :]).T
        self.coincident = self.after + rev
        if self.ann is None:
            self.ann = np.zeros(len(self.energies))

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
    listed = _table().get("daughters_listed_by_parent", {}).get(nuclide, ())
    for name, f in [(nuclide, 1.0)] + _daughters().get(nuclide, []):
        for rec in _table()["nuclides"].get(name, []):
            if name in listed and rec.get("mode") == "IT":
                continue        # the isomer's de-excitation is already in the parent's own decay record
            g = np.array(rec["g"], dtype=float).reshape(-1, 2)
            after = np.zeros((len(g), len(g)))
            for i, j, p in rec["c"]:
                after[int(i), int(j)] = float(p)
            ann = np.zeros(len(g))
            for i, p in rec.get("ann", []):
                ann[int(i)] = float(p)
            gs = np.array(rec["gs"], dtype=float) if "gs" in rec else None
            out.append(Transition(f * float(rec["br"]), g[:, 0].copy(), g[:, 1].copy(), after,
                                  int(rec.get("dropped", 0)), ann, bool(rec.get("ann_unresolved", False)), gs))
    return out


# ------------------------------------------------------------------ correction (first order)
SUM_TOL_KEV = 1.0          # a + b = i (summing-in) within this
LINE_TOL_KEV = 1.0         # library line <-> table gamma
ANNIHILATION_KEV = 511.0
ANN_UNRESOLVED_NOTE = "511 keV annihilation summing not evaluated (beta+ feeding not reconstructed)"


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
    annihilation: float = 0.0    # part of summing_out from 511 keV photons: P(beta+|i) 2 eps_t(511)
    note: str = ""               # what the correction leaves out (ANN_UNRESOLVED_NOTE)


INTENSITY_RANGE = (0.75, 1.33)   # table / library emission probability for the table to describe the line
BELOW_CURVE = 0.8                # partners below BELOW_CURVE x e_min are left out (eps = 0)


def coi(nuclide: str, energy: float, eps_peak, pt, e_min: float | None = None,
        intensity: float | None = None) -> Coi:
    """First-order coincidence summing correction of the line at `energy` keV
    (docs/baseline/tcs_protocol.md):

        COI = 1 - sum_j P(j|i) eps_t(E_j) - P(beta+|i) 2 eps_t(511)
                + sum_(a,b) I_a P(b|a) eps_p(E_a) eps_p(E_b) / (I_i eps_p(E_i))

    with eps_t = eps_p / PT, the pairs a above b with |E_a + E_b - E_i| <= SUM_TOL_KEV.  The 511 keV
    term (docs/baseline/annihilation_summing_protocol.md): each positron gives two annihilation
    photons, counted independently at first order (their 180 degree correlation enters at second
    order); all positrons annihilate in the source; no summing-in with 511 keV.  `eps_peak`
    and `pt` are callables of energy (keV).  A line emitted by several transitions takes their
    emission-weighted mean; a line of no cascade gives COI = 1 (found False).

    ``e_min``: partners well below it (under BELOW_CURVE x e_min: outside the efficiency
    calibration, e.g. strongly converted transitions of a few tens of keV) get eps = 0 and are
    reported in ``ignored``; the curve would otherwise lend them the efficiency of its lowest
    point.  Partners just below e_min keep the clamped efficiency.  ``intensity``: the library
    emission probability of the line (fraction).  When the table's (sum over transitions of
    br I) is outside INTENSITY_RANGE times it, the table does not describe that line (a weak
    neighbour within LINE_TOL_KEV, a dropped branch) and the line is not corrected."""
    num_out = num_in = num_ign = num_ann = wsum = 0.0
    unresolved = False
    for t in transitions(nuclide):
        i = t.index(energy, LINE_TOL_KEV)
        if i is None or t.intensities[i] <= 0:
            continue
        unresolved |= t.ann_unresolved
        ep = np.asarray(eps_peak(t.energies), dtype=float)
        low = np.zeros(len(t.energies), dtype=bool) if e_min is None else t.energies < BELOW_CURVE * e_min
        ep = np.where(low, 0.0, ep)
        et = np.minimum(ep / np.asarray(pt(t.energies), dtype=float), 1.0)
        out = float(t.coincident[i] @ et)
        ann = 0.0
        if t.ann[i] > 0:
            if e_min is not None and ANNIHILATION_KEV < BELOW_CURVE * e_min:
                num_ign += t.br * t.intensities[i] * float(t.ann[i])
            else:
                ep511 = float(np.ravel(np.asarray(eps_peak(ANNIHILATION_KEV), dtype=float))[0])
                et511 = min(ep511 / float(np.ravel(np.asarray(pt(ANNIHILATION_KEV), dtype=float))[0]), 1.0)
                ann = float(t.ann[i]) * 2.0 * et511
        out += ann
        gain = 0.0
        a_idx, b_idx = np.nonzero(t.after > 0)
        for a, b in zip(a_idx, b_idx):
            if abs(t.energies[a] + t.energies[b] - t.energies[i]) <= SUM_TOL_KEV:
                gain += t.intensities[a] * t.after[a, b] * ep[a] * ep[b]
        w = t.br * t.intensities[i]
        num_out += w * out
        num_ann += w * ann
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
    return Coi(1.0 - so + si, so, si, True, num_ign / wsum, annihilation=num_ann / wsum,
               note=ANN_UNRESOLVED_NOTE if unresolved else "")

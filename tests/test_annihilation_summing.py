"""511 keV annihilation summing in the true-coincidence correction
(docs/baseline/annihilation_summing_protocol.md)."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from spectramaster.analysis import coincidence as co
from spectramaster.analysis.data import build_coincidences as bc
from spectramaster.validation import annihilation as an
from spectramaster.validation import tcs_mc


def _const(v):
    return lambda e: np.full(np.shape(e), v, dtype=float)


# Na-22 P(beta+ | 1274.5 keV) of the ENSDF table (LiveChart: beta+ 89.9 % to the 1274.5 keV level,
# gamma 99.94 %); AN.C1 registered 0.90326 / 0.99941 of SandiaDecay (ensdf_coincidence_protocol.md)
NA22_ANN = 0.899515


def test_table_probabilities_as_registered():
    r = an.c1()
    off = [x for x in r["rows"] if abs(x["diff"]) > an.C1_TOL]
    # AN.C1 fails as written with the ENSDF table, only by the source difference of Na-22
    assert [x["nuclide"] for x in off] == ["Na-22"] and not r["pass"]
    assert off[0]["table"] == pytest.approx(0.899 / 0.99941, abs=1e-4)


def test_na22_coi_is_the_analytic_value():
    assert an.c4()["pass"]
    c = co.coi("Na-22", 1274.537, _const(0.03), _const(0.25))
    assert c.found and c.annihilation == pytest.approx(NA22_ANN * 2 * 0.12, abs=1e-5)
    assert c.summing_out == pytest.approx(c.annihilation)          # no gamma partner


def test_511_below_the_curve_is_left_out_and_reported():
    c = co.coi("Na-22", 1274.537, _const(0.03), _const(0.25), e_min=700.0)
    assert c.factor == 1.0 and c.annihilation == 0.0 and c.ignored == pytest.approx(NA22_ANN, abs=1e-5)


def test_ground_state_positrons_give_no_correction():
    for nuc, e in (("Zn-65", 1115.54), ("Co-58", 863.95)):
        c = co.coi(nuc, e, _const(0.03), _const(0.25))
        assert c.annihilation == 0.0


def test_unresolved_transitions_are_reported(monkeypatch):
    # the ENSDF table has none (Mn-52 was one of SandiaDecay's): a hand-made transition
    assert not any(t.ann_unresolved for n in co._table()["nuclides"] for t in co.transitions(n))
    t = co.Transition(1.0, np.array([1434.0, 744.2]), np.array([1.0, 0.9]),
                      np.array([[0.0, 0.9], [0.0, 0.0]]), ann_unresolved=True)
    monkeypatch.setattr(co, "transitions", lambda nuclide: [t])
    c = co.coi("Mn-52", 1434.0, _const(0.03), _const(0.25))
    assert c.note == co.ANN_UNRESOLVED_NOTE and c.annihilation == 0.0


def test_reconstruction_on_a_hand_made_transition():
    """beta+ to the 1000 keV level, which emits 600 then 400 keV (Q = 3000 keV); a weak EC branch
    to the ground state fixes Q (without it Q = 2400 keV, feeding the 400 keV level, fits as well)."""
    tr = {"br": 1.0, "g": [{"e": 600.0, "i": 0.99, "id": None, "c": [("1", 1.0)]},
                           {"e": 400.0, "i": 0.99, "id": "1", "c": []}],
          "ec": [(2000.0, 0.39), (3000.0, 0.01)], "p": [(3000.0 - bc.ME2_KEV - 1000.0, 0.6)]}
    ann, ok = bc.annihilation(tr)
    assert ok and ann == {0: pytest.approx(0.6 / 0.99), 1: pytest.approx(0.6 / 0.99)}
    tr["p"] = [(3000.0 - bc.ME2_KEV - 1000.0, 0.6), (123.0, 0.05)]    # the second fits no level
    assert bc.annihilation(tr) == ({}, False)


def test_simulation_keeps_the_existing_schemes_unchanged():
    assert set(tcs_mc.SCHEMES) == {"Co-60", "Cs-134", "Y-88"}
    assert tcs_mc.scheme("Co-60").positron is None
    s = tcs_mc.scheme("Na-22")
    assert s.positron[1] == pytest.approx(0.90326 / (0.90326 + 0.09618))


def test_simulation_agrees_far_from_the_detector():
    mc = tcs_mc.simulate("Na-22", 0.005, 2_000_000, 1)
    c_mc, s = mc[1274.537]
    c = co.coi("Na-22", 1274.537, lambda e: tcs_mc.eps_peak(e, 0.005), tcs_mc.peak_to_total).factor
    assert abs(c / c_mc - 1.0) <= 3 * s / c_mc + 0.005


SANDIA = os.environ.get("SPECTRAMASTER_SANDIA_COINC")


@pytest.mark.skipif(not SANDIA or not Path(SANDIA).exists(), reason="SandiaDecay source not given")
def test_rebuild_reproduces_the_bundled_table(tmp_path):
    out = tmp_path / "t.json"
    bc.build(SANDIA, out)
    assert out.read_text(encoding="utf-8") == bc.OUT.read_text(encoding="utf-8")

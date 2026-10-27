"""Coincidence table builder from ENSDF decay schemes (analysis/data/build_coincidences_ensdf.py,
docs/baseline/ensdf_coincidence_protocol.md), on hand-made LiveChart CSV files."""
from __future__ import annotations

import csv

import numpy as np
import pytest

from spectramaster.analysis import coincidence as co
from spectramaster.analysis.data import build_coincidences_ensdf as be

G_COLS = ["energy", "intensity", "start_level_energy", "end_level_energy", "conversion_coeff",
          "start_level_hl", "end_level_hl", "decay", "decay_%", "p_energy", "half_life_sec", "d_symbol"]
BP_COLS = ["decay", "p_energy", "intensity_beta", "daughter_level_energy"]


def _write(path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def _g(e, i, s, l, a=0.0, mode="B-", **kw):
    return {"energy": e, "intensity": 100.0 * i, "start_level_energy": s, "end_level_energy": l,
            "conversion_coeff": a, "decay": mode, "decay_%": 100, "p_energy": 0, **kw}


def _records(tmp_path, rows, bp=(), nuclide="Xx-100"):
    lc = be.lc_name(nuclide)[0]
    _write(tmp_path / "g" / f"{lc}.csv", G_COLS, rows)
    if bp:
        _write(tmp_path / "bp" / f"{lc}.csv", BP_COLS, bp)
    return be.mode_records(tmp_path / "g", tmp_path / "bp", nuclide, None)


def _p(rec, ei, ej):
    e = [x[0] for x in rec["g"]]
    a, b = e.index(ei), e.index(ej)
    return {(x, y): p for x, y, p in rec["c"]}.get((a, b), 0.0)


# 1600 -> 1000 (600 keV) and 1600 -> 0; 1000 -> 0 (alpha 0.25) and 1000 -> 700 -> 0
SCHEME = [_g(600.0, 0.5, 1600.0, 1000.0), _g(1600.0, 0.2, 1600.0, 0.0),
          _g(1000.0, 0.8, 1000.0, 0.0, a=0.25), _g(300.0, 0.1, 1000.0, 700.0), _g(700.0, 0.1, 700.0, 0.0)]


def test_single_path_conversion_and_branching(tmp_path):
    (rec,) = _records(tmp_path, SCHEME)
    assert rec["mode"] == "B-" and rec["br"] == 1.0
    # level 1000 de-excites by transition intensities 0.8 x 1.25 = 1.0 and 0.1
    assert _p(rec, 600.0, 1000.0) == pytest.approx((1.0 / 1.1) / 1.25, abs=1e-6)
    assert _p(rec, 600.0, 700.0) == pytest.approx(0.1 / 1.1, abs=1e-6)
    assert _p(rec, 300.0, 700.0) == pytest.approx(1.0, abs=1e-6)
    assert _p(rec, 1000.0, 600.0) == 0.0 and _p(rec, 1600.0, 1000.0) == 0.0   # below, or a parallel branch


def test_long_lived_level_ends_the_cascade(tmp_path):
    rows = [dict(r) for r in SCHEME]
    for r in rows:
        if r["start_level_energy"] == 1000.0:
            r["start_level_hl"] = 1.0e-3
    (rec,) = _records(tmp_path, rows)
    assert _p(rec, 600.0, 1000.0) == 0.0 and _p(rec, 600.0, 700.0) == 0.0
    assert _p(rec, 300.0, 700.0) == pytest.approx(1.0, abs=1e-6)            # below the isomer: prompt


def test_same_energy_gammas_are_one_line(tmp_path):
    rows = [_g(400.0, 0.8, 2000.0, 1600.0), _g(800.0, 0.5, 1600.0, 800.02), _g(800.02, 0.5, 800.02, 0.0),
            _g(1600.0, 0.3, 1600.0, 0.0)]
    (rec,) = _records(tmp_path, rows)
    assert [x[0] for x in rec["g"]] == [400.0, 800.01, 1600.0]
    assert rec["g"][1][1] == pytest.approx(1.0)
    # after 400 keV both 800 keV gammas follow (each 5/8): 1.25 photons of the line, not a
    # probability; the pair is left out and counted
    assert _p(rec, 400.0, 800.01) == 0.0 and rec["dropped"] == 1


def test_merged_line_above_and_below_keeps_the_stronger_direction(tmp_path):
    # 852 keV from 2000 -> 1148 (weak) and from 852 -> 0 (strong) around 296 keV (1148 -> 852)
    rows = [_g(852.21, 0.0037, 2000.0, 1148.8), _g(1148.8, 0.015, 2000.0, 852.2),
            _g(296.8, 0.00066, 1148.8, 852.2), _g(1148.8, 0.01, 1148.8, 0.0), _g(852.21, 0.2, 852.2, 0.0)]
    (rec,) = _records(tmp_path, rows)
    assert rec.get("dropped", 0) >= 1
    e = [x[0] for x in rec["g"]]
    t = co.Transition(1.0, np.array(e), np.array([x[1] for x in rec["g"]]), _after(rec))
    assert np.all(t.coincident <= be.REVERSE_TOL + 1e-9)
    assert _p(rec, 296.8, 852.21) == pytest.approx(1.0, abs=1e-6)


def _after(rec):
    a = np.zeros((len(rec["g"]),) * 2)
    for i, j, p in rec["c"]:
        a[i, j] = p
    return a


def test_beta_plus_probability_from_the_level_feeding(tmp_path):
    rows = [_g(1000.0, 0.9, 1000.0, 0.0, mode="EC+B+")]
    bp = [{"decay": "EC+B+", "p_energy": 0, "intensity_beta": 60.0, "daughter_level_energy": 1000.0},
          {"decay": "EC+B+", "p_energy": 0, "intensity_beta": 10.0, "daughter_level_energy": 0.0}]
    (rec,) = _records(tmp_path, rows, bp)
    assert rec["mode"] == "EC+B+" and rec["ann"] == [[0, pytest.approx(0.6 / 0.9, abs=1e-6)]]
    assert not rec.get("ann_unresolved")


def test_daughter_listed_by_the_parent_is_not_added_again(tmp_path, monkeypatch):
    gdir = tmp_path / "g"
    _write(gdir / "100aa.csv", G_COLS, [_g(500.0, 0.5, 800.0, 300.0, d_symbol="Bb"),
                                        _g(300.0, 0.9, 300.0, 0.0, d_symbol="Bb")])
    _write(gdir / "100bb.csv", G_COLS, [{**_g(300.0, 0.9, 300.0, 0.0, mode="IT"), "p_energy": 300.0,
                                         "half_life_sec": 100.0}])
    lib = {"Aa-100": {"includes": ["Bb-100m"], "half_life_s": 1.0e5}, "Bb-100m": {"half_life_s": 100.0}}
    assert be.daughters_listed_by_parent(lib, gdir) == {"Aa-100": ["Bb-100m"]}
    doc = {"nuclides": {"Aa-100": [{"br": 1.0, "mode": "B-", "g": [[300.0, 0.9], [500.0, 0.5]], "c": [[1, 0, 1.0]]}],
                        "Bb-100m": [{"br": 1.0, "mode": "IT", "g": [[300.0, 0.9]], "c": []}]},
           "daughters_listed_by_parent": {"Aa-100": ["Bb-100m"]}}
    monkeypatch.setattr(co, "_table", lambda: doc)
    monkeypatch.setattr(co, "_daughters", lambda: {"Aa-100": [("Bb-100m", 1.0)]})
    (t,) = co.transitions("Aa-100")
    assert t.intensities[t.index(300.0)] == pytest.approx(0.9)            # not 0.9 + 0.9


def test_check_without_livechart_files_is_refused(tmp_path):
    from spectramaster.validation import coincidence_ensdf_check as ck
    assert ck.OUT.parts[-3:] == ("docs", "baseline", "after_CT1")
    assert ck.main(["--raw", str(tmp_path)]) == 2


def test_check_compares_upward_and_two_way_probabilities():
    """R4-F (round4_validation_protocol.md): the upward P(a | b) = I_a P(b | a) / I_b and the two-way
    probability the correction uses are compared with the simulated counts."""
    from collections import defaultdict
    from spectramaster.validation import coincidence_ensdf_check as ck
    tab = [[1000.0, 0.5], [500.0, 1.0]]                 # 1000 keV above 500 keV, P(500 | 1000) = 1
    cnt = {0: 5000, 1: 10000}
    pair = defaultdict(int, {(0, 1): 5000})
    up, both = ck.other_directions(tab, {(0, 1): 1.0}, cnt, pair, {0, 1})
    assert [(r["i"], r["j"], r["table"], r["mc"], r["ok"]) for r in up] == [(1000.0, 500.0, 0.5, 0.5, True)]
    assert {(r["i"], r["j"]): (r["table"], r["mc"]) for r in both} == {(1000.0, 500.0): (1.0, 1.0),
                                                                     (500.0, 1000.0): (0.5, 0.5)}
    assert all(r["ok"] for r in both)
    # listed intensity of the upper gamma inconsistent with the cascade: the upward row fails
    up, both = ck.other_directions([[1000.0, 0.8], [500.0, 1.0]], {(0, 1): 1.0}, cnt, pair, {0, 1})
    assert up[0]["table"] == 0.8 and up[0]["mc"] == 0.5 and not up[0]["ok"]
    assert [r["ok"] for r in both] == [True, False]


# ---- levels receiving more than they emit (docs/baseline/ensdf_level_balance_protocol.md)

def test_balanced_scheme_has_no_scheme_intensities(tmp_path):
    (rec,) = _records(tmp_path, SCHEME)
    assert "gs" not in rec


def test_level_fed_by_more_than_it_emits_bounds_the_upward_probability(tmp_path):
    # 700 keV feeds the 300 keV level at 0.5 per decay; the 300 keV gamma is listed at 0.495
    (rec,) = _records(tmp_path, [_g(700.0, 0.5, 1000.0, 300.0), _g(300.0, 0.495, 300.0, 0.0)])
    e = [x[0] for x in rec["g"]]
    assert rec["gs"][e.index(300.0)] == pytest.approx(0.5, rel=1e-6)          # populated by its inflow
    assert rec["gs"][e.index(700.0)] == pytest.approx(0.5, rel=1e-6)
    g = np.array([x[1] for x in rec["g"]])
    old = co.Transition(1.0, np.array(e), g, _after(rec))
    new = co.Transition(1.0, np.array(e), g, _after(rec), scheme=np.array(rec["gs"]))
    lo, hi = e.index(300.0), e.index(700.0)
    assert old.coincident[lo, hi] == pytest.approx(0.5 / 0.495, rel=1e-6)    # above 1 with the listed intensity
    assert new.coincident[lo, hi] == pytest.approx(1.0, rel=1e-6)
    assert new.coincident[hi, lo] == old.coincident[hi, lo]                  # downward unchanged


def test_bundled_table_upward_probabilities_at_most_one():
    worst = 0.0
    for name, recs in co._table()["nuclides"].items():
        for rec in recs:
            s = np.array(rec.get("gs", [x[1] for x in rec["g"]]), dtype=float)
            for i, j, p in rec["c"]:
                worst = max(worst, s[i] * p / s[j])
    assert worst <= 1.0 + 1e-6
    (t,) = co.transitions("Co-57")
    assert t.coincident[t.index(14.4), t.index(122.06)] <= 1.0 + 1e-6

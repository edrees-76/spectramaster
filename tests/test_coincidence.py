"""Gamma-gamma coincidence table (analysis/coincidence.py, data/build_coincidences.py)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from spectramaster.analysis import coincidence as co
from spectramaster.analysis.efficiency import TCS_NUCLIDES

LIB = json.loads((Path(co.__file__).parent / "data" / "gamma_library.json").read_text(encoding="utf-8"))["nuclides"]


def test_co60_cascade_both_ways():
    (t,) = co.transitions("Co-60")
    i, j = t.index(1173.2), t.index(1332.5)
    assert t.after[i, j] == pytest.approx(0.9999)
    assert t.after[j, i] == 0.0                                 # 1332 is below 1173
    assert t.coincident[j, i] == pytest.approx(0.9985 * 0.9999 / 0.999826, rel=1e-6)


def test_cs134_main_cascade():
    t = co.transitions("Cs-134")[0]
    a, b = t.index(795.8), t.index(604.7)
    assert t.coincident[a, b] == pytest.approx(0.994)
    assert t.coincident[b, a] == pytest.approx(0.8544 * 0.994 / 0.9756, rel=1e-4)
    assert t.index(2000.0) is None


def test_probabilities_are_physical_everywhere():
    nuc = json.loads(co.TABLE.read_text(encoding="utf-8"))["nuclides"]
    for name in nuc:
        for t in co.transitions(name):
            assert np.all(t.coincident >= 0) and np.all(t.coincident <= 1.02), name
            assert np.all(np.diag(t.after) == 0)


def test_intensities_agree_with_the_library():
    """Per-decay intensities of the main lines agree with the bundled gamma library (same ENSDF
    origin; the library prefers IAEA values) to 2 %."""
    for name, e in (("Co-60", 1332.492), ("Cs-134", 604.721), ("Cs-134", 795.864), ("Bi-214", 609.32),
                    ("Tl-208", 583.19), ("Y-88", 1836.06), ("Ba-133", 356.013)):
        per_decay = sum(t.br * t.intensities[k] for t in co.transitions(name)
                        if (k := t.index(e)) is not None)
        lib = next(ln[1] for ln in LIB[name]["lines"] if abs(ln[0] - e) < 1.0) / 100.0
        assert per_decay == pytest.approx(lib, rel=0.02), (name, e)


def test_cascade_emitters_are_covered():
    """Every cascade emitter flagged by the engine has data, except those whose summing is not
    gamma-gamma (Na-22: 511 keV annihilation) or comes from daughters (Th-228, Ra-228)."""
    missing = {n for n in TCS_NUCLIDES if not co.has_cascades(n)}
    assert missing == {"Na-22", "Th-228", "Ra-228"}
    assert not co.has_cascades("Cs-137") and co.transitions("Cs-137") == []


def test_provenance():
    s = co.source()
    assert s["commit"] == "cd75314b56e12b80497531a1fbeed9c8e9968403"
    assert s["sha256"] == "ef9dcdb7e598c999cebab3fdcbfc968c851d191ae0e7600b3fc019fb11a6fb06"
    assert s["license"] == "LGPL-2.1"


@pytest.mark.skipif(not os.environ.get("SPECTRAMASTER_SANDIA_COINC"),
                    reason="set SPECTRAMASTER_SANDIA_COINC to sandia.decay.min.xml to check the rebuild")
def test_rebuild_is_identical(tmp_path):
    from spectramaster.analysis.data import build_coincidences as bc
    out = tmp_path / "t.json"
    bc.build(Path(os.environ["SPECTRAMASTER_SANDIA_COINC"]), out)
    assert out.read_text(encoding="utf-8") == co.TABLE.read_text(encoding="utf-8")

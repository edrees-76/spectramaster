"""Gamma-gamma coincidence table (analysis/coincidence.py, data/build_coincidences_ensdf.py)."""
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
    assert t.after[i, j] == pytest.approx(1.0 / (1.0 + 1.62e-4), abs=1e-6)   # 1 / (1 + alpha_1332)
    assert t.after[j, i] == 0.0                                 # 1332 is below 1173
    assert t.coincident[j, i] == pytest.approx(0.9985 * t.after[i, j] / 0.999826, rel=1e-6)


def test_cs134_main_cascade():
    t = co.transitions("Cs-134")[0]
    a, b = t.index(795.8), t.index(604.7)
    assert t.coincident[a, b] == pytest.approx(0.994, abs=1e-3)
    s = t.intensities if t.scheme is None else t.scheme       # scheme intensities (ensdf_level_balance_protocol.md)
    assert t.coincident[b, a] == pytest.approx(s[a] * t.coincident[a, b] / s[b], rel=1e-9)
    assert t.coincident[b, a] == pytest.approx(0.8544 * 0.994 / 0.9756, rel=0.01)
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
    """Every cascade emitter flagged by the engine has data, except those whose summing comes from
    daughters (Ra-228; Th-228 has its own weak cascades in ENSDF).  Na-22 (511 keV annihilation
    only) is covered since annihilation_summing_protocol.md."""
    missing = {n for n in TCS_NUCLIDES if not co.has_cascades(n)}
    assert missing == {"Ra-228"}
    assert not co.has_cascades("Cs-137") and co.transitions("Cs-137") == []


def test_provenance():
    s = co.source()
    assert "ENSDF" in s["project"] and "nds.iaea.org" in s["project"]
    assert s["digest_sha256"] == "e197398a0b2f506bbea49194fb83a56afb19faa840aa6353e87ad5d7ccc00b8b"
    assert s["files"] == len(s["files_sha256"]) == 450
    assert s["no_ensdf_data"] == ["Ag-109m", "Ce-140m"]


@pytest.mark.skipif(not os.environ.get("SPECTRAMASTER_LIVECHART_DIR"),
                    reason="set SPECTRAMASTER_LIVECHART_DIR to the LiveChart raw folder to check the rebuild")
def test_rebuild_is_identical(tmp_path):
    from spectramaster.analysis.data import build_coincidences_ensdf as be
    out = tmp_path / "t.json"
    be.build(Path(os.environ["SPECTRAMASTER_LIVECHART_DIR"]), out)
    assert out.read_text(encoding="utf-8") == co.TABLE.read_text(encoding="utf-8")


def test_build_refuses_any_other_source(tmp_path):
    from spectramaster.analysis.data import build_coincidences as bc
    wrong = tmp_path / "sandia.decay.min.xml"
    wrong.write_text("<document/>", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        bc.build(wrong, tmp_path / "t.json")
    other = tmp_path / "other.xml"
    other.write_text("<document/>", encoding="utf-8")
    with pytest.raises(ValueError, match="expected"):
        bc.build(other, tmp_path / "t.json")
    assert not (tmp_path / "t.json").exists()

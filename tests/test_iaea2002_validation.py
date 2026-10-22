"""IAEA 2002 test-spectra activity check (docs/baseline/iaea2002_validation_protocol.md)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectramaster.validation import iaea2002 as ia

BASE = Path(__file__).resolve().parents[1] / "docs" / "baseline"
RESULTS = BASE / "after_IA1" / "iaea2002_results.json"          # the pre-registered record (engine 1.7.0)
CURRENT = BASE / "after_MX1" / "iaea2002_results.json"          # the current engine (1.13.0)


def _pair(geo, spectrum, nuc, ratio, z, detected=True):
    return {"geometry": geo, "spectrum": spectrum, "long": spectrum in ia.LONG, "nuclide": nuc,
            "ratio": ratio, "z": z, "detected": detected}


def test_certificates_as_printed():
    assert ia.CERT["64921A"]["Cd-109"] == 39214 and ia.CERT["64922A"]["Y-88"] == 6306
    assert ia.CERT["64923"] == {"Ba-133": 1713, "Co-60": 1076, "Eu-152": 3739, "Cr-51": 7903, "Na-22": 1073}
    assert ia.CERT["64924A"]["Cr-51"] == 7827
    assert ia.CAL_U99["Cs-137"] == 4.8 and ia.K99 == 2.576


def test_criteria_count_a_missing_value_as_failure():
    pairs = []
    for geo, names in (("marinelli", ia.GEOMETRIES["marinelli"]["tests"]),
                       ("pillbox", ia.GEOMETRIES["pillbox"]["tests"])):
        for s in names:
            for nuc in ia.TEST_NUCLIDES:
                pairs.append(_pair(geo, s, nuc, 1.0, 0.0))
    assert all(c["pass"] for c in ia.criteria(pairs))
    pairs[0].update(ratio=None, z=None, detected=False)
    got = {c["id"]: c["pass"] for c in ia.criteria(pairs)}
    assert not got["IA.C5"] and not got["IA.C6"] and got["IA.C1"]       # 19/20 = 0.95 still passes C1
    assert got["IA.C4.M"]                                 # one 0 among five ones: the median stays 1


def test_recorded_results_match_the_protocol_limits():
    if not RESULTS.exists():
        pytest.skip("after_IA1 results not present")
    d = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert len(d["pairs"]) == 20
    assert {c["id"]: c["pass"] for c in d["criteria"]} == {
        "IA.C1": False, "IA.C2": True, "IA.C3": False, "IA.C4.M": True, "IA.C4.P": False, "IA.C5": False,
        "IA.C6": True}


@pytest.mark.skipif(not (ia.DEFAULT_DATA / "spectra").exists(), reason="IAEA 2002 test spectra not present")
def test_marinelli_reproduces_the_recorded_ratios():
    if not CURRENT.exists():
        pytest.skip("after_MX1 results not present")
    rec = {(p["spectrum"], p["nuclide"]): p["ratio"]
           for p in json.loads(CURRENT.read_text(encoding="utf-8"))["pairs"]}
    r = ia.run_geometry(ia.DEFAULT_DATA, "marinelli")
    for p in r["pairs"]:
        assert p["ratio"] == pytest.approx(rec[(p["spectrum"], p["nuclide"])], rel=1e-9)

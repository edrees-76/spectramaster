"""Laboratory HPGe spectra compared with GammaVision reports, kept outside the repository and skipped
when absent.  Protocol: docs/baseline/gammavision_compare_protocol.md.
These tests check that the harness runs as pre-registered; the criteria are reported, not asserted."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from spectramaster.validation import gammavision_compare as gv

DATA = Path(os.environ.get("SPECTRAMASTER_GV_DIR", str(gv.DEFAULT_DIR)))
needs_data = pytest.mark.skipif(not (DATA / gv.SAND).is_file(), reason="laboratory GammaVision data not available")


def test_reference_selection_as_pre_registered():
    assert [r[1] for r in gv.GV_SAND] == [295.25, 352.00, 583.45, 609.61, 911.63, 1461.44, 1765.26]
    assert all(r[3] <= 3.0 for r in gv.GV_SAND)
    assert [r[0] for r in gv.GV_OIL] == [186.03, 295.21, 352.18, 1120.11, 1763.48]
    assert gv.OUT.parts[-3:] == ("docs", "baseline", "after_GV1")


@needs_data
def test_harness_runs_on_the_laboratory_spectra():
    res = gv.criteria(gv.analyse(DATA))
    assert list(res["criteria"]) == ["G1", "G2", "G3", "G4", "G5", "G6"]
    assert len(res["spectra"]) == len(gv.SPECTRA)
    assert len(res["sand_comparison"]) == 7
    assert res["summary"]["pass"] + res["summary"]["fail"] == 6

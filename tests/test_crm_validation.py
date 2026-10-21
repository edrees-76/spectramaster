"""Certified reference materials (Truong & Huynh, doi:10.5281/zenodo.23093533, CC BY 4.0), kept
outside the repository and skipped when absent.  Protocol: docs/baseline/crm_validation_protocol.md.
These tests check that the harness runs as pre-registered; the criteria are reported, not asserted."""
from __future__ import annotations

import pytest

from spectramaster.validation import crm_zenodo as cz

needs_data = pytest.mark.skipif(not cz.DEFAULT_DATA.is_file(), reason="Zenodo 23093533 data set not available")


@needs_data
def test_dataset_loads_without_pickle_and_builds_spectra():
    ds = cz.Dataset(cz.DEFAULT_DATA)
    sp = ds.spectrum("S189")
    assert len(sp.counts) == 5760
    assert sp.energy_coeffs == [20.25, 0.5]
    assert ds.meta[ds.index["S189"]]["material"] == "RGU-1"
    assert ds.label("S189", "Pb-214/Bi-214")[0] == pytest.approx(4940.0)
    assert ds.background().live_time > 1e5


@needs_data
def test_selection_and_pairs_as_pre_registered():
    ds, results = cz.run_all()
    pairs = results["cylinder_loglog"]["pairs"]
    q = [p for p in pairs if p["quantitative"]]
    assert len(q) == 19
    assert sorted({p["nuclide"] for p in q}) == ["Cs-137", "K-40", "Ra-226", "Ra-228", "Th-228"]
    assert [p for p in pairs if not p["quantitative"]][0]["id"] == "S086"
    ids = [c["id"] for c in results["cylinder_loglog"]["criteria"]]
    assert ids == ["CRM.C1", "CRM.C2"] + [f"CRM.C3.{n}" for n in cz.TESTED] + ["CRM.C4"]
    # no reference material is both calibration and test
    cal = {ds.meta[ds.index[s]]["material"] for s in cz.CYLINDER_CAL}
    assert not cal & {p["material"] for p in pairs}

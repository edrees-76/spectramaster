"""Concentrations from sample information (Release E, E4)."""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest

from spectramaster.analysis.activity import (ActivityOptions, compute_activities, concentrations,
                                             sampling_decay_factor)
from spectramaster.lab.sample import SampleInfo
from spectramaster.validation.benchmark import _flat_curve
from spectramaster.validation.synthetic import HPGE, Continuum, TruePeak, make_spectrum


@pytest.fixture(scope="module")
def res():
    syn = make_spectrum(HPGE, [TruePeak(661.657, 2e4), TruePeak(364.49, 8e3)], Continuum(300, 400, 10), 7)
    syn.spectrum.start_time = datetime(2026, 5, 10, 8, 0)
    return compute_activities(syn.spectrum, _flat_curve(), ActivityOptions(nuclides=["Cs-137", "I-131", "Co-60"]))


def test_missing_inputs_give_no_value(res):
    out = concentrations(res, SampleInfo(matrix_type="food"), "Bq/kg")
    assert out["rows"] == [] and "sample mass (kg)" in out["missing"] and "mass basis (dry or wet)" in out["missing"]


def test_bq_per_kg_carries_its_basis_and_the_mass_uncertainty(res):
    out = concentrations(res, SampleInfo(matrix_type="soil", mass_kg=0.5, mass_basis="dry"), "Bq/kg",
                         quantity_rel_unc=0.01)
    cs = next(r for r in out["rows"] if r["nuclide"] == "Cs-137")
    a = next(r for r in res.nuclides if r.nuclide == "Cs-137")
    assert out["unit"] == "Bq/kg (dry)"
    assert cs["value"] == pytest.approx(a.activity / 0.5)
    assert cs["u"] == pytest.approx(cs["value"] * math.hypot(a.u / a.activity, 0.01))
    co = next(r for r in out["rows"] if r["nuclide"] == "Co-60")          # not in the spectrum
    assert co["value"] is None and co["text"].startswith("<")


def test_air_concentration_corrects_for_decay_during_sampling(res):
    end = res.ref_date
    s = SampleInfo(matrix_type="air_filter", flow_rate_m3_h=10.0, sampling_start=(end - timedelta(days=7)).isoformat(),
                   sampling_end=end.isoformat(), filter_fraction=1.0, collection_efficiency=0.95,
                   collection_efficiency_note="manufacturer value")
    out = concentrations(res, s, "Bq/m3")
    i131 = next(r for r in out["rows"] if r["nuclide"] == "I-131")
    cs = next(r for r in out["rows"] if r["nuclide"] == "Cs-137")
    assert i131["factor"] == pytest.approx(sampling_decay_factor(8.0252 * 86400, 7 * 86400), rel=1e-3)
    assert i131["factor"] > 1.3 and cs["factor"] == pytest.approx(1.0, abs=1e-3)
    a = next(r for r in res.nuclides if r.nuclide == "Cs-137")
    assert cs["value"] == pytest.approx(a.activity / (1680.0 * 0.95), rel=1e-3)
    assert any("assumption" in n for n in out["notes"])


def test_stored_results_rebuild_exactly(res):
    import json
    from spectramaster.analysis.activity import QuantResults
    from spectramaster.lab.session import quant_to_dict
    d = json.loads(json.dumps(quant_to_dict(res)))           # as written in a session file
    back = QuantResults.from_dict(d)
    assert quant_to_dict(back) == d
    assert back.ref_date == res.ref_date and back.start_time == res.start_time
    assert [r.decision for r in back.nuclides] == [r.decision for r in res.nuclides]
    unit = SampleInfo(matrix_type="soil", mass_kg=0.5, mass_basis="dry")
    assert concentrations(back, unit, "Bq/kg") == concentrations(res, unit, "Bq/kg")


def test_unknown_acquisition_start_is_reported_for_air_filters():
    syn = make_spectrum(HPGE, [TruePeak(364.49, 8e3)], Continuum(300, 400, 10), 7)
    syn.spectrum.start_time = None
    q = compute_activities(syn.spectrum, _flat_curve(), ActivityOptions(nuclides=["I-131"]))
    s = SampleInfo(matrix_type="air_filter", air_volume_m3=100.0, filter_fraction=1.0, collection_efficiency=1.0,
                   sampling_start="2026-05-01T08:00:00", sampling_end="2026-05-08T08:00:00")
    out = concentrations(q, s, "Bq/m3")
    assert any("NOT decay-corrected to the end of sampling" in n for n in out["notes"])

"""Detector / geometry / calibration / sample models (spectramaster.lab), no Qt."""
from __future__ import annotations

import json

import pytest

from spectramaster.analysis.efficiency import EfficiencyPoint, fit_efficiency
from spectramaster.lab import (CalibrationRecord, DetectorProfile, MeasurementGeometry, SampleInfo)
from spectramaster.model import Spectrum


def marinelli(**kw):
    base = dict(name="1 L Marinelli", kind="marinelli", container_id="GA-MA 130G", nominal_volume_ml=1000.0,
                fill_volume_ml=1000.0, matrix="soil", density_g_cm3=1.2)
    base.update(kw)
    return MeasurementGeometry(**base)


def curve():
    pts = [EfficiencyPoint(e, 0.05 * (e / 100.0) ** -0.8, 0.05 * (e / 100.0) ** -0.8 * 0.02, nuclide="X",
                           u_ref_rel=0.015)
           for e in (59.5, 122.1, 344.3, 661.7, 1173.2, 1332.5, 1836.1)]
    return fit_efficiency(pts, "loglog", order=2, name="Mar1L", geometry="1 L Marinelli", detector="GeD1")


# ------------------------------------------------------------------ detector


def test_detector_id_stable_and_optional_characteristics():
    d = DetectorProfile("GeD1", "HPGe")
    assert len(d.id) == 36 and d.relative_efficiency_pct is None and d.crystal_length_mm is None
    d2 = DetectorProfile.from_dict(json.loads(json.dumps(d.to_dict())))
    assert d2 == d
    d2.name = "renamed"
    assert d2.id == d.id
    assert DetectorProfile("GeD1").id != d.id          # never derived from the name
    with pytest.raises(ValueError):
        DetectorProfile("x", "Ge")
    with pytest.raises(ValueError):
        DetectorProfile("x", relative_efficiency_pct=0)   # unknown must be None, not 0


def test_detector_links_calibrations():
    d = DetectorProfile("GeD1")
    rec = CalibrationRecord.from_efficiency_curve(curve(), detector_id=d.id)
    d.link_calibration(rec)
    d.link_calibration(rec)
    assert d.efficiency_calibration_ids == [rec.id] and d.energy_calibration_ids == []


# ------------------------------------------------------------------ geometry


def test_identical_geometries_compatible():
    a = marinelli()
    b = MeasurementGeometry.from_dict(a.to_dict())
    assert a.compatibility(b) == [] and b.compatibility(a) == []


def test_same_volume_different_container_incompatible():
    a = marinelli()
    b = marinelli(kind="cylinder", container_id="bottle-1L")
    r = a.compatibility(b)
    assert r and "kind" in r[0]
    c = marinelli(container_id="Other 1L Marinelli")
    r = a.compatibility(c)
    assert any("container identifier" in x for x in r)


def test_missing_information_gives_unknown_reasons():
    a = marinelli(matrix=None, density_g_cm3=None)
    b = marinelli(density_g_cm3=None)
    r = a.compatibility(b)
    assert any(x.startswith("unknown:") and "matrix" in x for x in r)
    assert any(x.startswith("unknown:") and "density" in x for x in r)
    # volume alone, nothing else known: never compatible
    v1 = MeasurementGeometry("a", "marinelli", nominal_volume_ml=1000)
    v2 = MeasurementGeometry("b", "marinelli", nominal_volume_ml=1000)
    r = v1.compatibility(v2)
    assert r and all(x.startswith("unknown:") for x in r)


def test_geometry_differences_detected():
    a = marinelli()
    assert any("density" in x for x in a.compatibility(marinelli(density_g_cm3=1.6)))
    assert a.compatibility(marinelli(density_g_cm3=1.21)) == []          # within tolerance
    assert any("fill volume" in x for x in a.compatibility(marinelli(fill_volume_ml=800.0)))
    p1 = MeasurementGeometry("p", "point", source_distance_mm=100.0)
    assert p1.compatibility(MeasurementGeometry("p", "point", source_distance_mm=100.4)) == []
    assert any("distance" in x for x in p1.compatibility(MeasurementGeometry("p", "point", source_distance_mm=250)))
    assert any("unknown" in x for x in p1.compatibility(MeasurementGeometry("p", "point")))
    f1 = MeasurementGeometry("f", "filter", filter_shape="circle", filter_dimensions={"diameter_mm": 47.0},
                             filter_position="on end cap")
    assert f1.compatibility(MeasurementGeometry.from_dict(f1.to_dict())) == []
    f2 = MeasurementGeometry.from_dict({**f1.to_dict(), "filter_dimensions": {"diameter_mm": 25.0}})
    assert any("filter dimension" in x for x in f1.compatibility(f2))
    o = MeasurementGeometry("o", "other", container_id="x", fill_volume_ml=10, matrix="m", density_g_cm3=1)
    assert any("unknown" in x for x in o.compatibility(MeasurementGeometry.from_dict(o.to_dict())))


# ------------------------------------------------------------------ calibration


def test_calibration_hash_stable_and_detects_change():
    c = curve()
    rec = CalibrationRecord.from_efficiency_curve(c, detector_id="d1", geometry_id="g1")
    h = rec.content_hash
    again = CalibrationRecord.from_dict(json.loads(json.dumps(rec.to_dict())))
    assert again.content_hash == h and again.integrity_ok() and again == rec
    # labels / status do not change the hash
    again.note = "checked"
    again.name = "renamed"
    again.set_validation("validated", "QC 2026-10")
    assert again.content_hash == h
    # science does
    again.params[0] += 1e-9
    assert again.content_hash != h
    d = rec.to_dict()
    d["params"][1] *= 1.01                                  # hand-edited file
    assert not CalibrationRecord.from_dict(d).integrity_ok()
    other_geom = CalibrationRecord.from_efficiency_curve(c, detector_id="d1", geometry_id="g2")
    assert other_geom.content_hash != h


def test_imported_calibration_defaults_unvalidated():
    rec = CalibrationRecord.from_efficiency_curve(curve())
    assert rec.source == "imported" and rec.validation_status == "unvalidated"
    s = Spectrum(counts=[1.0] * 100, energy_coeffs=[0.5, 2.0], fwhm_coeffs=[1.2, 0.001])
    e = CalibrationRecord.from_spectrum(s, "energy")
    assert e.validation_status == "unvalidated" and e.model == "poly1_channel"
    assert e.energy_range == [0.5, 0.5 + 2.0 * 99] and e.geometry_id is None
    f = CalibrationRecord.from_spectrum(s, "fwhm")
    assert f.params == [1.2, 0.001] and f.content_hash != e.content_hash
    with pytest.raises(ValueError):
        CalibrationRecord.from_spectrum(Spectrum(counts=[1.0]), "energy")
    with pytest.raises(ValueError):
        CalibrationRecord(kind="energy", geometry_id="g")


def test_efficiency_curve_snapshot_round_trip():
    c = curve()
    rec = CalibrationRecord.from_efficiency_curve(c, detector_id="d", geometry_id="g", source="measured")
    back = CalibrationRecord.from_dict(json.loads(json.dumps(rec.to_dict()))).to_efficiency_curve()
    assert back.to_dict() == json.loads(json.dumps(c.to_dict()))
    for e in (80.0, 661.7, 1500.0):
        assert back.efficiency(e) == pytest.approx(c.efficiency(e), rel=1e-12)
        assert back.rel_uncertainty(e) == pytest.approx(c.rel_uncertainty(e), rel=1e-12)
    assert rec.energy_range == [59.5, 1836.1]


# ------------------------------------------------------------------ sample


def test_sample_missing_inputs_per_unit():
    s = SampleInfo("S1", "soil")
    assert s.mass_kg is None and s.filter_fraction is None
    assert s.concentration_unit_inputs("Bq") == []
    assert len(s.concentration_unit_inputs("Bq/kg")) == 2
    assert s.concentration_unit_inputs("Bq/L") == ["sample volume (L)"]
    assert len(s.concentration_unit_inputs("Bq/m3")) == 3
    s.mass_kg = 0.5
    assert s.concentration_unit_inputs("Bq/kg") == ["mass basis (dry or wet)"]
    w = SampleInfo("W1", "water", volume_l=1.0)
    assert w.concentration_unit_inputs("Bq/L") == []
    a = SampleInfo("A1", "air_filter", flow_rate_m3_h=10.0, sampling_start="2026-10-01T08:00",
                   sampling_end="2026-10-02T08:00", filter_fraction=0.5, collection_efficiency=0.99,
                   collection_efficiency_note="glass fibre, manufacturer data")
    assert a.air_volume() == pytest.approx(240.0)
    assert a.concentration_unit_inputs("Bq/m3") == []
    with pytest.raises(ValueError):
        s.concentration_unit_inputs("Bq/g")


def test_sample_validation_and_round_trip():
    with pytest.raises(ValueError):
        SampleInfo("x", mass_kg=0)
    with pytest.raises(ValueError):
        SampleInfo("x", filter_fraction=1.5)
    with pytest.raises(ValueError):
        SampleInfo("x", mass_basis="moist")
    with pytest.raises(ValueError):
        SampleInfo("x", sampling_start="2026-01-02", sampling_end="2026-01-01")
    s = SampleInfo("S", "food", mass_kg=0.25, mass_basis="wet", reference_date="2026-09-30 12:00")
    assert SampleInfo.from_dict(json.loads(json.dumps(s.to_dict()))) == s


def test_non_finite_values_are_stored_as_null():
    import json
    from spectramaster.lab.common import canonical_json, to_plain
    import numpy as np
    doc = {"chi2": float("nan"), "x": np.float64("inf"), "ok": 1.5}
    assert to_plain(doc) == {"chi2": None, "x": None, "ok": 1.5}
    assert json.loads(canonical_json(doc))["chi2"] is None

"""AnalysisSession: persistence, migration, relocation, staleness and undo/redo (no Qt)."""
from __future__ import annotations

import json
import shutil
from datetime import datetime

import pytest

from spectramaster.analysis import NuclideMatch, Peak
from spectramaster.analysis.activity import ActivityOptions, LineResult, NuclideResult, QuantResults
from spectramaster.analysis.efficiency import EfficiencyPoint, fit_efficiency
from spectramaster.lab import (SCHEMA_VERSION, AnalysisSession, CalibrationRecord, DetectorProfile,
                               MeasurementGeometry, SampleInfo, SessionSchemaError, migrate)
from spectramaster.lab.common import file_sha256
from spectramaster.model import Spectrum


def peak(ch, e, area=1000.0):
    return Peak(centroid=ch, energy=e, fwhm=3.0, fwhm_kev=1.5, net_area=area, net_area_unc=area ** 0.5,
                gross_area=area * 1.2, background=area * 0.2, left=int(ch) - 5, right=int(ch) + 5,
                significance=20.0, count_rate=area / 3600.0)


def eff_record(det_id, geo_id):
    pts = [EfficiencyPoint(e, 0.03 * (e / 100) ** -0.7, 0.0006 * (e / 100) ** -0.7, u_ref_rel=0.015)
           for e in (122.1, 344.3, 661.7, 1173.2, 1332.5)]
    return CalibrationRecord.from_efficiency_curve(fit_efficiency(pts, order=2, name="Mar1L"),
                                                   detector_id=det_id, geometry_id=geo_id)


@pytest.fixture
def spec_file(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    f = d / "sample1.spe"
    f.write_bytes(b"$SPEC_ID:\nsample1\n" + bytes(range(256)) * 8)
    return f


@pytest.fixture
def session(spec_file):
    sp = Spectrum(counts=[float(i % 17) for i in range(1024)], energy_coeffs=[0.0, 0.5], live_time=3600.0,
                  source_format="ortec_spe")
    s = AnalysisSession.for_spectrum(spec_file, sp, index=0)
    det = DetectorProfile("GeD1", "HPGe", relative_efficiency_pct=40.0)
    geo = MeasurementGeometry("1 L Marinelli", "marinelli", container_id="130G", nominal_volume_ml=1000,
                              fill_volume_ml=1000, matrix="soil", density_g_cm3=1.3)
    s.set_sample(SampleInfo("S1", "soil", mass_kg=1.1, mass_basis="dry"))
    s.set_detector(det)
    s.set_geometry(geo)
    s.set_calibration(CalibrationRecord.from_spectrum(sp, "energy", detector_id=det.id))
    s.set_calibration(eff_record(det.id, geo.id))
    s.set_library()
    s.set_setting("min_sig", 3.0)
    peaks = [peak(1323.3, 661.66), peak(2926.0, 1460.8, 300.0)]
    matches = [NuclideMatch("Cs-137", 0.95, matched=[(661.657, peaks[0])]),
               NuclideMatch("K-40", 0.9, matched=[(1460.82, peaks[1])], background=True)]
    opts = ActivityOptions(nuclides=("Cs-137", "K-40"), ref_date=datetime(2026, 9, 30, 12), quantity=1.1)
    quant = QuantResults(sample="S1", source_path=str(spec_file), start_time=datetime(2026, 10, 1, 8),
                         live_time=3600.0, real_time=3610.0, ref_date=opts.ref_date, curve_name="Mar1L",
                         curve_model="loglog", background="", options=opts,
                         nuclides=[NuclideResult("Cs-137", [LineResult("Cs-137", 661.657, 0.851)],
                                                 activity=12.5, u=0.6)])
    s.set_results(peaks, matches, quant, engine_version="1.0.0")
    return s


# ------------------------------------------------------------------ persistence


def test_round_trip_save_load(session, tmp_path, spec_file):
    before = spec_file.read_bytes()
    session.set_peak_field(0, "note", "checked", reason="visual check")
    out = session.save(tmp_path / "s.smsession.json")
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["format"] == "spectramaster-session" and doc["schema_version"] == SCHEMA_VERSION
    assert doc["detector_id"] == session.detector["id"] and doc["sample_id"] == "S1"
    assert doc["results"]["nuclide_matches"][0]["matched"] == [[661.657, 0]]
    assert doc["results"]["quant"]["options"]["ref_date"] == "2026-09-30T12:00:00"
    assert all(c["content_hash"] for c in doc["calibrations"])
    loaded = AnalysisSession.load(out)
    assert loaded.to_dict() == session.to_dict()
    assert loaded.created.endswith("+00:00")
    assert spec_file.read_bytes() == before                     # original untouched
    assert sorted(p.name for p in spec_file.parent.iterdir()) == ["sample1.spe"]
    assert not list(tmp_path.glob("*.tmp"))
    with pytest.raises(ValueError):
        session.save(spec_file)
    # loaded history still undoes
    loaded.undo()
    assert loaded.results["peaks"][0]["note"] == ""


def test_future_schema_rejected(session, tmp_path):
    doc = session.to_dict()
    doc["schema_version"] = SCHEMA_VERSION + 1
    p = tmp_path / "future.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SessionSchemaError, match="newer"):
        AnalysisSession.load(p)
    with pytest.raises(SessionSchemaError):
        migrate({"format": "something-else", "schema_version": 1})
    with pytest.raises(SessionSchemaError):
        migrate({"format": "spectramaster-session", "schema_version": "1"})


def test_migration_0_to_1(tmp_path):
    legacy = {"spectrum_path": "C:/old/x.spe", "sample_id": "L1",
              "peaks": [{"centroid": 10.0, "energy": 5.0}], "settings": {"min_sig": 2.5}}
    doc = migrate(legacy)
    assert doc["schema_version"] == 1 and legacy.get("schema_version") is None   # input untouched
    s = AnalysisSession.from_dict(legacy)
    assert s.spectrum_ref["path"] == "C:/old/x.spe" and s.spectrum_ref["sha256"] is None
    assert s.processing_settings == {"min_sig": 2.5} and s.sample == {"sample_id": "L1"}
    assert s.status["results_stale"] and s.is_stale_against("1.0.0", {})
    assert AnalysisSession.from_dict(s.to_dict()).to_dict() == s.to_dict()


# ------------------------------------------------------------------ spectrum relocation


def test_relocation_statuses(session, spec_file, tmp_path):
    assert session.resolve_spectrum().status == "ok"
    moved = tmp_path / "archive" / "2026"
    moved.mkdir(parents=True)
    (moved / "decoy.spe").write_bytes(b"other content")
    shutil.move(str(spec_file), str(moved / "renamed.spe"))
    assert session.resolve_spectrum([tmp_path / "nowhere"]).status == "missing"
    n_ops = len(session.history.ops)
    r = session.resolve_spectrum([tmp_path / "archive"])
    assert r.status == "relocated" and r.path.endswith("renamed.spe")
    assert session.spectrum_ref["path"] == r.path
    op = session.history.ops[-1]
    assert len(session.history.ops) == n_ops + 1 and op.kind == "relocate_spectrum" and "SHA-256" in op.reason
    assert not session.status["results_stale"]                  # same bytes: results still valid
    assert session.resolve_spectrum().status == "ok"
    (moved / "renamed.spe").write_bytes(b"changed")
    assert session.resolve_spectrum().status == "modified"


# ------------------------------------------------------------------ staleness


def test_is_stale_against(session):
    cals = {c["id"]: CalibrationRecord.from_dict(c) for c in session.calibrations}
    assert session.is_stale_against("1.0.0", cals) == []
    assert any("engine 1.0.0" in r for r in session.is_stale_against("1.1.0", cals))
    eff = next(c for c in cals.values() if c.kind == "efficiency")
    eff.set_validation("validated")                             # status only: still fresh
    assert session.is_stale_against("1.0.0", cals) == []
    eff.params[0] *= 1.02
    r = session.is_stale_against("1.0.0", cals)
    assert len(r) == 1 and "efficiency calibration" in r[0]
    stored = session.to_dict()
    session.is_stale_against("2.0", cals)
    assert session.to_dict() == stored                          # nothing recalculated / changed


# ------------------------------------------------------------------ undo / redo


def test_undo_redo_sequences(session):
    s0 = session.state_dict()
    assert not session.status["results_stale"]
    session.set_peak_field(1, "net_area", 310.0, reason="refit with fixed FWHM")
    s1 = session.state_dict()
    assert session.status["results_stale"] and "refit" in session.status["stale_reasons"][0]
    session.add_peak(peak(700.0, 350.0, 50.0), reason="manual")
    s2 = session.state_dict()
    session.remove_peak(0, reason="artefact")
    s3 = session.state_dict()
    assert len(session.results["peaks"]) == 2
    session.set_sample_field("mass_kg", 1.05, reason="re-weighed")
    session.set_setting("min_sig", 2.5)
    session.undo(), session.undo()
    assert session.state_dict() == s3
    session.undo()
    assert session.state_dict() == s2
    session.undo()
    assert session.state_dict() == s1
    session.undo()
    assert session.state_dict() == s0                           # stale flags restored too
    assert session.undo() is None
    session.redo(), session.redo()
    assert session.state_dict() == s2
    # new edit clears the redo stack, but nothing leaves the log
    n = len(session.history.ops)
    session.set_setting("bkg_mode", "spectrum", reason="test")
    assert not session.history.can_redo() and session.redo() is None
    assert len(session.history.ops) == n + 1
    assert sum(o.undone for o in session.history.ops) == 3      # remove_peak, mass, min_sig
    session.undo()
    assert session.state_dict() == s2


def test_edit_rules(session):
    with pytest.raises(ValueError):
        session.remove_peak(0, reason="")                       # reason required
    with pytest.raises(ValueError):
        session.set_sample_field("mass_kg", -1.0)               # validated through SampleInfo
    with pytest.raises(KeyError):
        session.set_sample_field("colour", "red")
    session.status["reviewed"] = True
    op = session.set_setting("new_key", 1)
    assert op.before_exists is False and session.status["reviewed"] is False
    session.undo()
    assert "new_key" not in session.processing_settings and session.status["reviewed"] is True
    # recomputing results seals undo positions but keeps the log
    session.set_peak_field(0, "note", "x", reason="r")
    session.set_results([peak(10.0, 5.0)])
    assert not session.history.can_undo() and session.history.ops

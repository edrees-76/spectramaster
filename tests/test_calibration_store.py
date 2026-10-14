"""Versioned calibration store (Release D, D5): history kept, nothing overwritten."""
import json

import pytest

from spectramaster.lab.calibration import CalibrationRecord
from spectramaster.lab.calibration_store import CalibrationStore, CalibrationStoreError


def _rec(a=0.5, b=0.25):
    return CalibrationRecord(kind="energy", model="poly1_channel", params=[a, b], energy_range=[0, 2000],
                             detector_id="det-1", name="HPGe-1 energy")


def test_versions_are_appended_and_linked(tmp_path):
    st = CalibrationStore(tmp_path)
    v1 = st.save(_rec(), "initial calibration with Eu-152")
    assert v1.version == 1 and v1.supersedes is None and v1.lineage
    same = st.save(CalibrationRecord.from_dict(v1.to_dict()), "saved again")
    assert same.version == 1                                   # identical content: no new version
    edited = CalibrationRecord.from_dict(v1.to_dict())
    edited.params = [0.6, 0.25]
    v2 = st.save(edited, "recalibrated after drift")
    assert (v2.version, v2.supersedes, v2.lineage) == (2, v1.id, v1.lineage)
    assert v2.id != v1.id and v2.change_reason == "recalibrated after drift"
    hist = st.history(v1.lineage)
    assert [r.version for r in hist] == [1, 2] and hist[0].params == [0.5, 0.25]   # old version intact
    assert st.current(v1.lineage).id == v2.id
    assert st.find(v1.id).version == 1
    d = st.diff(v1.lineage, 1, 2)
    assert d["reason"] == "recalibrated after drift" and any("params" in c for c in d["changes"])


def test_reason_required_and_kind_fixed(tmp_path):
    st = CalibrationStore(tmp_path)
    with pytest.raises(CalibrationStoreError):
        st.save(_rec(), "  ")
    v1 = st.save(_rec(), "first")
    other = CalibrationRecord(kind="fwhm", model="poly1_channel", params=[1, 0.001], lineage=v1.lineage)
    with pytest.raises(CalibrationStoreError):
        st.save(other, "wrong kind")


def test_validation_is_an_event_and_new_versions_start_unvalidated(tmp_path):
    st = CalibrationStore(tmp_path)
    v1 = st.save(_rec(), "first")
    with pytest.raises(CalibrationStoreError):
        st.set_validation(v1.lineage, 1, "validated")           # how it was validated is required
    st.set_validation(v1.lineage, 1, "validated", "checked with independent Cs-137 and Co-60 lines", "lab")
    assert st.load(v1.lineage, 1).validation_status == "validated"
    assert st.load(v1.lineage, 1).integrity_ok()                # validating does not change the hash
    e = CalibrationRecord.from_dict(v1.to_dict())
    e.params = [0.7, 0.25]
    v2 = st.save(e, "new source")
    assert v2.validation_status == "unvalidated"
    assert st.current(v1.lineage).version == 2
    assert st.current(v1.lineage, validated_only=True).version == 1


def test_files_never_overwritten_and_tampering_detected(tmp_path):
    st = CalibrationStore(tmp_path)
    v1 = st.save(_rec(), "first")
    f = tmp_path / v1.lineage / "v001.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["params"] = [9.0, 0.25]                                   # edited outside the program
    f.write_text(json.dumps(d), encoding="utf-8")
    assert st.integrity_problems() and st.current(v1.lineage) is None
    with pytest.raises(CalibrationStoreError):
        st.load("../escape")


def test_efficiency_record_round_trip(tmp_path):
    from spectramaster.analysis.efficiency import EfficiencyCurve
    curve = EfficiencyCurve(model="loglog", order=1, params=[-3.0, -0.8], cov=[[1e-4, 0], [0, 1e-4]], e_min=50, e_max=2000,
                            name="Marinelli 1 L")
    st = CalibrationStore(tmp_path)
    v1 = st.save(CalibrationRecord.from_efficiency_curve(curve, detector_id="det-1", geometry_id="mar-1"), "first")
    back = st.load(v1.lineage).to_efficiency_curve()
    assert back.efficiency(661.7) == pytest.approx(curve.efficiency(661.7))

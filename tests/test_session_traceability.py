"""Session traceability fixes from the second external review (Codex M2, M3, M4)."""
import datetime as dt
import json

import pytest

from spectramaster import __version__
from spectramaster.analysis import activity as act
from spectramaster.analysis.coincidence import TABLE
from spectramaster.analysis.peaks import find_peaks
from spectramaster.lab import session as sess
from spectramaster.lab.common import file_sha256
from spectramaster.lab.workflow import report_record
from spectramaster.validation import scenarios
from spectramaster.validation.benchmark import _flat_curve
from spectramaster.validation.synthetic import HPGE


def test_reference_peak_date_survives_a_session_round_trip():
    syn, _truth, _loss = next(scenarios.reference_peak_spectra(HPGE, 1))
    spec = syn.spectrum
    spec.start_time = dt.datetime(2024, 3, 1, 10, 0)
    ref = {"energy": scenarios.REF_PULSER_KEV["HPGe"], "rate": scenarios.REF_PULSER_CPS, "rate_rel_unc": 0.01,
           "half_life_s": 30.0 * 365.25 * 86400, "ref_date": dt.datetime(2020, 1, 1)}
    curve = _flat_curve()
    q = act.compute_activities(spec, curve, act.ActivityOptions(nuclides=["Cs-137"], reference_peak=ref))
    back = act.QuantResults.from_dict(json.loads(json.dumps(sess.quant_to_dict(q))))
    assert back.options.reference_peak["ref_date"] == ref["ref_date"]
    again = act.compute_activities(spec, curve, back.options)          # was a TypeError (str date)
    assert again.reference_factor == pytest.approx(q.reference_factor)
    as_text = dict(ref, ref_date="2020-01-01T00:00:00")                 # options edited as JSON
    k, *_ = act.reference_correction(spec, find_peaks(spec), as_text, spec.live_time)
    assert k == pytest.approx(q.reference_factor)


def test_engine_version_is_separate_and_flags_old_results():
    assert sess.ENGINE_VERSION != "1.0.0"
    s = sess.AnalysisSession()
    s.set_results((), (), {"nuclides": []}, engine_version="1.0.0")
    assert any("engine 1.0.0" in r for r in s.is_stale_against())
    s.set_results((), (), {"nuclides": []})
    assert not s.is_stale_against()
    assert s.app_version == __version__ and s.engine_version == sess.ENGINE_VERSION


def test_blank_and_coincidence_table_are_fingerprinted(tmp_path):
    blank = tmp_path / "blank.spe"
    blank.write_bytes(b"blank spectrum bytes")
    s = sess.AnalysisSession()
    s.set_blank(blank, live_time=3600.0, reason="test")
    s.set_coincidence_table(reason="test")
    assert s.blank_ref["sha256"] == file_sha256(blank) and s.blank_ref["live_time"] == 3600.0
    assert s.coincidence_ref["sha256"] == file_sha256(TABLE)
    back = sess.AnalysisSession.from_dict(json.loads(json.dumps(s.to_dict())))
    assert back.blank_ref == s.blank_ref and back.coincidence_ref == s.coincidence_ref
    rec = report_record(back)
    assert rec["blank"]["sha256"] == s.blank_ref["sha256"]
    assert rec["coincidence_table"]["sha256"] == s.coincidence_ref["sha256"]
    s.undo()
    assert s.coincidence_ref is None
    s.set_blank(None, reason="no blank")
    assert s.blank_ref is None
    old = {k: v for k, v in s.to_dict().items() if k not in ("blank_ref", "coincidence_ref")}
    assert sess.AnalysisSession.from_dict(old).blank_ref is None          # older sessions still load

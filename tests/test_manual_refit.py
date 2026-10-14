"""Manual peak editing (Release B, increment B3): refit a region, add / remove a peak with a
refit, compare before and after, undo / redo, stale downstream results, persistence."""
from __future__ import annotations

import numpy as np
import pytest

from spectramaster.analysis import find_peaks, identify
from spectramaster.analysis.manual import compare_peaks, refit_region
from spectramaster.lab.session import AnalysisSession
from spectramaster.validation.synthetic import HPGE, NAI, Continuum, TruePeak, make_spectrum

CONT = Continuum(exp_amp=300, exp_scale_kev=400, flat=10)


def _doublet(sep_fwhm=1.0, ratio=3.0, seed=3, det=HPGE):
    fw = float(det.fwhm_kev(662.0))
    truth = [TruePeak(662.0, 1.0e5), TruePeak(662.0 + sep_fwhm * fw, 1.0e5 / ratio), TruePeak(1332.0, 5e4)]
    return make_spectrum(det, truth, CONT, seed=seed)


def _session(syn):
    s = AnalysisSession()
    pk = find_peaks(syn.spectrum)
    s.set_results(pk, identify(syn.spectrum, pk), spectrum=syn.spectrum)
    return s


# ------------------------------------------------------------------ analysis.manual
def test_refit_region_reproduces_the_automatic_singlet():
    syn = make_spectrum(HPGE, [TruePeak(662.0, 1.0e5)], CONT, seed=1)
    auto = next(p for p in find_peaks(syn.spectrum) if abs(p.energy - 662) < 2)
    fw = auto.fwhm
    rf = refit_region(syn.spectrum, int(auto.centroid - 2.2 * fw), int(auto.centroid + 2.2 * fw), [auto.centroid])
    assert rf.ok and len(rf.peaks) == 1
    p = rf.peaks[0]
    assert p.net_area == pytest.approx(auto.net_area, rel=0.01)
    assert p.centroid == pytest.approx(auto.centroid, abs=0.05)
    assert "manual fit" in p.note
    assert rf.options["counts_sha256"] and rf.group.residuals.shape == rf.group.data.shape


def test_fixed_centroid_and_fixed_width_are_honoured():
    syn = make_spectrum(HPGE, [TruePeak(662.0, 1.0e5)], CONT, seed=2)
    c = HPGE.channel(662.0)
    rf = refit_region(syn.spectrum, int(c - 8), int(c + 8), [c + 0.3], fix_centroids=[True], width=1.2)
    assert rf.peaks[0].centroid == pytest.approx(c + 0.3, abs=1e-9)
    assert rf.group.width_free is False


def test_weak_requested_component_is_kept_and_labelled():
    syn = make_spectrum(HPGE, [TruePeak(662.0, 1.0e5)], CONT, seed=4)
    c = HPGE.channel(662.0)
    rf = refit_region(syn.spectrum, int(c - 15), int(c + 15), [c, c + 9])
    assert len(rf.peaks) == 2
    weak = max(rf.peaks, key=lambda p: p.centroid)
    assert "below decision threshold" in weak.note


def test_bad_inputs_are_rejected():
    syn = make_spectrum(HPGE, [TruePeak(662.0, 1.0e5)], CONT, seed=4)
    c = HPGE.channel(662.0)
    with pytest.raises(ValueError):
        refit_region(syn.spectrum, int(c - 5), int(c + 5), [c + 20])
    with pytest.raises(ValueError):
        refit_region(syn.spectrum, int(c - 5), int(c + 5), [])


def test_compare_peaks_reports_changes():
    a = [{"centroid": 100.0, "fwhm": 2.0, "net_area": 1000.0, "net_area_unc": 40.0},
         {"centroid": 300.0, "fwhm": 2.0, "net_area": 500.0, "net_area_unc": 30.0}]
    b = [{"centroid": 100.2, "fwhm": 2.0, "net_area": 1100.0, "net_area_unc": 40.0},
         {"centroid": 400.0, "fwhm": 2.0, "net_area": 50.0, "net_area_unc": 10.0}]
    rows = {(r["status"], r["centroid_before"] or r["centroid_after"]) for r in compare_peaks(a, b)}
    assert rows == {("changed", 100.0), ("removed", 300.0), ("added", 400.0)}


# ------------------------------------------------------------------ session edits
def test_add_peak_and_refit_then_undo_redo():
    syn = _doublet(sep_fwhm=1.6, ratio=10.0, seed=7)
    s = _session(syn)
    before = [dict(p) for p in s.results["peaks"]]
    c2 = HPGE.channel(662.0 + 1.6 * float(HPGE.fwhm_kev(662.0)))
    # remove whatever the engine reported near the weak component, then add it by hand
    near = [i for i, p in enumerate(s.results["peaks"]) if abs(p["centroid"] - c2) < 2]
    for i in reversed(near):
        s.remove_peak_and_refit(syn.spectrum, i, reason="test: start without the weak component")
    n0 = len(s.results["peaks"])
    op, rf = s.add_peak_and_refit(syn.spectrum, c2, reason="shoulder visible in the residuals")
    assert op.kind == "replace_peaks" and op.details["centroids"]
    assert len(s.results["peaks"]) == n0 + 1
    assert any(abs(p["centroid"] - c2) < 1.0 for p in s.results["peaks"])
    assert s.status["results_stale"] and not s.status["reviewed"]
    rows = compare_peaks(op.before, op.after)
    assert any(r["status"] == "added" for r in rows)
    s.undo()
    assert len(s.results["peaks"]) == n0
    s.redo()
    assert len(s.results["peaks"]) == n0 + 1
    while s.undo():
        pass
    assert s.results["peaks"] == before
    assert s.status["results_stale"] is False


def test_remove_requires_reason_and_survives_save_load(tmp_path):
    syn = _doublet(sep_fwhm=2.0, ratio=1.0, seed=9)
    s = _session(syn)
    with pytest.raises(ValueError):
        s.remove_peak_and_refit(syn.spectrum, 0, reason=" ")
    i = next(k for k, p in enumerate(s.results["peaks"]) if abs(p["energy"] - 662) < 2)
    n = len(s.results["peaks"])
    op, _rf = s.remove_peak_and_refit(syn.spectrum, i, reason="judged a tail artefact")
    assert len(s.results["peaks"]) == n - 1
    path = s.save(tmp_path / "s.smsession")
    back = AnalysisSession.load(path)
    assert back.results["peaks"] == s.results["peaks"]
    assert back.history.ops[-1].kind == "replace_peaks" and back.history.ops[-1].reason == "judged a tail artefact"
    assert back.is_stale_against()
    back.undo()
    assert len(back.results["peaks"]) == n


def test_refit_refuses_a_different_spectrum():
    syn = _doublet(seed=11)
    s = _session(syn)
    other = _doublet(seed=12)
    c = HPGE.channel(662.0)
    with pytest.raises(ValueError):
        s.refit_region(other.spectrum, int(c - 10), int(c + 10), [c])


def test_nai_manual_refit_does_not_invent_separation():
    """Two components 0.5 FWHM apart in NaI: a manual two-peak fit is allowed but must be
    labelled as poorly separated, never presented as a clean result."""
    syn = _doublet(sep_fwhm=0.5, ratio=1.0, seed=13, det=NAI)
    c = NAI.channel(662.0)
    fw = float(NAI.fwhm_ch(662.0))
    rf = refit_region(syn.spectrum, int(c - 3 * fw), int(c + 3 * fw), [c - 0.3 * fw, c + 0.6 * fw])
    assert rf.ok
    assert any("poorly determined" in w for w in rf.group.warnings)

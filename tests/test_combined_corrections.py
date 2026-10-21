"""Corrections used together (docs/baseline/combined_corrections_protocol.md): reference peak with a
background, decision threshold with a blank and reference peaks, manual peak edits, and the inputs
snapshot of a threaded calculation."""
from __future__ import annotations

import math
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from spectramaster.analysis import activity as act
from test_activity import LIVE, SAMPLE_REF, cal_curve, make_spectrum  # noqa: F401
from test_reagent_blank import A_BLANK, A_SAMPLE, cs_counts

PULSER_KEV = 2500.0


def opts(ref=None, **kw):
    return act.ActivityOptions(nuclides=["Cs-137"], ref_date=SAMPLE_REF, reference_peak=ref, **kw)


# ------------------------------------------------------------------ CC.C1 reference peak + background
@pytest.mark.parametrize("mode", ["peak", "spectrum"])
def test_reference_peak_also_in_the_background(cal_curve, mode):
    _pts, curve = cal_curve
    n_ref = 50.0 * LIVE
    sample = make_spectrum([cs_counts(A_SAMPLE), (PULSER_KEV, n_ref)])
    bkg = make_spectrum([(PULSER_KEV, n_ref)], sid="background")
    ref = {"energy": PULSER_KEV, "rate": n_ref / LIVE, "rate_rel_unc": 0.01}
    q = act.compute_activities(sample, curve, opts(ref, bkg_mode=mode), background=bkg)
    assert q.reference_factor == pytest.approx(1.0, abs=0.01)
    assert q.nuclides[0].activity == pytest.approx(A_SAMPLE, rel=0.03)


# ------------------------------------------------------------------ CC.C2 / C3 decision threshold
N_REF = 120.0          # small reference peaks: about 10 % counting uncertainty


def _pair(ref):
    blank = make_spectrum([cs_counts(A_BLANK), (PULSER_KEV, N_REF)], sid="blank")
    sample = make_spectrum([cs_counts(A_BLANK * 1.02), (PULSER_KEV, N_REF)])
    return sample, blank


def test_threshold_contains_the_reference_term_under_the_null(cal_curve):
    _pts, curve = cal_curve
    ref = {"energy": PULSER_KEV, "rate": N_REF / LIVE, "rate_rel_unc": 0.0}
    sample, blank_spec = _pair(ref)
    o = opts(ref)
    blank = act.compute_activities(blank_spec, curve, o)
    q = act.compute_activities(sample, curve, o, blank=blank)
    k = q.nuclides[0].key_line
    ab = k.blank_activity
    term = ab * math.sqrt(q.reference_u_count_rel ** 2 + blank.reference_u_count_rel ** 2
                          + (q.reference_u_rate_rel - blank.reference_u_rate_rel) ** 2)
    assert q.reference_u_count_rel > 0.05 and blank.reference_u_count_rel > 0.05
    assert k.decision_threshold >= 1.645 * term


def test_threshold_unchanged_without_blank_or_without_reference(cal_curve):
    _pts, curve = cal_curve
    ref = {"energy": PULSER_KEV, "rate": N_REF / LIVE, "rate_rel_unc": 0.0}
    sample, blank_spec = _pair(ref)
    # no blank: the term is zero; equal to the threshold of the uncorrected result times K
    q_ref = act.compute_activities(sample, curve, opts(ref))
    q_raw = act.compute_activities(sample, curve, opts())
    assert q_ref.nuclides[0].key_line.decision_threshold == pytest.approx(
        q_raw.nuclides[0].key_line.decision_threshold * q_ref.reference_factor, rel=1e-9)
    # blank without a reference correction: compared with the previous engine in the protocol results


# ------------------------------------------------------------------ CC.C4 / C5 manual peaks
def test_given_peaks_used_without_background_and_noted_with_one(cal_curve):
    from spectramaster.analysis.peaks import find_peaks
    _pts, curve = cal_curve
    sample = make_spectrum([cs_counts(A_SAMPLE)])
    peaks = find_peaks(sample)
    edited = [p for p in peaks if abs(p.energy - 661.66) > 2.0]          # Cs-137 removed by hand
    q = act.compute_activities(sample, curve, opts(), peaks=edited)
    assert not q.nuclides[0].key_line.peak_found and "no peak" in q.nuclides[0].key_line.note
    bkg = make_spectrum([], sid="background")
    plain = act.compute_activities(sample, curve, opts(), background=bkg)
    given = act.compute_activities(sample, curve, opts(), background=bkg, peaks=edited)
    assert any("peak list given was not used" in n for n in given.notes)
    assert not any("peak list given" in n for n in plain.notes)
    assert given.nuclides[0].activity == plain.nuclides[0].activity


# ------------------------------------------------------------------ GUI: manual edits and snapshot
pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


@pytest.fixture()
def window(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from spectramaster.gui import i18n
    from spectramaster.gui.app import MainWindow
    from spectramaster.gui.settings import Settings
    monkeypatch.setenv("SPECTRAMASTER_EFF_DIR", str(tmp_path / "curves"))
    monkeypatch.setenv("SPECTRAMASTER_DETECTOR_DIR", str(tmp_path / "detectors"))
    i18n.set_language("en")
    w = MainWindow(Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)))
    w.errors, w.infos = [], []
    w.show_error = w.errors.append
    w.show_info = w.infos.append
    yield w
    w.session_ctl.ask_save_changes = lambda: "discard"
    w.close()
    w.deleteLater()
    QApplication.processEvents()


def _dialog(window, tmp_path, cal_curve):
    from test_gui_session_io import analyse, spectrum_file
    from spectramaster.gui.quant_panel import ActivityDialog
    assert window.load_file(spectrum_file(tmp_path / "data"))
    analyse(window)
    _pts, curve = cal_curve
    path = tmp_path / "curves" / "c.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    curve.save(path)
    ad = ActivityDialog(window, window.current_spectrum(), getattr(window, "settings", None))
    ad.set_curve_path(path)
    ad.nuc_edit.setText("Cs-137, K-40")
    return ad


def test_dialog_uses_manually_edited_peaks(window, tmp_path, cal_curve):
    ad = _dialog(window, tmp_path, cal_curve)
    s = window.session
    assert ad.inputs()["peaks"] is None                      # no manual edit: the engine searches
    before = {r.nuclide: r.activity for r in ad.calculate().nuclides}
    assert before["Cs-137"] is not None
    i = next(j for j, p in enumerate(s.results["peaks"]) if abs(p["energy"] - 661.66) < 2.0)
    s.remove_peak(i, reason="test: not a real peak")
    assert s.status["peaks_edited"]
    res = ad.calculate()
    cs = next(r for r in res.nuclides if r.nuclide == "Cs-137")
    assert cs.activity is None and "manually edited peaks" in " ".join(res.notes)
    assert s.status["peaks_edited"]                          # kept after the activity calculation
    ad.close()


def test_blank_changed_during_a_threaded_calculation(window, tmp_path, cal_curve):
    from PySide6.QtWidgets import QApplication
    from test_activity import write_spec
    ad = _dialog(window, tmp_path, cal_curve)
    b1 = write_spec(make_spectrum([cs_counts(A_BLANK)], sid="b1"), tmp_path / "b1.json")
    b2 = write_spec(make_spectrum([cs_counts(2 * A_BLANK)], sid="b2"), tmp_path / "b2.json")
    assert ad.load_blank(str(b1))
    assert ad.calculate(threaded=True) is None
    assert ad.busy
    assert ad.load_blank(str(b2))                            # changed while the worker runs
    end = time.monotonic() + 120
    while ad.busy and time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.01)
    QApplication.processEvents()
    assert not ad.busy
    assert ad.results.blank.endswith("b1.json")
    assert window.session.blank_ref["path"].endswith("b1.json")
    ad.close()

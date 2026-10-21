"""Implausible FWHM model, finding F1 (docs/baseline/fwhm_plausibility_protocol.md)."""
from __future__ import annotations

import numpy as np
import pytest

from spectramaster.analysis import peaks as P
from spectramaster.analysis.activity import ActivityOptions, compute_activities
from spectramaster.validation import primary as pr
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE, NAI


def _coeffs(det, k):
    ch = np.arange(det.n_channels, dtype=float)
    e = det.energy(ch)
    fw = k * np.sqrt(det.fwhm_a + det.fwhm_b * e + det.fwhm_c * e * e)
    return [float(c) for c in np.polyfit(ch, fw, 2)[::-1]]


def _spectrum(det, k=None):
    syn = next(iter(scenarios.isolated_strong(det, 1)))
    if k is not None:
        syn.spectrum.fwhm_coeffs = _coeffs(det, k)
    return syn


@pytest.mark.parametrize("det,k", [(HPGE, 4.0), (NAI, 4.0), (NAI, 0.25)])
def test_implausible_calibration_is_replaced_with_a_note(det, k):
    syn = _spectrum(det, k)
    rep = P.FitReport()
    found = P.find_peaks(syn.spectrum, report=rep)
    assert rep.fwhm_source.startswith(P.IMPLAUSIBLE_PREFIX) and "fwhm calibration" in rep.fwhm_source
    assert any("does not match the peak widths" in n for n in rep.notes)
    assert all(any(abs(p.centroid - t.centroid) < 0.5 * t.fwhm_ch for p in found) for t in syn.truth)


@pytest.mark.parametrize("det", [HPGE, NAI])
@pytest.mark.parametrize("k", [0.7, 1.0, 1.4])
def test_plausible_calibration_is_kept(det, k):
    syn = _spectrum(det, k)
    y = np.asarray(syn.spectrum.counts, dtype=float)
    f, src = P.checked_fwhm_model(syn.spectrum, y)
    assert src == "fwhm calibration"
    assert np.array_equal(f, P.fwhm_model(syn.spectrum, y)[0])


def test_user_width_is_never_checked(monkeypatch):
    syn = _spectrum(HPGE, 4.0)
    monkeypatch.setattr(P, "checked_fwhm_model", lambda *a, **k: pytest.fail("checked"))
    rep = P.FitReport()
    P.find_peaks(syn.spectrum, fwhm=3.0, report=rep)
    assert rep.fwhm_source == "user"


def test_activity_windows_use_the_replacement():
    syn = _spectrum(HPGE, 4.0)
    res = compute_activities(syn.spectrum, pr._flat_curve(), ActivityOptions(nuclides=["Cs-137"]))
    assert any("does not match the peak widths" in n for n in res.notes)

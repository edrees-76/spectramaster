"""Energy-calibration review (Release B, increment B1): weighted fit, order selection, outlier
exclusion, validation report, drift check, and the data-driven width model it relies on."""
from __future__ import annotations

import math

import numpy as np
import pytest

from spectramaster.tools.calibrate import (CalibrationPoint, calibrate_from_source, check_drift,
                                           f_test_pvalue, fit_points)
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE, HPGE_NL, NAI, NAI_4K


def _max_err_fwhm(det, coeffs, e_lo, e_hi):
    ch = np.linspace(det.channel(e_lo), det.channel(e_hi), 200)
    et = det.energy(ch)
    return float(np.max(np.abs(np.polynomial.polynomial.polyval(ch, coeffs) - et) / det.fwhm_kev(et)))


# ------------------------------------------------------------------ statistics
def test_f_test_pvalue_reference_values():
    # F(1, 10) critical value at 5 % is 4.965; F(2, 20) at 1 % is 5.849
    assert f_test_pvalue(4.965, 1, 10) == pytest.approx(0.05, abs=5e-4)
    assert f_test_pvalue(5.849, 2, 20) == pytest.approx(0.01, abs=2e-4)
    assert f_test_pvalue(0.0, 1, 5) == 1.0


# ------------------------------------------------------------------ fit_points
def _points(coeffs, chans, sig=0.02, seed=0):
    rng = np.random.default_rng(seed)
    # energies from the true calibration, centroids perturbed by their stated uncertainty
    return [CalibrationPoint("X", float(np.polynomial.polynomial.polyval(c, coeffs)), c + rng.normal(0, sig), sig,
                             3.0, 50.0) for c in chans]


def test_linear_truth_keeps_order_one_and_quadratic_truth_gets_order_two():
    chans = np.linspace(200, 3800, 11)
    fit, p, _ = fit_points(_points([1.0, 0.5], chans))
    assert fit.order == 1 and p is not None and p > 0.05
    fit2, p2, _ = fit_points(_points([1.0, 0.5, 2e-7], chans))
    assert fit2.order == 2 and p2 is not None


def test_outlier_is_excluded_with_a_reason():
    pts = _points([1.0, 0.5], np.linspace(200, 3800, 8))
    pts[3].channel += 3.0            # wrong peak: 1.5 keV off, 150 sigma
    fit, _, _ = fit_points(pts)
    assert not pts[3].used and "sigma" in pts[3].reason
    assert all(p.used for k, p in enumerate(pts) if k != 3)
    assert fit.evaluate(2000) == pytest.approx(1001.0, abs=0.01)
    assert all(p.loo_residual_kev is not None for p in pts if p.used)


# ------------------------------------------------------------------ calibrate_from_source
def test_nonlinear_hpge_eu152_recovered_and_validated():
    syn = next(scenarios.calibration_source(HPGE_NL, "Eu-152", 1, category="unit"))
    sc = calibrate_from_source(syn.spectrum, "Eu-152")
    v = sc.validation
    assert v.ok, v.report()
    es = [m.energy for m in sc.matches]
    assert _max_err_fwhm(HPGE_NL, sc.coeffs, min(es), max(es)) <= 0.1
    assert v.monotonic and v.range_kev[0] < 130 and v.range_kev[1] > 1400
    assert v.detector_type == "HPGe" and 0.8 < v.fwhm_ratio_to_type < 1.25
    assert "Validation: OK" in sc.report()


@pytest.mark.parametrize("det", [NAI, NAI_4K], ids=["NaI-1024", "NaI-4096"])
def test_nai_source_calibration_recovered(det):
    syn = next(scenarios.calibration_source(det, "Am-241,Cs-137,Co-60", 1, category="unit"))
    sc = calibrate_from_source(syn.spectrum, "Am-241,Cs-137,Co-60")
    assert sc.validation.ok, sc.validation.report()
    es = [m.energy for m in sc.matches]
    assert len(es) >= 3
    assert _max_err_fwhm(det, sc.coeffs, min(es), max(es)) <= 0.1


@pytest.mark.parametrize("det", [HPGE, NAI], ids=["HPGe", "NaI"])
def test_wrong_source_is_flagged(det):
    syn = next(scenarios.calibration_source(det, "Co-60,Cs-137", 1, category="unit"))
    try:
        sc = calibrate_from_source(syn.spectrum, "Eu-152")
    except ValueError:
        return
    assert not sc.validation.ok and sc.validation.errors


def test_extrapolation_is_reported():
    syn = next(scenarios.calibration_source(HPGE, "Cs-137", 1, category="unit", with_background=True))
    sc = calibrate_from_source(syn.spectrum, "Cs-137,K-40")
    assert sc.validation.extrapolated_fraction > 0.2
    assert any("extrapolated" in w for w in sc.validation.warnings)


# ------------------------------------------------------------------ drift
def test_drift_detected_and_correction_proposed_not_applied():
    syn = next(scenarios.calibration_drift(HPGE, 0.003, 1))
    before = list(syn.spectrum.energy_coeffs)
    r = check_drift(syn.spectrum)
    assert r.detected and r.max_shift_fwhm > 1.0
    assert syn.spectrum.energy_coeffs == before            # a proposal only
    assert _max_err_fwhm(HPGE, r.proposed_coeffs, 300, 2000) <= 0.1
    assert "DRIFT DETECTED" in r.report()
    assert "{" not in r.message and f"{r.max_shift_kev:.2f} keV" in r.message


@pytest.mark.parametrize("det", [HPGE, NAI], ids=["HPGe", "NaI"])
def test_no_drift_no_alarm(det):
    syn = next(scenarios.calibration_drift(det, 0.0, 1))
    assert not check_drift(syn.spectrum).detected


def test_nai_blended_background_lines_are_not_used_as_references():
    syn = next(scenarios.calibration_drift(NAI, 0.01, 1))
    r = check_drift(syn.spectrum)
    assert r.detected
    used = {e for _n, e, _m, _s in r.points}
    assert 238.632 not in used and 609.312 not in used        # unresolved blends in NaI
    assert any("unresolved" in why for _n, _e, why in r.excluded)


def test_drift_check_needs_a_calibration():
    syn = next(scenarios.calibration_drift(HPGE, 0.0, 1))
    syn.spectrum.energy_coeffs = []
    with pytest.raises(ValueError):
        check_drift(syn.spectrum)


# ------------------------------------------------------------------ width model
def test_uncalibrated_width_estimate_follows_nai_energy_dependence():
    """The data-driven FWHM model of uncalibrated spectra used to be a constant (or dropped
    the energy dependence through a median filter), which broke peak search on NaI with
    4096 channels (widths change x4 across the spectrum)."""
    from spectramaster.analysis.peaks import _estimate_fwhm_from_data
    syn = next(scenarios.calibration_source(NAI_4K, "Am-241,Cs-137,Co-60", 1, category="unit"))
    f = _estimate_fwhm_from_data(np.asarray(syn.spectrum.counts, dtype=float))
    for e in (122.0, 662.0, 1332.0):
        c = int(round(NAI_4K.channel(e)))
        assert f[c] == pytest.approx(float(NAI_4K.fwhm_ch(e)), rel=0.25)

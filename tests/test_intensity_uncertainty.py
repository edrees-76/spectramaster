"""Emission-probability uncertainties (Release D, D5): library values (IAEA ENSDF), their use
in the efficiency calibration and in the activity budget, and the DDEP cross-check."""
from __future__ import annotations

import math
from datetime import datetime

import pytest

from spectramaster.analysis import efficiency as eff
from spectramaster.analysis.activity import ActivityOptions, compute_activities
from spectramaster.analysis.library import intensity_rel_unc, load_library
from spectramaster.validation.benchmark import _flat_curve
from spectramaster.validation.synthetic import HPGE, Continuum, TruePeak, make_spectrum


def test_library_lines_carry_ensdf_uncertainties():
    lib = load_library()
    cs = next(l for l in lib["Cs-137"].lines if abs(l.energy - 661.657) < 0.01)
    assert cs.intensity == pytest.approx(85.1) and cs.intensity_unc == pytest.approx(0.2)
    assert intensity_rel_unc("Cs-137", 661.657) == pytest.approx(0.2 / 85.1)
    assert intensity_rel_unc("Cs-137", 600.0) is None                 # no line there
    with_u = sum(l.intensity_unc is not None for nd in lib.values() for l in nd.lines)
    assert with_u / sum(len(nd.lines) for nd in lib.values()) > 0.9


def test_certificate_lines_and_efficiency_points_use_them():
    cert = eff.certificate_lines([eff.CertNuclide("Eu-152", 1000.0, 15.0, datetime(2026, 1, 1))])
    l344 = next(c for c in cert if abs(c.energy - 344.279) < 0.01)
    assert l344.intensity_unc == pytest.approx(0.002)                  # 26.59 (20) %
    own = eff.certificate_lines([eff.CertNuclide("Eu-152", 1000.0, 15.0, datetime(2026, 1, 1),
                                                 lines=[(344.279, 0.2659)])])
    assert own[0].intensity_unc == 0.0                                 # certificate data: nothing added


def test_activity_budget_includes_the_line_uncertainty():
    syn = make_spectrum(HPGE, [TruePeak(661.657, 5e4)], Continuum(300, 400, 10), 3)
    syn.spectrum.start_time = datetime(2026, 5, 10, 8, 0)
    q = compute_activities(syn.spectrum, _flat_curve(), ActivityOptions(nuclides=["Cs-137"]))
    r = q.nuclides[0]
    assert r.lines[0].int_rel_unc == pytest.approx(0.2 / 85.1)
    assert r.budget["intensity"] == pytest.approx(100 * 0.2 / 85.1, rel=1e-6)
    parts = [r.budget[k] / 100 * r.activity for k in ("counting", "efficiency", "intensity", "attenuation")]
    assert r.u == pytest.approx(math.sqrt(sum(p * p for p in parts)))


def test_ddep_cross_check_when_available():
    from spectramaster.validation.ddep_check import compare, ddep_folder
    folder = ddep_folder()
    if folder is None:
        pytest.skip("LNHB/DDEP LARA files not available (SPECTRAMASTER_DDEP_DIR)")
    r = compare(folder)
    assert r["lines"] >= 100
    assert r["within_3u"] >= 0.9           # measured 2026-10-15: 97.2 % of 363 lines


def test_heavy_element_k_beta_lines_are_resolved():
    # ENSDF's single K-beta line (Th 106.89 keV) split into K'beta1 / K'beta2 with DDEP constants
    lib = load_library()
    u235 = [l for l in lib["U-235"].lines if l.kind == "x" and l.energy > 100]
    assert [round(l.energy, 3) for l in u235] == [105.554]            # K'beta2 (0.7 %) below the 1 % cut
    assert u235[0].intensity == pytest.approx(2.7 * 0.749, rel=1e-3)
    np239 = [round(l.energy, 2) for l in lib["Np-239"].lines if l.kind == "x" and l.energy > 110]
    assert np239 == [117.13, 121.02]
    assert not any(abs(l.energy - 106.894) < 0.01 for nd in lib.values() for l in nd.lines if l.kind == "x")

"""Fit-inspection report (Release B, increment B2): components, background, residuals and
warnings for every fitted region; discarded components stay visible with a reason."""
from __future__ import annotations

import numpy as np
import pytest

from spectramaster.analysis import FitReport, find_peaks, inspect_fit
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE, NAI, Continuum, TruePeak, make_spectrum


def _key(peaks):
    return [(p.centroid, p.net_area, p.net_area_unc, p.fwhm, p.note) for p in peaks]


@pytest.mark.parametrize("det", [HPGE, NAI], ids=["HPGe", "NaI"])
def test_report_does_not_change_results(det):
    for syn in scenarios.identification(det, 1):
        if syn.meta["drift"] != 0:
            continue
        rep = FitReport()
        assert _key(find_peaks(syn.spectrum)) == _key(find_peaks(syn.spectrum, report=rep))
        assert rep.groups and rep.fwhm_source


def test_components_background_and_residuals_add_up():
    syn = next(scenarios.isolated_strong(HPGE, 1))
    peaks, rep = inspect_fit(syn.spectrum)
    kept = [c for g in rep.groups for c in g.components if c.kept]
    assert sorted(c.centroid for c in kept) == pytest.approx(sorted(p.centroid for p in peaks))
    for g in rep.groups:
        model = g.background + sum(g.component_curve(j) for j in range(len(g.components)))
        assert np.allclose(model, g.total)
        assert len(g.data) == len(g.channels) == len(g.residuals)
    big = rep.group_at(peaks[2].centroid)
    assert big is not None and big.chi2_reduced < 3 and not big.warnings
    assert np.sum(big.data - big.background) == pytest.approx(sum(c.area for c in big.components), rel=0.02)


@pytest.mark.parametrize("det", [HPGE, NAI], ids=["HPGe", "NaI"])
def test_every_discarded_component_has_a_reason(det):
    """Nothing the engine fitted disappears silently (baseline report, open item of P1)."""
    n_disc = 0
    for syn in scenarios.compton_edge(det, 6):
        _peaks, rep = inspect_fit(syn.spectrum)
        for _g, c in rep.discarded():
            n_disc += 1
            assert c.reason
    assert n_disc > 0


def test_unresolved_doublet_flagged_as_poorly_separated():
    fw = float(HPGE.fwhm_kev(662.0))
    syn = make_spectrum(HPGE, [TruePeak(662.0, 1.0e5), TruePeak(662.0 + 0.9 * fw, 1.0e5)],
                        Continuum(exp_amp=300, exp_scale_kev=400, flat=10), seed=11)
    peaks, rep = inspect_fit(syn.spectrum)
    g = rep.group_at(HPGE.channel(662.0))
    assert g is not None
    if sum(c.kept for c in g.components) >= 2:
        assert any("poorly determined" in w for w in g.warnings)
    else:
        assert g.warnings          # a single over-wide fit must not look clean

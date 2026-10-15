"""Compton-edge continuum step (Release C, increment C2): HPGe only, kept when it improves the
fit, reported in the fit inspection; NaI spectra are not changed by it."""
from __future__ import annotations

import pytest

from spectramaster.analysis import find_peaks
from spectramaster.analysis.peaks import FitReport, compton_edge_kev
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE, NAI


def test_compton_edge_energy():
    assert compton_edge_kev(661.657) == pytest.approx(477.3, abs=0.2)
    assert compton_edge_kev(1332.492) == pytest.approx(1118.1, abs=0.2)


def test_hpge_edge_is_not_reported_as_a_peak_and_the_step_is_shown():
    spurious, steps = 0, 0
    for syn in scenarios.compton_edge(HPGE, 6):
        rep = FitReport()
        peaks = find_peaks(syn.spectrum, report=rep)
        ce = HPGE.channel(syn.meta["edge_kev"])
        fw = float(HPGE.fwhm_ch(syn.meta["edge_kev"]))
        truth = [t.centroid for t in syn.truth]
        spurious += sum(1 for p in peaks if abs(p.centroid - ce) < 3 * fw
                        and not any(abs(p.centroid - t) < fw for t in truth))
        steps += any("Compton edge of the 1332 keV line" in w for g in rep.groups for w in g.warnings)
    assert spurious == 0
    assert steps == 6


def test_peak_two_fwhm_below_hpge_edge_keeps_its_area():
    for syn in scenarios.compton_edge(HPGE, 12):
        if syn.meta["offset"] != -2.0:
            continue
        t = next(p for p in syn.truth if p.tag.startswith("edge"))
        p = min(find_peaks(syn.spectrum), key=lambda p: abs(p.centroid - t.centroid))
        assert abs(p.centroid - t.centroid) < 1.0
        assert abs(p.net_area - t.area) < 3 * p.net_area_unc


def test_nai_has_no_edge_model():
    syn = next(scenarios.compton_edge(NAI, 1))
    rep = FitReport()
    find_peaks(syn.spectrum, report=rep)
    assert not any("Compton edge of the" in w for g in rep.groups for w in g.warnings)

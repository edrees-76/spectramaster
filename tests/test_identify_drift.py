"""Identification under gain drift (Release E, E2): the drift check runs first, peak energies
are corrected for the identification only, and the result says so."""
from __future__ import annotations

from spectramaster.analysis import find_peaks, identify
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE


def _cases(drift):
    return [s for s in scenarios.identification(HPGE, 1) if s.meta["drift"] == drift]


def test_drifted_hpge_spectrum_is_identified_and_the_correction_reported():
    syn = _cases(0.003)[0]
    before = list(syn.spectrum.energy_coeffs)
    res = identify(syn.spectrum, find_peaks(syn.spectrum))
    names = {m.nuclide for m in res}
    assert set(syn.meta["present"]) & names, (syn.meta["present"], names)
    assert all("calibration drift detected" in m.note for m in res)
    assert syn.spectrum.energy_coeffs == before            # the stored calibration is not changed
    off = identify(syn.spectrum, find_peaks(syn.spectrum), correct_drift=False)
    assert len(set(syn.meta["present"]) & {m.nuclide for m in off}) < len(set(syn.meta["present"]) & names)


def test_no_drift_no_correction_note():
    syn = _cases(0.0)[0]
    assert not any("drift" in m.note for m in identify(syn.spectrum, find_peaks(syn.spectrum)))

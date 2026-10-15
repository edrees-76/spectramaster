"""Application libraries (Release E, E3): candidates restricted by the library's categories."""
from __future__ import annotations

import pytest

from spectramaster.analysis import find_peaks, identify
from spectramaster.analysis.library import APPLICATIONS, application_library, load_library
from spectramaster.validation.synthetic import HPGE, Continuum, TruePeak, make_spectrum


def test_libraries_follow_the_categories():
    lib = load_library()
    env = application_library(lib, "environmental")
    assert {"Cs-137", "K-40", "Ra-226", "Be-7", "I-131", "Co-60", "Am-241"} <= set(env)
    assert not {"Tc-99m", "Se-75", "Ir-192", "Pu-239", "Gd-153"} & set(env)
    sg = application_library(lib, "safeguards")
    assert {"Pu-239", "U-235", "Am-241", "Np-237"} <= set(sg) and "Cs-137" not in sg
    assert application_library(lib, "all") is lib
    assert set(APPLICATIONS) >= {"all", "environmental", "calibration", "safeguards", "medical"}
    with pytest.raises(ValueError):
        application_library(lib, "everything")


def test_identification_only_reports_nuclides_of_the_chosen_library():
    syn = make_spectrum(HPGE, [TruePeak(661.657, 2e4), TruePeak(1460.8, 5e3), TruePeak(136.0, 3e3)],
                        Continuum(300, 400, 10), 5)
    pk = find_peaks(syn.spectrum)
    env = {m.nuclide for m in identify(syn.spectrum, pk, application="environmental")}
    assert "Cs-137" in env and "K-40" in env
    assert env <= set(application_library(load_library(), "environmental"))

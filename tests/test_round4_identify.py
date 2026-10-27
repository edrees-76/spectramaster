"""Round-4 review, identification findings (docs/baseline/round4_identify_protocol.md)."""
import copy
import importlib
from datetime import timedelta

import pytest

from spectramaster.analysis import find_peaks
from spectramaster.analysis.library import application_library, load_library
from spectramaster.validation import round4_identify as r4

idm = importlib.import_module("spectramaster.analysis.identify")


def test_fwhm_calibration_at_the_absolute_channel():
    assert r4._codex_fwhm() == pytest.approx(3.0, rel=1e-12)


def test_cropped_spectrum_has_the_same_resolution_model():
    cr = r4._crop_case()
    assert cr["fwhm_crop"] == pytest.approx(cr["fwhm_full"], rel=1e-9)


def test_decayed_nuclides_spare_series_and_supported_daughters():
    lib = load_library(None)
    d3 = idm.decayed_nuclides(lib, 3 * 86400.0)
    assert "Mn-56" in d3 and d3["Mn-56"] > 10
    assert "Tc-99m" not in d3 and "Mo-99" not in d3          # Mo-99 (1.1 half-lives) supports Tc-99m
    d30 = idm.decayed_nuclides(lib, 30 * 86400.0)
    assert {"Mo-99", "Tc-99m"} <= set(d30)
    assert not any(lib[n].series for n in d30)               # Pb-214, Bi-214 ... never
    assert idm.decayed_nuclides(lib, 0.0) == {}


def test_medical_nuclides_common_only_with_the_medical_library():
    pri = r4._priors()
    assert pri["all"]["Mo-99"] == pytest.approx(0.8)
    assert pri["environmental"]["Mo-99"] == pytest.approx(0.8)
    assert pri["medical"]["Mo-99"] == pytest.approx(1.0)
    assert pri["all"]["I-131"] == pri["all"]["Cs-137"] == pytest.approx(1.0)


@pytest.fixture(scope="module")
def sampling():
    s = r4._sampling_spectrum()
    return s, find_peaks(s)


def test_sampling_date_after_the_start_is_refused(sampling):
    s, pk = sampling
    with pytest.raises(ValueError, match="after the start"):
        idm.identify(s, copy.deepcopy(pk), sampled=s.start_time + timedelta(hours=1))


def test_decayed_nuclide_penalised_and_noted(sampling):
    s, pk = sampling
    base = {m.nuclide: m for m in idm.identify(s, copy.deepcopy(pk))}
    aged = {m.nuclide: m for m in idm.identify(s, copy.deepcopy(pk), sampled=s.start_time - timedelta(days=3))}
    assert aged["Tc-99m"].confidence == base["Tc-99m"].confidence
    mn = aged.get("Mn-56")
    assert mn is None or (mn.confidence <= 0.5 * base["Mn-56"].confidence and "half-lives since sampling" in mn.note)
    hour = {m.nuclide: (m.confidence, m.note) for m in
            idm.identify(s, copy.deepcopy(pk), sampled=s.start_time - timedelta(hours=1))}
    assert hour == {n: (m.confidence, m.note) for n, m in base.items()}


def test_single_line_note():
    w = r4._sampling_spectrum(mn56_area=150.0, with_mo=False, seed=r4.SEED + 1, mn56_only_846=True)
    res = {m.nuclide: m.note for m in idm.identify(w, find_peaks(w))}
    assert "one line matched" in res["Ba-133"]
    assert "one line matched" not in res["Cs-137"] and "one line matched" not in res["K-40"]


def test_cli_sampled_option(tmp_path, capsys):
    from spectramaster import cli
    assert cli.main(["identify", str(tmp_path / "none.chn"), "--sampled", "yesterday"]) == 2


def test_application_library_unchanged_by_the_prior():
    lib = load_library(None)
    assert "Mo-99" in application_library(lib, "environmental")

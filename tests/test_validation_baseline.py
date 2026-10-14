"""Tests of the validation harness itself (spectramaster/validation).

These check the *measuring instrument*: the synthetic generator conserves the declared truth,
spectra are reproducible from their seeds, matching and acceptance evaluation behave as
documented.  They do not require the engine to meet the acceptance limits; the baseline
report records which limits pass or fail.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from spectramaster.validation import acceptance, benchmark, reference, scenarios
from spectramaster.validation.synthetic import (HPGE, NAI, Continuum, TruePeak, area_for_snr,
                                                compton_edge_kev, continuum_counts, make_spectrum,
                                                window_background)


@pytest.mark.parametrize("det", [HPGE, NAI])
@pytest.mark.parametrize("tail", [0.0, 0.04])
def test_peak_area_and_centroid_conserved(det, tail):
    syn = make_spectrum(det, [TruePeak(662.0, 1.0e5, tail_frac=tail)], Continuum(), seed=1)
    peak = syn.expected - syn.continuum
    assert peak.sum() == pytest.approx(1.0e5, rel=1e-6)
    t = syn.truth[0]
    assert t.centroid == pytest.approx(662.0 / det.gain_kev)
    ch = np.arange(det.n_channels)
    mean = float((peak * ch).sum() / peak.sum())
    if tail == 0:
        assert mean == pytest.approx(t.centroid, abs=1e-3)
    else:                       # a low-energy tail pulls the mean below the Gaussian centroid
        assert mean < t.centroid


def test_gaussian_fwhm_matches_spec():
    syn = make_spectrum(HPGE, [TruePeak(1332.0, 1.0e6)], Continuum(), seed=1)
    y = syn.expected
    c = int(round(syn.truth[0].centroid))
    var = float(((np.arange(len(y)) - syn.truth[0].centroid) ** 2 * y)[c - 30:c + 31].sum() / y[c - 30:c + 31].sum())
    # channel integration adds 1/12 channel^2 to the variance
    fwhm = math.sqrt(var - 1.0 / 12.0) * 2.0 * math.sqrt(2.0 * math.log(2.0))
    assert fwhm == pytest.approx(float(HPGE.fwhm_ch(1332.0)), rel=2e-3)


def test_seed_reproducibility_and_independence():
    a = list(scenarios.isolated_weak(HPGE, 2))
    b = list(scenarios.isolated_weak(HPGE, 2))
    assert a[0].spectrum.counts == b[0].spectrum.counts
    assert a[0].spectrum.counts != a[1].spectrum.counts
    assert scenarios.seed_of(HPGE, "x", 0) != scenarios.seed_of(NAI, "x", 0)


def test_poisson_statistics_of_generated_counts():
    cont = Continuum(flat=400.0)
    syn = make_spectrum(HPGE, [], cont, seed=3)
    y = np.asarray(syn.spectrum.counts)
    assert y.mean() == pytest.approx(400.0, rel=0.01)
    assert y.var() == pytest.approx(400.0, rel=0.08)


def test_snr_definition():
    cont = scenarios.base_continuum(HPGE)
    cy = continuum_counts(HPGE, cont)
    a = area_for_snr(HPGE, cy, 700.0, 5.0)
    assert a / math.sqrt(window_background(HPGE, cy, 700.0)) == pytest.approx(5.0)


def test_compton_edge_position():
    assert compton_edge_kev(661.657) == pytest.approx(477.3, abs=0.2)
    assert compton_edge_kev(1332.0) == pytest.approx(1117.6, abs=0.1)   # 1332*2664/(511+2664)


def test_gain_error_only_changes_reported_calibration():
    p = [TruePeak(662.0, 1e4)]
    a = make_spectrum(HPGE, p, Continuum(flat=5), seed=9)
    b = make_spectrum(HPGE, p, Continuum(flat=5), seed=9, gain_error=0.003)
    assert a.spectrum.counts == b.spectrum.counts
    assert b.spectrum.energy_coeffs[1] == pytest.approx(HPGE.gain_kev * 1.003)


def test_matching_is_unique_and_nearest():
    syn = make_spectrum(HPGE, [TruePeak(662.0, 1e4), TruePeak(700.0, 1e4)], Continuum(), seed=1)

    class P:
        def __init__(self, c):
            self.centroid = c
    c0, c1 = syn.truth[0].centroid, syn.truth[1].centroid
    peaks = [P(c0 + 0.5), P(c0 - 0.2), P(c1 + 50)]
    m, un = benchmark.match(syn, peaks)
    assert m == {0: 1}
    assert sorted(un) == [0, 2]


def test_acceptance_evaluate_and_unique_ids():
    ids = [c.id for c in acceptance.CRITERIA]
    assert len(ids) == len(set(ids))
    cr = acceptance.Criterion("x", "any", "c", "m", "in", (0.6, 0.76), "")
    assert acceptance.evaluate(cr, 0.7) is True and acceptance.evaluate(cr, 0.8) is False
    assert acceptance.evaluate(acceptance.Criterion("y", "any", "c", "m", "abs<=", 0.01, ""), -0.02) is False
    assert acceptance.evaluate(acceptance.Criterion("z", "any", "c", "m", "report", None, ""), 1.0) is None
    for c in acceptance.CRITERIA:
        assert c.rationale and (c.op == "report") == (c.limit is None)


def test_every_criterion_metric_is_produced():
    """Each pre-registered metric must exist in a (quick) run, so no criterion is silently 'MISSING'."""
    det = HPGE
    produced = {
        "isolated_strong": benchmark.cat_isolated(det, 1)[0],
        "tailed": benchmark.cat_isolated(det, 1, tail=True)[0],
        "isolated_weak": benchmark.cat_weak(det, 4)[0],
        "background_only": benchmark.cat_background(det, 1)[0],
        "doublets": benchmark.cat_doublets(det, 1)[0],
        "compton_edge": benchmark.cat_edge(det, 6)[0],
        "low_counts": benchmark.cat_low(det, 4)[0],
        "runtime": {"median_s": 0.0},
    }
    for c in acceptance.CRITERIA:
        if c.detector == "HPGe" and c.category in produced:
            assert c.metric in produced[c.category], c.id


def test_identification_scenario_truth():
    syns = list(scenarios.identification(HPGE, n_seeds=1))
    assert len(syns) == len(scenarios.MIXTURES) * len(scenarios.DRIFTS)
    cs = next(s for s in syns if s.meta["mixture"] == "Cs-137" and s.meta["drift"] == 0)
    assert "Cs-137" in cs.meta["present"] and "K-40" in cs.meta["present"]


@pytest.mark.skipif(reference.find_refdata() is None, reason="IAEA G-1 / EML reference spectra not available")
def test_reference_sets_run():
    root = reference.find_refdata()
    g1 = reference.run_g1(root)
    assert g1 is not None and g1["G1100_found"] >= 18
    eml = reference.run_eml(root)
    assert eml is not None and "error" not in eml
    off, gain = eml["calibration_keV"]
    assert gain == pytest.approx(0.5, rel=0.05)

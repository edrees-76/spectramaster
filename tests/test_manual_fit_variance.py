"""Manual refits of net spectra (docs/baseline/manual_fit_variance_protocol.md): the variance
S + k^2 B is used, negative channels are kept, and without a variance a non-Poisson spectrum is
not fitted silently."""
from __future__ import annotations

import json

import numpy as np
import pytest

from spectramaster.analysis import find_peaks
from spectramaster.analysis.background import net_spectrum
from spectramaster.analysis.manual import refit_region
from spectramaster.lab.session import AnalysisSession
from spectramaster.validation.synthetic import Continuum, DetectorSpec, TruePeak, make_spectrum

# 512 channels (400-656 keV) keep the many realisations fast; HPGe resolution as synthetic.HPGE
DET = DetectorSpec("HPGe", 512, 400.0, 0.5, 1.0, 0.0016, label="HPGe")
E0, AREA = 530.0, 1000.0
FLAT = Continuum(exp_amp=0.0, exp_scale_kev=400.0, flat=1000.0)      # Codex H1: 1000 counts/channel


def _net(seed):
    s = make_spectrum(DET, [TruePeak(E0, AREA)], FLAT, seed=seed).spectrum
    b = make_spectrum(DET, [], FLAT, seed=seed + 100000).spectrum
    net, var, _k = net_spectrum(s, b)
    return net, var


def _region():
    c, fw = DET.channel(E0), float(DET.fwhm_ch(E0))
    return int(c - 2.2 * fw), int(c + 2.2 * fw), c


# ------------------------------------------------------------------ MF.C1 / C2
def test_the_variance_is_used_by_the_manual_fit():
    # MF.C1 itself FAILED (protocol results): with the default free width (x0.5..x2) the manual
    # u is 1.65 x the automatic one (width x0.7..x1.4).  Checked here: the variance is used, and
    # with the width held at the model (the same model as the search) u agrees (post hoc check).
    net, var = _net(1)
    lo, hi, c = _region()
    auto = next(p for p in find_peaks(net, variance=var) if abs(p.energy - E0) < 2)
    man = refit_region(net, lo, hi, [c], variance=var).peaks[0]
    old = refit_region(net, lo, hi, [c]).peaks[0]                   # no variance: Poisson weights
    assert man.net_area_unc > 2.0 * old.net_area_unc          # 223 vs 83 (seed 1)
    held = refit_region(net, lo, hi, [c], variance=var, width="model").peaks[0]
    assert 0.9 <= held.net_area_unc / auto.net_area_unc <= 1.1


def test_coverage_of_the_manual_uncertainty():
    lo, hi, c = _region()
    z = []
    for seed in range(300):
        net, var = _net(1000 + seed)
        p = refit_region(net, lo, hi, [c], variance=var).peaks[0]
        z.append(abs(p.net_area - AREA) / p.net_area_unc)
    z = np.array(z)
    assert 0.60 <= float(np.mean(z <= 1.0)) <= 0.78
    assert float(np.mean(z <= 2.0)) >= 0.90


# ------------------------------------------------------------------ MF.C3 negative channels
def test_negative_channels_are_kept_with_the_variance():
    net, var = _net(2)
    lo, hi, c = _region()
    counts = np.asarray(net.counts, dtype=float)
    counts[lo] = counts[lo + 1] = -400.0                            # make sure some are negative
    net.counts = [float(x) for x in counts]
    rf = refit_region(net, lo, hi, [c], variance=var)
    f0 = net.first_channel
    assert np.array_equal(rf.group.data, counts[rf.group.lo - f0:rf.group.hi - f0 + 1])
    assert (rf.group.data < 0).any()
    assert "not valid" not in rf.peaks[0].note


# ------------------------------------------------------------------ MF.C4 / C5 without a variance
def test_raw_spectrum_without_variance_has_no_note():
    s = make_spectrum(DET, [TruePeak(E0, 1.0e4)], FLAT, seed=3).spectrum
    lo, hi, c = _region()
    rf = refit_region(s, lo, hi, [c])
    assert "not valid" not in rf.peaks[0].note
    assert "variance" not in rf.options and "not_poisson" not in rf.options


def test_subtracted_spectrum_without_variance_is_not_fitted_silently():
    net, _var = _net(4)
    lo, hi, c = _region()
    counts = np.asarray(net.counts, dtype=float)
    counts[lo:lo + 3] = -50.0
    net.counts = [float(x) for x in counts]
    rf = refit_region(net, lo, hi, [c])
    n_neg = int((counts[lo:hi + 1] < 0).sum())
    for p in rf.peaks:
        assert "uncertainties not valid" in p.note and f"{n_neg} negative channel" in p.note
    assert f"{n_neg} negative channel" in rf.options["not_poisson"]


# ------------------------------------------------------------------ MF.C6 session
def test_session_refit_with_variance_records_its_hash():
    net, var = _net(5)
    lo, hi, c = _region()
    pk = find_peaks(net, variance=var)
    s = AnalysisSession()
    s.set_results(pk, [], spectrum=net)
    op, rf = s.refit_region(net, lo, hi, [c], reason="net spectrum", variance=var)
    d = json.loads(json.dumps(op.details))
    assert d["variance"] == "explicit" and len(d["variance_sha256"]) == 64
    with pytest.raises(ValueError):
        s.refit_region(net, lo, hi, [c], reason="bad", variance=var[:-1])

"""Round-7 review Gemini H2: background spectrum shared by the sample and its reagent blank
(docs/baseline/round7_shared_background_protocol.md)."""
import dataclasses
import math

import numpy as np
import pytest

from spectramaster.analysis import activity as act
from spectramaster.analysis.background import BackgroundFitter
from spectramaster.lab.session import quant_to_dict
from spectramaster.validation import round7_shared_background as h


@pytest.mark.parametrize("mode", ["peak", "spectrum"])
def test_identical_blank_cancels_the_background(mode):
    c = h._identity(mode)
    assert abs(c["net"]) < 1e-9 * c["u_s"]
    assert math.isclose(c["u"], math.sqrt(2.0 * (c["u_s"] ** 2 - c["u_B"] ** 2)), rel_tol=1e-9)


def test_fitter_coefficients_give_its_estimate():
    s, b = h._spec(5000.0, 30_000), h._spec(h.BKG_AREA, 10_000)
    bf = BackgroundFitter(s, b)
    idx = act._channel_of_energy(s, 661.657)
    kn, ku, (lo, c) = bf.at_energy(idx, 4.0)
    bb = np.maximum(np.asarray(b.counts, dtype=float), 0.0)[lo:lo + len(c)]
    assert math.isclose(kn, float(c @ bb), rel_tol=1e-9)
    assert math.isclose(ku, math.sqrt(float((c * c) @ bb)), rel_tol=1e-9)


def _sample_with(blank, bkg):
    return act.compute_activities(h._spec(5000.0, 30_000), h._flat_curve(), h._opt("peak"), background=bkg, blank=blank)


def test_covariance_only_with_the_same_background_in_the_same_session():
    curve, o = h._flat_curve(), h._opt("peak")
    bkg = h._spec(h.BKG_AREA, 10_000)
    qb = act.compute_activities(h._spec(h.BLANK_AREA, 20_000), curve, o, background=bkg)
    shared = _sample_with(qb, bkg)
    ln = shared.nuclides[0].lines[0]
    assert ln.blank_bkg_cov > 0 and any("covariance of their background estimates" in n for n in shared.notes)
    loaded = _sample_with(act.QuantResults.from_dict(quant_to_dict(qb)), bkg)
    other = _sample_with(qb, dataclasses.replace(bkg, counts=list(np.asarray(bkg.counts) + 1)))
    for q in (loaded, other):
        assert q.nuclides[0].lines[0].blank_bkg_cov == 0.0
        assert any(h.INDEP_NOTE in n for n in q.notes)
    assert loaded.nuclides[0].lines[0].u_count_bq > ln.u_count_bq
    assert "_bkg_res" not in quant_to_dict(shared)["nuclides"][0]["lines"][0]


def test_sample_counts_the_blank_level_under_the_null_hypothesis():
    curve, o = h._flat_curve(), h._opt(None)
    qb = act.compute_activities(h._spec(h.BLANK_AREA, 20_000), curve, o)
    smp = h._spec(h.BLANK_AREA, 30_000)
    ln = act.compute_activities(smp, curve, o, blank=qb).nuclides[0].lines[0]
    alone = act.compute_activities(smp, curve, o).nuclides[0].lines[0]
    w = alone.activity / alone.net_area
    fwin = alone.lc_counts / alone.decision_threshold * w           # Currie: L_C w / f_w
    s0 = (alone.lc_counts / o.k_alpha) ** 2 + (ln.blank_unc * fwin / w) ** 2 + ln.blank_activity * fwin / w
    assert math.isclose(ln.lc_counts, o.k_alpha * math.sqrt(s0), rel_tol=1e-9)

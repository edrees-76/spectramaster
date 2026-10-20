"""Uncertainty and input-validation defects confirmed by the second external review."""
from __future__ import annotations

import math

import numpy as np
import pytest

from spectramaster.analysis import activity as act
from spectramaster.analysis import efficiency as eff
from spectramaster.tools import qc
from test_activity import LIVE, SAMPLE_REF, cal_curve, make_spectrum  # noqa: F401
from test_reagent_blank import cs_counts

K = 1.645


def iso_root(sigma0, w, u_rel, k_a=K, k_b=K):
    """Positive root of (y# - y*)^2 = k_b^2 (w y# + w^2 sigma0^2 + y#^2 u_rel^2)."""
    ys = k_a * w * sigma0
    a = 1.0 - k_b ** 2 * u_rel ** 2
    b = -(2.0 * ys + k_b ** 2 * w)
    c = ys ** 2 - k_b ** 2 * w ** 2 * sigma0 ** 2
    return (-b + math.sqrt(b * b - 4.0 * a * c)) / (2.0 * a)


@pytest.mark.parametrize("u_rel", [0.0, 0.1, 0.5, 0.6, 0.607])
def test_iso11929_detection_limit_is_the_exact_root(u_rel):
    ys, yd = act.iso11929_limits(10.0, 0.01, u_rel)
    assert ys == pytest.approx(K * 0.01 * 10.0)
    assert yd == pytest.approx(iso_root(10.0, 0.01, u_rel), rel=1e-12)


def test_iso11929_detection_limit_unequal_k_and_no_limit():
    _ys, yd = act.iso11929_limits(15.0, 0.25, 0.05, k_alpha=1.282, k_beta=1.645)
    assert yd == pytest.approx(iso_root(15.0, 0.25, 0.05, 1.282, 1.645), rel=1e-12)
    assert act.iso11929_limits(10.0, 0.01, 1.0 / K)[1] == math.inf


def opts(**kw):
    return act.ActivityOptions(nuclides=["Cs-137"], ref_date=SAMPLE_REF, **kw)


def test_zero_net_activity_keeps_a_finite_uncertainty(cal_curve):
    _pts, curve = cal_curve
    smp = make_spectrum([cs_counts(30.0)])
    blank = act.compute_activities(make_spectrum([cs_counts(30.0)], sid="blank"), curve, opts())
    net = act.compute_activities(smp, curve, opts(), blank=blank)
    r, ln, bl = net.nuclides[0], net.nuclides[0].key_line, blank.nuclides[0].key_line
    assert abs(r.activity) < 1e-9 * bl.activity
    u_count = math.hypot(abs(bl.activity) * bl.u_count_rel, abs(bl.activity) * bl.u_count_rel)
    assert math.isfinite(r.u) and r.u == pytest.approx(u_count, rel=1e-6)
    assert ln.u_count_bq == pytest.approx(u_count, rel=1e-6)


PULSER_KEV = 2500.0


def pulsed(a, pulser_counts):
    e, n = cs_counts(a)
    return make_spectrum([(e, n), (PULSER_KEV, pulser_counts)])


def test_blank_and_sample_reference_uncertainties_are_both_kept(cal_curve):
    _pts, curve = cal_curve
    ref = {"energy": PULSER_KEV, "rate": 1500.0 / LIVE, "rate_rel_unc": 0.0}
    o = opts(reference_peak=ref)
    blank = act.compute_activities(pulsed(40.0, 1500.0), curve, o)
    net = act.compute_activities(pulsed(45.0, 1500.0), curve, o, blank=blank)
    r, ln = net.nuclides[0], net.nuclides[0].key_line
    u_s, u_b = net.reference_u_count_rel, blank.reference_u_count_rel
    assert u_s > 0.01 and u_b > 0.01                 # weak reference peaks: a few per cent each
    want = math.hypot(ln.gross_activity * u_s, ln.blank_activity * u_b)
    assert r.budget["reference peak"] / 100 * abs(r.activity) == pytest.approx(want, rel=1e-6)
    # the common expected rate scales the net value only
    ref2 = dict(ref, rate_rel_unc=0.05)
    o2 = opts(reference_peak=ref2)
    blank2 = act.compute_activities(pulsed(40.0, 1500.0), curve, o2)
    net2 = act.compute_activities(pulsed(45.0, 1500.0), curve, o2, blank=blank2)
    r2, ln2 = net2.nuclides[0], net2.nuclides[0].key_line
    want2 = math.sqrt((ln2.gross_activity * u_s) ** 2 + (ln2.blank_activity * u_b) ** 2
                      + (r2.activity * 0.05) ** 2)
    assert r2.budget["reference peak"] / 100 * abs(r2.activity) == pytest.approx(want2, rel=1e-6)


def test_blank_analysed_with_other_options_is_noted(cal_curve):
    _pts, curve = cal_curve
    blank = act.compute_activities(make_spectrum([cs_counts(20.0)], sid="blank"), curve,
                                   opts(attenuation=2.0, bkg_mode="spectrum"),
                                   background=make_spectrum([], sid="lab background"))
    net = act.compute_activities(make_spectrum([cs_counts(50.0)]), curve,
                                 opts(tcs={"peak_to_total": [0.24, -0.63], "pt_rel_unc": 0.1}), blank=blank)
    text = " | ".join(net.notes)
    for word in ("attenuation", "coincidence summing", "background mode"):
        assert word in text, word
    same = act.compute_activities(make_spectrum([cs_counts(50.0)]), curve, opts(),
                                  blank=act.compute_activities(make_spectrum([cs_counts(20.0)], sid="b"),
                                                               curve, opts()))
    assert not any("reagent blank analysed with" in t for t in same.notes)


@pytest.mark.parametrize("field, value", [("live_time", -100.0), ("live_time", math.nan),
                                          ("live_time", math.inf), ("real_time", -5.0),
                                          ("real_time", math.nan)])
def test_unphysical_times_are_refused(cal_curve, field, value):
    pts, curve = cal_curve
    s = make_spectrum([cs_counts(50.0)])
    setattr(s, field, value)
    with pytest.raises(ValueError, match="time"):
        act.compute_activities(s, curve, opts())
    cert = [eff.CertLine("Cs-137", 661.657, 0.85, 1000.0, 10.0, SAMPLE_REF, None)]
    with pytest.raises(ValueError, match="time"):
        eff.measure_efficiency(s, cert)


def test_non_finite_counts_are_refused(cal_curve):
    _pts, curve = cal_curve
    s = make_spectrum([cs_counts(50.0)])
    c = np.asarray(s.counts, dtype=float)
    c[10] = math.nan
    s.counts = c.tolist()
    with pytest.raises(ValueError, match="finite"):
        act.compute_activities(s, curve, opts())


def test_qc_constant_series_has_zero_sd():
    for v in (0.1, 661.657, 1332.492):
        mean, sd = qc._stats([v] * 20)
        assert sd == 0.0 and mean == pytest.approx(v)
    s = qc.Series(key="centroid", metric="centroid", line=None, unit="keV")
    s.points = [qc.SeriesPoint(mid=f"m{i}", date=None, value=0.1) for i in range(20)]
    s.mean, s.sd = qc._stats([0.1] * 20)
    qc._apply_rules(s, ["1-3s", "10-x"])
    assert all(p.flags == [] for p in s.points)

"""Reagent blank correction (docs/baseline/reagent_blank_protocol.md)."""
from __future__ import annotations

import math
from datetime import timedelta

import pytest

from spectramaster.analysis import activity as act
from spectramaster.analysis import efficiency as eff
from spectramaster.lab.session import quant_to_dict
from test_activity import LIVE, SAMPLE_REF, START, cal_curve, lib_line, make_spectrum, true_eff  # noqa: F401

A_SAMPLE, A_BLANK = 50.0, 20.0


def cs_counts(a, start=START):
    e, i, hl = lib_line("Cs-137", 661.657)
    d = eff.decay_factor(hl, (start - SAMPLE_REF).total_seconds())
    return e, a * d * eff.counting_decay_factor(hl, LIVE) * true_eff(e) * i * LIVE


def opts(**kw):
    return act.ActivityOptions(nuclides=["Cs-137", "Co-60"], ref_date=SAMPLE_REF, **kw)


def test_blank_subtracted_with_its_counting_uncertainty(cal_curve):
    _pts, curve = cal_curve
    blank = act.compute_activities(make_spectrum([cs_counts(A_BLANK)], sid="blank"), curve, opts())
    smp = make_spectrum([cs_counts(A_SAMPLE + A_BLANK)])
    gross = act.compute_activities(smp, curve, opts())
    net = act.compute_activities(smp, curve, opts(), blank=blank)
    g, n, b = (q.nuclides[0].key_line for q in (gross, net, blank))
    assert n.gross_activity == pytest.approx(g.activity, rel=1e-12)
    assert n.blank_activity == pytest.approx(b.activity, rel=1e-12)
    assert n.activity == pytest.approx(g.activity - b.activity, rel=1e-12)
    assert net.nuclides[0].activity == pytest.approx(A_SAMPLE, rel=0.02)
    u_gross, u_blank = abs(g.activity) * g.u_count_rel, abs(b.activity) * b.u_count_rel
    assert abs(n.activity) * n.u_count_rel == pytest.approx(math.hypot(u_gross, u_blank), rel=1e-9)
    assert n.blank_unc == pytest.approx(u_blank, rel=1e-12)
    # the blank widens the null hypothesis: higher decision threshold and MDA
    assert n.decision_threshold > g.decision_threshold and n.mda > g.mda
    # efficiency stays relative to the net value (fully correlated between sample and blank)
    r = net.nuclides[0]
    assert r.budget["efficiency"] == pytest.approx(100 * n.eff_rel_unc, rel=1e-9)
    assert net.blank == "blank" and any("reagent blank subtracted" in t for t in net.notes)
    # Co-60: no peak anywhere, no correction, reported per line
    co = net.nuclides[1]
    assert all(ln.blank_activity is None and "blank" in ln.note for ln in co.lines)


def test_iso11929_threshold_includes_blank(cal_curve):
    _pts, curve = cal_curve
    o = opts(mda_method="iso11929")
    blank = act.compute_activities(make_spectrum([cs_counts(A_BLANK)], sid="blank"), curve, o)
    smp = make_spectrum([cs_counts(1.01 * A_BLANK)])        # the reagents only (+1 %)
    g = act.compute_activities(smp, curve, o).nuclides[0]
    n = act.compute_activities(smp, curve, o, blank=blank).nuclides[0]
    assert g.detected and not n.detected
    assert abs(n.activity) < 0.05 * A_BLANK and n.decision_threshold > g.decision_threshold
    assert n.best_estimate is not None and n.best_estimate >= 0.0


def test_blank_decay_corrected_to_the_sample_reference_date(cal_curve):
    _pts, curve = cal_curve
    _e, _i, hl = lib_line("Cs-137", 661.657)
    blank = act.compute_activities(make_spectrum([cs_counts(A_BLANK)], sid="blank"), curve, opts())
    blank.ref_date = SAMPLE_REF - timedelta(seconds=hl)        # one half-life before the sample's
    n = act.compute_activities(make_spectrum([cs_counts(A_SAMPLE)]), curve, opts(), blank=blank)
    ln, bl = n.nuclides[0].key_line, blank.nuclides[0].key_line
    assert ln.blank_activity == pytest.approx(0.5 * bl.activity, rel=1e-9)
    assert ln.blank_unc == pytest.approx(0.5 * abs(bl.activity) * bl.u_count_rel, rel=1e-9)


def test_without_blank_unchanged_and_round_trip(cal_curve):
    _pts, curve = cal_curve
    smp = make_spectrum([cs_counts(A_SAMPLE)])
    a = act.compute_activities(smp, curve, opts())
    assert a.blank == "" and a.nuclides[0].key_line.blank_activity is None
    blank = act.compute_activities(make_spectrum([cs_counts(A_BLANK)], sid="blank"), curve, opts())
    n = act.compute_activities(smp, curve, opts(), blank=blank)
    back = act.QuantResults.from_dict(quant_to_dict(n))
    assert back.blank == n.blank
    assert back.nuclides[0].key_line.blank_activity == n.nuclides[0].key_line.blank_activity
    # a blank analysed with another curve is reported
    blank.curve_name = "another curve"
    assert any("another efficiency curve" in t
               for t in act.compute_activities(smp, curve, opts(), blank=blank).notes)


def test_cli_blank(cal_curve, tmp_path, capsys):
    from spectramaster import cli
    from test_activity import write_spec
    _pts, curve = cal_curve
    out = tmp_path / "eff.json"
    curve.save(out)
    smp = write_spec(make_spectrum([cs_counts(A_SAMPLE + A_BLANK)]), tmp_path / "smp.json")
    blk = write_spec(make_spectrum([cs_counts(A_BLANK)], sid="blank"), tmp_path / "blank.json")
    args = ["activity", str(smp), "--eff", str(out), "--ref-date", f"{SAMPLE_REF:%Y-%m-%d %H:%M}",
            "--nuclides", "Cs-137"]
    capsys.readouterr()
    assert cli.main(args + ["--blank", str(blk)]) == 0
    text = capsys.readouterr().out
    assert "reagent blank subtracted" in text
    row = [ln for ln in text.splitlines() if ln.startswith("Cs-137")][0]
    assert f"{A_SAMPLE:.3g}"[:2] in row

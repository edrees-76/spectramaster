"""Reference peak correction (docs/baseline/reference_peak_protocol.md)."""
from __future__ import annotations

from datetime import timedelta

import pytest

from spectramaster.analysis import activity as act
from test_activity import LIVE, SAMPLE_REF, START, cal_curve, make_spectrum  # noqa: F401
from test_reagent_blank import A_SAMPLE, cs_counts

PULSER_KEV, PULSER_CPS = 2500.0, 50.0


def lossy(loss, pulser=True, a=A_SAMPLE):
    e, n = cs_counts(a)
    peaks = [(e, n * (1 - loss))]
    if pulser:
        peaks.append((PULSER_KEV, PULSER_CPS * LIVE * (1 - loss)))
    return make_spectrum(peaks)


def opts(ref=None, **kw):
    return act.ActivityOptions(nuclides=["Cs-137"], ref_date=SAMPLE_REF, reference_peak=ref, **kw)


REF = {"energy": PULSER_KEV, "rate": PULSER_CPS, "rate_rel_unc": 0.01}


def test_losses_corrected_with_the_reference_uncertainty(cal_curve):
    _pts, curve = cal_curve
    q0 = act.compute_activities(lossy(0.10), curve, opts())
    q = act.compute_activities(lossy(0.10), curve, opts(REF))
    assert q0.reference_factor is None and q0.nuclides[0].activity == pytest.approx(0.9 * A_SAMPLE, rel=0.02)
    assert q.reference_factor == pytest.approx(1 / 0.9, rel=0.005)
    r = q.nuclides[0]
    assert r.activity == pytest.approx(A_SAMPLE, rel=0.02)
    assert r.activity == pytest.approx(q0.nuclides[0].activity * q.reference_factor, rel=1e-12)
    assert r.mda == pytest.approx(q0.nuclides[0].mda * q.reference_factor, rel=1e-9)
    assert q.reference_u_rel > 0.01 and r.budget["reference peak"] == pytest.approx(100 * q.reference_u_rel)
    assert any("reference peak correction" in t for t in q.notes)


def test_no_losses_no_bias_and_missing_peak_refused(cal_curve):
    _pts, curve = cal_curve
    q = act.compute_activities(lossy(0.0), curve, opts(REF))
    assert q.reference_factor == pytest.approx(1.0, abs=0.005)
    with pytest.raises(ValueError, match="reference peak"):
        act.compute_activities(lossy(0.05, pulser=False), curve, opts(REF))


def test_reference_source_decay_and_rate(cal_curve):
    _pts, curve = cal_curve
    ref_spec = lossy(0.0)
    rate, u = act.reference_rate(ref_spec, PULSER_KEV)
    assert rate == pytest.approx(PULSER_CPS, rel=0.005) and 0 < u < 0.01 * rate
    hl = 1.0e8
    src = {"energy": PULSER_KEV, "rate": PULSER_CPS * 2.0, "half_life_s": hl,
           "ref_date": START - timedelta(seconds=hl)}          # one half-life before the measurement
    q = act.compute_activities(lossy(0.0), curve, opts(src))
    assert q.reference_factor == pytest.approx(1.0, abs=0.005)


def test_cli_reference_peak(cal_curve, tmp_path, capsys):
    from spectramaster import cli
    from test_activity import write_spec
    _pts, curve = cal_curve
    out = tmp_path / "eff.json"
    curve.save(out)
    smp = write_spec(lossy(0.10), tmp_path / "smp.json")
    capsys.readouterr()
    assert cli.main(["activity", str(smp), "--eff", str(out), "--ref-date", f"{SAMPLE_REF:%Y-%m-%d %H:%M}",
                     "--nuclides", "Cs-137", "--ref-peak", f"{PULSER_KEV:g}", "--ref-rate", f"{PULSER_CPS:g}"]) == 0
    text = capsys.readouterr().out
    assert "reference peak correction" in text and "K = 1.11" in text

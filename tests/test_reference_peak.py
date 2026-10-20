"""Reference peak correction (docs/baseline/reference_peak_protocol.md)."""
from __future__ import annotations

from datetime import timedelta

import pytest

from spectramaster.analysis import activity as act
from test_activity import (LIVE, SAMPLE_REF, START, cal_curve, gui_settings, make_spectrum,  # noqa: F401
                           qapp)
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
    from spectramaster.lab.sample import SampleInfo
    conc = act.concentrations(q, SampleInfo(), "Bq")              # shown with the report's results
    assert any("K = 1.11" in n for n in conc["notes"])
    assert not any("reference peak" in n for n in act.concentrations(q0, SampleInfo(), "Bq")["notes"])


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


def test_activity_dialog_reference_peak(cal_curve, qapp, gui_settings, tmp_path):
    from PySide6.QtCore import QDateTime
    from spectramaster.gui import i18n
    from spectramaster.gui.quant_panel import ActivityDialog
    from test_activity import write_spec
    _pts, curve = cal_curve
    path = tmp_path / "curves" / "c.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    curve.save(path)
    ref_spec = write_spec(lossy(0.0), tmp_path / "reference.json")
    i18n.set_language("en")
    try:
        ad = ActivityDialog(None, lossy(0.10), gui_settings)
        ad.set_curve_path(path)
        ad.nuc_edit.setText("Cs-137")
        ad.ref_start.setChecked(False)
        ad.ref_edit.setDateTime(QDateTime(SAMPLE_REF))
        lost = ad.calculate().nuclides[0].activity
        assert lost == pytest.approx(0.9 * A_SAMPLE, rel=0.02)
        ad.refpk_box.setChecked(True)
        ad.refpk_energy.setValue(PULSER_KEV)
        assert ad.measure_reference(str(ref_spec))                # rate measured in a reference spectrum
        assert ad.refpk_rate.value() == pytest.approx(PULSER_CPS, rel=0.005) and ad.refpk_unc.value() > 0
        res = ad.calculate()
        assert res.reference_factor == pytest.approx(1 / 0.9, rel=0.005)
        assert res.nuclides[0].activity == pytest.approx(A_SAMPLE, rel=0.02)
        assert any("reference peak correction" in n for n in res.notes)
        assert gui_settings.get("quant/reference_peak", "").startswith(f"{PULSER_KEV:g},")
        ad.refpk_energy.setValue(1800.0)                          # no peak there: refused, never uncorrected
        ad.message = lambda text: setattr(ad, "last_error", text)
        assert ad.calculate() is None and "reference peak" in ad.last_error
        ad.refpk_energy.setValue(PULSER_KEV)
        ad.refpk_box.setChecked(False)                            # off by default and when unticked
        assert ad.calculate().reference_factor is None
        ad.close()
        ad2 = ActivityDialog(None, lossy(0.10), gui_settings)       # the settings come back
        assert ad2.refpk_energy.value() == pytest.approx(PULSER_KEV)
        assert ad2.refpk_rate.value() == pytest.approx(PULSER_CPS, rel=0.005)
        ad2.close()
    finally:
        i18n.set_language("ar")

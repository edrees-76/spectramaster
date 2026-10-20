"""True-coincidence summing correction (docs/baseline/tcs_protocol.md)."""
from __future__ import annotations

import pytest

from spectramaster.analysis import activity as act
from spectramaster.analysis import coincidence as co
from spectramaster.analysis import efficiency as eff
from spectramaster.validation import tcs_mc
from test_activity import LIVE, cal_curve, lib_line, make_spectrum, true_eff  # noqa: F401
from test_reagent_blank import SAMPLE_REF, START

PT = (0.24, -0.63)
A_CO60 = 2.0e4


def co60_spectrum(summing: bool):
    """Co-60 counts with the exact single-coincidence summing loss (1 - eps_t of the partner)."""
    peaks = []
    for e0, partner in ((1173.228, 1332.492), (1332.492, 1173.228)):
        e, i, hl = lib_line("Co-60", e0)
        d = eff.decay_factor(hl, (START - SAMPLE_REF).total_seconds())
        n = A_CO60 * d * eff.counting_decay_factor(hl, LIVE) * true_eff(e) * i * LIVE
        if summing:
            n *= 1.0 - true_eff(partner) / co.peak_to_total(partner, *PT)
        peaks.append((e, n))
    return make_spectrum(peaks)


def opts(**kw):
    return act.ActivityOptions(nuclides=["Co-60"], ref_date=SAMPLE_REF, method="mean", **kw)


def test_formula_matches_single_cascade_exactly():
    ep = lambda e: tcs_mc.eps_peak(e, 0.02)                       # noqa: E731
    pt = lambda e: tcs_mc.peak_to_total(e)                        # noqa: E731
    c = co.coi("Co-60", 1173.228, ep, pt)
    p = co.transitions("Co-60")[0]
    j = p.index(1332.492)
    assert c.found and c.summing_in < 1e-5
    assert c.summing_out == pytest.approx(sum(p.coincident[p.index(1173.228)] * ep(p.energies) / pt(p.energies)))
    assert c.factor == pytest.approx(1 - p.after[p.index(1173.228), j] * ep(1332.492) / pt(1332.492), abs=2e-4)
    assert not co.coi("Cs-137", 661.657, ep, pt).found and co.coi("Cs-137", 661.657, ep, pt).factor == 1.0


def test_crossover_gains_counts():
    ep = lambda e: tcs_mc.eps_peak(e, 0.02)                       # noqa: E731
    pt = lambda e: tcs_mc.peak_to_total(e)                        # noqa: E731
    assert co.coi("Cs-134", 1365.185, ep, pt).summing_in > 0.3
    assert co.coi("Cs-134", 604.721, ep, pt).summing_in == 0.0


def test_activity_corrected_with_budget(cal_curve):
    _pts, curve = cal_curve
    spec = co60_spectrum(summing=True)
    plain = act.compute_activities(spec, curve, opts())
    corr = act.compute_activities(spec, curve, opts(tcs={"peak_to_total": list(PT), "pt_rel_unc": 0.10}))
    r0, r = plain.nuclides[0], corr.nuclides[0]
    assert r0.activity < 0.97 * A_CO60                            # biased low without the correction
    assert r.activity == pytest.approx(A_CO60, rel=0.01)
    for ln in r.lines:
        assert ln.coi < 1.0 and ln.coi_rel_unc > 0
        assert ln.mda == pytest.approx(next(l0.mda for l0 in r0.lines if l0.energy == ln.energy) / ln.coi, rel=1e-9)
    assert r.budget["coincidence summing"] > 0
    assert "true-coincidence summing corrected" in r.note and "not corrected" not in r.note
    assert "not corrected" in r0.note
    assert any("peak-to-total" in n for n in corr.notes)


def test_no_summing_left_alone(cal_curve):
    _pts, curve = cal_curve
    q = act.compute_activities(make_spectrum([(661.657, 1e5)]), curve,
                               act.ActivityOptions(nuclides=["Cs-137"], tcs={"peak_to_total": list(PT)}))
    assert q.nuclides[0].lines[0].coi == 1.0 and "coincidence summing" not in q.nuclides[0].budget
    with pytest.raises(ValueError, match="peak-to-total"):
        act.compute_activities(make_spectrum([(661.657, 1e5)]), curve,
                               act.ActivityOptions(nuclides=["Cs-137"], tcs={"peak_to_total": [0, -0.6]}))


def test_mc_is_independent_and_consistent():
    """The benchmark's simulation reproduces the library emission probabilities and, for Co-60,
    the exact single-coincidence loss."""
    s = tcs_mc.scheme("Cs-134")
    assert s.emission == pytest.approx(s.intensity, rel=0.01)
    r = tcs_mc.simulate("Co-60", 0.02, 400_000, 7)
    exact = 1 - tcs_mc.eps_peak(1332.492, 0.02) / tcs_mc.peak_to_total(1332.492)
    c, sd = r[1173.228]
    assert abs(c - exact) < 4 * sd


def test_cli_tcs(cal_curve, tmp_path, capsys):
    from spectramaster import cli
    from test_activity import write_spec
    _pts, curve = cal_curve
    out = tmp_path / "eff.json"
    curve.save(out)
    smp = write_spec(co60_spectrum(summing=True), tmp_path / "co60.json")
    capsys.readouterr()
    assert cli.main(["activity", str(smp), "--eff", str(out), "--ref-date", f"{SAMPLE_REF:%Y-%m-%d %H:%M}",
                     "--nuclides", "Co-60", "--tcs-pt", "0.24,-0.63"]) == 0
    text = capsys.readouterr().out
    assert "true-coincidence summing corrected" in text and "peak-to-total" in text

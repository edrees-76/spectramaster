"""Quantitative analysis: efficiency calibration, activity, detection limits, CLI, dialogs."""
from __future__ import annotations

import math
import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from spectramaster import cli
from spectramaster.analysis import activity as act
from spectramaster.analysis import efficiency as eff
from spectramaster.analysis.library import load_library
from spectramaster.formats import get_format, load_all
from spectramaster.model import Spectrum

load_all()

GAIN = 0.25           # keV / channel
NCH = 12000
LIVE = 20000.0
START = datetime(2024, 3, 1, 10, 0, 0)
# true efficiency: ln eps = sum a_i ln(E/1000)^i
TRUE = [math.log(0.012), -0.80, -0.12, 0.03]


def true_eff(e):
    x = math.log(e / 1000.0)
    return math.exp(sum(a * x ** i for i, a in enumerate(TRUE)))


def fwhm_kev(e):
    return math.sqrt(0.75 + 0.00185 * e)


def make_spectrum(peaks, continuum=40.0, slope=-0.002, live=LIVE, start=START, sid="synthetic"):
    """Noise-free spectrum: linear-ish continuum + Gaussian peaks (exact channel integrals)."""
    ch = np.arange(NCH, dtype=float)
    e = ch * GAIN
    y = np.maximum(continuum + slope * e, 5.0)
    edges = (np.arange(NCH + 1) - 0.5) * GAIN
    for energy, area in peaks:
        s = fwhm_kev(energy) / 2.3548
        cdf = 0.5 * (1 + np.vectorize(math.erf)((edges - energy) / (s * math.sqrt(2))))
        y = y + area * np.diff(cdf)
    return Spectrum(counts=[float(v) for v in y], energy_coeffs=[0.0, GAIN], live_time=live, real_time=live,
                    start_time=start, sample_id=sid, detector="HPGe")


def lib_line(nuclide, energy):
    nd = load_library()[nuclide]
    l = min(nd.lines, key=lambda q: abs(q.energy - energy))
    return l.energy, l.intensity / 100.0, nd.half_life_s


# ------------------------------------------------------------------ helpers
def test_decay_helpers_exact():
    hl = 100.0
    assert eff.decay_factor(hl, 100.0) == pytest.approx(0.5)
    assert eff.decay_factor(hl, -100.0) == pytest.approx(2.0)
    assert eff.decay_factor(None, 1e9) == 1.0
    lam = math.log(2) / hl
    assert eff.counting_decay_factor(hl, 50.0) == pytest.approx((1 - math.exp(-lam * 50)) / (lam * 50))
    assert eff.counting_decay_factor(1e20, 50.0) == pytest.approx(1.0)
    assert eff.parse_date("22/07/2004 11:02") == datetime(2004, 7, 22, 11, 2)
    assert eff.parse_date("2004-07-22") == datetime(2004, 7, 22)


def test_currie_and_iso_formulas():
    lc, ld = act.currie_limits(10.0)
    assert lc == pytest.approx(16.45)
    assert ld == pytest.approx(1.645 ** 2 + 2 * 16.45)
    w = 0.01
    ys, yd = act.iso11929_limits(10.0, w, 0.0)
    assert ys == pytest.approx(1.645 * w * 10.0)
    # y# = y* + k sqrt(w y# + w^2 sigma0^2)
    assert yd == pytest.approx(ys + 1.645 * math.sqrt(w * yd + w * w * 100.0), rel=1e-9)
    # with u_rel(w) = 0 ISO detection limit equals Currie L_D (k_alpha = k_beta)
    assert yd == pytest.approx(ld * w, rel=1e-9)
    _ys, yd2 = act.iso11929_limits(10.0, w, 0.10)
    assert yd2 > yd


# ------------------------------------------------------------------ efficiency
CAL_LINES = [("Am-241", 59.541, 0.359, 4000.0), ("Co-57", 122.06, 0.856, 1500.0), ("Ce-139", 165.86, 0.799, 1800.0),
             ("Hg-203", 279.20, 0.815, 2500.0), ("Sn-113", 391.70, 0.650, 3000.0), ("Sr-85", 514.00, 0.96, 3500.0),
             ("Cs-137", 661.66, 0.851, 2000.0), ("Y-88", 898.04, 0.937, 3000.0), ("Co-60", 1173.23, 0.9985, 2500.0),
             ("Co-60b", 1332.49, 0.9998, 2500.0), ("Y-88b", 1836.06, 0.992, 3000.0)]
CAL_REF = START - timedelta(days=30)


def cal_certificate(unc=0.02):
    out = []
    for name, e, i, a in CAL_LINES:
        hl = {"Am-241": 1.365e10, "Co-57": 2.348e7, "Ce-139": 1.189e7, "Hg-203": 4.027e6, "Sn-113": 9.944e6,
              "Sr-85": 5.603e6, "Cs-137": 9.49e8, "Y-88": 9.212e6, "Co-60": 1.663e8}[name.rstrip("b")]
        out.append(eff.CertLine(name.rstrip("b"), e, i, a, a * unc, CAL_REF, hl))
    return out


def cal_spectrum(cert):
    peaks = []
    for c in cert:
        a0 = c.activity * eff.decay_factor(c.half_life_s, (START - c.ref_date).total_seconds())
        cf = eff.counting_decay_factor(c.half_life_s, LIVE)
        peaks.append((c.energy, true_eff(c.energy) * c.intensity * a0 * cf * LIVE))
    return make_spectrum(peaks)


@pytest.fixture(scope="module")
def cal_curve():
    cert = cal_certificate()
    pts = eff.measure_efficiency(cal_spectrum(cert), cert)
    return pts, eff.fit_efficiency(pts, "loglog", order=3, name="synthetic")


def test_efficiency_points_exact(cal_curve):
    pts, _c = cal_curve
    assert len(pts) == len(CAL_LINES)
    for p in pts:
        assert p.efficiency == pytest.approx(true_eff(p.energy), rel=0.01), p.energy
        assert p.u_ref_rel == pytest.approx(0.02)


def test_loglog_fit_recovers_curve(cal_curve):
    _pts, c = cal_curve
    for e in (80, 200, 661.66, 1500):
        assert c.efficiency(e) == pytest.approx(true_eff(e), rel=0.01)
    # Release D: the certificate activity uncertainty enters the fit covariance once (shared
    # by the lines of each nuclide), it is no longer added to the curve again as u_sys
    assert c.u_sys_rel == 0.0 and c.cov_method == "gls"
    assert 0.005 <= c.rel_uncertainty(661.66) < 0.05
    assert all(abs(r) < 1.5 for _p, r, _z in c.residuals())


def test_two_branch_fit_continuous_and_auto(cal_curve):
    pts, _c = cal_curve
    c = eff.fit_efficiency(pts, "two_branch", order=2, order_high=2, crossover=200.0)
    assert c.efficiency(200.0 - 1e-9) == pytest.approx(c.efficiency(200.0 + 1e-9), rel=1e-6)
    assert c.efficiency(661.66) == pytest.approx(true_eff(661.66), rel=0.02)
    ca = eff.fit_efficiency(pts, "two_branch", order=2, order_high=2, crossover="auto")
    assert 80 <= ca.e_ref <= 600
    with pytest.raises(ValueError):
        eff.fit_efficiency(pts[:2], "loglog", order=3)


def test_curve_json_roundtrip(cal_curve, tmp_path):
    _pts, c = cal_curve
    c.geometry, c.detector = "Marinelli 1L", "HPGe-30%"
    p = c.save(tmp_path / "eff.json")
    c2 = eff.load_curve(p)
    assert c2.geometry == "Marinelli 1L" and len(c2.points) == len(c.points)
    for e in (100, 661.66, 1460):
        assert c2.efficiency(e) == pytest.approx(c.efficiency(e))
        assert c2.rel_uncertainty(e) == pytest.approx(c.rel_uncertainty(e))


def test_manual_points_and_certificate_csv(tmp_path):
    pts = [eff.manual_point(e, true_eff(e), 2.0) for e in (100, 200, 400, 800, 1600)]
    c = eff.fit_efficiency(pts, "loglog", order=2)
    assert c.efficiency(300) == pytest.approx(true_eff(300), rel=0.03)
    entries = [eff.CertNuclide("Cs-137", 1000.0, 30.0, datetime(2020, 1, 1)),
               eff.CertNuclide("Co-60", 2000.0, 20.0, datetime(2020, 1, 1), lines=[(1173.23, 0.9985), (1332.49, 0.9998)])]
    p = eff.write_certificate_csv(tmp_path / "cert.csv", entries)
    back = eff.read_certificate_csv(p)
    assert back[0].nuclide == "Cs-137" and back[0].activity_unc == pytest.approx(30.0)
    assert [v for ln in back[1].lines for v in ln] == pytest.approx([1173.23, 0.9985, 1332.49, 0.9998])
    lines = eff.certificate_lines(back)
    assert any(abs(l.energy - 661.657) < 0.01 for l in lines)


# ------------------------------------------------------------------ activity
SAMPLE_REF = START - timedelta(days=200)
A_CS, A_K = 50.0, 400.0


def sample_peaks(a_cs=A_CS, a_k=A_K, t_live=LIVE, start=START):
    out = []
    for nuc, e0, a in (("Cs-137", 661.657, a_cs), ("K-40", 1460.82, a_k)):
        e, i, hl = lib_line(nuc, e0)
        d = eff.decay_factor(hl, (start - SAMPLE_REF).total_seconds())
        out.append((e, a * d * eff.counting_decay_factor(hl, t_live) * true_eff(e) * i * t_live))
    return out


def test_activity_exact_recovery(cal_curve):
    _pts, curve = cal_curve
    s = make_spectrum(sample_peaks())
    opt = act.ActivityOptions(nuclides=["Cs-137", "K-40", "Co-60"], ref_date=SAMPLE_REF, quantity=0.5,
                              quantity_unit="kg", quantity_rel_unc=0.01)
    res = act.compute_activities(s, curve, opt)
    by = {r.nuclide: r for r in res.nuclides}
    assert by["Cs-137"].activity == pytest.approx(A_CS, rel=0.015)
    assert by["K-40"].activity == pytest.approx(A_K, rel=0.015)
    assert by["Cs-137"].specific == pytest.approx(A_CS / 0.5, rel=0.015)
    assert by["Cs-137"].unit == "Bq/kg"
    assert by["Cs-137"].detected and by["Cs-137"].decision == "detected"
    assert by["Cs-137"].specific_U == pytest.approx(2 * by["Cs-137"].specific_u)
    b = by["Cs-137"].budget
    # the Bq budget must not contain the mass uncertainty (it only affects Bq/kg)
    # Release D: the 2 % certificate uncertainties of the independent nuclides average down in
    # the curve fit (they were previously added again as a fully correlated 2 % floor)
    assert "quantity" not in b and b["efficiency"] > 0.3 and b["counting"] > 0
    tot = math.sqrt(sum(v * v for v in b.values()))
    assert 100 * by["Cs-137"].u / by["Cs-137"].activity == pytest.approx(tot)
    cs = by["Cs-137"]
    assert cs.specific_u / cs.specific == pytest.approx(math.hypot(cs.u / cs.activity, 0.01))
    co = by["Co-60"]
    assert not co.detected and co.activity is None and co.mda > 0 and co.decision == "< MDA"
    assert co.specific_mda == pytest.approx(co.mda / 0.5)
    assert "true-coincidence" in co.note
    # g and mL units
    opt2 = act.ActivityOptions(nuclides=["Cs-137"], ref_date=SAMPLE_REF, quantity=500.0, quantity_unit="g")
    r2 = act.compute_activities(s, curve, opt2).nuclides[0]
    assert r2.specific == pytest.approx(by["Cs-137"].specific, rel=1e-9)


def test_mda_matches_currie_formula(cal_curve):
    _pts, curve = cal_curve
    s = make_spectrum([])
    res = act.compute_activities(s, curve, act.ActivityOptions(nuclides=["Cs-137"]))
    r = res.nuclides[0]
    ln = r.key_line
    from spectramaster.analysis.peaks import fwhm_model
    fw, _ = fwhm_model(s, np.asarray(s.counts))
    B, n, m, fwin = act.continuum_under(s, ln.energy, fw)
    lc, ld = act.currie_limits(math.sqrt(B * (1 + n / (2 * m))))
    e, i, hl = lib_line("Cs-137", 661.657)
    expect = ld / fwin / (curve.efficiency(e) * i * LIVE * eff.counting_decay_factor(hl, LIVE))
    assert r.mda == pytest.approx(expect, rel=1e-9)
    assert not r.detected
    iso = act.compute_activities(s, curve, act.ActivityOptions(nuclides=["Cs-137"], mda_method="iso11929"))
    assert iso.nuclides[0].mda > r.mda          # efficiency uncertainty enlarges the ISO limit


def test_weighted_mean_and_series(cal_curve):
    _pts, curve = cal_curve
    peaks = []
    a_ra = 30.0
    for nuc, e0 in (("Pb-214", 351.932), ("Bi-214", 609.321), ("Pb-214", 295.224), ("Bi-214", 1764.491)):
        e, i, _hl = lib_line(nuc, e0)
        peaks.append((e, a_ra * true_eff(e) * i * LIVE))
    for nuc, e0, b in (("Ac-228", 911.204, 1.0), ("Pb-212", 238.632, 1.0), ("Tl-208", 583.187, 0.3594)):
        e, i, _hl = lib_line(nuc, e0)
        peaks.append((e, 20.0 * b * true_eff(e) * i * LIVE))
    s = make_spectrum(peaks)
    for method in ("key", "mean"):
        res = act.compute_activities(s, curve, act.ActivityOptions(nuclides=["Ra-226", "Th-232"], method=method))
        by = {r.nuclide: r for r in res.nuclides}
        assert by["Ra-226"].activity == pytest.approx(a_ra, rel=0.02), method
        assert by["Th-232"].activity == pytest.approx(20.0, rel=0.02), method
        assert "equilibrium" in by["Ra-226"].note
    assert len(by["Th-232"].used_energies) == 3      # 968.97 keV not in the spectrum
    assert by["Th-232"].u < by["Th-232"].activity


def test_background_peak_subtraction(cal_curve):
    _pts, curve = cal_curve
    bkg_k = 30.0      # Bq-equivalent K-40 background in the shield
    e, i, _hl = lib_line("K-40", 1460.82)
    bkg = make_spectrum([(e, bkg_k * true_eff(e) * i * 2 * LIVE)], live=2 * LIVE, sid="bkg")
    peaks = sample_peaks()
    peaks[1] = (peaks[1][0], peaks[1][1] + bkg_k * true_eff(e) * i * LIVE)
    s = make_spectrum(peaks)
    opt = act.ActivityOptions(nuclides=["K-40"], ref_date=SAMPLE_REF)
    r_no = act.compute_activities(s, curve, opt).nuclides[0]
    r_pk = act.compute_activities(s, curve, opt, background=bkg).nuclides[0]
    assert r_no.activity == pytest.approx(A_K + bkg_k, rel=0.015)
    assert r_pk.activity == pytest.approx(A_K, rel=0.015)
    assert r_pk.key_line.bkg_peak == pytest.approx(bkg_k * true_eff(e) * i * LIVE, rel=0.01)
    opt.bkg_mode = "spectrum"
    r_sp = act.compute_activities(s, curve, opt, background=bkg).nuclides[0]
    assert r_sp.activity == pytest.approx(A_K, rel=0.03)


def test_export_csv_xlsx(cal_curve, tmp_path):
    _pts, curve = cal_curve
    res = act.compute_activities(make_spectrum(sample_peaks()), curve,
                                 act.ActivityOptions(nuclides=["Cs-137", "Co-60"], quantity=1, quantity_unit="L"))
    p = act.export_results(tmp_path / "a.csv", res)
    text = p.read_text(encoding="utf-8-sig")
    assert "Cs-137" in text and "< MDA" in text and "Bq/L" in text
    pytest.importorskip("openpyxl")
    act.export_results(tmp_path / "a.xlsx", res)
    assert (tmp_path / "a.xlsx").stat().st_size > 0
    assert "Cs-137" in act.format_table(res)


# ------------------------------------------------------------------ CLI
def write_spec(spec, path):
    get_format("json").writer(spec, path)
    return path


def test_cli_effcal_and_activity(tmp_path, capsys):
    std = write_spec(cal_spectrum(cal_certificate()), tmp_path / "std.json")
    rows = ["nuclide,activity_bq,unc_percent,ref_date,half_life_s,energy_kev,intensity_percent"]
    for c in cal_certificate():
        rows.append(f"{c.nuclide},{c.activity},2,{CAL_REF:%Y-%m-%d %H:%M},{c.half_life_s},{c.energy},{100 * c.intensity}")
    cert = tmp_path / "cert.csv"
    cert.write_text("\n".join(rows) + "\n", encoding="utf-8")
    out = tmp_path / "eff.json"
    assert cli.main(["effcal", str(std), "--cert", str(cert), "-o", str(out), "--model", "loglog", "--order", "3"]) == 0
    curve = eff.load_curve(out)
    assert curve.efficiency(661.66) == pytest.approx(true_eff(661.66), rel=0.01)
    smp = write_spec(make_spectrum(sample_peaks()), tmp_path / "smp.json")
    xl = tmp_path / "res.csv"
    capsys.readouterr()
    assert cli.main(["activity", str(smp), "--eff", str(out), "--mass", "0.5", "--unit", "kg",
                     "--ref-date", f"{SAMPLE_REF:%Y-%m-%d %H:%M}", "--nuclides", "Cs-137,K-40,Co-60",
                     "-o", str(xl)]) == 0
    text = capsys.readouterr().out
    assert "Cs-137" in text and "< MDA" in text and xl.is_file()
    res_cs = [l for l in text.splitlines() if l.startswith("Cs-137")][0]
    assert "detected" in res_cs
    assert cli.main(["activity", str(smp), "--eff", str(tmp_path / "missing.json")]) == 1


# ------------------------------------------------------------------ lab validation (read only, skipped elsewhere)
LAB = Path(r"D:\الاسس و المفاهيم العامة فى استخدام برامج الطيف الجامى\اطياف مرجعية"
           r"\4- أطياف المختبر (Aptec)\الملفات الأصلية S0")


@pytest.mark.skipif(not (LAB / "QCY48CAL.S0").is_file(), reason="lab reference spectra not available")
@pytest.mark.parametrize("name,tol", [("QCY48CAL.S0", 0.04), ("EFF.S0", 0.06), ("EFF-GOOD.S0", 0.10)])
def test_lab_closure(name, tol):
    from spectramaster.formats.aptec import read_aptec
    s = read_aptec(LAB / name)[0]
    recs = eff.aptec_source_records(LAB / name)
    assert recs and all(r.efficiency > 0 for r in recs)
    cert = eff.certificate_from_aptec(recs)
    pts = eff.measure_efficiency(s, cert)
    # our points vs Aptec's stored efficiencies: median deviation within a few %
    cmp_ = [c["diff_pct"] for c in eff.compare_with_aptec(pts, recs) if c["diff_pct"] is not None]
    assert abs(float(np.median(cmp_))) < 4.0
    # orders as before Release D (order selection by cross-validation chooses a stiffer curve
    # here and leaves Sr-85, blended with the 511 keV annihilation peak, 18 % above it)
    curve = eff.fit_efficiency(pts, "two_branch", order=3, order_high=2, crossover="auto")
    by = {}
    for c in cert:
        by.setdefault(c.nuclide, c)
    res = act.compute_activities(s, curve, act.ActivityOptions(nuclides=list(by), ref_date=cert[0].ref_date))
    for r in res.nuclides:
        assert r.activity == pytest.approx(by[r.nuclide].activity, rel=tol), r.nuclide


# ------------------------------------------------------------------ GUI (offscreen)
@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from spectramaster.gui.app import create_app
    return create_app(["test"])


@pytest.fixture()
def gui_settings(tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    from spectramaster.gui.settings import Settings
    monkeypatch.setenv("SPECTRAMASTER_EFF_DIR", str(tmp_path / "curves"))
    return Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat))


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_gui_efficiency_and_activity_dialogs(qapp, gui_settings, tmp_path, lang):
    from spectramaster.gui import i18n
    from spectramaster.gui.efficiency_dialog import EfficiencyDialog
    from spectramaster.gui.quant_panel import ActivityDialog, quant_table
    i18n.set_language(lang)
    try:
        cert = cal_certificate()
        std = cal_spectrum(cert)
        dlg = EfficiencyDialog(None, std, gui_settings)
        dlg.set_certificate([eff.CertNuclide(c.nuclide, c.activity, c.activity_unc, c.ref_date, c.half_life_s,
                                             [(c.energy, c.intensity)]) for c in cert[:9]] +
                            [eff.CertNuclide("Y-88", 3000.0, 60.0, CAL_REF, 9.212e6, [(898.04, 0.937), (1836.06, 0.992)])])
        assert dlg.cert_table.rowCount() == 10
        dlg.model_combo.setCurrentIndex(dlg.model_combo.findData("loglog"))
        assert dlg.measure_and_fit()
        assert dlg.pt_table.rowCount() >= 9
        assert dlg.curve.efficiency(661.66) == pytest.approx(true_eff(661.66), rel=0.02)
        dlg.add_manual_point(2000.0, true_eff(2000.0), 3.0)
        assert dlg.refit() and len(dlg.curve.points) == dlg.pt_table.rowCount()
        dlg.plot.resize(500, 400)
        dlg.plot.grab()                         # paint once
        path = dlg.save_curve(str(eff.default_curve_dir() / "synthetic.json"))
        assert path.is_file()
        dlg.apply_preset()
        assert dlg.cert_table.rowCount() > 0
        dlg2 = EfficiencyDialog(None, None, gui_settings)
        assert dlg2.load_curve_dialog(str(path)) and dlg2.curve is not None
        dlg.close(), dlg2.close()

        class Parent:
            quant_results = None
        smp = make_spectrum(sample_peaks())
        ad = ActivityDialog(None, smp, gui_settings)
        ad.set_curve_path(path)
        ad.qty_spin.setValue(0.5)
        ad.nuc_edit.setText("Cs-137, K-40, Co-60")
        ad.ref_start.setChecked(False)
        from PySide6.QtCore import QDateTime
        ad.ref_edit.setDateTime(QDateTime(SAMPLE_REF))
        res = ad.calculate()
        assert res is not None and ad.table.rowCount() == 3
        cs = next(r for r in res.nuclides if r.nuclide == "Cs-137")
        assert cs.activity == pytest.approx(A_CS, rel=0.02)
        header, rows = quant_table(res)
        assert len(header) == len(rows[0]) and rows[2][7] == i18n.tr("quant_res_lt_mda")
        out = ad.export(str(tmp_path / f"r_{lang}.csv"))
        assert out.is_file()
        ad.close()
    finally:
        i18n.set_language("ar")


def test_gui_menu_hook(qapp, gui_settings):
    from spectramaster.gui.app import MainWindow
    w = MainWindow(gui_settings)
    try:
        assert w.quant_results is None
        assert w.act_activity in w.menu_analyze.actions()
        assert w.act_effcal in w.menu_setup_advanced.actions()      # Setup > Advanced Calibration Tools
        assert w.act_effcal.text()
        from spectramaster.gui.quant_panel import open_activity_dialog, open_efficiency_dialog
        d1 = open_efficiency_dialog(w, modal=False)
        d2 = open_activity_dialog(w, modal=False)
        d1.close(), d2.close()
    finally:
        w.close()


def test_quantity_uncertainty_only_affects_specific_activity(cal_curve):
    """The Bq activity does not depend on the sample mass/volume, so its uncertainty must not
    change with quantity_rel_unc; the specific activity adds it in quadrature."""
    _pts, curve = cal_curve
    s = make_spectrum(sample_peaks())
    base = dict(nuclides=["Cs-137"], ref_date=SAMPLE_REF)
    r0 = act.compute_activities(s, curve, act.ActivityOptions(**base)).nuclides[0]
    r1 = act.compute_activities(s, curve, act.ActivityOptions(**base, quantity_rel_unc=0.10)).nuclides[0]
    r2 = act.compute_activities(s, curve, act.ActivityOptions(**base, quantity=2.0, quantity_unit="kg",
                                                              quantity_rel_unc=0.10)).nuclides[0]
    assert r1.u == pytest.approx(r0.u, rel=1e-12) and r2.u == pytest.approx(r0.u, rel=1e-12)
    assert r1.specific is None and r1.specific_u is None
    assert r2.specific == pytest.approx(r0.activity / 2.0)
    assert r2.specific_u == pytest.approx(math.hypot(r0.u / 2.0, 0.10 * r2.specific))


# ------------------------------------------------------------------ ISO 11929 best estimate
def _iso_direct(y, u, cov=0.95):
    """Independent, direct (not log-space) evaluation of the ISO 11929-1 formulas."""
    from scipy.stats import norm
    g = 1.0 - cov
    om = norm.cdf(y / u)
    best = y + u * norm.pdf(y / u) / om
    ub = math.sqrt(u * u - (best - y) * best)
    return best, ub, y - norm.ppf(om * (1 - g / 2)) * u, y + norm.isf(om * g / 2) * u


def test_iso11929_best_estimate_formula():
    u = 2.5
    for y in np.linspace(-8 * u, 8 * u, 33):
        got = act.iso11929_best_estimate(float(y), u)
        assert got == pytest.approx(_iso_direct(float(y), u), rel=1e-9, abs=1e-12)
        best, ub, lo, hi = got
        assert 0.0 <= lo < best < hi and 0.0 < ub <= u
    # y = 0: closed form
    best, ub, lo, hi = act.iso11929_best_estimate(0.0, 1.0)
    assert best == pytest.approx(math.sqrt(2 / math.pi), rel=1e-12)
    assert ub == pytest.approx(math.sqrt(1 - 2 / math.pi), rel=1e-12)
    # y >> u: the usual symmetric interval y +- 1.96 u
    best, ub, lo, hi = act.iso11929_best_estimate(100.0, 1.0)
    assert (best, ub) == pytest.approx((100.0, 1.0), rel=1e-12)
    assert (lo, hi) == pytest.approx((100 - 1.959964, 100 + 1.959964), abs=1e-6)
    # other coverage probability, and a strongly negative primary result stays finite and >= 0
    assert act.iso11929_best_estimate(1.0, 1.0, 0.90) == pytest.approx(_iso_direct(1.0, 1.0, 0.90), rel=1e-9)
    best, ub, lo, hi = act.iso11929_best_estimate(-60.0, 1.0)
    assert 0.0 <= lo < best < hi < 0.1
    # unusable inputs
    for y, uu in ((1.0, 0.0), (1.0, None), (None, 1.0), (float("nan"), 1.0), (1.0, float("inf"))):
        assert act.iso11929_best_estimate(y, uu) is None
    with pytest.raises(ValueError):
        act.iso11929_best_estimate(1.0, 1.0, 1.0)


def test_iso11929_best_estimate_in_results(cal_curve, tmp_path):
    from spectramaster.lab.sample import SampleInfo
    _pts, curve = cal_curve
    s = make_spectrum(sample_peaks())
    base = dict(nuclides=["Cs-137", "Co-60"], ref_date=SAMPLE_REF, quantity=0.5, quantity_unit="kg",
                quantity_rel_unc=0.01)
    iso = act.compute_activities(s, curve, act.ActivityOptions(**base, mda_method="iso11929"))
    cs, co = iso.nuclides
    assert (cs.best_estimate, cs.best_u, cs.coverage_low, cs.coverage_high) == pytest.approx(
        act.iso11929_best_estimate(cs.activity, cs.u), rel=1e-12)
    assert (cs.specific_best, cs.specific_best_u, cs.specific_low, cs.specific_high) == pytest.approx(
        act.iso11929_best_estimate(cs.specific, cs.specific_u), rel=1e-12)
    assert cs.coverage_low < cs.best_estimate < cs.coverage_high
    # no peak: the signed window result is the primary result (signed_primary_protocol.md)
    assert co.activity is None and co.primary_method == "window"
    assert (co.best_estimate, co.best_u) == pytest.approx(
        act.iso11929_best_estimate(co.primary, co.primary_u)[:2], rel=1e-12)
    cur = act.compute_activities(s, curve, act.ActivityOptions(**base)).nuclides[0]
    assert cur.best_estimate is None and cur.specific_best is None   # Currie: not computed
    # export, round trip of a stored session, concentrations
    text = act.export_results(tmp_path / "iso.csv", iso).read_text(encoding="utf-8-sig")
    assert "best_specific" in text and "Coverage probability" in text
    from spectramaster.lab.session import quant_to_dict
    d = quant_to_dict(iso)
    back = act.QuantResults.from_dict(d)
    assert back.nuclides[0].specific_best == pytest.approx(cs.specific_best)
    d["options"].pop("coverage")                         # sessions saved before this field existed
    assert act.QuantResults.from_dict(d).options.coverage == 0.95
    conc = act.concentrations(iso, SampleInfo(matrix_type="soil", mass_kg=0.5, mass_basis="dry"), "Bq/kg",
                              quantity_rel_unc=0.01)
    row = conc["rows"][0]
    y = cs.activity / 0.5
    assert (row["best"], row["best_u"]) == pytest.approx(act.iso11929_best_estimate(
        y, math.hypot(cs.u / 0.5, 0.01 * y))[:2], rel=1e-12)
    assert "ISO 11929" in row["best_text"] and "best" not in conc["rows"][1]


def test_iso11929_column_in_table(qapp, cal_curve):
    from spectramaster.gui import i18n
    from spectramaster.gui.quant_panel import RES_COLS, quant_table
    _pts, curve = cal_curve
    s = make_spectrum(sample_peaks())
    opt = act.ActivityOptions(nuclides=["Cs-137", "Co-60"], ref_date=SAMPLE_REF, quantity=0.5,
                              quantity_unit="kg", mda_method="iso11929", coverage=0.90)
    res = act.compute_activities(s, curve, opt)
    j = RES_COLS.index("res_col_best")
    for lang in ("en", "ar"):
        header, rows = quant_table(res, lang)
        assert "90" in header[j] and "Bq/kg" in header[j] and "{p}" not in header[j]
        assert rows[0][j].count("±") == 1 and rows[1][j].count("±") == 1   # Co-60: from the window result
        assert rows[0][7] == i18n.tr_in(lang, "quant_res_detected")

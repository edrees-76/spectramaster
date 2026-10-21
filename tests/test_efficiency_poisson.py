"""Efficiency points with a background, non-Poisson spectra and outliers in the model error
(docs/baseline/efficiency_poisson_protocol.md)."""
from __future__ import annotations

import os

import numpy as np
import pytest

from spectramaster.analysis import efficiency as ef
from spectramaster.analysis.background import net_spectrum
from spectramaster.analysis.peaks import FitReport, find_peaks
from spectramaster.tools import spectrum_ops as ops
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE, NAI

LINES = {("Cs-137", 661.657), ("Co-60", 1173.228), ("Co-60", 1332.492)}
N_PAIRS = 40


def cert_lines() -> list[ef.CertLine]:
    """Cs-137 and Co-60 at 1 Bq, no uncertainty, no date, library intensities."""
    lines = ef.certificate_lines([ef.CertNuclide("Cs-137", 1.0), ef.CertNuclide("Co-60", 1.0)])
    out = [ln for ln in lines if any(ln.nuclide == n and abs(ln.energy - e) < 0.5 for n, e in LINES)]
    assert len(out) == 3
    return out


def efficiency_runs(det, n=N_PAIRS):
    """{(nuclide, keV): [(net, unc, true) or None]} of measure_efficiency with the background."""
    cert = cert_lines()
    out = {k: [] for k in LINES}
    for smp, bkg, truth in scenarios.background_pairs(det, n):
        pts = ef.measure_efficiency(smp.spectrum, cert, background=bkg.spectrum)
        for key in LINES:
            p = next((q for q in pts if q.nuclide == key[0] and abs(q.energy - key[1]) < 0.5), None)
            out[key].append(None if p is None else (p.net_area, p.net_unc, truth[key]))
    return out


@pytest.fixture(scope="module", params=[NAI, HPGE], ids=["NaI", "HPGe"])
def runs(request):
    return request.param.name, efficiency_runs(request.param)


# ------------------------------------------------------------------ EP.C1 / C2
def test_bias_per_line(runs):
    name, res = runs
    for key, rows in res.items():
        assert all(r is not None for r in rows), (name, key, "line not found")
        bias = float(np.mean([n / t - 1.0 for n, _u, t in rows]))
        print(f"EP.C1 {name} {key[0]} {key[1]:.1f}: bias {100 * bias:+.2f} %")
        assert abs(bias) <= 0.03, (name, key, bias)


def test_coverage(runs):
    name, res = runs
    z = [(n - t) / u for rows in res.values() for n, u, t in rows]
    cov1 = float(np.mean([abs(x) <= 1 for x in z]))
    cov2 = float(np.mean([abs(x) <= 2 for x in z]))
    print(f"EP.C2 {name}: cov1 {cov1:.3f} cov2 {cov2:.3f} (n = {len(z)})")
    assert 0.55 <= cov1 <= 0.81 and 0.89 <= cov2 <= 1.0


# ------------------------------------------------------------------ EP.C3 / C4
@pytest.mark.parametrize("det", [NAI, HPGE], ids=["NaI", "HPGe"])
def test_points_are_the_net_fit(det):
    cert = cert_lines()
    for smp, bkg, _truth in scenarios.background_pairs(det, 5):
        pts = ef.measure_efficiency(smp.spectrum, cert, background=bkg.spectrum)
        net, var, _k = net_spectrum(smp.spectrum, bkg.spectrum)
        peaks = find_peaks(net, variance=var)
        assert pts
        for p in pts:
            pk = ef.match_peak(peaks, p.energy)
            assert pk is not None
            assert p.net_area == pytest.approx(pk.net_area, rel=1e-9)
            assert p.net_unc == pytest.approx(pk.net_area_unc, rel=1e-9)
            assert "background subtracted before the fit (S - kB)" in p.note


def test_peak_list_with_background_refused():
    smp, bkg, _ = next(scenarios.background_pairs(HPGE, 1))
    with pytest.raises(ValueError):
        ef.measure_efficiency(smp.spectrum, cert_lines(), peaks=find_peaks(smp.spectrum),
                              background=bkg.spectrum)


# ------------------------------------------------------------------ EP.C5
def _search(spec, **kw):
    rep = FitReport()
    return find_peaks(spec, report=rep, **kw), rep


def test_non_poisson_spectra_are_reported():
    smp, bkg, _ = next(scenarios.background_pairs(HPGE, 1))
    raw = smp.spectrum
    norm = ops.normalize(raw, 10.0)
    sub, var, _k = net_spectrum(raw, bkg.spectrum)
    cert = cert_lines()

    def curve_warns(pts):
        return " ".join(ef.fit_efficiency(pts, "loglog", order=1).warnings)

    _pk, rep = _search(raw)
    assert rep.notes == []
    pts = ef.measure_efficiency(raw, cert)
    assert not any(ef.NOT_POISSON_POINT in p.note for p in pts)
    assert "not Poisson" not in curve_warns(pts)

    for spec in (norm, sub):
        peaks, rep = _search(spec)
        assert len(rep.notes) == 1 and "not Poisson counts" in rep.notes[0]
        assert [p.net_area for p in peaks] == [p.net_area for p in find_peaks(spec)]
        pts = ef.measure_efficiency(spec, cert)
        assert pts and all(ef.NOT_POISSON_POINT in p.note for p in pts)
        assert "not Poisson counts" in curve_warns(pts)

    _pk, rep = _search(sub, variance=var)
    assert rep.notes == []


# ------------------------------------------------------------------ EP.C6
def test_analysis_window_banner(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from spectramaster.gui import i18n
    from spectramaster.gui.app import MainWindow, create_app
    from spectramaster.gui.settings import Settings
    QApplication.instance() or create_app(["test"])
    i18n.set_language("en")
    w = MainWindow(Settings(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)))
    try:
        smp, _bkg, _ = next(scenarios.background_pairs(HPGE, 1))
        w.display([ops.normalize(smp.spectrum, 10.0)], None, None)
        w._on_analysis_done(w._ana_token, [], [], True)
        assert not w.analysis_panel.banner.isHidden()
        assert i18n.tr("ana_not_poisson") in w.analysis_panel.banner.text()
        w.display([smp.spectrum], None, None)
        w._on_analysis_done(w._ana_token, [], [], True)
        assert w.analysis_panel.banner.isHidden()
    finally:
        w.close()
        w.deleteLater()
        QApplication.processEvents()


# EP.C7 / C8 (model error, D2): R3 was withdrawn after the CRM run; see the protocol's results.

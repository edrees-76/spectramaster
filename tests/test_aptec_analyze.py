"""Aptec-style Peak Search, Identify and Quantify (pure functions)."""
from __future__ import annotations

import math
import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from spectramaster.analysis import aptec_analyze as aa
from spectramaster.analysis.aptec_roi import RoiProperties

APTEC_DIR = Path(os.environ.get("SPECTRAMASTER_APTEC_DIR", r"C:\APTEC\APTEC"))


def _spectrum(peaks=((300, 2000.0, 2.5), (700, 800.0, 3.0)), n=1024, bkg=50.0, seed=1):
    rng = np.random.default_rng(seed)
    x = np.arange(n)
    mu = np.full(n, bkg)
    for c, area, s in peaks:
        mu += area / (s * math.sqrt(2 * math.pi)) * np.exp(-0.5 * ((x - c) / s) ** 2)
    return rng.poisson(mu).astype(float)


def test_peak_search_finds_peaks_and_rejects_noise():
    y = _spectrum()
    found = aa.peak_search(y, aa.PeakSearchSetup(max_error=20.0), RoiProperties(), 100.0)
    cen = sorted(st.centroid for st in found)
    assert any(abs(c - 300) < 1 for c in cen) and any(abs(c - 700) < 1 for c in cen)
    for st in found:
        assert st.err_pct < 20.0 and st.net > 0 and st.rh - st.rl + 1 >= aa.MIN_ROI_WIDTH
        top = st.rl + int(np.argmax(y[st.rl:st.rh + 1]))
        assert y[st.rl] <= y[st.rl:top + 1].min() and y[st.rh] <= y[top:st.rh + 1].min()
    flat = aa.peak_search(_spectrum(peaks=()), aa.PeakSearchSetup(max_error=20.0), RoiProperties(), 100.0)
    assert len(flat) <= 2


def test_peak_search_partial_and_validation():
    y = _spectrum()
    found = aa.peak_search(y, aa.PeakSearchSetup(max_error=20.0, partial=True, start=500, stop=900))
    assert found and all(500 <= st.rl and st.rh <= 900 for st in found)
    with pytest.raises(ValueError):
        aa.PeakSearchSetup(max_error=0).validate()
    assert aa.PeakSearchSetup.from_dict({"max_error": -1}).max_error == 30.0


def _lines():
    L = aa.LibraryLine
    return [L("Co-60", 1173.23, 0.9985, 1.66e8), L("Co-60", 1332.49, 0.9998, 1.66e8),
            L("Sc-46", 889.28, 0.9998, 7.2e6), L("Sc-46", 1120.55, 0.9999, 7.2e6),
            L("Cs-137", 661.66, 0.851, 9.49e8), L("Bi-214", 1120.29, 0.149, 1194.0),
            L("Bi-214", 609.31, 0.4549, 1194.0)]


def test_identify_fraction_limit_and_choice():
    lines = _lines()
    setup = aa.IdentifySetup(fraction_limit=40.0)
    res = aa.identify([1173.4, 1332.3, 661.5], [1.5, 1.6, None], lines, setup, (0, 3000))
    assert [(r.line.isotope, r.line.energy) for r in res] == [("Co-60", 1173.23), ("Co-60", 1332.49),
                                                                 ("Cs-137", 661.66)]
    assert res[2].tolerance == setup.fixed_tolerance          # no FWHM: fixed tolerance
    assert res[0].tolerance == pytest.approx(0.75)            # 0.5 x 1.5 keV
    # 1120: Sc-46 (1 of 2 lines, 50 %) and Bi-214 (2 of 2 lines) -> Bi-214, most lines found
    res = aa.identify([1120.4, 609.4], [2.0, 2.0], lines, setup, (0, 3000))
    assert res[0].line.isotope == "Bi-214" and res[0].lines_found == 2
    # fraction limit 60 %: Co-60 with only one of its two lines is rejected
    res = aa.identify([1173.4], [1.5], lines, aa.IdentifySetup(fraction_limit=60.0), (0, 3000))
    assert res == [None]
    # lines outside the spectrum range do not count
    res = aa.identify([1173.4], [1.5], lines, aa.IdentifySetup(fraction_limit=60.0), (0, 1200))
    assert res[0].line.isotope == "Co-60" and res[0].fraction == pytest.approx(100.0)


def test_identify_half_life_reject():
    lines = [aa.LibraryLine("X-1", 500.0, 1.0, 100.0)]
    on = aa.IdentifySetup(half_life_limit=7.0, half_life_reject=True)
    assert aa.identify([500.0], [2.0], lines, on, None, elapsed_s=1000.0) == [None]
    assert aa.identify([500.0], [2.0], lines, on, None, elapsed_s=500.0)[0] is not None


def test_quantify_formula():
    line = aa.LibraryLine("Cs-137", 661.66, 0.851, 9.49e8)
    q = aa.quantify(2.0, 5.0, 0.1, line, 0.01, aa.QuantifySetup("Bq", use_quantity=True), quantity=0.5,
                    efficiency_err_pct=3.0)
    assert q.activity == pytest.approx(2.0 / (0.01 * 0.851) / 0.5)
    assert q.activity_err_pct == pytest.approx(math.hypot(5.0, 3.0))
    assert q.mda == pytest.approx(0.1 / (0.01 * 0.851) / 0.5)
    g = aa.quantify(2.0, None, None, line, 0.01, aa.QuantifySetup("gamma/s", use_quantity=False))
    assert g.activity == pytest.approx(200.0)                  # emission rate: no yield
    pci = aa.quantify(2.0, None, None, line, 0.01, aa.QuantifySetup("pCi", use_quantity=False))
    assert pci.activity == pytest.approx(2.0 / (0.01 * 0.851) / 0.037)
    t0 = datetime(2020, 1, 1)
    short = aa.LibraryLine("X", 100.0, 1.0, 86400.0)
    d = aa.quantify(1.0, None, None, short, 0.1, aa.QuantifySetup("Bq", use_quantity=False),
                    start_time=t0 + timedelta(days=2), activity_time=t0)
    assert d.activity == pytest.approx(10.0 * 4.0)             # two half-lives back
    assert aa.quantify(1.0, None, None, line, 0.01, aa.QuantifySetup("Bq"), quantity=None).activity is None
    assert aa.quantify(1.0, None, None, line, None, aa.QuantifySetup("Bq", use_quantity=False)).activity is None
    assert "?" in aa.quantify(0.05, None, 0.1, line, 0.01, aa.QuantifySetup("Bq", use_quantity=False)).flags


def test_lines_from_spectramaster_library():
    lines = aa.lines_from_library()
    k40 = [l for l in lines if l.isotope == "K-40"]
    assert k40 and abs(k40[0].energy - 1460.8) < 0.2 and 0.05 < k40[0].yield_ < 0.2
    assert all(a.energy <= b.energy for a, b in zip(lines, lines[1:]))


@pytest.mark.skipif(not (APTEC_DIR / "isotope.lib").is_file(), reason="Aptec installation not available")
def test_read_aptec_library():
    lines, units = aa.read_aptec_library(APTEC_DIR / "isotope.lib")
    assert units == "keV" and len(lines) == 1378
    k40 = [l for l in lines if l.isotope == "K-40"]
    assert k40 and k40[0].energy == pytest.approx(1460.75, abs=0.01) and k40[0].yield_ == pytest.approx(0.107, abs=1e-4)


def _quantified_files():
    if not APTEC_DIR.is_dir():
        return []
    from spectramaster.analysis.aptec_s0 import read_s0
    out = []
    for p in sorted(APTEC_DIR.glob("*.s0")):
        f = read_s0(p)
        if f.flag("quantified"):
            out.append((p, f))
    return out


@pytest.mark.skipif(not _quantified_files(), reason="Aptec sample files not available")
def test_quantify_matches_aptec_sample_files():
    """Activities Aptec stored in its quantified sample files, efficiency at the ROI centroid."""
    from spectramaster.analysis import aptec_calibration as ac
    n = 0
    for p, f in _quantified_files():
        eff = ac.read_aptec_calibrations(p)["efficiency"]
        u = f.setup.quant_use
        setup = aa.QuantifySetup(f.activity_units, use_quantity=u["Q"], use_total_quantity=u["T"])
        for r in f.rois:
            if not r.isotope:
                continue
            e = float(np.polynomial.polynomial.polyval(r.centroid, f.energy_coeffs))
            q = aa.quantify(r.net / f.live_time, r.net_err_pct, None,
                            aa.LibraryLine(r.isotope, r.iso_energy, r.iso_yield, r.iso_half_life_s),
                            ac.calculate_efficiency(eff, e)[0], setup, start_time=f.start_time,
                            activity_time=f.activity_time, quantity=f.quantity, total_quantity=f.total_quantity)
            assert q.activity == pytest.approx(r.activity, rel=1e-4)
            n += 1
    assert n >= 10


def test_quantify_review_fixes():
    """External review (2026-10): total quantity, decay underflow, count-rate and mBq units."""
    line = aa.LibraryLine("Cs-137", 661.66, 0.851, 9.49e8)
    total = aa.QuantifySetup("Bq", use_quantity=True, use_total_quantity=True)
    q = aa.quantify(2.0, None, None, line, 0.01, total, quantity=0.5, total_quantity=None)
    assert q.activity is None and q.note == "total quantity is missing"
    q = aa.quantify(2.0, None, None, line, 0.01, total, quantity=0.5, total_quantity=4.0)
    assert q.activity == pytest.approx(2.0 / (0.01 * 0.851) / 0.5 * 4.0)
    # activity date many half-lives after the count: no silent zero
    short = aa.LibraryLine("X", 100.0, 1.0, 60.0)
    t0 = datetime(2020, 1, 1)
    u = aa.quantify(1.0, None, None, short, 0.1, aa.QuantifySetup("Bq", use_quantity=False),
                    start_time=t0, activity_time=t0 + timedelta(days=2))
    assert u.activity is None and "<" in u.flags and u.note == "decay correction underflow"
    # count-rate units: the net count rate itself
    c = aa.quantify(2.0, 4.0, 0.5, line, 0.01, aa.QuantifySetup("cps", use_quantity=False))
    assert c.activity == pytest.approx(2.0) and c.mda == pytest.approx(0.5) and c.activity_err_pct == 4.0
    m = aa.quantify(2.0, None, None, line, 0.01, aa.QuantifySetup("cpm", use_quantity=False))
    assert m.activity == pytest.approx(120.0)
    # mBq and MBq differ only by case
    bq = aa.quantify(2.0, None, None, line, 0.01, aa.QuantifySetup("Bq", use_quantity=False)).activity
    assert aa.quantify(2.0, None, None, line, 0.01, aa.QuantifySetup("mBq", use_quantity=False)).activity \
        == pytest.approx(bq * 1e3)
    assert aa.quantify(2.0, None, None, line, 0.01, aa.QuantifySetup("MBq", use_quantity=False)).activity \
        == pytest.approx(bq * 1e-6)


def test_non_finite_counts_rejected():
    from spectramaster.analysis.aptec_roi import analyze_rois
    y = np.full(200, 100.0)
    y[50] = np.nan
    with pytest.raises(ValueError, match="not numbers"):
        analyze_rois(y, [(45, 55)], live_time=100.0)
    y[50] = np.inf
    with pytest.raises(ValueError, match="not numbers"):
        aa.peak_search(y, live_time=100.0)

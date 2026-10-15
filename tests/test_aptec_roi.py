"""Aptec-compatible ROI arithmetic (spectramaster.analysis.aptec_roi).

Synthetic tests always run.  The comparison with ROI results computed by Aptec itself uses the
sample spectra installed with Aptec PCMCA/WIN (``C:\\APTEC\\APTEC`` or ``SPECTRAMASTER_APTEC_DIR``)
and is skipped when they are not on the machine (they are not part of the repository).
"""
from __future__ import annotations

import math
import os
import struct
from pathlib import Path

import numpy as np
import pytest

from spectramaster.analysis import aptec_roi as ar

APTEC_DIR = Path(os.environ.get("SPECTRAMASTER_APTEC_DIR", r"C:\APTEC\APTEC"))
SAMPLES = sorted(APTEC_DIR.glob("*.s0")) if APTEC_DIR.is_dir() else []


def _peak(n=200, pos=100.0, sigma=3.0, area=5000.0, bkg=(50.0, -0.1)):
    x = np.arange(n, dtype=float)
    return (bkg[0] + bkg[1] * x
            + area / (sigma * math.sqrt(2 * math.pi)) * np.exp(-0.5 * ((x - pos) / sigma) ** 2))


def test_end_points_are_outside_the_roi_and_background_is_exact_for_a_line():
    y = _peak()
    r = ar.analyze_rois(y, [(85, 115)], ar.RoiProperties(bkg_degree=1, end_points=4))[0]
    assert (r.bl, r.bh) == (81, 119)
    x = np.arange(85, 116)
    assert r.background == pytest.approx((50.0 - 0.1 * x).sum(), rel=1e-3)
    assert r.gross == pytest.approx(y[85:116].sum())
    assert r.net == pytest.approx(r.gross - r.background)
    assert r.net == pytest.approx(5000.0, rel=5e-3)
    assert r.err_pct == pytest.approx(math.sqrt(r.gross + r.background) / r.net * 100)


def test_degree_zero_joins_end_point_averages_at_the_roi_edges():
    y = np.arange(100, dtype=float)
    c = ar.background_coeffs(y, 10, 20, 40, 50, 0)
    # left average 14.5 placed at channel 19, right average 45.5 at channel 41
    assert np.polynomial.polynomial.polyval(19, c) == pytest.approx(14.5)
    assert np.polynomial.polynomial.polyval(41, c) == pytest.approx(45.5)


def test_centroid_fwhm_and_fwtm_of_a_gaussian():
    y = _peak(sigma=3.0)
    for rng in ar.CENTROID_RANGES:
        for wgt in ar.CENTROID_WEIGHTS:
            r = ar.analyze_rois(y, [(80, 120)], ar.RoiProperties(centroid_range=rng, centroid_weight=wgt))[0]
            assert r.centroid == pytest.approx(100.0, abs=0.05), (rng, wgt)
    r = ar.analyze_rois(y, [(80, 120)])[0]
    assert r.fwhm == pytest.approx(2.3548 * 3.0, rel=0.03)
    assert r.fwtm == pytest.approx(4.2919 * 3.0, rel=0.03)
    assert r.flags == "" and not r.grouped


def test_touching_rois_share_one_background_and_are_flagged():
    y = _peak(pos=90.0) + _peak(pos=110.0, bkg=(0.0, 0.0))
    a, b = ar.analyze_rois(y, [(80, 100), (101, 122)], ar.RoiProperties(end_points=3))
    assert (a.bl, a.bh) == (b.bl, b.bh) == (77, 125)
    assert a.coeffs == b.coeffs
    assert a.grouped and b.grouped
    alone = ar.analyze_rois(y, [(80, 100)])[0]
    assert not alone.grouped


def test_rois_closer_than_the_end_points_are_grouped_with_the_gap_as_end_points():
    y = _peak(pos=90.0) + _peak(pos=112.0, bkg=(0.0, 0.0))
    p = ar.RoiProperties(end_points=3)
    a, b = ar.analyze_rois(y, [(80, 98), (101, 122)], p)        # 98 + 3 reaches 101
    assert (a.bl, a.bh) == (b.bl, b.bh) == (77, 125) and a.grouped
    expect = ar.background_coeffs(y, 77, 80, 122, 125, 1, inner=[99, 100])
    assert a.coeffs == pytest.approx(expect)
    a, b = ar.analyze_rois(y, [(80, 97), (101, 122)], p)        # 97 + 3 stops short of 101
    assert (a.bl, a.bh, b.bl, b.bh) == (77, 100, 98, 125) and not a.grouped


def test_variable_end_points_and_groups():
    p = ar.RoiProperties(variable_end_points=True, end_points_low=2, end_points_high=12)
    assert ar.end_point_width(p, 0, 1001) == 2
    assert ar.end_point_width(p, 1000, 1001) == 12
    assert ar.groups([(50, 60), (10, 20), (21, 30), (61, 70), (90, 95)]) == [[1, 2], [0, 3], [4]]


def test_flags_negative_net_and_mda():
    y = np.full(100, 40.0)
    r = ar.analyze_rois(y, [(40, 60)], live_time=100.0)[0]
    assert r.net <= 0 and r.flags == "?"
    bg = r.background
    k = 1.645
    assert r.mda_cps == pytest.approx((k * k + 2 * k * math.sqrt(2 * bg)) / 100.0)
    strong = ar.analyze_rois(_peak(area=1e5), [(85, 115)], live_time=100.0)[0]
    assert strong.flags == "" and strong.net_cps > strong.mda_cps


def test_properties_round_trip_and_reject_bad_values():
    p = ar.RoiProperties(bkg_degree=0, end_points=5, centroid_range="all", centroid_weight="net")
    assert ar.RoiProperties.from_dict(p.to_dict()) == p
    assert ar.RoiProperties.from_dict({"bkg_degree": 9}) == ar.RoiProperties()
    assert ar.RoiProperties.from_dict({"unknown": 1}) == ar.RoiProperties()
    with pytest.raises(ValueError):
        ar.RoiProperties(centroid_range="x").validate()


def test_roi_order_and_reversed_bounds_are_kept():
    y = _peak()
    out = ar.analyze_rois(y, [(150, 140), (85, 115)])
    assert (out[0].rl, out[0].rh) == (140, 150)
    assert out[1].centroid == pytest.approx(100.0, abs=0.1)


# ---------------------------------------------------------------- comparison with Aptec
_RANGES = {0: "ghm", 1: "fwhm", 2: "fwtm", 3: "all"}


def _read(fn):
    d = fn.read_bytes()
    i16 = lambda o: struct.unpack_from("<h", d, o)[0]
    ne, nen, nres, nroi, nch = i16(330), i16(618), i16(694), i16(782), i16(790)
    if nroi <= 0:
        return None
    o = 1024 + 130 * ne + 8 * nen + 8 * nres
    cnt = np.array(struct.unpack_from("<%dI" % nch, d, o + 256 * nroi), dtype=float)
    job = o + 256 * nroi + 4 * nch
    props = ar.RoiProperties(bkg_degree=d[job + 788], centroid_range=_RANGES.get(d[job + 793], "fwhm"),
                             centroid_weight="squared" if d[job + 792] else "net")
    rois = []
    for k in range(nroi):
        r = o + 256 * k
        bl, rl, rh, bh, _deg = struct.unpack_from("<5h", d, r)
        rois.append(dict(bl=bl, rl=rl, rh=rh, bh=bh, cen=struct.unpack_from("<f", d, r + 108)[0],
                         G=struct.unpack_from("<d", d, r + 112)[0], B=struct.unpack_from("<d", d, r + 120)[0],
                         N=struct.unpack_from("<d", d, r + 128)[0], err=struct.unpack_from("<f", d, r + 136)[0],
                         hm=struct.unpack_from("<2f", d, r + 140), tm=struct.unpack_from("<2f", d, r + 148)))
    return cnt, props, rois


# nai1x1.s0: Aptec's stored backgrounds cannot be reproduced from the stored counts (see the
# module docstring), so that file only takes part in the end-point check.
STALE = {"nai1x1.s0"}


@pytest.mark.skipif(not SAMPLES, reason="Aptec sample spectra not installed")
def test_matches_roi_results_stored_by_aptec():
    total = ok_area = ok_hm = ok_tm = ok_cen = 0
    for fn in SAMPLES:
        got = _read(fn)
        if got is None or fn.name.lower() in STALE:
            continue
        cnt, props, rois = got
        res = ar.analyze_rois(cnt, [(r["rl"], r["rh"]) for r in rois], props,
                              end_points=[(r["bl"], r["bh"]) for r in rois])
        for r, a in zip(rois, res):
            total += 1
            ok_area += (a.gross == pytest.approx(r["G"], abs=1e-6)
                        and a.background == pytest.approx(r["B"], rel=1e-6, abs=1e-6)
                        and a.net == pytest.approx(r["N"], rel=1e-6, abs=1e-5)
                        and a.err_pct == pytest.approx(r["err"], rel=1e-5))
            ok_hm += np.allclose(a.fwhm_points, r["hm"], atol=0.01)
            ok_tm += np.allclose(a.fwtm_points, r["tm"], atol=0.01)
            ok_cen += a.centroid is not None and abs(a.centroid - r["cen"]) < 0.01
    assert total >= 70
    assert ok_area == total
    assert ok_hm >= total - 1
    assert ok_cen >= total - 4
    assert ok_tm >= total - 9


@pytest.mark.skipif(not SAMPLES, reason="Aptec sample spectra not installed")
def test_end_points_and_groups_match_aptec():
    total = same = 0
    for fn in SAMPLES:
        got = _read(fn)
        if got is None:
            continue
        cnt, props, rois = got
        widths = [r["rl"] - r["bl"] for r in rois]
        x = max(set(widths), key=widths.count)
        props.end_points = x
        res = ar.analyze_rois(cnt, [(r["rl"], r["rh"]) for r in rois], props)
        for r, a in zip(rois, res):
            total += 1
            same += (a.bl, a.bh) == (r["bl"], r["bh"])
    assert total >= 70 and same == total

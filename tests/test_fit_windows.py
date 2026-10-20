"""Fit windows and width-shape extrapolation (docs/baseline/fit_window_protocol.md)."""
import math

import numpy as np

from spectramaster.analysis import peaks as pk
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import NAI


def test_curvature_region_stops_at_neighbouring_peaks(monkeypatch):
    # NaI: Co-60 (ch ~391/444) next to Cs-137 (ch ~220), the reference-peak scenario
    syn, _truth, _loss = next(scenarios.reference_peak_spectra(NAI, 1))
    wide = []
    orig = pk._fit_group

    def spy(y, model, cents, lo, hi, **kw):
        c = kw.get("curvature")
        if isinstance(c, float) and math.isnan(c):
            wide.append((list(cents), lo, hi, model))
        return orig(y, model, cents, lo, hi, **kw)

    monkeypatch.setattr(pk, "_fit_group", spy)
    found = pk.find_peaks(syn.spectrum)
    cs = 661.657 / 3.0
    co = [(cents, lo, hi, m) for cents, lo, hi, m in wide if 380 < cents[0] < 400]
    assert co, "the Co-60 group has a curvature fit"
    for _cents, lo, _hi, m in co:
        assert lo >= cs + 2.5 * m.at(cs) - 1
    assert any(abs(p.centroid - cs) < 3 for p in found)


def test_width_shape_not_extrapolated():
    # strong peaks at 100, 175 and 625 keV, the two low ones 13 % wider than the model
    e = np.arange(4096) * 0.5
    f = np.sqrt(0.75 + 0.00185 * e) / 0.5
    pts = [(200, f[200] * 1.13, f[200], 50.0), (350, f[350] * 1.13, f[350], 50.0),
           (1250, f[1250], f[1250], 50.0)]
    g = pk._shape_rescale(f, pts, 10)
    r = g / f
    assert abs(r[3600] / r[1250] - 1.0) < 0.01           # 1800 keV: no trend beyond 625 keV
    assert abs(r[100] / r[200] - 1.0) < 1e-9             # below the lowest peak: held as well
    assert r[200] > 1.1 and r[1250] < 1.02                # inside the span: as fitted

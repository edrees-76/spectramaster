"""summing_free_curve chooses an automatic efficiency model again on the corrected points
(docs/baseline/close_geometry_efficiency_protocol.md)."""
from __future__ import annotations

import numpy as np
import pytest

from spectramaster.analysis import efficiency as eff
from test_tcs_safety import apparent_points, pt
from test_tcs_fixes import _apparent_curve


def _same(a, b):
    assert a.model == b.model and a.order == b.order and a.order_high == b.order_high
    assert a.e_ref == pytest.approx(b.e_ref, abs=0.0)
    np.testing.assert_array_equal(a.params, b.params)
    np.testing.assert_array_equal(a.cov, b.cov)
    assert [p.efficiency for p in a.points] == [p.efficiency for p in b.points]


def test_fit_records_how_the_model_was_chosen():
    pts = apparent_points()
    auto = eff.fit_efficiency(pts, "two_branch", crossover="auto")
    assert auto.orders_auto and auto.crossover_auto
    fixed = eff.fit_efficiency(pts, "two_branch", order=2, order_high=2, crossover=200.0)
    assert not fixed.orders_auto and not fixed.crossover_auto
    x_only = eff.fit_efficiency(pts, "two_branch", order=2, order_high=2, crossover="auto")
    assert not x_only.orders_auto and x_only.crossover_auto
    partial = eff.fit_efficiency(pts, "two_branch", order=2, crossover=200.0)
    assert not partial.orders_auto and not partial.crossover_auto
    assert eff.fit_efficiency(pts, "loglog").orders_auto
    assert not eff.fit_efficiency(pts, "loglog", order=3).orders_auto


def test_saved_curve_without_the_fields_loads_as_not_automatic():
    curve = eff.fit_efficiency(apparent_points(), "two_branch", crossover="auto")
    d = curve.to_dict()
    assert d["orders_auto"] and d["crossover_auto"]
    del d["orders_auto"], d["crossover_auto"]
    old = eff.EfficiencyCurve.from_dict(d)
    assert not old.orders_auto and not old.crossover_auto


def test_automatic_model_is_chosen_again_on_the_corrected_points():
    curve = eff.fit_efficiency(apparent_points(), "two_branch", crossover="auto")
    free = eff.summing_free_curve(curve, pt)
    assert free.summing_corrected and free.orders_auto and free.crossover_auto
    # the selection is the one an automatic fit of the corrected points makes
    again = eff.fit_efficiency(free.points, "two_branch", crossover="auto")
    assert (free.order, free.order_high, free.e_ref) == (again.order, again.order_high, again.e_ref)
    assert free.selection == again.selection


def test_explicit_model_and_old_curves_are_refitted_as_before():
    pts = apparent_points()
    auto = eff.fit_efficiency(pts, "two_branch", crossover="auto")
    fixed = eff.fit_efficiency(pts, "two_branch", order=auto.order, order_high=auto.order_high,
                               crossover=auto.e_ref)
    free_fixed = eff.summing_free_curve(fixed, pt)
    assert (free_fixed.order, free_fixed.order_high, free_fixed.e_ref) == (auto.order, auto.order_high, auto.e_ref)
    assert free_fixed.selection == fixed.selection
    d = auto.to_dict()
    del d["orders_auto"], d["crossover_auto"]
    free_old = eff.summing_free_curve(eff.EfficiencyCurve.from_dict(d), pt)
    _same(free_old, free_fixed)


def test_explicit_loglog_unchanged_and_no_cascade_untouched():
    curve, ptc = _apparent_curve(0.11)            # loglog order 1, given explicitly
    free = eff.summing_free_curve(curve, ptc)
    assert free.order == 1 and not free.orders_auto
    # Am-241 59.5 keV has cascade partners in the ENSDF table (ensdf_coincidence_protocol.md)
    flat = [p for p in apparent_points() if p.nuclide in ("Cs-137", "Mn-54", "Cd-109", "Sn-113")]
    assert len(flat) >= 2
    plain = eff.fit_efficiency(flat, "loglog", order=1)
    plain.orders_auto = True                      # an automatic curve without cascade points: untouched
    assert eff.summing_free_curve(plain, pt) is plain

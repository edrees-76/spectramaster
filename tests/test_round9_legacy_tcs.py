"""Round-9 review, Codex H1: efficiency curves saved by engine 1.26.0 and earlier keep the summing
state of their points whatever the curve flag, excluded points included
(docs/baseline/round9_legacy_tcs_protocol.md)."""
from __future__ import annotations

import pytest

from spectramaster.analysis import efficiency as ef
from spectramaster.validation import round5_tcs as r5
from spectramaster.validation import round8_coi_guard as r8
from spectramaster.validation import round9_legacy_tcs as h


@pytest.fixture(scope="module")
def files():
    return h._files()


@pytest.mark.parametrize("name", ["lost_flag", "lost_flag_resaved"])
def test_lost_flag_curve_is_not_corrected_again(files, name):
    c = h._load(files[name])
    assert not c.summing_corrected
    assert all(p.summing_coi is not None for p in c.points if p.nuclide == "Eu-152")
    f = ef.summing_free_curve(c, r5._pt, 0.1)
    ref = ef.fit_efficiency(list(c.points), c.model, order=c.order)
    assert f.summing_corrected
    assert float(f.efficiency(r8.EU121)) == pytest.approx(float(ref.efficiency(r8.EU121)), rel=1e-12)
    assert ef.TCS_ALREADY_CORRECTED in f.note


def test_excluded_corrected_points_keep_their_correction(files):
    c = h._load(files["excluded"])
    off = [p for p in c.points if not p.use]
    assert off and all(p.summing_coi is not None for p in off)
    out = h._include_all_refit(c)
    assert out["error"] is None and out["state"]["summing_corrected"]


def test_undecidable_legacy_curve_is_refused(files):
    with pytest.raises(ValueError, match="that are not"):
        ef.summing_free_curve(h._load(files["lost_flag_mixed"]), r5._pt, 0.1)


def test_uncorrected_legacy_curve_is_corrected_once(files):
    c = h._load(files["legacy_raw"])
    assert all(p.summing_coi is None for p in c.points)
    f = ef.summing_free_curve(c, r5._pt, 0.1)
    assert f.summing_corrected and ef.TCS_ALREADY_CORRECTED not in f.note

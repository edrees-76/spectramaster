"""Round-4 review, Gemini H2 (docs/baseline/round4_primary_protocol.md): the signed primary result of
a nuclide not detected is combined like the activity (key line or weighted mean of the usable window
results), and an unusable key line is replaced by the usable line of smallest MDA."""
from __future__ import annotations

from spectramaster.validation import round4_primary as rp
from spectramaster.validation.synthetic import HPGE


def test_mean_method_combines_the_usable_window_results():
    m = rp.mean_set(HPGE, n=3)
    assert m["multi_line"] > 0 and m["exact"] == m["multi_line"]
    assert m["best_present"] == m["with_usable"]


def test_interfered_key_line_is_replaced_by_the_usable_line_of_smallest_mda():
    m = rp.key_set(HPGE, n=3)
    assert m["eligible"] > 0 and m["ok"] == m["eligible"]
    assert set(m["methods"]) <= {"window", "fit"}

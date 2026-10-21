"""Deterministic tie order in the benchmark (docs/baseline/benchmark_tie_order_protocol.md)."""
from spectramaster.validation.benchmark import _by_name, _top_counts


def test_ties_are_ordered_by_name():
    counts = {"HPGe Sr-85": 15, "HPGe Fe-59": 15, "HPGe Sm-153": 39, "CZT Nb-95": 15}
    assert list(_top_counts(counts, 3).items()) == [("HPGe Sm-153", 39), ("CZT Nb-95", 15), ("HPGe Fe-59", 15)]


def test_order_does_not_depend_on_insertion_order():
    items = [("b", 2), ("a", 2), ("c", 3), ("d", 1), ("e", 2)]
    assert _top_counts(dict(items), 4) == _top_counts(dict(reversed(items)), 4)
    assert list(_top_counts(dict(reversed(items)), 4)) == ["c", "a", "b", "e"]


def test_n_larger_than_the_dictionary():
    assert _top_counts({"x": 1, "y": 1}, 15) == {"x": 1, "y": 1}
    assert _top_counts({}, 15) == {}


def test_by_name_orders_keys_and_keeps_counts():
    a = _by_name({"Y-88": 2, "Al-26": 1, "Sb-124": 3})
    b = _by_name({"Sb-124": 3, "Y-88": 2, "Al-26": 1})
    assert list(a.items()) == list(b.items()) == [("Al-26", 1), ("Sb-124", 3), ("Y-88", 2)]

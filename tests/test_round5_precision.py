"""Round-5 review, M4: full-precision proof of the round-4 activity criteria (round5_precision_protocol.md)."""
import json

from spectramaster.validation import round4_activity as r4
from spectramaster.validation import round5_precision as r5


def test_full_precision_before_values_and_criteria(monkeypatch):
    for k, v in r4.AFTER_R7C.items():     # RF.C4: the blank cases since engine 1.29.0
        monkeypatch.setitem(r4.BEFORE, k, v)
    r114 = json.loads(r5.RUN_114.read_text(encoding="utf-8"))
    r115 = json.loads(r5.RUN_115.read_text(encoding="utf-8"))
    cur = r4.run()
    c = r5.criteria(cur, r114, r115)
    assert all(ok for k, (ok, _v) in c.items() if k != "RF.C2"), c
    # RF.C2: the current engine as 1.14.0 but for the blank cases changed by engine 1.29.0
    # (round7_shared_background_protocol.md); r4.AFTER_R7C holds those
    a = r4.AFTER_R7C
    want = r5.quantities(r114)
    want[0], want[3:7] = a["C1_threshold"], [*a["C2_no_reference"], *a["C3_currie"]]
    assert all(r5._rel(x, y) <= 1e-9 for x, y in zip(r5.quantities(cur), want))


def test_before_is_the_full_precision_run():
    assert r4.BEFORE["C1_threshold"] == 13.70672112504547
    assert r4.BEFORE["C4"][1] == 0.958093894653114

"""Round-5 review, M4: full-precision proof of the round-4 activity criteria (round5_precision_protocol.md)."""
import json

from spectramaster.validation import round4_activity as r4
from spectramaster.validation import round5_precision as r5


def test_full_precision_before_values_and_criteria():
    r114 = json.loads(r5.RUN_114.read_text(encoding="utf-8"))
    r115 = json.loads(r5.RUN_115.read_text(encoding="utf-8"))
    c = r5.criteria(r4.run(), r114, r115)
    assert all(ok for ok, _v in c.values()), c


def test_before_is_the_full_precision_run():
    assert r4.BEFORE["C1_threshold"] == 13.70672112504547
    assert r4.BEFORE["C4"][1] == 0.958093894653114

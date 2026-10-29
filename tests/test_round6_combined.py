"""Round-6 review, H1: combined limits with a blank and a reference peak (round6_combined_protocol.md)."""
import math

import pytest

from spectramaster.validation import round6_combined as r6


@pytest.mark.parametrize("case", r6.CASES, ids=[c[0] for c in r6.CASES])
def test_combined_limits_match_full_covariance(case):
    name, mda, lines, blank, uc, buc, ur = case
    res, o = r6._run(mda, lines, blank, uc, buc, ur)
    assert len(res.used_energies) == 2
    ind = r6.independent(res, o, mda, uc, buc, ur)
    assert math.isclose(res.decision_threshold, ind["threshold"], rel_tol=1e-9)
    assert math.isclose(res.mda, ind["limit"], rel_tol=1e-9)


def test_no_blank_no_cross_terms():
    _name, mda, lines, _blank, uc, buc, ur = r6.CASES[3]
    res, _o = r6._run(mda, lines, None, uc, buc, ur)
    # no blank: the reference peak terms are zero at zero activity, so no cross term at that level
    # (round7_combined_protocol.md: ref_g0 is (0, 0, 0) for a line without a blank peak)
    assert all(l.ref_g0 in (None, [0.0, 0.0, 0.0]) for l in res.lines)

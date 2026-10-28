"""Round-6 review, H3/L1: partial summing correction state of an efficiency curve (round6_tcs_state_protocol.md)."""
from spectramaster.analysis import coincidence as co
from spectramaster.analysis import efficiency as ef
from spectramaster.validation import round6_tcs_state as r6
from spectramaster.validation import round5_tcs as r5


def test_partial_state_survives_save_and_old_files():
    cs = r6._curves()["eu_ba_121.8"]
    want = cs["free"].tcs_partial
    assert [(n, e) for n, e, _w in want] == [("Ba-133", 276.4), ("Ba-133", 302.9), ("Ba-133", 356.0),
                                             ("Ba-133", 383.8)]
    assert cs["loaded"].tcs_partial == want and cs["legacy"].tcs_partial == want
    assert "tcs_partial" not in r6._curves()["eu_only"]["free"].to_dict()


def test_partial_state_reaches_results_and_report():
    cs = r6._curves()["eu_ba_121.8"]
    for tcs in (True, False):
        q = r6._quant(cs["loaded"], tcs)
        assert q.curve_tcs_partial == cs["free"].tcs_partial
        assert sum("Ba-133 356 keV" in n for n in q.notes) == 1
        assert "partial true-coincidence summing correction" in q.nuclides[0].note
        rep = r6._report(cs["loaded"], q)
        assert rep["calibration"]["tcs_partial"] == cs["free"].tcs_partial
        assert sum("partial true-coincidence summing" in s["message"] for s in rep["statuses"]) == 1


def test_ignored_wording_is_not_a_fraction_of_decays():
    c = co.coi("Ba-133", 356.0129, r5._flat(0.02), r5._flat(0.24), e_min=122.0)
    assert "% of decays" not in c.partial_reason and "0.37 per emission" in c.partial_reason


def test_legacy_note_without_partial_gives_empty_list():
    assert ef.legacy_tcs_partial({"summing_corrected": True, "note": "corrected"}) == []

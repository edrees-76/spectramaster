"""Round-7 review, input validation, Codex M1 / Gemini M4 (docs/baseline/round7_inputs_protocol.md)."""
import math

import pytest

from spectramaster.validation import round7_inputs as h


@pytest.mark.parametrize("text", h.QC_BAD)
def test_qc_line_texts_are_refused(text):
    pytest.importorskip("PySide6")
    from spectramaster.gui.qc_window import parse_lines
    with pytest.raises(ValueError):
        parse_lines(text)


@pytest.mark.parametrize("name", list(h.CSV_BAD))
def test_certificate_csv_is_refused(tmp_path, name):
    from spectramaster.analysis import efficiency as eff
    p = tmp_path / "c.csv"
    p.write_text(h.CSV_BAD[name], encoding="utf-8")
    with pytest.raises(ValueError):
        eff.read_certificate_csv(p)


def test_certificate_rows_of_one_nuclide_give_its_lines(tmp_path):
    from spectramaster.analysis import efficiency as eff
    p = tmp_path / "c.csv"
    p.write_text(h.CSV_GOOD["second row date written otherwise"], encoding="utf-8")
    (c,) = eff.read_certificate_csv(p)
    assert c.activity == 1000.0 and c.lines == [(121.78, 0.285), (344.28, 0.266)]


@pytest.mark.parametrize("name", list(h.APTEC_BAD))
def test_aptec_record_is_refused(name):
    from spectramaster.analysis.efficiency import certificate_from_aptec
    with pytest.raises(ValueError):
        certificate_from_aptec([h._rec(), h._rec(**h.APTEC_BAD[name])])


def test_aptec_empty_slots_are_skipped():
    from spectramaster.analysis.efficiency import certificate_from_aptec
    lines = certificate_from_aptec([h._rec()] + [h._rec(**kw) for kw in h.APTEC_SKIP.values()])
    assert len(lines) == 1 and math.isclose(lines[0].activity_unc, 20.0)


def test_negative_activity_is_refused_and_the_value_kept():
    pytest.importorskip("PySide6")
    r = h.c5()
    assert all(h._refused(r[repr(v)]) for v in h.SET_BAD) and math.isclose(r["after a refusal"], 12345.678, rel_tol=1e-12)


@pytest.mark.parametrize("col,text", [(4, "0,02"), (4, "-0.01"), (2, "-100"), (5, "1,5"), (5, "")])
def test_invalid_manual_point_blocks_fit_and_save(col, text):
    pytest.importorskip("PySide6")
    v = h._point_case(col, text)
    assert not v["refit"] and not v["curve"] and not v["saved"] and v["shown"] == text
    assert any("row 1" in s.lower() for s in v["messages"])
    assert v["point"] == [h.MANUAL[0][0], h.MANUAL[0][1], h.MANUAL[0][2] / 100.0]


def test_valid_manual_point_edit_is_fitted():
    pytest.importorskip("PySide6")
    v = h._point_case(4, "0.02")
    assert v["refit"] and v["saved"] and not v["messages"] and v["point"][1] == 0.02

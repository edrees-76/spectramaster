"""Round-8 review, Codex M1-M3: an ambiguous comma, the mass/volume uncertainty and a non-finite
activity typed in the GUI are refused, never guessed or read as 0."""
import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from spectramaster.analysis import activity as act  # noqa: E402
from spectramaster.gui.number_text import decimal_text, is_ambiguous  # noqa: E402

# text -> value, or None for "refused"
TABLE = [
    ("1,000", None), ("1,000,000", None), ("12,500,000", None), ("-1,000", None), ("+1,000", None),
    ("1.000,5", None), ("1,000.5", None), ("0,500", 0.5), ("0,125", 0.125), ("-0,250", -0.25),
    ("0,5", 0.5), ("1,25", 1.25), ("1500,5", 1500.5), ("1,5e3", 1500.0), (" 0,5 ", 0.5),
    ("1000", 1000.0), ("1.5", 1.5), ("-2,5", -2.5), ("1,0000", 1.0), ("12,34", 12.34),
    ("٠,٥", 0.5), ("١,٠٠٠", None), ("١٢٣", 123.0),          # Arabic-Indic digits (float() reads them)
]


def _parse(text):
    try:
        return float(decimal_text(text))
    except ValueError:
        return None


@pytest.mark.parametrize("text,want", TABLE)
def test_decimal_comma_rule(text, want):
    got = _parse(text)
    assert got == (None if want is None else pytest.approx(want))
    assert is_ambiguous(text) == (want is None)


def test_empty_text_stays_empty():
    assert decimal_text("") == "" and decimal_text("  ") == "" and decimal_text(None) == ""


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, -0.1, "abc", None])
def test_quantity_rel_unc_refused(bad):
    with pytest.raises(ValueError):
        act.check_quantity_rel_unc(bad)
    with pytest.raises(ValueError, match="quantity relative uncertainty"):
        act.compute_activities(None, None, act.ActivityOptions(quantity_rel_unc=bad))


@pytest.mark.parametrize("good", [0, 0.0, 0.05])
def test_quantity_rel_unc_accepted(good):
    assert act.check_quantity_rel_unc(good) == good


@pytest.fixture(scope="module")
def res():
    from spectramaster.validation.benchmark import _flat_curve
    from spectramaster.validation.synthetic import HPGE, Continuum, TruePeak, make_spectrum
    syn = make_spectrum(HPGE, [TruePeak(661.657, 2e4)], Continuum(300, 400, 10), 7)
    return act.compute_activities(syn.spectrum, _flat_curve(), act.ActivityOptions(nuclides=["Cs-137"]))


def _soil():
    from spectramaster.lab.sample import SampleInfo
    return SampleInfo(matrix_type="soil", mass_kg=0.5, mass_basis="dry")


@pytest.mark.parametrize("bad", [math.nan, math.inf, -0.1])
def test_concentrations_refuse_a_bad_quantity_uncertainty(res, bad):
    with pytest.raises(ValueError, match="quantity relative uncertainty"):
        act.concentrations(res, _soil(), "Bq/kg", quantity_rel_unc=bad)


@pytest.mark.parametrize("good", [0.0, 0.05])
def test_concentrations_accept_a_valid_quantity_uncertainty(res, good):
    out = act.concentrations(res, _soil(), "Bq/kg", quantity_rel_unc=good)
    cs = next(r for r in out["rows"] if r["nuclide"] == "Cs-137")
    a = res.nuclides[0]
    assert cs["u"] == pytest.approx(cs["value"] * math.hypot(a.u / a.activity, good))


# ------------------------------------------------------------------ GUI
@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(["round8"])


def _sample(app):
    from spectramaster.gui.sample_panel import SampleSection
    w = SampleSection()
    w.set_unit("Bq/kg")
    return w


@pytest.mark.parametrize("text", ["1,000", "1,000,000", "1.000,5"])
def test_sample_mass_refuses_an_ambiguous_comma(app, text):
    w = _sample(app)
    w._num["mass_kg"].setText(text)
    with pytest.raises(ValueError, match=text.replace(".", r"\.")):
        w.sample_info()
    w.close()


@pytest.mark.parametrize("text,want", [("0,5", 0.5), ("1500,5", 1500.5), ("2", 2.0)])
def test_sample_mass_reads_a_decimal_comma(app, text, want):
    w = _sample(app)
    w._num["mass_kg"].setText(text)
    w.basis_combo.setCurrentIndex(max(0, w.basis_combo.findData("dry")))
    assert w.sample_info().mass_kg == pytest.approx(want)
    w.close()


@pytest.mark.parametrize("text", ["nan", "inf", "-inf", "-5", "1,000"])
def test_sample_quantity_uncertainty_refused(app, text):
    w = _sample(app)
    w._num["quantity_rel_unc_pct"].setText(text)
    with pytest.raises(ValueError):
        w.quantity_rel_unc()
    w.close()


@pytest.mark.parametrize("text,want", [("", 0.0), ("0", 0.0), ("5", 0.05), ("2,5", 0.025)])
def test_sample_quantity_uncertainty_accepted(app, text, want):
    w = _sample(app)
    w._num["quantity_rel_unc_pct"].setText(text)
    assert w.quantity_rel_unc() == pytest.approx(want)
    w.close()


def test_quant_panel_uncertainty_box_holds_no_bad_value(app):
    from spectramaster.gui.quant_panel import ActivityDialog
    p = ActivityDialog(None, None, None)
    for v in (math.nan, math.inf, -5.0):
        p.qty_unc.setValue(v)
        u = p.options().quantity_rel_unc
        assert math.isfinite(u) and u >= 0
        assert act.check_quantity_rel_unc(u) == u
    p.close()


@pytest.mark.parametrize("text", ["nan", "inf", "-inf", "abc", "-5", "1e400"])
def test_activity_input_refuses_non_finite(app, text):
    from spectramaster.gui.activity_input import ActivityInput
    w = ActivityInput(1000.0)
    w.number.setText(text)
    assert not w.is_valid()
    with pytest.raises(ValueError):
        w.value_bq()
    w.set_unit("kBq")                     # a unit change keeps the invalid text, no exception
    assert w.number.text() == text and w.current_unit() == "kBq"
    w.close()


def test_activity_input_valid_and_empty(app):
    from spectramaster.gui.activity_input import ActivityInput
    w = ActivityInput()
    w.number.setText("")
    assert w.value_bq() == 0.0
    w.number.setText("2")
    w.set_unit("kBq")
    assert w.value_bq() == pytest.approx(2.0)
    w.close()


def test_acceptance_dialog_shows_an_invalid_activity(app):
    from spectramaster.gui import detector_test_dialog as dd
    from spectramaster.validation import detector_acceptance as da
    area, _ref = da._area_for(40.0, 5.0)
    dlg = dd.AcceptanceDialog(da.build(0.5, 2.0, area))
    shown = []
    dlg._error = shown.append
    dlg.activity.number.setText("nan")
    assert dlg.calculate() is None
    assert shown and "nan" in shown[0]
    dlg.close()


def test_geometry_and_detector_fields_refuse_an_ambiguous_comma():
    pytest.importorskip("PySide6")
    from spectramaster.gui import detector_picker, geometry_editor
    from spectramaster.gui.aptec_edit_ui import parse_half_life
    with pytest.raises(ValueError):
        geometry_editor._parse("1,000")
    assert geometry_editor._parse("0,5") == 0.5
    with pytest.raises(ValueError):
        detector_picker._num("1,000", "Distance:")
    assert detector_picker._num("1,5", "Distance:") == 1.5
    for t in ("1,000 y", "1,000y", "1.000,5 d"):
        with pytest.raises(ValueError):
            parse_half_life(t)
    assert parse_half_life("30,08 y") == pytest.approx(30.08 * parse_half_life("1 y"))
    assert parse_half_life("2,5h") == pytest.approx(9000.0)

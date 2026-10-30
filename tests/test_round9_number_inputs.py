"""Round-9 review, Codex M1 / L1 and Gemini L3: a thousands grouping hidden by an exponent or a sign
is refused, an Arabic-Indic leading zero is a decimal comma like "0,500", and the activity input
reads a decimal comma like every other GUI number field."""
import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from spectramaster.gui.number_text import decimal_text, is_ambiguous  # noqa: E402

AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# text -> value, or None for "refused"
TABLE = [
    # Codex M1: the mantissa is checked without its exponent and sign
    ("1,000e0", None), ("1,000E3", None), ("-1,000e-2", None), ("+1,000e+2", None), ("1,000,000e0", None),
    ("12,500e1", None), (" 1,000e3 ", None),
    # unchanged meanings
    ("0,5e3", 500.0), ("1500,5e0", 1500.5), ("1e3", 1000.0), ("1.5e3", 1500.0), ("1,5e3", 1500.0),
    ("-0,500e1", -5.0), ("0,500", 0.5), ("1,000", None), ("1.000,5", None), ("1,000.5", None),
    ("-1,000", None), ("12,34", 12.34), ("1,0000", 1.0),
    # Codex L1: Arabic-Indic and Eastern Arabic-Indic zero
    ("0,500".translate(AR), 0.5), ("-0,250".translate(AR), -0.25), ("0,125".translate(FA), 0.125),
    ("1,000".translate(AR), None), ("1,000".translate(FA), None), ("1,000e3".translate(AR), None),
    ("0,5e3".translate(AR), 500.0),
]


def _parse(text):
    try:
        return float(decimal_text(text))
    except ValueError:
        return None


@pytest.mark.parametrize("text,want", TABLE)
def test_grouping_with_exponent_sign_and_arabic_digits(text, want):
    got = _parse(text)
    assert got == (None if want is None else pytest.approx(want))
    assert is_ambiguous(text) == (want is None)


def test_message_keeps_the_text_as_typed():
    typed = "1,000".translate(AR)
    with pytest.raises(ValueError, match=typed):
        decimal_text(typed)


# ------------------------------------------------------------------ GUI
@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(["round9"])


@pytest.mark.parametrize("text", ["1,000e0", "1,000E3", "-1,000e-2"])
def test_sample_mass_refuses_grouping_with_exponent(app, text):
    from spectramaster.gui.sample_panel import SampleSection
    w = SampleSection()
    w.set_unit("Bq/kg")
    w._num["mass_kg"].setText(text)
    with pytest.raises(ValueError, match=text.replace("+", r"\+")):
        w._float("mass_kg", "conc_mass")
    w.close()


@pytest.mark.parametrize("text,bq", [("0,5", 500.0), ("12,5", 12500.0), ("1,5e3", 1.5e6),
                                     ("0,500", 500.0), ("1.5", 1500.0), ("2", 2000.0)])
def test_activity_input_reads_a_decimal_comma(app, text, bq):
    from spectramaster.gui.activity_input import ActivityInput
    w = ActivityInput(unit="kBq")
    w.number.setText(text)
    assert w.is_valid()
    assert w.value_bq() == pytest.approx(bq)
    w.close()


@pytest.mark.parametrize("text", ["0,5", "12,5", "0,5e3", "1.5e-3"])
def test_activity_input_lets_a_decimal_comma_be_typed(app, text):
    from PySide6.QtGui import QValidator
    from spectramaster.gui.activity_input import ActivityInput
    w = ActivityInput()
    state = w.number.validator().validate(text, len(text))[0]
    assert state == QValidator.State.Acceptable
    w.close()


@pytest.mark.parametrize("text", ["1,000", "1,000e3", "1.000,5", "nan", "inf", "-5", "-0,5", "1e400", "abc"])
def test_activity_input_still_refuses(app, text):
    from spectramaster.gui.activity_input import ActivityInput
    w = ActivityInput(1000.0)
    w.number.setText(text)
    assert not w.is_valid()
    with pytest.raises(ValueError):
        w.value_bq()
    w.close()


def test_activity_input_unit_change_converts_a_decimal_comma(app):
    from spectramaster.gui.activity_input import ActivityInput
    w = ActivityInput(unit="kBq")
    w.number.setText("1,5")
    w.set_unit("Bq")
    assert w.value_bq() == pytest.approx(1500.0)
    assert math.isclose(float(w.number.text()), 1500.0)
    w.close()

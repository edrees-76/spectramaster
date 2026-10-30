"""Source activity in several units: a number with a unit list (Bq ... TBq, Ci ... pCi), held in Bq.
The conversion factors are those of analysis/decay_calc.py (1 Ci = 3.7e10 Bq)."""
from __future__ import annotations

import math
import re
from typing import Optional

from PySide6.QtCore import QRegularExpression, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QWidget

from ..analysis.decay_calc import ACTIVITY_UNITS
from .number_text import decimal_text

# units offered for a source, in this order; "µCi" is shown for the "uCi" of decay_calc
UNITS = ("Bq", "kBq", "MBq", "GBq", "TBq", "Ci", "mCi", "µCi", "nCi", "pCi")
_KEY = {"µCi": "uCi"}


def factor(unit: str) -> float:
    """Bq per `unit` ("µCi" and "uCi" both accepted)."""
    u = unit.strip()
    try:
        return ACTIVITY_UNITS[_KEY.get(u, u)]
    except KeyError:
        raise ValueError(f"unknown activity unit {unit!r}") from None


def to_bq(value: float, unit: str) -> float:
    return float(value) * factor(unit)


def from_bq(bq: float, unit: str) -> float:
    return float(bq) / factor(unit)


_NUM_UNIT = re.compile(r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)(?:\s*([A-Za-zµ]+))?")


def parse_activity(text: str, default_unit: str = "Bq") -> float:
    """Bq of "37000", "37 kBq", "1uCi", "1 µCi" ...  A comma in the number (thousands separator or
    decimal comma: ambiguous) and a value that is not finite are refused."""
    m = _NUM_UNIT.fullmatch(text.strip())
    if m is None:
        raise ValueError(f"not an activity: {text!r} (use a point for decimals, no thousands separator)")
    bq = to_bq(float(m.group(1)), m.group(2) or default_unit)
    if not math.isfinite(bq):
        raise ValueError(f"not a finite activity: {text!r}")
    return bq


def format_activity(bq: float, unit: str = "Bq", digits: int = 5) -> str:
    return f"{from_bq(bq, unit):.{digits}g} {unit}"


# what can be typed in ActivityInput (ASCII, Arabic-Indic and Eastern Arabic-Indic digits)
_DIGIT = r"[0-9\x{0660}-\x{0669}\x{06F0}-\x{06F9}]"
_TYPED = f"{_DIGIT}*[.,]?{_DIGIT}*(?:[eE][-+]?{_DIGIT}*)?"


class ActivityInput(QWidget):
    """A number and its unit; ``value_bq()`` / ``set_bq()``.  Changing the unit converts the number
    shown, so the activity stays the same.  A text field (6 significant digits, scientific notation
    accepted), not a spin box: 37 kBq is 1e-6 Ci."""
    changed = Signal()

    def __init__(self, bq: float = 0.0, unit: str = "Bq", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.number = QLineEdit()
        # digits, a decimal point or comma and an exponent; the text is read by decimal_text, which
        # refuses an ambiguous "1,000" (round-9 review, Gemini L3: "0,5" was blocked here)
        self.number.setValidator(QRegularExpressionValidator(QRegularExpression(_TYPED), self.number))
        self.unit = QComboBox()
        self.unit.addItems(list(UNITS))
        self.unit.setCurrentText(unit if unit in UNITS else "Bq")
        self._unit = self.unit.currentText()
        self._shown = (0.0, "")
        lay.addWidget(self.number, 1)
        lay.addWidget(self.unit)
        self.set_bq(bq)
        self.unit.currentTextChanged.connect(self._unit_changed)
        self.number.textChanged.connect(lambda _t: self.changed.emit())

    def _number(self) -> float:
        """The number typed; 0 for an empty field.  ValueError for a text that is not a finite number
        >= 0 ("nan", "inf", "abc", "-5"): refused, never read as 0 (round-8 review, Codex M3).  A decimal
        comma is read ("0,5"), an ambiguous comma ("1,000", "1,000e3") refused (round-9 review, Gemini L3)."""
        text = self.number.text().strip()
        if not text:
            return 0.0
        try:
            x = float(decimal_text(text))
        except ValueError:
            raise ValueError(f"not an activity: {text!r} (a finite number, no thousands separator)") from None
        if not (math.isfinite(x) and x >= 0):
            raise ValueError(f"not a finite activity, not negative: {text!r}")
        return x

    def value_bq(self) -> float:
        """The activity in Bq (0 for an empty field); ValueError for an invalid text (:meth:`_number`)."""
        if self.number.text() == self._shown[1]:          # not edited since set: the exact value
            return self._shown[0]
        bq = to_bq(self._number(), self._unit)
        if not math.isfinite(bq):                         # e.g. 1e300 TBq
            raise ValueError(f"not a finite activity: {self.number.text()!r} {self._unit}")
        return bq

    def is_valid(self) -> bool:
        try:
            self.value_bq()
        except ValueError:
            return False
        return True

    def set_bq(self, bq: float) -> None:
        if not math.isfinite(bq) or bq < 0:       # round6_inputs_protocol.md, round7_inputs_protocol.md
            raise ValueError(f"not a finite activity, not negative: {bq!r} Bq")
        text =f"{from_bq(bq, self._unit):.6g}" if bq else ""
        self._shown = (float(bq), text)
        self.number.setText(text)

    def current_unit(self) -> str:
        return self._unit

    def set_unit(self, unit: str) -> None:
        self.unit.setCurrentText(unit)

    def _unit_changed(self, unit: str) -> None:
        try:
            bq = self.value_bq()
        except ValueError:                    # an invalid text stays as typed (refused when used)
            self._unit = unit
            self.changed.emit()
            return
        self._unit = unit
        self.number.blockSignals(True)
        self.set_bq(bq)
        self.number.blockSignals(False)
        self.changed.emit()


def other_units(bq: float, shown: Optional[str] = None) -> str:
    """The activity in Bq and in the unit `shown` (when it is not Bq), e.g. "37000 Bq = 1 µCi"."""
    text = format_activity(bq, "Bq")
    if shown and shown != "Bq":
        text += " = " + format_activity(bq, shown)
    return text

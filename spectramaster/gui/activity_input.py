"""Source activity in several units: a number with a unit list (Bq ... TBq, Ci ... pCi), held in Bq.
The conversion factors are those of analysis/decay_calc.py (1 Ci = 3.7e10 Bq)."""
from __future__ import annotations

import re
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QWidget

from ..analysis.decay_calc import ACTIVITY_UNITS

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
    """Bq of "37000", "37 kBq", "1uCi", "1 µCi" ..."""
    m = _NUM_UNIT.fullmatch(text.replace(",", "").strip())
    if m is None:
        raise ValueError(f"not an activity: {text!r}")
    return to_bq(float(m.group(1)), m.group(2) or default_unit)


def format_activity(bq: float, unit: str = "Bq", digits: int = 5) -> str:
    return f"{from_bq(bq, unit):.{digits}g} {unit}"


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
        v = QDoubleValidator(0.0, 1e18, 12, self.number)
        v.setNotation(QDoubleValidator.ScientificNotation)
        self.number.setValidator(v)
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
        try:
            return float(self.number.text().replace(",", "") or 0.0)
        except ValueError:
            return 0.0

    def value_bq(self) -> float:
        if self.number.text() == self._shown[1]:          # not edited since set: the exact value
            return self._shown[0]
        return to_bq(self._number(), self._unit)

    def set_bq(self, bq: float) -> None:
        text = f"{from_bq(bq, self._unit):.6g}" if bq else ""
        self._shown = (float(bq), text)
        self.number.setText(text)

    def current_unit(self) -> str:
        return self._unit

    def set_unit(self, unit: str) -> None:
        self.unit.setCurrentText(unit)

    def _unit_changed(self, unit: str) -> None:
        bq = self.value_bq()
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

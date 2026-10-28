"""Source activities in several units (gui/activity_input.py): conversion, parsing, the input field,
the certificate table of the efficiency calibration and the QC reference activity."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from spectramaster.gui import activity_input as ai


def test_conversion_and_parsing():
    assert ai.to_bq(1, "Ci") == 3.7e10
    assert ai.to_bq(1, "µCi") == ai.to_bq(1, "uCi") == pytest.approx(37000.0)
    assert ai.from_bq(3.7e7, "mCi") == pytest.approx(1.0)
    assert ai.to_bq(2.5, "kBq") == 2500.0
    for text, bq in (("37000", 37000.0), ("37 kBq", 37000.0), ("1uCi", 37000.0), ("1 µCi", 37000.0),
                     ("3.7e4", 37000.0), ("0.5 MBq", 5e5)):
        assert ai.parse_activity(text) == pytest.approx(bq), text
    for bad in ("1 furlong", "1,000 Bq"):         # a comma in the number is ambiguous (round5_acceptance_protocol.md)
        with pytest.raises(ValueError):
            ai.parse_activity(bad)
    assert ai.other_units(37000.0, "µCi") == "37000 Bq = 1 µCi"


@pytest.fixture(scope="module")
def qapp():
    from spectramaster.gui.app import create_app
    return create_app(["test"])


def test_input_field_keeps_the_activity_when_the_unit_changes(qapp):
    w = ai.ActivityInput(12345.678)
    assert w.value_bq() == 12345.678
    for u in ("Ci", "pCi", "MBq", "Bq"):
        w.set_unit(u)
        assert w.value_bq() == 12345.678          # exact while the number is not edited
    w.set_unit("µCi")
    w.number.setText("2")
    assert w.value_bq() == pytest.approx(74000.0)
    w.set_unit("kBq")
    assert w.number.text() == "74"


def test_certificate_table_unit(qapp):
    from datetime import datetime
    from spectramaster.analysis import efficiency as eff
    from spectramaster.gui.efficiency_dialog import CertificateEditor
    ed = CertificateEditor()
    ed.set_certificate([eff.CertNuclide("Cs-137", 37000.0, 740.0, datetime(2020, 1, 1))])
    ed.set_activity_unit("µCi")
    assert ed.cert_table.item(0, 1).text() == "1"
    assert "µCi" in ed.cert_table.horizontalHeaderItem(1).text()
    c = ed.certificate()[0]
    assert c.activity == pytest.approx(37000.0) and c.activity_unc == pytest.approx(740.0)
    ed.cert_table.item(0, 1).setText("2")
    assert ed.certificate()[0].activity == pytest.approx(74000.0)
    ed.add_cert_row(eff.CertNuclide("Co-60", 3.7e6, 0.0, None))
    assert ed.cert_table.item(1, 1).text() == "100"


def test_qc_reference_activity_with_units():
    from spectramaster.gui.qc_window import _parse_activity
    assert _parse_activity("Cs-137=37000, Co-60=1 uCi; Am-241=2 kBq") == pytest.approx(
        {"Cs-137": 37000.0, "Co-60": 37000.0, "Am-241": 2000.0})

"""Round-6 review, input validation (round6_inputs_protocol.md)."""
import math
import os
from dataclasses import replace
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from spectramaster.analysis import detector_test as dt  # noqa: E402
from spectramaster.analysis import efficiency as eff  # noqa: E402
from spectramaster.validation import round6_inputs as r6  # noqa: E402


@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PySide6")
    return r6._app()


def _editor(app, *entries):
    from spectramaster.gui.efficiency_dialog import CertificateEditor
    ed = CertificateEditor()
    ed.set_certificate(list(entries))
    return ed


def test_unit_change_keeps_the_uncertainty_of_an_edited_activity(app):
    ed = _editor(app, eff.CertNuclide("Cs-137", 1000.0, 20.0, None))
    ed.cert_table.item(0, 1).setText("2000")
    ed.set_activity_unit("kBq")
    c = ed.certificate()[0]
    assert (c.activity, c.activity_unc) == (2000.0, 40.0)


@pytest.mark.parametrize("col,text", r6.CERT_BAD)
def test_certificate_cell_refused(app, col, text):
    ed = _editor(app, eff.CertNuclide("Cs-137", 1000.0, 20.0, None, 9.49e8))
    ed.cert_table.item(0, col).setText(text)
    with pytest.raises(ValueError, match="row 1"):
        ed.certificate()


@pytest.mark.parametrize("label", sorted(r6.CSV_BAD))
def test_certificate_csv_row_refused(tmp_path, label):
    p = tmp_path / "c.csv"
    p.write_text(r6.CSV_HEAD + r6.CSV_BAD[label], encoding="utf-8")
    with pytest.raises(ValueError, match="row 1"):
        eff.read_certificate_csv(p)


@pytest.mark.parametrize("label", sorted(r6.LINE_BAD))
def test_measure_efficiency_refuses_invalid_line(label):
    good = eff.CertLine("Cs-137", 661.657, 0.851, 1000.0, 20.0, datetime(2020, 1, 1, 12), 9.49e8, 0.002)
    with pytest.raises(ValueError, match="Cs-137"):
        eff.measure_efficiency(r6._cs_spectrum(), [replace(good, **r6.LINE_BAD[label])])


@pytest.mark.parametrize("fn", [dt.net_area, dt.peak_to_compton, lambda s: dt.relative_efficiency(s, 37000.0)])
def test_detector_test_refuses_non_finite_counts(fn):
    sp = r6._co60_spectrum()
    sp.counts[2666] = math.nan
    with pytest.raises(ValueError, match="not numbers"):
        fn(sp)


@pytest.mark.parametrize("text", r6.COUNTS_BAD)
def test_parse_counts_refuses(text):
    pytest.importorskip("PySide6")                  # the module imports Qt; no application is needed
    from spectramaster.gui.detector_test_dialog import parse_counts
    with pytest.raises(ValueError):
        parse_counts(text)


def test_qc_activity():
    pytest.importorskip("PySide6")
    from spectramaster.gui.qc_window import _parse_activity
    assert _parse_activity("Cs137=37000, Co60=1 uCi") == {"Cs-137": 37000.0, "Co-60": 37000.0}
    for text in r6.QC_BAD:
        with pytest.raises(ValueError):
            _parse_activity(text)


def test_set_bq_refuses_non_finite(app):
    from spectramaster.gui.activity_input import ActivityInput
    w = ActivityInput()
    with pytest.raises(ValueError):
        w.set_bq(math.inf)
    w.set_bq(12345.678)
    assert w.value_bq() == 12345.678

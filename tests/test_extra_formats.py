"""Tests for Excel (code 50) and JSON (code 51)."""
from __future__ import annotations

import json
from datetime import datetime

import pytest

from spectramaster.formats import FormatError, detect_format, get_format, load_all
from spectramaster.model import Spectrum

load_all()


def make_spectrum(**kw):
    d = dict(counts=[0.0, 5.0, 12.0, 1e6, 3.5], energy_coeffs=[1.0, 0.5, 1e-4],
             live_time=100.0, real_time=110.5, start_time=datetime(2021, 3, 4, 5, 6, 7),
             sample_id="عينة 1", description="first\nsecond", detector="GeHP",
             first_channel=2, fwhm_coeffs=[0.9, 0.001], extra={"lab": "LAEO", "n": 3})
    d.update(kw)
    return Spectrum(**d)


def test_codes():
    assert get_format(50).key == "excel_xlsx"
    assert get_format(51).key == "json"
    assert get_format("xlsx").code == 50


def test_json_roundtrip(tmp_path):
    sp = make_spectrum()
    p = tmp_path / "s.json"
    get_format("json").writer(sp, p)
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert doc["format"] == "spectramaster-spectrum" and doc["version"] == 1
    assert detect_format(p).key == "json"
    r = get_format("json").reader(p)[0]
    for attr in ("counts", "energy_coeffs", "live_time", "real_time", "start_time", "sample_id",
                 "description", "detector", "first_channel", "fwhm_coeffs", "extra"):
        assert getattr(r, attr) == getattr(sp, attr), attr


def test_json_bare_object_and_list(tmp_path):
    p = tmp_path / "b.json"
    p.write_text(json.dumps([{"counts": [1, 2, 3], "energy_coeffs": [0, 1]}]))
    r = get_format("json").reader(p)
    assert r[0].counts == [1.0, 2.0, 3.0] and r[0].energy_of(2) == 2.0


def test_json_invalid(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    with pytest.raises(FormatError):
        get_format("json").reader(p)
    p.write_text('{"spectra": [{"no_counts": 1}]}')
    with pytest.raises(FormatError):
        get_format("json").reader(p)


def test_xlsx_roundtrip(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    sp = make_spectrum()
    p = tmp_path / "s.xlsx"
    get_format("excel_xlsx").writer(sp, p)
    wb = openpyxl.load_workbook(p)
    assert wb.sheetnames == ["Spectrum", "Info"]
    ws = wb["Spectrum"]
    assert [c.value for c in ws[1]] == ["Channel", "Energy (keV)", "Counts"]
    assert ws["A2"].value == 2
    assert ws["B2"].value == pytest.approx(sp.energy_of(2))
    assert ws["C5"].value == 1000000
    assert detect_format(p).key == "excel_xlsx"
    r = get_format("excel_xlsx").reader(p)[0]
    assert r.counts == sp.counts
    assert r.first_channel == 2
    assert r.energy_coeffs == sp.energy_coeffs
    assert r.fwhm_coeffs == sp.fwhm_coeffs
    assert r.start_time == sp.start_time
    assert (r.live_time, r.real_time) == (100.0, 110.5)
    assert r.sample_id == sp.sample_id and r.description == sp.description
    assert r.extra["lab"] == "LAEO"


def test_xlsx_uncalibrated_has_no_energy_column(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    p = tmp_path / "u.xlsx"
    get_format("excel_xlsx").writer(make_spectrum(energy_coeffs=[], first_channel=0), p)
    ws = openpyxl.load_workbook(p)["Spectrum"]
    assert [c.value for c in ws[1]] == ["Channel", "Counts"]
    r = get_format("excel_xlsx").reader(p)[0]
    assert r.energy_coeffs == [] and r.counts[2] == 12.0


def test_xlsx_foreign_workbook_not_sniffed(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    p = tmp_path / "other.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append(["a", "b"])
    wb.save(p)
    assert not get_format("excel_xlsx").sniffer(p, p.read_bytes()[:4096])
    with pytest.raises(FormatError):
        get_format("excel_xlsx").reader(p)

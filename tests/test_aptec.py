"""Tests for the APTEC v6.3 (*.S0) reader/writer against the reference spectra."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pytest

from spectramaster.formats.base import FormatError, get_format
from spectramaster.formats.aptec import parse_aptec, read_aptec, sniff_aptec, write_aptec

REF = Path("D:/الاسس و المفاهيم العامة فى استخدام برامج الطيف الجامى/اطياف مرجعية/"
           "4- أطياف المختبر (Aptec)")
S0_DIR = REF / "الملفات الأصلية S0"
CSV_DIR = REF / "الأطياف CSV"

needs_ref = pytest.mark.skipif(not S0_DIR.is_dir(), reason="reference spectra not available")
S0_FILES = sorted(S0_DIR.glob("*.S0")) if S0_DIR.is_dir() else []


def _csv_counts(path: Path) -> list[int]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["channel", "counts"]
    assert [int(r[0]) for r in rows[1:]] == list(range(len(rows) - 1))
    return [int(float(r[1])) for r in rows[1:]]


@needs_ref
def test_reference_set_complete():
    assert len(S0_FILES) == 21 or len(S0_FILES) == 22


@needs_ref
@pytest.mark.parametrize("s0", S0_FILES, ids=lambda p: p.name)
def test_counts_match_csv(s0: Path):
    csv_path = CSV_DIR / (s0.stem + ".csv")
    if not csv_path.exists():
        pytest.skip(f"no CSV for {s0.name}")
    (spec,) = read_aptec(s0)
    assert spec.counts == _csv_counts(csv_path)
    assert "layout_warning" not in spec.extra
    if spec.live_time and spec.real_time:
        assert 0 < spec.live_time <= spec.real_time


@needs_ref
def test_chernbkg_metadata():
    (s,) = read_aptec(S0_DIR / "CHERNBKG.S0")
    assert s.num_channels == 8192
    assert s.sample_id == "Background, HPS Show, Pitts,PA"
    assert s.description.startswith("Aptec PC/MCA - HPS Show")
    assert s.extra["user_id"] == "Aptec"
    assert s.real_time == pytest.approx(1500.000)
    assert s.live_time == pytest.approx(1451.400)
    assert s.dead_time_percent == pytest.approx(3.24, abs=0.005)
    assert s.total_counts == 59112
    assert s.start_time == datetime(1986, 7, 2, 12, 43, 40)
    assert s.extra["stop_time"] == "1986-07-02 13:08:42"
    assert s.extra["preset_mode"] == "real time"
    assert s.extra["preset_value"] == pytest.approx(1500.0)
    assert s.energy_of(4096) == pytest.approx(808.081, abs=0.001)
    assert s.energy_of(0) == pytest.approx(43.21, abs=0.01)
    assert s.energy_of(8191) == pytest.approx(1573, abs=0.5)
    for nuc in ("Pb-212", "Pb-214", "Tl-208", "Bi-214", "K-40"):
        assert nuc in s.extra["roi_nuclides"]
    assert s.extra["roi_count"] == 9
    assert s.extra["library"] == "isotope.lib"
    assert s.fwhm_coeffs  # converted from channels to keV


@needs_ref
def test_calibration_points_lie_on_curve():
    (s,) = read_aptec(S0_DIR / "CHERNBKG.S0")
    for pair in s.extra["energy_cal_points"].split("; "):
        ch, e = map(float, pair.split(":"))
        assert s.energy_of(ch) == pytest.approx(e, abs=0.1)


@needs_ref
def test_uncalibrated_spectrum():
    (s,) = read_aptec(S0_DIR / "QCY48.S0")
    assert s.energy_coeffs == []
    assert s.num_channels == 4096


@needs_ref
def test_sniffer():
    for p in S0_FILES[:5]:
        assert sniff_aptec(p, p.read_bytes()[:4096])
    for p in sorted(CSV_DIR.glob("*.csv"))[:5]:
        assert not sniff_aptec(p, p.read_bytes()[:4096])


def test_sniffer_rejects_junk(tmp_path):
    assert not sniff_aptec(tmp_path / "x.s0", b"")
    assert not sniff_aptec(tmp_path / "x.s0", b"$SPEC_ID:\r\n" + bytes(2000))
    assert not sniff_aptec(tmp_path / "x.s0", bytes(4096))


def test_reader_rejects_bad_input(tmp_path):
    with pytest.raises(FormatError):
        parse_aptec(b"hello", "x")
    bad = tmp_path / "bad.s0"
    bad.write_bytes(b"VERSION6.3" + bytes(0x400))  # 0 channels
    with pytest.raises(FormatError):
        read_aptec(bad)
    hdr = bytearray(b"VERSION6.3".ljust(0x400, b"\0"))
    hdr[0x316:0x318] = (8192).to_bytes(2, "little")
    trunc = tmp_path / "trunc.s0"
    trunc.write_bytes(bytes(hdr) + bytes(100))
    with pytest.raises(FormatError):
        read_aptec(trunc)


def test_registered():
    # importing spectramaster.formats.aptec (above) registers the format
    f = get_format(13)
    assert f.key == "aptec_s0" and f.can_read and f.can_write
    assert get_format("aptec") is f and get_format("s0") is f


@needs_ref
@pytest.mark.parametrize("name", ["CHERNBKG.S0", "BA133CAL.S0", "EFF-GOOD.S0", "QCY48.S0"])
def test_writer_roundtrip(tmp_path, name):
    (a,) = read_aptec(S0_DIR / name)
    out = tmp_path / "ROUNDTRIP.S0"
    write_aptec(a, out)
    data = out.read_bytes()
    assert sniff_aptec(out, data[:4096])
    (b,) = read_aptec(out)
    assert "layout_warning" not in b.extra
    assert b.counts == a.counts
    assert b.energy_coeffs == a.energy_coeffs
    assert b.live_time == a.live_time and b.real_time == a.real_time
    assert b.start_time == a.start_time
    assert b.sample_id == a.sample_id and b.description == a.description
    assert b.detector == a.detector
    assert b.extra["gross_counts"] == sum(a.counts)
    assert b.extra.get("user_id") == a.extra.get("user_id")
    # header layout identical to a genuine file in all structural fields
    orig = (S0_DIR / name).read_bytes()
    assert data[:16] == orig[:16]
    assert data[0x310:0x312] == orig[0x310:0x312] or orig[0x310:0x312] == b"\0\0"
    assert len(data) == 0x400 + 4 * len(a.counts) + 2514


def test_writer_synthetic(tmp_path):
    from spectramaster.model import Spectrum
    s = Spectrum(counts=[0, 5, 70000, 3] * 256, energy_coeffs=[1.5, 0.5],
                 live_time=99.5, real_time=100.25, start_time=datetime(2020, 1, 2, 3, 4, 5),
                 sample_id="Test sample", description="label", detector="HPGe-1",
                 fwhm_coeffs=[0.8, 0.0002])
    out = tmp_path / "a long file name.s0"
    write_aptec(s, out)
    (b,) = read_aptec(out)
    assert b.counts == s.counts
    assert b.energy_coeffs == s.energy_coeffs
    assert b.fwhm_coeffs == pytest.approx(s.fwhm_coeffs)
    assert (b.live_time, b.real_time) == (99.5, 100.25)
    assert b.start_time == s.start_time
    assert b.extra["stop_time"] == "2020-01-02 03:05:45.250000"
    assert (b.sample_id, b.description, b.detector) == ("Test sample", "label", "HPGe-1")
    with pytest.raises(FormatError):
        write_aptec(Spectrum(counts=[-1.0]), tmp_path / "neg.s0")

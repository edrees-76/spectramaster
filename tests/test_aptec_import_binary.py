"""Tests for spectramaster.formats.aptec_import_binary (codes 70-79).

No original instrument files were available, so the read-only formats are
tested with files built byte-for-byte from the layouts recovered from the
Aptec MCA v6.31 converter DLLs (documented in the module docstring); writers
are tested by round trip and by auto-detection of their output.
"""
from __future__ import annotations

import struct
from datetime import datetime
from pathlib import Path

import pytest

from spectramaster.formats import aptec_import_binary as B
from spectramaster.formats import canberra_legacy as C
from spectramaster.formats import detect_format, get_format, load_all
from spectramaster.formats.base import FormatError
from spectramaster.model import Spectrum

load_all()
CO60 = Path("D:/الاسس و المفاهيم العامة فى استخدام برامج الطيف الجامى/اطياف مرجعية/"
            "4- أطياف المختبر (Aptec)/الملفات الأصلية S0/CO60CAL.S0")


def spec(n=1024, cal=(0.5, 0.25)):
    counts = [int(20 + (i * 7) % 13 + (9000 if 300 <= i <= 303 else 0)) for i in range(n)]
    return Spectrum(counts=counts, energy_coeffs=list(cal), live_time=1200.5, real_time=1250.25,
                    start_time=datetime(1996, 5, 17, 9, 41, 12), sample_id="QC-12",
                    description="Test spectrum", detector="HPGe-1")


def test_registered():
    keys = {70: "jcac_vax", 71: "nd66", 72: "norland5000", 73: "oxford_ans",
            74: "quantrad_scout", 75: "spectran_f", 76: "nucleus_pca", 77: "pca_multiport",
            78: "aptec_v30", 79: "aptec_v43"}
    for code, key in keys.items():
        f = get_format(code)
        assert f.key == key and f.can_read
        assert f.can_write == (code in (70, 71, 72, 73))
    with pytest.raises(KeyError):
        get_format(3)  # DataMaster Oxford PCA-2 deliberately not claimed


# ------------------------------------------------------------ float formats
def test_vax_float():
    assert B.float_to_vax(1.0) == bytes([0x80, 0x40, 0, 0])
    assert B.vax_to_float(bytes([0x80, 0x40, 0, 0])) == 1.0
    for x in (0.0, 1234.5, -3.25, 1e-3, 65535.0, 1e7):
        assert B.vax_to_float(B.float_to_vax(x)) == pytest.approx(x, rel=1e-7)
        # PDP-11 F-float == VAX F-float: consistent with canberra_legacy
        assert C._pdp11_float(B.float_to_vax(x)) == pytest.approx(x, rel=1e-7)


def test_mbf_float():
    assert B.float_to_mbf(1.0) == bytes([0, 0, 0, 0x81])
    assert B.mbf_to_float(bytes([0, 0, 0, 0x81])) == 1.0
    assert B.mbf_to_float(bytes([0, 0, 0x80, 0x81])) == -1.0
    for x in (0.0, 0.5, 1500.0, -7.125, 123456.0):
        assert B.mbf_to_float(B.float_to_mbf(x)) == pytest.approx(x, rel=1e-7)


def test_bcd():
    assert B._bcd3(bytes([0x45, 0x23, 0x01])) == 12345
    # 662.0 -> digits 662000000 * 1e-9 * 10^3
    assert B.bcd_real6(bytes([0x00, 0x00, 0x00, 0x62, 0x06, 0x03])) == pytest.approx(662.0)
    assert B.bcd_real6(bytes([0x00, 0x00, 0x00, 0x00, 0x91, 0x01])) == pytest.approx(-1.0)


# --------------------------------------------------------------- writers
def _roundtrip(tmp_path, key, ext, s=None):
    s = s or spec()
    f = get_format(key)
    p = tmp_path / f"x{ext}"
    f.writer(s, p)
    assert detect_format(p).key == key
    return s, f.reader(p)[0], p


def test_jcac_roundtrip(tmp_path):
    s, r, p = _roundtrip(tmp_path, "jcac_vax", ".spc")
    assert p.stat().st_size == 4 * 1024
    assert r.counts[:16] == [0] * 16 and r.counts[16:] == s.counts[16:]
    assert r.real_time == pytest.approx(1250.25) and r.live_time == pytest.approx(1200.5)


def test_nd66_roundtrip(tmp_path):
    s, r, p = _roundtrip(tmp_path, "nd66", ".001")
    raw = p.read_bytes()
    assert len(raw) == 512 + 3 * 1024
    assert raw[512 + 3 * 300:512 + 3 * 301] == (s.counts[300]).to_bytes(3, "big")
    assert r.counts == s.counts
    assert r.real_time == pytest.approx(1250.25) and r.live_time == pytest.approx(1200.5)
    assert r.start_time == s.start_time
    assert r.energy_coeffs == pytest.approx([0.5, 0.25])
    assert (r.sample_id, r.description, r.detector) == ("QC-12", "Test spectrum", "HPGe-1")
    with pytest.raises(FormatError):
        B.write_nd66(Spectrum(counts=[2 ** 24]), tmp_path / "bad.001")


def test_norland_roundtrip(tmp_path):
    s, r, p = _roundtrip(tmp_path, "norland5000", ".dat")
    assert p.stat().st_size == 512 + 4096
    assert r.counts[2:] == s.counts[2:] and r.counts[:2] == [0, 0]
    assert r.live_time == pytest.approx(1200.5) and r.real_time == pytest.approx(1250.25)
    assert r.energy_coeffs == pytest.approx([0.5, 0.25])
    # 1500 channels are padded to the next size code (2 = 2048 channels)
    s2 = spec(1500)
    B.write_norland(s2, tmp_path / "y.dat")
    assert len(B.read_norland(tmp_path / "y.dat")[0].counts) == 2048


def test_oxford_roundtrip(tmp_path):
    s, r, p = _roundtrip(tmp_path, "oxford_ans", ".ans")
    assert p.stat().st_size == 1024 + 4 * 1024
    assert r.counts == s.counts and r.first_channel == 0
    assert r.real_time == pytest.approx(1250.25) and r.live_time == pytest.approx(1200.5)
    assert abs((r.start_time - s.start_time).total_seconds()) < 1e-3


# ---------------------------------------------------------- read-only formats
def test_oxford_revision2(tmp_path):
    h = bytearray(0x600)
    struct.pack_into("<H", h, 0, 2)
    struct.pack_into("<dddd", h, 0x50, 35000.5, 35000.6, 100.0, 90.0)
    struct.pack_into("<HH", h, 0x3F0, 10, 13)
    p = tmp_path / "r2.ans"
    p.write_bytes(bytes(h) + struct.pack("<4i", 1, 2, 3, 4))
    r = B.read_oxford(p)[0]
    assert r.counts == [1, 2, 3, 4] and r.first_channel == 10
    assert r.start_time == datetime(1995, 10, 28, 12, 0)
    assert (r.real_time, r.live_time) == (100.0, 90.0)


def test_scout(tmp_path):
    rec = bytearray(B.SCT_LEN)
    struct.pack_into("<IIf", rec, 2, 820000000, 820000600, 10.0)
    struct.pack_into("<256H", rec, 0x0E, *range(256))
    rec[0x210:0x214] = b"S-01"
    rec[0x235:0x238] = b"keV"
    struct.pack_into("<ff", rec, 0x239, 11.7, -3.0)
    p = tmp_path / "a.sct"
    p.write_bytes(bytes(0x400) + bytes(rec))
    assert detect_format(p).key == "quantrad_scout"
    r = B.read_scout(p)[0]
    assert r.counts == list(range(256)) and r.real_time == 600 and r.live_time == pytest.approx(540)
    assert r.energy_coeffs == pytest.approx([-3.0, 11.7]) and r.sample_id == "S-01"
    assert r.start_time == datetime(1995, 12, 26, 17, 46, 40)


def test_spectran(tmp_path):
    hdr = bytearray(1024)
    for off, v in ((0x34, 1000.0), (0x60, 950.0), (0x18, 3.0), (0x1C, 4.0), (0x20, 1997.0),
                   (0x14, 3600.0), (0x5C, 1.0), (0x3C, 1.0), (0x40, 0.2), (0x44, 0.5), (0x64, 512.0)):
        struct.pack_into("<f", hdr, off, v)
    hdr[0x78:0x7D] = b"ABC12"
    vals = [7.0, 8.0] + [float(i) for i in range(2, 512)]

    def blk(payload):
        return struct.pack("<I", 0x408) + payload + struct.pack("<I", 0x408)
    data = blk(bytes(hdr)) + blk(struct.pack("<256f", *vals[:256])) + blk(struct.pack("<256f", *vals[256:]))
    p = tmp_path / "s.spc"
    p.write_bytes(data)
    assert detect_format(p).key == "spectran_f"
    r = B.read_spectran(p)[0]
    assert len(r.counts) == 512 and r.counts[:2] == [0, 0] and r.counts[100] == 100
    assert (r.real_time, r.live_time) == (1000.0, 950.0)
    assert r.start_time == datetime(1997, 4, 3, 1, 0)
    assert r.energy_coeffs == pytest.approx([0.2, 0.5]) and r.sample_id == "ABC12"


def _pca_header():
    h = bytearray(512)
    h[0:3] = bytes([0x00, 0x36, 0x00])  # BCD 3600
    struct.pack_into("<H", h, 0x10A, 256)
    return h


def test_nucleus_pca1(tmp_path):
    h = _pca_header()
    h[3] = 0xFF  # real time
    txt = b"Jan 05 1994 10:23:45 PM"
    h[0x16:0x16 + len(txt)] = txt
    pts = [(100.0, 50.0), (500.0, 250.0)]
    o = 0x2F
    for ch, en in pts:
        for v in (ch, en):
            h[o:o + 6] = bytes([0, 0, 0, 0x10, 0, 0]) if v == 1.0 else _bcd6(v)
            o += 6
    counts = [(i | 0x7F000000) for i in range(256)]
    p = tmp_path / "a.spm"
    p.write_bytes(bytes(h) + struct.pack("<256I", *counts))
    assert detect_format(p).key == "nucleus_pca"
    r = B.read_nucleus(p)[0]
    assert r.counts == list(range(256)) and r.real_time == 3600.0
    assert r.start_time == datetime(1994, 1, 5, 22, 23, 45)
    assert r.energy_coeffs == pytest.approx([0.0, 0.5])
    assert r.extra["nucleus_model"] == "PCA-I"


def _bcd6(v: float) -> bytes:
    exp = len(str(int(v)))
    digits = int(round(v / 10 ** exp * 1e9))
    s = f"{digits:09d}"[::-1]
    b = [int(s[2 * i]) | (int(s[2 * i + 1]) << 4) for i in range(4)] + [int(s[8]), exp]
    return bytes(b)


def test_nucleus_pca2(tmp_path):
    h = _pca_header()
    h[3] = 0xFF  # live time flag (PCA-II)
    h[0x164] = 1
    struct.pack_into("<I", h, 0x166, 4000)
    struct.pack_into("<BBH", h, 0x10C, 9, 3, 1998)
    h[0x110:0x114] = bytes([0, 30, 15, 13])
    h[0x30:0x33] = b"keV"
    struct.pack_into("<ddd", h, 0x34, 1.0, 0.5, 0.0)
    h[0x11C:0x120] = b"SMPL"
    p = tmp_path / "b.spm"
    p.write_bytes(bytes(h) + struct.pack("<256I", *range(256)))
    r = B.read_nucleus(p)[0]
    assert r.extra["nucleus_model"] == "PCA-II"
    assert (r.live_time, r.real_time) == (3600.0, 4000.0)
    assert r.start_time == datetime(1998, 3, 9, 13, 15, 30)
    assert r.energy_coeffs == [1.0, 0.5] and r.sample_id == "SMPL"


def test_pcam(tmp_path):
    def rec(t, payload):
        return struct.pack("<HI", t, len(payload)) + payload
    data = rec(1023, bytes(0x80)) + rec(1021, struct.pack("<H", 1))
    cal = bytearray(0x2A)
    cal[6:9] = b"keV"
    struct.pack_into("<4d", cal, 0x0A, 1.5, 0.75, 0.0, 0.0)
    dates = bytearray(0x3A)
    dates[0x06:0x0E] = b"10:20:30"
    dates[0x13:0x1F] = b"Feb 03, 1999"
    dates[0x20:0x28] = b"09:20:30"
    dates[0x2D:0x39] = b"Feb 03, 1999"
    times = bytearray(0x12)
    struct.pack_into("<II", times, 6, 3600, 3500)
    counts = struct.pack("<HHH", 0, 0, 512) + struct.pack("<512I", *[i | 0x01000000 for i in range(512)])
    data += rec(1015, bytes(cal)) + rec(1016, bytes(dates)) + rec(1019, bytes(times))
    data += rec(1014, counts) + rec(1014, struct.pack("<HHH", 1, 0, 4) + bytes(16)) + rec(1022, b"")
    p = tmp_path / "m.spt"
    p.write_bytes(data)
    assert detect_format(p).key == "pca_multiport"
    r = B.read_pcam(p)[0]
    assert r.counts == list(range(512))  # port 1 record ignored, top byte masked
    assert (r.real_time, r.live_time) == (3600.0, 3500.0)
    assert r.start_time == datetime(1999, 2, 3, 9, 20, 30)
    assert r.extra["stop_time"] == "1999-02-03 10:20:30"
    assert r.energy_coeffs == [1.5, 0.75]


def test_aptec_v30(tmp_path):
    h = bytearray(0x400)
    h[0:10] = b"VERSION3.0"
    struct.pack_into("<H", h, 0x0E, 512)
    struct.pack_into("<5BH", h, 0x14, 12, 34, 10, 2, 7, 1991)
    struct.pack_into("<III", h, 0x22, 150000, 145000, 99)
    h[0x66:0x6A] = b"BKGD"
    h[0x167:0x16A] = b"keV"
    struct.pack_into("<H4f", h, 0x16E, 1, 0.1, 0.5, 0, 0)
    p = tmp_path / "old.s0"
    p.write_bytes(bytes(h) + struct.pack("<512I", *range(512)))
    assert detect_format(p).key == "aptec_v30"
    r = B.read_aptec_v30(p)[0]
    assert r.counts == list(range(512)) and (r.real_time, r.live_time) == (1500.0, 1450.0)
    assert r.start_time == datetime(1991, 7, 2, 10, 34, 12)
    assert r.energy_coeffs == pytest.approx([0.1, 0.5]) and r.sample_id == "BKGD"


def test_aptec_v43(tmp_path):
    h = bytearray(0x400)
    h[0:10] = b"VERSION4.3"
    struct.pack_into("<H", h, 0x24, 256)
    struct.pack_into("<6BH", h, 0x2A, 0, 5, 4, 3, 2, 1, 1995)
    struct.pack_into("<I", h, 0x3A, 1000000)
    struct.pack_into("<I", h, 0x42, 990000)
    struct.pack_into("<H", h, 0x82, 1)       # one ROI record
    struct.pack_into("<H", h, 0x224, 2)      # two energy points
    struct.pack_into("<H", h, 0x226, 1)
    struct.pack_into("<2d", h, 0x228, 2.0, 0.5)
    h[0x214:0x217] = b"keV"
    struct.pack_into("<H", h, 0x2CC, 1)      # one efficiency record
    body = bytes(0xC0) + bytes(16) + bytes(0x100) + struct.pack("<256I", *range(256))
    p = tmp_path / "v43.s0"
    p.write_bytes(bytes(h) + body)
    assert detect_format(p).key == "aptec_v43"
    r = B.read_aptec_v43(p)[0]
    assert r.counts == list(range(256)) and (r.real_time, r.live_time) == (1000.0, 990.0)
    assert r.start_time == datetime(1995, 1, 2, 3, 4, 5)
    assert r.energy_coeffs == [2.0, 0.5]


def test_no_false_positives(tmp_path):
    """Writer outputs of other formats must not be claimed by these sniffers."""
    from spectramaster.formats import aptec
    s = spec()
    p = tmp_path / "a.s0"
    aptec.write_aptec(s, p)
    assert detect_format(p).key == "aptec_s0"
    p = tmp_path / "a.mca"
    C.write_s100(s, p)
    assert detect_format(p).key == "ci_s100"


@pytest.mark.skipif(not CO60.exists(), reason="reference Aptec sample not available")
def test_real_s0_through_all_writers(tmp_path):
    from spectramaster.convert import read_spectra
    from spectramaster.convert import fit_calibration
    from dataclasses import replace
    src = read_spectra(CO60)[0][0]
    src = replace(src, energy_coeffs=fit_calibration(src, 2)[0])  # Norland: linear only
    for key, ext in (("jcac_vax", ".spc"), ("nd66", ".001"), ("norland5000", ".dat"),
                     ("oxford_ans", ".ans")):
        f = get_format(key)
        p = tmp_path / f"co60{ext}"
        f.writer(src, p)
        r = f.reader(p)[0]
        skip = {"jcac_vax": 16, "norland5000": 2}.get(key, 0)
        n = min(len(src.counts), 8192)
        assert r.counts[skip:n] == src.counts[skip:n]
        assert r.live_time == pytest.approx(src.live_time, abs=0.01)

"""Tests for spectramaster.formats.ascii_formats (codes 5, 6, 8, 9)."""
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import pytest

from spectramaster.formats import ascii_formats as A
from spectramaster.formats import load_all
from spectramaster.formats.base import FormatError, detect, detect_format, get_format
from spectramaster.model import Spectrum

from _legacy_helpers import (G1_ASC, LAB_IEC, TECDOC_ASC, copy_to, genie_to_cnf, synthetic)


def _approx_coeffs(a, b, rel=1e-6):
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert x == pytest.approx(y, rel=rel, abs=1e-12)


# ------------------------------------------------------------------ registry
def test_registered_codes():
    assert get_format(5).key == "ascii1" and get_format(5).can_write
    assert get_format(6).key == "ascii2" and get_format(6).can_write
    assert get_format(8).key == "iec1455" and get_format(8).can_write
    assert get_format(9).key == "ieee_asc" and get_format(9).can_write
    with pytest.raises(KeyError):
        get_format("sampo90")      # deliberately not registered (no public spec)


# ------------------------------------------------------------------- ASCII-1
def test_ascii1_roundtrip(tmp_path):
    pytest.importorskip("SpecUtils")      # format read or written through SpecUtils
    s = synthetic()
    p = tmp_path / "a.txt"
    A.write_ascii1(s, p)
    assert p.read_bytes().count(b"\r\n") == len(s.counts)
    r = A.read_ascii1(p)[0]
    assert r.counts == s.counts
    load_all()     # TKA is registered by the SpecUtils bridge
    # its first two counts (50, 53) could be a live and a real time: ambiguous with TKA
    # (round5_tka_protocol.md)
    assert detect_format(p) is None
    assert {f.key for f in detect(p)[2]} == {"ascii1", "tka"}


def test_ascii1_tolerates_headers_and_blanks(tmp_path):
    p = tmp_path / "h.txt"
    p.write_text("My spectrum\nsecond header line\n\n1\n2\n\n3.5\n4\n", encoding="utf-8")
    r = A.read_ascii1(p)[0]
    assert r.counts == [1, 2, 3.5, 4]
    assert r.sample_id == "My spectrum"
    assert r.description == "second header line"


def test_ascii1_float_counts_roundtrip(tmp_path):
    s = Spectrum(counts=[0.5, 1.25, 1e-3, 7])
    p = tmp_path / "f.txt"
    A.write_ascii1(s, p)
    assert A.read_ascii1(p)[0].counts == [0.5, 1.25, 1e-3, 7]


def test_ascii1_empty_raises(tmp_path):
    p = tmp_path / "e.txt"
    p.write_text("just text\n")
    with pytest.raises(FormatError):
        A.read_ascii1(p)


# ------------------------------------------------------------------- ASCII-2
def test_ascii2_roundtrip_with_offset(tmp_path):
    s = synthetic(300)
    s.first_channel = 12
    p = tmp_path / "b.txt"
    A.write_ascii2(s, p)
    r = A.read_ascii2(p)[0]
    assert r.counts == s.counts and r.first_channel == 12
    assert detect_format(p).key == "ascii2"


@pytest.mark.parametrize("sep", [",", "\t", ";", "  "])
def test_ascii2_energy_column_calibration(tmp_path, sep):
    coeffs = [1.5, 0.3, 2e-5]
    lines = ["Sample X", sep.join(["Channel", "Energy", "Counts"])]
    for ch in range(512):
        e = coeffs[0] + coeffs[1] * ch + coeffs[2] * ch * ch
        lines.append(sep.join([str(ch), f"{e:.6f}", str(ch % 9)]))
    p = tmp_path / "c.txt"
    p.write_text("\n".join(lines) + "\n")
    r = A.read_ascii2(p)[0]
    assert r.num_channels == 512 and r.counts[10] == 1
    assert r.sample_id == "Sample X"
    for ch in (0, 100, 511):
        assert r.energy_of(ch) == pytest.approx(coeffs[0] + coeffs[1] * ch + coeffs[2] * ch * ch,
                                                abs=1e-4)


def test_ascii2_counts_energy_column_order_from_header(tmp_path):
    p = tmp_path / "d.txt"
    p.write_text("counts,channel,energy\n" + "".join(f"{7*c},{c},{2.0*c+1}\n" for c in range(50)))
    r = A.read_ascii2(p)[0]
    assert r.counts[3] == 21
    _approx_coeffs(r.energy_coeffs, [1.0, 2.0])


def test_linear_fit_stays_linear():
    c = A.fit_calibration([0, 1, 2, 3, 4, 5], [1, 3, 5, 7, 9, 11])
    _approx_coeffs(c, [1.0, 2.0])


# ------------------------------------------------------------------ IEC 1455
def test_iec_layout(tmp_path):
    s = synthetic(1027)
    p = tmp_path / "x.iec"
    A.write_iec(s, p)
    raw = p.read_bytes()
    lines = raw.split(b"\r\n")[:-1]
    assert all(l.startswith(b"A004") and len(l) == 68 for l in lines)
    assert len(lines) == 58 + math.ceil(1027 / 5)
    assert lines[1] == b"A004       1234.50       1300.25  1027" + b" " * 30
    assert lines[2].startswith(b"A00407/03/24 14:05:09")
    assert lines[58].startswith(b"A004     0")
    assert lines[-1][4:10] == b"  1025" and lines[-1][30:].strip() == b""
    assert detect_format(p).key == "iec1455"


def test_iec_roundtrip(tmp_path):
    s = synthetic(1027)
    p = tmp_path / "x.iec"
    A.write_iec(s, p)
    r = A.read_iec(p)[0]
    assert r.counts == s.counts
    assert r.live_time == 1234.5 and r.real_time == 1300.25
    assert r.start_time == s.start_time
    _approx_coeffs(r.energy_coeffs, s.energy_coeffs, rel=1e-7)
    assert r.sample_id == "Soil sample 42"
    assert r.description == "line two\nline three"
    assert r.detector == "HPGE1"
    # re-writing the read spectrum is stable
    p2 = tmp_path / "y.iec"
    A.write_iec(r, p2)
    assert p2.read_bytes() == p.read_bytes()


def test_iec_arabic_description_roundtrip(tmp_path):
    s = synthetic(20)
    s.sample_id = "حديد تسليح 10مم"
    p = tmp_path / "ar.iec"
    A.write_iec(s, p)
    assert A.read_iec(p)[0].sample_id == "حديد تسليح 10مم"


def test_iec_interwinner_variants(tmp_path):
    """Dotted dates, glued FWHM exponent, zero polynomial + energy/channel pairs."""
    recs = ["IWIN0410     SIL   0   0     0",
            "      54449.00      65100.00    12",
            "28.07.04 14:08:32 13.04.04 09:20:45",
            " 0.00000000E+00 0.00000000E+00 0.00000000E+00 0.00000000E+00",
            " 0.00000000E+00 0.00000000E+00 0.00000000E+00 0.00000000E+000.50",
            "Sample", "", "", "", ""]
    recs += [" 0.000000000E+00 0.000000000E+00 1.000000000E+02 4.000000000E+02",
             " 2.000000000E+02 8.000000000E+02 0.000000000E+00 0.000000000E+00"]
    recs += [" 0.000000000E+00" * 4] * 34 + [""] * 12
    recs += ["     0         1         2         3         4         5",
             "     5         6         7         8         9        10",
             "    10        11        12"]
    p = tmp_path / "iw.IEC"
    p.write_bytes("".join("A004" + r.ljust(64) + "\r\n" for r in recs).encode("ascii"))
    r = A.read_iec(p)[0]
    assert r.counts == list(range(1, 13))
    assert r.start_time == datetime(2004, 7, 28, 14, 8, 32)
    assert r.extra["iec_sample_time"] == "2004-04-13T09:20:45"
    _approx_coeffs(r.energy_coeffs, [0.0, 0.25])
    assert r.live_time == 54449.0 and r.extra["iec_system_id"] == "IWIN0410"


def test_iec_rejects_untagged(tmp_path):
    p = tmp_path / "bad.iec"
    p.write_text("hello\nworld\n")
    with pytest.raises(FormatError):
        A.read_iec(p)


def _lab_iec_files():
    return sorted(LAB_IEC.rglob("*.IEC")) if LAB_IEC.exists() else []


@pytest.mark.skipif(not _lab_iec_files(), reason="lab IEC samples not available")
def test_iec_real_interwinner_files():
    for f in _lab_iec_files():
        r = A.read_iec(f)[0]
        assert r.num_channels == 8192
        assert r.energy_coeffs == [0.0, 0.25]
        assert r.live_time > 0 and r.real_time >= r.live_time
        assert r.start_time is not None and r.start_time.year == 2004
    bkg = [f for f in _lab_iec_files() if f.name.startswith("BQCK")][0]
    r = A.read_iec(bkg)[0]
    assert (r.live_time, r.real_time, r.total_counts) == (54449.0, 65100.0, 261900.0)
    assert r.counts[:3] == [154, 163, 177] and r.counts[-2:] == [3, 1]
    assert r.sample_id == "حديد تسليح10مم"


@pytest.mark.skipif(not _lab_iec_files(), reason="lab IEC samples not available")
def test_iec_real_file_rewrite_is_equivalent(tmp_path):
    src = [f for f in _lab_iec_files() if f.name.startswith("BQCK")][0]
    a = A.read_iec(src)[0]
    p = tmp_path / "rw.iec"
    A.write_iec(a, p)
    b = A.read_iec(p)[0]
    assert b.counts == a.counts and b.start_time == a.start_time
    assert (b.live_time, b.real_time) == (a.live_time, a.real_time)


def test_iec_readable_by_genie_filecnvt(tmp_path):
    """Independent check: Canberra Genie 2000 FILECNVT /IEC1455 -> CNF -> SpecUtils."""
    pytest.importorskip("SpecUtils")
    s = synthetic(1027)
    p = tmp_path / "g.iec"
    A.write_iec(s, p)
    m = genie_to_cnf(p, "/IEC1455")
    if m is None:
        pytest.skip("Genie 2000 FILECNVT not available")
    counts = list(m.gammaCounts())
    assert counts[:1027] == [float(c) for c in s.counts]
    assert sum(counts[1027:]) == 0
    assert m.liveTime() == pytest.approx(1234.5) and m.realTime() == pytest.approx(1300.25)
    _approx_coeffs(list(m.calibrationCoeffs())[:3], s.energy_coeffs, rel=1e-6)


def test_iec_specutils_if_supported(tmp_path):
    """SpecUtils >= master (SpectraLine IEC parser) must read our files; older
    releases have no IEC 1455 parser at all, in which case this is skipped."""
    SpecUtils = pytest.importorskip("SpecUtils")
    s = synthetic(1027)
    p = tmp_path / "su.iec"
    A.write_iec(s, p)
    f = SpecUtils.SpecFile()
    try:
        f.loadFile(str(p), SpecUtils.ParserType.Auto)
    except Exception:
        pytest.skip("installed SpecUtils has no IEC 1455 parser")
    m = f.measurements()[0]
    assert list(m.gammaCounts()) == [float(c) for c in s.counts]
    assert m.liveTime() == pytest.approx(1234.5)


# ---------------------------------------------------------------- IEEE ASCII
def test_ieee_asc_roundtrip(tmp_path):
    s = synthetic(2020)
    p = tmp_path / "s.asc"
    A.write_ieee_asc(s, p)
    lines = p.read_bytes().split(b"\r\n")
    assert lines[0] == b"Soil sample 42" and lines[2] == b""
    assert len(lines[3]) == 72                        # 8 x I9
    r = A.read_ieee_asc(p)[0]
    assert r.counts == s.counts and r.sample_id == "Soil sample 42"
    assert detect_format(p).key == "ieee_asc"


def test_ieee_asc_numeric_title_is_protected(tmp_path):
    s = Spectrum(counts=[1, 2, 3], sample_id="2024")
    p = tmp_path / "n.asc"
    A.write_ieee_asc(s, p)
    assert A.read_ieee_asc(p)[0].counts == [1, 2, 3]


G1_NAMES = ["G1100", "G1200", "G1300", "G1301", "G1302", "G1303", "G1304", "G1305", "G1400"]


@pytest.mark.skipif(not G1_ASC.exists(), reason="IAEA G-1 samples not available")
@pytest.mark.parametrize("name", G1_NAMES)
def test_ieee_asc_iaea_g1(name):
    r = A.read_ieee_asc(G1_ASC / f"{name}.ASC")[0]
    # README says "2000 channels"; the files hold 2000 + 20 trailing channels
    # (identical to the S100 .MCA distribution, non-zero up to channel 2019)
    assert r.num_channels == 2020
    assert r.sample_id == "I.A.E.A. G1 Reference Spectra"
    assert r.extra["values_per_line"] == 8
    if name == "G1100":
        assert r.counts[:4] == [21756, 21400, 21187, 21187]
        assert r.counts[-4:] == [955, 969, 981, 904]
        assert r.total_counts == 22316686


@pytest.mark.skipif(not G1_ASC.exists(), reason="IAEA G-1 samples not available")
def test_ieee_asc_g1_rewrite(tmp_path):
    a = A.read_ieee_asc(G1_ASC / "G1100.ASC")[0]
    p = tmp_path / "g.asc"
    A.write_ieee_asc(a, p)
    b = A.read_ieee_asc(p)[0]
    assert b.counts == a.counts and b.sample_id == a.sample_id and b.description == a.description
    orig = [l.rstrip() for l in (G1_ASC / "G1100.ASC").read_bytes().replace(b"\x1a", b"")
            .decode("ascii").splitlines()]
    ours = [l.rstrip() for l in p.read_bytes().decode("ascii").splitlines()]
    assert ours == orig[:len(ours)]


@pytest.mark.skipif(not TECDOC_ASC.exists(), reason="TECDOC samples not available")
def test_ieee_asc_hyperlab_trailer():
    r = A.read_ieee_asc(TECDOC_ASC / "AmC160705k-6.ASC")[0]
    assert r.num_channels == 8192
    assert r.live_time == 450 and r.real_time == 453.38
    assert r.start_time == datetime(2016, 7, 7, 12, 47, 47)
    _approx_coeffs(r.energy_coeffs, [0.0174143, 0.249788])
    assert r.sample_id == "AmC160705k-6"

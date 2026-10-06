"""Tests for spectramaster.formats.canberra_legacy (codes 14, 15, 17)."""
from __future__ import annotations

import math
import struct
from datetime import datetime
from pathlib import Path

import pytest

from spectramaster.formats import ascii_formats as A
from spectramaster.formats import canberra_legacy as C
from spectramaster.formats.base import FormatError, detect_format, get_format
from spectramaster.model import Spectrum

from _legacy_helpers import G1_ASC, REF, SANDERSON, genie_to_cnf, synthetic



def test_registered_codes():
    assert get_format(14).key == "ci_s100" and get_format(14).can_write
    f = get_format(15)
    assert f.key == "ci_accuspec" and f.can_read and not f.can_write
    f = get_format(17)
    assert f.key == "eml_sanderson" and f.can_read and not f.can_write


# ---------------------------------------------------------------------- S100
def test_s100_roundtrip(tmp_path):
    s = synthetic(2048)
    p = tmp_path / "a.mca"
    C.write_s100(s, p)
    raw = p.read_bytes()
    assert len(raw) == 128 + 4 * 2048
    assert struct.unpack_from("<hhh", raw, 0) == (2, 1, 0)
    assert struct.unpack_from("<h", raw, 36)[0] == 0x180
    assert struct.unpack_from("<ii", raw, 48) == (123450, 130025)
    assert struct.unpack_from("<h", raw, 126)[0] == 2048
    r = C.read_s100(p)[0]
    assert r.counts == s.counts
    assert (r.live_time, r.real_time) == (1234.5, 1300.25)
    assert r.start_time == s.start_time
    assert r.sample_id == "Soil sample 42"
    for a, b in zip(r.energy_coeffs, s.energy_coeffs):
        assert a == pytest.approx(b, rel=1e-6)
    assert detect_format(p).key == "ci_s100"


def test_s100_rejects_offset_and_empty(tmp_path):
    with pytest.raises(FormatError):
        C.write_s100(Spectrum(counts=[]), tmp_path / "e.mca")
    with pytest.raises(FormatError):
        C.write_s100(Spectrum(counts=[1, 2], first_channel=5), tmp_path / "o.mca")


def _g1_like_mca(counts, path: Path) -> Path:
    """Header bytes exactly as in the IAEA G-1 distribution's G1100.MCA."""
    hdr = bytearray(128)
    struct.pack_into("<hhhi26shIhhhii", hdr, 0, 2, 1, 1, 15, b"Spectra formatted by G.R",
                     0x180, 551459400, 0, 480, 1, 10000, 10000)
    struct.pack_into("<3f", hdr, 68, 0.0, 0.9999995231628418, 0.0047915480099618435)
    hdr[80:84] = b"keV\x00"
    hdr[86], hdr[87] = 1, 1
    struct.pack_into("<h", hdr, 126, 2048)
    path.write_bytes(bytes(hdr) + struct.pack("<2048i", *counts))
    return path


@pytest.mark.skipif(not G1_ASC.exists(), reason="IAEA G-1 samples not available")
def test_s100_g1_header_decoding(tmp_path):
    """G1100.MCA header (as distributed, rebuilt byte for byte) must give the
    values of G1100.CHN: 100 s live/real, start 23-Jun-87 08:10, E = 0.00479 + 0.9999995 ch."""
    asc = A.read_ieee_asc(G1_ASC / "G1100.ASC")[0].counts
    p = _g1_like_mca(asc + [0] * (2048 - len(asc)), tmp_path / "G1100.MCA")
    r = C.read_s100(p)[0]
    assert r.counts[:2020] == asc and r.num_channels == 2048
    assert (r.live_time, r.real_time) == (100.0, 100.0)
    assert r.start_time == datetime(1987, 6, 23, 8, 10)
    assert r.energy_coeffs[0] == pytest.approx(0.0047915, rel=1e-4)
    assert r.energy_coeffs[1] == pytest.approx(0.9999995, rel=1e-7)
    assert r.extra["energy_unit"] == "keV"
    assert r.sample_id == "Spectra formatted by G.R"


def test_s100_readable_by_genie_filecnvt(tmp_path):
    """Independent check: Genie 2000 FILECNVT /S100 -> CNF -> SpecUtils."""
    pytest.importorskip("SpecUtils")
    s = synthetic(2048)
    p = tmp_path / "g.mca"
    C.write_s100(s, p)
    m = genie_to_cnf(p, "/S100")
    if m is None:
        pytest.skip("Genie 2000 FILECNVT not available")
    assert list(m.gammaCounts())[:2048] == [float(c) for c in s.counts]
    assert m.liveTime() == pytest.approx(1234.5) and m.realTime() == pytest.approx(1300.25)
    assert m.title().strip() == "Soil sample 42"
    cal = list(m.calibrationCoeffs())
    # CAM channels are 1-based: Genie stores c0 - c1 (+ c2) for our 0-based c0
    assert cal[1] == pytest.approx(0.25 - 2e-6, rel=1e-3)


# ------------------------------------------------------------------ AccuSpec
def _pdp11(f: float) -> bytes:
    if f == 0:
        return b"\x00\x00\x00\x00"
    sign = 0x80 if f < 0 else 0
    m, e = math.frexp(abs(f))             # m in [0.5, 1)
    exb = e + 128
    frac = int(round(m * 2 ** 24)) - 2 ** 23
    return bytes([((exb & 1) << 7) | ((frac >> 16) & 0x7F), sign | (exb >> 1),
                  frac & 0xFF, (frac >> 8) & 0xFF])


def _accuspec(path: Path, counts, cal=(0.44856, 0.03616, 5.684e-08)) -> Path:
    hdr = bytearray(1024)
    struct.pack_into("<H", hdr, 2, 300)
    struct.pack_into("<HHHHHH", hdr, 24, 1024, 1, 1, 0, 0, 4)
    struct.pack_into("<HH", hdr, 36, len(counts), 1)
    for o, v in zip((108, 112, 116), cal):
        hdr[o:o + 4] = _pdp11(v)
    body = b"".join(struct.pack("<HH", c >> 16, c & 0xFFFF) for c in counts)
    path.write_bytes(bytes(hdr) + body)
    return path


def test_pdp11_float_codec():
    for v in (0.44856, 0.03616, 5.684e-08, -3.25, 1.0, 1234.5):
        assert C._pdp11_float(_pdp11(v)) == pytest.approx(v, rel=1e-7)


def test_accuspec_read(tmp_path):
    counts = [i * 3 for i in range(2048)]
    counts[100] = 70000                    # > 16 bits: checks PDP-11 word order
    p = _accuspec(tmp_path / "x.dat", counts)
    r = C.read_accuspec(p)[0]
    assert r.counts == counts
    # file calibration is on 1-based channels: E(stored index 0) = a + b + c
    assert r.energy_of(0) == pytest.approx(0.44856 + 0.03616 + 5.684e-08, rel=1e-6)
    assert r.energy_of(99) == pytest.approx(0.44856 + 0.03616 * 100 + 5.684e-08 * 1e4, rel=1e-6)
    assert detect_format(p).key == "ci_accuspec"


def test_accuspec_rejects_other_binary(tmp_path):
    p = tmp_path / "n.dat"
    p.write_bytes(b"\x00\x00\x00\x20" + b"\x00" * 9000)
    with pytest.raises(FormatError):
        C.read_accuspec(p)


APTEC_DAT = REF / "4- أطياف المختبر (Aptec)" / "الملفات الأصلية S0" / "LN 881.dat"


@pytest.mark.skipif(not APTEC_DAT.exists(), reason="sample not available")
def test_ln881_dat_is_not_accuspec():
    head = APTEC_DAT.read_bytes()[:4096]
    assert not C.sniff_accuspec(APTEC_DAT, head)
    assert not C.sniff_sanderson(APTEC_DAT, head)


# ----------------------------------------------------------------- Sanderson
def test_sanderson_synthetic_fixed_width(tmp_path):
    lines = ["TEST99            LT=   240000 ST=22-NOV-89 10:00:00        "]
    vals = list(range(4090))
    for i in range(409):
        lines.append("".join(f"{v:7d}" for v in vals[10 * i:10 * i + 10]))
    lines[5] = lines[5][:28] + "  8      5"         # malformed row as in TEST01.DAT
    p = tmp_path / "TEST99.DAT"
    p.write_bytes(("\r\n".join(lines) + "\r\n\x1a").encode("ascii"))
    r = C.read_sanderson(p)[0]
    assert r.num_channels == 4090
    assert r.counts[40:46] == [40, 41, 42, 43, 8, 5] and r.counts[46:50] == [0, 0, 0, 0]
    assert r.live_time == 240000 and r.start_time == datetime(1989, 11, 22, 10, 0, 0)
    assert r.sample_id == "TEST99"
    assert detect_format(p).key == "eml_sanderson"


@pytest.mark.skipif(not SANDERSON.exists(), reason="Sanderson samples not available")
def test_sanderson_real_files():
    files = sorted(SANDERSON.glob("*.DAT"))
    assert len(files) == 38
    for f in files:
        r = C.read_sanderson(f)[0]
        # README: 409 lines of 10 values = 4090 points (BKG.DAT: 10F8.0 + 7 extra)
        assert r.num_channels == (4097 if f.name == "BKG.DAT" else 4090), f.name
    t34 = C.read_sanderson(SANDERSON / "TEST34.DAT")[0]
    assert t34.live_time == 10000 and t34.start_time == datetime(1986, 5, 15, 12, 0, 0)
    cal = C.read_sanderson(SANDERSON / "CALIBR01.DAT")[0]
    assert cal.live_time is None and cal.sample_id == "MIXED GAMMA-RAY STD 7/89"


@pytest.mark.skipif(not SANDERSON.exists(), reason="Sanderson samples not available")
def test_sanderson_reference_values():
    """README: TEST09 = background only (multiplier 0); TEST01 adds 0.1 x the
    standard whose net peak counts are 112768 + 136893 + 62723."""
    t09 = C.read_sanderson(SANDERSON / "TEST09.DAT")[0]
    bkg2 = C.read_sanderson(SANDERSON / "BKG2.DAT")[0]
    t01 = C.read_sanderson(SANDERSON / "TEST01.DAT")[0]
    assert t09.counts[1:] == bkg2.counts[1:]
    expected = 0.1 * (112768 + 136893 + 62723)
    assert t01.total_counts - t09.total_counts == pytest.approx(expected, rel=0.01)

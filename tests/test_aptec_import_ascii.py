"""Tests for the Aptec MCA v6.31 import text formats (codes 60-69)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from spectramaster.convert import read_spectra, write_spectrum
from spectramaster.formats import detect_format, get_format, load_all
from spectramaster.formats import aptec_import_ascii as M
from spectramaster.model import Spectrum

load_all()

WRITABLE = ["aptec_ascii", "chandata_csv", "davidson_ascii", "iaea_ascii_dat", "npl_ascii",
            "rump_ascii", "wallac_ascii", "laval_ascii"]


def _spec(n=512) -> Spectrum:
    counts = [(i * 37) % 1000 + (5000 if 300 <= i <= 302 else 0) for i in range(n)]
    counts[0] = counts[1] = 0
    return Spectrum(counts=counts, energy_coeffs=[19.69, 3.7375, 0.000329], live_time=3000.0,
                    real_time=3004.0, start_time=datetime(1991, 11, 27, 18, 57, 57),
                    sample_id="CO60CAL", description="Aptec PCMCA/WIN Spectrum", detector="NaI 3x3")


def test_codes_registered():
    keys = {f.code: f.key for f in (get_format(c) for c in range(60, 70))}
    assert keys == {60: "aptec_ascii", 61: "bti_ascii", 62: "chandata_csv", 63: "ci90_ascii",
                    64: "davidson_ascii", 65: "iaea_ascii_dat", 66: "npl_ascii", 67: "rump_ascii",
                    68: "wallac_ascii", 69: "laval_ascii"}
    assert not get_format("bti_ascii").can_write and not get_format("ci90_ascii").can_write


@pytest.mark.parametrize("key", WRITABLE)
def test_round_trip(tmp_path, key):
    s = _spec()
    f = get_format(key)
    out = tmp_path / ("t" + f.default_ext)
    write_spectrum(s, out, f)
    r = read_spectra(out, f)[0][0]
    first = M.LAVAL_FIRST if key == "laval_ascii" else 0
    assert r.counts[first:512] == s.counts[first:512]
    if key == "wallac_ascii":
        assert len(r.counts) == 1024 and not any(r.counts[512:])
    else:
        assert len(r.counts) == 512
    if key not in ("chandata_csv", "rump_ascii"):
        assert r.live_time == pytest.approx(3000.0)
    if key in ("aptec_ascii", "davidson_ascii", "iaea_ascii_dat", "npl_ascii", "laval_ascii"):
        assert r.real_time == pytest.approx(3004.0, abs=0.5)
    if key in ("aptec_ascii", "davidson_ascii", "iaea_ascii_dat"):
        assert r.start_time == datetime(1991, 11, 27, 18, 57, 57)
    if key in ("rump_ascii", "laval_ascii"):
        assert r.start_time.date() == datetime(1991, 11, 27).date()
    if key == "aptec_ascii":
        assert r.energy_coeffs == pytest.approx(s.energy_coeffs)
        assert r.sample_id == "CO60CAL" and r.description == s.description and r.detector == "NaI 3x3"
    if key == "chandata_csv":
        assert r.energy_of(340) == pytest.approx(s.energy_of(340), abs=0.01)
    if key == "laval_ascii":                       # linear refit of the quadratic
        assert r.energy_of(300) == pytest.approx(s.energy_of(300), abs=8)
    if key != "iaea_ascii_dat":                    # .dat goes to code 17 (same files)
        assert detect_format(out).key == key


def test_private_test_files_round_trip(tmp_path):
    s = _spec()
    M._bti_test_file(s, tmp_path / "a.bti")
    r = M.read_bti(tmp_path / "a.bti")[0]
    assert r.counts[:512] == s.counts and r.counts[512] == 0
    assert r.live_time == 3000.0 and r.real_time == pytest.approx(3004.0, abs=0.01)
    assert r.start_time == s.start_time
    assert detect_format(tmp_path / "a.bti").key == "bti_ascii"
    M._ci90_test_file(s, tmp_path / "a.o")
    r = M.read_ci90(tmp_path / "a.o")[0]
    assert r.counts == s.counts and r.live_time == 3000.0 and r.real_time == 3004.0
    assert r.start_time == s.start_time
    assert detect_format(tmp_path / "a.o").key == "ci90_ascii"


def test_aptec_ascii_quoted_form_written_by_aptec(tmp_path):
    # exact layout of aptascii.dll SaveFileSpectrum ('"%s" "%s"' etc.)
    p = tmp_path / "q.apt"
    p.write_bytes(b'"TITLE:" "Aptec PCMCA/WIN Spectrum"\r\n"LABEL:" "CO60CAL"\r\n'
                  b'"USER ID:" "Aptec"\r\n"DETECTOR ID:" "NaI"\r\n"GEOMETRY ID:" ""\r\n'
                  b'"ACQ START TIME:" 18:57:57\r\n"ACQ START DATE:" 11/27/1991\r\n'
                  b'"ACQ TRUE TIME:" 3003.878\r\n"ACQ LIVE TIME:" 3000.000\r\n"CHANNELS:" 4\r\n'
                  b'"ENERGY COEFF A0:" "19.6910873428"\r\n"ENERGY COEFF A1:" "3.73752567590"\r\n'
                  b'0: 5\r\n1: 6\r\n2: 7\r\n3: 8\r\n')
    r = read_spectra(p)[0][0]
    assert r.source_format == "aptec_ascii"
    assert r.counts == [5, 6, 7, 8] and r.sample_id == "CO60CAL" and r.detector == "NaI"
    assert r.real_time == pytest.approx(3003.878) and r.start_time == datetime(1991, 11, 27, 18, 57, 57)
    assert r.energy_coeffs == pytest.approx([19.6910873428, 3.7375256759])


def test_davidson_dll_layout(tmp_path):
    lines = ["", "", "10:15   01/02/95   ID=SAMPLE-1        ACQ AT 09:08:07   12/31/94",
             "LIVE TIME=  100 S  REAL TIME=  120 S  MEMORY= 1 OF 1 A", "",
             "DETECTOR=GE1        LLD=5", "AMP POLARITY=POS    ULD=4000",
             "AMP GAIN=0          ZERO LEVEL=3", "HVPS=0    VOLTS     THRESHOLD=0",
             "STABILIZER=OFF      P.U.REJECTOR=OFF", "",
             "CH   0       1       2       3       4       5       6       7       8",
             "CH   8       9      10      11      12      13      14      15      16"]
    p = tmp_path / "d.dav"
    p.write_bytes(("\r\n".join(lines) + "\r\n\x04").encode())
    r = read_spectra(p)[0][0]
    assert r.source_format == "davidson_ascii"
    assert r.counts == list(range(1, 17)) and r.sample_id == "SAMPLE-1" and r.detector == "GE1"
    assert (r.live_time, r.real_time) == (100.0, 120.0)
    assert r.start_time == datetime(1994, 12, 31, 9, 8, 7)
    assert r.extra["lld"] == 5 and r.extra["uld"] == 4000 and r.extra["zero_level"] == 3


def test_npl_and_rump_dll_layouts(tmp_path):
    p = tmp_path / "n.txt"
    p.write_bytes(b'\r\n Channel Contents for "N.TXT"\r\n\r\n\r\n Channel\r\n\r\n'
                  b'    1:      100      120        3        4        5        6        7        8\r\n'
                  b'    9:        9       10       11       12       13       14       15       16\r\n')
    r = read_spectra(p)[0][0]
    assert r.source_format == "npl_ascii"
    assert (r.live_time, r.real_time) == (100.0, 120.0) and r.counts == [0, 0] + list(range(3, 17))
    rump = ["EMPTY", "FILE          R.MAC", "IDENTIFIER    '4MeV He+ on Au'", "DATE          '94 DEC 31'",
            "MEV           4.000", "BEAM          4HE+", "CHARGE        1.00", "CURRENT       0.00",
            "GEOMETRY      Cornell", "THETA         20.0", "PHI           5.0",
            "CONVERSION    4.000    1.200", "CHOFF         0.00", "FWHM          20.0",
            "OMEGA         5.00", "CORRECTION    1.0000", "SWALLOW",
            "\t".join(str(i) for i in range(1, 9)), "", "ACTIVE", ""]
    p = tmp_path / "r.mac"
    p.write_bytes("\r\n".join(rump).encode())
    r = read_spectra(p)[0][0]
    assert r.source_format == "rump_ascii" and r.counts == list(range(1, 9))
    assert r.sample_id == "4MeV He+ on Au" and r.start_time == datetime(1994, 12, 31)


def test_iaea_dat_semantics_on_eml_header(tmp_path):
    p = tmp_path / "t.dat"
    rows = [" 240000      0      0      0      0      0      0      0      0      0"] + \
           ["      1      2      3      4      5      6      7      8      9     10"] * 3
    p.write_bytes(("TEST01            LT=   240000 ST=22-NOV-89 10:00:00              \r\n"
                   + "\r\n".join(rows) + "\r\n").encode())
    r = M.read_iaea_dat(p)[0]
    assert r.live_time == 240000 and r.real_time == 240000
    assert r.start_time == datetime(1989, 11, 22, 10, 0, 0) and r.sample_id == "TEST01"
    assert r.counts[:2] == [0, 0] and len(r.counts) == 40
    assert detect_format(p).key == "eml_sanderson"       # existing format keeps these files


def test_wallac_and_chandata_and_laval_layouts(tmp_path):
    p = tmp_path / "w.001"
    p.write_bytes(("HEADER 1\r\nHEADER 2\r\n600.5\r\n" + "".join(f"{i}\r\n" for i in range(1024))).encode())
    r = read_spectra(p)[0][0]
    assert r.source_format == "wallac_ascii" and r.counts == list(range(1024))
    assert r.live_time == r.real_time == 600.5
    with pytest.raises(Exception):
        M.write_wallac(_spec(2048), tmp_path / "x.001")
    p = tmp_path / "c.csv"
    p.write_bytes(b"".join(f'{i}, "{10 + 2 * i:.6g}", {i * 3}\r\n'.encode() for i in range(8)))
    r = read_spectra(p)[0][0]
    assert r.source_format == "chandata_csv" and r.counts == [i * 3 for i in range(8)]
    assert r.energy_of(5) == pytest.approx(20.0)
    lav = ["100", "120", "941230", "941231", "GE1", "1.5", "BEAKER", "0.5", "2", "16"] + \
          [str(i) for i in range(11, 16)] + ["0", "0", ""]
    p = tmp_path / "l.de1"
    p.write_bytes("\r\n".join(lav).encode())
    r = read_spectra(p)[0][0]
    assert r.source_format == "laval_ascii" and r.counts == [0] * 11 + list(range(11, 16))
    assert r.energy_coeffs == [2.0, 0.5] and r.start_time == datetime(1994, 12, 31)
    assert r.extra["sample_date"].startswith("1994-12-30") and r.detector == "GE1"


def test_sniffers_do_not_steal(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("\n".join(str(i) for i in range(20)))
    assert detect_format(p).key == "ascii1"
    p = tmp_path / "b.txt"
    p.write_text("\n".join(f"{i}\t{i * 2}" for i in range(20)))
    assert detect_format(p).key == "ascii2"
    p = tmp_path / "c.csv"
    p.write_text("Channel, Data\n" + "\n".join(f"{i}, {i}" for i in range(20)))
    assert detect_format(p).key != "chandata_csv"
    p = tmp_path / "d.dat"
    p.write_text("\n".join(f"{i}" for i in range(20)))
    assert detect_format(p) is None or detect_format(p).key != "iaea_ascii_dat"

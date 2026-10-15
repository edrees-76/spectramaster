"""Binary .dat with a 1670-byte text header (formats.lab_binary_dat).  The files are built here
with the inferred layout; no laboratory file is stored in the repository.  Set
SPECTRAMASTER_LAB_DAT_DIR to a folder of real files to also run the real-data check."""
from __future__ import annotations

import os
import struct
from datetime import datetime
from pathlib import Path

import pytest

from spectramaster.convert import read_spectra
from spectramaster.formats import detect_format, load_all
from spectramaster.formats.base import FormatError

load_all()


def _make(path: Path, counts, flag="2", d1="13/07/2006 09:55:01", d2="17/10/2006 12:44:41",
          live=1000, real=1002, coeffs=("2053.037000E-02", "3443.037000E-04"),
          desc="سيراميك مصرى".encode("cp1256"), extra=b"") -> Path:
    n = len(counts)
    h = bytearray(0x686)
    struct.pack_into(">I", h, 0, n // 256)
    t = (f"1       {d1} {d2} 1000.000000E-03 {flag} 100 {live:<9d} {real:<9d}").encode("latin-1")
    h[0x2C:0x2C + len(t)] = t
    h[0x9A:0x200] = b" " * (0x200 - 0x9A)
    h[0x9A:0x9A + len(desc)] = desc
    h[0x200:0x24C] = b" " * 0x4C
    h[0x200:0x208] = b"\\93xx #1"
    nums = list(coeffs) + ["0000.000000E+00"] * (12 - len(coeffs))
    txt = (" ".join(nums) + " 2").encode("latin-1")
    h[0x250:0x250 + len(txt)] = txt
    path.write_bytes(bytes(h) + struct.pack(f"<{n}i", *counts) + extra)
    return path


def test_reads_counts_calibration_times(tmp_path):
    counts = [0] * 8192
    counts[1861] = 3021
    p = _make(tmp_path / "a.dat", counts)
    assert detect_format(p).key == "lab_dat1670"
    s = read_spectra(p)[0][0]
    assert s.counts[1861] == 3021 and len(s.counts) == 8192
    assert s.energy_coeffs == pytest.approx([20.53037, 0.3443037])
    assert s.live_time == 1000 and s.real_time == 1002
    assert s.start_time == datetime(2006, 10, 17, 12, 44, 41)
    assert s.sample_id == "سيراميك مصرى"
    assert s.extra["header_label"] == "\\93xx #1"
    assert "start_time_inferred" not in s.extra


def test_flag_1_date_is_the_end_of_acquisition(tmp_path):
    p = _make(tmp_path / "b.dat", [1] * 8192, flag="1", d1="03/11/2009 14:12:43", d2="03/11/2009 14:12:43",
              live=1133, real=1134)
    s = read_spectra(p)[0][0]
    assert s.start_time == datetime(2009, 11, 3, 13, 53, 49)
    assert "end of acquisition" in s.extra["start_time_inferred"]


def test_4096_channels_and_trailing_bytes(tmp_path):
    p = _make(tmp_path / "c.dat", list(range(4096)), extra=b"\0" * 150)
    s = read_spectra(p)[0][0]
    assert len(s.counts) == 4096 and s.counts[-1] == 4095
    assert s.extra["trailing_bytes"] == 150


def test_header_only_file_is_rejected(tmp_path):
    p = _make(tmp_path / "d.dat", [0] * 8192)
    p.write_bytes(p.read_bytes()[:0x686])
    from spectramaster.formats.lab_binary_dat import read_lab_dat
    with pytest.raises(FormatError):
        read_lab_dat(p)


@pytest.mark.skipif(not os.environ.get("SPECTRAMASTER_LAB_DAT_DIR"), reason="laboratory files not available")
def test_real_files_put_known_lines_near_their_energies():
    """Reader check, not a calibration check: with the stored calibration Pb-214 351.93 keV must
    fall within 1.5 keV (a wrong offset, channel base or byte order would miss by far more).
    The stored calibrations themselves differ by period: Sep-Dec 2009 files are about +1 keV
    off at 352 keV (and the drift check flags them), 2004-2007 files agree within 0.1 keV."""
    import random
    from spectramaster.analysis import find_peaks
    root = Path(os.environ["SPECTRAMASTER_LAB_DAT_DIR"])
    files = sorted(p for p in root.rglob("*.dat") if p.stat().st_size == 34438)
    random.Random(1).shuffle(files)
    dev = []
    for f in files[:150]:
        s = read_spectra(f)[0][0]
        for p in find_peaks(s):
            if p.significance >= 20 and abs(p.energy - 351.93) < 5:
                dev.append(p.energy - 351.93)
    assert len(dev) >= 5
    assert max(abs(d) for d in dev) < 1.5

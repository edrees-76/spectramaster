"""Round-9 review Codex H2 and Gemini L2: a file whose header declares more channels than it
holds (a truncated or partially copied file) is refused instead of opening as a short or
zero-padded spectrum. Multi-block ASCII SPE, IEC 1455, Canberra S100 and Aptec ASCII.
Synthetic files only."""
from __future__ import annotations

import pytest

from spectramaster.formats import FormatError, load_all
from spectramaster.formats import aptec_import_ascii as M
from spectramaster.formats import ascii_formats as A
from spectramaster.formats import canberra_legacy as C
from spectramaster.model import Spectrum

load_all()


def _spec(n=100):
    s = Spectrum(counts=[(i * 7) % 50 + 1 for i in range(n)])
    s.live_time, s.real_time = 100.0, 101.0
    s.energy_coeffs = [0.5, 0.25]
    return s


# ------------------------------------------------------------------ multi-block SPE
SPE_HEAD = ["$SPEC_ID:", "synthetic", "$MEAS_TIM:", "100 100"]


def _write_lines(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def test_spe_two_blocks_one_spectrum_refused(tmp_path):
    pytest.importorskip("SpecUtils")
    from spectramaster.convert import read_spectra
    from spectramaster.formats import get_format
    p = _write_lines(tmp_path / "two.spe", SPE_HEAD + ["$DATA:", "0 4095", "1", "$DATA:", "0 8191", "2"])
    with pytest.raises(FormatError, match=r"2 \$DATA blocks but 1 measurement"):
        read_spectra(p)
    with pytest.raises(FormatError, match=r"2 \$DATA blocks"):
        read_spectra(p, get_format("iaea_spe"))


def test_spe_single_block_still_checked_and_accepted(tmp_path):
    pytest.importorskip("SpecUtils")
    from spectramaster.convert import read_spectra
    full = _write_lines(tmp_path / "full.spe", SPE_HEAD + ["$DATA:", "0 99"] + [str(i % 9) for i in range(100)])
    assert len(read_spectra(full)[0][0].counts) == 100
    excl = _write_lines(tmp_path / "excl.spe", SPE_HEAD + ["$DATA:", "0 99"] + [str(i % 9) for i in range(99)])
    assert len(read_spectra(excl)[0][0].counts) == 99        # exclusive end channel, as before
    short = _write_lines(tmp_path / "short.spe", SPE_HEAD + ["$DATA:", "0 99"] + ["1"] * 50)
    with pytest.raises(FormatError, match="declares 100 channels, 50 read"):
        read_spectra(short)


# ------------------------------------------------------------------ IEC 1455
def _iec_drop_rows(src, dst, rows):
    lines = src.read_bytes().split(b"\r\n")
    while lines and not lines[-1]:
        lines.pop()
    dst.write_bytes(b"\r\n".join(lines[:-rows]) + b"\r\n")
    return dst


def test_iec_truncated_refused(tmp_path):
    p = tmp_path / "full.iec"
    A.write_iec(_spec(100), p)
    assert len(A.read_iec(p)[0].counts) == 100
    short = _iec_drop_rows(p, tmp_path / "short.iec", 4)        # 20 channels missing
    with pytest.raises(FormatError, match="truncated IEC 1455 file: record 2 declares 100 channels, 80 read"):
        A.read_iec(short)


def test_iec_complete_partial_last_row_unchanged(tmp_path):
    p = tmp_path / "odd.iec"
    s = _spec(103)                                               # last data row holds 3 values
    A.write_iec(s, p)
    assert A.read_iec(p)[0].counts == s.counts


# ------------------------------------------------------------------ Canberra S100
def test_s100_truncated_refused(tmp_path):
    p = tmp_path / "full.mca"
    C.write_s100(_spec(256), p)
    assert len(C.read_s100(p)[0].counts) == 256
    short = tmp_path / "short.mca"
    short.write_bytes(p.read_bytes()[:128 + 4 * 10 + 2])
    with pytest.raises(FormatError, match="truncated S100 file: header declares 256 channels, 10 present"):
        C.read_s100(short)


def test_s100_header_only_refused(tmp_path):
    p = tmp_path / "full.mca"
    C.write_s100(_spec(256), p)
    hdr = tmp_path / "hdr.mca"
    hdr.write_bytes(p.read_bytes()[:128])
    with pytest.raises(FormatError):
        C.read_s100(hdr)


# ------------------------------------------------------------------ Aptec ASCII
APT_HEAD = ["TITLE: synthetic", "LABEL: x", "ACQ LIVE TIME: 100", "ACQ TRUE TIME: 101"]


def test_aptec_ascii_truncated_refused(tmp_path):
    p = _write_lines(tmp_path / "short.apt", APT_HEAD + ["CHANNELS: 4096", "0: 100"])
    with pytest.raises(FormatError, match="truncated Aptec ASCII file: CHANNELS: 4096, last data line is channel 0"):
        M.read_aptec_ascii(p)


def test_aptec_ascii_complete_and_gaps_unchanged(tmp_path):
    p = tmp_path / "full.apt"
    s = _spec(64)
    M.write_aptec_ascii(s, p)
    assert M.read_aptec_ascii(p)[0].counts == s.counts
    # a missing line inside the declared range still reads as 0 (Aptec zero-fills its memory)
    gap = _write_lines(tmp_path / "gap.apt", APT_HEAD + ["CHANNELS: 4", "0: 5", "1: 6", "3: 8"])
    assert M.read_aptec_ascii(gap)[0].counts == [5, 6, 0, 8]
    # no CHANNELS: line - the channel count comes from the data, as before
    nohdr = _write_lines(tmp_path / "nochan.apt", APT_HEAD + ["0: 5", "1: 6"])
    assert M.read_aptec_ascii(nohdr)[0].counts == [5, 6]

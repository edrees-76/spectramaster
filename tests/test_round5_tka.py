"""Round-5 review, H4: a TKA file named .txt (round5_tka_protocol.md)."""
import shutil

import pytest

from spectramaster.convert import read_spectra, resolve_format, write_spectrum
from spectramaster.formats import FormatError, load_all
from spectramaster.formats.base import detect
from spectramaster.model import Spectrum

load_all()


def _write(tmp_path, counts, key, name, **kw):
    p = tmp_path / ("src" + resolve_format(key).default_ext)
    write_spectrum(Spectrum(counts=counts, **kw), p, resolve_format(key))
    q = tmp_path / name
    shutil.copyfile(p, q)
    return q


def test_tka_named_txt_is_ambiguous(tmp_path):
    q = _write(tmp_path, [i % 31 for i in range(1024)], "tka", "a.txt", live_time=100.0, real_time=110.0)
    f, how, cands = detect(q)
    assert f is None and how == "ambiguous" and {c.key for c in cands} == {"ascii1", "tka"}
    with pytest.raises(FormatError, match="choose the input format"):
        read_spectra(q)
    s = read_spectra(q, resolve_format("tka"))[0][0]
    assert len(s.counts) == 1024 and sum(s.counts) == 15345 and s.live_time == 100.0 and s.real_time == 110.0


def test_one_column_txt_starting_with_zero_is_ascii1(tmp_path):
    q = _write(tmp_path, [0, 0] + [i % 31 for i in range(2, 1024)], "ascii1", "z.txt")
    f, how, _ = detect(q)
    assert f.key == "ascii1" and how == "usual"
    assert len(read_spectra(q)[0][0].counts) == 1024

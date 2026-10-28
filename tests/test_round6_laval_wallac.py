"""Round-6 review, H2: Laval and Wallac files named .txt (round6_laval_wallac_protocol.md)."""
import shutil
from datetime import datetime

import pytest

from spectramaster.convert import read_spectra, resolve_format, write_spectrum
from spectramaster.formats import FormatError, load_all
from spectramaster.formats.base import detect
from spectramaster.model import Spectrum

load_all()


def _write(tmp_path, spec, key, name):
    p = tmp_path / ("src" + resolve_format(key).default_ext)
    write_spectrum(spec, p, resolve_format(key))
    q = tmp_path / name
    shutil.copyfile(p, q)
    return q


def _spec():
    return Spectrum(counts=[i % 31 for i in range(1024)], live_time=100.0, real_time=110.0,
                    energy_coeffs=[0.0, 0.5], start_time=datetime(2024, 1, 1, 10))


@pytest.mark.parametrize("key,native", [("laval_ascii", "a.de1"), ("wallac_ascii", "a.001")])
def test_named_txt_is_ambiguous_and_reads_as_chosen(tmp_path, key, native):
    q = _write(tmp_path, _spec(), key, "a.txt")
    f, how, cands = detect(q)
    assert f is None and how == "ambiguous" and {c.key for c in cands} == {"ascii1", key}
    with pytest.raises(FormatError, match="choose the input format"):
        read_spectra(q)
    chosen = read_spectra(q, resolve_format(key))[0][0]
    own = read_spectra(_write(tmp_path, _spec(), key, native))[0][0]
    assert chosen.counts == own.counts and len(chosen.counts) == 1024
    assert (chosen.live_time, chosen.real_time, chosen.energy_coeffs) == (own.live_time, own.real_time,
                                                                         own.energy_coeffs)


def test_one_column_txt_starting_with_zero_stays_ascii1(tmp_path):
    q = _write(tmp_path, Spectrum(counts=[0, 0] + [i % 31 for i in range(2, 1024)]), "ascii1", "z.txt")
    f, how, _ = detect(q)
    assert f.key == "ascii1" and how == "usual"

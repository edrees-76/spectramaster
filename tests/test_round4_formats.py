"""Round-4 review, format findings (docs/baseline/round4_formats_protocol.md)."""
import math
import shutil
from datetime import datetime

import pytest

from spectramaster.analysis import find_peaks
from spectramaster.convert import counts_note, read_spectra, resolve_format, write_spectrum
from spectramaster.formats import load_all
from spectramaster.formats.base import detect
from spectramaster.formats.canberra_legacy import read_sanderson
from spectramaster.model import Spectrum


def _peak_spectrum(bad=None):
    c = [50.0] * 2048
    for i in range(-12, 13):
        c[1000 + i] += 5000.0 * math.exp(-0.5 * (i / 2.5) ** 2)
    if bad is not None:
        c[300] = bad
    return Spectrum(counts=c, live_time=100.0, energy_coeffs=[0.0, 0.5])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_peak_search_refuses_non_finite_counts(bad):
    with pytest.raises(ValueError, match="non-finite"):
        find_peaks(_peak_spectrum(bad))


def test_counts_note():
    assert counts_note([_peak_spectrum()]) is None
    assert "1 channels" in counts_note([_peak_spectrum(float("nan"))])


def _sanderson_file(tmp_path, c0, c1, lt=100):
    counts = [c0, c1] + [10, 20] * 509
    lines = [f"CASE                  LT=   {lt} ST= 1-JAN-24 10:00:00"]
    for k in range(0, len(counts), 10):
        lines.append("".join(f"{v:8d}" for v in counts[k:k + 10]))
    p = tmp_path / "case.dat"
    p.write_text("\r\n".join(lines) + "\r\n", encoding="latin-1")
    return read_sanderson(p)[0]


def test_sanderson_time_channels_only_with_a_possible_real_time(tmp_path):
    s = _sanderson_file(tmp_path, 100, 500)                 # Gemini's case: counts, not times
    assert s.counts[:2] == [100, 500] and s.real_time == 100.0 and "time_channels" not in s.extra
    assert "channel 1" in s.extra["time_channels_note"]
    s = _sanderson_file(tmp_path, 100, 0)                   # EML TEST layout: real time not given
    assert s.counts[:2] == [0, 0] and s.real_time == 100.0 and s.extra["time_channels"]
    s = _sanderson_file(tmp_path, 100, 130)
    assert s.counts[:2] == [0, 0] and s.real_time == 130.0


def test_chn_unit_gain_warning(tmp_path):
    s = Spectrum(counts=[5] * 1024, live_time=100.0, real_time=110.0, energy_coeffs=[0.0, 1.0],
                 start_time=datetime(2024, 1, 1, 10))
    w = write_spectrum(s, tmp_path / "x.chn", resolve_format("ortec_chn"))
    assert any("1 keV per channel" in x for x in w)


def _written(tmp_path, key, spec, name):
    load_all()
    f = resolve_format(key)
    p = tmp_path / ("src" + f.default_ext)
    write_spectrum(spec, p, f)
    q = tmp_path / name
    shutil.copyfile(p, q)
    return q


def test_specutils_txt_preferred_over_ascii(tmp_path):
    pytest.importorskip("SpecUtils")
    s = Spectrum(counts=[i % 31 for i in range(1024)], live_time=100.0, real_time=110.0,
                 energy_coeffs=[0.0, 0.5], start_time=datetime(2024, 1, 1, 10))
    q = _written(tmp_path, "specutils_txt", s, "a.txt")
    r, used = read_spectra(q)
    assert used.key == "specutils_txt" and r[0].live_time == 100.0 and r[0].real_time == 110.0


def test_tka_with_another_extension_is_ambiguous(tmp_path):
    pytest.importorskip("SpecUtils")
    s = Spectrum(counts=[i % 31 for i in range(1024)], live_time=100.0, real_time=110.0)
    f, how, cands = detect(_written(tmp_path, "tka", s, "a.xyz"))
    assert how == "ambiguous" and {c.key for c in cands} == {"tka", "ascii1"}
    z = Spectrum(counts=[0, 0] + [i % 31 for i in range(2, 1024)], live_time=100.0)
    f, how, _ = detect(_written(tmp_path, "ascii1", z, "z.xyz"))
    assert f.key == "ascii1"

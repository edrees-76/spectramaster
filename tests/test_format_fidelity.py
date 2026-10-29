"""What a format cannot hold is refused or reported, never changed silently (second external review)."""
import datetime as dt

import numpy as np
import pytest
from numpy.polynomial import polynomial as P

from spectramaster.convert import (CP1256_TEXT, DATE_REQUIRED, INTEGER_COUNTS, NO_NEGATIVE_COUNTS, read_spectra,
                                   resolve_format, write_spectrum)
from spectramaster.formats import FormatError, load_all, writable_formats
from spectramaster.model import Spectrum

START = dt.datetime(2020, 5, 6, 7, 8, 9)


def _formats():
    load_all()
    return [f for f in writable_formats() if f.can_read]


def _spec(counts=None, **kw):
    kw.setdefault("start_time", START)
    return Spectrum(counts=[7.0] * 1024 if counts is None else counts, energy_coeffs=[0.0, 0.5],
                    live_time=100.0, real_time=101.0, **kw)


def _roundtrip(tmp_path, fmt, spec, tag):
    out = tmp_path / (tag + fmt.default_ext)
    warnings = write_spectrum(spec, out, fmt)
    return warnings, read_spectra(out, fmt)[0][0]


@pytest.mark.parametrize("fmt", _formats(), ids=lambda f: f.key)
def test_negative_counts_kept_or_refused(tmp_path, fmt):
    c = [7.0] * 1024
    c[512] = -4.0
    try:
        _w, back = _roundtrip(tmp_path, fmt, _spec(c), "neg")
    except FormatError as e:
        assert "negative" in str(e) or "unsigned" in str(e) or "24-bit" in str(e)
        return
    assert fmt.key not in NO_NEGATIVE_COUNTS
    assert -4.0 in back.counts, f"{fmt.key} changed a negative count silently"


@pytest.mark.parametrize("fmt", _formats(), ids=lambda f: f.key)
def test_fractional_counts_kept_or_reported(tmp_path, fmt):
    c = [7.0] * 1024
    c[513] = 3.4
    w, back = _roundtrip(tmp_path, fmt, _spec(c), "frac")
    kept = any(abs(x - 3.4) < 1e-5 for x in back.counts)
    assert kept == (fmt.key not in INTEGER_COUNTS), fmt.key
    assert any("rounded" in x for x in w) == (not kept)


@pytest.mark.parametrize("fmt", _formats(), ids=lambda f: f.key)
def test_unknown_start_time_stays_unknown_or_is_reported(tmp_path, fmt):
    w, back = _roundtrip(tmp_path, fmt, _spec(start_time=None), "date")
    assert (back.start_time is not None) == (fmt.key in DATE_REQUIRED), fmt.key
    assert any("placeholder" in x for x in w) == (fmt.key in DATE_REQUIRED)


@pytest.mark.parametrize("fmt", _formats(), ids=lambda f: f.key)
def test_arabic_indic_digits_not_lost(tmp_path, fmt):
    w, back = _roundtrip(tmp_path, fmt, _spec(sample_id="عينة ١٢"), "digits")
    if not back.sample_id or back.sample_id.startswith("GR-13"):
        return                                    # the format keeps no sample ID
    assert "12" in back.sample_id or "١٢" in back.sample_id, (fmt.key, back.sample_id)
    if fmt.key in CP1256_TEXT:
        assert back.sample_id.startswith("عينة") and any("0-9" in x for x in w)


@pytest.mark.parametrize("fmt", _formats(), ids=lambda f: f.key)
def test_numpy_counts_and_first_channel(tmp_path, fmt):
    counts = np.arange(1024, dtype=float) % 50 + 5
    s = _spec(counts.copy(), first_channel=100)
    s.energy_coeffs = [10.0, 0.5]
    try:
        _w, back = _roundtrip(tmp_path, fmt, s, "fc")
    except FormatError as e:
        assert "offset" in str(e) or "1024 channels" in str(e) or "rebin" in str(e)
        _w, back = _roundtrip(tmp_path, fmt, _spec(counts.copy()), "np")
        assert back.num_channels >= 256
        return
    if not back.energy_coeffs or back.num_channels < 1024:
        return                                    # no calibration stored, or a fixed channel count
    pad = back.num_channels - 1024                # writers without an offset pad zeros below it
    k = 500
    e_in = P.polyval(100 + k, s.energy_coeffs)
    e_out = P.polyval(back.first_channel + pad + k, back.energy_coeffs)
    assert back.counts[pad + k] == pytest.approx(counts[k], abs=0.5)
    assert e_out == pytest.approx(e_in, abs=0.05), fmt.key


def test_chn_unknown_date_reads_back_unknown(tmp_path):
    fmt = resolve_format("ortec_chn")
    w, back = _roundtrip(tmp_path, fmt, _spec(start_time=None), "chn")
    assert back.start_time is None and not w
    _w, back = _roundtrip(tmp_path, fmt, _spec(), "chn2")
    assert back.start_time == START


def test_non_finite_counts_refused(tmp_path):
    pytest.importorskip("SpecUtils")      # format read or written through SpecUtils
    c = [7.0] * 1024
    c[3] = float("nan")
    with pytest.raises(FormatError, match="non-finite"):
        write_spectrum(_spec(c), tmp_path / "x.spe", resolve_format("iaea_spe"))


def test_stripped_spectrum_not_subtracted_again():
    from spectramaster.analysis.background import check_not_subtracted, not_poisson_note
    from spectramaster.tools import spectrum_ops as ops
    a, b = _spec([100.0] * 1024), _spec([10.0] * 1024)
    s = ops.strip(a, b)
    with pytest.raises(ValueError, match="stripped"):
        check_not_subtracted(s)
    assert "not Poisson" in not_poisson_note(s)
    n = ops.normalize(a, 2.0)
    check_not_subtracted(n)
    assert "Normalized" in not_poisson_note(n)
    assert not_poisson_note(a) is None

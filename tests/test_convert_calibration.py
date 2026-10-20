"""Calibration terms beyond what a format can store are refitted, not dropped."""
import pytest

from spectramaster.convert import MAX_CAL_TERMS, read_spectra, resolve_format, write_spectrum
from spectramaster.model import Spectrum

# CHERNBKG.S0's cubic calibration (E(4096) = 808.081 keV on the Aptec screen)
CUBIC = [43.20886884741018, 0.18637950888959978, 1.3081293666458735e-07, -1.0670804674551158e-11]


def _spectrum():
    return Spectrum(counts=[float(i % 50) for i in range(8192)], energy_coeffs=list(CUBIC),
                    live_time=1451.4, real_time=1500.0, sample_id="cubic")


@pytest.mark.parametrize("key", sorted(k for k, n in MAX_CAL_TERMS.items() if n == 3))
def test_refit_keeps_energies_close(tmp_path, key):
    fmt = resolve_format(key)
    src = _spectrum()
    out = tmp_path / ("x" + fmt.default_ext)
    warnings = write_spectrum(src, out, fmt)
    assert any("refitted" in w for w in warnings)
    back = read_spectra(out, fmt)[0][0]
    assert len(back.energy_coeffs) <= MAX_CAL_TERMS[key]
    worst = max(abs(src.energy_of(c) - back.energy_of(c)) for c in range(0, 8192, 16))
    assert worst < 0.35  # truncation alone would be ~5.7 keV


def test_no_warning_when_format_holds_calibration(tmp_path):
    fmt = resolve_format("iaea_spe")
    assert write_spectrum(_spectrum(), tmp_path / "x.spe", fmt) == []


def test_quadratic_untouched(tmp_path):
    fmt = resolve_format("ortec_chn")
    s = _spectrum()
    s.energy_coeffs = CUBIC[:3]
    assert write_spectrum(s, tmp_path / "x.chn", fmt) == []
    back = read_spectra(tmp_path / "x.chn", fmt)[0][0]
    assert back.energy_coeffs == pytest.approx(CUBIC[:3], rel=1e-6)

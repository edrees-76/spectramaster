"""Placeholder energy calibration E = channel (docs/baseline/placeholder_energy_calibration_protocol.md)."""
from __future__ import annotations

import struct

import pytest

from spectramaster import cli
from spectramaster.convert import calibration_note, read_spectra
from spectramaster.formats import get_format, load_all
from spectramaster.model import Spectrum


def _spec(e, f=()):
    return Spectrum(counts=[float(i % 50) for i in range(1024)], energy_coeffs=list(e), fwhm_coeffs=list(f),
                    live_time=10.0, real_time=11.0)


def _chn(tmp_path, e, f=(0.0, 0.0, 0.0)):
    """A CHN file whose -102 trailer holds exactly `e` and `f`."""
    load_all()
    p = tmp_path / "x.chn"
    get_format("ortec_chn").writer(_spec([0.5, 0.3]), p)
    b = bytearray(p.read_bytes())
    t = 32 + 4 * 1024
    struct.pack_into("<3f", b, t + 4, *e)
    struct.pack_into("<3f", b, t + 16, *f)
    p.write_bytes(bytes(b))
    return p


def test_chn_identity_calibration_is_read_as_uncalibrated(tmp_path):
    s = read_spectra(_chn(tmp_path, (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)))[0][0]
    assert s.energy_coeffs == [] and s.fwhm_coeffs == []
    assert s.extra["stored_energy_coeffs"] == [0.0, 1.0] and s.extra["stored_fwhm_coeffs"] == [1.0]
    assert s.extra["energy_calibration"] == "placeholder" and calibration_note([s])


@pytest.mark.parametrize("e", [(0.0, 1.0, 1e-6), (0.001, 1.0, 0.0), (0.0, 1.0001, 0.0), (-1.07, 0.429, 0.0)])
def test_other_chn_calibrations_are_kept(tmp_path, e):
    s = read_spectra(_chn(tmp_path, e))[0][0]
    assert s.energy_coeffs and "energy_calibration" not in s.extra and calibration_note([s]) is None


def test_cnf_checks_the_stored_genie_values(tmp_path):
    load_all()
    f = get_format("ci_cnf")
    p = tmp_path / "g.cnf"
    f.writer(_spec([1.0, 1.0]), p)            # stored by Genie numbering as (0, 1)
    s = read_spectra(p)[0][0]
    assert s.energy_coeffs == [] and s.extra["stored_energy_coeffs"][:2] == [0.0, 1.0]
    f.writer(_spec([0.0, 1.0]), p)            # stored as (-1, 1): a real calibration
    assert read_spectra(p)[0][0].energy_coeffs == pytest.approx([0.0, 1.0])


def test_cli_info_prints_the_note(tmp_path, capsys):
    cli.main(["info", str(_chn(tmp_path, (0.0, 1.0, 0.0)))])
    out = capsys.readouterr().out
    assert "default of an uncalibrated MCA" in out

"""Non-ASCII (Arabic) sample text: formats that cannot store it must warn."""
import datetime as dt

import pytest

from spectramaster.convert import ASCII_ONLY_TEXT, read_spectra, write_spectrum
from spectramaster.formats import load_all, writable_formats
from spectramaster.model import Spectrum

ASCII_WARNING = "stores only ASCII text"     # format names may contain "ASCII" too
AR_ID, AR_DESC = "عينة شاي", "وصف عربي للعينة"
EN_ID, EN_DESC = "TEA 12", "Black tea sample"


def _spec(sid, desc):
    return Spectrum(counts=[float(i % 50) for i in range(1024)], energy_coeffs=[0.0, 0.5],
                    live_time=100.0, real_time=101.0, sample_id=sid, description=desc,
                    start_time=dt.datetime(2020, 5, 6, 7, 8, 9))


def _roundtrip(tmp_path, fmt, sid, desc, tag):
    out = tmp_path / (tag + fmt.default_ext)
    warnings = write_spectrum(_spec(sid, desc), out, fmt)
    back = read_spectra(out, fmt)[0][0]
    return warnings, back.sample_id + " | " + back.description


def _formats():
    load_all()
    return [f for f in writable_formats() if f.can_read]


@pytest.mark.parametrize("fmt", _formats(), ids=lambda f: f.key)
def test_ascii_only_set_matches_behaviour(tmp_path, fmt):
    """A format keeping ASCII text but losing Arabic must be in ASCII_ONLY_TEXT (and warn)."""
    w_en, en = _roundtrip(tmp_path, fmt, EN_ID, EN_DESC, "en")
    w_ar, ar = _roundtrip(tmp_path, fmt, AR_ID, AR_DESC, "ar")
    assert not any(ASCII_WARNING in w for w in w_en)
    keeps = [x for x, y in ((EN_ID, AR_ID), (EN_DESC, AR_DESC)) if x.lower() in en.lower()]
    loses = [x for x, y in ((EN_ID, AR_ID), (EN_DESC, AR_DESC)) if x.lower() in en.lower() and y not in ar]
    if loses:
        assert fmt.key in ASCII_ONLY_TEXT, f"{fmt.key} loses Arabic {loses}"
        assert any(ASCII_WARNING in w for w in w_ar)
    elif keeps:
        assert fmt.key not in ASCII_ONLY_TEXT
        assert not any(ASCII_WARNING in w for w in w_ar)


def test_cli_prints_text_warning(tmp_path, capsys):
    from spectramaster import cli
    from spectramaster.convert import resolve_format
    src = tmp_path / "a.spe"
    write_spectrum(_spec(AR_ID, ""), src, resolve_format("iaea_spe"))
    cli.main(["convert", str(src), "--to", "ortec_chn", "--out", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert "warning:" in out and "ASCII" in out and "sample ID" in out


def test_ascii_text_no_warning(tmp_path):
    from spectramaster.convert import resolve_format
    assert write_spectrum(_spec(EN_ID, EN_DESC), tmp_path / "x.cnf", resolve_format("ci_cnf")) == []

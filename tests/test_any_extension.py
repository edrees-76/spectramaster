"""Reading spectrum files with any extension (docs/baseline/any_extension_protocol.md, AX.C5)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectramaster import cli
from spectramaster.convert import content_note, read_spectra, write_spectrum
from spectramaster.formats import FormatError, base, detect, get_format, load_all
from spectramaster.model import Spectrum
from spectramaster.validation import any_extension as ax

load_all()
RESULTS = Path(__file__).resolve().parent.parent / "docs" / "baseline" / "after_AX1"


def _spec(n=1024):
    return Spectrum(counts=[float(i % 97) for i in range(n)], energy_coeffs=[0.5, 0.3], live_time=100.0,
                    real_time=101.0, sample_id="S1")


def _write(fmt_key, path):
    write_spectrum(_spec(), path, get_format(fmt_key))
    return path


def test_own_extension_is_unchanged_and_carries_no_note(tmp_path):
    spectra, fmt = read_spectra(_write("ascii1", tmp_path / "a.txt"))
    assert fmt.key == "ascii1" and detect(tmp_path / "a.txt")[1] == "usual"
    assert "format_detection" not in spectra[0].extra and content_note(spectra, fmt) is None


def test_npl_with_its_header_needed_no_extension_before(tmp_path):
    odd = tmp_path / "a.xyz"
    odd.write_bytes(_write("npl_ascii", tmp_path / "a.txt").read_bytes())
    assert detect(odd)[:2] == (get_format("npl_ascii"), "usual")       # "Channel Contents for" header


@pytest.mark.parametrize("key", ["ascii1", "ascii2", "chandata_csv", "wallac_ascii", "laval_ascii", "jcac_vax"])
def test_other_extension_is_recognised_from_the_content(tmp_path, key):
    own = _write(key, tmp_path / ("own" + get_format(key).default_ext))
    odd = tmp_path / "spectrum.xyz"
    odd.write_bytes(own.read_bytes())
    s0, _ = read_spectra(own)
    s1, fmt = read_spectra(odd)
    assert fmt.key == key and s1[0].extra["format_detection"] == "content"
    assert s1[0].counts == s0[0].counts and s1[0].live_time == s0[0].live_time
    assert get_format(key).name in content_note(s1, fmt)


def test_excel_reads_whatever_the_name(tmp_path):
    own = _write("excel_xlsx", tmp_path / "a.xlsx")
    odd = tmp_path / "a.bin"
    odd.write_bytes(own.read_bytes())
    s, fmt = read_spectra(odd)
    assert fmt.key == "excel_xlsx" and s[0].counts == read_spectra(own)[0][0].counts


def test_note_is_not_carried_into_a_converted_file(tmp_path):
    odd = tmp_path / "a.xyz"
    odd.write_bytes(_write("ascii1", tmp_path / "a.txt").read_bytes())
    s, _ = read_spectra(odd)
    out = tmp_path / "b.xlsx"
    write_spectrum(s[0], out, get_format("excel_xlsx"))
    assert "format_detection" not in read_spectra(out)[0][0].extra


def test_ambiguity_is_refused_with_the_candidates(tmp_path, monkeypatch):
    odd = tmp_path / "a.xyz"
    odd.write_bytes(_write("chandata_csv", tmp_path / "a.csv").read_bytes())
    monkeypatch.setattr(base, "CONTENT_PREFERENCE", ())          # Channel Data CSV also looks like ASCII-2
    fmt, how, cands = detect(odd)
    assert fmt is None and how == "ambiguous" and {f.key for f in cands} == {"chandata_csv", "ascii2"}
    with pytest.raises(FormatError, match="choose the input format") as e:
        read_spectra(odd)
    assert get_format("ascii2").name in str(e.value)


def test_unrecognised_file_says_the_format_can_be_chosen(tmp_path):
    p = tmp_path / "notes.xyz"
    p.write_text("not a spectrum\n" * 20, encoding="utf-8")
    with pytest.raises(FormatError, match="chosen by hand"):
        read_spectra(p)


def test_tka_with_another_extension_is_read_as_ascii1_with_the_note(tmp_path):
    """Known limit stated in the protocol: TKA cannot be told from ASCII-1 by content."""
    odd = tmp_path / "a.xyz"
    odd.write_bytes(_write("tka", tmp_path / "a.tka").read_bytes())
    s, fmt = read_spectra(odd)
    assert fmt.key == "ascii1" and content_note(s, fmt)


def test_cli_info_shows_the_note(tmp_path, capsys):
    odd = tmp_path / "a.xyz"
    odd.write_bytes(_write("ascii2", tmp_path / "a.txt").read_bytes())
    assert cli.main(["info", str(odd)]) == 0
    assert "recognised from the content" in capsys.readouterr().out


def test_folder_scan_adds_recognised_files_of_any_extension(tmp_path):
    pytest.importorskip("PySide6")
    from spectramaster.gui.dialogs import scan_spectrum_files
    (tmp_path / "s.xyz").write_bytes(_write("ascii1", tmp_path / "x.txt").read_bytes())
    (tmp_path / "x.txt").unlink()
    (tmp_path / "readme.md").write_text("# notes\n", encoding="utf-8")
    (tmp_path / "notes.xyz").write_text("not a spectrum\n" * 20, encoding="utf-8")
    (tmp_path / "a.chn").write_bytes(b"\0" * 10)                  # known extension: kept, as before
    assert [p.name for p in scan_spectrum_files(tmp_path, True)] == ["a.chn", "s.xyz"]


@pytest.mark.skipif(not (RESULTS / "any_extension_results.json").is_file(), reason="results not recorded")
def test_recorded_evaluation_is_reproduced():
    before = json.loads((RESULTS / "any_extension_before.json").read_text(encoding="utf-8"))
    rec = json.loads((RESULTS / "any_extension_results.json").read_text(encoding="utf-8"))
    assert ax.evaluate(before, rec["after"]) == rec["evaluation"]

"""Round-8 review Codex H2: an ASCII SPE file whose $DATA declares more channels than it holds
(a truncated or partially copied file) is refused instead of opening as a short spectrum.
Synthetic files only."""
from __future__ import annotations

import pytest

pytest.importorskip("SpecUtils")

from spectramaster.convert import read_spectra  # noqa: E402
from spectramaster.formats import FormatError, get_format, load_all  # noqa: E402
from spectramaster.formats.specutils_bridge import _spe_declared_channels  # noqa: E402

load_all()

HEADER = ["$SPEC_ID:", "synthetic", "$MEAS_TIM:", "100 100", "$DATA:", "0 4095"]


def _write(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def test_truncated_spe_refused(tmp_path):
    p = _write(tmp_path / "trunc.spe", HEADER + ["5", "$ENDRECORD:"])
    with pytest.raises(FormatError, match=r"truncated SPE file: \$DATA declares 4096 channels, 1 read"):
        read_spectra(p)


def test_truncated_spe_refused_at_eof(tmp_path):
    p = _write(tmp_path / "trunc_eof.spe", HEADER + ["5"])
    with pytest.raises(FormatError, match="truncated SPE file"):
        read_spectra(p, get_format("iaea_spe"))


def test_complete_spe_unchanged(tmp_path):
    counts = [i % 50 for i in range(4096)]
    p = _write(tmp_path / "full.spe", HEADER + [str(c) for c in counts])
    spectra, fmt = read_spectra(p)
    assert fmt.key == "iaea_spe"
    assert len(spectra) == 1
    assert list(spectra[0].counts) == [float(c) for c in counts]
    assert spectra[0].live_time == 100.0


def test_one_channel_short_accepted(tmp_path):
    # exclusive end channel, as in part of the public IAEA IDB set ("0 8191" with 8191 values)
    p = _write(tmp_path / "excl.spe", HEADER + [str(i % 50) for i in range(4095)])
    spectra, _ = read_spectra(p)
    assert len(spectra[0].counts) == 4095


def test_two_channels_short_refused(tmp_path):
    p = _write(tmp_path / "short2.spe", HEADER + [str(i % 50) for i in range(4094)])
    with pytest.raises(FormatError, match="declares 4096 channels, 4094 read"):
        read_spectra(p)


def test_offset_range_complete_unchanged(tmp_path):
    lines = ["$SPEC_ID:", "x", "$MEAS_TIM:", "100 100", "$DATA:", "10 4095"]
    p = _write(tmp_path / "off.spe", lines + [str(i % 50) for i in range(4086)])
    spectra, _ = read_spectra(p)
    assert len(spectra[0].counts) == 4086


def test_more_values_than_declared_unchanged(tmp_path):
    p = _write(tmp_path / "extra.spe", HEADER + [str(i % 50) for i in range(5000)])
    spectra, _ = read_spectra(p)
    assert len(spectra[0].counts) == 5000          # current SpecUtils behaviour, kept


def test_missing_data_line_unchanged(tmp_path):
    p = _write(tmp_path / "nodata.spe", ["$SPEC_ID:", "x", "$MEAS_TIM:", "100 100"]
               + [str(i) for i in range(10)])
    with pytest.raises(FormatError) as exc:
        read_spectra(p, get_format("iaea_spe"))
    assert "truncated" not in str(exc.value)       # SpecUtils' own refusal, as before


@pytest.mark.parametrize("lines", [
    ["$SPEC_ID:", "x"],                            # no $DATA
    ["$DATA:"],                                    # no range
    ["$DATA:", "0"],                               # one number
    ["$DATA:", "a b"],                             # not numbers
    ["$DATA:", "10 5"],                            # reversed
])
def test_unparsable_declaration_means_no_check(tmp_path, lines):
    assert _spe_declared_channels(_write(tmp_path / "h.spe", lines)) == []


def test_declaration_parsed(tmp_path):
    assert _spe_declared_channels(_write(tmp_path / "h.spe", ["$data:", "", "  0   4095  "])) == [4096]

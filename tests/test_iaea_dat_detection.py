"""IAEA ASCII .dat output read as EML Sanderson (docs/baseline/iaea_dat_detection_protocol.md)."""
from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from spectramaster.convert import read_spectra
from spectramaster.formats import aptec_import_ascii as M
from spectramaster.formats import canberra_legacy as C
from spectramaster.model import Spectrum


def _spec(n=512, peak=5000) -> Spectrum:
    counts = [(i * 37) % 1000 + (peak if 300 <= i <= 302 else 0) for i in range(n)]
    return Spectrum(counts=counts, live_time=3000.0, real_time=3004.0,
                    start_time=datetime(1991, 11, 27, 18, 57, 57), sample_id="CO60CAL")


def _same(a: Spectrum, b: Spectrum) -> bool:
    return (a.counts == b.counts and a.live_time == b.live_time and a.real_time == b.real_time
            and a.sample_id == b.sample_id and a.start_time == b.start_time)


@pytest.mark.parametrize("name", ["x.dat", "x.xyz", "x"])
@pytest.mark.parametrize("peak", [5000, 2_000_000, 20_000_000])     # field width 7, 8, 9
def test_our_output_reads_like_the_iaea_reader_under_any_name(tmp_path, name, peak):
    p = tmp_path / name
    M.write_iaea_dat(_spec(peak=peak), p)
    got, ref = read_spectra(p)[0][0], M.read_iaea_dat(p)[0]
    assert _same(got, ref)
    assert got.real_time == 3004.0 and got.counts[:2] == [0, 0]


def test_time_channels_only_when_channel_0_repeats_lt(tmp_path):
    head = "TEST99            LT=   240000 ST=22-NOV-89 10:00:00"
    rows = ["".join(f"{v:7d}" for v in range(10 * i, 10 * i + 10)) for i in range(5)]
    p = tmp_path / "a.dat"
    p.write_bytes(("\r\n".join([head] + rows) + "\r\n").encode())
    r = C.read_sanderson(p)[0]
    assert r.counts[:2] == [0, 1] and r.real_time == 240000 and "time_channels" not in r.extra
    rows[0] = f"{240000:7d}{240100:7d}" + rows[0][14:]
    p.write_bytes(("\r\n".join([head] + rows) + "\r\n").encode())
    r = C.read_sanderson(p)[0]
    assert r.counts[:3] == [0, 0, 2] and r.real_time == 240100 and r.extra["time_channels"]


def test_touching_fields_are_read_fixed_width_under_any_name(tmp_path):
    head = "TEST98            LT=   240000 ST=22-NOV-89 10:00:00"
    rows = ["".join(f"{v:7d}" for v in ([240000, 0] + list(range(2, 10)) if i == 0 else range(10 * i, 10 * i + 10)))
            for i in range(5)]
    rows[4] = rows[4][:28] + "1234567" + rows[4][35:]       # fields 3 and 4 touch, past the rows both tests read
    reads = []
    for name in ("b.dat", "b.xyz"):
        p = tmp_path / name
        p.write_bytes(("\r\n".join([head] + rows) + "\r\n").encode())
        r = read_spectra(p)[0][0]
        assert r.source_format == "eml_sanderson" and len(r.counts) == 50
        reads.append(dataclasses.replace(r, extra={}))
    assert reads[0].counts == reads[1].counts and reads[0].counts[44] == 1234567

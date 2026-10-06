"""Build expected.json: reference values that do NOT come from SpectraMaster.

Each entry's `oracle` says where the numbers come from:
  source_test   - asserted in the source project's own unit tests (quoted in `ref`)
  header_text   - read by eye / tiny parser from the file's own plain-text header or
                  documented fixed binary header fields (independent of our readers)
  cross_format  - same measurement stored in another format by the source project
                  (e.g. becquerel's samples_converted/*.spe written by becquerel from
                  the .cnf/.Spc); counts are parsed here from the plain-text IAEA SPE.
Regenerate with:  python test_corpus/build_expected.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = [0, 1, 2, 100, 500, 1000, 2000]


def spe_data(rel: str) -> list[float]:
    """Minimal independent IAEA SPE $DATA parser (one count per line)."""
    lines = (HERE / rel).read_text(encoding="latin-1").splitlines()
    i = lines.index("$DATA:")
    first, last = (int(x) for x in lines[i + 1].split())
    vals = []
    for ln in lines[i + 2:]:
        if ln.startswith("$"):
            break
        vals.extend(float(x) for x in ln.split())
    return vals[: last - first + 1]


def probe(counts: list[float]) -> dict:
    return {str(k): counts[k] for k in PROBE if k < len(counts)}


E = []

# ---------------------------------------------------------------- pyne
E.append(dict(path="pyne/tests/gv_format_spect.spe", oracle="source_test",
              ref="pyne tests/test_spectrometry.py::test_read_dollar_spe",
              num_channels=1024, live_time=199.0, real_time=209.0,
              start_time="2014-08-01T11:43:41", first_channel=0))
E.append(dict(path="pyne/tests/test.spe", oracle="source_test",
              ref="pyne tests/test_spectrometry.py::test_read_spe (ORTEC 'ACQUISITION INFORMATION' text report)",
              num_channels=1024, live_time=199.800003, real_time=209.100006,
              start_time="2014-08-01T11:43:41", first_channel=0,
              same_counts_index={"other": "pyne/tests/gv_format_spect.spe", "index": 100}))

# ---------------------------------------------------------------- becquerel
for orig, conv, start in [
    ("becquerel/tests/samples/Alcatraz14.Spc", "becquerel/tests/samples_converted/Alcatraz14.spe",
     "2012-09-17T13:41:07"),
    ("becquerel/tests/samples/01122014152731-GT01122014182338-GA37.4963000N-GO122.4633000W.cnf",
     "becquerel/tests/samples_converted/01122014152731-GT01122014182338-GA37.4963000N-GO122.4633000W.spe",
     "2014-01-12T15:12:28"),
]:
    c = spe_data(conv)
    lt, rt = None, None
    lines = (HERE / conv).read_text(encoding="latin-1").splitlines()
    lt, rt = (float(x) for x in lines[lines.index("$MEAS_TIM:") + 1].split())
    common = dict(num_channels=len(c), live_time=lt, real_time=rt, start_time=start,
                  total_counts=sum(c), counts_probe=probe(c))
    E.append(dict(path=conv, oracle="header_text", ref="IAEA SPE text written by becquerel", **common))
    if orig.endswith(".cnf"):
        # becquerel's CNF reader returns [0] + Genie channels 1..N-1 (it reads 4 bytes
        # before the data and drops the last channel).  Genie-2000's own channel listing
        # (REPORT with CTLFILES/CSV.TPL) shows the first stored value is Genie channel 1,
        # i.e. index 0 for us: our counts[k] == becquerel[k + 1].  The last channel
        # (lost by becquerel) is 0 in Genie's listing, so totals are unchanged.
        common = dict(common, counts_probe={str(k): c[k + 1] for k in PROBE if k + 1 < len(c)})
    E.append(dict(path=orig, oracle="cross_format",
                  ref=f"becquerel's reading of this file, saved as {conv}", **common))

# ---------------------------------------------------------------- MBFS (original lab files)
c = spe_data("MBFS/MBFS/Converter/example/17_1113_3A.Spe")
E.append(dict(path="MBFS/MBFS/Converter/example/17_1113_3A.Spe", oracle="header_text",
              ref="$MEAS_TIM 83736 83925, $DATE_MEA 02/15/2016 17:12:17",
              num_channels=8192, live_time=83736.0, real_time=83925.0,
              start_time="2016-02-15T17:12:17", total_counts=sum(c), counts_probe=probe(c)))
E.append(dict(path="MBFS/MBFS/Converter/example/8H4275.Chn", oracle="header_text",
              ref="CHN header: real 1544549 ticks, live 1440000 ticks (x20 ms), date '30MAY85 ', time '1908', seconds field NUL",
              num_channels=8192, live_time=28800.0, real_time=30890.98,
              start_time="1985-05-30T19:08:00"))
E.append(dict(path="MBFS/MBFS/Converter/example/8H4275.Spc", oracle="cross_format",
              ref="same acquisition as 8H4275.Chn (stored by the lab in both formats)",
              num_channels=8192, live_time=28800.0, real_time=30890.98,
              start_time="1985-05-30T19:08:00",
              same_counts_as="MBFS/MBFS/Converter/example/8H4275.Chn"))
E.append(dict(path="MBFS/MBFS/Converter/example/CERNIPf.Chn", oracle="header_text",
              ref="CHN header: 4096 channels, -102 calibration trailer at 32+4*4096, followed by ~17 kB extra bytes",
              num_channels=4096))

(HERE / "expected.json").write_text(json.dumps(E, indent=1), encoding="utf-8")
print(f"wrote {len(E)} expectations")

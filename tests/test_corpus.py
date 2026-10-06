"""Real-world corpus tests (files under test_corpus/, see test_corpus/SOURCES.md).

* test_expected_values: files we can read AND for which an independent reference
  exists (source-project unit tests, plain-text headers, or the same measurement in
  another format) -- see test_corpus/expected.json / build_expected.py.
* test_detected_file_reads: smoke test -- every corpus file our auto-detect claims
  must read without exception.  Deliberately malformed inputs only have to fail
  cleanly with FormatError.

The whole module is skipped if test_corpus/ is not present.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from spectramaster.convert import read_spectra
from spectramaster.formats import FormatError, detect_format, load_all

CORPUS = Path(__file__).resolve().parent.parent / "test_corpus"
CATALOG = CORPUS / "catalog.csv"
EXPECTED = CORPUS / "expected.json"

if not CATALOG.is_file():
    pytest.skip("test_corpus/ not present", allow_module_level=True)

load_all()

# Inputs that are malformed on purpose (fuzz seeds / importer edge cases).
# Failing with FormatError is the correct behaviour for these.
MALFORMED = {
    "BecqMoni/handover/g6-a253/cases/case2_notanumber.n42",
    "BecqMoni/handover/g6-a253/cases/case4_empty.n42",
    "BecqMoni/handover/g6-a253/cases/case17_negcount.n42",
    "BecqMoni/handover/g6-a253/cases/case36_boundary_nan.n42",
    "InterSpec/target/fuzzing/corpus/state_xml/minimal_n42.xml",
}


def _catalog_paths() -> list[str]:
    with open(CATALOG, encoding="utf-8") as fh:
        return [r["path"] for r in csv.DictReader(fh) if (CORPUS / r["path"]).is_file()]


def _expected() -> list[dict]:
    if not EXPECTED.is_file():
        return []
    return [e for e in json.loads(EXPECTED.read_text(encoding="utf-8"))
            if (CORPUS / e["path"]).is_file()]


def _read_or_skip(rel: str):
    try:
        spectra, fmt = read_spectra(CORPUS / rel)
    except FormatError as exc:
        pytest.skip(f"not readable by SpectraMaster yet: {exc}")
    return spectra[0], fmt


# --------------------------------------------------------------------- smoke
@pytest.mark.parametrize("rel", _catalog_paths())
def test_detected_file_reads(rel):
    path = CORPUS / rel
    fmt = detect_format(path)
    if fmt is None:
        pytest.skip("format not detected (unsupported)")
    if rel in MALFORMED:
        try:
            read_spectra(path, fmt)
        except FormatError:
            pass
        return
    spectra, _ = read_spectra(path, fmt)
    assert spectra, "no spectrum returned"
    for s in spectra:
        assert s.num_channels > 0
        assert all(math.isfinite(c) for c in s.counts)
        # (no live <= real check: some synthetic RASE files really have live > real)


# ------------------------------------------------------------ expected values
@pytest.mark.parametrize("exp", _expected(), ids=lambda e: e["path"])
def test_expected_values(exp):
    s, fmt = _read_or_skip(exp["path"])
    where = f"{exp['path']} [{fmt.key}] vs {exp['oracle']}: {exp.get('ref', '')}"

    if "num_channels" in exp:
        assert s.num_channels == exp["num_channels"], where
    if "first_channel" in exp:
        assert s.first_channel == exp["first_channel"], where
    if "live_time" in exp:
        assert s.live_time == pytest.approx(exp["live_time"], rel=1e-6, abs=0.011), where
    if "real_time" in exp:
        assert s.real_time == pytest.approx(exp["real_time"], rel=1e-6, abs=0.011), where
    if "total_counts" in exp:
        assert s.total_counts == pytest.approx(exp["total_counts"]), where
    for idx, val in exp.get("counts_probe", {}).items():
        assert s.counts[int(idx)] == pytest.approx(val), f"{where} channel {idx}"
    if "start_time" in exp:
        want = datetime.fromisoformat(exp["start_time"])
        assert s.start_time is not None, f"{where}: start time missing"
        assert s.start_time.replace(microsecond=0) == want, where
    if "same_counts_as" in exp:
        other, _ = _read_or_skip(exp["same_counts_as"])
        assert s.counts == other.counts, where
    if "same_counts_index" in exp:
        other, _ = _read_or_skip(exp["same_counts_index"]["other"])
        i = exp["same_counts_index"]["index"]
        assert s.counts[i] == other.counts[i], where

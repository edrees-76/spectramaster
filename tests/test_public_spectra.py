"""Checks on public measured spectra kept outside the repository (skipped when absent).
Set SPECTRAMASTER_PUBLIC_DATA to the folder holding ``interspec_example_spectra/`` (InterSpec
example spectra, Sandia National Laboratories, LGPL-2.1: an ORTEC 8-detector HPGe portal, a
Ba-133 source and a background measured the same day)."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(os.environ.get("SPECTRAMASTER_PUBLIC_DATA", "D:/SpectraMaster_public_data"))
IS = ROOT / "interspec_example_spectra"
needs_interspec = pytest.mark.skipif(not (IS / "background_20100317.n42").is_file(),
                                     reason="InterSpec example spectra not available")


@needs_interspec
def test_n42_detector_type_is_used():
    from spectramaster.convert import read_spectra
    from spectramaster.analysis.peaks import guess_detector
    for f in ("ba133_source_640s_20100317.n42", "background_20100317.n42"):
        for s in read_spectra(IS / f)[0]:
            assert s.extra["detector_type"] == "HPGe 50%"
            assert guess_detector(s) == "HPGe"        # weak background spectra included


@needs_interspec
def test_measured_background_on_real_pairs():
    """Same-day background subtracted from a Ba-133 measurement, 8 HPGe detectors: the two
    modes agree on Ba-133, and the natural lines (background only) are not detected."""
    from spectramaster.convert import read_spectra
    from spectramaster.analysis.activity import ActivityOptions, compute_activities
    from spectramaster.validation.benchmark import _flat_curve
    S = read_spectra(IS / "ba133_source_640s_20100317.n42")[0]
    B = read_spectra(IS / "background_20100317.n42")[0]
    curve = _flat_curve()
    ba, nat = {}, []
    for s, b in zip(S, B):
        for mode in ("peak", "spectrum"):
            q = compute_activities(s, curve, ActivityOptions(nuclides=["Ba-133", "K-40", "Tl-208"], bkg_mode=mode,
                                                             min_intensity_pct=5.0), background=b)
            for r in q.nuclides:
                for ln in r.lines:
                    if r.nuclide != "Ba-133":
                        nat.append((ln.detected, ln.bkg_peak if mode == "peak" else 1.0))
                    elif ln.peak_found and ln.energy > 250:
                        ba.setdefault((s.extra["detector_name"], round(ln.energy)), {})[mode] = ln.net_area
    assert len(ba) >= 30
    for v in ba.values():
        assert v["peak"] == pytest.approx(v["spectrum"], rel=0.02)
    assert len(nat) >= 30 and sum(d for d, _ in nat) <= 0.05 * len(nat)
    assert all(b is not None for _d, b in nat)        # the background under each line is reported


IDB = ROOT / "iaea_idb" / "IDB-all-spectra"
needs_idb = pytest.mark.skipif(not (IDB / "1.spe").is_file(), reason="IAEA IDB spectra not available")


@needs_idb
def test_idb_spectra_are_read_and_the_detector_type_is_recognised():
    """IAEA IDB v2024-01 (CC BY 4.0, Dipti et al., Sci Data 12, 1868 (2025)): the SPE remark
    names the detector; the guess must agree (CdTe is treated as the CZT resolution class)."""
    import re
    from spectramaster.convert import read_spectra
    from spectramaster.analysis.peaks import guess_detector
    want = {"hpge": "HPGe", "czt": "CZT", "cdznte": "CZT", "cdte": "CZT", "labr": "LaBr3", "nai": "NaI"}
    files = sorted(IDB.glob("*.spe"))[::25]
    assert len(files) >= 50
    for f in files:
        m = re.search(r"Detector:\s*([^\n(]*)", f.read_text(encoding="latin-1"))
        key = next(k for k in want if k in m.group(1).lower())
        assert guess_detector(read_spectra(f)[0][0]) == want[key], f.name


@needs_idb
def test_idb_plutonium_is_identified_in_hpge_spectra():
    """Pu-239 (lines of 1e-5 to 1e-4 per decay, very high activity) must win its peaks against
    single-line nuclides (Os-191 at 129 keV) in HPGe plutonium spectra."""
    import re
    from spectramaster.convert import read_spectra
    from spectramaster.analysis import find_peaks, identify
    found = n = 0
    for f in sorted(IDB.glob("*.spe"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0)):
        txt = f.read_text(encoding="latin-1")
        if "Material type: Pu" not in txt or "HPGe" not in txt:
            continue
        s = read_spectra(f)[0][0]
        found += "Pu-239" in {m.nuclide for m in identify(s, find_peaks(s))}
        n += 1
        if n == 12:
            break
    # before E1: 0 of 12; after E1: 6 of 12 for these first files (78 % on the benchmark's
    # every-10th subset) - a regression guard, not an acceptance limit
    assert n == 12 and found >= 5

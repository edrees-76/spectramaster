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
    modes agree on Ba-133 and natural lines net to zero within their uncertainties."""
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
                    if not ln.peak_found:
                        continue
                    if r.nuclide == "Ba-133" and ln.energy > 250:
                        ba.setdefault((s.extra["detector_name"], round(ln.energy)), {})[mode] = ln.net_area
                    elif r.nuclide != "Ba-133" and mode == "peak":
                        nat.append(ln.net_area / ln.net_unc)
    assert len(ba) >= 30
    for v in ba.values():
        assert v["peak"] == pytest.approx(v["spectrum"], rel=0.02)
    z = np.array(nat)
    assert len(z) >= 15 and abs(z.mean()) < 0.8 and 0.5 < z.std() < 1.6


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

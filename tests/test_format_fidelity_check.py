"""Spectrum writers make no silent change (docs/baseline/format_fidelity_check_protocol.md): every
difference between the spectrum written and the file read back is named in the warnings."""
from __future__ import annotations

import re
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from numpy.polynomial import polynomial as P

from spectramaster.convert import write_spectrum
from spectramaster.formats import FormatError, all_formats, load_all, readable_formats, writable_formats
from spectramaster.model import Spectrum

pytest.importorskip("SpecUtils")


def spectrum(first=0, start=datetime(2024, 3, 5, 10, 20, 30), coeffs=(0.0, 0.5, 1e-6, -2e-10, 5e-13)):
    counts = [float(100 + (i * 37) % 900) for i in range(4096)]
    counts[2000] = 16777217.0
    return Spectrum(counts=counts, energy_coeffs=list(coeffs), live_time=100.75, real_time=120.25,
                    start_time=start, sample_id="عينة ١٢", description="تربة ٣", detector="كاشف ١",
                    first_channel=first, fwhm_coeffs=[1.0, 0.002, 1e-7])


VARIANTS = {"base": {}, "first-10": {"first": -10}, "first+10": {"first": 10},
            "y2000": {"start": datetime(2000, 1, 1)}, "nonmonotonic": {"coeffs": (0.0, 1.0, -0.01)}}


def differences(w: Spectrum, b: Spectrum) -> dict[str, tuple]:
    """Independent comparison: {category: keywords one of which a warning must contain}."""
    out = {}
    a, g = np.asarray(w.counts, float), np.asarray(b.counts, float)
    if len(a) != len(g) or w.first_channel != b.first_channel:
        out["channels"] = ("channels", "first channel")
    best = None
    for shift in {w.first_channel - b.first_channel, 0}:
        i0, i1 = max(0, -shift), min(len(a), len(g) - shift)
        if i1 > i0:
            n_bad = int(np.sum(a[i0:i1] != np.round(g[i0 + shift:i1 + shift], 6)))
            if best is None or n_bad < best[0]:
                best = (n_bad, shift, i0, i1)
    if best is None or best[0]:
        out["counts"] = ("counts", "channels")
    if any(w.energy_coeffs) and best is not None:
        _n, shift, i0, i1 = best
        if not any(b.energy_coeffs):
            out["energy"] = ("calibration",)
        else:
            i = np.arange(i0, i1, dtype=float)
            d = np.abs(P.polyval(w.first_channel + i, w.energy_coeffs)
                       - P.polyval(b.first_channel + shift + i, b.energy_coeffs))
            if d.max() > 0.001:
                out["energy"] = ("calibration", "energies")
    for name in ("live_time", "real_time"):
        x, y = getattr(w, name), getattr(b, name)
        if x is not None and (y is None or abs(y - x) > 1e-6 * x):
            out[name] = (name.replace("_", " "),)
    if w.start_time is not None and (b.start_time is None or abs(
            (b.start_time.replace(tzinfo=None) - w.start_time).total_seconds()) >= 1):
        out["start"] = ("start time",)
    for label, attr in (("sample ID", "sample_id"), ("description", "description"), ("detector", "detector")):
        x, y = getattr(w, attr).strip(), (getattr(b, attr) or "").strip()
        if x and x != y and x.translate({0x0660 + k: str(k) for k in range(10)}) != y:
            out[attr] = (label,)
        elif x and x != y:
            out[attr] = (label, "Arabic-Indic digits")
    if any(w.fwhm_coeffs) and list(np.round(b.fwhm_coeffs, 12)) != list(np.round(
            list(w.fwhm_coeffs) + [0.0] * (len(b.fwhm_coeffs) - len(w.fwhm_coeffs)), 12)):
        out["fwhm"] = ("FWHM",)
    return out


# ------------------------------------------------------------------ FF.C1 / C2 / C5
@pytest.mark.parametrize("variant", list(VARIANTS))
def test_every_difference_is_reported(variant, tmp_path):
    load_all()
    unreported = []
    for f in writable_formats():
        if not f.can_read:
            continue
        spec = spectrum(**VARIANTS[variant])
        try:
            warns = write_spectrum(spec, tmp_path / f"x{f.default_ext}", f)
        except FormatError:
            continue                                   # refused: not a silent change
        back = f.reader(tmp_path / f"x{f.default_ext}")[0]
        text = " | ".join(warns)
        for cat, words in differences(spec, back).items():
            if not any(w in text for w in words):
                unreported.append((f.key, cat))
    assert unreported == []


# ------------------------------------------------------------------ FF.C3 / C4
def test_write_only_formats_say_they_were_not_checked(tmp_path):
    load_all()
    only = [f for f in writable_formats() if not f.can_read]
    assert only
    for f in only:
        warns = write_spectrum(spectrum(), tmp_path / f"x{f.default_ext}", f)
        assert any("could not be checked" in w for w in warns), f.key


@pytest.mark.parametrize("key, terms", [("iec1455", 4), ("chandata_csv", 3)])
def test_calibration_refitted_before_writing(key, terms, tmp_path):
    from spectramaster.convert import resolve_format
    f = resolve_format(key)
    warns = write_spectrum(spectrum(), tmp_path / f"x{f.default_ext}", f)
    assert any(f"stores only {terms} calibration terms" in w for w in warns)


# ------------------------------------------------------------------ FF.C6 Aptec analysis readers
@pytest.mark.parametrize("head", [b"VERSION 3.0", b"VERSION9.9", b"VERSION6.3"])
def test_aptec_analysis_readers_refuse_unknown_or_empty(head):
    from spectramaster.analysis.aptec_roi import read_aptec_rois
    from spectramaster.analysis.aptec_s0 import read_s0
    data = head + bytes(1024 - len(head))                  # VERSION6.3 header with 0 channels
    with pytest.raises(ValueError):
        read_s0(data)
    with pytest.raises(ValueError):
        read_aptec_rois(data)


# ------------------------------------------------------------------ FF.C7 without SpecUtils
def test_chn_and_cnf_work_without_specutils(tmp_path):
    code = textwrap.dedent(f'''
        import sys, tempfile
        sys.modules["SpecUtils"] = None
        from pathlib import Path
        from spectramaster.formats import load_all, all_formats, get_format
        import spectramaster.formats as F
        from spectramaster.convert import write_spectrum
        from spectramaster.model import Spectrum
        load_all()
        keys = {{f.key for f in all_formats()}}
        assert "ortec_chn" in keys and "ci_cnf" in keys and "n42_2012" not in keys
        s = Spectrum(counts=[float(i % 50) for i in range(1024)], energy_coeffs=[0.0, 1.0],
                     live_time=10.0, real_time=11.0)
        for k in ("ortec_chn", "ci_cnf"):
            f = get_format(k)
            p = Path(r"{tmp_path}") / ("x" + f.default_ext)
            w = write_spectrum(s, p, f)
            assert not any("checked by reading" in x and "counts" in x for x in w), w
            assert f.reader(p)[0].counts[:50] == s.counts[:50]
        print("ok")
    ''')
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=Path(__file__).parents[1])
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-2000:]
    assert "not loaded" not in r.stderr                    # no other format module failed


# ------------------------------------------------------------------ FF.C8 README
def test_readme_counts_match_the_registry():
    load_all()
    text = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*(\d+) spectrum formats\*\* \((\d+) readable, (\d+) writable\)", text)
    assert m and tuple(map(int, m.groups())) == (len(all_formats()), len(readable_formats()),
                                                 len(writable_formats()))

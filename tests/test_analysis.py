"""Analysis engine: library, peak search, identification, CLI.

Real-data tests use the lab's Aptec spectra and the IAEA G-1 intercomparison spectra
(read-only, skipped when not present on the machine).
"""
from __future__ import annotations

import io
import json
import math
import statistics
import time
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pytest

from spectramaster.analysis import NuclideMatch, Peak, find_peaks, identify
from spectramaster.analysis.library import DEFAULT_LIBRARY, load_library
from spectramaster.convert import read_spectra
from spectramaster.model import Spectrum

REF = Path("D:/الاسس و المفاهيم العامة فى استخدام برامج الطيف الجامى/اطياف مرجعية")
S0 = REF / "4- أطياف المختبر (Aptec)" / "الملفات الأصلية S0"
G1 = REF / "1- IAEA G-1" / "الأطياف ASCII"
CORPUS = Path(__file__).resolve().parent.parent / "test_corpus"
EU16K = CORPUS / "curie" / "examples" / "eu_calib_7cm.Spe"

needs_lab = pytest.mark.skipif(not S0.is_dir(), reason="lab Aptec spectra not available")
needs_g1 = pytest.mark.skipif(not (G1 / "G1100.ASC").exists(), reason="IAEA G-1 spectra not available")


def _lab(name: str) -> Spectrum:
    return read_spectra(S0 / name)[0][0]


def _ids(spec, **kw) -> list[NuclideMatch]:
    return identify(spec, find_peaks(spec), **kw)


# ------------------------------------------------------------------ library
def test_library_contents_and_convention():
    raw = json.loads(DEFAULT_LIBRARY.read_text(encoding="utf-8"))
    assert DEFAULT_LIBRARY.stat().st_size < 2_000_000
    assert "convention" in raw and "sources" in raw
    lib = load_library()
    assert 150 <= len(lib) <= 260
    for name in ("Cs-137", "Co-60", "Am-241", "Eu-152", "Bi-214", "Tl-208", "K-40", "I-131", "Tc-99m",
                 "Ba-140", "Te-132", "Pa-234m", "U-235", "Ac-228", "Lu-177", "F-18"):
        assert name in lib, name
    cs = {round(l.energy, 1): l.intensity for l in lib["Cs-137"].gammas()}
    assert cs[661.7] == pytest.approx(85.1, abs=0.5)        # Ba-137m folded into Cs-137
    co = [l.energy for l in lib["Co-60"].gammas(50)]
    assert co == pytest.approx([1173.228, 1332.492], abs=0.01)
    na = [l for l in lib["Na-22"].lines if l.kind == "a"]
    assert na and na[0].intensity == pytest.approx(180, abs=2)
    tl = lib["Tl-208"]
    assert tl.series == "Th-232 series" and tl.series_factor == pytest.approx(0.3594)
    ba = {round(l.energy): l.intensity for l in lib["Ba-140"].gammas()}
    assert 1596 in ba and 537 in ba                          # La-140 lines in transient equilibrium
    assert lib["Bi-214"].background and "Ra-226" == lib["Bi-214"].subgroup


def test_user_csv_library(tmp_path):
    p = tmp_path / "mini.csv"
    p.write_text("nuclide,energy,intensity\n# comment\nXx-1, 661.66, 85\nYy-2, 1460.8, 10.7, 1.25e9 y, natural\n",
                 encoding="utf-8")
    lib = load_library(p)
    assert set(lib) == {"Xx-1", "Yy-2"} and lib["Yy-2"].category == "natural"
    spec = _synthetic([(661.66, 20000), (1460.8, 3000)])
    names = [m.nuclide for m in identify(spec, library=p)]
    assert "Xx-1" in names and "Yy-2" in names


# ---------------------------------------------------------------- synthetic
def _synthetic(lines, n=4096, gain=0.5, fwhm_kev=1.8, bkg=50.0, seed=1, live=1000.0):
    rng = np.random.default_rng(seed)
    ch = np.arange(n, dtype=float)
    e = gain * ch
    y = bkg * np.exp(-e / 1500.0) + 5
    for energy, area in lines:
        s = fwhm_kev / 2.3548 / gain
        y += area / (s * math.sqrt(2 * math.pi)) * np.exp(-0.5 * ((ch - energy / gain) / s) ** 2)
    return Spectrum(counts=list(rng.poisson(y).astype(float)), energy_coeffs=[0.0, gain], live_time=live)


def test_synthetic_peaks_areas_and_doublet():
    truth = [(122.0, 5000), (344.0, 20000), (661.66, 50000), (1000.0, 800), (1332.5, 30000),
             (1460.0, 30000), (1462.7, 15000)]                      # last two: 1.5 FWHM doublet
    spec = _synthetic(truth)
    peaks = find_peaks(spec)
    for e, area in truth:
        p = min(peaks, key=lambda p: abs(p.energy - e))
        assert abs(p.energy - e) < 0.3, (e, p.energy)
        assert abs(p.net_area - area) < max(4 * p.net_area_unc, 0.05 * area), (e, p.net_area, area)
    assert len(peaks) <= len(truth) + 1
    p = min(peaks, key=lambda p: abs(p.energy - 661.66))
    assert p.fwhm_kev == pytest.approx(1.8, rel=0.1)
    assert p.count_rate == pytest.approx(p.net_area / 1000.0)
    assert p.left < p.centroid < p.right


def test_uncalibrated_identify_returns_empty():
    spec = _synthetic([(661.66, 20000)])
    spec.energy_coeffs = []
    peaks = find_peaks(spec)
    assert peaks and all(p.energy is None for p in peaks)
    assert identify(spec, peaks) == []


def test_flags_annihilation_and_sum_peak():
    spec = _synthetic([(511.0, 20000), (1173.23, 100000), (1332.49, 90000), (2505.7, 600)], n=6000)
    peaks = find_peaks(spec)
    p511 = min(peaks, key=lambda p: abs(p.energy - 511))
    assert "annihilation" in p511.note
    ps = min(peaks, key=lambda p: abs(p.energy - 2505.7))
    assert "sum peak" in ps.note


# -------------------------------------------------------------- real spectra
@needs_lab
@pytest.mark.parametrize("name, nuclide", [
    ("CO60CAL.S0", "Co-60"), ("CS137CAL.S0", "Cs-137"), ("NA22CAL.S0", "Na-22"),
    ("BA133CAL.S0", "Ba-133"), ("Eu-152.S0", "Eu-152"), ("Eu-152 16-3-2006.S0", "Eu-152"),
    ("NAI1X1.S0", "Na-22"),
])
def test_calibration_source_is_top_match(name, nuclide):
    matches = _ids(_lab(name))
    assert matches and matches[0].nuclide == nuclide, [(m.nuclide, m.confidence) for m in matches[:4]]
    assert matches[0].confidence >= 0.6


@needs_lab
def test_chernbkg_finds_aptec_labelled_nuclides():
    spec = _lab("CHERNBKG.S0")
    aptec = {x.strip() for x in spec.extra["roi_nuclides"].split(",")}
    assert aptec == {"Pb-212", "Pb-214", "Tl-208", "Bi-214", "Cs-137", "K-40"}
    peaks = find_peaks(spec)
    found = {m.nuclide: m for m in identify(spec, peaks)}
    assert aptec <= set(found), aptec - set(found)
    assert "U-238 series" in found["Bi-214"].note and found["Bi-214"].background
    k40 = min(peaks, key=lambda p: abs(p.energy - 1460.8))
    assert k40.nuclide == "K-40" and k40.line_energy == pytest.approx(1460.82, abs=0.01)


@needs_lab
def test_chernobyl_sample():
    spec = _lab("CHERN.S0")
    aptec = {x.strip() for x in spec.extra["roi_nuclides"].split(",")}
    found = {m.nuclide for m in _ids(spec)}
    assert {"Cs-134", "Cs-137", "Ce-144", "Ru-103", "Zr-95", "Nb-95", "Ba-140", "La-140"} <= found
    assert len(aptec & found) >= 10, aptec - found


@needs_lab
@pytest.mark.parametrize("name, expected", [
    ("QCY48CAL.S0", {"Am-241", "Cd-109", "Co-57", "Ce-139", "Hg-203", "Sn-113", "Sr-85", "Cs-137",
                     "Y-88", "Co-60"}),
    ("EFF.S0", {"Ba-133", "Co-57", "Ce-139", "Cs-137", "Mn-54", "Y-88", "Zn-65"}),
    ("EFFNEW.S0", {"Ba-133", "Cs-137", "Mn-54", "Zn-65"}),
])
def test_multinuclide_standards(name, expected):
    found = [m.nuclide for m in _ids(_lab(name))]
    assert expected <= set(found), expected - set(found)
    # the standard's nuclides dominate the top of the list
    assert set(found[:len(expected)]) <= expected | {"Co-60", "K-40", "Sr-85", "Ce-139"}


# ---------------------------------------------------------------------- G-1
G1_REF = [130, 207, 306, 361, 563, 655, 818, 863, 924, 1011, 1095, 1196, 1300, 1430, 1522, 1574, 1734,
          1823, 1904, 1947]
G1200 = [(130, -11, 240.196), (207, 7, 78.652), (306, -21, 133.540), (361, -8, 261.628), (563, -42, 58.886),
         (655, -23, 146.530), (818, -51, 83.879), (818, 9, 138.229), (863, 7, 164.773), (924, 3, 109.641),
         (1011, -44, 142.857), (1095, 12, 283.582), (1196, -8, 261.628), (1300, 9, 1014.493),
         (1430, -32, 963.855), (1430, 37, 1005.578), (1522, -5, 2618.182), (1574, -8, 261.628),
         (1734, 9, 1014.493), (1823, 11, 2222.222), (1904, -5, 2618.182), (1947, 14, 616.822)]
G1300 = [(130, 0, 5.309), (207, 0, 24.138), (306, 0, 6.342), (361, 0, 23.316), (563, 0, 8.475),
         (655, 0, 34.337), (818, -43, 8.477), (818, 0, 40.506), (863, 0, 7.592), (924, 0, 38.926),
         (1011, 0, 11.776), (1095, 0, 211.111), (1196, 0, 23.316), (1300, 0, 271.552), (1430, 0, 25.442),
         (1430, 54, 257.143), (1522, 0, 38.919), (1574, 0, 23.316), (1734, 0, 271.552), (1823, 0, 336.634),
         (1904, 0, 38.919), (1947, 0, 55.562)]


def _g1(name):
    return read_spectra(G1 / f"{name}.ASC")[0][0]


def _g1_score(name, table, ref_area, tol=2.5):
    peaks = find_peaks(_g1(name))
    used, devs = set(), []
    for r, shift, ratio in table:
        pos = r + shift
        cands = [(abs(p.centroid - pos), i) for i, p in enumerate(peaks) if abs(p.centroid - pos) <= tol
                 and i not in used]
        if cands:
            _d, i = min(cands)
            used.add(i)
            devs.append((peaks[i].net_area - ref_area[r] / ratio) / (ref_area[r] / ratio))
    # the pseudo-Compton edge near channel 1024 is an artefact of the G-1 construction (ignored)
    spurious = [p for i, p in enumerate(peaks) if i not in used and not 1015 <= p.centroid <= 1035]
    recall = len(used) / len(table)
    precision = len(used) / max(len(used) + len(spurious), 1)
    return recall, precision, devs


@pytest.fixture(scope="module")
def g1_reference_areas():
    peaks = find_peaks(_g1("G1100"))
    out = {}
    for r in G1_REF:
        p = min(peaks, key=lambda p: abs(p.centroid - r))
        assert abs(p.centroid - r) < 2.0, r
        out[r] = p.net_area
    return out


@needs_g1
def test_g1_reference_spectrum_all_peaks(g1_reference_areas):
    assert len(g1_reference_areas) == 20
    assert len(find_peaks(_g1("G1100"))) <= 21


@needs_g1
@pytest.mark.parametrize("k", range(6))
def test_g1_consistency_spectra(g1_reference_areas, k):
    recall, precision, devs = _g1_score(f"G130{k}", G1300, g1_reference_areas)
    assert recall >= 0.95 and precision >= 0.95
    assert statistics.median(abs(d) for d in devs) < 0.06


@needs_g1
def test_g1_peak_search_spectrum(g1_reference_areas):
    # G1200 holds 22 mostly tiny peaks; the IAEA notes "many programs detect 17 peaks without
    # spurious peaks", the best result in the intercomparison was 19.  Require >= 15 (0.68).
    recall, precision, devs = _g1_score("G1200", G1200, g1_reference_areas)
    assert recall >= 0.68
    assert precision >= 0.9


# ------------------------------------------------------------------- timing
@pytest.mark.skipif(not EU16K.exists(), reason="test corpus not available")
def test_timing_16k_channels():
    spec = read_spectra(EU16K)[0][0]
    assert len(spec.counts) == 16384
    peaks = find_peaks(spec)          # warm-up (imports, library load)
    identify(spec, peaks)
    t_peaks, t_id = [], []
    for _ in range(3):
        t0 = time.perf_counter()
        peaks = find_peaks(spec)
        t1 = time.perf_counter()
        identify(spec, peaks)
        t2 = time.perf_counter()
        t_peaks.append(t1 - t0)
        t_id.append(t2 - t1)
    assert len(peaks) > 50
    # 0.5 s target on an idle machine; 1.0 s bound so a busy CPU (parallel builds) doesn't flake
    assert min(t_peaks) < 1.0, t_peaks
    assert min(t_id) < 1.0, t_id


# ---------------------------------------------------------------------- CLI
@needs_lab
def test_cli_peaks_and_identify():
    from spectramaster.cli import main
    f = str(S0 / "CO60CAL.S0")
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert main(["peaks", f, "--min-sig", "4"]) == 0
        assert main(["identify", f, "--peaks"]) == 0
    out = buf.getvalue()
    assert "Co-60" in out and "1173.2" in out and "Nuclide" in out


def test_cli_identify_uncalibrated(tmp_path):
    from spectramaster.cli import main
    p = tmp_path / "x.spe"
    spec = _synthetic([(661.66, 20000)], n=1024)
    lines = ["$SPEC_ID:", "test", "$MEAS_TIM:", "100 100", "$DATA:", f"0 {len(spec.counts) - 1}"]
    lines += [str(int(c)) for c in spec.counts]
    p.write_text("\n".join(lines) + "\n", encoding="ascii")
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert main(["identify", str(p)]) == 0
    assert "not energy calibrated" in buf.getvalue()


def test_peak_dataclass_additions_have_defaults():
    p = Peak(1.0, None, 2.0, None, 10.0, 1.0, 12.0, 2.0, 0, 3, 10.0)
    assert p.centroid_unc is None and p.multiplet == 1 and p.nuclide == ""
    m = NuclideMatch("Cs-137", 0.9)
    assert m.background is False and m.series == ""

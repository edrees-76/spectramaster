"""Benchmark scenarios (difficulty categories) for HPGe and NaI.

Each builder yields ``SyntheticSpectrum`` objects for one category.  Seeds are derived
from (detector, category, realisation index) so every spectrum is reproducible on its own.
The continuum levels are per *channel*; NaI channels are 6x wider than HPGe channels here,
so its continuum per channel is correspondingly higher.
"""
from __future__ import annotations

import zlib
from typing import Iterator

import numpy as np

from ..analysis.library import load_library
from .synthetic import (Continuum, DetectorSpec, SyntheticSpectrum, TruePeak, area_for_snr,
                        compton_edge_kev, continuum_counts, make_spectrum)


def seed_of(det: DetectorSpec, category: str, i: int) -> int:
    return zlib.crc32(f"{det.name}/{det.n_channels}/{category}/{i}".encode()) & 0x7FFFFFFF


def base_continuum(det: DetectorSpec) -> Continuum:
    k = det.gain_kev / 0.5            # counts per channel scale with channel width
    return Continuum(exp_amp=300.0 * k, exp_scale_kev=400.0, flat=10.0 * k)


def _energies(det: DetectorSpec, kind: str) -> list[float]:
    nai = det.name == "NaI"
    if kind == "strong":
        return [122.0, 364.0, 662.0, 1000.0, 1460.0, 2000.0] if nai else \
               [122.0, 344.0, 662.0, 1173.0, 1460.0, 1836.0]
    if kind == "weak":
        return [200.0, 500.0, 900.0, 1400.0, 2000.0] if nai else [200.0, 450.0, 700.0, 1000.0, 1400.0]
    if kind == "low":
        return [250.0, 700.0, 1300.0, 2000.0] if nai else [250.0, 600.0, 1000.0, 1500.0]
    raise ValueError(kind)


# ---------------------------------------------------------------------------- categories
def isolated_strong(det: DetectorSpec, n: int = 40, tail: bool = False) -> Iterator[SyntheticSpectrum]:
    cat = "tailed" if tail else "isolated_strong"
    for i in range(n):
        peaks = [TruePeak(e, 1.0e5, tail_frac=0.04 if tail else 0.0, tail_slope=1.5,
                          step_frac=0.001 if tail else 0.0) for e in _energies(det, "strong")]
        yield make_spectrum(det, peaks, base_continuum(det), seed_of(det, cat, i), meta={"category": cat})


SNR_LEVELS = (3.0, 5.0, 7.0, 10.0)


def isolated_weak(det: DetectorSpec, n: int = 60) -> Iterator[SyntheticSpectrum]:
    cont = base_continuum(det)
    cy = continuum_counts(det, cont)
    for i in range(n):
        s = SNR_LEVELS[i % len(SNR_LEVELS)]
        peaks = [TruePeak(e, area_for_snr(det, cy, e, s), tag=f"s={s:g}") for e in _energies(det, "weak")]
        yield make_spectrum(det, peaks, cont, seed_of(det, "isolated_weak", i),
                            meta={"category": "isolated_weak", "s": s})


def background_only(det: DetectorSpec, n: int = 30) -> Iterator[SyntheticSpectrum]:
    for i in range(n):
        yield make_spectrum(det, [], base_continuum(det), seed_of(det, "background_only", i),
                            meta={"category": "background_only"})


DOUBLET_SEPS = (0.5, 0.75, 1.0, 1.5, 2.0)
DOUBLET_RATIOS = (1.0, 3.0, 10.0)


def doublets(det: DetectorSpec, n_each: int = 8) -> Iterator[SyntheticSpectrum]:
    e0 = 662.0
    fw = float(det.fwhm_kev(e0))
    k = 0
    for d in DOUBLET_SEPS:
        for r in DOUBLET_RATIOS:
            for j in range(n_each):
                peaks = [TruePeak(e0, 1.0e5, tag="lo"), TruePeak(e0 + d * fw, 1.0e5 / r, tag="hi")]
                yield make_spectrum(det, peaks, base_continuum(det), seed_of(det, "doublets", k),
                                    meta={"category": "doublets", "sep_fwhm": d, "ratio": r})
                k += 1


EDGE_OFFSETS = (None, -2.0, -1.0, 0.0, 1.0, 2.0)     # test-peak offset from the edge, FWHM units


def compton_edge(det: DetectorSpec, n: int = 48, extra_sigma_kev: float = 0.0) -> Iterator[SyntheticSpectrum]:
    """Pre-registered case: extra_sigma_kev = 0 (edge smeared by detector resolution only, a
    worst case sharper than real edges).  The informational variant (added after the first run,
    no acceptance limit) uses a broader, more realistic edge."""
    line = 1332.0
    ec = compton_edge_kev(line)
    for i in range(n):
        cont = base_continuum(det)
        cont.compton_line_kev, cont.compton_level = line, 150.0 * det.gain_kev / 0.5
        cont.edge_extra_sigma_kev = extra_sigma_kev
        cy = continuum_counts(det, cont)
        off = EDGE_OFFSETS[i % len(EDGE_OFFSETS)]
        peaks = [TruePeak(line, 5.0e5, tag="source")]
        if off is not None:
            e = ec + off * float(det.fwhm_kev(ec))
            peaks.append(TruePeak(e, area_for_snr(det, cy, e, 20.0), tag=f"edge{off:+g}"))
        yield make_spectrum(det, peaks, cont, seed_of(det, "compton_edge", i),
                            meta={"category": "compton_edge", "edge_kev": ec, "offset": off})


LOW_AREAS = (50.0, 100.0, 200.0, 400.0)


def low_counts(det: DetectorSpec, n: int = 60) -> Iterator[SyntheticSpectrum]:
    k = det.gain_kev / 0.5
    for i in range(n):
        a = LOW_AREAS[i % len(LOW_AREAS)]
        cont = Continuum(exp_amp=4.0 * k, exp_scale_kev=500.0, flat=1.0 * k)
        peaks = [TruePeak(e, a, tag=f"A={a:g}") for e in _energies(det, "low")]
        yield make_spectrum(det, peaks, cont, seed_of(det, "low_counts", i),
                            meta={"category": "low_counts", "A": a})


# ---------------------------------------------------------------------------- identification
BKG_NUCLIDES = {"K-40": 1.0, "Pb-214": 0.5, "Bi-214": 0.5, "Pb-212": 0.4, "Tl-208": 0.4, "Ac-228": 0.3}

MIXTURES: dict[str, dict[str, float]] = {
    "background": {},
    "Cs-137": {"Cs-137": 1.0},
    "Co-60": {"Co-60": 1.0},
    "Am-241+Cs-137": {"Am-241": 1.5, "Cs-137": 1.0},
    "Ba-133": {"Ba-133": 1.0},
    "Eu-152": {"Eu-152": 1.0},
    "I-131": {"I-131": 1.0},
    "Cs-134+Cs-137": {"Cs-134": 0.6, "Cs-137": 1.0},
}
DRIFTS = (0.0, 0.001, 0.003, 0.01)


def rel_efficiency(e_kev: float) -> float:
    """Generic coaxial full-energy-peak efficiency shape (relative units, max ~1 near 120 keV)."""
    e = max(e_kev, 20.0)
    if e < 120.0:
        return (e / 120.0) ** 2.0
    return (e / 120.0) ** -0.9


def _lines(name: str, lib) -> list[tuple[float, float]]:
    nd = lib[name]
    f = nd.series_factor if nd.series_factor else 1.0
    return [(l.energy, l.intensity / 100.0 * f) for l in nd.gammas(1.0) if 40.0 <= l.energy <= 2900.0]


def identification(det: DetectorSpec, n_seeds: int = 4) -> Iterator[SyntheticSpectrum]:
    """Known-nuclide mixtures on natural background, each also with deliberate gain errors.

    Activities are scaled so the strongest line of each sample nuclide has s ~ 60 and the
    strongest background line s ~ 25; ``meta['present']`` lists nuclides whose strongest line
    has s >= 15 (the truth set), ``meta['weak']`` those present but weaker.
    """
    lib = load_library()
    cont = base_continuum(det)
    cy = continuum_counts(det, cont)
    emax = float(det.energy(det.n_channels - 20))
    k = 0
    for mix, comps in MIXTURES.items():
        for drift in DRIFTS:
            for j in range(n_seeds):
                peaks, s_best = [], {}
                for group, target in ((comps, 60.0), (BKG_NUCLIDES, 25.0)):
                    for name, w in group.items():
                        lines = [(e, y) for e, y in _lines(name, lib) if e < emax]
                        if not lines:
                            continue
                        resp = [(e, y * rel_efficiency(e)) for e, y in lines]
                        e_ref, r_ref = max(resp, key=lambda t: t[1])
                        scale = area_for_snr(det, cy, e_ref, target * w) / r_ref
                        best = 0.0
                        for e, r in resp:
                            a = scale * r
                            if a < 5:
                                continue
                            peaks.append(TruePeak(e, a, tag=name))
                            best = max(best, a / np.sqrt(max(_bkg(det, cy, e), 1.0)))
                        s_best[name] = best
                present = sorted(n for n, s in s_best.items() if s >= 15.0)
                weak = sorted(n for n, s in s_best.items() if s < 15.0)
                yield make_spectrum(det, peaks, cont, seed_of(det, "identification", k), gain_error=drift,
                                    meta={"category": "identification", "mixture": mix, "drift": drift,
                                          "present": present, "weak": weak})
                k += 1


def _bkg(det, cy, e):
    from .synthetic import window_background
    return window_background(det, cy, e)

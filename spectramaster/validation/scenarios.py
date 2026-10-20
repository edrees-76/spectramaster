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


def shape_calibration_spectra(det: DetectorSpec, n: int = 3, tail: bool = True) -> Iterator[SyntheticSpectrum]:
    """Calibration spectra of the same detector as `isolated_strong(tail=...)` (other seeds):
    the peak-shape calibration is measured on them and applied to the sample spectra."""
    cat = "shape_cal" if tail else "shape_cal_gauss"
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


SATELLITE_SEPS = (1.25, 1.5, 2.0)
SATELLITE_RATIOS = (10.0, 30.0, 100.0)


def satellites(det: DetectorSpec, n_each: int = 8, tail: bool = False) -> Iterator[SyntheticSpectrum]:
    """A strong peak (1e5 counts) with a weaker satellite 1.25-2 FWHM away, alternately on the
    high and the low side (residual-search protocol, docs/baseline/residual_search_protocol.md).
    `tail`: both peaks carry the low-energy tail of `shape_calibration_spectra(tail=True)`."""
    e0 = 662.0
    fw = float(det.fwhm_kev(e0))
    cat = "satellites_tailed" if tail else "satellites"
    sh = dict(tail_frac=0.04, tail_slope=1.5, step_frac=0.001) if tail else {}
    k = 0
    for d in SATELLITE_SEPS:
        for r in SATELLITE_RATIOS:
            for j in range(n_each):
                side = 1.0 if j % 2 == 0 else -1.0
                peaks = [TruePeak(e0, 1.0e5, tag="main", **sh),
                         TruePeak(e0 + side * d * fw, 1.0e5 / r, tag="sat", **sh)]
                yield make_spectrum(det, peaks, base_continuum(det), seed_of(det, cat, k),
                                    meta={"category": cat, "sep_fwhm": d, "ratio": r, "side": side})
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


# ---------------------------------------------------------------------------- energy calibration
def _source_peaks(det: DetectorSpec, cy, lines: list[tuple[float, float]], s_strongest: float):
    """TruePeaks for (keV, relative emission) lines, scaled so the strongest response has s."""
    emax = float(det.energy(det.n_channels - 20))
    resp = [(e, y * rel_efficiency(e)) for e, y in lines if 30.0 <= e < emax]
    e_ref, r_ref = max(resp, key=lambda t: t[1])
    scale = area_for_snr(det, cy, e_ref, s_strongest) / r_ref
    return [TruePeak(e, scale * r) for e, r in resp if scale * r >= 5]


def calibration_source(det: DetectorSpec, nuclides: str, n: int, category: str = "cal_source",
                       s_strongest: float = 150.0, with_background: bool = True
                       ) -> Iterator[SyntheticSpectrum]:
    """Calibration-source spectra stored WITHOUT an energy calibration (truth in ``detector``).

    Line energies and emission probabilities come from ``tools.calibrate.NUCLIDE_LINES`` (the
    calibration tool's own line list), optionally on top of a weak natural background.
    """
    from ..tools.calibrate import NUCLIDE_LINES
    lib = load_library()
    cont = base_continuum(det)
    cy = continuum_counts(det, cont)
    names = [x.strip() for x in nuclides.split(",") if x.strip()]
    lines = [(e, i / 100.0) for nm in names for e, i in NUCLIDE_LINES[nm] if not (nm == "Na-22" and e == 511.0)]
    for i in range(n):
        peaks = _source_peaks(det, cy, lines, s_strongest)
        if with_background:
            bl = [(e, y * w) for nm, w in BKG_NUCLIDES.items() for e, y in _lines(nm, lib)]
            peaks += _source_peaks(det, cy, bl, 15.0)
        syn = make_spectrum(det, peaks, cont, seed_of(det, f"{category}/{nuclides}", i),
                            meta={"category": category, "source": nuclides})
        syn.spectrum.energy_coeffs = []
        yield syn


def calibration_drift(det: DetectorSpec, drift: float, n: int, s_strongest: float = 60.0
                      ) -> Iterator[SyntheticSpectrum]:
    """Natural-background spectra whose stored gain is wrong by ``drift`` (relative)."""
    lib = load_library()
    cont = base_continuum(det)
    cy = continuum_counts(det, cont)
    bl = [(e, y * w) for nm, w in BKG_NUCLIDES.items() for e, y in _lines(nm, lib)]
    for i in range(n):
        peaks = _source_peaks(det, cy, bl, s_strongest)
        yield make_spectrum(det, peaks, cont, seed_of(det, f"drift/{drift:g}", i), gain_error=drift,
                            meta={"category": "drift", "drift": drift})


# ---------------------------------------------------------------------------- measured background
BKG_PRESENT = {"Cs-137": [661.657], "Co-60": [1173.228, 1332.492]}          # sample-only (net > 0)
BKG_ABSENT = {"K-40": [1460.82], "Bi-214": [609.312], "Pb-214": [351.932]}   # background only (net 0)
BKG_TIME_RATIO = 2.0


def background_pairs(det: DetectorSpec, n: int, live_time: float = 3600.0) -> Iterator[tuple]:
    """(sample, background, truth) triples.  The background is measured for BKG_TIME_RATIO x the
    sample live time and contains natural lines plus a weak Cs-137 contamination; the sample is
    the same background rate plus Cs-137 and Co-60.  truth[(nuclide, keV)] = true net (sample-only)
    counts in the sample spectrum (0 for the background-only lines)."""
    lib = load_library()
    cont = base_continuum(det)
    cy = continuum_counts(det, cont)
    bl = [(e, y * w) for nm, w in BKG_NUCLIDES.items() for e, y in _lines(nm, lib)]
    bkg_peaks = _source_peaks(det, cy, bl, 40.0)
    # Cs-137 contamination of the shield/detector: s ~ 8 in the sample time
    bkg_peaks.append(TruePeak(661.657, area_for_snr(det, cy, 661.657, 8.0), tag="Cs-137 contamination"))
    src = [TruePeak(661.657, area_for_snr(det, cy, 661.657, 40.0), tag="Cs-137"),
           TruePeak(1173.228, area_for_snr(det, cy, 1173.228, 40.0), tag="Co-60"),
           TruePeak(1332.492, area_for_snr(det, cy, 1332.492, 40.0) * 1.0, tag="Co-60")]
    k = BKG_TIME_RATIO
    bcont = Continuum(exp_amp=cont.exp_amp * k, exp_scale_kev=cont.exp_scale_kev, flat=cont.flat * k)
    truth = {("Cs-137", 661.657): src[0].area, ("Co-60", 1173.228): src[1].area,
             ("Co-60", 1332.492): src[2].area}
    for nm, es in BKG_ABSENT.items():
        for e in es:
            truth[(nm, e)] = 0.0
    for i in range(n):
        smp = make_spectrum(det, bkg_peaks + src, cont, seed_of(det, "bkgpair/sample", i), live_time=live_time,
                            meta={"category": "background_pair"})
        bkg = make_spectrum(det, [TruePeak(p.energy, p.area * k, tag=p.tag) for p in bkg_peaks], bcont,
                            seed_of(det, "bkgpair/background", i), live_time=live_time * k,
                            meta={"category": "background_pair"})
        bkg.spectrum.sample_id = f"background-{i}"
        yield smp, bkg, truth


REF_PULSER_KEV = {"HPGe": 1950.0, "NaI": 2800.0}
REF_PULSER_CPS = 50.0
REF_LOSSES = (0.0, 0.05, 0.10)


def reference_peak_spectra(det: DetectorSpec, n: int, live_time: float = 3600.0,
                           with_pulser: bool = True) -> Iterator[tuple]:
    """(spectrum, truth, loss) for the reference-peak protocol
    (docs/baseline/reference_peak_protocol.md): Cs-137 and Co-60 (s ~ 40) plus a pulser of
    REF_PULSER_CPS; a loss fraction (REF_LOSSES, cycled) removes counts from EVERY peak, the pulser
    included (random summing).  truth[(nuclide, keV)] = true pre-loss counts."""
    cont = base_continuum(det)
    cy = continuum_counts(det, cont)
    src = [("Cs-137", 661.657), ("Co-60", 1173.228), ("Co-60", 1332.492)]
    areas = {k: area_for_snr(det, cy, k[1], 40.0) for k in src}
    for i in range(n):
        loss = REF_LOSSES[i % len(REF_LOSSES)]
        keep = 1.0 - loss
        peaks = [TruePeak(e, a * keep, tag=nm) for (nm, e), a in areas.items()]
        if with_pulser:
            peaks.append(TruePeak(REF_PULSER_KEV[det.name], REF_PULSER_CPS * live_time * keep, tag="pulser"))
        syn = make_spectrum(det, peaks, cont, seed_of(det, "refpeak", i), live_time=live_time,
                            meta={"category": "reference_peak", "loss": loss})
        yield syn, dict(areas), loss


BLANK_REAGENT = {"Cs-137": 661.657, "Mn-54": 834.848}     # reagent contamination, s ~ 15 each


def blank_triples(det: DetectorSpec, n: int, live_time: float = 3600.0) -> Iterator[tuple]:
    """(sample, blank, background, truth) for the reagent-blank protocol
    (docs/baseline/reagent_blank_protocol.md).  The laboratory background is that of
    `background_pairs`; the blank is the background rate plus a reagent contamination
    (BLANK_REAGENT); the sample is the background rate plus the same contamination plus its own
    Cs-137 and Co-60.  truth[(nuclide, keV)] = true sample-only net counts (0 for Mn-54)."""
    lib = load_library()
    cont = base_continuum(det)
    cy = continuum_counts(det, cont)
    bl = [(e, y * w) for nm, w in BKG_NUCLIDES.items() for e, y in _lines(nm, lib)]
    bkg_peaks = _source_peaks(det, cy, bl, 40.0)
    bkg_peaks.append(TruePeak(661.657, area_for_snr(det, cy, 661.657, 8.0), tag="Cs-137 contamination"))
    reagent = [TruePeak(e, area_for_snr(det, cy, e, 15.0), tag=f"{nm} reagent") for nm, e in BLANK_REAGENT.items()]
    src = [TruePeak(661.657, area_for_snr(det, cy, 661.657, 40.0), tag="Cs-137"),
           TruePeak(1173.228, area_for_snr(det, cy, 1173.228, 40.0), tag="Co-60"),
           TruePeak(1332.492, area_for_snr(det, cy, 1332.492, 40.0), tag="Co-60")]
    k = BKG_TIME_RATIO
    bcont = Continuum(exp_amp=cont.exp_amp * k, exp_scale_kev=cont.exp_scale_kev, flat=cont.flat * k)
    truth = {("Cs-137", 661.657): src[0].area, ("Co-60", 1173.228): src[1].area,
             ("Co-60", 1332.492): src[2].area, ("Mn-54", 834.848): 0.0}
    for i in range(n):
        smp = make_spectrum(det, bkg_peaks + reagent + src, cont, seed_of(det, "blank/sample", i),
                            live_time=live_time, meta={"category": "reagent_blank"})
        blk = make_spectrum(det, bkg_peaks + reagent, cont, seed_of(det, "blank/blank", i),
                            live_time=live_time, meta={"category": "reagent_blank"})
        blk.spectrum.sample_id = f"blank-{i}"
        bkg = make_spectrum(det, [TruePeak(p.energy, p.area * k, tag=p.tag) for p in bkg_peaks], bcont,
                            seed_of(det, "blank/background", i), live_time=live_time * k,
                            meta={"category": "reagent_blank"})
        bkg.spectrum.sample_id = f"background-{i}"
        yield smp, blk, bkg, truth


# ---------------------------------------------------------------------------- efficiency calibration
EFF_STANDARD = ("Am-241", "Cd-109", "Co-57", "Ce-139", "Hg-203", "Sn-113", "Sr-85", "Cs-137", "Y-88", "Co-60")
EFF_SCALE = {"HPGe": 0.05, "NaI": 0.15}          # absolute efficiency at 120 keV
EFF_CERT_REL_UNC = 0.02                           # certificate activity uncertainty, per nuclide
EFF_DECAY_DAYS = 60.0                             # reference date before the measurement


# Smooth true curve, deliberately outside the fitted model family: a low-energy rise
# (absorption in the entrance window and dead layer) times a power-law fall,
# eps = k (1 - exp(-(E / E1)^p)) (E / 120)^-q.  ``shape="kinked"`` is the first-run curve
# (rel_efficiency: power laws meeting in a corner at 120 keV), kept as an informational case.
EFF_SHAPE = {"HPGe": (55.0, 3.0, 0.90), "NaI": (45.0, 2.5, 1.00)}     # E1 keV, p, q


def true_efficiency(det: DetectorSpec, e_kev, shape: str = "smooth"):
    """The true full-energy-peak efficiency of the efficiency scenarios."""
    k = EFF_SCALE.get(det.name, 0.05)
    e = np.maximum(np.atleast_1d(np.asarray(e_kev, dtype=float)), 20.0)
    if shape == "kinked":
        v = np.array([k * rel_efficiency(float(x)) for x in e])
    else:
        e1, pw, q = EFF_SHAPE.get(det.name, EFF_SHAPE["HPGe"])
        v = k * (1.0 - np.exp(-(e / e1) ** pw)) * (e / 120.0) ** -q
    return float(v[0]) if np.ndim(e_kev) == 0 else v


def efficiency_calibration(det: DetectorSpec, n: int, activity_bq: float = 500.0,
                           live_time: float = 3600.0, shape: str = "smooth") -> Iterator[tuple]:
    """(synthetic spectrum, certificate lines) of a mixed-nuclide standard measured with the
    true efficiency of :func:`true_efficiency`.  Each nuclide's true activity differs from the
    certificate value by N(0, EFF_CERT_REL_UNC), drawn per realisation (the certificate error
    is shared by all lines of that nuclide); the reference date is EFF_DECAY_DAYS before the
    start.  No true-coincidence summing is simulated."""
    from datetime import datetime, timedelta
    from ..analysis.efficiency import CertNuclide, certificate_lines, counting_decay_factor, decay_factor
    start = datetime(2026, 3, 1, 9, 0, 0)
    ref = start - timedelta(days=EFF_DECAY_DAYS)
    cert = certificate_lines([CertNuclide(nm, activity_bq, activity_bq * EFF_CERT_REL_UNC, ref)
                              for nm in EFF_STANDARD])
    real_time = live_time * 1.01
    e_lo, e_hi = float(det.energy(0)), float(det.energy(det.n_channels - 1))
    for i in range(n):
        rng = np.random.default_rng(seed_of(det, "efficiency/cert", i))
        factor = {nm: 1.0 + EFF_CERT_REL_UNC * rng.standard_normal() for nm in EFF_STANDARD}
        peaks = []
        for ln in cert:
            a0 = activity_bq * factor[ln.nuclide] * decay_factor(ln.half_life_s, EFF_DECAY_DAYS * 86400.0)
            c = counting_decay_factor(ln.half_life_s, real_time)
            area = a0 * c * ln.intensity * float(true_efficiency(det, ln.energy, shape)) * live_time
            if area > 0 and e_lo < ln.energy < e_hi:
                peaks.append(TruePeak(ln.energy, area, tag=ln.nuclide))
        syn = make_spectrum(det, peaks, base_continuum(det), seed_of(det, "efficiency", i), live_time=live_time,
                            meta={"category": "efficiency", "true_factor": factor, "shape": shape})
        syn.spectrum.start_time = start
        syn.spectrum.real_time = real_time
        yield syn, cert

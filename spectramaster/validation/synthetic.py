"""Seeded synthetic HPGe / NaI spectra with known peaks.

The generator is deliberately *not* the fitting model of ``analysis/peaks.py``:

* peak counts are channel integrals of the shape (not samples at the channel centre);
* optional low-energy exponential tail (Hypermet-like) and peak-related step;
* continuum = exponential + constant, plus optional Compton plateau/edge of a strong line,
  smeared by the detector resolution;
* the resolution law differs from the engine's built-in default, so the engine has to adapt.

Every channel is then drawn from a Poisson distribution with ``numpy.random.default_rng(seed)``,
so a (scenario, seed) pair always reproduces the same spectrum.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.special import erf, erfc

from ..model import Spectrum

F2S = 1.0 / (2.0 * math.sqrt(2.0 * math.log(2.0)))   # FWHM -> sigma
ME = 510.99895                                        # electron rest energy, keV


@dataclass(frozen=True)
class DetectorSpec:
    """Synthetic detector: channels, linear calibration and resolution FWHM(E) = sqrt(a + b E + c E^2)."""
    name: str
    n_channels: int
    offset_kev: float
    gain_kev: float
    fwhm_a: float
    fwhm_b: float
    fwhm_c: float = 0.0
    label: str = ""          # Spectrum.detector text ("" = let the engine guess)
    quad_kev: float = 0.0    # true calibration E = offset + gain*ch + quad*ch^2 (integral non-linearity)

    def energy(self, ch):
        c = np.asarray(ch, dtype=float)
        return self.offset_kev + self.gain_kev * c + self.quad_kev * c * c

    def channel(self, e_kev: float) -> float:
        if self.quad_kev == 0.0:
            return (e_kev - self.offset_kev) / self.gain_kev
        q, g = self.quad_kev, self.gain_kev
        return (-g + math.sqrt(g * g - 4.0 * q * (self.offset_kev - e_kev))) / (2.0 * q)

    @property
    def energy_coeffs(self) -> list[float]:
        return [self.offset_kev, self.gain_kev] + ([self.quad_kev] if self.quad_kev else [])

    def fwhm_kev(self, e_kev):
        e = np.asarray(e_kev, dtype=float)
        return np.sqrt(self.fwhm_a + self.fwhm_b * e + self.fwhm_c * e * e)

    def fwhm_ch(self, e_kev):
        if self.quad_kev == 0.0:
            return self.fwhm_kev(e_kev) / self.gain_kev
        return self.fwhm_kev(e_kev) / (self.gain_kev + 2.0 * self.quad_kev * self.channel(float(e_kev)))


# HPGe: ~1.1 keV @ 122, ~1.8 keV @ 1332 (typical coaxial p-type; differs from the engine default).
HPGE = DetectorSpec("HPGe", 4096, 0.0, 0.5, 1.0, 0.0016)
# NaI(Tl) 3x3": ~7.3 % @ 662 keV; resolution ~ sqrt(E) with a small quadratic term.
NAI = DetectorSpec("NaI", 1024, 0.0, 3.0, 4.0, 3.1, 2.0e-5)
# NaI on a 4096-channel MCA (0.75 keV/ch), no detector label - real lab configuration.
NAI_4K = DetectorSpec("NaI", 4096, 0.0, 0.75, 4.0, 3.1, 2.0e-5)
# HPGe with an offset and integral non-linearity (+0.84 keV at channel 4096, ~0.4 FWHM):
# a linear calibration through a wide set of lines is visibly biased, a quadratic one is not.
HPGE_NL = DetectorSpec("HPGe", 4096, 1.2, 0.4995, 1.0, 0.0016, quad_kev=5.0e-8)

DETECTORS = {"HPGe": HPGE, "NaI": NAI}


@dataclass
class TruePeak:
    energy: float            # keV
    area: float              # expected counts in the full peak (Gaussian + tail)
    centroid: float = 0.0    # channel (filled by the generator)
    fwhm_ch: float = 0.0     # channels (filled by the generator)
    tail_frac: float = 0.0   # fraction of the area in the low-energy tail
    tail_slope: float = 1.5  # tail decay length in units of sigma
    step_frac: float = 0.0   # peak-related step height, per channel, as a fraction of area/FWHM_ch
    tag: str = ""            # scenario-specific label (e.g. "s=5", "doublet-hi")


@dataclass
class Continuum:
    exp_amp: float = 0.0         # counts/channel at E = 0 of the exponential part
    exp_scale_kev: float = 400.0
    flat: float = 0.0            # counts/channel
    compton_line_kev: Optional[float] = None
    compton_level: float = 0.0   # counts/channel on the Compton plateau below the edge
    edge_extra_sigma_kev: float = 0.0   # extra edge smearing (electron binding / Doppler, multiple
                                        # scattering) added in quadrature to the detector resolution


@dataclass
class SyntheticSpectrum:
    spectrum: Spectrum
    truth: list[TruePeak]
    expected: np.ndarray          # noiseless expectation per channel
    continuum: np.ndarray         # noiseless continuum per channel
    detector: DetectorSpec
    seed: int
    meta: dict = field(default_factory=dict)


def compton_edge_kev(e_kev: float) -> float:
    return e_kev * (1.0 - 1.0 / (1.0 + 2.0 * e_kev / ME))


def _gauss_integral(lo, hi, mu, sigma):
    s = sigma * math.sqrt(2.0)
    return 0.5 * (erf((hi - mu) / s) - erf((lo - mu) / s))


def _peak_counts(edges: np.ndarray, mu: float, sigma: float, p: TruePeak) -> np.ndarray:
    """Expected counts per channel of one peak, integrated over the channel edges."""
    lo, hi = edges[:-1], edges[1:]
    g = (1.0 - p.tail_frac) * _gauss_integral(lo, hi, mu, sigma)
    out = p.area * g
    if p.tail_frac > 0:
        # exponential tail exp((x-mu)/t) for x < mu convolved with the Gaussian; integrate by
        # sub-sampling (10 points / channel) and normalise numerically to tail_frac.
        t = p.tail_slope * sigma
        sub = 10
        x = (lo[:, None] + (np.arange(sub)[None, :] + 0.5) / sub).ravel()
        d = np.clip(x - mu, -60.0 * t - 8.0 * sigma, 8.0 * sigma)   # avoid exp overflow far away
        inside = (x - mu >= -60.0 * t - 8.0 * sigma) & (x - mu <= 8.0 * sigma)
        dens = np.where(inside, np.exp(d / t + sigma * sigma / (2 * t * t))
                        * erfc((d / sigma + sigma / t) / math.sqrt(2.0)), 0.0)
        dens = dens.reshape(len(lo), sub).sum(axis=1)
        norm = dens.sum()
        if norm > 0:
            out = out + p.area * p.tail_frac * dens / norm
    if p.step_frac > 0:
        fw = sigma / F2S
        step = 0.5 * erfc((0.5 * (lo + hi) - mu) / (sigma * math.sqrt(2.0)))
        out = out + p.step_frac * p.area / fw * step
    return out


def continuum_counts(det: DetectorSpec, c: Continuum) -> np.ndarray:
    ch = np.arange(det.n_channels, dtype=float)
    e = det.energy(ch)
    y = c.exp_amp * np.exp(-e / c.exp_scale_kev) + c.flat
    if c.compton_line_kev and c.compton_level > 0:
        ec = compton_edge_kev(c.compton_line_kev)
        sig = math.hypot(float(det.fwhm_kev(ec)) * F2S, c.edge_extra_sigma_kev)
        # plateau rising mildly towards the edge (Klein-Nishina-like shape), smeared edge
        shape = 0.8 + 0.4 * np.clip(e / ec, 0, 1) ** 2
        y = y + c.compton_level * shape * 0.5 * erfc((e - ec) / (sig * math.sqrt(2.0)))
    return y


def make_spectrum(det: DetectorSpec, peaks: list[TruePeak], cont: Continuum, seed: int,
                  live_time: float = 3600.0, gain_error: float = 0.0, meta: Optional[dict] = None
                  ) -> SyntheticSpectrum:
    """Build one Poisson realisation.

    gain_error: relative error deliberately put into the *reported* energy calibration
    (e.g. 0.003 = the file claims a gain 0.3 % too high) to emulate calibration drift.
    """
    edges = np.arange(det.n_channels + 1, dtype=float) - 0.5
    bkg = continuum_counts(det, cont)
    lam = bkg.copy()
    truth = []
    for p in peaks:
        mu = det.channel(p.energy)
        fw = float(det.fwhm_ch(p.energy))
        q = TruePeak(**{**p.__dict__, "centroid": mu, "fwhm_ch": fw})
        lam += _peak_counts(edges, mu, fw * F2S, q)
        truth.append(q)
    rng = np.random.default_rng(seed)
    counts = rng.poisson(lam).astype(float)
    spec = Spectrum(counts=counts.tolist(),
                    energy_coeffs=[det.offset_kev, det.gain_kev * (1.0 + gain_error)]
                    + ([det.quad_kev * (1.0 + gain_error)] if det.quad_kev else []),
                    live_time=live_time, real_time=live_time * 1.01, sample_id=f"synthetic-{seed}",
                    description="SpectraMaster validation synthetic spectrum", detector=det.label,
                    source_format="synthetic")
    return SyntheticSpectrum(spec, truth, lam, bkg, det, seed, dict(meta or {}))


def window_background(det: DetectorSpec, cont_y: np.ndarray, energy: float, width_fwhm: float = 2.5) -> float:
    """Expected continuum counts in a window of `width_fwhm` FWHM centred on `energy`."""
    mu = det.channel(energy)
    half = 0.5 * width_fwhm * float(det.fwhm_ch(energy))
    lo, hi = int(math.floor(mu - half)), int(math.ceil(mu + half))
    lo, hi = max(lo, 0), min(hi, det.n_channels - 1)
    return float(cont_y[lo:hi + 1].sum())


def area_for_snr(det: DetectorSpec, cont_y: np.ndarray, energy: float, s: float) -> float:
    """True net area A giving s = A / sqrt(B_2.5FWHM) (see acceptance.py conventions)."""
    return s * math.sqrt(max(window_background(det, cont_y, energy), 1.0))

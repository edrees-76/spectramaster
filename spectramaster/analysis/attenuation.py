"""Self-attenuation of a sample whose density (or matrix) differs from the calibration source
(docs/baseline/self_attenuation_protocol.md, finding F5).

Mass attenuation coefficients mu/rho (cm2/g, coherent scattering included) versus photon energy
(MeV), from NIST Standard Reference Database 126: J. H. Hubbell and S. M. Seltzer, "Tables of
X-Ray Mass Attenuation Coefficients and Mass Energy-Absorption Coefficients", read from
https://physics.nist.gov/PhysRefData/XrayMassCoef/ComTab/{water,pmma,concrete}.html on
2026-10-22 (US government work, public domain).  Only the rows from 10 keV are kept.

Matrices: ``water``; ``organic`` = polymethyl methacrylate, a proxy for resins and organic
matter; ``mineral`` = ordinary concrete, a proxy for soil and sediment.

The correction uses the slab model: the mean transmission of a uniform layer of height h seen
perpendicular to its face, T = (1 - exp(-mu h)) / (mu h).  For a cylinder on the end cap the
oblique paths make the true effect somewhat larger; the user's ``rel_unc`` carries that.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# (energy MeV, mu/rho cm2/g), NIST SRD 126
MU_RHO = {
    "water": (
        (1.00000E-02, 5.329E+00),
        (1.50000E-02, 1.673E+00),
        (2.00000E-02, 8.096E-01),
        (3.00000E-02, 3.756E-01),
        (4.00000E-02, 2.683E-01),
        (5.00000E-02, 2.269E-01),
        (6.00000E-02, 2.059E-01),
        (8.00000E-02, 1.837E-01),
        (1.00000E-01, 1.707E-01),
        (1.50000E-01, 1.505E-01),
        (2.00000E-01, 1.370E-01),
        (3.00000E-01, 1.186E-01),
        (4.00000E-01, 1.061E-01),
        (5.00000E-01, 9.687E-02),
        (6.00000E-01, 8.956E-02),
        (8.00000E-01, 7.865E-02),
        (1.00000E+00, 7.072E-02),
        (1.25000E+00, 6.323E-02),
        (1.50000E+00, 5.754E-02),
        (2.00000E+00, 4.942E-02),
        (3.00000E+00, 3.969E-02),
        (4.00000E+00, 3.403E-02),
        (5.00000E+00, 3.031E-02),
        (6.00000E+00, 2.770E-02),
        (8.00000E+00, 2.429E-02),
        (1.00000E+01, 2.219E-02),
        (1.50000E+01, 1.941E-02),
        (2.00000E+01, 1.813E-02),
    ),
    "organic": (
        (1.00000E-02, 3.357E+00),
        (1.50000E-02, 1.101E+00),
        (2.00000E-02, 5.714E-01),
        (3.00000E-02, 3.032E-01),
        (4.00000E-02, 2.350E-01),
        (5.00000E-02, 2.074E-01),
        (6.00000E-02, 1.924E-01),
        (8.00000E-02, 1.751E-01),
        (1.00000E-01, 1.641E-01),
        (1.50000E-01, 1.456E-01),
        (2.00000E-01, 1.328E-01),
        (3.00000E-01, 1.152E-01),
        (4.00000E-01, 1.031E-01),
        (5.00000E-01, 9.410E-02),
        (6.00000E-01, 8.701E-02),
        (8.00000E-01, 7.641E-02),
        (1.00000E+00, 6.870E-02),
        (1.25000E+00, 6.143E-02),
        (1.50000E+00, 5.591E-02),
        (2.00000E+00, 4.796E-02),
        (3.00000E+00, 3.844E-02),
        (4.00000E+00, 3.286E-02),
        (5.00000E+00, 2.919E-02),
        (6.00000E+00, 2.659E-02),
        (8.00000E+00, 2.317E-02),
        (1.00000E+01, 2.105E-02),
        (1.50000E+01, 1.820E-02),
        (2.00000E+01, 1.684E-02),
    ),
    "mineral": (
        (1.00000E-02, 2.045E+01),
        (1.50000E-02, 6.351E+00),
        (2.00000E-02, 2.806E+00),
        (3.00000E-02, 9.601E-01),
        (4.00000E-02, 5.058E-01),
        (5.00000E-02, 3.412E-01),
        (6.00000E-02, 2.660E-01),
        (8.00000E-02, 2.014E-01),
        (1.00000E-01, 1.738E-01),
        (1.50000E-01, 1.436E-01),
        (2.00000E-01, 1.282E-01),
        (3.00000E-01, 1.097E-01),
        (4.00000E-01, 9.783E-02),
        (5.00000E-01, 8.915E-02),
        (6.00000E-01, 8.236E-02),
        (8.00000E-01, 7.227E-02),
        (1.00000E+00, 6.495E-02),
        (1.25000E+00, 5.807E-02),
        (1.50000E+00, 5.288E-02),
        (2.00000E+00, 4.557E-02),
        (3.00000E+00, 3.701E-02),
        (4.00000E+00, 3.217E-02),
        (5.00000E+00, 2.908E-02),
        (6.00000E+00, 2.697E-02),
        (8.00000E+00, 2.432E-02),
        (1.00000E+01, 2.278E-02),
        (1.50000E+01, 2.096E-02),
        (2.00000E+01, 2.030E-02),
    ),
}
MATRICES = tuple(MU_RHO)
_LOG = {k: (np.log([e * 1000.0 for e, _m in v]), np.log([m for _e, m in v])) for k, v in MU_RHO.items()}


def mass_attenuation(matrix: str, energy_kev: float) -> float:
    """mu/rho (cm2/g) of `matrix` at `energy_kev`, log-log interpolation of the NIST table."""
    if matrix not in _LOG:
        raise ValueError(f"matrix must be one of {MATRICES}, got {matrix!r}")
    le, lm = _LOG[matrix]
    x = math.log(energy_kev)
    if not le[0] <= x <= le[-1]:
        raise ValueError(f"{energy_kev:g} keV is outside the attenuation table (10 keV - 20 MeV)")
    return float(math.exp(np.interp(x, le, lm)))


def slab_transmission(mu_per_cm: float, height_cm: float) -> float:
    """Mean transmission (1 - exp(-mu h)) / (mu h) of a uniform slab (1 for mu h -> 0)."""
    x = mu_per_cm * height_cm
    if x < 1e-8:
        return 1.0 - x / 2.0
    return -math.expm1(-x) / x


@dataclass(frozen=True)
class SelfAttenuation:
    """Correction of a sample (matrix, density) measured with an efficiency calibrated on a source
    of the same container and fill height but another (matrix, density)."""
    sample_matrix: str
    sample_density: float          # g/cm3
    calibration_matrix: str
    calibration_density: float     # g/cm3
    height_mm: float               # fill height (slab thickness)
    rel_unc: float = 0.0           # model uncertainty of the factor (fraction, 1 sigma)

    def __post_init__(self):
        for m in (self.sample_matrix, self.calibration_matrix):
            if m not in MU_RHO:
                raise ValueError(f"matrix must be one of {MATRICES}, got {m!r}")
        for n in ("sample_density", "calibration_density", "height_mm"):
            if not getattr(self, n) > 0:
                raise ValueError(f"{n} must be positive")
        if self.rel_unc < 0:
            raise ValueError("rel_unc must not be negative")

    def factor(self, energy_kev: float) -> float:
        """Multiplies the activity: T_calibration(E) / T_sample(E)."""
        h = self.height_mm / 10.0
        t_cal = slab_transmission(mass_attenuation(self.calibration_matrix, energy_kev) * self.calibration_density, h)
        t_smp = slab_transmission(mass_attenuation(self.sample_matrix, energy_kev) * self.sample_density, h)
        return t_cal / t_smp

    def describe(self) -> str:
        return (f"self-attenuation (slab {self.height_mm:g} mm): sample {self.sample_matrix} "
                f"{self.sample_density:g} g/cm3, calibration {self.calibration_matrix} "
                f"{self.calibration_density:g} g/cm3")

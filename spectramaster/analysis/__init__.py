"""Spectrum analysis: peak search and nuclide identification.

Public contract shared by the analysis engine, the CLI and the GUI:

    from spectramaster.analysis import find_peaks, identify, Peak, NuclideMatch

    peaks = find_peaks(spectrum)                 # list[Peak], sorted by centroid
    matches = identify(spectrum, peaks)          # list[NuclideMatch], best first
    peaks, report = inspect_fit(spectrum)        # same peaks + FitReport for inspection

Both functions are pure (no I/O apart from loading the bundled nuclide library
once) and must be fast enough to run on every spectrum the GUI displays
(< 0.5 s for 16k channels).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Peak:
    centroid: float              # channel (fractional), same channel numbering as Spectrum.counts index + first_channel
    energy: Optional[float]      # keV at the centroid, None if the spectrum is uncalibrated
    fwhm: float                  # channels
    fwhm_kev: Optional[float]
    net_area: float              # counts above the fitted background
    net_area_unc: float          # 1-sigma counts
    gross_area: float
    background: float            # counts under the peak region
    left: int                    # ROI first channel (index into counts)
    right: int                   # ROI last channel (inclusive)
    significance: float          # net / sigma
    count_rate: Optional[float] = None   # net counts / live time (cps)
    nuclide: str = ""            # best assignment filled by identify(), e.g. "Cs-137"
    line_energy: Optional[float] = None  # library energy of that assignment (keV)
    note: str = ""               # e.g. "single escape", "sum peak", "annihilation"
    # --- optional additions (analysis engine v1) ---
    centroid_unc: Optional[float] = None  # 1-sigma uncertainty of the centroid (channels)
    multiplet: int = 1           # number of peaks fitted together with this one (1 = singlet)


@dataclass
class NuclideMatch:
    nuclide: str                 # "Cs-137"
    confidence: float            # 0..1
    matched: list[tuple[float, Peak]] = field(default_factory=list)   # (library keV, peak)
    missing: list[float] = field(default_factory=list)   # strong library lines expected but not found (keV)
    half_life: str = ""          # human readable, e.g. "30.08 y"
    category: str = ""           # "natural", "fission", "activation", "calibration", "medical", ...
    note: str = ""               # e.g. "Ra-226 daughter (U-238 series)"
    # --- optional additions (analysis engine v1) ---
    background: bool = False     # nuclide typically present in the natural/lab background
    series: str = ""             # natural decay series, e.g. "U-238 series" ("" if none)


# The submodules are imported eagerly and the wrappers defined *after* them: importing the
# submodule ``spectramaster.analysis.identify`` would otherwise replace the ``identify``
# function attribute of this package with the module object.
from . import peaks as _peaks_module          # noqa: E402
from . import identify as _identify_module    # noqa: E402


def find_peaks(spectrum, **kwargs) -> list[Peak]:
    return _peaks_module.find_peaks(spectrum, **kwargs)


def identify(spectrum, peaks: Optional[list[Peak]] = None, **kwargs) -> list[NuclideMatch]:
    return _identify_module.identify(spectrum, peaks, **kwargs)


FitReport = _peaks_module.FitReport
FitGroup = _peaks_module.FitGroup
FitComponent = _peaks_module.FitComponent


def inspect_fit(spectrum, **kwargs) -> tuple[list[Peak], "FitReport"]:
    """Peaks plus the fit report (data, total fit, components, background, residuals,
    warnings and discarded components with reasons) for the fit-inspection view."""
    rep = FitReport()
    return _peaks_module.find_peaks(spectrum, report=rep, **kwargs), rep


__all__ = ["Peak", "NuclideMatch", "find_peaks", "identify", "inspect_fit", "FitReport", "FitGroup",
           "FitComponent"]

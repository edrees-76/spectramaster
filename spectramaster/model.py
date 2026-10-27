"""Format-neutral in-memory spectrum representation.

Every reader returns a list of Spectrum objects and every writer consumes one.
This is the only contract shared between format modules, the converter, the CLI
and the GUI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Spectrum:
    counts: list[float]
    """Counts per channel; index 0 is the first channel stored in the file."""

    energy_coeffs: list[float] = field(default_factory=list)
    """Polynomial energy calibration E(ch) = c0 + c1*ch + c2*ch^2 ... in keV.

    `ch` is the channel number (0-based, channel centre convention as used by
    ORTEC/Canberra/IAEA SPE). Empty list means "uncalibrated".
    """

    live_time: Optional[float] = None
    """Seconds."""

    real_time: Optional[float] = None
    """Seconds."""

    start_time: Optional[datetime] = None
    """Acquisition start (naive local time)."""

    sample_id: str = ""
    """Short sample identifier / spectrum title (DataMaster's "Sample ID")."""

    description: str = ""
    """Free-text description / remarks."""

    detector: str = ""
    """Detector or MCA name/identifier if known."""

    first_channel: int = 0
    """Channel number of counts[0] (CHN 'channel offset'). Usually 0."""

    fwhm_coeffs: list[float] = field(default_factory=list)
    """Optional shape (FWHM) calibration, keV, polynomial in channel."""

    extra: dict = field(default_factory=dict)
    """Format-specific metadata worth carrying along (str -> str/number)."""

    source_path: str = ""
    """Path the spectrum was read from (informational)."""

    source_format: str = ""
    """Key of the FormatSpec that produced it (informational)."""

    variance: Optional[tuple] = field(default=None, repr=False, compare=False)
    """(SHA-256 of the counts, per-channel variance) of a spectrum whose contents are not Poisson
    counts (a net spectrum); in memory only.  Read it with ``analysis.background.channel_variance``,
    which ignores it once the counts have changed."""

    # ------------------------------------------------------------------ helpers
    @property
    def num_channels(self) -> int:
        return len(self.counts)

    @property
    def total_counts(self) -> float:
        return float(sum(self.counts))

    def energy_of(self, channel: float) -> Optional[float]:
        if not self.energy_coeffs:
            return None
        e = 0.0
        for power, c in enumerate(self.energy_coeffs):
            e += c * channel ** power
        return e

    def energies(self) -> Optional[list[float]]:
        """Energy at the centre of each stored channel, or None if uncalibrated."""
        if not self.energy_coeffs:
            return None
        return [self.energy_of(self.first_channel + i) for i in range(len(self.counts))]

    @property
    def dead_time_percent(self) -> Optional[float]:
        if self.live_time and self.real_time and self.real_time > 0:
            return 100.0 * (self.real_time - self.live_time) / self.real_time
        return None

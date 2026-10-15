"""Sample information needed to turn an activity (Bq) into a concentration.

Every quantity is ``Optional`` and stays ``None`` until the user supplies it: a missing
mass is never replaced by 1 kg, a missing filter fraction never by 1.  Before a
concentration is reported, :meth:`SampleInfo.concentration_unit_inputs` lists what is
still missing for the requested unit:

* ``Bq``     - nothing (activity of the measured object).
* ``Bq/kg``  - mass and its basis (dry / wet; the two differ by the moisture content).
* ``Bq/L``   - liquid volume.
* ``Bq/m3``  - sampled air volume (given, or flow rate x duration, the duration given or
  from sampling start/end), the measured fraction of the filter and the collection
  efficiency assumption (both explicit, 1.0 when the whole filter / full efficiency).

Units: mass kg, volume L, air volume m3, flow m3/h, duration h.  Dates are ISO strings
(naive local time, as ``Spectrum.start_time``).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional

from .common import from_known, opt_float

MATRIX_TYPES = ("soil", "water", "food", "air_filter", "other")
MASS_BASES = ("dry", "wet")
CONCENTRATION_UNITS = ("Bq", "Bq/kg", "Bq/L", "Bq/m3")


def _iso(v) -> Optional[str]:
    if v is None or v == "":
        return None
    return v.isoformat() if isinstance(v, datetime) else datetime.fromisoformat(str(v)).isoformat()


@dataclass
class SampleInfo:
    sample_id: str = ""
    matrix_type: str = "other"
    mass_kg: Optional[float] = None
    mass_basis: Optional[str] = None
    volume_l: Optional[float] = None
    air_volume_m3: Optional[float] = None
    flow_rate_m3_h: Optional[float] = None
    sampling_duration_h: Optional[float] = None
    sampling_start: Optional[str] = None
    sampling_end: Optional[str] = None
    reference_date: Optional[str] = None       # decay-correction reference (None = acquisition start)
    filter_fraction: Optional[float] = None    # measured fraction of the filter (0, 1]
    collection_efficiency: Optional[float] = None   # (0, 1]
    collection_efficiency_note: str = ""
    description: str = ""

    def __post_init__(self):
        if self.matrix_type not in MATRIX_TYPES:
            raise ValueError(f"matrix type must be one of {MATRIX_TYPES}, got {self.matrix_type!r}")
        if self.mass_basis not in MASS_BASES + (None,):
            raise ValueError(f"mass basis must be 'dry', 'wet' or None, got {self.mass_basis!r}")
        for n in ("mass_kg", "volume_l", "air_volume_m3", "flow_rate_m3_h", "sampling_duration_h",
                  "filter_fraction", "collection_efficiency"):
            setattr(self, n, opt_float(getattr(self, n), n))
        for n in ("filter_fraction", "collection_efficiency"):
            v = getattr(self, n)
            if v is not None and v > 1.0:
                raise ValueError(f"{n} must be in (0, 1], got {v}")
        for n in ("sampling_start", "sampling_end", "reference_date"):
            setattr(self, n, _iso(getattr(self, n)))
        if self.sampling_start and self.sampling_end and self.sampling_end < self.sampling_start:
            raise ValueError("sampling end is before sampling start")

    def sampling_hours(self) -> Optional[float]:
        if self.sampling_duration_h is not None:
            return self.sampling_duration_h
        if self.sampling_start and self.sampling_end:
            dt = datetime.fromisoformat(self.sampling_end) - datetime.fromisoformat(self.sampling_start)
            return dt.total_seconds() / 3600.0 or None
        return None

    def air_volume(self) -> Optional[float]:
        """Sampled air volume in m3 (given, else flow x duration), None if unknown."""
        if self.air_volume_m3 is not None:
            return self.air_volume_m3
        h = self.sampling_hours()
        return self.flow_rate_m3_h * h if (self.flow_rate_m3_h is not None and h) else None

    def concentration_unit_inputs(self, unit: str) -> list[str]:
        """Missing inputs required to express a result in `unit` ([] = all present)."""
        if unit not in CONCENTRATION_UNITS:
            raise ValueError(f"unknown concentration unit {unit!r}; expected one of {CONCENTRATION_UNITS}")
        miss: list[str] = []
        if unit == "Bq/kg":
            if self.mass_kg is None:
                miss.append("sample mass (kg)")
            if self.mass_basis is None:
                miss.append("mass basis (dry or wet)")
        elif unit == "Bq/L":
            if self.volume_l is None:
                miss.append("sample volume (L)")
        elif unit == "Bq/m3":
            if self.air_volume() is None:
                miss.append("sampled air volume (m3), or flow rate (m3/h) and sampling duration")
            if self.filter_fraction is None:
                miss.append("measured filter fraction (1 if the whole filter was measured)")
            if self.collection_efficiency is None:
                miss.append("filter collection efficiency assumption")
        return miss

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SampleInfo":
        return from_known(cls, d)

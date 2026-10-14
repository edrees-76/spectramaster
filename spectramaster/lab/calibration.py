"""Calibration records (energy, FWHM, efficiency) referenced by content hash.

Design
------
* A record is identified by a random ``id`` *and* by ``content_hash``: SHA-256 of the
  canonical JSON of its scientific content (kind, detector/geometry links, model,
  parameters, covariance, valid range, payload).  Labels, notes, creation date,
  provenance and validation status are excluded, so validating or annotating a record
  does not change its hash while any change to a coefficient does.  Sessions store a
  snapshot together with the hash; a later mismatch shows the calibration has changed
  since the results were produced (see ``AnalysisSession.is_stale_against``).
* ``to_dict`` writes the hash; ``from_dict`` keeps it as ``stored_hash`` so that
  hand-edited files can be detected (:meth:`CalibrationRecord.integrity_ok`).
* Imported and manually typed calibrations start as ``"unvalidated"``; only an explicit
  :meth:`CalibrationRecord.set_validation` changes that.
* Efficiency records embed ``EfficiencyCurve.to_dict()`` as ``payload`` (format
  ``spectramaster-efficiency-1``) so the curve can be rebuilt exactly.
* Energy / FWHM records hold the polynomial coefficients of ``Spectrum`` (keV as a
  polynomial in the channel number, ``first_channel`` convention of the file).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from .common import content_hash, from_known, new_id, utc_now

CALIBRATION_KINDS = ("energy", "fwhm", "efficiency")
SOURCES = ("measured", "imported", "manual")
VALIDATION = ("unvalidated", "validated", "rejected")
# payload keys that are labels, not science (top level only)
_PAYLOAD_LABELS = ("format", "name", "note", "date", "source")


@dataclass
class CalibrationRecord:
    kind: str
    model: str = ""                     # "poly2_channel", "loglog", "two_branch" ...
    params: list[float] = field(default_factory=list)
    cov: Optional[list[list[float]]] = None
    energy_range: Optional[list[float]] = None     # [keV min, keV max] of validity, None = unknown
    detector_id: Optional[str] = None
    geometry_id: Optional[str] = None   # efficiency only
    source: str = "imported"
    validation_status: str = "unvalidated"
    validation_note: str = ""
    payload: dict = field(default_factory=dict)
    id: str = field(default_factory=new_id)
    created: str = field(default_factory=utc_now)
    name: str = ""
    note: str = ""
    stored_hash: Optional[str] = field(default=None, compare=False)

    def __post_init__(self):
        if self.kind not in CALIBRATION_KINDS:
            raise ValueError(f"calibration kind must be one of {CALIBRATION_KINDS}, got {self.kind!r}")
        if self.source not in SOURCES:
            raise ValueError(f"calibration source must be one of {SOURCES}, got {self.source!r}")
        if self.validation_status not in VALIDATION:
            raise ValueError(f"validation status must be one of {VALIDATION}")
        if self.geometry_id and self.kind != "efficiency":
            raise ValueError("only efficiency calibrations are bound to a geometry")
        self.params = [float(p) for p in self.params]
        if self.energy_range is not None:
            lo, hi = (float(v) for v in self.energy_range)
            self.energy_range = [lo, hi]

    # ------------------------------------------------------------ identity
    def scientific_content(self) -> dict:
        payload = {k: v for k, v in self.payload.items() if k not in _PAYLOAD_LABELS}
        return {"kind": self.kind, "model": self.model, "params": self.params, "cov": self.cov,
                "energy_range": self.energy_range, "detector_id": self.detector_id,
                "geometry_id": self.geometry_id, "payload": payload}

    @property
    def content_hash(self) -> str:
        return content_hash(self.scientific_content())

    def integrity_ok(self) -> bool:
        """False when a loaded record's content no longer matches the hash written with it."""
        return self.stored_hash is None or self.stored_hash == self.content_hash

    def set_validation(self, status: str, note: str = "") -> None:
        if status not in VALIDATION:
            raise ValueError(f"validation status must be one of {VALIDATION}")
        self.validation_status, self.validation_note = status, note

    # ------------------------------------------------------------ persistence
    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("stored_hash")
        d["content_hash"] = self.content_hash
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "CalibrationRecord":
        return from_known(cls, d, stored_hash=d.get("content_hash"))

    # ------------------------------------------------------------ builders
    @classmethod
    def from_efficiency_curve(cls, curve, detector_id: Optional[str] = None,
                              geometry_id: Optional[str] = None, source: str = "imported",
                              **kw) -> "CalibrationRecord":
        """Snapshot of an :class:`~spectramaster.analysis.efficiency.EfficiencyCurve`."""
        rng = [curve.e_min, curve.e_max] if curve.e_max > curve.e_min > 0 else None
        return cls(kind="efficiency", model=curve.model, params=list(curve.params),
                   cov=[list(r) for r in curve.cov] or None, energy_range=rng,
                   detector_id=detector_id, geometry_id=geometry_id, source=source,
                   payload=curve.to_dict(), name=kw.pop("name", curve.name), **kw)

    def to_efficiency_curve(self):
        from ..analysis.efficiency import EfficiencyCurve
        if self.kind != "efficiency":
            raise ValueError(f"{self.kind} calibration is not an efficiency curve")
        return EfficiencyCurve.from_dict(self.payload)

    @classmethod
    def from_spectrum(cls, spectrum, kind: str = "energy", detector_id: Optional[str] = None,
                      source: str = "imported", **kw) -> "CalibrationRecord":
        """Energy or FWHM polynomial (keV vs channel) as stored in a spectrum file."""
        coeffs = spectrum.energy_coeffs if kind == "energy" else spectrum.fwhm_coeffs if kind == "fwhm" else None
        if coeffs is None:
            raise ValueError("from_spectrum builds 'energy' or 'fwhm' records")
        if not coeffs:
            raise ValueError(f"the spectrum has no {kind} calibration")
        rng = None
        if spectrum.energy_coeffs and spectrum.counts:
            ends = [spectrum.energy_of(spectrum.first_channel),
                    spectrum.energy_of(spectrum.first_channel + len(spectrum.counts) - 1)]
            rng = [min(ends), max(ends)]
        payload = {"variable": "channel", "unit": "keV", "first_channel": spectrum.first_channel,
                   "num_channels": len(spectrum.counts)}
        return cls(kind=kind, model=f"poly{len(coeffs) - 1}_channel", params=list(coeffs),
                   energy_range=rng, detector_id=detector_id, source=source, payload=payload,
                   name=kw.pop("name", spectrum.sample_id), **kw)

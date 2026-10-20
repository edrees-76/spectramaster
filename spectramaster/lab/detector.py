"""Detector profiles and measurement geometries.

Design
------
* Every object has a stable ``id`` (uuid4) created once; names are labels only, so a
  renamed detector or geometry keeps its calibrations.
* Physical characteristics are ``Optional``: ``None`` means *unknown* and is never
  replaced by 0 or 1.  Lengths in mm, volumes in mL, density in g/cm3.
* Geometry equivalence is decided *conservatively* by
  :meth:`MeasurementGeometry.compatibility`: it returns the reasons why two geometries
  must not share an efficiency calibration.  An empty list is returned only when every
  quantity that matters for that kind of geometry is known on both sides and agrees.
  Equal nominal volume alone is never sufficient (a 1 L Marinelli and a 1 L bottle have
  very different efficiencies), and missing information yields an ``"unknown: ..."``
  reason instead of an implicit match.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from .common import from_known, new_id, opt_float, utc_now

DETECTOR_TYPES = ("HPGe", "NaI", "LaBr3", "CZT", "other")
GEOMETRY_KINDS = ("marinelli", "point", "cylinder", "filter", "other")


@dataclass
class DetectorProfile:
    name: str
    type: str = "HPGe"
    id: str = field(default_factory=new_id)
    relative_efficiency_pct: Optional[float] = None     # vs 3"x3" NaI at 1332 keV
    crystal_diameter_mm: Optional[float] = None
    crystal_length_mm: Optional[float] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    nominal_fwhm: list[list[float]] = field(default_factory=list)   # [[keV, FWHM keV], ...] (data sheet)
    energy_calibration_ids: list[str] = field(default_factory=list)
    fwhm_calibration_ids: list[str] = field(default_factory=list)
    efficiency_calibration_ids: list[str] = field(default_factory=list)
    note: str = ""
    # peak-shape calibration (low-energy tail, analysis.peaks.shape_calibration) measured on
    # calibration spectra of this detector: {"eta", "u_eta", "tau", "n_peaks", "energies_kev",
    # "note", "measured", "sources"}; empty = never measured (Gaussian peaks)
    peak_shape: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.type not in DETECTOR_TYPES:
            raise ValueError(f"detector type must be one of {DETECTOR_TYPES}, got {self.type!r}")
        for n in ("relative_efficiency_pct", "crystal_diameter_mm", "crystal_length_mm"):
            setattr(self, n, opt_float(getattr(self, n), n))
        self.nominal_fwhm = [[float(e), float(w)] for e, w in self.nominal_fwhm]

    def link_calibration(self, record) -> None:
        """Attach a :class:`CalibrationRecord` (by id) to the list of its kind."""
        ids = getattr(self, f"{record.kind}_calibration_ids")
        if record.id not in ids:
            ids.append(record.id)

    def set_peak_shape(self, cal: dict, sources=()) -> None:
        """Record a peak-shape calibration (:func:`~spectramaster.analysis.peaks.shape_calibration`)
        measured on the calibration spectra named in `sources`.  A result with eta = 0 is kept
        too: it documents that the detector's peaks were measured to be Gaussian."""
        keys = ("eta", "u_eta", "tau", "n_peaks", "energies_kev", "note")
        self.peak_shape = {**{k: cal.get(k) for k in keys}, "measured": utc_now(),
                           "sources": [str(s) for s in sources]}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DetectorProfile":
        return from_known(cls, d)


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _norm(v) -> str:
    return " ".join(str(v).lower().split())


@dataclass
class MeasurementGeometry:
    name: str
    kind: str = "other"
    id: str = field(default_factory=new_id)
    container_id: Optional[str] = None           # catalogue / type number of the container
    nominal_volume_ml: Optional[float] = None
    dimensions: dict = field(default_factory=dict)   # e.g. {"diameter_mm": 70.0, "height_mm": None}
    fill_height_mm: Optional[float] = None
    fill_volume_ml: Optional[float] = None       # actual filled volume
    matrix: Optional[str] = None                 # sample material ("soil", "water", "calibration resin" ...)
    density_g_cm3: Optional[float] = None
    arrangement: str = ""                        # e.g. "on end cap, centred", "spacer 2 cm"
    source_distance_mm: Optional[float] = None   # point source to end cap
    filter_shape: Optional[str] = None           # "circle", "rectangle", "folded" ...
    filter_dimensions: dict = field(default_factory=dict)
    filter_position: Optional[str] = None
    note: str = ""

    def __post_init__(self):
        if self.kind not in GEOMETRY_KINDS:
            raise ValueError(f"geometry kind must be one of {GEOMETRY_KINDS}, got {self.kind!r}")
        for n in ("nominal_volume_ml", "fill_height_mm", "fill_volume_ml", "density_g_cm3"):
            setattr(self, n, opt_float(getattr(self, n), n))
        # a point source may sit directly on the end cap: distance 0 is a real value
        self.source_distance_mm = opt_float(self.source_distance_mm, "source_distance_mm", positive=False)
        self.dimensions = {k: opt_float(v, k) for k, v in self.dimensions.items()}
        self.filter_dimensions = {k: opt_float(v, k) for k, v in self.filter_dimensions.items()}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MeasurementGeometry":
        return from_known(cls, d)

    # ------------------------------------------------------------ equivalence
    def compatibility(self, other: "MeasurementGeometry", density_rel_tol: float = 0.05,
                      fill_rel_tol: float = 0.03, dim_rel_tol: float = 0.02,
                      distance_tol_mm: float = 1.0) -> list[str]:
        """Reasons the two geometries must NOT be treated as equivalent ([] = equivalent).

        Reasons starting with ``"unknown:"`` mean the information needed to decide is
        missing on at least one side; they block equivalence just like real differences.
        """
        a, b = self, other
        out: list[str] = []

        def text(label, x, y, required=True):
            if _blank(x) and _blank(y):
                if required:
                    out.append(f"unknown: {label} not given for either geometry")
            elif _blank(x) or _blank(y):
                out.append(f"unknown: {label} missing for one geometry")
            elif _norm(x) != _norm(y):
                out.append(f"different {label}: {x!r} vs {y!r}")

        def num(label, x, y, rel=None, abs_=None, required=True):
            if x is None and y is None:
                if required:
                    out.append(f"unknown: {label} not given for either geometry")
            elif x is None or y is None:
                out.append(f"unknown: {label} missing for one geometry")
            else:
                tol = abs_ if abs_ is not None else rel * max(abs(x), abs(y))
                if abs(x - y) > tol:
                    out.append(f"different {label}: {x:g} vs {y:g}")

        def dims(label, da, db, required):
            if not da and not db:
                if required:
                    out.append(f"unknown: {label} not given for either geometry")
                return
            for k in sorted(set(da) | set(db)):
                num(f"{label} {k}", da.get(k), db.get(k), rel=dim_rel_tol)

        if a.kind != b.kind:
            return [f"different geometry kind: {a.kind} vs {b.kind}"]
        if a.kind == "other":
            out.append("unknown: geometry kind 'other' cannot be checked automatically")
        if a.kind in ("marinelli", "cylinder", "other"):
            text("container identifier", a.container_id, b.container_id)
            num("nominal volume (mL)", a.nominal_volume_ml, b.nominal_volume_ml, rel=fill_rel_tol,
                required=False)
            dims("container dimension", a.dimensions, b.dimensions, required=False)
            # fill level: actual volume preferred, else fill height; one of them is required
            if a.fill_volume_ml is not None or b.fill_volume_ml is not None:
                num("fill volume (mL)", a.fill_volume_ml, b.fill_volume_ml, rel=fill_rel_tol)
            elif a.fill_height_mm is not None or b.fill_height_mm is not None:
                num("fill height (mm)", a.fill_height_mm, b.fill_height_mm, rel=fill_rel_tol)
            else:
                out.append("unknown: fill level (volume or height) not given for either geometry")
            text("matrix", a.matrix, b.matrix)
            num("density (g/cm3)", a.density_g_cm3, b.density_g_cm3, rel=density_rel_tol)
        elif a.kind == "point":
            num("source distance (mm)", a.source_distance_mm, b.source_distance_mm, abs_=distance_tol_mm)
            text("source holder", a.container_id, b.container_id, required=False)
        elif a.kind == "filter":
            text("filter shape", a.filter_shape, b.filter_shape)
            dims("filter dimension", a.filter_dimensions, b.filter_dimensions, required=True)
            text("filter position", a.filter_position, b.filter_position)
            num("source distance (mm)", a.source_distance_mm, b.source_distance_mm, abs_=distance_tol_mm,
                required=False)
        text("arrangement", a.arrangement, b.arrangement, required=False)
        return out

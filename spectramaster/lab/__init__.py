"""Laboratory data models: detectors, geometries, calibrations, samples, analysis sessions.

Pure Python (no Qt).  All objects serialise to plain JSON-compatible dicts; sessions are
saved as ``spectramaster-session`` JSON documents with a schema version and migrations.

    from spectramaster.lab import (DetectorProfile, MeasurementGeometry, CalibrationRecord,
                                   SampleInfo, AnalysisSession)
"""
from __future__ import annotations

from .calibration import CalibrationRecord
from .detector import DETECTOR_TYPES, GEOMETRY_KINDS, DetectorProfile, MeasurementGeometry
from .history import EDIT_KINDS, EditHistory, EditOperation
from .sample import CONCENTRATION_UNITS, MATRIX_TYPES, SampleInfo
from .session import (ENGINE_VERSION, MIGRATIONS, SCHEMA_VERSION, AnalysisSession, SessionSchemaError,
                      SpectrumResolution, matches_to_dicts, migrate, peaks_to_dicts, quant_to_dict)

__all__ = [
    "AnalysisSession", "CalibrationRecord", "DetectorProfile", "EditHistory", "EditOperation",
    "MeasurementGeometry", "SampleInfo", "SessionSchemaError", "SpectrumResolution",
    "CONCENTRATION_UNITS", "DETECTOR_TYPES", "EDIT_KINDS", "ENGINE_VERSION", "GEOMETRY_KINDS",
    "MATRIX_TYPES", "MIGRATIONS", "SCHEMA_VERSION", "matches_to_dicts", "migrate", "peaks_to_dicts",
    "quant_to_dict",
]

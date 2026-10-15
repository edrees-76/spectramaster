"""Calibration-source certificates (the Aptec *Certificate* editor, CAL_EDIT.EXE).

A certificate lists the lines of a calibration source with the certified activity, its
uncertainty and the reference date.  It is stored as JSON in the user's certificate folder and
used to fill the activities of the efficiency-calibration points (Setup > Full Efficiency
Calibration > EditPoints > Load ROIs).  Pure data, no GUI imports.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

SCHEMA = 1


@dataclass
class CertificateLine:
    isotope: str
    energy: float                      # keV
    yield_: float = 0.0                # emission probability, fraction (0.851 for 85.1 %)
    half_life_s: Optional[float] = None
    activity: float = 0.0              # in Certificate.units, at Certificate.reference_time
    activity_err: float = 0.0          # 1 sigma percent


@dataclass
class Certificate:
    name: str
    units: str = "Bq"
    reference_time: Optional[datetime] = None
    source_id: str = ""
    note: str = ""
    lines: list[CertificateLine] = field(default_factory=list)

    def validate(self) -> "Certificate":
        if not self.name.strip():
            raise ValueError("the certificate needs a name")
        from .decay_calc import ACTIVITY_UNITS
        if self.units not in ACTIVITY_UNITS:
            raise ValueError(f"unknown activity unit {self.units!r}")
        for ln in self.lines:
            if not ln.isotope.strip() or not ln.energy or ln.energy <= 0:
                raise ValueError("every line needs an isotope and a positive energy")
            if ln.activity < 0 or ln.activity_err < 0 or not 0 <= ln.yield_ <= 1:
                raise ValueError(f"{ln.isotope} {ln.energy} keV: invalid activity, error or yield")
        return self

    def match(self, isotope: str, energy: float, tolerance_kev: float = 1.0) -> Optional[CertificateLine]:
        """The certificate line of ``isotope`` closest to ``energy`` (within the tolerance)."""
        iso = isotope.replace(" ", "").lower()
        best = None
        for ln in self.lines:
            if ln.isotope.replace(" ", "").lower() != iso or abs(ln.energy - energy) > tolerance_kev:
                continue
            if best is None or abs(ln.energy - energy) < abs(best.energy - energy):
                best = ln
        return best

    # ---------------------------------------------------------------- JSON
    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SCHEMA
        d["reference_time"] = self.reference_time.isoformat() if self.reference_time else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Certificate":
        t = d.get("reference_time")
        lines = [CertificateLine(**{k: v for k, v in ln.items() if k in CertificateLine.__dataclass_fields__})
                 for ln in d.get("lines", [])]
        return cls(name=d.get("name", ""), units=d.get("units", "Bq"),
                   reference_time=datetime.fromisoformat(t) if t else None, source_id=d.get("source_id", ""),
                   note=d.get("note", ""), lines=lines)

    def save(self, path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.validate().to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path) -> "Certificate":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def default_certificate_dir() -> Path:
    base = os.environ.get("SPECTRAMASTER_CERT_DIR")
    if base:
        return Path(base)
    root = Path(os.environ.get("APPDATA") or Path.home() / ".config")
    return root / "SpectraMaster" / "certificates"


def list_certificates(folder=None) -> list[Path]:
    folder = Path(folder or default_certificate_dir())
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


def safe_file_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name.strip()) or "certificate"


__all__ = ["Certificate", "CertificateLine", "default_certificate_dir", "list_certificates", "safe_file_name"]

"""Persistent registry of detector profiles (plan D5).  Plain Python, no Qt.

One JSON file per :class:`~spectramaster.lab.detector.DetectorProfile`, named by its permanent
``id`` (``<folder>/<id>.json``, ``"format": "spectramaster-detector-1"``): renaming a detector
changes its label only, so calibrations and sessions that refer to the id keep their link.
The folder follows the efficiency curves: environment variable ``SPECTRAMASTER_DETECTOR_DIR``
(tests), else ``%APPDATA%/SpectraMaster/detectors`` (``~/.spectramaster/detectors``).

Writes are atomic (temporary file + ``os.replace``).  Unreadable files are skipped and listed in
:attr:`DetectorRegistry.problems`, never deleted.  Deleting a profile removes its file only:
sessions and calibration records keep their own snapshot / id.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

from ..lab.common import to_plain
from ..lab.detector import DetectorProfile

FORMAT = "spectramaster-detector-1"
_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def default_detector_dir() -> Path:
    """User folder of detector profiles (env SPECTRAMASTER_DETECTOR_DIR overrides)."""
    env = os.environ.get("SPECTRAMASTER_DETECTOR_DIR")
    if env:
        return Path(env)
    base = os.environ.get("APPDATA")
    return (Path(base) / "SpectraMaster" / "detectors") if base else (Path.home() / ".spectramaster" / "detectors")


class DetectorRegistry:
    def __init__(self, root=None):
        self.root = Path(root) if root else default_detector_dir()
        self.problems: list[str] = []

    def path_for(self, detector_id: str) -> Path:
        if not isinstance(detector_id, str) or not _ID.match(detector_id):
            raise ValueError(f"invalid detector id {detector_id!r}")
        return self.root / f"{detector_id}.json"

    def _read(self, path: Path) -> DetectorProfile:
        d = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(d, dict) or d.get("format") != FORMAT:
            raise ValueError("not a detector profile")
        p = DetectorProfile.from_dict(d)
        if p.id != path.stem:
            raise ValueError(f"file name does not match the profile id {p.id!r}")
        return p

    def list(self) -> list[DetectorProfile]:
        """All readable profiles, sorted by name (unreadable files in :attr:`problems`)."""
        self.problems = []
        out = []
        if self.root.is_dir():
            for f in sorted(self.root.glob("*.json")):
                try:
                    out.append(self._read(f))
                except Exception as exc:
                    self.problems.append(f"{f.name}: {exc}")
        return sorted(out, key=lambda p: (p.name.casefold(), p.id))

    def get(self, detector_id: Optional[str]) -> Optional[DetectorProfile]:
        if not detector_id:
            return None
        try:
            f = self.path_for(detector_id)
        except ValueError:
            return None
        if not f.is_file():
            return None
        try:
            return self._read(f)
        except Exception:
            return None

    def save(self, profile: DetectorProfile) -> Path:
        """Create or replace the profile with ``profile.id`` (a name is required)."""
        if not (profile.name or "").strip():
            raise ValueError("a detector profile needs a name")
        path = self.path_for(profile.id)
        self.root.mkdir(parents=True, exist_ok=True)
        text = json.dumps(to_plain({"format": FORMAT, **profile.to_dict()}), indent=1, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        return path

    def delete(self, detector_id: str) -> bool:
        f = self.path_for(detector_id)
        if not f.is_file():
            return False
        f.unlink()
        return True


__all__ = ["DetectorRegistry", "default_detector_dir", "FORMAT"]

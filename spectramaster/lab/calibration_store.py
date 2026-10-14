"""Versioned calibration store: every saved calibration is kept, nothing is overwritten.  No Qt.

Layout (one folder per calibration lineage)::

    <root>/<lineage>/v001.json        immutable record of version 1 (CalibrationRecord.to_dict)
    <root>/<lineage>/v002.json        ...
    <root>/<lineage>/events.jsonl     append-only validation events {version, status, note, time, user}

* :meth:`CalibrationStore.save` writes a new version of a lineage (a new lineage when the
  record has none) with the reason for the change; the previous version is linked by
  ``supersedes``.  Saving content identical to the latest version (same ``content_hash``)
  creates no version.  Version files are created exclusively and never rewritten.
* Validation is an event, not an edit: :meth:`set_validation` appends to ``events.jsonl`` and
  the latest event of a version gives its status (validating does not change the science, so
  the content hash is unchanged).  A new version always starts ``unvalidated``.
* :meth:`load` checks each file against the hash written with it; a hand-edited file is
  reported by :meth:`integrity_problems` and is never returned as the current calibration.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .calibration import VALIDATION, CalibrationRecord
from .common import new_id, utc_now


class CalibrationStoreError(ValueError):
    pass


class CalibrationStore:
    def __init__(self, root):
        self.root = Path(root)

    # ------------------------------------------------------------ paths
    def _dir(self, lineage: str) -> Path:
        if not lineage or any(c in lineage for c in "/\\:") or lineage.startswith("."):
            raise CalibrationStoreError(f"invalid lineage {lineage!r}")
        return self.root / lineage

    @staticmethod
    def _vfile(d: Path, version: int) -> Path:
        return d / f"v{version:03d}.json"

    def lineages(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and any(p.glob("v*.json")))

    def _version_numbers(self, lineage: str) -> list[int]:
        d = self._dir(lineage)
        out = []
        for p in d.glob("v*.json"):
            try:
                out.append(int(p.stem[1:]))
            except ValueError:
                continue
        return sorted(out)

    # ------------------------------------------------------------ events
    def _events(self, lineage: str) -> list[dict]:
        f = self._dir(lineage) / "events.jsonl"
        if not f.is_file():
            return []
        return [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def set_validation(self, lineage: str, version: int, status: str, note: str = "", user: str = "") -> None:
        if status not in VALIDATION:
            raise CalibrationStoreError(f"validation status must be one of {VALIDATION}")
        if version not in self._version_numbers(lineage):
            raise CalibrationStoreError(f"{lineage}: no version {version}")
        if status == "validated" and not note.strip():
            raise CalibrationStoreError("state how the calibration was validated (note)")
        ev = {"version": version, "status": status, "note": note, "user": user, "time": utc_now()}
        with (self._dir(lineage) / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------ read
    def load(self, lineage: str, version: Optional[int] = None) -> CalibrationRecord:
        """Version `version` (default: the latest) with its current validation status."""
        nums = self._version_numbers(lineage)
        if not nums:
            raise CalibrationStoreError(f"no calibration {lineage!r} in {self.root}")
        v = nums[-1] if version is None else version
        if v not in nums:
            raise CalibrationStoreError(f"{lineage}: no version {v}")
        rec = CalibrationRecord.from_dict(json.loads(self._vfile(self._dir(lineage), v).read_text(encoding="utf-8")))
        rec.validation_status, rec.validation_note = "unvalidated", ""
        for ev in self._events(lineage):
            if ev.get("version") == v:
                rec.validation_status, rec.validation_note = ev["status"], ev.get("note", "")
        return rec

    def history(self, lineage: str) -> list[CalibrationRecord]:
        return [self.load(lineage, v) for v in self._version_numbers(lineage)]

    def current(self, lineage: str, validated_only: bool = False) -> Optional[CalibrationRecord]:
        """Latest intact version (latest validated one with `validated_only`); None if there is none."""
        for rec in reversed(self.history(lineage)):
            if not rec.integrity_ok():
                continue
            if validated_only and rec.validation_status != "validated":
                continue
            return rec
        return None

    def find(self, record_id: str) -> Optional[CalibrationRecord]:
        for lin in self.lineages():
            for rec in self.history(lin):
                if rec.id == record_id:
                    return rec
        return None

    def integrity_problems(self) -> list[str]:
        return [f"{lin} v{rec.version}: content does not match its stored hash (file edited outside the program)"
                for lin in self.lineages() for rec in self.history(lin) if not rec.integrity_ok()]

    # ------------------------------------------------------------ write
    def save(self, record: CalibrationRecord, reason: str) -> CalibrationRecord:
        """Store `record` as the next version of its lineage; returns the stored record.

        The caller's record is not modified.  `reason` (why this version exists) is required."""
        if not reason.strip():
            raise CalibrationStoreError("a reason for the new calibration version is required")
        lineage = record.lineage or new_id()
        d = self._dir(lineage)
        nums = self._version_numbers(lineage) if d.is_dir() else []
        prev = self.load(lineage, nums[-1]) if nums else None
        if prev is not None:
            if prev.kind != record.kind:
                raise CalibrationStoreError(f"{lineage} holds {prev.kind} calibrations, not {record.kind}")
            if prev.content_hash == record.content_hash:
                return prev                                    # nothing changed: no new version
        new = CalibrationRecord.from_dict(record.to_dict())
        new.stored_hash = None
        new.id = new_id() if (prev is not None and record.id == prev.id) or self.find(record.id) else record.id
        new.lineage = lineage
        new.version = (nums[-1] + 1) if nums else 1
        new.supersedes = prev.id if prev is not None else None
        new.change_reason = reason.strip()
        new.created = utc_now()
        new.validation_status, new.validation_note = "unvalidated", ""
        d.mkdir(parents=True, exist_ok=True)
        with self._vfile(d, new.version).open("x", encoding="utf-8") as fh:     # never overwrite
            json.dump(new.to_dict(), fh, indent=1, ensure_ascii=False)
        return new

    def diff(self, lineage: str, v_old: int, v_new: int) -> dict:
        """What changed between two versions (model, parameters, range, validation)."""
        a, b = self.load(lineage, v_old), self.load(lineage, v_new)
        out = {"from": v_old, "to": v_new, "reason": b.change_reason, "changes": []}
        for key in ("model", "energy_range", "detector_id", "geometry_id"):
            if getattr(a, key) != getattr(b, key):
                out["changes"].append(f"{key}: {getattr(a, key)!r} -> {getattr(b, key)!r}")
        if a.params != b.params:
            out["changes"].append(f"params: {a.params} -> {b.params}")
        if a.content_hash != b.content_hash and not out["changes"]:
            out["changes"].append("other scientific content (points, covariance, payload)")
        return out


__all__ = ["CalibrationStore", "CalibrationStoreError"]

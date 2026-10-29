"""Batch analysis grouped by compatible measurement conditions (Release F, F2).  No Qt.

1. :func:`scan` reads the spectra (several per file are kept apart) and :func:`group_items`
   groups them by the detector stated in the file (unlabelled files together), number of channels and
   energy calibration (agreement within ``energy_tol_kev`` over the whole range).
2. The user assigns a :class:`BatchSetup` (efficiency calibration, sample geometry,
   application library, nuclides, background) to each group explicitly.  **No calibration is
   applied to all files automatically**: a group without a setup is not analysed and is
   reported as such; a calibration of an incompatible geometry is refused per file (the
   activity engine's geometry guard), unless the setup explicitly allows the mismatch.
3. :func:`run_batch` analyses every assigned file (peaks, identification, activities and MDA)
   and :func:`write_csv` writes one row per file and nuclide with its status and notes.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

import numpy as np


@dataclass
class BatchItem:
    path: str
    index: int
    spectrum: object
    detector: str          # the file's detector label, "unlabelled detector" when it has none
    n_channels: int
    group: int = -1
    error: str = ""
    guess: str = ""        # detector type guessed from the data (information only)


@dataclass
class BatchGroup:
    id: int
    detector: str
    n_channels: int
    energy_coeffs: list
    items: list = field(default_factory=list)

    def describe(self) -> str:
        e = self.energy_coeffs
        cal = f"E = {e[0]:.3f} + {e[1]:.5f} ch" if len(e) >= 2 else "uncalibrated"
        return f"group {self.id}: {self.detector}, {self.n_channels} channels, {cal}, {len(self.items)} spectra"


@dataclass
class BatchSetup:
    curve: Optional[object] = None           # analysis.efficiency.EfficiencyCurve (None: identification only)
    geometry: Optional[object] = None        # lab.detector.MeasurementGeometry of the samples
    allow_geometry_mismatch: bool = False
    application: str = "environmental"
    nuclides: Sequence[str] = ()
    background: Optional[object] = None      # measured background spectrum (same detector)
    bkg_mode: str = "peak"


def scan(paths: Sequence, stop=None) -> list[BatchItem]:
    """The spectra of `paths`.  `stop()` True raises InterruptedError (the window closed)."""
    from ..analysis.peaks import guess_detector
    from ..convert import read_spectra
    items = []
    for p in paths:
        if stop is not None and stop():
            raise InterruptedError("scan cancelled")
        try:
            spectra = read_spectra(p)[0]
        except Exception as exc:                       # unreadable file: kept, with the reason
            items.append(BatchItem(str(p), 0, None, "", 0, error=f"{type(exc).__name__}: {exc}"))
            continue
        for i, s in enumerate(spectra):
            # group on what the file states: a type guessed from weak peaks is not reliable
            # enough to separate measurements of one detector
            label = (s.detector or "").strip() or (s.extra or {}).get("detector_type", "") or "unlabelled detector"
            items.append(BatchItem(str(p), i, s, label, len(s.counts), guess=guess_detector(s)))
    return items


def _same_calibration(a: Sequence[float], b: Sequence[float], n: int, tol_kev: float) -> bool:
    if not a or not b:
        return not a and not b
    ch = np.array([0.0, n / 2.0, float(n - 1)])
    ea = sum(c * ch ** k for k, c in enumerate(a))
    eb = sum(c * ch ** k for k, c in enumerate(b))
    return bool(np.max(np.abs(ea - eb)) <= tol_kev)


def group_items(items: Sequence[BatchItem], energy_tol_kev: float = 1.0) -> list[BatchGroup]:
    groups: list[BatchGroup] = []
    for it in items:
        if it.spectrum is None:
            continue
        coeffs = list(it.spectrum.energy_coeffs or [])
        g = next((g for g in groups if g.detector == it.detector and g.n_channels == it.n_channels
                  and _same_calibration(g.energy_coeffs, coeffs, it.n_channels, energy_tol_kev)), None)
        if g is None:
            g = BatchGroup(len(groups) + 1, it.detector, it.n_channels, coeffs)
            groups.append(g)
        g.items.append(it)
        it.group = g.id
    return groups


def run_batch(groups: Sequence[BatchGroup], setups: dict, progress=None) -> list[dict]:
    """Rows {file, index, group, sample_id, start, live_time, status, nuclide, identified,
    activity_bq, u_bq, mda_bq, decision, notes}; `setups` maps group id -> BatchSetup."""
    from ..analysis import find_peaks, identify
    from ..analysis.activity import ActivityOptions, compute_activities
    rows: list[dict] = []
    total = sum(len(g.items) for g in groups)
    done = 0
    for g in groups:
        setup = setups.get(g.id)
        for it in g.items:
            done += 1
            if progress:
                progress(done, total)
            base = {"file": it.path, "index": it.index, "group": g.id, "sample_id": it.spectrum.sample_id,
                    "start": it.spectrum.start_time.isoformat(sep=" ") if it.spectrum.start_time else "",
                    "live_time": it.spectrum.live_time}
            if setup is None:
                rows.append(base | {"status": "not analysed: no calibration and setup assigned to this group",
                                    "nuclide": "", "notes": ""})
                continue
            try:
                pk = find_peaks(it.spectrum)
                ids = identify(it.spectrum, pk, application=setup.application)
            except Exception as exc:
                rows.append(base | {"status": f"failed: {exc}", "nuclide": "", "notes": ""})
                continue
            found = {m.nuclide: m for m in ids}
            if setup.curve is None:
                for m in ids:
                    rows.append(base | {"status": "identified (no efficiency calibration)", "nuclide": m.nuclide,
                                        "identified": True, "notes": m.note})
                if not ids:
                    rows.append(base | {"status": "no nuclide identified", "nuclide": "", "notes": ""})
                continue
            names = list(setup.nuclides) or sorted(found)
            if not names:          # nothing identified and no nuclide asked for: still one row
                rows.append(base | {"status": "no nuclide identified", "nuclide": "", "notes": ""})
                continue
            try:
                q = compute_activities(it.spectrum, setup.curve,
                                       ActivityOptions(nuclides=names, geometry=setup.geometry,
                                                       allow_geometry_mismatch=setup.allow_geometry_mismatch,
                                                       bkg_mode=setup.bkg_mode),
                                       background=setup.background, peaks=pk if setup.background is None else None)
            except ValueError as exc:
                rows.append(base | {"status": f"refused: {exc}", "nuclide": "", "notes": ""})
                continue
            except Exception as exc:       # one bad file must not stop the batch
                rows.append(base | {"status": f"failed: {type(exc).__name__}: {exc}", "nuclide": "", "notes": ""})
                continue
            common = "; ".join(q.notes)
            for r in q.nuclides:
                rows.append(base | {"status": "analysed", "nuclide": r.nuclide, "identified": r.nuclide in found,
                                    "activity_bq": r.activity if r.detected else None,
                                    "u_bq": r.u if r.detected else None, "mda_bq": r.mda or None,
                                    "decision": r.decision, "notes": "; ".join(x for x in (r.note, common) if x)})
    return rows


CSV_KEYS = ["file", "index", "group", "sample_id", "start", "live_time", "status", "nuclide", "identified",
            "activity_bq", "u_bq", "mda_bq", "decision", "notes"]


def write_csv(path, rows: Sequence[dict]) -> Path:
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_KEYS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in CSV_KEYS})
    return path


__all__ = ["BatchItem", "BatchGroup", "BatchSetup", "scan", "group_items", "run_batch", "write_csv"]

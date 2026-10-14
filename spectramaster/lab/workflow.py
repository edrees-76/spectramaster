"""Laboratory workflow: visible statuses, review, and the traceable report record (Release F).
No Qt.

Workflow (plan, stage nine): open spectrum -> detector and geometry -> calibrations and
background -> analyse -> review peaks and nuclides -> activity and MDA -> report and session.

:func:`workflow_status` lists what stands between the session and a reportable result:

=========================  =======  ==========================================================
code                       level    meaning
=========================  =======  ==========================================================
calibration_required       error    no energy calibration / no efficiency calibration recorded
incompatible_calibration   error    efficiency calibration of another detector or geometry
outside_validated_scope    warning  unvalidated calibration, extrapolated efficiency, geometry
                                    or sample information not recorded
results_stale              warning  inputs changed after the results were computed
no_results                 info     nothing computed yet
not_reviewed               warning  automatic analysis not yet reviewed by a person
reviewed                   ok       reviewed (who, when, note)
=========================  =======  ==========================================================

:func:`report_record` gathers everything a report must trace (sample, spectrum fingerprint,
detector, geometry, calibrations with their versions and validation status, library,
background, results, statuses, edits, conventions, application version and session id) as a
plain dict; :func:`write_report_json` saves it.  Nothing is recalculated here.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from .common import to_plain, utc_now

LEVELS = ("error", "warning", "info", "ok")


@dataclass
class WorkflowStatus:
    code: str
    level: str
    message: str


def _efficiency_records(session) -> list[dict]:
    return [c for c in (session.calibrations or []) if c.get("kind") == "efficiency"]


def workflow_status(session, spectrum=None, needs_activity: bool = True) -> list[WorkflowStatus]:
    """Statuses of `session` (and of `spectrum`, the counts it refers to, when given)."""
    out: list[WorkflowStatus] = []
    add = lambda c, lv, m: out.append(WorkflowStatus(c, lv, m))
    if spectrum is not None and not spectrum.energy_coeffs:
        add("calibration_required", "error", "the spectrum has no energy calibration")
    effs = _efficiency_records(session)
    if needs_activity and not effs:
        add("calibration_required", "error", "no efficiency calibration recorded: activities cannot be reported")
    for rec in effs:
        name = rec.get("name") or rec.get("id", "?")
        if rec.get("detector_id") and session.detector_id and rec["detector_id"] != session.detector_id:
            add("incompatible_calibration", "error", f"efficiency calibration {name!r} belongs to another detector")
        geo_rec = (rec.get("payload") or {}).get("geometry_record") or {}
        if session.geometry and geo_rec:
            from .detector import MeasurementGeometry
            reasons = MeasurementGeometry.from_dict(geo_rec).compatibility(MeasurementGeometry.from_dict(session.geometry))
            if reasons:
                add("incompatible_calibration", "error",
                    f"efficiency calibration {name!r} belongs to another geometry: " + "; ".join(reasons))
        elif rec.get("geometry_id") and session.geometry_id and rec["geometry_id"] != session.geometry_id:
            add("incompatible_calibration", "error", f"efficiency calibration {name!r} belongs to another geometry")
        if rec.get("validation_status") != "validated":
            add("outside_validated_scope", "warning",
                f"efficiency calibration {name!r} is {rec.get('validation_status', 'unvalidated')}")
    if session.geometry is None:
        add("outside_validated_scope", "warning", "measurement geometry not recorded: compatibility not checked")
    if session.sample is None:
        add("outside_validated_scope", "warning", "sample information not recorded: no concentration")
    quant = (session.results or {}).get("quant") or {}
    extrap = sorted({ln.get("energy") for r in quant.get("nuclides", []) for ln in r.get("lines", [])
                     if "extrapolated" in (ln.get("note") or "")} - {None})
    if extrap:
        add("outside_validated_scope", "warning",
            "efficiency extrapolated at " + ", ".join(f"{e:.1f}" for e in extrap) + " keV")
    if not session.has_results():
        add("no_results", "info", "no results computed yet")
        return out
    if session.status.get("results_stale"):
        add("results_stale", "warning", "results require recalculation: "
            + "; ".join(session.status.get("stale_reasons") or ["inputs changed"]))
    if session.status.get("reviewed"):
        rv = session.status.get("review") or {}
        add("reviewed", "ok", f"reviewed by {rv.get('reviewer', '?')} on {rv.get('time', '?')}"
            + (f": {rv['note']}" if rv.get("note") else ""))
    else:
        add("not_reviewed", "warning", "automatic analysis not yet reviewed")
    return out


def mark_reviewed(session, reviewer: str, note: str = "") -> None:
    """Record that a person reviewed the current results (refused while they are stale)."""
    if not reviewer.strip():
        raise ValueError("the reviewer's name is required")
    if not session.has_results():
        raise ValueError("there are no results to review")
    if session.status.get("results_stale"):
        raise ValueError("the results require recalculation before they can be reviewed")
    session.status["reviewed"] = True
    session.status["review"] = {"reviewer": reviewer.strip(), "time": utc_now(), "note": note}
    session.touch()


def report_record(session, concentrations: Optional[dict] = None, spectrum=None) -> dict:
    """Everything a report traces, as a plain dict (see the module docstring)."""
    quant = (session.results or {}).get("quant") or {}
    opts = quant.get("options") or {}
    statuses = [asdict(s) for s in workflow_status(session, spectrum, needs_activity=bool(quant))]
    cal = []
    for c in session.calibrations or []:
        payload = c.get("payload") or {}
        cal.append({k: c.get(k) for k in ("id", "kind", "name", "model", "source", "validation_status",
                                          "validation_note", "energy_range", "detector_id", "geometry_id",
                                          "content_hash", "created")}
                   | {"selection": payload.get("selection"), "u_model_rel": payload.get("u_model_rel")})
    edits = [{"kind": op.kind, "target": op.target, "reason": op.reason, "user": op.user,
              "time": op.timestamp, "undone": op.undone}
             for op in getattr(session.history, "ops", [])]
    return to_plain({
        "format": "spectramaster-report-1",
        "generated": utc_now(),
        "application": {"app_version": session.app_version, "engine_version": session.engine_version,
                        "session_id": session.session_id, "session_modified": session.modified},
        "spectrum": session.spectrum_ref,
        "sample": session.sample,
        "detector": session.detector,
        "geometry": session.geometry,
        "calibrations": cal,
        "library": session.library_ref,
        "background": session.background_ref,
        "processing_settings": session.processing_settings,
        "statuses": statuses,
        "reportable": not any(s["level"] == "error" for s in statuses),
        "results": {
            "peaks": (session.results or {}).get("peaks", []),
            "nuclides": (session.results or {}).get("nuclide_matches", []),
            "activities": quant.get("nuclides", []),
            "notes": quant.get("notes", []),
            "concentrations": concentrations,
        },
        "conventions": {
            "time_reference": quant.get("ref_date") or "acquisition start",
            "uncertainty": "standard uncertainty u (k = 1); expanded U = 2u (k = 2) where stated",
            "detection_limits": opts.get("mda_method", "currie"),
            "non_detects": "reported as '< MDA', never as zero",
            "weight_basis": (session.sample or {}).get("mass_basis"),
        },
        "edits": edits,
    })


def write_report_json(path, session, concentrations: Optional[dict] = None, spectrum=None) -> Path:
    path = Path(path)
    path.write_text(json.dumps(report_record(session, concentrations, spectrum), indent=1, ensure_ascii=False),
                    encoding="utf-8")
    return path


__all__ = ["WorkflowStatus", "workflow_status", "mark_reviewed", "report_record", "write_report_json", "LEVELS"]

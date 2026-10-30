"""Analysis session: everything needed to reopen, audit and reproduce one spectrum analysis.

Design
------
* A session is a JSON document (``"format": "spectramaster-session"``) holding plain
  data only.  The spectrum file is *referenced* (path, SHA-256 of the bytes, size,
  format, index in a multi-spectrum file, plus a format-independent fingerprint of the
  counts); it is opened read-only for hashing and never modified or copied.
* Detector, geometry, sample and calibrations are stored as full snapshots (calibrations
  with their content hash), the nuclide library and background by path + SHA-256.  A
  later change of any of them therefore cannot silently alter stored results:
  :meth:`AnalysisSession.is_stale_against` reports the differences and the caller
  decides whether to recalculate.  Displaying stored results and recalculating them with
  a newer engine are distinct actions; this module never recalculates.
* Results are plain dicts (``dataclasses.asdict`` of ``Peak`` / ``QuantResults``).  A
  ``NuclideMatch`` refers to its peaks by *index* into ``results["peaks"]``
  (``matched = [[library keV, peak index], ...]``) instead of duplicating them.
* Manual edits go through :class:`~spectramaster.lab.history.EditHistory` (undo/redo,
  reasons, timestamps); edits to peaks, settings, sample or context mark the results
  stale.
* Persistence: atomic write (temporary file + ``os.replace``).  Documents carry
  ``schema_version``; older documents are upgraded step by step with :data:`MIGRATIONS`,
  newer ones are rejected with :class:`SessionSchemaError`.

Schema version 0 (legacy, documented for the migration mechanism) is a minimal dict
without ``format``::

    {"spectrum_path": str, "peaks": [peak dict, ...], "settings": {...}}  # optional "sample_id"
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from .. import __version__
from .calibration import CalibrationRecord
from .common import counts_fingerprint, file_sha256, new_id, to_plain, utc_now
from .history import EditHistory, EditOperation
from .sample import SampleInfo

FORMAT = "spectramaster-session"
SCHEMA_VERSION = 1
# Version of the numerical analysis engine (peak search, fitting, quantification), separate
# from the application version: bump it whenever results can change, so that sessions computed
# with an older engine are reported (``is_stale_against``).
#   1.0.0  first release
#   1.1.0  2026-10-20 second external review: ISO 11929 solver, blank and reference
#          uncertainties, TCS safety, curvature fit windows, width-shape extrapolation
#   1.2.0  2026-10-21 peak-mode background fitted on S - kB (PR #35, which did not bump it);
#          gamma-line library: wrong, duplicated and lost lines (library_lines_protocol.md)
#   1.3.0  2026-10-21 reference peak measured on the gross spectrum with a background; decision
#          threshold with blank and reference peaks; manual peak edits used (combined_corrections_protocol.md)
#   1.4.0  2026-10-21 summing correction: daughter cascades, unestimable partners, calibration refit to
#          convergence, curves without points refused (tcs_fixes_protocol.md)
#   1.5.0  2026-10-21 efficiency points with a background fitted on S - kB; non-Poisson
#          spectra reported (efficiency_poisson_protocol.md)
#   1.6.0  2026-10-21 efficiency model error: outliers limited at 3 x the curve's scatter
#          (model_error_outlier_protocol.md)
#   1.7.0  2026-10-21 signed primary result for lines without a search peak (window estimator),
#          ISO 11929 best estimate for every nuclide, decision rule option (signed_primary_protocol.md)
#   1.8.0  2026-10-21 511 keV annihilation summing of beta+ emitters in the true-coincidence correction
#          (annihilation_summing_protocol.md)
#   1.9.0  2026-10-21 quadratic continuum with its own decision threshold for window results whose
#          linear continuum is too curved (NaI) (window_polynomial_protocol.md)
#   1.10.0 2026-10-22 an FWHM model (stored calibration or default resolution) that does not match
#          the peak widths of the spectrum is replaced by measured widths, with a note
#          (fwhm_plausibility_protocol.md)
#   1.11.0 2026-10-22 energy-dependent self-attenuation correction for a sample density or matrix
#          different from the calibration (slab model, NIST mu/rho) (self_attenuation_protocol.md)
#   1.12.0 2026-10-22 summing_free_curve chooses an automatically chosen efficiency model (orders,
#          crossover) again on the summing-corrected points (close_geometry_efficiency_protocol.md)
#   1.13.0 2026-10-22 FWHM calibration from a source fitted through measured (free-width) line widths,
#          not the search's width model (mix_peak_areas_protocol.md)
#   1.14.0 2026-10-22 coincidence table computed from the ENSDF decay schemes (IAEA LiveChart) instead
#          of SandiaDecay, whose probabilities were wrong for 80 of 191 transitions
#          (ensdf_coincidence_protocol.md)
#   1.15.0 2026-10-23 round-4 review (round4_activity_protocol.md): ISO 11929 detection limit with the
#          reference-peak term linear in the activity (blank + reference peak); coincidence summing of a
#          self-attenuating sample with its own efficiency; best estimate of nuclides not detected in the
#          concentration table; constant attenuation together with the self-attenuation model refused
#   1.16.0 2026-10-27 round-4 review (round4_identify_protocol.md): identification FWHM at the absolute
#          channel; low plausibility for nuclides decayed by > 10 half-lives since sampling; medical
#          nuclides common only with the medical library; note on single matched lines
#   1.17.0 2026-10-27 round-4 review (round4_formats_protocol.md): peak search refuses non-finite
#          channel contents; EML/Sanderson time channels only with a possible real time
#   1.18.0 2026-10-27 round-4 review (round4_calibration_protocol.md): source FWHM calibration
#          positive and not decreasing; manual fit of a net spectrum with its variance
#   1.19.0 2026-10-27 round-4 review (round4_primary_protocol.md): signed primary result of a nuclide
#          not detected combined like the activity; an unusable key line replaced by a usable line
#   1.20.0 2026-10-27 detector acceptance test (FWHM, FWTM, peak-to-Compton, relative efficiency) and
#          chi-square counting test (detector_acceptance_protocol.md and its amendment)
#   1.21.0 2026-10-27 coincidence correction: upward probabilities from the scheme intensities at ENSDF
#          levels that receive more than they emit (ensdf_level_balance_protocol.md)
#   1.22.0 2026-10-28 round-5 review (round5_acceptance_protocol.md): detector acceptance test at the
#          absolute channel (first_channel), peak-to-Compton only with the whole 1040-1096 keV window
#   1.23.0 2026-10-28 weighted mean of lines: decision threshold and detection limit of the mean with
#          its own weights (round5_combined_protocol.md)
#   1.24.0 2026-10-28 true-coincidence summing: partial state (partners below the curve, scheme
#          intensities inconsistent); partial calibration points refused (round5_tcs_protocol.md)
#   1.25.0 2026-10-28 weighted mean of lines with a blank: covariance of the shared reference peak
#          corrections in its decision threshold and detection limit (round6_combined_protocol.md)
#   1.26.0 2026-10-28 partial true-coincidence summing state of the efficiency curve kept with it and
#          carried to the results, the report and the review (round6_tcs_state_protocol.md)
#   1.27.0 2026-10-29 summing state of an efficiency curve kept through a refit, from its points; corrected
#          and uncorrected cascade points not fitted together (round7_tcs_refit_protocol.md)
#   1.28.0 2026-10-29 limits of the weighted mean: reference peak cross terms also with a blank peak on one
#          line only; an undetected nuclide (mean) gets the limits of its weighted mean (round7_combined_protocol.md)
#   1.29.0 2026-10-29 background spectrum shared by the sample and its reagent blank: covariance of
#          their background estimates; the sample's counting of the blank level in sigma0
#          (round7_shared_background_protocol.md)
#   1.30.0 2026-10-29 a line on the quadratic window reports that window's decision threshold and MDA,
#          and its nuclide inherits them (round7_quad_limits_protocol.md)
#   1.31.0 2026-10-30 a nuclide not detected whose primary result comes from another line than its key line
#          reports that line's decision threshold and MDA (round8_alt_limits_protocol.md)
#   1.32.0 2026-10-30 peak background mode: the limits of a line without a sample peak use the window
#          estimator of its primary result on the background (round8_peak_mode_protocol.md)
#   1.33.0 2026-10-30 calibration points already corrected for true-coincidence summing on a curve not
#          marked corrected are refitted as they are, not corrected twice (round8_coi_guard_protocol.md)
#   1.34.0 2026-10-30 weighted mean of a nuclide's window results: the covariance of lines whose windows
#          share channels, and the reference peak components summed before the norm
#          (round8_line_covariance_protocol.md)
ENGINE_VERSION = "1.34.0"


class SessionSchemaError(ValueError):
    """The document is not a session this version can read."""


# ------------------------------------------------------------------ result conversion


def peaks_to_dicts(peaks) -> list[dict]:
    return [to_plain(asdict(p)) for p in peaks]


def matches_to_dicts(matches, peaks) -> list[dict]:
    """NuclideMatch list -> dicts; matched peaks become indices into `peaks`."""
    index = {id(p): i for i, p in enumerate(peaks)}
    out = []
    for m in matches:
        d = {k: to_plain(getattr(m, k)) for k in m.__dataclass_fields__ if k != "matched"}
        refs = []
        for e, p in m.matched:
            i = index.get(id(p))
            if i is None:      # an equal copy of a listed peak
                i = next((j for j, q in enumerate(peaks) if q == p), None)
            if i is None:
                raise ValueError(f"{m.nuclide}: matched peak at {p.energy} keV is not in the peak list")
            refs.append([float(e), i])
        d["matched"] = refs
        out.append(d)
    return out


def quant_to_dict(quant) -> Optional[dict]:
    return None if quant is None else to_plain(asdict(quant))


@dataclass
class SpectrumResolution:
    status: str        # "ok" | "relocated" | "modified" | "missing"
    path: str
    message: str


def _file_ref(path, **extra) -> dict:
    p = Path(path)
    return {"path": str(p), "sha256": file_sha256(p), "size": p.stat().st_size, **extra}


def default_library_path() -> Path:
    return Path(__file__).resolve().parent.parent / "analysis" / "data" / "gamma_library.json"


# ------------------------------------------------------------------ session


@dataclass
class AnalysisSession:
    spectrum_ref: dict = field(default_factory=dict)
    session_id: str = field(default_factory=new_id)
    created: str = field(default_factory=utc_now)
    modified: str = ""
    app_version: str = __version__
    engine_version: str = ENGINE_VERSION
    sample: Optional[dict] = None
    detector: Optional[dict] = None
    geometry: Optional[dict] = None
    calibrations: list[dict] = field(default_factory=list)
    library_ref: Optional[dict] = None
    background_ref: Optional[dict] = None
    blank_ref: Optional[dict] = None          # reagent blank spectrum of the activities
    coincidence_ref: Optional[dict] = None    # coincidence table of a TCS correction
    processing_settings: dict = field(default_factory=dict)
    results: dict = field(default_factory=lambda: {"peaks": [], "nuclide_matches": [], "quant": None})
    status: dict = field(default_factory=lambda: {"results_stale": False, "stale_reasons": [],
                                                  "reviewed": False, "engine_version_at_results": None})
    note: str = ""
    history: EditHistory = field(default_factory=EditHistory)

    def __post_init__(self):
        self.modified = self.modified or self.created

    # ------------------------------------------------------------ construction
    @classmethod
    def for_spectrum(cls, path, spectrum=None, index: int = 0, fmt: str = "", **kw) -> "AnalysisSession":
        """New session referencing the spectrum file `path` (read only, for hashing)."""
        ref = _file_ref(Path(path).resolve(), format=fmt or (spectrum.source_format if spectrum else ""),
                        index=int(index),
                        counts_sha256=counts_fingerprint(spectrum.counts) if spectrum is not None else None)
        return cls(spectrum_ref=ref, **kw)

    def touch(self) -> None:
        self.modified = utc_now()

    # ------------------------------------------------------------ ids of the snapshots
    @property
    def detector_id(self) -> Optional[str]:
        return self.detector.get("id") if self.detector else None

    @property
    def geometry_id(self) -> Optional[str]:
        return self.geometry.get("id") if self.geometry else None

    def calibration_snapshot(self, cal_id: str) -> Optional[dict]:
        return next((c for c in self.calibrations if c.get("id") == cal_id), None)

    # ------------------------------------------------------------ status
    def mark_stale(self, reason: str) -> None:
        """Downstream results require an update (only meaningful when results exist)."""
        if not self.has_results():
            return
        self.status["results_stale"] = True
        if reason not in self.status["stale_reasons"]:
            self.status["stale_reasons"].append(reason)
        self.status["reviewed"] = False

    def has_results(self) -> bool:
        r = self.results
        return bool(r.get("peaks") or r.get("nuclide_matches") or r.get("quant"))

    def set_results(self, peaks=(), matches=(), quant=None, engine_version: str = ENGINE_VERSION,
                    spectrum=None, peaks_edited: bool = False) -> None:
        """Store freshly computed results (dataclass objects or already-plain dicts).

        Recomputation replaces the list positions recorded by earlier edits, so the undo
        and redo stacks are sealed (the log itself is kept).  ``peaks_edited``: the peaks
        carry manual edits (kept when only the activities are recomputed).
        """
        peaks = list(peaks)
        plain = peaks and not isinstance(peaks[0], dict)
        self.results = {
            "peaks": peaks_to_dicts(peaks) if plain else copy.deepcopy(peaks),
            "nuclide_matches": (matches_to_dicts(matches, peaks) if plain and matches
                                else copy.deepcopy(list(matches))),
            "quant": quant if quant is None or isinstance(quant, dict) else quant_to_dict(quant)}
        self.status = {"results_stale": False, "stale_reasons": [], "reviewed": False,
                       "engine_version_at_results": engine_version, "peaks_edited": bool(peaks_edited)}
        if spectrum is not None:      # lets later manual refits check they use the same counts
            from ..analysis.manual import counts_sha256
            self.processing_settings = {**(self.processing_settings or {}),
                                        "counts_sha256": counts_sha256(spectrum)}
        self.history.seal()
        self.touch()

    def is_stale_against(self, current_engine_version: str = ENGINE_VERSION,
                         calibrations_by_id: Optional[dict] = None) -> list[str]:
        """Why the stored results may no longer correspond to the current inputs.

        `calibrations_by_id` maps id -> current CalibrationRecord (or its dict).  Snapshots
        whose id is absent from the mapping are not judged.  Nothing is recalculated.
        """
        if not self.has_results():
            return []
        out = list(self.status.get("stale_reasons", [])) if self.status.get("results_stale") else []
        ev = self.status.get("engine_version_at_results")
        if ev is None:
            out.append("results were not produced by a recorded engine version")
        elif ev != current_engine_version:
            out.append(f"results produced by engine {ev}, current engine is {current_engine_version}")
        for snap in self.calibrations:
            cur = (calibrations_by_id or {}).get(snap.get("id"))
            if cur is None:
                continue
            cur_hash = cur.content_hash if isinstance(cur, CalibrationRecord) else \
                CalibrationRecord.from_dict(cur).content_hash
            if cur_hash != snap.get("content_hash"):
                out.append(f"{snap.get('kind')} calibration {snap.get('name') or snap.get('id')} "
                           f"changed since the results were produced")
        return out

    # ------------------------------------------------------------ edits (undoable)
    def edit(self, kind: str, target: list, after=None, reason: str = "", user: Optional[str] = None,
             details: Optional[dict] = None) -> EditOperation:
        kw = {"user": user} if user is not None else {}
        op = self.history.do(EditOperation(kind, list(target), after=to_plain(after), reason=reason,
                                           details=to_plain(details) if details else None, **kw), self)
        self.touch()
        return op

    # ------------------------------------------------------------ manual refits (B3)
    def _check_counts(self, spectrum) -> None:
        from ..analysis.manual import counts_sha256
        want = (self.processing_settings or {}).get("counts_sha256")
        if want and want != counts_sha256(spectrum):
            raise ValueError("the spectrum passed is not the one these results were computed from")

    def refit_region(self, spectrum, lo: int, hi: int, centroids, reason: str = "", **options):
        """Refit channels lo..hi with peaks at `centroids` and replace the stored peaks of that
        region (undoable).  Identification and activity are marked as requiring an update.
        A ``variance=`` option (net spectrum) is passed to the fit; the edit records its SHA-256,
        not the array.  Returns (EditOperation, RegionFit)."""
        from ..analysis.manual import refit_region
        self._check_counts(spectrum)
        rf = refit_region(spectrum, lo, hi, centroids, **options)
        if not rf.ok:
            raise ValueError("the fit did not converge; nothing was changed")
        lo_, hi_ = rf.options["lo"], rf.options["hi"]
        keep = [p for p in self.results["peaks"] if not lo_ <= p["centroid"] <= hi_]
        new = sorted(keep + peaks_to_dicts(rf.peaks), key=lambda p: p["centroid"])
        op = self.edit("replace_peaks", ["results", "peaks"], new,
                       reason or f"manual refit of channels {lo_}-{hi_}", details=rf.options)
        return op, rf

    def add_peak_and_refit(self, spectrum, channel: float, reason: str = "", **options):
        """Add a peak at `channel` and refit it together with its neighbours."""
        from ..analysis.manual import region_around
        from ..analysis.peaks import width_model
        import numpy as np
        var = options.get("variance")
        y = np.asarray(spectrum.counts, dtype=float)
        if var is None:
            y = np.maximum(y, 0.0)
        else:
            var = np.maximum(np.asarray(var, dtype=float), 0.0)
        f, _src, _ = width_model(spectrum, y, var=var)
        i = int(min(max(round(channel - spectrum.first_channel), 0), len(y) - 1))
        lo, hi, others = region_around(self.results["peaks"], float(channel), float(f[i]))
        return self.refit_region(spectrum, lo, hi, others + [float(channel)],
                                 reason or f"peak added at channel {channel:.1f}", **options)

    def remove_peak_and_refit(self, spectrum, index: int, reason: str, **options):
        """Remove stored peak `index` and refit its remaining neighbours (reason required)."""
        from ..analysis.manual import region_around
        if not reason.strip():
            raise ValueError("a reason is required to remove a peak")
        peaks = self.results["peaks"]
        gone = peaks[int(index)]
        c = float(gone["centroid"])
        lo, hi, others = region_around(peaks, c, float(gone.get("fwhm") or 1.0))
        if not others:            # isolated peak: nothing to refit
            return self.edit("replace_peaks", ["results", "peaks"],
                             [p for k, p in enumerate(peaks) if k != int(index)], reason,
                             details={"removed_centroid": c}), None
        return self.refit_region(spectrum, lo, hi, others, reason, **options)

    def add_peak(self, peak, index: Optional[int] = None, reason: str = "") -> EditOperation:
        d = peak if isinstance(peak, dict) else to_plain(asdict(peak))
        i = len(self.results["peaks"]) if index is None else int(index)
        return self.edit("add_peak", ["results", "peaks", i], d, reason)

    def remove_peak(self, index: int, reason: str) -> EditOperation:
        return self.edit("remove_peak", ["results", "peaks", int(index)], reason=reason)

    def set_peak_field(self, index: int, name: str, value, reason: str) -> EditOperation:
        return self.edit("set_peak_field", ["results", "peaks", int(index), name], value, reason)

    def set_sample_field(self, name: str, value, reason: str = "") -> EditOperation:
        if self.sample is None:
            raise ValueError("the session has no sample information yet (use set_sample)")
        if name not in SampleInfo.__dataclass_fields__:
            raise KeyError(f"unknown sample field {name!r}")
        value = getattr(SampleInfo.from_dict({**self.sample, name: value}), name)   # validated
        return self.edit("set_sample_field", ["sample", name], value, reason)

    def set_setting(self, key: str, value, reason: str = "") -> EditOperation:
        return self.edit("set_setting", ["processing_settings", key], value, reason)

    def set_sample(self, sample, reason: str = "") -> EditOperation:
        return self.edit("set_context", ["sample"], sample.to_dict(), reason)

    def set_detector(self, detector, reason: str = "") -> EditOperation:
        return self.edit("set_context", ["detector"], detector.to_dict(), reason)

    def set_geometry(self, geometry, reason: str = "") -> EditOperation:
        return self.edit("set_context", ["geometry"], geometry.to_dict(), reason)

    def set_calibration(self, record: CalibrationRecord, reason: str = "") -> EditOperation:
        """Add (or replace by id) the snapshot of a calibration record."""
        cals = [c for c in self.calibrations if c.get("id") != record.id] + [record.to_dict()]
        return self.edit("set_context", ["calibrations"], cals, reason)

    def set_library(self, path=None, note: str = "", reason: str = "") -> EditOperation:
        """Reference the nuclide library file (default: the bundled one); `note` = user changes."""
        return self.edit("set_context", ["library_ref"],
                         _file_ref(path or default_library_path(), note=note), reason)

    def set_background(self, path, live_time: Optional[float] = None, scaling: Optional[float] = None,
                       reason: str = "") -> EditOperation:
        return self.edit("set_context", ["background_ref"],
                         _file_ref(path, live_time=live_time, scaling=scaling), reason)

    def set_blank(self, path, live_time: Optional[float] = None, reason: str = "") -> EditOperation:
        """Reference the reagent blank spectrum file (None: no blank correction)."""
        ref = _file_ref(path, live_time=live_time) if path else None
        return self.edit("set_context", ["blank_ref"], ref, reason)

    def set_coincidence_table(self, path=None, reason: str = "") -> EditOperation:
        """Reference the coincidence table of a TCS correction (default: the bundled one)."""
        if path is None:
            from ..analysis.coincidence import TABLE
            path = TABLE
        return self.edit("set_context", ["coincidence_ref"], _file_ref(path), reason)

    def undo(self) -> Optional[EditOperation]:
        op = self.history.undo(self)
        if op:
            self.touch()
        return op

    def redo(self) -> Optional[EditOperation]:
        op = self.history.redo(self)
        if op:
            self.touch()
        return op

    # ------------------------------------------------------------ spectrum file
    def resolve_spectrum(self, search_dirs: Iterable = (), recursive: bool = True) -> SpectrumResolution:
        """Check the referenced spectrum file; look for a moved copy in `search_dirs`.

        ``ok`` - same path, same bytes.  ``modified`` - the path exists but its SHA-256
        differs (never accepted silently).  ``relocated`` - not at the stored path but a
        file with the same size and SHA-256 was found; the path is updated through an
        undoable ``relocate_spectrum`` edit.  ``missing`` - nothing found.
        """
        ref = self.spectrum_ref
        p = Path(ref["path"])
        if p.is_file():
            if file_sha256(p) == ref["sha256"]:
                return SpectrumResolution("ok", str(p), "spectrum file found and unchanged")
            return SpectrumResolution("modified", str(p), "the file at the stored path has different "
                                      "content (SHA-256 mismatch); results may not belong to it")
        name, size = p.name.lower(), ref.get("size")
        cands: list[Path] = []
        for d in search_dirs:
            d = Path(d)
            if d.is_dir():
                cands += [f for f in (d.rglob("*") if recursive else d.iterdir()) if f.is_file()]
        cands.sort(key=lambda f: f.name.lower() != name)        # same file name first
        for f in cands:
            if (size is None or f.stat().st_size == size) and file_sha256(f) == ref["sha256"]:
                new = str(f.resolve())
                self.edit("relocate_spectrum", ["spectrum_ref", "path"], new,
                          reason=f"not found at {p}; identical file (SHA-256) found at {new}")
                return SpectrumResolution("relocated", new, f"spectrum file relocated to {new}")
        return SpectrumResolution("missing", str(p), "spectrum file not found")

    # ------------------------------------------------------------ persistence
    def to_dict(self) -> dict:
        d = {"format": FORMAT, "schema_version": SCHEMA_VERSION}
        for k in self.__dataclass_fields__:
            v = getattr(self, k)
            d[k] = v.to_dict() if k == "history" else copy.deepcopy(v)
        d["detector_id"], d["geometry_id"] = self.detector_id, self.geometry_id
        d["sample_id"] = self.sample.get("sample_id") if self.sample else None
        return to_plain(d)

    def state_dict(self) -> dict:
        """to_dict() without history and modification time (for state comparisons)."""
        d = self.to_dict()
        d.pop("history"), d.pop("modified")
        return d

    @classmethod
    def from_dict(cls, doc: dict) -> "AnalysisSession":
        doc = migrate(doc)
        kw = {k: copy.deepcopy(doc[k]) for k in cls.__dataclass_fields__ if k in doc and k != "history"}
        return cls(history=EditHistory.from_dict(doc.get("history")), **kw)

    def save(self, path) -> Path:
        """Atomic JSON write; refuses to overwrite the referenced spectrum file."""
        path = Path(path).resolve()
        if self.spectrum_ref.get("path") and path == Path(self.spectrum_ref["path"]).resolve():
            raise ValueError("refusing to write the session over the spectrum file")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.touch()
        text = json.dumps(to_plain(self.to_dict()), indent=1, ensure_ascii=False, allow_nan=False)
        fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        return path

    @classmethod
    def load(cls, path) -> "AnalysisSession":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# ------------------------------------------------------------------ schema migration


def _migrate_0_to_1(doc: dict) -> dict:
    now = utc_now()
    p = doc.get("spectrum_path", "")
    return {"format": FORMAT, "schema_version": 1, "session_id": new_id(), "created": now,
            "modified": now, "app_version": "unknown", "engine_version": "unknown",
            "spectrum_ref": {"path": p, "sha256": None, "size": None, "format": "", "index": 0,
                             "counts_sha256": None},
            "sample": ({"sample_id": doc["sample_id"]} if doc.get("sample_id") else None),
            "processing_settings": dict(doc.get("settings", {})),
            "results": {"peaks": list(doc.get("peaks", [])), "nuclide_matches": [], "quant": None},
            "status": {"results_stale": bool(doc.get("peaks")), "reviewed": False,
                       "engine_version_at_results": None,
                       "stale_reasons": ["migrated from a legacy (version 0) session"] if doc.get("peaks") else []},
            "history": {"ops": [], "undo_stack": [], "redo_stack": []}}


MIGRATIONS: dict[int, Callable[[dict], dict]] = {0: _migrate_0_to_1}


def migrate(doc: dict) -> dict:
    """Upgrade a session document to :data:`SCHEMA_VERSION` (returns a new dict)."""
    if not isinstance(doc, dict):
        raise SessionSchemaError("a session document must be a JSON object")
    if "format" not in doc and "spectrum_path" in doc:
        v = 0                                       # legacy, see module docstring
    elif doc.get("format") == FORMAT:
        v = doc.get("schema_version")
    else:
        raise SessionSchemaError(f"not a SpectraMaster session (format {doc.get('format')!r})")
    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
        raise SessionSchemaError(f"invalid schema_version {v!r}")
    if v > SCHEMA_VERSION:
        raise SessionSchemaError(f"session schema version {v} is newer than supported ({SCHEMA_VERSION}); "
                                 "open it with a newer SpectraMaster")
    doc = copy.deepcopy(doc)
    while v < SCHEMA_VERSION:
        doc = MIGRATIONS[v](doc)
        v += 1
        doc["schema_version"] = v
    return doc

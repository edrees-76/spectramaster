"""Searchable archive index (SQLite) built from the original spectrum files, in place.

The archive is never written: files are only opened for reading and the database
may not lie inside an archive root.

Database (default ``%APPDATA%\\SpectraMaster\\archive.sqlite``)
---------------------------------------------------------------
``entries``   one row per spectrum file (per spectrum for rare multi-spectrum files):
              path, folder, name, sha256, ``dup_of`` (id of the canonical byte-identical
              copy, NULL for canonical rows), format, sample ID, description, comment
              (textual extra metadata), detector, guessed detector type, start time,
              live/real time, channels, total counts, calibration, size + mtime.
``skipped``   candidate files that are not spectra (so a refresh need not sniff them again).
``analysis``  per (sha256, spectrum #): analysis done/failed, time, peak count.
``nuclides``  per (sha256, spectrum #): identified nuclides with confidence.
``peaks``     per (sha256, spectrum #): key peaks (energy, net area, cps, assignment).
``entries_fts`` FTS5 (trigram tokenizer: substring search, works with attached Arabic
              prefixes such as ال/و/ب) over the Arabic-normalised text
              sample ID + description + comment + path.

Analysis results are keyed by file content (sha256), so byte-identical duplicates are
analysed once and every copy links to the result.

Build / refresh (:meth:`ArchiveIndex.build`)
    1. list candidates under each root; unchanged files (same size + mtime) are skipped;
    2. changed/new files are hashed; same hash as before -> only mtime is updated,
       otherwise the file is read (metadata pass, process pool);
    3. vanished files are removed; duplicate links are recomputed;
    4. analysis pass (peak search + identification, process pool) for every content
       hash without results.  Results are committed in batches, so an interrupted
       build resumes where it stopped.

Query API: :meth:`ArchiveIndex.search`, :meth:`count_by_period`, :meth:`nuclide_counts`,
:meth:`stats`; module-level :func:`normalize_text` (Arabic normalisation).
"""
from __future__ import annotations

import json
import os
import random
import re
import sqlite3
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

__all__ = ["normalize_text", "strip_article", "default_db_path", "ArchiveIndex", "ArchiveRow", "BuildResult",
           "canonical_nuclide", "nuclide_names", "SCHEMA_VERSION"]

SCHEMA_VERSION = 1
MIN_CONFIDENCE_STORED = 0.25          # identify() threshold used for the stored results
MAX_PEAKS_STORED = 40

BuildProgress = Callable[[str, int, int, Optional[float], str], Optional[bool]]
"""progress(phase, done, total, eta_seconds, current) -> False to cancel.
phase: "list", "scan", "analyse"."""

# ------------------------------------------------------------ Arabic text normalisation
_TASHKEEL = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",   # أ إ آ ٱ -> ا
    "ة": "ه",                                                             # ة -> ه
    "ى": "ي", "ی": "ي",                                         # ى ی -> ي
    "ک": "ك",                                                             # ک -> ك
    **{chr(0x0660 + i): str(i) for i in range(10)},                                 # ٠-٩
    **{chr(0x06F0 + i): str(i) for i in range(10)},                                 # ۰-۹
    "‌": " ", "‍": "", "‎": "", "‏": "", "﻿": "",
})


def normalize_text(text) -> str:
    """Search normalisation: alef forms -> ا, ة -> ه, ى -> ي, no tashkeel/tatweel,
    Arabic-Indic digits -> ASCII, case folded, whitespace collapsed."""
    if not text:
        return ""
    t = _TASHKEEL.sub("", str(text)).translate(_MAP).casefold()
    return " ".join(t.split())


# definite article with the attached particles (و ب ك ف ل), longest first; "لل" = ل + ال
_ARTICLES = ("وال", "بال", "كال", "فال", "لل", "ال")
_MIN_STEM = 3


def strip_article(term: str) -> str:
    """Query-side stemming of the Arabic definite article: «الشاي» -> «شاي», «والحليب» -> «حليب».

    Matching is by substring, so searching the stem still finds «الشاي», «شاي» and «بالشاي» in
    the index (no re-indexing needed).  Only stripped when at least three letters remain, so
    short words («الف», «لله») are left alone.  ``term`` is already normalised."""
    for art in _ARTICLES:
        if term.startswith(art) and len(term) - len(art) >= _MIN_STEM:
            rest = term[len(art):]
            if all("ء" <= ch <= "ي" for ch in rest):
                return rest
    return term


def default_db_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "SpectraMaster" / "archive.sqlite"


# ------------------------------------------------------------------- nuclide names
_NUC_RE = re.compile(r"^\s*([A-Za-z]{1,2})\s*-?\s*(\d{1,3})\s*(m\d?)?\s*$")
_NUC_RE2 = re.compile(r"^\s*(\d{1,3})\s*(m\d?)?\s*-?\s*([A-Za-z]{1,2})\s*$")


def nuclide_names() -> list[str]:
    """Names of the bundled library (for autocomplete)."""
    try:
        from ..analysis.library import load_library
        return sorted(load_library().keys(), key=_nuc_sort_key)
    except Exception:
        return []


def _nuc_sort_key(n: str):
    m = re.match(r"([A-Za-z]+)-(\d+)", n)
    return (m.group(1), int(m.group(2)), n) if m else (n, 0, n)


def canonical_nuclide(name: str, known: Optional[Iterable[str]] = None) -> str:
    """'cs137', 'Cs 137', '137Cs', 'CS-137' -> 'Cs-137' (library spelling when known)."""
    s = (name or "").strip()
    m = _NUC_RE.match(s)
    if m:
        el, a, meta = m.group(1), m.group(2), m.group(3) or ""
    else:
        m = _NUC_RE2.match(s)
        if not m:
            return s
        a, meta, el = m.group(1), m.group(2) or "", m.group(3)
    cand = f"{el.capitalize()}-{int(a)}{meta.lower()}"
    if known is not None:
        low = {k.lower(): k for k in known}
        return low.get(cand.lower(), cand)
    return cand


# ------------------------------------------------------------------------ results
@dataclass
class ArchiveRow:
    id: int
    path: str
    folder: str
    name: str
    sample_id: str = ""
    description: str = ""
    comment: str = ""
    detector: str = ""
    det_type: str = ""
    start_time: Optional[datetime] = None
    live_time: Optional[float] = None
    real_time: Optional[float] = None
    channels: int = 0
    total_counts: Optional[float] = None
    calibrated: bool = False
    energy_coeffs: list[float] = field(default_factory=list)
    format_key: str = ""
    sha256: str = ""
    spec_index: int = 1
    dup_of: Optional[int] = None
    copies: int = 1
    status: str = ""
    analysed: bool = False
    nuclides: list[tuple[str, float]] = field(default_factory=list)

    @property
    def nuclide_text(self) -> str:
        return ", ".join(f"{n} ({c:.2f})" for n, c in self.nuclides)

    @property
    def display_id(self) -> str:
        """Sample ID, or the file name stem when the file has none."""
        return self.sample_id or Path(self.name).stem


@dataclass
class BuildResult:
    files_listed: int = 0
    unchanged: int = 0
    scanned: int = 0
    rehashed_same: int = 0
    new_entries: int = 0
    non_spectra: int = 0
    removed: int = 0
    errors: int = 0
    duplicates: int = 0
    analysed: int = 0
    analysis_failed: int = 0
    analysis_pending: int = 0
    list_seconds: float = 0.0
    scan_seconds: float = 0.0
    analysis_seconds: float = 0.0
    cancelled: bool = False

    @property
    def elapsed(self) -> float:
        return self.list_seconds + self.scan_seconds + self.analysis_seconds


# ---------------------------------------------------------------- worker functions
# (module level: picklable for the process pool)
_TEXT_EXTRA_KEYS = ("comment", "file_remarks", "remarks", "title", "sample_ident", "sample_number",
                    "sample_description", "user_id", "operator", "geometry", "geometry_id",
                    "sample_quantity", "quantity", "location", "customer", "material", "roi_nuclides",
                    "background_file", "spectrum_type", "source_type")


def _init_worker() -> None:
    """Pool initializer: lower priority (keep the GUI responsive), load formats + library."""
    try:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),
                                                    0x00004000)    # BELOW_NORMAL_PRIORITY_CLASS
        else:
            os.nice(5)
    except Exception:
        pass
    from ..formats import load_all
    load_all()


def _comment_of(extra: dict) -> str:
    parts = []
    for k in _TEXT_EXTRA_KEYS:
        v = extra.get(k)
        if v not in (None, "") and not isinstance(v, (list, dict)):
            parts.append(str(v).strip())
    return " | ".join(p for p in parts if p)[:2000]


def _scan_one(path: str, root: str, known_sha: str) -> dict:
    """Metadata of one file.  kind: 'same' (content unchanged), 'entries', 'skip', 'error'."""
    from ..analysis.peaks import guess_detector
    from .archive import STRONG_SPECTRUM_EXTENSIONS, _checks, _energies, _recognise, sha256_file, \
        spectrum_fingerprint
    p = Path(path)
    try:
        st = p.stat()
    except OSError as exc:
        return {"kind": "gone", "path": path, "error": str(exc)}
    base = {"path": path, "root": root, "size": st.st_size, "mtime": st.st_mtime}
    if known_sha:
        try:
            sha = sha256_file(p)
        except OSError as exc:
            return {**base, "kind": "error", "sha256": "", "error": str(exc)}
        if sha == known_sha:
            return {**base, "kind": "same", "sha256": sha}
    fmt = _recognise(p)
    if fmt is None:
        if p.suffix.lower() in STRONG_SPECTRUM_EXTENSIONS:
            try:
                sha = sha256_file(p)
            except OSError:
                sha = ""
            return {**base, "kind": "error", "sha256": sha, "error": "unrecognised or corrupt spectrum file"}
        return {**base, "kind": "skip"}
    try:
        sha = sha256_file(p)
    except OSError as exc:
        return {**base, "kind": "error", "sha256": "", "error": str(exc)}
    try:
        spectra = fmt.reader(p)
        if not spectra:
            raise ValueError("no spectrum in file")
    except Exception as exc:
        return {**base, "kind": "error", "sha256": sha, "format_key": fmt.key,
                "error": f"{type(exc).__name__}: {exc}"}
    rows = []
    for i, s in enumerate(spectra, start=1):
        try:
            e = _energies(s)
            warns = _checks(s, e)
        except Exception:
            warns = []
        try:
            det_type = guess_detector(s)
        except Exception:
            det_type = ""
        rows.append({
            "spec_index": i, "format_key": fmt.key, "sample_id": s.sample_id or "",
            "description": s.description or "", "comment": _comment_of(s.extra or {}),
            "detector": s.detector or "", "det_type": det_type,
            "start_time": s.start_time.isoformat(sep=" ", timespec="seconds") if s.start_time else None,
            "live_time": s.live_time, "real_time": s.real_time, "channels": s.num_channels,
            "total_counts": s.total_counts, "calibrated": 1 if s.energy_coeffs else 0,
            "coeffs": json.dumps(list(s.energy_coeffs)), "fwhm_coeffs": json.dumps(list(s.fwhm_coeffs)),
            "fingerprint": spectrum_fingerprint(s),
            "status": "OK" if not warns else "warning: " + "; ".join(warns)})
    return {**base, "kind": "entries", "sha256": sha, "entries": rows}


def _scan_batch(items: Sequence[tuple[str, str, str]]) -> list[dict]:
    out = []
    for path, root, known in items:
        try:
            out.append(_scan_one(path, root, known))
        except Exception as exc:     # never lose the batch
            out.append({"kind": "error", "path": path, "root": root, "size": 0, "mtime": 0.0,
                        "sha256": "", "error": f"{type(exc).__name__}: {exc}"})
    return out


def _analyse_one(path: str, format_key: str, spec_index: int) -> dict:
    from .. import analysis as engine
    from ..formats import get_format
    from ..convert import read_spectra
    t0 = time.perf_counter()
    try:
        try:
            fmt = get_format(format_key) if format_key else None
        except KeyError:
            fmt = None
        spectra, _ = read_spectra(Path(path), fmt)
        s = spectra[spec_index - 1]
        peaks = list(engine.find_peaks(s) or [])
        matches = list(engine.identify(s, peaks, min_confidence=MIN_CONFIDENCE_STORED) or []) \
            if s.energy_coeffs else []
        top = sorted(peaks, key=lambda p: -(p.significance or 0))[:MAX_PEAKS_STORED]
        prow = [(float(p.energy) if p.energy is not None else None, float(p.net_area), float(p.net_area_unc),
                 float(p.count_rate) if p.count_rate is not None else
                 (float(p.net_area) / s.live_time if s.live_time else None),
                 float(p.fwhm_kev) if p.fwhm_kev is not None else None, float(p.significance), p.nuclide or "")
                for p in sorted(top, key=lambda p: p.centroid)]
        nrow = [(m.nuclide, float(m.confidence), len(m.matched)) for m in matches]
        return {"ok": True, "peaks": prow, "nuclides": nrow, "n_peaks": len(peaks),
                "seconds": time.perf_counter() - t0}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "peaks": [], "nuclides": [],
                "n_peaks": 0, "seconds": time.perf_counter() - t0}


def _analyse_batch(items: Sequence[tuple[str, int, str, str]]) -> list[tuple[str, int, dict]]:
    return [(sha, idx, _analyse_one(path, fk, idx)) for sha, idx, path, fk in items]


# --------------------------------------------------------------------------- schema
_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS roots(path TEXT PRIMARY KEY COLLATE NOCASE, added TEXT);
CREATE TABLE IF NOT EXISTS entries(
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL COLLATE NOCASE,
    spec_index INTEGER NOT NULL DEFAULT 1,
    root TEXT, rel_path TEXT, folder TEXT, name TEXT, ext TEXT,
    size INTEGER, mtime REAL, sha256 TEXT, dup_of INTEGER,
    format_key TEXT, sample_id TEXT, description TEXT, comment TEXT,
    detector TEXT, det_type TEXT, start_time TEXT, year INTEGER, month INTEGER,
    live_time REAL, real_time REAL, channels INTEGER, total_counts REAL,
    calibrated INTEGER, coeffs TEXT, fwhm_coeffs TEXT, fingerprint TEXT,
    status TEXT, error INTEGER DEFAULT 0, norm_text TEXT, norm_path TEXT,
    UNIQUE(path, spec_index));
CREATE INDEX IF NOT EXISTS ix_entries_sha ON entries(sha256, spec_index);
CREATE INDEX IF NOT EXISTS ix_entries_start ON entries(start_time);
CREATE INDEX IF NOT EXISTS ix_entries_dup ON entries(dup_of);
CREATE TABLE IF NOT EXISTS skipped(path TEXT PRIMARY KEY COLLATE NOCASE, root TEXT, size INTEGER, mtime REAL);
CREATE TABLE IF NOT EXISTS analysis(
    sha256 TEXT, spec_index INTEGER, analysed_at TEXT, ok INTEGER, error TEXT,
    seconds REAL, n_peaks INTEGER, PRIMARY KEY(sha256, spec_index));
CREATE TABLE IF NOT EXISTS nuclides(
    sha256 TEXT, spec_index INTEGER, nuclide TEXT, confidence REAL, n_lines INTEGER,
    PRIMARY KEY(sha256, spec_index, nuclide));
CREATE INDEX IF NOT EXISTS ix_nuclides_name ON nuclides(nuclide, confidence);
CREATE TABLE IF NOT EXISTS peaks(
    sha256 TEXT, spec_index INTEGER, energy REAL, net_area REAL, net_unc REAL, cps REAL,
    fwhm_kev REAL, significance REAL, nuclide TEXT);
CREATE INDEX IF NOT EXISTS ix_peaks_sha ON peaks(sha256, spec_index);
CREATE INDEX IF NOT EXISTS ix_peaks_energy ON peaks(energy);
CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(text, tokenize='trigram');
"""

_ROW_COLS = ("id, path, folder, name, sample_id, description, comment, detector, det_type, start_time, "
             "live_time, real_time, channels, total_counts, calibrated, coeffs, format_key, sha256, "
             "spec_index, dup_of, status")

ORDER_COLUMNS = {
    "date": "e.start_time", "sample_id": "e.sample_id", "name": "e.name COLLATE NOCASE",
    "folder": "e.folder COLLATE NOCASE", "live_time": "e.live_time", "path": "e.path",
    "total_counts": "e.total_counts", "detector": "e.detector", "id": "e.id",
}


def _norm_path(p) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def _is_inside(child, parent) -> bool:
    c, p = _norm_path(child), _norm_path(parent)
    return c == p or c.startswith(p.rstrip("\\/") + os.sep)


def _to_date(v, end: bool = False) -> Optional[str]:
    """date/datetime/'YYYY'/'YYYY-MM'/'YYYY-MM-DD' -> ISO bound string."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    if isinstance(v, date):
        d = v + timedelta(days=1) if end else v
        return d.isoformat()
    s = str(v).strip()
    if re.fullmatch(r"\d{4}", s):
        return f"{int(s) + 1:04d}" if end else s
    if re.fullmatch(r"\d{4}-\d{1,2}", s):
        y, m = map(int, s.split("-"))
        if end:
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return f"{y:04d}-{m:02d}"
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", s):
        d = date(*map(int, s.split("-")))
        return (d + timedelta(days=1)).isoformat() if end else d.isoformat()
    return s


class ArchiveIndex:
    """SQLite archive index.  Thread-safe for one writer (``build``) plus readers:
    every thread gets its own connection; WAL journal mode."""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        con = self._conn()
        con.executescript(_SCHEMA)
        con.execute("INSERT OR IGNORE INTO meta VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
        con.commit()

    # ------------------------------------------------------------ connections
    def _conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "con", None)
        if c is None:
            c = sqlite3.connect(str(self.db_path), timeout=60)
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.create_function("norm", 1, normalize_text, deterministic=True)
            self._local.con = c
        return c

    def close(self) -> None:
        c = getattr(self._local, "con", None)
        if c is not None:
            c.close()
            self._local.con = None

    # ------------------------------------------------------------------ roots
    def roots(self) -> list[str]:
        return [r[0] for r in self._conn().execute("SELECT path FROM roots ORDER BY path")]

    def add_root(self, path) -> None:
        p = str(Path(path))
        self._guard(p)
        c = self._conn()
        c.execute("INSERT OR IGNORE INTO roots VALUES(?, ?)", (p, datetime.now().isoformat(timespec="seconds")))
        c.commit()

    def remove_root(self, path, purge: bool = True) -> None:
        p = str(Path(path))
        c = self._conn()
        c.execute("DELETE FROM roots WHERE path = ?", (p,))
        if purge:
            ids = [r[0] for r in c.execute("SELECT id FROM entries WHERE root = ?", (p,))]
            self._delete_entries(c, ids)
            c.execute("DELETE FROM skipped WHERE root = ?", (p,))
            self._recompute_duplicates(c)
            self._purge_orphan_analysis(c)
        c.commit()

    def _guard(self, root) -> None:
        if _is_inside(self.db_path, root):
            raise ValueError(f"the index database {self.db_path} lies inside the archive {root}: "
                             "the archive is read-only, choose a database location outside it")

    # ------------------------------------------------------------------ build
    def build(self, roots: Optional[Sequence] = None, progress: Optional[BuildProgress] = None,
              workers: Optional[int] = None, analyse: bool = True, cancel: Optional[threading.Event] = None,
              analysis_sample: Optional[int] = None, sample_seed: int = 2026, recursive: bool = True,
              scan_batch: int = 16, analysis_batch: int = 4, commit_every: int = 400) -> BuildResult:
        """Incremental build/refresh.  `roots` default: the stored roots (given roots are added).
        `workers`: process count (default cores-1; 1 = in-process, no pool).
        `analysis_sample`: analyse only N randomly chosen pending spectra (timing estimates)."""
        from ..formats import load_all
        from .archive import find_spectrum_files
        load_all()
        res = BuildResult()
        if roots:
            for r in roots:
                self.add_root(r)
        roots = self.roots()
        for r in roots:
            self._guard(r)
        if workers is None:
            workers = max(1, (os.cpu_count() or 2) - 1)
        con = self._conn()
        state = {"cancel": False}

        def tick(phase, done, total, t0, current="") -> bool:
            if cancel is not None and cancel.is_set():
                state["cancel"] = True
            if progress is not None:
                el = time.perf_counter() - t0
                eta = (el / done * (total - done)) if done > 0 and total else None
                if progress(phase, done, total, eta, current) is False:
                    state["cancel"] = True
            return not state["cancel"]

        # ---- 1. list
        t0 = time.perf_counter()
        cand: list[tuple[str, str]] = []
        for r in roots:
            if not Path(r).is_dir():
                continue
            files = find_spectrum_files(Path(r), recursive)
            cand.extend((str(p), r) for p in files)
            if not tick("list", len(cand), 0, t0, r):
                break
        res.files_listed = len(cand)
        known = {row[0]: row[1:] for row in con.execute(
            "SELECT path, size, mtime, sha256 FROM entries WHERE spec_index = 1")}
        known_lc = {k.lower(): v for k, v in known.items()}
        skipped = {row[0].lower(): row[1:] for row in con.execute("SELECT path, size, mtime FROM skipped")}
        todo: list[tuple[str, str, str]] = []
        present = set()
        for path, root in cand:
            lc = path.lower()
            present.add(lc)
            try:
                st = os.stat(path)
            except OSError:
                continue
            k = known_lc.get(lc)
            if k is not None and k[0] == st.st_size and abs((k[1] or 0) - st.st_mtime) < 1e-3:
                res.unchanged += 1
                continue
            s = skipped.get(lc)
            if s is not None and s[0] == st.st_size and abs((s[1] or 0) - st.st_mtime) < 1e-3:
                res.unchanged += 1
                continue
            todo.append((path, root, (k[2] or "") if k is not None else ""))
        # vanished files (only under roots that were listed)
        if not state["cancel"]:
            listed_roots = [r for r in roots if Path(r).is_dir()]
            gone_ids = [i for i, p, rt in con.execute("SELECT id, path, root FROM entries")
                        if p.lower() not in present and rt in listed_roots]
            gone_ids += [i for i, p, rt in con.execute("SELECT id, path, root FROM entries")
                         if rt not in roots]
            gone_ids = sorted(set(gone_ids))
            self._delete_entries(con, gone_ids)
            res.removed = len(gone_ids)
            for p, rt in list(con.execute("SELECT path, root FROM skipped")):
                if rt not in roots or (rt in listed_roots and p.lower() not in present):
                    con.execute("DELETE FROM skipped WHERE path = ?", (p,))
            con.commit()
        res.list_seconds = time.perf_counter() - t0

        # ---- 2. metadata pass
        t1 = time.perf_counter()
        if todo and not state["cancel"]:
            batches = [todo[i:i + scan_batch] for i in range(0, len(todo), scan_batch)]
            done = [0]
            pending_commit = [0]

            def on_scan(results: list[dict]):
                for r in results:
                    self._store_scan(con, r, res)
                done[0] += len(results)
                pending_commit[0] += len(results)
                if pending_commit[0] >= commit_every:
                    con.commit()
                    pending_commit[0] = 0
                return tick("scan", done[0], len(todo), t1, results[-1]["path"] if results else "")

            self._run(_scan_batch, batches, workers, on_scan, state)
            con.commit()
        res.scanned = len(todo)
        self._recompute_duplicates(con)
        self._purge_orphan_analysis(con)
        con.commit()
        res.duplicates = con.execute("SELECT COUNT(*) FROM entries WHERE dup_of IS NOT NULL").fetchone()[0]
        res.errors = con.execute("SELECT COUNT(*) FROM entries WHERE error = 1").fetchone()[0]
        res.scan_seconds = time.perf_counter() - t1
        self._set_meta(con, "last_scan", datetime.now().isoformat(timespec="seconds"))
        con.commit()

        # ---- 3. analysis pass
        t2 = time.perf_counter()
        pend = self._pending_analysis(con)
        if analyse and not state["cancel"] and pend:
            if analysis_sample is not None and analysis_sample < len(pend):
                rnd = random.Random(sample_seed)
                pend = rnd.sample(pend, analysis_sample)
            batches = [pend[i:i + analysis_batch] for i in range(0, len(pend), analysis_batch)]
            done = [0]
            pending_commit = [0]

            def on_ana(results):
                stamp = datetime.now().isoformat(sep=" ", timespec="seconds")
                for sha, idx, r in results:
                    self._store_analysis(con, sha, idx, r, stamp)
                    if r["ok"]:
                        res.analysed += 1
                    else:
                        res.analysis_failed += 1
                done[0] += len(results)
                pending_commit[0] += len(results)
                if pending_commit[0] >= max(20, commit_every // 4):
                    con.commit()
                    pending_commit[0] = 0
                return tick("analyse", done[0], len(pend), t2, results[-1][0] if results else "")

            self._run(_analyse_batch, batches, workers, on_ana, state)
            con.commit()
            self._set_meta(con, "last_analysis", datetime.now().isoformat(timespec="seconds"))
            con.commit()
        res.analysis_pending = len(self._pending_analysis(con))
        res.analysis_seconds = time.perf_counter() - t2
        res.cancelled = state["cancel"]
        return res

    @staticmethod
    def _run(fn, batches, workers, on_result, state) -> None:
        """Run fn over batches (in-process for workers <= 1) and feed results in completion order."""
        if not batches:
            return
        if workers <= 1:
            for b in batches:
                if state["cancel"]:
                    return
                if on_result(fn(b)) is False:
                    return
            return
        ex = ProcessPoolExecutor(max_workers=workers, initializer=_init_worker)
        try:
            it = iter(batches)
            pending = set()
            window = workers * 3
            for _ in range(window):
                b = next(it, None)
                if b is None:
                    break
                pending.add(ex.submit(fn, b))
            while pending:
                done, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
                if not done and on_result([]) is False:       # lets a cancel through while waiting
                    break
                stop = False
                for f in done:
                    if on_result(f.result()) is False:
                        stop = True
                if stop or state["cancel"]:
                    break
                while len(pending) < window:
                    b = next(it, None)
                    if b is None:
                        break
                    pending.add(ex.submit(fn, b))
        finally:
            ex.shutdown(wait=True, cancel_futures=True)

    # ------------------------------------------------------------ storage
    def _store_scan(self, con, r: dict, res: BuildResult) -> None:
        kind = r.get("kind")
        path = r["path"]
        if kind == "gone":
            ids = [i for (i,) in con.execute("SELECT id FROM entries WHERE path = ?", (path,))]
            self._delete_entries(con, ids)
            con.execute("DELETE FROM skipped WHERE path = ?", (path,))
            return
        if kind == "same":
            res.rehashed_same += 1
            con.execute("UPDATE entries SET size = ?, mtime = ? WHERE path = ?", (r["size"], r["mtime"], path))
            return
        ids = [i for (i,) in con.execute("SELECT id FROM entries WHERE path = ?", (path,))]
        self._delete_entries(con, ids)
        con.execute("DELETE FROM skipped WHERE path = ?", (path,))
        if kind == "skip":
            res.non_spectra += 1
            con.execute("INSERT OR REPLACE INTO skipped VALUES(?,?,?,?)", (path, r["root"], r["size"], r["mtime"]))
            return
        root = r["root"]
        try:
            rel = os.path.relpath(path, root)
        except ValueError:
            rel = path
        folder, name = os.path.dirname(rel), os.path.basename(path)
        common = dict(path=path, root=root, rel_path=rel, folder=folder, name=name,
                      ext=os.path.splitext(name)[1].lower(), size=r["size"], mtime=r["mtime"],
                      sha256=r.get("sha256", ""), norm_path=normalize_text(path))
        rows = r.get("entries") if kind == "entries" else [
            {"spec_index": 1, "format_key": r.get("format_key", ""), "status": "error: " + r.get("error", ""),
             "error": 1}]
        for e in rows:
            d = {**common, **e}
            st = d.get("start_time")
            d["year"] = int(st[:4]) if st else None
            d["month"] = int(st[5:7]) if st else None
            d.setdefault("error", 0)
            d["norm_text"] = normalize_text(" ".join(
                x for x in (d.get("sample_id"), d.get("description"), d.get("comment"),
                         os.path.join(os.path.basename(root.rstrip("\\/")), rel)) if x))
            cols = list(d)
            cur = con.execute(f"INSERT INTO entries({', '.join(cols)}) VALUES({', '.join('?' * len(cols))})",
                              [d[c] for c in cols])
            con.execute("INSERT INTO entries_fts(rowid, text) VALUES(?, ?)", (cur.lastrowid, d["norm_text"]))
            res.new_entries += 1

    @staticmethod
    def _delete_entries(con, ids) -> None:
        for i in ids:
            con.execute("DELETE FROM entries WHERE id = ?", (i,))
            con.execute("DELETE FROM entries_fts WHERE rowid = ?", (i,))

    @staticmethod
    def _recompute_duplicates(con) -> None:
        rows = con.execute("SELECT id, sha256, spec_index, path FROM entries "
                           "WHERE sha256 != '' AND error = 0").fetchall()
        groups: dict[tuple, list] = {}
        for i, sha, idx, p in rows:
            groups.setdefault((sha, idx), []).append((p.lower(), i))
        updates = []
        for g in groups.values():
            g.sort()
            canon = g[0][1]
            updates.append((None, canon))
            updates.extend((canon, i) for _p, i in g[1:])
        con.execute("UPDATE entries SET dup_of = NULL WHERE dup_of IS NOT NULL")
        con.executemany("UPDATE entries SET dup_of = ? WHERE id = ?", [u for u in updates if u[0] is not None])

    @staticmethod
    def _purge_orphan_analysis(con) -> None:
        for t in ("analysis", "nuclides", "peaks"):
            con.execute(f"DELETE FROM {t} WHERE NOT EXISTS (SELECT 1 FROM entries e WHERE "
                        f"e.sha256 = {t}.sha256 AND e.spec_index = {t}.spec_index)")

    @staticmethod
    def _pending_analysis(con) -> list[tuple[str, int, str, str]]:
        return [tuple(r) for r in con.execute(
            "SELECT e.sha256, e.spec_index, e.path, e.format_key FROM entries e "
            "WHERE e.error = 0 AND e.dup_of IS NULL AND e.sha256 != '' AND NOT EXISTS "
            "(SELECT 1 FROM analysis a WHERE a.sha256 = e.sha256 AND a.spec_index = e.spec_index) "
            "ORDER BY e.path")]

    @staticmethod
    def _store_analysis(con, sha, idx, r: dict, stamp: str) -> None:
        con.execute("DELETE FROM nuclides WHERE sha256 = ? AND spec_index = ?", (sha, idx))
        con.execute("DELETE FROM peaks WHERE sha256 = ? AND spec_index = ?", (sha, idx))
        con.execute("INSERT OR REPLACE INTO analysis VALUES(?,?,?,?,?,?,?)",
                    (sha, idx, stamp, 1 if r["ok"] else 0, r.get("error"), r.get("seconds"), r.get("n_peaks")))
        con.executemany("INSERT OR REPLACE INTO nuclides VALUES(?,?,?,?,?)",
                        [(sha, idx, n, c, k) for n, c, k in r.get("nuclides", [])])
        con.executemany("INSERT INTO peaks VALUES(?,?,?,?,?,?,?,?,?)",
                        [(sha, idx, *p) for p in r.get("peaks", [])])

    @staticmethod
    def _set_meta(con, k, v) -> None:
        con.execute("INSERT OR REPLACE INTO meta VALUES(?, ?)", (k, str(v)))

    def meta(self, key: str, default=None):
        r = self._conn().execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return r[0] if r else default

    # ------------------------------------------------------------------ query
    def _where(self, text=None, nuclides=None, min_confidence=0.5, date_from=None, date_to=None,
               detector=None, folder_contains=None, has_calibration=None, min_live_time=None,
               include_duplicates=False, include_errors=False, nuclide_mode="all", year=None,
               energy=None, energy_tol=1.0) -> tuple[str, list]:
        cond, args = [], []
        if not include_duplicates:
            cond.append("e.dup_of IS NULL")
        if not include_errors:
            cond.append("e.error = 0")
        if text:
            terms = [strip_article(t) for t in normalize_text(text).split()]
            for t in terms:
                if len(t) >= 3:
                    cond.append("e.id IN (SELECT rowid FROM entries_fts WHERE entries_fts MATCH ?)")
                    args.append('"' + t.replace('"', '""') + '"')
                else:
                    cond.append("instr(e.norm_text, ?) > 0")
                    args.append(t)
        if nuclides:
            names = nuclide_names()
            nucs = [canonical_nuclide(n, names) for n in nuclides if str(n).strip()]
            sub = ("EXISTS (SELECT 1 FROM nuclides n WHERE n.sha256 = e.sha256 AND n.spec_index = "
                   "e.spec_index AND n.nuclide = ? AND n.confidence >= ?)")
            parts = []
            for n in nucs:
                parts.append(sub)
                args.extend([n, float(min_confidence or 0.0)])
            if parts:
                cond.append("(" + (" OR " if nuclide_mode == "any" else " AND ").join(parts) + ")")
        if year is not None:
            cond.append("e.year = ?")
            args.append(int(year))
        f = _to_date(date_from)
        if f:
            cond.append("e.start_time >= ?")
            args.append(f)
        t_ = _to_date(date_to, end=True)
        if t_:
            cond.append("e.start_time < ?")
            args.append(t_)
        if detector:
            d = normalize_text(detector)
            cond.append("(instr(lower(e.detector), ?) > 0 OR lower(e.det_type) = ?)")
            args.extend([d, d])
        if folder_contains:
            cond.append("instr(norm(e.folder), ?) > 0")
            args.append(normalize_text(folder_contains))
        if has_calibration is not None:
            cond.append("e.calibrated = ?")
            args.append(1 if has_calibration else 0)
        if min_live_time:
            cond.append("e.live_time >= ?")
            args.append(float(min_live_time))
        if energy is not None:
            cond.append("EXISTS (SELECT 1 FROM peaks p WHERE p.sha256 = e.sha256 AND p.spec_index = "
                        "e.spec_index AND p.energy BETWEEN ? AND ?)")
            args.extend([float(energy) - energy_tol, float(energy) + energy_tol])
        return (" WHERE " + " AND ".join(cond)) if cond else "", args

    def search(self, text: Optional[str] = None, nuclides: Optional[Sequence[str]] = None,
               min_confidence: float = 0.5, date_from=None, date_to=None, detector: Optional[str] = None,
               folder_contains: Optional[str] = None, has_calibration: Optional[bool] = None,
               min_live_time: Optional[float] = None, include_duplicates: bool = False,
               order_by: str = "date", limit: Optional[int] = 5000, include_errors: bool = False,
               nuclide_mode: str = "all", year: Optional[int] = None, energy: Optional[float] = None,
               energy_tol: float = 1.0, offset: int = 0) -> list[ArchiveRow]:
        """Filtered search.  `text`: words (AND), Arabic-normalised substring match on sample ID,
        description, comment and path.  `nuclides`: identified with confidence >= min_confidence
        (all of them, or any with nuclide_mode="any").  `date_from`/`date_to` inclusive (date,
        datetime, 'YYYY', 'YYYY-MM', 'YYYY-MM-DD').  `detector`: substring of the detector field or
        the guessed type (HPGe/NaI).  `energy`: has a peak at energy +/- energy_tol keV.
        `order_by`: date, sample_id, name, folder, live_time, path, total_counts (prefix '-' for
        descending)."""
        where, args = self._where(text, nuclides, min_confidence, date_from, date_to, detector,
                                  folder_contains, has_calibration, min_live_time, include_duplicates,
                                  include_errors, nuclide_mode, year, energy, energy_tol)
        desc = order_by.startswith("-")
        col = ORDER_COLUMNS.get(order_by.lstrip("-"), "e.start_time")
        sql = (f"SELECT {', '.join('e.' + c.strip() for c in _ROW_COLS.split(','))} FROM entries e{where} "
               f"ORDER BY {col} {'DESC' if desc else 'ASC'}, e.path")
        if limit:
            sql += f" LIMIT {int(limit)} OFFSET {int(offset)}"
        con = self._conn()
        rows = [self._row(r) for r in con.execute(sql, args)]
        self._attach(con, rows)
        return rows

    def count(self, **filters) -> int:
        where, args = self._where(**filters)
        return self._conn().execute(f"SELECT COUNT(*) FROM entries e{where}", args).fetchone()[0]

    def count_by_period(self, period: str = "year", **filters) -> list[tuple[str, int]]:
        """[(period, n)] for 'year' ('2009') or 'month' ('2009-03'); undated rows as ''."""
        n = 4 if period == "year" else 7
        where, args = self._where(**filters)
        sql = (f"SELECT COALESCE(substr(e.start_time, 1, {n}), '') AS k, COUNT(*) FROM entries e{where} "
               f"GROUP BY k ORDER BY k")
        return [(k, c) for k, c in self._conn().execute(sql, args)]

    def nuclide_counts(self, min_confidence: float = 0.5, **filters) -> list[tuple[str, int]]:
        """[(nuclide, number of matching spectra with that nuclide >= min_confidence)], most frequent first."""
        filters = dict(filters)
        where, args = self._where(min_confidence=min_confidence, **filters)
        sql = (f"SELECT n.nuclide, COUNT(DISTINCT e.id) FROM entries e JOIN nuclides n ON "
               f"n.sha256 = e.sha256 AND n.spec_index = e.spec_index AND n.confidence >= ?"
               f"{where} GROUP BY n.nuclide ORDER BY 2 DESC, 1")
        return [(k, c) for k, c in self._conn().execute(sql, [float(min_confidence)] + args)]

    def stats(self) -> dict:
        c = self._conn()
        q = lambda s: c.execute(s).fetchone()[0]
        return {
            "entries": q("SELECT COUNT(*) FROM entries"),
            "unique": q("SELECT COUNT(*) FROM entries WHERE dup_of IS NULL AND error = 0"),
            "duplicates": q("SELECT COUNT(*) FROM entries WHERE dup_of IS NOT NULL"),
            "errors": q("SELECT COUNT(*) FROM entries WHERE error = 1"),
            "non_spectra": q("SELECT COUNT(*) FROM skipped"),
            "analysed": q("SELECT COUNT(*) FROM analysis"),
            "analysis_failed": q("SELECT COUNT(*) FROM analysis WHERE ok = 0"),
            "pending_analysis": len(self._pending_analysis(c)),
            "roots": self.roots(),
            "last_scan": self.meta("last_scan"),
            "last_analysis": self.meta("last_analysis"),
        }

    def detectors(self) -> list[str]:
        vals = {r[0] for r in self._conn().execute("SELECT DISTINCT detector FROM entries") if r[0]}
        vals |= {r[0] for r in self._conn().execute("SELECT DISTINCT det_type FROM entries") if r[0]}
        return sorted(vals, key=str.lower)

    def peaks_of(self, row_or_id) -> list[dict]:
        con = self._conn()
        if isinstance(row_or_id, ArchiveRow):
            sha, idx = row_or_id.sha256, row_or_id.spec_index
        else:
            sha, idx = con.execute("SELECT sha256, spec_index FROM entries WHERE id = ?", (row_or_id,)).fetchone()
        return [dict(energy=r[0], net_area=r[1], net_unc=r[2], cps=r[3], fwhm_kev=r[4], significance=r[5],
                     nuclide=r[6]) for r in con.execute(
            "SELECT energy, net_area, net_unc, cps, fwhm_kev, significance, nuclide FROM peaks "
            "WHERE sha256 = ? AND spec_index = ? ORDER BY energy", (sha, idx))]

    def copies_of(self, row: ArchiveRow) -> list[str]:
        return [r[0] for r in self._conn().execute(
            "SELECT path FROM entries WHERE sha256 = ? AND spec_index = ? ORDER BY path",
            (row.sha256, row.spec_index))]

    @staticmethod
    def _row(r) -> ArchiveRow:
        (i, path, folder, name, sid, desc, com, det, dtype, st, lt, rt, ch, tc, cal, coeffs, fk, sha, idx,
         dup, status) = r
        try:
            stv = datetime.fromisoformat(st) if st else None
        except ValueError:
            stv = None
        try:
            co = json.loads(coeffs) if coeffs else []
        except ValueError:
            co = []
        return ArchiveRow(i, path, folder or "", name or "", sid or "", desc or "", com or "", det or "",
                          dtype or "", stv, lt, rt, ch or 0, tc, bool(cal), co, fk or "", sha or "", idx or 1,
                          dup, 1, status or "")

    @staticmethod
    def _attach(con, rows: list[ArchiveRow]) -> None:
        if not rows:
            return
        keys = {(r.sha256, r.spec_index) for r in rows}
        nuc: dict = {}
        done: set = set()
        copies: dict = {}
        shas = sorted({k[0] for k in keys})
        for i in range(0, len(shas), 500):
            chunk = shas[i:i + 500]
            ph = ",".join("?" * len(chunk))
            for sha, idx, n, c in con.execute(
                    f"SELECT sha256, spec_index, nuclide, confidence FROM nuclides WHERE sha256 IN ({ph}) "
                    f"ORDER BY confidence DESC", chunk):
                nuc.setdefault((sha, idx), []).append((n, c))
            for sha, idx in con.execute(f"SELECT sha256, spec_index FROM analysis WHERE sha256 IN ({ph})", chunk):
                done.add((sha, idx))
            for sha, idx, n in con.execute(
                    f"SELECT sha256, spec_index, COUNT(*) FROM entries WHERE sha256 IN ({ph}) "
                    f"GROUP BY sha256, spec_index", chunk):
                copies[(sha, idx)] = n
        for r in rows:
            k = (r.sha256, r.spec_index)
            r.nuclides = nuc.get(k, [])
            r.analysed = k in done
            r.copies = copies.get(k, 1)


def export_rows(rows: Sequence[ArchiveRow], path, lang_headers: Optional[Sequence[str]] = None) -> Path:
    """Write search results to .xlsx (by extension) or .csv (UTF-8 with BOM, opens in Excel)."""
    path = Path(path)
    headers = list(lang_headers) if lang_headers else [
        "Start date/time", "Sample ID", "Description", "Nuclides (confidence)", "Live time (s)",
        "Real time (s)", "Detector", "File name", "Folder", "Path", "Copies", "Total counts", "Comment"]
    data = [[r.start_time, r.display_id, r.description, r.nuclide_text, r.live_time, r.real_time,
             r.detector or r.det_type, r.name, r.folder, r.path, r.copies, r.total_counts, r.comment]
            for r in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".xlsx":
        from openpyxl import Workbook
        from .archive import _sheet
        wb = Workbook()
        ws = _sheet(wb, "Results", headers, data, first=True,
                    widths={headers[0]: 19, headers[2]: 30, headers[3]: 40, headers[8]: 50, headers[9]: 70})
        for row in ws.iter_rows(min_row=2, min_col=1, max_col=1):
            for c in row:
                c.number_format = "yyyy-mm-dd hh:mm:ss"
        wb.save(path)
    else:
        import csv
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(headers)
            for d in data:
                w.writerow(["" if v is None else (v.isoformat(sep=" ") if isinstance(v, datetime) else v)
                            for v in d])
    return path

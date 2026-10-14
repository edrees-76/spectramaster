"""Shared helpers of the lab data models: ids, UTC timestamps, plain-data conversion, hashing.

Everything in :mod:`spectramaster.lab` is stored as *plain data* (dict / list / str /
float / int / bool / None) so that sessions are JSON documents that can be diffed,
hashed and migrated without importing analysis classes.  ``to_plain`` is the single
conversion point (datetimes -> ISO strings, tuples -> lists, numpy scalars -> Python).

Content hashes are SHA-256 of the *canonical* JSON (sorted keys, no whitespace,
``repr``-exact floats), so the same scientific content always gives the same hash.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np


def new_id() -> str:
    """Random stable identifier (uuid4).  Never derived from a name: renaming keeps the id."""
    return str(uuid.uuid4())


def utc_now() -> str:
    """Timezone-aware UTC timestamp as ISO 8601 text."""
    return datetime.now(timezone.utc).isoformat()


def to_plain(obj: Any) -> Any:
    """Recursively convert `obj` to JSON-compatible plain data."""
    if obj is None or isinstance(obj, (bool, str, int)):
        return obj
    if isinstance(obj, float):
        # NaN/inf (e.g. an undefined chi2) are stored as null so documents stay strict JSON
        return obj if math.isfinite(obj) else None
    if isinstance(obj, np.generic):
        return to_plain(obj.item())
    if isinstance(obj, np.ndarray):
        return [to_plain(v) for v in obj.tolist()]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_plain(v) for v in obj]
    raise TypeError(f"cannot store {type(obj).__name__} in a session document")


def canonical_json(obj: Any) -> str:
    """Deterministic JSON text (sorted keys, compact); non-finite floats become null."""
    return json.dumps(to_plain(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_hash(obj: Any) -> str:
    return sha256_text(canonical_json(obj))


def file_sha256(path, chunk: int = 1 << 20) -> str:
    """SHA-256 of the file bytes (read-only access; the file is never modified)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def counts_fingerprint(counts) -> str:
    """SHA-256 of the counts as little-endian float64 - independent of the file format."""
    return hashlib.sha256(np.asarray(counts, dtype="<f8").tobytes()).hexdigest()


def opt_float(v: Any, name: str, positive: bool = True) -> Optional[float]:
    """Optional physical quantity: None stays None (missing is never 0); validates sign."""
    if v is None or v == "":
        return None
    f = float(v)
    if not math.isfinite(f):
        raise ValueError(f"{name}: not a finite number ({v!r})")
    if positive and f <= 0:
        raise ValueError(f"{name}: must be > 0 (use None when unknown), got {v!r}")
    return f


def from_known(cls, d: dict, **override):
    """Build dataclass `cls` from `d`, ignoring unknown keys (forward-tolerant reading)."""
    known = {f.name for f in dataclasses.fields(cls)}
    kw = {k: v for k, v in d.items() if k in known}
    kw.update(override)
    return cls(**kw)

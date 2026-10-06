"""Nuclide gamma-line library: loading of the bundled ``data/gamma_library.json`` and of
user libraries (same JSON layout, or a simple CSV).

Bundled data: IAEA ENSDF decay radiations (ndlab / LiveChart) cross-checked against
SandiaDecay; see ``data/SOURCES.md`` and ``data/build_library.py``.

CSV user library (``--lib my.csv``), one line per gamma line::

    nuclide, energy_keV, intensity_percent [, half_life [, category]]
    Cs-137, 661.657, 85.1, 30.08 y, calibration

Lines starting with ``#`` and a header row are ignored.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional, Union

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_LIBRARY = DATA_DIR / "gamma_library.json"


@dataclass(frozen=True)
class Line:
    energy: float          # keV
    intensity: float       # photons per 100 decays
    kind: str = "g"        # g gamma, x X-ray, a annihilation
    source: str = ""       # I = IAEA, S = SandiaDecay, U = user


@dataclass
class NuclideData:
    name: str
    lines: list[Line]
    half_life: str = ""
    half_life_s: Optional[float] = None
    category: str = ""
    series: str = ""
    series_factor: float = 1.0
    subgroup: str = ""
    background: bool = False
    note: str = ""
    includes: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    def gammas(self, min_intensity: float = 0.0) -> list[Line]:
        return [l for l in self.lines if l.kind == "g" and l.intensity >= min_intensity]


Library = dict[str, NuclideData]


def _from_json(doc: dict) -> Library:
    out: Library = {}
    for name, e in doc.get("nuclides", {}).items():
        lines = [Line(float(l[0]), float(l[1]), l[2] if len(l) > 2 else "g", l[3] if len(l) > 3 else "")
                 for l in e.get("lines", [])]
        out[name] = NuclideData(
            name=name, lines=sorted(lines, key=lambda l: l.energy), half_life=e.get("half_life", ""),
            half_life_s=e.get("half_life_s"), category=e.get("category", ""), series=e.get("series", ""),
            series_factor=float(e.get("series_factor", 1.0)), subgroup=e.get("subgroup", ""),
            background=bool(e.get("background", False)), note=e.get("note", ""),
            includes=list(e.get("includes", [])), flags=list(e.get("provenance", {}).get("flags", [])))
    return out


def _from_csv(path: Path) -> Library:
    out: Library = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.reader(fh):
            row = [c.strip() for c in row]
            if not row or not row[0] or row[0].startswith("#"):
                continue
            try:
                e, i = float(row[1]), float(row[2])
            except (IndexError, ValueError):
                continue   # header or malformed row
            nd = out.setdefault(row[0], NuclideData(name=row[0], lines=[]))
            nd.lines.append(Line(e, i, "g", "U"))
            if len(row) > 3 and row[3]:
                nd.half_life = row[3]
            if len(row) > 4 and row[4]:
                nd.category = row[4]
    for nd in out.values():
        nd.lines.sort(key=lambda l: l.energy)
    return out


@lru_cache(maxsize=8)
def _load_path(path: str) -> Library:
    p = Path(path)
    if p.suffix.lower() in (".csv", ".txt"):
        return _from_csv(p)
    return _from_json(json.loads(p.read_text(encoding="utf-8")))


def load_library(source: Union[None, str, Path, dict] = None) -> Library:
    """The bundled library (default), a JSON/CSV file path, or an already parsed dict/Library."""
    if source is None:
        return _load_path(str(DEFAULT_LIBRARY))
    if isinstance(source, dict):
        if source and all(isinstance(v, NuclideData) for v in source.values()):
            return source  # type: ignore[return-value]
        return _from_json(source)
    return _load_path(str(Path(source).resolve()))


def lines_of(name: str, source=None) -> list[Line]:
    nd = load_library(source).get(name)
    return list(nd.lines) if nd else []

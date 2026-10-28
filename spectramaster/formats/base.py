"""Format registry.

Each format module calls `register(FormatSpec(...))` at import time.
`spectramaster.formats.load_all()` imports every module so the registry is full.

Numeric codes 1-16 follow the ORTEC DataMaster command-line table so existing
batch scripts keep working (`-13 in.s0 -1 out.chn`). Codes >= 20 are formats
DataMaster never had.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..model import Spectrum

Reader = Callable[[Path], list[Spectrum]]
Writer = Callable[[Spectrum, Path], None]
Sniffer = Callable[[Path, bytes], bool]
"""Return True if the file (path + first 4 KiB) looks like this format."""


class FormatError(Exception):
    """Raised by readers/writers for malformed input or unwritable data."""


@dataclass
class FormatSpec:
    code: int
    key: str                      # stable identifier, e.g. "aptec_s0"
    name: str                     # display name, e.g. "APTEC v6.3"
    extensions: list[str]         # lower-case, with dot; first is the default output ext
    reader: Optional[Reader] = None
    writer: Optional[Writer] = None
    sniffer: Optional[Sniffer] = None
    notes: str = ""
    content_sniffer: Optional[Sniffer] = None
    """Test on the content alone (the file name is ignored), used only when no format is
    recognised the usual way; registered only for tests with no false match on other files
    (docs/baseline/any_extension_protocol.md)."""
    aliases: list[str] = field(default_factory=list)

    @property
    def can_read(self) -> bool:
        return self.reader is not None

    @property
    def can_write(self) -> bool:
        return self.writer is not None

    @property
    def default_ext(self) -> str:
        return self.extensions[0] if self.extensions else ".dat"

    def label(self) -> str:
        exts = ";".join("*" + e for e in self.extensions)
        return f"{self.name}  ({exts})"


_REGISTRY: dict[str, FormatSpec] = {}


def register(spec: FormatSpec) -> FormatSpec:
    for other in _REGISTRY.values():
        if other.code == spec.code and other.key != spec.key:
            raise ValueError(f"format code {spec.code} used by both {other.key} and {spec.key}")
    _REGISTRY[spec.key] = spec
    return spec


def all_formats() -> list[FormatSpec]:
    return sorted(_REGISTRY.values(), key=lambda f: f.code)


def readable_formats() -> list[FormatSpec]:
    return [f for f in all_formats() if f.can_read]


def writable_formats() -> list[FormatSpec]:
    return [f for f in all_formats() if f.can_write]


def get_format(key_or_code) -> FormatSpec:
    """Look up by key, alias, or numeric code (int or digit string)."""
    if isinstance(key_or_code, int) or (isinstance(key_or_code, str) and key_or_code.isdigit()):
        code = int(key_or_code)
        for f in _REGISTRY.values():
            if f.code == code:
                return f
        raise KeyError(f"no format with code {code}")
    k = str(key_or_code).lower()
    if k in _REGISTRY:
        return _REGISTRY[k]
    for f in _REGISTRY.values():
        if k in f.aliases:
            return f
    raise KeyError(f"unknown format {key_or_code!r}")


# When several content tests match, the more specific format wins over the more general one.
CONTENT_PREFERENCE = (("chandata_csv", "ascii2"), ("eml_sanderson", "iaea_ascii_dat"),
                      ("wallac_ascii", "ascii1"), ("laval_ascii", "ascii1"), ("laval_ascii", "tka"))


# ... and among the usual tests: a SpecUtils TXT file (first line "Original File Name:") also has
# the numeric lines of the ASCII layouts (docs/baseline/round4_formats_protocol.md)
USUAL_PREFERENCE = (("specutils_txt", "ascii2"), ("specutils_txt", "ascii1"))


# A usual match that stays ambiguous when the other format's content test also matches: a TKA file
# named .txt is also one-column ASCII (docs/baseline/round5_tka_protocol.md); so are Laval and
# Wallac files (docs/baseline/round6_laval_wallac_protocol.md)
USUAL_AMBIGUOUS = (("ascii1", "tka"), ("ascii1", "laval_ascii"), ("ascii1", "wallac_ascii"))


def _detect_usual(path: Path, head: bytes) -> Optional[FormatSpec]:
    found = []
    for f in readable_formats():
        if f.sniffer is not None:
            try:
                if f.sniffer(path, head):
                    found.append(f)
            except Exception:
                pass
    keys = {f.key for f in found}
    beaten = {loser for winner, loser in USUAL_PREFERENCE if winner in keys}
    for f in found:
        if f.key not in beaten:
            return f
    # Extension fallback only for formats whose content can't be sniffed: a sniffer
    # that already said "no" (e.g. HyperLab binary .SPE vs IAEA SPE) is trusted.
    ext = path.suffix.lower()
    for f in readable_formats():
        if f.sniffer is None and ext in f.extensions:
            return f
    return None


def content_candidates(path: Path, head: bytes) -> list[FormatSpec]:
    """Formats whose content-only test matches, after dropping the less specific of each
    preferred pair."""
    found = []
    for f in readable_formats():
        if f.content_sniffer is not None:
            try:
                if f.content_sniffer(path, head):
                    found.append(f)
            except Exception:
                pass
    keys = {f.key for f in found}
    beaten = {loser for winner, loser in CONTENT_PREFERENCE if winner in keys}
    return [f for f in found if f.key not in beaten]


def detect(path: Path) -> tuple[Optional[FormatSpec], str, list[FormatSpec]]:
    """(format, how, candidates): how is "usual", "content" (recognised from the content alone,
    whatever the extension), "ambiguous" (several content candidates, format None) or "none"."""
    path = Path(path)
    try:
        with open(path, "rb") as fh:
            head = fh.read(4096)
    except OSError:
        return None, "none", []
    f = _detect_usual(path, head)
    if f is not None:
        rivals = {o for u, o in USUAL_AMBIGUOUS if u == f.key}
        if rivals:
            also = [c for c in content_candidates(path, head) if c.key in rivals]
            if also:
                return None, "ambiguous", [f] + also
        return f, "usual", [f]
    cands = content_candidates(path, head)
    if len(cands) == 1:
        return cands[0], "content", cands
    return None, ("ambiguous" if cands else "none"), cands


def detect_format(path: Path) -> Optional[FormatSpec]:
    """Best-effort auto-detection: content sniffers first, then extension; then, whatever the
    extension, the content-only tests when they point to exactly one format."""
    return detect(path)[0]

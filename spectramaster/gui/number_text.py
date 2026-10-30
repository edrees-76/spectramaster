"""The decimal comma of numbers typed in the GUI (round-8 review, Codex M1).

A comma is read as a decimal comma ("0,5" = 0.5) unless the text is ambiguous: "1,000" may be one
thousand (thousands separator) or one (decimal comma), and "1.000,5" / "1,000.5" mix both
separators.  Such text is refused, never guessed - a guess is a silent factor-1000 error in a mass
or a volume.  Pure Python (no Qt), shared by every GUI number field that accepts a decimal comma.
"""
from __future__ import annotations

import re
import unicodedata

# thousands grouping of a mantissa (sign and exponent removed, digits ASCII): "1,000", "12,500,000";
# a lone leading zero is not a thousands group, so "0,500" is the decimal 0.5
_GROUPED = re.compile(r"(?!0,)\d{1,3}(?:,\d{3})+", re.ASCII)
_EXPONENT = re.compile(r"[eE]")


def _ascii_digits(s: str) -> str:
    """`s` with every decimal digit (Arabic-Indic, Eastern Arabic-Indic ..., which float() reads) as
    an ASCII digit, so "٠,٥٠٠" is checked like "0,500" (round-9 review, Codex L1)."""
    return "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in s)


def is_ambiguous(text: str) -> bool:
    """True for text that is both a thousands-separated and a decimal-comma number, or that mixes
    a comma and a point.  The mantissa is checked without its sign and its exponent, so "1,000e3"
    is as ambiguous as "1,000" (round-9 review, Codex M1)."""
    s = _ascii_digits((text or "").strip())
    if "," in s and "." in s:
        return True
    mantissa = _EXPONENT.split(s, maxsplit=1)[0].strip()
    if mantissa[:1] in ("+", "-"):
        mantissa = mantissa[1:].strip()
    return _GROUPED.fullmatch(mantissa) is not None


def decimal_text(text: str) -> str:
    """`text` stripped, its decimal comma replaced by a point (for ``float()``).  ValueError for
    ambiguous text (:func:`is_ambiguous`), with the text as typed in the message."""
    s = (text or "").strip()
    if is_ambiguous(s):
        raise ValueError(f"ambiguous number {s!r}: thousands separator or decimal comma? "
                         "Write it without a thousands separator (1000, 1.5 or 1,5)")
    return s.replace(",", ".")

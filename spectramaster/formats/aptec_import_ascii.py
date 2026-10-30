"""Text spectrum formats imported by Aptec MCA v6.31 (codes 60-69).

Every layout below was recovered by disassembling the 16-bit import-converter
DLLs shipped with Aptec MCA v6.31 (``C:\\APTEC\\APTEC\\CONVERT\\*.dll``, NE format,
Aptec-NRC "PCMCA/SUPER Windows Library").  Each DLL exports
``OpenFileSpectrum`` (reader) and, for some, ``SaveFileSpectrum`` (writer); the
readers fill the same in-memory header that Aptec saves as ``*.S0`` (offsets as
documented in ``aptec.py``: 0x020 label, 0x04A title, 0x07A detector ID,
0x08A geometry ID, 0x09A sample ID, 0x286 energy coefficients, 0x316 channels,
0x31A acquisition start, 0x32A real ms, 0x332 live ms) through PCMCA.DLL helper
functions (ReadLineFromFile, AsciiToLong/Double, MakeTDS(year, month, day, h, m,
s, 1/100), ValidSpectrumSize = round DOWN to a power of two 256..16384).
Keyword strings come from each DLL's string table; numeric constants (1000,
-100, 1) from its data segment.  No public specification or genuine sample
file of these formats was available (web search not possible, no samples on
this machine), so the DLL code is the only source.  Notes on what Aptec does
are given so its behaviour can be reproduced; our readers are a bit more
tolerant than Aptec but never interpret a field differently.

Code 60 ``aptec_ascii``  Aptec ASCII *.APT  (aptascii.dll, reader + writer)
    Lines ``KEY: value`` with the keys TITLE: (-> header 0x020 label, our
    ``description``), LABEL: (-> 0x04A title, our ``sample_id``), USER ID:,
    DETECTOR ID:, GEOMETRY ID:, ACQ START TIME: hh:mm:ss, ACQ START DATE:
    MM/DD/YYYY, ACQ TRUE TIME: s, ACQ LIVE TIME: s, CHANNELS: n,
    ENERGY COEFF A0: .. A5: (polynomial, E = sum Ai*ch^i), and data lines
    ``channel: counts`` (0-based).  Aptec's *writer* quotes keys and string
    values (``"TITLE:" "abc"``) but its *reader* compares the bare line start
    with ``TITLE:`` and its number parser rejects a leading quote - so Aptec
    cannot read back the header of its own APT files.  Our writer therefore
    emits the unquoted form the reader understands; our reader accepts both.
    Data lines with channel >= CHANNELS (default 16384) are dropped by Aptec,
    so CHANNELS is written before the data.

Code 61 ``bti_ascii``  BTI ASCII *.BTI  (bti.dll, read only - Aptec has no writer)
    Line numbers 0-based: line 2 = label (leading blanks skipped); line 3 =
    acquisition date at fixed columns: month name at col 19, day 23, hour 26,
    minute 29, year 35 (4 digits) - i.e. a C ``ctime`` string "Www Mmm dd
    hh:mm:ss yyyy" starting at col 15 (Aptec reads the seconds at col 31,
    which is the ':' - so it always gets 0 s; we parse the ctime string);
    line 4 = live time in s after the first ':'; line 10 = dead time in %
    after the first ':' (real = live / (1 - DT/100)); lines >= 13 = pairs
    ``channel: counts`` (several per line).  Aptec sets the channel count to
    the largest power of two <= the highest channel number, so 0-based data
    0..8191 shows as 4096 channels.  Other header lines are not read and their
    content is unknown -> no writer is registered.

Code 62 ``chandata_csv``  Channel Data *.CSV  (chandata.dll, reader + writer)
    One line per channel: ``channel, energy, counts`` (Aptec writes
    ``%d, "%s", %ld`` with the energy as a 6-significant-digit string, or the
    channel number when uncalibrated).  Aptec's reader takes 15 characters
    after the first comma for the energy and its number parser rejects a
    leading quote, so with Aptec's own quoting the energy reads as 0.  Our
    writer leaves the energy unquoted.  Aptec builds a 2-point linear
    calibration from channel 1 and the highest channel; our reader fits all
    (channel, energy) pairs (linear, or quadratic when clearly better).

Code 63 ``ci90_ascii``  Canberra Series 90 ASCII *.O  (ci_90o.dll, read only)
    Token-based: wherever a token starts with ``Live =`` / ``True =`` the next
    token is live / real time in s; ``Collected at:`` is followed by
    ``hh:mm:ss.t dd-Mon-yy[yy]`` (':' '-' '.' act as separators, t = tenths);
    after a line starting with ``Channel#`` every line whose first token is a
    multiple of 5 contributes the remaining tokens as counts, appended in file
    order (the label itself is not used as an index).  Aptec zeroes channels
    0 and 1 (Series 90 kept times there) and keeps the largest power of two
    <= the number of values.  No writer is registered (the rest of a genuine
    Series 90 listing is unknown).

Code 64 ``davidson_ascii``  Davidson ASCII *.DAV  (davidson.dll, reader + writer)
    Writer layout (verbatim from the DLL)::

        <blank>
        <blank>
        HH:MM   MM/DD/YY   ID=<sample id %-15s> ACQ AT HH:MM:SS   MM/DD/YY
        LIVE TIME=%5lu S  REAL TIME=%5lu S  MEMORY= 1 OF 1 A
        <blank>
        DETECTOR=<%-10s> LLD=%d
        AMP POLARITY=POS    ULD=%d
        AMP GAIN=0          ZERO LEVEL=%d
        HVPS=0    VOLTS     THRESHOLD=0
        STABILIZER=OFF      P.U.REJECTOR=OFF
        <blank>
        CH%4d %7ld %7ld %7ld %7ld %7ld %7ld %7ld %7ld     (0-based channel)
        ^D

    (first time/date = time of writing).  Aptec's reader searches the keywords
    in fixed column windows (CH 0-8, ID= / REAL TIME= / LLD= / ULD= /
    ZERO LEVEL= 18-26, ACQ AT 36-44, LIVE TIME= / DETECTOR= 0-8) and reads the
    eight counts at fixed 8-character steps after the channel number.

Code 65 ``iaea_ascii_dat``  IAEA ASCII *.DAT  (iaea.dll, reader + writer)
    The EML/C.G. Sanderson intercomparison layout (also code 17): optional
    header line ``<title> LT=<live s> ST=dd-Mmm-yy hh:mm:ss`` then 10 counts per
    line.  Aptec: header present if the first line contains anything but
    digits and blanks; every data line yields exactly 10 values; live = LT
    (else channel 0), real = channel 1 (raised to live if smaller), then
    channels 0 and 1 are zeroed; channel count = largest power of two <= the
    number of values.  Without a header the first token of each line is
    skipped (channel label) and Aptec invents 400 s / 15-May-1986 - our reader
    leaves the times unset instead.  Our writer stores live/real seconds in
    channels 0/1 (as the reader expects), like the EML files.

Code 66 ``npl_ascii``  NPL ASCII *.TXT  (npl_txt.dll, reader + writer)
    Writer: blank line, `` Channel Contents for "<file name>"``, two blank
    lines, `` Channel``, blank line, then ``%5d: %8ld x 8`` with 1-BASED channel
    numbers; channel 1 holds the live time and channel 2 the real time in
    whole seconds.  Reader: any line ``<digits> : v1 .. v8``.

Code 67 ``rump_ascii``  Rump ASCII *.MAC  (rump.dll, reader + writer)
    RUMP (RBS analysis) layout written by the DLL: EMPTY / FILE name /
    IDENTIFIER '...' / DATE 'yy MON dd' / MEV .. / BEAM .. / CHARGE .. /
    CURRENT .. / GEOMETRY .. / THETA .. / PHI .. / CONVERSION .. / CHOFF .. /
    FWHM .. / OMEGA .. / CORRECTION .. / SWALLOW, then 8 tab-separated counts
    per line from line 17 on, then ``ACTIVE``.  Values are at column 14.  Aptec
    reads line 2 (identifier -> sample ID), line 3 (date: year at col 15, month
    name col 18, day col 22) and line 8 (geometry); no times.  The DLL writes
    day and year with ``%d``, which breaks those fixed columns for values < 10;
    our writer zero-pads them.  The DLL always writes the identifier
    '4MeV He+ on Au'; we write the sample ID there (Aptec reads 16 characters
    from col 14, quote included, so 14 characters fit).

Code 68 ``wallac_ascii``  Wallac ASCII *.001  (wallac.dll, reader + writer)
    Two header lines (skipped by Aptec), one line with the counting time in
    seconds (used as live and real time), then exactly 1024 lines of one
    count each.  Our writer pads shorter spectra with zeros and refuses
    longer ones.

Code 69 ``laval_ascii``  Laval ASCII *.DE?  (laval.dll, reader + writer)
    One value per line: live s, real s, sample date YYMMDD, acquisition date
    YYMMDD, detector ID, sample quantity, geometry ID, energy slope, energy
    offset, N = channel count, then the counts of channels 11..N-1 (channels
    0-10 are not stored), followed by ``0``, ``0`` and a blank line.  Only a
    linear calibration is stored (a higher-order one is refitted).
"""
from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..model import Spectrum
from .ascii_formats import _decode, fit_calibration
from .base import FormatError, FormatSpec, register

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_INT = re.compile(r"^[+-]?\d+$")


# ================================================================ helpers
def _lines(path: Path) -> list[str]:
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise FormatError(str(exc)) from exc
    if b"\x00" in raw[:4096]:
        raise FormatError("binary file")
    text = _decode(raw).replace("\x04", "")
    return text.splitlines()


def _head_lines(head: bytes) -> Optional[list[str]]:
    if b"\x00" in head:
        return None
    lines = _decode(head).replace("\x04", "").splitlines()
    if len(head) >= 4096 and lines:
        lines = lines[:-1]                # last line may be cut
    return lines


def _write(path: Path, lines: list[str], tail: str = "") -> None:
    data = "".join(l + "\r\n" for l in lines) + tail
    Path(path).write_bytes(data.encode("cp1256", errors="replace"))


def _ival(c) -> int:
    return int(round(float(c)))


def _abs_counts(spec: Spectrum) -> list[int]:
    """Counts indexed by absolute channel number (leading zeros for an offset)."""
    if len(spec.counts) == 0:
        raise FormatError("empty spectrum")
    return [0] * max(spec.first_channel, 0) + [_ival(c) for c in spec.counts]


def _year(y: int) -> int:
    if y < 100:
        return 2000 + y if y < 70 else 1900 + y
    return y


def _mk_date(y, mo, d, h=0, mi=0, s=0, us=0) -> Optional[datetime]:
    try:
        return datetime(_year(int(y)), int(mo), int(d), int(h), int(mi), int(s), int(us))
    except (ValueError, TypeError):
        return None


def _month(name: str) -> Optional[int]:
    n = name.strip()[:3].upper()
    return _MONTHS.index(n) + 1 if n in _MONTHS else None


def _lead_long(s: str) -> int:
    """C atol(): leading blanks, optional sign, digits; 0 if none."""
    m = re.match(r"\s*([+-]?\d+)", s)
    return int(m.group(1)) if m else 0


def _lead_float(s: str) -> Optional[float]:
    m = re.match(r"\s*([+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?)", s)
    return float(m.group(1)) if m else None


def _secs(ms_or_s) -> float:
    return float(ms_or_s) if ms_or_s is not None else 0.0


def _refit(spec: Spectrum, terms: int) -> list[float]:
    coeffs = list(spec.energy_coeffs)
    while coeffs and coeffs[-1] == 0.0:
        coeffs.pop()
    if len(coeffs) <= terms:
        return coeffs
    from ..convert import fit_calibration as _fit   # local import: convert imports formats
    new, _err = _fit(spec, terms)
    return new


def _pow2_floor(n: int) -> int:
    for p in (16384, 8192, 4096, 2048, 1024, 512, 256):
        if n >= p:
            return p
    return 256


# ============================================================ 60 Aptec ASCII
_APT_KEYS = ["TITLE:", "LABEL:", "USER ID:", "DETECTOR ID:", "GEOMETRY ID:", "ACQ START TIME:",
             "ACQ START DATE:", "ACQ TRUE TIME:", "ACQ LIVE TIME:", "CHANNELS:"] + \
            [f"ENERGY COEFF A{i}:" for i in range(6)]
_APT_DATA = re.compile(r'^"?(\d{1,12})"?:\s*"?\s*([+-]?\d+)')


def _apt_split(line: str) -> Optional[tuple[str, str]]:
    s = line.strip()
    bare = s.lstrip('"')
    up = bare.upper()
    for k in _APT_KEYS:
        if up.startswith(k):
            rest = bare[len(k):].strip()
            if s.startswith('"') and rest.startswith('"'):
                rest = rest[1:].strip()              # closing quote of a quoted key
            if len(rest) >= 2 and rest[0] == '"' and rest[-1] == '"':
                rest = rest[1:-1]                    # quoted value (Aptec's writer)
            return k, rest.strip()
    return None


def read_aptec_ascii(path: Path) -> list[Spectrum]:
    spec = Spectrum(counts=[])
    data: dict[int, int] = {}
    nch: Optional[int] = None
    t = d = None
    coeffs: dict[int, float] = {}
    for line in _lines(path):
        m = _APT_DATA.match(line.strip())
        if m:
            data[int(m.group(1))] = int(m.group(2))
            continue
        kv = _apt_split(line)
        if kv is None:
            continue
        k, v = kv
        if k == "TITLE:":
            spec.description = v
        elif k == "LABEL:":
            spec.sample_id = v
        elif k == "USER ID:":
            spec.extra["user_id"] = v
        elif k == "DETECTOR ID:":
            spec.detector = v
        elif k == "GEOMETRY ID:":
            spec.extra["geometry_id"] = v
        elif k == "ACQ START TIME:":
            t = [int(x) for x in re.findall(r"\d+", v)[:3]]
        elif k == "ACQ START DATE:":
            d = [int(x) for x in re.findall(r"\d+", v)[:3]]
        elif k == "ACQ TRUE TIME:":
            spec.real_time = _lead_float(v)
        elif k == "ACQ LIVE TIME:":
            spec.live_time = _lead_float(v)
        elif k == "CHANNELS:":
            nch = _lead_long(v) or None
        elif k.startswith("ENERGY COEFF A"):
            f = _lead_float(v)
            if f is not None:
                coeffs[int(k[14])] = f
    if not data:
        raise FormatError("no 'channel: counts' lines")
    if nch and max(data) + 1 < nch:
        # one "channel: counts" line per channel up to CHANNELS - 1 (Aptec's writer and ours):
        # data that stop early come from a truncated or partially copied file. Missing lines
        # inside the range still read as 0, as in Aptec's own reader (zeroed memory).
        raise FormatError(f"{Path(path).name}: truncated Aptec ASCII file: CHANNELS: {nch}, "
                          f"last data line is channel {max(data)}")
    n = nch if nch else max(data) + 1
    spec.counts = [data.get(i, 0) for i in range(n)]
    if d and len(d) == 3:
        t = (t + [0, 0, 0])[:3] if t else [0, 0, 0]
        spec.start_time = _mk_date(d[2], d[0], d[1], *t)
    if coeffs:
        order = max(coeffs)
        spec.energy_coeffs = [coeffs.get(i, 0.0) for i in range(order + 1)]
    return [spec]


def write_aptec_ascii(spec: Spectrum, path: Path) -> None:
    counts = _abs_counts(spec)
    st = spec.start_time
    lines = [f"TITLE: {spec.description.splitlines()[0] if spec.description else ''}"[:7 + 41].rstrip(),
             f"LABEL: {spec.sample_id}"[:7 + 31].rstrip(),
             f"USER ID: {spec.extra.get('user_id', '')}"[:9 + 15].rstrip(),
             f"DETECTOR ID: {spec.detector}"[:13 + 15].rstrip(),
             f"GEOMETRY ID: {spec.extra.get('geometry_id', '')}"[:13 + 15].rstrip()]
    if st:
        lines += [f"ACQ START TIME: {st:%H:%M:%S}", f"ACQ START DATE: {st.month:02d}/{st.day:02d}/{st.year}"]
    lt, rt = spec.live_time, spec.real_time
    if rt is not None:
        lines.append(f"ACQ TRUE TIME: {rt:.3f}")
    if lt is not None:
        lines.append(f"ACQ LIVE TIME: {lt:.3f}")
    lines.append(f"CHANNELS: {len(counts)}")
    coeffs = list(spec.energy_coeffs)
    while coeffs and coeffs[-1] == 0.0:
        coeffs.pop()
    if len(coeffs) > 6:
        coeffs = _refit(spec, 6)
    for i, c in enumerate(coeffs):
        lines.append(f"ENERGY COEFF A{i}: {c:.12g}")
    lines += [f"{i}: {c}" for i, c in enumerate(counts)]
    _write(path, lines)


def sniff_aptec_ascii(path: Path, head: bytes) -> bool:
    lines = _head_lines(head)
    if not lines:
        return False
    keys = sum(1 for l in lines[:40] if _apt_split(l))
    data = sum(1 for l in lines[:80] if _APT_DATA.match(l.strip()))
    return keys >= 3 and data >= 1 or (keys >= 1 and data >= 1 and path.suffix.lower() == ".apt")


# ============================================================== 61 BTI ASCII
_CTIME = re.compile(r"([A-Za-z]{3})\s+(\d{1,2})\s+(\d{1,2}):(\d{2}):(\d{2})\s+(\d{4})")
_PAIR = re.compile(r"(\d+)\s*:\s*([+-]?\d+)")


def _after_colon(line: str) -> Optional[float]:
    if ":" not in line:
        return None
    return _lead_float(line.split(":", 1)[1])


def read_bti(path: Path) -> list[Spectrum]:
    lines = _lines(path)
    if len(lines) < 14:
        raise FormatError("too short for a BTI ASCII file")
    spec = Spectrum(counts=[])
    spec.description = lines[2].strip()
    m = _CTIME.search(lines[3])
    if m and _month(m.group(1)):
        spec.start_time = _mk_date(m.group(6), _month(m.group(1)), m.group(2),
                                   m.group(3), m.group(4), m.group(5))
    else:                                     # Aptec's fixed columns
        l3 = lines[3].ljust(40)
        mo = _month(l3[19:22])
        if mo:
            spec.start_time = _mk_date(_lead_long(l3[35:39]), mo, _lead_long(l3[23:25]),
                                       _lead_long(l3[26:28]), _lead_long(l3[29:31]), 0)
    spec.live_time = _after_colon(lines[4])
    dt = _after_colon(lines[10])
    if spec.live_time is not None and dt is not None and dt < 100:
        spec.real_time = spec.live_time / (1.0 - dt / 100.0)
        spec.extra["dead_time_percent"] = dt
    data: dict[int, int] = {}
    for l in lines[13:]:
        for ch, v in _PAIR.findall(l):
            data[int(ch)] = int(v)
    if not data:
        raise FormatError("no 'channel: counts' pairs from line 14 on")
    spec.counts = [data.get(i, 0) for i in range(max(data) + 1)]
    spec.extra["header"] = "\n".join(l.rstrip() for l in lines[:13])
    return [spec]


def _bti_test_file(spec: Spectrum, path: Path, aptec_pad: bool = True) -> None:
    """Minimal file in the layout Aptec's BTI importer reads (verification only).

    Header lines Aptec ignores are placeholders.  With ``aptec_pad`` a zero entry
    for channel N is appended so that Aptec (largest power of two <= highest
    channel number) keeps all N channels."""
    counts = _abs_counts(spec)
    st = spec.start_time or datetime(2000, 1, 1)
    lt = spec.live_time or 0.0
    rt = spec.real_time or lt
    dt = 100.0 * (rt - lt) / rt if rt else 0.0
    ctime = st.strftime("%a %b ") + f"{st.day:02d} {st:%H:%M:%S} {st.year}"
    lines = ["BTI ASCII spectrum", "written by SpectraMaster (test file)",
             " " + (spec.description or spec.sample_id or "Spectrum")[:41],
             "Acquired on  : " + ctime,
             f"Live time (s): {lt:.2f}", "", "", "", "", "",
             f"Dead time (%): {dt:.4f}", "", ""]
    pairs = list(enumerate(counts)) + ([(len(counts), 0)] if aptec_pad else [])
    for i in range(0, len(pairs), 8):
        lines.append("".join(f"{c:6d}:{v:9d}" for c, v in pairs[i:i + 8]))
    _write(path, lines)


def sniff_bti(path: Path, head: bytes) -> bool:
    if path.suffix.lower() != ".bti":
        return False
    lines = _head_lines(head)
    return bool(lines) and len(lines) > 14 and ":" in lines[4] and \
        len(_PAIR.findall(lines[13])) >= 1


# ============================================================ 62 Channel Data
_CSV_LINE = re.compile(r'^\s*(\d+)\s*,\s*"?\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*"?\s*,\s*([+-]?\d+)\s*$')


def read_chandata(path: Path) -> list[Spectrum]:
    rows = []
    for l in _lines(path):
        m = _CSV_LINE.match(l)
        if m:
            rows.append((int(m.group(1)), float(m.group(2)), int(m.group(3))))
    if not rows:
        raise FormatError("no 'channel, energy, counts' lines")
    n = max(r[0] for r in rows) + 1
    counts = [0] * n
    for ch, _e, c in rows:
        counts[ch] = c
    spec = Spectrum(counts=counts)
    chans = [float(r[0]) for r in rows]
    ens = [r[1] for r in rows]
    if any(e != c for e, c in zip(ens, chans)):        # energy == channel means uncalibrated
        try:
            spec.energy_coeffs = fit_calibration(chans, ens)
        except ValueError:
            pass
    return [spec]


def write_chandata(spec: Spectrum, path: Path) -> None:
    counts = _abs_counts(spec)
    lines = []
    for i, c in enumerate(counts):
        e = spec.energy_of(i) if spec.energy_coeffs else float(i)
        es = f"{e:.6g}"
        if "e" in es:
            es = f"{e:.4f}"
        lines.append(f"{i}, {es}, {c}")
    _write(path, lines)


def sniff_chandata(path: Path, head: bytes) -> bool:
    return path.suffix.lower() == ".csv" and content_chandata(path, head)


def content_chandata(path: Path, head: bytes) -> bool:
    lines = _head_lines(head)
    if not lines:
        return False
    ms = [_CSV_LINE.match(l) for l in lines[:20] if l.strip()]
    if len(ms) < 5 or not all(ms):
        return False
    ch = [int(m.group(1)) for m in ms]
    return all(b - a == 1 for a, b in zip(ch, ch[1:]))


# ============================================================== 63 CI 90 .O
def _ci90_tokens(line: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group()) for m in re.finditer(r"\S+", line)]


def read_ci90(path: Path) -> list[Spectrum]:
    lines = _lines(path)
    spec = Spectrum(counts=[])
    counts: list[int] = []
    in_data = False
    for line in lines:
        if in_data:
            toks = line.split()
            if toks and _INT.match(toks[0]) and int(toks[0]) % 5 == 0:
                counts += [_lead_long(t) for t in toks[1:]]
            continue
        low = line.lower()
        for kw, attr in (("live =", "live_time"), ("true =", "real_time")):
            for m in re.finditer(re.escape(kw), low):
                if m.start() == 0 or line[m.start() - 1].isspace():
                    v = _lead_float(line[m.end() + 1:]) if m.end() < len(line) else None
                    if v is not None:
                        setattr(spec, attr, v)
        i = low.find("collected at:")
        if i >= 0:
            rest = re.sub(r"[:\-.]", " ", line[i + 14:]).split()
            try:
                h, mi, s, tenth, day = (int(x) for x in rest[:5])
                mo = _month(rest[5])
                y = int(rest[6])
                spec.start_time = _mk_date(y, mo, day, h, mi, s, tenth * 100000)
            except (ValueError, IndexError, TypeError):
                pass
        if line.lstrip().lower().startswith("channel#"):
            in_data = True
    if not counts:
        raise FormatError("no 'Channel#' data block")
    counts[0:2] = [0] * min(2, len(counts))           # Aptec: channels 0/1 hold times
    spec.counts = counts
    return [spec]


def _ci90_test_file(spec: Spectrum, path: Path) -> None:
    """Minimal file in the layout Aptec's CI 90 importer reads (verification only)."""
    counts = _abs_counts(spec)
    lt = spec.live_time or 0.0
    rt = spec.real_time or lt
    lines = [" Canberra Series 90 listing (SpectraMaster test file)",
             f" {spec.sample_id or 'Spectrum'}", "",
             f" Live = {lt:.2f}   True = {rt:.2f}"]
    st = spec.start_time
    if st:
        lines.append(f" Collected at: {st:%H:%M:%S}.{st.microsecond // 100000} "
                     f"{st.day:02d}-{_MONTHS[st.month - 1].title()}-{st.year}")
    lines += ["", " Channel#"]
    for i in range(0, len(counts), 5):
        lines.append(f"{i:8d}" + "".join(f"{v:10d}" for v in counts[i:i + 5]))
    _write(path, lines)


def sniff_ci90(path: Path, head: bytes) -> bool:
    if path.suffix.lower() != ".o":
        return False
    lines = _head_lines(head)
    return bool(lines) and any(l.lstrip().lower().startswith("channel#") for l in lines) and \
        any("live =" in l.lower() for l in lines)


# ============================================================ 64 Davidson
def read_davidson(path: Path) -> list[Spectrum]:
    spec = Spectrum(counts=[])
    data: dict[int, int] = {}
    for line in _lines(path):
        m = re.match(r"^\s{0,8}CH\s*(\d+)((?:\s+[+-]?\d+)*)\s*$", line)
        if m:
            ch = int(m.group(1))
            for k, v in enumerate(m.group(2).split()):
                data[ch + k] = int(v)
            continue
        m = re.search(r"ACQ AT\s?(\d{1,2}):(\d{1,2}):(\d{1,2})\s+(\d{1,2})/(\d{1,2})/(\d{2,4})", line)
        if m:
            h, mi, s, mo, d, y = m.groups()
            spec.start_time = _mk_date(y, mo, d, h, mi, s)
        m = re.search(r"ID=(.*?)(\s+ACQ AT|$)", line)
        if m and "ID=" in line:
            spec.sample_id = m.group(1).strip()
        for kw, attr in (("LIVE TIME=", "live_time"), ("REAL TIME=", "real_time")):
            m = re.search(re.escape(kw) + r"\s*([\d.]+)", line)
            if m:
                setattr(spec, attr, float(m.group(1)))
        m = re.search(r"DETECTOR=(.*?)(\s+LLD=|$)", line)
        if m:
            spec.detector = m.group(1).strip()
        for kw in ("LLD", "ULD", "ZERO LEVEL"):
            m = re.search(r"(?<![A-Z])" + kw + r"=\s*([+-]?\d+)", line)
            if m:
                spec.extra[kw.lower().replace(" ", "_")] = int(m.group(1))
    if not data:
        raise FormatError("no 'CH' data lines")
    spec.counts = [data.get(i, 0) for i in range(max(data) + 1)]
    return [spec]


def write_davidson(spec: Spectrum, path: Path) -> None:
    counts = _abs_counts(spec)
    while len(counts) % 8:
        counts.append(0)
    now = datetime.now()
    st = spec.start_time
    if st:
        acq = f"{st:%H:%M:%S}   {st.month:02d}/{st.day:02d}/{st.year % 100:02d}"
    else:
        acq = "00:00:00   01/01/00"
    lt = int(round(_secs(spec.live_time)))
    rt = int(round(_secs(spec.real_time if spec.real_time is not None else spec.live_time)))
    ex = spec.extra
    lines = ["", "",
             f"{now:%H:%M}   {now.month:02d}/{now.day:02d}/{now.year % 100:02d}   "
             f"ID={spec.sample_id[:15]:<15} ACQ AT {acq}",
             f"LIVE TIME={lt:5d} S  REAL TIME={rt:5d} S  MEMORY= 1 OF 1 A", "",
             f"DETECTOR={spec.detector[:10]:<10} LLD={int(ex.get('lld', 0) or 0)}",
             f"AMP POLARITY=POS    ULD={int(ex.get('uld', 0) or 0)}",
             f"AMP GAIN=0          ZERO LEVEL={int(ex.get('zero_level', 0) or 0)}",
             "HVPS=0    VOLTS     THRESHOLD=0",
             "STABILIZER=OFF      P.U.REJECTOR=OFF", ""]
    for i in range(0, len(counts), 8):
        lines.append(f"CH{i:4d}" + "".join(f" {v:7d}" for v in counts[i:i + 8]))
    _write(path, lines, "\x04")


def sniff_davidson(path: Path, head: bytes) -> bool:
    lines = _head_lines(head)
    if not lines:
        return False
    txt = "\n".join(lines[:20])
    return "LIVE TIME=" in txt and "REAL TIME=" in txt and \
        any(re.match(r"^CH\s*\d+(\s+\d+){8}\s*$", l) for l in lines[:40])


# ====================================================== 65 IAEA ASCII (.DAT)
def read_iaea_dat(path: Path) -> list[Spectrum]:
    lines = _lines(path)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        raise FormatError("empty file")
    spec = Spectrum(counts=[])
    header = bool(re.search(r"[^\d ]", lines[0].strip())) if lines[0].strip() else True
    body = lines[1:] if header else lines
    vals: list[int] = []
    for l in body:
        toks = l.split()
        if not header and toks:
            toks = toks[1:]
        if not toks:
            continue
        if not all(_INT.match(t) for t in toks):
            raise FormatError(f"non-numeric data line {l[:40]!r}")
        vals += [int(t) for t in toks]
    if not vals:
        raise FormatError("no counts")
    if header:
        h = lines[0]
        spec.extra["header"] = h.rstrip()
        m = re.search(r"LT=", h)
        title = h[:m.start()] if m else h
        spec.sample_id = title.strip()
        if m:
            spec.live_time = float(_lead_long(h[m.end():]))
        st = re.search(r"ST=(\d{1,2}).([A-Za-z]{3}).(\d{2,4})\s+(\d{1,2}):(\d{2}):(\d{2})", h)
        if st and _month(st.group(2)):
            spec.start_time = _mk_date(st.group(3), _month(st.group(2)), st.group(1),
                                       st.group(4), st.group(5), st.group(6))
        if spec.live_time is None and vals:
            spec.live_time = float(vals[0])
        if len(vals) > 1:
            spec.real_time = max(float(vals[1]), spec.live_time or 0.0)
        vals[0:2] = [0] * min(2, len(vals))
    spec.counts = vals
    return [spec]


def write_iaea_dat(spec: Spectrum, path: Path) -> None:
    counts = _abs_counts(spec)
    lt = int(round(_secs(spec.live_time)))
    rt = int(round(_secs(spec.real_time if spec.real_time is not None else spec.live_time)))
    vals = list(counts)
    vals[0:2] = [lt, rt][:len(vals)]
    title = " ".join(spec.sample_id.split()) or "SPECTRUM"
    if not re.search(r"[^\d ]", title):
        title = "SPECTRUM " + title
    st = spec.start_time
    hdr = f"{title[:17]:<18}LT={lt:9d}"
    if st:
        hdr += f" ST={st.day:02d}-{_MONTHS[st.month - 1]}-{st.year % 100:02d} {st:%H:%M:%S}"
    width = max(7, len(str(max(abs(v) for v in vals))) + 1)
    lines = [hdr]
    for i in range(0, len(vals), 10):
        lines.append("".join(f"{v:{width}d}" for v in vals[i:i + 10]))
    _write(path, lines)


def sniff_iaea_dat(path: Path, head: bytes) -> bool:
    return path.suffix.lower() == ".dat" and content_iaea_dat(path, head)


def content_iaea_dat(path: Path, head: bytes) -> bool:
    lines = _head_lines(head)
    if not lines or len(lines) < 4 or "LT=" not in lines[0]:
        return False
    return all(len(l.split()) == 10 and all(_INT.match(t) for t in l.split()) for l in lines[1:4])


# ============================================================ 66 NPL ASCII
_NPL_LINE = re.compile(r"^\D*?(\d+)\s*:(.*)$")


def read_npl(path: Path) -> list[Spectrum]:
    data: dict[int, int] = {}
    spec = Spectrum(counts=[])
    for line in _lines(path):
        m = re.search(r'Channel Contents for\s+"([^"]*)"', line)
        if m:
            spec.extra["npl_file_name"] = m.group(1)
            continue
        m = _NPL_LINE.match(line)
        if not m or not re.match(r"^\s*\d+\s*:", line):
            continue
        n = int(m.group(1))
        vals = re.findall(r"\d+", m.group(2))[:8]
        for i, v in enumerate(vals):
            if n + i >= 1:
                data[n + i - 1] = int(v)
    if not data:
        raise FormatError("no 'channel: v1 .. v8' lines")
    counts = [data.get(i, 0) for i in range(max(data) + 1)]
    spec.live_time = float(counts[0])
    if len(counts) > 1:
        spec.real_time = float(counts[1])
    counts[0:2] = [0] * min(2, len(counts))
    spec.counts = counts
    return [spec]


def write_npl(spec: Spectrum, path: Path) -> None:
    counts = _abs_counts(spec)
    while len(counts) % 8:
        counts.append(0)
    counts[0] = int(round(_secs(spec.live_time)))
    counts[1] = int(round(_secs(spec.real_time if spec.real_time is not None else spec.live_time)))
    lines = ["", f' Channel Contents for "{Path(path).name.upper()}"', "", "", " Channel", ""]
    for i in range(0, len(counts), 8):
        lines.append(f"{i + 1:5d}: " + " ".join(f"{v:8d}" for v in counts[i:i + 8]))
    _write(path, lines)


def sniff_npl(path: Path, head: bytes) -> bool:
    lines = _head_lines(head)
    if not lines:
        return False
    if any("Channel Contents for" in l for l in lines[:5]):
        return True
    rows = [l for l in lines[:30] if re.match(r"^\s*\d+:(\s+\d+){8}\s*$", l)]
    return len(rows) >= 5 and path.suffix.lower() == ".txt"


def content_npl(path: Path, head: bytes) -> bool:
    """Either branch of the NPL test, whatever the extension."""
    lines = _head_lines(head)
    if not lines:
        return False
    if any("Channel Contents for" in l for l in lines[:5]):
        return True
    return len([l for l in lines[:30] if re.match(r"^\s*\d+:(\s+\d+){8}\s*$", l)]) >= 5


# ============================================================ 67 Rump ASCII
_RUMP_KEYS = ("FILE", "IDENTIFIER", "DATE", "MEV", "BEAM", "CHARGE", "CURRENT", "GEOMETRY",
              "THETA", "PHI", "CONVERSION", "CHOFF", "FWHM", "OMEGA", "CORRECTION", "SWALLOW")


def read_rump(path: Path) -> list[Spectrum]:
    lines = _lines(path)
    if len(lines) < 18:
        raise FormatError("too short for a Rump file")
    spec = Spectrum(counts=[])
    spec.sample_id = lines[2][14:].strip().strip("'").strip()
    spec.extra["rump_file"] = lines[1][14:].strip()
    m = re.search(r"'\s*(\d{1,4})\s+([A-Za-z]{3})\s+(\d{1,2})\s*'", lines[3])
    if m and _month(m.group(2)):
        spec.start_time = _mk_date(m.group(1), _month(m.group(2)), m.group(3))
    spec.extra["geometry_id"] = lines[8][14:].strip()
    spec.extra["rump_header"] = "\n".join(l.rstrip() for l in lines[:17])
    counts: list[int] = []
    for l in lines[17:]:
        toks = l.split()
        if not toks:
            continue
        if not all(_INT.match(t) for t in toks):
            break                                   # "ACTIVE" trailer
        counts += [int(t) for t in toks]
    if not counts:
        raise FormatError("no counts after line 17")
    spec.counts = counts
    return [spec]


def write_rump(spec: Spectrum, path: Path) -> None:
    counts = _abs_counts(spec)
    while len(counts) % 8:
        counts.append(0)
    st = spec.start_time
    if st:
        date = f"'{st.year % 100:02d} {_MONTHS[st.month - 1]} {st.day:02d}'"
    else:
        date = "'00 JAN 01'"
    name = Path(path).name.upper()[:13]
    ident = " ".join(spec.sample_id.replace("'", " ").split())[:14] or "4MeV He+ on Au"
    lines = ["EMPTY", f"FILE          {name}", f"IDENTIFIER    '{ident}'",
             f"DATE          {date}",
             "MEV           4.000", "BEAM          4HE+", "CHARGE        1.00", "CURRENT       0.00",
             "GEOMETRY      Cornell", "THETA         20.0", "PHI           5.0",
             "CONVERSION    4.000    1.200", "CHOFF         0.00", "FWHM          20.0",
             "OMEGA         5.00", "CORRECTION    1.0000", "SWALLOW"]
    for i in range(0, len(counts), 8):
        lines.append("\t".join(str(v) for v in counts[i:i + 8]))
    lines += ["", "ACTIVE", ""]
    _write(path, lines)


def sniff_rump(path: Path, head: bytes) -> bool:
    lines = _head_lines(head)
    if not lines or len(lines) < 18:
        return False
    hits = sum(1 for l in lines[1:17] if l.split() and l.split()[0].upper() in _RUMP_KEYS)
    return hits >= 10


# =========================================================== 68 Wallac ASCII
WALLAC_CHANNELS = 1024


def read_wallac(path: Path) -> list[Spectrum]:
    lines = _lines(path)
    if len(lines) < 4:
        raise FormatError("too short for a Wallac file")
    t = _lead_float(lines[2])
    if t is None:
        raise FormatError("line 3 is not a counting time")
    counts = []
    for l in lines[3:3 + WALLAC_CHANNELS]:
        s = l.strip()
        if not s:
            counts.append(0)
            continue
        f = _lead_float(s)
        if f is None:
            raise FormatError(f"non-numeric count line {s[:30]!r}")
        counts.append(_ival(f))
    spec = Spectrum(counts=counts, live_time=t, real_time=t)
    spec.sample_id = lines[0].strip()
    spec.description = lines[1].strip()
    return [spec]


def write_wallac(spec: Spectrum, path: Path) -> None:
    counts = _abs_counts(spec)
    if len(counts) > WALLAC_CHANNELS:
        raise FormatError(f"Wallac ASCII holds exactly {WALLAC_CHANNELS} channels "
                          f"(this spectrum has {len(counts)}); rebin it first")
    counts += [0] * (WALLAC_CHANNELS - len(counts))
    t = spec.live_time if spec.live_time is not None else (spec.real_time or 0.0)
    lines = [spec.sample_id or "Spectrum", spec.description.splitlines()[0] if spec.description else "",
             f"{t:.2f}"] + [str(c) for c in counts]
    _write(path, lines)


def sniff_wallac(path: Path, head: bytes) -> bool:
    return path.suffix.lower() == ".001" and content_wallac(path, head)


def content_wallac_strict(path: Path, head: bytes) -> bool:
    """Without the extension: also exactly the 3 + WALLAC_CHANNELS lines the reader and writer use
    (empty header lines included, trailing empty lines not), which tells it from a
    one-count-per-line ASCII-1 file."""
    if not content_wallac(path, head):
        return False
    try:
        lines = Path(path).read_bytes().splitlines()
    except OSError:
        return False
    while lines and not lines[-1].strip():
        lines.pop()
    return len(lines) == 3 + WALLAC_CHANNELS


def content_wallac(path: Path, head: bytes) -> bool:
    lines = _head_lines(head)
    if not lines or len(lines) < 30:
        return False
    if _lead_float(lines[2]) is None or len(lines[2].split()) != 1:
        return False
    return all(_INT.match(l.strip()) for l in lines[3:30])


# ============================================================ 69 Laval ASCII
LAVAL_FIRST = 11


def read_laval(path: Path) -> list[Spectrum]:
    lines = _lines(path)
    if len(lines) < 11:
        raise FormatError("too short for a Laval file")
    spec = Spectrum(counts=[])
    spec.live_time = _lead_float(lines[0])
    spec.real_time = _lead_float(lines[1])

    def yymmdd(s: str) -> Optional[datetime]:
        s = s.strip()
        if re.fullmatch(r"\d{6}", s):
            return _mk_date(int(s[0:2]), int(s[2:4]), int(s[4:6]))
        return None
    sd = yymmdd(lines[2])
    if sd:
        spec.extra["sample_date"] = sd.isoformat()
    spec.start_time = yymmdd(lines[3])
    spec.detector = lines[4].strip()
    q = _lead_float(lines[5])
    if q is not None:
        spec.extra["sample_quantity"] = q
    spec.extra["geometry_id"] = lines[6].strip()
    slope, offset = _lead_float(lines[7]), _lead_float(lines[8])
    if slope:
        spec.energy_coeffs = [offset or 0.0, slope]
    n = _lead_long(lines[9])
    if n <= LAVAL_FIRST:
        raise FormatError("bad channel count on line 10")
    vals = []
    for l in lines[10:10 + n - LAVAL_FIRST]:
        vals.append(_lead_long(l))
    if len(vals) < n - LAVAL_FIRST:
        raise FormatError("file shorter than the channel count says")
    spec.counts = [0] * LAVAL_FIRST + vals
    return [spec]


def _dtoa(x: float) -> str:
    s = f"{x:.12g}"
    return s[:-1] if s.endswith(".") else s


def write_laval(spec: Spectrum, path: Path) -> None:
    counts = _abs_counts(spec)
    if len(counts) <= LAVAL_FIRST:
        raise FormatError("Laval ASCII needs more than 11 channels")
    lt = int(_secs(spec.live_time) + 0.5)
    rt = int(_secs(spec.real_time if spec.real_time is not None else spec.live_time) + 0.5)
    st = spec.start_time
    sd = spec.extra.get("sample_date")
    try:
        sdt = datetime.fromisoformat(str(sd)) if sd else st
    except ValueError:
        sdt = st

    def ymd(d: Optional[datetime]) -> str:
        return f"{d.year % 100:02d}{d.month:02d}{d.day:02d}" if d else "000000"
    coeffs = _refit(spec, 2) if spec.energy_coeffs else []
    c0 = coeffs[0] if coeffs else 0.0
    c1 = coeffs[1] if len(coeffs) > 1 else 0.0
    lines = [str(lt), str(rt), ymd(sdt), ymd(st), spec.detector[:15],
             _dtoa(float(spec.extra.get("sample_quantity", 0.0) or 0.0)),
             str(spec.extra.get("geometry_id", ""))[:15], _dtoa(c1), _dtoa(c0), str(len(counts))]
    lines += [str(c) for c in counts[LAVAL_FIRST:]]
    lines += ["0", "0"]
    _write(path, lines, "\r\n")


def sniff_laval(path: Path, head: bytes) -> bool:
    return re.fullmatch(r"\.de.", path.suffix.lower()) is not None and content_laval(path, head)


def content_laval(path: Path, head: bytes) -> bool:
    lines = _head_lines(head)
    if not lines or len(lines) < 15:
        return False
    return (_lead_float(lines[0]) is not None and _lead_float(lines[1]) is not None
            and re.fullmatch(r"\d{6}", lines[3].strip()) is not None
            and _INT.match(lines[9].strip()) is not None)


# ================================================================ registration
_SRC = "Layout reverse-engineered from Aptec MCA v6.31 "
register(FormatSpec(
    code=60, key="aptec_ascii", name="Aptec ASCII", extensions=[".apt"],
    reader=read_aptec_ascii, writer=write_aptec_ascii, sniffer=sniff_aptec_ascii, aliases=["apt"],
    notes=_SRC + "aptascii.dll. KEY: value header (times, date, channels, 6 energy coefficients) + "
          "'channel: counts'. Written unquoted (Aptec's own quoted form cannot be re-read by Aptec)."))
register(FormatSpec(
    code=61, key="bti_ascii", name="BTI ASCII (read only)", extensions=[".bti"],
    reader=read_bti, sniffer=sniff_bti, aliases=["bti"],
    notes=_SRC + "bti.dll (import only): label line 3, ctime date line 4, live time line 5, "
          "dead time % line 11, 'channel: counts' pairs from line 14."))
register(FormatSpec(
    code=62, key="chandata_csv", name="Aptec Channel Data CSV", extensions=[".csv"],
    reader=read_chandata, writer=write_chandata, sniffer=sniff_chandata, aliases=["chandata"],
    content_sniffer=content_chandata,
    notes=_SRC + "chandata.dll. 'channel, energy, counts' per line; no times."))
register(FormatSpec(
    code=63, key="ci90_ascii", name="Canberra Series 90 ASCII (read only)", extensions=[".o"],
    reader=read_ci90, sniffer=sniff_ci90, aliases=["ci90", "ci_90o"],
    notes=_SRC + "ci_90o.dll (import only): 'Live =', 'True =', 'Collected at:' and a 'Channel#' "
          "block (5 counts per line); channels 0/1 are zeroed as Aptec does."))
register(FormatSpec(
    code=64, key="davidson_ascii", name="Davidson ASCII", extensions=[".dav"],
    reader=read_davidson, writer=write_davidson, sniffer=sniff_davidson, aliases=["davidson"],
    notes=_SRC + "davidson.dll. Keyword header (ID=, ACQ AT, LIVE/REAL TIME=, DETECTOR=) + "
          "'CH nnnn' lines of 8 counts; no calibration."))
register(FormatSpec(
    code=65, key="iaea_ascii_dat", name="IAEA ASCII (Aptec, EML layout)", extensions=[".dat"],
    reader=read_iaea_dat, writer=write_iaea_dat, sniffer=sniff_iaea_dat, aliases=["iaea_dat"],
    content_sniffer=content_iaea_dat,
    notes=_SRC + "iaea.dll. Header '<title> LT= ST=' + 10 counts/line; channels 0/1 carry live/real "
          "seconds. Same files as code 17 (EML/Sanderson)."))
register(FormatSpec(
    code=66, key="npl_ascii", name="NPL ASCII", extensions=[".txt"],
    reader=read_npl, writer=write_npl, sniffer=sniff_npl, aliases=["npl"],
    content_sniffer=content_npl,
    notes=_SRC + "npl_txt.dll. '%5d: ' + 8 counts, 1-based channels; channels 1/2 = live/real s."))
register(FormatSpec(
    code=67, key="rump_ascii", name="Rump ASCII (RBS)", extensions=[".mac"],
    reader=read_rump, writer=write_rump, sniffer=sniff_rump, aliases=["rump"],
    notes=_SRC + "rump.dll. 17 RUMP header lines + 8 counts/line + ACTIVE; identifier, date, "
          "geometry only (no times, no calibration)."))
register(FormatSpec(
    code=68, key="wallac_ascii", name="Wallac ASCII (1024 ch)", extensions=[".001"],
    reader=read_wallac, writer=write_wallac, sniffer=sniff_wallac, aliases=["wallac"],
    content_sniffer=content_wallac_strict,
    notes=_SRC + "wallac.dll (import only in Aptec). 2 header lines, counting time, 1024 counts."))
register(FormatSpec(
    code=69, key="laval_ascii", name="Laval ASCII", extensions=[".de1"],
    reader=read_laval, writer=write_laval, sniffer=sniff_laval, aliases=["laval"],
    content_sniffer=content_laval,
    notes=_SRC + "laval.dll. One value per line: times, YYMMDD dates, detector, quantity, geometry, "
          "linear calibration, N, counts of channels 11..N-1."))

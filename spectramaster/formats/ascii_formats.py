"""Plain-text spectrum formats from the ORTEC DataMaster table (codes 5, 6, 8, 9).

Code 5  ``ascii1``   ASCII-1  (*.txt)  read/write
    One count per line.  DataMaster's manual gives no layout beyond the name, so
    the reader is tolerant: blank lines are skipped, non-numeric lines are kept
    as header text (first one -> ``sample_id``), and a ``#Key=Value`` trailer
    (HyperLab style) is understood.  The writer emits nothing but the counts.

Code 6  ``ascii2``   ASCII-2  (*.txt)  read/write
    Columns "channel counts" or "channel energy counts".  Separators may be
    commas, semicolons, tabs or spaces; header/title lines are skipped (a header
    naming the columns, e.g. ``channel,energy,counts``, is used to map them).
    When an energy column is present a polynomial (linear, or quadratic when it
    fits clearly better) is least-squares fitted to (channel, energy) and stored
    as ``energy_coeffs``.  The writer emits ``channel counts`` (two columns, no
    header) — the calibration is not representable in this format.

Code 8  ``iec1455``  IEC 1455 / IEC 61455 (= IEEE Std 1214-1992 content) *.iec  r/w
    Layout (from the IEC 1455 record list documented in becquerel's parser
    lbl-anp/becquerel ``parsers/iec1455.py``, SpecUtils ``SpecFile_lsrm.cpp``
    ``load_from_spectraline_iec`` and OpenGammaX ``readIEC1455``; checked against
    real InterWinner 2004 files on this lab's D: drive and against Canberra
    Genie 2000 ``FILECNVT /IEC1455``).  Every line is ``A004`` + a 64-character
    payload, CR LF terminated:

      rec 1   A8 system id, A8 sub-system id, I4 ADC, I4 segment, I6 digital offset
      rec 2   F14.2 live time, F14.2 real time, I6 number of channels
      rec 3   start "DD/MM/YY HH:MM:SS" [space + sample time "DD/MM/YY HH:MM:SS"]
              (Genie 2000 interprets 09/12/21 as 9-Dec-2021; InterWinner writes
              "28.07.04" with dots - both accepted)
      rec 4   4 x E15.8 energy polynomial coefficients c0..c3 (keV)
      rec 5   4 x E15.8 FWHM coefficients (+ optional exponent, InterWinner)
      rec 6-9 sample description, 64 chars each
      rec 10  spare
      rec 11-22  energy/channel pairs (4 x E16.9 per record = 2 pairs)
      rec 23-34  energy/resolution pairs
      rec 35-46  energy/efficiency pairs
      rec 47-58  user defined text
      rec 59-    I6 channel number + 5 x I10 counts; last record blank-padded
    If rec 4 is all zero but energy/channel pairs exist, a calibration is fitted
    from the pairs (as becquerel does).  Text is decoded UTF-8, else cp1256.

Code 9  ``ieee_asc`` IEEE ASCII *.asc  read/write
    DataMaster's "IEEE ASCII" is presumably IEEE Std 1214-1992, whose text is not
    publicly available, so this module does NOT claim to implement that standard.
    The reader accepts the .ASC layouts actually found in reference material:
      * IAEA G-1 intercomparison spectra (G.R. Gilmore distribution): a short
        text header, then 8 counts per line in I9 fields, DOS ^Z at the end;
        the README calls them 2000-channel spectra, but every file actually
        holds 2020 values (252 x 8 + 4), identical channel by channel to the
        matching S100 *.MCA of the same distribution (non-zero up to 2019).
      * HyperLab/k0-IAEA exports (IAEA TECDOC annexes): one count per line
        followed by ``#LiveTime=``, ``#TrueTime=``, ``#AcqStart=``,
        ``#LinEnergyCalParams=`` ... lines.
    The writer reproduces the G-1 layout (title line, description line, blank
    line, 8 x I9 per line, CR LF), as in the G-1 files.
    Live/real time and calibration are not representable in that layout.

Not implemented: code 12 ``sampo90`` (SAMPO 90 *.sam).  No public description of
the file layout was found (Genie 2000 can import it, but its layout is not
documented anywhere accessible), and no sample file was available, so nothing
is registered rather than guessing a format.
"""
from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..model import Spectrum
from .base import FormatError, FormatSpec, register

# ============================================================== shared helpers
_SPLIT = re.compile(r"[,\t; ]+")
_NUM = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def _decode(raw: bytes) -> str:
    raw = raw.replace(b"\x1a", b"")           # DOS end-of-file marker
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1256", errors="replace")


def _read_text(path: Path) -> str:
    try:
        return _decode(Path(path).read_bytes())
    except OSError as exc:
        raise FormatError(str(exc)) from exc


def _numeric_tokens(line: str) -> Optional[list[float]]:
    """Return the numbers of a line if *every* token is numeric, else None."""
    toks = [t for t in _SPLIT.split(line.strip()) if t]
    if not toks:
        return None
    if not all(_NUM.match(t) for t in toks):
        return None
    return [float(t) for t in toks]


def _count_value(x: float):
    return int(x) if float(x).is_integer() else float(x)


def _fmt_count(c) -> str:
    c = float(c)
    if c.is_integer():
        return str(int(c))
    return repr(c)


def _int_count(c) -> int:
    return int(round(float(c)))


def polyfit(xs: list[float], ys: list[float], degree: int) -> list[float]:
    """Least-squares polynomial fit (pure Python, centred for stability)."""
    n = len(xs)
    if n <= degree:
        raise ValueError("not enough points")
    xm = sum(xs) / n
    xc = [x - xm for x in xs]
    m = degree + 1
    a = [[sum(x ** (i + j) for x in xc) for j in range(m)] for i in range(m)]
    b = [sum(y * x ** i for x, y in zip(xc, ys)) for i in range(m)]
    # Gaussian elimination with partial pivoting
    for col in range(m):
        piv = max(range(col, m), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-300:
            raise ValueError("singular fit")
        a[col], a[piv] = a[piv], a[col]
        b[col], b[piv] = b[piv], b[col]
        for r in range(col + 1, m):
            f = a[r][col] / a[col][col]
            for k in range(col, m):
                a[r][k] -= f * a[col][k]
            b[r] -= f * b[col]
    p = [0.0] * m
    for r in range(m - 1, -1, -1):
        p[r] = (b[r] - sum(a[r][k] * p[k] for k in range(r + 1, m))) / a[r][r]
    # expand sum p_k (x - xm)^k into powers of x
    coeffs = [0.0] * m
    for k, pk in enumerate(p):
        for j in range(k + 1):
            coeffs[j] += pk * math.comb(k, j) * (-xm) ** (k - j)
    return coeffs


def fit_calibration(channels: list[float], energies: list[float]) -> list[float]:
    """Linear fit, upgraded to quadratic when it is clearly better."""
    pts = [(c, e) for c, e in zip(channels, energies) if math.isfinite(e)]
    if len(pts) < 2:
        return []
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if max(xs) == min(xs):
        return []
    lin = polyfit(xs, ys, 1)

    def rms(c):
        return math.sqrt(sum((sum(ci * x ** i for i, ci in enumerate(c)) - y) ** 2
                             for x, y in zip(xs, ys)) / len(xs))

    best = lin
    if len(pts) >= 4:
        try:
            quad = polyfit(xs, ys, 2)
            span = max(ys) - min(ys)
            if rms(lin) > 1e-6 * max(span, 1.0) and rms(quad) < 0.5 * rms(lin):
                best = quad
        except ValueError:
            pass
    return best


# ===================================================================== ASCII-1
def _parse_hash_trailer(line: str, spec: Spectrum) -> bool:
    """Handle '#Key=Value' lines (HyperLab ASC export). Returns True if consumed."""
    s = line.strip()
    if not s.startswith("#") or "=" not in s:
        return False
    key, _, val = s[1:].partition("=")
    key, val = key.strip(), val.strip()
    kl = key.lower()
    try:
        if kl == "livetime":
            spec.live_time = float(val)
        elif kl in ("truetime", "realtime"):
            spec.real_time = float(val)
        elif kl == "acqstart":
            spec.start_time = datetime.fromisoformat(val)
        elif kl == "title":
            spec.sample_id = val.split("  ")[0].strip() if val else spec.sample_id
            spec.extra["title"] = val
        elif kl == "comment":
            spec.description = val
        elif kl == "linenergycalparams":
            spec.energy_coeffs = [float(v) for v in val.split()]
        else:
            spec.extra[key] = val
    except ValueError:
        spec.extra[key] = val
    return True


def read_ascii1(path: Path) -> list[Spectrum]:
    text = _read_text(path)
    spec = Spectrum(counts=[])
    header: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if _parse_hash_trailer(line, spec):
            continue
        nums = _numeric_tokens(line)
        if nums is None:
            if len(spec.counts) == 0:
                header.append(line.strip())
            continue
        spec.counts.append(_count_value(nums[-1] if len(nums) == 2 else nums[0]))
    if len(spec.counts) == 0:
        raise FormatError("no counts found")
    if header:
        spec.sample_id = spec.sample_id or header[0]
        if len(header) > 1:
            spec.description = spec.description or " ".join(header[1:])
        spec.extra["header"] = "\n".join(header)
    return [spec]


def write_ascii1(spec: Spectrum, path: Path) -> None:
    with open(path, "w", encoding="ascii", newline="\r\n") as fh:
        for c in spec.counts:
            fh.write(_fmt_count(c) + "\n")


def _txt_numeric_lines(head: bytes, limit: int = 60) -> list[list[float]]:
    rows = []
    for line in _decode(head).splitlines()[:-1]:      # last line may be cut
        nums = _numeric_tokens(line)
        if nums is not None:
            rows.append(nums)
        if len(rows) >= limit:
            break
    return rows


def sniff_ascii1(path: Path, head: bytes) -> bool:
    if path.suffix.lower() != ".txt" or b"\x00" in head:
        return False
    rows = _txt_numeric_lines(head)
    return len(rows) >= 8 and all(len(r) == 1 for r in rows)


# ===================================================================== ASCII-2
def _header_map(line: str) -> Optional[dict]:
    toks = [t.strip().strip('"').lower() for t in _SPLIT.split(line.strip()) if t.strip()]
    if len(toks) < 2:
        return None
    m = {}
    for i, t in enumerate(toks):
        if t.startswith("chan") or t in ("ch", "#ch", "channel#"):
            m.setdefault("channel", i)
        elif t.startswith("energ") or t.startswith("kev") or t == "e":
            m.setdefault("energy", i)
        elif t.startswith("count") or t in ("cts", "data", "y"):
            m.setdefault("counts", i)
    return m if "counts" in m else None


def read_ascii2(path: Path) -> list[Spectrum]:
    text = _read_text(path)
    colmap: Optional[dict] = None
    header: list[str] = []
    rows: list[list[float]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        nums = _numeric_tokens(line)
        if nums is None:
            if not rows:
                header.append(line.strip())
                hm = _header_map(line)
                if hm:
                    colmap = hm
            continue
        rows.append(nums)
    if not rows:
        raise FormatError("no numeric rows found")
    ncols = max(set(len(r) for r in rows), key=lambda n: sum(1 for r in rows if len(r) == n))
    if ncols < 2:
        raise FormatError("ASCII-2 needs at least two columns (channel, counts)")
    rows = [r for r in rows if len(r) >= ncols]
    if colmap is None or max(colmap.values()) >= ncols:
        colmap = {"channel": 0, "counts": ncols - 1}
        if ncols >= 3:
            colmap["energy"] = 1
    ic, iy = colmap.get("channel"), colmap["counts"]
    ie = colmap.get("energy")
    if ic is None:
        chans = list(range(len(rows)))
    else:
        chans = [r[ic] for r in rows]
    if any(float(c) != int(c) for c in chans):
        raise FormatError("channel column is not integer")
    chans = [int(c) for c in chans]
    first = min(chans)
    n = max(chans) - first + 1
    if n > 4 * len(rows) + 1024:
        raise FormatError("channel numbers too sparse")
    counts: list = [0] * n
    for ch, r in zip(chans, rows):
        counts[ch - first] = _count_value(r[iy])
    spec = Spectrum(counts=counts, first_channel=first)
    if ie is not None:
        try:
            spec.energy_coeffs = fit_calibration([float(c) for c in chans], [r[ie] for r in rows])
        except ValueError:
            pass
    if header:
        spec.extra["header"] = "\n".join(header)
        if colmap is not None and _header_map(header[-1]) is not None:
            titles = header[:-1]
        else:
            titles = header
        if titles:
            spec.sample_id = titles[0]
    return [spec]


def write_ascii2(spec: Spectrum, path: Path) -> None:
    with open(path, "w", encoding="ascii", newline="\r\n") as fh:
        for i, c in enumerate(spec.counts):
            fh.write(f"{spec.first_channel + i}\t{_fmt_count(c)}\n")


def sniff_ascii2(path: Path, head: bytes) -> bool:
    if path.suffix.lower() != ".txt" or b"\x00" in head:
        return False
    rows = _txt_numeric_lines(head)
    if len(rows) < 8 or not all(2 <= len(r) <= 3 for r in rows):
        return False
    ch = [r[0] for r in rows]
    return all(b - a == 1 for a, b in zip(ch, ch[1:]))


# ================================================================== IEC 1455
_IEC_TAG = "A004"
_DATE_RE = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\s+(\d{1,2}):(\d{2}):(\d{2})")


def _iec_date(s: str) -> Optional[datetime]:
    m = _DATE_RE.search(s)
    if not m:
        return None
    a, b, y, hh, mm, ss = (int(g) for g in m.groups())
    if y < 100:
        y += 2000 if y < 80 else 1900
    for day, month in ((a, b), (b, a)):          # standard DD/MM, fallback MM/DD
        try:
            return datetime(y, month, day, hh, mm, ss)
        except ValueError:
            continue
    return None


def _floats_loose(s: str) -> list[float]:
    # InterWinner glues fields: "0.00000000E+000.50" -> split after exponent
    s = re.sub(r"([eE][+-]\d{2})", r"\1 ", s)
    out = []
    for t in s.split():
        try:
            out.append(float(t))
        except ValueError:
            pass
    return out


def read_iec(path: Path) -> list[Spectrum]:
    text = _read_text(path)
    recs: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line.startswith(_IEC_TAG):
            raise FormatError("line without A004 tag - not an IEC 1455 file")
        recs.append(line[4:].rstrip("\r\n"))
    if len(recs) < 6:
        raise FormatError("too few IEC 1455 records")
    spec = Spectrum(counts=[])
    r1 = recs[0].ljust(30)
    sys_id, sub_id = r1[0:8].strip(), r1[8:16].strip()
    spec.extra["iec_system_id"] = sys_id
    spec.extra["iec_subsystem_id"] = sub_id
    spec.detector = sub_id or sys_id
    offset = 0
    try:
        spec.extra["iec_adc"] = int(r1[16:20] or 0)
        spec.extra["iec_segment"] = int(r1[20:24] or 0)
        offset = int(r1[24:30] or 0)
    except ValueError:      # some writers do not respect the columns
        toks = recs[0].split()
        if len(toks) >= 3 and all(t.isdigit() for t in toks[-3:]):
            spec.extra["iec_adc"], spec.extra["iec_segment"] = int(toks[-3]), int(toks[-2])
            offset = int(toks[-1])
    spec.first_channel = offset
    r2 = recs[1].split()
    try:
        spec.live_time, spec.real_time, nch = float(r2[0]), float(r2[1]), int(float(r2[2]))
    except (IndexError, ValueError) as exc:
        raise FormatError("bad IEC record 2 (live, real, channels)") from exc
    spec.start_time = _iec_date(recs[2])
    rest = recs[2][17:]
    sample_t = _iec_date(rest)
    if sample_t:
        spec.extra["iec_sample_time"] = sample_t.isoformat()
    coeffs = _floats_loose(recs[3])[:4]
    if recs[4].strip():
        spec.extra["iec_record5"] = recs[4].rstrip()
    desc = [r.strip() for r in recs[5:9]]
    nonempty = [d for d in desc if d]
    if nonempty:
        spec.sample_id = nonempty[0]
        spec.description = "\n".join(nonempty[1:])
    pairs = []
    for r in recs[10:22]:
        v = _floats_loose(r)
        pairs += [(v[i], v[i + 1]) for i in range(0, len(v) - 1, 2) if v[i] or v[i + 1]]
    if any(coeffs):
        while coeffs and coeffs[-1] == 0.0:
            coeffs.pop()
        spec.energy_coeffs = coeffs
    elif len(pairs) >= 2:
        spec.energy_coeffs = fit_calibration([p[1] for p in pairs], [p[0] for p in pairs])
    if pairs:
        spec.extra["iec_energy_channel_pairs"] = " ".join(f"{e:g}:{c:g}" for e, c in pairs)
    users = [r.strip() for r in recs[46:58] if r.strip()]
    if users:
        spec.extra["iec_user_records"] = "\n".join(users)

    # spectral data: from record 59 on, rows "chan c1..c5" with chan advancing by 5
    counts: list = []
    expect = 0
    start = 58 if len(recs) > 58 else 5
    for r in recs[start:]:
        toks = r.split()
        if not toks or not all(re.fullmatch(r"[+-]?\d+(\.\d*)?", t) for t in toks):
            continue
        ch = int(float(toks[0]))
        if ch != expect or len(toks) > 6:
            if not counts:
                continue
            raise FormatError(f"IEC data record out of sequence at channel {ch}")
        counts += [_count_value(float(t)) for t in toks[1:]]
        expect += 5
        if len(counts) >= nch:
            break
    if not counts:
        raise FormatError("no IEC 1455 count records")
    if len(counts) > nch:
        counts = counts[:nch]
    elif len(counts) < nch:
        spec.extra["iec_declared_channels"] = nch
    spec.counts = counts
    return [spec]


def _iec_line(payload: str) -> str:
    return _IEC_TAG + payload[:64].ljust(64)


def write_iec(spec: Spectrum, path: Path) -> None:
    n = len(spec.counts)
    if n == 0:
        raise FormatError("empty spectrum")
    ex = spec.extra
    recs: list[str] = []
    sys_id = str(ex.get("iec_system_id") or "SPECMAST")
    sub_id = str(ex.get("iec_subsystem_id") or spec.detector or "")
    recs.append(f"{sys_id[:8]:<8}{sub_id[:8]:<8}{int(ex.get('iec_adc', 0) or 0):4d}"
                f"{int(ex.get('iec_segment', 0) or 0):4d}{spec.first_channel:6d}")
    lt = spec.live_time if spec.live_time is not None else 0.0
    rt = spec.real_time if spec.real_time is not None else lt
    recs.append(f"{lt:14.2f}{rt:14.2f}{n:6d}")
    r3 = spec.start_time.strftime("%d/%m/%y %H:%M:%S") if spec.start_time else ""
    st = ex.get("iec_sample_time")
    if st:
        try:
            r3 = r3.ljust(17) + " " + datetime.fromisoformat(str(st)).strftime("%d/%m/%y %H:%M:%S")
        except ValueError:
            pass
    recs.append(r3)
    c = (list(spec.energy_coeffs) + [0.0] * 4)[:4]
    recs.append("".join(f"{x:15.8E}" for x in c))
    recs.append(str(ex.get("iec_record5") or "".join(f"{0.0:15.8E}" for _ in range(4))))
    desc = [spec.sample_id] + [d for d in spec.description.splitlines() if d.strip()]
    desc = (desc + ["", "", "", ""])[:4]
    recs += [d.strip()[:64] for d in desc]
    recs.append("")                                       # rec 10 spare
    pairs: list[float] = []
    if spec.energy_coeffs and n > 1:
        for k in range(24):
            ch = spec.first_channel + round(k * (n - 1) / 23)
            pairs += [spec.energy_of(ch), float(ch)]
    pairs += [0.0] * (96 - len(pairs))
    zeros = [0.0] * 4
    for i in range(12):                                   # rec 11-22
        recs.append("".join(f"{x:16.9E}" for x in pairs[4 * i:4 * i + 4]))
    for _ in range(24):                                   # rec 23-46
        recs.append("".join(f"{x:16.9E}" for x in zeros))
    for _ in range(12):                                   # rec 47-58
        recs.append("")
    for i in range(0, n, 5):
        row = f"{i:6d}" + "".join(f"{_int_count(v):10d}" for v in spec.counts[i:i + 5])
        recs.append(row)
    data = "".join(_iec_line(r) + "\r\n" for r in recs)
    Path(path).write_bytes(data.encode("cp1256", errors="replace"))


def sniff_iec(path: Path, head: bytes) -> bool:
    lines = head.split(b"\n")[:4]
    return len(lines) >= 3 and all(l.startswith(b"A004") for l in lines[:3])


# ================================================================ IEEE ASCII
def read_ieee_asc(path: Path) -> list[Spectrum]:
    text = _read_text(path)
    spec = Spectrum(counts=[])
    header: list[str] = []
    per_line: list[int] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if _parse_hash_trailer(line, spec):
            continue
        nums = _numeric_tokens(line)
        if nums is None:
            if spec.counts:
                spec.extra.setdefault("trailer", "")
                spec.extra["trailer"] += line.strip() + "\n"
            else:
                header.append(line.strip())
            continue
        per_line.append(len(nums))
        spec.counts.extend(_count_value(v) for v in nums)
    if len(spec.counts) == 0:
        raise FormatError("no counts found")
    if header:
        spec.sample_id = spec.sample_id or header[0]
        if len(header) > 1:
            spec.description = spec.description or "\n".join(header[1:])
    if per_line:
        spec.extra["values_per_line"] = max(set(per_line), key=per_line.count)
    return [spec]


def _safe_header(s: str, default: str) -> str:
    s = " ".join(s.split()) or default
    return ("# " + s) if _numeric_tokens(s) is not None else s


def write_ieee_asc(spec: Spectrum, path: Path) -> None:
    lines = [_safe_header(spec.sample_id, "Spectrum"),
             _safe_header(" ".join(spec.description.split()), "SpectraMaster export"), ""]
    cnt = [_int_count(c) for c in spec.counts]
    for i in range(0, len(cnt), 8):
        lines.append("".join(f"{v:9d}" for v in cnt[i:i + 8]))
    lines.append("")
    data = "".join(l + "\r\n" for l in lines)
    Path(path).write_bytes(data.encode("cp1256", errors="replace"))


def sniff_ieee_asc(path: Path, head: bytes) -> bool:
    if path.suffix.lower() != ".asc" or b"\x00" in head:
        return False
    return len(_txt_numeric_lines(head, 20)) >= 5


# ================================================================ registration
register(FormatSpec(
    code=5, key="ascii1", name="ASCII-1 (one count per line)", extensions=[".txt"],
    reader=read_ascii1, writer=write_ascii1, sniffer=sniff_ascii1, aliases=["ascii-1"],
    notes="Counts only; header lines and '#Key=Value' trailers tolerated on input."))
register(FormatSpec(
    code=6, key="ascii2", name="ASCII-2 (channel, counts)", extensions=[".txt"],
    reader=read_ascii2, writer=write_ascii2, sniffer=sniff_ascii2, aliases=["ascii-2"],
    notes="Reads 2 or 3 columns (channel[, energy], counts) with any separator; an energy "
          "column is fitted to a polynomial calibration. Writes 'channel<TAB>counts'."))
register(FormatSpec(
    code=8, key="iec1455", name="IEC 1455 ASCII", extensions=[".iec"],
    reader=read_iec, writer=write_iec, sniffer=sniff_iec, aliases=["iec", "iec61455"],
    notes="A004 records, DD/MM/YY dates. Verified against InterWinner files and Genie 2000 "
          "FILECNVT /IEC1455."))
register(FormatSpec(
    code=9, key="ieee_asc", name="IEEE ASCII", extensions=[".asc"],
    reader=read_ieee_asc, writer=write_ieee_asc, sniffer=sniff_ieee_asc, aliases=["asc"],
    notes="Reads IAEA G-1 (header + 8/line) and HyperLab (1/line + #trailer) .ASC. Writes the "
          "G-1 layout (title, description, counts 8 x I9); times/calibration not stored. "
          "Not verified against the IEEE 1214 text."))

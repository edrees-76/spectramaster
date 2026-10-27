"""Legacy Canberra binary formats (DataMaster codes 14, 15) and the EML/Sanderson
ASCII test spectra (extra code 17).

Code 14 ``ci_s100``  Canberra System 100 *.mca   read/write
    Spec source: ``struct GAM_S100_HEADER`` in Los Alamos' MIC package
    (github.com/hnordquist/MIC, MIC/COMMONSOURCE/GamNew.h, BSD licence) plus the
    IAEA G-1 README ("128 bytes of header, 4 bytes per channel").  Validated on
    the nine G-1 *.MCA files (counts identical to G1*.ASC / G1100.CHN, calibration
    and times identical to G1100.CHN) and by converting files with Canberra
    Genie 2000 ``FILECNVT /S100``.  Little-endian, packed::

        0  int16  readout_type (2 = spectrum)     2  int16 mca_number
        4  int16  readout_region (0 = full)       6  int32 tag_number
       10  char[26] spectrum id
       36  int16  acquire_mode (0x180 = PHA+)
       38  uint32 start, seconds since 1970 GMT  42 int16 msec
       44  int16  timezone (minutes west of GMT) 46 int16 dstflag
       48  int32  live time, 1/100 s             52 int32 true (real) time, 1/100 s
       56  int32  sweeps                         60 float64 computational preset
       68  float32 2nd-order, 72 1st-order, 76 constant calibration term
       80  char[5] unit name, 85 unit_type, 86 format, 87 order
       88  int16[19] filler                     126 int16 number of channels
      128  int32[num_channels] counts
    Calibration is E = constant + first*ch + second*ch^2 with ch 0-based (Genie
    turns G1100.MCA's constant 0.00479 into -0.9952 for its 1-based channels).
    Local start time = GMT seconds - timezone*60 + dstflag*3600 (reproduces the
    G1100.CHN time 08:10).  The writer stores the naive local time with
    timezone = dstflag = 0, readout_region 0 (Genie refuses region 1).

Code 15 ``ci_accuspec``  Canberra AccuSpec *.dat   read-only
    Spec source: xylib ``canberra_mca.cpp`` (LGPL), from Canberra's MCA manual
    "Appendix B: File structures": two 512-byte header blocks, word 0 = 0,
    word@24 = data offset in bytes, word@34 = 4 (bytes/channel),
    word@36 = number of channels, word@38 = 1; energy calibration as three
    PDP-11 F-floats at bytes 108 (offset), 112 (slope), 116 (quadratic) applied to
    1-based channel numbers (xylib calls this point unclear).  The two xylib
    sample files show the counts are PDP-11 "middle-endian" 32-bit integers (high
    16-bit word first): read as plain little-endian every value is a multiple of
    65536.  Live/real time and date are not described, so they are not read.
    No gamma-spectrum AccuSpec sample was available; DataMaster itself could
    not write this format, and neither do we.
    NOTE: ``LN 881.dat`` in the APTEC sample folder is *not* AccuSpec (fails the
    signature; it holds ASCII dates and calibration text): it is read by
    ``lab_binary_dat.py`` (code 80).

Code 17 ``eml_sanderson``  EML / C.G. Sanderson PC test spectra *.dat  read-only
    US DOE EML (1990) intercomparison spectra.  README: "1 header line, 409 lines
    of 10I7 (10F7.0) data - 4090 data points"; header "<title> LT= <sec>
    ST=dd-MMM-yy hh:mm:ss".  Parsed like the distribution's own CONVERT program:
    fixed-width fields, a blank field is 0.  The field width is taken from the
    line length (BKG.DAT uses 10F8.0 and has a 410th, 7-value line, which is
    kept, giving 4097 values).  In the TEST* files channel 0 holds the live time
    (240000), as in the original data; it is left untouched.
"""
from __future__ import annotations

import math
import re
import struct
from datetime import datetime, timedelta
from pathlib import Path

from ..model import Spectrum
from .base import FormatError, FormatSpec, register

_EPOCH = datetime(1970, 1, 1)


# ===================================================================== S100
_S100_HDR = struct.Struct("<hhhi26shIhhhiiid3f5sBBB38sh")
assert _S100_HDR.size == 128


def _cstr(b: bytes) -> str:
    return b.split(b"\x00", 1)[0].decode("latin-1").strip()


def read_s100(path: Path) -> list[Spectrum]:
    data = Path(path).read_bytes()
    if len(data) < 128:
        raise FormatError("file too short for an S100 header")
    (rtype, mca, region, tag, specid, acqmode, sec, msec, tz, dst, live, true, sweeps,
     comp, q2, q1, q0, unit, unit_type, fmt, order, _filler, nch) = _S100_HDR.unpack_from(data)
    if nch <= 0 or len(data) < 128 + 4 * nch:
        # some files store fewer channels than the header claims; use what is there
        nch = (len(data) - 128) // 4
        if nch <= 0:
            raise FormatError("no channel data")
    counts = list(struct.unpack_from(f"<{nch}i", data, 128))
    s = Spectrum(counts=counts)
    s.sample_id = _cstr(specid)
    s.live_time = live / 100.0
    s.real_time = true / 100.0
    if sec:
        s.start_time = _EPOCH + timedelta(seconds=sec - tz * 60 + (3600 if dst else 0))
    if q1 or q0 or q2:
        s.energy_coeffs = [float(q0), float(q1)] + ([float(q2)] if q2 else [])
    s.extra.update({
        "s100_readout_type": rtype, "s100_mca_number": mca, "s100_readout_region": region,
        "s100_tag_number": tag, "s100_acquire_mode": acqmode, "s100_sweeps": sweeps,
        "s100_timezone_min_west": tz, "s100_dstflag": dst, "energy_unit": _cstr(unit),
    })
    return [s]


def write_s100(spec: Spectrum, path: Path) -> None:
    n = len(spec.counts)
    if n == 0 or n > 32767:
        raise FormatError("S100 supports 1..32767 channels")
    if spec.first_channel:
        raise FormatError("S100 cannot store a channel offset")
    sec = 0
    if spec.start_time is not None:
        sec = int((spec.start_time.replace(tzinfo=None) - _EPOCH).total_seconds())
        if not 0 <= sec < 2 ** 32:
            sec = 0
    c = list(spec.energy_coeffs[:3]) + [0.0] * (3 - min(3, len(spec.energy_coeffs)))
    if not spec.energy_coeffs:
        c = [0.0, 1.0, 0.0]
    order = 2 if c[2] else 1
    unit = (b"keV" if spec.energy_coeffs else b"chan")
    lt = spec.live_time if spec.live_time is not None else 0.0
    rt = spec.real_time if spec.real_time is not None else lt
    hdr = _S100_HDR.pack(2, 1, 0, 0, spec.sample_id.encode("latin-1", "replace")[:26],
                         0x180, sec, 0, 0, 0, int(round(lt * 100)), int(round(rt * 100)),
                         0, 0.0, c[2], c[1], c[0], unit, 0, 1, order, b"\x00" * 38, n)
    counts = [int(round(float(v))) for v in spec.counts]
    if any(v < -2 ** 31 or v >= 2 ** 31 for v in counts):
        raise FormatError("count exceeds 32-bit range")
    Path(path).write_bytes(hdr + struct.pack(f"<{n}i", *counts))


def sniff_s100(path: Path, head: bytes) -> bool:
    if len(head) < 128:
        return False
    rtype, = struct.unpack_from("<h", head, 0)
    nch, = struct.unpack_from("<h", head, 126)
    if rtype != 2 or nch <= 0:
        return False
    try:
        size = path.stat().st_size
    except OSError:
        return False
    return size == 128 + 4 * nch


# ================================================================= AccuSpec
def _pdp11_float(p: bytes) -> float:
    sign = -1.0 if p[1] & 0x80 else 1.0
    exb = ((p[1] & 0x7F) << 1) + ((p[0] & 0x80) >> 7)
    if exb == 0:
        return 0.0
    h = p[2] / 256 ** 3 + p[3] / 256 ** 2 + (128 + (p[0] & 0x7F)) / 256
    return sign * h * 2.0 ** (exb - 128)


def _accuspec_header_ok(head: bytes) -> bool:
    if len(head) < 1024:
        return False
    w = lambda o: struct.unpack_from("<H", head, o)[0]
    return w(0) == 0 and w(34) == 4 and w(38) == 1 and 0 < w(36) <= 16384 and w(24) >= 40


def read_accuspec(path: Path) -> list[Spectrum]:
    data = Path(path).read_bytes()
    if not _accuspec_header_ok(data):
        raise FormatError("not a Canberra AccuSpec file (header signature mismatch)")
    off, = struct.unpack_from("<H", data, 24)
    nch, = struct.unpack_from("<H", data, 36)
    if len(data) < off + 4 * nch:
        raise FormatError("AccuSpec file truncated")
    words = struct.unpack_from(f"<{2 * nch}H", data, off)
    counts = [(words[2 * i] << 16) | words[2 * i + 1] for i in range(nch)]
    a, b, c = (_pdp11_float(data[o:o + 4]) for o in (108, 112, 116))
    s = Spectrum(counts=counts)
    if a or b or c:
        # file calibration uses 1-based channels: E = a + b*k + c*k^2, k = i+1
        s.energy_coeffs = [a + b + c, b + 2 * c] + ([c] if c else [])
    s.extra["accuspec_cal_raw"] = f"{a!r} {b!r} {c!r} (1-based channels)"
    return [s]


def sniff_accuspec(path: Path, head: bytes) -> bool:
    if not _accuspec_header_ok(head):
        return False
    off, = struct.unpack_from("<H", head, 24)
    nch, = struct.unpack_from("<H", head, 36)
    try:
        return path.stat().st_size >= off + 4 * nch
    except OSError:
        return False


# ================================================================ Sanderson
_LT_RE = re.compile(r"LT=\s*(\d+(?:\.\d*)?)")
_ST_RE = re.compile(r"ST=\s*(\d{1,2}-[A-Za-z]{3}-\d{2,4})\s+(\d{1,2}:\d{2}:\d{2})")


def _fixed_fields(line: str, width: int, nfields: int) -> list[float]:
    out = []
    for k in range(nfields):
        f = line[k * width:(k + 1) * width].strip()
        out.append(float(f) if f else 0.0)
    return out


def read_sanderson(path: Path) -> list[Spectrum]:
    text = Path(path).read_bytes().replace(b"\x1a", b"").decode("latin-1")
    lines = [l.rstrip("\r\n") for l in text.splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    if len(lines) < 2:
        raise FormatError("too short for an EML/Sanderson spectrum")
    header, body = lines[0], [l for l in lines[1:] if l.strip()]
    lengths = sorted(len(l.rstrip()) for l in body)
    typical = lengths[len(lengths) // 2]
    width = round(typical / 10)
    if width not in (6, 7, 8, 9, 10):
        raise FormatError("unexpected field width")
    counts: list = []
    try:
        for i, l in enumerate(body):
            if i == len(body) - 1:
                nf = -(-len(l.rstrip()) // width)
            else:
                nf = 10
            counts += _fixed_fields(l, width, nf)
    except ValueError as exc:
        raise FormatError(f"non-numeric data: {exc}") from exc
    counts = [int(c) if float(c).is_integer() else c for c in counts]
    s = Spectrum(counts=counts)
    m = _LT_RE.search(header)
    title = header[:m.start()] if m else header
    s.sample_id = title.strip()
    if m:
        s.live_time = float(m.group(1))
        s.real_time = s.live_time
        # channels 0 and 1 hold live and real time when channel 0 repeats LT= (EML TEST files,
        # IAEA ASCII .dat output; docs/baseline/iaea_dat_detection_protocol.md) and channel 1 is a
        # possible real time: 0 (not given, as in the EML TEST files) or LT <= RT <= 2 LT
        # (round4_formats_protocol.md)
        c = s.counts
        if c and c[0] == s.live_time:
            rt = float(c[1]) if len(c) > 1 else float("nan")
            if math.isclose(rt, 0.0, abs_tol=1e-9) or s.live_time <= rt <= 2.0 * s.live_time:
                s.real_time = max(rt, s.live_time)
                c[0:2] = [0, 0]
                s.extra["time_channels"] = True
            else:
                s.extra["time_channels_note"] = (
                    f"channel 0 equals the live time but channel 1 ({c[1] if len(c) > 1 else 'missing'}) is not "
                    "a possible real time (0, or LT to 2 LT): channels 0 and 1 read as counts")
    st = _ST_RE.search(header)
    if st:
        try:
            s.start_time = datetime.strptime(f"{st.group(1).title()} {st.group(2)}",
                                             "%d-%b-%y %H:%M:%S")
        except ValueError:
            pass
    s.extra["header"] = header.rstrip()
    s.extra["field_width"] = width
    return [s]


def sniff_sanderson(path: Path, head: bytes) -> bool:
    return path.suffix.lower() == ".dat" and content_sanderson(path, head)


def content_sanderson(path: Path, head: bytes) -> bool:
    if b"\x00" in head:
        return False
    lines = [l for l in head.decode("latin-1").splitlines() if l.strip()]
    if len(lines) < 5:
        return False
    for l in lines[1:4]:
        n = len(l.rstrip())
        if n not in (70, 80):
            return False
        try:
            _fixed_fields(l, n // 10, 10)
        except ValueError:
            return False
    return True


# ============================================================ registration
register(FormatSpec(
    code=14, key="ci_s100", name="Canberra S100", extensions=[".mca"],
    reader=read_s100, writer=write_s100, sniffer=sniff_s100, aliases=["s100", "mca"],
    notes="128-byte GAM_S100_HEADER (LANL MIC) + int32 counts; verified on IAEA G-1 .MCA "
          "files and with Genie 2000 FILECNVT /S100."))
register(FormatSpec(
    code=15, key="ci_accuspec", name="Canberra AccuSpec", extensions=[".dat"],
    reader=read_accuspec, sniffer=sniff_accuspec, aliases=["accuspec"],
    notes="Read-only (as in DataMaster). Layout from xylib canberra_mca; counts and energy "
          "calibration only; no gamma sample was available for validation."))
register(FormatSpec(
    code=17, key="eml_sanderson", name="EML/Sanderson ASCII test spectra", extensions=[".dat"],
    reader=read_sanderson, sniffer=sniff_sanderson, aliases=["sanderson", "eml"],
    content_sniffer=content_sanderson,
    notes="Read-only. 1 header line (title LT= ST=) + 10I7/10F7.0 lines (4090 channels)."))

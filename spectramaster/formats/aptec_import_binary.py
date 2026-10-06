"""Binary spectrum formats imported by Aptec MCA v6.31 (Win16) converter DLLs.

Every layout below was recovered by disassembling the 16-bit NE converter DLLs
shipped with Aptec MCA v6.31 (``C:\\APTEC\\APTEC\\CONVERT\\*.dll``, plus the
native ``aptecspc.dll``) - their ``OPENFILESPECTRUM`` / ``SAVEFILESPECTRUM``
exports - and of the helper library ``pcmca.dll`` they call.  No public
specification or sample file was available for any of them, so "verified"
below means "this is exactly what Aptec does", not "checked against a file
written by the original instrument".  Each converter fills Aptec's in-memory
spectrum structure, which is the 1024-byte S0 header of ``aptec.py`` (offsets
0x31A start, 0x32A real ms, 0x332 live ms, 0x286 energy coefficients ...), so
field meanings are known exactly.

Helper semantics established from pcmca.dll:
  * VALIDSPECTRUMSIZE(n): Aptec rounds the channel count *down* to a power of
    two in 256..16384 (warning if inexact).  Our readers keep every channel.
  * MAKETDS/TDSTOSEC: Aptec's time base is seconds since 1900-01-01.
  * FILLINSPCHEADER (run after every import): gross = channel sum, 0x396 and
    0x38E = number of channels, live<-real or real<-live if one is 0, 0x32E =
    copy of 0x332.
  * lstrcpyn-style string fields (n includes the NUL).

Formats (code, key, read/write):

70 jcac_vax  "JCAC VAX (*.SPC)"  jcac_vax.dll  R/W
    The whole file is a sequence of 32-bit VAX F-floats (bytes: word0 =
    sign/exponent/high fraction, word1 = low fraction, each little-endian;
    IEEE value = bits(word0<<16|word1) / 4, word0 == 0 -> 0).
    record 0 = real time [s], record 1 = live time [s]; record k >= 2 is the
    count of channel k, but Aptec zeroes channels 0..15 after reading (they
    hold header data), and its writer emits 0.0 for records 2..15.  The
    number of channels is the number of records.  Writer = Aptec's writer.

71 nd66  "ND66 (*.001)"  nd66.dll  R/W
    Nuclear Data ND66: 512-byte header, PDP-11 conventions: 32-bit integers
    stored high word first ("middle-endian"), floats are PDP-11/VAX F-floats.
    Same header family as Canberra AccuSpec (accuspec.dll reads it with
    identical code).  Header (byte offsets)::
      0x00 u16  0 (Aptec checks: "1st byte is %d not 0")
      0x14 u16  live time, hundredths     0x16 u16 real time, hundredths
      0x18 u16  byte offset of channel data (512)
      0x1C long 1                        0x24 u16 x 0x26 u16 = channels
      0x2C long live preset s   0x30 long live s   0x34 long real preset s
      0x38 long real s          0x3C long -> Aptec 0x380 (not decoded)
      0x50 u16 day of year (1-based)  0x52 u16 year  0x54 long seconds of day
           = acquisition start;  same triple at 0x124 (sample/decay date),
           0x144 (sample stop), 0x12C (energy calibration date)
      0x6C 3 x F-float  energy E = c0 + c1*ch + c2*ch^2 (Aptec: 0-based ch)
      0x120 F-float quantity   0x14C label (64)   0x18C sample id (16)
      0x1AC quantity units (16)  0x1BC geometry (16)  0x1DC detector (16)
    Data: one 24-bit big-endian count per channel (3 bytes), so the file is
    0x200 + 3*channels bytes.  Live/real = long seconds*100 + hundredths.

72 norland5000  "Norland PHA-5000 (*.DAT)"  norland.dll  R/W
    512-byte header: u16 @0 size code 1..8 (channels = 1024*code),
    MBF single @2 = energy offset, MBF single @6 = keV/channel, rest 0.
    Then 1024*code Microsoft-Binary-Format single floats; channel 0 holds the
    live time [s] and channel 1 the real time [s] (Aptec zeroes both counts).

73 oxford_ans  "Oxford (*.ANS)"  oxford.dll  R/W
    u16 @0 revision.  Revisions 0/1: 1024-byte header, f64 @0x56 start and
    @0x5E stop as day numbers with day 2.0 = 1900-01-01 (OLE/Excel date),
    f64 @0x66 real s, @0x6E live s, u16 @0x3F6 first channel, @0x3F8 last
    channel, u16 @0x3FE extra bytes to skip; then int32 counts.  Revision 2:
    1536-byte header, dates @0x50/0x58, real @0x60, live @0x68, first/last
    @0x3F0/0x3F2, skip @0x3FE.  Aptec's writer (revision 0) also stores
    channels at 0xC2 and 0xC4, 1 at 0xE6, dead time % (f32) at 0x7A.

74 quantrad_scout  "Quantrad Scout (*.SCT)"  scout.dll  read only
    1024 unused bytes, then a 579-byte record: +2 u32 start and +6 u32 stop
    (seconds since 1970), +0x0A f32 dead time %, +0x0E 256 x u16 counts,
    +0x20E u16 (gross, -> extra), +0x210 sample id (16), +0x235 energy units,
    +0x239 f32 keV/channel, +0x23D f32 offset.  real = stop-start,
    live = real*(1-dead/100).

75 spectran_f  "Spectran F (*.SPC)"  spectran.dll  read only
    Sequence of 0x408-byte blocks: u32 0x408, 256 x f32 (1024 bytes),
    u32 0x408 (Aptec checks both markers).  Block 1 = header (offsets in the
    payload): f32 0x34 real s, 0x60 live s, 0x58 preset s, start date =
    f32 day 0x18 / month 0x1C / year 0x20 (valid if year >= 1900) + f32
    seconds-of-day 0x14; decay date = start - f32 0x10 minutes; stop date =
    0x28/0x2C/0x30 + 0x24; f32 0x68 -> MCA number; 0x8C user (20 chars),
    0x320 label (40), 0x78 sample id (20; if blank: f32 @0 as integer),
    f32 @4 / @8 detector / geometry numbers; if 0 < f32 0x5C <= 5: energy
    order = f32 0x3C, coefficients c0..c5 = f32 0x40..0x54; channels = f32
    0x64.  Following blocks: the channel values as f32 (channel 0 and 1 hold
    live/real seconds, used only if the header times are 0).

76 nucleus_pca  "Nucleus PCA-I / PCA-II (*.SPM)"  nucleus.dll  read only
    512-byte header + channels x 4 bytes (24-bit little-endian count, the top
    byte is a flag and is masked).  Bytes 0..2: elapsed time [s] as 3 packed
    BCD bytes (least significant pair first); byte 3 == 0xFF / byte 4 == 0xFF
    mark which time it is (Aptec requires one of them).  u16 @0x10A channels.
    PCA-II if byte @0x164 != 0 or s16 @0x1FE > 0, else PCA-I:
      PCA-I : time = real if byte3 is 0xFF else live; start date as text
              "Mon" @0x16, day @0x1A, year @0x1D, hh @0x22, mm @0x25,
              ss @0x28, "PM" @0x2B; energy calibration points as up to 14
              pairs (channel, keV) of 6-byte BCD reals from @0x2F (4 bytes of
              digit pairs LSB first + 1 digit, sign nibble 9 = negative,
              signed exponent byte; value = digits*1e-9*10^exp) -> linear fit.
      PCA-II: time = real if byte4 is 0xFF else live (byte3); real time is
              then taken from u32 @0x166 [s]; start: year u16 @0x10E, month
              @0x10D, day @0x10C, hour @0x113, min @0x112, sec @0x111,
              1/100 @0x110; stop likewise at 0x114..0x11B; energy c0/c1/c2 =
              f64 @0x34/0x3C/0x44, units @0x30, n points u16 @0x4C with f64
              channels @0x4E and energies @0x76; sample id @0x11C.
    (Aptec labels them "Imported from Nucleus PCA-I/-II".  Whether this is the
    same format ORTEC DataMaster calls "OXFORD PCA-2 (*.spm)" (code 3) is NOT
    confirmed, so the DataMaster code is not claimed.)

77 pca_multiport  "PCA-Multiport (*.SPT)"  pcam.dll  read only
    Tagged records {u16 type, u32 payload length, payload}; the first must
    be type 1023 (payload 0x80).  1014 data {u16 port, u16 first channel,
    u16 count, count x int32 (24-bit, top byte masked)}; 1015 energy
    calibration (payload 0x2A) {port, units @6 (4), f64 c0..c3 @0x0A};
    1016 dates (0x3A) {port, stop "hh:mm:ss" @6, stop "Mon dd, yyyy" @0x13,
    start time @0x20, start date @0x2D}; 1019 times (0x12) {port, u32 real s
    @6, u32 live s @0x0A}; 1020 (0x0E) selects the port (first one wins);
    1021 number of spectra; 1022 end.  Only the selected port is imported.
    (DataMaster "OXFORD PCA-3 (*.spt)" (code 4) not confirmed -> not claimed.)

78 aptec_v30 / 79 aptec_v43  older Aptec S0 versions, read only
    Read by aptecspc.dll (ReadSpectrumV30/V43; aptecv30/v43.dll only write).
    v3.0: "VERSION3.0" @0, u16 @0x0E channels, start @0x14 / stop @0x1B as
    (sec, min, hour, day, month, u16 year), u32 @0x22 real and @0x26 live in
    1/100 s, u32 @0x2A gross, u16 @0x32 preset mode char, @0x34 preset 1/100s,
    label @0x3C (42), title @0x66 (32), user @0x86, detector @0x96,
    geometry @0xA6, sample id @0xB6 (16 each), energy units @0x167, order
    u16 @0x16E, 4 x f32 coefficients @0x170; counts int32 from 0x400.
    v4.3: "VERSION4.3" @0, u16 @0x24 channels, start/stop DT8 @0x2A/0x32,
    u32 ms real @0x3A / live @0x42, gross @0x4A, nROI @0x82, trailer length
    @0x10E, comment length @0x110, label @0x112, title @0x13C, user @0x15C,
    detector @0x16C, geometry @0x17C, sample id @0x18C, energy units @0x214,
    nEcal @0x224, order @0x226, 6 x f64 @0x228, FWHM units @0x268,
    nFcal @0x278, order @0x27A, 6 x f64 @0x27C, nEff @0x2CC; after the 1 KiB
    header: nEff x 192, nEcal x 8, nFcal x 8, nROI x 256 bytes, counts.
"""
from __future__ import annotations

import math
import struct
from datetime import datetime, timedelta
from pathlib import Path

from ..model import Spectrum
from .base import FormatError, FormatSpec, register

_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_EPOCH1900 = datetime(1900, 1, 1)


# ============================================================ common helpers
def _read(path: Path) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise FormatError(f"cannot read {Path(path).name}: {exc}") from exc


def _cstr(b: bytes) -> str:
    return b.split(b"\0", 1)[0].decode("cp1252", errors="replace").strip()


def _put(buf: bytearray, off: int, size: int, s: str) -> None:
    raw = (s or "").encode("cp1252", errors="replace")[:size - 1]
    buf[off:off + len(raw)] = raw


def _u16(d, o):
    return struct.unpack_from("<H", d, o)[0]


def _u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def _f32(d, o):
    return struct.unpack_from("<f", d, o)[0]


def _f64(d, o):
    return struct.unpack_from("<d", d, o)[0]


def _finite(x) -> bool:
    return isinstance(x, float) and math.isfinite(x)


def _dt(year, month, day, hour=0, minute=0, sec=0, hs=0):
    try:
        return datetime(int(year), int(month), int(day), int(hour), int(minute),
                        int(sec), int(hs) * 10000)
    except (ValueError, OverflowError):
        return None


def _aptec_dt7(d, o):
    """Aptec v3.0 date: sec, min, hour, day, month, u16 year."""
    sec, mi, h, day, mon, year = struct.unpack_from("<5BH", d, o)
    return None if year == 0 else _dt(year, mon, day, h, mi, sec)


def _aptec_dt8(d, o):
    hs, sec, mi, h, day, mon, year = struct.unpack_from("<6BH", d, o)
    return None if year == 0 else _dt(year, mon, day, h, mi, sec, min(hs, 99))


def _int_or_float(v: float):
    r = round(v)
    return int(r) if abs(v - r) < 1e-6 else v


def _linfit(points):
    n = len(points)
    if n < 2:
        return []
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    sxx = sum(p[0] * p[0] for p in points)
    sxy = sum(p[0] * p[1] for p in points)
    den = n * sxx - sx * sx
    if den == 0:
        return []
    b = (n * sxy - sx * sy) / den
    return [(sy - b * sx) / n, b]


# --------------------------------------------------------- VAX / PDP-11 float
def vax_to_float(b: bytes) -> float:
    w0, w1 = struct.unpack("<HH", b)
    if w0 == 0:
        return 0.0
    if (w0 >> 7) & 0xFF == 0:  # reserved operand / dirty zero
        return 0.0
    return struct.unpack("<f", struct.pack("<I", (w0 << 16) | w1))[0] / 4.0


def float_to_vax(x: float) -> bytes:
    x = float(x)
    if x == 0.0:
        return bytes(4)
    bits = struct.unpack("<I", struct.pack("<f", x * 4.0))[0]
    return struct.pack("<HH", bits >> 16, bits & 0xFFFF)


def _pdp_long(d, o) -> int:
    hi, lo = struct.unpack_from("<HH", d, o)
    return (hi << 16) | lo


def _pack_pdp_long(v: int) -> bytes:
    v &= 0xFFFFFFFF
    return struct.pack("<HH", v >> 16, v & 0xFFFF)


# ----------------------------------------------------------------- MBF float
def mbf_to_float(b: bytes) -> float:
    if b[3] == 0:
        return 0.0
    sign = -1.0 if b[2] & 0x80 else 1.0
    mant = ((b[2] & 0x7F) << 16) | (b[1] << 8) | b[0]
    return sign * (1.0 + mant / 8388608.0) * 2.0 ** (b[3] - 129)


def float_to_mbf(x: float) -> bytes:
    x = float(x)
    if x == 0.0:
        return bytes(4)
    bits = struct.unpack("<I", struct.pack("<f", x))[0]
    sign = bits >> 31
    exp = (bits >> 23) & 0xFF
    mant = bits & 0x7FFFFF
    if exp == 0:
        return bytes(4)
    e = exp + 2
    if e > 255:
        raise FormatError(f"value {x} too large for an MBF float")
    return bytes([mant & 0xFF, (mant >> 8) & 0xFF, ((mant >> 16) & 0x7F) | (sign << 7), e])


# ======================================================== 70  JCAC VAX .SPC
JCAC_RESERVED = 16


def read_jcac(path: Path) -> list[Spectrum]:
    d = _read(path)
    if len(d) < 4 * (JCAC_RESERVED + 1) or len(d) % 4:
        raise FormatError(f"{Path(path).name}: not a JCAC VAX spectrum (size {len(d)})")
    vals = [vax_to_float(d[i:i + 4]) for i in range(0, len(d), 4)]
    real, live = vals[0], vals[1]
    counts = [0] * JCAC_RESERVED + [_int_or_float(v) for v in vals[JCAC_RESERVED:]]
    s = Spectrum(counts=counts, real_time=real or None, live_time=live or None)
    s.extra["header_records"] = ", ".join(f"{v:g}" for v in vals[2:JCAC_RESERVED])
    return [s]


def write_jcac(spec: Spectrum, path: Path) -> None:
    n = len(spec.counts)
    if n <= JCAC_RESERVED:
        raise FormatError("JCAC VAX needs more than 16 channels")
    if spec.first_channel:
        raise FormatError("JCAC VAX cannot store a channel offset")
    real = spec.real_time if spec.real_time is not None else (spec.live_time or 0.0)
    live = spec.live_time if spec.live_time is not None else real
    out = bytearray(float_to_vax(real) + float_to_vax(live) + bytes(4 * (JCAC_RESERVED - 2)))
    for c in spec.counts[JCAC_RESERVED:]:
        out += float_to_vax(float(c))
    Path(path).write_bytes(bytes(out))


def sniff_jcac(path: Path, head: bytes) -> bool:
    if path.suffix.lower() != ".spc" or len(head) < 4 * JCAC_RESERVED + 64:
        return False
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size % 4 or not 256 * 4 <= size <= 65536 * 4:
        return False
    vals = []
    for i in range(0, min(len(head), 4096), 4):
        w0 = _u16(head, i)
        if w0 and (w0 >> 7) & 0xFF == 0:
            return False
        vals.append(vax_to_float(head[i:i + 4]))
    real, live = vals[0], vals[1]
    if not (0 < live <= real * 1.0001 + 1e-9 < 1e9):
        return False
    if any(v != 0.0 for v in vals[2:JCAC_RESERVED]):
        return False
    return all(v >= 0 and v == int(v) and v < 1e9 for v in vals[JCAC_RESERVED:])


# ============================================================== 71  ND66
ND_HDR = 512


def _nd_date(d, o_date, o_time):
    doy, year = struct.unpack_from("<HH", d, o_date)
    if not year or not doy:
        return None
    if year < 100:  # not seen in Aptec's code; 2-digit years are assumed 19xx
        year += 1900
    secs = _pdp_long(d, o_time)
    try:
        return datetime(year, 1, 1) + timedelta(days=doy - 1, seconds=secs)
    except (ValueError, OverflowError):
        return None


def _nd_pack_date(buf, o_date, o_time, t):
    if t is None:
        return
    doy = t.timetuple().tm_yday
    struct.pack_into("<HH", buf, o_date, doy, t.year)
    buf[o_time:o_time + 4] = _pack_pdp_long(t.hour * 3600 + t.minute * 60 + t.second)


def _nd_header_ok(d: bytes) -> bool:
    if len(d) < ND_HDR or _u16(d, 0) != 0:
        return False
    off, n = _u16(d, 0x18), _u16(d, 0x24) * _u16(d, 0x26)
    return 32 <= off <= 0x10000 and 0 < n <= 65536


def read_nd66(path: Path) -> list[Spectrum]:
    d = _read(path)
    if not _nd_header_ok(d):
        raise FormatError(f"{Path(path).name}: not an ND66 spectrum (header check failed)")
    off, n = _u16(d, 0x18), _u16(d, 0x24) * _u16(d, 0x26)
    if len(d) < off + 3 * n:
        raise FormatError(f"{Path(path).name}: ND66 file truncated")
    counts = [(d[off + 3 * i] << 16) | (d[off + 3 * i + 1] << 8) | d[off + 3 * i + 2]
              for i in range(n)]
    real = (_pdp_long(d, 0x38) * 100 + _u16(d, 0x16)) / 100.0
    live = (_pdp_long(d, 0x30) * 100 + _u16(d, 0x14)) / 100.0
    coefs = [vax_to_float(d[o:o + 4]) for o in (0x6C, 0x70, 0x74)]
    while coefs and coefs[-1] == 0.0:
        coefs.pop()
    s = Spectrum(counts=counts, real_time=real or None, live_time=live or None,
                 start_time=_nd_date(d, 0x50, 0x54),
                 energy_coeffs=coefs if len(coefs) >= 2 else [],
                 sample_id=_cstr(d[0x18C:0x19C]), description=_cstr(d[0x14C:0x18C]),
                 detector=_cstr(d[0x1DC:0x1EC]))
    ex = s.extra
    ex["live_preset_s"] = _pdp_long(d, 0x2C)
    ex["real_preset_s"] = _pdp_long(d, 0x34)
    for key, od, ot in (("sample_date", 0x124, 0x128), ("sample_stop", 0x144, 0x148),
                        ("energy_cal_date", 0x12C, 0x130)):
        t = _nd_date(d, od, ot)
        if t:
            ex[key] = t.isoformat(sep=" ")
    for key, o in (("geometry_id", 0x1BC), ("quantity_units", 0x1AC)):
        v = _cstr(d[o:o + 16])
        if v:
            ex[key] = v
    q = vax_to_float(d[0x120:0x124])
    if q:
        ex["quantity"] = q
    return [s]


def write_nd66(spec: Spectrum, path: Path) -> None:
    n = len(spec.counts)
    if not 0 < n <= 65535:
        raise FormatError("ND66 needs 1..65535 channels")
    if spec.first_channel:
        raise FormatError("ND66 cannot store a channel offset")
    if len(spec.energy_coeffs) > 3:
        raise FormatError("ND66 stores at most 3 calibration coefficients")
    counts = [int(round(float(c))) for c in spec.counts]
    if any(c < 0 or c > 0xFFFFFF for c in counts):
        raise FormatError("ND66 channels are 24-bit (0..16777215)")
    h = bytearray(ND_HDR)
    struct.pack_into("<H", h, 0x18, ND_HDR)
    h[0x1C:0x20] = _pack_pdp_long(1)
    struct.pack_into("<HH", h, 0x24, n, 1)
    real = spec.real_time if spec.real_time is not None else (spec.live_time or 0.0)
    live = spec.live_time if spec.live_time is not None else real
    for t, o_hs, o_el, o_pre in ((real, 0x16, 0x38, 0x34), (live, 0x14, 0x30, 0x2C)):
        cs = int(round(t * 100))
        struct.pack_into("<H", h, o_hs, cs % 100)
        h[o_el:o_el + 4] = _pack_pdp_long(cs // 100)
        h[o_pre:o_pre + 4] = _pack_pdp_long(cs // 100)
    _nd_pack_date(h, 0x50, 0x54, spec.start_time)
    for i, c in enumerate(spec.energy_coeffs):
        h[0x6C + 4 * i:0x70 + 4 * i] = float_to_vax(c)
    _put(h, 0x14C, 64, spec.description)
    _put(h, 0x18C, 16, spec.sample_id)
    _put(h, 0x1BC, 16, str(spec.extra.get("geometry_id", "")))
    _put(h, 0x1DC, 16, spec.detector)
    data = bytearray(3 * n)
    for i, c in enumerate(counts):
        data[3 * i:3 * i + 3] = c.to_bytes(3, "big")
    Path(path).write_bytes(bytes(h) + bytes(data))


def sniff_nd66(path: Path, head: bytes) -> bool:
    if not _nd_header_ok(head) or _u16(head, 0x18) != ND_HDR:
        return False
    try:
        size = path.stat().st_size
    except OSError:
        return False
    return size == ND_HDR + 3 * _u16(head, 0x24) * _u16(head, 0x26)


# ======================================================= 72  Norland PHA-5000
NOR_HDR = 512


def read_norland(path: Path) -> list[Spectrum]:
    d = _read(path)
    if len(d) < NOR_HDR or not 1 <= _u16(d, 0) <= 8:
        raise FormatError(f"{Path(path).name}: not a Norland PHA-5000 spectrum")
    n = 1024 * _u16(d, 0)
    if len(d) < NOR_HDR + 4 * n:
        raise FormatError(f"{Path(path).name}: Norland file truncated")
    vals = [mbf_to_float(d[NOR_HDR + 4 * i:NOR_HDR + 4 * i + 4]) for i in range(n)]
    live, real = vals[0], vals[1]
    counts = [0, 0] + [_int_or_float(v) for v in vals[2:]]
    c0, c1 = mbf_to_float(d[2:6]), mbf_to_float(d[6:10])
    return [Spectrum(counts=counts, live_time=live or None, real_time=real or None,
                     energy_coeffs=[c0, c1] if c1 else [],
                     extra={"norland_size_code": _u16(d, 0)})]


def write_norland(spec: Spectrum, path: Path) -> None:
    n = len(spec.counts)
    if spec.first_channel:
        raise FormatError("Norland cannot store a channel offset")
    if n > 8192:
        raise FormatError("Norland PHA-5000 holds at most 8192 channels")
    if len(spec.energy_coeffs) > 2 and any(spec.energy_coeffs[2:]):
        raise FormatError("Norland stores only a linear calibration")
    code = next(c for c in (1, 2, 4, 8) if 1024 * c >= n)
    vals = [float(c) for c in spec.counts] + [0.0] * (1024 * code - n)
    real = spec.real_time if spec.real_time is not None else (spec.live_time or 0.0)
    live = spec.live_time if spec.live_time is not None else real
    vals[0], vals[1] = live, real
    h = bytearray(NOR_HDR)
    struct.pack_into("<H", h, 0, code)
    ec = list(spec.energy_coeffs[:2]) + [0.0] * (2 - min(2, len(spec.energy_coeffs)))
    h[2:6], h[6:10] = float_to_mbf(ec[0]), float_to_mbf(ec[1])
    Path(path).write_bytes(bytes(h) + b"".join(float_to_mbf(v) for v in vals))


def sniff_norland(path: Path, head: bytes) -> bool:
    if len(head) < NOR_HDR + 8 or _u16(head, 0) not in (1, 2, 4, 8):
        return False
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size != NOR_HDR + 4096 * _u16(head, 0) or any(head[10:NOR_HDR]):
        return False
    live = mbf_to_float(head[NOR_HDR:NOR_HDR + 4])
    real = mbf_to_float(head[NOR_HDR + 4:NOR_HDR + 8])
    return 0 <= live <= real * 1.0001 + 1


# ================================================================ 73  Oxford
def _ole(days: float):
    if not _finite(days) or days <= 2.0:
        return None
    try:
        return datetime(1899, 12, 30) + timedelta(days=days)
    except OverflowError:
        return None


def _oxford_layout(d: bytes):
    rev = _u16(d, 0)
    if rev in (0, 1):
        return rev, 0x400, 0x56, 0x5E, 0x66, 0x6E, 0x3F6, 0x3F8
    if rev == 2:
        return rev, 0x600, 0x50, 0x58, 0x60, 0x68, 0x3F0, 0x3F2
    return None


def read_oxford(path: Path) -> list[Spectrum]:
    d = _read(path)
    lay = _oxford_layout(d) if len(d) >= 0x400 else None
    if lay is None or len(d) < lay[1]:
        raise FormatError(f"{Path(path).name}: not an Oxford .ANS spectrum")
    rev, hdr, o_start, o_stop, o_real, o_live, o_first, o_last = lay
    first, last, skip = _u16(d, o_first), _u16(d, o_last), _u16(d, 0x3FE)
    n = last - first + 1
    off = hdr + skip
    if n <= 0 or len(d) < off + 4 * n:
        raise FormatError(f"{Path(path).name}: Oxford file truncated or bad channel range")
    counts = list(struct.unpack_from(f"<{n}i", d, off))
    real, live = _f64(d, o_real), _f64(d, o_live)
    s = Spectrum(counts=counts, first_channel=first,
                 real_time=real if _finite(real) and real > 0 else None,
                 live_time=live if _finite(live) and live > 0 else None,
                 start_time=_ole(_f64(d, o_start)))
    s.extra["oxford_revision"] = rev
    stop = _ole(_f64(d, o_stop))
    if stop:
        s.extra["stop_time"] = stop.isoformat(sep=" ")
    return [s]


def write_oxford(spec: Spectrum, path: Path) -> None:
    n = len(spec.counts)
    if not 0 < n <= 65535:
        raise FormatError("Oxford .ANS needs 1..65535 channels")
    if spec.first_channel:
        raise FormatError("channel offset not supported by the Oxford writer")
    counts = [int(round(float(c))) for c in spec.counts]
    if any(c < -2 ** 31 or c >= 2 ** 31 for c in counts):
        raise FormatError("count exceeds 32-bit range")
    h = bytearray(0x400)
    real = spec.real_time if spec.real_time is not None else (spec.live_time or 0.0)
    live = spec.live_time if spec.live_time is not None else real
    struct.pack_into("<HH", h, 0xC2, n, n)
    struct.pack_into("<H", h, 0xE6, 1)
    if spec.start_time is not None:
        st = (spec.start_time - datetime(1899, 12, 30)).total_seconds() / 86400.0
        struct.pack_into("<dd", h, 0x56, st, st + real / 86400.0)
    struct.pack_into("<dd", h, 0x66, real, live)
    struct.pack_into("<f", h, 0x7A, 100.0 * (real - live) / real if real else 0.0)
    struct.pack_into("<HH", h, 0x3F6, 0, n - 1)
    Path(path).write_bytes(bytes(h) + struct.pack(f"<{n}i", *counts))


def sniff_oxford(path: Path, head: bytes) -> bool:
    if path.suffix.lower() != ".ans" or len(head) < 0x400:
        return False
    lay = _oxford_layout(head)
    if lay is None:
        return False
    first, last = _u16(head, lay[6]), _u16(head, lay[7])
    if last < first:
        return False
    try:
        size = path.stat().st_size
    except OSError:
        return False
    return size >= lay[1] + _u16(head, 0x3FE) + 4 * (last - first + 1)


# ========================================================= 74  Quantrad Scout
SCT_REC, SCT_LEN = 0x400, 0x243


def read_scout(path: Path) -> list[Spectrum]:
    d = _read(path)
    if len(d) < SCT_REC + SCT_LEN:
        raise FormatError(f"{Path(path).name}: too short for a Quantrad Scout spectrum")
    r = d[SCT_REC:SCT_REC + SCT_LEN]
    start, stop = _u32(r, 2), _u32(r, 6)
    dead = _f32(r, 0x0A)
    counts = list(struct.unpack_from("<256H", r, 0x0E))
    real = float(stop - start) if stop >= start else None
    live = real * (1.0 - dead / 100.0) if real is not None and _finite(dead) else real
    slope, off = _f32(r, 0x239), _f32(r, 0x23D)
    s = Spectrum(counts=counts, real_time=real, live_time=live,
                 start_time=datetime(1970, 1, 1) + timedelta(seconds=start) if start else None,
                 sample_id=_cstr(r[0x210:0x220]),
                 energy_coeffs=[off, slope] if _finite(slope) and slope else [])
    s.extra.update({"dead_time_percent_stored": dead, "scout_gross_u16": _u16(r, 0x20E),
                    "energy_units": _cstr(r[0x235:0x239])})
    return [s]


def sniff_scout(path: Path, head: bytes) -> bool:
    if path.suffix.lower() != ".sct" or len(head) < SCT_REC + SCT_LEN:
        return False
    r = head[SCT_REC:]
    start, stop, dead = _u32(r, 2), _u32(r, 6), _f32(r, 0x0A)
    return 3e8 < start <= stop < 4.2e9 and _finite(dead) and 0 <= dead < 100


# ============================================================ 75  Spectran F
SPF_BLK = 0x408


def _spf_blocks(d: bytes):
    out = []
    for o in range(0, len(d) - SPF_BLK + 1, SPF_BLK):
        if _u32(d, o) != SPF_BLK or _u32(d, o + 0x404) != SPF_BLK:
            break
        out.append(d[o + 4:o + 0x404])
    return out


def _spf_date(p, o_day, o_mon, o_year, o_sec):
    year = _f32(p, o_year)
    if not _finite(year) or year < 1900:
        return None
    t = _dt(round(year), round(_f32(p, o_mon)), round(_f32(p, o_day)))
    sec = _f32(p, o_sec)
    return t + timedelta(seconds=sec) if t and _finite(sec) else t


def read_spectran(path: Path) -> list[Spectrum]:
    d = _read(path)
    blocks = _spf_blocks(d)
    if not blocks:
        raise FormatError(f"{Path(path).name}: not a Spectran-F file (no 0x408 record markers)")
    p = blocks[0]
    n = int(round(_f32(p, 0x64)))
    vals = []
    for b in blocks[1:]:
        vals += struct.unpack("<256f", b)
    if n <= 0 or n > len(vals):
        n = len(vals)
    if n < 3:
        raise FormatError(f"{Path(path).name}: Spectran-F file has no channel data")
    real, live = _f32(p, 0x34), _f32(p, 0x60)
    if not real:
        real = vals[1]
    if not live:
        live = vals[0]
    counts = [0, 0] + [_int_or_float(v) for v in vals[2:n]]
    s = Spectrum(counts=counts, real_time=real or None, live_time=live or None,
                 start_time=_spf_date(p, 0x18, 0x1C, 0x20, 0x14),
                 description=_cstr(p[0x320:0x348]), sample_id=_cstr(p[0x78:0x8C]))
    if not s.sample_id and _f32(p, 0):
        s.sample_id = str(int(round(_f32(p, 0))))
    if _f32(p, 4):
        s.detector = str(int(round(_f32(p, 4))))
    chk = _f32(p, 0x5C)
    if _finite(chk) and 0 < chk <= 5:
        order = max(0, min(5, int(round(_f32(p, 0x3C)))))
        c = [_f32(p, 0x40 + 4 * i) for i in range(order + 1)]
        while c and c[-1] == 0.0:
            c.pop()
        if len(c) >= 2:
            s.energy_coeffs = c
    ex = s.extra
    stop = _spf_date(p, 0x28, 0x2C, 0x30, 0x24)
    if stop:
        ex["stop_time"] = stop.isoformat(sep=" ")
    if s.start_time and _f32(p, 0x10):
        ex["decay_reference"] = (s.start_time - timedelta(minutes=_f32(p, 0x10))).isoformat(sep=" ")
    ex["preset_s"] = _f32(p, 0x58)
    user = _cstr(p[0x8C:0xA0])
    if user:
        ex["user_id"] = user
    if _f32(p, 8):
        ex["geometry_id"] = str(int(round(_f32(p, 8))))
    return [s]


def sniff_spectran(path: Path, head: bytes) -> bool:
    return len(head) >= SPF_BLK and _u32(head, 0) == SPF_BLK and _u32(head, 0x404) == SPF_BLK


# ===================================================== 76  Nucleus PCA-I/-II
PCA_HDR = 512


def _bcd3(b: bytes) -> int:
    v, mul = 0, 1
    for x in b[:3]:
        hi, lo = x >> 4, x & 15
        v += ((hi if hi <= 9 else 0) * 10 + (lo if lo <= 9 else 0)) * mul
        mul *= 100
    return v


def bcd_real6(b: bytes):
    """6-byte BCD real used by Nucleus PCA-I (see module docstring)."""
    acc, s1 = 0.0, 1.0
    for i in range(4):
        hi, lo = b[i] >> 4, b[i] & 15
        if hi > 9 or lo > 9:
            return None
        acc += lo * s1 + hi * s1 * 10
        s1 *= 100
    hi, lo = b[4] >> 4, b[4] & 15
    if lo > 9:
        return None
    acc += lo * s1
    if hi == 9:
        sign = -1.0
    elif hi == 0:
        sign = 1.0
    else:
        return None
    exp = b[5] - 256 if b[5] > 127 else b[5]
    return sign * acc * 1e-9 * 10.0 ** exp


def _int(b: bytes):
    try:
        return int(_cstr(b) or "x")
    except ValueError:
        return None


def read_nucleus(path: Path) -> list[Spectrum]:
    d = _read(path)
    if len(d) < PCA_HDR or not (d[3] == 0xFF or d[4] == 0xFF):
        raise FormatError(f"{Path(path).name}: not a Nucleus PCA spectrum "
                          "(neither time flag byte 3 nor 4 is 0xFF)")
    n = _u16(d, 0x10A)
    if n <= 0 or len(d) < PCA_HDR + 4 * n:
        raise FormatError(f"{Path(path).name}: Nucleus PCA file truncated")
    counts = [_u32(d, PCA_HDR + 4 * i) & 0xFFFFFF for i in range(n)]
    t = float(_bcd3(d[0:3]))
    pca2 = d[0x164] != 0 or struct.unpack_from("<h", d, 0x1FE)[0] > 0
    s = Spectrum(counts=counts)
    ex = s.extra
    if pca2:
        ex["nucleus_model"] = "PCA-II"
        if d[4] == 0xFF:
            ex["preset_mode"] = "real time"
        elif d[3] == 0xFF:
            ex["preset_mode"] = "live time"
            s.live_time = t
        s.real_time = float(_u32(d, 0x166)) or (t if d[4] == 0xFF else None)
        s.start_time = _dt(_u16(d, 0x10E), d[0x10D], d[0x10C], d[0x113], d[0x112], d[0x111],
                           min(d[0x110], 99))
        stop = _dt(_u16(d, 0x116), d[0x115], d[0x114], d[0x11B], d[0x11A], d[0x119],
                   min(d[0x118], 99))
        if stop:
            ex["stop_time"] = stop.isoformat(sep=" ")
        c = [_f64(d, 0x34), _f64(d, 0x3C), _f64(d, 0x44)]
        if all(_finite(x) for x in c) and c[1]:
            while c and c[-1] == 0.0:
                c.pop()
            s.energy_coeffs = c
        ex["energy_units"] = _cstr(d[0x30:0x34])
        npts = min(_u16(d, 0x4C), 5)
        if npts:
            ex["energy_cal_points"] = "; ".join(
                f"{_f64(d, 0x4E + 8 * k):g}:{_f64(d, 0x76 + 8 * k):g}" for k in range(npts))
        s.sample_id = _cstr(d[0x11C:0x12C])
    else:
        ex["nucleus_model"] = "PCA-I"
        if d[3] == 0xFF:
            s.real_time, ex["preset_mode"] = t, "real time"
        else:
            s.live_time, ex["preset_mode"] = t, "live time"
        mon = _cstr(d[0x16:0x19]).lower()
        hour = _int(d[0x22:0x24])
        if hour is not None and _cstr(d[0x2B:0x2D]).upper() == "PM" and hour < 12:
            hour += 12
        if mon in _MONTHS and None not in (hour, _int(d[0x1A:0x1C]), _int(d[0x1D:0x21])):
            s.start_time = _dt(_int(d[0x1D:0x21]), _MONTHS.index(mon) + 1, _int(d[0x1A:0x1C]),
                               hour, _int(d[0x25:0x27]) or 0, _int(d[0x28:0x2A]) or 0)
        pts = []
        for k in range(14):
            o = 0x2F + 12 * k
            ch, en = bcd_real6(d[o:o + 6]), bcd_real6(d[o + 6:o + 12])
            if ch is None or en is None or (ch <= 0 and en <= 0):
                break
            pts.append((ch, en))
        if pts:
            ex["energy_cal_points"] = "; ".join(f"{a:g}:{b:g}" for a, b in pts)
            s.energy_coeffs = _linfit(pts)
    return [s]


def sniff_nucleus(path: Path, head: bytes) -> bool:
    if path.suffix.lower() != ".spm" or len(head) < PCA_HDR:
        return False
    if not (head[3] == 0xFF or head[4] == 0xFF):
        return False
    n = _u16(head, 0x10A)
    if not 0 < n <= 16384 or any(x >> 4 > 9 or x & 15 > 9 for x in head[0:3]):
        return False
    try:
        return path.stat().st_size >= PCA_HDR + 4 * n
    except OSError:
        return False


# ======================================================= 77  PCA-Multiport
def _pcam_date(date: bytes, time: bytes):
    ds = _cstr(date)
    mon = ds[0:3].lower()
    if mon not in _MONTHS:
        return None
    try:
        day, year = int(ds[4:6]), int(ds[7:12].strip())
        ts = _cstr(time)
        h, mi, sec = int(ts[0:2]), int(ts[3:5]), int(ts[6:8])
    except ValueError:
        return None
    if ts[9:11].upper() == "PM" and h < 12:
        h += 12
    return _dt(year, _MONTHS.index(mon) + 1, day, h, mi, sec)


def read_pcam(path: Path) -> list[Spectrum]:
    d = _read(path)
    if len(d) < 6 or _u16(d, 0) != 1023:
        raise FormatError(f"{Path(path).name}: not a PCA-Multiport file (first record type != 1023)")
    o, port, port_set = 0, 0, False
    counts: list = []
    s = Spectrum(counts=[])
    ex = s.extra
    real = live = 0
    while o + 6 <= len(d):
        typ, ln = struct.unpack_from("<HI", d, o)
        p = d[o + 6:o + 6 + ln]
        o += 6 + ln
        if ln > 150000 or len(p) < ln:
            break
        if typ == 1022:
            break
        if typ == 1020 and ln == 0x0E and not port_set:
            port, port_set = _u16(p, 0), True
            continue
        if typ == 1021 and ln == 2:
            ex["spectra_in_file"] = _u16(p, 0)
            continue
        if typ not in (1014, 1015, 1016, 1019) or ln < 2 or _u16(p, 0) != port:
            continue
        if typ == 1014 and ln > 6:
            first, cnt = _u16(p, 2), _u16(p, 4)
            cnt = min(cnt, (ln - 6) // 4)
            vals = [v & 0xFFFFFF for v in struct.unpack_from(f"<{cnt}I", p, 6)]
            if len(counts) < first + cnt:
                counts += [0] * (first + cnt - len(counts))
            counts[first:first + cnt] = vals
        elif typ == 1015 and ln == 0x2A:
            c = list(struct.unpack_from("<4d", p, 0x0A))
            while c and c[-1] == 0.0:
                c.pop()
            if len(c) >= 2 and all(_finite(x) for x in c):
                s.energy_coeffs = c
            ex["energy_units"] = _cstr(p[6:10])
        elif typ == 1016 and ln == 0x3A:
            s.start_time = _pcam_date(p[0x2D:0x3A], p[0x20:0x2D])
            stop = _pcam_date(p[0x13:0x20], p[6:0x13])
            if stop:
                ex["stop_time"] = stop.isoformat(sep=" ")
        elif typ == 1019 and ln == 0x12:
            real = max(real, _u32(p, 6))
            live = max(live, _u32(p, 0x0A))
    if not counts:
        raise FormatError(f"{Path(path).name}: no spectrum data record (type 1014) found")
    s.counts = counts
    s.real_time = float(real or live) or None
    s.live_time = float(live or real) or None
    ex["port"] = port
    return [s]


def sniff_pcam(path: Path, head: bytes) -> bool:
    return len(head) >= 6 + 0x80 + 6 and _u16(head, 0) == 1023 and _u32(head, 2) == 0x80


# ===================================================== 78/79  old Aptec S0
def _fix_poly(c):
    c = [x if _finite(x) else 0.0 for x in c]
    while c and c[-1] == 0.0:
        c.pop()
    return c if len(c) >= 2 and c[1] else []


def _scale_units(units: str, coeffs):
    sc = {"mev": 1000.0, "ev": 0.001}.get(units.lower(), 1.0)
    return [x * sc for x in coeffs]


def read_aptec_v30(path: Path) -> list[Spectrum]:
    d = _read(path)
    if len(d) < 0x400 or not d.startswith(b"VERSION3.0"):
        raise FormatError(f"{Path(path).name}: not an Aptec v3.0 S0 file")
    n = _u16(d, 0x0E)
    if n == 0 or len(d) < 0x400 + 4 * n:
        raise FormatError(f"{Path(path).name}: truncated Aptec v3.0 file")
    counts = list(struct.unpack_from(f"<{n}I", d, 0x400))
    order = _u16(d, 0x16E)
    units = _cstr(d[0x167:0x16E])
    coef = []
    if order <= 3:
        coef = _scale_units(units, _fix_poly(struct.unpack_from(f"<{order + 1}f", d, 0x170)))
    s = Spectrum(counts=counts, real_time=_u32(d, 0x22) / 100.0 or None,
                 live_time=_u32(d, 0x26) / 100.0 or None, start_time=_aptec_dt7(d, 0x14),
                 description=_cstr(d[0x3C:0x66]), sample_id=_cstr(d[0x66:0x86]),
                 detector=_cstr(d[0x96:0xA6]), energy_coeffs=coef)
    ex = s.extra
    ex.update({"aptec_version": "3.0", "gross_counts": _u32(d, 0x2A), "energy_units": units,
               "user_id": _cstr(d[0x86:0x96]), "geometry_id": _cstr(d[0xA6:0xB6]),
               "aptec_sample_id": _cstr(d[0xB6:0xC6])})
    stop = _aptec_dt7(d, 0x1B)
    if stop:
        ex["stop_time"] = stop.isoformat(sep=" ")
    return [s]


def read_aptec_v43(path: Path) -> list[Spectrum]:
    d = _read(path)
    if len(d) < 0x400 or not d.startswith(b"VERSION4.3"):
        raise FormatError(f"{Path(path).name}: not an Aptec v4.3 S0 file")
    n = _u16(d, 0x24)
    o = 0x400 + 0xC0 * _u16(d, 0x2CC) + 8 * (_u16(d, 0x224) + _u16(d, 0x278)) + 0x100 * _u16(d, 0x82)
    if n == 0 or len(d) < o + 4 * n:
        raise FormatError(f"{Path(path).name}: truncated Aptec v4.3 file")
    counts = list(struct.unpack_from(f"<{n}I", d, o))
    units = _cstr(d[0x214:0x224])
    ecoef = _fix_poly(struct.unpack_from(f"<{min(_u16(d, 0x226), 5) + 1}d", d, 0x228))
    if units.lower() not in ("", "kev", "mev", "ev"):
        ecoef = []
    ecoef = _scale_units(units, ecoef)
    fcoef = _fix_poly(struct.unpack_from(f"<{min(_u16(d, 0x27A), 5) + 1}d", d, 0x27C))
    fwhm = []
    if fcoef and len(ecoef) >= 2 and _cstr(d[0x268:0x278]).lower() in ("", "channels", "channel"):
        deriv = [i * c for i, c in enumerate(ecoef)][1:]
        fwhm = [0.0] * (len(fcoef) + len(deriv) - 1)
        for i, x in enumerate(fcoef):
            for j, y in enumerate(deriv):
                fwhm[i + j] += x * y
    s = Spectrum(counts=counts, real_time=_u32(d, 0x3A) / 1000.0 or None,
                 live_time=_u32(d, 0x42) / 1000.0 or None, start_time=_aptec_dt8(d, 0x2A),
                 description=_cstr(d[0x112:0x13C]), sample_id=_cstr(d[0x13C:0x15C]),
                 detector=_cstr(d[0x16C:0x17C]), energy_coeffs=ecoef, fwhm_coeffs=fwhm)
    ex = s.extra
    ex.update({"aptec_version": "4.3", "gross_counts": _u32(d, 0x4A), "energy_units": units,
               "user_id": _cstr(d[0x15C:0x16C]), "geometry_id": _cstr(d[0x17C:0x18C]),
               "aptec_sample_id": _cstr(d[0x18C:0x19C]), "roi_count": _u16(d, 0x82)})
    if fcoef:
        ex["fwhm_coeffs_raw"] = ", ".join(f"{c:.6g}" for c in fcoef)
    stop = _aptec_dt8(d, 0x32)
    if stop:
        ex["stop_time"] = stop.isoformat(sep=" ")
    return [s]


def sniff_v30(path: Path, head: bytes) -> bool:
    return head.startswith(b"VERSION3.0") and len(head) >= 0x400 and 0 < _u16(head, 0x0E)


def sniff_v43(path: Path, head: bytes) -> bool:
    return head.startswith(b"VERSION4.3") and len(head) >= 0x400 and 0 < _u16(head, 0x24)


# ============================================================ registration
_NOTE = "Layout recovered from Aptec MCA v6.31 converter DLL (%s); no sample file available. "
register(FormatSpec(70, "jcac_vax", "JCAC VAX", [".spc"], read_jcac, write_jcac, sniff_jcac,
                    _NOTE % "jcac_vax.dll" + "VAX F-floats: real, live, 14 reserved, counts.",
                    aliases=["jcac"]))
register(FormatSpec(71, "nd66", "Nuclear Data ND66", [".001"], read_nd66, write_nd66, sniff_nd66,
                    _NOTE % "nd66.dll" + "512-byte PDP-11 header + 24-bit big-endian counts.",
                    aliases=["nd"]))
register(FormatSpec(72, "norland5000", "Norland PHA-5000", [".dat"], read_norland, write_norland,
                    sniff_norland, _NOTE % "norland.dll" + "512-byte header + MBF floats.",
                    aliases=["norland"]))
register(FormatSpec(73, "oxford_ans", "Oxford ANS", [".ans"], read_oxford, write_oxford,
                    sniff_oxford, _NOTE % "oxford.dll" + "Revisions 0/1/2 read, revision 0 written.",
                    aliases=["ans"]))
register(FormatSpec(74, "quantrad_scout", "Quantrad Scout (read only)", [".sct"], read_scout,
                    None, sniff_scout, _NOTE % "scout.dll" + "256 x u16 channels.",
                    aliases=["scout"]))
register(FormatSpec(75, "spectran_f", "Spectran F (read only)", [".spc"], read_spectran, None,
                    sniff_spectran, _NOTE % "spectran.dll" + "0x408-byte float records.",
                    aliases=["spectran"]))
register(FormatSpec(76, "nucleus_pca", "Nucleus PCA-I/PCA-II (read only)", [".spm"],
                    read_nucleus, None, sniff_nucleus,
                    _NOTE % "nucleus.dll" + "Possibly DataMaster's 'Oxford PCA-2' (unconfirmed).",
                    aliases=["nucleus", "pca2"]))
register(FormatSpec(77, "pca_multiport", "PCA-Multiport (read only)", [".spt"], read_pcam, None,
                    sniff_pcam, _NOTE % "pcam.dll" + "Possibly DataMaster's 'Oxford PCA-3' (unconfirmed).",
                    aliases=["pcam", "pca3"]))
register(FormatSpec(78, "aptec_v30", "APTEC v3.0 (read only)", [".s0"], read_aptec_v30, None,
                    sniff_v30, _NOTE % "aptecspc.dll ReadSpectrumV30 / aptecv30.dll",
                    aliases=["s0v30"]))
register(FormatSpec(79, "aptec_v43", "APTEC v4.3 (read only)", [".s0"], read_aptec_v43, None,
                    sniff_v43, _NOTE % "aptecspc.dll ReadSpectrumV43 / aptecv43.dll",
                    aliases=["s0v43"]))

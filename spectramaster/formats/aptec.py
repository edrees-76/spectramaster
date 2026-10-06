"""APTEC MCA v6.x binary spectrum files (``*.S0``) - reader and writer.

Written by "Aptec PCMCA/WIN" / "Aptec MCA Application" v6.31 (Aptec Instruments,
Aptec-NRC) and also by the later "Emca" software, 1990s-2010s.  ORTEC DataMaster
lists it as "APTEC v6.3 (*.s0)".  No public specification exists; everything
below was reverse-engineered from 22 reference files with independently decoded
channel data (CSV) plus a screenshot of the Aptec software for CHERNBKG.S0, and
then checked against ~3000 files of an 11,000-file laboratory corpus (2004-2014).

Everything is little-endian.  Strings are fixed-length, NUL-terminated (bytes
after the first NUL are garbage; the "Emca" writer pads with spaces) in the
Windows ANSI code page (decoded here as cp1256 because the corpus is Arabic;
ASCII is unaffected).  The 8-byte timestamp structure ``DT`` used everywhere is

    u8 hundredths, u8 sec, u8 min, u8 hour, u8 day, u8 month, u16 year

(all-zero = not set).  Verified: CHERNBKG start/stop 2-Jul-1986 12:43:40 /
13:08:42 match the Aptec screen.

File layout
===========
::

    0x000  1024-byte fixed header                     (table below)
    0x400  nEff  x 130-byte efficiency/source records  nEff = u16 @0x14A
           nEcal x (f32 channel, f32 energy)           nEcal = u16 @0x26A
           nFcal x (f32 channel, f32 FWHM [channels])  nFcal = u16 @0x2B6
           nROI  x 256-byte ROI / peak records         nROI = u16 @0x30E
           nCh   x u32 channel counts (uncompressed!)  nCh = u16 @0x316
           trailer: analysis-settings block, u16 @0x310 bytes (always 2514,
           or 0 = absent), followed by a free-text comment of u16 @0x312 bytes.

The resulting size equation ``0x400 + 130*nEff + 8*(nEcal+nFcal) + 256*nROI
+ 4*nCh + len_settings + len_comment == file size`` holds for all 22 reference
files and for every one of 3000 randomly sampled corpus files.  The counts
match the reference CSVs exactly for all 22 files (``tests/test_aptec.py``).
(The "compression" suspected from small file sizes was just the fact that
nothing but the counts depends on the channel count.)

Header fields (V = verified against independent ground truth, C = consistent
across files / self-consistent arithmetic, ? = plausible guess -> ``extra``)::

    off    type     meaning
    0x000  c16      "VERSION6.3"                                         V
    0x010  c16      DOS 8.3 file name ("EC-BL7~1.S0")                     C
    0x020  c42      spectrum label ("Aptec PC/MCA - HPS Show June 30-July 3",
                    shown next to the file name on the Aptec screen)      V
                    -> Spectrum.description
    0x04A  c32      title ("Background, HPS Show, Pitts,PA")             V
                    -> Spectrum.sample_id
    0x06A  c16      user ID ("Aptec")                                     V
    0x07A  c16      detector ID ("HPGe-30% Eff", "1x1 NaI(Tl)")           C -> detector
    0x08A  c16      geometry ID ("4Pi", "Bottle @10cm")                   C
    0x09A  c16      sample ID ("QCRB1241")                                C
    0x0AA  DT       sample (collection) start / decay reference date       ?
    0x0B2  DT       sample (collection) stop date                          ?
    0x0BA  c16      sample quantity units ("ml", "kg")                    C
    0x0CA  f32      sample quantity                                        ?
    0x11A  c16      second quantity unit ("mL", "point", "Rod")            ?
    0x12A  c16      activity units ("uCi", "Bq", "cps", "gamma/s")        C
    0x13A  DT       activity reference date                                ?
    0x14A  u16      nEff, number of 130-byte efficiency records            C (size eq.)
    0x14C  DT       efficiency calibration date                            ?
    0x154  c16      efficiency energy units ("keV")                        C
    0x1A2  c16      efficiency calibration detector / 0x1B2 geometry        C
    0x26A  u16      nEcal, energy calibration points                       V (points
                    lie on the curve, e.g. ch 423.0 -> 122.07 keV)
    0x26C  DT       energy calibration date
    0x274  c16      energy units ("keV"/"Kev")                             C
    0x284  u16      energy polynomial order k                              V
    0x286  6 x f64  energy coefficients c0..c5, E = sum c_i * ch^i (k+1 used),
                    0-based channel.  CHERNBKG: E(4096) = 808.081 keV and
                    E(0)=43.21, E(8191)=1572.8 keV exactly as on screen.  V
    0x2B6  u16      nFcal, FWHM calibration points                         V
    0x2B8  DT       FWHM calibration date
    0x2C0  c16      FWHM units ("channels" or empty = channels)            V (the
                    stored FWHM points, e.g. ch 3310.4 -> 5.83, fit the curve)
    0x2D0  u16      FWHM polynomial order
    0x2D2  6 x f64  FWHM coefficients, FWHM[ch] = sum f_i * ch^i            V
    0x30A  f32      1.645 (confidence-level k factor)                      ?
    0x30E  u16      nROI                                                   C (size eq.)
    0x310  u16      length of analysis-settings trailer (2514 or 0)        C
    0x312  u16      length of free-text comment after the trailer          C
    0x314  u16      1 (flag)
    0x316  u16      nCh, number of channels                                V
    0x31A  DT       acquisition start                                      V
    0x322  DT       acquisition stop                                       V
    0x32A  u32      real (true) time, ms         CHERNBKG 1500000 = 1500.000 s  V
    0x32E  u32      live time, ms                CHERNBKG 1451400 = 1451.400 s  V
    0x332  u32      live time again (occasionally differs by 1 ms)
    0x336  u32      gross counts, 59112 for CHERNBKG = channel sum           V
                    (equals the channel sum in 18 of 22 reference files; the
                    other 4 are slightly lower - probably an acquisition-time
                    snapshot, so it is only reported in ``extra``)
    0x340  16 bytes copy of 0x32A..0x339
    0x350  f32 x2   dead time % (3.24)                                     V
    0x358  f64 x3   gross count rate (counts/real s, counts/live s x2)     C
    0x378  char     preset mode: 'T' true time, 'L' live time, 'G' gross counts  C
    0x37A  u32      preset value (ms for T/L, counts for G); CHERNBKG 1500 s   V
    0x396  u16      ADC conversion gain (1024 for 512-ch NaI spectra)       ?
    0x37E..0x3FF    acquisition / MCA hardware settings (not decoded)

Section records (layouts partly decoded, all values go to ``extra``):

* 130-byte efficiency/source record: +0x02 c16 nuclide, +0x12 f32 energy keV,
  +0x16 f32 gamma yield.  (Am-241 59.54 keV 0.363 etc. - C)
* 256-byte ROI record: +0x00 4 x u16 channel markers (left background start,
  ROI start, ROI end, right background end), +0x3A c16 nuclide label,
  +0x4C f32 library energy keV, +0x50 f32 yield, +0x6C f32 centroid channel,
  +0x70 f64 gross area, +0x78 f64 background, +0x80 f64 net area,
  +0x88 f32 net area uncertainty, +0xA2 c16 rate units, +0xB2 f32 net rate.
  Verified on CHERNBKG ROI 1: channels 1035..1054 sum to exactly 500 = gross;
  net = gross - background; centroid 1046.37 -> 238.5 keV ~ Pb-212 238.6 keV;
  the five labels Pb-212, Pb-214, Tl-208, Bi-214, K-40 match the screenshot.
* Trailer (analysis settings, 2514 bytes): +0x35A/+0x368/+0x376 three 14-byte
  file-name slots, +0x504 background-subtraction file, +0x704 nuclide library
  ("isotope.lib", "NAI.LIB"), +0x904 "runtime.txt"; rest not decoded.

The writer emits a minimal but complete file: header + calibration polynomials
(no point lists, efficiency records or ROIs) + counts + the 2514-byte settings
trailer.  Hardware/analysis settings that are not decoded are copied verbatim
from a genuine Aptec PCMCA/WIN v6.3 file (QCY48.S0, embedded below), so every
byte the Aptec software might validate comes either from a real file or from a
field whose meaning is verified above.
"""
from __future__ import annotations

import base64
import math
import struct
import sys
import zlib
from array import array
from datetime import datetime, timedelta
from pathlib import Path

from ..model import Spectrum
from .base import FormatError, FormatSpec, register

ENCODING = "cp1256"
HEADER_SIZE = 0x400
EFF_REC = 130
ROI_REC = 256
SETTINGS_SIZE = 2514
MAGIC = b"VERSION6"

# Header offsets
O_VERSION, O_FNAME, O_LABEL, O_TITLE = 0x000, 0x010, 0x020, 0x04A
O_USER, O_DET, O_GEOM, O_SAMPLE = 0x06A, 0x07A, 0x08A, 0x09A
O_SAMPLE_START, O_SAMPLE_STOP, O_QTY_UNITS, O_QTY = 0x0AA, 0x0B2, 0x0BA, 0x0CA
O_ACT_UNITS, O_ACT_DATE, O_NEFF = 0x12A, 0x13A, 0x14A
O_NECAL, O_ECAL_DATE, O_EUNITS, O_EORDER, O_ECOEF = 0x26A, 0x26C, 0x274, 0x284, 0x286
O_NFCAL, O_FCAL_DATE, O_FUNITS, O_FORDER, O_FCOEF = 0x2B6, 0x2B8, 0x2C0, 0x2D0, 0x2D2
O_NROI, O_SETLEN, O_CMTLEN, O_FLAG, O_NCH = 0x30E, 0x310, 0x312, 0x314, 0x316
O_START, O_STOP, O_REAL, O_LIVE, O_LIVE2, O_GROSS = 0x31A, 0x322, 0x32A, 0x32E, 0x332, 0x336
O_DEAD, O_RATES, O_PRESET_MODE, O_PRESET, O_GAIN = 0x350, 0x358, 0x378, 0x37A, 0x396

# Header (1024 B) + settings trailer (2514 B) of a genuine Aptec PCMCA/WIN v6.3
# file (QCY48.S0, 4096 ch, uncalibrated); used as writer template.
_TEMPLATE_B64 = (
    "eNoLcw0K9vT3M9MzZgCDQOdIEwu9YAMGKHAsKElNVghw9nV21A/39FMILkhNLikqzWXAAKF5usmJ"
    "OZlJRYklqSl41A0VUJCfmVeCxE8uKEZVoMDHw8R+iJ2BocGeVm7IY55uzzDsQHZqGAqfmYpmM5Gr"
    "0SGm/xIwrC9xMjAwMjAIAEVMzPmkmI6wM4hr8oPoA8d0Gc5YQPCifH6oNnTRHzyz7UF43vvlx7yF"
    "Sx06WnkuFIciaIiuD/YhYJ0gq8BJyQHuDg4Fhv/8YPtZIAKMUDWMcIKBVR1I/GeHiF9gBym0YRDg"
    "w+9BUCg3MDFcYHCAQhaGUTAKBhGQhNIv7IN2yLW+DvwFLfsu2HMAEz4k6cuxMnEdB6b8aU4QORlg"
    "znEAqbNnhGUUaH4GaWBEy+NQMUZGJBk9oAn/+ZkYeIA5hI2X1QGii5GRUt+g1qT4eKNgFIyCgQOZ"
    "xfkl+QWpesDG62hgjEBQVJpXkpmbqldSUTKArnCuTM5JLVYIT8wD9p9I1o2orgDDdGUh"
)


# --------------------------------------------------------------------- helpers
def _u16(d: bytes, o: int) -> int:
    return struct.unpack_from("<H", d, o)[0]


def _u32(d: bytes, o: int) -> int:
    return struct.unpack_from("<I", d, o)[0]


def _f32(d: bytes, o: int) -> float:
    return struct.unpack_from("<f", d, o)[0]


def _str(d: bytes, o: int, n: int) -> str:
    raw = d[o:o + n].split(b"\0", 1)[0]
    return raw.decode(ENCODING, errors="replace").strip()


def _dt(d: bytes, o: int):
    hs, s, mi, h, day, mon, year = struct.unpack_from("<6BH", d, o)
    if year == 0 and mon == 0 and day == 0:
        return None
    try:
        return datetime(year, mon, day, h, mi, s, min(hs, 99) * 10000)
    except ValueError:
        return None


def _pack_dt(t) -> bytes:
    if t is None:
        return bytes(8)
    return struct.pack("<6BH", t.microsecond // 10000, t.second, t.minute, t.hour,
                       t.day, t.month, t.year)


def _poly(d: bytes, o_order: int, o_coef: int) -> list[float]:
    order = _u16(d, o_order)
    n = min(order + 1, 6) if order < 6 else 6
    c = list(struct.unpack_from("<6d", d, o_coef))[:n]
    c = [x if math.isfinite(x) else 0.0 for x in c]
    while c and c[-1] == 0.0:
        c.pop()
    return c


def _polymul(a: list[float], b: list[float]) -> list[float]:
    out = [0.0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i + j] += x * y
    return out


def _fmt(x: float) -> str:
    return f"{x:.6g}"


# ---------------------------------------------------------------------- reader
def read_aptec(path: Path) -> list[Spectrum]:
    path = Path(path)
    try:
        d = path.read_bytes()
    except OSError as exc:
        raise FormatError(f"cannot read {path.name}: {exc}") from exc
    return [parse_aptec(d, path.name)]


def parse_aptec(d: bytes, name: str = "") -> Spectrum:
    if len(d) < HEADER_SIZE or not d.startswith(MAGIC):
        raise FormatError(f"{name}: not an APTEC v6 .S0 file (missing VERSION6 header)")
    n_eff, n_ecal, n_fcal = _u16(d, O_NEFF), _u16(d, O_NECAL), _u16(d, O_NFCAL)
    n_roi, n_ch = _u16(d, O_NROI), _u16(d, O_NCH)
    set_len, cmt_len = _u16(d, O_SETLEN), _u16(d, O_CMTLEN)
    if n_ch == 0:
        raise FormatError(f"{name}: header declares 0 channels")
    o_eff = HEADER_SIZE
    o_ecal = o_eff + EFF_REC * n_eff
    o_fcal = o_ecal + 8 * n_ecal
    o_roi = o_fcal + 8 * n_fcal
    o_counts = o_roi + ROI_REC * n_roi
    o_trailer = o_counts + 4 * n_ch
    if o_trailer > len(d):
        raise FormatError(f"{name}: truncated APTEC file ({len(d)} bytes, "
                          f"channel data needs {o_trailer})")
    extra: dict = {}
    expected = o_trailer + set_len + cmt_len
    if expected != len(d):
        extra["layout_warning"] = f"file size {len(d)} != expected {expected}"

    cnt = array("I")
    if cnt.itemsize != 4:  # pragma: no cover - exotic platforms
        cnt = array("L")
    cnt.frombytes(d[o_counts:o_trailer])
    if sys.byteorder != "little":  # pragma: no cover
        cnt.byteswap()
    counts = cnt.tolist()

    # -- calibrations
    e_units = _str(d, O_EUNITS, 16)
    ecoef = _poly(d, O_EORDER, O_ECOEF)
    scale = {"mev": 1000.0, "ev": 0.001}.get(e_units.lower(), 1.0)
    energy_coeffs: list[float] = []
    if len(ecoef) >= 2 and ecoef[1] != 0.0 and e_units.lower() in ("", "kev", "mev", "ev"):
        energy_coeffs = [c * scale for c in ecoef]
    elif ecoef:
        extra["energy_coeffs_raw"] = ", ".join(_fmt(c) for c in ecoef)
    extra["energy_units"] = e_units

    f_units = _str(d, O_FUNITS, 16)
    fcoef = _poly(d, O_FORDER, O_FCOEF)
    fwhm_coeffs: list[float] = []
    if fcoef and any(fcoef):
        extra["fwhm_coeffs_raw"] = ", ".join(_fmt(c) for c in fcoef)
        extra["fwhm_units"] = f_units or "channels"
        if f_units.lower() == "kev":
            fwhm_coeffs = list(fcoef)
        elif f_units.lower() in ("", "channels", "channel") and energy_coeffs:
            # FWHM[keV](ch) ~= FWHM[ch](ch) * dE/dch  (exact polynomial product)
            deriv = [i * c for i, c in enumerate(energy_coeffs)][1:]
            fwhm_coeffs = _polymul(fcoef, deriv)

    if n_ecal:
        pts = struct.unpack_from(f"<{2 * n_ecal}f", d, o_ecal)
        extra["energy_cal_points"] = "; ".join(
            f"{_fmt(pts[2 * i])}:{_fmt(pts[2 * i + 1])}" for i in range(n_ecal))
    if n_fcal:
        pts = struct.unpack_from(f"<{2 * n_fcal}f", d, o_fcal)
        extra["fwhm_cal_points"] = "; ".join(
            f"{_fmt(pts[2 * i])}:{_fmt(pts[2 * i + 1])}" for i in range(n_fcal))
    for key, off in (("energy_cal_date", O_ECAL_DATE), ("fwhm_cal_date", O_FCAL_DATE)):
        t = _dt(d, off)
        if t:
            extra[key] = t.isoformat(sep=" ")

    # -- times
    real = _u32(d, O_REAL) / 1000.0
    live = _u32(d, O_LIVE) / 1000.0
    start = _dt(d, O_START)
    stop = _dt(d, O_STOP)
    if stop:
        extra["stop_time"] = stop.isoformat(sep=" ")
    extra["gross_counts"] = _u32(d, O_GROSS)
    extra["dead_time_percent_stored"] = round(_f32(d, O_DEAD), 4)
    mode = chr(d[O_PRESET_MODE]) if 32 < d[O_PRESET_MODE] < 127 else ""
    pv = _u32(d, O_PRESET)
    if mode:
        extra["preset_mode"] = {"T": "real time", "L": "live time",
                                "G": "gross counts"}.get(mode, mode)
        extra["preset_value"] = pv / 1000.0 if mode in "TL" else pv

    # -- strings
    title = _str(d, O_TITLE, 32)
    label = _str(d, O_LABEL, 42)
    extra["aptec_version"] = _str(d, O_VERSION, 16)
    extra["file_name_field"] = _str(d, O_FNAME, 16)
    for key, off in (("user_id", O_USER), ("geometry_id", O_GEOM),
                     ("aptec_sample_id", O_SAMPLE), ("quantity_units", O_QTY_UNITS),
                     ("activity_units", O_ACT_UNITS)):
        s = _str(d, off, 16)
        if s:
            extra[key] = s
    for key, off in (("sample_start", O_SAMPLE_START), ("sample_stop", O_SAMPLE_STOP),
                     ("activity_ref_date", O_ACT_DATE)):
        t = _dt(d, off)
        if t:
            extra[key] = t.isoformat(sep=" ")
    q = _f32(d, O_QTY)
    if q and math.isfinite(q):
        extra["quantity"] = q

    # -- efficiency / source records
    if n_eff:
        items = []
        for i in range(n_eff):
            o = o_eff + EFF_REC * i
            items.append(f"{_str(d, o + 2, 16)}:{_fmt(_f32(d, o + 0x12))} keV"
                         f" y={_fmt(_f32(d, o + 0x16))}")
        extra["efficiency_points"] = "; ".join(items)

    # -- ROIs / peaks
    extra["roi_count"] = n_roi
    if n_roi:
        rois, names = [], []
        for i in range(n_roi):
            o = o_roi + ROI_REC * i
            m = struct.unpack_from("<4H", d, o)
            nuc = _str(d, o + 0x3A, 16)
            en = _f32(d, o + 0x4C)
            cen = _f32(d, o + 0x6C)
            gross, bkg, net = struct.unpack_from("<3d", d, o + 0x70)
            s = f"{m[1]}-{m[2]} bg {m[0]}/{m[3]}"
            if nuc:
                names.append(nuc)
                s += f" {nuc} {_fmt(en)} keV"
            s += f" centroid={_fmt(cen)} gross={_fmt(gross)} net={_fmt(net)}"
            rois.append(s)
        extra["rois"] = " | ".join(rois)
        if names:
            extra["roi_nuclides"] = ", ".join(dict.fromkeys(names))

    # -- trailer
    if set_len >= SETTINGS_SIZE and o_trailer + SETTINGS_SIZE <= len(d):
        lib = _str(d, o_trailer + 0x704, 64)
        bkg = _str(d, o_trailer + 0x504, 64)
        if lib:
            extra["library"] = lib
        if bkg:
            extra["background_file"] = bkg
    if cmt_len and o_trailer + set_len + cmt_len <= len(d):
        c = d[o_trailer + set_len:o_trailer + set_len + cmt_len]
        extra["comment"] = c.split(b"\0", 1)[0].decode(ENCODING, errors="replace").strip()

    return Spectrum(
        counts=counts,
        energy_coeffs=energy_coeffs,
        live_time=live if _u32(d, O_LIVE) else None,
        real_time=real if _u32(d, O_REAL) else None,
        start_time=start,
        sample_id=title,
        description=label,
        detector=_str(d, O_DET, 16),
        fwhm_coeffs=fwhm_coeffs,
        extra=extra,
    )


# --------------------------------------------------------------------- sniffer
def sniff_aptec(path: Path, head: bytes) -> bool:
    if not head.startswith(MAGIC) or len(head) < O_NCH + 2:
        return False
    return 0 < _u16(head, O_NCH) <= 65535


# ---------------------------------------------------------------------- writer
def _put_str(buf: bytearray, off: int, size: int, s: str) -> None:
    raw = (s or "").encode(ENCODING, errors="replace")[:size - 1]
    buf[off:off + size] = raw + bytes(size - len(raw))


def _short_name(name: str) -> str:
    p = Path(name)
    stem, ext = p.stem.upper(), p.suffix.upper()[:4]
    if len(stem) <= 8 and len(stem) + len(ext) <= 15 and " " not in stem:
        return stem + ext
    clean = "".join(ch for ch in stem if ch.isalnum() or ch in "-_")[:6]
    return f"{clean}~1{ext}"


def write_aptec(spec: Spectrum, path: Path) -> None:
    path = Path(path)
    n = len(spec.counts)
    if not 0 < n <= 65535:
        raise FormatError(f"APTEC S0 needs 1..65535 channels, got {n}")
    if len(spec.energy_coeffs) > 6 or len(spec.fwhm_coeffs) > 6:
        raise FormatError("APTEC S0 supports at most 6 calibration coefficients")
    counts = []
    for c in spec.counts:
        v = int(round(float(c)))
        if v < 0 or v > 0xFFFFFFFF:
            raise FormatError(f"count {c} does not fit an unsigned 32-bit channel")
        counts.append(v)

    tmpl = zlib.decompress(base64.b64decode(_TEMPLATE_B64))
    hdr = bytearray(tmpl[:HEADER_SIZE])
    trailer = bytearray(tmpl[HEADER_SIZE:])
    # wipe every sample-specific field of the template
    hdr[O_FNAME:O_NEFF + 2] = bytes(O_NEFF + 2 - O_FNAME)
    hdr[O_NECAL:O_NROI + 2] = bytes(O_NROI + 2 - O_NECAL)
    hdr[0x318:O_PRESET + 4] = bytes(O_PRESET + 4 - 0x318)
    hdr[0x308:0x30E] = tmpl[0x308:0x30E]  # 1.645 confidence factor
    hdr[0x370:0x378] = tmpl[0x370:0x378]  # f64 1.0

    ex = spec.extra or {}
    short = _short_name(path.name)
    _put_str(hdr, O_FNAME, 16, short)
    _put_str(hdr, O_LABEL, 42, spec.description or "Aptec PCMCA/WIN Spectrum")
    _put_str(hdr, O_TITLE, 32, spec.sample_id)
    _put_str(hdr, O_USER, 16, str(ex.get("user_id", "")))
    _put_str(hdr, O_DET, 16, spec.detector)
    _put_str(hdr, O_GEOM, 16, str(ex.get("geometry_id", "")))
    _put_str(hdr, O_SAMPLE, 16, str(ex.get("aptec_sample_id", "")))
    _put_str(hdr, O_ACT_UNITS, 16, str(ex.get("activity_units", "cps")))

    # energy calibration (polynomial only, no point list)
    _put_str(hdr, O_EUNITS, 16, "keV")
    if spec.energy_coeffs:
        ec = [float(c) for c in spec.energy_coeffs]
        struct.pack_into("<H", hdr, O_EORDER, len(ec) - 1)
        struct.pack_into(f"<{len(ec)}d", hdr, O_ECOEF, *ec)
    else:
        struct.pack_into("<H", hdr, O_EORDER, 1)
    # FWHM calibration: S0 stores it in channels.  Only exact for a linear
    # energy calibration (FWHM_ch = FWHM_keV / slope).
    ec = spec.energy_coeffs
    if spec.fwhm_coeffs and len(ec) >= 2 and ec[1] and not any(ec[2:]):
        fc = [float(c) / float(ec[1]) for c in spec.fwhm_coeffs]
        _put_str(hdr, O_FUNITS, 16, "channels")
        struct.pack_into("<H", hdr, O_FORDER, len(fc) - 1)
        struct.pack_into(f"<{len(fc)}d", hdr, O_FCOEF, *fc)
    else:
        struct.pack_into("<H", hdr, O_FORDER, 1)

    struct.pack_into("<HHHHH", hdr, O_NROI, 0, SETTINGS_SIZE, 0, 1, n)
    start = spec.start_time
    real_ms = int(round((spec.real_time or spec.live_time or 0.0) * 1000))
    live_ms = int(round((spec.live_time or spec.real_time or 0.0) * 1000))
    gross = sum(counts)
    stop = None
    if start is not None and real_ms:
        stop = start + timedelta(milliseconds=real_ms)
    hdr[O_START:O_START + 8] = _pack_dt(start)
    hdr[O_STOP:O_STOP + 8] = _pack_dt(stop)
    times = struct.pack("<IIII", real_ms, live_ms, live_ms, gross & 0xFFFFFFFF)
    hdr[O_REAL:O_REAL + 16] = times
    hdr[0x340:0x350] = times
    dead = 100.0 * (real_ms - live_ms) / real_ms if real_ms else 0.0
    struct.pack_into("<ff", hdr, O_DEAD, dead, dead)
    struct.pack_into("<ddd", hdr, O_RATES, gross / real_ms * 1000 if real_ms else 0.0,
                     gross / live_ms * 1000 if live_ms else 0.0,
                     gross / live_ms * 1000 if live_ms else 0.0)
    hdr[O_PRESET_MODE] = ord("L")
    struct.pack_into("<I", hdr, O_PRESET, live_ms)
    struct.pack_into("<H", hdr, O_GAIN, n)    # = channels, as pcmca's FILLINSPCHEADER sets it
    # 0x38E is left as in the template: genuine files hold 0 (or 511/512), not the channel count

    # settings trailer: the three file-name slots refer to the spectrum itself
    for off in (0x35A, 0x368, 0x376):
        _put_str(trailer, off, 14, short)

    data = array("I", counts)
    if sys.byteorder != "little":  # pragma: no cover
        data.byteswap()
    path.write_bytes(bytes(hdr) + data.tobytes() + bytes(trailer))


register(FormatSpec(
    code=13, key="aptec_s0", name="APTEC v6.3", extensions=[".s0"],
    reader=read_aptec, writer=write_aptec, sniffer=sniff_aptec,
    notes="Aptec PCMCA/WIN v6.x binary; reader decodes counts, times, calibrations, "
          "ROIs; writer emits header+calibration+counts with a genuine settings block.",
    aliases=["aptec", "s0"],
))

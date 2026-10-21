"""Formats backed by Sandia's SpecUtils (pip package ``SandiaSpecUtils``, LGPL-2.1).

Codes (see ``formats/__init__.py``):

    1 ortec_chn     ORTEC .chn         r/w  (own implementation, SpecUtils' CHN reader
                                             zeroes the first/last channels)
    2 ortec_spc     ORTEC integer SPC   r/w
    7 iaea_spe      IAEA SPE            r/w
   10 rms_phd       RMS/IMS PHD         r
   16 ci_cnf        Canberra CAM CNF    r/w  (start time read/written by us, see below)
   20-43            N42, PCF, CSV, TXT, TKA, HTML, SPC variants, Exploranium,
                    and read-only vendor formats.

Energy calibration convention
-----------------------------
SpecUtils stores polynomial coefficients exactly as found in the file and calls
``poly(i)`` the energy of channel ``i`` (it labels that the lower edge).  ORTEC,
Canberra and IAEA SPE files use the very same numbers with ``i`` = channel number,
which is what :class:`~spectramaster.model.Spectrum` means by ``energy_coeffs``.
Therefore polynomial coefficients are passed through *unchanged* in both directions
(no half-channel shift); this keeps CHN -> SPE -> CNF ... conversions bit-faithful,
like DataMaster.  Full-range-fraction calibrations (PCF) are converted with
SpecUtils' own ``fullRangeFractionCoefToPolynomial``; lower-channel-edge lists
(CSV/TXT) are least-squares fitted with a quadratic (cubic if needed) in channel
number.  A non-zero ``first_channel`` is folded into the polynomial on write,
because SpecUtils has no channel-offset concept (CHN keeps it natively).
"""
from __future__ import annotations

import contextlib
import io
import math
import re
import os
import struct
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from ..model import Spectrum
from .base import FormatError, FormatSpec, register

try:        # the native library; without it only the pure-Python CHN and CNF code is registered
    import SpecUtils as _SU
except ImportError as _exc:
    import logging
    logging.getLogger(__name__).warning("SpecUtils not available (%s): only ORTEC CHN and Canberra CNF "
                                        "are registered by this module", _exc)
    _SU = None


class _Missing:
    """Stand-in for SpecUtils' enums when the library is missing (every member is None)."""
    def __getattr__(self, name):
        return None


P = _SU.ParserType if _SU is not None else _Missing()
W = _SU.SaveSpectrumAsType if _SU is not None else _Missing()


# --------------------------------------------------------------------- helpers
@contextlib.contextmanager
def _quiet_native():
    """Silence messages that the C++ library prints straight to fd 1/2."""
    saved = []
    try:
        for s in (sys.stdout, sys.stderr):
            try:
                s.flush()
            except Exception:
                pass
        devnull = os.open(os.devnull, os.O_WRONLY)
        for fd in (1, 2):
            try:
                saved.append((fd, os.dup(fd)))
                os.dup2(devnull, fd)
            except OSError:
                pass
        os.close(devnull)
    except OSError:
        pass
    try:
        yield
    finally:
        for fd, dup in saved:
            try:
                os.dup2(dup, fd)
                os.close(dup)
            except OSError:
                pass


# SpecUtils keeps times as "UTC" time points that hold the file's wall-clock time;
# its Python binding converts them to/from *local* naive datetimes.  These two helpers
# undo that, so file wall-clock time in == wall-clock time out (N42 '...Z' times keep
# their UTC wall clock).
def _utc_offset_now() -> timedelta:
    off = datetime.now().astimezone().utcoffset()
    return off if off is not None else timedelta(0)


def _from_su(dt: datetime) -> datetime:
    """Binding (local naive) -> file wall clock."""
    dt = dt.replace(tzinfo=None) if dt.tzinfo is None else dt.astimezone().replace(tzinfo=None)
    try:
        return datetime.fromtimestamp(dt.timestamp(), timezone.utc).replace(tzinfo=None)
    except (OSError, OverflowError, ValueError):  # pre-1970 on Windows
        return dt - _utc_offset_now()


def _to_su(dt: datetime) -> datetime:
    """File wall clock -> local naive datetime for the binding."""
    dt = dt.replace(tzinfo=None)
    try:
        return datetime.fromtimestamp(dt.replace(tzinfo=timezone.utc).timestamp())
    except (OSError, OverflowError, ValueError):
        return dt + _utc_offset_now()


def _is_null_time(dt: Optional[datetime]) -> bool:
    """`dt` already converted with _from_su; SpecUtils' 'no time' is the epoch."""
    if dt is None:
        return True
    return dt.year < 1900 or dt == datetime(1970, 1, 1)


def _shift_poly(coeffs: list[float], offset: float) -> list[float]:
    """Coefficients of q(i) = p(i + offset)."""
    n = len(coeffs)
    out = [0.0] * n
    for k, c in enumerate(coeffs):
        for j in range(k + 1):
            out[j] += c * math.comb(k, j) * offset ** (k - j)
    return out


def _fit_edges(edges: list[float]) -> list[float]:
    import numpy as np
    y = np.asarray(edges, dtype=float)
    x = np.arange(len(y), dtype=float)
    if len(y) < 2:
        return []
    best = []
    span = max(abs(y[-1] - y[0]), 1e-9)
    for deg in (1, 2, 3):
        if len(y) <= deg:
            break
        c = np.polynomial.polynomial.polyfit(x, y, deg)
        resid = float(np.max(np.abs(np.polynomial.polynomial.polyval(x, c) - y)))
        best = [float(v) for v in c]
        if resid <= 1e-5 * span + 1e-4:
            break
    return best


def _f32(x: float) -> float:
    """Strip float32 noise (SpecUtils stores single precision): 0.38999998569 -> 0.39."""
    x = float(x)
    if x == 0.0 or not math.isfinite(x):
        return x
    return float(f"{x:.7g}")


def _coeffs_from_measurement(m) -> list[float]:
    model = m.energyCalibrationModel()
    coeffs = [float(c) for c in m.calibrationCoeffs()]
    n = m.numGammaChannels()
    if model == _SU.EnergyCalType.Polynomial:
        coeffs = [_f32(c) for c in coeffs]
    elif model == _SU.EnergyCalType.FullRangeFraction:
        coeffs = [_f32(c) for c in _SU.fullRangeFractionCoefToPolynomial(coeffs, n)]
    elif model == _SU.EnergyCalType.LowerChannelEdge:
        coeffs = _fit_edges(coeffs)
    else:  # UnspecifiedUsingDefaultPolynomial / Invalid -> not a real calibration
        return []
    while len(coeffs) > 2 and coeffs[-1] == 0.0:
        coeffs.pop()
    if not coeffs or all(c == 0.0 for c in coeffs):
        return []
    return coeffs


_ID_PREFIXES = ("Sample ID:", "Sample Description:", "Title:", "Detector Description:")


def _measurement_to_spectrum(sf, m, file_remarks: list[str]) -> Spectrum:
    counts = [float(c) for c in m.gammaCounts()]
    remarks = [str(r).strip() for r in m.remarks() if str(r).strip()]
    title = (m.title() or "").strip()
    used: set[str] = set()
    if not title:
        for prefix in _ID_PREFIXES:
            for r in remarks + file_remarks:
                if r.startswith(prefix) and r[len(prefix):].strip():
                    title = r[len(prefix):].strip()
                    used.add(r)
                    break
            if title:
                break
    for r in remarks + file_remarks:
        if r.startswith(_ID_PREFIXES) and r[r.index(":") + 1:].strip() in ("", title):
            used.add(r)  # empty or duplicate "Sample ID:" style lines
    desc = "\n".join(r for r in remarks if r not in used)
    try:
        st = _from_su(m.startTime())
    except Exception:
        st = None
    start = None if _is_null_time(st) else st
    lt = m.liveTime()
    rt = m.realTime()
    det = (m.detectorName() or "").strip()
    extra: dict = {}
    for key, fn in (("manufacturer", sf.manufacturer), ("instrument_model", sf.instrumentModel),
                    ("instrument_id", sf.instrumentId), ("uuid", sf.uuid)):
        try:
            v = (fn() or "").strip()
        except Exception:
            v = ""
        if v:
            extra[key] = v
    if det:
        extra["detector_name"] = det
    try:
        dtype = (m.detectorType() or "").strip()     # e.g. N42 <DetectorType>HPGe 50%</DetectorType>
    except Exception:
        dtype = ""
    if dtype:
        extra["detector_type"] = dtype
    try:
        extra["sample_number"] = int(m.sampleNumber())
    except Exception:
        pass
    other = [r for r in file_remarks if r not in used]
    if other:
        extra["file_remarks"] = "\n".join(other)
    detector = det
    return Spectrum(
        counts=counts,
        energy_coeffs=_coeffs_from_measurement(m),
        live_time=_f32(lt) if lt and lt > 0 else None,
        real_time=_f32(rt) if rt and rt > 0 else None,
        start_time=start,
        sample_id=title,
        description=desc,
        detector=detector,
        extra=extra,
    )


def _load_specfile(path: Path, parser) -> "_SU.SpecFile":
    path = Path(path)
    if not path.is_file():
        raise FormatError(f"file not found: {path}")
    sf = _SU.SpecFile()
    try:
        with _quiet_native():
            sf.loadFile(str(path), parser, path.suffix.lstrip("."))
    except Exception as exc:
        raise FormatError(f"{path.name}: not a valid {parser.name} file ({exc.__class__.__name__})") from None
    return sf


def _read_with(path: Path, parser) -> list[Spectrum]:
    sf = _load_specfile(path, parser)
    file_remarks = [str(r).strip() for r in sf.remarks() if str(r).strip()]
    out = []
    foreground = []
    for m in sf.measurements():
        if m.numGammaChannels() <= 0:
            continue
        s = _measurement_to_spectrum(sf, m, file_remarks)
        try:
            kind = m.sourceType().name
        except Exception:
            kind = "UnknownSourceType"
        if kind != "UnknownSourceType":
            s.extra["source_type"] = kind
        (foreground if kind == "Foreground" else out).append(s)
    out = foreground + out  # foreground first (e.g. RASE files store the background first)
    if not out:
        raise FormatError(f"{Path(path).name}: no gamma spectrum in file")
    return out


def _build_specfile(spec: Spectrum) -> "_SU.SpecFile":
    if len(spec.counts) == 0:
        raise FormatError("spectrum has no channels")
    n = len(spec.counts)
    m = _SU.Measurement.new()
    lt = float(spec.live_time or 0.0)
    rt = float(spec.real_time or 0.0)
    m.setGammaCounts([float(c) for c in spec.counts], lt, rt)
    if spec.energy_coeffs:
        coeffs = list(spec.energy_coeffs)
        if spec.first_channel:
            coeffs = _shift_poly(coeffs, spec.first_channel)
        try:
            m.setEnergyCalibration(_SU.EnergyCalibration.fromPolynomial(n, [float(c) for c in coeffs]))
        except Exception:
            # SpecUtils rejects non-monotonic calibrations; write uncalibrated rather than fail
            pass
    if spec.start_time is not None:
        m.setStartTime(_to_su(spec.start_time))
    if spec.sample_id:
        m.setTitle(spec.sample_id)
    if spec.description:
        m.setRemarks([ln for ln in spec.description.splitlines() if ln.strip()])
    if spec.detector:
        m.setDetectorName(spec.detector)
    sf = _SU.SpecFile()
    sf.addMeasurement(m, True)
    return sf


def _write_bytes(spec: Spectrum, kind) -> bytes:
    sf = _build_specfile(spec)
    bio = io.BytesIO()
    try:
        with _quiet_native():
            sf.writeToStream(bio, sf.sampleNumbers(), sf.detectorNames(), kind)
    except Exception as exc:
        raise FormatError(f"SpecUtils could not write {kind.name}: {exc}") from None
    data = bio.getvalue()
    if not data:
        raise FormatError(f"SpecUtils produced an empty {kind.name} file")
    return data


def _writer(kind, post=None):
    def write(spec: Spectrum, path: Path) -> None:
        data = _write_bytes(spec, kind)
        if post is not None:
            data = post(spec, data)
        Path(path).write_bytes(data)
    return write


def _reader(parser):
    def read(path: Path) -> list[Spectrum]:
        return _read_with(path, parser)
    return read


# ------------------------------------------------------------------ ORTEC CHN
_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
# CHN always holds a date: an unknown start is written as 2000-01-01 00:00:00 and read
# back as unknown (an MCA clock that was never set gives the same placeholder).
_CHN_NO_DATE = (b"00", b"01JAN001", b"0000")


def _chn_read(path: Path) -> list[Spectrum]:
    b = Path(path).read_bytes()
    if len(b) < 32 or struct.unpack_from("<h", b, 0)[0] != -1:
        raise FormatError(f"{Path(path).name}: not an ORTEC CHN file")
    mca, seg = struct.unpack_from("<HH", b, 2)
    secs = b[6:8].decode("ascii", "replace")
    real_ticks, live_ticks = struct.unpack_from("<ii", b, 8)
    date = b[16:24].decode("ascii", "replace")
    hhmm = b[24:28].decode("ascii", "replace")
    offset, nch = struct.unpack_from("<HH", b, 28)
    if len(b) < 32 + 4 * nch:
        raise FormatError(f"{Path(path).name}: truncated CHN file")
    counts = [float(c) for c in struct.unpack_from(f"<{nch}I", b, 32)]
    start = None
    if (secs.encode(), date.encode(), hhmm.encode()) == _CHN_NO_DATE:
        date = ""                      # the placeholder of an unknown start time
    try:
        day = int(date[0:2]); mon = _MONTHS.index(date[2:5].upper()); yy = int(date[5:7])
        # ORTEC: 8th char '1' = 2000s, '0' = 1900s.  Older writers leave it blank/NUL;
        # CHN dates back to the mid-1980s, so pivot those at 80 (yy < 80 -> 20yy).
        century = date[7:8]
        if century == "1":
            year = 2000 + yy
        elif century == "0":
            year = 1900 + yy
        else:
            year = 2000 + yy if yy < 80 else 1900 + yy
        sec_txt = secs.strip("\x00 ")
        sec = int(sec_txt) if sec_txt else 0  # some writers leave the seconds field NUL
        start = datetime(year, mon + 1, day, int(hhmm[0:2]), int(hhmm[2:4]), sec)
    except (ValueError, IndexError):
        start = None
    spec = Spectrum(counts=counts, live_time=live_ticks * 0.02 if live_ticks > 0 else None,
                    real_time=real_ticks * 0.02 if real_ticks > 0 else None,
                    start_time=start, first_channel=offset)
    spec.extra["mca_number"] = mca
    spec.extra["segment"] = seg
    t = 32 + 4 * nch
    if len(b) >= t + 28:
        kind = struct.unpack_from("<h", b, t)[0]
        if kind in (-101, -102):
            e = list(struct.unpack_from("<3f", b, t + 4))
            f = list(struct.unpack_from("<3f", b, t + 16))
            if kind == -101:
                e[2] = 0.0
                f[2] = 0.0
            e = [float(v) for v in e]
            if any(e) and all(math.isfinite(v) for v in e):
                while len(e) > 2 and e[-1] == 0.0:
                    e.pop()
                spec.energy_coeffs = e
            f = [float(v) for v in f]
            if any(f) and all(math.isfinite(v) for v in f):
                while len(f) > 1 and f[-1] == 0.0:
                    f.pop()
                spec.fwhm_coeffs = f
            if len(b) >= t + 384:
                def pstr(off):
                    ln = min(b[off], 63)
                    return b[off + 1:off + 1 + ln].decode("latin-1", "replace").rstrip("\x00 ").strip()
                spec.detector = pstr(t + 256)
                spec.sample_id = pstr(t + 320)
    return [spec]


def _chn_write(spec: Spectrum, path: Path) -> None:
    n = len(spec.counts)
    if n == 0 or n > 65535:
        raise FormatError(f"CHN supports 1..65535 channels, spectrum has {n}")
    counts = []
    for c in spec.counts:
        v = int(round(float(c)))
        if v < 0:
            raise FormatError(f"CHN cannot store a negative count ({c:g})")
        if v > 0xFFFFFFFF:
            raise FormatError("channel content exceeds 32-bit CHN range")
        counts.append(v)
    st = spec.start_time
    if st is not None:
        secs = f"{st.second:02d}".encode()
        date = (f"{st.day:02d}{_MONTHS[st.month - 1]}{st.year % 100:02d}"
                + ("1" if st.year >= 2000 else "0")).encode()
        hhmm = f"{st.hour:02d}{st.minute:02d}".encode()
    else:
        secs, date, hhmm = _CHN_NO_DATE
    rt = int(round((spec.real_time or 0.0) * 50))
    lt = int(round((spec.live_time or 0.0) * 50))
    first = int(spec.first_channel or 0)
    if not 0 <= first <= 65535:
        first = 0
    out = bytearray()
    out += struct.pack("<hHH", -1, int(spec.extra.get("mca_number", 0) or 0) & 0xFFFF,
                       int(spec.extra.get("segment", 1) or 1) & 0xFFFF)
    out += secs[:2] + struct.pack("<ii", rt, lt) + date[:8] + hhmm[:4]
    out += struct.pack("<HH", first, n)
    out += struct.pack(f"<{n}I", *counts)
    e = (list(spec.energy_coeffs) + [0.0, 0.0, 0.0])[:3]
    f = (list(spec.fwhm_coeffs) + [0.0, 0.0, 0.0])[:3]
    trailer = bytearray(512)
    struct.pack_into("<hh", trailer, 0, -102, 0)
    struct.pack_into("<3f", trailer, 4, *[float(v) for v in e])
    struct.pack_into("<3f", trailer, 16, *[float(v) for v in f])

    def put(off, text):
        raw = (text or "").encode("latin-1", "replace")[:63]
        trailer[off] = len(raw)
        trailer[off + 1:off + 1 + len(raw)] = raw
    put(256, spec.detector)
    sample = spec.sample_id or (spec.description.strip().splitlines() or [""])[0]
    put(320, sample)
    out += trailer
    Path(path).write_bytes(bytes(out))


def _chn_sniff(path: Path, head: bytes) -> bool:
    if len(head) < 32 or struct.unpack_from("<h", head, 0)[0] != -1:
        return False
    nch = struct.unpack_from("<H", head, 30)[0]
    try:
        size = path.stat().st_size
    except OSError:
        return False
    end = 32 + 4 * nch
    if nch == 0 or size < end:
        return False
    if size <= end + 1024:
        return True
    # longer files (extra data after the trailer): require the -101/-102 trailer marker
    try:
        with open(path, "rb") as fh:
            fh.seek(end)
            marker = fh.read(2)
    except OSError:
        return False
    return len(marker) == 2 and struct.unpack("<h", marker)[0] in (-101, -102)


# ------------------------------------------------------- SpecUtils-style CSV
def _csv_read(path: Path) -> list[Spectrum]:
    """'Energy, Data' / 'Channel, Data' two-column CSV.

    Parsed here because SpecUtils' reader drops leading rows with negative energy.
    Anything else is handed to SpecUtils' generic TXT/CSV parser.
    """
    text = Path(path).read_bytes().decode("utf-8-sig", "replace")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise FormatError(f"{Path(path).name}: empty file")
    hdr = lines[0].replace(" ", "").lower()
    if hdr not in ("energy,data", "channel,data"):
        return _read_with(path, P.TxtOrCsv)
    xs, ys = [], []
    for ln in lines[1:]:
        parts = [p for p in ln.replace(";", ",").split(",") if p.strip()]
        if len(parts) < 2:
            continue
        try:
            xs.append(float(parts[0])); ys.append(float(parts[1]))
        except ValueError:
            raise FormatError(f"{Path(path).name}: bad CSV line {ln[:40]!r}") from None
    if not ys:
        raise FormatError(f"{Path(path).name}: no data rows")
    spec = Spectrum(counts=ys)
    if hdr.startswith("energy"):
        spec.energy_coeffs = [_f32(c) for c in _fit_edges(xs)]
    return [spec]


# ------------------------------------------------------------- Canberra CNF
_CAM_EPOCH = datetime(1858, 11, 17)


def _cam_blocks(b: bytes) -> dict[int, tuple[int, int, int]]:
    """{block id: (offset, size, directory entry offset)} from the CAM directory."""
    out: dict[int, tuple[int, int, int]] = {}
    for i in range(29):
        h = 0x70 + i * 0x30
        if h + 0x30 > len(b):
            break
        sid = struct.unpack_from("<I", b, h)[0]
        if sid == 0:
            break
        out[sid] = (struct.unpack_from("<I", b, h + 0x0A)[0], struct.unpack_from("<I", b, h + 6)[0], h)
    return out


_ACQ, _SAMP, _DATA, _DETB = 0x12000, 0x12001, 0x12005, 0x12002


def _cnf_time_offset(b: bytes) -> Optional[int]:
    """Byte offset of the acquisition start time (64-bit, 100 ns since 1858-11-17).

    Followed by real time and live time as negative 64-bit 100 ns counts."""
    acq = _cam_blocks(b).get(_ACQ)
    if acq is None or acq[0] + 0x26 > len(b):
        return None
    off = acq[0]
    rel = struct.unpack_from("<H", b, off + 0x24)[0]
    pos = off + 0x30 + rel + 1
    return pos if pos + 24 <= len(b) else None


def _cam_text(b: bytes, off: int, n: int) -> str:
    raw = b[off:off + n].split(b"\x00", 1)[0]
    if any(c < 0x20 for c in raw):
        return ""
    return raw.decode("latin-1").strip()


def _from_pdp11(raw: bytes) -> float:
    return struct.unpack("<f", raw[2:4] + raw[0:2])[0] / 4.0


def _cnf_native(b: bytes) -> Spectrum:
    """Minimal CAM reader (counts, times, calibration); used when SpecUtils gives up,
    e.g. for 65536-channel files."""
    blocks = _cam_blocks(b)
    if _DATA not in blocks or _ACQ not in blocks:
        raise FormatError("CNF file has no spectrum/acquisition block")
    d_off, _, h = blocks[_DATA]
    n = struct.unpack_from("<I", b, h + 0x2A)[0]
    if not 0 < n <= 1 << 20 or d_off + 0x200 + 4 * n > len(b):
        raise FormatError("CNF data block is inconsistent")
    spec = Spectrum(counts=[float(c) for c in struct.unpack_from(f"<{n}I", b, d_off + 0x200)])
    pos = _cnf_time_offset(b)
    if pos is not None:
        rt, lt = struct.unpack_from("<qq", b, pos + 8)
        spec.real_time = -rt / 1e7 if rt < 0 else None
        spec.live_time = -lt / 1e7 if lt < 0 else None
    acq = blocks[_ACQ][0]
    cal = acq + 0x30 + struct.unpack_from("<H", b, acq + 0x22)[0] + 0x44
    if cal + 12 <= len(b):
        c = [_f32(_from_pdp11(b[cal + 4 * k:cal + 4 * k + 4])) for k in range(3)]
        if c[1]:
            spec.energy_coeffs = c if c[2] else c[:2]
    return spec


def _cnf_read(path: Path) -> list[Spectrum]:
    try:
        if _SU is None:
            raise FormatError("SpecUtils not available")
        spectra = _read_with(path, P.Cnf)
    except FormatError:
        try:
            spectra = [_cnf_native(Path(path).read_bytes())]
        except (FormatError, struct.error) as exc:
            raise FormatError(f"{Path(path).name}: not a readable CNF file ({exc})") from None
    # Genie-2000 numbers the stored channels 1..N and its energy calibration uses that
    # numbering (verified with Genie's REPORT CSV.TPL: the first stored value is
    # "channel 1" at E = c0 + c1*1).  Our channel numbers are 0-based, so the
    # polynomial is re-expressed as E(i) = p(i + 1); counts are not shifted.
    for s in spectra:
        if s.energy_coeffs:
            s.energy_coeffs = [_f32(c) for c in _shift_poly(s.energy_coeffs, 1.0)]
    try:
        b = Path(path).read_bytes()
        # SpecUtils converts the CAM time through the local time zone and loses a few
        # seconds; decode the stored (local, naive) value directly instead.
        pos = _cnf_time_offset(b)
        if pos is not None:
            v = struct.unpack_from("<Q", b, pos)[0]
            if v:
                st = _CAM_EPOCH + timedelta(microseconds=v // 10)
                for s in spectra:
                    s.start_time = st
        # sample block: STITLE (+0x30, 64), SIDENT (+0x70, 16), SDESC1-4 (+878, 4 x 64)
        samp = _cam_blocks(b).get(_SAMP)
        if samp is not None and samp[0] + 1134 <= len(b):
            o = samp[0]
            title = _cam_text(b, o + 0x30, 64)
            ident = _cam_text(b, o + 0x70, 16)
            desc = [_cam_text(b, o + 878 + 64 * k, 64) for k in range(4)]
            desc_text = "\n".join(d for d in desc if d)
            for s in spectra:
                if title:
                    s.sample_id = title
                if ident:
                    s.extra["sample_ident"] = ident
                if s.description.startswith("Sample ID:"):
                    s.description = ""
                if desc_text:
                    s.description = desc_text
    except Exception:
        pass
    return spectra


# Genie-2000 compatible writer -------------------------------------------------
# SpecUtils' CNF output is rejected by Genie ("<57> Invalid channel count"), so CNF
# files are built from a template produced by Genie's own FILECNVT and patched:
#   file header  +0x0A u32 file size
#   directory    entry (0x30 bytes at 0x70 + 0x30*i, repeated in the first 0x30 bytes
#                of every block): +0x06 u32 block size, +0x0A u32 block offset,
#                data block (0x12005) +0x2A u32 channel count
#   0x12005      counts as u32 from +0x200; block size 0x200 + 4*N; it is the first
#                block, so every other block moves by the size change
#   0x12000      +185 u32 channels; +775 start (u64 100 ns since 1858-11-17),
#                +783 real / +791 live (i64, negative 100 ns ticks); +1067/1071/1075
#                ECOFFSET/ECSLOPE/ECQUAD (PDP-11 floats); +1385 calibration flag
#                (0 none, 1 linear, 3 quadratic); +1263 DETNAME (16)
#   0x12001      +0x30 STITLE (64), +0x70 SIDENT (16), +878 SDESC1..4 (4 x 64)
#   0x12002      +90 detector name (16)
# Genie only accepts power-of-two channel counts >= 256 (its own importers pad the
# same way), so other channel counts are zero-padded.
_T_START, _T_REAL, _T_LIVE = 775, 783, 791
_T_CAL, _T_CALFLAG, _T_DETNAME, _T_CHANS = 1067, 1385, 1263, 185


def _pdp11(value: float) -> bytes:
    if value == 0.0:
        return b"\x00\x00\x00\x00"
    ieee = struct.pack("<f", float(value) * 4.0)
    return ieee[2:4] + ieee[0:2]


def _ticks(dt: datetime) -> int:
    d = dt.replace(tzinfo=None) - _CAM_EPOCH
    return (d.days * 86400 + d.seconds) * 10_000_000 + d.microseconds * 10


def _put_text(buf: bytearray, off: int, n: int, text: str) -> None:
    raw = (text or "").encode("latin-1", "replace")[:n]
    buf[off:off + n] = raw + b" " * (n - len(raw))


def _cnf_write(spec: Spectrum, path: Path) -> None:
    from ._cnf_template import template_bytes
    n = len(spec.counts)
    if n == 0 or n > 65536:
        raise FormatError(f"CNF supports 1..65536 channels, spectrum has {n}")
    nch = 256
    while nch < n:
        nch *= 2
    counts = []
    for c in spec.counts:
        v = int(round(float(c)))
        if v < 0:
            raise FormatError(f"CNF cannot store a negative count ({c:g})")
        if v > 0xFFFFFFFF:
            raise FormatError("channel content exceeds 32-bit CNF range")
        counts.append(v)
    counts += [0] * (nch - n)

    t = template_bytes()
    blocks = _cam_blocks(t)
    d_off, d_size, _ = blocks[_DATA]
    new_size = 0x200 + 4 * nch
    delta = new_size - d_size
    out = (bytearray(t[:d_off]) + bytearray(t[d_off:d_off + 0x200])
           + struct.pack(f"<{nch}I", *counts) + bytearray(t[d_off + d_size:]))
    struct.pack_into("<I", out, 0x0A, len(out))
    for sid, (off, size, h) in blocks.items():
        new_off = off if sid == _DATA else off + delta
        for base in (h, new_off):  # directory entry and the block's own copy
            struct.pack_into("<I", out, base + 0x0A, new_off)
            if sid == _DATA:
                struct.pack_into("<I", out, base + 0x06, new_size)
                struct.pack_into("<I", out, base + 0x2A, nch)
    nb = _cam_blocks(out)
    acq, samp, det = nb[_ACQ][0], nb[_SAMP][0], nb[_DETB][0]
    struct.pack_into("<I", out, acq + _T_CHANS, nch)
    if spec.start_time is not None:
        struct.pack_into("<Q", out, acq + _T_START, _ticks(spec.start_time))
    struct.pack_into("<q", out, acq + _T_REAL, -int(round((spec.real_time or 0.0) * 1e7)))
    struct.pack_into("<q", out, acq + _T_LIVE, -int(round((spec.live_time or 0.0) * 1e7)))
    coeffs = list(spec.energy_coeffs)
    if coeffs:
        # Genie numbers the stored channels 1..N (see _cnf_read): Genie channel k is
        # our channel first_channel + k - 1.
        coeffs = _shift_poly(coeffs, spec.first_channel - 1)
    if len(coeffs) > 3 and any(coeffs[3:]):
        # CAM holds offset/slope/quadratic only: best quadratic over the stored channels
        import numpy as np
        x = np.arange(1, n + 1, dtype=float)
        y = np.polynomial.polynomial.polyval(x, coeffs)
        coeffs = [float(v) for v in np.polynomial.polynomial.polyfit(x, y, 2)]
    coeffs = (coeffs + [0.0, 0.0, 0.0])[:3]
    for k, c in enumerate(coeffs):
        out[acq + _T_CAL + 4 * k:acq + _T_CAL + 4 * k + 4] = _pdp11(c)
    out[acq + _T_CALFLAG] = 0 if not spec.energy_coeffs else (3 if coeffs[2] else 1)
    _put_text(out, acq + _T_DETNAME, 16, spec.detector)
    _put_text(out, det + 90, 16, spec.detector)
    _put_text(out, samp + 0x30, 64, spec.sample_id)
    lines = [ln.strip() for ln in (spec.description or "").splitlines() if ln.strip()]
    for k in range(4):
        _put_text(out, samp + 878 + 64 * k, 64, lines[k] if k < len(lines) else "")
    Path(path).write_bytes(bytes(out))


def _cnf_sniff(path: Path, head: bytes) -> bool:
    if len(head) < 0x74 or head[0] != 0 or head[1] != 4:
        return False
    return struct.unpack_from("<I", head, 0x70)[0] & 0xFFFFFF00 == 0x00012000


# ------------------------------------------------ lenient N42-2006 fallback
# SpecUtils rejects some N42-2006 dialects (e.g. BecqMoni's <RadiologicalInstrumentData>
# root with a "List" calibration).  This small namespace-agnostic parser handles the
# simple single-<Spectrum> layout; it is only used when SpecUtils gives up.
_ISO_DUR = re.compile(r"^P(?:(\d+(?:\.\d+)?)D)?(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?$")


def _n42_seconds(text: Optional[str]) -> Optional[float]:
    if text is None or not text.strip():
        return None
    t = text.strip()
    try:
        v = float(t)
    except ValueError:
        m = _ISO_DUR.match(t.upper())
        if not m or not any(m.groups()):
            return None
        d, h, mi, s = (float(g) if g else 0.0 for g in m.groups())
        v = d * 86400 + h * 3600 + mi * 60 + s
    return v if math.isfinite(v) and v >= 0 else None


def _n42_time(text: Optional[str]) -> Optional[datetime]:
    if not text or not text.strip():
        return None
    t = text.strip()
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=None)  # wall clock as written ('Z' -> UTC wall clock)


def _n42_lenient(path: Path) -> list[Spectrum]:
    import xml.etree.ElementTree as ET
    try:
        root = ET.parse(str(path)).getroot()
    except (ET.ParseError, OSError) as exc:
        raise FormatError(f"{Path(path).name}: invalid XML ({exc})") from None

    def local(el):
        return el.tag.rsplit("}", 1)[-1]

    def child(el, name):
        for c in el:
            if local(c) == name:
                return c
        return None

    def find_text(el, name):
        for c in el.iter():
            if local(c) == name and c.text is not None:
                return c.text
        return None

    out, fg = [], []
    for sp in root.iter():
        if local(sp) != "Spectrum":
            continue
        cd = child(sp, "ChannelData")
        if cd is None or not (cd.text or "").strip():
            continue
        try:
            counts = [float(x) for x in cd.text.split()]
        except ValueError:
            raise FormatError(f"{Path(path).name}: non-numeric channel data") from None
        if not counts or not all(math.isfinite(c) for c in counts):
            raise FormatError(f"{Path(path).name}: invalid channel data")
        s = Spectrum(counts=counts)
        s.live_time = _n42_seconds(find_text(sp, "LiveTime"))
        s.real_time = _n42_seconds(find_text(sp, "RealTime"))
        s.start_time = _n42_time(find_text(sp, "StartTime"))
        cal = child(sp, "EnergyCalibration")
        if cal is not None:
            try:
                coef = find_text(cal, "Coefficients") or find_text(cal, "CoefficientValues")
                if coef:
                    s.energy_coeffs = [float(x) for x in coef.split()]
                else:
                    ce = find_text(cal, "ChannelEnergies")
                    if ce:
                        vals = [float(x) for x in ce.split()][:len(counts)]
                        if len(vals) >= 2 and all(math.isfinite(v) for v in vals):
                            s.energy_coeffs = [_f32(c) for c in _fit_edges(vals)]
            except ValueError:
                s.energy_coeffs = []
            if s.energy_coeffs and not all(math.isfinite(c) for c in s.energy_coeffs):
                s.energy_coeffs = []
        for key, name in (("manufacturer", "Manufacturer"), ("instrument_model", "Model"),
                          ("instrument_id", "SerialNumber")):
            v = find_text(sp, name)
            if v and v.strip():
                s.extra[key] = v.strip()
        kind = (find_text(sp, "SpectrumType") or "").strip()
        if kind:
            s.extra["spectrum_type"] = kind
        s.sample_id = (sp.get("Name") or sp.get("ID") or "").strip()
        (fg if kind.lower() not in ("background", "calibration") else out).append(s)
    spectra = fg + out
    if not spectra:
        raise FormatError(f"{Path(path).name}: no <Spectrum> with channel data")
    return spectra


def _n42_reader(parser):
    def read(path: Path) -> list[Spectrum]:
        try:
            return _read_with(path, parser)
        except FormatError:
            return _n42_lenient(path)
    return read


# --------------------------------------------------------------- sniffers
def _txt_head(head: bytes) -> bytes:
    if head.startswith(b"\xef\xbb\xbf"):
        head = head[3:]
    return head.lstrip()


def _spc_sniff(filtyp):
    def sniff(path: Path, head: bytes) -> bool:
        if len(head) < 4:
            return False
        a, b = struct.unpack_from("<hh", head, 0)
        return a == 1 and b == filtyp
    return sniff


def _spe_sniff(path, head):
    h = _txt_head(head)
    return h.startswith(b"$") and any(k in h for k in (b"$SPEC_ID:", b"$DATA:", b"$MEAS_TIM:", b"$DATE_MEA:"))


def _contains(*markers, within=4096, start=False):
    def sniff(path, head):
        h = _txt_head(head)[:within]
        if start:
            return any(h.startswith(m) for m in markers)
        return any(m in h for m in markers)
    return sniff


def _pcf_sniff(path, head):
    return len(head) > 6 and head[2:5] in (b"DHS", b"DHG", b"DHC")


def _gr_sniff(gr135: bool):
    def sniff(path, head):
        if not head.startswith(b"ZZZZ") or len(head) < 8:
            return False
        is135 = head[4:7] == b"135"
        return is135 if gr135 else not is135
    return sniff


def _phd_sniff(path, head):
    h = _txt_head(head)
    return h.startswith(b"BEGIN") and (b"#Header" in h or b"DATA_TYPE" in h or b"IMS" in h[:40])


def _lis_sniff(path, head):
    return len(head) >= 4 and struct.unpack_from("<i", head, 0)[0] == -13 and b"LIST" in head[:64].upper()


# --------------------------------------------------------------- registry
_PURE = {_chn_read, _chn_write, _cnf_read, _cnf_write}      # need no SpecUtils


def _reg(code, key, name, exts, parser=None, kind=None, sniffer=None, notes="", reader=None,
         writer=None, aliases=()):
    if _SU is None and not (reader in _PURE and writer in _PURE | {None}):
        return
    register(FormatSpec(
        code=code, key=key, name=name, extensions=list(exts),
        reader=reader or (_reader(parser) if parser is not None else None),
        writer=writer or (_writer(kind) if kind is not None else None),
        sniffer=sniffer, notes=notes, aliases=list(aliases)))


_reg(1, "ortec_chn", "ORTEC ADCAM / MAESTRO", [".chn"], reader=_chn_read, writer=_chn_write,
     sniffer=_chn_sniff, aliases=["chn"], notes="Integer CHN with -102 calibration trailer.")
_reg(2, "ortec_spc", "ORTEC INFORM (integer SPC)", [".spc"], P.Spc, W.SpcBinaryInt,
     sniffer=_spc_sniff(1), aliases=["spc"], notes="Reads integer, float and ASCII SPC.")
_reg(7, "iaea_spe", "IAEA / Rossendorf ASCII SPE", [".spe"], P.SpeIaea, W.SpeIaea,
     sniffer=_spe_sniff, aliases=["spe", "rossendorf"])
_reg(10, "rms_phd", "RMS / IMS ASCII PHD", [".phd"], P.Phd, sniffer=_phd_sniff, aliases=["phd"])
_reg(16, "ci_cnf", "Canberra CAM (Genie-2000)", [".cnf"], reader=_cnf_read,
     writer=_cnf_write, sniffer=_cnf_sniff, aliases=["cnf", "cam"],
     notes="Genie-2000 compatible (template based); pads to a power-of-two channel count.")

_reg(20, "n42_2006", "ANSI N42.42-2006 XML", [".n42", ".xml"], reader=_n42_reader(P.N42_2006), kind=W.N42_2006,
     sniffer=_contains(b"<N42InstrumentData", b"<RadiologicalInstrumentData"), aliases=["n42-2006"])
_reg(21, "n42_2012", "ANSI N42.42-2012 XML", [".n42", ".xml"], reader=_n42_reader(P.N42_2012), kind=W.N42_2012,
     sniffer=_contains(b"RadInstrumentData"), aliases=["n42", "n42-2012"])
_reg(22, "gadras_pcf", "GADRAS PCF", [".pcf"], P.Pcf, W.Pcf, sniffer=_pcf_sniff, aliases=["pcf"],
     notes="Full-range-fraction calibration converted to/from polynomial.")
_reg(23, "specutils_csv", "SpecUtils CSV (Energy, Data)", [".csv"], reader=_csv_read, kind=W.Csv,
     sniffer=_contains(b"Energy, Data", b"Channel, Data", start=True), aliases=["csv"],
     notes="Energy column is the lower channel edge; times and metadata are lost.")
_reg(24, "specutils_txt", "SpecUtils TXT", [".txt"], P.TxtOrCsv, W.Txt,
     sniffer=_contains(b"Original File Name:", start=True))
_reg(25, "tka", "Canberra/Toolkit TKA", [".tka"], P.Tka, W.Tka, aliases=["tka"],
     notes="Live time, real time, then one count per line; no calibration.")
_reg(26, "html_d3", "HTML page (interactive D3 chart)", [".html", ".htm"], kind=W.HtmlD3,
     aliases=["html"])
_reg(27, "spc_ascii", "ORTEC/IAEA ASCII SPC", [".spc"], P.Spc, W.SpcAscii,
     sniffer=_contains(b"SpectrumName", start=True))
_reg(28, "spc_float", "ORTEC SPC (floating point)", [".spc"], P.Spc, W.SpcBinaryFloat,
     sniffer=_spc_sniff(5))
_reg(29, "exploranium_gr130", "Exploranium GR-130 binary", [".dat"], P.Exploranium,
     W.ExploraniumGr130v0, sniffer=_gr_sniff(False), notes="Rebinned to 256 channels on write.")
_reg(30, "exploranium_gr135", "Exploranium GR-135 v2 binary", [".dat"], P.Exploranium,
     W.ExploraniumGr135v2, sniffer=_gr_sniff(True))
_reg(31, "amptek_mca", "Amptek MCA (read only)", [".mca"], P.AmptekMca,
     sniffer=_contains(b"<<PMCA SPECTRUM>>", within=200), aliases=["amptek"])
_reg(32, "radiacode_xml", "RadiaCode / BecqMoni XML (read only)", [".xml", ".rcspg"], P.RadiaCode,
     sniffer=_contains(b"<ResultDataFile", b"<ResultDataList"), aliases=["radiacode", "becqmoni"])
_reg(33, "lsrm_spe", "LSRM / SpectraLine SPE (read only)", [".spe"], P.LsrmSpe,
     sniffer=_contains(b"SHIFR=", b"MEASBEGIN="), aliases=["lsrm"])
_reg(34, "multiact", "MultiAct (read only)", [".spm"], P.MultiAct,
     sniffer=_contains(b"MultiAct", start=True))
_reg(35, "labzy_lzs", "LabZY nanoMCA LZS (read only)", [".lzs"], P.Lzs, aliases=["lzs"])
_reg(36, "caen_gxml", "CAEN Hexagon GXML (read only)", [".gxml"], P.CaenHexagonGXml,
     aliases=["gxml"])
_reg(37, "specutils_json", "SpecUtils JSON (read only)", [".json"], P.Json)
_reg(38, "tracs_mps", "TRACS MPS (read only)", [".mps"], P.TracsMps)
_reg(39, "aram", "ARAM (read only)", [".xml"], P.Aram)
_reg(40, "microraider", "ICx MicroRaider XML (read only)", [".xml"], P.MicroRaider,
     sniffer=_contains(b"<IdResult"))
_reg(41, "spm_daily", "Spectroscopic portal daily file (read only)", [".txt"], P.SPMDailyFile,
     sniffer=_contains(b"S1,", start=True))
_reg(42, "scandata_xml", "ScanData XML (read only)", [".xml"], P.ScanDataXml,
     sniffer=_contains(b"<scanData"))
_reg(43, "ortec_listmode", "ORTEC list mode (read only, summed)", [".lis"], P.OrtecListMode,
     sniffer=_lis_sniff, aliases=["lis"])

"""Binary *.dat spectra with a 1670-byte text header (read only).

Code 80 ``lab_dat1670``.  The writing MCA program is not identified; no public description
of the layout was found.  The layout below was inferred from about 13,000 laboratory files
(HPGe, 2004-2009) and checked as stated; every inferred field is recorded in ``extra`` with
its raw text so a later correction is possible:

* u32 big-endian @0 = channels / 256 (32 -> 8192, 16 -> 4096).
* text @0x20..0x9A: "1", two dates "dd/mm/yyyy hh:mm:ss" (D1, D2), a number (always
  "1000.000000E-03"), a flag (1 or 2), "100", live time and real time in whole seconds.
  - flag 2: D2 is the acquisition start (start + real time agrees with the file time;
    272 of 272 sampled files within the clock/time-zone scatter); D1 is a fixed earlier date
    shared by many files (probably the calibration date; not used).
  - flag 1 (Sep-Dec 2009, 1056 files): D1 = D2 lies about 1 minute before the file time
    while the real time is about 1000 s, so D2 is the *end* of the acquisition and the start
    is D2 - real time (``extra["start_time_inferred"]``).
* text @0x9A..0x200 (Arabic, Windows-1256): sample description, 40-character fields.
* text @0x200..0x24C: a label (e.g. an office name); stored, not interpreted.
* text @0x24C..0x320: 12 numbers "dddd.dddddE+xx"; the first four are the energy calibration
  E = c0 + c1 k + c2 k^2 + c3 k^3 with 0-based channel k (on 300 sampled spectra the Pb-214
  351.93 keV and Cs-137 661.66 keV peaks fall within 0.05 keV; 1-based channels would give
  +0.3 keV).  The meaning of the other eight is unknown (raw text kept).
* int32 little-endian counts from byte 0x686 (1670).
"""
from __future__ import annotations

import re
import struct
from datetime import datetime, timedelta
from pathlib import Path

from ..model import Spectrum
from .base import FormatError, FormatSpec, register

DATA_OFFSET = 0x686
_DT = r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})"
_HEAD_RE = re.compile(_DT + r"\s+" + _DT + r"\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)")
_NUM_RE = re.compile(r"-?\d+\.\d+E[+-]\d+")


def _text(b: bytes, enc: str = "latin-1") -> str:
    return b.replace(b"\0", b" ").decode(enc, "replace")


def _channels(head: bytes) -> int:
    return struct.unpack_from(">I", head, 0)[0] * 256


def _header_ok(head: bytes) -> bool:
    if len(head) < 0x320 or head[:3] != b"\0\0\0" or head[3] not in (1, 2, 4, 8, 16, 32, 64):
        return False
    return _HEAD_RE.search(_text(head[0x20:0x9A])) is not None


def read_lab_dat(path: Path) -> list[Spectrum]:
    data = Path(path).read_bytes()
    if not _header_ok(data):
        raise FormatError(f"{Path(path).name}: not a 1670-byte-header binary .dat spectrum")
    n = _channels(data)
    if len(data) < DATA_OFFSET + 4 * n:
        raise FormatError(f"{Path(path).name}: truncated or empty ({len(data)} bytes for {n} channels)")
    counts = list(struct.unpack_from(f"<{n}i", data, DATA_OFFSET))
    m = _HEAD_RE.search(_text(data[0x20:0x9A]))
    d1, d2, unit, flag, preset, lt, rt = m.groups()
    t1 = datetime.strptime(d1, "%d/%m/%Y %H:%M:%S")
    t2 = datetime.strptime(d2, "%d/%m/%Y %H:%M:%S")
    live, real = float(lt), float(rt)
    nums = _NUM_RE.findall(_text(data[0x24C:0x320]))
    ecoef = [float(x) for x in nums[:4]]
    while ecoef and ecoef[-1] == 0.0:
        ecoef.pop()
    if len(ecoef) < 2 or ecoef[1] <= 0:
        ecoef = []
    extra = {"header_date_1": t1.isoformat(sep=" "), "header_date_2": t2.isoformat(sep=" "),
             "header_flag": flag, "header_unit_raw": unit, "header_preset_raw": preset,
             "header_numbers_raw": " ".join(nums), "layout": "inferred from laboratory files"}
    if flag == "1":
        start = t2 - timedelta(seconds=real)
        extra["start_time_inferred"] = "header date read as the end of acquisition; start = date - real time"
    elif flag == "2":
        start = t2
    else:
        start = None
        extra["start_time_inferred"] = f"unknown date convention (flag {flag}): no start time"
    label = _text(data[0x200:0x24C], "cp1256").strip()
    if label:
        extra["header_label"] = label
    desc_raw = data[0x9A:0x200]
    fields = [_text(desc_raw[i:i + 40], "cp1256").strip() for i in range(0, len(desc_raw), 40)]
    fields = [f for f in fields if f]
    trailing = len(data) - DATA_OFFSET - 4 * n
    if trailing:
        extra["trailing_bytes"] = trailing
    s = Spectrum(counts=counts, energy_coeffs=ecoef, live_time=live or None, real_time=real or None,
                 start_time=start, sample_id=fields[0] if fields else "",
                 description=" | ".join(fields[1:]) if len(fields) > 1 else "")
    s.extra.update(extra)
    return [s]


def sniff_lab_dat(path: Path, head: bytes) -> bool:
    if not _header_ok(head):
        return False
    try:
        return path.stat().st_size >= DATA_OFFSET + 4 * _channels(head)
    except OSError:
        return False


register(FormatSpec(80, "lab_dat1670", "Binary .dat, 1670-byte text header (read only)", [".dat"],
                    read_lab_dat, None, sniff_lab_dat,
                    "Layout inferred from laboratory HPGe files (2004-2009); writer program not "
                    "identified.  See the module docstring for what was verified.",
                    aliases=["dat1670"]))

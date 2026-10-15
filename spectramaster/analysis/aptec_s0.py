"""Read the analysis part of an Aptec Version 6.3 ``.S0`` spectrum file: the ROI records (with
the identification and quantification results Aptec stored in them) and the analysis setup of
the job header (peak search, identification, background subtract, quantify).

Layout from the published "Spectrum File Format Version 6.3" (Aptec help file): main header
1024 B, efficiency records 130 B, energy and resolution points 8 B each, ROI records 256 B,
channel data 4 B each, then the job header (``iJobHeaderSize`` bytes, 2514 in Version 6.3).
Pure functions, no GUI.  Used to verify the Aptec-style analysis against what Aptec stored.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

__all__ = ["S0File", "S0Roi", "AnalysisSetup", "read_s0", "ROI_FLAGS"]

ROI_FLAGS = {"bkg_fixed": 0x0001, "summed": 0x0002, "multifit": 0x0004, "identified": 0x0008,
             "quantified": 0x0010, "bkgnd_sub": 0x0020}


def _dt(d: bytes, o: int) -> Optional[datetime]:
    t, sec, mi, h, day, mon = d[o:o + 6]
    y = struct.unpack_from("<h", d, o + 6)[0]
    if not y or not mon or not day:
        return None
    try:
        return datetime(y, mon, day, h, mi, sec, min(t, 99) * 10000)
    except ValueError:
        return None


def _s(d: bytes, o: int, n: int) -> str:
    return d[o:o + n].split(b"\0", 1)[0].decode("latin-1").strip()


@dataclass
class S0Roi:
    bl: int
    rl: int
    rh: int
    bh: int
    bkg_degree: int
    bkg_coeffs: list[float]
    isotope: str
    iso_bkg_grate: float
    iso_bkg_brate: float
    iso_bits: int
    iso_energy: float
    iso_yield: float
    iso_half_life_s: float
    iso_half_life_err: float
    iso_convert_factor: float
    iso_activity: float
    iso_activity_err: float
    centroid: float
    gross: float
    background: float
    net: float
    net_err_pct: float
    fwhm_lo: float
    fwhm_hi: float
    fwtm_lo: float
    fwtm_hi: float
    roi_bits: int
    activity_units: str
    activity: float
    activity_err_pct: float
    critical_level: float
    mda: float
    mda_err_pct: float
    function_type: int

    @property
    def force_mda(self) -> bool:
        return bool(self.iso_bits & 0x1)

    @property
    def is_mda(self) -> bool:
        return bool(self.roi_bits & 0x1)

    @property
    def bkgnd_subtracted(self) -> bool:
        return bool(self.roi_bits & 0x2)


@dataclass
class AnalysisSetup:
    """Analysis fields of the job header (defaults when the file has no job header)."""
    peak_statistics: float = 0.0          # Max Peak Error (% at error sigma)
    peak_start: int = 0
    peak_stop: int = 0
    peak_partial: bool = False
    peak_lo_bkg_width: int = 0
    peak_hi_bkg_width: int = 0
    peak_bkg_width: int = 0
    peak_calc_bkg_width: bool = False
    peak_bkg_degree: int = 1
    peak_bkg_fit: int = 0
    peak_bkg_lny: bool = False
    peak_bkg_lnx: bool = False
    peak_cen_weight: int = 0              # 0 = net, 1 = squared
    peak_cen_range: int = 0               # 0 ghm, 1 fwhm, 2 fwtm, 3 all
    peak_mda_width_factor: float = 0.0
    peak_fit_fwhm: bool = False
    peak_no_bkg: bool = False
    smooth: dict = field(default_factory=dict)
    ident_fraction_limit: float = 0.0
    ident_half_life_limit: float = 0.0
    ident_match_limit: float = 0.0
    ident_fwhm_fract: float = 0.0
    ident_allow_mda: bool = False
    ident_half_life_reject: bool = False
    ident_limit_fwhm: int = 0
    ident_match_type: int = 0
    bkgnd_sub: bool = False
    quant_use: dict = field(default_factory=dict)   # E, M, T, Q, W, X, Y
    quant_allow_negative: bool = False
    bkgnd_file: str = ""
    library_file: str = ""


@dataclass
class S0File:
    counts: np.ndarray
    live_time: float
    true_time: float
    energy_coeffs: list[float]
    energy_units: str
    res_coeffs: list[float]
    res_units: str
    err_sigma: float
    mda_sigma: float
    analyze_status: int
    roi_flag: int
    activity_units: str
    quantity: float
    quantity_units: str
    rois: list[S0Roi]
    setup: Optional[AnalysisSetup]
    eff_type: str = ""
    eff_coeffs: list[float] = field(default_factory=list)
    start_time: Optional[datetime] = None
    activity_time: Optional[datetime] = None
    sample_start: Optional[datetime] = None
    sample_stop: Optional[datetime] = None
    w_const: float = 0.0
    x_const: float = 0.0
    y_const: float = 0.0
    total_quantity: float = 0.0

    def flag(self, name: str) -> bool:
        return bool(self.roi_flag & ROI_FLAGS[name])


def _roi(d: bytes, o: int) -> S0Roi:
    bl, rl, rh, bh, deg = struct.unpack_from("<5h", d, o)
    coeffs = list(struct.unpack_from("<6d", d, o + 10))
    g, b = struct.unpack_from("<2f", d, o + 66)
    iso_bits = struct.unpack_from("<H", d, o + 74)[0]
    e, y = struct.unpack_from("<2f", d, o + 76)
    hl = struct.unpack_from("<d", d, o + 84)[0]
    hle, cf, act, acte, cen = struct.unpack_from("<5f", d, o + 92)
    gross, bkg, net = struct.unpack_from("<3d", d, o + 112)
    nerr, hlo, hhi, tlo, thi = struct.unpack_from("<5f", d, o + 136)
    bits = struct.unpack_from("<H", d, o + 156)[0]
    a, ae, cl, mda, mdae = struct.unpack_from("<5f", d, o + 178)
    ft = struct.unpack_from("<H", d, o + 198)[0]
    return S0Roi(bl, rl, rh, bh, deg, coeffs, _s(d, o + 58, 8), g, b, iso_bits, e, y, hl, hle, cf, act, acte,
                 cen, gross, bkg, net, nerr, hlo, hhi, tlo, thi, bits, _s(d, o + 162, 16), a, ae, cl, mda, mdae, ft)


def _setup(d: bytes, o: int) -> AnalysisSetup:
    u8 = lambda k: d[o + k]                                  # noqa: E731
    i16 = lambda k: struct.unpack_from("<h", d, o + k)[0]    # noqa: E731
    f32 = lambda k: struct.unpack_from("<f", d, o + k)[0]    # noqa: E731
    f64 = lambda k: struct.unpack_from("<d", d, o + k)[0]    # noqa: E731
    return AnalysisSetup(
        peak_statistics=f64(764), peak_start=i16(772), peak_stop=i16(774), peak_lo_bkg_width=i16(776),
        peak_hi_bkg_width=i16(778), peak_bkg_width=i16(780), peak_mda_width_factor=f32(782),
        peak_calc_bkg_width=bool(u8(786)), peak_partial=bool(u8(787)), peak_bkg_degree=u8(788),
        peak_bkg_fit=u8(789), peak_bkg_lny=bool(u8(790)), peak_bkg_lnx=bool(u8(791)), peak_cen_weight=u8(792),
        peak_cen_range=u8(793), peak_fit_fwhm=bool(u8(2440)), peak_no_bkg=bool(u8(2441)),
        smooth={k: bool(u8(2504 + i)) for i, k in enumerate(("classic", "3", "5", "7", "9", "11", "keep"))},
        ident_fraction_limit=f32(694), ident_half_life_limit=f64(698), ident_match_limit=f32(706),
        ident_fwhm_fract=f32(710), ident_allow_mda=bool(u8(714)), ident_half_life_reject=bool(u8(715)),
        ident_limit_fwhm=u8(716), ident_match_type=u8(717), bkgnd_sub=bool(u8(718)),
        quant_use={k: bool(u8(719 + i)) for i, k in enumerate("EMTQWXY")},
        quant_allow_negative=bool(u8(2436)), bkgnd_file=_s(d, o + 1284, 128), library_file=_s(d, o + 1796, 128))


def read_s0(data) -> S0File:
    """Parse an Aptec Version 6.x ``.S0`` file (path or bytes)."""
    d = Path(data).read_bytes() if not isinstance(data, (bytes, bytearray)) else bytes(data)
    if len(d) < 1024 or not d[:7].startswith(b"VERSION"):
        raise ValueError("not an Aptec Version 6.x spectrum file")
    i16 = lambda o: struct.unpack_from("<h", d, o)[0]          # noqa: E731
    f32 = lambda o: struct.unpack_from("<f", d, o)[0]          # noqa: E731
    n_eff, n_en, n_res, n_roi = (max(i16(k), 0) for k in (330, 618, 694, 782))
    n_ch, job = max(i16(790), 0), max(i16(784), 0)
    roi_o = 1024 + 130 * n_eff + 8 * n_en + 8 * n_res
    data_o = roi_o + 256 * n_roi
    if data_o + 4 * n_ch > len(d):
        raise ValueError("truncated Aptec spectrum file")
    counts = np.frombuffer(d, dtype="<u4", count=n_ch, offset=data_o).astype(float)
    rois = [_roi(d, roi_o + 256 * k) for k in range(n_roi)]
    job_o = data_o + 4 * n_ch
    setup = _setup(d, job_o) if job >= 2514 and job_o + 2514 <= len(d) else None
    deg = lambda o: max(0, min(5, i16(o)))                       # noqa: E731
    en = list(struct.unpack_from("<6d", d, 646))[:deg(644) + 1]
    res = list(struct.unpack_from("<6d", d, 722))[:deg(720) + 1]
    return S0File(counts=counts, live_time=struct.unpack_from("<I", d, 818)[0] / 1000.0,
                  true_time=struct.unpack_from("<I", d, 810)[0] / 1000.0, energy_coeffs=en,
                  energy_units=_s(d, 628, 16), res_coeffs=res, res_units=_s(d, 704, 16), err_sigma=f32(774),
                  mda_sigma=f32(778), analyze_status=struct.unpack_from("<H", d, 770)[0],
                  roi_flag=struct.unpack_from("<H", d, 772)[0], activity_units=_s(d, 298, 16),
                  quantity=f32(202), quantity_units=_s(d, 186, 16), rois=rois, setup=setup,
                  eff_type=chr(struct.unpack_from("<H", d, 356)[0] & 0xFF) if d[356] else "",
                  eff_coeffs=list(struct.unpack_from("<6d", d, 358)), start_time=_dt(d, 794),
                  activity_time=_dt(d, 314), sample_start=_dt(d, 170), sample_stop=_dt(d, 178), w_const=f32(226),
                  x_const=f32(250), y_const=f32(274), total_quantity=f32(322))

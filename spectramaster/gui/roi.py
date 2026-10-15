"""Region-of-interest arithmetic (MAESTRO/GammaVision style).

The background under an ROI is a straight line joining the average of the
``n_avg`` channels at each end of the ROI (those channels belong to the ROI),
so for a linear continuum the background estimate is exact:

    B   = n * (L + R) / 2          L, R = end averages, n = ROI width
    N   = G - B
    s_N = sqrt(G + B * n / (2 * n_avg))
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

N_AVG = 3


@dataclass
class RoiStats:
    left: int                     # first index into counts (inclusive)
    right: int                    # last index (inclusive)
    first_channel: int
    gross: float
    background: float
    net: float
    net_unc: float
    bg_left: float                # average level at the left end (counts/channel)
    bg_right: float
    centroid: Optional[float]     # channel number (first_channel based, fractional)
    centroid_energy: Optional[float]
    fwhm: Optional[float]         # channels
    fwhm_kev: Optional[float]
    live_time: Optional[float]
    count_rate: Optional[float]   # net cps
    count_rate_unc: Optional[float]
    n_avg: int = N_AVG

    @property
    def width(self) -> int:
        return self.right - self.left + 1

    @property
    def start_channel(self) -> int:
        return self.first_channel + self.left

    @property
    def end_channel(self) -> int:
        return self.first_channel + self.right

    def background_at(self, idx: float) -> float:
        """Background level (counts/channel) at a fractional index."""
        xl = self.left + (self.n_avg - 1) / 2.0
        xr = self.right - (self.n_avg - 1) / 2.0
        if xr <= xl:
            return (self.bg_left + self.bg_right) / 2
        return self.bg_left + (self.bg_right - self.bg_left) * (idx - xl) / (xr - xl)


def compute_roi(counts: Sequence[float], left: int, right: int, first_channel: int = 0,
                energy_of: Optional[Callable[[float], Optional[float]]] = None,
                live_time: Optional[float] = None, n_avg: int = N_AVG) -> RoiStats:
    n_total = len(counts)
    left, right = sorted((int(left), int(right)))
    left = max(0, left)
    right = min(n_total - 1, right)
    if right < left:
        raise ValueError("empty ROI")
    seg = [float(c) for c in counts[left:right + 1]]
    n = len(seg)
    m = max(1, min(n_avg, n // 2 if n >= 2 else 1))
    gross = sum(seg)
    bl = sum(seg[:m]) / m
    br = sum(seg[-m:]) / m
    background = n * (bl + br) / 2.0
    net = gross - background
    net_unc = math.sqrt(max(0.0, gross + background * n / (2.0 * m)))

    # linear background per channel; end-average centres
    xl = (m - 1) / 2.0
    xr = (n - 1) - (m - 1) / 2.0
    def bg(i: int) -> float:
        if xr <= xl:
            return (bl + br) / 2
        return bl + (br - bl) * (i - xl) / (xr - xl)
    netc = [seg[i] - bg(i) for i in range(n)]

    centroid = None
    pos_sum = sum(v for v in netc if v > 0)
    if pos_sum > 0:
        centroid = first_channel + left + sum(i * v for i, v in enumerate(netc) if v > 0) / pos_sum

    fwhm = None
    if n >= 3:
        j = max(range(n), key=lambda i: netc[i])
        peak = netc[j]
        if peak > 0:
            half = peak / 2.0
            lo = None
            k = j
            while k > 0 and netc[k - 1] >= half:
                k -= 1
            if k > 0:
                a, b = netc[k - 1], netc[k]
                lo = (k - 1) + (half - a) / (b - a) if b != a else k - 0.5
            k = j
            hi = None
            while k < n - 1 and netc[k + 1] >= half:
                k += 1
            if k < n - 1:
                a, b = netc[k], netc[k + 1]
                hi = k + (a - half) / (a - b) if a != b else k + 0.5
            if lo is not None and hi is not None and hi > lo:
                fwhm = hi - lo

    centroid_energy = fwhm_kev = None
    if energy_of is not None and centroid is not None:
        centroid_energy = energy_of(centroid)
        if fwhm is not None and centroid_energy is not None:
            ea = energy_of(centroid - fwhm / 2)
            eb = energy_of(centroid + fwhm / 2)
            if ea is not None and eb is not None:
                fwhm_kev = abs(eb - ea)

    rate = rate_unc = None
    if live_time and live_time > 0:
        rate = net / live_time
        rate_unc = net_unc / live_time
    return RoiStats(left=left, right=right, first_channel=first_channel, gross=gross,
                    background=background, net=net, net_unc=net_unc, bg_left=bl, bg_right=br,
                    centroid=centroid, centroid_energy=centroid_energy, fwhm=fwhm, fwhm_kev=fwhm_kev,
                    live_time=live_time, count_rate=rate, count_rate_unc=rate_unc, n_avg=m)


# --------------------------------------------------------------------------- Aptec rules
@dataclass
class AptecRoiStats(RoiStats):
    """RoiStats computed with Aptec's rules (spectramaster.analysis.aptec_roi).

    The background is the polynomial ``coeffs`` (index space) fitted to end points outside the
    ROI; ``net_unc`` is Aptec's statistical error sqrt(G + B) at 1 sigma."""
    bl: int = 0                   # first / last end-point index
    bh: int = 0
    coeffs: tuple = ()
    err_pct: Optional[float] = None   # 1 sigma
    fwtm: Optional[float] = None
    fwtm_kev: Optional[float] = None
    mda_cps: Optional[float] = None
    flags: str = ""
    grouped: bool = False

    def background_at(self, idx: float) -> float:
        v = 0.0
        for k, c in enumerate(self.coeffs):
            v += c * idx ** k
        return v


def compute_rois_aptec(counts: Sequence[float], bounds: Sequence[tuple[int, int]], first_channel: int = 0,
                       energy_of: Optional[Callable[[float], Optional[float]]] = None,
                       live_time: Optional[float] = None, props=None) -> list[AptecRoiStats]:
    """Aptec ROI results for every ``(left, right)`` index pair, in the order given."""
    from ..analysis.aptec_roi import analyze_rois
    res = analyze_rois(counts, bounds, props, live_time)
    out = []
    for r in res:
        cen = None if r.centroid is None else first_channel + r.centroid
        cen_e = fwhm_kev = fwtm_kev = None
        if energy_of is not None and cen is not None:
            cen_e = energy_of(cen)

            def width_kev(w):
                if w is None or cen_e is None:
                    return None
                ea, eb = energy_of(cen - w / 2), energy_of(cen + w / 2)
                return abs(eb - ea) if ea is not None and eb is not None else None
            fwhm_kev, fwtm_kev = width_kev(r.fwhm), width_kev(r.fwtm)
        rate = rate_unc = None
        if live_time and live_time > 0:
            rate = r.net / live_time
            rate_unc = r.net_unc / live_time
        out.append(AptecRoiStats(
            left=r.rl, right=r.rh, first_channel=first_channel, gross=r.gross, background=r.background,
            net=r.net, net_unc=r.net_unc, bg_left=float(r.background_at(r.rl)),
            bg_right=float(r.background_at(r.rh)), centroid=cen, centroid_energy=cen_e, fwhm=r.fwhm,
            fwhm_kev=fwhm_kev, live_time=live_time, count_rate=rate, count_rate_unc=rate_unc, n_avg=0,
            bl=r.bl, bh=r.bh, coeffs=tuple(r.coeffs), err_pct=r.err_pct, fwtm=r.fwtm, fwtm_kev=fwtm_kev,
            mda_cps=r.mda_cps, flags=r.flags, grouped=r.grouped))
    return out


def fitted_stats(st: AptecRoiStats, result, k: int, energy_of=None, live_time: Optional[float] = None) -> AptecRoiStats:
    """ROI statistics of component ``k`` of a MultiFit ``result``: the fitted Gaussian replaces
    the summed net counts (area, its uncertainty, centroid and FWHM); flag ``m`` for a component
    of a multiplet, ``s`` for a fitted singlet (Aptec's letters)."""
    from dataclasses import replace
    c = result.components[k]
    first = st.first_channel
    cen = first + c.centroid
    cen_e = fw_kev = None
    if energy_of is not None:
        cen_e = energy_of(cen)
        ea, eb = energy_of(cen - c.fwhm / 2), energy_of(cen + c.fwhm / 2)
        if cen_e is not None and ea is not None and eb is not None:
            fw_kev = abs(eb - ea)
    rate = rate_unc = None
    if live_time and live_time > 0:
        rate, rate_unc = c.area / live_time, c.area_unc / live_time
    flags = ("m" if result.multiplet else "s")
    if rate is not None and st.mda_cps is not None and rate < st.mda_cps:
        flags += "?"
    return replace(st, net=c.area, net_unc=c.area_unc, centroid=cen, centroid_energy=cen_e, fwhm=c.fwhm,
                   fwhm_kev=fw_kev, count_rate=rate, count_rate_unc=rate_unc,
                   err_pct=100.0 * c.area_unc / c.area if c.area else None, flags=flags)

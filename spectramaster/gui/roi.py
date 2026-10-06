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

"""Detector acceptance test and chi-square counting test: evaluation harness of
docs/baseline/detector_acceptance_protocol.md (spectra built here, fixed seeds).

    python -m spectramaster.validation.detector_acceptance

Writes ``detector_acceptance.json`` and ``detector_acceptance.md`` to docs/baseline/after_DA1.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from scipy.special import ndtr

from ..analysis import detector_test as dt
from ..model import Spectrum

OUT = Path(__file__).resolve().parents[2] / "docs" / "baseline" / "after_DA1"
FWTM_RATIO = math.sqrt(math.log(10.0) / math.log(2.0))      # Gaussian FWTM / FWHM
AREA = 1.0e5
LIVE = 3600.0
START = datetime(2026, 1, 1, 12, 0, 0)
ACTIVITY = 37000.0


def build(gain: float, fwhm_kev: float, area: float, cont=(120.0, -0.01), rng=None, n_ch=None) -> Spectrum:
    """A Gaussian peak at 1332.5 keV integrated over each channel (channel i at gain * i keV) on a
    linear continuum a + b i (b per channel); Poisson noise when `rng` is given."""
    n = n_ch or int(2100.0 / gain)
    i = np.arange(n, dtype=float)
    c = dt.CO60_1332 / gain
    s = fwhm_kev / gain / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    y = area * (ndtr((i + 0.5 - c) / s) - ndtr((i - 0.5 - c) / s)) + np.maximum(cont[0] + cont[1] * i, 0.0)
    if rng is not None:
        y = rng.poisson(y).astype(float)
    return Spectrum(counts=list(y), energy_coeffs=[0.0, gain], live_time=LIVE, real_time=LIVE, start_time=START)


def widths() -> dict:
    """DA.C1 (noiseless) and DA.C2 (50 Poisson realizations, continuum 100 per channel)."""
    rows = []
    for gain in (0.5, 0.25):
        for fw in (1.8, 2.2):
            w = dt.peak_width(build(gain, fw, AREA))
            rng = np.random.default_rng(int(1000 * gain + 10 * fw))
            ws = [dt.peak_width(build(gain, fw, AREA, cont=(100.0, 0.0), rng=rng)) for _ in range(50)]
            fh = [x.fwhm_kev for x in ws if x.fwhm_kev]
            ft = [x.fwtm_kev for x in ws if x.fwtm_kev]
            rows.append({"gain": gain, "fwhm_true": fw, "fwtm_true": FWTM_RATIO * fw,
                         "noiseless_fwhm": w.fwhm_kev, "noiseless_fwtm": w.fwtm_kev,
                         "noiseless_fwhm_dev": w.fwhm_kev / fw - 1.0,
                         "noiseless_fwtm_dev": w.fwtm_kev / (FWTM_RATIO * fw) - 1.0,
                         "poisson_n": len(fh), "poisson_fwhm_dev": float(np.mean(fh)) / fw - 1.0,
                         "poisson_fwtm_dev": float(np.mean(ft)) / (FWTM_RATIO * fw) - 1.0})
    return {"rows": rows}


def _area_for(r_pct: float, years: float) -> tuple[float, datetime]:
    hl, inten = dt._co60()
    ref = START - timedelta(days=365.25 * years)
    a = ACTIVITY * math.exp(-math.log(2.0) * (START - ref).total_seconds() / hl)
    return r_pct / 100.0 * dt.NAI_REF_EFFICIENCY * a * inten * LIVE, ref


def efficiency() -> dict:
    """DA.C3 (noiseless, R 20/40/100 %, reference 5 years before and at the start) and DA.C4."""
    rows = []
    for r in (20.0, 40.0, 100.0):
        for years in (5.0, 0.0):
            area, ref = _area_for(r, years)
            re = dt.relative_efficiency(build(0.5, 2.0, area), ACTIVITY, 0.0, ref)
            rows.append({"R": r, "years": years, "measured": re.percent, "dev": re.percent / r - 1.0,
                         "decay_factor": re.decay_factor})
    area, ref = _area_for(40.0, 5.0)
    rng = np.random.default_rng(4040)
    z = []
    for _ in range(200):
        re = dt.relative_efficiency(build(0.5, 2.0, area, rng=rng), ACTIVITY, 0.0, ref)
        z.append((re.percent - 40.0) / re.u_counting)
    return {"rows": rows, "z_n": len(z), "z_mean": float(np.mean(z)),
            "cov2": float(np.mean([abs(v) <= 2.0 for v in z]))}


def p_to_c() -> dict:
    """DA.C5: hand-made spectrum."""
    y = np.full(4200, 50.0)
    sp = Spectrum(counts=list(y), energy_coeffs=[0.0, 0.5], live_time=LIVE, real_time=LIVE)
    e = np.asarray(sp.energies())
    sel = (e >= 1040.0) & (e <= 1096.0)
    y[sel] = 40.0 + (np.arange(sel.sum()) % 5)          # region mean 42
    roi = (2650, 2680)
    y[2665], y[2666] = 9000.0, 8000.0
    sp.counts = list(y)
    hand = 9000.0 / float(y[sel].mean())
    got = dt.peak_to_compton(sp, roi)
    return {"hand": hand, "engine": got, "equal": got == hand}


def chi_square() -> dict:
    """DA.C6 and DA.C7."""
    pts = {n: [dt.chi_square_test(np.full(n, 100.0) + np.arange(n)).low,
               dt.chi_square_test(np.full(n, 100.0) + np.arange(n)).high] for n in (10, 20)}
    rng = np.random.default_rng(1599)
    ok_p = [dt.chi_square_test(rng.poisson(10000.0, 10)).passed for _ in range(2000)]
    ok_x = [dt.chi_square_test(rng.poisson(rng.normal(10000.0, 300.0, 10))).passed for _ in range(2000)]
    return {"points": {str(k): [round(v, 3) for v in p] for k, p in pts.items()},
            "poisson_accepted": float(np.mean(ok_p)), "scatter_rejected": 1.0 - float(np.mean(ok_x))}


def reported() -> dict:
    """The synthetic module's HPGe Co-60 spectrum (low-energy tail): reported only."""
    from . import scenarios
    from .synthetic import HPGE, TruePeak, make_spectrum
    syn = make_spectrum(HPGE, [TruePeak(1173.228, 2.0e5), TruePeak(1332.492, 1.8e5)],
                        scenarios.base_continuum(HPGE), 325)
    r = dt.acceptance_test(syn.spectrum)
    w = r.width_1332
    return {"fwhm_kev": w.fwhm_kev, "fwtm_kev": w.fwtm_kev, "ratio": w.ratio, "p_to_c": r.peak_to_compton,
            "model_fwhm_kev": float(HPGE.fwhm_kev(1332.492))}


def criteria(m: dict) -> list[dict]:
    w = m["widths"]["rows"]
    c1 = all(abs(r["noiseless_fwhm_dev"]) <= 0.025 and abs(r["noiseless_fwtm_dev"]) <= 0.025 for r in w)
    c2 = all(abs(r["poisson_fwhm_dev"]) <= 0.025 and abs(r["poisson_fwtm_dev"]) <= 0.025 for r in w)
    e = m["efficiency"]
    c3 = all(abs(r["dev"]) <= 0.01 for r in e["rows"])
    c4 = 0.90 <= e["cov2"] <= 0.99
    c5 = m["p_to_c"]["equal"]
    p = m["chi_square"]["points"]
    c6 = p["10"] == [3.325, 16.919] and p["20"] == [10.117, 30.144]
    cs = m["chi_square"]
    c7 = 0.88 <= cs["poisson_accepted"] <= 0.92 and cs["scatter_rejected"] >= 0.99
    fmt = lambda k: max(abs(r[k]) for r in w)    # noqa: E731
    return [
        {"id": "DA.C1", "pass": c1, "value": f"largest |dev| FWHM {fmt('noiseless_fwhm_dev'):.4f}, FWTM {fmt('noiseless_fwtm_dev'):.4f}"},
        {"id": "DA.C2", "pass": c2, "value": f"largest |mean dev| FWHM {fmt('poisson_fwhm_dev'):.4f}, FWTM {fmt('poisson_fwtm_dev'):.4f}"},
        {"id": "DA.C3", "pass": c3, "value": f"largest |dev| {max(abs(r['dev']) for r in e['rows']):.5f}"},
        {"id": "DA.C4", "pass": c4, "value": f"mean z {e['z_mean']:.3f}, |z| <= 2 {e['cov2']:.3f} (n {e['z_n']})"},
        {"id": "DA.C5", "pass": c5, "value": f"hand {m['p_to_c']['hand']:.6g}, engine {m['p_to_c']['engine']}"},
        {"id": "DA.C6", "pass": c6, "value": f"10: {p['10']}, 20: {p['20']}"},
        {"id": "DA.C7", "pass": c7, "value": f"Poisson accepted {cs['poisson_accepted']:.4f}, extra scatter rejected {cs['scatter_rejected']:.4f}"},
    ]


def run() -> dict:
    return {"widths": widths(), "efficiency": efficiency(), "p_to_c": p_to_c(), "chi_square": chi_square(),
            "reported": reported()}


def main(argv=None) -> int:
    m = run()
    cs = criteria(m)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "detector_acceptance.json").write_text(json.dumps({"measured": m, "criteria": cs}, indent=1),
                                                  encoding="utf-8", newline="\n")
    lines = ["# Detector acceptance test and chi-square counting test", "",
             "Protocol: `docs/baseline/detector_acceptance_protocol.md`.", "",
             "| ID | result | value |", "|---|---|---|"]
    lines += [f"| {c['id']} | {'PASS' if c['pass'] else 'FAIL'} | {c['value']} |" for c in cs]
    lines += ["", "## Measured", "", "```", json.dumps(m, indent=1), "```", ""]
    (OUT / "detector_acceptance.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(json.dumps(cs))
    return 1 if any(not c["pass"] for c in cs) else 0


if __name__ == "__main__":
    sys.exit(main())

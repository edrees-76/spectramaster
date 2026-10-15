# Aptec-style MultiFit: validation protocol (pre-registered)

Written 2026-10-15, before the method was run on the validation spectra.  Limits are not to be
changed after results are known; a result outside a limit is reported as a failure.

## Why synthetic spectra

No Aptec spectrum file available to us (Aptec sample files, lab archive: 35 203 ROIs) contains
a MultiFit result (`wFunctionType` = 0 everywhere, no MultiFit flag), so MultiFit cannot be
compared with Aptec.  It is validated against spectra whose true peaks are known.

## Spectra

Generated with numpy's default generator, seeds 1000–1199 for the validation runs (other seeds
may be used while developing).  HPGe-like: 4096 channels, Gaussian peaks of FWHM 6 channels
(the resolution calibration given to MultiFit is the true one), linear background of 50
counts per channel, Poisson counts.  ROI: centroid of the outer peaks ± 2 FWHM.

* Singlets: area 2000.
* Doublets: total area 4000, area ratios 1:1 and 3:1, separations 0.8, 1.0, 1.5, 2.0 FWHM.

Fit setup: Aptec defaults (fixed width from the resolution calibration, fixed background from
the ROI end points, K = 1.645, Max Iterations 20, Percent Change 0.5 %, Max Overlaps 8),
"Overlapped Close Peaks" centroid search, multiplets and singlets fitted.

## Metrics and limits

For each configuration over the 200 spectra:

| Metric | Limit |
|---|---|
| Singlets: mean relative area bias | ≤ 1 % |
| Doublets with separation ≥ 1.0 FWHM: both components found (two peaks, each within 0.5 FWHM of its true centroid) | ≥ 90 % |
| Same: mean relative area bias of each component | ≤ 3 % |
| Same: standard deviation of the area pulls (fitted − true) / reported uncertainty | 0.8 – 1.25 |

Reported with no limit: the 0.8 FWHM doublets, centroid bias, reduced chi-square.

A pass shows that the implementation recovers known Gaussian peaks; it does not show
agreement with Aptec's MultiFit, which could not be compared.

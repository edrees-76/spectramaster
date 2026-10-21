# Peak-by-peak background subtraction with unresolved background lines: evaluation protocol (pre-registered)

Written 2026-10-21, **before** the implementation and before any benchmark run of it. The limits
below must not be changed after results are known. A result outside a limit is reported as a
failure.

## Motivation

In `after_SG1`, four NaI peak-mode criteria fail:

| id | value | limit |
|---|---|---|
| NaI.bkg_peak.cov1 | 0.350 | in [0.55, 0.81] |
| NaI.bkg_peak.cov2 | 0.708 | in [0.89, 1.0] |
| NaI.bkg_peak.false_detect | 0.167 | <= 0.11 |
| NaI.bkg_peak.net_bias | +0.029 | abs <= 0.03 (passes, but only just) |

The same NaI spectra in full-spectrum mode pass every criterion.

Diagnosis on the benchmark's own background pairs (60 pairs), per line, peak mode:

| line | bias | SD / u | z mean | cov2 |
|---|---|---|---|---|
| Cs-137 662 | +0.1 % | 1.16 | -0.02 | 0.92 |
| Co-60 1173 | -1.3 % | 1.57 | -0.32 | 0.82 |
| Co-60 1332 | +9.1 % | 1.22 | +2.09 | 0.43 |

Cause, from scratch probes:

- In peak mode the sample is fitted as measured. The background is then estimated under each
  sample peak with the sample fit's own linear estimator (`BackgroundFitter`). The gross fit and
  the estimator agree to 0.1 %.
- The Co-60 group (about 945-1600 keV) also holds background lines that the NaI resolution does
  not separate: Bi-214 at 1120, 1238 and 1377 keV. The sample fit has components only at about
  1173, 1332 and 1461 keV.
- These unmodelled lines distort the shapes of the Co-60 components. The estimator of the
  1332 keV component then takes 8.9 % of the Co-60 **1173 keV** peak.
- The background lines themselves cancel, because the same linear estimator is applied to the
  sample and to the scaled background. The share taken from the 1173 keV peak does not cancel,
  because it is a sample line that the background spectrum does not contain. This explains the
  +9 % on 1332 keV.
- In full-spectrum mode the background lines are removed before the fit, so the shapes are
  fitted on the sample's own peaks.

## Change

In peak mode, the peaks are searched and fitted on the background-subtracted spectrum
`S - k B`, with variance `S + k^2 B`, which is the same fit as full-spectrum mode. Their net
areas and uncertainties are the result.

The background under each peak (`bkg_peak`, shown in the results) and the detection limits of
lines without a peak still use the background fitter. It applies the estimator of this fit to
the background spectrum.

Consequence, stated in advance: in peak mode the net areas of found peaks become those of
full-spectrum mode. The two modes still differ in the background reported under each line and
in the detection limit of lines without a peak.

## Criteria

- **Every existing pre-registered criterion.** No PASS -> FAIL is allowed, including all
  `HPGe.bkg_peak.*` and `*.bkg_spectrum.*` criteria. The limits are unchanged.
- **The target criteria, limits unchanged:** `NaI.bkg_peak.cov1`, `cov2`, `false_detect` and
  `net_bias`.
- **Manual criterion.** In the per-line diagnosis above (60 NaI pairs, peak mode), every line's
  |bias| must be <= 3 %.

**Expected, but not criteria.** The NaI peak-mode coverage moves to that of spectrum mode (about
0.63 / 0.93 in the diagnosis), and the HPGe peak-mode values change little.

Before: `docs/baseline/after_SG1`. After: `docs/baseline/after_BP1`. The name was checked to be
free.

## Results (after_SG1 -> after_BP1, 2026-10-21)

| id | SG1 | BP1 | limit | status |
|---|---|---|---|---|
| NaI.bkg_peak.cov1 | 0.350 | 0.633 | in [0.55, 0.81] | PASS (was FAIL) |
| NaI.bkg_peak.cov2 | 0.708 | 0.942 | in [0.89, 1.0] | PASS (was FAIL) |
| NaI.bkg_peak.false_detect | 0.167 | 0.000 | <= 0.11 | PASS (was FAIL) |
| NaI.bkg_peak.net_bias | +0.0291 | +0.0096 | abs <= 0.03 | PASS |
| HPGe.bkg_peak.cov1 | 0.667 | 0.642 | in [0.55, 0.81] | PASS |
| HPGe.bkg_peak.cov2 | 0.958 | 0.967 | in [0.89, 1.0] | PASS |
| HPGe.bkg_peak.false_detect | 0.025 | 0.000 | <= 0.11 | PASS |
| HPGe.bkg_peak.net_bias | -0.0102 | -0.0090 | abs <= 0.03 | PASS |

Manual criterion: in the per-line diagnosis (60 NaI pairs, peak mode), the line biases are -0.39 %
(1173 keV), +1.35 % (1332 keV) and +0.39 % (662 keV). All are <= 3 %: PASS.

Everything else:

- No criterion went from PASS to FAIL. Three went from FAIL to PASS, and 13 criteria fail. No
  other criterion value changed.
- The old peak-mode false detections were K-40 1461 keV, detected in 21 of 40 NaI pairs. That
  line lies in the distorted Co-60 group.
- **Behaviour change, found in testing and not stated in the protocol in advance:**
  - A line present only in the background is no longer fitted in the sample. It is reported
    as not found, with the background under it, which also enters its detection limit.
  - Before, it was reported with a signed net area near zero.
  - Two tests that assumed the old behaviour were changed to check the new one:
    - `test_measured_background.py`: a background line stronger than in the sample.
    - `test_public_spectra.py`: the InterSpec Ba-133 pairs. 0 of 48 natural lines are detected,
      and both modes agree on Ba-133 within 2 %.

# Round-6 review: channel binning bias of the acceptance test's widths, M3 (pre-registered)

Written 2026-10-29, before any change to the code. Gemini round-6 review
(`C:\Users\DELL\Downloads\gemini_review_round6.md`, main 624e199), finding M3, checked on the code
(`analysis/detector_test.py` `peak_width`, `_width`, `_log_parabola`, main e8c3b05) and measured by
the harness below before this protocol was written.

**Finding.** `peak_width` takes the FWHM and FWTM of the acceptance test from the net channel
contents, the half and tenth maximum crossings interpolated by a parabola through the logarithms of
three channels. Each channel integrates the peak over its width, so for a narrow peak the crossings lie
outside those of the Gaussian: the widths are overestimated. Gemini measured +1.45 % at 4 channels per
FWHM (2.029 instead of 2.000 keV) and +2.5 % at 3 channels, for a peak centred on a channel. The
harness also shows that the bias depends on where the centroid falls within a channel (noise-free
Gaussians, 0.5 keV per channel):

| FWHM (channels) | centred on a channel | centred between two |
|---|---|---|
| 3 | +2.59 % | +7.87 % |
| 4 | +1.45 % | +4.49 % |
| 5 | +0.93 % | +2.89 % |
| 6 | +0.64 % | +2.01 % |
| 7 | +0.46 % | +1.47 % |

FWTM: +2.55 to +4.16 % at 3 channels, +0.44 to +0.74 % at 7. Below 3 channels the result already
carries the note "too few channels for an accurate width". A detector near its specified FWHM can
appear to exceed it.

**Decision.** The widths are not corrected: the acceptance test reports the width measured from the
channel contents, and a correction that depends on the centroid position would itself be an
estimate. The bias is stated instead, so that a value near the limit can be judged.

## Change

1. `peak_width` computes, for the measured FWHM and FWTM, the relative overestimate of a Gaussian
   integrated over channels when its centroid is on a channel and when it is between two channels:
   for each case the Gaussian width whose crossings (the same `_width`) give the measured width
   (fixed-point iteration), and measured / that width - 1. The two values are kept in the new fields
   `PeakWidth.fwhm_bin_bias` and `PeakWidth.fwtm_bin_bias` (lower, upper).
2. When the upper FWHM value is 1 % or more (and the FWHM is at least 3 channels), the width's note
   says: "FWHM x channels: the widths from the channel contents are overestimated by the channel
   binning, FWHM by a to b %, FWTM by c to d % (centroid on a channel to between two); not corrected".
   The acceptance test carries the note as before.
3. No value changes; engine version unchanged (1.26.0): only a note and two fields of the detector
   acceptance test.

Harness `validation/round6_fwhm.py`, fixed output folder `after_R6G`; values before the change
recorded with `--collect` into `after_R6G/round6_fwhm_before.json` (engine 1.26.0, e8c3b05), committed
with this protocol.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RG.C1 | measured FWHM overestimate (vs the true FWHM) of the 30 cases: 3, 3.5, 4, 5, 6, 7 channels, centroid offset 0, 0.1, 0.25, 0.4, 0.5 channel | inside `fwhm_bin_bias` within 0.05 percentage points, every case |
| RG.C2 | measured FWTM overestimate of the same cases | inside `fwtm_bin_bias` within 0.05 percentage points, every case |
| RG.C3 | the note | present exactly when the upper FWHM value is >= 1 % (all cases above and the two `round5_acceptance` spectra, in the acceptance notes); absent at 12 channels (5 cases) |
| RG.C4 | centroid, FWHM, FWTM, P/C of the 35 cases and of the two `round5_acceptance` spectra | identical to before, and to the values recorded in `round5_acceptance` |
| RG.C5 | benchmark (`after_R6E`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes, each changed existing test listed with its reason |

Before the change: RG.C1 to RG.C3 fail (no fields, no note); RG.C4 is the control.

## Limitations

- Noise-free Gaussians on a linear calibration: the range describes the binning of a Gaussian peak,
  not the tailing of a real peak, nor counting noise.
- The range is checked from 3 to 7 channels per FWHM; above, other effects of the method (ROI
  background) are of the same size.
- Only the acceptance test's widths are concerned; the widths of the peak analysis (`analysis.peaks`)
  are not examined here.

---

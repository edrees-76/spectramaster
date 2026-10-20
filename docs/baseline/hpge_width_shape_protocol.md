# HPGe resolution-model shape from the spectrum's own peaks: evaluation protocol (pre-registered)

Written 2026-10-20, **before** the implementation and before any benchmark run of it. The limits
below must not be changed after results are known. A result outside a limit is reported as a
failure.

## Motivation

After `medium_peaks_protocol.md` (`after_MP2`), HPGe peaks at s = 20 and 40 are fitted 3.1 % and
1.4 % low, and their 2-sigma coverage is 0.92. Three pre-registered criteria fail.

Diagnostics on scratch seeds:

- Weak peaks are fitted with the width held at the resolution model. A free width is used only
  when z > 25.
- Without a FWHM calibration, the model is the default HPGe resolution sqrt(0.75 + 0.00185 E).
- That model differs in shape from the detector: x0.92 at 200 keV, x0.96 at 450 keV, x1.015 at
  1400 keV.
- The existing rescale (`_rescale_model`) applies one median factor, and only when it is beyond
  8 %. It cannot correct a shape error.
- Fitted widths at s = 20 equal the model exactly, and the area errors follow the width errors:
  -5 % at 200 keV.

A scratch prototype was run before this protocol, on other seeds (15 spectra per s). It fitted
FWHM^2 = k^2 f^2 + d to the free widths of the strong isolated peaks:

| detector | s = 20 | s = 40 | s = 80 | strong | cov2 at s = 40 |
|---|---|---|---|---|---|
| HPGe | -1.9 % -> -0.9 % | -1.3 % -> +0.4 % | unchanged | unchanged | 0.88 -> 0.93 |
| NaI | worse | worse | SD x2.4 | | |

The change is therefore limited to high-resolution detectors.

## Change

`_rescale_model` gains a shape correction. It applies when all of these hold:

- The model is not a FWHM calibration and not a user width: it is the default resolution of the
  guessed detector, or estimated from the data.
- The detector is not a scintillator (`guess_detector` not in `LOGLINEAR_DETECTORS`).
- At least 3 strong isolated peaks have a free-width fit (the same selection as now:
  significance >= 10, not at a width bound, chi2r <= 20).
- These peaks span more than a quarter of the channels.

Then the model becomes f' = sqrt(k f^2 + d):

- k and d come from a weighted least-squares fit of the fitted FWHM^2. Weights are the
  significance / FWHM^2, since width precision scales with significance.
- The correction is accepted only if k > 0 and 0.5 < f'/f < 2 over the analysed range.
  Otherwise the current median rescale is used.

Nothing changes with a FWHM calibration, for scintillators, or with fewer than 3 such peaks.

## Benchmark

There are no new categories. The criteria are the existing `HPGe.medium.*` criteria, unchanged
(`medium_peaks_protocol.md`), plus every other pre-registered criterion. No PASS -> FAIL is
allowed.

A manual precision criterion compares against `after_MP2`: the HPGe medium relative SD at each s
must not grow by more than 10 % (ratio <= 1.10).

Expected, but not a criterion: `HPGe.medium.area_bias_s40` and `HPGe.medium.cov2` pass;
`area_bias_s20` may still fail.

Before: `docs/baseline/after_MP2`. After: `docs/baseline/after_HW1`. The name was checked to be
free.

## Results (after_MP2 -> after_HW1, 2026-10-20)

| id | MP2 | HW1 | limit | status |
|---|---|---|---|---|
| HPGe.medium.area_bias_s20 | -0.0314 | -0.0205 | abs <= 0.02 | **FAIL** (still) |
| HPGe.medium.area_bias_s40 | -0.0142 | -0.0016 | abs <= 0.01 | PASS (was FAIL) |
| HPGe.medium.area_bias_s80 | +0.0002 | -0.0031 | abs <= 0.01 | PASS |
| HPGe.medium.cov2 | 0.923 | 0.942 | in [0.93, 1.0] | PASS (was FAIL) |
| HPGe.ref.bias | -0.0101 | -0.0033 | abs <= 0.01 | PASS (was FAIL) |
| HPGe.ref.no_loss_bias | -0.0146 | -0.0096 | abs <= 0.01 | PASS (was FAIL) |

Precision, the manual criterion. The HPGe medium relative SD ratio HW1 / MP2 at s = 20 / 40 / 80
is 1.031 / 0.810 / 0.997, all <= 1.10: PASS.

Everything else:

- No criterion went from PASS to FAIL; four went from FAIL to PASS. 19 criteria fail.
- `HPGe.weak.area_bias_s7` is unchanged at -5.0 %, FAIL. Those spectra have no peaks strong enough
  for the shape correction.
- HPGe runtime median: 0.096 s -> 0.111 s.

The weak peaks of the shape fit are fitted at the effective width of channel-integrated counts,
FWHM^2 + 8 ln2 / 12 channels^2. The corrected model is that effective width, which is the width
the fit needs; the unit test compares against it.

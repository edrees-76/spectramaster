# Fit windows and width-shape extrapolation: evaluation protocol (pre-registered)

Written 2026-10-20, **before** the implementation and before any benchmark run of it. The limits
below must not be changed after results are known. A result outside a limit is reported as a
failure.

## Motivation

The second external review (Gemini, M3 and M4) reported two defects. Both were reproduced before
this protocol was written (scratch probes, not committed).

**M3, wide region of the log-quadratic continuum.** For scintillators the continuum curvature
b2 is measured on a region (1 + LOGQUAD_WIDE) times wider than the fit region, then held fixed
(`medium_peaks_protocol.md`). That wider region is not stopped at neighbouring peaks.

In the 40 NaI reference-peak spectra (`after_FF1`), the Co-60 group (channels ~391/444) is
fitted on a wide region of channels 195-645, which contains Cs-137 at channel 220. The wide fit
has chi2r 4.1-4.4 and is always rejected, so b2 = 0. The Co-60 net areas are fitted -4.48 %
(1173 keV) and -3.36 % (1332 keV) low; Cs-137 -0.62 %. These drive the failures of
`NaI.ref.bias` (-2.81 %) and `NaI.ref.no_loss_bias` (-2.28 %).

**M4, extrapolation of the HPGe width shape.** `_shape_rescale` fits FWHM^2 = k f^2 + d to the
free widths of strong isolated peaks and applies it to the whole spectrum. Example: strong peaks
at 100, 175 and 625 keV, with the two low ones 13 % wider than the model and the 625 keV peak at
the model. The corrected width is then x0.95 at 1200 keV and x0.92 at 1800 keV. Nothing beyond
625 keV supports that trend, and narrower widths bias weak high-energy areas low.

## Change

1. **Wide region stops at neighbours.** The wide region of the curvature fit stops 2.5 FWHM short
   of any other search candidate outside the group. This is the rule already used for the
   Compton-edge region (`EDGE_REGION_FWHM`) and the residual search. It is never narrower than
   the fit region itself. Everything else is unchanged: LOGQUAD_WIDE, the chi2 acceptance test,
   LOGQUAD_MAX and the fallback b2 = 0.
2. **No extrapolation of the width shape.** Between the lowest and highest strong peak used,
   the shape correction is applied as now. Outside that span the ratio f'/f is held at its value
   at the nearest end peak. The existing acceptance tests are unchanged (k > 0, 0.5 < f'/f < 2,
   at least SHAPE_MIN_PEAKS peaks spanning more than a quarter of the channels).

## Criteria

- **Every existing pre-registered criterion.** No PASS -> FAIL is allowed. The limits are
  unchanged, including `NaI.ref.bias` and `NaI.ref.no_loss_bias` (|bias| <= 1 %).
- **Manual precision criterion.** Compared with `after_FF1`, the relative SD of the NaI medium
  areas (s = 20, 40, 80) and of the NaI reference-peak line activities must not grow by more
  than 10 % (ratio <= 1.10).
- **Unit test for M4.** For the example above, the corrected width at 1800 keV must be within 1 %
  of the corrected width at 625 keV, as a ratio to the model.

**Expected, but not criteria.** The Co-60 area bias in the NaI reference spectra moves towards
zero, and `NaI.ref.bias` and `NaI.ref.no_loss_bias` may pass. Other NaI groups with a neighbour
3.5-7.5 FWHM away also change, and the change is reported whether it helps or not. HPGe results
change only where strong peaks do not span the spectrum.

Before: `docs/baseline/after_FF1`. After: `docs/baseline/after_FW1`. The name was checked to be
free.

## Results (after_FF1 -> after_FW1, 2026-10-20)

| id | FF1 | FW1 | limit | status |
|---|---|---|---|---|
| NaI.ref.bias | -0.0281 | -0.0073 | abs <= 0.01 | PASS (was FAIL) |
| NaI.ref.no_loss_bias | -0.0228 | -0.0020 | abs <= 0.01 | PASS (was FAIL) |
| NaI.bkg_peak.net_bias | +0.0319 | +0.0291 | abs <= 0.03 | PASS (was FAIL) |

In the NaI reference spectra, the Co-60 net areas went from -4.48 % to -1.47 % at 1173 keV and from
-3.36 % to -0.15 % at 1332 keV. Cs-137 is unchanged at -0.6 %. The Co-60 wide fit is now
accepted in all 40 spectra (chi2r about 0.98), where before it was rejected in every one.

Precision, the manual criterion:

- NaI medium relative SD ratio FW1 / FF1 at s = 20 / 40 / 80: 1.011 / 1.007 / 0.994.
- NaI reference-line activities: relative SD 0.0386 -> 0.0366 (ratio 0.95).
- All are <= 1.10: PASS.

The M4 unit test passes.

Everything else:

- No criterion went from PASS to FAIL. Three went from FAIL to PASS, and 16 criteria fail.
- **At its limit:** `HPGe.tailed.false_increase` went from 1.075 to 1.100 (limit <= 1.1), one more
  false peak in 40 spectra. It still passes, but with no margin.
- **Worse, among criteria that already failed:**
  - `NaI.bkg_peak.cov2`: 0.817 -> 0.708.
  - `NaI.bkg_peak.cov1`: 0.383 -> 0.350.
  - `NaI.id.false_per_spectrum`: 1.92 -> 2.17.
  - `NaI.eff.cov2`: 0.881 -> 0.873.
- **Better, among criteria that already failed:**
  - `NaI.tailed.cov2`: 0.571 -> 0.600.
  - `NaI_4096.id.false_per_spectrum`: 2.00 -> 1.83.
  - `NaI.bkg_peak.false_detect`: 0.183 -> 0.167.
- **Reasons:**
  - In the background-peak spectra the net bias improves, but the coverage drops, so the
    uncertainty of those peaks is now too small for their scatter. This is not corrected here.
  - The HPGe changes are small and come from the width-shape change (M4) only. The HPGe
    continuum is not log-quadratic.
- **Runtime median:** HPGe 0.100 s -> 0.098 s; NaI 0.055 s -> 0.059 s.

# Residual search in every fit region: evaluation protocol (pre-registered)

Written 2026-10-20, **before** any evaluation result was seen. The limits below must not be changed
after results are known. A result outside a limit is reported as a failure.

## Change

`analysis.peaks._fit_and_make` used to run a residual search only in fit regions that hold an
expected Compton edge. Single peaks with a bad fit could also be retried as a doublet. The change
runs the residual search in every region:

- It adds one component at a time.
- Each component goes at the most significant Gaussian-shaped excess of the residuals (z > 4).
- That excess must lie at least 1 FWHM from the fitted components.
- The region is widened when needed:
  - If χ²/dof > 2, the search runs on a region widened by 1.5 FWHM on each side.
  - The region also grows to include the new component.
  - In both cases it stops short of candidates fitted in other regions.
- The component is kept only when χ² on that same region drops by more than 9 (scaled by
  χ²/dof).

This idea comes from the published Genie 2000 algorithm description ("Residual Search",
Customization Tools manual ch. 3). No vendor software was decompiled.

## Development and test data

- **Development (tuning), already seen:**
  - A strong 662 keV peak (1e5 counts) with a weaker satellite on the high-energy side.
  - The satellite sits at 1.25 / 1.5 / 2.0 FWHM, with intensity ratios 10 / 30 / 100.
  - 8 realisations each, seeds 900000+, for HPGe and NaI.
  - Results: before the change, the satellite was often missed (HPGe 2 FWHM ratio 100: 1 of 8;
    NaI ratio 30: 0 of 8). After it, HPGe found 72 of 72 and NaI found all cases at ratios 10
    and 30 up to 1.5 FWHM. No extra peaks either way.
- **Test (counts against the limits):** the new benchmark category `satellites`.
  - Same separations and ratios.
  - The satellite alternates between the **high and the low** side.
  - Seeds come from `seed_of(det, "satellites", k)`, which is disjoint from the development
    seeds.
  - 8 realisations per case (48 per side-pair group).

## Criteria

New criteria (`acceptance.py`, category `satellites`):

| id | metric | limit | rationale |
|---|---|---|---|
| HPGe.satellite.found_ratio_le30 | satellite found, ratio <= 30, all separations | >= 0.90 | a satellite >= 3 % of a 1e5-count peak at >= 1.25 FWHM is clearly significant in HPGe |
| NaI.satellite.found_ratio10 | satellite found, ratio 10 | >= 0.90 | NaI resolution is ~7 %; only the 10 % satellite is required |
| {det}.satellite.found_ratio100 / NaI found_ratio30 | | report | may be below the statistical limit |
| {det}.satellite.extra_per_spectrum | reported peaks within the multiplet window beyond the matched ones | <= 0.05 | the search must not split peaks |
| {det}.satellite.main_area_bias | main peak area | abs <= 0.01 | adding a satellite must not distort the strong peak |
| {det}.satellite.sat_area_bias_ratio10 | satellite area, ratio 10, found | abs <= 0.10 | components of 1e4 counts beside 1e5 |

All earlier pre-registered criteria apply unchanged. The change is accepted only if none of them
moves from PASS to FAIL; this protects against false peaks, false splits, doublet behaviour,
Compton edges, weak peaks and identification. Runtime is reported.

Before and after: `docs/baseline/before_R1`, `docs/baseline/after_R1`.

## Amendment (2026-10-20, after the first evaluation)

The first evaluation **failed** the no-regression rule. All new satellite criteria passed, but
five earlier criteria went from PASS to FAIL:

| criterion | before | after |
|---|---|---|
| G1.G1100.false | 0 | 12 |
| G1.G1300.ratio_bias | 0.0004 | 0.042 |
| G1.G1300.cov2 | 0.94 | 0.76 |
| NaI.eff.bias | 0.003 | 0.012 |
| NaI.eff.cov1 | 0.65 | 0.47 |

Diagnosis on G1100: all 12 false components lay on the low-energy side of strong peaks, 0.55 to
0.8 FWHM away, at 1/4 to 1/25 of their area. This is the low-energy tail of real HPGe peaks.

The cause was an implementation error, not a threshold. The 1 FWHM proximity clause was checked
only for the candidate position, and the component then moved closer during the refit. The fix
applies the same clause to the fitted positions; no threshold was changed or added.

Because G1100 was inspected to find this error, **the G-1 set is no longer independent test data
for this change**. Its results after the fix are reported but carry less weight. The synthetic
test criteria and the other reference sets keep their status. The limits above are unchanged.

## Amendment 2 (2026-10-20, after the second evaluation)

With the proximity fix, all G-1 criteria were back to PASS. Two NaI efficiency criteria still went
from PASS to FAIL:

| criterion | before | after |
|---|---|---|
| NaI.eff.bias | 0.003 | 0.014 |
| NaI.eff.cov1 | 0.65 | 0.46 |

Diagnosis on the synthetic NaI calibration spectra (12 realisations): the search now found Cd-109
88 keV, which was missed before. It also redistributed the shared area of the overlapping low-energy
lines:

- Co-57 122 keV: point bias went from +5.8 % to +8.5 %.
- Ce-139 166 keV: point bias went from +0.8 % to +4.1 %.

At about 7 % resolution these lines overlap over several FWHM, and a residual split is not well
determined.

Decision: the residual search runs only where the spectrum is high resolution, defined as
FWHM / E <= `EDGE_MAX_REL_FWHM` (0.02). This is the condition already used for the Compton-edge
model. Uncalibrated spectra use the detector guess. NaI therefore keeps its previous peak fits.

The pre-registered NaI satellite criterion (`NaI.satellite.found_ratio10` >= 0.90) is evaluated
as it stands. Without the search it measured 0.958 on the test seeds. No limit was changed.

## Outcome of the first attempt (R1, 2026-10-20): not merged

After amendment 2 every pre-registered criterion passed. The search nevertheless split tailed
HPGe peaks: in the uncalibrated `tailed` category the unmatched peaks rose from 0.98 to 6.45 per
spectrum. No criterion caught it, because `{det}.tail.split` counts only matched splits. The
residual of an unmodelled low-energy tail is a real excess 1-2 FWHM below the peak, and the
search took it for a satellite. The change was not merged; the peak model needed a tail first.
That tail is now the detector's peak-shape calibration (`docs/baseline/peak_tail_protocol.md`,
merged in PR #16 and PR #17).

## Amendment 3 (2026-10-20, second attempt R2, written before any R2 result)

Change relative to R1: the residual search runs **only on spectra with a measured peak-shape
calibration**, which `analysis.peaks.shape_calibrated` checks. The calibration can be tailed, or
Gaussian (eta = 0). It also still requires high resolution, as in amendment 2. Without a measured
shape, the residual of an unmodelled tail cannot be told from a satellite, so uncalibrated spectra
are fitted exactly as before. A Gaussian calibration (eta = 0) is now recorded as
`extra["peak_shape_calibrated"]`; before, it left no trace on the spectrum. The session applies a
detector's measured shape even when it is Gaussian.

Evaluation:

- `satellites` is now fitted with the detector's shape calibration, measured on 3 tail-free
  calibration spectra (`shape_calibration_spectra(tail=False)`). Its criteria and limits are
  unchanged.
- New category `satellites_tailed`: the same pairs, but both peaks carry the 4 % / 1.5 sigma tail.
  They are fitted with the tailed calibration measured on 3 separate spectra. Seeds come from
  `seed_of(det, "satellites_tailed", k)`, and no R2 result has been seen. HPGe criteria:

| id | metric | limit |
|---|---|---|
| HPGe.satellite_tailed.extra_per_spectrum | reported peaks in the window beyond the matched ones | <= 0.05 |
| HPGe.satellite_tailed.main_area_bias | main peak area | abs <= 0.01 |
| HPGe.satellite_tailed.sat_area_bias_ratio10 | satellite area, ratio 10 | abs <= 0.10 |
| HPGe.satellite_tailed.found_ratio_le30 | satellite found, ratio <= 30 | >= 0.90 |

  NaI is not searched (low resolution), so the NaI values are reported only.
- The R1 blocker is measured by the pre-registered `{det}.tailed.split` (<= 0.05) and
  `{det}.tailed.false_per_spectrum` (<= 1.5) on `tailed_shape_cal`, where the search now runs.
- One criterion is added for that same blocker: **HPGe.tailed.false_increase**. The unmatched
  peaks per spectrum in `tailed_shape_cal` may rise by no more than 0.1 over the R2 baseline
  (1.0). This is stricter than the 1.5 limit, which allowed 0.5 extra per spectrum.
- The uncalibrated categories, including `tailed` and every G-1 / EML / IDB result, must be
  **identical** to the baseline, because the search does not run on them.
- All earlier criteria apply; none may go from PASS to FAIL.
- Before: `docs/baseline/after_T1` (the same engine as main 493c2db; PR #17 changed no engine
  code). After: `docs/baseline/after_R2`.

## Result of R2 (2026-10-20)

`docs/baseline/after_R2` against `after_T1`. **No pre-registered criterion went from PASS to
FAIL.** The same 16 criteria fail as before; they are known limitations not related to this
change. The full test suite gives 995 passed, 67 skipped.

| criterion | value | |
|---|---|---|
| HPGe.satellite.found_ratio_le30 | 1.00 | PASS |
| HPGe.satellite.extra_per_spectrum | 0.0 | PASS |
| HPGe.satellite.main_area_bias / sat_area_bias_ratio10 | 0.00003 / 0.003 | PASS |
| HPGe.satellite_tailed.found_ratio_le30 | 1.00 (ratio 100 also 1.00) | PASS |
| HPGe.satellite_tailed.extra_per_spectrum | 0.0 | PASS |
| HPGe.satellite_tailed.main_area_bias / sat_area_bias_ratio10 | 0.0007 / 0.0018 | PASS |
| HPGe.tailed.false_per_spectrum / false_increase / split | 1.0 / 1.0 / 0.0 (unchanged) | PASS |
| NaI.satellite.found_ratio10 | 0.958 (no search: low resolution) | PASS |

- Every other category is identical to the baseline, value for value. This includes the
  uncalibrated `tailed` category and the G-1, EML and IDB reference results, because the search
  does not run without a shape calibration.
- The R1 blocker is gone. With the tail modelled, the tailed peaks of `tailed_shape_cal` and
  `satellites_tailed` gained no component.
- HPGe median runtime per spectrum went from 0.11 to 0.13 s; the limit is 0.5 s.

Limitation: real spectra get the residual search only after the detector's peak shape has been
measured, using the detector manager's "Peak Shape..." command. No real-data result supports the
search yet. G-1 is not a valid test for it (see amendment 1), and the archive is private.

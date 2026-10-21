# Efficiency measurement with a background, non-Poisson spectra, outliers in the model error: evaluation protocol (pre-registered)

Written 2026-10-21, **before** the implementation and before any run of it. The limits below must
not be changed after the results are known. A result outside a limit is reported as a failure.

Round-3 review, plan item 5. Three defects:

1. **Gemini H3a.** `measure_efficiency(..., background=)` fits the peaks of the gross spectrum S
   and then subtracts `BackgroundFitter.under_peaks`. PR #35 (`bkg_peak_protocol.md`) removed this
   method from `compute_activities`, because unresolved background lines distort the shapes of the
   sample peaks. On NaI, Co-60 1332 keV took 9 % of the 1173 keV peak. `measure_efficiency` was not
   changed. The reviewer measured a bias of +8.96 % and a 2-sigma coverage of 0.450 for Co-60
   1332 keV on the NaI background pairs.
2. **Gemini M1.** `not_poisson_note` is checked only in `compute_activities`. A spectrum that has
   been normalized, smoothed or stripped can be searched (`find_peaks`) or used to measure an
   efficiency without any message. Normalizing by 10 raises the significances by sqrt(10) and
   lowers the efficiency uncertainties by sqrt(10).
3. **D2** (`crm_validation_protocol.md`). `model_error` is the mean excess of the leave-one-out
   residuals. A single outlier dominates it. In the CRM check, one 7-sigma point (the D1 line)
   gave a model error of 58.5 %. Without it the error was 8.1 %, and this error is added to every
   energy of the curve. D1 is fixed and the point is gone, but any other outlier would do the same.

**Not in this item:** Gemini H3b. A net peak between L_C and 3 sigma gets no activity in background
mode. This concerns the reported primary result of lines without a peak, and it belongs to item 6
(signed primary result, Codex M2).

## Changes

**R1, H3a.** With a background, `measure_efficiency` searches and fits the peaks of `S - k B` with the
variance `S + k^2 B` (`background.net_spectrum`). This is the fit `compute_activities` uses in both
background modes. The net areas and uncertainties of these peaks are the result, and the
`BackgroundFitter` subtraction is removed. The point note says "background subtracted before the fit
(S - kB)". A `peaks` list given together with a `background` is refused with `ValueError`, because
it was not fitted on `S - k B`.

**R2, M1.**

- `find_peaks` without `variance`: when `not_poisson_note(spectrum)` returns a note, the note is
  added to `FitReport.notes`. This is a new field and is empty otherwise. The peaks do not change.
- The analysis window shows the same note in its banner after a search.
- `cli peaks` prints it to stderr.
- `measure_efficiency` on such a spectrum appends the note "counts are not Poisson counts: the
  uncertainty is not valid" to every point. `fit_efficiency` adds a curve warning when a used point
  carries it.
- No refusal. These operations stay possible, but none of them is silent.

**R3, D2.** In `model_error`, the contribution of each left-out point is limited:
r_i^2 is replaced by min(r_i^2, Z^2 (s_i^2 + v_i)), with Z = `OUTLIER_Z` = 3. This is winsorizing at
the threshold the curve already uses to flag points for review. An outlier still raises the model
error, but by at most (Z^2 - 1)(s_i^2 + v_i) / n. Without such a point, the value is unchanged to the
last bit. `fit_efficiency` names the limited points in `curve.warnings`.

**ENGINE_VERSION** 1.4.0 -> 1.5.0. Efficiency points measured with a background and the curve
uncertainty change. Saved curves keep their stored `u_model_rel`.

## Criteria

Pre-registered; the limits come from existing protocols where one exists.

| id | test | limit |
|---|---|---|
| EP.C1 | H3a. `scenarios.background_pairs(det, 40)`, NaI and HPGe. `measure_efficiency(sample, cert, background=bkg)` with Cs-137 661.657, Co-60 1173.228 and 1332.492 keV (activity 1 Bq, no uncertainty, no date, library intensities). Ratio = point net area / true area. | every line found in every pair; per detector and line, \|mean ratio - 1\| <= 0.03 (the bkg_peak manual criterion) |
| EP.C2 | Same runs. z = (net - true) / net uncertainty, pooled over the three lines, per detector. | cov1 in [0.55, 0.81] and cov2 in [0.89, 1.0] (the bkg_peak limits) |
| EP.C3 | Identity. For the first 5 pairs of each detector, each point's net area and uncertainty equal those of the peak at the same energy from `find_peaks(S - kB, variance=S + k^2 B)`. | relative difference <= 1e-9 |
| EP.C4 | `measure_efficiency(..., peaks=..., background=...)` | `ValueError` |
| EP.C5 | M1. HPGe synthetic spectrum: raw; `spectrum_ops.normalize(s, 10)`; a background-subtracted spectrum. `find_peaks` with a `FitReport`; `measure_efficiency`; `fit_efficiency`. | raw: no note anywhere. Normalized and subtracted (without `variance`): `FitReport.notes` holds the note, every point carries it and `curve.warnings` names it. Subtracted with `variance=`: no note. Peaks identical with and without a report. |
| EP.C6 | M1 GUI. Offscreen: `_on_analysis_done` on a normalized spectrum, then on a raw spectrum. | the banner shows the note, then it is hidden |
| EP.C7 | D2 synthetic. 12 log-log points, 3 % uncertainties, scatter drawn with a fixed seed. (a) As is. (b) One point moved to 7 sigma. | (a) `model_error` bit-identical to the old formula (copied into the test). (b) value <= 2 x value of (a). |
| EP.C8 | D2 on CRM data. Cylinder and Marinelli, log-log, harness of `crm_validation_protocol.md`. One point is added in the RGTh-1 group to replay D1: Ac-228 674.75 keV at 0.05 x the clean curve's efficiency (0.105 / 2.1), u_count_rel 0.06, u_act_rel equal to that of the other RGTh-1 points. | model error with the point <= 2 x without, in both geometries (before: 58.5 / 8.1 and 54.8 / 10.0) |
| EP.C9 | The CRM protocol re-run unchanged (R1 changes its calibration points). | no PASS -> FAIL among CRM.C1, C2, C3.*, C4. CRM.C3 Ra-228 and Cs-137 already FAIL; their values are reported. |
| EP.C10 | Benchmark, `after_FC1` -> `after_EP1` (name checked to be free). | no PASS -> FAIL. Counts reported. |
| EP.C11 | Full test suite. | passes; existing tests changed only where this protocol changes behaviour, each listed with its reason |

**Expected, but not criteria.** The NaI Co-60 1332 keV bias drops from about +9 % to that of
`compute_activities` in peak mode (after_BP1). The HPGe values change little. On the clean CRM
data the model error changes only if a leave-one-out point exceeds 3 sigma.

## Results (2026-10-21)

The protocol text above was recorded with SHA-256
`9958b3394846368fe86507c7129f91a3aea6e177b68ea6ea60f5c5ca9062c6d9` before the implementation. Only this
section was added afterwards.

| id | value | limit | status |
|---|---|---|---|
| EP.C1 NaI | Cs-137 +0.37 %, Co-60 1173 +0.84 %, Co-60 1332 **+1.60 %**; every line found in all 40 pairs | \|bias\| <= 3 % | PASS |
| EP.C1 HPGe | -1.07 %, -0.47 %, -1.16 %; every line found | \|bias\| <= 3 % | PASS |
| EP.C2 NaI | cov1 0.633, cov2 0.933 (120 values) | [0.55, 0.81], [0.89, 1.0] | PASS |
| EP.C2 HPGe | cov1 0.642, cov2 0.967 | same | PASS |
| EP.C3 | identical to the net fit (5 + 5 pairs) | <= 1e-9 | PASS |
| EP.C4 | `ValueError` | | PASS |
| EP.C5 | as specified | | PASS |
| EP.C6 | banner shown, then hidden | | PASS |
| EP.C7 (a) | 0.00 %, bit-identical to the old formula | | PASS |
| EP.C7 (b) | 2.86 % with R3 (old formula 5.50 %) | <= 2 x (a) = 0 | **FAIL** (protocol design) |
| EP.C8 | with R3: cylinder 4.50 -> 5.31 %, Marinelli 4.11 -> 4.98 % | <= 2 x clean | PASS, but see R3 below |
| EP.C9 | CRM: 6 of 8, same statuses (table below) | no PASS -> FAIL | PASS |
| EP.C10 | `after_FC1` 154 / 13 / 60 -> `after_EP1` 154 / 13 / 60; only HPGe.runtime and NaI.runtime values changed | no PASS -> FAIL | PASS |
| EP.C11 | 1273 passed, 68 skipped; no existing test changed | | PASS |

### EP.C7 (b) fails by protocol design

With 3 % Gaussian scatter, the clean synthetic points give a model error of 0. The scatter is fully
explained by the point uncertainties. Any estimator that an outlier raises at all then fails
"<= 2 x clean". The limit should have been stated relative to the point uncertainty, not to the clean
value. It is reported as written and not changed.

### R3 withdrawn

Withdrawn after the CRM run (EP.C8, C9), before the commit. Its code and its two tests were removed.

The CRM calibration points do not scatter around the curve as their uncertainties say: chi^2/dof is
24 (cylinder) and 49 (Marinelli). The causes are true-coincidence summing, interferences and
peak-fit limits, as listed in `crm_validation_protocol.md`. With the cap at 3 times each point's own
uncertainty, R3 limited **17 of 34** cylinder points and 20 of 34 Marinelli points. That is not one outlier
but systematic scatter, which is exactly what the model error must keep. The results with R3
(`after_EP1/crm_validation_results_with_R3_withdrawn.md`):

| | without R3 | with R3 |
|---|---|---|
| model error, cylinder log-log | 8.32 % | 4.50 % |
| model error, Marinelli | 9.96 % | 4.11 % |
| CRM.C4 rms z, cylinder | 0.933 | 1.354 |
| Marinelli, fraction \|z\| <= 2.58 (reported) | 1.000 | **0.500** |

R3 therefore made the uncertainties less realistic on real data while every pre-registered criterion
passed. The criteria tested a single outlier on clean points, not systematic scatter. R3 is not
shipped.

**D2 stays open.** Without R3, the D1 replay of EP.C8 gives cylinder 8.32 -> 51.15 % and Marinelli
9.96 -> 51.56 %. A next protocol should set the cap relative to the points' actual scatter, for example
Z sqrt(s_i^2 + v_i + u_model^2) iterated to convergence. It needs criteria that include systematic
scatter (the clean CRM curves) as well as a single outlier.

### CRM re-run without R3 (EP.C9, `after_EP1/crm_validation_results.md`)

R1 changes the calibration points, because they are now fitted on S - kB.

| | after_LB1 | after_EP1 |
|---|---|---|
| CRM.C1 / C2 | 1.000 / 1.000 | 1.000 / 1.000 |
| CRM.C3 Ra-226 / Ra-228 / Th-228 / K-40 / Cs-137 | 1.066 / 1.147 / 1.066 / 0.926 / 1.114 | 1.067 / 1.147 / 1.066 / 0.925 / 1.115 |
| CRM.C4 | 0.945 | 0.933 |
| model error cylinder / two-branch / Marinelli | 8.13 / 8.78 / 9.98 % | 8.32 / 8.82 / 9.96 % |

Ra-228 and Cs-137 still FAIL CRM.C3, as before.

### Shipped

R1 and R2. `ENGINE_VERSION` 1.5.0. The changelog line names only R1 and R2.

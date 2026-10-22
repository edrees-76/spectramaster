# Implausible FWHM model (finding F1): pre-registered protocol

Written 2026-10-22, before the evaluation runs. This is finding F1 of
`iaea2002_validation_protocol.md`. Results are appended below the line after the run; nothing above
it changes after its SHA-256 is recorded.

## 1. Defect

The search takes its peak widths (FWHM in channels) from one of two sources:

* the stored FWHM calibration;
* a default detector resolution, divided by the gain of the energy calibration.

`fwhm_model` only checks that the stored calibration gives 0.8 to n/4 channels. A model that is
wrong by a large factor is used silently:

* **Rescaling cannot recover it.** `_rescale_model` corrects the model to the widths of strong
  isolated peaks. But a fit at its width bound (x0.5 or x2) is discarded, and the correction is
  clipped to x0.5–x2.
* **`maricsmall.chn` (IAEA 2002).**
  * Stored values: energy calibration (0, 1, 0), FWHM calibration (1, 0, 0), so 1 channel. The real
    peaks are about 4 channels wide.
  * All 8 strongest isolated peaks fit at the bound, so nothing is corrected and nothing is said.
  * On `main` the search finds 14 peaks. The same counts as `maricsmall.spe` (no calibration,
    widths measured on the spectrum) give 79.
  * The activity windows (decision threshold, MDA) use the same 1-channel model.
* **Other IAEA 2002 `.Chn` files.** Many store the energy calibration (0, 1, 0), so the default
  resolution is about 2.5 times too narrow. In `Cs137SMALL.Chn` the detector is guessed as NaI, so
  the default width is about 15 times too wide.

## 2. Measurements made before writing this protocol

A prototype of the change in §3 was run before this protocol was written:

* **IAEA 2002 `.Chn` files.** The model is replaced in 3 of 36: `maricsmall.chn` (x4.00),
  `Cs137SMALL.Chn` (x0.05) and `Co57SMALL.Chn` (x2.31). Peaks found go from 14 to 76, 8 to 18, and
  9 to 25 (the `.spe` copies: 79, 19, 24).
* **Synthetic `isolated_strong` spectra** (10 per case) given a stored FWHM calibration of k times
  the true width:
  * k = 4 (HPGe and NaI) and k = 0.25 (NaI): replaced in 10 of 10.
  * HPGe k = 0.25 is already rejected by the existing 0.8-channel check.
  * k = 0.7, 1.0 and 1.4: never replaced.
  * Recall 1.0 in every case.
* **Not addressed here.** Some `.Chn` files with the (0, 1, 0) energy calibration still find fewer
  peaks than their `.spe` copy, for example Am241 and Cd109 (5 against 14 to 26). Their model is
  within x2 of the measured widths, so this check does not apply. The placeholder energy
  calibration is a separate finding.

## 3. Change

1. **`checked_fwhm_model(spectrum, y, var)`** in `analysis/peaks.py`:
   * It starts from `fwhm_model`.
   * The model is implausible when both hold:
     * at least 3 strong candidates are considered by `_width_points`, and fewer than half of them
       give a usable free width;
     * the widths measured without the model (`_estimate_fwhm_from_data`, the estimator already
       used for uncalibrated spectra) differ from it by more than x2 (median ratio over the
       analysed channels outside [0.5, 2]).
   * An implausible model is replaced by the measured widths. The source becomes
     `data (FWHM model implausible: <source> x<ratio>)`.
2. **`width_model`** (search, manual refits, shape calibration, session peak editing) uses it.
   `find_peaks` adds a note to the `FitReport`. The note names the model and the ratio and asks for
   the calibration to be checked.
3. **`compute_activities`** uses it for the window widths (decision threshold, MDA) and adds the same
   note to the result notes.
4. **`ENGINE_VERSION`** becomes 1.10.0. Nothing changes when the model is plausible.

## 4. Criteria (set before the run)

| id | what | limit |
|---|---|---|
| FP.C1 | `maricsmall.chn` | model replaced, note in the `FitReport` and in the activity notes; peaks found >= 60 |
| FP.C2 | `maricsmall.chn` against `maricsmall.spe`, `calibrate_from_source(..., use_existing=False)` with the certificate nuclides except Cr-51 | number of lines >= 15; gain within 0.5 % of the gain on `maricsmall.spe` |
| FP.C3 | IAEA 2002 `.Chn` files (36) | replaced exactly in `maricsmall.chn`, `Cs137SMALL.Chn`, `Co57SMALL.Chn`; for each, peaks found >= 80 % of its `.spe` copy |
| FP.C4 | synthetic `isolated_strong`, 20 spectra per case, HPGe and NaI, stored FWHM calibration k x true | k = 4 (both) and k = 0.25 (NaI): replaced in all; k = 0.7, 1.0, 1.4: replaced in none; recall of every case >= recall at k = 1 minus 0.02 |
| FP.C5 | standard benchmark against after_ID1 (values and key order) | identical except runtime fields and `engine_version`; 154 PASS / 13 FAIL / 60 REPORT; runtime criteria PASS |
| FP.C6 | IAEA 2002 harness against after_AN1 | criteria statuses identical (5 PASS / 2 FAIL); values that differ are listed with the spectrum that caused them |
| FP.C7 | CRM harness against after_WP1 | criteria values identical (only `engine_version` differs) |
| FP.C8 | new unit tests; full test suite | pass; changed existing tests listed with reasons |

Outputs go to a new folder `docs/baseline/after_FP1/`. IAEA spectra are not copied into the
repository; only derived numbers are stored.

---
## Results

(appended after the run)

Run 2026-10-22, engine 1.10.0. The text above the line is unchanged (SHA-256 of the pre-registered
part still 930609eda82544bd0edc6046093d583a519c755a8a0b9c36f8ebea79a9c34383). Outputs:
`docs/baseline/after_FP1/`, which holds:
* `fwhm_plausibility_results.json`: FP.C1–C4, plus the C4 cases run on `main` for comparison;
* `baseline.*`;
* `iaea2002_results.*`;
* `crm_validation_results.*`.

| id | value | limit | result |
|---|---|---|---|
| FP.C1 `maricsmall.chn` | replaced (x4.00); note in the `FitReport` and the activity notes; 76 peaks (`main`: 14) | >= 60 | PASS |
| FP.C2 calibration | 17 lines on `.chn` and on `.spe`; gain 0.432866 against 0.432865 (+0.0001 %) | >= 15; 0.5 % | PASS |
| FP.C3 IAEA `.Chn` | replaced in exactly the three files; peaks 76/79, 18/19, 25/24 of the `.spe` copy | | PASS |
| FP.C4 synthetic | replacement as registered in all 10 cases; recall NaI k = 0.25 and k = 4: **0.958** against 1.000 at k = 1 | >= 0.98 | **FAIL** |
| FP.C5 benchmark | **13 PASS -> FAIL**: 141 PASS / 26 FAIL / 60 REPORT | 154 / 13 / 60, identical | **FAIL** |
| FP.C6 IAEA 2002 | **IA.C1 PASS -> FAIL** (18/20 -> 17/20 pairs with \|z\| <= 2.58); 20 ratios differ, by up to 0.3 % | statuses identical | **FAIL** |
| FP.C7 CRM | criteria values identical | | PASS |
| FP.C8 tests | new tests 11 passed; **5 existing tests fail** (below) | pass | **FAIL** |

**The change as written is not shipped.** It finds the F1 defect, but it also replaces correct
models.

* **Where it goes wrong.** The trigger (fewer than half of the strong isolated peaks give a usable
  free width) fires on spectra where the model is right but the strong isolated peaks are few,
  weak or crowded:
  * NaI background spectra;
  * background-subtracted and blank-corrected NaI spectra;
  * NaI doublets and satellites;
  * IDB spectra.
  The estimator without a model (`_estimate_fwhm_from_data`) is then wrong by more than x2. On the
  synthetic NaI background spectra it gives about 0.35 of the true width.
  * Diagnostic: 2 of 12 NaI background spectra replaced; IDB HPGe spectrum 3.spe replaced (x0.46).
* **Benchmark PASS -> FAIL (13, all NaI):**
  * `doublet.area_bias_wide` +0.003 -> -0.42;
  * `satellite.extra_per_spectrum` 0 -> 0.22;
  * `satellite.main_area_bias` -0.008 -> -0.046;
  * `satellite.sat_area_bias_ratio10` -0.009 -> -0.15;
  * `bkg_peak` and `bkg_spectrum`: net bias +0.009 -> -0.88, cov1 and cov2 -> 0;
  * `blank`: bias -0.003 -> -1.05, cov1 and cov2 -> 0.

  Values also change in IDB (all detector kinds), NaI drift, `satellite_tailed` and NaI_4096
  identification.
* **IAEA 2002.** The ratios of every test pair change slightly, through the background spectra. One
  more Na-22 pair leaves |z| <= 2.58, so IA.C1 fails.
* **Failing existing tests (not changed):**
  * `test_efficiency_poisson::test_bias_per_line[NaI]` and `test_coverage[NaI]`: Cs-137 not found
    with the background;
  * `test_measured_background::test_unresolved_background_line_does_not_bias_a_sample_peak`;
  * `test_public_spectra::test_idb_plutonium_is_identified_in_hpge_spectra`;
  * `test_iaea2002_validation::test_marinelli_reproduces_the_recorded_ratios`.
* **FP.C4.** NaI k = 4 misses the 2000 keV line in 5 of 20 spectra. On `main` all of them are found
  (`main` recall: k = 0.25 0.78 with 4.7 false peaks per spectrum; k = 4 1.00).
* **Another finding.** For `maricsmall.chn` the estimator without a model found no usable width
  point and returned its fallback of 4 channels everywhere. That happens to be close to the true
  width. The success on that file is partly luck.

A narrower rule follows in an amendment protocol, written before its run. No limit above is
changed.

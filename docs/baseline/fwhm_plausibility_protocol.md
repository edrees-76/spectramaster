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

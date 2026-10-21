# Implausible FWHM model (finding F1), amendment: pre-registered protocol

Written 2026-10-22, after the results of `fwhm_plausibility_protocol.md` (3 PASS / 5 FAIL, not
shippable) and before this evaluation run. Results are appended below the line after the run;
nothing above it changes after its SHA-256 is recorded.

## 1. Why the first rule failed

* The first rule replaced the model when fewer than half of the strong isolated peaks gave a
  usable free width.
* That happens for many reasons on spectra whose model is right: few, weak or crowded peaks; NaI
  backgrounds; background-subtracted spectra.
* The replacement came from `_estimate_fwhm_from_data`, which is unreliable on such spectra
  (about 0.35 of the true width on NaI backgrounds).

## 2. Measurements made before writing this protocol

A wrong model has a specific signature: the free-width fits of the strong isolated peaks run into
the *same* width bound. In `maricsmall.chn` all 8 hit the upper bound (x2). In `Cs137SMALL.Chn`,
3 of 5 hit the lower bound (x0.5). A prototype of §3 was run on:

* **IAEA 2002 `.Chn` (36 files).** Replaced in 6:
  * `maricsmall.chn` and `Cs137SMALL.Chn`;
  * `maritsmall60.Chn`, `mix2eq.Chn`, `mix2eq3.Chn` and `mix2neq6.Chn`, which have the placeholder
    energy calibration (0, 1), so the default width is about 2.5 times too narrow.
* **IAEA 2002 harness spectra** (calibrated `.spe`): none replaced.
* **Synthetic `isolated_strong`, 20 per case, stored FWHM calibration k x true:**
  * HPGe k = 4: replaced in all;
  * NaI k = 0.25: replaced in all;
  * k = 0.7, 1.0, 1.4: none replaced;
  * HPGe k = 0.25 and NaI k = 4: none replaced (the first is rejected by the existing check; the
    second is handled by the existing rescale).
* **Other synthetic sets, HPGe and NaI:** none replaced. The sets: background pairs (sample and
  background), doublets, satellites, weak, background only, medium, Compton edge, low counts.
* **IDB, every 10th spectrum (160, the benchmark's subset):** replaced in 4. In 761, 771 and 781
  (CdTe) the default CZT resolution is about 3.5 times wider than the measured widths. In 1321
  (CZT) the model is about 1.7 times too narrow.

## 3. Change (replaces §3 of the first protocol)

`checked_fwhm_model(spectrum, y, var)`:

1. It starts from `fwhm_model`. With no model (`"none"`) nothing changes.
2. **Vote.**
   * Take the strongest 8 search candidates (significance >= 12), as `_width_points` does.
   * Keep those with no other candidate within 4 FWHM.
   * Fit each with a free width in [x0.5, x2] of the model.
   * Count the fits that end at the upper bound ("wider") and at the lower bound ("narrower"). Fit
     quality is not required; a wrong width gives a bad fit.
3. **Rescale.**
   * At least 3 isolated candidates are needed.
   * If at least max(3, half of them) are "wider", the model is multiplied by 2. If as many are
     "narrower", it is multiplied by 0.5.
   * The vote is repeated on the scaled model, at most 5 times. The usual `_rescale_model`
     refinement follows, as for any model.
4. **Report.**
   * If the factor is not 1, the source becomes `rescaled (FWHM model implausible: <source>
     x<factor>)`.
   * The search (`FitReport.notes`) and `compute_activities` (result notes) say that the model did
     not match the peak widths and was rescaled, and ask for the calibration to be checked.
5. `_estimate_fwhm_from_data` is no longer used by this check. `ENGINE_VERSION` stays 1.10.0
   (unreleased).

## 4. Criteria (set before the run)

| id | what | limit |
|---|---|---|
| FA.C1 | `maricsmall.chn` | rescaled; note in `FitReport` and activity notes; peaks found >= 60 |
| FA.C2 | `maricsmall.chn` against `.spe`, `calibrate_from_source(use_existing=False)`, certificate nuclides except Cr-51 | >= 15 lines; gain within 0.5 % |
| FA.C3 | IAEA 2002 `.Chn` (36) | rescaled exactly in the 6 files of §2; for each, peaks found >= 80 % of its `.spe` copy |
| FA.C4 | synthetic `isolated_strong`, 20 per case, k in {0.25, 0.7, 1.0, 1.4, 4} | rescaled as in §2 (HPGe k = 4 and NaI k = 0.25 all, every other case none); recall of every case >= its `main` recall (after_FP1 `C4_main`) minus 0.02 |
| FA.C5 | the other synthetic sets of §2, the same sizes | 0 rescaled |
| FA.C6 | standard benchmark against after_ID1 | no PASS -> FAIL; criteria statuses identical (154 / 13 / 60); values identical, key order included, except runtime fields, `engine_version`, and the `IDB` section (listed) |
| FA.C7 | IAEA 2002 harness against after_AN1 | all values identical |
| FA.C8 | CRM harness against after_WP1 | criteria values identical |
| FA.C9 | tests | the 5 existing tests that failed in after_FP1 pass; full suite passes; changed tests listed |

Outputs go to a new folder `docs/baseline/after_FP2/`.

---
## Results

(appended after the run)

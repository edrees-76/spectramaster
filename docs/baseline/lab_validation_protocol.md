# Laboratory validation against measured spectra, Genie-2000 reports and proficiency tests (pre-registered)

Written 2026-10-30, before any of the data it applies to has been received or seen. Engine 1.35.0
(main 0d2c16c). The limits below are fixed now; they are not changed after the data are seen. A
change is made only as a separate pre-registered amendment, before the run it applies to, and every
failed run and harness error is kept and disclosed (as for every protocol in `docs/baseline`).

## Purpose

All evidence so far is synthetic, public or a partial comparison with stored Aptec and GammaVision
results. This protocol tests SpectraMaster on a laboratory's own measurements: the same spectra
analysed by Genie-2000 (and, where available, a FoodGuard-1 monitor), the laboratory's efficiency
calibration and its certificate, and proficiency-test (PT) or intercomparison samples whose reference
values are known. Agreement with another program is comparison evidence, not proof of correctness;
the PT and certified-source criteria are the tests against a known truth. Passing this protocol is
evidence for the laboratory's own decision; it is not a claim of validation or compliance by
SpectraMaster.

## Data and handling

Expected from the laboratory (each item optional; what is missing is listed, never assumed):

| item | used by |
|---|---|
| original sample spectra (Genie `.CNF`; FoodGuard-1 native files) with live and real time | LV.C3-C6 |
| Genie-2000 analysis reports of the same spectra (activity, uncertainty and its coverage factor, MDA, detection decision, library, settings) | LV.C3-C5 |
| efficiency calibration file and the spectrum it was made from, with the source certificate (activities, uncertainties, reference date) | LV.C2 |
| background spectrum and how Genie used it | LV.C3-C5 |
| sample data: geometry, mass or volume and its basis, reference date | LV.C3, LV.C6 |
| PT / intercomparison: the spectra of the PT samples, the provider's reference values and uncertainties, the provider's acceptance rule, the laboratory's reported values | LV.C6 |
| a certified source or reference material measured as a sample and not used in the calibration | LV.C7 |

- The data are private and read-only: kept in a folder outside the repository, never copied into it,
  never quoted. Samples are named S01, S02, ... in every committed output; no sample description, ID,
  customer or date is committed.
- The harness (`spectramaster/validation/lab_validation.py`, to be written) takes the data folder as
  an argument and writes per-sample values only to a private folder outside the repository; the
  committed results (`docs/baseline/after_LV1`) hold aggregate statistics, counts and anonymised
  per-pair values.
- The harness may be written after the data arrive by looking at the file *structure* (formats,
  report layout) only; its matching rules (below) are fixed here. If a structure forces a change of a
  rule, it is pre-registered as an amendment before the first run.

## Matched analysis (fixed now)

SpectraMaster is run with the laboratory's choices wherever they are known, so that a difference
measures the analysis, not the inputs:

1. **Efficiency:** the curve rebuilt in SpectraMaster from the laboratory's calibration spectrum and
   certificate (LV.C2), same geometry; when that spectrum is missing, the laboratory's efficiency
   points entered by hand with their uncertainties.
2. **Library:** the nuclides and lines of the Genie library used for the sample (energies and
   emission probabilities taken from the report or library file); SpectraMaster's own library only
   when Genie's is not available, stated per sample.
3. **Times and dates:** live time from the spectrum; decay to the report's reference date.
4. **Background:** the same background spectrum, subtracted peak by peak as SpectraMaster does; when
   Genie used none, none.
5. **Corrections:** true-coincidence summing and self-attenuation only when Genie applied them (same
   inputs); otherwise off. Each case is listed.
6. **Limits:** Currie (k = 1.645) unless the report states ISO 11929, then ISO 11929.
7. **Uncertainties:** compared at the same coverage factor (Genie's k read from the report; both
   converted to k = 2 for En).

No setting is tuned per sample after its result is seen.

## Definitions

- Relative difference D = (A_SM - A_ref) / A_ref.
- En = (A_SM - A_ref) / sqrt(U_SM^2 + U_ref^2), U expanded uncertainties at k = 2.
- PT accuracy test (IAEA ALMERA rule): |A_ref - A_SM| <= 2.58 sqrt(u_ref^2 + u_SM^2) (standard
  uncertainties). PT precision test: P = sqrt((u_ref/A_ref)^2 + (u_SM/A_SM)^2) x 100 % <= LAP, the
  provider's limit of acceptable precision; when the provider gives none, LAP = 20 %. A result is
  *Accepted* when it passes both.
- z = (A_SM - A_ref) / sigma_pt when the provider gives sigma_pt: |z| <= 2 satisfactory,
  2 < |z| < 3 questionable, |z| >= 3 unsatisfactory (ISO 13528).
- Detector classes HPGe and NaI are evaluated separately throughout.

## Criteria

| ID | quantity | limit |
|---|---|---|
| LV.C1 | data completeness (gate) | REPORT: items received, samples usable per criterion with the reason for each exclusion. With fewer than 20 usable HPGe sample spectra (10 NaI) for LV.C3-C5, those criteria are reported as "insufficient data" and no PASS is claimed for them |
| LV.C2 | efficiency rebuilt from the laboratory's calibration spectrum and certificate | at >= 90 % of the laboratory's calibration points: \|En\| <= 1 against the laboratory's efficiency, and \|D\| <= 5 % (HPGe) / 10 % (NaI); the rebuilt curve within 5 % (HPGe) / 10 % (NaI) of the laboratory's over the calibrated energy range |
| LV.C3 | activity of nuclides detected by both programs, against Genie | \|En\| <= 1 for >= 90 % (HPGe) / 80 % (NaI) of the pairs; median D within +-5 % (HPGe) / +-10 % (NaI) |
| LV.C4 | detection decision, every nuclide of the sample's library | agreement >= 90 %, excluding borderline pairs (either program's result between 0.5 and 2 times its own decision threshold), which are counted and reported separately |
| LV.C5 | MDA of the same pairs, ratio SpectraMaster / Genie | median ratio in [0.67, 1.5]; the 10th and 90th percentiles reported |
| LV.C6 | PT / intercomparison results, against the provider's reference values | >= 80 % Accepted (accuracy and precision tests), per detector class; z reported where sigma_pt is given; the laboratory's own reported values under the same tests reported alongside |
| LV.C7 | certified source or reference material measured as a sample | every certified nuclide above 10 times its MDA: PT accuracy test passed and \|D\| <= 10 % |

Each criterion is evaluated only on the data it needs; a criterion without data is "not tested",
never PASS. LV.C3-C5 compare two programs; LV.C6 and LV.C7 compare with a known value and carry the
most weight.

## Interpretation fixed now

- All tested criteria PASS: SpectraMaster agrees with Genie and with the known values within these
  limits on these data. This supports the laboratory's decision to use it; it does not extend to other
  detectors, geometries or sample types than those tested.
- LV.C6 or LV.C7 FAIL: a defect or a matching error to be found before any use beyond parallel
  operation; the cause is investigated and reported, and a fix follows the usual pre-registered path.
- Only LV.C3-C5 FAIL while LV.C6 and LV.C7 PASS: the programs differ but SpectraMaster agrees with
  the truth; the differences are analysed and reported, not "fixed" towards Genie.

## Limitations

- Agreement with Genie-2000 is not proof; both programs may share an input error (efficiency,
  library, geometry).
- The results apply to the detectors, geometries, matrices and activity ranges in the data.
- Genie's internal algorithms are not inspected (no decompiling); differences are explained from the
  reports and settings only.
- FoodGuard-1 results are compared only if its native files can be read and its report gives
  activities with uncertainties; otherwise they are listed as not tested.

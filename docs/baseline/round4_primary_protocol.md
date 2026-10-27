# Round-4 review, signed primary result of nuclides not detected (Gemini H2): evaluation protocol (pre-registered)

Written 2026-10-27, **before** the changes below were made. Gemini H2 has three parts. Part 1
(`concentrations()` dropping the ISO 11929 best estimate) was fixed in R4-A
(`round4_activity_protocol.md`). Parts 2 and 3 were checked on the code (engine 1.18.0, commit
82ab3d2). The "before" values are collected by the harness of this protocol
(`python -m spectramaster.validation.round4_primary --collect`) and kept in
`docs/baseline/after_R4H/round4_primary_before.json`, and the signed-primary harness was run before
the change (`python -m spectramaster.validation.primary`, outputs kept outside the repository and
compared in RH.C3). The limits must not be changed after results are known. A result outside a limit
is reported as a failure.

## Findings and changes

1. **The primary result of a nuclide not detected comes from the key line only (Gemini H2.2,
   confirmed).** `signed_primary_protocol.md` registered the nuclide's `primary` as "combined like
   the activity (key line or weighted mean)", but `_combine()` takes the key line's primary in every
   case. With `method="mean"` the other lines are ignored. When the key line's window result is
   "interfered" or "curved" (not used), the nuclide gets that unusable result and no best estimate,
   even when another line has a usable window result. Change, for a nuclide without an activity:
   * usable lines: lines with a window primary result (`primary_method == "window"`);
   * `method="mean"`: the weighted mean of the usable lines, with the weights and uncertainty
     components of the activity combination (`_combine_activity`: weights from counting and
     intensity variances; efficiency, coincidence and reference-peak components correlated);
     `primary_method` "window";
   * `method="key"`: the key line when it is usable; otherwise the usable line with the smallest MDA,
     with a note naming that line; when no line is usable, the key line's result as before (method
     "interfered" or "curved", no best estimate).
   The activity, the detection decision, the decision threshold and the MDA do not change.
Not changed (Gemini H2.3, checked): `_quad_result()` does not mix a linear background estimator into
the quadratic window. With the background fitter (peak mode) the window result subtracts the
background spectrum's own window counts (`bfit.b`, `bfit.k`), and in spectrum mode the scaled
background counts, each with its own quadratic window; `bnet` (a fitted peak area) is subtracted only
for caller-supplied background peaks, and is a peak area, independent of the sample's continuum
model. A unit detail was found: `bnet` is a full peak area while the window holds the fraction
`fwin` (0.997 for E +- 1.25 FWHM) of a peak; the difference is at most 0.3 % of the background term
and is left as it is.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RH.C1 | HPGe, 200 synthetic spectra without Ba-133 (seeds fixed; base continuum and Co-60 peaks of the signed-primary harness), `nuclides=["Ba-133"]`, `method="mean"`, `mda_method="iso11929"` | in every spectrum with at least 2 usable lines, the nuclide's primary equals the weighted mean computed from the line results as specified in 1 (relative 1e-9); z = primary / primary_u over the 200 spectra: \|mean z\| <= 0.2 and fraction \|z\| <= 2 in [0.91, 0.99]; best estimate and coverage interval present in every spectrum with a usable line |
| RH.C2 | HPGe, 100 synthetic spectra without Cs-134, a peak (SNR 40) 1 FWHM above the 604.7 keV key line, `nuclides=["Cs-134"]`, `mda_method="iso11929"` (key method) | in at least 0.9 of the spectra whose key line is not usable and which have a usable line: the nuclide's primary method is "window", it equals the usable line with the smallest MDA, and the best estimate is present; over those spectra \|mean z\| <= 0.3 and fraction \|z\| <= 2 >= 0.90 |
| RH.C3 | existing harnesses and tests | every criterion of `validation.primary` (versions 1-3) has the same PASS/FAIL state as before the change; benchmark PASS/FAIL counts unchanged (154 / 13) and no criterion changes state; full test suite passes (tests that lock the old key-line-only behaviour are changed, with the reason recorded) |

## Outputs

`docs/baseline/after_R4H/round4_primary.md` and `.json`, from
`python -m spectramaster.validation.round4_primary`, and `docs/baseline/after_R4H/baseline.md` and
`.json`.

## Limitations

- Synthetic spectra only, HPGe for the criteria (NaI Ba-133 lines overlap at NaI resolution; NaI
  numbers of RH.C1 are reported, not judged).
- The ISO 11929 best estimate of a nuclide not detected stays a reported quantity; the activity
  column keeps "< MDA".

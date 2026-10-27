# Round-4 review, calibration and manual-fit findings (R4-D): evaluation protocol (pre-registered)

Written 2026-10-27, **before** the changes below were made. The observations "before" were collected
with engine 1.17.0 (commit 1a23db7) by the harness of this protocol
(`python -m spectramaster.validation.round4_calibration --collect`) and are kept in
`docs/baseline/after_R4D/round4_calibration_before.json` (synthetic spectra, and only names and
calibration coefficients of the IAEA 2002 test spectra, which stay outside the repository). The
findings come from the fourth external review (Gemini H4 parts 1 and 2, Codex M1 and Gemini H1
part 2) and were checked on the code first. The limits must not be changed after results are known.
A result outside a limit is reported as a failure.

## Findings and changes

1. **The calibration dialog keeps the first FWHM calibration (Gemini H4.1).** `SourceCalibrationDialog.refit()`
   refits the energy calibration after the user excludes a line or changes the order, but the FWHM
   calibration shown and applied stays the one of the first proposal, which may include the excluded
   line. Change: `calibrate_from_source` keeps the measured width of every matched line
   (`SourceCalibration.line_widths`, centroid and width in channels); a new
   `fwhm_from_widths(widths, keys, coeffs, channel_range)` fits the FWHM calibration through the
   widths of the lines given (same rules as before: 511 keV left out, order 2 from 4 widths when it
   rises over the lines, outlier removal); the dialog calls it after every refit with the lines still
   used and the new energy calibration, and applies that one. No peak is refitted (the widths are
   measured once).
2. **A falling or negative FWHM calibration is accepted (Gemini H4.2).** With order 1 the slope is
   not checked, and an order-2 fit is only required to rise over the lines: Gemini's two widths
   (6.0 keV at channel 100, a doublet, and 2.5 keV at channel 1000) give FWHM = 6.39 - 0.0039 ch,
   -25 keV at the end of the spectrum. Change: an order-2 fit must also be positive over the whole
   channel range of the spectrum, otherwise order 1 is used; an order-1 fit must have a slope >= 0 and
   be positive over the whole range, otherwise no FWHM calibration is proposed and
   `SourceCalibration.fwhm_note` (shown in the dialog and the report) says that the measured widths
   decrease with energy or give a non-positive FWHM.
3. **The manual fit of a net spectrum gets no variance (Codex M1, Gemini H1.2).** `manual.refit_region`
   accepts `variance=` (`manual_fit_variance_protocol.md`), but the fit-inspection window never passes
   it, so a background-subtracted spectrum is fitted with clipped counts and Poisson weights, with a
   note that the uncertainties are not valid. Change: a spectrum can carry its per-channel variance,
   tied to its counts by their SHA-256 (`analysis.background.set_channel_variance` /
   `channel_variance`; any later change of the counts makes it unknown, so it can never be stale).
   `subtract_background` stores S + k^2 B; the Aptec operations Normalize (x f^2), Strip and Combine
   (sum of the variances) and Shift propagate it, taking a Poisson spectrum's variance as its counts;
   every other operation leaves it unknown. The fit-inspection window passes it to refit, add and
   remove. A raw Poisson spectrum is fitted exactly as before. The variance is held in memory only (a
   net spectrum saved to a file and opened again has no variance and gets the note, as before).

Not changed: Gemini H4.3 (`line_widths` window of +-2.5 model FWHM without the tail): the widths are
bounded and checked against an independent scan in `mix_peak_areas_protocol.md`; a change needs its
own data. The variance is not passed to the automatic analysis (peak search) of a net spectrum in the
GUI: that changes its results and is left for a separate protocol.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RD.C1 | 3 synthetic HPGe Eu-152 spectra (benchmark scenario `calibration_source`) | the proposal's FWHM calibration identical to before; `fwhm_from_widths` with the lines used and the proposed energy calibration gives the proposal's FWHM calibration (relative 1e-9); after excluding the line with the largest width residual and refitting the energy calibration as the dialog does, the FWHM calibration does not contain that line and differs from the proposal |
| RD.C2 | widths (channel, FWHM channels) with E = 0.5 keV/ch over channels 0-8191: Gemini's falling pair; a rising pair (200, 2.0), (3000, 3.2); four widths rising over the lines whose quadratic is negative at both ends | Gemini's pair: no FWHM calibration and a note containing "decreas"; rising pair: coefficients as before; four widths: order 1, positive over 0-8191 |
| RD.C3 | source calibrations of 10 IAEA 2002 test spectra (nuclides as in the IAEA harness) and 10 synthetic benchmark sources (HPGe Eu-152, NaI Am-241 + Cs-137 + Co-60, 5 each) | energy calibration identical; FWHM calibration identical, except where the old one was not positive somewhere in the channel range |
| RD.C4 | synthetic Poisson sample (1024 channels, peak of 1000 counts on 50/channel, LT 1000 s) and background (peak of 400 on 80/channel, LT 2000 s): background subtracted (k = 0.5), and Aptec Strip of the background normalized by 0.5; manual fit of channels 480-520 with one peak at 500 | the variance the manual-fit window passes equals S + k^2 B (relative 1e-9) and its fit equals the fit with that explicit variance (area and uncertainty, relative 1e-9), without the not-Poisson note, for both; after Smooth, or after one channel is changed by hand, no variance is passed; the raw sample is fitted exactly as before |
| RD.C5 | GUI tests and the existing tests and benchmark | the calibration dialog applies the FWHM calibration recomputed after an exclusion and restores the proposal's when the line is used again; the fit-inspection window passes the variance of a net spectrum to the session; full test suite passes; benchmark PASS/FAIL counts unchanged (154 / 13) |

## Outputs

`docs/baseline/after_R4D/round4_calibration.md` and `.json`, from
`python -m spectramaster.validation.round4_calibration`.

## Limitations

- The variance is not saved with a spectrum file or a session; a reopened net spectrum keeps the
  not-Poisson note.
- RD.C1 checks the engine functions the dialog calls; the dialog itself is checked by the GUI tests
  of RD.C5.

---

## Results (after_R4D)

**First run: 4 PASS / 0 FAIL** (`after_R4D/round4_calibration.md`), engine 1.18.0:

| ID | result | key numbers |
|---|---|---|
| RD.C1 | PASS | 3 Eu-152 spectra: the refit without exclusion gives the proposal's FWHM calibration; after excluding the line with the largest width residual (Eu-152 1112.08, 1112.08, 1085.84 keV) the FWHM calibration is fitted through the 6 or 7 remaining widths and differs from the proposal |
| RD.C2 | PASS | Gemini's pair: no FWHM calibration, note "decrease with energy ... 6.389 keV at channel 0, -25.47 keV at channel 8191" (before: FWHM = 6.389 - 0.00389 ch accepted); rising pair unchanged; four widths: order 1, 0.25 to 6.80 keV over 0-8191 (before: order 2, -1.43 to 2.51 keV) |
| RD.C3 | PASS | 20 source calibrations (10 IAEA 2002 test spectra, 10 synthetic): energy and FWHM calibrations identical, no change |
| RD.C4 | PASS | net spectrum: manual fit u 59.147, the same as with the explicit variance S + k^2 B (before: 83.188 with the not-Poisson note, the region clipped); Aptec Strip of the normalized background: u 59.147; after Smooth or a channel edited by hand no variance is passed; raw spectrum fitted as before |
| RD.C5 | PASS | GUI tests: the calibration dialog applies the FWHM calibration recomputed after an exclusion and the proposal's when the line is used again; the fit-inspection window passes the variance of a net spectrum (edit recorded with `variance: explicit`) and none for a raw spectrum. Full suite 1464 passed, 69 skipped; benchmark 154 PASS / 13 FAIL / 60 REPORT, no criterion changed status (`after_R4D/baseline.md`) |

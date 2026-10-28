# Round-5 review: detector acceptance test and activity entry (pre-registered)

Written 2026-10-28, before any change to the code. Codex round-5 review
(`D:\DSpectraMaster_reviews\codex_review_round5.md`, main 865c1ec) reported five findings on the work
of PR #75. Each was checked on the code before this protocol was written.

| ID | finding | checked |
|---|---|---|
| H2 | `detector_test.peak_width` gives the local centroid of the ROI to `Spectrum.energy_of` and `_kev_per_channel`, which take the absolute channel. With `first_channel` != 0 the centroid energy is wrong (832.5 instead of 1332.5 keV with 1000 channels cut, linear 0.5 keV/channel) and, with a non-linear calibration, the widths too | reproduced |
| M3 | `peak_to_compton` uses whatever channels of 1040-1096 keV the spectrum has; a spectrum covering only part of the window gives a P/C from that part, without a note | code |
| H3 | QC reference activity: `qc_window._parse_activity` splits at every comma before reading the number, so `Cs-137=1,000 Bq` gives 1 Bq; parts without `=` are dropped | reproduced |
| M2 | `activity_input.parse_activity` removes every comma (`1,5 Bq` gives 15) and accepts an overflow (`1e309` gives inf); `detector_test.relative_efficiency` does not check that the activity and the live time are finite | reproduced |
| M1 | efficiency certificate table: changing the unit rewrites each activity from its 6-significant-digit text, so 12345.678 Bq becomes 12345.7 Bq after Bq -> Ci -> Bq | code |

## Changes (fixed now)

1. **H2.** `peak_width` evaluates the energy and the keV per channel at `first_channel + centroid`.
   The ROI, the net counts and the widths in channels are unchanged.
2. **M3.** `peak_to_compton` returns None when the energies of the spectrum do not reach both
   1040 and 1096 keV; `acceptance_test` adds the note "the 1040-1096 keV Compton window is not fully
   inside the spectrum".
3. **H3.** The QC text is split into records at a semicolon, a new line, or a comma followed by a
   nuclide name and `=` (e.g. `Cs-137=37000, Co-60=1 uCi`). Each record must be `nuclide=activity`;
   a record without `=` or with an activity that cannot be read is an error shown to the user, not
   dropped.
4. **M2.** `parse_activity` refuses a comma inside the number (thousands separator or decimal comma:
   ambiguous) and a value that is not finite. `relative_efficiency` refuses an activity, an activity
   uncertainty or a live time that is not finite. `ActivityInput.value_bq` returns 0 for a text that
   is not a finite number (as for an empty field).
5. **M1.** Each activity cell of the certificate table keeps its value in Bq. A unit change rewrites
   the text from that value. Editing the text stores the new value (text x unit). `certificate()`
   uses the stored Bq when the text was not edited.

Engine version 1.22.0 (detector test results change for spectra with `first_channel` != 0).
Harness `validation/round5_acceptance.py`, fixed output folder `after_R5B`.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RB.C1 | spectra of the DA harness (Gaussian 1332.5 keV, FWHM 2.0 keV, area 1e5, continuum 120 - 0.01 i) with calibrations [0, 0.5] and [0, 0.3, 5e-5] keV; the same counts cut by 1000 channels with `first_channel` = 1000 | centroid, FWHM, FWTM, FWTM/FWHM and P/C of the cut spectrum equal those of the full spectrum to relative 1e-9 |
| RB.C2 | the full spectra of RB.C1 and the DA harness | `peak_width` and `peak_to_compton` equal the values before the change (commit 865c1ec) to relative 1e-12; DA.C1-C7 values equal `after_DA2` |
| RB.C3 | P/C of the linear spectrum cut so that it starts at 1060 keV (and at 1030 keV) | None with the note (and, from 1030 keV, equal to the full spectrum) |
| RB.C4 | QC text | `Cs-137=37000` -> 37000; `Cs-137=37000, Co-60=1 uCi` -> 37000 and 37000; `Cs-137=1 µCi; Co-60=2 kBq` -> 37000 and 2000; `Cs-137=1,000 Bq`, `Cs-137=1,5 Bq`, `Cs-137=1e309`, `Cs-137=abc`, `Cs-137` -> error |
| RB.C5 | `parse_activity` | `1,000`, `1,5 Bq`, `1e309`, `nan`, `inf` refused; `37 kBq`, `1uCi`, `1 µCi`, `.5e3`, `-2 Bq` read as before; `relative_efficiency` with inf or NaN activity, or inf live time, raises ValueError |
| RB.C6 | certificate table, 12345.678 +- 246.91356 Bq, unit Bq -> Ci -> µCi -> Bq; then the text edited to 2 in kBq | `certificate()` gives exactly 12345.678 and 246.91356 Bq; after the edit 2000 Bq |
| RB.C7 | benchmark and tests | benchmark PASS / FAIL / REPORT states as `after_EB1` (154 / 13 / 60); full suite passes |

## Outputs

`docs/baseline/after_R5B/round5_acceptance.md` and `.json`; `after_R5B/baseline.md` and `.json`.

## Limitations

- Synthetic spectra only, as in `detector_acceptance_protocol.md`.
- The decimal comma is refused, not read: a user typing `1,5` gets an error and must type `1.5`.

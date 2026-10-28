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

---

## Results (`after_R5B`)

Protocol committed in f0f7f1d before the change (SHA-256 of the file
6e4319459bae11a48ce44645353da0a6752d63fd8d85d9d17ca29b9b6bb9d386). Engine 1.22.0.

**First run: 4 PASS / 2 FAIL, from a harness error.** The harness built its peak at `CO60_1332`
(1332.492 keV), while the values "before" (commit 865c1ec, recorded before the change) were taken
with a peak at 1332.5 keV, as the protocol states. RB.C2 then compared two different spectra
(largest difference 0.00155) and RB.C1 came out at 1.0e-9. The engine was not the cause: the script
that recorded "before", run on the changed code, gives the recorded values bit for bit. The harness
now builds the peak at 1332.5 keV (`PEAK_KEV`).

**Corrected run: 6 PASS / 0 FAIL, and RB.C7 PASS.**

| ID | value | result |
|---|---|---|
| RB.C1 | cut (first_channel 1000) against full: largest relative difference 9.6e-10 (FWTM/FWHM, quadratic calibration); centroid 1332.5 keV (before the fix 832.5 keV) | PASS |
| RB.C2 | full spectra against 865c1ec: 0; DA.C1-C7 equal to `after_DA2` | PASS |
| RB.C3 | spectrum from 1060 keV: no P/C, with the note; from 1030 keV: equal to the full spectrum (235.6498) | PASS |
| RB.C4 | 8 of 8 QC texts as registered (the five wrong ones refused with a message) | PASS |
| RB.C5 | 5 of 5 texts refused, 5 of 5 read as before; relative efficiency refuses inf / NaN activity and inf live time | PASS |
| RB.C6 | 12345.678 +- 246.91356 Bq after Bq -> Ci -> µCi -> Bq; 2000 Bq after typing 2 in kBq | PASS |
| RB.C7 | benchmark 154 PASS / 13 FAIL / 60 REPORT, no criterion changed state against `after_EB1`; full suite 1490 passed, 69 skipped | PASS |

**Margin of RB.C1.** The differences of 4e-10 to 1e-9 between the cut and the full spectrum come
from the log-parabola fit (`np.polyfit`) on channel numbers near 1665 and 2665: the same
arithmetic at different offsets. They are rounding, not a remaining dependence on `first_channel`;
the margin to the limit is small.

**Changed existing test (reason).** `test_activity_units.py::test_conversion_and_parsing` read
`1,000 Bq` as 1000; a comma in the number is now refused, as registered (change 4).

Also changed: the QC hint and manuals (sections on the QC reference activity): nuclides separated by
`;`, a new line or a comma, a point for decimals, no thousands separator. The number field of
`ActivityInput` uses the C locale and refuses group separators.

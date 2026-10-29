# Round-7 review: input validation, Codex M1 and Gemini M4 (pre-registered)

Written 2026-10-29, before any change to the code. Codex and Gemini round-7 reviews
(`C:\Users\DELL\Downloads\codex_review_round7.md`, `gemini_review_round7.md`, main b3d88d1), findings
Codex M1 and Gemini M4, checked on the code (main 27a54b1). Follows `round6_inputs_protocol.md`
(R6-C), whose rule is kept: a value a calculation cannot use is refused with a message naming it,
never replaced silently; a comma inside a number is ambiguous (decimal or thousands) and is not read.

## Findings (all confirmed on the code)

1. **Manual efficiency points** (`gui/efficiency_dialog.py` `_read_points`, Codex M1, Gemini M4.2).
   An edited energy or efficiency that is not a finite number above 0 (`0,02`, `-0.01`, `nan`) is
   ignored: the point keeps its old value while the cell shows the new text, and the refit and the
   save succeed with the old value. An uncertainty that is not read (`1,5`) silently becomes 2 %; a
   negative one is accepted.
2. **QC monitored lines** (`gui/qc_window.py` `parse_lines`, Gemini M4.1). `inf` or `nan` energies,
   and a maximum FWHM `nan`, `inf`, 0 or negative are accepted; `661,657:Cs-137` is split at the
   comma into two lines (661 keV and 657 keV) without a message.
3. **Certificate CSV** (`analysis/efficiency.py` `read_certificate_csv`, Gemini M4.3). For the
   second and later rows of a nuclide, the activity, uncertainty, reference date and half-life are
   not read (a conflicting or invalid value is ignored); a header with an unknown column (e.g.
   `uncertainty_pct`) or without an uncertainty column gives an uncertainty of 0; an intensity
   above 100 % is accepted; an energy without intensity (or the reverse) is dropped silently.
4. **Aptec source records** (`certificate_from_aptec`, Gemini M4.4). Non-finite energies, yields,
   activities, uncertainties and half-lives are not checked (a NaN activity passes `a <= 0`); a
   negative uncertainty is set to 0; a yield above 1 is accepted.
5. **`ActivityInput.set_bq`** (Gemini M4.5) accepts a negative activity.

## Change

1. `_read_points` reads every manual row first; an energy or efficiency that is not a finite number
   above 0, or an uncertainty (%) that is not a finite number above 0 (empty included), raises a
   ValueError naming the row and column, and nothing is changed. `refit`, `set_point_used`,
   `add_manual_point` show it; the refit fails, the fitted curve is cleared (so it cannot be saved
   from stale values) until the cell is corrected.
2. `parse_lines`: energy finite and > 0, maximum FWHM (when given) finite and > 0; a comma between
   digits (`\d,\d`) is refused as ambiguous (lines are separated by `;`, a new line, or `, `).
3. `read_certificate_csv`: every header name must be known (nuclide, activity_bq | activity,
   unc_percent | unc_% | unc_bq, ref_date, half_life_s, energy_kev, intensity_percent); a header must
   have an uncertainty column; later rows of a nuclide must repeat its activity, uncertainty,
   reference date (as a date) and half-life (relative 1e-9), else ValueError naming the row;
   intensity_percent must be <= 100; energy and intensity are given together or not at all.
4. `certificate_from_aptec`: empty slots (no nuclide, activity or yield 0) are still skipped; a
   record with a non-finite or negative energy, yield, activity or uncertainty, a yield above 1, or a
   non-finite half-life raises ValueError naming the record.
5. `set_bq`: a negative activity raises ValueError; the shown value is kept.

No calculation changes for valid inputs; ENGINE_VERSION is not changed (input layer only).

Harness `validation/round7_inputs.py`, fixed output folder `after_R7E`; observations before the change
recorded with `--collect` into `after_R7E/round7_inputs_before.json` (main 27a54b1), committed with
this protocol.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RE.C1 | 14 invalid manual-point cells (efficiency `0,02` `-0.01` `nan` `0` `abc` empty; energy `inf` `-100` `1,5`; uncertainty `1,5` `-2` `nan` `0` empty), dialog with 5 manual points, log-log | each: refit False, a message naming row 1, no curve, save refused, the cell keeps the text, the point keeps its value; 3 valid edits: observations identical to before |
| RE.C2 | 9 invalid QC line texts, 3 valid | all invalid refused; valid identical to before |
| RE.C3 | 11 invalid certificate files (conflicting / invalid later rows, unknown or missing uncertainty column, intensity > 100, energy or intensity alone), 6 valid (including a file written by the program, a date written in another format) | all invalid refused; valid identical to before |
| RE.C4 | 12 invalid Aptec records next to a valid one; 3 skipped slots; a record without half-life | all invalid refused; valid and skipped identical to before |
| RE.C5 | `set_bq` of -5 and -1e-9; 0, 12345.678, 1e-3 | negative refused and the previous value kept; others identical to before |
| RE.C6 | benchmark (`after_R7D`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes, each changed existing test listed with its reason |

Before the change RE.C1 to RE.C5 fail.

## Limitations

- The checks are the ones named; other fields of these editors are covered by R6-C.
- A comma between digits in a QC line list is refused even where it was meant as a separator
  without a space (`661.657,1332.492`); the message says to use `;` or `, `.

---

## Results (`after_R7E`)

Protocol committed in 5bf16c1 before the change (SHA-256 of the file
c082e227221c3869013b62f3bd42e439156ab0ffa6677620c2c2b8242413f656).

**First run: 4 PASS / 1 FAIL, harness error, disclosed** (kept as `after_R7E/round7_inputs_run1.md`).
RE.C1 looked for "row 1" in the messages case-sensitively; the message says "Row 1, Efficiency: ..."
(every one of the 14 cases was refused, named row 1, fitted and saved nothing). The comparison was
made case-insensitive.

**Second run: 4 PASS / 1 FAIL, harness error, disclosed** (kept as `after_R7E/round7_inputs_run2.md`).
RE.C1 compared the refused point with its value *before the change*; for the 4 cases the old code
accepted (`-0.01`, `-100`, `-2`, `0` uncertainty) that value is the accepted invalid one. The row
"the point keeps its value" means the value it had before the edit (the 5 manual points of the
case); the comparison was corrected to that. No limit was changed.

**Third run: 5 PASS / 0 FAIL.**

| ID | value | result |
|---|---|---|
| RE.C1 | refused with row 1 named, nothing fitted or saved, cell text and point value kept: 14 of 14; 3 valid edits as before | PASS |
| RE.C2 | QC lines refused 9 of 9; 3 valid as before | PASS |
| RE.C3 | certificate CSV refused 11 of 11; 6 valid files as before | PASS |
| RE.C4 | Aptec records refused 12 of 12; valid records and skipped empty slots as before | PASS |
| RE.C5 | negative `set_bq` refused 2 of 2, previous value kept; valid as before | PASS |
| RE.C6 | benchmark 154 PASS / 13 FAIL / 60 REPORT, no criterion changed state against `after_R7D`; full suite 1638 passed, 69 skipped, no existing test changed | PASS |

RE.C6 is evaluated outside the harness. **Disclosed:** the first full-suite run printed
"1638 passed, 69 skipped" and then exited with code 127 (no test failed or errored); the
second full-suite run, unchanged code, printed the same and exited 0, and `tests/test_round7_inputs.py`
alone exited 0 twice. This matches the abnormal end of the Qt test process reported in Codex M2,
which is batch R7-G; it is recorded there.

New tests: `tests/test_round7_inputs.py`. Also changed: the manuals (sources), certificate CSV,
QC monitored lines, manual efficiency points.

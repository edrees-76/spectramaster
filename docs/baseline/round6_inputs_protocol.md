# Round-6 review: input validation (pre-registered)

Written 2026-10-28, before any change to the code. Codex round-6 review
(`C:\Users\DELL\Downloads\codex_review_round6.md`, main 624e199) findings H2 and M1, Gemini round-6
review (`gemini_review_round6.md`) findings H1 and M2. Each was checked on the code (main 6c5933b)
and reproduced by the harness below before this protocol was written.

| ID | finding | before (harness, main 6c5933b) |
|---|---|---|
| Codex H2 | certificate table: after the activity is edited, a unit change brings back the cached absolute uncertainty of the old activity | 1000 +- 20 Bq (2 %), activity edited to 2000: 2000 +- 40; then kBq: 2000 +- **20** |
| Codex M1 / Gemini H1 | certificate table, `_num` of the efficiency dialog: a non-finite or negative activity, uncertainty or half-life is accepted; the comma is turned into a point | activity `1e309` -> inf +- inf; `nan` -> nan; `-5` -> -5; `1,000` -> 1; `0` -> row dropped without a note; half-life `0`, `-3`, `inf`, `nan` kept; lines `661.657:85,1` -> 85 % |
| Gemini H1 | `read_certificate_csv` accepts inf, nan, negative and zero activities, negative uncertainties, non-finite half-lives, energies and intensities | e.g. activity `inf` -> inf +- inf, intensity `-85.1` -> -0.851 |
| Gemini H1 | `measure_efficiency` lets non-finite certificate values through (`a0 <= 0` is false for NaN) | activity NaN -> efficiency NaN, used; activity inf -> efficiency 0, used; negative uncertainty and zero or negative half-life used silently |
| Gemini H1 | `detector_test.net_area`, `peak_to_compton`, `relative_efficiency` do not check the counts | one NaN in the 1332.5 keV ROI -> net area NaN, P/C NaN, relative efficiency NaN (`peak_width` already refuses) |
| Gemini M2 | `parse_counts` (chi-square test) removes every comma and accepts non-finite values | `1,5` -> 15; `1,000` -> 1000; `inf`, `nan`, `1e309` kept |
| Gemini M2 | QC reference activity: a zero or negative activity is accepted; a record split only before a hyphenated nuclide name | `Cs-137=-1000` -> -1000 Bq; `Cs137=37000, Co60=1 uCi` -> error |
| Codex M1 | `ActivityInput.set_bq` keeps a non-finite value | `set_bq(inf)` -> `value_bq()` inf |

## Changes

1. **Certificate table (Codex H2).** A unit change keeps the uncertainty in Bq that the row had before
   the change (the one `certificate()` gave): after an edited activity, that is activity x percentage.
2. **Certificate table and `_num` (Codex M1, Gemini H1).** `_num` of the efficiency dialog no longer
   turns a comma into a point and gives the default for a value that is not finite. `certificate()`
   raises ValueError naming the row and the column when a filled cell of a named row is not
   acceptable: activity not a finite number > 0; uncertainty not a finite number >= 0; half-life not a
   finite number > 0; a line entry that is not `energy:intensity` with both finite and > 0 (a comma
   still separates entries, so `661.657:85,1` leaves `1` without energy: refused). An empty activity
   (row being filled in) is still skipped. Export, measurement and validation show the message.
3. **`read_certificate_csv` (Gemini H1).** The same limits, ValueError naming the CSV row.
4. **`measure_efficiency` (Gemini H1).** A used certificate line whose activity is not finite and
   > 0, whose activity uncertainty is not finite and >= 0, whose intensity or intensity uncertainty is
   not finite (or negative), or whose half-life is given and not finite and > 0, raises ValueError
   naming the nuclide and energy. Valid lines: unchanged.
5. **Detector test (Gemini H1).** `net_area`, `peak_to_compton` and (through `net_area`)
   `relative_efficiency` refuse a spectrum with non-finite counts (`check_finite`, as `peak_width`).
6. **`parse_counts` (Gemini M2).** A comma is refused (ambiguous, as in `parse_activity`), and a
   value that is not finite: error naming the line.
7. **QC reference activity (Gemini M2).** An activity <= 0 is refused. A record is also split at a
   comma followed by any name beginning with a letter and `=`; the nuclide name is written in the
   library spelling (`cs137`, `Cs137` -> `Cs-137`, as the archive search does), which is the key the
   QC line results look up.
8. **`ActivityInput.set_bq` (Codex M1).** A value that is not finite raises ValueError.

Results of valid inputs are unchanged (criteria below), so the engine version stays 1.24.0. The one
behaviour change for valid input is change 7: QC nuclide names typed without the library spelling are
stored in it. Harness `validation/round6_inputs.py`, fixed output folder `after_R6C`; values before
the change recorded with `--collect` into `after_R6C/round6_inputs_before.json` (engine 1.24.0,
6c5933b), committed with this protocol.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RC.C1 | certificate table, Codex H2 sequence; the round-5 round trip 12345.678 +- 246.91356 Bq through Ci, µCi, Bq | after the edit 2000 +- 40 Bq and after kBq exactly 2000 +- 40; round trip exact |
| RC.C2 | certificate table, the 20 invalid cells of the harness (`CERT_BAD`); a typed valid Co-60 row | every invalid cell raises ValueError; the valid row identical to before |
| RC.C3 | certificate CSV, the 12 invalid rows of the harness; a valid two-nuclide file | each invalid row raises ValueError; the valid file identical to before |
| RC.C4 | `measure_efficiency` on a synthetic Cs-137 spectrum (seed 20261028), the 10 invalid lines of the harness; the valid line | each invalid line raises ValueError; the valid point identical to before (energy, efficiency, uncertainty, use, note) |
| RC.C5 | detector test, a NaN in the 1332.5 keV ROI, a NaN in the Compton window, an inf in the ROI; the clean spectrum | `peak_width`, `peak_to_compton`, `net_area`, `relative_efficiency` all raise ValueError; clean values identical to before |
| RC.C6 | `parse_counts`: `1,5`, `1,000`, `inf`, `nan`, `1e309`; a valid text | each refused; the valid text read as before |
| RC.C7 | QC: `Cs-137=-1000`, `Cs-137=0`, `Cs-137=-1 uCi`; five valid texts incl. `Cs137=37000, Co60=1 uCi` and `cs137=37000; Am241=500`; the round-5 refusals | invalid refused; the five read as listed in the harness (library spelling); round-5 refusals still refused |
| RC.C8 | `set_bq(inf)`, `set_bq(nan)`, `set_bq(-inf)`; `set_bq(12345.678)`, `set_bq(0)` | non-finite raise ValueError; 12345.678 exact; 0 as before |
| RC.C9 | benchmark (`after_R6B`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes, each changed existing test listed with its reason |

Before the change: RC.C1-C8 fail (except the parts measured as controls).

## Limitations

- The decimal comma is refused, not read, as in round 5: the user types a point.
- The common uncertainty field of the efficiency dialog (a percentage below 100, already checked for
  range and finiteness) keeps reading a comma as a decimal point; it is not changed here.

---

## Results (`after_R6C`)

Protocol committed in 2f14de2 before the change (SHA-256 of the file
cf9ad35fcc41a982c8b279d72b4d9650c33b30b0b05c2a9e676de03c9977cc1e). Engine 1.24.0 (unchanged).

**First run: 5 PASS / 3 FAIL, a harness error.** RC.C2, RC.C3 and RC.C5 compared the values just
measured (Python tuples) with the before file (JSON lists), so equal values compared unequal. The
harness now passes the measured values through JSON before comparing; no value and no limit changed.
The first run's report is kept as `after_R6C/round6_inputs_run1.md`.

**Second run: 8 PASS / 0 FAIL.**

| ID | value | result |
|---|---|---|
| RC.C1 | edited 2000 +- 40 Bq; after kBq 2000 +- 40 (before: +- 20); round trip 12345.678 +- 246.91356 exact | PASS |
| RC.C2 | 20 of 20 invalid cells refused with the row and column; the typed Co-60 row as before | PASS |
| RC.C3 | 12 of 12 invalid CSV rows refused with the row; the valid file as before | PASS |
| RC.C4 | 10 of 10 invalid certificate lines refused; the valid point identical to before | PASS |
| RC.C5 | NaN / inf in the ROI or the Compton window: the four functions refuse; clean values identical | PASS |
| RC.C6 | 5 of 5 counts texts refused; the valid text as before | PASS |
| RC.C7 | 3 of 3 refused; 5 of 5 read in the library spelling; round-5 refusals kept | PASS |
| RC.C8 | `set_bq` of inf, NaN, -inf refused; 12345.678 exact; 0 as before | PASS |
| RC.C9 | benchmark 154 PASS / 13 FAIL / 60 REPORT, no criterion changed state against `after_R6B`; full suite 1568 passed, 69 skipped; no existing test changed | PASS |

**Consequence not named in the protocol.** The efficiency points table of the wizard reads a manual
point's energy, efficiency and uncertainty with the same `_num`: a value typed with a decimal comma
(`0,005`) was read as 0.005 and is now not read, so the point keeps its previous values. No result of
a valid (point-decimal) entry changes.

Also changed: the manuals (sources), efficiency certificate step, chi-square counting test and QC
reference activity.

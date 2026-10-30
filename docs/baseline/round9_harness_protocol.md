# Round-9 review: re-run reliability of the round-7 and round-8 harnesses, Codex M3 / M4, Gemini M1 (pre-registered)

Written 2026-10-30, before any change to the code. Codex round-9 review
(`C:\Users\DELL\Downloads\codex_review_round9.md`, main 5de3b03) findings M3 and M4, Gemini round-9
review (`gemini_review_round9.md`) finding M1, checked on the code (main 5de3b03) and measured before
this protocol was written. Harness code only: the analysis engine is not changed, ENGINE_VERSION
stays 1.34.0, no committed `after_*` file is changed.

## Findings

1. **`round8_rerun` accepts a stale artifact (Codex M3, confirmed).** `_run` keeps a harness's exit
   code but `_at_commit` and `collect` read the harness's Markdown whatever the exit; in the temporary
   worktree that file is the committed one, so a run that fails before writing (exit 99, import error)
   reports the committed states and RG8.C2 / RG8.C3 pass. Measured: `_run` replaced by one that
   returns exit 99 without running, harness `round7_inputs`: see "Before" below.
2. **`round7_quad_limits` drops the window coefficients (Codex M4, confirmed).** Its Ba-133 mean
   recombination copies each quadratic line with `dataclasses.replace`, which keeps the dataclass
   fields only; the in-memory window coefficients `_cov_res` / `_ref_vec` added by engine 1.34.0
   (round8_line_covariance_protocol.md) are lost, so `combined_limits` on the copies misses the
   cross terms the engine adds. On the current engine (`--rerun`, engine 1.34.0): RD.C2 FAIL (Currie
   nuclide 5.743 / 11.52 Bq against recombined 6.572 / 13.17 Bq; ISO 11929 likewise) and RD.C3 FAIL
   (Ba-133 mean `primary_u` 4.8228 -> 4.4875 Bq, the intended change of 1.34.0).
3. **The round-8 harnesses compare with exact JSON text (Gemini M1, confirmed).** `_same` in
   `round8_alt_limits`, `round8_peak_mode` and `round8_coi_guard` is `json.dumps(a) == json.dumps(b)`:
   a last-bit difference of a float (another platform or library build) fails a control. Measured,
   current results against the committed before values with every float scaled by (1 + 1e-13):
   RA8.C1, RA8.C3, RA8.C4, RB8.C2, RB8.C3a and RC8.C4 fail (all pass as is). The `engine` field is not
   compared by any criterion (changing it alters no result).

## Change

1. `round8_rerun`: before each harness run (current code and every temporary worktree) the harness's
   own Markdown output is removed; a run counts only with exit 0 or 1 *and* a Markdown file written by
   it, otherwise its states are empty and its error recorded (exit, last stderr lines). RG8.C2 and
   RG8.C3 already fail on empty states; a later-commit step with an error assigns nothing.
2. `round7_quad_limits`: the copies keep the line's in-memory attributes (`_cov_res`, `_ref_vec`), so
   the recombination is the engine's. RD.C3 excepts the Ba-133 mean nuclide's `primary_u` when the
   engine is 1.34.0 or later (the intended change of round8_line_covariance_protocol.md, checked by
   that protocol's criteria) and reports its value; everything else unchanged.
3. New `validation/compare.py` `same(a, b, rel=1e-12)`: nested dicts (same keys), lists (same length),
   numbers equal within relative 1e-12 (`math.isclose`, `abs_tol` 0; NaN equals NaN), other values
   equal. `_same` of the three round-8 harnesses uses it. The tolerance is the one the other harnesses
   register for "identical" numbers (round8_line_covariance, round9_legacy_tcs); it is a widening from
   bit identity and is stated here as such.
4. Committed results (`after_R7D`, `after_R8A`, `after_R8B`, `after_R8B2`, `after_R8C`, `after_R8G`)
   stay as committed; the historical FAILs and the RD.C2 / RD.C3 FAIL of the current engine before this
   change remain recorded in this protocol.

Evidence: tests `tests/test_round9_harness.py` and `--rerun` runs (temporary folders); results below
the line. Fixed output folder `docs/baseline/after_R9E` for the copies of the re-run results.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RE9.C1 | `round8_rerun` with `_run` returning exit 99 without running (`round7_inputs`, committed Markdown present) | no states read; RG8.C2 and RG8.C3 FAIL; the error recorded |
| RE9.C2 | `round7_quad_limits --rerun`, current engine | 4 PASS / 0 FAIL: RD.C2 nuclide limits equal the recombined ones (1e-9); RD.C3 with the Ba-133 `primary_u` exception only; `after_R7D` byte-identical |
| RE9.C3 | the three round-8 harnesses against their before values scaled by (1 + 1e-13) | every criterion as unscaled; scaled by (1 + 1e-9): the controls named in finding 3 still FAIL |
| RE9.C4 | `--rerun` of `round8_alt_limits`, `round8_peak_mode` (`--amendment`), `round8_coi_guard` | 4/0, 4/0, 4/0 as before; committed folders byte-identical |
| RE9.C5 | `round8_rerun --rerun` on this branch | RG8.C1-C3 PASS; the round7_quad_limits states equal the historical ones; every other change assigned |
| RE9.C6 | full test suite | passes and exits 0; each changed existing test listed with its reason |

Before the change: RE9.C1, RE9.C2 and RE9.C3 fail; RE9.C4 is the control.

## Before (main 5de3b03, engine 1.34.0; `after_R9E/round9_harness_before.json`)

- Codex M3, `_run` returning exit 99 without running, `round7_inputs`: current and historical states
  RE.C1-C5 all PASS read from the files present; RG8.C1, RG8.C2 and RG8.C3 PASS.
- Codex M4: `round7_quad_limits --rerun` 2 PASS / 2 FAIL (RD.C2, RD.C3).
- Gemini M1, before values scaled by (1 + 1e-13): RA8.C1, RA8.C3, RA8.C4, RB8.C2, RB8.C3a, RC8.C4 FAIL;
  as is all PASS; the engine field changed: all PASS.
- `round8_alt_limits --rerun` 4/0, `round8_peak_mode --rerun --amendment` 4/0, `round8_coi_guard --rerun`
  4/0.
- `round8_rerun --rerun` (`after_R9E/round8_rerun_before.md`): 3 PASS / 0 FAIL; round7_quad_limits
  RD.C2 and RD.C3 PASS -> FAIL from 5de3b03, round7_combined RB.C2 / RB.C5 from 3cd2aa7 and RB.C3 from
  5de3b03 (the latter predicted by round8_line_covariance_protocol.md).

## Limitations

- The tolerance applies to the three round-8 harnesses named by Gemini M1; the round-7 harnesses keep
  their registered comparisons (R8-G re-ran them on this platform).
- A harness that exits 1 with a fresh file is a measured result (some criteria FAIL), not an error.

---

## Results

First run (this commit, engine 1.34.0; outputs in `after_R9E`): RE9.C1, RE9.C2 and RE9.C4 PASS, RE9.C3
FAIL; RE9.C5 and RE9.C6 not yet run (they are run once, on the code after the amendment below).

| ID | result |
|---|---|
| RE9.C1 | PASS (`tests/test_round9_harness.py::test_rerun_ignores_a_stale_artifact`): with exit 99 and a stale results file, no states read, error "exit 99" recorded, RG8.C2 and RG8.C3 FAIL |
| RE9.C2 | PASS: `round7_quad_limits --rerun` 4 PASS / 0 FAIL; Ba-133 mean limits equal the recombined ones (Currie 5.743 / 11.52 Bq, ISO 11929 5.743 / 16.22 Bq); RD.C3 excepts only the Ba-133 mean `primary_u` 4.8228 -> 4.4875 Bq (both methods); `after_R7D` unchanged |
| RE9.C3 | FAIL: scaled by (1 + 1e-13) RA8.C1 still fails (`round9_harness_scaled.txt`); RA8.C3, RA8.C4, RB8.C2, RB8.C3a and RC8.C4 now pass, and scaled by (1 + 1e-9) they fail as required. RA8.C1 compares the nuclide's `key_energy`, `primary` and `primary_u` with the before values by `==`, not through `_same`, so the registered change does not reach it |
| RE9.C4 | PASS: `round8_alt_limits` 4/0, `round8_peak_mode --amendment` 4/0, `round8_coi_guard` 4/0; committed folders unchanged |

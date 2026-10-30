# Round-8 review: re-runs of the round-7 harnesses, historical and on the current engine, Codex M6 / Gemini M2 (pre-registered)

Written 2026-10-30, before any change to the code and before any re-run. Codex round-8 review M6 and
Gemini round-8 review M2 (main 384e89d), checked on the code (`validation/round7_*.py`, main
dbfb5b5).

## Finding

**A round-7 harness re-run on a later engine compares that engine with values frozen before its
own batch, and writes over the committed results (Codex M6, Gemini M2, confirmed).** Each
`validation/round7_*.py` evaluates its criteria against its `before.json`, recorded before its
batch's change. Later intended changes (for example R7-C, `round7_shared_background_protocol.md`,
which adds the blank's counting term to sigma0) change values that an earlier harness requires
"identical to before", so its re-run on the current engine fails although its own fix holds; Codex
reports `round7_combined` 3 PASS / 2 FAIL on 384e89d. The harnesses have no option to write
elsewhere, so a re-run overwrites `docs/baseline/after_R7x`, the record of the run that the
protocol's results cite. (`round6_inputs` has `--out` since R7-G; the round-8 harnesses have
`--rerun`.)

## Change

1. `validation/round7_tcs_refit.py`, `round7_combined.py`, `round7_shared_background.py`,
   `round7_quad_limits.py`, `round7_inputs.py`: an option `--rerun` writes the results to a fixed
   folder in the temporary directory (`spectramaster_<harness>`), not to `after_R7x`. Without it
   they behave as before. A results path is not taken from the command line (SonarCloud
   pythonsecurity:S8707, as in `round8_alt_limits_protocol.md`); this replaces the `--out` option
   the review suggested.
2. New `validation/round8_rerun.py`: for each of the five harnesses, (a) its committed results;
   (b) a historical run at the merge commit of its batch (R7-A 1d610ac, R7-B 0b95938, R7-C 3cd2aa7,
   R7-D 27a54b1, R7-E 2469fda) in a temporary git worktree, the harness as it was then; (c) a run on
   the current code with `--rerun`; (d) for every criterion whose state in (c) differs from (b),
   runs at the later merge commits of main (first parent, in order) until the first one at which
   it differs, to which the change is assigned. Results to `after_R8G`. The committed `after_R7x`
   folders, the `before.json` files and the protocols are not changed.
3. No change to the analysis code; ENGINE_VERSION unchanged.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RG8.C1 | the files of every `after_R7x` folder | byte-identical (SHA-256) before and after the `--rerun` runs |
| RG8.C2 | historical runs | each harness at its merge commit gives the PASS / FAIL of every criterion as committed in its results |
| RG8.C3 | runs on the current code | every harness runs and gives a state for every criterion; every state that differs from the historical run is assigned to a later merge commit |
| RG8.C4 | benchmark (`after_R8B2`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes and exits 0; each changed existing test listed with its reason |

No limit of a round-7 criterion is changed; a criterion that fails on the current code stays
failed in this record, with the merge commit that changes it. Whether that change is the intended
one of the assigned batch is stated in the results by reading that batch's protocol.

## Limitations

- The assignment names the first merge commit at which a state changes, not the line of code.
- Historical runs use today's Python, NumPy, SciPy and SpecUtils; a difference from the committed
  results caused by them is reported as an RG8.C2 failure, not corrected.
- `round6_inputs` and the round-8 harnesses are not re-run here (they already write elsewhere).

---

## Results (2026-10-30, HEAD 3e75c89, engine 1.32.0)

`py -B -m spectramaster.validation.round8_rerun` (exit 0), results in `after_R8G/round8_rerun.{json,md}`.

| ID | value | result |
|---|---|---|
| RG8.C1 | every committed after_R7x file byte-identical after the --rerun runs | PASS |
| RG8.C2 | round7_tcs_refit at 1d610ac 6 / 0; round7_combined at 0b95938 5 / 0; round7_shared_background at 3cd2aa7 4 / 1; round7_quad_limits at 27a54b1 4 / 0; round7_inputs at 2469fda 5 / 0 (PASS / FAIL), each as committed (the round7_shared_background FAIL is RC.C3, disclosed in its protocol) | PASS |
| RG8.C3 | current code: round7_tcs_refit 6 / 0, round7_combined 3 / 2, round7_shared_background 4 / 1, round7_quad_limits 4 / 0, round7_inputs 5 / 0; changed states RB.C2 and RB.C5 of round7_combined (PASS -> FAIL), both assigned to 3cd2aa7 (PR #95, R7-C) | PASS |
| RG8.C4 | benchmark `after_R8G` 154 PASS / 13 FAIL / 60 REPORT, no criterion changed from `after_R8B2`; full suite 1752 passed, 69 skipped, exit 0; no existing test changed | PASS |

**4 PASS / 0 FAIL.**

Reading of the assigned changes (round7_shared_background_protocol.md, change 3): R7-C adds to
sigma0 of every line with a blank the sample's own counting of the blank level
(`var0 += max(blank_activity, 0) fwin / w`), which that protocol states "alters the limits of every
blank case, by design" and lists the round-4 / round-5 tests it changed for it. RB.C2 (Currie blank
cases identical to the 1.27.0 before-file) and RB.C5 (controls identical) compare blank cases with
the values before R7-C: the failing entries are exactly the cases with a blank (blank_1173_rate_currie,
blank_1332_currie; r5_ba133_iso_blank, r6_co60_ref_blank_iso, r6_co60_ref_blank_currie,
r6_co60_ref_blank_rate_iso), e.g. blank_1332_currie threshold 6.551868 -> 6.568151 Bq, and the
engine still equals RB.C1's independent full-covariance computation in that case (6.568151 Bq both).
The change is therefore the intended one of R7-C, not a regression; the round-7 records stay as
committed, and these two states stay failed on the current code against R7-B's before-file.
(The line field `ref_g0` of a line without a blank peak, `None` in the 1.27.0 before-file and zeros
now, is R7-B's own change; RB.C2 does not compare line fields.)

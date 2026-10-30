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

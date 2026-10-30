# Round-9 review, Gemini M1: amendment of the change for RA8.C1 (pre-registered)

Written 2026-10-30, after the first run (`round9_harness_protocol.md`, e7ffcd0: RE9.C3 FAIL) and
before any re-run. Amends `round9_harness_protocol.md`; that protocol, its before values and the
first run's results stay as committed.

## Reason

Change 3 replaced `_same` of the three round-8 harnesses. RA8.C1 of `round8_alt_limits` compares the
nuclide's `key_energy`, `primary` and `primary_u` with the before values by `==` directly, not
through `_same`, so a last-bit difference of those floats still fails it (first run: RA8.C1 FAIL at a
scale of 1 + 1e-13). Gemini M1 names RA8.C1 among the affected controls.

## Amended change

3a. In RA8.C1 the three comparisons with the before values (`key_energy`, `primary`, `primary_u`) use
`_same`. The comparisons within the current run (the nuclide's limits equal to the substituted line's)
stay exact. Nothing else changes.

## Criteria

RE9.C3a: as RE9.C3 (every criterion of the three harnesses as unscaled at a scale of 1 + 1e-13; the
named controls, RA8.C1 included, FAIL at 1 + 1e-9). RE9.C1, RE9.C2 and RE9.C4 are re-checked on the
amended code; RE9.C5 and RE9.C6 are run on it for the first time. Outputs to `after_R9E2`.

---

## Results

Amended code (6c4ea7b; RE9.C5 and RE9.C6 on d47fb31, the branch with main 091736d merged, engine
1.35.0); outputs in `after_R9E2`. **6 PASS / 0 FAIL.**

| ID | result |
|---|---|
| RE9.C1 | PASS (test `test_rerun_ignores_a_stale_artifact`) |
| RE9.C2 | PASS: `round7_quad_limits --rerun` 4/0, RD.C3 excepting the Ba-133 mean `primary_u` only |
| RE9.C3a | PASS: scaled by (1 + 1e-13) every criterion of the three harnesses as unscaled; scaled by (1 + 1e-9) RA8.C1, RA8.C3, RA8.C4, RB8.C2, RB8.C3a and RC8.C4 FAIL (`round9_harness_scaled.txt`) |
| RE9.C4 | PASS: 4/0, 4/0 (`--amendment`), 4/0; committed folders unchanged |
| RE9.C5 | PASS: `round8_rerun --rerun` 3 PASS / 0 FAIL; round7_quad_limits 4/0 at d47fb31, equal to the historical states; round7_combined RB.C2 / RB.C5 from 3cd2aa7 and RB.C3 from 5de3b03 as before |
| RE9.C6 | PASS: full suite 1774 passed, 69 skipped, exit 0; no existing test changed (new `tests/test_round9_harness.py`, 7 tests) |

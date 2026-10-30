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

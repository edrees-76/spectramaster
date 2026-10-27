# Round-4 review, validation and documentation findings (R4-F): evaluation protocol (pre-registered)

Written 2026-10-27, **before** the changes below were made and before the new comparisons were run.
The findings come from the fourth external review (Codex, the Monte Carlo check of the coincidence
table; Gemini, the wording of `ensdf_coincidence_protocol.md`) and from the project record (the
progress file has no record of the third review round). They were checked on the code first. The
limits must not be changed after results are known. A result outside a limit is reported as a
failure.

## Findings and changes

1. **The Monte Carlo check tests one direction only (Codex).** `validation/coincidence_ensdf_check.py`
   compares the table's P(j | i) for j **below** i in the cascade (`after[i, j]`) with the simulation.
   The correction uses `Transition.coincident`, which adds the upward probability
   P(i | j) = I_i P(j | i) / I_j, built from the table's emission intensities. That term was never
   compared with the simulation, so an error in the intensities of the table (for example an
   intensity balance that does not hold at a level) would not be seen. Change, check only (no engine
   or table change):
   * **Upward rows.** For every compared table line pair (a above b), the simulation's
     P(a | b) = n(a then b) / n(b) is compared with the table's I_a P(b | a) / I_b.
   * **Two-way rows.** For every ordered pair of compared lines (i, j), the simulation's
     (n(i then j) + n(j then i)) / n(i) is compared with `Transition.coincident[i, j]` built from
     the record exactly as `analysis.coincidence.transitions` builds it. This is the quantity
     `coi()` uses.
   * Same lines (>= 0.005 per decay of the mode), same threshold (table or simulation >= 0.01), same
     limit max(0.005, 4 sigma) with sigma = sqrt(p (1 - p) / n) of the conditioning line, same
     simulation (18 nuclides, 200000 decays per mode, seed 12345) as the existing downward rows.
     The new comparisons draw no random numbers, so the existing rows are reproduced exactly.
   * `--out DIR` selects the output folder (default unchanged, `docs/baseline/after_CT1`).
2. **The coincidence protocol says "every transition is checked against an independent simulation"
   (Gemini).** The Monte Carlo covers 18 nuclides (20 decay modes), not the 191 transitions of the
   table. The text above the result line of `ensdf_coincidence_protocol.md` is fixed by its
   SHA-256 and the result text is a record, so neither is edited; a dated correction is appended at
   the end of that file stating what was checked.
3. **The progress file has no record of the third review round.** PRs #36–#67 (2026-10-21/22) are
   listed only in the git history. Change: one section in `docs/SpectraMaster_Progress.md` with each
   PR, its subject and its registered result.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RF.C1 | downward rows (pairs and annihilation) of the new run | identical to `after_CT1/coincidence_check.json` (every field, 237 comparisons, 0 failed) |
| RF.C2 | upward rows, 18 nuclides | every row within max(0.005, 4 sigma); z values (diff / sigma, rows with sigma > 0): rms <= 1.3 |
| RF.C3 | two-way rows (`Transition.coincident`), 18 nuclides | every row within max(0.005, 4 sigma) |
| RF.C4 | documents and tests | correction appended to `ensdf_coincidence_protocol.md` without changing any earlier line; round-3 record in the progress file; new unit tests of the upward and two-way comparison on a hand-made scheme pass; full test suite passes; benchmark PASS/FAIL counts unchanged (154 / 13) |

## Outputs

`docs/baseline/after_R4F/coincidence_check.md` and `.json`, from
`python -m spectramaster.validation.coincidence_ensdf_check --out docs/baseline/after_R4F`
(derived numbers only; the LiveChart files stay outside the repository), and
`docs/baseline/after_R4F/baseline.md` and `.json`.

## Limitations

- The simulation reads the same ENSDF rows as the table builder. An error in ENSDF itself is not
  detected; only the builder's arithmetic and the table's consistency are checked.
- Nuclides outside the 18 of the Monte Carlo set are checked only through the library coverage
  count (CT.C3), as before.

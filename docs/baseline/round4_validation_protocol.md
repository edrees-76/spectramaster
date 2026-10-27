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

---

## Results (after_R4F)

Run 2026-10-27, engine 1.18.0. The text above the line is unchanged (SHA-256 of the registered file
77645f0011f39131c5ea361bc450464e49bc121c6b366dcc2ce94588285276bf, commit 49b4f96).

**First run: 2 PASS / 2 FAIL** (`after_R4F/coincidence_check.md`):

| ID | result | key numbers |
|---|---|---|
| RF.C1 | PASS | downward rows identical to after_CT1 (237 compared, 0 failed, largest 0.0242) |
| RF.C2 | **FAIL** | 215 upward rows, 13 outside the limit, largest \|diff\| 0.0947; rms of z 3.39 (limit 1.3) |
| RF.C3 | **FAIL** | 448 two-way rows, the same 13 outside (the downward part agrees) |
| RF.C4 | PASS | correction appended to `ensdf_coincidence_protocol.md` (8 lines added, none changed); round-3 record in the progress file; new test `test_check_compares_upward_and_two_way_probabilities` passes; full suite 1468 passed, 69 skipped; benchmark 154 PASS / 13 FAIL / 60 REPORT, no criterion changed status (`after_R4F/baseline.md`) |

**Cause of the failures, checked after the run.** The failures are not errors of the check
or of the builder's arithmetic. They come from ENSDF level schemes whose intensity balance does not
close. The table's upward probability uses the listed intensity I_j. The simulation uses the
emission rate that its cascade walk gives. At a level whose listed inflow exceeds its listed
outflow, the walk sends the excess through the listed gammas:

* **Ac-228 (10 rows).** The 674.75 keV gamma (2.1 %) feeds the 968.3 keV level, whose listed
  outflow is 0.22 %. The 214.85 keV gamma (0.76 %) feeds the 938.6 keV level, whose outflow is
  0.03 %. The excess reaches the 328.0 keV level. In the simulation the 270.2, 328.0, 338.3 and
  209.3 keV lines come out 9-17 % above their listed intensities, while the 794.9, 911.2 and
  969.0 keV lines agree within 3 %.
* **Co-57 (1 row).** The 14.4 keV level receives 4 % more than it emits. The table's
  P(122.1 | 14.4) is 1.018, a probability above 1; the builder drops a pair only above
  REVERSE_TOL = 1.02.
* **Ba-133 81.0 keV, Ir-192 205.8 keV (1 row each).** Imbalances of about 1 %, a difference of
  0.008 and 0.006 against 4 sigma = 0.007 and 0.005.

**Size of the effect on the correction** (reported, not registered). The summing-out term of a line
changes by sum_i dP(i | j) eps_t(E_i). The sums of dP over the failing partners are:

| line | sum of dP |
|---|---|
| Ac-228 270.2 keV | 0.138 |
| Ac-228 328.0 keV | 0.132 |
| Ac-228 209.3 keV | 0.033 |
| Ac-228 338.3 keV | 0.028 |
| Co-57 14.4 keV | 0.044 |
| Ba-133 81.0 keV | 0.011 |
| Ir-192 205.8 keV | 0.007 |

With a total efficiency of 0.1 for the partners (a close Marinelli geometry), the change is about
1.4 % at most, on the weak Ac-228 lines at 270 and 328 keV. It is 0.3 % on 338.3 keV and below 0.1 %
on the key lines 911.2 and 969.0 keV.

**Not changed.** The table and the correction are left as they are; which is right, the listed
intensities or the level balance, is a question about ENSDF data. A rule for imbalanced levels (for
example, capping the two-way probability at 1, or taking the upward term from the level balance)
needs its own protocol.

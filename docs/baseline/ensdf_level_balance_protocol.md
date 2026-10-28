# Coincidence table: upward probabilities at ENSDF levels whose intensity balance does not close (pre-registered)

Written 2026-10-27, before any change to the code or the table. It follows the round-4 R4-F result
(`round4_validation_protocol.md`, `after_R4F`): the downward probabilities P(j | i) of the table
agree with the Monte Carlo of `coincidence_ensdf_check` (237/237), but 13 upward and 13 two-way
probabilities do not (Ac-228 10, Ba-133 1, Ir-192 1, Co-57 1). The Co-57 value 122.1 keV given
14.4 keV is 1.018, above 1.

Checked before writing (no code changed): rebuilding the table with the current builder and the
same LiveChart files gives the bundled `coincidence_table.json` byte for byte.

## Cause

`Transition.coincident` adds the upward direction as P(i | j) = I_i P(j | i) / I_j, with I the
tabulated gamma intensities. I_i P(j | i) is the rate of the pair: it uses the transitions that
leave each level (branching). I_j is the tabulated rate of gamma j. Both are the same number only
when the level that emits j is populated exactly as fast as it de-excites. At some ENSDF levels the
transition intensities entering the level (gamma inflow) exceed those leaving it, so the implied
direct feeding is negative. There I_j is smaller than the rate implied by the scheme, and the upward
probability comes out too large (up to 17 % for Ac-228 270.2 and 328.0 keV, 1.018 for Co-57). The
Monte Carlo populates such a level by its inflow (direct feeding clipped at zero).

## Change (rule fixed now)

1. **Scheme intensities.** For each parent and decay mode, the builder
   (`analysis/data/build_coincidences_ensdf.py`) computes level populations:
   * direct feeding F(L) = max(0, out(L) - in(L));
   * out and in are the tabulated transition intensities I (1 + a) leaving and entering L;
   * the population of a level is P(L) = F(L) + the sum over gammas k entering L of P(S_k) b_k,
     taken from the highest level down, with b_k the branching of k at its start level S_k. The
     propagation does not stop at long-lived levels; they still end the coincident cascade, as
     before.
   * The scheme intensity of gamma k is I^s_k = P(S_k) b_k / (1 + a_k). For merged lines (same
     energy within MERGE_KEV) the intensities are summed.
   * Where every implied feeding is non-negative, I^s = I exactly.
2. **Table.** A record stores `gs`, the scheme intensities per gamma of the mode, only when some
   line differs from `g` by more than 1e-4 relative. `g`, `c`, `ann` and `dropped` are not changed:
   the downward probabilities, the annihilation probabilities, the line matching (INTENSITY_RANGE)
   and the dropping rule (REVERSE_TOL, tabulated intensities) stay as they are.
3. **Correction.** `Transition` builds the upward part of `coincident` as I^s_i P(j | i) / I^s_j,
   with `gs` when present, else `g` (identical to now). The summing-in term and the weighting of a
   line over transitions (br I, tabulated) are not changed.
4. **Harness.** `coincidence_ensdf_check` compares the upward rows against I^s_a P(b | a) / I^s_b
   (the record's `gs`, else `g`) and the two-way rows against `Transition.coincident`, as now. New
   fixed output folder `after_EB1` (`--eb1`). Engine version 1.21.0.

## Criteria

| ID | quantity | limit |
|---|---|---|
| EB.C1 | table rebuilt with the new builder, same LiveChart files | `g`, `c`, `ann`, `ann_unresolved`, `dropped`, `source`, `daughters_listed_by_parent` identical to the current table; the only difference is the added `gs` |
| EB.C2 | Monte Carlo check (same seed, 200000 decays per mode, 18 nuclides, 20 modes) | downward and annihilation rows identical to `after_R4F`; upward and two-way rows: 0 outside max(0.005, 4 sigma) (now 13 and 13) |
| EB.C3 | upward probabilities of the whole table, I^s_i P(j \| i) / I^s_j for every pair | all <= 1 + 1e-6 |
| EB.C4 | benchmark | the same PASS / FAIL / REPORT state of every criterion as `after_DA2` (154 / 13 / 60) |
| EB.C5 | IAEA 2002 check and CRM check as they run in the test suite | no criterion changes state |
| EB.C6 | tests | full suite passes; any existing test whose expected value changes is listed with the reason |

Reported, not judged:
* the records that get `gs`, the lines whose I^s / I differs by more than 1 %, and the levels with
  negative implied feeding;
* COI factors of all lines described by the table with `tcs_mc.eps_peak(E, 0.05)` and
  `tcs_mc.peak_to_total`, before and after; the largest changes, by nuclide and line (R4-F estimated
  at most about 1.4 % on the weak Ac-228 270/328 keV lines).

## Outputs

`docs/baseline/after_EB1/coincidence_check.md` and `.json`, `coi_change.md` and `.json`,
`baseline.md` and `.json`.

## Limitations

- When the scheme does not balance, either the tabulated gamma intensities of the level or its
  feeding are wrong. The rule follows the scheme (the downward probabilities already do). The
  Monte Carlo uses the same populations, so EB.C2 checks the computation, not the ENSDF data.
- The summing-in term still uses the tabulated intensities.
- Imbalances where out(L) > in(L) are read as direct feeding, as before, whatever the measured beta
  feeding is.

---

## Results (`after_EB1`)

Protocol committed in 78268ad before the change (SHA-256 of the file
1d05feafeb981c69a6996bbe2494e0d2798ae69ef226d617337ae15cc0197c2d). Engine 1.21.0.

| ID | value | result |
|---|---|---|
| EB.C1 | table rebuilt from the same LiveChart files: identical to the previous table once `gs` is removed (all records, `source`, `daughters_listed_by_parent`); 98 records of 95 nuclides get `gs` | PASS |
| EB.C2 | downward and annihilation rows, single-path cascades and coverage identical to `after_R4F`; upward 215 compared, 0 outside (before 13), largest 0.027, rms of z 0.95; two-way 448 compared, 0 outside (before 13) | PASS |
| EB.C3 | 25011 pairs of the table: 0 upward probabilities above 1 (before 12; largest Co-57 122.1 given 14.4 keV, 1.018); largest now 1.000 | PASS |
| EB.C4 | 154 PASS / 13 FAIL / 60 REPORT, no criterion changed state against after_DA2 | PASS |
| EB.C5 | IAEA 2002 (`after_EB1/iaea2002_results.*`): IA.C1-C6 in the same states as `after_CT1`; largest change of a ratio 1.8e-5 (maritsmall60 Co-60). CRM check: its test passes with the recorded values | PASS |
| EB.C6 | 1483 passed, 69 skipped | PASS |

**Implementation note (before judging EB.C1).** The first build also added `gs_tol` to `source` and a
sentence on `gs` to `convention`. EB.C1 allows only `gs`, so both were taken out; `gs` is described
in the builder's docstring and in `analysis/coincidence.py`. The criterion was then judged.

**Changed existing tests (reasons).**
* `test_coincidence.py::test_cs134_main_cascade`: the reverse probability is now checked against the
  scheme intensities (Cs-134 has `gs`).
* `test_iaea2002_validation.py`: the reproduced record is `after_EB1` (engine 1.21.0) instead of
  `after_CT1`; one Marinelli ratio moves by 4e-6 relative, above the test's 1e-9.

New tests in `test_build_coincidences_ensdf.py`: a balanced scheme gets no `gs`; a level fed by more
than it emits gives an upward probability of 1 instead of 1.0101, with the downward unchanged; every
upward probability of the bundled table is at most 1.

**Reported.**
* Levels with negative implied feeding in the four nuclides that failed in R4-F (P(L) / out(L)):
  Ac-228 13 levels, among them 328.0 (1.17), 396.1 (1.10), 831.8 (1.11), 1539.2 (1.68), and 938.6 and
  968.3 keV (25.8 and 10.2: the 214.85 and 674.75 keV gammas, 0.76 % and 2.1 %, are placed into
  levels whose listed gammas total 0.03 % and 0.25 %; a misplacement in the data is more likely than
  missing outflow). Ba-133 81.0 keV (1.012), Ir-192 205.8 keV (1.007), Co-57 14.4 keV (1.044).
* COI with eps_peak(1000 keV) = 0.05 (`coi_change.*`): 1575 lines, 280 changed. For lines with COI
  of at least 0.8 before and after (75 lines), 6 change by more than 1 %: Th-227 93.9 keV -2.0 %,
  U-237 26.3 and 59.5 keV -1.5 %, Ac-228 209.3 keV -1.4 %, Th-227 79.7 keV -1.3 %, Ac-228 338.3 keV
  -1.2 %. Ac-228 270.2 and 328.0 keV: +0.8 % (R4-F estimated at most about 1.4 %). Co-57 14.4 keV
  +2.2 %. The large relative changes in the table (up to 104 %) are lines whose COI is far below 1
  in this geometry, mostly below 300 keV where eps_peak exceeds 0.3. The efficiency is a test model,
  not a laboratory geometry.

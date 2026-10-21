# Annihilation (511 keV) summing in the true-coincidence correction (finding F2): pre-registered

Status: **pre-registered**. This file and its SHA-256 are recorded before the change is implemented.
Results go below the line at the end. Limits are not changed after the results are seen.

## 1. Defect

The IAEA 2002 check (`iaea2002_validation_protocol.md`, finding F2) measured Na-22 at a ratio of
0.80 in a 500 ml Marinelli on a 33 % HPGe and 0.66 in a 100 ml pillbox on a 96 % HPGe. The cause is
that the coincidence table is gamma–gamma only. A gamma that follows a β+ decay can sum with one of
the two 511 keV annihilation photons, and that loss from its full-energy peak is not corrected.

## 2. Data and method

**Source.** The same SandiaDecay file the table is built from: `sandia.decay.min.xml`, commit
cd75314b, SHA-256 `ef9dcdb7…`. Per decay transition it lists:
- the gammas, with their gamma–gamma coincidences;
- the EC branches (`<ec e=…>`, e = Q − level);
- the β+ branches (`<p e=…>`, endpoint e = Q − 1022 − level).

The level of each branch is not given, so it is reconstructed.

**Reconstruction (build time, `build_coincidences.py`).**
1. **Top level of each gamma.** E_g plus the highest top level among the gammas that follow it in
   the cascade, taken from the source coincidences. A gamma with no successor ends on the ground
   state.
2. **Levels.** {0} plus the top levels.
3. **Q.** The value that maximises the summed intensity of EC branches (Q − e) and β+ branches
   (Q − 1021.998 − e) falling within TOL = 6 keV of a level. On ties, the smallest Q is taken.
   - TOL is 6 keV because one source endpoint, Zn-65 EC to the ground state, differs by 5 keV;
     this was found in the feasibility check.
4. **β+ feeding per level.** f_L, the sum of the β+ intensities of the branches assigned to level L.
5. **Probability that gamma k comes with a positron.**
   P(β+ | k) = Σ_L f_L · P(k | L) / I_k, with:
   - P(k | L) = I_k / F_L when k leaves L (top level of k = L);
   - P(k | L) = Σ_{g leaves L} (I_g / F_L) · P(k | g) otherwise.

   F_L = Σ_{g leaves L} I_g is the gamma flux out of L. Conversion is neglected, which is documented.
6. **Validity per transition.** The result is stored only when:
   - every β+ branch is assigned to a level; and
   - every P(β+ | k) ≤ 1.001.

   Otherwise the transition is marked `"ann_unresolved": true` and nothing is stored.
   - In the feasibility check (library nuclides, TOL 6 keV) these fail: V-48, Mn-52, Co-55, Ni-57,
     Ga-68, As-74, Rb-81 (main branch) and Rb-82.
   - These pass: C-11, N-13, F-18, Na-22, Al-26, K-40, Sc-44, Mn-52m, Mn-54, Fe-52, Co-56, Co-58,
     Cu-62, Cu-64, Zn-62, Zn-65, Rb-84, Y-87, Y-88, Zr-89, Ag-108, In-114, Sb-122, I-124, Cs-132,
     Eu-152, Eu-152m and Bi-207.

**Table.** Each transition gains `"ann": [[i, P(β+ | i)], …]` for the gammas with P > 1e-4. Records
are now kept when they have gamma–gamma pairs **or** annihilation entries, so Na-22 enters the
table. The table is rebuilt from the checked source; the gamma–gamma content stays byte-identical.

**Correction (`coincidence.coi`).** Each positron gives two 511 keV photons, each of which can be
detected. The first-order summing-out of line i gains

    P(β+ | i) · 2 · ε_t(511),   ε_t = ε_p / PT

(the same e_min rule applies: 511 keV below BELOW_CURVE · e_min gets ε = 0 and is reported).

Assumptions, stated in the code and in SOURCES.md:
- All positrons annihilate in the source; annihilation in flight is neglected.
- The two photons are counted independently at first order. Their 180° correlation only enters at
  second order.
- No summing-in with 511 keV.
- Lines of an `ann_unresolved` transition are corrected for gamma–gamma summing only, with the note
  "511 keV summing not evaluated".

`has_cascades` is true for nuclides with annihilation entries, so efficiency-calibration points of
Na-22 are corrected by `summing_free_curve` as well.

**Version.** ENGINE_VERSION 1.7.0 → **1.8.0**: activities of β+ emitters change when TCS is on.

## 3. Criteria

| ID | Quantity | Limit |
|---|---|---|
| AN.C1 | P(β+ \| γ) in the rebuilt table: Na-22 1274.54 = 0.90326/0.99941; Co-58 810.76 = 0.149/0.9945; Co-58 863.95 = 0; Zn-65 1115.54 = 0 (β+ to the ground state); Y-88 1836.06 = 0.0021/0.9924; Y-88 898.04 = 0; Cu-64 1345.77 = 0 | each within 0.002 absolute |
| AN.C2 | Gamma–gamma part of the rebuilt table (`g`, `c`, `br`, `dropped` of every record already present) | identical to the bundled table |
| AN.C3 | Independent event-by-event simulation (`tcs_mc`): new hand-coded ENSDF schemes for Na-22 (β+ 90.326 % and EC 9.618 % to 1274.54; β+ 0.056 % to the ground state) and Co-58 (β+ 14.9 % and EC 83.9 % to 810.76; EC 1.2 % to 1674.7). Each β+ emits two 511 keV photons, each independently deposited. COI vs COI_MC for Na-22 1274.5 and Co-58 810.8 at e1000 = 0.005 and 0.02, 2·10⁷ decays | \|d\| − 3σ ≤ 0.005 at 0.005 and ≤ 0.01 at 0.02 (the tcs.far / tcs.mid limits); 0.05 reported |
| AN.C4 | Analytic check: Na-22 1274.5 with constant ε_p, PT gives COI = 1 − 0.90379 · 2 ε_t(511) | 1e-12 |
| AN.C5 | IAEA 2002 check re-run (harness unchanged, new folder `after_AN1`): Marinelli Na-22 ratio, both spectra | in [0.90, 1.10] |
| AN.C6 | Same re-run: every Marinelli pair of another nuclide | ratio changes by ≤ 0.01 absolute from after_IA1 |
| AN.C7 | Same re-run: pillbox Na-22 ratio, both spectra | higher than after_IA1 (0.661 / 0.662); value reported |
| AN.C8 | Standard benchmark | 154 PASS / 13 FAIL / 60 REPORT, no PASS → FAIL |
| AN.C9 | Full test suite | passes. Tests whose expected values are this defect are updated and listed: `test_coincidence.py` "missing" set without Na-22 |

The new simulation schemes for C3 are kept apart from `tcs_mc.SCHEMES` (`POSITRON_SCHEMES`), so the
existing benchmark category `cat_tcs` and its criteria are unchanged.

Re-evaluating the IA.C1–IA.C6 criteria on `after_AN1` is **report only**. The after_IA1 record and
its FAIL entries stay as they are.

## 4. Outputs

- `docs/baseline/after_AN1/`: the benchmark, `iaea2002_results.md/.json` and
  `annihilation_results.md` (C1–C4).
- Tests: `tests/test_annihilation_summing.py`.

---
## Results

(appended after the run)

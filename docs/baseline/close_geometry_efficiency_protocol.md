# Close-geometry efficiency curve with cascade-emitter calibration points (F4): pre-registered protocol

Written 2026-10-22, before implementation. This is finding F4 of `iaea2002_validation_protocol.md`.
Results are appended below the line after the run; nothing above it changes after its SHA-256 is
recorded.

## 1. Defect

* `fit_efficiency(points, "two_branch", crossover="auto")` chooses the branch orders and the
  crossover by leave-one-out cross-validation on the points it is given.
* When the sample analysis corrects true-coincidence summing, `summing_free_curve` divides the
  cascade-emitter points (Cs-134, Y-88 ...) by their COI and refits. Each refit keeps the orders
  and crossover chosen **on the uncorrected points**.
* On a large detector in a close geometry those points are strongly distorted:
  * summing-out down to COI 0.78;
  * summing-in at Cs-134 1365 keV, whose apparent efficiency lies above that at Zn-65 1115 keV.

  The selection made on them does not fit the corrected points.
* IAEA 2002 pillbox (96 % detector):
  * The chosen model is Ec = 103.7 keV with orders 1/1. It is kept after the correction.
  * The curve then lies 14.6 % above the measured Co-57 122.06 keV point, so Eu-152 at 121.8 keV
    is 13 % low from the curve alone.
  * The leave-one-out model error is 6.0 %, so every pillbox result carries u ≈ 14 %.

## 2. Measurements made before writing this protocol

Prototype on the IAEA 2002 data: the refits inside `summing_free_curve` choose the orders and
crossover again, as the original fit did. Measured with the harness of `iaea2002.py`.

* **Pillbox curve.**
  * The model becomes Ec = 205.7 keV, orders 3/3, model error 0.
  * Residuals of the non-cascade points (Am-241 ... Zn-65): at most 2.2 % (Zn-65); Co-57
    122.06 keV goes from −12.6 % to −1.2 %.
  * The corrected Cs-134 points stay 4–7 % below the curve: their summing is under-corrected. That
    is not changed here.
* **Marinelli curve.** Ec = 586.8 keV 3/1 becomes 469.7 keV 3/3. The test ratios change by at most
  1.4 %.
* **Ratios, long spectra, without self-attenuation:**

  | | Ba-133 | Co-60 | Eu-152 | Cr-51 | Na-22 | median |
  |---|---|---|---|---|---|---|
  | pillbox now | 0.912 | 0.863 | 0.683 | 0.940 | 0.838 | 0.863 |
  | pillbox prototype | 0.887 | 0.896 | 0.773 | 0.909 | 0.882 | 0.887 |
  | Marinelli now | 0.963 | 0.973 | 0.908 | 1.007 | 0.954 | 0.963 |
  | Marinelli prototype | 0.952 | 0.959 | 0.905 | 1.003 | 0.959 | 0.959 |

* **With the F5 self-attenuation correction** (`SelfAttenuation("organic", 1.6, "organic", 1.15,
  35.3)`) on the pillbox:
  * pillbox long ratios: Ba-133 0.960, Co-60 0.940, Eu-152 0.860, Cr-51 0.986, Na-22 0.924;
  * IA.C3 1.0, IA.C4.P 0.940, IA.C5 1.61;
  * IA.C1 0.85: 17/20, because u is now 3–5 % instead of 14 %.
  * The three pairs with |z| > 2.58 are all Eu-152 at 121.8 keV: PITBIG and both Marinelli
    spectra. In PITBIG60 the engine takes 1408 keV as the Eu-152 key line and gets 0.955.
  * This points to the missing X-ray–gamma summing at 121.8 keV, finding F3. That remains a
    hypothesis here.
* **Run time** of the pillbox geometry: 7.4 s now, 8.1 s with re-selection.
* The standard benchmark and the CRM check do not call `summing_free_curve`.

## 3. Change

1. **`EfficiencyCurve` records how its model was chosen.** New fields:
   * `orders_auto: bool = False`: orders chosen by cross-validation;
   * `crossover_auto: bool = False`: two-branch crossover chosen automatically.

   `fit_efficiency` sets them. Curves saved earlier load with both False.
2. **`summing_free_curve` refits like the original fit.**
   * Orders chosen automatically are chosen again on the corrected points at every refit, and so
     is an automatic crossover.
   * Orders or a crossover given explicitly are kept, exactly as now.
   * The refitted curve keeps the new fit's `selection` text and the two flags.
   * Convergence is unchanged: the corrected points must change by less than 1e-7 between refits,
     with at most 200 refits; otherwise the existing error is raised.
3. **Unchanged:**
   * curves fitted with explicit orders and crossover;
   * curves without cascade points;
   * curves loaded from earlier files;
   * the COI computation;
   * the peak-to-total ratio;
   * every analysis without the summing correction.
4. **Engine version.** The engine changes, so `ENGINE_VERSION` becomes 1.12.0.

**Not in this change:**
* the under-correction of the strongly summing Cs-134 points (first-order COI, P/T measured at
  10 cm);
* X-ray–gamma summing (F3).

## 4. Criteria (set before the run)

| id | what | limit |
|---|---|---|
| CG.C1 | IAEA pillbox summing-free curve: residual of every non-cascade calibration point (Am-241, Cd-109, Co-57, Ce-139, Sn-113, Hg-203, Cs-137, Mn-54, Zn-65) | ≤ 3 % in magnitude |
| CG.C2 | IAEA harness, pillbox with the F5 correction `SelfAttenuation("organic", 1.6, "organic", 1.15, 35.3)` | IA.C3 ≥ 0.80 and IA.C4.P in [0.93, 1.07] |
| CG.C3 | IAEA harness, Marinelli (no self-attenuation) | IA.C2 and IA.C4.M still pass; every one of the 10 ratios within 2 % of after_SA1 |
| CG.C4 | `summing_free_curve` on curves with explicit orders and crossover, on curves without cascade points, and on curves loaded from a dict without the new fields | identical to the current code (parameters, covariance, points) |
| CG.C5 | standard benchmark against after_SA1; CRM check against after_SA1 | identical except the engine version (and runtime fields) |
| CG.C6 | new unit tests; full suite | pass; changed existing tests listed with reasons |

**Reported, not criteria:**
* the IAEA criteria without self-attenuation, as the harness writes them;
* IA.C1 and IA.C5 with the correction. IA.C1 is expected to fail because of Eu-152 at 121.8 keV
  (F3).
* the per-pair ratios, z and u;
* the run time.

Outputs go to a new folder `docs/baseline/after_CG1/`.

---
## Results

(appended after the run)

Run 2026-10-22, engine 1.12.0. The text above the line is unchanged (SHA-256 of the pre-registered
file 41077eb4c14dca560f380acec53143b018a10e62a2fd44494c2014287a293bce, commit a4fa232). Outputs:
`docs/baseline/after_CG1/`:
* `close_geometry_results.json`: CG.C1 residuals, CG.C2/C3 values, the pillbox pairs with the F5
  correction. No spectrum data is stored.
* `baseline.*`, `iaea2002_results.*` (the harness as written, no self-attenuation),
  `crm_validation_results.*`.

| id | value | limit | result |
|---|---|---|---|
| CG.C1 pillbox curve | Ec = 205.7 keV, orders 3/3 (was 103.7 keV, 1/1). Largest residual of the listed points 2.2 % (Zn-65); Co-57 122.06 keV −1.2 % (was −12.6 %) | ≤ 3 % | PASS |
| CG.C2 pillbox with F5 | IA.C3 1.0 (10/10); IA.C4.P 0.940 | ≥ 0.80; [0.93, 1.07] | PASS |
| CG.C3 Marinelli | IA.C2 1.0, IA.C4.M 0.959; largest ratio change from after_SA1 1.4 % (Ba-133, Co-60) | 2 % | PASS |
| CG.C4 unchanged cases | explicit orders and crossover, no cascade points, curves loaded without the new fields: refitted exactly as before (`tests/test_close_geometry_efficiency.py`) | identical | PASS |
| CG.C5 benchmark, CRM | benchmark vs after_SA1: 1 difference, `meta/engine_version`; CRM: 1 difference, `engine_version` | engine version only | PASS |
| CG.C6 tests | new `tests/test_close_geometry_efficiency.py` (5) pass; full suite 1409 passed, 69 skipped after one change below | | PASS |

**Changed existing test.** `tests/test_iaea2002_validation.py::test_marinelli_reproduces_the_recorded_ratios`
compared the Marinelli ratios with the engine 1.8.0 record (after_AN1). This change moves them by up
to 1.4 % (CG.C3), as intended; the test now reproduces the after_CG1 record. Its check (1e-9) is
unchanged.

**Note on CG.C1.** `coincidence.has_cascades` also counts Zn-65 (annihilation photons), so the
engine corrects its point; the criterion uses the protocol's list, in which Zn-65 is included.

**Reported.**
* The IAEA criteria as the harness writes them (no self-attenuation): IA.C1 0.55 (was 0.70),
  IA.C2 1.0, IA.C3 0.8, IA.C4.M 0.959, IA.C4.P 0.887 (was 0.863), IA.C5 2.90 (was 2.50), IA.C6 20.
  The ratios are closer to 1, but the pillbox u fell from about 14 % to 3–5 % (model error 6.0 % ->
  0), so the remaining density bias now gives |z| > 2.58.
* With the F5 correction: IA.C1 0.85 FAIL, IA.C5 1.61. The three pairs with |z| > 2.58 are all
  Eu-152 at 121.8 keV (PITBIG −3.59, both Marinelli spectra −2.86 and −2.71). PITBIG60 takes
  1408 keV as its Eu-152 key line: ratio 0.955. This is consistent with missing X-ray–gamma summing
  (F3), still a hypothesis.
* Pillbox long ratios with F5: Ba-133 0.960, Co-60 0.940, Eu-152 0.860, Cr-51 0.986, Na-22 0.924.
* The Cs-134 points stay 4–7 % below the curve after correction: under-corrected summing, not
  changed here.

**What ships.**
* An efficiency curve whose orders or crossover were chosen automatically has them chosen again
  on the summing-corrected points when the sample analysis corrects true-coincidence summing.
* Explicit models and earlier saved curves are refitted as before.
* The IAEA pillbox now passes IA.C3 and IA.C4.P with the self-attenuation correction. The
  remaining defect is Eu-152 at 121.8 keV (F3).

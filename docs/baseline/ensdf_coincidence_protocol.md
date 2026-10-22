# Coincidence table from ENSDF decay schemes: pre-registered protocol

Written 2026-10-22, before the final run. This is part of item F3 of the plan (summing in the IAEA
Eu-152 lines). Results are appended below the line after the run; nothing above it changes after
its SHA-256 is recorded.

## 1. Defect

**What F3 showed.**
* After the F5 self-attenuation correction, the IAEA 2002 Eu-152 activities are still low.
* At the long Marinelli spectra the 121.8 keV key line gives 0.904 of the certificate.
* The per-line ratios split by decay branch:
  * the β⁻ lines (344.3 keV 1.026, 778.9 keV 1.028) are close to 1;
  * the EC lines are low: 121.8 keV 0.904, 244.7 keV 0.850, 964.1 keV 0.903, 1408 keV 0.953.
* At the pillbox, 121.8 and 244.7 keV are both at 0.771.
* The K X-ray summing that F3 was to add is only 1–2 % here (Sm K X-rays, 0.74 per EC decay at
  ~41 keV). It does not explain the gap.

**Diagnosis, verified.** The coincidence probabilities of the bundled table, taken from the
SandiaDecay `sandia.decay.min.xml` (SHA-256 ef9dcdb7…), are wrong for 80 of the 191 transitions of
the library. Most of them are far too small. Recomputed from the ENSDF level schemes:

| cascade | SandiaDecay | ENSDF level scheme |
|---|---|---|
| Sc-48 1312 → 983.5 keV (single path) | 0.1001 | 0.99988 |
| Eu-152 EC 1408 → 121.8 keV (single path) | 0.1716 | 0.464 = 1/(1+α₁₂₁.₈) |
| Eu-152 EC 244.7 → 121.8 keV | 0.336 | 0.903 |

Co-60, Ba-133, Cs-134 and Y-88, the nuclides of the benchmark TCS criteria, are correct in the
old table. This is why the benchmark did not show the defect.

## 2. Measurements made before writing this protocol

**Prototype, which is the code that will be committed.**

`analysis/data/build_coincidences_ensdf.py` builds the table from the IAEA LiveChart of Nuclides
decay-radiation tables (ENSDF), one CSV file per nuclide (`rad_types` g and bp).
* The files are kept outside the repository.
* Their SHA-256 values are recorded in the table.

Method:
1. **Transitions and branching.** The gammas are placed by their start and end levels. The
   transition intensity is I(1+α). Each level branches in proportion to the transition
   intensities.
2. **Isomers.** A level with a half-life > 1 µs ends the coincident cascade.
3. **Coincidence probability.** P(j|i) = reach_j(end level of i) / (1+α_j). It does not depend on
   how the levels are fed.
4. **Annihilation.** P(β⁺|i) is computed from the β⁺ feeding of the levels.
5. **Same-energy gammas.** Gammas of the same tabulated energy from different levels are merged
   into one line (Te-131m 852.21 keV).
6. **Daughters already listed by the parent.** The parent's ENSDF decay may already list an
   included isomer daughter: this happens when the daughter is an isomer of the decay product and
   gammas start from its level (Cs-137 → Ba-137m, Bi-207 → Pb-207m, 16 parents).
   `coincidence.transitions` then skips that daughter's IT record. Without this skip, Bi-207
   1063.7 keV appeared at 180 %.

**Inputs.**
* 225 gamma files, digest e197398a….
* Table: 185 nuclides. No ENSDF data for Ag-109m and Ce-140m.

**Independent check (`validation/coincidence_ensdf_check.py`).** It shares no code with the
builder: its own CSV reading, level feeding from the intensity balance, and a Monte Carlo random
walk down the levels (200 000 decays per mode, seed 12345) instead of the analytic path sums.
* **18 nuclides:** Co-60, Sc-48, Y-88, Na-22, Cs-134, Ba-133, Eu-152, Bi-207, Se-75, Ir-192,
  Co-56, Sb-124, La-140, Bi-214, Pb-214, Tl-208, Ac-228, Co-57.
* **237 comparisons** (pairs and annihilation probabilities ≥ 0.01, lines ≥ 0.5 % per decay):
  * none outside max(0.005, 4σ);
  * largest |table − simulation| 0.024 (Eu-152, a weak line);
  * z of the 212 with σ > 1e-5: mean 0.10, rms 1.02; 10 above 2, 1 above 3.
* **Single-path cascades**, P = 1/(1+α_j) with α from the same rows:
  * Co-60 1173 → 1332: 0.999838;
  * Sc-48 1312 → 983.5: 0.999876;
  * Y-88 898 → 1836: 0.99986;
  * Eu-152 1408 → 121.8: 0.464037.

  Each equals the expected value to 1e-6.

**Library coverage.** Library gamma lines ≥ 1 % whose intensity the table's transitions reproduce
within ×0.75–1.33:
* **old table:** 975 described, 32 in the table but not described;
* **new table:** 1015 described, 6 not described (In-114m 558.4 and 725.2, Np-237 86.6, Sb-125
  35.5, Te-131m 182.2, Zr-97 657.9).
* **Lost:** In-116m 1753.8, Kr-88 1249.0, Sb-126 555.2, 605.4 and 1034.8. The library intensity
  differs from ENSDF, so these lines are left uncorrected and flagged like the others.
* **Annihilation:** 24 nuclides have β⁺ coincidences, none unresolved. The old table had 9
  unresolved, including As-74, Co-55, Ga-68, Mn-52, Ni-57, Rb-81, Rb-82 and V-48.

**IAEA 2002 harness as written (no self-attenuation), against after_MX1.**
* **Eu-152:**

  | spectrum | key line | before | after |
  |---|---|---|---|
  | maritsmall | 121.8 keV | 0.904 | 0.963 |
  | maritsmall60 | 121.8 keV | 0.908 | 0.968 |
  | PITBIG | 121.8 keV | 0.771 | 0.840 |
  | PITBIG60 | 1408 keV (was 121.8 keV) | 0.759 | 0.951 |

* **The other 16 pairs** move by at most 0.36 % (Cr-51, through the summing-corrected efficiency
  curve).
* **Criteria:**
  * IA.C1 0.55 → 0.65, IA.C3 0.8 → 0.9, IA.C5 2.94 → 2.09, IA.C4.P 0.887 → 0.887;
  * no criterion changes its state.
* **Long Marinelli Eu-152 lines:** 121.8 keV 0.963, 244.7 keV 0.927, 344.3 keV 1.030, 778.9 keV
  1.033, 964.1 keV 0.940, 1408 keV 0.983.

**With the F5 correction (pillbox organic 1.6 / 1.15 g/cm³ as in after_SA1):** all seven IAEA
criteria pass:
* IA.C1 1.0, C2 1.0, C3 1.0, C4.M 0.959, C4.P 0.941, C5 1.12, C6 20;
* Eu-152: Marinelli 0.963, pillbox 0.936.

**Standard benchmark against after_MX1.**
* The same 13 criteria fail; no PASS → FAIL.
* The close-geometry TCS lines (Co-60, Cs-134, Y-88) change by at most 0.0067 in d (Y-88 2734 keV
  sum peak).

**Unit tests.** 14 existing tests fail with the new table. Each depends on a number or example
of the old source:
* exact Co-60 / Cs-134 values;
* the covered set (Th-228 now has data);
* the provenance keys;
* Bi-207, whose hand calculation must skip the listed daughter;
* Ir-192 484.6 and U-235 as examples of a line not described or of a partner below the curve;
* Na-22 β⁺ 0.90379 of the old source, against ENSDF 0.8995;
* "unresolved Mn-52";
* Am-241 in a list of nuclides without cascades.

## 3. Change

1. **New `analysis/data/build_coincidences_ensdf.py`**, as in §2. `coincidence_table.json` is
   rebuilt with it. The new keys are:
   * `mode` per record;
   * `daughters_listed_by_parent`;
   * the source digest and the files' SHA-256.

   The format number is unchanged (1).
2. **`analysis/coincidence.py`:** `transitions()` skips the IT records of the daughters a parent
   lists. Docstrings name the new source.
3. **New `validation/coincidence_ensdf_check.py`**, as in §2. It writes `coincidence_check.*`.
   The raw files stay outside the repository.
4. **Documentation and licence.** SOURCES.md and the installer's third-party notice name ENSDF via
   the IAEA LiveChart of Nuclides with the acknowledgement the IAEA terms ask for: content may be
   adapted and copied for commercial and non-commercial products, with the IAEA acknowledged as
   the source and no IAEA endorsement implied. The SandiaDecay builder `build_coincidences.py`
   stays in the repository for reference; its table is no longer shipped.
5. **Engine version.** Every TCS correction changes, so `ENGINE_VERSION` becomes 1.14.0.

**Unchanged:**
* the TCS correction formulas;
* the gamma library;
* the efficiency methods;
* the IAEA harness;
* the X-ray coincidences, which are still absent (the rest of F3, a separate item).

## 4. Criteria (set before the run)

| id | what | limit |
|---|---|---|
| CT.C1 | single-path cascades (Co-60 1173 → 1332, Sc-48 1312 → 983.5, Y-88 898 → 1836, Eu-152 EC 1408 → 121.8) against 1/(1+α_j) from the same ENSDF rows | \|diff\| ≤ 5e-4 each |
| CT.C2 | Monte Carlo check of the 18 nuclides of §2 (seed 12345, 200 000 decays per mode) | every comparison within max(0.005, 4σ); rms z ≤ 1.3 |
| CT.C3 | library coverage | ≥ 1000 lines described; ≤ 10 in the table but not described; no `ann_unresolved`; `no_ensdf_data` only Ag-109m and Ce-140m |
| CT.C4 | IAEA 2002 harness as written, against after_MX1 | each of the 4 Eu-152 ratios closer to 1 than before; the other 16 within 1 %; no IAEA criterion PASS → FAIL |
| CT.C5 | IAEA 2002 with the F5 correction (pillbox organic 1.6 / 1.15 g/cm³) | IA.C1–C6 all pass |
| CT.C6 | standard benchmark and CRM check against after_MX1 | benchmark: the same failing criteria, close-geometry TCS \|Δd\| ≤ 0.01 per line; CRM: the same criteria states, every activity within 2 % |
| CT.C7 | unit tests: new builder tests on synthetic CSV files (single path with α, branching, isomer cut, same-energy merge, β⁺ probability, listed daughter skipped); full suite | pass; changed existing tests listed with reasons |

**Reported, not criteria:**
* the Eu-152 per-line ratios;
* the lines lost from or gained in the coverage;
* the run time.

Outputs go to a new folder `docs/baseline/after_CT1/`. No ENSDF or IAEA data is copied into the
repository; only the derived numbers are.

---
## Results

(appended after the run)

Run 2026-10-22, engine 1.14.0, implementation commit 581390c. The text above the line is unchanged
(SHA-256 of the pre-registered file d602340380ae0cfcf07a4ce0d2b3c4bcb083043d0b6dec94bdfaf319966c1cb4,
commit 9cb5c65). Outputs in `docs/baseline/after_CT1/`:
* `coincidence_check.*`: CT.C1–C3. Derived numbers only; no ENSDF rows are stored.
* `iaea2002_results.*`: CT.C4.
* `iaea2002_self_attenuation_results.json`: CT.C5.
* `baseline.*`, `crm_validation_results.*`: CT.C6.

| id | value | limit | result |
|---|---|---|---|
| CT.C1 single-path cascades | Co-60 0.999838, Sc-48 0.999876, Y-88 0.99986, Eu-152 1408 → 121.8 0.464037; each equals 1/(1+α_j) to 1e-6 | ≤ 5e-4 | PASS |
| CT.C2 Monte Carlo, 18 nuclides | 237 comparisons, 0 outside max(0.005, 4σ); largest \|diff\| 0.024 (Eu-152); z of 212: mean 0.10, rms 1.02 (10 above 2, 1 above 3) | all within; rms ≤ 1.3 | PASS |
| CT.C3 coverage | 1015 described, 6 not described; no `ann_unresolved`; `no_ensdf_data` Ag-109m, Ce-140m | ≥ 1000; ≤ 10; none; those two | PASS |
| CT.C4 IAEA as written | Eu-152 0.904 → 0.963, 0.908 → 0.968, 0.771 → 0.840, 0.759 → 0.950 (PITBIG60 key line now 1408 keV); other 16 pairs within 0.13 %; IA.C1 0.55 → 0.65, IA.C3 0.8 → 0.9, IA.C5 2.94 → 2.09; no criterion changes state | closer to 1; ≤ 1 %; no PASS → FAIL | PASS |
| CT.C5 IAEA with F5 correction | IA.C1 1.0, C2 1.0, C3 1.0, C4.M 0.959, C4.P 0.941, C5 1.115, C6 20 | all pass | PASS |
| CT.C6 benchmark, CRM | benchmark: the same failing criteria as after_MX1; largest close-geometry TCS \|Δd\| 0.0067 (Y-88 2734 keV sum peak); CRM: 1 difference, `engine_version` | same; ≤ 0.01; same states, ≤ 2 % | PASS |
| CT.C7 tests | new `tests/test_build_coincidences_ensdf.py` (6) pass; full suite 1425 passed, 69 skipped | | PASS |

**Deviation found after registration (builder).**
* **What happened.** In Te-131m, the merged 852.21 keV line comes from two levels: the weak gamma
  from 2001 keV lies above the 296.8 keV gamma, and the strong gamma from 852 keV lies below it.
  The table then held both directions of the pair, so the two-way probability of the 296.8 keV
  line reached 1.48.
* **Fix.** When the two directions of a pair together exceed REVERSE_TOL, the builder now keeps only
  the larger contribution and counts the pair as `dropped`.
* **Effect.** One pair of Te-131m (296.8 keV, 0.066 % per decay) changed; nothing else in the table.
* **Timing.** All criteria above were run with this fix.

**Changed existing tests (reasons).**
* **`test_coincidence`:**
  * Co-60 and Cs-134 exact values now from ENSDF (1/(1+α) = 0.999838; 0.994046);
  * the covered set is {Ra-228}, because Th-228 has its own weak cascades in ENSDF;
  * provenance checks the ENSDF source digest;
  * the rebuild test uses `SPECTRAMASTER_LIVECHART_DIR`.
* **`test_tcs_fixes`:**
  * the Bi-207 hand calculation skips the Pb-207m IT record listed by the parent (COI 0.9306 →
    0.9335 with the table's own data);
  * the untreatable-point example states three times the Ir-192 484.6 keV intensity, because the
    line is now described.
* **`test_tcs_safety`:**
  * the partner-below-the-curve example is Mg-28 1342.2 keV (30.6 keV partner) instead of U-235;
  * the line-not-described example is In-114m 558.4 keV (4.4 % library, 3.27 % ENSDF) instead of
    Ir-192 484.6 keV.
* **`test_annihilation_summing`:**
  * Na-22 P(β⁺ | 1274.5) is 0.899515 from ENSDF (β⁺ 89.9 %) instead of 0.90379;
  * the unresolved case is a hand-made transition, because the ENSDF table has none.
* **`test_close_geometry_efficiency`:** Am-241 is removed from the list of nuclides without
  cascades.
* **`test_iaea2002_validation`:** reproduces the after_CT1 record.

**AN.C1 of annihilation_summing_protocol.md fails as written with the new table.**
* **Value.** Its registered Na-22 value 0.90326/0.99941 = 0.9038 comes from SandiaDecay. ENSDF
  (LiveChart) gives 0.8995, a difference of 0.0043 against the limit of 0.002. The other six AN.C1
  lines agree within 5e-5.
* **Not changed.** The criterion and its harness are left unchanged. The test now states this
  failure explicitly.

**Reported.**
* **Lines no longer described:** In-116m 1753.8, Kr-88 1249.0, and Sb-126 555.2, 605.4 and
  1034.8 keV. Their library intensity differs from ENSDF; they are left uncorrected with the usual
  note.
* **Eu-152 lines of the long Marinelli spectra, from §2:** 121.8 keV 0.963, 244.7 keV 0.927,
  344.3 keV 1.030, 778.9 keV 1.033, 964.1 keV 0.940, 1408 keV 0.983. The remaining EC-line
  deficit, 3–7 %, is in the range of the missing X-ray summing (Sm K X-rays), the rest of F3.
* **Run time:** Monte Carlo check about 1 min.

**What ships.** The true-coincidence correction now uses cascade probabilities computed from the
ENSDF level schemes:
* every transition is checked against an independent simulation;
* the large SandiaDecay errors (Sc-48, Eu-152 EC and 78 others) are gone;
* β⁺ summing is resolved for every positron emitter of the library.

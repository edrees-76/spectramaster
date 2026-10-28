# Round-5 review: partial true-coincidence summing corrections, H5 and H6 (pre-registered)

Written 2026-10-28, before any change to the engine. Codex round-5 review
(`D:\DSpectraMaster_reviews\codex_review_round5.md`, main 865c1ec), findings H5 and H6, checked on the
code (`analysis/coincidence.py`, `coi` and `Transition`; `analysis/efficiency.py`,
`summing_free_curve`; `analysis/activity.py`) before this protocol was written.

**H5.** Cascade partners below 0.8 x the lower limit of the efficiency curve get efficiency 0 and are
reported in `ignored`, but the correction is otherwise returned as complete (`reason` empty,
`found` True). Reproduced (harness below): Ba-133 356.0129 keV, flat efficiency 0.02, P/T 0.24:
COI 0.9703591 with e_min 50 keV, 1.0 with e_min 122 keV (`ignored` 0.369959, `reason` empty). In the
activity the line gets a note, but `coi_applied` is True and the nuclide reads "true-coincidence
summing corrected". `summing_free_curve` corrects such calibration points and labels the curve
`summing_corrected`: a curve of Eu-152 and Ba-133 points from 121.8 keV is corrected (lowest COI
0.8230), its Ba-133 points without their partners at 53 and 81 keV.

**H6.** In a transition whose scheme intensities `gs` (levels fed by their gamma inflow,
ensdf_level_balance_protocol.md) differ from the gamma intensities `g`, the upward probability
P(i | j) = s_i P(j | i) / s_j uses `gs` while the line rates and the summing-in use `g`: the pair rate
seen from the two lines differs. Reproduced: Ac-228 278.95 / 880.76 keV,
I_i P(j | i) = 8.07739e-6 against I_j P(i | j) = 3.132671e-7 (ratio 25.78435). Of the 98 table records
with `gs`, 65 have `gs / g` varying by more than 5 % between gammas.

## Change

1. `coincidence.coi` reports two new quantities and a state; the correction itself (factor,
   summing-out, summing-in, `ignored`, `found`, `reason`, annihilation, note) is unchanged:
   - `inconsistent`: emission-weighted sum over the line's upward partners j of
     |P(j | i) with `gs` - P(j | i) with `g`|, i.e. how much the line's upward coincidence probability
     depends on the choice between the two intensity sets (0 where `gs` = `g` or no `gs`). The line
     above in such a pair uses only its downward branching, which does not depend on intensities.
   - `partial` = `ignored` > 0.01 or `inconsistent` > 0.01 (PARTIAL_LIMIT, the 1 % already used for
     the activity note on `ignored`), with `partial_reason` naming the cause(s) and the fraction.
2. Activity: a corrected line whose correction is partial gets `coi_partial` True and the note
   `partial_reason` (in place of the note "coincident photons below the efficiency curve left out",
   which it contains); the nuclide note names the lines with a partial correction. Activities,
   uncertainties, limits and `coi_applied` are unchanged: the first-order factor is still applied,
   as before, and is now reported as partial.
3. Calibration (`summing_free_curve`): a cascade point whose correction is partial is refused like a
   point the table cannot treat (ValueError naming the points, "partial"), so a curve is not labelled
   summing-corrected with partners missing. The user excludes the points, extends the calibration to
   lower energies, or declares the curve free of summing.
4. Nothing else: no change of efficiencies or factors, of the table, or of the 0.8 x e_min rule.

The X-ray coincidences of EC nuclides, absent from the table, are not part of this change (stated
limit of the table since the TCS work; no measured low-energy response is available here).

Engine version 1.24.0 (calibrations that were corrected before can now be refused). Harness
`validation/round5_tcs.py`, fixed output folder `after_R5E`; values before the change recorded with
`--collect` into `after_R5E/round5_tcs_before.json` (engine 1.23.0, e59eff8), committed with this
protocol.

## Cases (synthetic)

- Examples: Ba-133 356.0129 keV (flat efficiency 0.02, P/T 0.24) with e_min 50 and 122 keV; Ac-228
  880.76, 338.32, 911.204, 968.971 and 278.95 keV (e_min 40 keV).
- All lines: every gamma of every nuclide of the coincidence table (29228 evaluations: two curves,
  flat 0.02 and a close geometry 0.02 (E / 1 MeV)^-0.85 from 59.5 keV; e_min 40 and 122 keV; P/T
  0.24).
- Calibration (loglog order 2, efficiency 0.03 (E / 300 keV)^-0.7, P/T 0.24, u(P/T) 10 %): Eu-152
  (8 lines) with Ba-133 276-384 keV (lowest point 121.8 keV); Eu-152 with Ba-133 53-384 keV (lowest
  point 53.2 keV); Eu-152 only.
- Activity: Ba-133, net areas 5000 / 1500 / 600 / 600 counts at 356.0 / 302.9 / 383.8 / 276.4 keV,
  "mean" method, TCS on (P/T 0.24, u 10 %), flat manual curve 1 % from 50 keV and from 122 keV.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RE.C1 | Ba-133 356.0129 keV | e_min 122: partial, `partial_reason` names the partners below the efficiency curve; e_min 50: not partial, no reason; correction values identical to before (==) in both |
| RE.C2 | Ac-228 | 880.76 and 338.32 keV partial, the reason of 880.76 names the intensities; 911.204 and 968.971 keV not partial; correction values of the five lines identical to before (==) |
| RE.C3 | all 29228 line evaluations | correction values identical to before (==) for every one; number of partial lines reported |
| RE.C4 | calibration | from 121.8 keV with Ba-133: refused, message names Ba-133 and "partial" (before: corrected); from 53.2 keV and Eu-152 only: result identical to before (==) |
| RE.C5 | activity | activity, uncertainty and every line's COI, applied flag, COI uncertainty and activity identical to before (==); from 122 keV: every corrected line partial and named in its note, the nuclide note says "partial"; from 50 keV: no line partial, no "partial" in the note |
| RE.C6 | benchmark (`after_R5D`: 154 PASS / 13 FAIL / 60 REPORT), IAEA 2002 check, full test suite | no benchmark criterion changes state; IAEA 2002 check: criteria and activities identical to its run before the change; suite passes, each changed existing test listed with its reason |

Before the change: RE.C1, RE.C2, RE.C4 and RE.C5 fail (no partial state; the calibration from
121.8 keV is corrected); RE.C3 is the control.

## Limits of this change (stated now)

- The partial state says that the first-order correction is incomplete; it does not estimate the
  missing loss (the efficiency below the curve is unknown) and adds no uncertainty for it.
- `inconsistent` measures the dependence on the intensity set, not which set is right; the decay
  schemes themselves are not audited here.
- The 1 % limit is a reporting threshold on probabilities, not on the effect on the activity (that
  is the probability times an unknown total efficiency).

---

## Results, first rule (`after_R5E`)

Protocol committed in d6d51cc before the change (SHA-256 of the file
ad52468e8b5917d0cb568dd43ff47d1bb121b3850f1e6fe6bacc99d1bf8b6c46). Engine 1.24.0.

**First run: 3 PASS / 2 FAIL (RE.C6 not evaluated). The first rule is not shipped.**

| ID | value | result |
|---|---|---|
| RE.C1 | Ba-133 356 keV, e_min 122: partial, "coincident photons below the efficiency curve left out (37 % of decays)", factor 1.0; e_min 50: not partial, factor 0.9703591; values identical to before | PASS |
| RE.C2 | Ac-228 880.76 partial (`inconsistent` 1.2049), 338.32 partial (0.1112), 911.204 and 968.971 not partial (5.8e-5); values identical | PASS |
| RE.C3 | 29228 evaluations, correction changed for 0; 4646 partial | PASS |
| RE.C4 | from 121.8 keV with Ba-133: refused as registered; but from 53.2 keV also refused (before: corrected): Ba-133 81.0 keV `inconsistent` 0.0118 | FAIL |
| RE.C5 | values identical; from 122 keV all four lines partial and named; but from 50 keV the Ba-133 81.0 keV line (no peak) partial | FAIL |

**Cause.** Ba-133 81.0 keV: its upward coincidence probability is 0.0118 apart between the two
intensity sets, above the limit 0.01 on that probability. The survey written in the protocol (65 of
98 records) did not include this line; the criteria expected the 53.2 keV calibration unchanged. The
rule as written refuses a Ba-133 calibration with its 81 keV point for a dependence of the factor of
about 0.1 % (0.0118 x total efficiency 0.083 in the flat case).

# Round-8 review: calibration points already corrected for true-coincidence summing on a curve not marked corrected, Gemini M1 (pre-registered)

Written 2026-10-30, before any change to the code. Gemini round-8 review
(`C:\Users\DELL\Downloads\gemini_review_round8.md`, main 384e89d), finding M1, checked on the code
(`analysis/efficiency.py` `summing_free_curve`, `_summing_state`, `_cascade_points`,
`fit_efficiency`; main 6ba72d7) and measured before this protocol was written.

## Finding

**`summing_free_curve` divides by the COI again points that already carry it (Gemini M1,
confirmed).** A curve's summing state is kept through a refit from its points
(`round7_tcs_refit_protocol.md`), but only the points in use count (`_cascade_points`). If the
corrected cascade points of a curve are excluded and the curve refitted, it is not marked corrected
(right: no point in its fit carries a correction); if they are then included again without a refit,
`summing_free_curve` sees a curve not marked corrected with cascade points in use and divides their
efficiencies, already divided by their COI, by the COI once more, adding the COI uncertainty a
second time. Measured (Eu-152 calibration corrected for summing, PT(E) = 0.24, 10 %, plus seven
points of nuclides without cascades; the Eu-152 points excluded, refitted, included again):
the 121.78 keV point 0.060915 -> 0.065826 (+8.06 %), the curve at 121.78 keV 0.06480 against 0.06134
for an explicit refit of the same points; the Cs-137 activity with the summing correction 64.37 +-
10.22 Bq against 65.21 +- 4.52 Bq. With corrected and uncorrected cascade points in use together
(here a raw Co-60 point added) the uncorrected ones are corrected and the corrected ones corrected
twice, with no refusal; `fit_efficiency` refuses that mix.

These measurements were made with exploratory scripts and the new harness's `--collect` run before
this protocol; no value after a change was seen.

## Change

1. `summing_free_curve`, after its existing early returns (curve marked corrected, declared free):
   when the cascade points in use already carry a correction (`summing_coi` set), the curve is
   refitted on its points as they are, without a new correction, exactly as `fit_efficiency` with
   the curve's own model and options would (`fit_efficiency` then marks it corrected from the points
   and names their partial corrections). A mix of corrected and uncorrected cascade points in use is
   refused with `fit_efficiency`'s message. The note says "cascade-emitter calibration points
   already corrected for true-coincidence summing: curve refitted on them, not corrected again".
2. `compute_activities` reports that note as it is (not "with the same peak-to-total").
3. Unchanged: curves marked corrected, declared free, without cascade points in use, with only
   uncorrected cascade points (the correction as before).
4. ENGINE_VERSION becomes 1.33.0.

Harness `validation/round8_coi_guard.py` (`--rerun` writes to a fixed temporary folder), fixed
output folder `after_R8C`; values before the change recorded with `--collect` into
`after_R8C/round8_coi_guard_before.json` (engine 1.31.0, 6ba72d7), committed with this protocol.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RC8.C1 | Gemini's sequence (above) | `summing_free_curve` returns every point identical to its input, the curve marked corrected, its efficiency at 20 energies 60-1800 keV and 121.78 keV equal to the explicit refit `fit_efficiency` of the same points (relative 1e-12), the same partial corrections |
| RC8.C2 | the Cs-137 activity with the summing correction on that curve | activity, uncertainty and MDA equal to those with the explicit refit (relative 1e-12); the notes say "not corrected again" |
| RC8.C3 | corrected and uncorrected cascade points in use together | refused (ValueError) |
| RC8.C4 | controls: the uncorrected curve, the corrected curve, the curve with the Eu-152 points excluded, the explicit refit, the declared-free curve; their activities | identical to before (every curve field, the efficiencies, the notes) |
| RC8.C5 | benchmark (`after_R8B2`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes and exits 0; each changed existing test listed with its reason |

Before the change: RC8.C1, RC8.C2 and RC8.C3 fail; RC8.C4 is the control.

## Limitations

- The points keep the correction computed with the peak-to-total ratio of the earlier correction;
  a different peak-to-total for the sample is not applied to them again (the correction of the
  sample's own lines uses the new one).
- A curve whose stored fit does not match its points' use flags is refitted; its earlier
  coefficients are not kept.
- Synthetic Eu-152 calibration; the sequence is reachable through the API and saved curves, the
  efficiency dialog refits on every change of the points.

---

## Results (`after_R8C`)

Protocol committed in 4435773 before the change (SHA-256 of the file
32198ab2626bd852d0cf09ddf90110455c8425003839cf8233de485ac23755b5; before file
`after_R8C/round8_coi_guard_before.json` a25fad245d4e28158bcfbbff9abd0fb1ea7d771fc99da5abfdae64b7de01b39d).

Harness errors before the result (disclosed; no criterion or limit changed):
1. The first evaluation stopped with a KeyError: `EfficiencyCurve.to_dict` leaves out an empty
   `tcs_partial`; the harness now reads it with an empty default.
2. The next run gave 3 PASS / 1 FAIL (kept in `after_R8C/first_run_harness_error/`): RC8.C4 failed
   on every control only through the curves' `date` field, the time of the fit in minutes
   (09:32 before, 09:34 after), which is not a result. The harness now leaves `date` out of the
   comparison on both sides.

Run after these fixes: 4 PASS / 0 FAIL.

| ID | value | result |
|---|---|---|
| RC8.C1 | Eu-152 121.78 keV point: input 0.060915; before 0.065826 (+8.06 %), curve 0.064797; now 0.060915 (unchanged), curve 0.061342, marked corrected; explicit refit 0.061342 | PASS |
| RC8.C2 | Cs-137 activity with the summing correction: before 64.366 Bq, now 65.210 Bq, explicit refit 65.210 Bq; note "not corrected again" | PASS |
| RC8.C3 | corrected Eu-152 points with an uncorrected Co-60 1173.2 keV point: before corrected without refusal; now refused with `fit_efficiency`'s message | PASS |
| RC8.C4 | uncorrected, corrected, excluded, explicitly refitted and declared-free curves and their activities identical to before | PASS |
| RC8.C5 | benchmark 154 PASS / 13 FAIL / 60 REPORT, no criterion changed state against `after_R8A`; full suite 1748 passed, 69 skipped, exit 0; no existing test changed | PASS |

New tests: `tests/test_round8_coi_guard.py` (4); on the code before the change (4435773) all 4 fail
(three on the defect, the fourth because the note constant `TCS_ALREADY_CORRECTED` is new).
ENGINE_VERSION 1.33.0 (after 1.32.0 of R8-B, merged in). Re-run after merging main (R8-B):
4 PASS / 0 FAIL. The manual sources say that corrected points excluded and included again are
refitted as they are.

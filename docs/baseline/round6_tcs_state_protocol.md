# Round-6 review: the partial summing correction state of an efficiency curve, H3 and L1 (pre-registered)

Written 2026-10-28, before any change to the code. Codex round-6 review
(`C:\Users\DELL\Downloads\codex_review_round6.md`, main 624e199), findings H3 and L1, checked on the
code (`analysis/efficiency.py` `summing_free_curve`, `analysis/activity.py` `compute_activities`,
`lab/workflow.py` `report_record`, `analysis/coincidence.py` `coi`, main c7cfd73) and reproduced by
the harness below before this protocol was written.

**Finding H3.** Round 5 (`round5_tcs_protocol.md`, second amendment) accepts a calibration whose
cascade-emitter points can only be partly corrected for true-coincidence summing (partners below the
curve, inconsistent decay scheme) and names those points in the curve's note and warnings. The state
exists only as text. `summing_free_curve` returns a curve that is already corrected unchanged, and
`compute_activities` adds its "efficiency curve: ..." note only when it refits the curve in the same
call. So a corrected curve that is saved and loaded again (the usual case) gives results whose notes
do not mention the partial correction, and the report's calibration summary (`report_record`) carries
neither the curve's note nor its warnings. Reproduced (harness: Eu-152 and Ba-133 points from
121.8 keV, loglog order 2, P/T 0.24 +- 10 %, corrected, saved and loaded again, then a Cs-137 sample):
the corrected curve names Ba-133 276.4, 302.9, 356 and 383.8 keV as partial; with the loaded curve the
result notes (with or without summing correction of the sample), the Cs-137 note and the report's
calibration summary do not mention it. The efficiency of the whole fit depends on these points, so
the restriction concerns every result of the curve, not only cascade lines of the sample.

**Finding L1.** The partial reason says "coincident photons below the efficiency curve left out
(37 % of decays)". The quantity (`Coi.ignored`) is the expected number of coincident partner photons
below the curve per emission of the line (a sum of conditional probabilities, which can exceed 1),
not a fraction of decays.

## Change

1. `EfficiencyCurve` gains `tcs_partial`: a list of `[nuclide, energy keV, reason]`, one per
   calibration point whose summing correction is partial, set by `summing_free_curve` and saved with
   the curve (left out of the saved file when empty, so curves without it keep their content and
   hash). A curve saved by engine 1.25.0 or earlier (no such key) recovers the list from its note
   ("partial correction for ...") and its warnings.
2. `compute_activities`: whenever the curve used (corrected in this call or loaded already corrected,
   with or without the sample's own summing correction) has `tcs_partial`, the results gain the field
   `curve_tcs_partial` (the list) and one note naming every partial point; each nuclide result gains
   the note "efficiency curve with a partial true-coincidence summing correction". The note of a curve
   corrected in this call no longer repeats the partial points.
3. `report_record`: each calibration summary adds the curve's `note`, `warnings` and `tcs_partial`
   from its payload; the report's results add `curve_tcs_partial`. `workflow_status` adds one review
   warning (`outside_validated_scope`) naming the partial points (from the results, else from the
   efficiency calibrations).
4. L1 wording: "coincident photons below the efficiency curve left out (on average {ignored:.2g} per
   emission of this line)". The quantity, the limit (0.01) and the factors are unchanged.
5. Engine version 1.26.0: notes and fields of the results change (no number).

Harness `validation/round6_tcs_state.py`, fixed output folder `after_R6E`; values before the change
recorded with `--collect` into `after_R6E/round6_tcs_state_before.json` (engine 1.25.0, c7cfd73),
committed with this protocol.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RE.C1 | `tcs_partial` of the corrected Eu/Ba curve; after save and load; from a file without the key (1.25.0); uncorrected curve and Eu-only curve | non-empty, the same points as its partial warnings; equal after load and from the old file; empty for the others |
| RE.C2 | results of Cs-137 with the Eu/Ba curve: corrected in the call (summing on), loaded (summing on and off), old file (summing off) | `curve_tcs_partial` equal to the curve's list; each partial point named in exactly one result note; the Cs-137 note names the partial correction. Controls (Eu-only curve, corrected in the call and loaded): no field, notes identical to before |
| RE.C3 | report record of the same four cases | report results carry the list; for the saved curves the calibration summary carries the list, the note and the warnings; exactly one review status names every partial point; controls without any of them |
| RE.C4 | partial reason of Ba-133 356.0129 keV, flat curve, e_min 122 keV | no "% of decays"; states ignored to 2 significant figures "per emission"; factor and ignored as before |
| RE.C5 | activity, uncertainty, decision threshold, detection limit, detection and each line (energy, COI, applied, efficiency, activity) of the six cases; efficiency at 500 keV of the eight curves; round-5 calibration points and Ba-133 activity cases (`round5_tcs`) | identical to before |
| RE.C6 | benchmark (`after_R6D`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes, each changed existing test listed with its reason |

Before the change: RE.C1 (no field), RE.C2 (no field, the points named only in the call that
corrects), RE.C3 and RE.C4 fail; RE.C5 is the control.

## Limitations

- The state is a label: the summing loss left out at the partial points is not estimated (Codex,
  round 6 section on partial). Results stay computable with such a curve; the warning goes to the
  review.
- Old curves recover the list from their text only if the note and warnings are as written since round 5
  (up to engine 1.25.0); a curve edited by hand may not.
- `round5_tcs` outputs containing the partial reason change wording (only the text).

---

## Results (`after_R6E`)

Protocol committed in fb3f5c8 before the change (SHA-256 of the file
d5a40154e15df3259e8309ea26af38213ff3268f6699782517ce1815776e2c88). Engine 1.26.0.

**First run: 6 PASS / 0 FAIL.**

| ID | value | result |
|---|---|---|
| RE.C1 | Ba-133 276.4, 302.9, 356 and 383.8 keV, the same as the partial warnings; equal after save and load and from a file without the key; empty for the uncorrected and the Eu-only curves (before: no field) | PASS |
| RE.C2 | the four cases carry `curve_tcs_partial`, each point named in one result note, the Cs-137 note names the partial correction; controls unchanged (before: named only in the call that corrects) | PASS |
| RE.C3 | report results carry the list, calibration summaries of the saved curves the list, note and warnings; one review status names the four points; controls without them | PASS |
| RE.C4 | "coincident photons below the efficiency curve left out (on average 0.37 per emission of this line)", ignored 0.369959, factor 1 as before (before: "37 % of decays") | PASS |
| RE.C5 | activities, uncertainties, limits, detection, COI factors and efficiencies of all cases and curves, round-5 calibration points and Ba-133 activities identical to before | PASS |
| RE.C6 | benchmark (engine 1.26.0) 154 PASS / 13 FAIL / 60 REPORT, no criterion changed state against `after_R6D`; full suite 1577 passed, 69 skipped; no existing test changed | PASS |

RE.C6 is evaluated outside the harness (benchmark compared criterion by criterion with `after_R6D`).

Also changed: the manuals (sources): the partial points stay with a saved curve and reach the results,
the report and the review; the partner photons below the curve are an average number per emission,
not a fraction of decays (the same wording defect as L1).

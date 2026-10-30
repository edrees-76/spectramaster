# Round-9 review: summing state of efficiency curves saved by engine 1.26.0 and earlier, Codex H1 (pre-registered)

Written 2026-10-30, before any change to the code. Codex round-9 review
(`C:\Users\DELL\Downloads\codex_review_round9.md`, main 5de3b03), finding H1, checked on the code
(`analysis/efficiency.py` `EfficiencyCurve.from_dict`, `_legacy_summing_points`, `_cascade_points`,
`summing_free_curve`; main 5de3b03) and measured with the new harness's `--collect` before this
protocol was written.

## Finding

**A curve saved by engine 1.26.0 or earlier whose summing state was lost by a refit of those
engines is corrected again (Codex H1, confirmed).** Before engine 1.27.0 (round7_tcs_refit_protocol.md)
the summing state lived only in the curve flag `summing_corrected`; a refit lost it while the point
efficiencies stayed divided by their COI, with "summing corrected, COI x" in the point notes. The
per-point fields `summing_coi` / `summing_partial` of 1.27.0 are rebuilt for old files only when the
flag is set (`from_dict` -> `_legacy_summing_points`), and only for points in use
(`_cascade_points`). So:

1. A lost-flag file (flag False, corrected values and notes) loads with no point marked corrected,
   and `summing_free_curve` divides the points by their COI a second time. Measured (the round-8
   COI-guard Eu-152 calibration plus seven non-cascade points, PT 0.24 +- 10 %): the curve at
   121.78 keV 0.0647965 against 0.0613416 for a refit of the same points as they are (+5.6 %; the
   121.78 keV point +8.06 %); the same for such a file opened and saved again by 1.27.0-1.34.0
   (fields written as None).
2. A file marked corrected with corrected points excluded: the excluded points get no fields; included
   again and refitted, the fit is refused as a mix of corrected and uncorrected points.
3. A lost-flag file plus an uncorrected cascade point in use (which points are corrected cannot be
   decided from the flag): corrected once more without refusal.

## Change

1. On loading a curve (`from_dict`), when no cascade point (in use or not, not manual) carries
   `summing_coi`, the fields are rebuilt from the point notes for every such point, whatever the curve
   flag: a point whose note has "summing corrected, COI x" gets `summing_coi = x`; a point in use
   without such a note on a curve marked corrected gets 1.0 (as before: a point the correction found
   no cascade for); other points stay uncorrected. The partial reason is taken from `tcs_partial` as
   before.
2. The existing rules then apply unchanged: `summing_free_curve` refits a curve whose cascade points
   in use carry a correction as they are (round8_coi_guard_protocol.md), and refuses a mix of corrected
   and uncorrected cascade points in use.
3. Unchanged: files with per-point fields set, legacy files marked corrected with all corrected points
   in use, uncorrected files without COI notes.
4. ENGINE_VERSION becomes 1.35.0.

Harness `validation/round9_legacy_tcs.py` (`--rerun` writes to a fixed temporary folder), fixed
output folder `after_R9A`; values before the change recorded with `--collect` into
`after_R9A/round9_legacy_tcs_before.json` (engine 1.34.0), committed with this protocol.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RA9.C1 | lost-flag file, as saved by 1.26.0 and re-saved by 1.27.0-1.34.0 | `summing_free_curve` marks it corrected; its efficiency at 20 energies 60-1800 keV and 121.78 keV equals the refit of the loaded points as they are (relative 1e-12); the Cs-137 activity, uncertainty and MDA with the summing correction equal those with that refit (relative 1e-12) |
| RA9.C2 | file marked corrected with two corrected points excluded | the loaded points' `summing_coi` equal those of the same curve saved by the current engine; all points included again and refitted: not refused, marked corrected, efficiencies equal to the current engine's file (relative 1e-12) |
| RA9.C3 | lost-flag file plus an uncorrected cascade point in use | `summing_free_curve` refuses (ValueError) |
| RA9.C4 | controls: legacy file marked corrected (all used), legacy uncorrected file, current-engine corrected, excluded and uncorrected files | loaded state, `summing_free_curve` result and activity identical to before (fit dates excluded) |
| RA9.C5 | benchmark (`after_R8H`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes and exits 0; each changed existing test listed with its reason |

Before the change (collect run): RA9.C1, RA9.C2 and RA9.C3 fail; RA9.C4 is the control.

## Limitations

- A lost-flag file's partial-correction reasons are lost with its flag (its `tcs_partial` was emptied
  by the old refit); its points are restored as corrected without the partial warning.
- The COI read from a note has the note's 4 decimals; it marks the state, the efficiencies are the
  stored ones.
- A point note edited by hand to contain or remove "summing corrected, COI" changes the restored state.

# Round-7 review: summing state of an efficiency curve kept through a refit, H1 (pre-registered)

Written 2026-10-29, before any change to the code. Codex and Gemini round-7 reviews
(`C:\Users\DELL\Downloads\codex_review_round7.md`, `gemini_review_round7.md`, main b3d88d1), finding H1
of both, checked on the code (`analysis/efficiency.py` `fit_efficiency`, `summing_free_curve`;
`gui/efficiency_dialog.py` `refit`, `load_curve`) and reproduced before this protocol was written.

**Finding.** `summing_free_curve` divides the cascade-emitter calibration points by their COI, refits,
and marks the result `summing_corrected` with its `tcs_partial` list. Those two fields are set on the
curve only. `fit_efficiency` always returns `summing_corrected = False` and `tcs_partial = []`, so a
corrected curve refitted from its own points (the efficiency dialog's *Refit* after loading it, or any
caller) loses both while its points stay corrected. Reproduced on the round-6 example (Eu-152 and
Ba-133 from 121.8 keV, `round6_tcs_state._curves()`): the corrected curve has `summing_corrected` True
and 4 partial points; `fit_efficiency(list(c.points), c.model, order=c.order)` gives False and [], with
the same efficiencies. Then:

- with the sample's summing correction off, the partial warning disappears from results, report and
  review;
- with it on, the points are corrected a second time: Cs-137 67.8844 Bq becomes 69.0339 Bq (+1.69 %,
  Codex's numbers, both reports).

## Change

1. `EfficiencyPoint` gets two fields: `summing_coi` (None, or the COI the point was divided by) and
   `summing_partial` ("", or the reason its correction is partial). `summing_free_curve` sets them on
   every cascade-emitter point it treats, `summing_coi = 1.0` for a point without coincident partners.
2. `fit_efficiency` derives the state from the points it fits. Cascade points are the used, non-manual
   points of a nuclide with cascades, as in `summing_free_curve`:
   - every cascade point has `summing_coi`: `summing_corrected = True`, `tcs_partial` from their
     `summing_partial`, in the format and order `summing_free_curve` gives;
   - none has it: unchanged (False, []);
   - some have it and some not: `ValueError` naming the uncorrected points. Mixing corrected and
     uncorrected cascade points cannot be fitted as one calibration, and either reading of the result
     is wrong.
   No other number of the fit changes.
3. Saved curves: the two point fields are written only when set, so a curve without a summing
   correction keeps its file content. A curve saved by engine 1.26.0 and earlier with
   `summing_corrected` gets them on loading: `summing_coi` from the point note
   ("summing corrected, COI x", otherwise 1.0 for a cascade point) and `summing_partial` from its
   `tcs_partial`. It then refits as a corrected curve.
4. Nothing in the efficiency dialog changes: its *Refit* calls `fit_efficiency` with the shown points,
   and its error message shows the `ValueError` of item 2.
5. ENGINE_VERSION becomes 1.27.0: a refitted corrected curve now keeps its state, so with the
   sample's summing correction on, the activities change (no second correction).

Harness `validation/round7_tcs_refit.py`, fixed output folder `after_R7A`; values before the change
recorded with `--collect` into `after_R7A/round7_tcs_refit_before.json` (engine 1.26.0, b3d88d1),
committed with this protocol.

## Criteria

Example of round 6: corrected curves `eu_ba_121.8` (4 partial points) and `eu_only` (none);
Cs-137 sample of `round6_tcs_state`.

| ID | quantity | limit |
|---|---|---|
| RA.C1 | each corrected curve refitted with `fit_efficiency` from its own points, same model and orders | `summing_corrected` True, `tcs_partial` equal to the source's, efficiencies at 20 energies within 1e-12 relative |
| RA.C2 | Cs-137 activity, u and MDA, with and without the sample's summing correction, from the refitted curve | equal to those of the source curve within 1e-12 relative (before: 69.0339 Bq with the correction); partial note present without the correction exactly as with the source |
| RA.C3 | the efficiency dialog (offscreen): load the saved corrected curve, *Refit*, keep the curve | as RA.C1, and the saved file loads with the same state |
| RA.C4 | corrected curve plus one raw cascade point (Co-60 1332.5 keV), and plus one raw non-cascade point (Cs-137 661.7 keV) | the first refit refused, the message naming Co-60 1332.5 keV; the second fitted with the state kept |
| RA.C5 | saved files: uncorrected curves (raw `eu_ba_121.8`, raw `eu_only`) and a 1.26.0 corrected curve (its `to_dict` recorded before the change) | uncorrected: `to_dict` identical to before (except `date`, the time of the fit); legacy corrected: loads with `summing_coi` and `summing_partial` set, refits as RA.C1 |
| RA.C6 | uncorrected curves, curves without cascade points, and `round6_tcs_state` cases | every number identical to before |
| RA.C7 | benchmark (`after_R6G`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes, each changed existing test listed with its reason |

Before the change: RA.C1 to RA.C5 fail (state lost on refit, mixed points accepted, no point fields);
RA.C6 is the control.

## Limitations

- Synthetic calibration points and the bundled coincidence table only.
- A refit keeps the correction of the shown points; it does not recompute the COI with the new curve.
  The COI depends on the curve, but only weakly (`summing_free_curve` iterates to 1e-4), and a new
  correction needs the raw points, which a corrected curve no longer holds.
- An imported curve with no calibration points is not concerned: it cannot be refitted.

# Round-8 review: the limits of a nuclide whose primary result comes from another line, Codex H1 / Gemini H1 (pre-registered)

Written 2026-10-30, before any change to the code. Codex and Gemini round-8 reviews
(`C:\Users\DELL\Downloads\codex_review_round8.md`, `gemini_review_round8.md`, main 384e89d),
findings Codex H1 and Gemini H1, checked on the code (`analysis/activity.py` `_combine`,
`_combine_activity`, `_window_primary`; `gui/quant_panel.py` `_primary_text`, main 384e89d) and
measured before this protocol was written.

## Findings

1. **The nuclide keeps the limits of a key line it does not use (Codex H1, Gemini H1 part b,
   confirmed).** For a nuclide not detected whose key line has no usable window result (method
   "interfered" or "curved"), `_combine` takes the primary result from another usable line (the
   usable line of smallest MDA, or with `method = "mean"` the only usable line;
   `round4_primary_protocol.md`). That protocol kept "the activity, the detection decision, the
   decision threshold and the MDA" of the key line (`_combine_activity`). Since
   `round7_combined_protocol.md` (R7-B) a not-detected weighted mean reports the limits of the mean
   itself, so the nuclide's limits now follow the estimator of its primary result except in this
   case, where the decision threshold and MDA are those of a window that was not used. Measured
   (HPGe, flat efficiency, Co-60 absent, an interfering peak at 1176.5 keV, seed 0, Currie): key
   line 1173.2 keV interfered, threshold 2.876 Bq, MDA 5.882 Bq; the 1332.5 keV line gives the
   primary result, threshold 1.703 Bq, MDA 3.553 Bq; the nuclide reports 2.876 / 5.882 Bq.
2. **Gemini H1 part a is not a defect (checked).** With no usable line the nuclide keeps the key
   line's window result with its method "interfered" or "curved" and no best estimate; that is the
   registered rule (`round4_primary_protocol.md`, "when no line is usable, the key line's result as
   before"), and the results table marks an interfered result as not used. The covariance of the
   shared background that such a line carries belongs to the result shown.
3. **A "curved" primary result is shown without its mark (found while checking 2).** The table and
   report text of a not-detected primary result (`quant_panel._primary_text`) adds "(window overlaps
   another peak: not used)" for "interfered" only; a "curved" result (continuum too curved for
   the window estimator) is shown like a usable one.

These measurements were made with exploratory scripts and the new harness's `--collect` run before
this protocol; no value after a change was seen.

## Change

1. `_combine`: when the primary result of a nuclide not detected is taken from a usable line other
   than the key line, the nuclide's `decision_threshold` and `mda` become that line's (its own,
   quadratic when it is on the quadratic window, `round7_quad_limits_protocol.md`); the specific MDA
   follows (it is computed from the MDA). The note names the line: "primary result and limits from
   the X keV line (key line Y keV: method)". `key_energy`, the primary result, its uncertainty, the
   detection decision, the lines and every other case do not change: detected nuclides, a usable
   key line, the weighted mean of two or more usable lines, no usable line.
2. `quant_panel._primary_text`: a "curved" primary result is marked "(continuum too curved for the
   window: not used)" (Arabic and English), like an "interfered" one.
3. ENGINE_VERSION becomes 1.31.0.

Harness `validation/round8_alt_limits.py` (with `--out DIR`), fixed output folder `after_R8A`;
values before the change recorded with `--collect` into `after_R8A/round8_alt_limits_before.json`
(engine 1.30.0, 384e89d), committed with this protocol.

## Criteria

Cases (synthetic, Co-60 asked, flat efficiency, quantity 0.5 kg, Currie and ISO 11929 each):
HPGe base continuum with an interfering peak (SNR 30) at 1176.5 keV, seeds 0 and 1 `method = "key"`,
seed 0 `method = "mean"`; HPGe with the Compton edge of a 1390 keV line (level 40) `key` (key line
interfered by a false search peak); NaI with the edge of a 1550 keV line (level 40) `key`, both lines
curved (no usable line). Controls: HPGe with the interfering peak at 1180 keV (both lines usable),
seed 0 `key` and `mean`; HPGe base continuum without a peak, seed 3; NaI with the Co-60 peaks
(detected), seed 7.

| ID | quantity | limit |
|---|---|---|
| RA8.C1 | the four substitution cases, both methods | key line not usable, one usable line; the nuclide's threshold and MDA equal that line's (exactly), the specific MDA equals its MDA / 0.5 kg (relative 1e-12); key energy, primary result and its uncertainty as before; not detected; the note says "limits from the X keV line" |
| RA8.C2 | the same cases before the change | the nuclide reported the key line's threshold and MDA, which differ from the used line's (documents the finding) |
| RA8.C3 | no usable line, both methods | method "curved", every value and note identical to before |
| RA8.C4 | controls: every case | every line field and the notes identical to before; every nuclide field identical except, in the substitution cases, the threshold, MDA, specific MDA and note |
| RA8.C5 | benchmark (`after_R7G`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes and exits 0; each changed existing test listed with its reason |
| RA8.C6 | `_primary_text` (test) | a "curved" primary result carries its mark in Arabic and English; an "interfered" one as before; a usable one without a mark |

Before the change: RA8.C1 and RA8.C6 fail; RA8.C2, RA8.C3 and RA8.C4 are the controls.

## Limitations

- Synthetic spectra; the interfering and edge cases are chosen to reach the substitution path, not
  representative of a laboratory's rate of it.
- The usable line replacing the key line is the one the existing rule chooses (smallest MDA); the
  reported MDA is then smaller than the key line's. It is the MDA of the estimator whose result is
  reported, not a minimum over lines chosen after seeing the data.
- With no usable line the reported limits stay those of the key line, whose window was not used;
  the primary result is marked as not used, and no best estimate is given.
- Correlations between the lines of a nuclide (overlapping windows, Gemini M3) are not in this
  change.

---

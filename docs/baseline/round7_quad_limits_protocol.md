# Round-7 review: the limits of a line on the quadratic window, Gemini H3 (pre-registered)

Written 2026-10-29, before any change to the code. Gemini round-7 review
(`C:\Users\DELL\Downloads\gemini_review_round7.md`, main b3d88d1), finding H3, checked on the code
(`analysis/activity.py` `compute_activities` line loop, `quad_limits`, `_window_primary`, `_combine`,
`combined_limits`, main 3cd2aa7) and measured before this protocol was written.

## Findings

**Gemini H3: the reported limits of a quadratic-window line are the linear ones.** A line without a
search peak whose linear window is too curved gets a quadratic continuum over wider sides
(`window_polynomial_protocol.md`, engine 1.9.0). Its own decision threshold is computed
(`quad_limits`) and decides detection, but by design of that protocol (change 4) the line's
reported `decision_threshold`, `lc_counts`, `ld_counts` and `mda` stayed the linear ones, and the
quadratic detection limit was discarded. The nuclide takes its limits from those fields (key line,
or `combined_limits` of the window lines for `method = "mean"`), so the nuclide's threshold and MDA
are those of an estimator that was not used, and smaller than those of the one that was.

Measured on the code (NaI, Co-60 spectrum on the base continuum of `scenarios`, Cs-137 661.7 keV
absent, flat efficiency, Currie): with seed 7 the reported threshold is 8.559 Bq and the MDA
17.20 Bq, the quadratic threshold 9.931 Bq and its detection limit (Currie formula) 19.94 Bq; over
200 realisations (seeds 1000 + i; 195 on the quadratic window) the reported threshold is 0.881 x
k sigma of the line's primary result under the null hypothesis, the quadratic one 1.02 x, and 6.2 %
of the primary results exceed the reported threshold (nominal 5 %). Ba-133 (`method = "mean"`, four
of six lines quadratic) inherits the linear limits through `combined_limits`.

These measurements were made with exploratory scripts outside the repository before this protocol;
no value after a change was seen.

## Change

1. A line whose primary result is the quadratic window (`window_continuum == "quadratic"`,
   `primary_method == "window"`) reports the limits of that window: `lc_counts`, `ld_counts`,
   `decision_threshold` and `mda` are those returned by `quad_limits` (Currie or ISO 11929, the
   same formulas as every line, from the quadratic window's sigma0). `window_lc_counts` and
   `window_decision_threshold` keep their values (equal to the reported ones for such a line).
2. The nuclide's limits follow without other change: key line, or `combined_limits` of the window
   lines with these line limits.
3. Nothing else changes: lines with a search peak, linear windows, lines whose window is
   interfered or too curved for a polynomial window (they keep the linear limits, as before), the
   primary result, its uncertainty, the detection decision and the notes. ENGINE_VERSION becomes
   1.30.0.

Harness `validation/round7_quad_limits.py`, fixed output folder `after_R7D`; values before the change
recorded with `--collect` into `after_R7D/round7_quad_limits_before.json` (engine 1.29.0, 3cd2aa7),
committed with this protocol.

## Criteria

Cases (synthetic, seed 7 unless stated, Currie and ISO 11929 each): NaI Cs-137 (quadratic window),
NaI Ba-133 `method = "mean"`, HPGe Cs-137 (linear window), NaI Co-60 (search peaks), NaI Cs-137 on the
Compton-edge continuum of `primary.edge_continuum`, seed 0 (window not used). "Expected" limits are
recomputed in the harness from the quadratic L_C and decision threshold with `currie_limits` /
`iso11929_limits` (checked before the change to reproduce the engine's linear limits within 1e-15).

| ID | quantity | limit |
|---|---|---|
| RD.C1 | NaI Cs-137, both methods | `lc_counts` and `decision_threshold` equal `window_lc_counts` and `window_decision_threshold` (relative 1e-12), the latter unchanged from before; `ld_counts` and `mda` equal the expected ones (relative 1e-9) |
| RD.C2 | nuclide limits, both methods | Cs-137: equal to the quadratic window's threshold (1e-12) and expected MDA (1e-9); Ba-133 mean: equal to `combined_limits` of the window lines with the quadratic lines' own limits (1e-9), at least two quadratic lines |
| RD.C3 | controls: every case | every other line and nuclide field, and the notes, identical to before (the four limits of quadratic-window lines and the two limits of their nuclides excepted) |
| RD.C4 | 200 null realisations, NaI Cs-137, Currie | on the quadratic lines the reported threshold equals the quadratic one (1e-12), which with the primary results is unchanged from before; the ratio to k sigma and the fraction above it reported (before 0.881 and 0.0615) |
| RD.C5 | benchmark (`after_R7C`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes, each changed existing test listed with its reason (expected: the `test_window_polynomial.py` tests that assert the line's limits are the linear ones) |

Before the change: RD.C1, RD.C2 and RD.C4 fail; RD.C3 is the control.

## Limitations

- Synthetic spectra; one detector shape per type; the quadratic window is chosen by the engine's
  existing rule, which this change does not touch.
- A line marked "curved" without a usable polynomial window keeps the linear limits, which are then
  too small for its continuum; its primary result is not used and the note says so.
- RD.C4's null realisations measure the threshold only; the detection limit is checked by formula
  (RD.C1), not by injected peaks (a peak at the MDA is often found by the search and leaves the
  window path).

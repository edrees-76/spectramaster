# Round-8 review: covariance of the window results of a nuclide's lines, Gemini M3 (pre-registered)

Written 2026-10-30, before any change to the code. Gemini round-8 review
(`C:\Users\DELL\Downloads\gemini_review_round8.md`, main 384e89d), finding M3, checked on the code
(`analysis/activity.py` `combined_limits`, `_weighted_primary`, `_window_primary`; main 77310c2)
and measured before this protocol was written.

## Findings

1. **The weighted mean of a nuclide's window results treats its lines as independent although
   their windows share channels (Gemini M3, confirmed).** A nuclide not detected with
   `method = "mean"` and two or more usable window results reports their weighted mean
   (`_weighted_primary`) and the limits of that mean (`combined_limits`,
   `round7_combined_protocol.md`). Each line's window result is a linear combination of sample
   channels (the window minus its continuum sides, or the quadratic continuum's wider sides) and,
   with a background spectrum, of background channels. Lines close in energy use the same channels:
   NaI Ba-133 (base continuum with Co-60, seed 7, `round5_combined`'s flat efficiency curve),
   correlation of the linear window estimators +0.925 between 79.6 and 81.0 keV, from -0.51 to
   +0.30 between 276.4, 302.9, 356.0 and 383.8 keV. Both functions add the lines' counting variances
   only. Measured on that spectrum: s0 of the weighted mean 9.140 Bq counted independently, 8.595 Bq
   with the covariance of the linear windows (-6 %). Monte Carlo (200 spectra, seeds 1000-1199,
   Ba-133 absent): standard deviation of the weighted mean 8.936 Bq, mean reported uncertainty
   9.235 Bq (ratio 1.033), mean decision threshold / (1.645 x standard deviation) 1.034, false
   detections 0.010, mean -2.38 Bq. The lines used vary between spectra (2 to 6), which dilutes the
   effect in the Monte Carlo; it is a coverage check, not the measure of the defect. (A first
   exploration with the benchmark's flat curve, whose 33 % efficiency uncertainty dominates the
   reported uncertainty, gave a ratio 1.19 that is not the counting part; it is not used.)
2. **The reference-peak uncertainty of the weighted mean adds the lines' magnitudes (Gemini M3,
   second part, confirmed).** `_weighted_primary` adds `w_i ref_unc_bq_i` linearly; each line's
   `ref_unc_bq` is the norm of three components (the sample's reference peak counting, the blank's,
   the reference rate; `_window_primary`), each fully correlated between the lines but with the sign
   of the line's gross result. The sum of norms is not the norm of the summed components when lines
   have results of opposite sign or a blank.

These measurements were made with exploratory scripts before this protocol; no value after a
change was seen.

## Change

1. Each line with a window result keeps, in memory, the coefficients of its estimator in Bq per
   count: on the sample channels (linear window: `_window_coef`; quadratic window: `_quad_coef` of
   the sample's quadratic continuum) and, with a background spectrum (both modes), on the
   background channels (the same, with the background's scale), and the three reference-peak
   components of its result.
2. `_weighted_primary`: the counting variance of the weighted mean is W' C W with C_ii the line's
   `primary_u_count`^2 (as before) and C_ij = sum a_i a_j max(y, 0) + sum b_i b_j max(B, 0) over the
   shared channels (a: sample coefficients, y: sample counts, b: background coefficients, B:
   background counts); the reference-peak term is the norm of sum W_i g_i over the three components
   g_i. Weights unchanged.
3. `combined_limits`: S0^2 gains sum_{i != j} w_i w_j C_ij with the same C_ij (the observed counts as
   the estimate of the expected ones under H0, as the quadratic window's variance does); the rest of
   the formula is unchanged.
4. Unchanged: a single line, the key-line method, detected nuclides and their activity combination,
   every line's own values, the blank's terms (the covariance between the blank's own windows is not
   added), lines whose windows share no channel (their C_ij is 0).
5. ENGINE_VERSION becomes 1.34.0 (after R8-C's 1.33.0).

Harness `validation/round8_line_covariance.py` (`--rerun` writes to a fixed temporary folder),
fixed output folder `after_R8H`; values before the change recorded with `--collect` into
`after_R8H/round8_line_covariance_before.json`, committed with this protocol.

## Criteria

Cases (synthetic, `round5_combined`'s flat efficiency curve, `method = "mean"`, Currie and ISO 11929
each): NaI base continuum with the Co-60 peaks, seed 7, Ba-133 asked (six lines on linear and
quadratic windows, overlapping); the same with a background spectrum (base continuum, seed 8), peak
and spectrum modes; the same with a reference peak correction (sample and blank reference peak
counting 10 %, expected rate 3 %) and a reagent blank (base continuum with Co-60 and the Ba-133
lines at signal-to-noise 15, seed 9); controls: `method = "key"`, a detected nuclide (NaI Co-60),
Cs-137 (one line), Co-60 not detected on `round5_combined`'s flat spectrum (windows 159 keV apart).
Monte Carlo: NaI Ba-133 absent, 400 spectra (seeds 1000-1399), Currie.

| ID | quantity | limit |
|---|---|---|
| RH8.C1 | weighted mean of two or more usable window lines, every case and method | `primary_u` equals sqrt(u_c^2 + the other components as before) with u_c^2 = W' C W recomputed by the harness from the public window functions (relative 1e-9) |
| RH8.C2 | the same | decision threshold equals 1.645 sqrt(S0^2) with the C_ij of the Change, recomputed (relative 1e-9); MDA equal to the root of the registered quadratic with that S0^2 (relative 1e-9) |
| RH8.C3 | reference-peak case | the reference term equals the norm of sum W_i g_i (relative 1e-9) |
| RH8.C4 | controls and every line field | identical to before (relative 1e-12 for floating sums of zero cross terms) |
| RH8.C5 | Monte Carlo | mean reported uncertainty / standard deviation of the weighted mean in [0.909, 1.091]; mean decision threshold / (1.645 x standard deviation) in [0.909, 1.091] (99 % sampling limits of a standard deviation from 400 values); false-detection fraction reported |
| RH8.C6 | benchmark (`after_R8C`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes and exits 0; each changed existing test listed with its reason |

Before the change: RH8.C1 and RH8.C2 are expected to fail; RH8.C3 fails only where the reference
components differ in sign; RH8.C4 is the control; RH8.C5 passes before too (1.03 in the
exploration): it guards the change against over-correcting, it does not measure the defect.

## Limitations

- C_ij uses the observed counts; the lines' own s0_i keep their formulas.
- The covariances involving the blank's results between different lines (the blank's own windows,
  and a line's background estimate with another line's blank under a shared background), and between
  the efficiency values beyond the existing fully correlated term, are not added.
- A background re-binned to the sample's grid (spectrum mode, other calibration) is treated as
  independent counts per channel, as the lines' own variances already do.
- The false-detection fraction of the weighted mean also depends on the bias of the window results
  at low counts (mean -1.07 Bq in the exploration); it is reported, not a limit.

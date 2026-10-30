# Round-8 review: the detection limits of a line without a sample peak in the peak background mode, Gemini H2 (pre-registered)

Written 2026-10-30, before any change to the code. Gemini round-8 review
(`C:\Users\DELL\Downloads\gemini_review_round8.md`, main 384e89d), finding H2, checked on the code
(`analysis/activity.py` `compute_activities` line loop, `_window_primary`, `_quad_result`; main
497467b) and measured before this protocol was written.

## Finding

**In the peak background mode the decision threshold of a line without a sample peak is computed
with another estimator than its primary result (Gemini H2, confirmed).** With a background spectrum
and `bkg_mode = "peak"`, a line whose expected peak the search did not find has its primary result
from the window estimator on the sample minus the scaled window estimator on the background
fitter's counts `bfit.b` (`_window_primary`, "one window estimator for the sample and the background
in both modes", `signed_primary_amendment_protocol.md`, A3), and the result is compared with the
decision threshold L_C. But sigma0^2 of that threshold takes its background term from
`BackgroundFitter.at_energy`: the fitted full-peak area k N_b of a Gaussian at the line and its
variance (`var0 += max(k N_b, 0) + (k u_b)^2`), not the window counts of the background estimate
that is subtracted (not multiplied by the window fraction f_w, and the variance of a fitted area,
not of the window estimator); its covariance with a blank sharing the background uses the fitter's
coefficients too (`h0 = bnet[2]`), while the primary result's uses the window's
(`round7_shared_background_protocol.md`). Where the window is quadratic the H0 background term is
not replaced either (peak mode: `b_term = 0`). Measured (HPGe flat continuum 20 counts per channel,
live time 1000 s, Cs-137 asked, the sample and the background each counting a background Cs-137
peak of 1500 counts, Currie): L_C 97.68 counts in the peak mode against 99.79 in the spectrum mode,
for the same primary result; with no background peak 33.98 against 42.71.

These measurements were made with exploratory scripts and the new harness's `--collect` run before
this protocol; no value after a change was seen.

## Change

1. Peak mode, a line without a sample peak: the background terms of sigma0^2 are those of the
   window estimator of its primary result on the background fitter's counts `bfit.b` scaled by
   `bfit.k`: with (N_w, V_w) = `window_net` of `bfit.b` at the line,
   `sigma0^2 = B (1 + n / 2m) + k max(N_w, 0) + k^2 V_w` (window counts: the sample counts the
   background's level, and the variance of the subtracted background estimate), minus the blank
   terms as before; the covariance with a blank sharing the background uses the window
   estimator's coefficients (`_window_coef`, as the primary result). When the window is quadratic
   (`window_polynomial_protocol.md`), the linear background term is replaced by the quadratic
   one, `k max(G_b - B_b,q, 0) + k^2 (G_b + var_data,b)`, and the covariance by the quadratic
   estimator's coefficients. When the window of the background cannot be computed the previous
   term is kept.
2. Unchanged: the primary result and its uncertainty, lines with a sample peak (the fitter's
   estimator under the fitted peak), the spectrum mode, the legacy caller-supplied background peaks,
   the reported background area `bkg_peak` of the line (the fitter's area), every case without a
   background spectrum.
3. ENGINE_VERSION becomes 1.32.0.

Harness `validation/round8_peak_mode.py` (`--rerun` writes to a fixed temporary folder), fixed
output folder `after_R8B`; values before the change recorded with `--collect` into
`after_R8B/round8_peak_mode_before.json` (engine 1.31.0, 497467b), committed with this protocol.

## Criteria

Cases (synthetic, flat efficiency, Currie and ISO 11929 each, peak and spectrum modes): HPGe flat
continuum 20, live time 1000 s, Cs-137 asked, sample (seed 30000) and background (seed 10000) each
with a background Cs-137 peak of 1500 counts, of 20000 counts, of none; the 1500-count case with a
blank (seed 20000, 2000 counts above the background's) subtracting the same background; a sample
with 3000 counts of its own (peak found); NaI base continuum with Co-60 in sample (seed 7) and
background (seed 8), Cs-137 and Co-60 asked (lines without a sample peak, one on the quadratic
window, one curved). Monte Carlo: the 1500- and 20000-count cases, 400 realisations each (sample
seeds 30000+i, background 10000+i), peak mode, Currie.

| ID | quantity | limit |
|---|---|---|
| RB8.C1 | peak mode, every line without a sample peak with a usable window result, both methods | L_C equals 1.645 sqrt(sigma0^2) of the Change (linear or quadratic, with the blank terms and the covariance 2 C (f_w / w)^2 of the primary result's covariance C), recomputed by the harness from the public window functions (relative 1e-9); at least one such line on the quadratic window |
| RB8.C2 | the same lines | every line field other than the limits (L_C, L_D, decision threshold, MDA, their window copies), the limit slope and the note identical to before |
| RB8.C3 | the spectrum mode, and the peak-mode lines with a sample peak or without a usable window result | identical to before |
| RB8.C4 | Monte Carlo, results without a sample peak with a usable window | false-detection fraction (primary > decision threshold) in [0.022, 0.078]; mean decision threshold / (1.645 x standard deviation of the primary results) in [0.909, 1.091] (99 % sampling limits) |
| RB8.C5 | benchmark (`after_R8A` / `after_R7G`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes and exits 0; each changed existing test listed with its reason |

Before the change: RB8.C1 fails; RB8.C2 and RB8.C3 are the controls; RB8.C4 is measured before and
after.

## Limitations

- Synthetic spectra; the Monte Carlo cases have no sample activity and the background peak exactly
  at the line.
- sigma0^2 uses the observed sample continuum and background window as the expected values under
  H0, as the existing window limits do.
- The spectrum mode's background term (`k^2 G_b (1 + n / 2m)`, without the sample's counting of the
  background level) is not in this change, so the two modes keep different limits for the same
  primary result.
- The background area reported for such a line (`bkg_peak`) stays the fitter's, which is not the
  one subtracted from the window result.

---

## Results (`after_R8B`)

Protocol committed in 14f3437 before the change (SHA-256 of the file
92678ee7cdc3f3a71034694248ae478e0d2d92c278fab687c075917773153ebe; before file
`after_R8B/round8_peak_mode_before.json` c8bcb1f53880372b571218a298810cf7f60142d9680dee8232eca29d6fa54af8).
First run: 3 PASS / 1 FAIL.

| ID | value | result |
|---|---|---|
| RB8.C1 | every peak-mode line without a sample peak with a usable window result equals the registered sigma0^2 (e.g. HPGe 1500-count background peak: L_C 97.68 -> 99.25 counts; no background peak 33.98 -> 41.49; with the blank 145.35 -> 146.69; NaI 661.7 keV quadratic 392.1 -> 476.1, 1173.2 keV linear 309.2 -> 336.4) | PASS |
| RB8.C2 | primary result, its uncertainty, method and every other line field identical to before | PASS |
| RB8.C3 | NaI case, peak mode: the 1332.5 keV line (no sample peak, "curved", not used) changed its limits (Currie L_C 291.08 -> 314.42 counts); every other field and every other line identical | FAIL |
| RB8.C4 | 1500-count case: 396 results without a peak, false detections 0.0556 -> 0.0530, threshold ratio 0.9277 -> 0.9444; 20000-count case: 399, 0.0526 -> 0.0526, 0.9379 -> 0.9397 | PASS |

The RB8.C3 failure is a drafting error of this protocol, not of the change: Change 1 applies to
every line without a sample peak, and RB8.C3 wrongly listed the lines without a usable window
result among those unchanged. It stays a FAIL; the amendment below was written after seeing it and
before any re-run.

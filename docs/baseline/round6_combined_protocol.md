# Round-6 review: limits of the line combination with a blank and a reference peak, H1 (pre-registered)

Written 2026-10-28, before any change to the code. Codex round-6 review
(`C:\Users\DELL\Downloads\codex_review_round6.md`, main 624e199), finding H1, checked on the code
(`analysis/activity.py`, `combined_limits` and the per-line limits of `compute_activities`, main
e2c0144) and reproduced by the harness below before this protocol was written.

**Finding.** Round 5 (`round5_combined_protocol.md`) gave the weighted mean of several lines its own
decision threshold and detection limit, `combined_limits`, from each line's s0 and slope, assuming the
lines are counted independently at zero net activity. With a reagent blank and a reference peak
correction that is not true: one reference peak correction K_s corrects every line of the sample, one
K_b every line of the blank, and the expected rate is common. At zero net activity the sample's gross
activity of line i is the blank's Ab_i, so the corrections give two lines the covariance

    Cov0(i, j) = Ab_i Ab_j (u_c^2 + u_cb^2 + (u_r - u_rb)^2)

(u_c, u_cb: relative counting uncertainties of the sample's and the blank's reference peaks; u_r,
u_rb: of the expected rate, as `compute_activities` uses them), and the term of the variance linear in
the net activity y the cross term (Ab_i + Ab_j)(u_c^2 + u_r (u_r - u_rb)) y. Each line's own limits
already contain the diagonal terms (u_ref0^2 and `ref_lin`); `combined_limits` leaves out the cross
terms. Reproduced (harness, Co-60 1173 and 1332 keV, blank 50 Bq per line, reference peaks counted to
10 % in the sample and in the blank, rate exact, ISO 11929):

- decision threshold 8.2576 Bq, independent computation from the full covariance 11.6600 Bq;
- detection limit 18.4036 Bq, independent 26.8031 Bq;
- a zero-activity weighted mean (Gaussian linear model, 10^6 draws, seed 20261028) exceeds the
  engine's threshold in 12.19 % of the draws, the independent threshold in 4.99 % (alpha 5 %).

Without a blank (Ab = 0) the cross terms vanish: the limits are unchanged, and without a reference
peak correction only the blank's own reference correction (u_cb, u_rb) remains.

## Change

1. Each line result records, when its blank line exists, the reference-peak part of its zero-activity
   uncertainty as a vector over the three shared variables (sample peak, blank peak, expected rate):
   `ref_g0 = Ab_i (u_c, u_cb, u_r - u_rb)` (Bq), and its derivative in y, `ref_dg = (u_c, 0, u_r)`.
2. `combined_limits` adds the cross terms of these vectors: S0^2 += sum over i != j of
   w_i w_j ref_g0_i . ref_g0_j (both methods, since each line's s0 contains u_ref0 in both); the slope
   += sum over i != j of w_i w_j (ref_dg_i . ref_g0_j + ref_g0_i . ref_dg_j) (ISO 11929 only, as
   each line's `ref_lin`). The weights, the activity, its uncertainty and the per-line limits are
   unchanged.
3. Engine version 1.25.0: the combined limits (and so possibly the detection decision of a weighted
   mean) change for analyses with a blank and a reference peak correction (sample's or blank's).

Harness `validation/round6_combined.py`, fixed output folder `after_R6D`; values before the change
recorded with `--collect` into `after_R6D/round6_combined_before.json` (engine 1.24.0, e2c0144),
committed with this protocol.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RD.C1 | decision threshold of the weighted mean, the four cases of the harness (ISO and Currie with blank and reference peaks; with a rate uncertainty; reference peak without blank) | equal to the independent computation from the full covariance to relative 1e-9 |
| RD.C2 | detection limit of the same cases | equal to the independent root (bisection) to relative 1e-9 |
| RD.C3 | false-positive rate of the engine's threshold, linear Gaussian model with the shared corrections, 10^6 draws | within 0.002 of alpha = 0.05 in every case |
| RD.C4 | activity, uncertainty, lines used, detection and each line's own limits of the four cases | identical to before |
| RD.C5 | the round-5 cases (`round5_combined`: no reference peak) and the one-line ("key") results | identical to before |
| RD.C6 | benchmark (`after_R6C`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes, each changed existing test listed with its reason |

Before the change: RD.C1, RD.C2 and RD.C3 fail for the three cases with a blank (threshold 8.2576
vs 11.6600, 8.2576 vs 11.6600, 5.5293 vs 7.7929 Bq; rates 12.19 %, 12.19 %, 12.14 %) and pass for the
case without a blank; RD.C4 and RD.C5 are the controls.

## Limitations

- The weights stay fixed (the uncorrelated part), as in round 5: the limits are those of that
  estimator, conditional on the lines used; the line selection after detection is not simulated
  (Codex round 6 notes this; not changed here).
- The linear Gaussian model of RD.C3 checks the formula, not the full search-and-select analysis.
- The weighted mean's own uncertainty still adds the reference-peak components linearly (fully
  correlated); not changed here.

---

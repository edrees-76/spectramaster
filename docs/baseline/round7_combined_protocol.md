# Round-7 review: limits of the weighted mean, Codex H2 and Gemini M1 (pre-registered)

Written 2026-10-29, before any change to the code. Codex and Gemini round-7 reviews
(`C:\Users\DELL\Downloads\codex_review_round7.md`, `gemini_review_round7.md`, main b3d88d1),
checked on the code (`analysis/activity.py` `combined_limits`, the line loop of `compute_activities`,
`_combine`, `_combine_activity`, `_weighted_primary`, main 1d610ac) before this protocol was written.

## Findings

**Codex H2: cross terms of a line without a blank peak.** With a reference peak correction, the
correction's variance for a line is u^2(y) = |g0 + y dg|^2, where g0 holds the components at zero net
activity (from the line's blank activity) and dg = (u_c, 0, u_r) their change with the net activity y
(round6_combined_protocol.md). The reference peak is shared, so two lines covary by
(g0_i + y dg_i).(g0_j + y dg_j). `combined_limits` adds the cross terms only when both lines carry
`ref_g0`, and the line loop sets `ref_g0` and `ref_dg` only for a line whose blank has a peak. For a
line without one, g0 = 0 but dg is not: the linear cross term g0_i.dg_j of the other line is missing.
Codex: Co-60, blank peak at 1173 keV only, reference counting 10 %, rate 3 %, ISO 11929: detection
limit 9.37289 Bq against 10.02554 Bq from the full covariance (-6.5 %); the decision threshold is
right (g0_j = 0 adds nothing at zero activity). Currie has no linear term and is not concerned.

**Gemini M1: limits of a nuclide whose lines are not detected, `method = "mean"`.** `_combine` then
reports the weighted mean of the usable lines' window results as the primary result (`primary`,
`primary_u`, round4_primary_protocol.md), while `_combine_activity` keeps the decision threshold and
detection limit of the key line alone. Gemini: flat spectrum, Co-60, ISO 11929: primary
0.000 +- 1.470 Bq, threshold 3.058 Bq and MDA 6.364 Bq of the 1173 keV line, against 2.418 and
4.976 Bq for the weighted mean of both lines. The threshold reported is not the one of the result
reported.

**Gemini L1: rejected.** The finding quotes `math.copysign(l.ref_unc_bq, l.gross_activity or
l.primary)` at `activity.py:1289`. That expression is not in the code: line 1289 is
`ur = sum(w * l.ref_unc_bq ...)`, a sum of magnitudes (the reference component taken as fully
correlated), with no sign taken from `gross_activity` or `primary`. Nothing to change.

## Change

1. The line loop sets `ref_dg` = (u_c, 0, u_r) for every line with a reference peak correction, and
   `ref_g0` = (0, 0, 0) for a line without a blank peak (unchanged for a line with one).
   `combined_limits` adds the cross terms for every pair of lines that both carry `ref_dg`: the
   constant term g0_i.g0_j and, for ISO 11929, the linear term g0_i.dg_j + dg_i.g0_j. Lines with a
   blank peak on both: unchanged. Without a blank or without a reference peak: g0 = 0 everywhere,
   unchanged.
2. `_combine`, for a nuclide with no line detected, `method = "mean"` and more than one usable window
   result: the decision threshold and detection limit are those of the weighted mean of the same lines
   with the same weights as `primary` (`combined_limits` with the weights of `_weighted_primary`).
   The nuclide's detection decision is unchanged (no line detected: not detected). When `primary`
   exceeds that decision threshold, the nuclide's note says "weighted mean of the window results above
   its decision threshold, no line detected".
3. Key-line results, detected nuclides, and a single usable line: unchanged.
4. ENGINE_VERSION becomes 1.28.0 (reported limits change in the two cases above).

Harness `validation/round7_combined.py`, fixed output folder `after_R7B`; values before the change
recorded with `--collect` into `after_R7B/round7_combined_before.json` (engine 1.27.0, 1d610ac),
committed with this protocol.

## Criteria

Synthetic spectra and peaks of `round5_combined` / `round6_combined` (flat efficiency 0.01, flat
continuum).

| ID | quantity | limit |
|---|---|---|
| RB.C1 | Co-60, mean, reference peak, blank peak on one line only (1173 keV; and 1332 keV), ISO 11929 with rate uncertainty 0 and 3 % | threshold and limit equal the full-covariance computation of `round6_combined.independent` within 1e-9 relative (before: limit 6.5 % low in Codex's case) |
| RB.C2 | the same with Currie | identical to before |
| RB.C3 | Co-60 (2 lines) and Ba-133 (6 usable lines), mean, no peak, flat spectrum, ISO 11929 and Currie | threshold and limit equal an independent computation for the weighted mean with the weights of `primary` within 1e-9 relative; `primary` and `primary_u` identical to before |
| RB.C4 | Co-60, mean, ISO 11929, flat spectrum with a Gaussian at each line of 0.9 x that line's L_C counts (from the run without them), no search peak | nuclide not detected; note "weighted mean of the window results above its decision threshold" present exactly when `primary` exceeds the reported threshold |
| RB.C5 | the cases of `round5_combined` and `round6_combined` (detected), key-line runs of RB.C3, single usable line | every number identical to before |
| RB.C6 | benchmark (`after_R7A`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes, each changed existing test listed with its reason |

Before the change: RB.C1 and RB.C3 fail (missing cross term; key-line limits); RB.C4 fails (no note);
RB.C2 and RB.C5 are the controls.

## Limitations

- Synthetic data; the reference peak model (components u_c, u_b, u_r) is the one of
  round6_combined_protocol.md, not re-examined here.
- Weights held at their observed values, and lines selected after detection, as in
  round5_combined_protocol.md.
- Detection of a nuclide stays line by line; deciding it on the weighted mean is a separate question,
  not answered here.

---

## Results (`after_R7B`)

Protocol committed in 8c6b8dd before the change (SHA-256 of the file
a881ebcf11c0392ed9c300f9ba435de95afa8bdb9425c88de96422a867184f0a). Engine 1.28.0.

**First run: 4 PASS / 1 FAIL, harness error, disclosed** (kept as
`after_R7B/round7_combined_run1.md`). RB.C2 compared every field of the line results, including
`ref_g0` and `ref_dg`, which item 1 of the change sets by design for a line without a blank peak;
every number of the Currie cases was identical. The comparison was corrected to the reported
quantities (threshold, limit, activity, u, primary, primary_u, detection, note, lines used), as the
row "identical to before" intends for the results; the limit was not changed.

**Second run: 5 PASS / 0 FAIL.**

| ID | value | result |
|---|---|---|
| RB.C1 | ISO 11929, blank peak on 1173 keV only and on 1332 keV only, rate 0 and 3 %: threshold and limit equal the full-covariance computation within 1e-9 (before: limit 6.5 % low in Codex's case) | PASS |
| RB.C2 | Currie cases identical to before (second run) | PASS |
| RB.C3 | Co-60 and Ba-133, ISO 11929 and Currie: limits equal those of the weighted mean with the weights of `primary`; `primary` and `primary_u` identical to before | PASS |
| RB.C4 | primary 0.2759 Bq above the threshold 0.2176 Bq of the weighted mean, not detected, note present; absent without the Gaussians | PASS |
| RB.C5 | detected cases of `round5_combined` / `round6_combined`, key-line runs, single usable line identical to before | PASS |
| RB.C6 | benchmark 154 PASS / 13 FAIL / 60 REPORT, no criterion changed state against `after_R7A`; full suite 1591 passed, 1 failed, 69 skipped before the test change below, then that test file rerun: passed | PASS |

RB.C6 is evaluated outside the harness. Changed existing test:
`tests/test_round6_combined.py::test_no_blank_no_cross_terms` asserted `ref_g0 is None` for lines
with a reference peak and no blank; item 1 sets `ref_g0 = (0, 0, 0)` for such a line, so the test now
accepts None or (0, 0, 0). The limits it covers are unchanged (zero cross terms at that level).

Also changed: the manuals (sources), MDA and primary result rows: the limits of the weighted mean are
reported for an undetected nuclide with `method = "mean"`; cross terms also apply when only some lines
have a blank peak.

# Round-5 review: limits of the line combination, H1 (pre-registered)

Written 2026-10-28, before any change to the engine. Codex round-5 review
(`D:\DSpectraMaster_reviews\codex_review_round5.md`, main 865c1ec), finding H1, checked on the code
(`analysis/activity.py`, `_combine_activity`) before this protocol was written.

**Finding.** With the "mean" method and more than one line, the activity is the weighted mean
`a = sum(lambda_i a_i)` with `lambda_i` proportional to `1 / (u_count_i^2 + (a_i u_I)^2 + (a_i u_I,i)^2)`
(counting and intensity variances of the observed lines). The decision threshold of the combination
was computed as `k_alpha / sqrt(sum(1 / s0_i^2))`, `s0_i` = each line's decision threshold / `k_alpha`:
the threshold of the inverse-variance mean with weights `1 / s0_i^2`, not of the estimator reported.
The detection limit was `min(line limits)`, not derived for the estimator. Reproduced (harness below,
case `co60_iso`): weights 0.97821 / 0.02179, threshold 0.217599 Bq, while the same weights give
0.298760 Bq (Codex: 0.217599 against 0.302321 Bq in a case with weights 0.990071 / 0.009929).

## Change

1. **Decision threshold.** With the weights `lambda_i` of the reported mean, held fixed, the standard
   uncertainty of the mean at zero activity is `S0 = sqrt(sum(lambda_i^2 s0_i^2))` (lines counted
   independently, as the activity combination already assumes). The decision threshold is
   `y* = k_alpha S0`.
2. **Detection limit.** Each line's limit already solves `y# = y* + k_beta u(y#)` with
   `u^2(y) = c_i y + s0_i^2 + y^2 r_i^2` (`c_i`: Bq per count of the line plus the linear
   reference-peak term; `r_i`: relative uncertainty of the line's calibration factor; Currie: `r_i = 0`
   and no reference term). For the mean: `u^2(y) = sum(lambda_i^2 c_i) y + S0^2 + y^2 R^2`, with `R`
   combined as the activity budget combines the components: efficiency, true-coincidence and
   reference peak linear in `lambda` (fully correlated between lines), the intensity term
   `hypot(u_I, sqrt(sum(lambda_i^2 u_I,i^2)))`, the attenuation term common. `y#` is the larger root of
   the same quadratic as `iso11929_limits`. A new function `combined_limits(lines, weights, options)`
   returns `(y*, y#)`; each line keeps `c_i` and its reference-peak relative uncertainty.
3. Unchanged: the line selection (detected lines with a positive net area), the weights, the
   activity, its uncertainty and budget, the "key" method, a single selected line, and every line's
   own limits. `detected` stays `a > y*`.

Engine version 1.23.0 (combined decision threshold and detection limit change with the "mean"
method). Harness `validation/round5_combined.py`, fixed output folder `after_R5C`.

## Cases (synthetic, flat efficiency 1 %, live time 20000 s, `u_I` 1 %, attenuation 2 %)

| case | nuclide | lines (energy, net area +- u) | limits | blank |
|---|---|---|---|---|
| `co60_iso` | Co-60 | 1173.228: 3000 +- 60; 1332.492: 900 +- 450 | ISO 11929 | none |
| `co60_currie` | Co-60 | same | Currie | none |
| `ba133_iso_blank` | Ba-133 | 356.0129: 5000 +- 80; 302.8508: 1500 +- 300; 383.8485: 600 +- 240 | ISO 11929 | 400 / 150 / 60 counts |
| `key_iso11929`, `key_currie` | Co-60 | as `co60_*`, "key" method | both | none |

## Independent computation (harness)

From the line fields only (no engine limit function): the weights as in the engine; `s0_i` =
line threshold / `k_alpha`; `c_i` solved back from each line's own threshold and limit,
`c_i = ((y#_i - y*_i)^2 / k_beta^2 - s0_i^2 - (y#_i r_i)^2) / y#_i`; `y#` of the mean by bisection
(200 steps) of `y - y* - k_beta u(y) = 0`. False positives: 1 000 000 Gaussian draws per line
(seed 20261028), standard deviations `s0_i`, zero activity, fraction of weighted means above the
engine's threshold.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RC.C1 | engine threshold against the independent one, all three cases | relative difference <= 1e-9 |
| RC.C2 | engine detection limit against the independent one, all three cases | relative difference <= 1e-9 |
| RC.C3 | false-positive fraction at the engine's threshold, all three cases | within 0.002 of alpha = 1 - Phi(1.645) |
| RC.C4 | activity, uncertainty, budget and lines used, the three cases, against engine 1.22.0 (96cfb90) | identical (==) |
| RC.C5 | "key" method, ISO and Currie: threshold, limit, activity, uncertainty against 1.22.0; `combined_limits` of the single key line with weight 1 against that line's own limits | identical (==); relative difference <= 1e-12 |
| RC.C6 | benchmark (`after_R5B`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes, each changed existing test listed with its reason |

Values before the change (engine 1.22.0, 96cfb90), recorded by the harness with `--before`:

| case | threshold | independent | limit | independent | P(false positive) |
|---|---|---|---|---|---|
| `co60_iso` | 0.217599 | 0.298760 | 0.625243 (min of lines) | 0.611489 | 0.1155 |
| `co60_currie` | 0.217599 | 0.298760 | 0.624253 (min of lines) | 0.610521 | 0.1155 |
| `ba133_iso_blank` | 0.585883 | 0.614935 | 1.268805 (min of lines) | 1.253079 | 0.0582 |

So RC.C1-C3 fail before the change; RC.C4 and RC.C5 are the controls.

## Limits of this change (stated now)

- The weights depend on the observed activities (the intensity terms); they are held fixed in the
  limits, as for the reported estimator. A selection and weighting fixed before the measurement, as
  Codex suggests, would change the activity values and is not part of this change.
- The lines are selected after detection (detected lines with a positive net area). The threshold is
  that of the mean of the selected lines; the selection itself is not propagated.
- Counting covariance between lines (a shared continuum or overlapping windows) is not modelled, as
  in the activity combination.

---

## Results (`after_R5C`)

Protocol committed in 6fc92af before the change (SHA-256 of the file
813d0b3da888a00a9c24d3f033d0cf777a7fa426e3209d6c9a0fb436c03012b5). Engine 1.23.0.

**First run: 6 PASS / 0 FAIL.**

| ID | value | result |
|---|---|---|
| RC.C1 | threshold equal to the independent one: `co60_iso` 0.298760, `co60_currie` 0.298760, `ba133_iso_blank` 0.614935 Bq (before 0.217599, 0.217599, 0.585883) | PASS |
| RC.C2 | detection limit equal to the independent one: 0.611489, 0.610521, 1.253079 Bq (before: min of the lines 0.625243, 0.624253, 1.268805) | PASS |
| RC.C3 | false-positive fraction 0.04994, 0.04994, 0.04990 against alpha 0.04998 (before 0.1155, 0.1155, 0.0582) | PASS |
| RC.C4 | activity, uncertainty, budget and lines used identical to 1.22.0 | PASS |
| RC.C5 | "key" method identical to 1.22.0; `combined_limits` of one line equal to its own limits | PASS |
| RC.C6 | benchmark 154 PASS / 13 FAIL / 60 REPORT, no criterion changed state against `after_R5B`; full suite 1497 passed, 69 skipped; no existing test changed | PASS |

In these cases the detection limit of the mean is slightly lower than the smallest line limit
(by 1.2-2.2 %): the second line adds information. `detected` did not change in any case (all
activities far above the thresholds).

**CI (Linux), disclosed.** The unit test first ran the harness criteria as they are and failed RC.C4
on GitHub: the values "before" were recorded on this Windows machine, and the efficiency fit differs
in the last digits on another platform. RC.C4 and RC.C5 as registered (==) were evaluated here, on
the machine that recorded "before", and pass. The unit test now checks RC.C1-C3 as registered and
compares with "before" within a relative 1e-12; the criteria are unchanged.

Also changed: the manuals (sources) say that, with the weighted mean of lines, the decision threshold
and the MDA are those of the mean itself.

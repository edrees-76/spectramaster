# Outliers in the efficiency model error (D2): evaluation protocol (pre-registered)

Written 2026-10-21, **before** the implementation and before any run of the new estimator. The limits
below must not be changed after the results are known. A result outside a limit is reported as a
failure.

## Background

`model_error` is u_model^2 = max(0, mean(r_i^2 - s_i^2 - v_i)), where r_i is the leave-one-out
prediction error of point i, s_i its uncertainty and v_i the prediction variance. A single outlier
sets this value for the whole curve. In the CRM check, the D1 point gave 58.5 % where the curve without
it gives 8.1 %. That is D2 in `crm_validation_protocol.md`.

The first attempt, R3 of `efficiency_poisson_protocol.md`, capped r_i^2 at 3^2 (s_i^2 + v_i). It was
withdrawn. The CRM points scatter systematically (chi^2/dof 24-49), so the cap limited 17 of 34 points.
The model error fell from 8.3 % to 4.5 %, and the Marinelli fraction |z| <= 2.58 from 1.0 to 0.5.
**Lesson:** the cap must be relative to the scatter that is actually present, not to each point's own
uncertainty. The criteria must include systematic scatter, not only a single outlier.

Values known before writing this protocol, from the plain formula on `main`:

| | clean | D1 replay |
|---|---|---|
| CRM cylinder log-log (after_EP1 points) | 8.32 % | 51.15 % |
| CRM Marinelli log-log (after_EP1 points) | 9.96 % | 51.56 % |
| 12 synthetic points, 3 % scatter | 0.00 % | 5.50 % (one 7-sigma point) |

The new estimator has not been run on any of them.

## Change (R1)

Huber-type cap at the curve's own scatter, iterated to a fixed point:

- u_0 = the plain value.
- u_{k+1}^2 = max(0, mean(min(r_i^2, Z^2 (s_i^2 + v_i + u_k^2)) - s_i^2 - v_i)), with Z = `OUTLIER_Z` = 3.
- Stop when |u_{k+1} - u_k| <= 1e-12 or after 200 iterations. The map is non-decreasing in u and starts
  at its largest value, so the sequence does not increase. If it does not converge, the plain value is
  kept and a curve warning says so.

Properties, stated in advance:

- When no point exceeds Z sqrt(s_i^2 + v_i + u_0^2), the result is the plain value, bit-identical.
- An outlier's contribution is bounded, so moving it further away changes nothing.
- The result never exceeds the plain value.

`fit_efficiency` names the capped points in `curve.warnings`: "... leave-one-out prediction error
beyond 3 x the curve's scatter, limited in the model error". The curve parameters and covariance do
not change. `ENGINE_VERSION` goes up one minor version.

**Order.** This branch starts from `main` before PR #42. The criteria are evaluated after PR #42 is
merged and this branch is brought up to date, so the CRM points are those of after_EP1 (fitted on
S - kB). If PR #42 is not merged, the criteria are evaluated on `main` and this is stated.

## Criteria

| id | test | limit |
|---|---|---|
| ME.C1 | Bounded influence. 12 synthetic log-log points (seed and model as in `tests/test_efficiency_poisson.py` of PR #42), one point moved to 7, 20 and 100 sigma. | the three values equal (relative 1e-9); the plain formula is reported for comparison |
| ME.C2 | Clean synthetic points (that set unmoved) and every efficiency curve fitted by the existing tests | bit-identical to the plain formula wherever no point is capped; checked in the test |
| ME.C3 | D1 replay on CRM (as EP.C8: Ac-228 674.75 keV at 0.05 x the clean curve, u_count_rel 0.06, RGTh-1 u_act_rel), cylinder and Marinelli log-log | model error with the point <= 1.5 x clean, both |
| ME.C4 | Systematic scatter kept. Clean CRM curves: cylinder log-log, cylinder two-branch, Marinelli log-log | new value >= 0.90 x plain value, each |
| ME.C5 | CRM protocol re-run unchanged | no PASS -> FAIL in CRM.C1, C2, C3.*, C4; the reported C1 of the two-branch and Marinelli runs not lower than in after_EP1 |
| ME.C6 | QCY48 leave-one-nuclide-out (crm-validation memory: rms z 0.99) | rms z reported. Not a criterion: the harness is not in the repository. |
| ME.C7 | Benchmark, `after_EP1` -> `after_ME1` (name checked free) | no PASS -> FAIL |
| ME.C8 | Full test suite | passes; any changed existing test listed with its reason |

**Expected, but not criteria.** Arithmetic with the CRM numbers above gives about 10 % for the D1
replay (34 + 1 points). For 12 points with one 7-sigma point it gives about 1.6 x the point uncertainty
(4.9 %). With few points a single outlier stays strong evidence, and the estimator does not hide it.

## Results (2026-10-21)

The text above was recorded with SHA-256
`9e47e7fec7705bc4a9dacf2cf82d2346525f604aba96dac522bbb5bf5cf88aef` before the implementation.
PR #42 was merged and this branch was brought up to date before the evaluation, so the CRM points are
those of after_EP1.

A diagnostic run on `main` before that merge gave the same statuses: ME.C3 8.13 -> 9.85 % and
9.98 -> 11.85 %, ME.C4 unchanged, ME.C1 as below. It also showed the ME.C1 failure before the
official run.

| id | value | limit | status |
|---|---|---|---|
| ME.C1 | 5.501 / 16.813 / 87.772 % at 7 / 20 / 100 sigma (plain formula 5.501 / 18.535 / 96.553 %) | the three equal | **FAIL** |
| ME.C2 | bit-identical to the plain formula wherever no point is capped (30 synthetic cases, the three clean CRM curves). The other curves of the test suite were not checked one by one; the suite passes unchanged. | | PASS |
| ME.C3 | cylinder 8.32 -> 10.01 %, Marinelli 9.96 -> 11.84 % (plain formula: about 51 %) | <= 1.5 x clean | PASS |
| ME.C4 | cylinder log-log 8.32 = 8.32 %, two-branch 8.82 = 8.82 %, Marinelli 9.96 = 9.96 %; no point capped | >= 0.90 x plain | PASS |
| ME.C5 | CRM identical to after_EP1: 6 of 8, C4 0.933; reported C1 two-branch 1.000, Marinelli 1.000 | no PASS -> FAIL, no lower C1 | PASS |
| ME.C6 | not run; the QCY48 harness is not in the repository | reported only | not evaluated |
| ME.C7 | after_EP1 154 / 13 / 60 -> after_ME1 154 / 13 / 60; only the runtime values changed | no PASS -> FAIL | PASS |
| ME.C8 | 1309 passed, 68 skipped; no existing test changed | | PASS |

### ME.C1: why it fails

The property "an outlier's contribution is bounded" was stated wrongly. The cap limits only the
outlier's own term r_i^2. The outlier also stays in the leave-one-out fits of every other point, so
those points' residuals grow with it. This effect is large with 12 points and a second-order curve.

At 7 sigma, nothing is capped. The starting value u_0 is the plain value, which the outlier itself
inflates, so the outlier hides itself (masking). The estimator is therefore never above the plain
value and is lower once the outlier's own term is capped. It does not bound the influence. Bounding
it would need a robust fit of the curve itself, which down-weights the outlier in every
leave-one-out fit. That would change the curve and is not in this change.

### What the change does and does not do

- **It does:** with many points (CRM, 34 + 1), a single gross outlier raises the model error by about
  a fifth instead of six-fold. Systematic scatter shared by many points is untouched (ME.C4, C5).
  Curves without a capped point are unchanged to the bit.
- **It does not:** with few points, a large outlier still raises the model error strongly. It is
  lower than with the plain formula, but not bounded. The curve's outlier warnings (|z| > 3) remain
  the way to find such a point, and setting it unused remains the remedy.

`ENGINE_VERSION` 1.6.0.

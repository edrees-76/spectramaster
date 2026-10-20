# Reference peak correction: evaluation protocol (pre-registered)

Written 2026-10-20, **before** the implementation and before any evaluation result. The limits
below must not be changed after results are known. A result outside a limit is reported as a
failure.

## Motivation

This is the first link of Genie's peak-area correction chain (Customization Tools manual ch. 3,
published documentation; no vendor software was decompiled). It covers the losses that the live
time does not correct, mainly random summing and pile-up at high count rates.

These losses can be measured with a peak of known rate:

- an electronic **pulser**, whose rate is its frequency;
- or a **fixed reference source**, whose rate is measured once in a low-rate reference
  measurement and decay-corrected.

The ratio of the expected to the measured rate of that peak corrects every peak of the spectrum.

## Change

`ActivityOptions.reference_peak = {"energy": keV, "rate": cps, "rate_rel_unc": fraction,
"half_life_s": optional, "ref_date": optional}`. When it is set:

```
r_meas = N_ref / t_live                                   reference peak in the sample spectrum
r_exp  = rate * exp(-lambda (t_start - ref_date))         decay-corrected (pulser: no half-life)
K      = r_exp / r_meas
u_rel(K)^2 = (u(N_ref) / N_ref)^2 + rate_rel_unc^2
```

- Every activity, decision threshold and MDA is multiplied by K. In the formulas this is a factor
  in w = Bq per net count.
- u_rel(K) is a correlated relative component, like attenuation. It enters the uncertainty budget
  as "reference peak" and the ISO 11929 w uncertainty.
- The measured reference peak is the fitted peak nearest to the given energy, within the match
  tolerance. If none is found the calculation is refused with an error; it is never silently
  uncorrected.
- K and u_rel(K) are kept in the results and noted.
- Nothing changes when no reference peak is set.
- `reference_rate(spectrum, energy)` measures the rate of a fixed reference source in a reference
  (low-rate) spectrum.

## Benchmark (new category `reference_peak`, HPGe and NaI)

Each sample spectrum contains Cs-137 662 keV and Co-60 1173/1332 keV (s about 40), plus a pulser
peak at 50 counts per second:

- HPGe: 1950 keV.
- NaI: 2800 keV, beyond the natural lines.

A loss fraction L is applied to **every** peak, the pulser included, emulating random summing.
L cycles through 0, 0.05 and 0.10 over the realisations. There are 40 realisations per detector,
with seeds `seed_of(det, "refpeak", i)`. The analysis is run with `reference_peak` = {energy,
rate 50, rate_rel_unc 0}.

"True" activities are the true pre-loss counts times the line's counts-to-Bq factor without the
correction (`w0 = A0 / N0`, from the same spectrum analysed without `reference_peak`).

| id | metric | limit | rationale |
|---|---|---|---|
| {det}.ref.bias | mean (A - A_true)/A_true, all L | abs <= 0.01 | the losses are 5-10 %; the correction must remove them to 1 % |
| {det}.ref.no_loss_bias | same, L = 0 only | abs <= 0.01 | the correction must not bias a spectrum without losses |
| {det}.ref.cov1 | fraction of \|z\| <= 1, u including u_rel(K) | in [0.55, 0.81] | binomial band for 120 lines |
| {det}.ref.cov2 | fraction of \|z\| <= 2 | in [0.89, 1.0] | |
| {det}.ref.uncorrected_bias | the same bias without the correction | report | shows that the correction matters |
| {det}.ref.missing_refused | the reference peak absent: the calculation is refused | >= 1.0 | never silently uncorrected |

All existing pre-registered criteria apply unchanged. No PASS -> FAIL is allowed.

Before: `docs/baseline/after_RB1`. After: `docs/baseline/after_RP1`. Both names were checked to
be free before the run.

## Results (after_RP1, 2026-10-20)

| id | HPGe | NaI | limit | status |
|---|---|---|---|---|
| ref.bias | -0.0101 | -0.0300 | abs <= 0.01 | **FAIL** / **FAIL** |
| ref.no_loss_bias | -0.0146 | -0.0246 | abs <= 0.01 | **FAIL** / **FAIL** |
| ref.cov1 | 0.708 | 0.567 | in [0.55, 0.81] | PASS / PASS |
| ref.cov2 | 0.983 | 0.933 | in [0.89, 1.0] | PASS / PASS |
| ref.uncorrected_bias | -0.0590 | -0.0773 | report | |
| ref.missing_refused | 1.0 | 1.0 | >= 1.0 | PASS / PASS |

Bias by loss L = 0 / 0.05 / 0.10: HPGe -0.015 / -0.006 / -0.009; NaI -0.025 / -0.028 / -0.038.

The four bias criteria fail. Their limits are **not** changed.

### Cause (found after the results)

The bias criteria were meant to measure the correction. They also measure the area bias of the
small nuclide peaks, a design error of this protocol:

- The "true" activity is the true count times the counts-to-Bq factor, w0 = A0 / N0.
- The corrected activity is K times the *fitted* count.
- The ratio of the two therefore includes the fitted / true area of the nuclide peaks (s about 40).

A separate diagnostic over 12 spectra per detector (`find_peaks`, outside the benchmark) gave a
fitted / true area of:

| peak | HPGe | NaI |
|---|---|---|
| pulser (180 000 counts) | 0.9985 | 0.9994 |
| nuclide peaks (s about 40) | 0.993 | 0.980 |

Two report-only metrics were then added to the benchmark. They are marked post hoc in
`acceptance.py` and change no limit:

| id | HPGe | NaI | meaning |
|---|---|---|---|
| ref.k_bias | +0.0006 | +0.0003 | mean K (1 - L) - 1: error of the correction factor alone |
| ref.fit_bias | -0.0107 | -0.0303 | mean fitted / true pre-loss area of the nuclide peaks, loss removed |

`bias` is approximately `k_bias + fit_bias`. The correction recovers losses of 5-10 % to better than
0.1 %. The residual -1 % (HPGe) and -3 % (NaI) is the existing low-bias of weak-peak areas, which
is present with or without the correction.

That weak-peak area bias, mainly on NaI, is a separate defect for a future increment. The coverage
criteria pass, so the uncertainties cover it at this signal level.

All other criteria are identical to `after_RB1`. No criterion went from PASS to FAIL. The 20
failed criteria are the 16 known before plus the 4 above.

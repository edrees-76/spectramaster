# Reagent blank correction: evaluation protocol (pre-registered)

Written 2026-10-20, **before** the implementation and before any evaluation result. The limits
below must not be changed after results are known. A result outside a limit is reported as a
failure.

## Motivation

Genie 2000 has a peak-area correction chain (Customization Tools manual ch. 3, published
documentation; no vendor software was decompiled):

- reference peak correction;
- background subtraction (peak by peak);
- reagent blank correction.

SpectraMaster already subtracts a measured background spectrum, peak by peak or as a full
spectrum, and benchmarks it in `background_peak` and `background_spectrum`.

What is missing is the **reagent blank**. A blank sample is prepared with the same reagents,
container and geometry as the samples, but without sample material, and is counted like a sample.
Activity found in it comes from the preparation, not from the sample, and must be subtracted
from every sample prepared the same way.

## Change

`compute_activities(spectrum, curve, options, background, blank=...)` takes the results of the
blank's own analysis (a `QuantResults` from the same efficiency curve, options and laboratory
background). For each gamma line, with `A_b` the blank's line activity at the blank's reference
date and `u_b` its **counting** standard uncertainty:

```
A_b'  = A_b exp(-lambda (t_ref,sample - t_ref,blank))      decay to the sample reference date
A     = A_gross - A_b'                                       Bq, before division by the sample quantity
u_count(A)^2 = u_count(A_gross)^2 + u_b'^2                    independent measurements
```

How each uncertainty component is treated:

- Efficiency, emission probability and attenuation stay relative components of the net value.
  They are fully correlated between sample and blank, because the blank uses the same curve,
  line and geometry.
- The blank enters the null hypothesis. Its counting variance is added to the decision-threshold
  variance, in window counts: `sigma0^2 += (u_b' f_w / w)^2`. This applies to Currie and to
  ISO 11929.
- A line with no peak in the blank, or not analysed in it, is not corrected, and this is
  reported. Negative values are kept: a blank below zero is subtracted as it is.
- Nothing changes when no blank is given.

## Benchmark (new category `reagent_blank`, HPGe and NaI)

Each realisation is a triple of spectra, all with seeds `seed_of(det, "blank/...", i)`:

- **Laboratory background:** the `background_pairs` background, at 2x the live time.
- **Blank:** the background rate, plus a reagent contamination of Cs-137 (s about 15) and
  Mn-54 834.8 keV (s about 15).
- **Sample:** the background rate, plus the same reagent contamination, plus the sample's own
  Cs-137 (s about 40) and Co-60 1173/1332 keV (s about 40).

The blank and the sample are each analysed with the background in full-spectrum mode. That mode
passes in both detectors, so it tests the blank correction alone. The sample is then analysed
again with the blank. All have the same live time, so there is no decay correction here; decay is
covered by unit tests. 40 realisations per detector.

"True" values are in activity units: the true sample-only net counts times the line's counts-to-Bq
factor `w = A_gross / N_net`.

| id | metric | limit | rationale |
|---|---|---|---|
| {det}.blank.bias | mean (A - A_true)/A_true over the present lines (Cs-137 662, Co-60 1173 and 1332) | abs <= 0.03 | the same limit as the measured-background net bias |
| {det}.blank.cov1 | fraction of \|z\| <= 1, z = (A - A_true)/u_count(A) | in [0.55, 0.81] | the blank's counting uncertainty must be included (binomial band for 120 lines) |
| {det}.blank.cov2 | fraction of \|z\| <= 2 | in [0.89, 1.0] | |
| {det}.blank.false_detect | Mn-54 (blank only) declared detected after correction | <= 0.125 | k_alpha = 1.645 gives 5 %; 5 of 40 or fewer (binomial P(fail) about 1.4 %) |
| {det}.blank.uncorrected_detect | Mn-54 declared detected **without** the blank | report | shows that the correction matters |
| {det}.blank.mn54_z_mean | mean z of Mn-54 after correction | report | |

All existing pre-registered criteria apply unchanged. No PASS -> FAIL is allowed.

Before: `docs/baseline/after_R2` (main cdcc54d). After: `docs/baseline/after_RB1`.

## Result (2026-10-20)

`docs/baseline/after_RB1` against `after_R2`:

- **All new criteria pass, and no criterion goes from PASS to FAIL.** The same 16 criteria fail as
  before; they are known limitations not related to this change.
- Every existing category and every G-1, EML and IDB result is identical, value for value,
  because nothing changes without a blank.
- The full test suite gives 1000 passed, 67 skipped.

| criterion | HPGe | NaI | limit |
|---|---|---|---|
| blank.bias | -0.0044 | -0.0043 | abs <= 0.03 |
| blank.cov1 | 0.72 | 0.74 | [0.55, 0.81] |
| blank.cov2 | 0.97 | 0.975 | [0.89, 1.0] |
| blank.false_detect (Mn-54, reagents only) | 0.025 | 0.0 | <= 0.125 |
| blank.uncorrected_detect (report) | 1.0 | 1.0 | - |
| blank.mn54_z_mean (report) | -0.02 | -0.22 | - |

Without the blank, the reagent-only Mn-54 was declared detected in every sample. With it, the
false detection rate is within what k_alpha allows. The blank's Cs-137 was subtracted in every
realisation.

Limitations:

- A line with no peak in the blank is not corrected. It is reported, but no upper limit is
  subtracted.
- A net value of exactly zero gives an infinite relative counting uncertainty. This is an
  existing representation, by relative components, and is not specific to the blank.
- The blank is not yet selectable in the interface. This increment covers the engine and the CLI
  (`activity --blank FILE`).

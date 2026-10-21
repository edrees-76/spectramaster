# Manual refits of net spectra: variance and negative channels (pre-registered)

Written 2026-10-21, **before** the implementation. The rules and limits below must not be changed after
results are known. A result outside a limit is reported as a failure.

## Motivation (third external review, Codex H1, also open after round 2)

`analysis.manual.refit_region` clips every channel at zero (`np.maximum(counts, 0)`) and fits with
Poisson weights taken from the (clipped) counts. For a background-subtracted spectrum S - kB the
channel contents are not Poisson counts; their variance is S + k^2 B. Codex's case: a peak of area
1000 on a continuum of 1000 counts per channel, background subtracted. The manual fit reports
999.9 +- 31.7, the same model with the variance S + k^2 B gives 995.6 +- 149.4. The uncertainty is
about 4.7 times too small, and negative net channels are silently raised to zero, which biases the
continuum and the area upwards.

`find_peaks` already accepts `variance=` (since the measured-background work, PR #35), keeps negative
channels and uses the variance in every weight and uncertainty. The manual refit does not.

## Change

- **R1.** `refit_region(..., variance=None)`. With a variance (one finite value per channel), the
  counts are used as they are (negative channels kept), the width model, the fit weights and the
  uncertainty floor use that variance, exactly as `find_peaks(..., variance=...)` does. The fit
  options record `"variance": "explicit"` and the variance's SHA-256 (not the array), so that the
  record stays small and a repeat can check it was given the same variance.
- **R2.** Without a variance, a spectrum whose contents are not Poisson counts (`not_poisson_note`:
  background subtracted, stripped, changed by an operation) or that has negative channels is still
  fitted as before, but not silently: every peak's note and the fit options state that the
  uncertainties are not valid, and how many negative channels of the region were set to zero.
- **R3.** `Session.refit_region` (and the add/remove-and-refit helpers) pass `variance` on; the
  recorded edit details are JSON-serialisable (no array).
- **R4.** A raw Poisson spectrum without a variance is fitted exactly as before (no numerical change).

## Criteria

| id | criterion | limit |
|---|---|---|
| MF.C1 | Codex H1 case (peak 1000 on 1000/channel, S and B independent Poisson with fixed seeds, k = 1): manual u with the variance vs `find_peaks(variance=)` u of the same peak | ratio within [0.9, 1.1] |
| MF.C2 | the same case, 300 seeded realisations: fraction with \|A - 1000\| <= u | within [0.60, 0.78]; fraction within 2u >= 0.90 |
| MF.C3 | a net region with negative channels, with the variance | the fitted data equal the given counts (no channel clipped) |
| MF.C4 | raw Poisson spectrum without a variance | areas, uncertainties and centroids identical to the previous code (relative difference < 1e-12) |
| MF.C5 | subtracted spectrum without a variance | every peak note and the options state the uncertainties are not valid and the number of negative channels set to zero |
| MF.C6 | session refit with a variance | edit details JSON-serialisable and contain the variance SHA-256; a wrong-shaped variance raises ValueError |
| MF.C7 | benchmark `after_MF1` vs `after_CC1` | no PASS -> FAIL |

The benchmark does not use manual refits, so it is not expected to change.

**Engine version.** Every call possible before this change (no `variance` argument) keeps its numbers
(R4); only notes are added on non-Poisson spectra (R2). Stored results do not change, so
`ENGINE_VERSION` stays 1.3.0. If any stored number turns out to change, it is raised and this is
recorded in the results.

Results: appended below; `after_MF1` (the name was checked to be free).

## Results (2026-10-21)

The protocol's SHA-256 was recorded before the implementation (`b296e2b7...c611`); the sections above
are unchanged. Tests: `tests/test_manual_fit_variance.py`. Five of its six tests fail on the previous
code and pass now; the sixth (raw spectrum, no note) passes on both.

| id | result | status |
|---|---|---|
| MF.C1 | seed 1: manual u 223.1 (default free width) vs `find_peaks(variance=)` u 135.2, ratio 1.65 | **FAIL** |
| MF.C2 | 300 realisations: within u 0.697, within 2u 0.967 | PASS |
| MF.C3 | two channels set to -400 with the variance: the fitted data equal the given counts, negatives included | PASS |
| MF.C4 | 480 values (areas, uncertainties, centroids, FWHM; HPGe, NaI, doublets, three width options) against the previous code: relative difference 0, notes identical | PASS |
| MF.C5 | subtracted spectrum, no variance: every note and `options["not_poisson"]` say "uncertainties not valid; N negative channel(s) of the region set to zero" | PASS |
| MF.C6 | session refit: edit details JSON-serialisable with `variance: explicit` and a 64-character SHA-256; a variance one channel short raises ValueError | PASS |
| MF.C7 | `after_MF1` vs `after_CC1`: 154 PASS / 13 FAIL / 60 REPORT, no PASS -> FAIL | PASS |

**MF.C1 failed, and the limit is not changed.** The criterion compared two different models. The
manual fit's default width is free within x0.5..x2 of the resolution model, while the automatic search
allows x0.7..x1.4. For this weak peak (about 7 sigma) the wider width freedom costs precision; the
criterion should have named the width option. That is a design error of the protocol, not a defect
found in the variance handling. Two checks made after the result was known, and therefore not
criteria, support this:

- With the width held at the model (`width="model"`), the same peak gives u 135.1, ratio 1.00.
- Over 300 realisations (seeds 1000-1299) the manual uncertainty with the default free width matches
  the actual scatter of its areas (mean u 206, standard deviation of the areas 187), and coverage is as
  above. The automatic search: mean u 138, standard deviation 113, coverage 0.750 / 0.983.

**Effect, same 300 realisations, default options:**

| manual fit | median area (true 1000) | standard deviation | median u (10th-90th percentile) | within u | within 2u |
|---|---|---|---|---|---|
| previous (clipped, Poisson weights) | 919 | 293 | 180 (113-288) | 0.720 | 0.950 |
| now (variance S + k^2 B) | 996 | 187 | 182 (148-265) | 0.697 | 0.967 |

In this case the main defect of the previous code was a biased and imprecise area: clipping negative
channels raises the continuum. Codex's reported uncertainty 4.7 times too small was not reproduced on
average here. Some realisations show it: seed 1 gives u 83 before against 223 now. The
uncertainty floor of the previous code limited the effect in most realisations.

**Benchmark.** `after_MF1` differs from `after_CC1` only in the runtimes and in one tie: in the IDB
list of the most frequent implausible nuclides, HPGe Sr-85 and HPGe Fe-59 (15 each) swap places at the
cut-off. All values are equal.

**Engine version** stays 1.3.0, as registered: every call possible before keeps its numbers (MF.C4),
and only notes are added.

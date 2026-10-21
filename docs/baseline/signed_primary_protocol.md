# Signed primary result for every line: evaluation protocol (pre-registered)

Written 2026-10-21, **before** the implementation and before any run of it. The limits below must
not be changed after the results are known. A result outside a limit is reported as a failure.

Round-3 review, plan item 6a: Codex M2 and Gemini H3b. Design and the user's decisions:
`docs/design/signed_primary_result.md`. The user chose estimator E1, decision rule D1 as the default
with D2 as an option, and negative values outside the activity column.

## Changes

**R1, primary result (E1).** Every line whose window lies in the spectrum gets a signed primary
result.

- **Peak found:** the fitted net area, as now. Method `"fit"`.
- **No peak:** the window estimator y = G - B over the window of `continuum_under` (E +- 1.25 FWHM,
  m side channels each side), divided by its Gaussian fraction f_win. Method `"window"`. G is the
  window sum; B = side * n / (2m).
  - **No background:** u^2(y_win) = G + side (n / 2m)^2.
  - **Spectrum mode:** the same on the background, scaled by k and subtracted. Its variance
    k^2 (G_b + side_b (n / 2m)^2) is added.
  - **Peak mode:** the background-fitter area under the line, k N_b (`BackgroundFitter.at_energy`),
    is subtracted. Its variance u_b^2 is added.
  - **Reagent blank:** subtracted as for found peaks, with its uncertainty.
- **Interference:** a window whose range, side channels included, overlaps +- 1.5 FWHM of a found
  peak not matched to this line gets method `"interfered"`. Its value is reported but never used for
  the decision or the ISO best estimate.

New fields:

| field | content |
|---|---|
| `LineResult.primary`, `primary_u_count` | Bq, counting part |
| `LineResult.primary_net`, `primary_net_unc` | counts, full-peak equivalent |
| `LineResult.primary_method` | how the value was obtained |
| `NuclideResult.primary`, `primary_u`, `primary_method` | total standard uncertainty, combined like the activity (key line or weighted mean) |

**R2, decision rule.** `ActivityOptions.decision` = `"search"` (default, D1) | `"iso11929"` (D2).

- **D1:** detected only for a found peak with net > L_C, as now. A line whose window result exceeds
  L_C gets the note "above the decision threshold without a search peak".
- **D2:** a non-interfered window result above L_C (window counts, after the blank) is detected. It
  then becomes the line's activity, so it enters the combination like a found peak.
- Every result records the rule in `QuantResults.notes`.

**R3, ISO 11929 values.** With `mda_method = "iso11929"`, the best estimate, its uncertainty and the
coverage interval are computed from the primary result of every nuclide. Today they are computed only
when an activity exists. Interfered primary results give none.

**R4, display.**

- `activity` keeps its meaning. The activity column still shows "< MDA" for nuclides not detected.
- New column "primary result Bq +- u", filled for nuclides not detected, in the results table, report
  and print (`quant_table`).
- New keys `primary_bq`, `primary_u_bq` and `primary_method` in `result_row` / CSV.
- Saved sessions get the new fields with defaults; old sessions load unchanged.
- `ENGINE_VERSION` goes up one minor version.

## Harness

`spectramaster/validation/primary.py`, new, uses only the synthetic generator:
`synthetic.make_spectrum`, `scenarios.base_continuum`, `area_for_snr` and `seed_of`. It uses the
benchmark's `_flat_curve`. Seeds are fixed by category name. Quantities are compared in counts
(`primary_net` versus the true area), so they do not depend on the curve.

Spectra: HPGe and NaI separately. Co-60 (s ~ 40) is always present.

| set | content | n per detector |
|---|---|---|
| zero | Cs-137 661.657 keV absent | 200 |
| weak | Cs-137 at s = 1, 2 and 3 (`area_for_snr`) | 100 each |
| H3b | Cs-137 at s = 2.45 | 100 |
| interference | Cs-137 absent, a strong peak (s ~ 40) at 661.657 keV + 1 FWHM | 50 |
| M2 | background spectrum with K-40 1460.82 keV of area 10000; sample with the same continuum and K-40 area 5000; equal live times | 20 |
| background-absent | `scenarios.background_pairs(det, 40)`, lines of `BKG_ABSENT` (true net 0) | 40 pairs, in both background modes |

z = (primary_net - true area) / primary_net_unc.

## Criteria

| id | test | limit |
|---|---|---|
| PR.C1 | zero set, every line (any method) | \|mean z\| <= 0.2 and fraction \|z\| <= 2 in [0.91, 0.99], per detector |
| PR.C2 | background-absent set, each mode | \|mean z\| <= 0.3 and fraction \|z\| <= 2 >= 0.90, per detector and mode |
| PR.C3 | weak set, per s | \|mean z\| <= 0.3 and fraction \|z\| <= 2 in [0.90, 0.99]; with `mda_method="iso11929"` the coverage interval holds the true activity (true area x the line's Bq per count) in >= 0.89 of the spectra |
| PR.C4 | H3b set | primary result and ISO best estimate present in all; D2 detection fraction in [0.65, 0.92]; D1 detection fraction <= D2 fraction |
| PR.C5 | M2 set, both modes | primary_net < 0 in >= 18 of 20; best estimate >= 0 and interval present in all; activity None and not detected |
| PR.C6 | interference set | primary_method "interfered" in all 50; never detected under D2; no best estimate from it |
| PR.C7 | D2 false detections on the zero set | detected fraction in [0.010, 0.090] (binomial 99 % around alpha = 0.05, n = 200) |
| PR.C8 | Unchanged under D1 | For lines with a found peak: activity, u, detected, decision threshold and MDA bit-identical to `main` (zero and weak sets, both detectors, checked against the previous code copied into the test run). Benchmark after_ME1 -> after_PR1 (name checked free): no PASS -> FAIL, every value identical except runtimes. |
| PR.C9 | CRM protocol re-run | identical criteria values to after_ME1 |
| PR.C10 | Session round trip; a session saved without the new fields loads | new fields kept; defaults for old files |
| PR.C11 | Full test suite | passes; any changed existing test listed with its reason |

**Expected, but not criteria.** D2 detects about 79 % of the H3b set (P(z > 1.645 - 2.45)). D1
detects fewer, since the search needs about 3 sigma.

## Results (2026-10-21, first evaluation)

The text above was recorded with SHA-256
`85b1fc129116a2cf78b773ff9e80419d9ede6a14ecee822f9df9736ede32ccdb` before the implementation. The
harness output is `after_PR1/signed_primary_results_v1.md`.

| criterion | HPGe | NaI |
|---|---|---|
| PR.C1 zero, mean z / cov2 | 0.073 / 0.955 PASS | **-1.92 / 0.505 FAIL** |
| PR.C2 spectrum mode | 0.126 / 0.95 PASS | 0.134 / 1.00 PASS |
| PR.C2 peak mode | **0.460** / 0.917 **FAIL** | **-3.70 / 0.025 FAIL** |
| PR.C3 s = 1 (mean z, cov2, interval) | -0.117, **0.89**, 0.96 **FAIL** (cov2) | **-2.09, 0.41**, 1.00 **FAIL** |
| PR.C3 s = 2 | 0.063, 0.95, 0.99 PASS | **-1.54, 0.51**, 1.00 **FAIL** |
| PR.C3 s = 3 | 0.203, 0.98, 0.99 PASS | **-1.14, 0.61, 0.68 FAIL** |
| PR.C4 present / D2 / D1 <= D2 | **best missing in 1 of 100**, **0.56**, 0.24 **FAIL** | present, **0.30**, 0.29 **FAIL** |
| PR.C5 M2 (both modes): negative / best / no activity | 20 / 20 / 20 PASS | 20 / **0** / 20 **FAIL** |
| PR.C6 interference | 50 / 0 / 0 PASS | 50 / 0 / 0 PASS |
| PR.C7 D2 false detections | 0.050 PASS | **0.000 FAIL** |
| PR.C8 found peaks unchanged | 6468 values compared with `main`, 0 different: PASS | (same run) |

Not yet run: PR.C9-C11, because R1 is not shippable as it stands (below).

### Causes (diagnosed after the run)

1. **The window estimator is biased on a curved continuum.**
   - B interpolates the side regions linearly. The NaI window is wide: 40 channels plus 23 side
     channels each side at 662 keV. The convex continuum then makes B too large.
   - On the noiseless synthetic continuum, the window result is **-353 counts**, against a standard
     uncertainty of about 175. This explains every NaI failure in C1, C2 peak mode, C3, C4 and C7
     (negative bias, so no false detections).
   - The same B already enters the decision threshold, but there only as a variance.
2. **The interference rule fires on the wrong peaks.**
   - HPGe H3b: the line's own peak was found at 667.3 keV, outside the match tolerance, and counted as
     "interfering".
   - NaI M2: peaks found on the shoulders of the negative K-40 structure of S - kB (1331-1341 and
     1593 keV) marked every window as interfered, so no best estimate was given.
3. **HPGe peak mode, C2: the two estimators do not cancel.** The window result of the sample has the
   background fitter's area subtracted, a different estimator. Bi-214 609 keV gives mean z +0.61 and
   Pb-214 352 keV +0.81. In spectrum mode the same window estimator is used for both spectra, and C2
   passes.
4. **C4's limit used the wrong scale.** s from `area_for_snr` is A / sqrt(B), while the decision
   threshold uses sigma_0 = sqrt(B (1 + n / 2m)), about 1.35 sqrt(B). s = 2.45 is therefore about
   1.8 sigma_0, with an expected detection probability of about 0.57, not 0.79. HPGe 0.56 matches
   this. The limit [0.65, 0.92] is a protocol design error, reported as FAIL and not changed.
5. HPGe C3 s = 1 cov2 0.89 against 0.90 is within the binomial noise of 100 spectra. It is reported
   as FAIL.

R1 is not shipped in this form. Any correction needs a new pre-registered amendment with its own
criteria.

The amendment is `signed_primary_amendment_protocol.md`. Its results decide what ships.

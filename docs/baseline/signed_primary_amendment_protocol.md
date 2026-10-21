# Signed primary result, amendment 1: evaluation protocol (pre-registered)

Written 2026-10-21, after the first evaluation of `signed_primary_protocol.md` failed and before
any change for it. The limits below must not be changed after the results are known.

## Why an amendment

The first evaluation is recorded unchanged in `signed_primary_protocol.md`. Four causes were found:

1. The linear continuum B is biased on a curved continuum: NaI noiseless -353 counts against
   u = 175 at 662 keV.
2. The interference rule fired on the line's own offset peak and on artefacts of S - kB.
3. Peak mode mixed two estimators: the window result of the sample minus the fitter's area of the
   background.
4. C4 used s = A / sqrt(B) where the decision uses sigma_0, about 1.35 sqrt(B).

**Measured before writing this protocol** on the noiseless synthetic continuum, at 352, 609, 662 and
1461 keV:

| detector | linear | log-linear (geometric between the side means) | quadratic or log-quadratic fit to the sides |
|---|---|---|---|
| HPGe | 0 | 0 | 0 |
| NaI | -159 to -366 (0.9 to 2.0 u) | -38 to -92 (0.2 to 0.85 u) | about 0, but u x 1.8 |

The quadratic fit would remove the bias. Its larger variance would no longer match the decision
threshold sigma_0, which is shared with every found peak and must not change (PR.C8). So no
estimator is both unbiased and consistent with the existing limits on wide NaI windows. **The
amendment therefore checks the estimator's assumption instead of replacing it.**

## Changes

**A1, continuum check.** For each window result, B is computed twice from the same side channels:
linear (the estimator) and geometric (log-linear between the two side means, where both are
positive).

- If |B_lin - B_geo| > 0.5 u(window result), the line gets method `"curved"`. Its value is reported
  with the note "continuum too curved for the window estimator" but is never used for the decision
  or the best estimate.
- With a background spectrum, the check is made on the sample and on the background, and either
  failing is enough.
- Lines with a found peak are not affected.

**A2, interference by expected effect.** A found peak not matched to the line marks the window
"interfered" only when its expected contribution to the window result exceeds 0.5 u(window result).
That contribution is A (F_window - r F_sides), where A is its fitted area, F the fractions of its
Gaussian in the window and in the side regions, and r = n / 2m. Peaks of the background-subtracted
search are taken in background modes, as before.

**A3, one estimator in both background modes.** Peak mode subtracts k times the window result of the
background spectrum on the sample grid (`BackgroundFitter`'s aligned background and k), as spectrum
mode does. The legacy caller-supplied background-peak list keeps the old subtraction.

**A4, harness.** The H3b set places the Cs-137 line at a window result of 2.45 sigma_0, so that
area = 2.45 sigma_0 / f_win, with sigma_0 from the noiseless continuum
(`sqrt(B_lin (1 + n / 2m))`). Expected D2 detection probability: Phi(2.45 - 1.645), about 0.79.

## Criteria

Harness `spectramaster/validation/primary.py` (version 2), the same sets, seeds and sizes as before.
"Used" = method `"window"` (not interfered, not curved).

| id | test | limit |
|---|---|---|
| PA.C1 HPGe | zero set: \|mean z\| / cov2 | <= 0.2 / [0.91, 0.99] (as PR.C1) |
| PA.C2 HPGe | background-absent, each mode | \|mean z\| <= 0.3, cov2 >= 0.90 (as PR.C2) |
| PA.C3 HPGe | weak s = 1, 2, 3 | as PR.C3 |
| PA.C4 HPGe | H3b (A4) | primary and best estimate in all; D2 detection in [0.65, 0.92]; D1 <= D2 |
| PA.C5 | M2, both detectors and modes | primary_net < 0 in >= 18 of 20; activity None, not detected in all. HPGe: best estimate and interval in all. NaI: best estimate in all **or** the line marked curved or interfered (never a best estimate from such a line). |
| PA.C6 | interference set, both detectors | interfered in >= 45 of 50; never detected under D2; no best estimate from an interfered line |
| PA.C7 | D2 false detections, zero set | HPGe in [0.010, 0.090]; NaI <= 0.090 |
| PA.C8 NaI | zero, weak and background-absent sets | every line either "curved" / "interfered" (reported) or, over the used lines (if >= 20), \|mean z\| <= 0.3 and cov2 >= 0.90; the fraction marked curved is reported |
| PA.C9 | the line's own offset peak (the HPGe H3b case at 667.3 keV) | HPGe H3b: interfered in <= 2 of 100 |
| PA.C10 | found peaks unchanged against `main` (as PR.C8) | 0 differences |
| PA.C11 | benchmark after_ME1 -> after_PR1 (folder holds only the v1 harness file) | no PASS -> FAIL; every value identical except runtimes |
| PA.C12 | CRM re-run | criteria values identical to after_ME1 |
| PA.C13 | full test suite | passes; changed existing tests listed with reasons |

**Expected, but not criteria.** Most NaI lines without a peak are marked curved. On NaI, the
primary result is then reported but gives no ISO values, as before this change. HPGe lines get
them. This is a partial fix of M2 and H3b, stated as such.

## Results (2026-10-21)

The text above was recorded with SHA-256
`5f969e044750cc13ad9cce542bb5e94938ae479c90fd91ec63f56702c69c8b5f` before A1-A3 were implemented.
Harness output: `after_PR1/signed_primary_results_v2.md`.

### Harness error corrected before the final run

The first run of harness version 2 counted lines with a found peak ("fit") as "used" in PA.C8. The
protocol defines "used" as window results only (`after_PR1/signed_primary_results_v2_harness_error.md`).

- In that run, NaI weak s = 3 failed PA.C8 with mean z 0.93. Those were 37 found peaks, and search
  peaks at 3 sigma are selected upward fluctuations.
- The harness was corrected to the protocol's definition (`USED = ("window",)`) and run again.
- No limit and no estimator changed. This is recorded because the first run showed a FAIL.

### Criteria

| id | HPGe | NaI | status |
|---|---|---|---|
| PA.C1 zero: mean z / cov2 | 0.073 / 0.955 | (PA.C8) | PASS |
| PA.C2 background-absent, spectrum / peak mode | 0.126, 0.950 / 0.126, 0.950 | (PA.C8) | PASS |
| PA.C3 s = 1: mean z / cov2 / interval | -0.117 / **0.89** / 0.96 | (PA.C8) | **FAIL** (cov2, limit 0.90) |
| PA.C3 s = 2 | 0.063 / 0.95 / 0.99 | | PASS |
| PA.C3 s = 3 | 0.203 / 0.98 / 0.99 | | PASS |
| PA.C4 H3b at 2.45 sigma_0: present / D2 / D1 | all / 0.88 / 0.53 | | PASS |
| PA.C5 M2, both modes | 20 negative, 20 best, 20 no activity | 20 negative, 20 flagged (no best estimate from them), 20 no activity | PASS |
| PA.C6 interference | 50 / 0 detected / 0 best | 50 / 0 / 0 | PASS |
| PA.C7 D2 false detections | 0.050 | 0.000 | PASS |
| PA.C8 NaI used window lines | | 0 used in every set: 199 of 200 zero-set lines and 98 of the background-absent lines marked "curved" | PASS (reported) |
| PA.C9 own offset peak counted as interference (HPGe H3b) | 0 of 100 | | PASS |
| PA.C10 found peaks against `main` | 6468 values, 0 different | | PASS |
| PA.C11 benchmark after_ME1 -> after_PR1 | 154 / 13 / 60, only runtimes changed | | PASS |
| PA.C12 CRM | criteria values identical to after_ME1 | | PASS |
| PA.C13 full suite | 1318 passed, 68 skipped | | PASS |

PA.C3 s = 1 cov2 is 0.89 against 0.90, as in the first evaluation (same spectra). The binomial
standard error for 100 spectra is 0.022. It is reported as FAIL and the limit is not changed.

### Changed existing tests (PA.C13)

`tests/test_activity.py`, two tests. Both encoded the old rule "no peak, no best estimate", which R3
changes on purpose:
- `test_iso11929_best_estimate_in_results`: Co-60 without a peak now has a window primary result and
  its ISO best estimate.
- `test_iso11929_column_in_table`: the best-estimate column of that row is no longer empty.

### What ships

- **HPGe** (narrow windows): every line without a search peak gets a signed primary result. With ISO
  11929, it also gets a best estimate and a coverage interval. This fixes Codex M2 and Gemini H3b.
  Option D2 detects H3b-type signals: 88 % at 2.45 sigma_0, with 5.0 % false detections.
- **NaI** (wide windows on a curved continuum): window results are reported but marked "curved". They
  give no ISO values and no detection, as before this change. This is a partial fix, stated here.
- **Next step for NaI** (separate protocol): a polynomial continuum fitted to the end channels, as in
  Aptec's ROI background, with the decision threshold computed for that estimator.

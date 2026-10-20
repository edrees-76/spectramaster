# Area bias of medium-signal peaks: evaluation protocol (pre-registered)

Written 2026-10-20, **before** the change to the fit and before any benchmark result of the new
category. The limits below must not be changed after results are known. A result outside a limit is
reported as a failure.

## Motivation

The reference-peak benchmark (`reference_peak_protocol.md`, `after_RP1`) showed that the areas of
peaks with s about 40 are fitted low: -1.1 % on HPGe and -3.0 % on NaI. Existing categories test
strong peaks (1e5 counts) and weak peaks (s <= 10) only, so this signal range was not measured.

Diagnostics were run before this protocol, outside the benchmark, with scratch scripts and other
seeds. They gave the following picture; it motivates the change, not the limits.

**NaI.** The fitted area is low by about 1 % at s = 40 and 0.6 % at s = 80, on a continuum
exp + flat:

- On a purely exponential continuum, which the two-parameter log-linear continuum of NaI fits
  exactly, the bias is +0.0 % at s = 40.
- A straight-line continuum makes it -6 %.

The cause is the curvature of the real continuum that exp(b0 + b1 x) cannot follow over the wide
NaI fit regions. With a free width the misfit also moves the width.

**HPGe.** The bias is about -1 % at s = 20-40 and scatters between runs. Fixing the width at a
FWHM calibration does not remove it, and a curved continuum does not apply: the HPGe regions are a
few keV wide. No HPGe change is made here; its criteria measure the remaining defect.

## Change

For fits whose continuum is log-linear (raw counts of NaI, LaBr3 and CZT, as now), the continuum
gets a curvature term:

    B(x) = exp(b0 + b1 (x - xm) + b2 (x - xm)^2)

- b2 is free, bounded to |b2| (half-width)^2 <= 2. That is a factor of at most e^2 from the straight
  log-line at the region's edges, so it cannot mimic a peak.
- It belongs to the continuum: it is in `bkg` and `cont_cols` (peak inspection, background
  subtraction of fitted continua).
- Nothing changes for linear continua (HPGe) or explicit-variance fits.

**Amendment, 2026-10-20, before any result of the category on the changed engine.** The limits
above and below are unchanged; only the change itself was revised.

A scratch check (other seeds, NaI, 20 spectra per s) showed that b2 free in the fit region
removes the bias but raises the relative SD at s = 40 from 3.8 % to 6.3 % (x 1.66). That would
fail the precision criterion below, and the mean squared error would be worse than before:
under the peak, b2 trades with the area. That variant was rejected.

Revised change:

- b2 is measured by a fit of the same group on a region three times wider
  (`LOGQUAD_WIDE = 2`, the region extended by its own width on each side), with |b2| h_w^2 <= 2.
- b2 is then held fixed in the fit on the usual region.
- The bound limits the effect of an unrelated peak inside the wide region to a factor of
  e^(2/9) at the edges of the usual region.

In the same scratch check, against the unchanged engine:

- s = 40: -1.1 % -> -0.2 %, SD ratio 1.00.
- s = 80: -0.85 % -> -0.3 %, SD ratio 0.99.
- s = 20: -4.9 % -> -4.1 %. That residual has another cause.

`LOGQUAD_WIDE = 1` gave a similar bias with a slightly larger SD and was not kept.

The NaI fit takes one more group fit, so it is slower.

**Amendment 2, 2026-10-20, after the run `after_MP1`. The limits are unchanged.**

`after_MP1` turned two criteria from PASS to FAIL: `NaI.strong.cov1` (0.67 -> 0.22) and
`NaI.strong.cov2` (0.95 -> 0.50). The SD of strong-peak areas rose from 0.37 % to 0.92 %.

Cause: the wider region of a strong peak contains other strong peaks and Compton edges. These
distort b2, and with 1e5-count peaks even a small distortion is many sigma.

`after_MP1` is kept as the record of that failure. The change was revised once more:

- The wide fit's b2 is used only when the wide fit is consistent with its model:
  chi2r <= 1 + 3 sqrt(2 / dof) (`LOGQUAD_CHI2_SIGMA`).
- Otherwise b2 = 0, exactly the previous behaviour.

Scratch check (other seeds):

- NaI strong peaks: bias -0.07 %, SD 0.37 %, cov2 0.94. That is the old behaviour.
- Medium peaks: unchanged by the revision.

The final run is `docs/baseline/after_MP2`. The name was checked to be free.

## Benchmark (new category `medium_peaks`, HPGe and NaI)

- Isolated Gaussian peaks at the weak-peak energies (`_energies(det, "weak")`, 5 per spectrum).
- Base continuum (exp + flat), s in {20, 40, 80}.
- 40 spectra per s and detector (200 peaks per s), seeds `seed_of(det, f"medium_s{s:g}", i)`.
- Analysis by `find_peaks` with defaults, so the FWHM model is estimated as for any uncalibrated
  spectrum.
- Metrics per s: mean (A - A_true)/A_true of found peaks, relative SD, |z| <= 1 and |z| <= 2
  fractions, and the found fraction.

| id | metric | limit | rationale |
|---|---|---|---|
| {det}.medium.area_bias_s20 | mean relative area error, s = 20 | abs <= 0.02 | SE about 0.4 %; 2 % is systematic |
| {det}.medium.area_bias_s40 | same, s = 40 | abs <= 0.01 | SE about 0.3 % |
| {det}.medium.area_bias_s80 | same, s = 80 | abs <= 0.01 | SE about 0.15 % |
| {det}.medium.cov2 | fraction \|z\| <= 2, all s | in [0.93, 1.0] | binomial band for 600 peaks |
| {det}.medium.sd_s40 | relative SD at s = 40 | report | precision cost of the extra parameter |

A further manual criterion uses the same category run on the unchanged engine (`after_MP0`): the
NaI relative SD at each s must not grow by more than 10 % (ratio <= 1.10). The extra parameter
must not buy a bias reduction with a large loss of precision.

All existing pre-registered criteria apply unchanged. No PASS -> FAIL is allowed.

Runs:

- Before, with the new category on the unchanged engine: `docs/baseline/after_MP0`.
- After: `docs/baseline/after_MP1`.

Both names were checked to be free before the run.

## Results (after_MP0 -> after_MP2, 2026-10-20)

| id | MP0 (unchanged engine) | MP2 (final) | limit | status MP2 |
|---|---|---|---|---|
| NaI.medium.area_bias_s20 | -0.0227 | -0.0134 | abs <= 0.02 | PASS (was FAIL) |
| NaI.medium.area_bias_s40 | -0.0083 | +0.0003 | abs <= 0.01 | PASS |
| NaI.medium.area_bias_s80 | -0.0026 | +0.0025 | abs <= 0.01 | PASS |
| NaI.medium.cov2 | 0.942 | 0.947 | in [0.93, 1.0] | PASS |
| HPGe.medium.area_bias_s20 | -0.0314 | -0.0314 | abs <= 0.02 | **FAIL** |
| HPGe.medium.area_bias_s40 | -0.0142 | -0.0142 | abs <= 0.01 | **FAIL** |
| HPGe.medium.area_bias_s80 | +0.0002 | +0.0002 | abs <= 0.01 | PASS |
| HPGe.medium.cov2 | 0.923 | 0.923 | in [0.93, 1.0] | **FAIL** |

Precision, the manual criterion. The NaI relative SD ratio MP2 / MP0 at s = 20 / 40 / 80 is
1.004 / 1.013 / 1.034, all <= 1.10: PASS.

Everything else, compared with `after_MP0`:

- No criterion went from PASS to FAIL; one went from FAIL to PASS. 23 criteria fail: the 20
  known before, plus the three HPGe medium criteria above.
- `NaI.strong` is unchanged: SD 0.37 %, cov2 0.95.
- Runtime: NaI median 0.051 s -> 0.057 s.
- The reference-peak NaI bias improves only slightly, -3.0 % -> -2.8 %, still FAIL. In that
  scenario the chi2 gate mostly rejects the wide fit of the Co-60 group, so the old continuum is
  used. Why it is rejected there was not investigated.
  `after_MP1`, with the curvature ungated, gave +0.35 % there but broke the strong-peak coverage.

The HPGe medium criteria fail because of the remaining HPGe defect, which this change does not
touch. Areas at s = 20-40 are 1.4-3 % low, and the uncertainties under-cover (cov2 0.92).

Diagnostics point to the fixed model width of weak peaks:

- The default HPGe resolution is up to 8 % narrower than the detector's at low energy.
- The width becomes free only when z > 25.

This is a separate next step.

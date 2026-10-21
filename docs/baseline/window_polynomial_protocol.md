# Quadratic continuum for curved window results (NaI): pre-registered protocol

Written 2026-10-21, before implementation. This is item 6b, the next step named in
`signed_primary_amendment_protocol.md`. Results are appended below the line after the run; nothing
above it changes after its SHA-256 is recorded.

## 1. Defect

A line without a search peak gets a window result: G minus a linear continuum from m side channels
on each side. Amendment A1 marks the result "curved" when the linear continuum differs from a
log-linear one by more than 0.5 u.

- On NaI this marked 199 of 200 zero-set lines (after_PR1).
- A curved line gives no ISO 11929 best estimate and no D2 detection.
- So on NaI the signed primary result (Codex M2, Gemini H3b) is reported but unusable.

## 2. Measurements made before writing this protocol

Prototype scripts were kept outside the repository and do not change the engine. They used the
synthetic NaI continuum of the harness and a stress continuum: the same continuum plus a Compton
plateau and edge of a 1460.8 keV line (level 40 × gain/0.5).

**Noiseless.** Bias of B in units of sigma_0 = sqrt(B + Var B), and sigma_0 relative to the linear
estimator's, at 200-2000 keV:

| estimator | NaI bias | sigma_0 ratio |
|---|---|---|
| linear (current), m sides | +0.7 to +2.1 | 1 |
| quadratic, m sides | 0.00 to 0.02 | 1.73-1.79 |
| **quadratic, 2m sides** | **-0.01 to +0.09** | **1.16-1.18** |
| log-quadratic, 2m sides | 0.00 to 0.02 | 1.15-1.18 |
| linear in log, m or 2m sides | up to +1.97 | 0.88-1.00 |
| cubic, 3m sides | -0.15 to -0.01 | 1.01-1.02 |

**Poisson noise** (quadratic, 2m sides, weights from a first unweighted fit):

| case | mean z | sd z | coverage of \|z\| <= 2 | P(z > 1.645) |
|---|---|---|---|---|
| smooth continuum, 200-2000 keV, 1500-3000 realisations each | -0.10 to +0.04 | ~1.00 | 0.953-0.956 | 0.037-0.060 |
| near a Compton edge, 1000-1461 keV | -12 to +0.6 | | | up to 0.13 |

Every estimator fails near an edge, so a check is needed. Fraction of realisations flagged:

| check | smooth (false flags) | edge 1000 / 1400 / 1461 keV |
|---|---|---|
| B over m sides vs B over 2m sides, \|difference\| > 3 sd | 0.002-0.004 | 0.62 / 1.00 / 0.09 |
| cubic vs quadratic on 2m sides, > 3 sd | 0.003-0.012 | 1.00 / 1.00 / 1.00 |
| **chi-square of the quadratic fit to the 2m sides, p < 0.001** | **0.000-0.003** | **1.00 / 1.00 / 1.00** |

## 3. Change

Only lines that A1 marks "curved" are affected. Lines with a search peak, lines whose linear window
result is not curved, and every HPGe line handled as before are unchanged.

1. **Quadratic continuum.** For a curved line, B_q is computed from 2m side channels on each side
   of the same window: a quadratic least-squares fit, weighted by its own first unweighted fit's
   values (floored at 1), integrated over the window channels. B_q is a linear combination
   sum c_i y_i of the side channels.
   * Window result: G - B_q.
   * Variance: G + sum c_i^2 y_i (with y_i floored at 0).
   * With a background spectrum, the same estimator is applied to the background (spectrum mode:
     the scaled background spectrum; peak mode: `BackgroundFitter`'s aligned background and k, as
     A3), and k times its result is subtracted, adding k^2 times its variance.
2. **Smoothness check.** The line stays "curved" (not used, as now) when:
   * the 2m sides do not fit in the spectrum; or
   * the chi-square of the weighted quadratic fit to the 2m sides has p < 0.001 (dof = 4m - 3),
     for the sample or, with a background spectrum, for the background.

   The note then says "continuum not smooth enough for a polynomial window (e.g. a Compton edge)".
3. **Interference** (A2, generalised). A found peak's expected contribution is
   A (F_window - sum c_i F_i), where F_i is the fraction of its Gaussian in channel i. A
   contribution above 0.5 u marks the line "interfered", as now.
4. **Its own decision threshold.** The quadratic estimator has its own sigma_0:
   * the same variance terms as now (background, blank, reference peak);
   * the sample's linear term B (1 + n/2m) replaced by B_q + sum c_i^2 f_i, with f the fitted
     values;
   * in spectrum mode, the background's linear term replaced in the same way.

   L_C and L_D follow from this sigma_0 with the same rule (Currie or ISO 11929) and k values.
   They decide detection under D2 for this line. The line's reported decision threshold and MDA
   (the shared, linear ones of every line) do not change. The quadratic threshold is reported in
   new fields `window_lc_counts` and `window_decision_threshold`, and in the note.
5. A line evaluated this way keeps `primary_method = "window"`; the new field `window_continuum`
   is `"quadratic"` (otherwise `"linear"`). The note says "quadratic continuum (curved for the
   linear window)". ENGINE_VERSION becomes 1.9.0.

This is a quadratic end-channel continuum in the spirit of the Aptec ROI background named in the
amendment. No equivalence with Aptec is claimed or tested.

## 4. Criteria

Harness `spectramaster/validation/primary.py`, version 3: the same sets, seeds and sizes as version 2,
plus an **edge set** (NaI only). It has 100 spectra with the base continuum, a Compton plateau of an
850 keV line (edge at 653.6 keV, level 40 × gain/0.5) and the two Co-60 peaks; Cs-137 is absent. "Used"
= method `"window"` (linear or quadratic). Results go to `docs/baseline/after_WP1/`.

| id | test | limit |
|---|---|---|
| WP.C1 | NaI zero set: fraction of lines used; over used lines \|mean z\| and cov2 | used >= 0.90; \|mean z\| <= 0.2; cov2 in [0.91, 0.99] |
| WP.C2 | NaI background-absent set, each mode, used lines | used >= 0.80 of lines; \|mean z\| <= 0.3, cov2 >= 0.90 |
| WP.C3 | NaI weak s = 1, 2, 3, used lines (window results) | \|mean z\| <= 0.3, cov2 in [0.90, 0.99] when >= 20 used; interval coverage (all lines) >= 0.89 |
| WP.C4 | NaI H3b set (area at 2.45 linear sigma_0, as A4) | primary and best estimate present in all; D2 detection >= 0.50 (expected about 0.67, since sigma_0 is ~1.17 × linear); D1 <= D2 |
| WP.C5 | NaI M2, both modes | primary_net < 0 in >= 18 of 20; best estimate and interval in all 20; activity None, not detected in all |
| WP.C6 | NaI interference set | interfered >= 45 of 50; never detected under D2; no best estimate from an interfered line |
| WP.C7 | NaI D2 false detections, zero set | in [0.010, 0.090] |
| WP.C8 | NaI edge set | D2 false detections <= 0.090; used lines (if >= 20) \|mean z\| <= 0.3, cov2 >= 0.90; fraction still "curved" reported |
| WP.C9 | HPGe: every harness value | identical to version 2 (after_PR1) |
| WP.C10 | found peaks against `main` (as PA.C10) | 0 differences |
| WP.C11 | benchmark after_AX1 -> after_WP1 | 154 / 13 / 60, no PASS -> FAIL, every value identical except runtimes |
| WP.C12 | CRM re-run (HPGe) | criteria values identical to after_PR1 |
| WP.C13 | full test suite | passes; changed existing tests listed with reasons |

**Reported, not criteria:** the NaI fraction of quadratic lines per set; the ratio of window to linear
decision thresholds.

---
## Results

(appended after the run)

Run 2026-10-21, engine 1.9.0. The text above the line is unchanged (SHA-256 of the pre-registered
part still 588ebaf7991e68fbaf1988d142a4155585689d5b66ca1c206f45ac902c0f2eca). Outputs:
`docs/baseline/after_WP1/` (`signed_primary_results.md` with all measured values, `baseline.*`,
`crm_validation_results.*`).

| id | value | limit | result |
|---|---|---|---|
| WP.C1 NaI zero: used / mean z / cov2 | 0.995 / +0.004 / 0.955 (199 quadratic, 1 interfered) | >= 0.90 / <= 0.2 / [0.91, 0.99] | PASS |
| WP.C2 NaI background-absent, both modes | used 0 of 120: 80 interfered, 40 curved | used >= 0.80 | **FAIL** |
| WP.C3 s = 1 (97 used) | -0.225 / 0.969, interval 0.98 | | PASS |
| WP.C3 s = 2 (85 used) | -0.084 / 0.941, interval 0.99 | | PASS |
| WP.C3 s = 3 (61 used) | **-0.649** / 0.934, interval 1.00 | \|mean z\| <= 0.3 | **FAIL** |
| WP.C4 NaI H3b: present / D2 / D1 | all / 0.86 / 0.68 (version 2: best estimate absent, D2 0.68) | all / >= 0.50 / D1 <= D2 | PASS |
| WP.C5 NaI M2, both modes: negative / best / no activity | 20 / **0** / 20 | 18 / all / all | **FAIL** (best) |
| WP.C6 NaI interference | 50 interfered, 0 detected, 0 best | | PASS |
| WP.C7 NaI D2 false detections | 0.075 (version 2: 0.000) | [0.010, 0.090] | PASS |
| WP.C8 NaI edge set | 0 false detections; 0 used (all 100 interfered) | | PASS (see below) |
| WP.C9 HPGe, every harness value | 0 differences from version 2 | 0 | PASS |
| WP.C10 found peaks against `main` | 1170 values (234 lines, zero and weak sets, both detectors, Currie and ISO), 0 different | 0 | PASS |
| WP.C11 benchmark | 154 / 13 / 60, no PASS -> FAIL; one value other than runtimes differs (below) | | **FAIL as written** |
| WP.C12 CRM | criteria values identical to after_PR1 (only `engine_version` differs) | | PASS |
| WP.C13 full suite | 1363 passed, 69 skipped; no existing test changed | | PASS |

Reported: NaI window decision threshold / linear threshold, zero set, mean 1.160 (expected about 1.17).

**The three FAILs, recorded as they are.** No limit, estimator or check was changed after the run.

* **WP.C2 and WP.C5 (background spectrum sets).** These sets are unchanged from version 2 (identical
  method counts and values).
  * 80 of the 120 background-absent lines, and all 20 M2 K-40 lines, are "interfered".
    The *linear* interference rule (A2) marks them before the continuum is looked at. In M2 the
    background-subtracted search finds a peak near 1331 keV. This protocol leaves that rule
    unchanged (§3: only curved lines are affected).
  * The other 40 lines (Pb-214 351.9 keV, every pair) stay "curved". The chi-square check rejects
    the quadratic fit in both sample and background (p = 0): the 2m sides reach neighbouring
    lines of that scenario.
  * The limits were written without first looking at the version 2 method counts of these sets,
    which already showed 80 interfered lines. That was an error in the protocol. The FAIL is kept.
* **WP.C3 s = 3.** Mean z of the 61 used lines is -0.649. Diagnosis (same 100 spectra):
  * Over all 100 spectra, the quadratic window gives mean z -0.297, cov2 0.94.
  * Over the 61 lines the search did not find, it gives -0.649.
  * About half is selection: lines without a search peak are the downward fluctuations.
  * The other half is a small negative bias of the estimator with a real peak present. The
    peak's tails reach the wider sides, and the quadratic extrapolation amplifies them.
  * s = 1 and s = 2 pass.

**WP.C11.** One value other than runtimes differs from after_AX1.
* The 15th entry of the benchmark's list of the 15 most frequent implausible IDB
  identifications is "HPGe Fe-59" (count 15) instead of "HPGe Sr-85" (count 15).
* The counts are identical. The cause is a tie broken by insertion order: the benchmark iterates
  a Python `set` of nuclide names, whose order depends on the per-process string hash seed. The
  identification code is not changed by this work.
* Evidence: the benchmark run with `PYTHONHASHSEED=0` on an export of `main` and on this branch
  gives identical values except runtimes and the engine version (15th entry Sr-85 in both).
* The criterion as written still fails. The benchmark's tie order is recorded as a separate
  finding: sort ties by name.

**WP.C8 tested less than intended.** In the edge set the search finds a peak at about 625 keV (the
Compton edge itself) in all 100 spectra, so the Cs-137 line is "interfered" before the continuum
check. The criterion passes, but the chi-square check is exercised there only by the unit tests
and the prototype (§2), not by this set.

**What ships.**

* NaI lines without a search peak on a smooth continuum now get a usable window result with an
  ISO 11929 best estimate. The zero set gives mean z 0.004 and cov2 0.955, against 199 of 200
  "curved" before.
* They also get their own decision threshold, about 1.16 times the linear one, used for D2:
  * false detections 0.075;
  * H3b-type detection 0.68 -> 0.86.
* The line's reported decision threshold and MDA are unchanged.
* Not solved: lines interfered by background-subtracted artefacts (M2, background-absent), lines
  whose wide sides reach other peaks, and a small negative bias with a real peak near the
  detection limit.

Tests: new `tests/test_window_polynomial.py` (8). No existing test changed.

# Round-7 review: background spectrum shared by the sample and its reagent blank, Gemini H2 (pre-registered)

Written 2026-10-29, before any change to the code. Gemini round-7 review
(`C:\Users\DELL\Downloads\gemini_review_round7.md`, main b3d88d1), finding H2, checked on the code
(`analysis/activity.py` line loop of `compute_activities`, `_window_primary`, `_quad_result`;
`analysis/background.py` `BackgroundFitter`; `gui/quant_panel.py` `_compute`; `tools/quant_cli.py`
`cmd_activity`, main 0b95938) and measured before this protocol was written.

## Findings

**Gemini H2: the background variance counted twice.** The GUI and the CLI analyse the reagent blank
with the same laboratory background spectrum as the sample, in the same call. Every background
estimate the engine subtracts is linear in the background counts B_i: the peak fit's estimator
(`BackgroundFitter`, peak mode, and the fit on S - kB in both modes), the window estimator and the
quadratic window. With r_i the sample result's coefficients and g_i the blank's (Bq per background
count), the background part of the net result A = A_gross - k_d A_b is sum (r_i - k_d g_i) B_i, of
variance sum r_i^2 B_i + k_d^2 sum g_i^2 B_i - 2 k_d sum r_i g_i B_i. The engine adds the first two
(inside the sample's counting uncertainty and inside the blank's `u_count`) and leaves out the
covariance, which has the opposite sign: the counting uncertainty, the decision threshold and the
detection limit are too large. Gemini: Cs-137, equal times, sample 5000, blank 2000, background
1500 counts: u_count +23.9 %, threshold +59 %.

Measured on the code (Monte Carlo, HPGe, Cs-137 661.7 keV on a flat continuum of 20 counts per
channel, sample, blank and background 1000 s each, background peak 1500 counts, blank peak 2000,
sample peak 2000 (net zero) or 5000 (net 3000), 400 realisations, seeds 10000 + i, 20000 + i,
30000 + i): at net zero the mean reported uncertainty of the net counts is 1.45 x the standard
deviation of the net counts, at net 3000 1.28 x, in both background modes; at net zero 1.5 % of the
realisations are declared detected against the nominal 5 %.

**Found while measuring H2: the sample's counting of the blank level is missing from the null
hypothesis variance.** The decision threshold's sigma0^2 holds the sample's continuum, the sample's
counting of the background level (k N_b), the background measurement and the blank's counting
uncertainty. Under the null hypothesis the sample's true content is the blank's, so the sample also
counts the blank level, of Poisson variance its expected counts, and that term is absent. Measured
(same peak, no background spectrum, blank and sample identical in expectation, 2000 counts, 400
realisations): L_C is 0.81 x 1.645 times the standard deviation of the net counts, and 8.75 % of the
realisations are declared detected against the nominal 5 %. This one is not conservative.

These measurements were made with exploratory scripts outside the repository before this protocol;
no value after a change was seen.

## Change

1. Background estimators with their coefficients. `BackgroundFitter` returns, with each
   (k N_b, k u_b), the coefficients of the estimate on the background channels. The engine keeps,
   for each line and only in memory (not saved), the coefficients of the background estimate in its
   result (Bq per background count) and in its decision-threshold variance, for every estimator:
   peak fit (both modes; in full-spectrum mode the background is then also fitted with the sample
   fit's estimator, used for these coefficients only), window, quadratic window, background fitted
   at a line without a peak.
2. Covariance with the blank. When the blank's results come from the same call path (they carry
   the coefficients), were obtained with the same background spectrum (same counts, same live
   time), and neither the sample nor the blank re-binned it (both on the background's own channels),
   then for each corrected line with C = k_d sum r_i g_i B_i (B_i the background counts, clipped at
   zero as in the fitter):
   - u_count(A)^2 = u_count(A_gross)^2 + u_count(A_b')^2 - 2 C;
   - sigma0^2 -= 2 k_d (f_w / w) sum h_i g_i B_i, h the coefficients of the background term of
     sigma0 (the quadratic window's own when its threshold is used).
   The term, in Bq^2, is saved in a new line field `blank_bkg_cov`. Otherwise (results loaded from
   a file, another background, a re-binned background, caller-supplied background peaks) nothing
   changes and a note says the shared background is counted as independent (conservative).
3. Null hypothesis variance with a blank: sigma0^2 += max(A_b', 0) f_w / w (the sample's counting
   of the blank level, in window counts), for every corrected line, with or without a background
   spectrum, Currie and ISO 11929.
4. Nothing changes without a blank. ENGINE_VERSION becomes 1.29.0.

Harness `validation/round7_shared_background.py`, fixed output folder `after_R7C`; values before the
change recorded with `--collect` into `after_R7C/round7_shared_background_before.json` (engine
1.28.0, 0b95938), committed with this protocol.

## Criteria

Monte Carlo cases of the findings (400 realisations each, seeds as above, Currie; ISO 11929 uses the
same sigma0). "Ratio" is the mean reported uncertainty of the net counts (`primary_net_unc`) over the
standard deviation of the net counts (`primary_net`) across realisations. Limits from the sampling
distribution of 400 realisations at 99 % (standard deviation +-9 %, coverage 0.683 +- 0.060 and
0.954 +- 0.027, false detection 0.05 +- 0.028), plus 3 % for the ratio's model approximations.

| ID | quantity | limit |
|---|---|---|
| RC.C1 | blank spectrum identical to the sample's, shared background, equal times, both modes | net zero; u_count^2 = 2 (u_s^2 - u_B^2) within 1e-9 relative, u_s the sample's counting uncertainty and u_B its background part (the estimates of sample and blank are the same, so the background cancels) |
| RC.C2 | shared background, net zero, peak and full-spectrum modes | ratio in [0.88, 1.12] (before 1.45); fraction detected in [0.022, 0.078] (before 0.015) |
| RC.C3 | shared background, net 3000, peak and full-spectrum modes | ratio in [0.88, 1.12] (before 1.28); fraction of \|z\| <= 1 in [0.623, 0.743], of \|z\| <= 2 in [0.927, 0.981] |
| RC.C4 | blank without background spectrum, net zero | fraction detected in [0.022, 0.078] (before 0.0875); u_count identical to before |
| RC.C5 | controls: no blank (with and without background, both modes); blank results loaded from their saved dict with a background | no blank: every number identical to before; loaded blank: u_count identical to before, the "counted as independent" note present |
| RC.C6 | benchmark (`after_R7B`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state (the `reagent_blank` values change, full-spectrum mode); suite passes, each changed existing test listed with its reason |

Before the change: RC.C1 to RC.C4 fail; RC.C5 is the control.

## Limitations

- Synthetic spectra, one line, flat continuum; the covariance needs the blank's results from the
  same session (GUI, CLI), not from a file.
- Background peaks fitted for a peak the search rebuilds without the sample's fit report (rare) use
  the rebuilt estimator, close to but not the fit's.
- The blank's own analysis is unchanged; only the sample's net result, threshold and limit change.
- Covariances between different lines (the background under one line and the blank at another)
  are not added: their estimators do not share channels unless the lines overlap.

---

## Results (`after_R7C`)

Protocol committed in 512fdf0 before the change (SHA-256 of the file
c52e45103c2404021baaf7f19924288786f4db5d1b7ecbfd0f9f70ec0f49b2d7). Engine 1.29.0.

**4 PASS / 1 FAIL as written.**

| ID | value | result |
|---|---|---|
| RC.C1 | peak and full-spectrum modes: u 10.9937 Bq, expected 10.9937 Bq; net zero | PASS |
| RC.C2 | peak_null: ratio 1.163 (before 1.447), detected 0.0425 (before 0.0150); spectrum_null: ratio 1.163 (before 1.447), detected 0.0375 (before 0.0150) | **FAIL** (ratio above 1.12) |
| RC.C3 | peak_net and spectrum_net: ratio 1.103 (before 1.276), \|z\| <= 1 0.7125, \|z\| <= 2 0.9525 | PASS |
| RC.C4 | detected 0.0475 (before 0.0875), L_C / (1.645 sd) 1.046 (before 0.814), u_count identical | PASS |
| RC.C5 | no blank identical to before; loaded blank unchanged, "counted as independent" note present | PASS |
| RC.C6 | benchmark 154 PASS / 13 FAIL / 60 REPORT, no criterion changed state against `after_R7B`; full suite 1595 passed, 2 failed, 69 skipped before the test changes below, then those files rerun: passed; the new `tests/test_round7_shared_background.py` 5 passed | PASS |

RC.C6 is evaluated outside the harness.

**RC.C2 FAIL, diagnosis.** The false detection fraction is now inside its limit in both modes, and the
ratio fell from 1.447 to 1.163, but stays above 1.12. Measured after the run with the same
realisations (exploratory, not a criterion): the fit uncertainties of the single spectra are
themselves above their observed scatter, by about 2 % for the sample's fit on S - kB, 15 % for the
blank's, and 5 % for a sample without background spectrum; the no-background null case had a ratio of
1.10 before the change and is untouched by it. The remainder is therefore the existing conservatism
of the peak-fit uncertainty at low net counts, enlarged relative to the scatter once the background
cancels; it is not from the covariance, which RC.C1 checks exactly. The limit is kept and the result
stands as written; the fit-uncertainty overestimate at low net counts is noted for later work.

**Changed existing tests** (change 3 alters the limits of every blank case, by design):
- `tests/test_self_attenuation.py::test_round4_activity_criteria` and
  `tests/test_round5_precision.py::test_full_precision_before_values_and_criteria`: RA.C1-C3 of the
  round-4 harness (and RF.C2 / RF.C4 of round 5) lock the blank cases' threshold and limit at engine
  1.14.0. With the sample's counting of the blank level in sigma0 they become: RA.C1 threshold
  13.706721 -> 13.740820 Bq (detection limit 31.5366 Bq, +0.240 % from Codex's 31.461, still within
  1 %); RA.C2 without reference peak 1.021354 / 2.059014 -> 1.406803 / 2.830053 Bq (there the blank's
  given uncertainty, 100 counts, dominated sigma0 and the blank level, 10000 counts, adds as much
  again); RA.C3 Currie 13.706721 / 27.429372 -> 13.740820 / 27.497569 Bq. The new values are held in
  `round4_activity.AFTER_R7C` and the tests use them for those quantities only; every other value
  (no blank, COI, summing, uncertainty interval) is still checked against 1.14.0 at the original limits.
  The archived round-4 and round-5 results are not changed.

Also changed: the manuals (sources), section 9.3 reagent blank.

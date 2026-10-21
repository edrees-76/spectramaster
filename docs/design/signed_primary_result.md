# Signed primary result for lines without a peak: design note

Status: **decided 2026-10-21.** The user chose E1, D1 as the default with D2 as an option, and primary
results shown in a separate column (the activity column keeps "< MDA"). Implemented under the
pre-registered `docs/baseline/signed_primary_protocol.md`. Round-3 review, plan item 6a: Codex M2 and
Gemini H3b.

## The defect

`compute_activities` (spectramaster/analysis/activity.py) gives a line an activity only when the peak
search found a peak there (`find_peaks`, min_sig = 3). Otherwise the line gets `activity = None`, the
note "no peak", `net_area = 0` and `net_unc = 0`, and only its decision threshold and MDA.

1. **Codex M2.** A negative or near-zero net signal has no estimate. Example: K-40 with a sample area
   of 5000 and a background of 10000 gives activity None in both background modes. ISO 11929 needs a
   primary result y with its uncertainty u(y) for every measurand, including y < 0. The best estimate
   and the coverage interval are derived from them.
2. **Gemini H3b.** A real net peak between the decision threshold L_C (1.645 sigma_0) and the search
   threshold (3 sigma) is reported as "no peak". The reviewer's example: 130 net counts (2.45 sigma)
   above a 1000-count background line, with L_C = 84.6, is withheld. `best_estimate` is then None
   too. The search acts as a second, stricter detection test before the ISO decision.

The decision threshold and the detection limit are computed today for exactly the estimator that is
missing. sigma_0^2 = B (1 + n / 2m) (+ background, blank and spectrum-mode terms) is the variance of
a window sum minus a side-channel continuum, that is the net counts of the window E +- 1.25 FWHM,
`continuum_under`. A found peak is compared with L_C through its fitted area. A line without a peak
has no value to compare.

## Options for the estimator (lines without a found peak)

| | estimator | pro | contra |
|---|---|---|---|
| **E1, window sum (recommended)** | y = (G - B) / f_win, with G = window sum, B = side continuum (`continuum_under`), f_win = Gaussian fraction in the window. Background modes: on S - kB with the variance S + k^2 B (spectrum mode), or G - B - k N_b with N_b from `BackgroundFitter.at_energy` (peak mode). Blank subtracted as for found peaks. | Exactly the estimator whose variance sigma_0 already defines L_C and L_D, so the decision is consistent by construction. No fit, so it is defined for any sign. Few new code paths. | Less precise than a fit when the line sits on a structured continuum. A neighbouring peak's tail inside the window biases it upwards (see the interference rule). |
| E2, constrained fit | One component fitted at the calibrated energy and width (centroid and FWHM fixed), amplitude free in sign. `manual.refit_region` already accepts a variance and negative channels (PR #39). | Same shape model as found peaks. Handles a sloping continuum. | L_C and L_D would then need this estimator's variance, not sigma_0, so the limits change for every line. More cost per line, and fit failure modes near zero. |
| E3, no change | Keep "no peak". | | Leaves both defects. |

**Interference rule (E1).** A line whose window overlaps a found peak assigned to another line, or the
±1.5 FWHM of any found peak not matched to it, gets its primary result marked "interfered". It is
reported but not used for the decision. This prevents a neighbour's tail from producing a detection.

## Options for the detection decision

| | rule | false detections | effect |
|---|---|---|---|
| **D1, unchanged (recommended default)** | detected = peak found AND net > L_C (as now) | below alpha = 5 % (the search adds a second test) | Values are no longer withheld: primary result, best estimate and coverage interval are reported for every line. Lines between L_C and 3 sigma stay "not detected", but their value is shown. |
| D2, ISO decision (option) | detected = y > y* for every line, found peak or not | alpha = 5 % per tested line by design (k_alpha = 1.645) | Fixes H3b fully. With several lines and several nuclides, some false detections are expected. The batch and benchmark false-detection criteria change meaning. |

Recommendation: **D1 as the default, D2 as an explicit option** (`ActivityOptions.decision = "search"
| "iso11929"`). Every result states which rule was used. The benchmark measures both before any
default changes.

## Where the value goes (compatibility)

`LineResult.activity` and `NuclideResult.activity` keep their meaning: a value only for a found peak
(D1) or a detected line (D2). Consumers that test `activity is None` are unchanged: the GUI quant and
ROI panels, the Aptec analyze view, the benchmark and the CRM harness. New fields:

- `LineResult.primary`, `primary_u` (Bq, signed), `primary_method` ("fit" | "window" | "interfered").
- `NuclideResult.primary`, `primary_u`, combined as now for the key line or the weighted mean.
- `best_estimate`, `best_u`, `coverage_low` and `coverage_high` are computed from the primary result
  for **every** nuclide (ISO 11929 method). Today they are computed only when an activity exists.

Reports and the GUI add a "primary result" column for lines and nuclides without an activity. Sessions
get the new fields with defaults, so old sessions load unchanged. `ENGINE_VERSION` goes up one minor
version.

## Validation plan (to be pre-registered)

Synthetic, HPGe and NaI separately, fixed seeds, with and without a background spectrum:

1. **Zero activity** (line absent): mean of y / u(y) within ±0.1, and the fraction |y| <= 2 u in
   [0.93, 0.97].
2. **Weak lines** at 1, 2 and 3 sigma_0: bias of the primary result <= 3 %, and coverage of the
   coverage interval for the true value >= 0.93.
3. **H3b case** (Gemini's example) and **M2 case** (Codex's K-40 example): primary result and interval
   present, with the expected sign.
4. **Interference:** a line 1 FWHM from a strong peak is marked "interfered" and is never detected.
5. **D2 false detections** on absent lines: within the binomial 99 % interval around alpha.
6. **Unchanged:** for lines with a found peak, activity, uncertainty and the D1 decision are
   bit-identical. Benchmark no PASS -> FAIL under D1. Under D2 the values are reported, not criteria.
7. CRM re-run: no PASS -> FAIL.

## Open questions for the user

1. E1 (window sum, consistent with the existing limits) or E2 (constrained fit)?
2. Keep D1 as the default and offer D2 as an option, or make D2 (pure ISO) the default?
3. Show negative primary results in the main results table, or only in the details and report?

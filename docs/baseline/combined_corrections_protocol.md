# Corrections used together: reference peak, background, blank, manual peaks (pre-registered)

Written 2026-10-21, **before** the implementation. The rules and limits below must not be changed after
results are known. A result outside a limit is reported as a failure.

## Motivation (third external review, verified on `fdb12d6`)

1. **Reference peak and background (Codex H3, regression of PR #35).** `reference_correction` measures
   the reference peak in `peaks`. Since PR #35 these are the peaks of S - kB in peak mode (and they
   always were in spectrum mode). A reference source or pulser present in both the sample and the
   background measurement is subtracted, and the correction stops with "reference peak not found".
   The expected rate (`reference_rate`) is measured on a gross spectrum. The sample peak must be
   measured the same way.
2. **Decision threshold with blank and reference peak (Codex H2).** Under the null hypothesis (no net
   activity) the sample's gross activity equals the blank's, A_b. The counting uncertainties of the two
   reference peaks, and the difference of their expected-rate components, then still contribute
   sqrt((A_b u_c,s)^2 + (A_b u_c,b)^2 + (A_b (u_r,s - u_r,b))^2) to the result. `var0`, which sets
   L_C and L_D, does not contain this term. The term is zero without a blank or without a reference
   peak.
3. **Manual peak edits (Gemini H2).** The activity dialog never passes the session's peaks to
   `compute_activities`, so peaks added, removed or refitted by hand are ignored. The message after a
   manual edit says the activity "needs updating", which suggests the opposite. With a background,
   `compute_activities` refits the peaks on S - kB and silently ignores a `peaks` argument.
4. **Inputs changed during a threaded calculation (Codex M1).** The worker reads the dialog's
   current blank and background, and the session records them after the calculation. A blank chosen
   while the calculation runs is recorded, with its fingerprint, although another one was used.

## Change

- **R1.** With a background spectrum (either mode), the reference peak is measured in the peaks of
  the **gross** sample spectrum (`find_peaks(spectrum, min_sig)`). Without a background, nothing
  changes: the peaks used are those of the spectrum, or those given.
- **R2.** For a line with a blank activity A_b and a reference peak correction (sample, blank or
  both), `var0` receives
  ((A_b u_c,s)^2 + (A_b u_c,b)^2 + (A_b (u_r,s - u_r,b))^2) x (fwin / w)^2.
  This is the reference term above under the null hypothesis, in the count units of `var0`, converted
  like the blank's own term. Lines without a blank or without a reference correction are unchanged.
- **R3.**
  - `compute_activities` adds a note when a `peaks` argument is replaced because a background
    spectrum is subtracted (both modes).
  - The activity dialog passes the session's peaks when the session records manual peak edits since
    its last automatic analysis. Those edits are `add_peak`, `remove_peak`, `set_peak_field` and
    `replace_peaks`. A new `status["peaks_edited"]` is set by those edits and cleared by a new
    automatic analysis.
  - With a background, the dialog adds the note that the manual edits were not used.
- **R4.** The dialog takes one snapshot at the start of a calculation: spectrum, background, blank and
  peaks. The worker computes from it, and the session records the background and blank of the
  snapshot, not the dialog's current ones.

## Criteria

| id | criterion | limit |
|---|---|---|
| CC.C1 | Codex H3 case, synthetic: sample with a Cs-137 peak and a reference peak, background with the same reference peak, expected rate = the sample's measured gross rate | both modes compute; \|K - 1\| <= 0.01 |
| CC.C2 | Codex H2 case, synthetic: blank and sample of nearly equal activity, reference correction with 10 % independent counting uncertainty in each | L_C >= 1.645 x the null reference term of R2 (in Bq) |
| CC.C3 | the same case without a blank, and with a blank but no reference correction | L_C unchanged (relative difference < 1e-9) |
| CC.C4 | manual edit, no background: a peak removed by hand | that line reported "no peak" |
| CC.C5 | manual edit with a background | the note is present; results equal those without the edit |
| CC.C6 | Codex M1 case: blank changed while the worker runs | the session records the blank used |
| CC.C7 | benchmark `after_CC1` vs the baseline current at the time of the run | no PASS -> FAIL |

The benchmark is not expected to change: none of its scenarios uses a reference peak with a
background, or a blank with a reference peak. Every value that changes will be listed.

**Engine version.** Results can change (R1, R2, R3), so `ENGINE_VERSION` is raised. Which number
depends on whether #37 (1.2.0) is merged first. It will be recorded in the results.

Results: appended below; `after_CC1` (the name was checked to be free).

## Results (2026-10-21)

The protocol's SHA-256 was recorded before the implementation (`eeb84dbb...fd6d49`); the sections
above are unchanged. Tests: `tests/test_combined_corrections.py`. Six of its seven tests fail on the
previous code and pass now. The seventh checks a case that must not change and passes on both.

| id | result | status |
|---|---|---|
| CC.C1 | reference peak in sample and background: K = 1.00 in both modes (before: "reference peak not found") | PASS |
| CC.C2 | blank 20 Bq, reference peaks of about 25 % counting uncertainty: L_C 0.53 -> 11.8 Bq, >= 1.645 x the null reference term | PASS |
| CC.C3 | L_C against the previous engine: reference without blank, blank without reference, neither: relative difference 0 | PASS |
| CC.C4 | Cs-137 peak removed by hand, no background: "no peak", note "manually edited peaks of the session were used" | PASS |
| CC.C5 | with a background: the note is present, results equal those without the edit | PASS |
| CC.C6 | blank changed while the worker runs: results and session record the blank used | PASS |
| CC.C7 | `after_CC1` (on main e39a0ef, after #37) vs `after_LB1`: 154 PASS / 13 FAIL / 60 REPORT, only the two runtimes differ | PASS |

The first `after_CC1` run was made on the previous main (`after_BP1` then current), and it was also
identical apart from the runtimes. It was regenerated on the updated main, so that the baseline chain
stays consistent.

`ENGINE_VERSION` goes from 1.2.0 to 1.3.0, because reference-peak results with a background, decision
thresholds with blank and reference peaks, and results with manual peak edits can change.

In CC.C2 the higher threshold is the correct one. With a 20 Bq blank and reference corrections
uncertain to about 25 %, a net activity below about 12 Bq cannot be told from zero. The previous
threshold of 0.53 Bq claimed a detection capability the measurement does not have.

# Round-4 review, activity findings (R4-A): evaluation protocol (pre-registered)

Written 2026-10-23, **before** the changes below were made. The reference values "as before" were
computed with engine 1.14.0 (commit a8d5346) by the harness of this protocol. The findings come from the fourth external
review (Codex, Antigravity, Gemini) and were checked on the code first (reproductions in the review
notes). The limits must not be changed after results are known. A result outside a limit is reported
as a failure.

## Findings and changes

1. **Detection limit with a reagent blank and a reference peak (Codex H1).** With gross activity
   `y + A_b` (net `y`, blank `A_b`), the reference-peak part of the variance is

       u_ref^2(y) = (y + A_b)^2 u_s^2 + A_b^2 u_b^2 + ((y + A_b) u_r - A_b u_rb)^2
                  = u_ref0^2 + 2 A_b (u_s^2 + u_r (u_r - u_rb)) y + (u_s^2 + u_r^2) y^2

   (`u_s`, `u_b`: counting parts of the sample and blank reference corrections; `u_r`, `u_rb`: their
   expected-rate parts). The constant and the square term are in the code; the linear term
   `L y`, `L = 2 A_b (u_s^2 + u_r (u_r - u_rb))`, is missing from the ISO 11929 detection limit.
   Change: `iso11929_limits` takes an extra linear coefficient (Bq) added to the Poisson term of the
   detection-limit equation, `y# = y* + k_b sqrt(w y# + L y# + w^2 sigma0^2 + u_rel^2 y#^2)`; the
   decision threshold is unchanged (y = 0). Currie limits are unchanged (they have no relative terms).
2. **Coincidence summing in a sample with self-attenuation (Gemini H3).** The summing correction of
   the sample used the efficiency of the calibration matrix. Change: with a self-attenuation model the
   peak efficiency passed to the coincidence correction of the sample is `eps(E) / F_sa(E)` (the
   sample's efficiency); the peak-to-total ratio is kept (assumption, stated in the notes). The
   calibration points' correction (summing-free curve) is unchanged.
3. **ISO 11929 best estimate in the concentration table (Gemini H2).** `concentrations()` gave the
   best estimate and coverage interval only for nuclides with an activity. Change: the same primary
   result as `compute_activities` (the window result when there is no activity, none when it is
   interfered) is used, so a nuclide not detected has its best estimate in Bq/kg, Bq/L and Bq/m3 as
   it has in Bq.

Fixes without a numerical criterion (tests only):

4. Deleting the last peak in a session: an edited peak list that is empty is passed as an empty list
   (no search), not as "no list" (Codex H2).
5. A constant attenuation factor other than 1 together with the energy-dependent self-attenuation model
   is refused (the same correction would be applied twice; all three reviews).
6. The self-attenuation model refuses non-finite densities, height and model uncertainty (Codex M3).
7. The self-attenuation model used is described in the results' notes (Gemini H3).

Kept on purpose: the reagent blank is analysed with the sample's options, self-attenuation included
(the blank's contamination is measured in the same geometry and filling as the sample); options that
differ are already reported.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RA.C1 | detection limit of Codex's case (Cs-137 line, flat efficiency 0.01, reference line 1950 keV area 10000 +- 1000 and expected rate 0.5 cps, blank line area 10000 +- 100, sample 11000 +- 105, ISO 11929) | within 1 % of Codex's independent value 31.461 Bq; decision threshold unchanged (13.706721 Bq, relative 1e-6) |
| RA.C2 | same case without blank, and without reference peak | decision threshold and detection limit as before the change (relative 1e-9): no blank 0.330165 / 0.695198 Bq, no reference peak 1.021354 / 2.059014 Bq |
| RA.C3 | same case with Currie limits | as before (relative 1e-9): 13.706721 / 27.429372 Bq |
| RA.C4 | Co-60 1173 and 1332 keV, Ba-133 356 and 303 keV with TCS (peak-to-total 0.25 (E/1000)^-0.3), self-attenuation model with the sample matrix and density equal to the calibration's | COI as before (relative 1e-9): 0.956410, 0.958094, 0.993632, 0.991883 |
| RA.C5 | Co-60 1332 keV and Ba-133 81 keV (no summing-in, so 1 - COI is the summing-out), sample mineral 1.6 g/cm3 against calibration water 1.0, 50 mm | 1 - COI equals an independent sum over the table, `sum_j P(j|i) min(1, eps(E_j) / F_sa(E_j) / PT(E_j))`, to relative 1e-9, and is smaller than without self-attenuation |
| RA.C6 | concentration table (Bq/kg dry, 0.5 kg, ISO 11929) of a detected Cs-137 and a not detected Co-60 | the Cs-137 row as before (best 58.754836 Bq/kg, relative 1e-9); the Co-60 row's best estimate, its uncertainty and interval equal `iso11929_best_estimate(primary / 0.5, u / 0.5)` to relative 1e-12 |
| RA.C7 | existing tests and the benchmark report | full test suite passes; benchmark PASS/FAIL counts unchanged (154 / 13) |

## Outputs

`docs/baseline/after_R4A/round4_activity.md` and `.json` (numbers of RA.C1-C6, synthetic data only),
from `python -m spectramaster.validation.round4_activity`. Engine version raised.

## Limitations

- The peak-to-total ratio of a self-attenuating sample is taken equal to the calibration's: its change
  is not modelled.
- RA.C1 checks the program against the measurement model it implements and one independent number; it
  is not an audit of every term of ISO 11929.

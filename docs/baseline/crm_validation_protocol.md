# Activity concentrations of certified reference materials: evaluation protocol (pre-registered)

Written 2026-10-21, **before** the harness was written and before any spectrum of this data set
was analysed. Only the metadata (materials, masses, fill heights, live times, labels) were read to
fix the selection below. The limits must not be changed after results are known. A result outside
a limit is reported as a failure.

## Purpose

Every earlier benchmark uses synthetic spectra, public InterSpec pairs without certified activities,
or comparisons with Aptec. This is the first check of SpectraMaster's activity concentrations against
**certified values of real reference materials**, measured on a real detector. It tests the whole
chain: peak search and fit, background subtraction, efficiency calibration, natural-series key lines
and the concentration.

It is a relative test: the efficiency curve is made from three IAEA reference materials and used for
other reference materials in the same geometry. It does not validate the program for any laboratory.

## Data

- H.N.T. Truong, T.Y.H. Huynh, "HPGe gamma-ray spectra of certified reference materials with
  decay-corrected labels (ORTEC GMX35P4-70, 2013-2022)", v1.0, Zenodo, doi:10.5281/zenodo.23093533,
  CC BY 4.0. File `Pub6_dataset_v1.0.zip`, MD5 `64aa9d4786c3e0a65a0355d563e75d09`.
- Kept in `D:\SpectraMaster_public_data\zenodo_23093533\`, outside the repository. Nothing from it is
  committed. The test that runs the harness is skipped when the data are absent.
- `pub6_hpge_crm_v1.npz` is loaded with `allow_pickle=False` (every array loads that way).
- Spectra: 5760 bins of 0.5 keV from 20 to 2900 keV. The authors re-fitted each energy calibration
  and **rebinned** the counts, so the counts are not integers (fractions down to 0.5) and are not the
  original Poisson counts.
- Labels: reference activity concentrations (Bq/kg) and standard uncertainties, decay-corrected by the
  authors to the acquisition start of each spectrum.

### Spectrum construction

`Spectrum(counts=row, energy_coeffs=[20.25, 0.5], live_time=lt_s, real_time=rt_s, start_time=start)`,
no FWHM calibration (the program's own width estimate). Counts are used as given, with the program's
usual variance (the counts). The effect of the rebinning on the uncertainties is a stated limitation,
not corrected.

## Selection (fixed from the metadata only)

Detector GMX35P4-70, tier `gold`, `representative` true, geometry `cylindrical box`, fill height
2.0 cm (|h - 2.0| < 0.05), mass recorded.

| role | ID | material | mass g | live h | file |
|---|---|---|---|---|---|
| calibration | S189 | RGU-1 | 164.6 | 20.0 | IAEA-RGU-1-cylinder-2cm.Chn |
| calibration | S136 | RGTh-1 | 158.9 | 20.0 | IAEA-RGTh-1-cylinder-2cm.Chn |
| calibration | S112 | RGK-1 | 166.2 | 6.7 | IAEA-RGK-1-cylinder-2cm-6h.Chn |
| test | S018 | IAEA-312 | 149.0 | 24.0 | IAEA-312-cylinder-86400s.Chn |
| test | S021 | IAEA-312 | 149.0 | 24.0 | IAEA-312-cylinder-2cm.Chn |
| test | S047 | IAEA-375 | 185.8 | 23.6 | IAEA-375-cylinder-2cm.Chn |
| test | S059 | IAEA-434 | 94.8 | 22.2 | IAEA-434-cylinder-2cm.Chn |
| test | S067 | IAEA-444 | 148.6 | 24.0 | IAEA-444-cylinder-2cm.Chn |
| test | S086 | IAEA-SL-2 | 188.7 | 24.0 | IAEA-SL-2-cylinder-2cm.Chn |
| test | S332 | IAEA-447 | 146.3 | 24.0 | IAEA-CU-09-03-cylinder-2cm.Chn |

S204 (RGU-1, 1.3 h) also passes the rules. It is not used, because S189 is the longer measurement of
the same filling. No reference material is used both for calibration and for testing.

Background for every spectrum, calibration and test: `background Feb-2016.Chn` (lead shield,
2016-02, 144 h), the background measured closest in time to the January-February 2016 campaign.

## Efficiency calibration

Certificate entries per calibration spectrum, activity = label (Bq/kg) x mass, with the label's
standard uncertainty:

- RGU-1: Pb-214 and Bi-214 at the `Pb-214/Bi-214` label.
- RGTh-1: Ac-228 at the `Ra-228/Ac-228` label; Pb-212 and Bi-212 at the `Th-228/Pb-212` label;
  Tl-208 at 0.3594 x the `Th-228/Pb-212` label.
- RGK-1: K-40 at the `K-40` label.

Half-lives: those of the long-lived parents (Ra-226 for Pb-214/Bi-214, Ra-228 for Ac-228, Th-228 for
Pb-212/Bi-212/Tl-208), because the daughters are in equilibrium with them during counting. Reference
date = acquisition start (the labels are already decay-corrected).

Lines: the library lines with intensity >= 2 % (`certificate_lines` default) and energy >= 200 keV.
Below 200 keV, self-attenuation differs between the materials and the program has no correction.
`measure_efficiency` with the background, then `fit_efficiency(model="loglog")` with the orders the
program chooses. Every point the program accepts is used; no point is removed by hand, before or
after the results.

## Test

For each test spectrum: `compute_activities(spectrum, curve, ActivityOptions(nuclides=[Ra-226,
Ra-228, Th-228, K-40, Cs-137]), background=...)` with the program defaults (key line, peak-mode
background, Currie). The concentration is the program's activity divided by the mass (mass
uncertainty 0).

Mapping to the labels: Ra-226 to `Pb-214/Bi-214` (the program measures the progeny), Ra-228 to
`Ra-228/Ac-228`, Th-228 to `Th-228/Pb-212`, K-40, Cs-137.

- **Quantitative pairs:** label x mass >= 1 Bq. 19 pairs: Ra-226 5, Ra-228 4, Th-228 4, K-40 3,
  Cs-137 3.
- **Detection check (report only):** IAEA-SL-2 Cs-137 (1.2 Bq/kg, 0.23 Bq).

For each pair: ratio = c / c_ref and z = (c - c_ref) / sqrt(u_c^2 + u_ref^2), with the program's
combined standard uncertainty u_c (curve uncertainty included). A pair the program reports as not
detected, or that the harness cannot compute, counts as a failure for C1 and C2 and is listed with
the reason.

## Criteria

The limits follow the IAEA proficiency-test practice for environmental soils: a u-test limit of 2.58
and a relative bias of 20 %. They are deliberately those of a laboratory, not tighter, because
neither coincidence summing nor self-attenuation is corrected here.

| id | criterion | limit |
|---|---|---|
| CRM.C1 | fraction of quantitative pairs with \|z\| <= 2.58 | >= 0.90 |
| CRM.C2 | fraction of quantitative pairs with \|ratio - 1\| <= 0.20 | >= 0.80 |
| CRM.C3 | median ratio of each nuclide (all five have >= 3 pairs) | in [0.90, 1.10] |
| CRM.C4 | rms of z over the quantitative pairs | <= 2.0 |

## Reported, not criteria

- Every pair and every line: value, uncertainty, ratio, z, and the program's notes.
- The calibration: points, model, orders, chi^2, warnings.
- The same test with `model="two_branch"` (crossover chosen by the program).
- Marinelli (3π) geometry, same rules without the height rule: calibration S180 (RGU-1), S131
  (RGTh-1), S104 (RGK-1), all June 2015, 24 h; test S080 (IAEA-SL-2, June 2015): K-40, and the
  Cs-137 detection check.
- The QCY48 leave-one-nuclide-out check (Aptec demo spectrum, 2026-10-21) was **run before this
  protocol**. It is not part of these criteria.

## Known limitations, stated in advance

- No coincidence-summing correction. The calibration lines of Bi-214, Tl-208 and Ac-228 are cascade
  lines in a close geometry, and the curve passes between their biased points. Cs-137 and K-40 are
  read from that curve.
- No self-attenuation correction. IAEA-434 (phosphogypsum, 94.8 g in the same 2 cm) is much less
  dense than the other materials.
- Radon equilibrium in the test materials is assumed, as in the labels.
- Rebinned, non-Poisson counts.
- One detector, one laboratory, one geometry. A pass is evidence for the chain, not a validation.

## Files

Harness `spectramaster/validation/crm_zenodo.py`; results `docs/baseline/crm_validation_results.md`
(the name was checked to be free).

## Results (2026-10-21)

Run once, as pre-registered, with engine 1.1.0 (`python -m spectramaster.validation.crm_zenodo --out
docs/baseline`). The protocol file's SHA-256 was recorded before the harness was written
(`80b29259...e419cb`); the sections above are unchanged. Full tables:
`crm_validation_results.md` / `.json`.

| id | value | limit | status |
|---|---|---|---|
| CRM.C1 | 1.000 (19/19) | >= 0.90 | PASS |
| CRM.C2 | 1.000 (19/19) | >= 0.80 | PASS |
| CRM.C3.Ra-226 | 1.066 | in [0.90, 1.10] | PASS |
| CRM.C3.Ra-228 | 1.147 | in [0.90, 1.10] | **FAIL** |
| CRM.C3.Th-228 | 1.066 | in [0.90, 1.10] | PASS |
| CRM.C3.K-40 | 0.926 | in [0.90, 1.10] | PASS |
| CRM.C3.Cs-137 | 1.114 | in [0.90, 1.10] | **FAIL** |
| CRM.C4 | 0.158 | <= 2.0 | PASS |

6 of 8 criteria pass. All 19 ratios lie between 0.92 and 1.18.

### C1 and C4 pass for the wrong reason

Every result carries a relative uncertainty of about 58 %, so every |z| is small. The cause is a
defect found by this check (below, D2), not realistic uncertainties. **C1 and C4 therefore say nothing
about the quality of the uncertainties.** The relative criteria C2 and C3 are not affected.

### Defects found, not stated in advance

- **D1, nuclear data.** The library gives Ac-228 674.75 keV an emission probability of 2.1 %
  (IAEA ndlab). SandiaDecay gives 0.109 % and DDEP/LNHB 0.105 %. The library build had already
  flagged the disagreement (`provenance.flags`) and kept the IAEA value. The RGTh-1 spectra confirm
  the small value: about 320 counts were found where 2.1 % predicts about 10 000. The efficiency
  point of that line is 97 % below the curve, in both geometries.
- **D2, efficiency-curve uncertainty.** `model_error` adds the mean excess of the leave-one-out
  residuals to every point of the curve. The single D1 point (a 7-sigma outlier, flagged by the
  fit's own warning but still used) contributes 11.7 of the 0.342 mean. That is a model error of
  58.5 %. With that point unused, it is 8.1 % and the curve itself does not change (diagnostic run,
  not a protocol result). A curve's uncertainty should not depend so strongly on one point that the
  fit already rejects as an outlier.

### Pattern of the biases (hypotheses, not verified)

- Cs-137 (+11 %) has no cascade, but is read from a curve made mostly of cascade lines (Bi-214,
  Ac-228, Tl-208). Without the coincidence-summing correction, these points are lowered, the curve is
  too low, and non-cascade nuclides come out too high. This was stated as a limitation in advance.
- Ra-228 (+15 %) uses Ac-228 911.2 keV, whose own calibration point is 7 % above the curve.
- K-40 (-7 % in two of three samples) is read near its own RGK-1 point (residual -0.3 %). Self-
  attenuation or the background is a possible cause.
- Some calibration lines are far from the curve in both geometries: Tl-208 277.4 keV (-18 %),
  Ac-228 270.2 keV (-12 %), Pb-212 300.1 keV (-11 %), Bi-212 727.3 keV (+16 to +22 %), Bi-214
  1729.6 keV (+17 to +19 %). Candidates: summing, unresolved interferences, emission probabilities.
  Not investigated here.

### Reported, not criteria

- Two-branch model (cylinder): ratios 0.92-1.15. The median ratios are Ra-226 1.057, Ra-228 1.116,
  Th-228 1.062, K-40 0.961 and Cs-137 1.088. The model error is 58.9 %, from the same point.
- Marinelli (S080, IAEA-SL-2): K-40 ratio 0.998, Cs-137 ratio 1.28 (1.2 Bq/kg). The protocol calls
  this Cs-137 result a detection check, but its label x mass is 1.08 Bq, above the 1 Bq rule, so the
  harness classed it as quantitative. The two rules of the protocol disagree here. It has no effect
  on any criterion, because the Marinelli results are reported only.
- Cylinder detection check (S086, IAEA-SL-2 Cs-137, 1.2 Bq/kg): detected, 0.73 +- 0.45 Bq/kg.

### What this shows

On real spectra of certified materials, the chain from peak to concentration gives values within
20 % of the certified ones for every tested pair. The remaining biases (Cs-137, Ra-228) are of the
size that the uncorrected coincidence summing predicts. The uncertainties are not realistic yet, D2
being the cause. This is not a validation of the program.

Next, each as its own pre-registered change, followed by a re-run of this protocol: D1 (emission
probabilities that disagree between the sources) and D2 (outlier handling in the curve uncertainty).

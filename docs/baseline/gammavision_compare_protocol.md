# Laboratory HPGe spectra compared with GammaVision reports: evaluation protocol (pre-registered)

Written 2026-10-22, **before** any of these spectra was analysed with SpectraMaster. Only the two
GammaVision reports, the energy and efficiency calibration files and the spectrum headers
(`spectramaster info`: format, live time, total counts, energy coefficients) were read to fix the
selection below. The limits must not be changed after results are known. A result outside a limit is
reported as a failure.

## Purpose

The first comparison of SpectraMaster with another program on **real laboratory measurements**
analysed by that program: same spectra, same energy calibration (stored in the files). It tests the
peak search and fit (centroid, net area, width) and the nuclide identification. It does **not** test
activities: the efficiency calibration GammaVision used for the report is not available (the report
prints the coefficients as zero), and the efficiency file supplied with the data is not consistent
(see Limitations). Agreement with GammaVision is not proof of correctness of either program.

## Data

- Folder `D:\specter mohamed` (laboratory data, private, read-only; outside the repository; nothing
  from it is committed). The harness reads the folder from `SPECTRAMASTER_GV_DIR` (default that path)
  and is skipped when it is absent.
- Detector: ORTEC Detective HPGe (instrument `HPG6P4 DSPECJR2`), 16384 channels, live times
  84 600-86 400 s.
- Spectra (ORTEC integer SPC, read by SpectraMaster as `ortec_spc`): `sand sample 2.Spc`,
  `sand sample 2.An1`, `oil sample 1.An1`, `Oil sample 6.Spc`, `sludge sample 4.Spc`,
  `Sludg Sample 7.Spc`, `SLUDG SAMPIL 13.Spc`, `SLUDG SAMPIL 15.Spc`, `Water  Sample 11.Spc`.
- GammaVision reports (Wan32 engine): `sand sample 2.rpt` (spectrum `sand sample 2.An1`, start
  2022-11-17 13:05:39, live time 86218 s) and `oil sample 1.rpt` (spectrum `oil sample 1.An1`,
  start 2023-02-14 11:32:24, live time 86359 s). Sample descriptions in the files are not reproduced.

## Reference values (copied from `sand sample 2.rpt`, identified-peak summary)

Selection rule, fixed from the report only: identified peaks that are **not** deconvoluted (no `D`),
**not** flagged as failing the shape test (no `s`), with counting uncertainty <= 3 %, excluding the
186 keV doublet (Ra-226 + U-235).

| nuclide | GV energy keV | GV net area | GV 1 sigma % | GV FWHM keV |
|---|---|---|---|---|
| Pb-214 | 295.25 | 14771 | 1.17 | 1.054 |
| Pb-214 | 352.00 | 25322 | 0.80 | 1.128 |
| Tl-208 | 583.45 | 5335 | 2.49 | 1.206 |
| Bi-214 | 609.61 | 19368 | 0.89 | 1.317 |
| Ac-228 | 911.63 | 3619 | 2.68 | 1.467 |
| K-40 | 1461.44 | 25119 | 0.68 | 1.823 |
| Bi-214 | 1765.26 | 3269 | 2.02 | 1.955 |

Oil sample 1: GammaVision identified five peaks, all flagged `s` (fail shape test), with widths
0.20-0.48 keV: 186.03 keV (111 counts, FWHM 0.197), 295.21 (137, 0.236), 352.18 (138, 0.475),
1120.11 (59, 0.195), 1763.48 (39, 0.413). From them it reported Ra-226 35.8 Bq, Bi-214 85.8 Bq and
Pb-214 13.4 Bq.

## Procedure

SpectraMaster as in the release (`find_peaks(s, min_sig=3)`, `identify(s, peaks)` with the bundled
library and the default minimum confidence 0.25), energy calibration from the file, no FWHM
calibration (the program's own width model), no background spectrum. A GammaVision peak is matched to
the SpectraMaster peak with the nearest energy within 1.0 keV; no match fails G1-G3 for that peak.

## Criteria

| ID | quantity | limit |
|---|---|---|
| G1 | centroid, sand sample 2.An1, the 7 peaks | \|E_SM - E_GV\| <= 0.10 keV for all 7 |
| G2 | net area, same peaks | \|A_SM / A_GV - 1\| <= max(5 %, 2 x sqrt(u_SM^2 + u_GV^2)) for at least 6 of 7, **and** median ratio within 0.97-1.03 |
| G3 | FWHM, same peaks | \|W_SM / W_GV - 1\| <= 10 % for at least 6 of 7 |
| G4 | identification, sand sample 2.An1 | K-40, Pb-212, Pb-214, Bi-214, Ac-228 and Tl-208 all identified |
| G5 | oil sample 1.An1, the 5 energies above | no SpectraMaster peak within 1.0 keV of them with FWHM < 0.5 keV |
| G6 | `sand sample 2.Spc` and `sand sample 2.An1` | identical counts, live time and energy coefficients (same measurement) |

Descriptive, no limit: for every spectrum the number of peaks, the identified nuclides, and whether
SpectraMaster finds a peak (significance >= 3) near each of the five oil-sample energies with its
width.

## Outputs

`docs/baseline/after_GV1/gammavision_compare.md` and `.json`: derived numbers only (energies, areas,
widths, ratios, nuclide names), file names as listed above, no sample descriptions.

## Limitations

- One report with usable peaks (sand sample 2). The other spectra have no GammaVision result.
- GammaVision's peak background is "average of five points"; SpectraMaster fits the continuum. Small
  area differences are expected from the method alone.
- Activities are not compared. The efficiency file `effcaas.Eft` (Eu-152, reference 2007) lists an
  efficiency at 40 keV about 90 times lower than at 122 keV and counts that do not match its source
  activity; it ends at 1212 keV. It is not used.

---

## Results (2026-10-22)

`python -m spectramaster.validation.gammavision_compare` (engine 1.14.0), output in
`docs/baseline/after_GV1/`. **4 PASS / 2 FAIL**, reported as registered.

| ID | result | detail |
|---|---|---|
| G1 | FAIL | 7/7 peaks matched; \|dE\| 0.011-0.115 keV, above 0.10 keV for 1461 and 1765 keV |
| G2 | FAIL | every peak within its own limit, but the median area ratio is 0.962 (limit 0.97-1.03) |
| G3 | PASS | FWHM ratios 0.98-1.07 |
| G4 | PASS | K-40, Pb-212, Pb-214, Bi-214, Ac-228, Tl-208 identified |
| G5 | PASS | no narrow peak; at 186 and 295 keV no peak, at 352, 1120 and 1764 keV peaks of normal width (1.2-2.0 keV) at significance 3.0-4.2 |
| G6 | PASS | `.Spc` and `.An1` of sand sample 2 identical |

Findings (to be checked, not established):

- **Centroid and area differ with energy in the same way.** SpectraMaster's centroids are higher by
  0.06 channel at 295 keV rising to 0.61 channel at 1765 keV (same energy coefficients), and its areas
  are lower by 0.6 % at 295-352 keV and by about 4 % from 583 keV upwards, with a higher continuum
  under the peak (K-40: 1002 against 682 counts) and widths 6-7 % larger above 900 keV. A low-energy
  tail on this detector's peaks, counted in the peak by GammaVision (five-point average background)
  and partly in the continuum by SpectraMaster, would explain all three. A dedicated check of the
  peak tail on these spectra is needed before any change.
- **Spurious identifications in GammaVision.** In oil sample 1 GammaVision accepted five peaks of width
  0.2-0.5 keV (the detector FWHM there is 1.0-2.0 keV) and reported Ra-226 35.8 Bq and Bi-214 85.8 Bq
  from them. SpectraMaster finds no peak at 186 and 295 keV.
- **Doubtful identifications in SpectraMaster.** Short-lived or activation nuclides are proposed in
  NORM samples measured weeks after collection (Mn-56, Dy-165, Xe-133, Mo-99/Tc-99m, As-74, Yb-169,
  Ce-141, Gd-153). These are candidates from single weak lines; they show the limits of automatic
  identification and need the analyst's review.
- Both programs place the lines 0.3-0.9 keV above the library energies (Bi-214 1764.49 keV: GV
  1765.26, SM 1765.38): the stored energy calibration has drifted; a drift check (section 8.2 of the
  manual) would show it.

This is a comparison with another program on one report; it is not a validation of either program.

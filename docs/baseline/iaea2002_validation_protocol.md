# IAEA 2002 low-level test spectra: pre-registered activity check

Status: **pre-registered**. This file is written and its SHA-256 recorded before any activity of the
test spectra has been computed. Results are appended below the line at the end, never above it.
Limits are not changed after the results are seen; a failure is recorded as a failure.

## 1. Purpose

The first check of SpectraMaster against certified activities in a laboratory workflow:

1. Efficiency calibration from a certified mixed source, measured in the sample geometry.
2. A second certified source in the same geometry is analysed as an unknown sample.
3. The result is compared with its certificate.

This is the routine of an environmental laboratory: a 500 ml Marinelli beaker on an HPGe detector,
and a 100 ml container. The check does not establish laboratory validation or compliance with any
standard. It is one piece of evidence on one data set.

## 2. Data

The data are the IAEA 2002 test spectra for low-level gamma-ray spectrometry. They were used in
Arnold et al., NIM A 536 (2005) 196, doi:10.1016/j.nima.2004.10.012.

- **Source:** the Fukushima University IER data page, which posted them with the permission of the
  IAEA comparison lead. No formal licence is given, so the files are **not** committed.
- **Location:** `SPECTRAMASTER_PUBLIC_DATA/iaea_2002_testspectra`.
- **Archive SHA-256:**
  - `IAEA_2002_testspectra.zip`: `361a09e350976c0e32407d182d77bb4c492fcf74bf5fa29d91024dd2dd184c51`.
  - `IAEA_1995_testspectra.zip`: `023fdd649fd15d6a68815c61a9e47eb1001b63c7ad11eeb1b5e008d0ae240eb5`.
- **Extraction:** with Python `zipfile`, every path checked to stay inside the target folder. The
  DOS program `cmpspec.exe` was not extracted and is never run.

### Detectors and spectra

| Detector | Calibration spectrum | Certificate | Test spectra | Certificate | Background |
|---|---|---|---|---|---|
| SMALL: 33 % Canberra HPGe, unshielded | `maricsmall.spe`: 500 ml Marinelli, 1.15 g/cm3 | Analytics 64921A | `maritsmall.spe` (long), `maritsmall60.spe` (1 h) | Analytics 64923: 500 ml Marinelli, 1.15 g/cm3 | `BGSMALLMARI.spe`: Marinelli with water |
| BIG: 96.3 % ORTEC HPGe, 10 cm lead | `picbig.spe`: 100 ml pillbox, 1.15 g/cm3 | Analytics 64922A | `PITBIG.spe` (long), `PITBIG60.spe` (1 h) | Analytics 64924A: 100 ml, **1.6 g/cm3** | `BGBIGPOINT.spe` |

**Certificates.** All four are dated 2002-11-01 12:00 EST. The uncertainties are stated at a 99 %
confidence level and are divided by 2.576 to give standard uncertainties.

| Nuclide | 64921A (Bq) | 64922A (Bq) | total U99 % |
|---|---|---|---|
| Am-241 | 3353 | 5403 | 5.0 |
| Cd-109 | 39214 | 63190 | 5.0 |
| Ce-139 | 1325 | 2136 | 5.0 |
| Co-57 | 884 | 1424 | 5.0 |
| Cs-134 | 5529 | 8909 | 5.0 |
| Cs-137 | 1106 | 1782 | 4.8 |
| Hg-203 | 2666 | 4297 | 5.0 |
| Mn-54 | 1564 | 2519 | 5.0 |
| Sn-113 | 2391 | 3853 | 5.0 |
| Y-88 | 3914 | 6306 | 5.0 |
| Zn-65 | 3191 | 5142 | 5.0 |

| Nuclide | 64923 Marinelli test (Bq) | 64924A pillbox test (Bq) | total U99 % |
|---|---|---|---|
| Ba-133 | 1713 | 1253 | 5.0 |
| Co-60 | 1076 | 799 | 5.0 |
| Eu-152 | 3739 | 2827 | 5.0 |
| Cr-51 (\*) | 7903 | 7827 | 5.0 |
| Na-22 | 1073 | 1063 | 5.0 |

(\*) The certificates print "Cr-52", which is stable. The half-life they give, 27.70 d, is that of
Cr-51, so the entry is taken as Cr-51.

### Decisions on the data, fixed before any activity was computed

- **D-a, file format.** The `.spe` files (IAEA ASCII format) are read. The 2002 READ_ME lists the
  same spectra in three formats. For every spectrum except one, the `.spe` and `.Chn` counts are
  identical. `maricsmall.chn` differs from `maricsmall.spe` in three ways:
  - Its counts are shifted by two channels.
  - It carries another start time: 2002-11-20 12:00 instead of 2002-11-22 14:08:39.
  - It holds a FWHM calibration of 1.0 channel.
  The `.spe` version is consistent with all other spectra of the same detector: its energy offset
  is 7.99 keV against 8.00 keV for `maritsmall.spe`. The `.Chn` start time is evaluated only as a
  sensitivity variant (S3).
- **D-b, time zone.** The spectrum clock is taken as CET (UTC+1). The certificate reference is
  12:00 EST, which is 2002-11-01 18:00 in spectrum time. The EST reading is a sensitivity variant (S4).
- **D-c, Am-241.** Am-241 of the single-nuclide point sources has no activity ("??"). That only
  concerns the peak-to-total spectra, which use no activity.

### Feasibility checks done before this protocol (energy calibration only, no activities)

These checks looked at energy calibration only; no activity was computed.

- `calibrate_from_source(..., use_existing=False)` with the certificate nuclides calibrates every
  spectrum:
  - `.spe` calibration spectra: 17 and 18 lines, residual rms 0.011 and 0.105 keV.
  - Test spectra: 19 to 20 lines, rms ≤ 0.16 keV.
  - Backgrounds: 8 and 10 lines.
  Cr-51 is not in the calibration tool's line list, so it is left out of the energy calibration only.
- **Finding F1, recorded and not fixed here.** On `maricsmall.chn`, whose stored FWHM calibration
  is 1.0 channel, the analysis engine finds 3 peaks instead of about 60. Automatic calibration then
  fails without saying why: 2 lines, gain 0.197 instead of 0.433 keV/ch. An implausible stored FWHM
  calibration is trusted silently. This is a robustness defect for a later item.

## 3. Procedure (harness `spectramaster/validation/iaea2002.py`)

1. **Energy calibration.**
   - Each calibration, test and background spectrum: `calibrate_from_source(spectrum, nuclides,
     use_existing=False)` with its own certificate nuclides. Cr-51 is excluded. Backgrounds use
     `K-40, Ra-226, Th-232`. The calibration and its FWHM fit are applied to the spectrum.
   - Peak-to-total spectra: the calibration of the background point spectrum of the same detector,
     measured within one day (`BGSMALLPOINT`, `BGBIGPOINT`).
2. **Efficiency points.**
   - `ef.certificate_lines(certificate, e_min=50 keV)` on the calibration spectrum.
   - `ef.measure_efficiency(calibration, lines, background=matching background)`.
   - Each certificate's points share one `group`, because the certificate's systematic uncertainty
     is common to them.
3. **Efficiency curve.** `ef.fit_efficiency(points, "two_branch", crossover="auto")`, with orders
   chosen by the engine.
4. **Peak-to-total (P/T)** per detector, from the single-nuclide point spectra at 10 cm. Their
   activities are not needed.
   - Lines: Co-57 122.06, Sn-113 391.70, Cs-137 661.66, Mn-54 834.85 and Zn-65 1115.54 keV.
   - Net spectrum: S − kB, with the point background of the same detector scaled by live time.
   - Peak area: the engine's net peak area of that line, searched on the net spectrum.
   - Total: the sum of the net counts at E ≥ 40 keV, plus the mean net counts per channel between
     40 and 60 keV times the number of channels below 40 keV (flat extrapolation).
   - P/T = peak area / total. The fit is ln P/T = ln a + b ln(E/1000), unweighted, over the five
     points, and the PT relative uncertainty is fixed at 0.10.
   - Known approximations: the point at 10 cm is not the sample geometry; X-rays below 40 keV are
     extrapolated; Co-57 136 keV and Zn-65 511 keV enter the total.
5. **Summing.**
   - `ef.summing_free_curve(curve, pt, 0.10)` removes the summing losses of the cascade points in
     the calibration: Co-57, Cs-134, Y-88 and Zn-65.
   - Then `compute_activities(test, curve, ActivityOptions(nuclides=[Ba-133, Co-60, Eu-152,
     Cr-51, Na-22], ref_date=2002-11-01 18:00, tcs={"peak_to_total": [a, b], "pt_rel_unc": 0.10}),
     background=matching background)`.
   - Everything else is left at the engine defaults: key-line method, peak-mode background, Currie.
6. **Comparison.** For each of the 20 pairs (2 geometries × 2 durations × 5 nuclides):
   - ratio = A / A_cert.
   - z = (A − A_cert) / sqrt(u(A)² + u_cert²).
   - u(A) already contains the calibration certificate's uncertainty, and both certificates come
     from one producer, so z double-counts part of a common systematic and errs on the
     conservative side. This is stated, not corrected.

The pillbox test source has a density of 1.6 g/cm3 against 1.15 g/cm3 for its calibration source.
SpectraMaster has no self-attenuation correction from a material database yet. The pillbox results
are therefore expected to be biased low at low energy, and that is part of what this check
measures. No attenuation factor is entered by hand.

## 4. Criteria (main analysis, steps 1–6)

| ID | Quantity | Limit |
|---|---|---|
| IA.C1 | Fraction of the 20 pairs with \|z\| ≤ 2.58 | ≥ 0.90 |
| IA.C2 | Marinelli, 10 pairs: fraction with \|ratio − 1\| ≤ 0.10 | ≥ 0.80 |
| IA.C3 | Pillbox, 10 pairs: fraction with \|ratio − 1\| ≤ 0.15 | ≥ 0.80 |
| IA.C4.M | Median ratio of the 5 long-spectrum Marinelli pairs | in [0.93, 1.07] |
| IA.C4.P | Median ratio of the 5 long-spectrum pillbox pairs | in [0.93, 1.07] |
| IA.C5 | rms z of the 20 pairs; every pair has a value | ≤ 2.0, and no pair missing |
| IA.C6 | All 20 nuclide–spectrum pairs reported as detected | 20 / 20 |

A pair without a value (not detected, an error, or no line) counts as a failure in C1–C3 and C5. In
a median it enters as 0.

## 5. Sensitivity and report-only variants (no pass/fail)

- **S1:** no summing correction (no `tcs`, curve not made summing-free).
- **S2:** `loglog` efficiency model instead of `two_branch`.
- **S3:** the `maricsmall.chn` start time (2002-11-20 12:00) for the Marinelli calibration.
- **S4:** the certificate reference read in spectrum time as 12:00, i.e. clock = EST.
- **S5:** peak areas of `mix2neq6.spe` against the IRI reference list `refrsl/mix2neq6ref.txt`.
  - The CMPSPEC definitions in the 2002 READ_ME are re-implemented, not run: z-scores, misses,
    false hits, and the reduced χ² per group.
  - Energy calibration: from `mix2neqlong.spe` with `Ra-226, Th-232, K-40`, applied to `mix2neq6`.
  - Count-time ratio: 239 (READ_ME).
- The MIX1/MIX2 natural-series samples (IAEA-RGU-1 / RGTh-1 blends) are **not** part of this
  check. Their certified values are not in the downloaded documentation, so they need their own
  protocol.

## 6. Outputs

- New, free folder `docs/baseline/after_IA1/`: `iaea2002_results.md` and `iaea2002_results.json`,
  plus the standard benchmark of the same commit, which must stay at 154 PASS / 13 FAIL / 60 REPORT.
- Tests `tests/test_iaea2002_validation.py`. They are skipped when the data are absent; when the
  data are present, they check that the harness runs and reproduces the recorded numbers.
- No engine change is part of this check. Any defect it shows becomes a separate, pre-registered
  item.

---
## Results

(appended after the run)

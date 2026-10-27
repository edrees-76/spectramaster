# Detector acceptance test and chi-square counting test: evaluation protocol (pre-registered)

Written 2026-10-27, **before** the code below was written. The limits must not be changed after
results are known. A result outside a limit is reported as a failure.

## What is missing

SpectraMaster tracks a detector over time (Tools > Detector QC, control charts) and stores a relative
efficiency typed by hand in the detector record. It has no calculator for the acceptance test of an
HPGe detector from a Co-60 spectrum, and no chi-square test of repeated counts. The user's reference
documents (kept outside the repository) describe both:

* **Acceptance test** (Canberra Germanium Detectors User's Manual, chapter 7, and IEEE Std 325; IAEA
  MRNI-507 for the HPGe test):
  * FWHM and FWTM of the 1332.5 keV peak (and of the 122.1 keV peak of Co-57 when that spectrum is
    given), and the ratio FWTM / FWHM;
  * peak-to-Compton ratio: the counts in the highest channel of the 1332.5 keV peak divided by the
    mean counts per channel between 1040 and 1096 keV;
  * relative efficiency: the 1332.5 keV full-energy efficiency of the detector for a Co-60 point
    source at 25 cm on the axis, divided by 1.2e-3 (that of a 3 x 3 inch NaI detector), in percent.
* **Chi-square test** (IAEA-TECDOC-1599): n repeated counts of the same source;
  chi^2 = sum (x_i - mean)^2 / mean, accepted when it lies between the 5 % and 95 % points of the
  chi-square distribution with n - 1 degrees of freedom (3.325 and 16.919 for 10 counts).

## Implementation (engine, no Qt)

New module `analysis/detector_test.py`:

* `peak_width(spectrum, energy)`: an ROI of +-3 FWHM (FWHM from the spectrum's resolution model)
  around the peak, analysed by the existing Aptec ROI analysis (`aptec_roi.analyze_rois`: linear
  background between the end points, half and tenth maximum by linear interpolation of the net
  counts); widths converted to keV with the local slope of the energy calibration.
* `peak_to_compton(spectrum)`: the highest gross count among the channels of the 1332.5 keV ROI,
  divided by the mean gross counts of the channels whose energy lies in 1040-1096 keV.
* `relative_efficiency(spectrum, activity_bq, activity_u_bq, reference_date)`: the net area N of
  the 1332.5 keV ROI, the activity decayed from the reference date to the start of the measurement
  (Co-60 half-life of the library; no correction when the start is unknown, with a note),
  eps = N / (t_live A I_1332), R = 100 eps / 1.2e-3, with the counting and activity uncertainties
  combined. No true-coincidence summing correction (as in the standard test at 25 cm).
* `acceptance_test(...)`: the three together, with notes (a width below 3 channels, a missing peak,
  an energy outside the calibration).
* `chi_square_test(counts)`: chi^2, n - 1, the 5 % and 95 % points (`scipy.stats.chi2.ppf`), the
  result, and a note when n is not 10 or 20 (the numbers of TECDOC-1599) or a count is not positive.

Interface: Tools > Detector Acceptance Test... (the displayed spectrum, source activity, its
uncertainty and reference date, an optional Co-57 spectrum; results table, copy) and Tools >
Chi-Square Counting Test... (counts typed or pasted, one per line). Manuals AR/EN.

## Criteria

| ID | quantity | limit |
|---|---|---|
| DA.C1 | noiseless spectra built here (independent of the synthetic module): a Gaussian peak integrated over each channel at 1332.5 keV on a linear continuum, gains 0.5 and 0.25 keV/channel, FWHM 1.8 and 2.2 keV (3.6 to 8.8 channels), peak area 1e5 | FWHM and FWTM within 2.5 % of the true Gaussian values (FWTM = 1.8226 FWHM) |
| DA.C2 | the same with Poisson noise, 50 realizations each (fixed seeds), continuum 100 counts per channel | mean FWHM and mean FWTM within 2.5 % of the true values |
| DA.C3 | noiseless spectra with a known relative efficiency R (20 %, 40 %, 100 %), live time 3600 s, activity 37 kBq stated 5 years before the measurement | measured R within 1 % of R (decay correction included); with the reference date at the measurement start, also within 1 % |
| DA.C4 | Poisson spectra, R = 40 %, 200 realizations | z = (R_measured - R) / u(R) with the counting uncertainty only: fraction \|z\| <= 2 in [0.90, 0.99] |
| DA.C5 | peak-to-Compton on a hand-made spectrum | equals the hand calculation (highest channel / mean of the 1040-1096 keV channels) exactly |
| DA.C6 | chi-square points | 10 counts: 3.325 and 16.919 (3 decimals, TECDOC-1599); 20 counts: 10.117 and 30.144 |
| DA.C7 | 2000 sets of 10 Poisson counts of mean 10000 (fixed seed); 2000 sets with extra Gaussian scatter of 3 % (variance ratio about 10) | Poisson: accepted fraction in [0.88, 0.92]; extra scatter: rejected fraction >= 0.99 |
| DA.C8 | interface and existing tests | dialog results equal the engine's for the displayed spectrum; chi-square dialog parses one count per line and shows the result; full test suite passes; benchmark PASS/FAIL counts unchanged (154 / 13) |

Reported, not judged: the widths, P/C and FWTM/FWHM of the HPGe Co-60 spectrum of the synthetic
module (which has a low-energy tail, so FWTM/FWHM is above 1.8226).

## Outputs

`docs/baseline/after_DA1/detector_acceptance.md` and `.json`, from
`python -m spectramaster.validation.detector_acceptance`, and `after_DA1/baseline.md` and `.json`.

## Limitations

- Synthetic spectra only. No laboratory Co-60 spectrum measured at 25 cm with a known activity is
  available; the calculator is not validated against a manufacturer's acceptance report.
- The relative efficiency assumes the standard geometry (point source, 25 cm, on the axis); the
  interface states it, it cannot check it.
- The NaI detector QC of TECDOC-602 (nuclear-medicine instruments) is not part of this work.

---

## Results (first run, `after_DA1`, commit ba60fa7)

**5 PASS / 2 FAIL as registered.** DA.C1 and DA.C2 failed in one case: FWHM 1.8 keV at 0.5 keV per
channel, where the FWTM by linear interpolation came out 5.7 % above the Gaussian value. DA.C3 to
DA.C7 passed. The widths are now measured as in `detector_acceptance_amendment_protocol.md`
(registered before the change); its results are in `after_DA2`. DA.C8 was judged on the final code,
after the amendment (see there).

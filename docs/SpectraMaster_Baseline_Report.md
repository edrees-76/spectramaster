# SpectraMaster 1.0.0 analysis-engine baseline report

Date: 2026-10-14. Engine: SpectraMaster 1.0.0, commit `e3d2e8e` (the analysis code is unchanged
by Release A). Generated data: `docs/baseline/baseline.json` and `docs/baseline/baseline.md`.
To reproduce:

```
python -m spectramaster.validation.benchmark --out docs/baseline [--refdata DIR]
```

The full run takes about 2 minutes. Every synthetic spectrum is reproducible from its seed.

## 1. What was tested, and what was not

**Tested:**

- **Peak search and fitting** (`analysis/peaks.py`):
  - synthetic HPGe spectra (4096 channels, 0.5 keV/channel) and NaI spectra (1024 channels,
    3 keV/channel), about 1 200 spectra in total;
  - the IAEA G-1 test spectra (Ge(Li), 9 spectra);
  - the EML/Sanderson test spectra (HPGe, 34 spectra).
- **Nuclide identification** (`analysis/identify.py`): synthetic mixtures of known nuclides on a
  natural background, with deliberate gain errors of 0, 0.1, 0.3 and 1 %.
- **Library-level session models** (`spectramaster/lab`): unit tests only.

**Not tested here (no benchmark yet):**

- energy and FWHM calibration (`tools/calibrate.py`);
- efficiency calibration, activity and MDA (reviewed in section 4 only);
- spectrum-level background subtraction;
- real measured spectra with certified reference values.

**Limits of the evidence:**

- **Synthetic spectra.**
  - Peaks are Gaussian, optionally with a low-energy tail and step, on an exponential-plus-flat
    continuum. A Compton edge is present only in the `compton_edge` category.
  - There are no escape, sum or X-ray peaks, no backscatter, and no detector-specific shapes.
  - The identification mixtures use a generic efficiency shape and contain no coincidence summing.
- **IAEA G-1 areas are ratios** to G1100 as analysed by the same engine. They test consistency,
  not absolute area accuracy.
- **No laboratory validation.** No certified real-source measurements and no Aptec, Genie or
  GammaVision reports were available, so nothing here compares SpectraMaster with those programs.

## 2. Pre-registered acceptance criteria: result

- The limits are in `spectramaster/validation/acceptance.py`. They were committed (`36f00c9`)
  before the first benchmark run.
- 69 criteria in total: **51 pass, 9 fail, 9 are report-only**.
- The full table is in `docs/baseline/baseline.md`.

### Failed criteria

| Criterion | Value | Limit | Reading |
|---|---|---|---|
| HPGe.edge.recall | 0.775 | >= 0.90 | Peaks 1–2 FWHM above a sharp Compton edge are lost or merged with an edge artefact |
| HPGe.edge.area_bias | +13.8 % | abs <= 5 % | Areas near the edge absorb edge counts |
| HPGe.edge.spurious | 0.73 per spectrum | <= 0.20 | The edge itself is reported as a peak (also with no test peak present) |
| NaI.edge.recall | 0.40 | >= 0.90 | NaI: the edge becomes one broad pseudo-peak that swallows nearby test peaks |
| NaI.edge.area_bias | +319 % | abs <= 5 % | Same cause |
| NaI.edge.spurious | 0.85 per spectrum | <= 0.20 | Same cause |
| NaI.weak.area_bias_s7 | −7.2 % | abs <= 5 % | Weak NaI peaks (fixed model width) are biased low; −5.2 % at s = 10, −5.8 % at s = 5 |
| NaI.id.false_per_spectrum | 1.54 | <= 1.0 | False nuclides such as Sb-124, Mg-28, Y-88, I-131, Xe-133, Co-55 and Al-26 on NaI |
| EML.linearity | 3.6 sigma | <= 3 sigma | 1332 keV in TEST04 (multiplier 0.005): area 0.46× expected |

**Compton-edge caveat.** In the pre-registered case the synthetic edge is smeared only by the
detector resolution. This is sharper than a measured edge.

- An informational variant was added after the run, with no limit.
- With an extra 8 keV edge smearing, the HPGe failures disappear: recall 1.0, area bias −1.2 %,
  no spurious edge peaks.
- The NaI failure persists with an extra 15 keV smearing: recall 0.40, spurious 0.83 per spectrum.
- So the NaI failure is robust. The HPGe failure shows that the engine is sensitive to sharp
  continuum steps, which also matches the G-1 notes about pseudo-Compton edges.

### Passing areas (what works)

- **Strong isolated peaks** (s >= 100), HPGe and NaI:
  - recall 100 %, area bias < 0.2 %, centroid bias < 0.001 FWHM, FWHM within 3 %;
  - nominal uncertainty coverage: HPGe |z| <= 1 in 72.9 % and |z| <= 2 in 96.3 %; NaI 60.8 % / 92.1 %.
  - The NaI mean z is −0.45: a small (−0.17 %) bias that is statistically significant but
    scientifically minor.
- **Weak peaks:** detection probability 100 % at s = 7 and 93 % at s = 5, for both detectors.
- **False peaks on a pure continuum:**
  - HPGe: 0.68 per 1000 resolution elements (0.9 per spectrum);
  - NaI: none.
- **Doublets:**
  - equal peaks are resolved down to 0.75 FWHM;
  - when separated by 1.5 FWHM or more, component areas are unbiased (< 0.3 %).
- **Model mismatch:** a 4 % low-energy tail biases areas by −1.0 % (HPGe) and −1.5 % (NaI), with no
  spurious tail peaks.
- **Low counts** (A >= 100 on about 1–3 counts/channel): bias −2.8 % (HPGe) and +4.7 % (NaI).
  - These pass, but the per-area breakdown shows systematic structure.
  - HPGe A = 200: −4.0 %, mean z −0.49.
  - NaI A = 100: +11 %.
  - This is consistent with Neyman-weighted least squares and with selection near the threshold.
- **Runtime:** a median of 0.05 s per spectrum.
- **IAEA G-1:**
  - G1100: 20 of 20 peaks found.
  - G1200: 17 of 22 found, no false peaks (the G-1 notes cite 17 as typical).
  - G1300: 100 % recall, mean area-ratio bias +0.12 %, median |deviation| 2.3 %, 2-sigma coverage 94.7 %.
  - G1400: the three 6-channel doublets are resolved; 1 of 3 is resolved at 3-channel separation and
    none at 1 channel.
- **EML:** detection down to multiplier 0.005 (122 keV) and 0.0005 (662 and 1332 keV); no false
  detection in the blank (TEST09).
- **HPGe identification** (drift 0): recall 100 %, 0.25 false nuclides per spectrum.

## 3. Defects found while measuring (verified)

**P1. A strong unresolved doublet can vanish silently** (HPGe, separation 1 FWHM, ratio 3:1).

- In 7 of 8 realisations no peak at all was reported for 1.33e5 counts.
- Traced in this session:
  - the singlet fit hits the width bound (scale 1.40) with χ²ᵣ ≈ 850;
  - the √χ²ᵣ-inflated uncertainty lowers the significance to about 12;
  - the rule "broad singlet at the width bound with significance < 30 is a Compton hump"
    (`peaks.py:554`) then discards it;
  - the doublet retry fails because both start centroids converge to the same value.
- The search without fitting (`fit=False`) does find the region (about 108 000 counts).
- **Correction (after the baseline):** the report first suggested that missing EML 662 keV
  doublet peaks had the same cause. That was a benchmark-harness error: the search window assumed
  the doublet shift was towards higher channels. The engine did report the peaks. The window was
  made symmetric (`reference.py`). The affected metric is report-only.
- **Effect:** a large real peak, and every nuclide and activity that depends on it, disappears with no warning.

**P2. Calibrated NaI spectra on 4096-channel MCAs fail completely** unless metadata says "NaI".

- Informational run: recall 1.7 % (1 of 60 strong peaks found).
- Cause: `guess_detector` → "HPGe", and the FWHM rescale is clamped to ×2.
- This was first measured by the code review; this benchmark reproduces it.

**P3. Identification is not robust to gain drift on HPGe.**

| Gain error | Recall | False nuclides per spectrum |
|---|---|---|
| 0.1 % | 94 % | 0.21 |
| 0.3 % | 6 % | 1.7 |
| 1 % | 6 % | 4.7 |

A 0.3 % error is about 2 keV at 662 keV. That is beyond the matching tolerance, and the
built-in calibration correction does not recover it.

**P4. Too many false nuclides on NaI**, including physically implausible ones for environmental
samples (Mg-28, Co-55, Al-26). NaI recall is also only 50 % for Ba-133 and 67 % for Eu-152.

**P5. Weak NaI peaks are biased low** by 5–7 % for s = 5–10 (HPGe: −1.2 to −4.5 %). This is not
yet traced. Candidates are the fixed model width for weak peaks and the narrow ±2.2 FWHM fit
window.

## 4. Code review findings (not part of the benchmark)

These come from three read-only reviews run in this session. "Verified" means it was reproduced
with a script during the review. Those scripts were scratch files and are not in the repository.

**Peak search and calibration (`analysis/peaks.py`, `tools/calibrate.py`):**

- Verified: failed group fits are dropped silently (`peaks.py:527`), with no flag on the result.
- Verified: `calibrate.find_peaks` uses one fixed width (n/2000 + 2 channels).
  - On NaI it underestimates the FWHM by about 30 % and creates duplicate peaks.
  - It gives about 6.8 false peaks per flat spectrum at a nominal 5 sigma.
  - It is a separate search from `analysis/peaks.py`. Consolidating the two is a Release B task
    (the `Peak` classes and the tests differ).
- Verified: the Na-22 511 keV annihilation line, which is Doppler-broadened, is used as a
  calibration line and enters the FWHM fit.
- Verified: there is no monotonicity check and no extrapolation warning on proposed energy calibrations.
- Verified: the calibration line list agrees with `gamma_library.json` for 42 of 52 lines.
  The differences are ≤ 22 eV in energy, plus Eu-152 444 keV intensity (2.83 % vs 3.125 %),
  Ba-133 81 keV (33.3 % vs 32.9 %) and Ra-226 186 keV (3.56 % vs 3.64 %).
  These matter for ranking only, but the two lists should share one source.
- Documentation errors: `peaks.py` says it uses scipy `least_squares`, but a custom LM is used.
  A comment in `calibrate.py` mis-states its significance formula.

**Efficiency, activity and MDA (`analysis/efficiency.py`, `analysis/activity.py`):**

- **Verified: the mass/volume uncertainty enters the uncertainty of the Bq activity**
  (`activity.py:509–512`). Example: u(Bq) rose from 2.0 % to 6.2 % with a 10 % quantity uncertainty.
  The existing test asserts this behaviour.
- **Verified: the emission-probability uncertainty of efficiency points is always 0.**
  `CertLine.intensity_unc` is never filled.
- **Verified: one attenuation factor is applied to every energy and nuclide.**
- **Verified: no detector/geometry check between an efficiency curve and the sample.**
  Any curve can be applied to any spectrum (now addressable with `lab.MeasurementGeometry`).
- **Verified: an uncalibrated background is silently ignored in peak mode**, while the notes still
  say that background was subtracted.
- **Verified: the ISO 11929 detection-limit iteration does not converge as k_β·u_rel → 1.**
  - At u_rel = 0.6 it gives −6.9 % (not conservative).
  - It is exact for u_rel <= 0.55.
- **Verified: `EfficiencyCurve.from_dict` rejects unknown keys** (no forward compatibility).
- **Correct against independent hand calculation:**
  - Currie L_C/L_D: 2.71 + 4.65√B, and the general k_α ≠ k_β case.
  - The ISO 11929 decision threshold and detection limit (simplified form).
  - A complete activity, decision-threshold and MDA example on a flat spectrum, which matched to
    all printed digits.
- **The claimed scope should read "ISO 11929 (simplified, Currie-type blank)".**
  - There is no best estimate and no confidence limits.
  - Full compliance with ISO 11929-1:2019 is not established.
- **The identification "confidence" is a heuristic score shown as a percentage.** It is not a
  probability (plan section 11).
- **Not handled:** wet/dry mass basis, Bq/m³ in the GUI (it is CLI-only), true-coincidence summing,
  and protection against subtracting the background twice.

## 5. Changes since this baseline

| Change | Evidence | Criteria |
|---|---|---|
| **P1 fixed**. When a singlet fit hits its upper width bound, `peaks.py` now also tries the doublet with symmetric starts (±0.3 model FWHM) before the "Compton hump" rule can discard it. Tailed or asymmetric peaks are below the bound and keep the old behaviour. | HPGe, 1 FWHM, 3:1: resolved 12.5 % → 100 %, total-area bias −88 % → −0.01 %. New regression test `test_strong_doublet_one_fwhm_not_discarded` fails on the old code (2 of 4 seeds) and passes on the new. | Re-run in `docs/baseline/after_P1/`. All 69 criteria have the same status as the baseline (51 pass, 9 fail, 9 report). |
| A first version of the fix used a looser trigger (FWHM > 1.15 × model). It split the slightly asymmetric G1100 peaks at 1823, 1904 and 1947 into tail components, and the existing G-1 test caught it. That version was discarded. | `test_g1_reference_spectrum_all_peaks` | – |
| EML doublet window corrected in the harness (see P1). | `docs/baseline/after_P1/` | report-only |
| **The mass/volume uncertainty no longer enters u(Bq)**. It is added in quadrature only to the specific activity: u_rel(A/q)² = u_rel(A)² + u_rel(q)². The Bq budget no longer lists "quantity". | `test_quantity_uncertainty_only_affects_specific_activity`. The existing test, which asserted the old behaviour, was corrected. | not covered by the peak benchmark |
| **P2 fixed**. When the spectrum carries no detector label, `guess_detector` now tries the default resolution model of HPGe, LaBr3 and NaI, fits the strong peaks in groups with a free width scale, and picks the type whose model the peaks match (scale within ×1/1.5…×1.5). Channel count and gain are used only when there are no strong peaks. A detector label still takes precedence. | Before/after runs in `docs/baseline/before_P2/` and `docs/baseline/after_P2/`. NaI on 4096 channels: type correct 0 % → 100 %, strong-peak recall 2.5 % → 100 %, area bias −99.8 % → −0.18 %, FWHM ratio 0.027 → 0.999, nuclide recall 0 % → 86 %. 21 lab Aptec spectra (HPGe 8192 ch, NaI 512 ch): same type as before, and the type found from the widths (18 of them) agrees with the file's label where there is one. New tests `test_unlabelled_nai_on_4096_channels_is_not_hpge` (fails on the old code, 3 of 3) and `test_detector_label_overrides_measured_widths`. | Criteria pre-registered in a separate commit before the fix. All earlier criteria: same status and value (runtime: HPGe median 0.044 → 0.067 s, NaI 0.025 → 0.037 s, limit 0.5 s). New: `NaI_4096.id.false_per_spectrum` fails (1.58 per spectrum), the same NaI false-identification defect as P4 (1.54 on 1024 channels), visible now that the peaks are found. |

For NaI, a 3:1 doublet 1 FWHM apart is still reported as one peak, as before. Splitting it is not
required by the plan (no separation beyond NaI resolution). Its total area is within −5.2 %.

## 6. Recommended order of work (impact first)

1. ~~P1~~ done (section 5). Still open: features that the engine discards should be reported as
   visible warnings rather than dropped. This belongs to the Release B fit-inspection window.
2. ~~Bq uncertainty defect~~ done (section 5). Still open: the emission-probability uncertainty of
   efficiency points is 0. This is a **data gap**, not just code: `gamma_library.json` stores no
   intensity uncertainties, so they must first be added from ENSDF/DDEP, with provenance (Release D).
3. ~~P2~~ done (section 5). Still open: low-count and continuum-only spectra have no width
   information, so on a 4096-channel NaI they still fall back to "HPGe" (`NaI_4096.dettype.low`
   = 0.25, report only). The remedy is the detector label: the session's `DetectorProfile.type`
   must be written into the analysed spectrum's `detector` field (A5, GUI integration).
4. **The calibration-tool search and drift handling (P3)**, in Release B.
5. **Compton-edge robustness and NaI identification false positives (P4)**, in Releases C and E.

Each fix must be evaluated against the unchanged acceptance limits. A limit may only be changed in
a separate, justified commit.

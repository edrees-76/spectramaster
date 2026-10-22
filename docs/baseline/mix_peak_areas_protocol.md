# IAEA 2002 mix spectrum peak areas and the FWHM calibration from a source: pre-registered protocol

Written 2026-10-22, before the final run. This is the MIX item of the plan after the IAEA 2002
check, whose variant S5 compared the `mix2neq6` peak areas with the IRI reference list (report
only). Results are appended below the line after the run; nothing above it changes after its
SHA-256 is recorded.

## 1. Defect

**What S5 showed (after_CG1, CMPSPEC definitions of the 2002 READ_ME):**
* reduced χ² 8.88 for 50 matched high peaks;
* 3 false hits (χ² 55.9);
* total 5.79.

**Diagnosis, verified.**

1. **The three false hits are halves of split peaks.** At 1120.3, 1377.65 and 1764.5 keV the
   engine reports two peaks for one: 546 + 396 counts against a reference of 1082 at 1120.3 keV.
   * These three alone give z −11.1, −9.6 and −8.5, plus the three false hits.
   * Most of the χ² comes from them.
2. **The cause is the FWHM calibration that `calibrate_from_source` returns.**
   * It fits the widths of the matched peaks as the engine search reports them. For a spectrum
     without a FWHM calibration these are the search's **own width model**, not measured widths.
   * When the spectrum also has no energy calibration (the IAEA `.spe` files), that model is a
     constant in channels. Its shape is corrected only between the strong isolated peaks used,
     and it is flat outside them.
   * For `mix2neqlong`, the "measured" widths are 1.3632 keV for every line from 609 to
     1764 keV. The resulting FWHM calibration is 1.35 keV at 1764 keV.
   * The harness applies this calibration to `mix2neq6`. A peak about 1.7 times wider than the
     model is then fitted as two.
3. **The same mechanism affects every source calibration of an uncalibrated spectrum**, for
   example in the calibration dialog and the `calibrate` CLI.
   * In the IAEA harness: the model widths of `picbig` are a constant 1.762 keV from 59 to
     280 keV, and those of `BGBIGPOINT` a constant 1.183 keV at 5 lines.
   * The 511 keV annihilation line, which is Doppler-broadened, also enters the fit.

## 2. Measurements made before writing this protocol

Prototype, which is the code that will be committed:
* `peaks.line_widths(spectrum, centroids)`: the free-width fit of each line, centred on the nearest
  search candidate within one model FWHM, with the other candidates within 3 FWHM (shared width).
  The width runs between ×1/3 and ×3 of the model. The width counts as measured if the fit
  converges, does not end at a bound, and has area / u ≥ 10.
* `calibrate_from_source` fits the FWHM calibration through these measured widths:
  * the annihilation line (|E − 511| ≤ 3 keV) is left out;
  * order 2 is used, from 4 widths, only if it rises with energy over the lines; otherwise order 1;
  * the width furthest from the fit is removed, one at a time, while it is more than 10 % off and
    more than 3 remain.

Results:

* **S5 (`mix2neq6`):**
  * high-peak χ² 8.88 → 2.41 (53 matches);
  * false hits 3 → 0;
  * misses χ² 2.83 → 2.69;
  * total 5.79 → 2.59.
* **Independent width check.** A fixed-width χ² scan in steps of 0.05 keV (single Gaussian, step,
  linear continuum, ±2.5 FWHM) at three lines of each certificate-source spectrum, compared with
  the FWHM calibration of that spectrum:

  | | before (max \|diff\|) | prototype (max \|diff\|) |
  |---|---|---|
  | picbig, maricsmall (122, 662, 1116 keV) | 0.105 keV | 0.021 keV |
  | PITBIG, PITBIG60, maritsmall, maritsmall60 (122, 344, 1332 keV) | 0.678 keV (maritsmall60 1332) | 0.122 keV (maritsmall60 1332) |

* **`mix2neqlong`.**
  * FWHM 2.365 keV at 1764 keV. Before: 1.353 keV; the scan gives 2.50 keV.
  * In this natural-series spectrum the scan, which fits no neighbours, lies 0.05–0.24 keV above
    the calibration at 352–1764 keV.
* **Same detector, different spectra.**
  * PITBIG60 is narrower than picbig and PITBIG by 0.3 keV at 122 keV, and the scan confirms it.
    The likely cause is the 48 h acquisitions broadened by gain drift; this is not separated
    here.
  * So the widths must be measured per spectrum.
* **FWHM calibrations of the 9 spectra the harness calibrates:**
  * each rises with energy over its lines;
  * median residual ≤ 2.3 %, largest 6.9 % (BGBIGPOINT).
* **IAEA activities, harness as written (no self-attenuation), against after_CG1:**
  * the largest change is 1.8 % (maritsmall60 Na-22), then 1.2 % (maritsmall60 Co-60); every
    other change is below 1 %;
  * the IAEA criteria keep their pass/fail state.
* **With the F5 correction (organic 1.6 / 1.15):**
  * IA.C3 1.0, IA.C4.P 0.941, IA.C5 1.60, IA.C1 0.85;
  * PITBIG60 Eu-152 now takes 1408 keV as its key line (0.958).
* **Long-spectrum areas against the reference** (strong peaks, A/dA ≥ 30): median of
  (area / 239) / Ar is 0.957 over 57 peaks; 0.948 above 1000 keV (0.926 before).
* **Run time** of `calibrate_from_source` on these spectra: 1.0–2.3 s.

## 3. Change

1. `analysis/peaks.py`: new `line_widths(spectrum, centroids)`, as in §2.
2. `tools/calibrate.py`: `calibrate_from_source` builds its FWHM calibration with
   `_fwhm_from_lines`, as in §2. With fewer than 2 measured widths it returns no FWHM calibration.
3. **Unchanged:**
   * the energy calibration and its validation;
   * the line matching;
   * the peak search and fits of an analysis;
   * every spectrum that already has a FWHM calibration;
   * the stored format.
4. **Engine version.** The FWHM calibration of a source calibration changes the analysis of every
   spectrum it is applied to, so `ENGINE_VERSION` becomes 1.13.0.

**Not in this change:**
* the remaining 5 % deficit of the long-spectrum areas against the reference;
* the misses of small peaks in the 6-min spectrum (below its detection limit, as reported in S5);
* MIX1 / MIX2 natural-series activities, whose certified values are not in the downloaded
  documentation.

## 4. Criteria (set before the run)

| id | what | limit |
|---|---|---|
| MX.C1 | S5 on `mix2neq6` (harness `mix2neq6_areas`, CMPSPEC definitions) | high-peak reduced χ² ≤ 3.0; false hits ≤ 1; total χ² ≤ 3.0 |
| MX.C2 | FWHM calibration of the 9 spectra the harness calibrates (BGSMALLMARI, maricsmall, maritsmall, maritsmall60, BGBIGPOINT, picbig, PITBIG, PITBIG60, mix2neqlong) | every one exists and rises with energy over its lines; median \|residual\| ≤ 3 %, largest ≤ 10 % |
| MX.C3 | independent fixed-width scan (§2) at the 18 lines of the 6 certificate-source spectra | \|FWHM calibration − scan\| ≤ 0.15 keV at every line |
| MX.C4 | IAEA 2002 harness as written against after_CG1 | every one of the 20 ratios within 2 %; no criterion PASS → FAIL |
| MX.C5 | standard benchmark and CRM check against after_CG1 | identical except the engine version (and runtime fields) |
| MX.C6 | new unit tests (synthetic spectrum without FWHM calibration, known widths: calibration within 3 % of the truth; annihilation line and an outlier left out; no calibration from fewer than 2 widths); full suite | pass; changed existing tests listed with reasons |

**Reported, not criteria:**
* the scan check on `mix2neqlong`;
* the long-spectrum area ratio;
* the IAEA criteria with the F5 correction;
* the run time.

Outputs go to a new folder `docs/baseline/after_MX1/`. No IAEA data is copied into the repository;
only the derived numbers are.

---
## Results

(appended after the run)

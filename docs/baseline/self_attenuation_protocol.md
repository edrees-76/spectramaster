# Self-attenuation correction for a sample density different from the calibration (F5): pre-registered protocol

Written 2026-10-22, before implementation. This is finding F5 of `iaea2002_validation_protocol.md`.
Results are appended below the line after the run; nothing above it changes after its SHA-256 is
recorded.

## 1. Defect

* The only self-attenuation input is `ActivityOptions.attenuation`, a factor typed by the user. It
  is constant, or one value per nuclide; it does not depend on energy.
* A sample denser than the calibration source absorbs more of its own photons, most of all at low
  energy. Its activity is then underestimated.
* In the IAEA 2002 test the pillbox sample (100 ml, density 1.6 g/cm³) was measured with a
  calibration of the same container at 1.15 g/cm³. Our pillbox results are low: the median
  ratio of the long spectrum is 0.863 (IA.C4.P FAIL).

## 2. Measurements made before writing this protocol

* **Attenuation data.** Mass attenuation coefficients μ/ρ from NIST Standard Reference Database
  126 (Hubbell & Seltzer, *X-Ray Mass Attenuation Coefficients*), read from the pages
  `physics.nist.gov/PhysRefData/XrayMassCoef/ComTab/{water,pmma,concrete}.html` on 2026-10-22.
  These are public-domain US government data.
* **Pillbox geometry.** From the IAEA documentation: inner diameter 6.0 cm and fill height 3.53 cm,
  which gives 99.8 ml, in agreement with 100 ml. The matrix is resin, with no composition given.
* **Prototype.** The slab factor of §3 was applied with PMMA as the resin and h = 3.53 cm. It
  multiplies the pillbox results by:

  | | factor | ratio before | ratio after |
  |---|---|---|---|
  | Cr-51 | 1.085 | 0.94 | 1.02 |
  | Eu-152 | 1.082 | 0.68 | 0.74 |
  | Ba-133 | 1.081 | 0.91 | 0.99 |
  | Na-22 | 1.047 | 0.84 | 0.88 |
  | Co-60 | 1.046 | 0.86 | 0.90 |

  * Median ratio of the long spectrum: 0.863 -> 0.902.
  * With water or concrete in place of PMMA, the factors differ by at most 0.4 %.
  * The remaining low Eu-152, Co-60 and Na-22 ratios are not explained by self-attenuation. They
    belong to finding F4, the close-geometry curve with cascade emitters.

## 3. Change

1. **New module `analysis/attenuation.py`.**
   * NIST μ/ρ tables for `water`, `organic` (PMMA, as a proxy for resins and organic matter) and
     `mineral` (ordinary concrete, as a proxy for soil and sediment), 10 keV to 20 MeV.
     Interpolation is log-log.
   * `slab_transmission(mu_cm, h_cm) = (1 - exp(-mu h)) / (mu h)`: the mean transmission of a
     uniform slab of height h, viewed perpendicular to its face.
   * `SelfAttenuation(sample_matrix, sample_density, calibration_matrix, calibration_density,
     height_mm, rel_unc=0.0)` with `factor(E) = T_cal(E) / T_sample(E)`. It multiplies the
     activity.
   * The slab model (perpendicular paths) is an approximation for a cylinder on the end cap.
     Oblique paths make the true effect somewhat larger. `rel_unc` is the user's model
     uncertainty, combined like the existing attenuation uncertainty.
2. **`ActivityOptions.self_attenuation`** (`None` by default).
   * When set, each line's Bq-per-count is multiplied by `factor(E)` of its energy, in the
     activity, the decision threshold and the MDA alike.
   * `LineResult.self_attenuation` records the factor.
   * The existing constant `attenuation` keeps its meaning and is applied as before.
   * A blank with different `self_attenuation` options is reported like the other option
     differences.
3. **CLI** (`quant`): `--self-att-matrix`, `--self-att-density`, `--cal-matrix`, `--cal-density`,
   `--self-att-height-mm`, `--self-att-unc`.
4. **IAEA 2002 harness.** `run_geometry(..., self_attenuation=None)`. The default leaves every
   result unchanged.
5. **Not in this change:**
   * the GUI (a later item);
   * Marinelli beakers, where the slab model does not apply;
   * matrices other than the three;
   * measured transmission.
6. **Engine version.** The engine changes, so `ENGINE_VERSION` becomes 1.11.0.

## 4. Criteria (set before the run)

| id | what | limit |
|---|---|---|
| SA.C1 | `mass_attenuation(matrix, E)` at every tabulated energy from 10 keV | equal to the NIST value (relative 1e-9) |
| SA.C2 | `factor(E)` limits | 1 when sample = calibration; -> 1 as h -> 0; > 1 when the sample is denser; decreasing with energy for a denser sample between 30 keV and 3 MeV |
| SA.C3 | IAEA pillbox (PITBIG, PITBIG60) with `SelfAttenuation("organic", 1.6, "organic", 1.15, 35.3)` | every corrected value = uncorrected value × factor(E) of its key line (relative 1e-9); the median ratio of the long spectrum moves from 0.863 to within [0.89, 0.92] |
| SA.C4 | the same with `water` and `mineral` | factors within 1 % of `organic` at every test energy |
| SA.C5 | IAEA harness without `self_attenuation` against after_PE1/FP2 results; benchmark against after_PE1; CRM | identical except `engine_version` |
| SA.C6 | unit tests; full suite | pass; changed existing tests listed with reasons |

**Reported, not criteria:**
* IA.C4.P with the correction: it is expected still to fail, because of F4;
* the per-nuclide ratios after correction.

Outputs go to a new folder `docs/baseline/after_SA1/`.

---
## Results

(appended after the run)

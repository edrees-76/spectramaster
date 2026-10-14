# SpectraMaster development progress

This document tracks the plan in `docs/SpectraMaster_Development_Plan_EN.md`: the stages,
their acceptance criteria and status, and any justified changes to the plan. The plan itself is
not edited.

Status values:

- **done**: implemented and tested within the stated scope.
- **in progress**: partly implemented.
- **open**: not started.
- **blocked**: needs data or information that is not available.

## Release A: accuracy baseline and the detector, geometry and session models

| Increment | Status | Evidence |
|---|---|---|
| A0. Review of the plan against the repository; existing tests run | done | `docs/SpectraMaster_Baseline_Report.md` section 4. Full test suite: 639 passed, 66 skipped (reasons recorded below). |
| A1. Acceptance limits fixed before measuring | done | `spectramaster/validation/acceptance.py`, committed in its own commit before the first benchmark run |
| A2. Reproducible benchmark harness: synthetic HPGe/NaI, IAEA G-1, EML | done | `spectramaster/validation/`, `tests/test_validation_baseline.py` |
| A3. Baseline report | done | `docs/baseline/baseline.md` (generated), `docs/SpectraMaster_Baseline_Report.md` (interpretation) |
| A4. Data models: detector profile, geometry, calibration record, sample, analysis session, edit history with undo/redo, schema versioning and migration | done (library level) | `spectramaster/lab/`, `tests/test_lab_models.py`, `tests/test_lab_session.py` |
| A6. Fix P1 (strong unresolved doublet silently discarded) | done | `peaks.py` doublet retry; regression test; `docs/baseline/after_P1/` shows no criterion changed status |
| A7. Mass/volume uncertainty removed from u(Bq), kept in the specific activity | done | `analysis/activity.py`; `tests/test_activity.py` |
| A8. Fix P2 (unlabelled NaI on a 4096-channel MCA treated as HPGe) | done | `peaks.py` width-based type inference; criteria pre-registered in `acceptance.py` (separate commit); `docs/baseline/before_P2/`, `docs/baseline/after_P2/`; tests in `tests/test_analysis.py` |
| A5. Session integration in the GUI (open/save session, display stored vs recalculated results) | open | Planned for Release B together with the peak-inspection window |

## Release B: energy and FWHM calibration, peak inspection and manual editing

| Increment | Status | Evidence |
|---|---|---|
| B0. Calibration criteria pre-registered; calibration and drift scenarios; current tool measured | done | `acceptance.py` (commit 573041b, before any change); `docs/baseline/before_B1/` |
| B1. Calibration review: fitted centroids with uncertainties, weighted fit, F-test order selection, outlier exclusion with reasons, validation report (independent lines, monotonicity, extrapolated range, expected lines not found, width consistency), drift check with a proposed (not applied) correction | done (library level) | `tools/calibrate.py`; `analysis/peaks.py` (data-driven width model); `docs/baseline/after_B1/`; `tests/test_calibration_review.py` |
| B2. Fit-inspection data (components, background, residuals, warnings, discarded components with reasons) | done (library level) | `analysis/peaks.py` (`FitReport`), `inspect_fit`; `tests/test_fit_inspection.py` |
| B3. Manual peak editing with undo/redo and stale results | done (library level) | `analysis/manual.py`, `lab/session.py`; `tests/test_manual_refit.py` |
| B4. GUI: calibration review dialog (point toggles with reasons, refit, validation blocks Accept, counts untouched), drift dialog (correction only after confirmation), fit-inspection window (data, components, background, residuals, discarded components with reasons) with manual refit, add/remove peak, undo/redo and a stale-results indicator | done | `gui/calibration_dialog.py`, `gui/fit_inspection.py`, `gui/session_strings.py`; `tests/test_gui_calibration.py` (8), `tests/test_gui_fit_session.py` (6). Limits: engine messages stay English inside the Arabic UI; manual edits mark results stale but the analysis table must be re-run; opening and saving session files from the GUI (A5) is still open |

Stage 3 acceptance criterion ("known calibrations are recovered; incorrect matches, drift and
unreliable extrapolation are detected"), synthetic evidence only:

- recovered: HPGe Eu-152 with a non-linear true calibration (100 %), NaI Am+Cs+Co (100 %);
- incorrect matches: Co-60 + Cs-137 presented as Eu-152 flagged in 100 % (HPGe and NaI);
- drift: detected at 0.3 % (HPGe) and 1 % (NaI) in 100 %, no false alarm;
- extrapolation: reported as a warning with the fraction of channels outside the range;
- **not met**: the proposed NaI drift correction is within 0.1 FWHM in 85 % of cases (limit 95 %).
  With natural background only, 2-3 unblended NaI lines remain (σ 5-9 keV each).

Stage 2 acceptance criterion: reopening a session restores its state, and changes to a
calibration or library do not silently alter previous results.

- At library level this is covered by the round-trip, staleness and undo/redo tests.
- At GUI level it is not covered yet (A5).

## Release C: fitting, background handling and uncertainty propagation

| Increment | Status | Evidence |
|---|---|---|
| C0. Measured-background criteria pre-registered; sample/background pairs (background counted 2x longer, natural lines + weak Cs-137 contamination) scored in peak and spectrum modes | done | `acceptance.py` (commit 09775b3, before any change); `docs/baseline/before_C1/` |
| C1. Measured background: explicit variance S + k²B for net spectra (no clipping, no Poisson assumption), peak-by-peak subtraction with the sample fit's own linear estimator, negative net areas kept, double subtraction refused, sample/background compatibility warnings | done | `analysis/background.py`, `analysis/peaks.py` (`variance=`), `analysis/activity.py`, `analysis/efficiency.py`, `tools/arithmetic.py`; `docs/baseline/after_C1/`; `tests/test_measured_background.py` (12 tests) |

| C2. Compton edges (HPGe): a continuum step at the expected edge of each strong line (E·2a/(1+2a), a = E/511 keV), fitted over ±6 FWHM with neighbouring groups merged, kept only when it lowers χ² significantly; a residual search adds a masked peak; components the step explains are discarded with that reason and the step is shown as a fit warning | done (HPGe); NaI open | `analysis/peaks.py`; `docs/baseline/after_C2/`; `tests/test_compton_edge.py` (4 tests) |

| C3. Fit model: Poisson maximum likelihood for raw counts (iteratively reweighted with the model); log-linear continuum under fitted groups for scintillators (NaI, LaBr3, CZT), straight line kept for HPGe; the measured-background estimator uses the fit's own continuum columns and weights | done | `analysis/peaks.py`, `analysis/background.py`, `analysis/manual.py`; `docs/baseline/after_C3/`; `tests/test_fit_model.py` (4 tests) |

C3 result (after_C2 → after_C3, all limits unchanged; totals stay FAIL 12 / PASS 84):

- now PASS: `NaI.weak.area_bias_s7` −7.2 % → −0.6 % (the cause was continuum curvature under a
  straight line: on a flat continuum the bias disappears); `EML.linearity` 3.59 → 1.49.
- improved: low counts (HPGe −2.8 % → −1.7 %, NaI +4.7 % → +3.5 %, coverage up); NaI weak
  detection at s = 3 0.27 → 0.41 and s = 5 0.93 → 0.97; HPGe false identifications 0.25 → 0.08.
- **now FAIL**: `HPGe.weak.area_bias_s7` −4.53 % → −5.01 % (the change is within the
  statistical scatter of the 80-spectrum category, about ±2 %, but the pre-registered limit is
  exceeded and is not changed); `NaI.bkg_peak.net_bias` 2.0 % → 3.2 %.
- **worse, already failing**: NaI false identifications 1.54 → 1.88 per spectrum (NaI_4096
  1.58 → 1.96): more weak peaks are found and the identification step (P4, Release E) accepts
  them too easily. EML doublets separated by 6-7 channels are now reported as one peak
  (report-only).
- Tried and rejected: a free quadratic continuum (too flexible: HPGe detection at s = 5
  0.93 → 0.69, false peaks ×3); the log-linear continuum for HPGe (Sr-85 in the laboratory
  EFF-GOOD.S0 closure +9.3 % → +13.7 %, the 511/514 keV doublet).

Stage 4 (Compton edges), synthetic evidence plus a real-spectrum regression check:

| | before C2 | after C2 |
|---|---|---|
| HPGe, sharp edge (resolution only): recall / area bias / false peaks per spectrum | 0.78 / **+13.8 %** / **0.73** | **0.60** / +1.5 % / 0 |
| HPGe, realistic edge (+8 keV smearing, informational) | 1.0 / −1.2 % / 1.02 | 1.0 / −1.2 % / 0 |
| NaI | unchanged (model not applied) | |

- **Recall on a resolution-only edge falls** (0.78 → 0.60): a peak within about one FWHM of a
  step whose width equals the resolution is mathematically almost the derivative of a shifted
  step; with the edge position free, its area is undetermined (uncertainty > 10× the area) and it is
  discarded with the reason "the continuum step of the Compton edge explains it". Before, these
  peaks were "found" with areas off by +21 % to +53 %. Fixing the edge position at the kinematic
  value would separate them on synthetic data but real edges are not centred there; that was not done.
- **NaI is excluded** (relative FWHM above 2 % at the edge). Tried and rejected: on real NaI
  calibration spectra (Cs-137, Na-22, Ba-133, Co-60) the step model over ±6 FWHM (≈ 70–610 keV)
  produced new false peaks of significance 10–22 in the backscatter region and moved the Co-60
  1332 keV centroid by 4 keV. Diagnosed but not fixed: in the synthetic NaI edge case the width
  model is rescaled ×1.5 from the edge hump itself (it passes the isolation test), which is why
  NaI edge areas are biased. A NaI-specific continuum model is needed.
- Real-spectrum check (21 laboratory Aptec spectra + 80 laboratory archive spectra): 79 peak lists
  identical, the others differ by one weak peak (significance 3–4) or by area changes; all
  real-spectrum tests pass.

Stage 5 acceptance criterion ("known test cases recover net areas and uncertainties without
false detections due to subtraction"), synthetic evidence only:

| | before C1 | after C1 |
|---|---|---|
| HPGe, peak mode: bias / cov1 / cov2 / false detections | −1.1 % / 0.64 / 0.94 / 0 | −0.8 % / 0.65 / 0.95 / 0.025 |
| HPGe, spectrum mode | **−3.3 %** / 0.75 / 1.0 / 0 | −1.5 % / 0.63 / 0.93 / 0 |
| NaI, peak mode | **+4.1 % / 0.27 / 0.44 / 0.17** | +2.0 % / **0.43 / 0.70 / 0.24** |
| NaI, spectrum mode | **−9.9 % / 0.18 / 0.59** / 0 | +1.0 % / 0.63 / 0.94 / 0 |

- **Not met: NaI peak mode.** The remaining error is not in the subtraction: the sample fit
  models unresolved NaI blends (Bi-214 609 + Tl-208 583 keV next to Cs-137 662 keV; Co-60 1332
  next to K-40 1461 keV) with one shared width scale. The shape mismatch leaks part of the net
  Cs-137/Co-60 signal into the neighbouring background-only components, biased by up to about
  ±2.5 σ (Bi-214 −585 counts, K-40 +426). Their fit uncertainty does not contain that
  model error. Spectrum mode does not fit those blends and meets every limit. For NaI with a
  measured background, spectrum mode is therefore the better choice at present.
- Re-binning a background with a different calibration correlates neighbouring channels; this
  correlation is ignored (documented in `analysis/background.py`).
- The live times are taken as exact (no uncertainty on k).

## Release D: experimental efficiency calibration

| Increment | Status | Evidence |
|---|---|---|
| D0. Criteria pre-registered (bias and coverage of the curve; summing warnings; geometry guard; validation status shown); mixed-standard scenarios with a smooth known efficiency and per-nuclide certificate errors | done | `acceptance.py` (68e0db6, before any measurement); `docs/baseline/before_D1/` (7699119) |
| D1. Generalised least squares with the full covariance of the points: counting and emission probability independent, certificate activity shared by the lines of a nuclide, an optional component common to the standard; nothing added to the curve afterwards | done | `analysis/efficiency.py` (`point_covariance`); `tests/test_efficiency_release_d.py` |
| D2. Cascade-emitter calibration points carry a summing warning; the curve stores its geometry and validation status; `compute_activities` refuses a calibration of an incompatible geometry unless the user overrides it (reported), and reports unvalidated calibrations; a record's validation does not change its content hash | done | `analysis/efficiency.py`, `analysis/activity.py` (`calibration_checks`), `lab/calibration.py` |
| D3. Model orders and crossover chosen by leave-one-out cross-validation when not given; a model (interpolation) error from the leave-one-out residuals enters the curve uncertainty; points more than 3 σ from the curve are listed for review | done | `analysis/efficiency.py` (`select_orders`, `model_error`); `docs/baseline/after_D1/` |
| D4. Independent validation (`validate_curve`: points of a second source, \|z\| ≤ 3 and mean z² ≤ 2; marking validated stays the user's decision) and the GUI wizard extending the efficiency dialog: certificate (with an optional common standard uncertainty), detector and geometry editor (Marinelli/cylinder dimensions, nominal and filled volume, fill height, matrix, density; point distance; filter; empty = unknown, never zero), points with summing notes and exclusion reasons, automatic or explicit model orders with the selection, model error and outliers shown, independent validation tab, saved curve plus a `CalibrationRecord` with its status; the activity dialog checks the sample geometry and asks before using an incompatible calibration | done | `analysis/efficiency.py` (162db01), `gui/efficiency_dialog.py`, `gui/geometry_editor.py`, `gui/quant_panel.py`; `tests/test_gui_efficiency_wizard.py` (8) |
| D5. Emission-probability uncertainties (library data gap: ENSDF/DDEP values with provenance); detector picker linked to `DetectorProfile`; history of saved calibration versions | open | |

Result (before_D1 → after_D1, limits unchanged): efficiency criteria 2/8 → 7/8 pass per detector
pair; totals FAIL 20 → 13, no other criterion changed.

| | HPGe before → after | NaI before → after |
|---|---|---|
| mean bias (≤ 1 %) | −0.2 % → −0.4 % | **+1.2 %** → +0.2 % |
| 1σ coverage (0.55–0.81) | **0.84** → 0.68 | 0.69 → 0.65 |
| 2σ coverage (0.89–1.0) | 0.98 → 0.93 | 0.97 → **0.8875** |
| summing warning / geometry guard / validation shown | 0 / 0 / 0 → 1 / 1 / 1 | same |

- HPGe over-covered before because the certificate uncertainty was counted twice. Once it is
  counted correctly, NaI shows the model error that the double counting had hidden. The order
  selection removes most of it (largest deviation 7.2 % → 5.8 %), and the cross-validated
  model error covers the rest on average.
- **Not met:** NaI 2σ coverage is 0.8875 (limit 0.89). The model error is one average value,
  but it is concentrated between Am-241 (59.5 keV) and Co-57 (122 keV), where NaI has no
  other line. An energy-dependent model error is a possible next step. The limit is not changed.
- Scenario change, made openly: the first run used a true curve with a corner at 120 keV,
  which is not physical. It is kept as an informational case (`*_efficiency_kinked_truth`).
  There the curve uncertainty is now conservative.
- Real data (laboratory `EFF-GOOD.S0`): the cross-validated curve is stiffer and leaves
  Sr-85 +18 % (3.4 σ) above it, because the 514 keV peak is blended with the 511 keV
  annihilation peak. Both Y-88 points are 5 % below it, as expected from coincidence summing.
  Both are now listed or flagged. The closure test keeps its pre-D orders (3/2) to retain
  its meaning.
- Two existing tests asserted the double-counted behaviour (a 2 % floor of the efficiency
  component). They were corrected, with a comment.

## Release E: identification, activity, concentration and MDA

| Increment | Status | Evidence |
|---|---|---|
| E0. Criteria pre-registered: recall at 0.3 % drift; IAEA IDB real spectra (HPGe implausible identifications ≤ 1 per spectrum, U-235 recall ≥ 0.90; others report only). A first look at IDB preceded the registration (disclosed); the synthetic HPGe false-identification limit is 0.5, the IDB limit 1.0 was chosen for the much richer U/Pu spectra | done | `acceptance.py` (8c8fb27); `docs/baseline/before_E1/` (0e90aa1) |
| E1. Identification scoring: unmatched lines below 30 keV (L X-rays, absorbed unpredictably) no longer count as missing; the weak-emitter penalty applies only with ≤ 2 matched gamma lines; at good resolution (FWHM/E ≤ 4 % at 662 keV) the greedy explanation ranks a nuclide matching several distinct peaks first (parsimony) | done | `analysis/identify.py`; `docs/baseline/after_E1/`; `tests/test_public_spectra.py` |

E1 result (all synthetic criteria unchanged; IDB, 160 real spectra):

| | before | after |
|---|---|---|
| HPGe: Pu-239 found in Pu/MOX | 0 % | 78 % |
| HPGe: implausible identifications per spectrum (limit 1) | 9.6 | 8.8 (FAIL) |
| CZT: U-235 / Pu-239 found | 59 % / 0 % | 82 % / 20 % |
| LaBr3: U-235 / Pu-239 found | 23 % / 0 % | 69 % / 63 % |

- Rejected during E1: parsimony for NaI. Ag-110m (657.8 keV and many other lines) then took
  the Cs-137 662 keV peak in all four synthetic Cs-137 spectra (recall 0.88 → 0.74). At NaI
  resolution, a nuclide with many lines matches unrelated broad peaks by chance.
- Remaining IDB false identifications are mostly nuclides claiming U/Th/Pu K X-rays
  (90–115 keV: Eu-155, Sm-153) and lines of the U/Pu chains that are missing from the library.
  Next: application libraries (environmental, calibration, safeguards) as Aptec and Genie use.

## Public measured spectra (kept outside the repository)

Folder `SPECTRAMASTER_PUBLIC_DATA` (default `D:/SpectraMaster_public_data`); the files are not
redistributed with SpectraMaster. Tests that use them are skipped when the folder is absent.

| Source | Contents | Licence | Used for |
|---|---|---|---|
| InterSpec `example_spectra` (Sandia National Laboratories, github.com/sandialabs/InterSpec) | ORTEC portal, 8 HPGe detectors ("HPGe 50%"), 16384 channels: Ba-133 source 640 s and a background measured the same day (N42-2006); a 1064-spectrum pass-through | LGPL-2.1 | `tests/test_public_spectra.py`: N42 detector type; measured-background subtraction on real pairs |
| IAEA IDB, reference gamma spectra for U/Pu isotopics (nds.iaea.org/idb, v2024-01, 1591 SPE files, folder `iaea_idb/IDB-all-spectra`) | real U, Pu and MOX spectra; HPGe 961, CZT 336, LaBr3 225, CdTe 61, NaI 8; material type and certified isotopics in each file | CC BY 4.0, cite Dipti et al., Sci Data 12, 1868 (2025) | all 1591 read; detector type recognised for all (CdTe added as the CZT class); identification test set for Release E |

Result on the InterSpec pairs (8 detectors): Ba-133 net areas from peak-by-peak and full-spectrum
subtraction agree within 0.3 % (276-384 keV); natural lines that are in both spectra (K-40, Tl-208,
Bi-214) net to z = 0.0 ± 1.0 on average. A slight positive excess of Bi-214 at 1120/1238 keV
(z ≈ +1 to +1.5) is consistent with radon-progeny change between the morning and evening
measurements. Found while doing this: the N42 reader did not pass `<DetectorType>` on, so two
weak background spectra were guessed as NaI; it is now read (`extra["detector_type"]`) and used
first by `guess_detector`.

IAEA IDB identification check (random 60 spectra per detector type, before any Release E change;
evidence for E0, not yet a pre-registered criterion):

| detector | U-235 identified in U / MOX (≥ 0.7 % U-235) | Pu-239 identified in Pu / MOX | implausible identifications per spectrum |
|---|---|---|---|
| HPGe | 33/34 | **0/27** | **10.6** |
| CZT | 22/38 | 0/22 | 5.8 |
| LaBr3 | 6/33 | 1/18 | 7.0 |
| CdTe | 6/7 | 0/52 | 7.5 |
| NaI | 1/7 | – | 3.1 |

"Implausible" = not a U or Pu chain member, Am-241, Np-237, or a natural/fallout background
nuclide (most frequent: Gd-153, Lu-177, Ce-141, Nb-95, Eu-155, Xe-133m). Pu-239 lines have
emission probabilities of 10⁻⁵–10⁻⁴ per decay. The identification is not designed for such
spectra; this is the real-data counterpart of the synthetic P4 defect.

## Skipped tests in the existing suite (2026-10-14, this machine)

- 64: test_corpus files whose format is not detected (InterSpec RADDATA `.txt`, non-gamma xylib files, and others).
- 1: `test.spe` not readable.
- 1: the installed SandiaSpecUtils has no IEC 1455 parser.

The lab Aptec spectra, IAEA G-1, EML and TECDOC-2026 tests ran, because those data sets are
present on this machine under `D:/الاسس و المفاهيم العامة فى استخدام برامج الطيف الجامى/اطياف مرجعية`.
On another machine they are skipped.

## Justified changes and additions to the plan

1. **The plan document was copied into `docs/`.** It was supplied outside the repository
   (`Downloads`) and the skill expects it at `docs/SpectraMaster_Development_Plan_EN.md`.
2. **External reference spectra are referenced, not copied.** IAEA G-1 and EML are used from a local
   directory (`SPECTRAMASTER_REFDATA`). G-1 is described as public domain in its README. The EML
   files' licence is not stated, so they are not redistributed.
3. **Informational benchmark variants were added after the first run, with no acceptance limits:**
   - a broad Compton edge (8 keV / 15 keV extra smearing);
   - NaI on a 4096-channel MCA with no detector label.

   They do not replace or relax any pre-registered criterion. In A8 the 4096-channel NaI
   variant received its own pre-registered criteria (the NaI limits, unchanged) before the
   fix was written, and it moved from "informational" into the scored results. They show how much of the
   Compton-edge failure comes from the worst-case sharpness of the synthetic edge, and they
   reproduce defect P1 below.

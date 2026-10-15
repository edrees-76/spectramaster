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
| A5. Session integration in the GUI (open/save session, display stored vs recalculated results) | done | `gui/session_io.py` (`SessionController`): File > Open / Save / Save As session (`.smsession`); every opened spectrum gets a session; the spectrum file is found by SHA-256 (session folder first, then the user is asked; a different file is refused); stored results, energy calibration, activities (`QuantResults.from_dict`) and the edit history are restored as saved, never recalculated - stale reasons (including another engine version) are shown; unsaved-changes prompt for saved, opened or reviewed sessions. `tests/test_gui_session_io.py` (7). Limits: concentrations are not stored in the session file; spectra opened from the archive search do not prompt |

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

Weak-peak area bias (`HPGe.weak.area_bias_s7` −5.0 %, FAIL), diagnosed 2026-10-15 with 10× the
benchmark sample (diagnostic only, the criterion and its sample size unchanged): s = 5 / 7 / 10 give
−0.8 ± 0.6 % / −3.6 ± 0.5 % / −3.1 ± 0.4 %, so the −5.0 % of the scored run is partly a fluctuation
(≈ 20 peaks, standard error ≈ 3 %) on top of a real bias of about −3 %. Cause: the synthetic spectra
carry no FWHM calibration, weak peaks are fitted with the model width, and the default HPGe
resolution is 2.4 % narrower than the synthetic detector on average (−7.9 % to +1.5 %); strong
peaks (free width) are unbiased. Rescaling the model needs strong isolated peaks, absent here. A
narrower rescaling dead band (3 % instead of 8 % with ≥ 3 strong peaks) was measured and rejected:
no effect on the weak category, slightly more false peaks. Remedy in practice: an FWHM
calibration (B1 tool); the EMCA2000 `.dat` files carry none. The workflow now warns when a
spectrum has no FWHM calibration (`lab/workflow.py`, status outside_validated_scope).

## Release D: experimental efficiency calibration

| Increment | Status | Evidence |
|---|---|---|
| D0. Criteria pre-registered (bias and coverage of the curve; summing warnings; geometry guard; validation status shown); mixed-standard scenarios with a smooth known efficiency and per-nuclide certificate errors | done | `acceptance.py` (68e0db6, before any measurement); `docs/baseline/before_D1/` (7699119) |
| D1. Generalised least squares with the full covariance of the points: counting and emission probability independent, certificate activity shared by the lines of a nuclide, an optional component common to the standard; nothing added to the curve afterwards | done | `analysis/efficiency.py` (`point_covariance`); `tests/test_efficiency_release_d.py` |
| D2. Cascade-emitter calibration points carry a summing warning; the curve stores its geometry and validation status; `compute_activities` refuses a calibration of an incompatible geometry unless the user overrides it (reported), and reports unvalidated calibrations; a record's validation does not change its content hash | done | `analysis/efficiency.py`, `analysis/activity.py` (`calibration_checks`), `lab/calibration.py` |
| D3. Model orders and crossover chosen by leave-one-out cross-validation when not given; a model (interpolation) error from the leave-one-out residuals enters the curve uncertainty; points more than 3 σ from the curve are listed for review | done | `analysis/efficiency.py` (`select_orders`, `model_error`); `docs/baseline/after_D1/` |
| D4. Independent validation (`validate_curve`: points of a second source, \|z\| ≤ 3 and mean z² ≤ 2; marking validated stays the user's decision) and the GUI wizard extending the efficiency dialog: certificate (with an optional common standard uncertainty), detector and geometry editor (Marinelli/cylinder dimensions, nominal and filled volume, fill height, matrix, density; point distance; filter; empty = unknown, never zero), points with summing notes and exclusion reasons, automatic or explicit model orders with the selection, model error and outliers shown, independent validation tab, saved curve plus a `CalibrationRecord` with its status; the activity dialog checks the sample geometry and asks before using an incompatible calibration | done | `analysis/efficiency.py` (162db01), `gui/efficiency_dialog.py`, `gui/geometry_editor.py`, `gui/quant_panel.py`; `tests/test_gui_efficiency_wizard.py` (8) |
| D5. Emission-probability uncertainties (library data gap: ENSDF/DDEP values with provenance); detector picker linked to `DetectorProfile`; history of saved calibration versions | done | `lab/calibration_store.py` (`CalibrationStore`): append-only versions per lineage with a required reason, `supersedes` link, identical content creates no version, validation as events (a new version starts unvalidated; "validated" needs a note), tampered files detected and never returned as current; `tests/test_calibration_store.py` (5). Emission-probability uncertainties: ENSDF values from the bundled IAEA ndlab extract added to every IAEA library line (2542 of 2732; energies and intensities unchanged); used by `certificate_lines` (efficiency points `u_int_rel`) and per line in the activity (decision threshold/MDA weight, line weights, budget "intensity"); cross-checked against LNHB/DDEP (`validation/ddep_check.py`, 97.2 % of 363 lines within 3u; see `analysis/data/SOURCES.md`); `tests/test_intensity_uncertainty.py`. Benchmark effect within noise (HPGe eff cov1 0.677 → 0.663, cov2 0.927 → 0.923; NaI cov2 0.8875 → 0.881, already failing): the synthetic truth uses the library intensities exactly, so it cannot reward this component. Detector picker: `gui/detector_registry.py` (one JSON per `DetectorProfile`, stable ids, `SPECTRAMASTER_DETECTOR_DIR`), `gui/detector_picker.py` (manager dialog; session bar with detector, file label shown and never overwritten, geometry, undo); the efficiency wizard writes `detector_id`, the activity dialog warns on another detector's calibration and the workflow shows `incompatible_calibration`; `tests/test_gui_detector_context.py` (10). Limits: curves without a calibration record have no detector id, so no mismatch can be detected for them; no automatic match with the file's detector label |

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

`NaI.eff.cov2` (0.8875, limit 0.89), diagnosed 2026-10-15 with 10× the sample (diagnostic only):
coverage 0.63 / 0.88 at 1 / 2 sigma is a real shortfall, not a fluctuation. It is not in the curve
fit: the measured NaI efficiency points themselves are biased relative to their counting
uncertainty (60 realisations, z = (measured / true − 1) / u_count): Co-57 122 keV +2.2 (sd 0.13),
Hg-203 279 keV +2.8, Am-241 60 keV −0.9, Sr-85 514 keV sd 4.7; all NaI points sd 2.0 against
0.91 for HPGe. These are NaI peak-area systematics (continuum shape, Compton structures, blends)
- the same open problem as `NaI.edge.*` and `NaI.bkg_peak.*`. Not fixed; the Birge factor and the
LOO model error cannot see energy-specific biases that a smooth curve absorbs.

## Release E: identification, activity, concentration and MDA

| Increment | Status | Evidence |
|---|---|---|
| E0. Criteria pre-registered: recall at 0.3 % drift; IAEA IDB real spectra (HPGe implausible identifications ≤ 1 per spectrum, U-235 recall ≥ 0.90; others report only). A first look at IDB preceded the registration (disclosed); the synthetic HPGe false-identification limit is 0.5, the IDB limit 1.0 was chosen for the much richer U/Pu spectra | done | `acceptance.py` (8c8fb27); `docs/baseline/before_E1/` (0e90aa1) |
| E1. Identification scoring: unmatched lines below 30 keV (L X-rays, absorbed unpredictably) no longer count as missing; the weak-emitter penalty applies only with ≤ 2 matched gamma lines; at good resolution (FWHM/E ≤ 4 % at 662 keV) the greedy explanation ranks a nuclide matching several distinct peaks first (parsimony) | done | `analysis/identify.py`; `docs/baseline/after_E1/`; `tests/test_public_spectra.py` |

| E2. Drift before identification (P3): the B1 drift check (natural-background lines) runs first; its correction is applied to the peak energies for the identification only, and kept only when it explains the significant peaks ≥ 5 % better; every result then says so; the stored calibration is never changed | done | `analysis/identify.py`, `tools/calibrate.py` (`check_drift(peaks=)`); `tests/test_identify_drift.py` |

| E3. Application libraries built from the library's own categories (`environmental`: natural, cosmogenic, fission products, Co-60/Mn-54/Zn-65/Eu-152/154, Am-241, Cs-137 - 84 nuclides; `calibration` 50; `safeguards` 41; `medical` 56; `all` = engine default) and `identify(..., application=)` | done (engine and GUI: library combo, environmental by default in the GUI, drift warning) | `analysis/library.py` (`APPLICATIONS`, `application_library`); `tests/test_application_library.py` |

| E4. Concentrations from `lab.sample.SampleInfo`: Bq/kg labelled with its basis (dry/wet), Bq/L, Bq/m3 with measured filter fraction, stated collection efficiency (reported as an assumption) and decay during sampling (K = λt/(1−e^(−λt)), activities taken to the end of sampling); nothing computed when an input is missing (listed instead); not detected → "< MDA" in the same unit; quantity uncertainty added to the value, not to the MDA | done (engine and GUI: sample section and concentration table in the activity dialog, XLSX/CSV export) | `analysis/activity.py` (`concentrations`, `sampling_decay_factor`); `tests/test_concentrations.py` |

E3 result (real spectra; the scored criteria keep the `all` library for comparability):
IAEA IDB HPGe (98 spectra) implausible identifications 8.85 → **1.12** per spectrum with the
`safeguards` library, Pu-239 found 32/40 → 35/40 (reported as
`HPGe_implausible_per_spectrum_safeguards_library`). Five long laboratory spectra (ceramics,
14-309 ks) with `environmental`: already plausible (U/Th chains, K-40); Eu-155 is reported in
2 of 5 and stays a candidate (a genuine fallout nuclide; its 86.5/105.3 keV lines lie among the
Th/U X-rays): open.

Rejected attempt (X-ray interference, not committed): a candidate whose matched gamma lines
all lay on peaks already explained by the K X-rays of an element present in the spectrum (scale
from the element's strongest X-ray line) lost 70 % of its confidence (HPGe-like resolution only).
Measured before/after on the 20 longest laboratory spectra and the IAEA IDB subset: Eu-155 12 → 11
of 20 lab spectra and 53 → 52 IDB reports, Sm-153 39 → 22, HPGe implausible 8.82 → 8.46 per
spectrum (still FAIL), but CZT U-235 recall 0.77 → 0.68. Reverted. Cause found: in the IDB
spectra Eu-155 is matched at 105.5 keV **and** 146.1 keV (not an X-ray), and the library stores
each K-beta group as one weighted line (Th 106.9 keV instead of K-beta1 105.6 keV), so the
105.5 keV peak is not recognised as an X-ray. Fixed by the nuclear-data update (D5): the library
now resolves heavy-element K'beta1/K'beta2 (DDEP constants, `analysis/data/SOURCES.md`); U-235 and
Ac-228 claim the 105.5 keV peak as Th K'beta1. Eu-155 12 -> 2 of 20 lab spectra, IDB HPGe implausible
8.82 -> 8.15, no criterion changed.

Full benchmark after E2-E4/F1-F2 (`docs/baseline/after_E4_F2`): FAIL 15 → 14, PASS 99 → 100,
no criterion newly failing. HPGe recall at 0.3 % drift 0.06 → 1.0. Informational, not criteria:
IDB CZT U-235 0.82 → 0.77 and LaBr3 0.69 → 0.62 (drift correction applied to scintillator
spectra), HPGe Pu-239 0.78 → 0.80. Fixed in 631c763: the identification drift correction now
runs only at germanium resolution (FWHM/E ≤ 1 % at 662 keV); CZT U-235 0.82 and LaBr3 0.69 restored,
implausible CZT 5.09 → 4.79 and LaBr3 5.78 → 5.43 per spectrum; synthetic HPGe/NaI criteria unchanged.

E2 result (synthetic, 4 seeds per mixture): HPGe recall at 0.1 / 0.3 / 1 % drift
0.98 / 0.06 / 0.06 → 1.0 / 1.0 / 1.0; false identifications at drift ≤ 0.09 per spectrum; NaI
unchanged (0.88 at 0.3 %). A first version applied every detected drift. On IAEA IDB
plutonium spectra, which have few natural lines, the check matched Pu lines to background lines,
and Pu-239 fell from 6/12 to 1/12; the IDB test caught it. The correction now has to improve
the explanation. Laboratory archive, October 2009 (12 random spectra): the 1000 s food
spectra show K-40 only, so they cannot be checked (≥ 2 lines needed). A 6130 s ceramic spectrum
gives offset +0.93 keV, gain −0.09 %, as found when reading the archive.

E1 result (all synthetic criteria unchanged; IDB, 160 real spectra):

| | before | after |
|---|---|---|
| HPGe: Pu-239 found in Pu/MOX | 0 % | 78 % (benchmark subset; 6 of the first 12 Pu files) |
| HPGe: implausible identifications per spectrum (limit 1) | 9.6 | 8.8 (FAIL) |
| CZT: U-235 / Pu-239 found | 59 % / 0 % | 82 % / 20 % |
| LaBr3: U-235 / Pu-239 found | 23 % / 0 % | 69 % / 63 % |

- Rejected during E1: parsimony for NaI. Ag-110m (657.8 keV and many other lines) then took
  the Cs-137 662 keV peak in all four synthetic Cs-137 spectra (recall 0.88 → 0.74). At NaI
  resolution, a nuclide with many lines matches unrelated broad peaks by chance.
- Remaining IDB false identifications are mostly nuclides claiming U/Th/Pu K X-rays
  (90–115 keV: Eu-155, Sm-153) and lines of the U/Pu chains that are missing from the library.
  Next: application libraries (environmental, calibration, safeguards) as Aptec and Genie use.

## Release F: workflow, reporting and batch analysis

| Increment | Status | Evidence |
|---|---|---|
| F1. Workflow statuses (calibration required, incompatible calibration, outside the validated scope, results stale, not reviewed / reviewed), review approval (named reviewer, refused while stale), traceable report record (application and engine version, session id, spectrum fingerprint, sample, detector, geometry, calibrations with content hash and validation status, library, background, peaks, nuclides, activities, concentrations, statuses, edits, conventions) as JSON | done (engine and GUI) | `lab/workflow.py`; `tests/test_workflow.py` |
| F2. Batch analysis: spectra grouped by the detector stated in the file (unlabelled files together; a type guessed from weak peaks is shown, not used), number of channels and energy calibration (±1 keV over the range); each group needs its own explicit setup (efficiency calibration, sample geometry, application library, nuclides, background), unassigned groups are not analysed and say so, an incompatible geometry is refused per file; CSV with one row per file and nuclide; CLI `spectramaster batch PATHS [--group N --eff curve.json --geometry geom.json ...]` | done (engine, CLI, GUI) | `lab/batch.py`, `tools/quant_cli.py`; `tests/test_batch.py`. Laboratory archive, May 2009 (445 files): 8 groups, one per recalibration of the unlabelled HPGe |
| F3. GUI: status bar / workflow panel, review action, report from the record | done | `gui/session_io.py` (`WorkflowPanel`: always-visible dock, colour per level, translated; a missing efficiency calibration is information for identification-only work, an error once activities are computed - as in the report record), Analyze > Mark as Reviewed (name remembered, refused while stale), File > Export Report Record (JSON; asks before exporting a non-reportable record and marks it `"reportable": false`); `gui/batch_analysis.py` (groups, explicit setup per group, run off the GUI thread with progress and cancel, CSV). `tests/test_gui_workflow.py`, `tests/test_gui_batch.py`. PDF/HTML reports show the library, detector, geometry, concentrations (as computed, missing inputs listed) and the workflow statuses with "reportable" (option, on by default) |

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

## Aptec-style workflow, phase 1: Setup menu calibrations (2026-10-15)

The user works with Aptec PCMCA/WIN 6.31 and asked for its menus, workflow and, where possible,
its algorithms. Phase 1 of 6 (calibration) is on branch `claude/ux-aptec-calibration`.

**Method.** Aptec's code was not decompiled (licence, and 16-bit code that tools read poorly).
The methods were taken from Aptec's own help file (`aptec.hlp`, including the published `.S0`
file layout) and verified black-box: Aptec stores each calibration's points next to the
equation it computed, so a refit of the stored points must reproduce the stored equation.

| Aptec method | Rule | Verified on |
|---|---|---|
| Energy, resolution | unweighted polynomial, degree = min(max degree, points - 1) | 10 Aptec sample files, equal to 6 significant digits |
| Efficiency point | rate / (A[Bq] · yield · quantity · decay); `gamma/s` without yield; err = √(rate² + activity²) | 12 + 3 points of the sample files (`test_point_formula_reproduces_aptec_efficiencies`) |
| Efficiency A, B, D | ln eff polynomial in ln E (A 5th, B 3rd) or E (D 3rd), weights 1/(err%)², no error = 100 %, covariance (AᵀWA)⁻¹ unscaled | A and D on sample files (coefficients and full covariance), B on 3 laboratory files (numbers only) |
| Efficiency C, S | C as D with degree 5; S natural cubic spline of ln eff vs ln E | **not verified**: no Aptec example; reports say so |

**Interface.** New *Setup* menu before *Analyze*: Quick Energy Calibration (F2, up to 16 points,
the channel comes from the new channel marker or the centroid of the ROI containing it), Full
Energy / Resolution / Efficiency Calibration (Shift+F2 = efficiency) in an S_CALIB-style window
(File, Calibration F5/F6/F7/F8/F9, EditPoints, Method, Help; report and graph). The previous
calibration tools moved to *Setup > Advanced Calibration Tools*. Saving puts the calibration on
the displayed spectrum (no file is overwritten); the efficiency calibration is also written to
the efficiency library as a curve that Quantify can use (`EfficiencyCurve` gained the `lnpoly`
and `spline_lnln` forms).

**Scientific notes.** Aptec's covariance is not rescaled by χ²/dof; when χ²/dof > 1 the saved
curve carries a warning that its uncertainty may be underestimated. Aptec does not flag
true-coincidence summing or interferences in calibration points; the advanced efficiency wizard
still does. No pre-registered benchmark criterion is affected: the analysis engine is unchanged.

Remaining phases: ROI menu, View menu, spectrum operations, Peak Search / Identify / Background
Subtract / Quantify, MultiFit.

## Aptec-style workflow, phase 2: ROI menu (2026-10-15)

Branch `claude/ux-aptec-roi`. The ROIs drawn on the plot are now calculated with Aptec's rules
(`spectramaster/analysis/aptec_roi.py`), verified against the ROI records Aptec stored in its
sample spectra (`tests/test_aptec_roi.py`; ROI layout from the help file's `.S0` structure):

| Aptec rule | Verified on (Aptec sample files) |
|---|---|
| End points: X channels outside each side (`BL = RL - X`, `BH = RH + X`), or X varying from a low- to a high-energy value | 79/79 ROIs, including the groups below |
| Group: when an ROI's end points would fall inside its neighbour, the ROIs share one background (end points outside the group plus the channels between them); `chern.s0` (3-channel gap, X = 5) is grouped, `co60cal.s0` (2-channel gap, X = 2) is not | 79/79 |
| Background: degree 0 = line between end-point averages placed at `RL-1` / `RH+1`; degree 1-5 = unweighted least squares through the end points | 73/79 |
| Gross = Σ RL..RH; Net = Gross - Background; % error (1σ) = √(G + B) / Net · 100 | gross 79/79; background, net, error 73/79 |
| FWHM / FWTM: outward from the maximum net channel to the first channel below 1/2 (1/10), linear interpolation; edge sentinels when not found | FWHM 72/73, FWTM 64/73 |
| Centroid: Net or Net·\|Net\| weighting over gross half max, net FWHM, net FWTM (rounded) or the whole ROI | 69/73 |
| MDA (cps) = (K² + 2K√(2B)) / live time | help file only; not stored per ROI, not verified |

The six ROIs that do not match are all in `nai1x1.s0`: no end-point window or weighting
reproduces their stored background from the stored counts, so they were presumably computed from
an earlier state of that file; the other comparisons exclude it. The remaining FWHM, FWTM and
centroid differences are weak, noisy peaks. A help-file note (Aptec 6.x change log) about
searching the maximum from the ROI centre outward was tested and matched worse, so it is not used.

**Interface.** New *ROI* menu between *Setup* and *Analyze*: Properties (Shift+R: background line,
end points, centroid range and weighting, MDA and error sigma; saved in the settings), Paint (F3,
Ctrl-click), Edit (F4), Delete Indexed (Del, no warning, as in Aptec), Delete All (with
confirmation), Sort (by centroid), Flag Definitions (Aptec's letters b, m, s, *, <, ?, >).
Space / Shift+Space index the next / previous ROI (the marker moves to its centroid; the ROI is
outlined). While painting or editing, the ROI Paint bar appears above the status bar (Set,
Delete, Cancel, << >> F3, >> << F4, <<-- F5, -->> F6), the mouse paints the ROI and the status
bar shows its live gross, net and centroid; Enter sets, Esc cancels. Quick paint: Ctrl-click the
left side of a peak, then the right side. The ROI list gained Background, % Err (×error sigma)
and Flags columns, and its CSV export the end-point channels, FWTM, MDA and flags.

**Scientific note.** Aptec's error √(G + B) treats the background as if it had been counted over
the ROI width. The background is estimated from 2X end-point channels, so with few end points
its true variance is larger (B·n/(2X) for an end-point-average line); the earlier MAESTRO-style
formula included this. The ROI list follows Aptec, as requested; the analysis engine (peak
search, fits, activities) is unchanged, so no pre-registered benchmark criterion is affected.

## Aptec-style workflow, phase 3: View menu (2026-10-15)

Branch `claude/ux-aptec-view`. The View menu now follows Aptec's order and sits after *Analyze*
(`spectramaster/gui/aptec_view_ui.py`):

- **Preferences** (all display options in one dialog), **Color** (spectrum, fill, background,
  grid, axis text, ROIs, marker, fitted peaks; *Default Colors* and *Black & White* for printing;
  the colors also apply to printed and exported graphs), **QA Control Bar** (Ctrl+8: the buttons
  of the main tool bar), **Default Position**, **Save Settings on Exit**.
- **Vertical Scale**: Auto Vert (A), Auto Zero Vert (Z: the minimum follows the lowest counts in
  view), Next / Prev Scale Type (S / Shift+S), linear / log / sqrt, Raise / Lower Spectrum (Up /
  Down), Raise / Lower Base (Shift+Up / Down).
- **Horizontal Scale**: Channel / Energy X Scale (C / E), Zoom (NumPad 5: 64, 16, all channels
  around the marker), Expand / Contract (NumPad + / -), Max Expand / Contract (Shift), Marker
  Left / Right (arrows; the window scrolls at its edge), Marker to Left / Right Edge (Home / End),
  Marker to Far Left / Right (Shift+Home / End), Spectrum Left / Right (PgDn / PgUp, Shift: all
  the way). These keys act when the plot has the focus.
- **Horizontal / Vertical Split** (H / V): the whole spectrum below or beside the expanded region,
  which is shaded on it; a click there moves the expanded region.
- Next / Prev ROI (Space / Shift+Space), Plot All Points (L), Fill Spc (F), Grid (G), Show Fitted
  ROIs (K: Show, Fill, Hide), Fill Normal ROIs (Shift+F), ROI Data (D: an Aptec-style ROI
  information box with Gross, Bkgnd, Net, err, Cntr, FWHM, FWTM, Net cps, or the background
  parameters BL, RL, RH, BH, B0-B5 in channel numbers; or off), ROI Display (Shift+D), Show ROI
  Labels (J), Show Channel Marker (Shift+J), FWHM Percent (%), Connect Points (N).
- Double-click indexes the next ROI (Shift: the previous one), as in Aptec; without ROIs it
  still shows the whole spectrum. Esc and Ctrl+0 show the whole spectrum (Home now moves the
  marker, as in Aptec).
- SpectraMaster's own view commands (zoom history, go to, overlays, panels, overview strip) are
  under *View > More View Options*; the language stays at the end of the View menu.

**Note.** *Show Fitted ROIs* draws each peak of the analysis as a Gaussian from its centroid,
FWHM and net area over the average background of its region; it is a display aid, not the
fitted continuum (Fit Inspection shows the exact fit). Aptec's MultiFit (phase 6) will replace
it with its own fitted ROIs. The analysis engine is unchanged.

Remaining phases: spectrum operations, Peak Search / Identify / Background Subtract / Quantify,
MultiFit.

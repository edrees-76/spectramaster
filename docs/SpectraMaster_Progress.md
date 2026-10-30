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
- The spectrum is drawn as Aptec draws it: one point per channel, and with more channels than
  screen columns only the highest channel of each column; Fill Spc (F) gives the filled
  histogram, Connect Points (N) the connected line, Plot All Points (L) all channels of each
  column. *View > Color > Aptec Colors* gives Aptec's yellow points on black.
- Double-click indexes the next ROI (Shift: the previous one), as in Aptec; without ROIs it
  still shows the whole spectrum. Esc and Ctrl+0 show the whole spectrum (Home now moves the
  marker, as in Aptec).
- SpectraMaster's own view commands (zoom history, go to, overlays, panels, overview strip) are
  under *View > More View Options*; the language stays at the end of the View menu.

**Note.** *Show Fitted ROIs* draws each peak of the analysis as a Gaussian from its centroid,
FWHM and net area over the average background of its region; it is a display aid, not the
fitted continuum (Fit Inspection shows the exact fit). Aptec's MultiFit (phase 6) will replace
it with its own fitted ROIs. The analysis engine is unchanged.

## Aptec-style workflow: Edit and Display menus (2026-10-15)

Branch `claude/ux-aptec-edit`, requested with screenshots of Aptec's Edit and Display menus. Menu
bar order now: File, Edit, Display, Setup, ROI, Analyze, View (`spectramaster/gui/aptec_edit_ui.py`).

- **Edit**: Select All / Select Region (reverse video, as in Aptec), Copy to ClipBrd (Ctrl+Ins: the
  selected part of the display as a picture), Clear Selection (Ctrl+Del); Sample Description (F5:
  title, spectrum label, user, detector, geometry and sample IDs, sampling start / stop); Quantity
  Description (F6: quantity and units, W/X/Y constants, convert-factor units, activity units and
  time, total quantity; Quantify reads the quantity); Spectrum Data (start, live and true time,
  with Aptec's warning); Certificate (calibration-source certificates, `analysis/certificate.py`);
  Library (read-only view of the identification library); Decay Correction Calculation
  (`analysis/decay_calc.py`: activity and half-life units, A(t) = A0·exp(−ln2·Δt/T½), with the
  half-life contribution to the uncertainty); Load Header Information (energy and resolution
  calibrations, efficiency calibration of an Aptec file saved to the efficiency library, sample and
  quantity descriptions, ROIs read from the `.S0` ROI records, spectrum data); Reset Header (with
  confirmation). Load File into MCArd stays disabled: acquisition hardware is out of scope.
- **Display**: Normal Spectrum; Energy, Resolution and Efficiency Calibration drawn in place of the
  spectrum with their points (Aptec files: the points Aptec stored), Space / Shift+Space index the
  points and show the calculated value and deviation. Intermediate and Stabilized Spectrum (digital
  stabilizer hardware) stay disabled.
- Keys as in Aptec: F5 / F6 are Sample / Quantity Description; peak search & identify moved from F5
  to P (Aptec's Peak Search key).
- The efficiency calibration's *Load ROIs* defaults can name a certificate: activities, their
  errors, units, reference time, yields and half-lives then come from it (lines matched by isotope
  and energy within 1 keV).

All edits apply to a copy of the displayed spectrum; no file is overwritten until it is saved. The
analysis engine is unchanged.

Remaining phases: spectrum operations, Peak Search / Identify / Background Subtract / Quantify,
MultiFit.

### Aptec UX phase 4: spectrum operations (Analyze menu)

The lower part of Aptec's Analyze menu, in Aptec's order. The calculations are in
`tools/spectrum_ops.py` (no Qt); the menu and dialogs in `gui/aptec_ops_ui.py`.

- **Add Constant** (whole number, may be negative), **Normalize** (counts and live / true times
  multiplied; with a compare spectrum the default factor is Aptec's live time matching multiplier,
  compare / displayed live time, shown with 16 significant figures; −1 inverts), **Shift** (left /
  right by whole channels, calibrations unchanged, vacated channels zero), **Smooth** (3, 5, 7, 9
  points), **Reduce Channels** (2, 4, 8 … : 1, gross counts unchanged; energy and resolution
  calibrations, stored calibration points, ROI end points and the view follow), **Derivative**
  (1st / 2nd / 3rd, always taken from the original data, "Original data" restores it; optional
  smoothing first).
- **Compare** loads a spectrum file and draws it over the displayed one (again: leaves compare
  mode); **Position** and Ctrl+Up / Ctrl+Down move it vertically in pixels; **Exchange** swaps the
  two spectra; **Combine** / **Strip** add / subtract it channel by channel (live and true times
  added by Combine), after a confirmation that shows both live times and warns when they differ
  or when the energy calibrations differ.
- Not in Aptec: **Undo Spectrum Operation** (Ctrl+Z, 20 steps) and **Reload Original Spectrum**.
- Every operation changes only the spectrum on the screen; the operations done are listed in
  `extra["aptec_status"]` with Aptec's wAnalyzeStatus names (ConstantAdded, Normalized,
  Left/RightShifted, Smoothed, Packed, Derivative, Combined, Stripped). After smoothing, stripping,
  a derivative, a constant or a normalization `extra["counts_are_poisson"] = "no"` and the status
  bar warns that sqrt(counts) uncertainties are not valid. Negative channels are drawn below zero.

Not documented by Aptec, hence our own choices, **not verified against Aptec output**: binomial
smoothing weights ((1 2 1)/4, (1 4 6 4 1)/16, …, renormalised at the spectrum ends); derivatives
by central differences; Normalize multiplies the times by |factor|. A stripped spectrum keeps no
per-channel variance yet: ROI errors computed on it assume Poisson counts and are too small; the
Background Subtract of phase 5 will propagate the background uncertainty.

### Aptec UX phase 5: Peak Search, Identify, Background Subtract, Quantify (Analyze menu)

Aptec's method is now the default (user decision); SpectraMaster's fitted analysis stays
available under Analyze > Setup > Analysis Method.  Calculations: `analysis/aptec_analyze.py`
(no Qt); `.S0` analysis records: `analysis/aptec_s0.py`; menu and dialogs:
`gui/aptec_analyze_ui.py`.

- **Analyze menu in Aptec's order**: Setup > (ROI Properties Shift+R, Peak Search Shift+P,
  Identification Shift+I, Background Subtract Shift+B, Quantify Shift+Q, Analyze Defaults,
  Analysis Method), Peak Search `P`, Identify Peaks `I`, Background Subtract `B`, Quantify `Q`.
- **P** sets ROIs on the peaks (ROI statistics with the ROI Properties; ROIs whose 1-sigma net
  error is above Max Peak Error rejected, backgrounds recalculated, until stable).
- **I** identifies the ROIs with an Aptec isotope library (`.lib`) or the bundled library
  (S_Ident logic: FWHM-based or fixed tolerance, fraction limit, optional half-life reject).
- **B** subtracts the net rate of the same identified line in a background spectrum (searched
  and identified with the same setups) when it is above its MDA; flag `b`.
- **Q** activity = net rate / (efficiency × yield), decay-corrected to the activity time,
  per quantity, W / X / Y, in the chosen units; efficiency from the spectrum's Aptec
  calibration or a saved efficiency curve, taken at the ROI centroid energy.
- Results are kept on the ROIs: the ROI list gains Isotope, Line keV, Activity, Err %, MDA
  (also in the CSV export) and the plot labels each ROI with its isotope.
- Analyze Defaults: factory defaults, save / recall user defaults for all analysis setups.

**Comparison with Aptec** (pre-registered protocols, `docs/baseline/aptec_*_protocol.md`;
results `docs/baseline/aptec_analyze_results.md`; lab archive, numbers only):

- Peak Search **failed** its limits: on the test set (4203 spectra, 28 030 stored ROIs) it
  finds 79 % of Aptec's ROIs with 62 % precision, median edge difference 2 channels.  The
  acceptance rule (1-sigma error) and the edge rule (lowest count between edge and top) were
  established from the stored ROIs; how Aptec picks peak tops and window extents was not.
- Identify **failed** its limits: 88 % ROI agreement (84 files, 736 ROIs) against 95 %.
- Quantify: the pre-registered comparison (efficiency at the line energy) **failed** (45 of 49
  within 0.5 %); with the efficiency at the ROI centroid energy, found afterwards on the same
  files, 49 of 49 agree within 0.003 %.
- Background Subtract could not be compared (no background-subtracted file).

### Aptec UX phase 6: MultiFit (Analyze menu, `M` / Shift+M)

`analysis/aptec_multifit.py` (no Qt): Gaussian decomposition of each ROI by Marquardt-Levenberg
least squares, following the Aptec help (Multifit Fitting Parameters): fixed width from the
resolution calibration or one varying scale (always varying when 511 keV is in the region),
fixed ROI background or varying polynomial, peaks kept when amplitude >= K x its uncertainty
(K = 1.645), Max Iterations / Percent Change / Min Reduced Chi Square stopping, Maximum Overlaps,
multiplets only or multiplets and singlets, NaI limited to 512 channels, auto resolution
calibration from the ROI widths when the spectrum has none.  Centroid guesses: third-derivative
crossings (overlapped close peaks) or net maxima (separated overlaps).  With a fixed background
the area uncertainty includes the background-line uncertainty (our addition).

- A multiplet ROI becomes one ROI per fitted peak (same bounds); its statistics report the
  fitted area, centroid and FWHM, flag `m` (multiplet component) or `s` (fitted singlet), so
  Identify and Quantify use the fitted peaks.  The plot draws each Gaussian and their sum.
- Changing the ROI Properties removes the fits (as in Aptec).

**Validation** (no Aptec MultiFit result exists in any available file): pre-registered
synthetic protocol `docs/baseline/aptec_multifit_protocol.md`, results
`docs/baseline/aptec_multifit_results.md` -- all limits **passed** (singlet area bias −0.43 %;
doublets >= 1 FWHM apart: both found 94.5–100 %, component bias <= 2.8 %, pull SD 0.90–1.17).
At 0.8 FWHM doublets are usually fitted as one peak.

All six Aptec UX phases are done; the user manual is to be updated next (user decision).

## External review fixes (2026-10-20)

Findings of an external review (Gemini) and a SonarQube Cloud scan, checked one by one against
the code; only the confirmed ones are fixed.

- **mBq read as MBq** (found while checking the units; neither review reported it): the Aptec
  activity units matched case-insensitively, so `mBq` gave a factor 10^9 wrong.  Exact match
  first now; `mBq` added to the units table.
- Quantify: *total quantity* selected but missing → not quantified ("total quantity is
  missing") instead of silently omitted; activity date far after the count → flag `<`, "decay
  correction underflow" instead of activity 0; units `cps` / `cpm` → the net count rate (no
  efficiency, yield or decay), instead of "unknown units".
- Peak search and ROI statistics reject NaN / infinite counts with a clear message.
- Strip records `strip_live_time_warning` when the live times differ (the dialog already warned;
  counts are subtracted as they are, as Aptec: normalize first).
- Engine messages of the Aptec Analyze commands are shown in the interface language.
- CI installs pinned wheels (`requirements-ci.txt`); NaN tests with `math.isnan`; the peak cache
  hash is marked not for security.

Not changed, by design: Aptec's ROI area uncertainty sqrt(G + B), Background Subtract only for
background lines above their MDA, channel-by-channel Strip -- these reproduce Aptec (the
SpectraMaster engine has the full propagation).  NaI and true-coincidence summing remain the
documented limitations.

## ISO 11929: best estimate and coverage interval (2026-10-20)

First item of the development proposals drawn from the published vendor documentation (Genie 2000
Customization Tools manual, chapter 3, and its ISO 11929 help: Genie reports Bayesian best estimates
with upper and lower bounds).  No vendor software was decompiled.

- With the detection limits set to ISO 11929, each nuclide with a primary result now also gets
  the best estimate of the non-negative true value, its standard uncertainty and the
  probabilistically symmetric coverage interval (ISO 11929-1:2019; coverage probability
  `ActivityOptions.coverage`, default 0.95), in Bq and in the specific unit
  (`analysis.activity.iso11929_best_estimate`).  Computed in log space (`log_ndtr`,
  `ndtri_exp`), so a strongly negative primary result stays finite.
- Shown in a new column of the results table and in the printed report (concentrations), and
  exported (CSV/XLSX columns `best_*`, `coverage_*`, metadata "Coverage probability").  Currie
  results are unchanged and get no best estimate.  Stored sessions without the field read as 0.95.
- Tests: the formulas against an independent direct evaluation (`scipy.stats.norm`, relative
  1e-9 over y/u in [-8, 8]); the closed form at y = 0 (sqrt(2/pi) u, sqrt(1 - 2/pi) u); y >> u
  gives y +- 1.96 u; integration through results, export, session round trip, concentrations
  and the table (both languages).  This is a reporting formula, not a laboratory validation.

## Peak-shape calibration: low-energy tail (2026-10-20, increment 1: engine)

Real HPGe and NaI peaks have a low-energy tail. Fitted with pure Gaussians, the areas of the
synthetic `tailed` peaks (4 % tail) were biased (-1.05 % HPGe, -1.42 % NaI), and their stated
uncertainties did not cover the error (z within 2 sigma 0.78 / 0.03). The idea follows the
published Genie 2000 "Energy and Shape Calibration"; no vendor software was decompiled.

- `analysis.peaks.peak_shape`: a Gaussian plus a fraction eta of an exponentially modified
  Gaussian tail (slope tau sigma), with the same area normalisation and an analytic Jacobian.
  The tail is evaluated with `erfcx` (lazy scipy import), so it stays stable far from the peak.
- `shape_calibration(spectra)` measures eta and tau on the strong isolated peaks of a detector's
  calibration spectra (pooled). `set_peak_tail` attaches them to a spectrum
  (`extra["peak_tail"]`, kept by background subtraction and re-binning). `find_peaks`, the
  manual refit and the measured-background estimator use them.
- **Without a shape calibration nothing changes.** Results are bit for bit those of the Gaussian
  engine.
- A first attempt estimated the tail in every spectrum. It was rejected: the same detector got
  different tails, so G1300 area ratios were biased (0.025 > 0.02), and the raw and the
  background-subtracted spectrum disagreed. See `docs/baseline/peak_tail_protocol.md`.
- Evaluation (pre-registered criteria, `before_T1` / `after_T1`): no criterion went from PASS to
  FAIL.
  - HPGe tailed peaks with the calibration: area bias +0.14 %, z within 2 sigma 0.95.
  - A tail-free detector gets eta = 0.
  - **NaI tailed criteria fail** (-0.71 %, 0.57): the NaI tail is underestimated (eta 0.021
    against 0.04). This is a known limitation.
- Next: store the shape calibration per detector (calibration store), the interface, then the
  Genie-style residual search on top of it (it splits tailed peaks without a tail model).

## Peak-shape calibration, increment 2: per detector, used by the session (2026-10-20)

- `DetectorProfile.peak_shape` holds the detector's peak-shape calibration: eta, u(eta), tau,
  number of peaks, their energies, a note, the measurement time and the source file names.
  It is stored with the profile in the detector registry, and old profile files read as "not
  measured". `set_peak_shape` records a result. A result with eta = 0 is kept too, because it
  documents that the peaks were measured to be Gaussian.
- **Setup > Detector Profiles > Peak Shape...** measures the selected detector's shape on
  calibration spectra (strong isolated peaks, pooled), shows the result and records it after
  confirmation. It refuses with fewer than 2 qualifying peaks. Editing the profile keeps the
  shape, and the profile tooltip shows it.
- The session takes a snapshot of the detector, including its shape. When the displayed spectrum
  belongs to a session whose detector has a tail, it is fitted with that shape: peak search,
  manual refit and the measured background. Choosing another detector without one returns to
  Gaussian peaks. As for every detector change, existing results are marked as requiring an update.
- The printed report lists the peak shape next to the FWHM calibration.
- Not yet: batch analysis groups spectra by the file's detector label and has no link to the
  detector registry, so it fits Gaussian peaks, as before.

## Residual search on top of the peak-shape calibration (2026-10-20)

Genie-style residual search in every fit region (`analysis/peaks.py`, `RESIDUAL_SEARCH`):

- One component is added at a time, at the most significant residual excess at least 1 FWHM
  from the fitted components.
- The component is kept when chi2 drops by more than 9.
- The 1 FWHM proximity clause is also checked on the fitted positions.

It runs only on high-resolution spectra **with a measured peak-shape calibration**
(`shape_calibrated`; a Gaussian calibration, eta = 0, now counts too). Without a measured shape,
the residual of an unmodelled tail looked like a satellite peak: in the first attempt the
unmatched peaks rose from 0.98 to 6.45 per spectrum. Uncalibrated spectra are fitted exactly as
before.

Benchmark (`docs/baseline/after_R2`, protocol `docs/baseline/residual_search_protocol.md`,
amendment 3):

- HPGe satellites at 1.25-2 FWHM, at 3-10 % of the main peak, were all found (100 %), with and
  without a tail.
- No extra peaks were reported.
- The main-peak area changed by less than 0.1 %.
- No criterion went from PASS to FAIL, and all uncalibrated results are identical.
- There is no real-data evidence yet.

## Reagent blank correction (2026-10-20, engine and CLI)

This is the third link of Genie's peak-area correction chain; peak-by-peak background subtraction
already existed.

`compute_activities(..., blank=QuantResults)` subtracts, line by line, the activity of a blank
sample prepared and counted like the samples:

- The blank's value is decay-corrected to the sample reference date.
- Its counting uncertainty is added both to the result and to the decision-threshold variance,
  for Currie and for ISO 11929.
- Efficiency, emission probability and attenuation stay relative to the net value.
- A line with no peak in the blank is not corrected, and this is noted.

CLI: `spectramaster activity SAMPLE --eff CURVE --bkg BKG --blank BLANK`.

Benchmark `reagent_blank` (`docs/baseline/reagent_blank_protocol.md`, `after_RB1`), HPGe and NaI:

- Activity bias -0.4 %.
- 2-sigma coverage 0.97 / 0.975.
- A reagent-only nuclide was declared detected in 2.5 % / 0 % of samples, against 100 % without
  the blank.
- No criterion went from PASS to FAIL.

The interface comes next.

## Reagent blank in the interface (2026-10-20)

The activity dialog (Analyze > Activity...) has a "Reagent blank" row, under the background row,
with Browse and Clear:

- The blank spectrum is analysed exactly like the sample, with the same curve, options and
  background, and is then subtracted line by line (`ActivityDialog._compute`).
- The results table has a new column "Blank subtracted Bq ± u".
- The export gets `blank_bq` and `blank_u_bq`.
- The report shows the subtracted value under each concentration.
- The session results keep the blank's name in `QuantResults.blank`.

## Reference peak correction (2026-10-20, engine and CLI)

This is the first link of Genie's peak-area correction chain. It handles random summing and
pile-up losses that the live time does not correct.

`ActivityOptions.reference_peak = {energy, rate, rate_rel_unc, half_life_s, ref_date}`:

- The peak at `energy` (a pulser, or a fixed reference source) gives K = expected rate / measured
  rate. A source's rate is decay-corrected.
- K multiplies every activity, threshold and MDA.
- u_rel(K) enters the budget as "reference peak" and the ISO 11929 w uncertainty.
- A reference peak that is not found refuses the calculation.
- `reference_rate(spectrum, energy)` measures a reference source's rate in a low-rate spectrum.

CLI: `--ref-peak KEV --ref-rate CPS [--ref-rate-unc F] [--ref-spectrum FILE] [--ref-half-life S]`.

Benchmark `reference_peak` (`docs/baseline/reference_peak_protocol.md`, `after_RP1`):

- The correction factor is accurate to 0.06 % (HPGe) and 0.03 % (NaI), with losses of 0-10 %.
- Uncorrected, the bias is -5.9 % / -7.7 %.
- Coverage passes, and a missing reference peak is always refused.
- The four pre-registered bias criteria **fail** (-1.0 % / -3.0 % against 1 %). Their limits are
  unchanged.
- The cause was found after the results: the criteria also measure the existing low-bias of weak
  (s about 40) peak areas, -1.1 % on HPGe and -3.0 % on NaI. Two report-only metrics, `k_bias` and
  `fit_bias`, were added post hoc to separate the two.
- That weak-peak area bias is left for a later increment.
- No criterion went from PASS to FAIL.

The interface is not done yet.

## Medium-signal peak areas: NaI continuum curvature (2026-10-20)

The reference-peak benchmark showed that peaks of s about 20-40 are fitted low. A new
pre-registered category `medium_peaks` (`docs/baseline/medium_peaks_protocol.md`) measures
isolated peaks at s = 20, 40 and 80.

The NaI cause: the log-linear continuum exp(b0 + b1 x) cannot follow the curvature of a real
continuum over the wide NaI fit regions.

The change is for log-linear fits only:

- The continuum becomes exp(b0 + b1 x + b2 x^2).
- b2 is measured on a region three times wider and then held fixed.
- The wide fit is used only when its chi2 is consistent with the model; otherwise b2 = 0, as
  before.

Two earlier variants were rejected by the protocol's criteria; the protocol documents both:

- b2 free in the fit raised the SD by 1.66 times.
- An ungated wide fit broke the strong-peak coverage (`after_MP1`).

Results (`after_MP0` -> `after_MP2`), NaI, s = 20 / 40 / 80:

- Bias: -2.3 / -0.8 / -0.3 % -> -1.3 / +0.03 / +0.25 %.
- SD ratio: 1.00-1.03.
- No criterion went from PASS to FAIL; NaI.medium.area_bias_s20 went from FAIL to PASS.

HPGe medium peaks remain 1.4-3 % low, with cov2 of 0.92. Three new HPGe criteria fail. The cause
is probably the fixed model width of weak peaks; this is the next step.

## HPGe resolution-model shape from the spectrum's own peaks (2026-10-20)

Without a FWHM calibration, HPGe weak peaks were fitted with the width held at the default
resolution sqrt(0.75 + 0.00185 E). For the benchmark detector that model is 8 % narrow at
200 keV and 1.5 % wide at 1400 keV. The existing rescale only applies one median factor beyond
8 %, so the areas followed the width error.

When at least 3 strong isolated peaks span more than a quarter of the spectrum, the model of a
non-scintillator without a FWHM calibration now becomes sqrt(k f^2 + d), fitted to their free
widths. `docs/baseline/hpge_width_shape_protocol.md` was pre-registered.

Results (`after_MP2` -> `after_HW1`), HPGe:

- Medium peaks at s = 40: -1.4 % -> -0.2 %.
- cov2: 0.92 -> 0.94.
- Reference-peak bias: -1.0 % -> -0.3 %.
- Four criteria went from FAIL to PASS, none from PASS to FAIL; 19 criteria fail.
- s = 20 is still -2.05 %, against a limit of 2 %.
- `HPGe.weak.area_bias_s7` (-5 %) is unchanged: there are no strong peaks to calibrate the shape.

In the laboratory, a FWHM calibration (Setup > calibrations) gives the right shape directly, and
it is used as it is.

## Reference peak correction in the interface (2026-10-20)

The activity dialog (Analyze > Activity...) has a checkable group "Reference peak correction
(pulser or fixed reference source)". It is off by default.

- Fields: the peak energy, the expected rate in cps and its uncertainty in %.
- Half-life in days; 0 means a pulser, with no decay. For a source, there is also the date of
  the rate.
- "Measure from a spectrum..." takes the rate, its uncertainty and its date from a low-rate
  reference measurement (`activity.reference_rate`).
- The values are remembered in the settings (`quant/reference_peak`). The group itself is not
  remembered, so the correction is always switched on explicitly.
- A reference peak missing from the sample (or from the reagent blank, which is corrected the
  same way) refuses the calculation with a message.
- K and its uncertainty appear in the result notes and in the concentration notes of the report.

## True-coincidence summing, increment 1: coincidence data (2026-10-20)

This is the first step towards a true-coincidence summing (TCS) correction. No correction is
applied yet; cascade emitters keep their "not corrected" note.

The data come from SandiaDecay `sandia.decay.min.xml`. It is the same commit as the bundled data,
but with the gamma-gamma coincidence tables, and it is kept outside the repository like the IAEA
database. `build_coincidences.py` derives `analysis/data/coincidence_table.json` from it:

- For 171 library nuclides and their included daughters with gamma cascades, each decay
  transition gets its gammas (per decay) and the cascade probabilities P(j | i).
- 182 physically impossible pairs of weak lines are dropped and counted. These have P > 1, or a
  reverse probability I_i P(j|i) / I_j > 1.02, mostly Pa-233, Pa-234, Yb-169 and Ir-192.
- The main laboratory nuclides are clean: Co-60, Cs-134, Ba-133, Bi-214, Pb-214, Tl-208, Y-88
  and Eu-154.

`analysis/coincidence.py` loads the table. `Transition.coincident[i, j]` is P(j | i) in either
cascade order.

Limits of the data:

- Gamma-gamma only. There is no X-ray - gamma summing for EC nuclides such as Ba-133, and no
  511 keV summing for Na-22.
- No angular correlation.

Tests check the main cascades against the source, that every probability is physical, that the
intensities agree with the gamma library to 2 %, the provenance, and an optional byte-identical
rebuild.

The table is bundled with the executable and listed in the third-party notices.

## True-coincidence summing, increment 2: correction engine and CLI (2026-10-20)

`ActivityOptions.tcs = {"peak_to_total": [a, b], "pt_rel_unc": u}`; on the command line,
`--tcs-pt A,B [--tcs-pt-unc %]`. Each line of a cascade emitter is divided by its first-order
COI:

- COI = 1 - sum_j P(j|i) eps_t(E_j), plus the summing-in of crossover pairs.
- eps_p comes from the efficiency curve, clamped to its range.
- eps_t = eps_p / PT. The peak-to-total ratio PT(E) = min(1, a (E/1000)^b) is a stated assumption
  of the detector and geometry.
- u_rel(COI) = summing-out x u / COI is a correlated "coincidence summing" budget component.
- COI is exported per line. The "not corrected" note becomes "corrected (COI ...)", and the
  assumptions are listed in the result notes.

`docs/baseline/tcs_protocol.md` was pre-registered and validated against an independent
event-by-event simulation (`validation/tcs_mc.py`). The simulation uses hand-coded ENSDF level
schemes of Co-60, Cs-134 and Y-88 with the library's IAEA intensities, so it shares neither the
formula nor the coincidence table.

Results (`after_TC1`):

- All pre-registered criteria pass. Far: max(|d| - 3 sigma) = -0.4 %. Marinelli-like: +0.2 %.
  Co-60: 0.23 %. Crossover lines: within the limit.
- The effect being corrected reaches 18 % for Cs-134 lines and a factor of 5 for Y-88 2734 keV.
- The close geometry (report only) shows the limit of first order: Cs-134 multi-coincidence lines
  are 7-9 % low and crossover lines 12-14 % high. Co-60 and Y-88 stay within 0.3 %.
- No criterion went from PASS to FAIL.

Not covered:

- X-ray - gamma and 511 keV summing.
- Angular correlation.
- Higher orders.
- A measured P/T. The P/T comes from the user.

The interface comes next.

## True-coincidence summing in the interface (2026-10-20)

The activity dialog has a checkable group "True-coincidence summing correction". It is off by
default; when it is ticked, the calculation applies `ActivityOptions.tcs`.

- The fields are the peak-to-total at 1 MeV (a), the slope b, and the uncertainty in %.
- The defaults are an example coaxial HPGe model, 0.24 / -0.63 / 10 %. An orange label says that
  they are assumed values, to be replaced by those of the detector and geometry.
- The tooltip explains the model and its limits: gamma-gamma only, no angular correlation, and
  first order in very close geometries.
- The values are remembered (`quant/tcs`). The tick is not remembered.
- The report's concentration notes state the correction with the assumed P/T.

## External review round 2: uncertainty and input fixes (2026-10-20)

Two external reviews (Codex and Gemini, commit c527f4e) found defects. This change fixes those
that concern the uncertainties and the input checks. Each one first got a test that failed
(`tests/test_uncertainty_fixes.py`).

- ISO 11929 detection limit. The fixed-point iteration stopped after 200 steps without
  converging as k u_rel(w) -> 1. For example, at u_rel = 0.607 it gave 31.4 instead of 120.0.
  It is now the closed-form root of the quadratic, and it is infinite when k u_rel >= 1.
- A net value of exactly zero gave u = NaN, because the relative counting uncertainty was
  infinite. Counting uncertainties are now carried in Bq (`LineResult.u_count_bq`).
- Reagent blank with a reference peak correction. The blank's own reference uncertainty was
  dropped, and the sample's u_rel(K) was applied to the net difference only. Now each spectrum's
  reference-peak counting is independent, and the expected rate is common to both
  (`QuantResults.reference_u_count_rel`, `reference_u_rate_rel`).
- Blank options that differ from the sample's are noted: attenuation, true-coincidence summing,
  reference peak, and background spectrum or mode.
- Unphysical input is refused with a clear message, instead of silently giving "no usable line"
  and MDA = 0. This covers a live time that is negative, NaN or infinite, a real time that is
  negative or NaN, and counts that are not finite. It applies to the sample, background,
  reference and calibration spectra (`efficiency.check_measurement`).
- QC statistics use `math.fsum`. A spread at the rounding level counts as zero, so identical
  readings no longer raise false Westgard alarms on Python versions without compensated `sum`.

The other review findings (true-coincidence summing safety, formats, fit windows, the interface
thread, traceability) follow in separate changes.

## True-coincidence summing safety (2026-10-20, from the second external review)

Both external reviews found that the TCS correction could go wrong outside its tested range.
Each case first got a test that failed (`tests/test_tcs_safety.py`).

- Double counting. An efficiency curve measured in the sample's geometry with cascade emitters
  already contains their summing losses. LN 881 is an example, with Ba-133 and Y-88. With the
  correction on, such points are now corrected with the same P/T and the curve is refitted
  (`efficiency.summing_free_curve`, `EfficiencyCurve.summing_corrected`). With a Co-60
  calibration this went from +3.1 % to 0.0 %. A curve that cannot be refitted (an Aptec model)
  is refused.
- Coincident photons more than 20 % below the curve's lowest energy are left out (eps = 0),
  instead of borrowing its lowest efficiency. U-235 185.7 keV went from COI 0.82 to about 0.98.
- A line that the coincidence table does not describe is not corrected, and the reason is
  noted. The test is an emission probability outside 0.75-1.33 times the library's. For example,
  Ir-192 484.6 keV had been matched to a 0.002 % neighbour.
- A first-order COI <= 0 gives no result for the line. A summing-out above 10 % is noted.
- The protocol's summing-in formula is corrected to divide by I_i eps_p(E_i), the formula the
  implementation already used (erratum in `tcs_protocol.md`).

## Format fidelity (2026-10-20, from the second external review)

Writing a spectrum to a format that cannot hold part of it now refuses or reports the loss,
never changes it silently. A round trip through every writable format checks each rule
(`tests/test_format_fidelity.py`), and the sets in `convert.py` are kept in step with it.

- Negative counts are refused by formats that only store non-negative channels. Before, CHN
  and CNF set them to 0. Such spectra come from background subtraction or Strip. The affected
  formats are CHN, SPC, CNF, Exploranium, NPL ASCII and SPC ASCII. The last of these was
  written but could not be read back.
- Fractional counts written to an integer format are rounded with a warning that gives the
  largest change.
- An unknown start time in a format that always stores a date is reported. CHN's placeholder
  (2000-01-01 00:00:00) now reads back as unknown, instead of a false date that a decay
  correction would use.
- Arabic-Indic digits in the sample ID and description are written as 0-9, with a warning.
  This covers the ASCII-only formats and the cp1256 formats (Aptec S0 and ASCII, IEC 1455 and
  others), which had turned them into '?'. Other characters a cp1256 format cannot hold are
  reported.
- Aptec S0 writes the channels below `first_channel` as zeros, as the Aptec ASCII writers do.
  Before, the energy calibration was shifted by the offset (50 keV in the test).
- Counts given as a numpy array no longer stop most writers. NaN or infinite counts are
  refused.
- A spectrum already stripped with Aptec's Strip is not background-subtracted again. When the
  channel contents are not Poisson counts (subtracted, stripped, normalized, smoothed), the
  activity results carry a note that their uncertainties, decision thresholds and MDA are not
  valid.

## Fit windows and width-shape extrapolation (2026-10-20, from the second external review)

Pre-registered in `docs/baseline/fit_window_protocol.md`, with the results there.

- For scintillators, the wide region used to measure the continuum curvature now stops
  2.5 FWHM short of neighbouring peaks. Before, in the NaI reference spectra, the region for the
  Co-60 group contained Cs-137, the curvature was always rejected, and Co-60 was fitted 3-4.5 %
  low. `NaI.ref.bias` went from -2.8 % to -0.7 %, and `NaI.ref.no_loss_bias` and
  `NaI.bkg_peak.net_bias` now pass as well.
- The HPGe width-shape correction is not extrapolated beyond the strong peaks used. Outside
  them the width ratio stays at its end value.
- No criterion went from PASS to FAIL, and 16 criteria fail.
  - `HPGe.tailed.false_increase` is now at its limit.
  - The NaI background-peak coverage is worse and is still open.

## Session traceability and the activity calculation thread (2026-10-20, from the second external review)

- The engine has its own version, `ENGINE_VERSION` = 1.1.0, separate from the application
  version. Before, it was tied to the application version, which never changed. The benchmark
  records it. A session computed with engine 1.0.0 is now reported as produced by an older
  engine.
- A session records the reagent blank file with its SHA-256 (`blank_ref`). When a TCS
  correction is used, it also records the coincidence table with its SHA-256
  (`coincidence_ref`). Both appear in the JSON report. Sessions saved before this still load.
- The reference date of the reference-peak correction is restored from a saved session as a
  date. Recalculating from restored options used to raise a `TypeError`.
- The activity dialog's Calculate button analyses the blank and the sample on a worker thread.
  The dialog shows "Calculating ..." and ignores a second click. A geometry mismatch is still
  asked about before the calculation is repeated. `calculate()` without `threaded` stays
  synchronous for scripts and tests.
- `multiprocessing.freeze_support()` was already called in the frozen entry points
  (`build_exe/*_entry.py`), so no change was needed.
- Still open:
  - Other long operations of the Aptec analysis window, the detector manager and file
    opening still run on the interface thread.
  - The user manuals still need the features of PR #17-#32. They follow in a separate change.

## User manuals updated (2026-10-21, from the second external review)

The Arabic and English manuals (`docs/tools/src/manual_*.html`, rebuilt into `docs/manual_*.html` and the PDFs) now
describe:

- the reagent blank, the reference peak correction and the true-coincidence summing correction (new sections 9.3-9.5,
  replacing "TCS is not corrected");
- sample information and concentrations in Bq/kg, Bq/L and Bq/m³ (9.6);
- detector profiles, peak-shape calibration and analysis sessions (6.6);
- the peak-fit changes (the HPGe width shape, the NaI log-quadratic continuum, the low-energy tail);
- the format rules from PR #31.

Still not documented: the remaining Release B dialogs (fit inspection and manual refit, review and the JSON report,
batch analysis) beyond their menu entries.

## Peak-by-peak background with unresolved background lines (2026-10-21)

Pre-registered in `docs/baseline/bkg_peak_protocol.md`, with the results there.

- **Cause.** In NaI, the background lines Bi-214 at 1120, 1238 and 1377 keV are not resolved from
  the Co-60 sample peaks. In peak mode they distorted the fitted Co-60 shapes, so 9 % of
  1173 keV was counted under 1332 keV, and K-40 was falsely detected in half the pairs.
- **Change.** Peak mode now fits the peaks on S - kB, the same fit as full-spectrum mode. The
  background under each line is still reported and enters the detection limits.
- **Results.** NaI.bkg_peak.cov1, cov2 and false_detect go from FAIL to PASS. No criterion went
  from PASS to FAIL, and 13 criteria fail.
- **Behaviour change.** A line present only in the background is reported as not found, with its
  background, instead of with a net area near zero.


## Long operations off the interface thread (2026-10-22)

Timed on 8192-channel HPGe spectra before the change (the operations below 0.3 s stay on the interface thread):

| operation | time | change |
|---|---|---|
| Aptec analysis window: peak search, multiplet fit, identify, quantify | 0.02-0.22 s each | none |
| opening a spectrum file | 0.01-0.12 s | none |
| detector manager: Measure peak shape (3 spectra) | 4.5 s | worker thread |
| report (Print, Print Preview, Export PDF) with "analyse first?" answered yes | 0.8-1.1 s, more on 16k spectra | worker thread |

- **Detector manager.** Measure peak shape reads the spectra and measures the shape on a worker
  thread. The dialog shows "Measuring the peak shape ..." and refuses a second start, and its
  buttons are disabled until the measurement ends. The confirmation and the saving follow on the
  interface thread. A file that cannot be read is reported as before.
- **Reports.** When a report command needs an analysis first, the menu commands start the same
  background analysis as Analyze. The command is repeated after the analysis thread has ended, so
  the busy cursor is gone before a save dialog opens. If the analysis fails, its error is shown and
  no report is written. A newer analysis replaces a waiting one.
- **Unchanged.** Direct calls without `threaded` (scripts, tests) stay synchronous.
- **Tests.** `test_gui_detector_context.py::test_peak_shape_button_measures_on_a_worker_thread` and
  `test_report.py::test_window_report_command_analyses_on_the_worker_thread`.
- **X-ray summing (F3) deferred.** In the IAEA 2002 data the efficiency curves start at 59.5 keV,
  so the K X-rays (Sm 39.5-46 keV in Eu-152, Cs 30.6-35.4 keV in Ba-133) lie below 0.8 x e_min and
  are left out by the existing rule. The expected effect is about 2-3 % on the EC lines and needs
  per-level K-capture fractions and K-shell conversion coefficients that are not in the
  downloaded data. It is worth doing only with a calibration below about 47 keV.


## External review round 3 (2026-10-21/22): record

Reviews: Codex 74, Gemini 90. Every High finding was checked on the code before a change; science
changes followed a pre-registered protocol in `docs/baseline/` (limits fixed before the run, results
below its line). The merged pull requests, with the registered result where there is one:

| PR | subject | result (outputs) |
|---|---|---|
| #36 | certified reference materials: first real-data concentration check | 6 PASS / 2 FAIL (defects D1, D2) |
| #37 | gamma-line library: wrong, duplicated and lost lines (D1, Ac-228 674.75 keV) | fixed |
| #38 | corrections used together: reference peak, background, blank, manual peaks | tests |
| #39 | manual refits of net spectra: variance and negative channels | tests |
| #40 | true-coincidence summing: daughters, calibration refit, curves without points | tests |
| #41 | spectrum writers: no silent change | tests |
| #42 | efficiency with a background on S - kB; non-Poisson spectra reported | tests |
| #43 | efficiency model error: outliers limited at 3 x the curve's scatter (D2) | tests |
| #44 | signed primary result for lines without a search peak (M2, H3b) | tests |
| #45 | interface: step through found peaks, coloured nuclide lines, maximize buttons | tests |
| #46 | IAEA 2002 test spectra: certified-activity check | 3 PASS / 4 FAIL as registered |
| #47 | 511 keV annihilation summing in TCS (F2) | 9 PASS / 0 FAIL (after_AN1, engine 1.8.0) |
| #48 | reading spectrum files with any extension | 5 PASS / 2 FAIL as registered (after_AX1) |
| #49 | quadratic continuum for curved NaI windows (item 6b) | 9 PASS / 4 FAIL as registered (after_WP1, engine 1.9.0) |
| #50 | deterministic benchmark report (ties in name order) | after_TO1 4 / 2, amendment after_TO2 5 / 0 |
| #51 | EML / IAEA ASCII .dat layout: time channels, one reader under any name | 5 PASS / 0 FAIL (after_ID1) |
| #52 | implausible FWHM model (F1): rescale to the strongest peaks, with a note | first rule after_FP1 3 / 5, not shipped; amendment after_FP2 8 / 1 (engine 1.10.0) |
| #53 | placeholder energy calibration E = channel read as uncalibrated | 6 PASS / 0 FAIL (after_PE1) |
| #54 | self-attenuation correction for sample density (F5) | 5 PASS / 1 FAIL as written (after_SA1, engine 1.11.0) |
| #55 | close-geometry efficiency curve with cascade emitters (F4) | 6 PASS / 0 FAIL (after_CG1, engine 1.12.0) |
| #56 | FWHM calibration from a source through measured line widths (MIX) | 6 PASS / 0 FAIL (after_MX1, engine 1.13.0) |
| #57, #59, #60, #65 | interface: maximize buttons and screen fit, close button fix, modal calibration and fit windows, widget attributes | tests |
| #58 | installer: SciPy license, unused large packages excluded | installer rebuilt 2026-10-22 |
| #61 | TCS coincidence table from ENSDF (LiveChart) instead of SandiaDecay (F3, part 1) | 7 PASS (after_CT1, engine 1.14.0); AN.C1 fails as written (Na-22 source difference) |
| #62, #64 | logo | - |
| #63 | long operations off the interface thread (section above) | tests |
| #66 | user manuals AR/EN: full rewrite for release 1.0.0 | - |
| #67 | laboratory HPGe spectra against GammaVision reports | 4 PASS / 2 FAIL (after_GV1) |

Deferred from this round: X-ray summing (F3, section above).


## Round-4 external review: activity findings R4-A (2026-10-23)

Reviews: Codex 78, Antigravity 82, Gemini 92 (Gemini reviewed 5945b16, before #67). Each finding was
checked on the code before any change; findings by batch: R4-A activity (here), R4-B identification,
R4-C formats, R4-D calibration and manual fit, R4-E interface thread, R4-F validation and documents.
Refuted: undo does restore the "peaks edited" status (`status_before`). Antigravity cites files that
do not exist (`gui/aptec_panel.py`, `gui/aptec_spectrum_view.py`, `tools/session_io.py`); its own
findings were not used.

Protocol `docs/baseline/round4_activity_protocol.md` (committed before the change), results in
`docs/baseline/after_R4A/`, engine 1.15.0:

- **Detection limit, blank with a reference peak (Codex H1).** The reference-peak variance has a
  term linear in the net activity, `2 A_b (u_s^2 + u_r (u_r - u_rb)) y`, now in the ISO 11929
  detection limit. Codex's case: 28.198 -> 31.466 Bq (Codex 31.461).
- **Summing of a self-attenuating sample (Gemini H3).** Computed with the sample's efficiency
  `eps / F_sa`; peak-to-total kept.
- **Concentration table (Gemini H2).** A nuclide not detected has its ISO 11929 best estimate and
  interval in Bq/kg, Bq/L and Bq/m3, as in Bq.
- **Without numerical criterion.** Removing every peak of a session is respected (Codex H2); a
  constant attenuation factor with the self-attenuation model is refused; the model refuses
  non-finite inputs and is described in the notes.
- **Kept.** The reagent blank is analysed with the sample's options, self-attenuation included.

## Round-4 external review: identification findings R4-B (2026-10-27)

Protocol `docs/baseline/round4_identify_protocol.md` (committed before the change), results in
`docs/baseline/after_R4B/`, engine 1.16.0:

- **Resolution model with a channel offset (Codex M2).** The identification evaluates the FWHM
  calibration at the absolute channel: Codex's case 2.0 -> 3.0 keV; a cropped spectrum has the same
  resolution model as the full one.
- **Half-life against the time since sampling (Codex 5.9, Gemini M3).** `identify(..., sampled=)`,
  CLI `identify --sampled`, GUI from the session's sample information: a nuclide decayed by more than
  10 half-lives gets a prior x 0.25 and a note; natural series and daughters of a parent still
  present are not affected. On 255 public CRM spectra with a date 30 days before the measurement:
  short-lived identifications 118 -> 0.
- **Medical nuclides (Gemini M3).** Mo-99, Tc-99m, F-18, Ga-67 ... common only with the medical
  library. CRM spectra without a date: medical identifications 41 -> 21.
- **Single matched line.** Note "one line matched ... confirm" when a nuclide with several lines is
  found from one.
- Benchmark 154 / 13 / 60 unchanged; IDB implausible identifications per spectrum slightly lower.

## Round-4 external review: format findings R4-C (2026-10-27)

Protocol `docs/baseline/round4_formats_protocol.md` (committed before the change), results in
`docs/baseline/after_R4C/`, engine 1.17.0. First run 2 PASS / 2 FAIL from two implementation errors
(disclosed in the protocol), corrected without changing limits: 4 PASS / 0 FAIL.

- **NaN or infinite counts (Codex M3).** Peak search refuses them with an error naming the channels
  (before: NaN returned no peaks silently); the GUI status bar and `info` give a note.
- **Sanderson time channels (Gemini M1).** Channels 0/1 are taken as live/real time only when
  channel 1 is 0 or between LT and 2 LT; otherwise they stay counts with a note. The 38 EML
  reference files read as before.
- **CHN with 1 keV per channel (Gemini M2).** The write check says that 0 + 1 keV per channel reads
  back as an uncalibrated MCA.
- **Detection (Codex M4).** SpecUtils TXT `.txt` is no longer read as two-column ASCII (live and
  real time kept); a TKA file with another extension is ambiguous (TKA / one-column ASCII) instead
  of one-column ASCII with the times as counts.
- Benchmark 154 / 13 / 60 unchanged.

## Round-4 external review: calibration and manual-fit findings R4-D (2026-10-27)

Protocol `docs/baseline/round4_calibration_protocol.md` (committed before the change), results in
`docs/baseline/after_R4D/`, engine 1.18.0, 4 PASS / 0 FAIL at the first run:

- **FWHM calibration in the calibration dialog (Gemini H4.1).** The measured width of every matched
  line is kept with the proposal; after an exclusion or an order change the dialog fits the FWHM
  calibration again through the widths of the lines still used (no peak refitted) and applies that one.
- **Positive, non-decreasing FWHM (Gemini H4.2).** Order 2 must also be positive over the whole
  spectrum, order 1 must not fall and must stay positive; otherwise no FWHM calibration, with a note
  (Gemini's doublet case: -25 keV at the end of the spectrum before). The 20 source calibrations of the
  IAEA 2002 and synthetic checks are unchanged.
- **Manual fit of a net spectrum (Codex M1, Gemini H1.2).** A spectrum carries its per-channel variance
  in memory, tied to its counts by SHA-256: background subtraction and the Aptec operations Strip,
  Combine, Normalize and Shift set or propagate it; the fit-inspection window passes it to refit, add
  and remove. Synthetic case: u 83.19 with the not-Poisson note -> 59.15, equal to the explicit S + k^2 B.
- Benchmark 154 / 13 / 60 unchanged.

## Round-4 external review: interface thread R4-E (2026-10-27)

Timed before the change (Codex M6, Gemini H5):

| operation | time | change |
|---|---|---|
| searching a folder for spectra (drop on the main window, Batch Analysis > Add Folder, Print Reports for Multiple Files > Add Folder): lab archive, 18394 files with spectrum extensions | 0.8 s | worker thread |
| the same, a mixed folder of 6240 files (content of every file of unknown extension read) | 80.9 s | worker thread |
| Activity dialog: measure the reference peak (read the spectrum and fit the peak) | 0.08 s for 1024 channels, plus the file reading | worker thread |
| Aptec analysis window operations | 0.02-0.22 s each (2026-10-22) | none, as before |

- The main window shows "Looking for spectra in the folder..." in the status bar and opens the batch
  window when the search ends; files dropped alone open at once, as before.
- Batch Analysis and Print Reports for Multiple Files disable their add and start buttons during the
  search and refuse a second one.
- The reference-peak measurement disables Measure and Calculate until it ends; an unreadable file or a
  missing peak is reported as before.
- No change to the analysis engine (engine 1.18.0). Tests `tests/test_round4_ui_thread.py`.


## Round-4 external review: validation and documentation R4-F (2026-10-27)

Protocol `docs/baseline/round4_validation_protocol.md` (registered before the run).

- **Monte Carlo check of the coincidence table, both directions (Codex).** The check compared only
  P(j | i) down the cascade. It now also compares the upward P(i | j) = I_i P(j | i) / I_j and the
  two-way probability `Transition.coincident` that the correction uses
  (`coincidence_ensdf_check --r4f`). Results are in `docs/baseline/after_R4F/`.
- **Wording of the coincidence protocol (Gemini).** A dated correction is appended to
  `ensdf_coincidence_protocol.md`. "Every transition checked" meant only the 18 nuclides of the Monte
  Carlo.
- **Round-3 record.** The section above lists PRs #36-#67.
- No change to the analysis engine or the coincidence table (engine 1.18.0).
- **Result: 2 PASS / 2 FAIL as registered.** The downward rows are unchanged. Upward and two-way rows: 13 outside the limit, from ENSDF levels whose intensity balance does not close (Ac-228 968.3 and 938.6 keV levels, Co-57 14.4 keV). Effect on the correction: at most about 1.4 % on the weak Ac-228 270/328 keV lines in a close geometry. Left for its own protocol.

## Round-4 external review: primary result of nuclides not detected, Gemini H2 (2026-10-27)

Protocol `docs/baseline/round4_primary_protocol.md` (registered before the change); engine 1.19.0.

- **Part 1** (`concentrations()` without the ISO 11929 best estimate) was fixed in R4-A.
- **Part 2, confirmed.** For a nuclide without an activity, the signed primary result came from the
  key line only, so with "weighted mean of lines" the other lines were ignored. A flagged key line
  (interfered or curved) left the nuclide without a best estimate even when another line had a
  usable window result. It is now combined like the activity: the key line, or the weighted mean of
  the usable lines. A flagged key line is replaced by the usable line with the smallest MDA, named in
  the nuclide's note. The activity, the decision, the decision threshold and the MDA are unchanged.
- **Part 3, not confirmed.** `_quad_result()` subtracts a background **peak area** or the background
  spectrum's own window, never a linear sample continuum. The unit detail found (a full peak area
  against a window holding 99.7 % of a peak) is at most 0.3 % of the background term and is left as
  it is.
- **Result:** first run 1 PASS / 1 FAIL from a harness error (RH.C1 also counted 3 nuclides that had
  an activity); corrected run 3 PASS / 0 FAIL (`after_R4H`). Ba-133, weighted mean: 197/197
  combinations exact, mean z 0.091, coverage 0.985. Cs-134 with the key line interfered: 99/99 now
  from the 795.9 keV line, mean z -0.117, coverage 0.970 (before: 99 "interfered", no best estimate).
  The signed-primary harness and the benchmark are unchanged.
- Manuals AR/EN: the primary result row says how lines are combined.

## Detector acceptance test, chi-square counting test and activity units (2026-10-27)

Protocols `docs/baseline/detector_acceptance_protocol.md` and
`detector_acceptance_amendment_protocol.md` (both registered before the change); engine 1.20.0.

- **Acceptance test** (`analysis/detector_test.py`, Tools > Detector Acceptance Test...): FWHM, FWTM
  and FWTM/FWHM of the Co-60 1332.5 keV peak (and of Co-57 122 keV when a spectrum is given),
  peak-to-Compton (1040-1096 keV), and the relative efficiency against the 3x3 inch NaI value 1.2e-3
  at 25 cm, with decay correction and its uncertainty. The standard geometry is stated, not checked.
- **Chi-square counting test** (Tools > Chi-Square Counting Test...): chi^2 of repeated counts with the
  5 % and 95 % points (TECDOC-1599).
- **Result:** first run 5 PASS / 2 FAIL (`after_DA1`: FWTM +5.7 % by linear interpolation at 3.6
  channels per FWHM). Amendment 1 measures the crossings by a parabola through the logarithms of three
  channels: 7 PASS / 0 FAIL and DA.C8 PASS (`after_DA2`). Full suite 1479 passed, 69 skipped, 1 failed on the first run: the dialogs' attribute `result` hid `QDialog.result()` (`tests/test_widget_attribute_shadowing.py`); renamed `outcome`, that test and the dialog tests then passed (1480 passed in all); benchmark 154 PASS /
  13 FAIL unchanged.
- **Activity units.** Source activities can be entered and shown in Bq, kBq, MBq, GBq, TBq, Ci, mCi,
  µCi, nCi or pCi (acceptance dialog, efficiency certificate table, QC reference activity, e.g.
  `Cs-137=1 µCi`). Values are kept in Bq; the conversion factors are those of the decay calculator.
- Manuals AR/EN: sections 12.5 and 12.6, the Tools table, the certificate unit and the QC unit hint.
- Limitations: synthetic spectra only; no laboratory Co-60 spectrum at 25 cm with a known activity.

## Coincidence table: ENSDF levels whose intensity balance does not close (2026-10-27)

Protocol `docs/baseline/ensdf_level_balance_protocol.md` (registered before the change); engine 1.21.0.

- **Problem (from R4-F).** The upward probability P(i | j) = I_i P(j | i) / I_j used the tabulated
  intensities. At levels that receive more gamma transitions than they emit, it came out too large:
  13 upward rows failed the Monte Carlo check, and Co-57 122.1 given 14.4 keV was 1.018.
- **Change.** The builder computes level populations from the direct feeding max(0, out - in) and
  the gamma inflow, and stores the scheme intensities (`gs`) for 98 records. The correction uses them
  for the upward direction only. The downward probabilities, the annihilation probabilities, the line
  matching and the summing-in term are unchanged.
- **Result: 6 PASS / 0 FAIL.** Upward 215/215 and two-way 448/448 now agree with the simulation
  (before 13 and 13 failed); no upward probability above 1. Benchmark: 154 PASS / 13 FAIL / 60 REPORT, no criterion changed state against after_DA2; IAEA 2002 states
  unchanged. Full suite: 1483 passed, 69 skipped.
- **Effect.** At eps_peak(1000 keV) = 0.05, lines with COI of at least 0.8: at most 2 % (Th-227
  93.9 keV); Ac-228 270/328 keV +0.8 %.
- **Limitation.** The rule follows the scheme. In Ac-228 the 938.6 and 968.3 keV levels receive 25 and
  10 times what they emit, more likely a misplaced gamma in the data. The lines affected are weak
  (at most 0.15 %).
- Manuals AR/EN: the coincidence data paragraph and appendix E.

## Round-5 external review: worker threads outliving their dialog, C1 (2026-10-28)

Codex round 5 (75/100). No change to the analysis engine (engine 1.21.0).

- **Confirmed.** A dialog deleted on close (Reports > several spectra) owned the QThread of its
  `start_call`. Closing it during a folder scan deleted a running thread, and the process ended
  ("QThread: Destroyed while thread is still running"; exit code 3221226505, reproduced).
- **Fix.** `gui/worker.start_call` gives the thread to the application instead of the dialog. The
  dialog's callbacks are disconnected with it, so the result is dropped. The application waits for
  running calls when it quits. `running_calls()` counts them. The dialogs that run their own
  QThread already wait in `closeEvent`.
- **Tests:** `tests/test_round5_worker_lifetime.py` (in a separate process): closing the owner during
  the call does not end the process and drops the result; with the owner open, the result arrives.

## Round-5 external review: detector acceptance test and activity entry, H2 H3 M1 M2 M3 (2026-10-28)

Protocol `docs/baseline/round5_acceptance_protocol.md` (registered before the change); engine 1.22.0.

- **H2, confirmed.** The acceptance test evaluated the energy at the ROI's local channel: with
  `first_channel` != 0 the centroid was wrong (832.5 instead of 1332.5 keV) and, with a non-linear
  calibration, the widths too. It now uses the absolute channel.
- **M3.** Peak-to-Compton only when the spectrum covers the whole 1040-1096 keV window, else a note.
- **H3.** QC reference activity: `Cs-137=1,000 Bq` gave 1 Bq. Records are now split at `;`, a new
  line, or a comma before the next `nuclide=`; a record that cannot be read is an error, not dropped.
- **M2.** A comma inside a number and a value that is not finite are refused; the relative efficiency
  checks the activity and the live time.
- **M1.** The certificate table keeps each activity in Bq, so a unit change no longer rounds it to 6
  digits.
- **Result:** first run 4 PASS / 2 FAIL from a harness error (peak at 1332.492 instead of the
  protocol's 1332.5 keV); corrected run 6 PASS / 0 FAIL and RB.C7 PASS (`after_R5B`). Benchmark
  154 / 13 unchanged; full suite 1490 passed, 69 skipped.

## Round-5 external review: limits of the weighted mean of lines, H1 (2026-10-28)

Protocol `docs/baseline/round5_combined_protocol.md` (registered before the change); engine 1.23.0.

- **H1, confirmed.** With the "mean" method the decision threshold was that of an inverse-variance
  mean with the zero-activity weights, not of the reported mean (0.218 instead of 0.299 Bq in the
  harness case; false positives 11.6 % instead of 5 %), and the MDA was the smallest line MDA.
  Both are now computed for the reported weighted mean with its own weights (`combined_limits`).
  Activities, uncertainties and the key-line method are unchanged.
- **Result:** 6 PASS / 0 FAIL at the first run (`after_R5C`); benchmark 154 / 13 unchanged; full
  suite 1497 passed, 69 skipped.
- **Remaining:** the weights depend on the observed activities and the lines are selected after
  detection; neither is propagated into the limits (stated in the protocol).

## Round-5 external review: a TKA file named .txt, H4 (2026-10-28)

Protocol `docs/baseline/round5_tka_protocol.md` (registered before the change); engine unchanged.

- **H4, confirmed.** A TKA file named `.txt` was read as one-column ASCII by the usual `.txt` test
  (1026 channels instead of 1024, the two times counted, live and real time lost), without a note.
  When the usual test chose ASCII-1 and the TKA content test also matches, the file is now ambiguous
  and the input format must be chosen.
- **Result:** 6 PASS / 0 FAIL at the first run (`after_R5D`); 190 `.txt` and 319 control files
  unchanged; benchmark 154 / 13 unchanged; full suite 1499 passed, 69 skipped.

## Round-5 external review: partial true-coincidence summing corrections, H5/H6 (2026-10-28)

Protocol `docs/baseline/round5_tcs_protocol.md` (registered before the change, two amendments
registered after failed runs); engine 1.24.0.

- **H5, confirmed.** Partners below the efficiency curve were left out without the correction being
  marked incomplete; a calibration with such points was labelled summing-corrected.
- **H6, confirmed.** Where the scheme intensities differ from the line intensities, the upward
  coincidence probabilities depend on the set used (Ac-228 880.76 keV: summing-out 10 % apart).
- **Change.** A partial state (`Coi.partial_reason`, `LineResult.coi_partial`): partners below the
  curve above 1 % of decays, or a summing-out that changes by 1 % or more between the intensity
  sets. Lines and nuclides name it; a calibration corrected with such points names them in its note
  and warnings. No factor or activity changes.
- **Result:** first rule 3 / 2 and amendment 5 / 1 (not shipped); second amendment 6 / 0
  (`after_R5E3`); benchmark 154 / 13 unchanged; IAEA 2002 check unchanged; full suite 1506 passed,
  69 skipped.
- **Remaining:** the missing loss of a partial correction is not estimated; X-ray coincidences are
  not in the table.

## Round-5 external review: full-precision proof of the round-4 activity criteria, M4 (2026-10-28)

Protocol `docs/baseline/round5_precision_protocol.md` (registered before the change); engine unchanged.

- **M4, confirmed.** The round-4 activity harness compared with values printed to 6-7 digits
  (relative 1e-6) where the protocol registered 1e-9.
- **Change.** The R4-A harness was run unchanged on engines 1.14.0 (a8d5346) and 1.15.0 (c892145);
  both runs are committed (`after_R5F`). `round4_activity` now compares with the 1.14.0 values at
  the registered limits.
- **Result:** 5 PASS / 0 FAIL; the 12 values are identical in every digit on 1.14.0, 1.15.0 and
  1.24.0; full suite 1508 passed, 69 skipped. Round-5 batches R5-A to R5-F are done.


## Round-6 external review: quitting while a worker runs, C1 (2026-10-28)

Codex round 6 (76/100), Gemini round 6 (88/100). No change to the analysis engine (engine 1.24.0).

- **Confirmed.** Every worker thread was stopped by its worker's "finished" signal through a queued
  call to `QThread.quit`, which runs in the GUI thread. When the application quit, the GUI thread
  was blocked in `_wait_all` (and a closing window in its `wait()`), so the quit never arrived: the
  wait timed out after 30 s and the running QThread was then destroyed (exit code 3221226505,
  reproduced by the new test before the fix in all three cases). The same pattern was in the
  analysis thread and in the conversion, batch-analysis, report and QC import windows.
- **Fix.** `gui/worker.quit_on` connects the worker's signals to `QThread.quit` directly (in the
  worker's thread; `quit` is thread-safe), used by `start_call` and by every window that runs its
  own QThread. On quit and on close the threads are waited for until they end (no timeout): a
  running thread is never destroyed.
- **Tests:** `tests/test_round6_quit.py`: the application quits 100 ms after a call of 1 s or 3 s
  starts (also with its window closed and deleted) and ends with exit code 0, nothing left running;
  `quit_on` stops a thread while the GUI thread is blocked in `wait()`. Full suite 1512 passed,
  69 skipped.


## Round-6 external review: Laval and Wallac files named .txt, H2 (2026-10-28)

Protocol `docs/baseline/round6_laval_wallac_protocol.md`, committed before the change (089e337).
No change to the analysis engine (engine 1.24.0).

- **Confirmed.** A Laval or Wallac file named `.txt` was read as one-column ASCII without a note:
  Laval 1023 channels, sum 496726.5 (header lines counted), no times or calibration; Wallac 1025
  channels, no time.
- **Fix.** `USUAL_AMBIGUOUS` also holds ASCII-1/Laval and ASCII-1/Wallac: such a file is ambiguous
  and the input format is chosen; read as chosen it is identical to its reading under its own
  extension. Price: a one-column `.txt` with a six-digit 4th count or exactly 1027 counts also
  becomes ambiguous (as ASCII-1 it reads as before); none among the files at hand.
- **Result (`after_R6B`):** 6 PASS / 0 FAIL at the first run, laboratory `.txt` files unchanged
  (counts only); benchmark 154 / 13 / 60 unchanged against `after_R5E3`; full suite 1515 passed,
  69 skipped. Manual sources: the Laval/Wallac case added to reading by content.


## Round-6 external review: input validation, Codex H2 / M1, Gemini H1 / M2 (2026-10-28)

Protocol `docs/baseline/round6_inputs_protocol.md`, committed before the change (2f14de2).
No change to the analysis engine for valid inputs (engine 1.24.0).

- **Confirmed.** Certificate table: after an edited activity a unit change brought back the old
  absolute uncertainty (2000 +- 40 became 2000 +- 20). The table, the certificate CSV and
  `measure_efficiency` accepted infinite, NaN, negative or zero activities, uncertainties,
  half-lives and intensities (NaN efficiency points used); `1,000` was read as 1. The detector test
  (`net_area`, `peak_to_compton`, `relative_efficiency`) did not check the counts. The chi-square
  input turned `1,5` into 15; the QC reference activity accepted -1000 Bq; `set_bq(inf)` was kept.
- **Fix.** The uncertainty of each row is kept across a unit change; invalid cells, CSV rows and
  certificate lines raise an error naming the row (or nuclide and energy); a comma in a number is
  refused, as in round 5; the detector test refuses non-finite counts; QC activities must be above 0
  and names are stored in the library spelling (`Cs137` -> `Cs-137`).
- **Result (`after_R6C`):** first run 5 PASS / 3 FAIL from a harness error (tuples compared with
  JSON lists; values equal), kept as `round6_inputs_run1.md`; second run 8 PASS / 0 FAIL. Benchmark
  154 / 13 / 60 unchanged against `after_R6B`; full suite 1568 passed, 69 skipped. A manual
  efficiency point typed with a decimal comma is no longer read (keeps its values).


## Round-6 external review: combined limits with a blank and a reference peak, Codex H1 (2026-10-28)

Protocol `docs/baseline/round6_combined_protocol.md`, committed before the change (43810f8).
Engine 1.25.0.

- **Confirmed.** The weighted mean's decision threshold and detection limit (`combined_limits`,
  round 5) assumed independent lines. With a reagent blank and a reference peak correction, the
  corrections shared by the lines make them covary at zero net activity (Ab_i Ab_j times the
  reference variances) and in the term linear in y. Co-60, blank 50 Bq per line, reference peaks to
  10 %: threshold 8.26 instead of 11.66 Bq, detection limit 18.40 instead of 26.80 Bq, false-positive
  rate 12.2 % instead of 5 %.
- **Fix.** Each line with a blank records its reference-peak part over the shared variables
  (`ref_g0`, `ref_dg`); `combined_limits` adds their cross terms. Without a blank nothing changes.
- **Result (`after_R6D`):** 6 PASS / 0 FAIL at the first run (false-positive rates 4.99 %); benchmark
  154 / 13 / 60 unchanged against `after_R6C`; full suite 1573 passed, 69 skipped.


## Round-6 external review: partial summing correction state of the efficiency curve, Codex H3 and L1 (2026-10-29)

Protocol `docs/baseline/round6_tcs_state_protocol.md`, committed before the change (fb3f5c8).
Engine 1.26.0.

- **Confirmed.** The partial true-coincidence summing correction of calibration points was only text in
  the curve's note and warnings: a corrected curve saved and loaded again gave results whose notes did
  not mention it, and the report's calibration summary carried neither note nor warnings (Eu/Ba curve
  from 121.8 keV, four Ba-133 points). The partial reason called an expected number of partner photons
  per emission a "% of decays" (L1).
- **Fix.** `EfficiencyCurve.tcs_partial` ([nuclide, keV, reason]) saved with the curve (recovered from
  the text of older files); the results gain `curve_tcs_partial`, one note and a note per nuclide; the
  report gains the list, note and warnings; the review one warning. Wording "on average x per emission
  of this line". No number changes.
- **Result (`after_R6E`):** 6 PASS / 0 FAIL at the first run; benchmark 154 / 13 / 60 unchanged against
  `after_R6D`; full suite 1577 passed, 69 skipped.


## Round-6 external review: folder searches and QC exports off the GUI thread, Gemini M1 (2026-10-29)

No science change (engine 1.26.0 kept), so no protocol.

- **Confirmed.** `ReportBatchDialog.is_running` ignored a running folder search (Esc closed the dialog
  during it); the folder search of *Convert Folder...* (`BatchDialog.scan`) and the QC window's PDF /
  Excel exports ran on the GUI thread.
- **Fix.** The report dialog counts a search as running and waits for it on close; `BatchDialog.scan`
  runs on `start_call` (a change made meanwhile searches again at the end; closing waits, without the
  cancel question); the QC exports run on `start_call` from copies of the track and its evaluation,
  errors in a message box.
- **Tests.** New `tests/test_round6_threads.py`; two existing tests now wait for the background work
  (`test_folder_dialog_recursive_keep_tree`, `test_qc_window_offscreen_and_exports`: the search and the
  exports are no longer synchronous). Full suite 1579 passed, 69 skipped, 1 failed:
  `test_timing_16k_channels` over its 1 s bound on a busy machine (code not touched); passed 3 of 3 runs
  alone.


## Round-6 external review: channel binning bias of the acceptance test widths, Gemini M3 (2026-10-29)

Protocol `docs/baseline/round6_fwhm_protocol.md`, committed before the change (f16f812).
Engine 1.26.0 (unchanged).

- **Confirmed, and larger than reported.** The FWHM and FWTM of the detector acceptance test, from the
  channel contents, overestimate a narrow Gaussian: +1.45 % at 4 channels per FWHM when the centroid is
  on a channel (Gemini), but +4.49 % when it is between two (+7.87 % at 3 channels, +2.0 % at 6).
- **Decision: noted, not corrected.** `PeakWidth.fwhm_bin_bias` / `fwtm_bin_bias` give the range (centroid
  on a channel to between two), from the Gaussian whose binned width is the measured one; the note
  states it when the upper FWHM value reaches 1 %. The manuals no longer call the method exact.
- **Result (`after_R6G`):** 5 PASS / 0 FAIL at the first run; benchmark 154 / 13 / 60 unchanged against
  `after_R6E`; full suite 1583 passed, 69 skipped; one existing test changed (an 8-channel peak now
  carries the note).

## Round-6 external review: test suite portability and the chi-square input format, Gemini L1 / L3 (2026-10-29)

No program change (engine 1.26.0 kept), so no protocol.

- **Confirmed.** Run with SpecUtils and PySide6 made unimportable (pytest-qt disabled, as in a stripped
  environment), the suite had one collection error (`test_open_dialog_size.py` imported PySide6 before
  its `importorskip`) and 25 failures instead of skips: 24 tests that read or write a format of the
  SpecUtils bridge without `importorskip("SpecUtils")` (Gemini counted 15; the others need optional data
  as well), and `test_gui_import_failure_is_graceful`, which assumed PySide6 present (without it `main()`
  prints the help and returns 0 before the failing import).
- **Fix.** `importorskip("PySide6")` before the Qt imports; `importorskip("SpecUtils")` in the 24 tests
  (in `test_refit_keeps_energies_close` only for the formats SpecUtils registers); the GUI test mocks
  `gui_available`.
- **L3.** Section 12.6 of the manual sources already states the counts format (point for decimals, no
  thousands separator) since R6-C, and 12.5 the binning overestimate since R6-G; the built manuals are
  regenerated with the final manuals step.
- **Result.** Stripped environment: 920 passed, 365 skipped, 0 failed (before: 1 collection error, 25
  failed). Full environment, the 15 changed files: 380 passed, 1 skipped.

## Round-7 external review: summing state of an efficiency curve kept through a refit, H1 (2026-10-29)

Protocol `docs/baseline/round7_tcs_refit_protocol.md`, committed before the change (e93d747).
Engine 1.27.0.

- **Confirmed (Codex and Gemini H1).** `fit_efficiency` always returned an uncorrected curve: a
  corrected curve refitted from its own points (the efficiency dialog's *Refit* after loading it) lost
  `summing_corrected` and `tcs_partial` while its points stayed corrected. Without the sample's summing
  correction the partial warning disappeared; with it the points were corrected twice (Cs-137
  67.8844 -> 69.0339 Bq, +1.69 %).
- **Fix.** Each corrected point keeps its COI and partial reason (`EfficiencyPoint.summing_coi`,
  `summing_partial`); `fit_efficiency` derives the curve's state from its points and refuses corrected
  and uncorrected cascade points together. Point fields are saved only when set; curves saved by 1.26.0
  get them on loading from the point notes. `summing_free_curve` leaves `tcs_partial` and its warnings
  to the fit.
- **Result (`after_R7A`):** 6 PASS / 0 FAIL at the first run; benchmark 154 / 13 / 60 unchanged against
  `after_R6G`; full suite 1588 passed, 69 skipped, exit 0. A harness comparison including the fit time
  was corrected before the protocol commit (disclosed).

## Round-7 external review: limits of the weighted mean, Codex H2 and Gemini M1 (2026-10-29)

Protocol `docs/baseline/round7_combined_protocol.md`, committed before the change (8c6b8dd).
Engine 1.28.0.

- **Confirmed (Codex H2).** With a reference peak correction, the cross terms of the shared reference
  peak were added only between lines that both had a blank peak; a line without one lost the linear
  term of the other (Co-60, blank peak at 1173 keV only, ISO 11929: detection limit 6.5 % low).
- **Confirmed (Gemini M1).** An undetected nuclide with `method = "mean"` reported the weighted mean of
  its window results as primary result but the decision threshold and MDA of the key line alone.
- **Rejected (Gemini L1).** The quoted `math.copysign` expression is not in the code.
- **Fix.** A line with a reference peak correction and no blank peak carries g0 = 0 and its dg, so
  every pair of such lines gets its cross terms. An undetected nuclide with `method = "mean"` and more
  than one usable line reports the limits of the weighted mean with the weights of `primary`, and a
  note when `primary` exceeds that threshold; the detection decision is unchanged.
- **Result (`after_R7B`):** first run 4 PASS / 1 FAIL from a harness comparison of internal line
  fields set by design (kept, disclosed); corrected comparison 5 PASS / 0 FAIL; benchmark 154 / 13 / 60
  unchanged against `after_R7A`; one existing test changed (`test_no_blank_no_cross_terms`, ref_g0 now
  (0, 0, 0) without a blank).

## Round-7 external review: background spectrum shared by the sample and its reagent blank, Gemini H2 (2026-10-29)

Protocol `docs/baseline/round7_shared_background_protocol.md`, committed before the change (512fdf0).
Engine 1.29.0.

- **Confirmed (Gemini H2).** Sample and blank analysed with the same background spectrum: the
  covariance of their background estimates was left out, so u_count, the threshold and the limit were
  too large (Monte Carlo: uncertainty 1.45 x the scatter at net zero, 1.5 % detected against 5 %).
- **Found while measuring.** The sample's counting of the blank level was missing from sigma0 (8.75 %
  detected against 5 % without a background spectrum; not conservative).
- **Fix.** The background estimators return their coefficients on the background channels; with the
  blank's results from the same session and the same background, C = k_d sum r_i g_i B_i is taken twice
  off u_count^2 and sigma0^2 (new field `blank_bkg_cov`), otherwise counted as independent with a note;
  sigma0^2 gets max(A_b', 0) f_w / w.
- **Result (`after_R7C`):** 4 PASS / 1 FAIL as written (RC.C2: ratio 1.163 against 1.12, from the
  existing fit-uncertainty overestimate at low net counts; false detection now within limits);
  benchmark 154 / 13 / 60 unchanged against `after_R7B`; round-4/5 blank-case regression values updated
  (`round4_activity.AFTER_R7C`).

## Round-7 external review: limits of the quadratic window, Gemini H3 (2026-10-29)

Protocol `docs/baseline/round7_quad_limits_protocol.md`, committed before the change (f57e493).
Engine 1.30.0.

- **Confirmed (Gemini H3).** A line on the quadratic window decided detection with its own threshold
  but reported the linear threshold and MDA, inherited by its nuclide (NaI Cs-137: threshold 0.88 x
  k sigma, 6.2 % of null results above it).
- **Fix.** Such a line reports the quadratic window's L_C, L_D, threshold and MDA; the nuclide (key
  line or weighted mean) inherits them.
- **Result (`after_R7D`):** 5 PASS / 0 FAIL (threshold 1.02 x k sigma, 4.1 % above it); benchmark
  154 / 13 / 60 unchanged against `after_R7C`; three `test_window_polynomial.py` tests changed.

## Round-7 external review: input validation, Codex M1 and Gemini M4 (2026-10-29)

Protocol `docs/baseline/round7_inputs_protocol.md`, committed before the change (5bf16c1).

- **Confirmed.** Invalid manual efficiency cells were ignored silently (the fit and the save used the
  old value while the cell showed the new text); QC lines accepted inf / nan / negative values and
  split a decimal comma into two lines; the certificate CSV ignored later rows' activity, date and
  half-life, gave a zero uncertainty for an unknown column, accepted intensities above 100 %; Aptec
  source records were not checked for finite values; `set_bq` accepted a negative activity.
- **Fix.** Each is refused with a message naming the row / value; an invalid manual cell clears the
  curve until corrected; valid inputs give the same results.
- **Result (`after_R7E`):** runs 1 and 2 4 PASS / 1 FAIL from two harness comparison errors (kept,
  disclosed), run 3 5 PASS / 0 FAIL; benchmark unchanged; suite 1638 passed (one run exited 127 after
  passing, not reproduced; Codex M2, R7-G).

## Round-7 external review: warnings and threads, Gemini M2 and M3 (2026-10-29)

GUI / warning batch, no number changes (no protocol, as R6-F). Engine unchanged.

- **Confirmed (Gemini M2).** A partial true-coincidence summing correction of the efficiency curve was
  named only in the review; the concentrations, the report's calibration record (when the curve was
  corrected in the activity calculation), the activity window's warning line and the Arabic status
  text left it out or showed it in English.
- **Confirmed (Gemini M3).** The QC window closed without waiting for its PDF / Excel export threads;
  folder searches (batch conversion, batch reports, batch analysis, dropped folders) could not be
  stopped, so closing a window during a large search waited for its end.
- **Fix.** The partial points are named in all four places (Arabic and English); the QC window waits
  for its exports; a folder search is cancelled when its window closes, without a message.
- **Result (`after_R7F`):** benchmark 154 / 13 / 60 unchanged against `after_R7E`; 10 new tests
  (`tests/test_round7_warnings_threads.py`), all failing on the old code; no existing test changed.

## Round-7 external review: tests and harnesses, Codex M2 / L1 and Gemini L3 (2026-10-29)

Protocol `docs/baseline/round7_tests_protocol.md`, committed before the change (85e589d).

- **Confirmed.** The Qt test process ended with 0xC0000409 after every test had passed (a batch
  conversion dialog left open by the tests, destroyed during the interpreter's teardown; the object
  inside it not identified; the application's own exit clean); `round6_inputs` RC.C5 failed on a
  re-run because it compared the width note added by R6-G as a measurement, and a re-run wrote over
  `after_R6C`; two parser tests created a QApplication they do not need.
- **Fix.** The session closes and deletes the widgets left open; RC.C5 compares the numbers exactly
  and the note apart, `--out` for re-runs; the parser tests need PySide6 only.
- **Result (`after_R7G`):** 5 PASS / 0 FAIL (abnormal ends 2 of 20 -> 0 of 20); benchmark unchanged;
  suite 1652 passed, exit 0. Round 7 complete.

## Round-8 external review: limits of a replacing line, Codex H1 / Gemini H1 (2026-10-30)

Protocol `docs/baseline/round8_alt_limits_protocol.md`, committed before the change (09f3471).

- **Confirmed.** A nuclide not detected whose key line has no usable window result takes its primary
  result from another usable line, but kept the key line's decision threshold and MDA (2.876 / 5.882
  Bq instead of the used line's 1.703 / 3.553 Bq in the HPGe case). A "curved" primary result was
  shown without the "not used" mark that an interfered one has. Gemini H1 part a (no usable line: the
  key line's marked result) is the registered rule and was not changed.
- **Fix.** The nuclide reports the replacing line's threshold and MDA (and the specific MDA), named in
  the note; "curved" is marked in Arabic and English. ENGINE_VERSION 1.31.0.
- **Result (`after_R8A`):** 6 PASS / 0 FAIL; benchmark 154 / 13 / 60 unchanged against `after_R7G`;
  suite 1659 passed, exit 0; 7 new tests, no existing test changed.

### 2026-10-30 Round-8 review, Gemini H2 (R8-B): peak-mode limits of a line without a sample peak

- Protocol `docs/baseline/round8_peak_mode_protocol.md` (14f3437) and amendment
  `round8_peak_mode_amendment_protocol.md` (5e897d0). In the peak background mode a line without a
  sample peak took the background term of its decision threshold from the background fitter's
  full-peak area (`BackgroundFitter.at_energy`), while its primary result subtracts the window
  estimator on the background counts. Now sigma0^2 = B (1 + n/2m) + k max(N_w, 0) + k^2 V_w with the
  window estimator of the background (quadratic window: its quadratic counterpart), and the blank
  covariance uses the window coefficients.
- `after_R8B` 3 PASS / 1 FAIL (RB8.C3 drafting error: the curved line follows the change);
  `after_R8B2` 4 PASS / 0 FAIL. Benchmark 154 / 13 / 60 unchanged. ENGINE_VERSION 1.32.0.
- Same day, by subagents: R8-F scan cancel (#101), R8-E inputs (#102), R8-D truncated SPE (#103).

### 2026-10-30 Round-8 review, Gemini M1 (R8-C): summing-corrected points not corrected twice

- Protocol `docs/baseline/round8_coi_guard_protocol.md` (4435773). Cascade points corrected for
  true-coincidence summing, excluded, the curve refitted (not marked corrected), then included again
  without a refit were divided by their COI a second time by `summing_free_curve` (Eu-152 121.78 keV
  +8.06 %). Now such a curve is refitted on its points as they are and marked corrected; a mix with
  uncorrected cascade points is refused.
- `after_R8C` 4 PASS / 0 FAIL after two disclosed harness errors (missing empty `tcs_partial`; the
  fit time compared). Benchmark 154 / 13 / 60 unchanged; suite 1748 passed. ENGINE_VERSION 1.33.0.

### 2026-10-30 Round-8 review, Codex M6 / Gemini M2 (R8-G): re-runs of the round-7 harnesses

- Protocol `docs/baseline/round8_rerun_protocol.md` (d2f9ce4). The five round-7 harnesses gain
  `--rerun` (results to a fixed temporary folder, the committed `after_R7x` left as they are);
  `validation/round8_rerun.py` runs each at its merge commit (temporary worktree) and on the current
  code, and assigns every changed criterion state to the first later merge commit that changes it.
- `after_R8G` 4 PASS / 0 FAIL: committed files unchanged; historical states as committed; on the
  current code RB.C2 and RB.C5 of round7_combined fail from 3cd2aa7 (R7-C, #95), the intended
  change 3 of round7_shared_background_protocol.md (the sample counts the blank level). Benchmark
  154 / 13 / 60 unchanged; suite 1752 passed. No analysis change; ENGINE_VERSION unchanged.

### 2026-10-30 Round-8 review, Gemini M3 (R8-H): covariance of a nuclide's window results

- Protocol `docs/baseline/round8_line_covariance_protocol.md` (7208d2c, before values 2 PASS / 3 FAIL).
  The weighted mean of a not-detected nuclide's window results added the lines' counting variances
  as if independent, although close lines share window channels (NaI Ba-133: correlation +0.925
  between 79.6 and 81.0 keV), and added the reference peak terms as magnitudes. Each window line now
  keeps its estimator's coefficients on the sample and background channels (in memory);
  `_weighted_primary` and `combined_limits` add the cross terms with the observed counts, and the
  reference components are summed before the norm.
- `after_R8H` 6 PASS / 0 FAIL: NaI Ba-133 threshold 15.04 -> 13.67 Bq, uncertainty 9.11 -> 8.28 Bq;
  Monte Carlo u / sd 1.085 -> 0.989. One harness correction (conversion factor 0/0 at a zero result)
  and one changed existing test (`test_round7_combined`, Ba-133) disclosed. Benchmark 154 / 13 / 60
  unchanged; suite 1762 passed. ENGINE_VERSION 1.34.0.

### 2026-10-30 Round-9 review, Codex H1 (R9-A): summing state of curves saved by engine 1.26.0 and earlier

- Protocol `docs/baseline/round9_legacy_tcs_protocol.md` (82c64c4, before values 1 PASS / 3 FAIL).
  A legacy curve whose summing flag was lost by an old refit (point values still divided by their
  COI, "summing corrected, COI x" in the notes) loaded as uncorrected and was corrected a second time
  (curve at 121.78 keV +5.6 %); excluded corrected points got no state. The state is now read from
  the point notes on loading whatever the flag, excluded points included.
- `after_R9A` 3 PASS / 1 FAIL: RA9.C2 a drafting FAIL (exact equality with the note's 4 decimals),
  kept; pre-registered amendment (c8aab2b, tolerance 5e-5) re-run `after_R9A2` 4 PASS / 0 FAIL.
  Benchmark 154 / 13 / 60 unchanged; suite 1767 passed. ENGINE_VERSION 1.35.0.

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

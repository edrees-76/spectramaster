# SpectraMaster Development Plan for Standalone Laboratory Gamma Spectrum Analysis

**Handoff document for Claude Code — October 12, 2026**

Project location: `D:\DSpectraMaster`

Review this plan against the existing code, then implement it incrementally. Do not stop at general recommendations: begin with exploration and performance assessment, then deliver small, testable, reviewable changes. Do not rewrite the entire application.

## 1. Objective and Confirmed Requirements

Develop the current version of SpectraMaster into a standalone application for complete laboratory analysis of environmental samples, with the aim of matching **Aptec** and addressing these priorities:

- Detection of weak peaks.
- Resolution of overlapping peaks.
- Reduction of radionuclide identification errors.
- Energy and energy-resolution calibration.
- Experimental efficiency calibration.
- Background subtraction.
- Activity, activity concentration, and minimum detectable activity (MDA) calculations.
- Automatic analysis and manual editing, with a retained history of edits.

Intended use:

- Soil, water, food, and air-filter samples.
- HPGe and NaI detectors.
- Marinelli beakers of different sizes, without restricting the application to a fixed list of sizes.
- Calibration sources in Marinelli beakers and point sources.
- The user already has separate calibrations.
- File analysis only; hardware connections and spectrum acquisition are outside the scope of this development.
- Results in Bq, Bq/kg, Bq/L, and Bq/m³.
- Preserve the Arabic and English interfaces and existing conversion features.

The user does not currently have a matched collection of original spectra and Aptec/Genie/GammaVision analysis reports. Do not make their availability a prerequisite for starting work, and do not claim a direct comparison without the necessary data.

## 2. References and Their Intended Use

Consult the following primary sources when making scientific decisions or designing analysis tools:

| Reference | Intended use |
|---|---|
| [IAEA-TECDOC-1011, 1998](https://www-pub.iaea.org/MTCD/Publications/PDF/te_1011_prn.pdf) | Test methodology for peak searching, peak areas, uncertainty, and peak resolution |
| [IAEA-TECDOC-1565, 2007](https://www-pub.iaea.org/MTCD/Publications/PDF/te_1565_web.pdf) | Validation procedures and performance comparisons for specific tests |
| [IAEA intercomparison for low-level gamma-ray spectrometry, published in 2005](https://doi.org/10.1016/j.nima.2004.10.012) | Low-count and high-background cases |
| [HyperLab](https://www.hlabsoft.com/web/hl2023/productinfo.php) | Visual fit inspection, manual intervention, and complex peak regions |
| [InterSpec official repository](https://github.com/sandialabs/InterSpec) | Interactive analysis, peak interpretation, and spectrum data management |
| [GammaVision](https://www.ortec-online.com/products/software/gammavision) | Laboratory workflow, analysis, reporting, and quality control |
| [Genie and the Mirion ecosystem](https://www.mirion.com/reliable-advanced-gamma-spectroscopy-solutions) | Integration of calibration, analysis, activity calculations, and corrections |
| [bGamma](https://www.brightspec.be/brightspec/?q=node%2F42) | Search and fitting options and interactive inspection |

These are scientific and functional references, not a current ranking of software accuracy. Historical comparison results apply to the versions, settings, and spectra tested.

Respect the licenses of external code and data. Do not copy code before checking its license and compatibility with this project. Record the provenance of any added algorithm or dataset.

## 3. Existing Implementation to Verify

The project already contains core functionality that should be improved and reused:

| Path relative to the project root | Current role |
|---|---|
| `spectramaster/model.py` | Shared spectrum model |
| `spectramaster/convert.py` | Reading, writing, and conversion |
| `spectramaster/formats/` | Format readers and writers |
| `spectramaster/analysis/peaks.py` | Peak searching and fitting |
| `spectramaster/analysis/identify.py` | Radionuclide identification |
| `spectramaster/analysis/library.py` | Radionuclide library |
| `spectramaster/analysis/efficiency.py` | Certificates, efficiency points, and efficiency curves |
| `spectramaster/analysis/activity.py` | Activity, uncertainty, and detection limits |
| `spectramaster/tools/calibrate.py` | Energy and FWHM calibration |
| `spectramaster/tools/arithmetic.py` | Spectrum arithmetic |
| `spectramaster/gui/analysis_panel.py` | Analysis results display |
| `spectramaster/gui/efficiency_dialog.py` | Efficiency calibration interface |
| `spectramaster/gui/quant_panel.py` | Quantitative analysis interface |
| `spectramaster/gui/report.py` | Reporting |
| `tests/` | Format, analysis, calibration, calculation, and interface tests |

Peak searching exists in both the analysis engine and calibration tools. Examine the differences before consolidating them. Also check the consistency of the calibration line list with the main nuclear data library.

The presence of features and tests does not establish scientific validation. Record what actually works and which tests are skipped because data or dependencies are unavailable.

## 4. General Implementation Rules

- Read repository instructions and inspect local changes before editing.
- Preserve the user's changes and compatibility with existing formats, command-line behavior, and interfaces.
- Keep scientific calculations separate from Qt and the interface.
- Preserve original spectrum files; store modifications in an analysis session or a derived copy.
- Use explicit data models and versioned file schemas with migration support.
- Implement and test a small stage or increment before moving to the next.
- Do not add an alternative algorithm merely because a reference mentions it; demonstrate its benefit with suitable tests.
- Do not treat commercial software output as the sole ground truth if it becomes available later.
- Do not claim standards compliance or laboratory accuracy without defining the validation scope and evidence.
- Do not fabricate source certificates, detector characteristics, or sample data.
- Development can proceed using public and synthetic data, but validation with real sources remains a separate outstanding item until the required data are available.

## 5. Stage One: Establish Current Performance and a Validation Baseline

Create a reproducible evaluation before changing the engine.

Inspect the spectra in `test_corpus`, existing tests, their provenance, and their licenses. Find suitable public reference data when needed.

Build test collections covering:

- Strong and weak isolated peaks.
- Overlapping peaks with different separations and intensity ratios.
- Peaks near Compton edges or on varying backgrounds.
- Different counting-statistics levels.
- Separate HPGe and NaI spectra.
- Uncalibrated spectra and spectra with calibration drift.
- Natural background radionuclides, interferences, and missing expected lines.

For synthetic data, use fixed seeds for reproducibility and multiple random realizations when assessing statistical performance. Do not generate only peaks that exactly match the fitted model; include model-mismatch cases to test robustness.

Record:

- Energy, centroid, and FWHM deviations.
- Peak-area bias.
- Correct, missed, and false peaks.
- Uncertainty quality and statistical coverage.
- Correct and incorrect radionuclide identifications.
- Analysis runtime.
- Results by detector type and difficulty category.

Define and justify acceptance limits in advance for each test category. Do not use one percentage for all energies, detectors, and intensities, and do not adjust limits after seeing results to make tests pass.

**Deliverable:** A baseline report and reproducible reference tests identifying where improvement is needed.

## 6. Stage Two: Detectors, Geometries, Calibrations, and Analysis Sessions

Add explicit data models for detectors, measurement geometries, calibrations, samples, and analysis sessions.

A detector profile includes a stable identifier, name, type, available characteristics, and links to energy, FWHM, and efficiency calibrations.

A measurement geometry includes, as applicable:

- Container type, identifier, and nominal volume.
- Dimensions and actual fill level when known.
- Sample material or matrix and density.
- Measurement arrangement.
- Point-source distance and arrangement.
- Filter shape, dimensions, and positioning.

Do not assume that similar volumes imply equivalent geometries.

An analysis session stores:

- A spectrum reference and content fingerprint, with explicit handling of relocated files.
- Sample, detector, and geometry information.
- Snapshots of the calibrations and library used, or immutable references to them.
- Background and processing settings.
- Peaks, fits, assignments, and calculations.
- Application and analysis-engine versions.
- Edit history, including reasons and timestamps.

Add undo and redo for core manual edits. Distinguish displaying a previous session's stored results from recalculating them with a newer engine.

**Acceptance criterion:** Reopening a session restores its state, and changes to a calibration or library do not silently alter previous results.

## 7. Stage Three: Energy and FWHM Calibration

Develop an integrated calibration interface supporting:

- Selection of the source and its lines.
- Proposed peaks and review of line-to-peak matching.
- Addition, modification, or exclusion of points, with reasons.
- Selection of an appropriate model without unjustified increases in polynomial degree.
- Residuals, fit quality, and available uncertainty information.
- Saving the calibration, its range, and its date.
- Drift checks and proposed corrections subject to user review.

Validate:

- Lines independent of those used to build the calibration.
- The number and energy distribution of calibration points.
- Monotonicity of the energy-channel relationship.
- The first-channel offset, `first_channel`.
- Model behavior at the boundaries of the calibrated range.
- FWHM consistency with the detector type and actual measurements.

Use the shared nuclear data library as the common line source wherever possible, retaining provenance, version, and any specific selections.

**Acceptance criterion:** Known calibrations are recovered in tests, and incorrect matches, drift, and unreliable extrapolation are detected.

## 8. Stage Four: Peak Searching, Fitting, and Manual Editing

Inspect the current engine before selecting changes. Evaluate the need to improve:

- The energy-dependent resolution model.
- Weak-peak searching.
- Additional searching in fit residuals.
- Joint fitting of overlapping peaks.
- Asymmetric peak shapes and varying backgrounds.
- Fitting methods for low counts.
- Uncertainty calculations and correlations between peak parameters.

For original count data, evaluate Poisson-likelihood fitting in low-count cases. Do not apply it directly to a subtracted spectrum containing negative values as if those values were original Poisson counts.

Add a fit-inspection window displaying:

- Measured data.
- The total fit and each individual peak component.
- Background.
- Residuals and an appropriate goodness-of-fit measure.
- Area, energy, width, and their uncertainties.
- Warnings for fit failure or poor peak separability.

Manual intervention includes:

- Adding or removing a peak and refitting its group.
- Adjusting region boundaries and background.
- Fixing or freeing appropriate parameters.
- Comparing results before and after editing.
- Recording operations and undoing them.

Peak edits must have explicit downstream effects: recalculate dependent results or mark them as requiring an update.

**Acceptance criterion:** Test collections demonstrate improvement, failures remain visible, and the application does not invent separation beyond NaI's resolving capability.

## 9. Stage Five: Background and Uncertainty Propagation

Distinguish between:

1. The continuum background beneath a peak.
2. A measured laboratory background spectrum.

Review live-time normalization, energy alignment, channel redistribution, and count conservation.

Preserve variance information during subtraction and redistribution. Do not treat net counts as a new Poisson spectrum. Where redistribution introduces correlations, account for their effects or document and validate an approximation.

Add:

- Selection of an appropriate background for the detector and measurement arrangement.
- Display of the sample, background, and derived result.
- Comparison of subtraction at the peak level and spectrum level.
- Prevention of double background subtraction.
- Scientifically appropriate handling of negative net areas.
- Explicit indication of background validity changes or mismatches.

**Acceptance criterion:** Known test cases recover net areas and uncertainties without producing false detections due to subtraction.

## 10. Stage Six: Experimental Efficiency Calibration

Build a wizard that starts with the source certificate and ends with a saved calibration:

1. Enter the certificate or import it in a supported format.
2. Record activity, uncertainty, and reference date.
3. Select the calibration spectrum, detector, and geometry.
4. Review energy calibration, peaks, and background.
5. Calculate efficiency points and required time-related corrections.
6. Select the model and inspect residuals.
7. Exclude points with recorded reasons.
8. Perform independent validation and save the calibration version.

Extend the existing functionality in `efficiency.py` rather than creating a parallel engine.

Review:

- Counting, source-certificate, and emission-probability uncertainties.
- Shared and correlated uncertainty components among points from the same source.
- Prevention of double counting the same uncertainty component.
- Curve validity, calibrated range, and extrapolation.
- Effects of interferences and true coincidence summing on calibration lines.

Do not automatically apply point-source calibration to a Marinelli geometry, or transfer calibration between containers or materials without an appropriate validated method.

Allow the user's existing calibrations to be registered, but distinguish an imported, unvalidated calibration from a validated one. Do not assume that an Aptec file contains all required validity information.

**Acceptance criterion:** Known curves are recovered in tests, independent measurements can be used for validation when available, and incompatible geometries cannot be used silently.

## 11. Stage Seven: Improve Radionuclide Identification

Improve interpretability before adding unproven complexity.

For each radionuclide, show:

- Matched lines.
- Energy deviations and interferences.
- Expected and missing lines.
- Consistency of relative responses.
- Possible explanations as escape, sum, annihilation, or X-ray peaks.
- Background contributions.
- Reasons for accepting or rejecting the candidate.

Use the actual efficiency curve when valid, with an explicit, limited fallback when it is unavailable.

For NaI, account for merged lines and cases where a broad peak cannot be confidently assigned to one radionuclide.

Do not present a candidate score as an established statistical probability. Distinguish evidence for the presence of a radionuclide from detecting its activity above the decision threshold.

Add customizable environmental working libraries while preserving nuclear-data provenance and tracking user modifications.

Do not infer the activity of a natural decay-series parent from its daughters without an explicit, documented equilibrium assumption.

**Acceptance criterion:** Identification performance improves while false positives remain controlled, and users can understand the decisions.

## 12. Stage Eight: Activity, Activity Concentration, Uncertainty, and MDA

Review the existing calculations in detail using documented references and independently verified examples.

For each line, record:

- Net area and its uncertainty.
- Live time.
- Efficiency and its uncertainty.
- Emission probability.
- Applied time-related corrections.
- Calculated activity and uncertainty.
- Reason for accepting or excluding the line.

For each radionuclide:

- Allow selection of a key line or a justified combination of multiple lines.
- Account for shared uncertainty components across lines.
- Show inconsistencies among line-based results.
- Retain selection and combination rules.

Required inputs for concentration calculations:

| Unit | Inputs |
|---|---|
| Bq/kg | Mass and dry- or wet-weight basis |
| Bq/L | Measured sample volume |
| Bq/m³ | Sampled air volume, or flow rate and sampling duration |

For air filters, record sampling and measurement times, filter geometry, and any measured fraction of the filter. When converting filter activity to air concentration, make collection and retention efficiency assumptions and applied corrections explicit. Do not silently assume unknown values.

For MDA:

- Distinguish the decision threshold from the detection limit.
- Document the method, parameters, and scope.
- Calculate detection limits for requested radionuclides even when no peak is detected, provided valid inputs are available.
- Do not reduce every nondetection to an activity of zero.
- Report “less than MDA” according to an explicit decision rule.
- Review the existing Currie and ISO 11929 support; do not claim full compliance without verifying the formulation and scope.

**Acceptance criterion:** Independent numerical examples pass, uncertainty propagation is correct, and nondetections and missing inputs are handled explicitly.

## 13. Stage Nine: Workflow, Reporting, and Batch Analysis

Provide a clear workflow:

**Open spectrum → Select detector and geometry → Review calibrations and background → Analyze → Review peaks and radionuclides → Calculate activity and MDA → Generate report and save session.**

Add visible statuses such as:

- Calibration required.
- Incompatible calibration.
- Results require recalculation.
- Automatic analysis not yet reviewed.
- User-reviewed analysis.
- Measurement outside the validated scope.

Reports include:

- Sample, spectrum, detector, and geometry information.
- Calibrations, background, library, and their versions.
- Peaks and lines used.
- Activity, concentration, uncertainty, and MDA.
- Units, time reference, and weight basis.
- Warnings, assumptions, and important edits.
- Application version and session identifier.

For batch analysis, group measurements by compatible detector, geometry, and calibrations. Do not automatically apply one calibration to all files.

Preserve Arabic RTL behavior, correct number and unit direction, and existing result-export capabilities.

## 14. Quality Criteria and Tests

Use complementary validation layers:

- Unit tests for calculations.
- Statistical simulation tests for bias and uncertainty assessment.
- Public spectra with reference values.
- Integration tests from spectrum to report.
- Session persistence and schema migration tests.
- Undo, redo, and dependent-result update tests.
- Regression tests for formats, conversion, and CLI behavior.
- Interface tests for major operations in Arabic and English.
- Real-source measurements when available.

Do not write tests that merely repeat the same equation using the same implementation approach; use reference values or independent derivations.

Record skipped tests and their reasons. Passing synthetic tests does not constitute complete laboratory validation.

## 15. Development Release Sequence

| Release | Contents |
|---|---|
| **A** | Accuracy baseline and detector, geometry, and session models |
| **B** | Energy and FWHM calibration, peak inspection, and manual editing |
| **C** | Improved fitting, background handling, and uncertainty propagation |
| **D** | Experimental efficiency calibration and validity management |
| **E** | Improved identification, activity, concentration, and MDA |
| **F** | Reporting, batch analysis, laboratory workflow, and available final validation |

Do not commit to a deadline or promise final accuracy before completing the baseline and estimating the scope of changes.

## 16. What Claude Code Should Do First

1. Inspect the repository, its instructions, and local changes.
2. Review this plan against the current implementation and identify existing functionality, gaps, and risks.
3. Run appropriate tests and record missing dependencies and data.
4. Retain this document as the implementation plan. Add a separate progress document tracking stages, acceptance criteria, and justified changes to the plan.
5. Produce the scientific baseline report, including the limits of what was tested.
6. Begin implementing Release A in small increments.
7. Continue through the confirmed stages. Request user information only when its absence materially affects a decision's correctness or laboratory validation.

After each increment, report what changed, why, how it was tested, remaining limitations, and the next stage.

## Required Outcome

An application that enables users to analyze an environmental spectrum, review it manually, select a valid calibration for the detector and geometry, calculate activity, concentration, and detection limits with uncertainty, and save a session and report whose results can be traced to how they were produced.

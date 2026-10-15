"""Acceptance limits for the analysis-engine baseline.

These limits were written and committed BEFORE the benchmark was run for the first time
(see ``git log -- spectramaster/validation/acceptance.py``).  They must not be loosened to
make a run pass.  Changing one requires a new commit whose message states the scientific
reason, and the change must be recorded in ``docs/SpectraMaster_Progress.md``.

Conventions
-----------
* ``s`` (true signal-to-noise) of a synthetic peak = A / sqrt(B), A = true net counts of the
  peak, B = expected continuum counts in a window of 2.5 FWHM centred on the peak.  It is a
  property of the spectrum, not of the algorithm.
* A peak is *found* when a reported centroid lies within 0.5 FWHM of the true centroid
  (one reported peak per true peak, nearest first).  Everything else reported inside the
  analysed range is a *false peak*.
* ``z`` = (reported area - true area) / reported 1-sigma area uncertainty.  For a correct
  estimator with correct uncertainties |z| <= 1 holds ~68.3 % and |z| <= 2 ~95.4 % of the time.
* Area bias = mean over realisations of (reported - true) / true for found peaks.
* Status "report" means the metric is recorded but no pass/fail limit is set yet, because a
  justified limit cannot be fixed before the first measurement (stated per item).

Why the limits are not one global percentage: counting statistics, resolution and model
mismatch differ between detector types and categories, so each limit below is derived for
its own category.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Criterion:
    id: str
    detector: str          # "HPGe", "NaI" or "any"
    category: str          # scenario / reference-set name
    metric: str            # key in the benchmark result for that category
    op: str                # ">=", "<=", "abs<=", "in", "report"
    limit: Optional[object]
    rationale: str


# Binomial band for coverage with n >= 200 matched peaks: 0.683 +/- 3*sqrt(0.683*0.317/200)
# = 0.683 +/- 0.099; rounded to [0.60, 0.76].  For 2 sigma: 0.954 +/- 0.044 -> [0.90, 0.98]
# (upper bound kept below 1 so grossly over-estimated uncertainties are also flagged).
_COV1 = (0.60, 0.76)
_COV2 = (0.90, 0.98)

CRITERIA: list[Criterion] = []


def _c(*args):
    CRITERIA.append(Criterion(*args))


for det in ("HPGe", "NaI"):
    # ---------------------------------------------------------------- strong isolated peaks
    _c(f"{det}.strong.recall", det, "isolated_strong", "recall", ">=", 0.99,
       "Peaks with s >= 100 must essentially always be found; 1 % allows a pathological "
       "realisation near the analysis-range boundary.")
    _c(f"{det}.strong.area_bias", det, "isolated_strong", "area_bias", "abs<=", 0.01,
       "Gaussian peaks on a smooth continuum match the fitted model; with ~1e5 counts the "
       "statistical error of the mean over 30+ realisations is < 0.1 %, so a bias > 1 % is a "
       "systematic defect of the area estimator.")
    _c(f"{det}.strong.centroid_bias_fwhm", det, "isolated_strong", "centroid_bias_fwhm", "abs<=", 0.02,
       "Centroid precision for 1e5-count peaks is ~FWHM/(2.355*sqrt(N)) ~ 0.001 FWHM; 0.02 FWHM "
       "allows for channel-integration effects only.")
    _c(f"{det}.strong.fwhm_ratio", det, "isolated_strong", "fwhm_ratio_mean", "in", (0.95, 1.05),
       "The engine's FWHM model is rescaled to strong isolated peaks; it must reproduce the true "
       "width to 5 % (a 5 % width error already biases constrained-width areas by ~1-2 %).")
    _c(f"{det}.strong.cov1", det, "isolated_strong", "z_cov1", "in", _COV1,
       "Reported 1-sigma area uncertainties must have nominal coverage (binomial band, n >= 200).")
    _c(f"{det}.strong.cov2", det, "isolated_strong", "z_cov2", "in", _COV2,
       "Same as above for 2 sigma.")
    _c(f"{det}.strong.split", det, "isolated_strong", "split_fraction", "<=", 0.05,
       "No invented separation: a true singlet reported as two or more peaks within 1 FWHM in "
       "more than 5 % of cases means the doublet retry fires on noise.")

    # ---------------------------------------------------------------- weak isolated peaks
    # A-priori estimate: fitted-area sigma ~ sqrt(A + c*B) with c ~ 1.5-2 for a 2.5 FWHM
    # window, so the engine's significance ~ s/1.3.  With min_sig = 3, P(detect) ~ Phi(s/1.3-3):
    # s = 7 -> 0.99, s = 5 -> 0.79, s = 3 -> 0.12.  Limits below leave margin for that estimate.
    _c(f"{det}.weak.pdet_s7", det, "isolated_weak", "pdet_s7", ">=", 0.90,
       "At s = 7 the expected detection probability is ~0.99 for an efficient search.")
    _c(f"{det}.weak.pdet_s5", det, "isolated_weak", "pdet_s5", ">=", 0.50,
       "At s = 5 the expected detection probability is ~0.8; below 0.5 the search wastes "
       "sensitivity relative to its own threshold.")
    _c(f"{det}.weak.pdet_s3", det, "isolated_weak", "pdet_s3", "report", None,
       "Near the threshold; recorded to compare future search improvements (no limit: the "
       "trade-off against false peaks is set by the false-peak criterion).")
    _c(f"{det}.weak.area_bias_s7", det, "isolated_weak", "area_bias_s7", "abs<=", 0.05,
       "For s >= 7 detection selection bias is small; a mean area bias > 5 % is systematic.")

    # ---------------------------------------------------------------- background only
    _c(f"{det}.bkg.false_per_1000_res", det, "background_only", "false_per_1000_res", "<=", 3.0,
       "Pure Poisson continuum: a 3-sigma one-sided threshold gives ~1.35 false peaks per 1000 "
       "independent resolution elements; 3 allows for Poisson tails and correlated trials.")

    # ---------------------------------------------------------------- doublets
    _c(f"{det}.doublet.resolved_wide", det, "doublets", "resolved_ge1.5fwhm_ratio_le3", ">=", 0.90,
       "Separation >= 1.5 FWHM with intensity ratio <= 3 is visibly two peaks; both must be found.")
    _c(f"{det}.doublet.area_bias_wide", det, "doublets", "component_area_bias_ge1.5fwhm", "abs<=", 0.05,
       "Component areas of resolved doublets (s >= 30 each) must be unbiased within 5 %.")
    _c(f"{det}.doublet.resolved_1fwhm_equal", det, "doublets", "resolved_1.0fwhm_ratio1", ">=", 0.70,
       "Two equal peaks 1 FWHM apart still show a flat top / inflection that a joint fit "
       "should resolve in most realisations (counts >= 2e4 per component).")
    _c(f"{det}.doublet.total_area_close", det, "doublets", "total_area_bias_le0.75fwhm", "abs<=", 0.03,
       "Unresolvable doublets need not be split, but the multiplet's total area must be conserved "
       "(sum of reported peaks within the multiplet window).")
    _c(f"{det}.doublet.resolved_close", det, "doublets", "resolved_le0.75fwhm", "report", None,
       "Splitting peaks < 0.75 FWHM apart is reported only: claiming it automatically is not "
       "required and can be a sign of over-fitting.")

    # ---------------------------------------------------------------- Compton edge
    _c(f"{det}.edge.recall", det, "compton_edge", "recall", ">=", 0.90,
       "Peaks with s >= 20 on a Compton edge must still be found.")
    _c(f"{det}.edge.area_bias", det, "compton_edge", "area_bias", "abs<=", 0.05,
       "Linear background + step under a peak on an edge: 5 % allows for continuum-shape mismatch.")
    _c(f"{det}.edge.spurious", det, "compton_edge", "spurious_near_edge_per_spectrum", "<=", 0.20,
       "The edge itself must not be reported as a peak in more than 1 of 5 spectra.")

    # ---------------------------------------------------------------- model mismatch (tail)
    _c(f"{det}.tail.area_bias", det, "tailed", "area_bias", "abs<=", 0.03,
       "Peaks carry a low-energy exponential tail with 4 % of the area; an estimator that recovers "
       "at least a quarter of the tail stays within 3 %.  Larger bias means tailed peaks lose area.")
    _c(f"{det}.tail.split", det, "tailed", "split_fraction", "<=", 0.05,
       "A tail must not be reported as a separate peak.")

    # ---------------------------------------------------------------- low counts
    _c(f"{det}.low.area_bias", det, "low_counts", "area_bias_A_ge100", "abs<=", 0.05,
       "Peaks of 100-400 counts on ~1-3 counts/channel: Poisson regime.  Neyman-weighted least "
       "squares is known to bias low here; > 5 % average bias is a defect worth fixing.")
    _c(f"{det}.low.cov1", det, "low_counts", "z_cov1", "in", (0.55, 0.80),
       "Uncertainty coverage in the low-count regime (wider band: fewer matched peaks).")

    # ---------------------------------------------------------------- runtime
    _c(f"{det}.runtime", det, "runtime", "median_s", "<=", 0.5,
       "Engine contract (analysis/__init__.py): < 0.5 s per spectrum for interactive use.")

    # ---------------------------------------------------------------- identification
    _c(f"{det}.id.recall", det, "identification", "recall", ">=", 0.90 if det == "HPGe" else 0.75,
       "Fraction of present nuclides (strongest line s >= 15) reported.  NaI lower: merged lines "
       "make some nuclides legitimately ambiguous.")
    _c(f"{det}.id.false_per_spectrum", det, "identification", "false_per_spectrum", "<=",
       0.5 if det == "HPGe" else 1.0,
       "Reported nuclides that are absent (aliases of the same decay chain count as present).")
    _c(f"{det}.id.drift", det, "identification", "recall_by_drift", "report", None,
       "Recall vs. deliberate gain error (0, 0.1, 0.3, 1 %): informational, no a-priori limit.")
    _c(f"{det}.id.false_per_spectrum_environmental", det, "identification",
       "false_per_spectrum_environmental_library", "report", None,
       "Same spectra searched with the environmental application library (the GUI default): "
       "informational; the scored criteria keep the full library for comparability.")
    _c(f"{det}.id.recall_environmental", det, "identification", "recall_environmental_library", "report", None,
       "Recall with the environmental library, over present nuclides that belong to it.")

# -------------------------------------------------------------------- detector-type guess (P2)
# Added 2026-10-14 for increment A8, BEFORE the P2 fix was written or the benchmark was re-run
# with these categories.  Spectra carry no detector label, so the engine must infer the type.
for det in ("HPGe", "NaI", "NaI_4096"):
    _c(f"{det}.dettype.strong", det, "detector_guess", "correct_fraction_strong", ">=", 0.99,
       "Unlabelled spectra with strong isolated peaks: the detector type that sets the default "
       "resolution model must be inferred correctly (resolution differs ~30x between HPGe and NaI).")
    _c(f"{det}.dettype.low", det, "detector_guess", "correct_fraction_low", "report", None,
       "Low-count spectra (100-400 counts per peak): recorded only; little width information.")

# NaI(Tl) on a 4096-channel MCA (0.75 keV/ch): same physics as the 1024-channel NaI case, so the
# same limits apply (no relaxation for the finer binning).
_c("NaI_4096.strong.recall", "NaI_4096", "isolated_strong", "recall", ">=", 0.99,
   "Same limit as NaI.strong.recall.")
_c("NaI_4096.strong.area_bias", "NaI_4096", "isolated_strong", "area_bias", "abs<=", 0.01,
   "Same limit as NaI.strong.area_bias.")
_c("NaI_4096.strong.fwhm_ratio", "NaI_4096", "isolated_strong", "fwhm_ratio_mean", "in", (0.95, 1.05),
   "Same limit as NaI.strong.fwhm_ratio.")
_c("NaI_4096.strong.split", "NaI_4096", "isolated_strong", "split_fraction", "<=", 0.05,
   "Same limit as NaI.strong.split.")
_c("NaI_4096.id.recall", "NaI_4096", "identification", "recall", ">=", 0.75,
   "Same limit as NaI.id.recall.")
_c("NaI_4096.id.false_per_spectrum", "NaI_4096", "identification", "false_per_spectrum", "<=", 1.0,
   "Same limit as NaI.id.false_per_spectrum.")

# -------------------------------------------------------------------- energy calibration (Release B)
# Added 2026-10-14 for increment B0, BEFORE the calibration changes of Release B were written and
# before the benchmark computed these categories.  Source spectra are generated without an
# energy calibration; the true calibration is known.  "Error" = max |E_fit(ch) - E_true(ch)|
# over the energy range spanned by the matched lines, in units of the true FWHM there.
for det in ("HPGe", "NaI"):
    _c(f"{det}.cal.recover", det, "calibration", "recover_ok_fraction", ">=", 0.95,
       "A source spectrum with strong lines (HPGe: Eu-152 with a mildly non-linear true "
       "calibration; NaI: Am-241 + Cs-137 + Co-60) must give a calibration within 0.1 FWHM over "
       "the calibrated range.  0.1 FWHM keeps identification windows (~0.5 FWHM) unaffected.")
    _c(f"{det}.cal.wrong_source", det, "calibration", "wrong_source_flagged_fraction", ">=", 0.90,
       "A spectrum of Co-60 + Cs-137 presented as 'Eu-152' must not produce an unflagged "
       "calibration (an exception or a failed validation both count as flagged).")
    _c(f"{det}.drift.detect", det, "drift", "detected_fraction_at_limit", ">=", 0.95,
       "Natural-background spectrum whose stored gain is wrong by 0.3 % (HPGe) / 1 % (NaI), i.e. "
       ">= 0.2 FWHM at 1460 keV: the drift check must report it.")
    _c(f"{det}.drift.false_alarm", det, "drift", "false_alarm_fraction", "<=", 0.05,
       "No drift: the check must stay quiet in at least 95 % of spectra.")
    _c(f"{det}.drift.corrected", det, "drift", "corrected_ok_fraction_at_limit", ">=", 0.95,
       "The proposed correction, once accepted, must bring the calibration within 0.1 FWHM over "
       "the range of the background lines used.")
    _c(f"{det}.drift.by_level", det, "drift", "detected_fraction_by_level", "report", None,
       "Detection fraction per drift level (0, 0.1, 0.3, 1 %): informational.")
_c("HPGe.cal.order_linear", "HPGe", "calibration", "linear_truth_order1_fraction", ">=", 0.90,
   "Linear true calibration with 11 Eu-152 lines: the model selection must keep order 1 in at "
   "least 90 % of realisations (a test at the 5 % level would keep it ~95 % of the time); "
   "the plan forbids raising the degree without justification.")

# -------------------------------------------------------------------- measured background (Release C)
# Added 2026-10-14 for increment C0, BEFORE any Release C change and before the benchmark computed
# these categories.  Pairs of synthetic spectra: a laboratory background measured for 2x the
# sample live time (natural lines + a small Cs-137 contamination) and a sample = the same
# background rate + source lines (Cs-137, Co-60).  Net areas come from compute_activities with
# that background, in both modes ("peak": peak-by-peak; "spectrum": full-spectrum subtraction).
# Present lines: Cs-137 662, Co-60 1173 and 1332 keV (true sample-only area known); absent lines:
# K-40 1461, Bi-214 609, Pb-214 352 keV (present in sample and background alike, true net 0).
# About 120 present / 120 absent lines per category: binomial 3-sigma bands
# 0.683 +- 0.127 and 0.954 +- 0.057.
for det in ("HPGe", "NaI"):
    for mode in ("peak", "spectrum"):
        _c(f"{det}.bkg_{mode}.net_bias", det, f"background_{mode}", "net_area_bias", "abs<=", 0.03,
           "Subtracting a measured background must conserve the sample's own net area; 3 % allows for "
           "continuum-shape and alignment effects (statistical error of the mean < 1 %).")
        _c(f"{det}.bkg_{mode}.cov1", det, f"background_{mode}", "z_cov1", "in", (0.55, 0.81),
           "Net-area uncertainties must include the scaled background contribution (nominal 1-sigma "
           "coverage, binomial band for ~120 lines).")
        _c(f"{det}.bkg_{mode}.cov2", det, f"background_{mode}", "z_cov2", "in", (0.89, 1.0),
           "Same for 2 sigma.")
        _c(f"{det}.bkg_{mode}.false_detect", det, f"background_{mode}", "false_detection_fraction", "<=", 0.11,
           "Lines present only through the background must not be declared detected after subtraction "
           "more often than the decision threshold allows (k_alpha = 1.645: 5 %, + 3 sigma for ~120 trials).")
        _c(f"{det}.bkg_{mode}.recall", det, f"background_{mode}", "present_detected_fraction", "report", None,
           "Fraction of present lines declared detected (informational).")

# ------------------------------------------------- experimental efficiency (Release D, pre-registered D0)
# Synthetic mixed-standard calibration spectra with a known true efficiency curve.  In each
# realisation every nuclide's true activity differs from its certificate value by N(0, u_cert)
# (independent per nuclide, 2 %), so the certificate error is real and is shared by all lines
# of that nuclide.  The curve is evaluated at test energies between the calibration lines.
for det in ("HPGe", "NaI"):
    _c(f"{det}.eff.bias", det, "efficiency", "mean_rel_dev", "abs<=", 0.01,
       "Mean relative deviation of the fitted curve from the true efficiency at interpolation "
       "energies: > 1 % is a model or method bias (the random part averages over ~40 realisations).")
    _c(f"{det}.eff.cov1", det, "efficiency", "z_cov1", "in", (0.55, 0.81),
       "The curve uncertainty must cover the true efficiency at the nominal 68 % (counting, "
       "certificate and intensity components, correlations included, none counted twice).")
    _c(f"{det}.eff.cov2", det, "efficiency", "z_cov2", "in", (0.89, 1.0),
       "Same at 2 sigma.")
    _c(f"{det}.eff.extrapolation_flagged", det, "efficiency", "extrapolation_flagged", ">=", 1.0,
       "Every activity line outside the calibrated energy range must be flagged.")
    _c(f"{det}.eff.tcs_flagged", det, "efficiency", "tcs_flagged", ">=", 1.0,
       "Every calibration point from a cascade emitter (Co-60, Y-88, ...) must carry a "
       "coincidence-summing warning; summing is not negligible in close geometries.")
    _c(f"{det}.eff.geometry_guard", det, "efficiency", "geometry_guard", ">=", 1.0,
       "An efficiency calibration of another geometry (e.g. point source for a Marinelli sample) "
       "must not be used silently: refused, or used only with an explicit override that is reported.")
    _c(f"{det}.eff.validation_shown", det, "efficiency", "validation_shown", ">=", 1.0,
       "Results computed with an imported or unvalidated calibration must say so.")
    _c(f"{det}.eff.max_dev", det, "efficiency", "median_max_rel_dev", "report", None,
       "Median over realisations of the largest deviation within the calibrated range (informational).")

# ------------------------------------------------------ identification (Release E, pre-registered E0)
# Identification under gain drift (P3): the drift check of B1 exists; identification must still
# work at 0.3 % drift (HPGe ~3 FWHM at 1.5 MeV, NaI well inside its resolution).
_c("HPGe.id.recall_drift_0.3", "HPGe", "identification", "recall_at_drift_0.3", ">=", 0.85,
   "At 0.3 % gain drift the present nuclides must still be identified (drift corrected or tolerated).")
_c("NaI.id.recall_drift_0.3", "NaI", "identification", "recall_at_drift_0.3", ">=", 0.75,
   "Same, with the NaI recall limit.")
# Real spectra: IAEA IDB v2024-01 (CC BY 4.0), when available.  A first look at these spectra
# was taken BEFORE this registration (Pu-239 found 0/27, 6-11 implausible identifications per
# spectrum, see the progress document); the limits below are set from the laboratory's needs,
# the same as the synthetic limits, not from those values.
_c("IDB.HPGe.implausible_per_spectrum", "HPGe", "IDB", "HPGe_implausible_per_spectrum", "<=", 1.0,
   "Identifications that are neither the material's chains, Am-241/Np-237, nor natural/fallout "
   "background: at most 1 per spectrum, as for the synthetic false-identification limit.")
_c("IDB.HPGe.U235_recall", "HPGe", "IDB", "HPGe_U235_recall", ">=", 0.90,
   "U-235 (185.7 keV, strong) must be identified in uranium-bearing materials with >= 0.7 % U-235.")
for _d in ("HPGe", "CZT", "LaBr3", "CdTe", "NaI"):
    _c(f"IDB.{_d}.Pu239_recall", _d, "IDB", f"{_d}_Pu239_recall", "report", None,
       "Pu-239 in Pu/MOX (lines of 1e-5 to 1e-4 per decay); outside the laboratory's usual scope.")
    if _d != "HPGe":
        _c(f"IDB.{_d}.implausible_per_spectrum", _d, "IDB", f"{_d}_implausible_per_spectrum", "report", None,
           "Lower-resolution detectors: recorded for comparison.")
        _c(f"IDB.{_d}.U235_recall", _d, "IDB", f"{_d}_U235_recall", "report", None, "Recorded for comparison.")

# -------------------------------------------------------------------- IAEA G-1 (HPGe-like Ge(Li))
_c("G1.G1100.found", "HPGe", "G1", "G1100_found", ">=", 20,
   "Reference spectrum: 20 strong peaks (~65 000 counts each) must all be found.")
_c("G1.G1100.false", "HPGe", "G1", "G1100_false", "<=", 1,
   "At most one unexplained peak (the pseudo-Compton edge artefact at ~1024 ch is excluded).")
_c("G1.G1200.found", "HPGe", "G1", "G1200_found", ">=", 17,
   "G1 notes: 'many programs detect 17 peaks without spurious peaks'; best in the "
   "intercomparison was 19 of 22.")
_c("G1.G1200.false", "HPGe", "G1", "G1200_false", "<=", 1,
   "Same assessment rule as the G-1 notes (1020-1030 keV region ignored).")
_c("G1.G1300.recall", "HPGe", "G1", "G1300_recall_mean", ">=", 0.95,
   "Consistency spectra: 22 peaks, all with workable statistics.")
_c("G1.G1300.ratio_bias", "HPGe", "G1", "G1300_area_ratio_bias", "abs<=", 0.02,
   "Mean (measured/expected - 1) of area ratios vs. G1100 over 6 replicates; peaks were "
   "constructed by integral shifts and exact attenuation, so the ratio has no model bias.")
_c("G1.G1300.cov2", "HPGe", "G1", "G1300_z_cov2", "in", (0.85, 0.99),
   "z of the ratio deviation using the reported uncertainties (G1100 term included); ~130 "
   "values, so a wider band than for synthetic data.")
_c("G1.G1400.wide", "HPGe", "G1", "G1400_resolved_sep_ge6", ">=", 3,
   "The three doublets with 6-channel separation (~2 FWHM) must be resolved.")
_c("G1.G1400.mid", "HPGe", "G1", "G1400_resolved_sep3", "report", None,
   "3-channel separation (~1 FWHM): recorded; the G-1 notes say automatic analysis often fails.")

# -------------------------------------------------------------------- EML / Sanderson (HPGe)
_c("EML.linearity", "HPGe", "EML", "linearity_dev_max_sig", "<=", 3.0,
   "TEST01-TEST05 contain the standard scaled by 0.1 ... 0.001: area/multiplier must agree with "
   "TEST01 within 3 combined sigma for each of the 122, 662 and 1332 keV peaks.")
_c("EML.detect", "HPGe", "EML", "lowest_multiplier_detected", "report", None,
   "Lowest multiplier at which each peak is still detected (TEST01-TEST08); TEST09 has no "
   "standard added and any peak found there at those energies is a false detection.")
_c("EML.blank", "HPGe", "EML", "TEST09_false_at_lines", "<=", 0,
   "TEST09 (multiplier 0) must not report peaks at 122, 662 or 1332 keV unless they are present "
   "in the background spectrum itself (checked against BKG.DAT).")
_c("EML.doublets", "HPGe", "EML", "doublet_resolved_by_shift", "report", None,
   "TEST10-TEST32 doublets (shift 1-10 channels, varied ratios): recorded only, since the "
   "exact peak shape of the standard is not documented.")


def by_id() -> dict[str, Criterion]:
    return {c.id: c for c in CRITERIA}


def evaluate(c: Criterion, value) -> Optional[bool]:
    """True/False for pass/fail, None for 'report' criteria or missing values."""
    if c.op == "report" or value is None:
        return None
    try:
        if c.op == ">=":
            return value >= c.limit
        if c.op == "<=":
            return value <= c.limit
        if c.op == "abs<=":
            return abs(value) <= c.limit
        if c.op == "in":
            lo, hi = c.limit
            return lo <= value <= hi
    except TypeError:
        return None
    raise ValueError(c.op)

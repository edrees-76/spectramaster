# Aptec-style analysis: comparison results (2026-10-15)

Protocols, written before the comparisons: `aptec_peak_search_protocol.md`,
`aptec_identify_protocol.md`, `aptec_quantify_protocol.md`.  Data: Aptec Version 6.3 `.S0`
files of the read-only lab archive and the Aptec sample files; only numbers are reported.
The test sets were evaluated once, after the methods were frozen
(`spectramaster/analysis/aptec_analyze.py`).

## Peak Search — **FAIL**

| Set | Files | Stored ROIs | Our ROIs | Matched | Recall (≥ 0.90) | Precision (≥ 0.85) | median abs(ΔRL) / abs(ΔRH) (≤ 1) | identical RL and RH |
|---|---|---|---|---|---|---|---|---|
| development | 1002 | 7094 | 8974 | 5629 | 0.794 | 0.627 | 2 / 2 | 0.165 |
| **test** | 4203 | 28030 | 35874 | 22134 | **0.790** | **0.617** | **2 / 2** | 0.180 |

Excluded: 164 files without ROIs.  ΔRL percentiles (5, 25, 50, 75, 95): −7, −3, 0, 0, 6;
ΔRH: −6, 0, 0, 2, 6.  None of the three limits is met: the search does not reproduce Aptec's
ROIs.  Established from the stored data and used: acceptance at 1-sigma error < Max Peak Error;
each ROI edge is the lowest count between it and the peak top.  Not found: how Aptec chooses
the peak tops and the extent of the search window (it varies widely even for strong isolated
peaks of similar FWHM; some stored ROIs may have been edited by hand).

## Identify — **FAIL**

| Set | Files | Input ROIs | Aptec-identified | Agreement (≥ 0.95) | Identified-ROI recall (≥ 0.95) | wrong / missed / extra |
|---|---|---|---|---|---|---|
| development | 29 | 242 | 178 | 0.917 | 0.899 | 9 / 9 / 2 |
| **test** | 84 | 736 | 561 | **0.883** | **0.877** | 48 / 21 / 17 |

Library: Aptec's installed `isotope.lib` / `nai.lib`; 735 of 739 stored identifications are
lines of `isotope.lib` with identical yield and half-life.  Established and used: tolerance =
FWHM fraction × ROI FWHM (fixed tolerance when the ROI has no valid FWHM); fraction limit on
the yield of the lines found; among candidates, the isotope with most lines found, then the
nearest energy.  The remaining differences are mostly the choice between isotopes sharing a
line and ROIs Aptec matched to lines 1–2 keV away.

## Quantify — pre-registered comparison **FAIL**, corrected method agrees

| Method | Quantified ROIs | within 0.5 % (≥ 95 %) | max abs. difference |
|---|---|---|---|
| pre-registered: efficiency at the library line energy | 49 | 45 (91.8 %) | 3.19 % |
| found afterwards: efficiency at the ROI centroid energy (now used) | 49 | 49 (100 %) | 0.0025 % |

The correction was found on the same four files after the pre-registered comparison failed, so
its agreement is not an independent confirmation.  Stored activities of ROIs that were not
quantified equal net count / live time (35 134 of 35 134).

## Not compared

Background Subtract: no archive file has background-subtracted ROIs.  It follows the help
(subtract the background net rate of the same identified line when it is above its MDA).

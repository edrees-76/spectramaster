# Aptec-style identification: comparison protocol (pre-registered)

Written 2026-10-15, **before** any comparison result was seen.  The limits are not to be changed
after results are known; a result below a limit is reported as a failure.

## Question

Given the ROIs Aptec stored in a spectrum, its identification setup and its isotope library,
does SpectraMaster's Aptec-style identification (Analyze > Identify, `I`) assign the same
isotope line to each ROI as Aptec's S_Ident did?

## Data

* Aptec Version 6.3 `.S0` files with the "identified" ROI flag (Aptec sample files and the
  read-only lab archive; only numbers are reported).
* Library: the isotope library file named in the job header, read from the Aptec installation
  (`isotope.lib`, `nai.lib`).  Files whose library cannot be read are excluded (count reported).
* Input ROIs: the stored ROIs **without** those created by identification (Force MDA ROIs);
  stored centroid, FWHM points and statistics are used as stored.
* Split: SHA-256 of the file contents, `% 5 == 0` development, the rest test (same rule as
  the peak-search protocol).

## Metrics and limits (test set)

| Metric | Limit |
|---|---|
| ROI agreement: same isotope name and line energy (or both unidentified), over all input ROIs | ≥ 0.95 |
| Identified-ROI recall: Aptec-identified ROIs given the same line | ≥ 0.95 |

Also reported, with no limit: confusion counts (wrong isotope, missed, extra) and the Force
MDA ROIs created by both programs.

A pass means agreement with Aptec's S_Ident on these files, not correctness of either program's
identifications.

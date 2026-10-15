# Aptec-style peak search: comparison protocol (pre-registered)

Written 2026-10-15, **before** any comparison result was seen.  The limits below are not to be
changed after results are known; a result below a limit is reported as a failure.

## Question

Does SpectraMaster's Aptec-style peak search (Analyze > Peak Search, `P`) set the same ROIs that
Aptec PCMCA/WIN 6.31 stored, when it is run with the peak-search setup stored in the same file?

## Data

* Lab archive (read-only, private; only numbers are reported, never names or sample data):
  Aptec Version 6.3 `.S0` files with a job header (peak-search setup) and at least one ROI.
* Included: 8192-channel spectra, `wAnalyzeStatus = 0` (spectrum not processed), not
  background-subtracted, no MultiFit flag.
* Excluded: everything else (reported as a count).
* The stored ROIs are taken as Aptec's peak-search result.  Some may have been edited by hand
  afterwards; that is a known source of disagreement and is not corrected for.

## Split

Files are ordered by the SHA-256 of their contents.  `int(sha[:8], 16) % 5 == 0` is the
**development** set (about 20 %, used to design and tune the method); the rest is the **test**
set, evaluated once the method is frozen.  Only test-set numbers count against the limits.

## Matching

A stored ROI and a SpectraMaster ROI match when each one's centroid lies inside the other's
`[RL, RH]`; matching is one-to-one, closest centroids first.

## Metrics and limits (test set)

| Metric | Limit |
|---|---|
| Recall: matched / stored ROIs | ≥ 0.90 |
| Precision: matched / SpectraMaster ROIs | ≥ 0.85 |
| Median abs(ΔRL) and median abs(ΔRH) of matched ROIs | ≤ 1 channel |

Also reported, with no limit: share of matched ROIs with identical `RL` and `RH`, the
distribution of ΔRL / ΔRH, and the same metrics on the development set.

## What a pass does and does not mean

A pass means the method reproduces Aptec's stored peak-search ROIs on this archive.  It does
not validate either program's peak search against true peaks, and it does not establish
laboratory validation.

# Aptec-style quantification: comparison protocol (pre-registered)

Written 2026-10-15, **before** any comparison of computed activities with stored ones.  The
limits are not to be changed after results are known.

## Question

Given the identified ROIs, efficiency calibration, sample quantity, times and quantification
setup stored in an Aptec `.S0` file, does SpectraMaster's Aptec-style Quantify (Analyze >
Quantify, `Q`) give the activity and MDA Aptec stored in each ROI?

## Data

All Aptec Version 6.3 `.S0` files with the "quantified" ROI flag (Aptec sample files and the
read-only lab archive; only numbers are reported).  There are only four such files, so there is
no development / test split: the method follows the Aptec help (Quantification Setup, MDA
Definition) and is compared once.  Already observed while choosing the data, before
implementing: stored activities are proportional to net rate / (efficiency × yield) for each
file, and ROIs not quantified store the net count rate as their activity.

## Metrics and limits

| Metric | Limit |
|---|---|
| Quantified ROIs whose activity agrees within 0.5 % | ≥ 95 % |
| Quantified ROIs whose MDA agrees within 0.5 % | reported, no limit (the MDA formula for an activity is not documented) |

Stored values are 4-byte floats; 0.5 % allows for that and for efficiency-curve rounding.
A pass means agreement with Aptec on these files only.

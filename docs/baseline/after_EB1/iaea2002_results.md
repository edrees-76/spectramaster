# IAEA 2002 test spectra: activity check results

Engine 1.21.0. Protocol: `docs/baseline/iaea2002_validation_protocol.md`.

## Criteria (main analysis)

| ID | Value | Limit | Result | Detail |
|---|---|---|---|---|
| IA.C1 | 0.65 | >= 0.9 | FAIL | 13/20 pairs with |z| <= 2.58 |
| IA.C2 | 1 | >= 0.8 | PASS | marinelli: 10/10 pairs with |ratio - 1| <= 0.1 |
| IA.C3 | 0.9 | >= 0.8 | PASS | pillbox: 9/10 pairs with |ratio - 1| <= 0.15 |
| IA.C4.M | 0.9594 | in [0.93, 1.07] | PASS | marinelli: median ratio of 5 long-spectrum pairs |
| IA.C4.P | 0.8873 | in [0.93, 1.07] | FAIL | pillbox: median ratio of 5 long-spectrum pairs |
| IA.C5 | 2.093 | <= 2.0, none missing | FAIL | rms z of 20 pairs |
| IA.C6 | 20 | 20 / 20 | PASS | 20/20 pairs reported as detected |

## Pairs (main analysis)

| Geometry | Spectrum | Nuclide | Certificate Bq | Result Bq | u (k=1) | Ratio | z | Detected | Lines |
|---|---|---|---|---|---|---|---|---|---|
| marinelli | maritsmall | Ba-133 | 1713 | 1632 | 50.19 | 0.953 | -1.34 | yes | 356.0 |
| marinelli | maritsmall | Co-60 | 1076 | 1032 | 37.4 | 0.959 | -1.02 | yes | 1173.2 |
| marinelli | maritsmall | Eu-152 | 3739 | 3602 | 113.3 | 0.963 | -1.02 | yes | 121.8 |
| marinelli | maritsmall | Cr-51 | 7903 | 7926 | 234.1 | 1.003 | 0.08 | yes | 320.1 |
| marinelli | maritsmall | Na-22 | 1073 | 1029 | 42.55 | 0.959 | -0.93 | yes | 1274.5 |
| marinelli | maritsmall60 | Ba-133 | 1713 | 1630 | 50.67 | 0.952 | -1.36 | yes | 356.0 |
| marinelli | maritsmall60 | Co-60 | 1076 | 1039 | 38.36 | 0.965 | -0.85 | yes | 1173.2 |
| marinelli | maritsmall60 | Eu-152 | 3739 | 3620 | 114.2 | 0.968 | -0.88 | yes | 121.8 |
| marinelli | maritsmall60 | Cr-51 | 7903 | 7964 | 237.8 | 1.008 | 0.21 | yes | 320.1 |
| marinelli | maritsmall60 | Na-22 | 1073 | 1031 | 43.69 | 0.961 | -0.87 | yes | 1274.5 |
| pillbox | PITBIG | Ba-133 | 1253 | 1112 | 40.62 | 0.887 | -2.98 | yes | 356.0 |
| pillbox | PITBIG | Co-60 | 799 | 716.6 | 27.24 | 0.897 | -2.63 | yes | 1173.2 |
| pillbox | PITBIG | Eu-152 | 2827 | 2375 | 95.77 | 0.840 | -4.10 | yes | 121.8 |
| pillbox | PITBIG | Cr-51 | 7827 | 7113 | 258.3 | 0.909 | -2.38 | yes | 320.1 |
| pillbox | PITBIG | Na-22 | 1063 | 937.8 | 42.92 | 0.882 | -2.63 | yes | 1274.5 |
| pillbox | PITBIG60 | Ba-133 | 1253 | 1100 | 41.01 | 0.878 | -3.21 | yes | 356.0 |
| pillbox | PITBIG60 | Co-60 | 799 | 706.1 | 27.04 | 0.884 | -2.98 | yes | 1173.2 |
| pillbox | PITBIG60 | Eu-152 | 2827 | 2688 | 105.7 | 0.951 | -1.16 | yes | 1408.0 |
| pillbox | PITBIG60 | Cr-51 | 7827 | 7077 | 258 | 0.904 | -2.51 | yes | 320.1 |
| pillbox | PITBIG60 | Na-22 | 1063 | 938.7 | 43.22 | 0.883 | -2.60 | yes | 1274.5 |

## marinelli: calibration

Efficiency curve: two-branch log-log, Ec = 469.7 keV, orders 3/3; model error 0.00 %; warnings 0; points used 18/18.
Peak-to-total: a = 0.1958, b = -0.5097 (PT(E) = a (E/1000)^b).

| Spectrum | Method | Lines | rms keV | Unmatched |
|---|---|---|---|---|
| BGSMALLMARI | pattern search | 8 | 0.104 | Th-232 583.2, Ra-226 609.3, Th-232 969.0, Ra-226 1764.5 |
| maricsmall | pattern search | 17 | 0.011 | — |
| maritsmall | pattern search | 20 | 0.146 | — |
| maritsmall60 | pattern search | 19 | 0.155 | Eu-152 867.4 |

| P/T spectrum | Line keV | Peak area | Total | P/T |
|---|---|---|---|---|
| Co57SMALL | 122.06 | 7.621e+04 | 1.376e+05 | 0.5536 |
| Sn113SMALL | 391.7 | 1.315e+04 | 3.99e+04 | 0.3296 |
| Cs137SMALL | 661.66 | 1.021e+05 | 4.017e+05 | 0.2541 |
| Mn54SMALL | 834.85 | 3.331e+04 | 1.541e+05 | 0.2161 |
| Zn65SMALL | 1115.54 | 1.158e+04 | 6.68e+04 | 0.1733 |

| Efficiency point | keV | eps | u % | used | note |
|---|---|---|---|---|---|
| Am-241 | 59.54 | 0.033508 | 2.28 | yes | background subtracted before the fit (S - kB) |
| Cd-109 | 88.03 | 0.054392 | 2.05 | yes | background subtracted before the fit (S - kB) |
| Co-57 | 122.06 | 0.061351 | 2.02 | yes | background subtracted before the fit (S - kB) |
| Co-57 | 136.47 | 0.061242 | 2.22 | yes | background subtracted before the fit (S - kB) |
| Ce-139 | 165.86 | 0.056806 | 2.05 | yes | background subtracted before the fit (S - kB) |
| Sn-113 | 255.13 | 0.043652 | 4.32 | yes | background subtracted before the fit (S - kB) |
| Hg-203 | 279.19 | 0.040678 | 2.08 | yes | background subtracted before the fit (S - kB) |
| Sn-113 | 391.70 | 0.030996 | 2.13 | yes | background subtracted before the fit (S - kB) |
| Cs-134 | 563.25 | 0.018207 | 2.06 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Cs-134 | 569.33 | 0.018042 | 2.13 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Cs-134 | 604.72 | 0.018728 | 2.12 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Cs-137 | 661.66 | 0.020201 | 2.14 | yes | background subtracted before the fit (S - kB) |
| Cs-134 | 795.86 | 0.015068 | 2.14 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Cs-134 | 801.95 | 0.013522 | 5.52 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Mn-54 | 834.85 | 0.016694 | 2.38 | yes | background subtracted before the fit (S - kB) |
| Y-88 | 898.04 | 0.014843 | 2.51 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Zn-65 | 1115.54 | 0.013427 | 2.56 | yes | background subtracted before the fit (S - kB) |
| Cs-134 | 1365.18 | 0.012999 | 2.36 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |

## pillbox: calibration

Efficiency curve: two-branch log-log, Ec = 205.7 keV, orders 3/2; model error 0.00 %; warnings 0; points used 19/19.
Peak-to-total: a = 0.2669, b = -0.3540 (PT(E) = a (E/1000)^b).

| Spectrum | Method | Lines | rms keV | Unmatched |
|---|---|---|---|---|
| BGBIGPOINT | pattern search | 10 | 0.063 | Th-232 911.2, Ra-226 1764.5 |
| picbig | pattern search | 18 | 0.105 | — |
| PITBIG | pattern search | 19 | 0.007 | Na-22 511.0 |
| PITBIG60 | pattern search | 19 | 0.162 | Eu-152 1408.0 |

| P/T spectrum | Line keV | Peak area | Total | P/T |
|---|---|---|---|---|
| Co57BIG | 122.06 | 3.824e+04 | 7.041e+04 | 0.5431 |
| Sn113BIG | 391.7 | 9024 | 2.309e+04 | 0.3908 |
| Cs137BIG | 661.66 | 8.115e+04 | 2.542e+05 | 0.3193 |
| Mn54BIG | 834.85 | 2.839e+04 | 9.779e+04 | 0.2903 |
| Zn65BIG | 1115.54 | 1.039e+04 | 4.336e+04 | 0.2396 |

| Efficiency point | keV | eps | u % | used | note |
|---|---|---|---|---|---|
| Am-241 | 59.54 | 0.025987 | 2.51 | yes | background subtracted before the fit (S - kB) |
| Cd-109 | 88.03 | 0.059775 | 2.20 | yes | background subtracted before the fit (S - kB) |
| Co-57 | 122.06 | 0.074541 | 2.06 | yes | background subtracted before the fit (S - kB) |
| Co-57 | 136.47 | 0.077623 | 2.14 | yes | background subtracted before the fit (S - kB) |
| Ce-139 | 165.86 | 0.073942 | 2.02 | yes | background subtracted before the fit (S - kB) |
| Sn-113 | 255.13 | 0.060199 | 4.33 | yes | background subtracted before the fit (S - kB) |
| Hg-203 | 279.19 | 0.056794 | 1.97 | yes | background subtracted before the fit (S - kB) |
| Sn-113 | 391.70 | 0.046778 | 1.99 | yes | background subtracted before the fit (S - kB) |
| Cs-134 | 563.25 | 0.027374 | 2.14 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Cs-134 | 569.33 | 0.027267 | 2.03 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Cs-134 | 604.72 | 0.029733 | 2.09 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Cs-137 | 661.66 | 0.034462 | 2.04 | yes | background subtracted before the fit (S - kB) |
| Cs-134 | 795.86 | 0.02546 | 2.08 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Cs-134 | 801.95 | 0.022958 | 4.93 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Mn-54 | 834.85 | 0.029832 | 2.15 | yes | background subtracted before the fit (S - kB) |
| Y-88 | 898.04 | 0.025868 | 2.10 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Zn-65 | 1115.54 | 0.025557 | 2.14 | yes | background subtracted before the fit (S - kB) |
| Cs-134 | 1365.18 | 0.027567 | 2.05 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Y-88 | 1836.06 | 0.01655 | 2.03 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |

## Sensitivity variants (report only)

| Variant | Geometry | Spectrum | Nuclide | Ratio | z |
|---|---|---|---|---|---|
| S1 no summing correction | marinelli | maritsmall | Ba-133 | 0.943 | -0.42 |
| S1 no summing correction | marinelli | maritsmall | Co-60 | 0.832 | -1.35 |
| S1 no summing correction | marinelli | maritsmall | Eu-152 | 0.867 | -1.08 |
| S1 no summing correction | marinelli | maritsmall | Cr-51 | 0.993 | -0.05 |
| S1 no summing correction | marinelli | maritsmall | Na-22 | 0.716 | -2.61 |
| S1 no summing correction | marinelli | maritsmall60 | Ba-133 | 0.942 | -0.42 |
| S1 no summing correction | marinelli | maritsmall60 | Co-60 | 0.837 | -1.30 |
| S1 no summing correction | marinelli | maritsmall60 | Eu-152 | 0.871 | -1.04 |
| S1 no summing correction | marinelli | maritsmall60 | Cr-51 | 0.997 | -0.02 |
| S1 no summing correction | marinelli | maritsmall60 | Na-22 | 0.717 | -2.59 |
| S1 no summing correction | pillbox | PITBIG | Ba-133 | 0.917 | -0.22 |
| S1 no summing correction | pillbox | PITBIG | Co-60 | 0.838 | -0.46 |
| S1 no summing correction | pillbox | PITBIG | Eu-152 | 0.650 | -1.29 |
| S1 no summing correction | pillbox | PITBIG | Cr-51 | 0.967 | -0.08 |
| S1 no summing correction | pillbox | PITBIG | Na-22 | 0.714 | -0.96 |
| S1 no summing correction | pillbox | PITBIG60 | Ba-133 | 0.907 | -0.25 |
| S1 no summing correction | pillbox | PITBIG60 | Co-60 | 0.826 | -0.51 |
| S1 no summing correction | pillbox | PITBIG60 | Eu-152 | 0.640 | -1.35 |
| S1 no summing correction | pillbox | PITBIG60 | Cr-51 | 0.962 | -0.10 |
| S1 no summing correction | pillbox | PITBIG60 | Na-22 | 0.715 | -0.96 |
| S2 loglog model | marinelli | maritsmall | Ba-133 | 0.954 | -1.30 |
| S2 loglog model | marinelli | maritsmall | Co-60 | 0.975 | -0.61 |
| S2 loglog model | marinelli | maritsmall | Eu-152 | 0.965 | -0.95 |
| S2 loglog model | marinelli | maritsmall | Cr-51 | 1.001 | 0.02 |
| S2 loglog model | marinelli | maritsmall | Na-22 | 0.959 | -0.92 |
| S2 loglog model | marinelli | maritsmall60 | Ba-133 | 0.953 | -1.32 |
| S2 loglog model | marinelli | maritsmall60 | Co-60 | 0.981 | -0.45 |
| S2 loglog model | marinelli | maritsmall60 | Eu-152 | 0.970 | -0.81 |
| S2 loglog model | marinelli | maritsmall60 | Cr-51 | 1.006 | 0.15 |
| S2 loglog model | marinelli | maritsmall60 | Na-22 | 0.960 | -0.86 |
| S2 loglog model | pillbox | PITBIG | Ba-133 | 0.890 | -2.31 |
| S2 loglog model | pillbox | PITBIG | Co-60 | 0.872 | -2.68 |
| S2 loglog model | pillbox | PITBIG | Eu-152 | 0.849 | -3.15 |
| S2 loglog model | pillbox | PITBIG | Cr-51 | 0.905 | -1.99 |
| S2 loglog model | pillbox | PITBIG | Na-22 | 0.849 | -2.95 |
| S2 loglog model | pillbox | PITBIG60 | Ba-133 | 0.881 | -2.51 |
| S2 loglog model | pillbox | PITBIG60 | Co-60 | 0.859 | -2.97 |
| S2 loglog model | pillbox | PITBIG60 | Eu-152 | 0.923 | -1.51 |
| S2 loglog model | pillbox | PITBIG60 | Cr-51 | 0.900 | -2.09 |
| S2 loglog model | pillbox | PITBIG60 | Na-22 | 0.850 | -2.92 |
| S3 maricsmall.chn start time | marinelli | maritsmall | Ba-133 | 0.976 | -0.66 |
| S3 maricsmall.chn start time | marinelli | maritsmall | Co-60 | 0.986 | -0.36 |
| S3 maricsmall.chn start time | marinelli | maritsmall | Eu-152 | 0.968 | -0.87 |
| S3 maricsmall.chn start time | marinelli | maritsmall | Cr-51 | 1.029 | 0.78 |
| S3 maricsmall.chn start time | marinelli | maritsmall | Na-22 | 0.971 | -0.67 |
| S3 maricsmall.chn start time | marinelli | maritsmall60 | Ba-133 | 0.975 | -0.68 |
| S3 maricsmall.chn start time | marinelli | maritsmall60 | Co-60 | 0.992 | -0.20 |
| S3 maricsmall.chn start time | marinelli | maritsmall60 | Eu-152 | 0.973 | -0.74 |
| S3 maricsmall.chn start time | marinelli | maritsmall60 | Cr-51 | 1.034 | 0.90 |
| S3 maricsmall.chn start time | marinelli | maritsmall60 | Na-22 | 0.972 | -0.62 |
| S4 certificate time read as EST | marinelli | maritsmall | Ba-133 | 0.951 | -1.41 |
| S4 certificate time read as EST | marinelli | maritsmall | Co-60 | 0.959 | -1.03 |
| S4 certificate time read as EST | marinelli | maritsmall | Eu-152 | 0.963 | -1.03 |
| S4 certificate time read as EST | marinelli | maritsmall | Cr-51 | 1.006 | 0.18 |
| S4 certificate time read as EST | marinelli | maritsmall | Na-22 | 0.959 | -0.93 |
| S4 certificate time read as EST | marinelli | maritsmall60 | Ba-133 | 0.950 | -1.43 |
| S4 certificate time read as EST | marinelli | maritsmall60 | Co-60 | 0.965 | -0.87 |
| S4 certificate time read as EST | marinelli | maritsmall60 | Eu-152 | 0.968 | -0.89 |
| S4 certificate time read as EST | marinelli | maritsmall60 | Cr-51 | 1.011 | 0.31 |
| S4 certificate time read as EST | marinelli | maritsmall60 | Na-22 | 0.961 | -0.87 |
| S4 certificate time read as EST | pillbox | PITBIG | Ba-133 | 0.886 | -3.03 |
| S4 certificate time read as EST | pillbox | PITBIG | Co-60 | 0.897 | -2.63 |
| S4 certificate time read as EST | pillbox | PITBIG | Eu-152 | 0.840 | -4.09 |
| S4 certificate time read as EST | pillbox | PITBIG | Cr-51 | 0.912 | -2.29 |
| S4 certificate time read as EST | pillbox | PITBIG | Na-22 | 0.882 | -2.63 |
| S4 certificate time read as EST | pillbox | PITBIG60 | Ba-133 | 0.876 | -3.26 |
| S4 certificate time read as EST | pillbox | PITBIG60 | Co-60 | 0.883 | -2.98 |
| S4 certificate time read as EST | pillbox | PITBIG60 | Eu-152 | 0.950 | -1.18 |
| S4 certificate time read as EST | pillbox | PITBIG60 | Cr-51 | 0.907 | -2.41 |
| S4 certificate time read as EST | pillbox | PITBIG60 | Na-22 | 0.883 | -2.60 |

## S5: peak areas of mix2neq6 against the IRI reference (report only)

| Group | reduced chi2 | n |
|---|---|---|
| matches, high peaks (A/dA > 10) | 2.41 | 53 |
| matches, small peaks | — | 0 |
| misses | 2.69 | 100 |
| false hits | — | 0 |
| total | 2.59 | 153 |

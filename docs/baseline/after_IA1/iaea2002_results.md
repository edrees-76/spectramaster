# IAEA 2002 test spectra: activity check results

Engine 1.7.0. Protocol: `docs/baseline/iaea2002_validation_protocol.md`.

## Criteria (main analysis)

| ID | Value | Limit | Result | Detail |
|---|---|---|---|---|
| IA.C1 | 0.7 | >= 0.9 | FAIL | 14/20 pairs with |z| <= 2.58 |
| IA.C2 | 0.8 | >= 0.8 | PASS | marinelli: 8/10 pairs with |ratio - 1| <= 0.1 |
| IA.C3 | 0.5 | >= 0.8 | FAIL | pillbox: 5/10 pairs with |ratio - 1| <= 0.15 |
| IA.C4.M | 0.9627 | in [0.93, 1.07] | PASS | marinelli: median ratio of 5 long-spectrum pairs |
| IA.C4.P | 0.8627 | in [0.93, 1.07] | FAIL | pillbox: median ratio of 5 long-spectrum pairs |
| IA.C5 | 2.497 | <= 2.0, none missing | FAIL | rms z of 20 pairs |
| IA.C6 | 20 | 20 / 20 | PASS | 20/20 pairs reported as detected |

## Pairs (main analysis)

| Geometry | Spectrum | Nuclide | Certificate Bq | Result Bq | u (k=1) | Ratio | z | Detected | Lines |
|---|---|---|---|---|---|---|---|---|---|
| marinelli | maritsmall | Ba-133 | 1713 | 1649 | 55.83 | 0.963 | -0.98 | yes | 356.0 |
| marinelli | maritsmall | Co-60 | 1076 | 1047 | 40.97 | 0.973 | -0.62 | yes | 1173.2 |
| marinelli | maritsmall | Eu-152 | 3739 | 3395 | 113.1 | 0.908 | -2.56 | yes | 121.8 |
| marinelli | maritsmall | Cr-51 | 7903 | 7958 | 259.7 | 1.007 | 0.18 | yes | 320.1 |
| marinelli | maritsmall | Na-22 | 1073 | 861.6 | 34.45 | 0.803 | -5.25 | yes | 1274.5 |
| marinelli | maritsmall60 | Ba-133 | 1713 | 1647 | 56.43 | 0.961 | -1.01 | yes | 356.0 |
| marinelli | maritsmall60 | Co-60 | 1076 | 1042 | 40.05 | 0.968 | -0.76 | yes | 1173.2 |
| marinelli | maritsmall60 | Eu-152 | 3739 | 3409 | 115.4 | 0.912 | -2.42 | yes | 121.8 |
| marinelli | maritsmall60 | Cr-51 | 7903 | 7979 | 266.8 | 1.010 | 0.25 | yes | 320.1 |
| marinelli | maritsmall60 | Na-22 | 1073 | 847.8 | 32.74 | 0.790 | -5.80 | yes | 1274.5 |
| pillbox | PITBIG | Ba-133 | 1253 | 1143 | 165.5 | 0.912 | -0.66 | yes | 356.0 |
| pillbox | PITBIG | Co-60 | 799 | 689.3 | 101 | 0.863 | -1.07 | yes | 1173.2 |
| pillbox | PITBIG | Eu-152 | 2827 | 1929 | 282.7 | 0.682 | -3.12 | yes | 121.8 |
| pillbox | PITBIG | Cr-51 | 7827 | 7360 | 1066 | 0.940 | -0.43 | yes | 320.1 |
| pillbox | PITBIG | Na-22 | 1063 | 702.7 | 102.9 | 0.661 | -3.43 | yes | 1274.5 |
| pillbox | PITBIG60 | Ba-133 | 1253 | 1131 | 164 | 0.902 | -0.74 | yes | 356.0 |
| pillbox | PITBIG60 | Co-60 | 799 | 678.8 | 99.52 | 0.850 | -1.19 | yes | 1173.2 |
| pillbox | PITBIG60 | Eu-152 | 2827 | 1896 | 278 | 0.671 | -3.29 | yes | 121.8 |
| pillbox | PITBIG60 | Cr-51 | 7827 | 7319 | 1060 | 0.935 | -0.47 | yes | 320.1 |
| pillbox | PITBIG60 | Na-22 | 1063 | 703.4 | 103 | 0.662 | -3.42 | yes | 1274.5 |

## marinelli: calibration

Efficiency curve: two-branch log-log, Ec = 586.8 keV, orders 3/1; model error 0.00 %; warnings 0; points used 18/18.
Peak-to-total: a = 0.1960, b = -0.5094 (PT(E) = a (E/1000)^b).

| Spectrum | Method | Lines | rms keV | Unmatched |
|---|---|---|---|---|
| BGSMALLMARI | pattern search | 8 | 0.104 | Th-232 583.2, Ra-226 609.3, Th-232 969.0, Ra-226 1764.5 |
| maricsmall | pattern search | 17 | 0.011 | — |
| maritsmall | pattern search | 20 | 0.146 | — |
| maritsmall60 | pattern search | 19 | 0.155 | Eu-152 867.4 |

| P/T spectrum | Line keV | Peak area | Total | P/T |
|---|---|---|---|---|
| Co57SMALL | 122.06 | 7.621e+04 | 1.376e+05 | 0.5536 |
| Sn113SMALL | 391.7 | 1.315e+04 | 3.99e+04 | 0.3295 |
| Cs137SMALL | 661.66 | 1.023e+05 | 4.017e+05 | 0.2548 |
| Mn54SMALL | 834.85 | 3.335e+04 | 1.541e+05 | 0.2164 |
| Zn65SMALL | 1115.54 | 1.157e+04 | 6.68e+04 | 0.1732 |

| Efficiency point | keV | eps | u % | used | note |
|---|---|---|---|---|---|
| Am-241 | 59.54 | 0.033508 | 2.28 | yes | background subtracted before the fit (S - kB) |
| Cd-109 | 88.03 | 0.054362 | 2.05 | yes | background subtracted before the fit (S - kB) |
| Co-57 | 122.06 | 0.061351 | 2.02 | yes | background subtracted before the fit (S - kB) |
| Co-57 | 136.47 | 0.061194 | 2.15 | yes | background subtracted before the fit (S - kB) |
| Ce-139 | 165.86 | 0.056806 | 2.05 | yes | background subtracted before the fit (S - kB) |
| Sn-113 | 255.13 | 0.043652 | 4.32 | yes | background subtracted before the fit (S - kB) |
| Hg-203 | 279.19 | 0.040729 | 2.02 | yes | background subtracted before the fit (S - kB) |
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

Efficiency curve: two-branch log-log, Ec = 103.7 keV, orders 1/1; model error 5.97 %; warnings 2; points used 19/19.
Peak-to-total: a = 0.2669, b = -0.3540 (PT(E) = a (E/1000)^b).

| Spectrum | Method | Lines | rms keV | Unmatched |
|---|---|---|---|---|
| BGBIGPOINT | pattern search | 10 | 0.063 | Th-232 911.2, Ra-226 1764.5 |
| picbig | pattern search | 18 | 0.105 | — |
| PITBIG | pattern search | 19 | 0.007 | Na-22 511.0 |
| PITBIG60 | pattern search | 19 | 0.162 | Eu-152 1408.0 |

| P/T spectrum | Line keV | Peak area | Total | P/T |
|---|---|---|---|---|
| Co57BIG | 122.06 | 3.826e+04 | 7.041e+04 | 0.5434 |
| Sn113BIG | 391.7 | 9024 | 2.309e+04 | 0.3908 |
| Cs137BIG | 661.66 | 8.115e+04 | 2.542e+05 | 0.3193 |
| Mn54BIG | 834.85 | 2.839e+04 | 9.779e+04 | 0.2903 |
| Zn65BIG | 1115.54 | 1.039e+04 | 4.336e+04 | 0.2397 |

| Efficiency point | keV | eps | u % | used | note |
|---|---|---|---|---|---|
| Am-241 | 59.54 | 0.026063 | 2.45 | yes | background subtracted before the fit (S - kB) |
| Cd-109 | 88.03 | 0.059776 | 2.20 | yes | background subtracted before the fit (S - kB) |
| Co-57 | 122.06 | 0.074541 | 2.06 | yes | background subtracted before the fit (S - kB) |
| Co-57 | 136.47 | 0.077602 | 2.14 | yes | background subtracted before the fit (S - kB) |
| Ce-139 | 165.86 | 0.074122 | 2.00 | yes | background subtracted before the fit (S - kB) |
| Sn-113 | 255.13 | 0.060351 | 4.33 | yes | background subtracted before the fit (S - kB) |
| Hg-203 | 279.19 | 0.05691 | 1.97 | yes | background subtracted before the fit (S - kB) |
| Sn-113 | 391.70 | 0.046778 | 1.99 | yes | background subtracted before the fit (S - kB) |
| Cs-134 | 563.25 | 0.027378 | 2.15 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Cs-134 | 569.33 | 0.027266 | 2.03 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Cs-134 | 604.72 | 0.029733 | 2.09 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Cs-137 | 661.66 | 0.034462 | 2.04 | yes | background subtracted before the fit (S - kB) |
| Cs-134 | 795.86 | 0.02546 | 2.08 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Cs-134 | 801.95 | 0.022955 | 4.93 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Mn-54 | 834.85 | 0.029832 | 2.15 | yes | background subtracted before the fit (S - kB) |
| Y-88 | 898.04 | 0.025868 | 2.10 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Zn-65 | 1115.54 | 0.025557 | 2.14 | yes | background subtracted before the fit (S - kB) |
| Cs-134 | 1365.18 | 0.027567 | 2.05 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Y-88 | 1836.06 | 0.01655 | 2.03 | yes | background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |

## Sensitivity variants (report only)

| Variant | Geometry | Spectrum | Nuclide | Ratio | z |
|---|---|---|---|---|---|
| S1 no summing correction | marinelli | maritsmall | Ba-133 | 0.946 | -0.40 |
| S1 no summing correction | marinelli | maritsmall | Co-60 | 0.832 | -1.35 |
| S1 no summing correction | marinelli | maritsmall | Eu-152 | 0.867 | -1.08 |
| S1 no summing correction | marinelli | maritsmall | Cr-51 | 0.998 | -0.02 |
| S1 no summing correction | marinelli | maritsmall | Na-22 | 0.716 | -2.61 |
| S1 no summing correction | marinelli | maritsmall60 | Ba-133 | 0.945 | -0.41 |
| S1 no summing correction | marinelli | maritsmall60 | Co-60 | 0.828 | -1.40 |
| S1 no summing correction | marinelli | maritsmall60 | Eu-152 | 0.871 | -1.04 |
| S1 no summing correction | marinelli | maritsmall60 | Cr-51 | 1.000 | 0.00 |
| S1 no summing correction | marinelli | maritsmall60 | Na-22 | 0.705 | -2.77 |
| S1 no summing correction | pillbox | PITBIG | Ba-133 | 0.915 | -0.22 |
| S1 no summing correction | pillbox | PITBIG | Co-60 | 0.839 | -0.46 |
| S1 no summing correction | pillbox | PITBIG | Eu-152 | 0.648 | -1.30 |
| S1 no summing correction | pillbox | PITBIG | Cr-51 | 0.965 | -0.09 |
| S1 no summing correction | pillbox | PITBIG | Na-22 | 0.715 | -0.96 |
| S1 no summing correction | pillbox | PITBIG60 | Ba-133 | 0.905 | -0.25 |
| S1 no summing correction | pillbox | PITBIG60 | Co-60 | 0.826 | -0.51 |
| S1 no summing correction | pillbox | PITBIG60 | Eu-152 | 0.637 | -1.36 |
| S1 no summing correction | pillbox | PITBIG60 | Cr-51 | 0.960 | -0.10 |
| S1 no summing correction | pillbox | PITBIG60 | Na-22 | 0.716 | -0.96 |
| S2 loglog model | marinelli | maritsmall | Ba-133 | 0.931 | -0.78 |
| S2 loglog model | marinelli | maritsmall | Co-60 | 0.947 | -0.56 |
| S2 loglog model | marinelli | maritsmall | Eu-152 | 0.919 | -0.93 |
| S2 loglog model | marinelli | maritsmall | Cr-51 | 0.973 | -0.29 |
| S2 loglog model | marinelli | maritsmall | Na-22 | 0.749 | -3.27 |
| S2 loglog model | marinelli | maritsmall60 | Ba-133 | 0.930 | -0.79 |
| S2 loglog model | marinelli | maritsmall60 | Co-60 | 0.942 | -0.62 |
| S2 loglog model | marinelli | maritsmall60 | Eu-152 | 0.922 | -0.88 |
| S2 loglog model | marinelli | maritsmall60 | Cr-51 | 0.976 | -0.26 |
| S2 loglog model | marinelli | maritsmall60 | Na-22 | 0.737 | -3.49 |
| S2 loglog model | pillbox | PITBIG | Ba-133 | 0.889 | -2.48 |
| S2 loglog model | pillbox | PITBIG | Co-60 | 0.872 | -2.81 |
| S2 loglog model | pillbox | PITBIG | Eu-152 | 0.778 | -5.38 |
| S2 loglog model | pillbox | PITBIG | Cr-51 | 0.904 | -2.12 |
| S2 loglog model | pillbox | PITBIG | Na-22 | 0.673 | -8.93 |
| S2 loglog model | pillbox | PITBIG60 | Ba-133 | 0.879 | -2.68 |
| S2 loglog model | pillbox | PITBIG60 | Co-60 | 0.859 | -3.13 |
| S2 loglog model | pillbox | PITBIG60 | Eu-152 | 0.888 | -2.40 |
| S2 loglog model | pillbox | PITBIG60 | Cr-51 | 0.899 | -2.24 |
| S2 loglog model | pillbox | PITBIG60 | Na-22 | 0.673 | -8.87 |
| S3 maricsmall.chn start time | marinelli | maritsmall | Ba-133 | 0.986 | -0.34 |
| S3 maricsmall.chn start time | marinelli | maritsmall | Co-60 | 0.978 | -0.48 |
| S3 maricsmall.chn start time | marinelli | maritsmall | Eu-152 | 0.913 | -2.31 |
| S3 maricsmall.chn start time | marinelli | maritsmall | Cr-51 | 1.033 | 0.80 |
| S3 maricsmall.chn start time | marinelli | maritsmall | Na-22 | 0.808 | -4.89 |
| S3 maricsmall.chn start time | marinelli | maritsmall60 | Ba-133 | 0.985 | -0.37 |
| S3 maricsmall.chn start time | marinelli | maritsmall60 | Co-60 | 0.973 | -0.61 |
| S3 maricsmall.chn start time | marinelli | maritsmall60 | Eu-152 | 0.916 | -2.19 |
| S3 maricsmall.chn start time | marinelli | maritsmall60 | Cr-51 | 1.036 | 0.85 |
| S3 maricsmall.chn start time | marinelli | maritsmall60 | Na-22 | 0.795 | -5.40 |
| S4 certificate time read as EST | marinelli | maritsmall | Ba-133 | 0.960 | -1.06 |
| S4 certificate time read as EST | marinelli | maritsmall | Co-60 | 0.973 | -0.64 |
| S4 certificate time read as EST | marinelli | maritsmall | Eu-152 | 0.908 | -2.58 |
| S4 certificate time read as EST | marinelli | maritsmall | Cr-51 | 1.010 | 0.27 |
| S4 certificate time read as EST | marinelli | maritsmall | Na-22 | 0.803 | -5.27 |
| S4 certificate time read as EST | marinelli | maritsmall60 | Ba-133 | 0.959 | -1.08 |
| S4 certificate time read as EST | marinelli | maritsmall60 | Co-60 | 0.968 | -0.77 |
| S4 certificate time read as EST | marinelli | maritsmall60 | Eu-152 | 0.911 | -2.44 |
| S4 certificate time read as EST | marinelli | maritsmall60 | Cr-51 | 1.013 | 0.33 |
| S4 certificate time read as EST | marinelli | maritsmall60 | Na-22 | 0.790 | -5.82 |
| S4 certificate time read as EST | pillbox | PITBIG | Ba-133 | 0.911 | -0.66 |
| S4 certificate time read as EST | pillbox | PITBIG | Co-60 | 0.862 | -1.06 |
| S4 certificate time read as EST | pillbox | PITBIG | Eu-152 | 0.681 | -3.09 |
| S4 certificate time read as EST | pillbox | PITBIG | Cr-51 | 0.945 | -0.39 |
| S4 certificate time read as EST | pillbox | PITBIG | Na-22 | 0.660 | -3.39 |
| S4 certificate time read as EST | pillbox | PITBIG60 | Ba-133 | 0.901 | -0.74 |
| S4 certificate time read as EST | pillbox | PITBIG60 | Co-60 | 0.849 | -1.18 |
| S4 certificate time read as EST | pillbox | PITBIG60 | Eu-152 | 0.669 | -3.25 |
| S4 certificate time read as EST | pillbox | PITBIG60 | Cr-51 | 0.940 | -0.43 |
| S4 certificate time read as EST | pillbox | PITBIG60 | Na-22 | 0.661 | -3.38 |

## S5: peak areas of mix2neq6 against the IRI reference (report only)

| Group | reduced chi2 | n |
|---|---|---|
| matches, high peaks (A/dA > 10) | 8.88 | 50 |
| matches, small peaks | — | 0 |
| misses | 2.83 | 103 |
| false hits | 55.91 | 3 |
| total | 5.79 | 156 |

# Certified reference materials: results

Protocol: `crm_validation_protocol.md`. Engine 1.6.0. Data: doi:10.5281/zenodo.23093533 (zip MD5 64aa9d4786c3e0a65a0355d563e75d09).

## Criteria (cylinder, log-log): 6 of 8 pass

| id | value | limit | status | detail |
|---|---|---|---|---|
| CRM.C1 | 1.000 | >= 0.9 | PASS | 19/19 pairs with |z| <= 2.58 |
| CRM.C2 | 1.000 | >= 0.8 | PASS | 19/19 pairs with |ratio - 1| <= 0.2 |
| CRM.C3.Ra-226 | 1.067 | in [0.9, 1.1] | PASS | median ratio of 5 pairs |
| CRM.C3.Ra-228 | 1.147 | in [0.9, 1.1] | FAIL | median ratio of 4 pairs |
| CRM.C3.Th-228 | 1.066 | in [0.9, 1.1] | PASS | median ratio of 4 pairs |
| CRM.C3.K-40 | 0.925 | in [0.9, 1.1] | PASS | median ratio of 3 pairs |
| CRM.C3.Cs-137 | 1.115 | in [0.9, 1.1] | FAIL | median ratio of 3 pairs |
| CRM.C4 | 0.933 | <= 2.0 | PASS | rms z of 19 pairs |

## Pairs (cylinder, log-log)

| ID | material | nuclide | ref Bq/kg | ours Bq/kg | ratio | z | lines | note |
|---|---|---|---|---|---|---|---|---|
| S018 | IAEA-312 | Ra-226 | 269 +- 9.4 | 293 +- 26 | 1.089 | +0.88 | 351.9 | via Pb-214/Bi-214: assumes Ra-226/Rn-222 equilibrium (sealed container >= 3-4 weeks); true-coincidence summing not corrected |
| S018 | IAEA-312 | Ra-228 | 370.8 +- 21 | 435.5 +- 38 | 1.174 | +1.48 | 911.2 | via Ac-228 (equilibrium Ra-228/Ac-228); true-coincidence summing not corrected |
| S018 | IAEA-312 | Th-228 | 370.8 +- 21 | 411.5 +- 42 | 1.110 | +0.86 | 238.6 | via Pb-212 / Tl-208 (equilibrium Th-228 daughters); true-coincidence summing not corrected |
| S021 | IAEA-312 | Ra-226 | 269 +- 9.4 | 286.9 +- 25 | 1.067 | +0.67 | 351.9 | via Pb-214/Bi-214: assumes Ra-226/Rn-222 equilibrium (sealed container >= 3-4 weeks); true-coincidence summing not corrected |
| S021 | IAEA-312 | Ra-228 | 370.8 +- 21 | 436.3 +- 38 | 1.177 | +1.50 | 911.2 | via Ac-228 (equilibrium Ra-228/Ac-228); true-coincidence summing not corrected |
| S021 | IAEA-312 | Th-228 | 370.8 +- 21 | 411.1 +- 42 | 1.109 | +0.85 | 238.6 | via Pb-212 / Tl-208 (equilibrium Th-228 daughters); true-coincidence summing not corrected |
| S047 | IAEA-375 | Ra-226 | 20 +- 1 | 22.77 +- 2.2 | 1.139 | +1.13 | 351.9 | via Pb-214/Bi-214: assumes Ra-226/Rn-222 equilibrium (sealed container >= 3-4 weeks); true-coincidence summing not corrected |
| S047 | IAEA-375 | Ra-228 | 20.5 +- 0.69 | 22.94 +- 2.2 | 1.119 | +1.05 | 911.2 | via Ac-228 (equilibrium Ra-228/Ac-228); true-coincidence summing not corrected |
| S047 | IAEA-375 | Th-228 | 21 +- 2 | 20.13 +- 1.9 | 0.958 | -0.31 | 238.6 | via Pb-212 / Tl-208 (equilibrium Th-228 daughters); true-coincidence summing not corrected |
| S047 | IAEA-375 | K-40 | 424 +- 3.8 | 391.4 +- 35 | 0.923 | -0.93 | 1460.8 |  |
| S047 | IAEA-375 | Cs-137 | 3030 +- 23 | 3379 +- 2.9e+02 | 1.115 | +1.19 | 661.7 |  |
| S059 | IAEA-434 | Ra-226 | 780 +- 32 | 725.2 +- 64 | 0.930 | -0.77 | 351.9 | via Pb-214/Bi-214: assumes Ra-226/Rn-222 equilibrium (sealed container >= 3-4 weeks); true-coincidence summing not corrected |
| S067 | IAEA-444 | Cs-137 | 56.58 +- 1.2 | 62.77 +- 5.5 | 1.109 | +1.10 | 661.7 |  |
| S086 | IAEA-SL-2 | K-40 | 240 +- 12 | 222.1 +- 20 | 0.925 | -0.76 | 1460.8 |  |
| S086 | IAEA-SL-2 | Cs-137 (detection check) | 1.202 +- 0.077 | 0.7322 +- 0.15 | 0.609 | -2.83 | 661.7 |  |
| S332 | IAEA-447 | Ra-226 | 26 +- 2 | 24.33 +- 2.3 | 0.936 | -0.55 | 351.9 | via Pb-214/Bi-214: assumes Ra-226/Rn-222 equilibrium (sealed container >= 3-4 weeks); true-coincidence summing not corrected |
| S332 | IAEA-447 | Ra-228 | 37 +- 2 | 40.07 +- 3.8 | 1.083 | +0.72 | 911.2 | via Ac-228 (equilibrium Ra-228/Ac-228); true-coincidence summing not corrected |
| S332 | IAEA-447 | Th-228 | 37 +- 1.5 | 37.85 +- 3.8 | 1.023 | +0.21 | 238.6 | via Pb-212 / Tl-208 (equilibrium Th-228 daughters); true-coincidence summing not corrected |
| S332 | IAEA-447 | K-40 | 550 +- 20 | 546.9 +- 49 | 0.994 | -0.06 | 1460.8 |  |
| S332 | IAEA-447 | Cs-137 | 368.3 +- 8.7 | 412.2 +- 36 | 1.119 | +1.19 | 661.7 |  |

## Calibration (cylinder, log-log)

Model `loglog`, order 4, chi^2/dof = 704.68/29, model error 8.32 %, range 209-2615 keV. orders chosen by leave-one-out cross-validation (mean squared normalised prediction error 25.11)

| line | keV | eps | u % | used | residual % | note |
|---|---|---|---|---|---|---|
| Ac-228 | 209.3 | 0.03432 | 2.2 | yes | -5.3 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Pb-212 | 238.6 | 0.03457 | 1.6 | yes | +1.0 | RGTh-1 S136; background subtracted before the fit (S - kB) |
| Pb-214 | 242.0 | 0.03447 | 0.8 | yes | +1.5 | RGU-1 S189; background subtracted before the fit (S - kB) |
| Ac-228 | 270.2 | 0.02782 | 2.1 | yes | -11.5 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 277.4 | 0.02526 | 4.9 | yes | -18.0 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Pb-214 | 295.2 | 0.02957 | 0.8 | yes | +1.3 | RGU-1 S189; background subtracted before the fit (S - kB) |
| Pb-212 | 300.1 | 0.02552 | 1.8 | yes | -11.3 | RGTh-1 S136; background subtracted before the fit (S - kB) |
| Ac-228 | 328.0 | 0.02518 | 4.3 | yes | -4.8 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 338.3 | 0.02512 | 2.0 | yes | -2.1 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Pb-214 | 351.9 | 0.02567 | 0.9 | yes | +4.1 | RGU-1 S189; background subtracted before the fit (S - kB) |
| Ac-228 | 463.0 | 0.01797 | 2.0 | yes | -3.5 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 510.8 | 0.01528 | 1.8 | yes | -9.5 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 583.2 | 0.01440 | 1.2 | yes | -3.4 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 609.3 | 0.01451 | 0.7 | yes | +1.2 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-212 | 727.3 | 0.01434 | 1.9 | yes | +15.5 | RGTh-1 S136; background subtracted before the fit (S - kB) |
| Bi-214 | 768.4 | 0.01191 | 0.9 | yes | -0.1 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 794.9 | 0.01149 | 2.2 | yes | -1.3 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 860.6 | 0.01169 | 1.5 | yes | +5.9 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 911.2 | 0.01142 | 2.0 | yes | +7.3 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 934.1 | 0.00983 | 1.6 | yes | -6.3 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 964.8 | 0.01018 | 2.8 | yes | -1.0 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 969.0 | 0.01083 | 2.3 | yes | +5.6 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1120.3 | 0.00903 | 1.0 | yes | -4.4 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1238.1 | 0.00842 | 0.9 | yes | -5.9 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1377.7 | 0.00884 | 1.3 | yes | +4.9 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1408.0 | 0.00736 | 1.5 | yes | -11.5 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| K-40 | 1460.8 | 0.00810 | 2.0 | yes | -0.4 | RGK-1 S112; background subtracted before the fit (S - kB) |
| Bi-214 | 1509.2 | 0.00757 | 2.1 | yes | -5.0 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 1588.2 | 0.00742 | 3.1 | yes | -3.7 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1729.6 | 0.00848 | 1.5 | yes | +17.0 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1764.5 | 0.00711 | 1.3 | yes | -0.3 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1847.4 | 0.00739 | 1.5 | yes | +7.7 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 2204.1 | 0.00569 | 1.5 | yes | -0.6 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 2614.5 | 0.00418 | 1.8 | yes | -6.0 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |

Warnings: Ac-228 270.2 keV: -11.5 % from the curve (-6.1 sigma) - check interferences, summing and the peak fit; Tl-208 277.4 keV: -18.0 % from the curve (-4.5 sigma) - check interferences, summing and the peak fit; Pb-212 300.1 keV: -11.3 % from the curve (-7.2 sigma) - check interferences, summing and the peak fit; Pb-214 351.9 keV: +4.1 % from the curve (+4.2 sigma) - check interferences, summing and the peak fit; Tl-208 510.8 keV: -9.5 % from the curve (-6.0 sigma) - check interferences, summing and the peak fit; Tl-208 583.2 keV: -3.4 % from the curve (-3.1 sigma) - check interferences, summing and the peak fit; Bi-212 727.3 keV: +15.5 % from the curve (+7.3 sigma) - check interferences, summing and the peak fit; Tl-208 860.6 keV: +5.9 % from the curve (+3.6 sigma) - check interferences, summing and the peak fit; Ac-228 911.2 keV: +7.3 % from the curve (+3.3 sigma) - check interferences, summing and the peak fit; Bi-214 934.1 keV: -6.3 % from the curve (-4.2 sigma) - check interferences, summing and the peak fit; Bi-214 1120.3 keV: -4.4 % from the curve (-4.8 sigma) - check interferences, summing and the peak fit; Bi-214 1238.1 keV: -5.9 % from the curve (-7.0 sigma) - check interferences, summing and the peak fit; Bi-214 1377.7 keV: +4.9 % from the curve (+3.7 sigma) - check interferences, summing and the peak fit; Bi-214 1408.0 keV: -11.5 % from the curve (-8.6 sigma) - check interferences, summing and the peak fit; Bi-214 1729.6 keV: +17.0 % from the curve (+10.0 sigma) - check interferences, summing and the peak fit; Bi-214 1847.4 keV: +7.7 % from the curve (+4.9 sigma) - check interferences, summing and the peak fit; Tl-208 2614.5 keV: -6.0 % from the curve (-3.5 sigma) - check interferences, summing and the peak fit

## Lines (cylinder, log-log)

| ID | nuclide | line | keV | found | net | eff | c (line) Bq/kg | ref | note |
|---|---|---|---|---|---|---|---|---|---|
| S018 | Ra-226 | Pb-214 | 351.9 | yes | 33224 +- 208 | 0.02467 | 293 | 269 |  |
| S018 | Ra-226 | Bi-214 | 609.3 | yes | 24000 +- 173 | 0.01434 | 286.2 | 269 |  |
| S018 | Ra-226 | Pb-214 | 295.2 | yes | 19811 +- 227 | 0.02919 | 285.5 | 269 |  |
| S018 | Ra-226 | Bi-214 | 1764.5 | yes | 3846 +- 91 | 0.00713 | 274 | 269 |  |
| S018 | Ra-228 | Ac-228 | 911.2 | yes | 15392 +- 176 | 0.01064 | 435.5 | 370.8 |  |
| S018 | Ra-228 | Ac-228 | 969.0 | yes | 8970 +- 108 | 0.01026 | 430.1 | 370.8 |  |
| S018 | Th-228 | Pb-212 | 238.6 | yes | 79015 +- 4000 | 0.03424 | 411.5 | 370.8 |  |
| S018 | Th-228 | Tl-208 | 583.2 | yes | 23194 +- 168 | 0.01491 | 395.9 | 370.8 |  |
| S021 | Ra-226 | Pb-214 | 351.9 | yes | 32535 +- 247 | 0.02467 | 286.9 | 269 |  |
| S021 | Ra-226 | Bi-214 | 609.3 | yes | 23708 +- 199 | 0.01434 | 282.7 | 269 |  |
| S021 | Ra-226 | Pb-214 | 295.2 | yes | 19461 +- 183 | 0.02919 | 280.5 | 269 |  |
| S021 | Ra-226 | Bi-214 | 1764.5 | yes | 3829 +- 69 | 0.00713 | 272.7 | 269 |  |
| S021 | Ra-228 | Ac-228 | 911.2 | yes | 15420 +- 142 | 0.01064 | 436.3 | 370.8 |  |
| S021 | Ra-228 | Ac-228 | 969.0 | yes | 9052 +- 116 | 0.01026 | 434 | 370.8 |  |
| S021 | Th-228 | Pb-212 | 238.6 | yes | 78928 +- 4018 | 0.03424 | 411.1 | 370.8 |  |
| S021 | Th-228 | Tl-208 | 583.2 | yes | 23072 +- 170 | 0.01491 | 393.8 | 370.8 |  |
| S047 | Ra-226 | Pb-214 | 351.9 | yes | 3163 +- 139 | 0.02467 | 22.77 | 20 |  |
| S047 | Ra-226 | Bi-214 | 609.3 | yes | 2210 +- 88 | 0.01434 | 21.51 | 20 |  |
| S047 | Ra-226 | Pb-214 | 295.2 | yes | 1906 +- 130 | 0.02919 | 22.42 | 20 |  |
| S047 | Ra-226 | Bi-214 | 1764.5 | yes | 320 +- 26 | 0.00713 | 18.62 | 20 |  |
| S047 | Ra-228 | Ac-228 | 911.2 | yes | 993 +- 41 | 0.01064 | 22.94 | 20.5 |  |
| S047 | Ra-228 | Ac-228 | 969.0 | yes | 595 +- 34 | 0.01026 | 23.3 | 20.5 |  |
| S047 | Th-228 | Pb-212 | 238.6 | yes | 4735 +- 171 | 0.03424 | 20.13 | 21 |  |
| S047 | Th-228 | Tl-208 | 583.2 | yes | 1547 +- 72 | 0.01491 | 21.56 | 21 |  |
| S047 | K-40 | K-40 | 1460.8 | yes | 5351 +- 83 | 0.00813 | 391.4 | 424 |  |
| S047 | Cs-137 | Cs-137 | 661.7 | yes | 606480 +- 4407 | 0.01337 | 3379 | 3030 |  |
| S059 | Ra-226 | Pb-214 | 351.9 | yes | 48281 +- 322 | 0.02467 | 725.2 | 780 |  |
| S059 | Ra-226 | Bi-214 | 609.3 | yes | 34398 +- 291 | 0.01434 | 698.6 | 780 |  |
| S059 | Ra-226 | Pb-214 | 295.2 | yes | 28989 +- 185 | 0.02919 | 711.6 | 780 |  |
| S059 | Ra-226 | Bi-214 | 1764.5 | yes | 5459 +- 78 | 0.00713 | 662.3 | 780 |  |
| S067 | Cs-137 | Cs-137 | 661.7 | yes | 9169 +- 147 | 0.01337 | 62.77 | 56.58 |  |
| S086 | K-40 | K-40 | 1460.8 | yes | 3139 +- 67 | 0.00813 | 222.1 | 240 |  |
| S086 | Cs-137 | Cs-137 | 661.7 | yes | 136 +- 25 | 0.01337 | 0.7322 | 1.202 |  |
| S332 | Ra-226 | Pb-214 | 351.9 | yes | 2707 +- 88 | 0.02467 | 24.33 | 26 |  |
| S332 | Ra-226 | Bi-214 | 609.3 | yes | 1768 +- 60 | 0.01434 | 21.48 | 26 |  |
| S332 | Ra-226 | Pb-214 | 295.2 | yes | 1546 +- 66 | 0.02919 | 22.71 | 26 |  |
| S332 | Ra-226 | Bi-214 | 1764.5 | yes | 268 +- 24 | 0.00713 | 19.47 | 26 |  |
| S332 | Ra-228 | Ac-228 | 911.2 | yes | 1390 +- 47 | 0.01064 | 40.07 | 37 |  |
| S332 | Ra-228 | Ac-228 | 969.0 | yes | 877 +- 39 | 0.01026 | 42.87 | 37 |  |
| S332 | Th-228 | Pb-212 | 238.6 | yes | 7131 +- 321 | 0.03424 | 37.85 | 37 |  |
| S332 | Th-228 | Tl-208 | 583.2 | yes | 2001 +- 61 | 0.01491 | 34.8 | 37 |  |
| S332 | K-40 | K-40 | 1460.8 | yes | 5989 +- 86 | 0.00813 | 546.9 | 550 |  |
| S332 | Cs-137 | Cs-137 | 661.7 | yes | 59244 +- 275 | 0.01337 | 412.2 | 368.3 |  |

## Report: cylinder, two-branch model

Criteria values (not criteria here): CRM.C1 1.000; CRM.C2 1.000; CRM.C3.Ra-226 1.056; CRM.C3.Ra-228 1.116; CRM.C3.Th-228 1.063; CRM.C3.K-40 0.960; CRM.C3.Cs-137 1.089; CRM.C4 0.752

| ID | material | nuclide | ref Bq/kg | ours Bq/kg | ratio | z | lines | note |
|---|---|---|---|---|---|---|---|---|
| S018 | IAEA-312 | Ra-226 | 269 +- 9.4 | 290.2 +- 27 | 1.079 | +0.73 | 351.9 | via Pb-214/Bi-214: assumes Ra-226/Rn-222 equilibrium (sealed container >= 3-4 weeks); true-coincidence summing not corrected |
| S018 | IAEA-312 | Ra-228 | 370.8 +- 21 | 423.9 +- 39 | 1.143 | +1.20 | 911.2 | via Ac-228 (equilibrium Ra-228/Ac-228); true-coincidence summing not corrected |
| S018 | IAEA-312 | Th-228 | 370.8 +- 21 | 410.3 +- 44 | 1.107 | +0.81 | 238.6 | via Pb-212 / Tl-208 (equilibrium Th-228 daughters); true-coincidence summing not corrected |
| S021 | IAEA-312 | Ra-226 | 269 +- 9.4 | 284.2 +- 27 | 1.056 | +0.53 | 351.9 | via Pb-214/Bi-214: assumes Ra-226/Rn-222 equilibrium (sealed container >= 3-4 weeks); true-coincidence summing not corrected |
| S021 | IAEA-312 | Ra-228 | 370.8 +- 21 | 424.7 +- 39 | 1.145 | +1.21 | 911.2 | via Ac-228 (equilibrium Ra-228/Ac-228); true-coincidence summing not corrected |
| S021 | IAEA-312 | Th-228 | 370.8 +- 21 | 409.9 +- 44 | 1.105 | +0.80 | 238.6 | via Pb-212 / Tl-208 (equilibrium Th-228 daughters); true-coincidence summing not corrected |
| S047 | IAEA-375 | Ra-226 | 20 +- 1 | 22.55 +- 2.3 | 1.128 | +1.00 | 351.9 | via Pb-214/Bi-214: assumes Ra-226/Rn-222 equilibrium (sealed container >= 3-4 weeks); true-coincidence summing not corrected |
| S047 | IAEA-375 | Ra-228 | 20.5 +- 0.69 | 22.33 +- 2.2 | 1.089 | +0.78 | 911.2 | via Ac-228 (equilibrium Ra-228/Ac-228); true-coincidence summing not corrected |
| S047 | IAEA-375 | Th-228 | 21 +- 2 | 20.07 +- 2 | 0.956 | -0.32 | 238.6 | via Pb-212 / Tl-208 (equilibrium Th-228 daughters); true-coincidence summing not corrected |
| S047 | IAEA-375 | K-40 | 424 +- 3.8 | 406 +- 38 | 0.958 | -0.47 | 1460.8 |  |
| S047 | IAEA-375 | Cs-137 | 3030 +- 23 | 3299 +- 3e+02 | 1.089 | +0.89 | 661.7 |  |
| S059 | IAEA-434 | Ra-226 | 780 +- 32 | 718.2 +- 67 | 0.921 | -0.83 | 351.9 | via Pb-214/Bi-214: assumes Ra-226/Rn-222 equilibrium (sealed container >= 3-4 weeks); true-coincidence summing not corrected |
| S067 | IAEA-444 | Cs-137 | 56.58 +- 1.2 | 61.27 +- 5.7 | 1.083 | +0.81 | 661.7 |  |
| S086 | IAEA-SL-2 | K-40 | 240 +- 12 | 230.4 +- 22 | 0.960 | -0.38 | 1460.8 |  |
| S086 | IAEA-SL-2 | Cs-137 (detection check) | 1.202 +- 0.077 | 0.7147 +- 0.15 | 0.595 | -2.97 | 661.7 |  |
| S332 | IAEA-447 | Ra-226 | 26 +- 2 | 24.1 +- 2.4 | 0.927 | -0.61 | 351.9 | via Pb-214/Bi-214: assumes Ra-226/Rn-222 equilibrium (sealed container >= 3-4 weeks); true-coincidence summing not corrected |
| S332 | IAEA-447 | Ra-228 | 37 +- 2 | 39.01 +- 3.8 | 1.054 | +0.47 | 911.2 | via Ac-228 (equilibrium Ra-228/Ac-228); true-coincidence summing not corrected |
| S332 | IAEA-447 | Th-228 | 37 +- 1.5 | 37.74 +- 4 | 1.020 | +0.17 | 238.6 | via Pb-212 / Tl-208 (equilibrium Th-228 daughters); true-coincidence summing not corrected |
| S332 | IAEA-447 | K-40 | 550 +- 20 | 567.4 +- 53 | 1.032 | +0.31 | 1460.8 |  |
| S332 | IAEA-447 | Cs-137 | 368.3 +- 8.7 | 402.3 +- 37 | 1.092 | +0.90 | 661.7 |  |

Model `two_branch`, order 2/1, crossover 486.3 keV, chi^2/dof = 855.95/30, model error 8.82 %, range 209-2615 keV. orders chosen by leave-one-out cross-validation (mean squared normalised prediction error 28.63)

| line | keV | eps | u % | used | residual % | note |
|---|---|---|---|---|---|---|
| Ac-228 | 209.3 | 0.03432 | 2.2 | yes | -7.3 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Pb-212 | 238.6 | 0.03457 | 1.6 | yes | +0.7 | RGTh-1 S136; background subtracted before the fit (S - kB) |
| Pb-214 | 242.0 | 0.03447 | 0.8 | yes | +1.3 | RGU-1 S189; background subtracted before the fit (S - kB) |
| Ac-228 | 270.2 | 0.02782 | 2.1 | yes | -11.6 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 277.4 | 0.02526 | 4.9 | yes | -18.1 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Pb-214 | 295.2 | 0.02957 | 0.8 | yes | +0.8 | RGU-1 S189; background subtracted before the fit (S - kB) |
| Pb-212 | 300.1 | 0.02552 | 1.8 | yes | -11.8 | RGTh-1 S136; background subtracted before the fit (S - kB) |
| Ac-228 | 328.0 | 0.02518 | 4.3 | yes | -5.7 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 338.3 | 0.02512 | 2.0 | yes | -3.0 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Pb-214 | 351.9 | 0.02567 | 0.9 | yes | +3.1 | RGU-1 S189; background subtracted before the fit (S - kB) |
| Ac-228 | 463.0 | 0.01797 | 2.0 | yes | -1.0 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 510.8 | 0.01528 | 1.8 | yes | -7.1 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 583.2 | 0.01440 | 1.2 | yes | -3.9 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 609.3 | 0.01451 | 0.7 | yes | -0.1 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-212 | 727.3 | 0.01434 | 1.9 | yes | +11.9 | RGTh-1 S136; background subtracted before the fit (S - kB) |
| Bi-214 | 768.4 | 0.01191 | 0.9 | yes | -3.4 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 794.9 | 0.01149 | 2.2 | yes | -4.5 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 860.6 | 0.01169 | 1.5 | yes | +2.7 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 911.2 | 0.01142 | 2.0 | yes | +4.4 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 934.1 | 0.00983 | 1.6 | yes | -8.5 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 964.8 | 0.01018 | 2.8 | yes | -3.1 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 969.0 | 0.01083 | 2.3 | yes | +3.5 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1120.3 | 0.00903 | 1.0 | yes | -4.5 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1238.1 | 0.00842 | 0.9 | yes | -4.4 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1377.7 | 0.00884 | 1.3 | yes | +8.1 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1408.0 | 0.00736 | 1.5 | yes | -8.5 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| K-40 | 1460.8 | 0.00810 | 2.0 | yes | +3.4 | RGK-1 S112; background subtracted before the fit (S - kB) |
| Bi-214 | 1509.2 | 0.00757 | 2.1 | yes | -1.2 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 1588.2 | 0.00742 | 3.1 | yes | +0.4 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1729.6 | 0.00848 | 1.5 | yes | +21.8 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1764.5 | 0.00711 | 1.3 | yes | +3.6 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1847.4 | 0.00739 | 1.5 | yes | +11.3 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 2204.1 | 0.00569 | 1.5 | yes | -3.1 | RGU-1 S189; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 2614.5 | 0.00418 | 1.8 | yes | -19.6 | RGTh-1 S136; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |

Warnings: Ac-228 209.3 keV: -7.3 % from the curve (-3.5 sigma) - check interferences, summing and the peak fit; Ac-228 270.2 keV: -11.6 % from the curve (-6.2 sigma) - check interferences, summing and the peak fit; Tl-208 277.4 keV: -18.1 % from the curve (-4.6 sigma) - check interferences, summing and the peak fit; Pb-212 300.1 keV: -11.8 % from the curve (-7.6 sigma) - check interferences, summing and the peak fit; Pb-214 351.9 keV: +3.1 % from the curve (+3.2 sigma) - check interferences, summing and the peak fit; Tl-208 510.8 keV: -7.1 % from the curve (-4.3 sigma) - check interferences, summing and the peak fit; Tl-208 583.2 keV: -3.9 % from the curve (-3.5 sigma) - check interferences, summing and the peak fit; Bi-212 727.3 keV: +11.9 % from the curve (+5.7 sigma) - check interferences, summing and the peak fit; Bi-214 768.4 keV: -3.4 % from the curve (-3.7 sigma) - check interferences, summing and the peak fit; Bi-214 934.1 keV: -8.5 % from the curve (-5.9 sigma) - check interferences, summing and the peak fit; Bi-214 1120.3 keV: -4.5 % from the curve (-4.8 sigma) - check interferences, summing and the peak fit; Bi-214 1238.1 keV: -4.4 % from the curve (-5.2 sigma) - check interferences, summing and the peak fit; Bi-214 1377.7 keV: +8.1 % from the curve (+5.9 sigma) - check interferences, summing and the peak fit; Bi-214 1408.0 keV: -8.5 % from the curve (-6.2 sigma) - check interferences, summing and the peak fit; Bi-214 1729.6 keV: +21.8 % from the curve (+12.3 sigma) - check interferences, summing and the peak fit; Bi-214 1847.4 keV: +11.3 % from the curve (+6.9 sigma) - check interferences, summing and the peak fit; Tl-208 2614.5 keV: -19.6 % from the curve (-13.2 sigma) - check interferences, summing and the peak fit

## Report: Marinelli, log-log

Criteria values (not criteria here): CRM.C1 1.000; CRM.C2 0.500; CRM.C4 1.277

| ID | material | nuclide | ref Bq/kg | ours Bq/kg | ratio | z | lines | note |
|---|---|---|---|---|---|---|---|---|
| S080 | IAEA-SL-2 | K-40 | 240 +- 12 | 239.5 +- 25 | 0.998 | -0.02 | 1460.8 |  |
| S080 | IAEA-SL-2 | Cs-137 | 1.219 +- 0.078 | 1.562 +- 0.17 | 1.281 | +1.81 | 661.7 |  |

Model `loglog`, order 4, chi^2/dof = 1433.01/29, model error 9.96 %, range 209-2615 keV. orders chosen by leave-one-out cross-validation (mean squared normalised prediction error 49.98)

| line | keV | eps | u % | used | residual % | note |
|---|---|---|---|---|---|---|
| Ac-228 | 209.3 | 0.04243 | 2.1 | yes | -2.8 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Pb-212 | 238.6 | 0.04292 | 1.5 | yes | +2.7 | RGTh-1 S131; background subtracted before the fit (S - kB) |
| Pb-214 | 242.0 | 0.04236 | 0.7 | yes | +2.1 | RGU-1 S180; background subtracted before the fit (S - kB) |
| Ac-228 | 270.2 | 0.03349 | 2.0 | yes | -13.3 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 277.4 | 0.03047 | 4.7 | yes | -19.6 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Pb-214 | 295.2 | 0.03645 | 0.8 | yes | +1.4 | RGU-1 S180; background subtracted before the fit (S - kB) |
| Pb-212 | 300.1 | 0.03138 | 1.8 | yes | -11.4 | RGTh-1 S131; background subtracted before the fit (S - kB) |
| Ac-228 | 328.0 | 0.03065 | 4.2 | yes | -6.0 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 338.3 | 0.03087 | 2.5 | yes | -2.3 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Pb-214 | 351.9 | 0.03180 | 1.1 | yes | +4.7 | RGU-1 S180; background subtracted before the fit (S - kB) |
| Ac-228 | 463.0 | 0.02222 | 1.9 | yes | -2.3 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 510.8 | 0.01855 | 2.0 | yes | -9.8 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 583.2 | 0.01793 | 1.1 | yes | -0.8 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 609.3 | 0.01769 | 0.7 | yes | +1.8 | RGU-1 S180; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-212 | 727.3 | 0.01831 | 1.8 | yes | +22.1 | RGTh-1 S131; background subtracted before the fit (S - kB) |
| Bi-214 | 768.4 | 0.01437 | 0.9 | yes | -0.2 | RGU-1 S180; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 794.9 | 0.01428 | 2.0 | yes | +1.6 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 860.6 | 0.01462 | 1.4 | yes | +9.7 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 911.2 | 0.01445 | 2.0 | yes | +12.3 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 934.1 | 0.01209 | 0.9 | yes | -4.6 | RGU-1 S180; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 964.8 | 0.01272 | 2.4 | yes | +2.3 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 969.0 | 0.01370 | 2.2 | yes | +10.4 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1120.3 | 0.01104 | 0.8 | yes | -3.8 | RGU-1 S180; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1238.1 | 0.01027 | 0.6 | yes | -5.7 | RGU-1 S180; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1377.7 | 0.01105 | 0.9 | yes | +7.4 | RGU-1 S180; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1408.0 | 0.00921 | 0.9 | yes | -9.5 | RGU-1 S180; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| K-40 | 1460.8 | 0.01009 | 1.8 | yes | +1.3 | RGK-1 S104; background subtracted before the fit (S - kB) |
| Bi-214 | 1509.2 | 0.00899 | 1.0 | yes | -8.0 | RGU-1 S180; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Ac-228 | 1588.2 | 0.00960 | 2.9 | yes | +1.4 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1729.6 | 0.01061 | 1.2 | yes | +19.0 | RGU-1 S180; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1764.5 | 0.00880 | 1.0 | yes | +0.1 | RGU-1 S180; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 1847.4 | 0.00939 | 1.0 | yes | +10.9 | RGU-1 S180; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Bi-214 | 2204.1 | 0.00715 | 1.0 | yes | +1.4 | RGU-1 S180; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |
| Tl-208 | 2614.5 | 0.00515 | 1.5 | yes | -5.5 | RGTh-1 S131; background subtracted before the fit (S - kB); cascade emitter: true-coincidence summing not corrected (biased in close geometries) |

Warnings: Pb-214 242.0 keV: +2.1 % from the curve (+3.0 sigma) - check interferences, summing and the peak fit; Ac-228 270.2 keV: -13.3 % from the curve (-7.6 sigma) - check interferences, summing and the peak fit; Tl-208 277.4 keV: -19.6 % from the curve (-5.2 sigma) - check interferences, summing and the peak fit; Pb-212 300.1 keV: -11.4 % from the curve (-7.3 sigma) - check interferences, summing and the peak fit; Pb-214 351.9 keV: +4.7 % from the curve (+4.0 sigma) - check interferences, summing and the peak fit; Tl-208 510.8 keV: -9.8 % from the curve (-5.4 sigma) - check interferences, summing and the peak fit; Bi-212 727.3 keV: +22.1 % from the curve (+10.3 sigma) - check interferences, summing and the peak fit; Tl-208 860.6 keV: +9.7 % from the curve (+6.5 sigma) - check interferences, summing and the peak fit; Ac-228 911.2 keV: +12.3 % from the curve (+5.5 sigma) - check interferences, summing and the peak fit; Bi-214 934.1 keV: -4.6 % from the curve (-5.6 sigma) - check interferences, summing and the peak fit; Ac-228 969.0 keV: +10.4 % from the curve (+4.2 sigma) - check interferences, summing and the peak fit; Bi-214 1120.3 keV: -3.8 % from the curve (-4.9 sigma) - check interferences, summing and the peak fit; Bi-214 1238.1 keV: -5.7 % from the curve (-9.5 sigma) - check interferences, summing and the peak fit; Bi-214 1377.7 keV: +7.4 % from the curve (+8.0 sigma) - check interferences, summing and the peak fit; Bi-214 1408.0 keV: -9.5 % from the curve (-11.9 sigma) - check interferences, summing and the peak fit; Bi-214 1509.2 keV: -8.0 % from the curve (-8.7 sigma) - check interferences, summing and the peak fit; Bi-214 1729.6 keV: +19.0 % from the curve (+12.8 sigma) - check interferences, summing and the peak fit; Bi-214 1847.4 keV: +10.9 % from the curve (+10.3 sigma) - check interferences, summing and the peak fit; Tl-208 2614.5 keV: -5.5 % from the curve (-4.0 sigma) - check interferences, summing and the peak fit

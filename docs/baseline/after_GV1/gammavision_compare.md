# Laboratory HPGe spectra compared with GammaVision reports (after_GV1)

Protocol: `docs/baseline/gammavision_compare_protocol.md`. Spectra outside the repository; derived numbers only.

**4 PASS / 2 FAIL**

| ID | result | detail |
|---|---|---|
| G1 | FAIL | 7/7 matched, max |dE| 0.115 keV |
| G2 | FAIL | 7/7 within limit, median ratio 0.9616 |
| G3 | PASS | 7/7 within 10 % |
| G4 | PASS | all identified |
| G5 | PASS | 0 narrow peak(s) at the oil-sample energies |
| G6 | PASS | identical |

## Sand sample 2: peaks

| nuclide | E GV | E SM | dE | area GV | area SM | ratio | limit | FWHM GV | FWHM SM | ratio |
|---|---|---|---|---|---|---|---|---|---|---|
| Pb-214 | 295.25 | 295.261 | +0.011 | 14771 | 14677 ± 0.97 % | 0.9936 | 0.050 | 1.054 | 1.038 | 0.9851 |
| Pb-214 | 352.0 | 352.015 | +0.015 | 25322 | 25157 ± 0.72 % | 0.9935 | 0.050 | 1.128 | 1.108 | 0.9826 |
| Tl-208 | 583.45 | 583.49 | +0.040 | 5335 | 5112 ± 1.71 % | 0.9582 | 0.060 | 1.206 | 1.225 | 1.0159 |
| Bi-214 | 609.61 | 609.636 | +0.026 | 19368 | 19019 ± 0.89 % | 0.9820 | 0.050 | 1.317 | 1.327 | 1.0075 |
| Ac-228 | 911.63 | 911.689 | +0.059 | 3619 | 3476 ± 2.39 % | 0.9604 | 0.072 | 1.467 | 1.568 | 1.0689 |
| K-40 | 1461.44 | 1461.549 | +0.109 | 25119 | 24154 ± 1.29 % | 0.9616 | 0.050 | 1.823 | 1.929 | 1.0583 |
| Bi-214 | 1765.26 | 1765.375 | +0.115 | 3269 | 3137 ± 2.17 % | 0.9596 | 0.059 | 1.955 | 2.093 | 1.0706 |

## All spectra

| file | live s | counts | peaks | nuclides |
|---|---|---|---|---|
| sand sample 2.Spc | 86217.76 | 1150951 | 100 | Pb-214, Bi-214, Ac-228, K-40, Bi-212, Cs-137, U-235, Tl-208, Pb-212, Th-231, Yb-169, Pa-234m |
| sand sample 2.An1 | 86217.76 | 1150951 | 100 | Pb-214, Bi-214, Ac-228, K-40, Bi-212, Cs-137, U-235, Tl-208, Pb-212, Th-231, Yb-169, Pa-234m |
| oil sample 1.An1 | 86359.28 | 22634 | 10 | Bi-214, Pb-214 |
| Oil sample 6.Spc | 86330.32 | 121864 | 34 | Pb-214, Th-234, Bi-214, K-40, Ac-228, Ra-226, As-74, Pb-212, Th-228, Pb-210, Mo-99, Tc-99m, Tl-208 |
| sludge sample 4.Spc | 86088.76 | 1527625 | 107 | Bi-214, Pb-214, K-40, Ac-228, Tl-208, Ra-226, Bi-212, Th-231, Cs-137, Pa-231, Pb-212, Yb-169, Pb-211 |
| Sludg Sample 7.Spc | 84645.82 | 43257591 | 217 | Bi-214, Pb-214, Ac-228, Tl-208, Bi-212, Th-228, Ra-226, Gd-153, Pb-212, Mn-56, Xe-133, Dy-165, Co-60, Cs-134, Ce-141, As-74 |
| SLUDG SAMPIL 13.Spc | 85890.82 | 10714329 | 189 | Ac-228, Bi-214, Pb-214, Tl-208, Ra-226, Bi-212, Pb-210, Th-228, Pb-212, Ce-141 |
| SLUDG SAMPIL 15.Spc | 86243.74 | 680115 | 92 | Pb-214, Bi-214, Ac-228, K-40, Tl-208, Th-234, Bi-212, Cs-137, U-235, Th-231, Pb-212, Pb-210, Be-7, Pa-234m, Pb-211 |
| Water  Sample 11.Spc | 86315.94 | 559598 | 89 | Pb-214, Ac-228, Bi-214, K-40, Ra-226, Tl-208, Pb-212, Ra-223 |

## Oil sample 1: SpectraMaster near the GammaVision energies

| GV keV | GV area | GV FWHM | SM peak |
|---|---|---|---|
| 186.03 | 111 | 0.197 | none (significance >= 3) |
| 295.21 | 137 | 0.236 | none (significance >= 3) |
| 352.18 | 138 | 0.475 | 352.35 keV, net 101, FWHM 1.184 keV, sig 4.2 |
| 1120.11 | 59 | 0.195 | 1119.772 keV, net 46, FWHM 1.68 keV, sig 3.0 |
| 1763.48 | 39 | 0.413 | 1763.644 keV, net 25, FWHM 2.003 keV, sig 3.3 |

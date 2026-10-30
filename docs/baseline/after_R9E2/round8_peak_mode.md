# Round-8 limits of a line without a sample peak, peak background mode (Gemini H2)

engine 1.34.0

| ID | value | result |
|---|---|---|
| RB8.C1 | hpge_bkg1500 currie 661.7 keV (linear): L_C 99.247 vs 99.247 counts; hpge_bkg1500 iso11929 661.7 keV (linear): L_C 99.247 vs 99.247 counts; hpge_bkg20000 currie 661.7 keV (linear): L_C 331.89 vs 331.89 counts; hpge_bkg20000 iso11929 661.7 keV (linear): L_C 331.89 vs 331.89 counts; hpge_nobkgpeak currie 661.7 keV (linear): L_C 41.485 vs 41.485 counts; hpge_nobkgpeak iso11929 661.7 keV (linear): L_C 41.485 vs 41.485 counts; hpge_bkg1500_blank currie 661.7 keV (linear): L_C 146.69 vs 146.69 counts; hpge_bkg1500_blank iso11929 661.7 keV (linear): L_C 146.69 vs 146.69 counts; nai_co60 currie 661.7 keV (quadratic): L_C 476.1 vs 476.1 counts; nai_co60 currie 1173.2 keV (linear): L_C 336.39 vs 336.39 counts; nai_co60 iso11929 661.7 keV (quadratic): L_C 476.1 vs 476.1 counts; nai_co60 iso11929 1173.2 keV (linear): L_C 336.39 vs 336.39 counts | PASS |
| RB8.C2 | primary result, its uncertainty, method and every other line field identical to before | PASS |
| RB8.C3 | nai_co60_peak_currie lines with a peak or not usable; nai_co60_peak_iso11929 lines with a peak or not usable | FAIL |
| RB8.C4 | mc_bkg1500: 396 results without a peak, false detections 0.0530, threshold ratio 0.9444; mc_bkg20000: 399 results without a peak, false detections 0.0526, threshold ratio 0.9397 | PASS |

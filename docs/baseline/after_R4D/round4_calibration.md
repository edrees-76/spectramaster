# Round-4 calibration and manual-fit findings (after_R4D)

Protocol: `docs/baseline/round4_calibration_protocol.md`. Synthetic spectra and the IAEA 2002 test spectra (names and coefficients only).

**4 PASS / 0 FAIL** (RD.C1-C4; RD.C5 is the test suite and the benchmark, reported in the protocol)

| ID | result | detail |
|---|---|---|
| RD.C1 | PASS | proposal 7 widths, refit without exclusion identical; without Eu-152 1112.08: 6 widths; proposal 8 widths, refit without exclusion identical; without Eu-152 1112.08: 7 widths; proposal 8 widths, refit without exclusion identical; without Eu-152 1085.84: 7 widths |
| RD.C2 | PASS | Gemini's case: None 'no FWHM calibration: the measured widths of L0 0.00, L1 1.00 decrease with energy or give a FWHM <= 0 (fit 6.389 keV at channel 0, -25.47 keV at channel 8191); check these lines for doublets' (before [6.388888888888888, -0.0038888888888888896], FWHM [-25.465000000000007, 6.388888888888888] keV); rising case [0.9571428571428573, 0.00021428571428571425]; quadratic case order 1 FWHM (0.24999999999999964, 6.8028) keV (before order 2, [-1.4319962000000623, 2.5124995631031886] keV) |
| RD.C3 | PASS | 20 source calibrations; FWHM changed: none; not allowed: none |
| RD.C4 | PASS | net spectrum: manual fit u 59.1470, explicit S + k2 B 59.1470 (before 83.1879, not-Poisson note True); Aptec strip: u 59.1470, explicit 59.1470 (before 83.1879); stale variance used {'smoothed': False, 'edited': False}; raw spectrum unchanged True |

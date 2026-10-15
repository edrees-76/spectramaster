# Aptec-style MultiFit: validation results (2026-10-15)

Protocol: `aptec_multifit_protocol.md` (written before these runs).  Method frozen after
development runs on seeds 0–49 (one change during development: an ROI with several significant
centroid guesses is treated as a multiplet even when its FWHM looks normal).  Validation run
once on seeds 1000–1199 (200 spectra per configuration).

| Configuration | both / all found | area bias % (low, high) | pull SD (low, high) | median reduced chi² |
|---|---|---|---|---|
| singlet | 0.995 | −0.43 | 1.052 | 1.16 |
| 0.8 FWHM, 1:1 | 0.185 | +0.14, −1.52 | 0.77, 0.66 | 15.5 |
| 0.8 FWHM, 3:1 | 0.030 | +4.01, −12.88 | 0.88, 0.46 | 8.8 |
| 1.0 FWHM, 1:1 | 0.995 | −0.16, −0.37 | 0.995, 1.012 | 1.07 |
| 1.0 FWHM, 3:1 | 0.945 | +0.51, −2.79 | 1.019, 1.165 | 1.09 |
| 1.5 FWHM, 1:1 | 1.000 | −0.36, −0.76 | 0.977, 0.984 | 1.10 |
| 1.5 FWHM, 3:1 | 0.995 | −0.12, −1.73 | 0.956, 0.996 | 1.12 |
| 2.0 FWHM, 1:1 | 1.000 | −0.36, −0.73 | 0.984, 0.939 | 1.09 |
| 2.0 FWHM, 3:1 | 1.000 | −0.32, −1.46 | 0.955, 0.903 | 1.10 |

Limits: singlet bias ≤ 1 % — **pass** (−0.43 %).  Separation ≥ 1.0 FWHM: found ≥ 90 % —
**pass** (94.5–100 %); component bias ≤ 3 % — **pass** (largest −2.79 %, the weak component
of the 3:1 doublet at 1.0 FWHM); pull SD 0.8–1.25 — **pass** (0.903–1.165).

At 0.8 FWHM the doublet is usually fitted as one peak (no limit was set; reported).  The
weaker component of unequal doublets is biased low by 1.5–2.8 %.  This validates the
implementation on ideal Gaussian peaks with the true resolution; it is not a comparison with
Aptec's MultiFit (no Aptec MultiFit result was available).

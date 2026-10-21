# Signed primary result: results

Protocol: `signed_primary_protocol.md`.

| id | value | limit | status |
|---|---|---|---|
| HPGe.PR.C1.mean_z | 0.0733 | abs <= 0.2 | PASS |
| HPGe.PR.C1.cov2 | 0.955 | in [0.91, 0.99] | PASS |
| HPGe.PR.C2.spectrum.mean_z | 0.126 | abs <= 0.3 | PASS |
| HPGe.PR.C2.spectrum.cov2 | 0.95 | >= 0.90 | PASS |
| HPGe.PR.C2.peak.mean_z | 0.4604 | abs <= 0.3 | FAIL |
| HPGe.PR.C2.peak.cov2 | 0.9167 | >= 0.90 | PASS |
| HPGe.PR.C3.s1.mean_z | -0.1173 | abs <= 0.3 | PASS |
| HPGe.PR.C3.s1.cov2 | 0.89 | in [0.90, 0.99] | FAIL |
| HPGe.PR.C3.s1.interval | 0.96 | >= 0.89 | PASS |
| HPGe.PR.C3.s2.mean_z | 0.06295 | abs <= 0.3 | PASS |
| HPGe.PR.C3.s2.cov2 | 0.95 | in [0.90, 0.99] | PASS |
| HPGe.PR.C3.s2.interval | 0.99 | >= 0.89 | PASS |
| HPGe.PR.C3.s3.mean_z | 0.2031 | abs <= 0.3 | PASS |
| HPGe.PR.C3.s3.cov2 | 0.98 | in [0.90, 0.99] | PASS |
| HPGe.PR.C3.s3.interval | 0.99 | >= 0.89 | PASS |
| HPGe.PR.C4.present | 0 | all | FAIL |
| HPGe.PR.C4.d2_detected | 0.56 | in [0.65, 0.92] | FAIL |
| HPGe.PR.C4.d1_le_d2 | 0.24 | <= D2 | PASS |
| HPGe.PR.C5.spectrum.negative | 20 | >= 18 of 20 | PASS |
| HPGe.PR.C5.spectrum.best | 20 | all | PASS |
| HPGe.PR.C5.spectrum.no_activity | 20 | all | PASS |
| HPGe.PR.C5.peak.negative | 20 | >= 18 of 20 | PASS |
| HPGe.PR.C5.peak.best | 20 | all | PASS |
| HPGe.PR.C5.peak.no_activity | 20 | all | PASS |
| HPGe.PR.C6.interfered | 50 | all 50 | PASS |
| HPGe.PR.C6.detected | 0 | 0 | PASS |
| HPGe.PR.C6.best | 0 | 0 | PASS |
| HPGe.PR.C7.false_detect | 0.05 | in [0.010, 0.090] | PASS |
| NaI.PR.C1.mean_z | -1.919 | abs <= 0.2 | FAIL |
| NaI.PR.C1.cov2 | 0.505 | in [0.91, 0.99] | FAIL |
| NaI.PR.C2.spectrum.mean_z | 0.1342 | abs <= 0.3 | PASS |
| NaI.PR.C2.spectrum.cov2 | 1 | >= 0.90 | PASS |
| NaI.PR.C2.peak.mean_z | -3.702 | abs <= 0.3 | FAIL |
| NaI.PR.C2.peak.cov2 | 0.025 | >= 0.90 | FAIL |
| NaI.PR.C3.s1.mean_z | -2.091 | abs <= 0.3 | FAIL |
| NaI.PR.C3.s1.cov2 | 0.41 | in [0.90, 0.99] | FAIL |
| NaI.PR.C3.s1.interval | 1 | >= 0.89 | PASS |
| NaI.PR.C3.s2.mean_z | -1.538 | abs <= 0.3 | FAIL |
| NaI.PR.C3.s2.cov2 | 0.51 | in [0.90, 0.99] | FAIL |
| NaI.PR.C3.s2.interval | 1 | >= 0.89 | PASS |
| NaI.PR.C3.s3.mean_z | -1.14 | abs <= 0.3 | FAIL |
| NaI.PR.C3.s3.cov2 | 0.61 | in [0.90, 0.99] | FAIL |
| NaI.PR.C3.s3.interval | 0.68 | >= 0.89 | FAIL |
| NaI.PR.C4.present | 1 | all | PASS |
| NaI.PR.C4.d2_detected | 0.3 | in [0.65, 0.92] | FAIL |
| NaI.PR.C4.d1_le_d2 | 0.29 | <= D2 | PASS |
| NaI.PR.C5.spectrum.negative | 20 | >= 18 of 20 | PASS |
| NaI.PR.C5.spectrum.best | 0 | all | FAIL |
| NaI.PR.C5.spectrum.no_activity | 20 | all | PASS |
| NaI.PR.C5.peak.negative | 20 | >= 18 of 20 | PASS |
| NaI.PR.C5.peak.best | 0 | all | FAIL |
| NaI.PR.C5.peak.no_activity | 20 | all | PASS |
| NaI.PR.C6.interfered | 50 | all 50 | PASS |
| NaI.PR.C6.detected | 0 | 0 | PASS |
| NaI.PR.C6.best | 0 | 0 | PASS |
| NaI.PR.C7.false_detect | 0 | in [0.010, 0.090] | FAIL |

## Measured values

```
{
 "HPGe": {
  "zero": {
   "n": 200,
   "mean_z": 0.07330077083747512,
   "cov2": 0.955,
   "methods": {
    "fit": 0,
    "window": 200,
    "interfered": 0
   }
  },
  "zero_iso_false_detect": 0.05,
  "weak_s1": {
   "n": 100,
   "mean_z": -0.11731160705931526,
   "cov2": 0.89,
   "interval_coverage": 0.96,
   "found": 0.01
  },
  "weak_s2": {
   "n": 100,
   "mean_z": 0.06295051403657603,
   "cov2": 0.95,
   "interval_coverage": 0.99,
   "found": 0.14
  },
  "weak_s3": {
   "n": 100,
   "mean_z": 0.20307802321034898,
   "cov2": 0.98,
   "interval_coverage": 0.99,
   "found": 0.47
  },
  "h3b": {
   "primary_present": true,
   "best_present": false,
   "d1_detected": 0.24,
   "d2_detected": 0.56
  },
  "interference": {
   "interfered": 50,
   "n": 50,
   "detected": 0,
   "best_from_it": 0
  },
  "m2": {
   "spectrum": {
    "negative": 20,
    "best_and_interval": 20,
    "no_activity_not_detected": 20,
    "n": 20
   },
   "peak": {
    "negative": 20,
    "best_and_interval": 20,
    "no_activity_not_detected": 20,
    "n": 20
   }
  },
  "bkg_absent": {
   "spectrum": {
    "n": 120,
    "mean_z": 0.1259641878091082,
    "cov2": 0.95
   },
   "peak": {
    "n": 120,
    "mean_z": 0.4604440105868461,
    "cov2": 0.9166666666666666
   }
  }
 },
 "NaI": {
  "zero": {
   "n": 200,
   "mean_z": -1.9187677709010456,
   "cov2": 0.505,
   "methods": {
    "fit": 0,
    "window": 197,
    "interfered": 3
   }
  },
  "zero_iso_false_detect": 0.0,
  "weak_s1": {
   "n": 100,
   "mean_z": -2.0906446713866207,
   "cov2": 0.41,
   "interval_coverage": 1.0,
   "found": 0.02
  },
  "weak_s2": {
   "n": 100,
   "mean_z": -1.5376566179271172,
   "cov2": 0.51,
   "interval_coverage": 1.0,
   "found": 0.14
  },
  "weak_s3": {
   "n": 100,
   "mean_z": -1.1400726933002578,
   "cov2": 0.61,
   "interval_coverage": 0.68,
   "found": 0.39
  },
  "h3b": {
   "primary_present": true,
   "best_present": true,
   "d1_detected": 0.29,
   "d2_detected": 0.3
  },
  "interference": {
   "interfered": 50,
   "n": 50,
   "detected": 0,
   "best_from_it": 0
  },
  "m2": {
   "spectrum": {
    "negative": 20,
    "best_and_interval": 0,
    "no_activity_not_detected": 20,
    "n": 20
   },
   "peak": {
    "negative": 20,
    "best_and_interval": 0,
    "no_activity_not_detected": 20,
    "n": 20
   }
  },
  "bkg_absent": {
   "spectrum": {
    "n": 40,
    "mean_z": 0.1342039379298332,
    "cov2": 1.0
   },
   "peak": {
    "n": 40,
    "mean_z": -3.701698937162149,
    "cov2": 0.025
   }
  }
 }
}
```

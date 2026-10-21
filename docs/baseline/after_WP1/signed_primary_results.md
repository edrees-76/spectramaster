# Signed primary result: results

Protocol: `window_polynomial_protocol.md` (harness version 3; version 2 criteria in `criteria_v2`, version 1 in `criteria`).

| id | value | limit | status |
|---|---|---|---|
| HPGe.WP.C9.identical_to_v2 | 0 | 0 differences | PASS |
| NaI.WP.C1.used | 0.995 | >= 0.90 | PASS |
| NaI.WP.C1.mean_z | 0.004355 | abs <= 0.2 | PASS |
| NaI.WP.C1.cov2 | 0.9548 | in [0.91, 0.99] | PASS |
| NaI.WP.C2.spectrum.used | 0 | >= 0.80 | FAIL |
| NaI.WP.C2.spectrum.mean_z | nan | abs <= 0.3 | FAIL |
| NaI.WP.C2.spectrum.cov2 | nan | >= 0.90 | FAIL |
| NaI.WP.C2.peak.used | 0 | >= 0.80 | FAIL |
| NaI.WP.C2.peak.mean_z | nan | abs <= 0.3 | FAIL |
| NaI.WP.C2.peak.cov2 | nan | >= 0.90 | FAIL |
| NaI.WP.C3.s1.mean_z | -0.225 | abs <= 0.3 (used n=97) | PASS |
| NaI.WP.C3.s1.cov2 | 0.9691 | in [0.90, 0.99] | PASS |
| NaI.WP.C3.s1.interval | 0.98 | >= 0.89 | PASS |
| NaI.WP.C3.s2.mean_z | -0.08433 | abs <= 0.3 (used n=85) | PASS |
| NaI.WP.C3.s2.cov2 | 0.9412 | in [0.90, 0.99] | PASS |
| NaI.WP.C3.s2.interval | 0.99 | >= 0.89 | PASS |
| NaI.WP.C3.s3.mean_z | -0.6494 | abs <= 0.3 (used n=61) | FAIL |
| NaI.WP.C3.s3.cov2 | 0.9344 | in [0.90, 0.99] | PASS |
| NaI.WP.C3.s3.interval | 1 | >= 0.89 | PASS |
| NaI.WP.C4.present | 1 | all | PASS |
| NaI.WP.C4.d2_detected | 0.86 | >= 0.50 | PASS |
| NaI.WP.C4.d1_le_d2 | 0.68 | <= D2 | PASS |
| NaI.WP.C5.spectrum.negative | 20 | >= 18 of 20 | PASS |
| NaI.WP.C5.spectrum.best | 0 | all | FAIL |
| NaI.WP.C5.spectrum.no_activity | 20 | all | PASS |
| NaI.WP.C5.peak.negative | 20 | >= 18 of 20 | PASS |
| NaI.WP.C5.peak.best | 0 | all | FAIL |
| NaI.WP.C5.peak.no_activity | 20 | all | PASS |
| NaI.WP.C6.interfered | 50 | >= 45 of 50 | PASS |
| NaI.WP.C6.detected | 0 | 0 | PASS |
| NaI.WP.C6.best | 0 | 0 | PASS |
| NaI.WP.C7.false_detect | 0.075 | in [0.010, 0.090] | PASS |
| NaI.WP.C8.false_detect | 0 | <= 0.090 | PASS |
| NaI.WP.C8.used | 0 | fewer than 20 used: reported | PASS |

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
    "interfered": 0,
    "curved": 0
   },
   "used": {
    "n": 200,
    "mean_z": 0.07330077083747512,
    "cov2": 0.955
   }
  },
  "zero_iso_false_detect": 0.05,
  "weak_s1": {
   "n": 100,
   "mean_z": -0.11731160705931526,
   "cov2": 0.89,
   "interval_coverage": 0.96,
   "found": 0.01,
   "methods": {
    "fit": 1,
    "window": 99,
    "interfered": 0,
    "curved": 0
   },
   "used": {
    "n": 99,
    "mean_z": -0.14237720770754228,
    "cov2": 0.898989898989899
   }
  },
  "weak_s2": {
   "n": 100,
   "mean_z": 0.06295051403657603,
   "cov2": 0.95,
   "interval_coverage": 0.99,
   "found": 0.14,
   "methods": {
    "fit": 14,
    "window": 86,
    "interfered": 0,
    "curved": 0
   },
   "used": {
    "n": 86,
    "mean_z": -0.17178710949802456,
    "cov2": 0.9651162790697675
   }
  },
  "weak_s3": {
   "n": 100,
   "mean_z": 0.20307802321034898,
   "cov2": 0.98,
   "interval_coverage": 0.99,
   "found": 0.47,
   "methods": {
    "fit": 47,
    "window": 53,
    "interfered": 0,
    "curved": 0
   },
   "used": {
    "n": 53,
    "mean_z": -0.30482727236263124,
    "cov2": 0.9811320754716981
   }
  },
  "h3b": {
   "primary_present": true,
   "best_present": true,
   "d1_detected": 0.53,
   "d2_detected": 0.88,
   "methods": {
    "fit": 53,
    "window": 47,
    "interfered": 0,
    "curved": 0
   }
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
    "n": 20,
    "flagged": 0,
    "best_from_flagged": 0
   },
   "peak": {
    "negative": 20,
    "best_and_interval": 20,
    "no_activity_not_detected": 20,
    "n": 20,
    "flagged": 0,
    "best_from_flagged": 0
   }
  },
  "bkg_absent": {
   "spectrum": {
    "n": 120,
    "mean_z": 0.1259641878091082,
    "cov2": 0.95,
    "methods": {
     "window": 120
    },
    "lines": 120
   },
   "peak": {
    "n": 120,
    "mean_z": 0.1259641878091082,
    "cov2": 0.95,
    "methods": {
     "window": 120
    },
    "lines": 120
   }
  }
 },
 "NaI": {
  "zero": {
   "n": 200,
   "mean_z": -0.009009967892178939,
   "cov2": 0.95,
   "methods": {
    "fit": 0,
    "window": 199,
    "interfered": 1,
    "curved": 0
   },
   "used": {
    "n": 199,
    "mean_z": 0.004354739620883292,
    "cov2": 0.9547738693467337
   },
   "quadratic": 199,
   "lc_ratio_mean": 1.1597288220071988
  },
  "zero_iso_false_detect": 0.075,
  "weak_s1": {
   "n": 100,
   "mean_z": -0.18179755952730983,
   "cov2": 0.95,
   "interval_coverage": 0.98,
   "found": 0.02,
   "methods": {
    "fit": 2,
    "window": 97,
    "interfered": 0,
    "curved": 1
   },
   "used": {
    "n": 97,
    "mean_z": -0.22500459384817215,
    "cov2": 0.9690721649484536
   },
   "quadratic": 97
  },
  "weak_s2": {
   "n": 100,
   "mean_z": 0.15919754606128558,
   "cov2": 0.91,
   "interval_coverage": 0.99,
   "found": 0.14,
   "methods": {
    "fit": 14,
    "window": 85,
    "interfered": 1,
    "curved": 0
   },
   "used": {
    "n": 85,
    "mean_z": -0.08432860829815801,
    "cov2": 0.9411764705882353
   },
   "quadratic": 85
  },
  "weak_s3": {
   "n": 100,
   "mean_z": -0.03217346357303185,
   "cov2": 0.96,
   "interval_coverage": 1.0,
   "found": 0.39,
   "methods": {
    "fit": 39,
    "window": 61,
    "interfered": 0,
    "curved": 0
   },
   "used": {
    "n": 61,
    "mean_z": -0.6493823701167523,
    "cov2": 0.9344262295081968
   },
   "quadratic": 61
  },
  "h3b": {
   "primary_present": true,
   "best_present": true,
   "d1_detected": 0.68,
   "d2_detected": 0.86,
   "methods": {
    "fit": 68,
    "window": 32,
    "interfered": 0,
    "curved": 0
   }
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
    "n": 20,
    "flagged": 20,
    "best_from_flagged": 0
   },
   "peak": {
    "negative": 20,
    "best_and_interval": 0,
    "no_activity_not_detected": 20,
    "n": 20,
    "flagged": 20,
    "best_from_flagged": 0
   }
  },
  "bkg_absent": {
   "spectrum": {
    "n": 0,
    "mean_z": NaN,
    "cov2": NaN,
    "methods": {
     "curved": 40,
     "interfered": 80
    },
    "lines": 120
   },
   "peak": {
    "n": 0,
    "mean_z": NaN,
    "cov2": NaN,
    "methods": {
     "curved": 40,
     "interfered": 80
    },
    "lines": 120
   }
  },
  "edge": {
   "false_detect": 0.0,
   "methods": {
    "fit": 0,
    "window": 0,
    "interfered": 100,
    "curved": 0
   },
   "quadratic": 0,
   "n": 100,
   "used": {
    "n": 0,
    "mean_z": NaN,
    "cov2": NaN
   }
  }
 }
}
```

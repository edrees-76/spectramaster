# Signed primary result: results

Protocol: `signed_primary_amendment_protocol.md` (harness version 2; version 1 criteria in `criteria`).

| id | value | limit | status |
|---|---|---|---|
| HPGe.PA.C1.mean_z | 0.0733 | abs <= 0.2 | PASS |
| HPGe.PA.C1.cov2 | 0.955 | in [0.91, 0.99] | PASS |
| HPGe.PA.C2.spectrum.mean_z | 0.126 | abs <= 0.3 | PASS |
| HPGe.PA.C2.spectrum.cov2 | 0.95 | >= 0.90 | PASS |
| HPGe.PA.C2.peak.mean_z | 0.126 | abs <= 0.3 | PASS |
| HPGe.PA.C2.peak.cov2 | 0.95 | >= 0.90 | PASS |
| HPGe.PA.C3.s1.mean_z | -0.1173 | abs <= 0.3 | PASS |
| HPGe.PA.C3.s1.cov2 | 0.89 | in [0.90, 0.99] | FAIL |
| HPGe.PA.C3.s1.interval | 0.96 | >= 0.89 | PASS |
| HPGe.PA.C3.s2.mean_z | 0.06295 | abs <= 0.3 | PASS |
| HPGe.PA.C3.s2.cov2 | 0.95 | in [0.90, 0.99] | PASS |
| HPGe.PA.C3.s2.interval | 0.99 | >= 0.89 | PASS |
| HPGe.PA.C3.s3.mean_z | 0.2031 | abs <= 0.3 | PASS |
| HPGe.PA.C3.s3.cov2 | 0.98 | in [0.90, 0.99] | PASS |
| HPGe.PA.C3.s3.interval | 0.99 | >= 0.89 | PASS |
| HPGe.PA.C4.present | 1 | all | PASS |
| HPGe.PA.C4.d2_detected | 0.88 | in [0.65, 0.92] | PASS |
| HPGe.PA.C4.d1_le_d2 | 0.53 | <= D2 | PASS |
| HPGe.PA.C9.own_peak_interfered | 0 | <= 2 of 100 | PASS |
| HPGe.PA.C5.spectrum.negative | 20 | >= 18 of 20 | PASS |
| HPGe.PA.C5.spectrum.no_activity | 20 | all | PASS |
| HPGe.PA.C5.spectrum.best | 20 | all | PASS |
| HPGe.PA.C5.peak.negative | 20 | >= 18 of 20 | PASS |
| HPGe.PA.C5.peak.no_activity | 20 | all | PASS |
| HPGe.PA.C5.peak.best | 20 | all | PASS |
| HPGe.PA.C6.interfered | 50 | >= 45 of 50 | PASS |
| HPGe.PA.C6.detected | 0 | 0 | PASS |
| HPGe.PA.C6.best | 0 | 0 | PASS |
| HPGe.PA.C7.false_detect | 0.05 | in [0.010, 0.090] | PASS |
| NaI.PA.C5.spectrum.negative | 20 | >= 18 of 20 | PASS |
| NaI.PA.C5.spectrum.no_activity | 20 | all | PASS |
| NaI.PA.C5.spectrum.best_or_flagged | 20 | all; none from a flagged line | PASS |
| NaI.PA.C5.peak.negative | 20 | >= 18 of 20 | PASS |
| NaI.PA.C5.peak.no_activity | 20 | all | PASS |
| NaI.PA.C5.peak.best_or_flagged | 20 | all; none from a flagged line | PASS |
| NaI.PA.C6.interfered | 50 | >= 45 of 50 | PASS |
| NaI.PA.C6.detected | 0 | 0 | PASS |
| NaI.PA.C6.best | 0 | 0 | PASS |
| NaI.PA.C7.false_detect | 0 | <= 0.090 | PASS |
| NaI.PA.C8.zero | 0 | fewer than 20 used lines: reported | PASS |
| NaI.PA.C8.weak_s1 | 0 | fewer than 20 used lines: reported | PASS |
| NaI.PA.C8.weak_s2 | 0 | fewer than 20 used lines: reported | PASS |
| NaI.PA.C8.weak_s3 | 0 | fewer than 20 used lines: reported | PASS |
| NaI.PA.C8.bkg_absent.spectrum | 0 | fewer than 20 used lines: reported | PASS |
| NaI.PA.C8.bkg_absent.peak | 0 | fewer than 20 used lines: reported | PASS |

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
    }
   },
   "peak": {
    "n": 120,
    "mean_z": 0.1259641878091082,
    "cov2": 0.95,
    "methods": {
     "window": 120
    }
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
    "window": 0,
    "interfered": 1,
    "curved": 199
   },
   "used": {
    "n": 0,
    "mean_z": NaN,
    "cov2": NaN
   }
  },
  "zero_iso_false_detect": 0.0,
  "weak_s1": {
   "n": 100,
   "mean_z": -2.0906446713866207,
   "cov2": 0.41,
   "interval_coverage": 0.02,
   "found": 0.02,
   "methods": {
    "fit": 2,
    "window": 0,
    "interfered": 0,
    "curved": 98
   },
   "used": {
    "n": 0,
    "mean_z": NaN,
    "cov2": NaN
   }
  },
  "weak_s2": {
   "n": 100,
   "mean_z": -1.5376566179271172,
   "cov2": 0.51,
   "interval_coverage": 0.14,
   "found": 0.14,
   "methods": {
    "fit": 14,
    "window": 0,
    "interfered": 0,
    "curved": 86
   },
   "used": {
    "n": 0,
    "mean_z": NaN,
    "cov2": NaN
   }
  },
  "weak_s3": {
   "n": 100,
   "mean_z": -1.1400726933002578,
   "cov2": 0.61,
   "interval_coverage": 0.39,
   "found": 0.39,
   "methods": {
    "fit": 39,
    "window": 0,
    "interfered": 0,
    "curved": 61
   },
   "used": {
    "n": 0,
    "mean_z": NaN,
    "cov2": NaN
   }
  },
  "h3b": {
   "primary_present": true,
   "best_present": false,
   "d1_detected": 0.68,
   "d2_detected": 0.68,
   "methods": {
    "fit": 68,
    "window": 0,
    "interfered": 0,
    "curved": 32
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
    }
   },
   "peak": {
    "n": 0,
    "mean_z": NaN,
    "cov2": NaN,
    "methods": {
     "curved": 40,
     "interfered": 80
    }
   }
  }
 }
}
```

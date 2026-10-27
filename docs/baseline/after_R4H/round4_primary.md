# Round-4 review, signed primary result of nuclides not detected (R4-H2)

Protocol: `docs/baseline/round4_primary_protocol.md`.

| ID | result | value |
|---|---|---|
| RH.C1 | PASS | 197/197 exact; mean z 0.091, cov2 0.985 (n 200); best estimate 200/200 |
| RH.C2 | PASS | 99/99 from the usable line; mean z -0.117, cov2 0.970 (n 100) |

## Measured

```
{
 "HPGe": {
  "mean": {
   "n": 200,
   "mean_z": 0.09082613742934942,
   "cov2": 0.985,
   "n_z": 200,
   "multi_line": 197,
   "exact": 197,
   "with_usable": 200,
   "best_present": 200,
   "mean_usable_lines": 5.98,
   "methods": {
    "window": 197,
    "fit": 3
   }
  },
  "key": {
   "n": 100,
   "eligible": 99,
   "ok": 99,
   "mean_z": -0.11664032750874387,
   "cov2": 0.9696969696969697,
   "n_z": 99,
   "methods": {
    "window": 99,
    "fit": 1
   }
  }
 },
 "NaI": {
  "mean": {
   "n": 200,
   "mean_z": -0.21256871516553766,
   "cov2": 0.995,
   "n_z": 200,
   "multi_line": 199,
   "exact": 199,
   "with_usable": 200,
   "best_present": 200,
   "mean_usable_lines": 5.965,
   "methods": {
    "window": 199,
    "fit": 1
   }
  }
 }
}
```

## Before the change

```
{
 "HPGe": {
  "mean": {
   "n": 200,
   "mean_z": 0.09243919522649695,
   "cov2": 0.975,
   "n_z": 200,
   "multi_line": 200,
   "exact": 0,
   "with_usable": 200,
   "best_present": 200,
   "mean_usable_lines": 5.98,
   "methods": {
    "window": 197,
    "fit": 3
   }
  },
  "key": {
   "n": 100,
   "eligible": 99,
   "ok": 0,
   "mean_z": NaN,
   "cov2": NaN,
   "n_z": 0,
   "methods": {
    "interfered": 99,
    "fit": 1
   }
  }
 },
 "NaI": {
  "mean": {
   "n": 200,
   "mean_z": -0.03132146612746148,
   "cov2": 0.985,
   "n_z": 200,
   "multi_line": 200,
   "exact": 0,
   "with_usable": 200,
   "best_present": 198,
   "mean_usable_lines": 5.965,
   "methods": {
    "window": 197,
    "interfered": 1,
    "fit": 1,
    "curved": 1
   }
  }
 }
}
```

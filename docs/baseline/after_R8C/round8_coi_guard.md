# Round-8 calibration points already corrected for summing (Gemini M1)

engine 1.33.0

| ID | value | result |
|---|---|---|
| RC8.C1 | Eu-152 121.78 keV point: input 0.060915; before 0.0658259 (+8.06 %), curve 0.0647965; now 0.060915, curve at 121.78 keV 0.0613416, marked corrected True; explicit refit curve 0.0613416 | PASS |
| RC8.C2 | Cs-137 activity with TCS: before 64.366 Bq, now 65.2101 Bq, explicit refit 65.2101 Bq | PASS |
| RC8.C3 | mixed corrected and uncorrected cascade points: before corrected; now calibration points corrected for true-coincidence summing are fitted together with cascade-emitter points that are not: Co-60 1173.2 keV. Exclude them, or fit the calibration again from the measured points | PASS |
| RC8.C4 | uncorrected, corrected, excluded and declared-free curves, and their activities, identical to before | PASS |

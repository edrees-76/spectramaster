# Round-9 summing state of curves saved by engine 1.26.0 and earlier (Codex H1)

engine 1.35.0

| ID | value | result |
|---|---|---|
| RA9.C1 | lost-flag files (as saved and re-saved) refitted as they are, not corrected again (before: curve at 121.78 keV 0.0647965; refit as is 0.0613416) | PASS |
| RA9.C2 | excluded points' summing_coi differ from the modern file's | FAIL |
| RA9.C3 | lost flag with an uncorrected cascade point: before corrected; now calibration points corrected for true-coincidence summing are fitted together with cascade-emitter points that are not: Co-60 1173.2 keV. Exclude them, or fit the calibration again from the measured points | PASS |
| RA9.C4 | legacy corrected and raw files, modern files: identical to before | PASS |

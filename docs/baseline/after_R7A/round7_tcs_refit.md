# Round-7 TCS state through a refit (H1)

engine 1.27.0

| ID | value | result |
|---|---|---|
| RA.C1 | both corrected curves keep summing_corrected, tcs_partial and their efficiencies | PASS |
| RA.C2 | activities, u and MDA from the refitted curves equal the source's, partial notes kept | PASS |
| RA.C3 | dialog refit and save keep the state | PASS |
| RA.C4 | raw cascade point: calibration points corrected for true-coincidence summing are fitted together with cascade-emitter points that are not: Co-60 1332.5 keV. Exclude them, or fit the calibration again from the measured points; raw non-cascade point: fitted, state True | PASS |
| RA.C5 | uncorrected files unchanged; 1.26.0 corrected files load with the point fields and refit as corrected | PASS |
| RA.C6 | uncorrected curves and round-6 cases identical to before | PASS |

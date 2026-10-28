# Round-6 TCS state (H3, L1)

engine 1.26.0

| ID | value | result |
|---|---|---|
| RE.C1 | partial points of the corrected curve [('Ba-133', 276.4), ('Ba-133', 302.9), ('Ba-133', 356.0), ('Ba-133', 383.8)]; same after save/reload True, from a 1.25.0 file True | PASS |
| RE.C2 | the four cases carry the field, one note per partial point and the Cs-137 note; controls unchanged | PASS |
| RE.C3 | the report's results carry the list, its calibration summary the list, note and warnings (saved curves); one review status names the points; controls without it | PASS |
| RE.C4 | 'partial true-coincidence summing correction: coincident photons below the efficiency curve left out (on average 0.37 per emission of this line)' (ignored 0.369959) | PASS |
| RE.C5 | activities, uncertainties, limits, COI factors and efficiencies identical to before | PASS |

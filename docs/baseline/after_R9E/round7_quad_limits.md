# Round-7 limits of the quadratic window (Gemini H3)

engine 1.34.0

| ID | value | result |
|---|---|---|
| RD.C1 | currie: threshold 8.559 -> 9.931 Bq (quadratic 9.931), MDA 17.2 -> 19.94 Bq (expected 19.94); iso11929: threshold 8.559 -> 9.931 Bq (quadratic 9.931), MDA 24.07 -> 27.91 Bq (expected 27.91) | PASS |
| RD.C2 | currie: Cs-137 8.559 / 17.2 -> 9.931 / 19.94 Bq; currie: Ba-133 mean 5.778 / 11.59 -> 5.743 / 11.52 Bq; iso11929: Cs-137 8.559 / 24.07 -> 9.931 / 27.91 Bq; iso11929: Ba-133 mean 5.778 / 16.31 -> 5.743 / 16.22 Bq | PASS |
| RD.C3 | every other number, decision and note identical to before (excepted, the intended change of round8_line_covariance_protocol.md: nai_ba_mean_currie Ba-133 primary_u 4.8228 -> 4.4875 Bq; nai_ba_mean_iso11929 Ba-133 primary_u 4.8228 -> 4.4875 Bq) | PASS |
| RD.C4 | 195 of 200 quadratic; reported threshold / (k sd) 0.881 -> 1.022; fraction above the reported threshold 0.0615 -> 0.0410 | PASS |

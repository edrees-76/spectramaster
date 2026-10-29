# Round-7 limits of the quadratic window (Gemini H3)

engine 1.30.0

| ID | value | result |
|---|---|---|
| RD.C1 | currie: threshold 8.559 -> 9.931 Bq (quadratic 9.931), MDA 17.2 -> 19.94 Bq (expected 19.94); iso11929: threshold 8.559 -> 9.931 Bq (quadratic 9.931), MDA 24.07 -> 27.91 Bq (expected 27.91) | PASS |
| RD.C2 | currie: Cs-137 8.559 / 17.2 -> 9.931 / 19.94 Bq; currie: Ba-133 mean 5.778 / 11.59 -> 6.437 / 12.9 Bq; iso11929: Cs-137 8.559 / 24.07 -> 9.931 / 27.91 Bq; iso11929: Ba-133 mean 5.778 / 16.31 -> 6.437 / 18.17 Bq | PASS |
| RD.C3 | every other number, decision and note identical to before | PASS |
| RD.C4 | 195 of 200 quadratic; reported threshold / (k sd) 0.881 -> 1.022; fraction above the reported threshold 0.0615 -> 0.0410 | PASS |

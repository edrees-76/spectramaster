# Round-7 input validation (Codex M1, Gemini M4)

| ID | value | result |
|---|---|---|
| RE.C1 | refused with the row named, nothing fitted or saved: 0 of 14 (not: ["4:'0,02'", "4:'-0.01'", "4:'nan'", "4:'0'", "4:'abc'", "4:''", "2:'inf'", "2:'-100'", "2:'1,5'", "5:'1,5'", "5:'-2'", "5:'nan'", "5:'0'", "5:''"]); valid edits as before: True | FAIL |
| RE.C2 | refused 9 of 9 (not: []); valid as before: True | PASS |
| RE.C3 | refused 11 of 11 (not: []); valid files as before: True | PASS |
| RE.C4 | refused 12 of 12 (not: []); valid records and skipped empty slots as before: True | PASS |
| RE.C5 | refused 2 of 2 (not: []); valid as before and the previous value kept: True | PASS |

# Round-6 review: input validation

Protocol: `docs/baseline/round6_inputs_protocol.md`.

| ID | result | value |
|---|---|---|
| RC.C1 | PASS | edited [['Cs-137', 2000.0, 40.0, None, None]]; then kBq [['Cs-137', 2000.0, 40.0, None, None]]; round trip [['Cs-137', 12345.678, 246.91356, None, None]] |
| RC.C2 | PASS | refused 20 of 20 (not: []); typed valid row [['Co-60', 1000.0, 20.0, 166000000.0, [[1173.228, 0.9984999999999999], [1332.492, 0.9998260000000001]]]] |
| RC.C3 | PASS | refused 12 of 12 (not: []); valid file as before: True |
| RC.C4 | PASS | refused 10 of 10 (not: []); valid line as before: True |
| RC.C5 | PASS | not refused: []; clean spectrum as before: True |
| RC.C6 | PASS | refused 5 of 5; valid text [100.0, 105.0, 98.5, 100.0, -3.0] |
| RC.C7 | PASS | refused 3 of 3; read as registered 5 of 5; round-5 refusals kept: True |
| RC.C8 | PASS | set_bq: {'inf': 'ValueError: not a finite activity: inf Bq', 'nan': 'ValueError: not a finite activity: nan Bq', '-inf': 'ValueError: not a finite activity: -inf Bq', '12345.678': 12345.678, '0': [0.0, '']} |

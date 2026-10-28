# Round-5 review, H4: a TKA file named .txt

Protocol: `docs/baseline/round5_tka_protocol.md`.

| ID | result | value |
|---|---|---|
| RD.C1 | PASS | TKA named .txt: ambiguous ['ascii1', 'tka'], read: FormatError: a.txt could be any of: ASCII-1 (one count per line), Canberra/Toolkit TKA; choose the input format; chosen TKA: ['tka', 1024, 15345.0, 100.0, 110.0] (before: usual, ['ascii1', 1026, 15555.0, None, None]) |
| RD.C2 | PASS | .tka: ['tka', 1024, 15345.0, 100.0, 110.0]; one-column .txt starting with zeros: usual ['ascii1', 1024, 15344.0, None, None] |
| RD.C3 | PASS | one-column .txt whose first two counts look like times: ambiguous ['ascii1', 'tka']; chosen ASCII-1: ['ascii1', 1024, 16369.0, None, None] (before read as ['ascii1', 1024, 16369.0, None, None]) |
| RD.C4 | PASS | 190 .txt files, detection changed for 0: [] |
| RD.C5 | PASS | 319 files with own name, .xyz and no extension: changed [] |

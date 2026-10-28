# Round-6 review, H2: Laval and Wallac files named .txt

Protocol: `docs/baseline/round6_laval_wallac_protocol.md`.

| ID | result | value |
|---|---|---|
| RB.C1 | PASS | laval as .txt: ambiguous ['ascii1', 'laval_ascii'], read: FormatError: a.txt could be any of: ASCII-1 (one count per line), Laval ASCII; choose the input format; chosen laval_ascii: ['laval_ascii', 1024, 15290.0, 100.0, 110.0, [0.0, 0.5]] (before: usual, ['ascii1', 1023, 496726.5, None, None, []]) |
| RB.C2 | PASS | wallac as .txt: ambiguous ['ascii1', 'wallac_ascii'], read: FormatError: w.txt could be any of: ASCII-1 (one count per line), Wallac ASCII (1024 ch); choose the input format; chosen wallac_ascii: ['wallac_ascii', 1024, 15345.0, 100.0, 100.0, []] (before: usual, ['ascii1', 1025, 15445.0, None, None, []]) |
| RB.C3 | PASS | .de1: usual ['laval_ascii', 1024, 15290.0, 100.0, 110.0, [0.0, 0.5]]; .001: usual ['wallac_ascii', 1024, 15345.0, 100.0, 100.0, []]; one-column .txt: ambiguous FormatError: p.txt could be any of: ASCII-1 (one count per line), Canberra/Toolkit TKA; choose the input format |
| RB.C4 | PASS | ascii1 six-digit 4th count as .txt: ambiguous ['ascii1', 'laval_ascii'], chosen ASCII-1 identical; ascii1 1027 counts as .txt: ambiguous ['ascii1', 'wallac_ascii'], chosen ASCII-1 identical |
| RB.C5 | PASS | 190 .txt files, detection changed for 0: [] |
| RB.C6 | PASS | 319 files with own name, .xyz and no extension: changed [] |
| RB.R1 | REPORT | laboratory .txt files (counts only), before {'None|ambiguous|ascii1+tka': 10, 'None|none|': 34}, now {'None|ambiguous|ascii1+tka': 10, 'None|none|': 34} |

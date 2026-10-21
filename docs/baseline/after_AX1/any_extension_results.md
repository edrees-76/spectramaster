# Any-extension reading: AX.C1-AX.C4

Protocol: `docs/baseline/any_extension_protocol.md`.

| ID | Value | Limit | Result | Scope |
|---|---|---|---|---|
| AX.C1 | 0 | 0 | PASS | 319 files, own name |
| AX.C2 | 2 | 0 | FAIL | 10 content-set and Excel files |
| AX.C3 | 0 | 0 | PASS | 206 negative files as .xyz |
| AX.C4 | 2 | 0 | FAIL |   |

## AX.C2 failures

- {"file": "write:specutils_txt", "name": "probe.xyz", "own": "ascii2", "detected": "specutils_txt", "read": "specutils_txt"}
- {"file": "write:specutils_txt", "name": "probe", "own": "ascii2", "detected": "specutils_txt", "read": "specutils_txt"}

## AX.C4 failures

- {"file": "write:tka", "name": "probe.xyz", "before": null, "after": "ascii1"}
- {"file": "write:tka", "name": "probe", "before": null, "after": "ascii1"}

## AX.C2 excluded (known own-name misdetection)

- {"file": "write:iaea_ascii_dat", "own": "eml_sanderson", "probe.xyz": "iaea_ascii_dat", "probe": "iaea_ascii_dat"}

## Reported: undetected under their own name, detected renamed

- none

## Reported: written files of formats outside the content set, as .xyz

| Own-name format | Detected as .xyz |
|---|---|
| aptec_ascii | aptec_ascii |
| aptec_s0 | aptec_s0 |
| ci_cnf | ci_cnf |
| ci_s100 | ci_s100 |
| davidson_ascii | davidson_ascii |
| exploranium_gr130 | exploranium_gr130 |
| exploranium_gr135 | exploranium_gr135 |
| gadras_pcf | gadras_pcf |
| iaea_spe | iaea_spe |
| iec1455 | iec1455 |
| ieee_asc | None |
| json | json |
| n42_2006 | n42_2006 |
| n42_2012 | n42_2012 |
| nd66 | nd66 |
| norland5000 | norland5000 |
| ortec_chn | ortec_chn |
| ortec_spc | ortec_spc |
| oxford_ans | None |
| rump_ascii | rump_ascii |
| spc_ascii | spc_ascii |
| spc_float | spc_float |
| specutils_csv | specutils_csv |
| tka | ascii1 |

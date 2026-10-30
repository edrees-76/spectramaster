# Round-8 review, Gemini H2: amendment to `round8_peak_mode_protocol.md` (pre-registered)

Written 2026-10-30 after the first run (`after_R8B`, 3 PASS / 1 FAIL) and before any re-run. No code
change: the change of `round8_peak_mode_protocol.md` stays as committed.

## Reason

RB8.C3 required the peak-mode lines "without a usable window result" to be identical to before,
while Change 1 of the protocol applies to every line without a sample peak, whatever its window
result. In the NaI case the 1332.5 keV line (no sample peak, window "curved", not used) changed its
limits only, as Change 1 says. RB8.C3 as written failed and stays failed in `after_R8B`.

## Amended criterion

| ID | quantity | limit |
|---|---|---|
| RB8.C3a | the spectrum mode; the peak-mode lines with a sample peak; the peak-mode lines without a sample peak whose window result is not used ("interfered" or "curved") | the spectrum mode and the lines with a sample peak identical to before; a line without a usable window result: every field other than L_C, L_D, the decision threshold and the MDA identical to before, and L_C equal to 1.645 sqrt(sigma0^2) of Change 1 for the linear window (relative 1e-9) |

RB8.C1, RB8.C2, RB8.C4 and RB8.C5 unchanged. Output folder `after_R8B2` (`--amendment`); `after_R8B`
is kept as the first run.

---

## Results (`after_R8B2`)

Amendment committed in 5e897d0 before the re-run (SHA-256 of the file
c07ae3934dbd8860023c5b86c476a63a2002659c57f3a36f89bfe5ac1ec5061f). Re-run: 4 PASS / 0 FAIL.

| ID | value | result |
|---|---|---|
| RB8.C1 | as in `after_R8B` (every line equals the registered sigma0^2, one on the quadratic window) | PASS |
| RB8.C2 | primary result, its uncertainty, method and every other line field identical to before | PASS |
| RB8.C3a | spectrum mode and lines with a sample peak identical to before; NaI 1332.5 keV ("curved"), Currie and ISO 11929: L_C 291.08 -> 314.42 counts, the registered value 314.42 | PASS |
| RB8.C4 | as in `after_R8B` (false detections 0.0530 and 0.0526, threshold ratios 0.9444 and 0.9397) | PASS |
| RB8.C5 | benchmark 154 PASS / 13 FAIL / 60 REPORT, no criterion changed state against `after_R8A`; full suite 1666 passed, 69 skipped, 1 failed: `test_analysis::test_timing_16k_channels` (a timing limit, the machine running three other full suites at the same time), passed when re-run alone; no existing test changed | PASS |

New tests: `tests/test_round8_peak_mode.py` (8). ENGINE_VERSION 1.32.0. The manual sources say that
for a line without a sample peak the window result and its decision threshold use the same window
estimate of the background.

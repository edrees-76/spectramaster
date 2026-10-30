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

# Round-9 review, Codex H1: amendment of RA9.C2 (pre-registered)

Written 2026-10-30, after the first run (`after_R9A`, 3 PASS / 1 FAIL) and before any re-run.
Amends `round9_legacy_tcs_protocol.md`; that protocol, its before values and the first run's results
stay as committed (666b5fc).

## Reason

RA9.C2 required the loaded points' `summing_coi` to *equal* those of the same curve saved by the current
engine. A legacy file holds the COI only in the point note, written with 4 decimals
("summing corrected, COI 0.9257"); the protocol itself states this under Limitations ("The COI read
from a note has the note's 4 decimals"), and the existing rebuild for files marked corrected
(round7_tcs_refit_protocol.md) reads it the same way. The criterion therefore contradicted the change
as registered. The first run shows exactly that: every corrected point, in use or excluded, differs
only by the rounding (e.g. 0.9257 against 0.9257086683803547; 0.8210 against 0.8209548298401738),
the pattern of corrected / uncorrected points is identical, and the include-and-refit part of RA9.C2
passed (curve at 121.78 keV 0.06134159693644672 in both). The FAIL is kept in `after_R9A`.

## Amended criterion

| ID | quantity | limit |
|---|---|---|
| RA9.C2a | file marked corrected with two corrected points excluded | the loaded points carry a `summing_coi` exactly where the current engine's file does, each within 5e-5 (half the last decimal of the note) of it; all points included again and refitted: not refused, marked corrected, efficiencies equal to the current engine's file (relative 1e-12) |

RA9.C1, RA9.C3, RA9.C4 and RA9.C5 are unchanged. The re-run is `round9_legacy_tcs --amendment`,
results to `after_R9A2`; the code is not changed between the runs.

---

## Results

Re-run `round9_legacy_tcs --amendment` (`after_R9A2`, engine 1.35.0, code unchanged since 666b5fc): **4 PASS / 0 FAIL**
(RA9.C1, RA9.C2a, RA9.C3, RA9.C4). The only harness change between the runs is the `--amendment`
flag (criterion RA9.C2a, output folder `after_R9A2`). RA9.C5: see the main protocol.

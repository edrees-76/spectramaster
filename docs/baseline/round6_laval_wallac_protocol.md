# Round-6 review: Laval and Wallac files named .txt, H2 (pre-registered)

Written 2026-10-28, before any change to the code. Gemini round-6 review
(`C:\Users\DELL\Downloads\gemini_review_round6.md`, main 624e199), finding H2, checked on the code
(`formats/base.py`, `detect` / `USUAL_AMBIGUOUS`; `formats/aptec_import_ascii.py`,
`content_laval` / `content_wallac_strict`) before this protocol was written.

**Finding.** Round 5 (`round5_tka_protocol.md`) made a `.txt` file that also passes the TKA
content test ambiguous. Laval ASCII (live time, real time, two YYMMDD dates, detector, quantity,
geometry, slope, offset, channel count, then counts from channel 11) and Wallac ASCII (sample id,
description, counting time, then 1024 counts) are also one value per line, but they are not in
`USUAL_AMBIGUOUS`: named `.txt`, the usual ASCII-1 test answers and their content tests are never
asked. Reproduced (harness below, file written by SpectraMaster from a 1024-channel spectrum,
LT/RT 100/110 s, counts `i % 31`, calibration 0 + 0.5 keV/ch):

- Laval named `.txt`: read as ASCII-1, 1023 channels, sum 496726.5 (header values counted as
  channels), no times, no calibration; as `.de1`: 1024 channels, sum 15290, LT 100, RT 110,
  calibration (0, 0.5).
- Wallac named `.txt`: read as ASCII-1, 1025 channels, sum 15445, no time; as `.001`: 1024
  channels, sum 15345, LT = RT = 100.

No note is given in either case.

## Change

1. `USUAL_AMBIGUOUS` gets `("ascii1", "laval_ascii")` and `("ascii1", "wallac_ascii")`: when the
   usual test chose ASCII-1 and the file also passes the Laval content test (`content_laval`) or the
   strict Wallac content test (`content_wallac_strict`, exactly 3 + 1024 lines), the result is
   ambiguous (format None, candidates ASCII-1 and that format), as for TKA in round 5. Reading it
   without a chosen format then stops with "could be any of: ...; choose the input format"; with the
   input format chosen, it is read as chosen.
2. Nothing else: the content tests, the readers, the other usual tests and the preferences are
   unchanged. A file named `.de1` or `.001` is read as before.

The price, as in round 5: a genuine one-column `.txt` spectrum whose 4th value has exactly six
digits (passes the Laval date test) or which has exactly 1027 counts with a single number on line 3
(passes the strict Wallac test) becomes ambiguous; the user then chooses ASCII-1 once and gets the
same reading as before. Measured below on the files at hand.

No engine change (reading only); engine version stays 1.24.0. Harness
`validation/round6_laval_wallac.py`, fixed output folder `after_R6B`; values before the change
recorded with `--collect` into `after_R6B/round6_laval_wallac_before.json` (engine 1.24.0, 6c11fd5),
committed with this protocol. The laboratory archives are only counted by detection result, with
no file names.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RB.C1 | Laval file named `.txt` | detection ambiguous with candidates exactly {ASCII-1, Laval}; reading without a format: FormatError containing "choose the input format"; reading as Laval: identical to the same file read as `.de1` (1024 channels, sum 15290, LT 100, RT 110, calibration 0, 0.5) |
| RB.C2 | Wallac file named `.txt` | the same with {ASCII-1, Wallac}; reading as Wallac identical to the `.001` reading (1024 channels, sum 15345, LT = RT = 100) |
| RB.C3 | Laval as `.de1`, Wallac as `.001`, a one-column `.txt` already ambiguous with TKA | detection and reading identical to before |
| RB.C4 | one-column `.txt` with a six-digit 4th count; one-column `.txt` with 1027 counts | either unchanged or ambiguous; reading as ASCII-1 identical to before |
| RB.C5 | detection of every `.txt` file under `test_corpus`, `tests` and `D:/SpectraMaster_public_data` (190 files before) | identical to before for every file |
| RB.C6 | `any_extension` collection (319 files: own name, `.xyz`, no extension; detection and read signatures) | identical to before for every file |
| RB.C7 | benchmark (`after_R5C`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes, each changed existing test listed with its reason |
| RB.R1 | `.txt` files of the laboratory archives, counts by detection result | REPORT only |

Before the change: RB.C1 and RB.C2 fail (usual ASCII-1, wrong channels and sums, no times);
RB.C3, RB.C5 and RB.C6 are the controls; RB.C4 measures the price. Of the 190 `.txt` files, 1 is
detected as ASCII-1 (usual) and 189 are not spectra. Laboratory archives before: 10 `.txt` files
ambiguous ASCII-1/TKA, 34 not spectra, none detected as ASCII-1 by the usual test.

---

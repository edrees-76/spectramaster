# Round-5 review: a TKA file named .txt, H4 (pre-registered)

Written 2026-10-28, before any change to the code. Codex round-5 review
(`D:\DSpectraMaster_reviews\codex_review_round5.md`, main 865c1ec), finding H4, checked on the code
(`formats/base.py`, `detect`; `formats/ascii_formats.py`, `sniff_ascii1` / `content_tka`) before this
protocol was written.

**Finding.** Round 4 (`round4_formats_protocol.md`) made a file that passes both the one-column
ASCII test and the TKA test (live time, real time, then one count per line, `0 < LT <= RT <= 10 LT`)
ambiguous when its extension is unknown. With the extension `.txt`, the usual test of ASCII-1
(`sniff_ascii1`: `.txt` and one number per line) answers first and the content tests are never
asked. Reproduced (harness below): a TKA file written by SpectraMaster (1024 channels, LT/RT
100/110 s, counts `i % 31`, sum 15345) renamed `.txt` is read as ASCII-1 with 1026 channels,
sum 15555, and no live or real time, without a note.

## Change

1. `detect`: when the usual test chose ASCII-1 and the file also passes the TKA content test, the
   result is ambiguous (format None, candidates ASCII-1 and TKA), as for an unknown extension.
   Reading it without a chosen format then stops with "could be any of: ...; choose the input
   format"; with the input format chosen, it is read as chosen.
2. Nothing else: a `.txt` one-column file whose first value is 0, or whose first two values fail
   `0 < c0 <= c1 <= 10 c0`, is read as ASCII-1 as before; `.tka` files as before; the other usual
   tests and preferences unchanged.

This makes some genuine one-column `.txt` spectra ambiguous (first two counts positive and within a
factor 10): the user then chooses ASCII-1 once. This is the price of not losing the times and
channels of a TKA file silently; measured below on the files at hand.

No engine change (reading only); engine version stays 1.23.0. Harness
`validation/round5_tka.py`, fixed output folder `after_R5D`; values before the change recorded with
`--collect` into `after_R5D/round5_tka_before.json` (engine 1.23.0, d641271), committed with this
protocol.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RD.C1 | TKA file (1024 ch, LT/RT 100/110, sum 15345) named `.txt` | detection ambiguous with candidates exactly {ASCII-1, TKA}; reading without a format: FormatError containing "choose the input format"; reading as TKA: 1024 channels, sum 15345, LT 100, RT 110 |
| RD.C2 | the same TKA file as `.tka`; a one-column `.txt` starting with zeros | detection and reading identical to before |
| RD.C3 | a one-column `.txt` whose first two counts are 1 and 2 | ambiguous; reading as ASCII-1 identical to its reading before (1024 channels, sum 16369) |
| RD.C4 | detection of every `.txt` file under `test_corpus`, `tests` and `D:/SpectraMaster_public_data` (190 files before) | identical to before for every file |
| RD.C5 | `any_extension` collection (319 files: own name, `.xyz`, no extension; detection and read signatures) | identical to before for every file |
| RD.C6 | benchmark (`after_R5C`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes, each changed existing test listed with its reason |

Before the change: RD.C1 fails (usual ASCII-1, 1026 channels, sum 15555, no times) and RD.C3 fails
(usual ASCII-1); RD.C2, RD.C4 and RD.C5 are the controls. Of the 190 `.txt` files, 1 is detected as
ASCII-1 (usual) and 189 are not spectra (no format); none passes the TKA test.

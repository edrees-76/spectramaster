# Round-4 review, format findings (R4-C): evaluation protocol (pre-registered)

Written 2026-10-27, **before** the changes below were made. The observations "before" were collected
with engine 1.16.0 (commit af74a8c) by the harness of this protocol
(`python -m spectramaster.validation.round4_formats --collect`) and are kept in
`docs/baseline/after_R4C/round4_formats_before.json` (synthetic files, the test corpus, and only
names, sums, flags and count hashes of the EML/Sanderson reference spectra, which stay outside the
repository). The findings come from the fourth external review (Codex M4 and section 2, Gemini M2)
and were checked on the code first. The limits must not be changed after results are known. A result
outside a limit is reported as a failure.

## Findings and changes

1. **Non-finite channel contents (Codex).** A spectrum with one NaN or infinite channel gives no
   peaks at all, without a message. Change: the peak search refuses it (ValueError naming the
   non-finite channels); reading such a file still works and `convert.counts_note()` gives a note,
   shown in the status bar of the GUI and by `info` in the CLI. Writing was already refused.
2. **EML/Sanderson time channels (Gemini M2).** Channels 0 and 1 are taken as live and real time
   whenever channel 0 equals the header's `LT=`; a spectrum whose channel 0 holds as many counts as
   the live time loses its first two channels and gets a wrong real time. Change: they are taken as
   times only when, in addition, channel 1 is a possible real time, `LT <= channel 1 <= 2 LT` (dead
   time below 50 %); otherwise both are kept as counts and `extra["time_channels_note"]` says why.
3. **CHN with E = 1 keV x channel (Gemini M2).** A real calibration of exactly 0 + 1 keV x channel
   cannot be told apart from the placeholder of an uncalibrated MCA, so it reads back as uncalibrated;
   the write check said only "energy calibration not stored". Change: the warning says that a
   calibration of 0 + 1 keV per channel is read back as the placeholder of an uncalibrated MCA. The
   reading is not changed (deliberate since `placeholder_energy_calibration_protocol.md`).
4. **Format detection (Codex M4).** (a) A SpecUtils TXT file with the `.txt` extension is read as
   two-column ASCII and loses live and real time; change: the SpecUtils TXT test (first line
   `Original File Name:`) is preferred over the ASCII ones when both match. (b) A TKA file (live
   time, real time, then counts, one value per line) with another extension is read as one-column
   ASCII with the two times as counts; change: TKA gets a content test (one value per line, the first
   two `0 < LT <= RT <= 10 LT`), so such a file is "ambiguous" and the user chooses the format. A
   one-column file whose first channels are 0 is still one-column ASCII.

Not changed: Gemini's "any two-column table whose first column counts 0, 1, 2 ... is read as a
spectrum" - such a table has the layout of a channel/count spectrum and cannot be told apart from one.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RC.C1 | 2048-channel synthetic spectrum with one peak and one NaN (then one infinite) channel; the same spectrum without it | peak search raises ValueError mentioning non-finite channels for NaN and for infinity; the finite spectrum gives the same peaks as before; `counts_note` gives a note for the NaN spectrum and None for the finite one |
| RC.C2 | Gemini's case (LT 100, channel 0 = 100, channel 1 = 500); the IAEA ASCII .dat written by the program (LT 1000, RT 1100); the 38 EML/Sanderson reference files | Gemini's case: channels 0-3 read as 100, 500, 10, 20, real time 100, no time channels, a note naming channel 1; own .dat file as before (real time 1100); every EML file identical to before (channels, sum, live and real time, time-channel flag, hash of the counts) |
| RC.C3 | 1024-channel spectrum with E = 0 + 1 keV x channel, then 0 + 0.5 keV x channel, written to CHN and read back | 1 keV/ch: a warning containing "1 keV per channel", read-back coefficients as before; 0.5 keV/ch: warnings and coefficients as before |
| RC.C4 | SpecUtils TXT written with `.txt`; TKA renamed `.xyz`; one-column ASCII starting with two zero channels renamed `.xyz`; the any-extension collection (319 files: test corpus and one written file per format, own name, `.xyz` and no extension; negative files) | SpecUtils TXT read as SpecUtils TXT with live time 100, real time 110 and 15345 counts; TKA ambiguous between TKA and one-column ASCII; one-column file as before; every other file of the any-extension collection detected and read as before (only the written SpecUtils TXT file under its own name and the written TKA file renamed may change); negative files detected not more than before |
| RC.C5 | existing tests and the benchmark report | full test suite passes; benchmark PASS/FAIL counts unchanged (154 / 13) |

## Outputs

`docs/baseline/after_R4C/round4_formats.md` and `.json`, from
`python -m spectramaster.validation.round4_formats`.

## Limitations

- The dead-time bound of RC.C2 (50 %) is a judgement: an EML-style file with more dead time keeps
  its time channels as counts and says so.
- A TKA file whose first counts look like live and real time is still ambiguous with one-column
  ASCII; the user chooses.

---

## Results (after_R4C)

**First run: 2 PASS / 2 FAIL** (RC.C1 PASS, RC.C2 FAIL, RC.C3 PASS, RC.C4 FAIL). Both failures were
errors of the implementation, not of the criteria; the limits were not changed.

- RC.C2 FAIL: all 38 EML/Sanderson files changed, only 2 kept their time channels. In 36 of the
  EML TEST files channel 0 is the live time and channel 1 is 0 (real time not given), which the rule
  `LT <= channel 1 <= 2 LT` refused. Correction: channel 1 = 0 is also a time channel (real time
  taken equal to the live time, as before). This widens change 2 above to `channel 1 = 0, or
  LT <= channel 1 <= 2 LT`; Gemini's case (channel 1 = 500 with LT 100) is still read as counts.
- RC.C4 FAIL: the Laval ASCII file written by the program and renamed `.xyz` (or with no extension)
  became ambiguous between Laval and TKA, because the new TKA content test also matched it (blank
  lines are skipped). Correction: Laval is preferred over TKA when both content tests match, as it
  already was over one-column ASCII (`CONTENT_PREFERENCE`).

**Second run, with both corrections: 4 PASS / 0 FAIL** (`after_R4C/round4_formats.md`):

| ID | result | key numbers |
|---|---|---|
| RC.C1 | PASS | NaN and infinity: ValueError naming channel 300 (before: NaN returned 0 peaks silently); finite spectrum peaks unchanged; `counts_note` note for NaN, None for finite |
| RC.C2 | PASS | Gemini's case read as counts 100, 500, real time 100, note naming channel 1 (before: channels zeroed, real time 500); own IAEA .dat RT 1100 as before; 38 EML files identical, 36 with time channels |
| RC.C3 | PASS | 1 keV/ch: warning that 0 + 1 keV per channel reads back as an uncalibrated MCA; 0.5 keV/ch unchanged |
| RC.C4 | PASS | SpecUtils TXT `.txt` read as SpecUtils TXT, LT 100 / RT 110 (before: two-column ASCII, no times); TKA `.xyz` ambiguous TKA / one-column ASCII; one-column file starting with zeros still one-column ASCII; no other detection change; negative files detected 0 -> 0 |
| RC.C5 | PASS | full test suite passed (see below); benchmark 154 PASS / 13 FAIL / 60 REPORT, no criterion changed status (`after_R4C/baseline.md`) |

Engine version 1.17.0 (Sanderson time channels and format detection can change what an existing
file reads as).

# Spectrum writers: no silent change (pre-registered)

Written 2026-10-21, **before** the implementation. The rules and limits below must not be changed after
results are known. A result outside a limit is reported as a failure.

## Motivation (third external review, verified on `fdb12d6`, code unchanged since)

`convert.write_spectrum` reports what a format cannot hold through hand-kept lists
(`MAX_CAL_TERMS`, `INTEGER_COUNTS`, `CP1256_TEXT` ...). The reviews found changes that no list
covers:

- **Gemini H4.**
  - Calibration terms cut without a refit or a warning: `iec1455` (4 terms, -128 keV at channel 4000
    for a 5-term calibration) and `chandata_csv` (refitted to 3 terms on reading, -11 keV).
  - First channels set to zero: channels 0-1 in `iaea_ascii_dat`, `npl_ascii`, `norland5000`;
    channels 0-10 in `laval_ascii`; channels 0-15 in `jcac_vax`.
  - Energy calibration, live time or resolution calibration dropped by formats that do not store
    them.
  - Live time rounded to whole seconds.
  - A negative `first_channel` shifts all energies; a positive one changes the number of channels.
  - The detector field is not checked for Arabic text (Arabic-Indic digits become '?').
- **Codex M3.** Counts pass through single precision: 16777217 is written as 16777216 by N42-2012,
  SPE, PCF and CNF, and as 16777200 by N42-2006.
- **Codex M4.** A non-monotonic calibration `[0, 1, -0.01]` is replaced (N42) or dropped (CNF).
- **Codex M5.** A real start time 2000-01-01 00:00:00 reads back from CHN as unknown (it is the
  placeholder).

In every case the warnings were empty. Separately:

- **Codex M6.** The Aptec analysis readers (`analysis.aptec_s0.read_s0`, `analysis.aptec_roi`)
  accept any data starting with "VERSION", for example "VERSION 3.0" or "VERSION9.9", as a
  zero-channel file.
- **Gemini L1.** `formats/specutils_bridge.py` imports SpecUtils unguarded, so without it the pure-Python
  CHN and CNF readers and writers are not registered either.
- **README.** It states 59 formats (58 readable, 35 writable); the registry has 60 (59, 35).

## Change

- **R1. Read-back check.** After writing, `write_spectrum` reads the file back with the same format
  and compares it with what it meant to write (after the reported adjustments: rounding, refit,
  digits). Each difference not already reported becomes a warning that names it:
  - counts: exact for whole-number values, relative 1e-6 otherwise; the number of channels changed
    and the largest change are given;
  - number of channels and first channel;
  - energy at every stored channel, more than 0.001 keV apart, or the calibration not stored;
  - live time and real time (relative 1e-6), or not stored;
  - start time (1 s or more apart, or lost);
  - sample ID, description and detector (leading and trailing spaces ignored);
  - resolution calibration (relative 1e-9), or not stored.

  A file that cannot be read back gives the warning that it could not be checked. Nothing is
  refused by R1; it only reports.
- **R2.** `iec1455` (4 terms) and `chandata_csv` (3 terms) are added to `MAX_CAL_TERMS`, so the
  calibration is refitted before writing and the deviation reported, as for the other formats. The
  detector field joins the text checks (Arabic-Indic digits written as 0-9, with the warning).
- **R3.** The Aptec analysis readers accept only "VERSION6" files with at least one channel, a data
  block that fits the file, and non-negative record counts; anything else is refused.
- **R4.** SpecUtils is imported in a guard. Without it the CHN and CNF formats are still registered,
  the formats that need it are not, and a log message says why.
- **R5.** The README counts are corrected.

## Criteria

The test spectrum has 4096 channels, a count in every channel (the first 16 included) and one channel
of 16777217 counts. It has a 5-term calibration, live time 100.75 s and real time 120.25 s, a start
time of 2024-03-05 10:20:30, and a 3-term resolution calibration. The sample ID, description and
detector contain Arabic letters and Arabic-Indic digits.

| id | criterion | limit |
|---|---|---|
| FF.C1 | every writable format that can be read back, the test spectrum | 0 differences between written and read-back spectra that are not reported in the warnings |
| FF.C2 | the same with first channel -10 and +10, and with a start time of 2000-01-01 00:00:00 (M5) | 0 unreported differences |
| FF.C3 | write-only formats | each gives the "could not be checked" warning |
| FF.C4 | iec1455 and chandata_csv with the 5-term calibration | calibration refitted before writing, deviation reported |
| FF.C5 | Codex M4 case: calibration [0, 1, -0.01] | the change is reported for every format that changes it |
| FF.C6 | Aptec analysis readers: 1024 bytes beginning "VERSION 3.0", "VERSION9.9", and a VERSION6 header with 0 channels | refused (ValueError); the lab's real S0 files still read (tests that use them, where present) |
| FF.C7 | SpecUtils import blocked (a separate process) | ortec_chn and ci_cnf register and round-trip a spectrum; no other module fails to load |
| FF.C8 | README counts | equal to the registry |
| FF.C9 | benchmark `after_FC1` vs `after_TF1` | no PASS -> FAIL |

Every format's warnings for the test spectrum are listed in the results. The extra time taken by the
read-back is reported, with no limit. The analysis engine is not changed, so `ENGINE_VERSION` stays
1.4.0.

Results: appended below; `after_FC1` (the name was checked to be free).

## Results (2026-10-21)

The protocol's SHA-256 was recorded before the implementation (`b7588562...07aa3`). One correction was
made before any code: the baseline name was first written as `after_FF1`, which belongs to the second
review's format work. It was changed to `after_FC1` and the hash recorded again. The sections above
are otherwise unchanged. Tests: `tests/test_format_fidelity_check.py`. All 13 fail on the previous code
and pass now.

| id | result | status |
|---|---|---|
| FF.C1 | 33 readable writable formats, the test spectrum: 0 unreported differences (previous code: 158 in 30 formats) | PASS |
| FF.C2 | first channel -10: 0 (before 162 in 26 formats); +10: 0 (before 157 in 26); start time 2000-01-01: 0 (before 159 in 30) | PASS |
| FF.C3 | write-only formats (HTML) give "could not be checked" | PASS |
| FF.C4 | iec1455 refitted to 4 terms (max deviation 2.006 keV, reported); chandata_csv to 3 terms (15.37 keV, reported). Before: cut to 4 terms without a word (-128 keV at channel 4000), and refitted on reading without a word | PASS |
| FF.C5 | calibration [0, 1, -0.01]: 0 unreported differences (before 165 in 30 formats); the change is reported in every format that changes it | PASS |
| FF.C6 | "VERSION 3.0", "VERSION9.9" and a VERSION6 header with 0 channels refused by both readers; the 10 real S0 files of `C:\APTEC\APTEC` still read by both | PASS |
| FF.C7 | SpecUtils blocked: 33 formats registered, CHN and CNF written and read back, no other module failed | PASS |
| FF.C8 | README: 60 formats (59 readable, 35 writable), equal to the registry | PASS |
| FF.C9 | `after_FC1` vs `after_TF1`: 154 PASS / 13 FAIL / 60 REPORT, no PASS -> FAIL; only runtimes and the Sr-85/Fe-59 tie at the cut-off of one IDB list differ | PASS |

Counted by the test's own comparison: written and read-back spectra compared category by category
(channels, counts, energies, live and real time, start time, the three text fields, FWHM calibration),
each difference looked up in the warnings. The count was made with the previous `convert.py` and
with the new one.

**Time.** The read-back adds about 20 ms per file (33 formats: 0.3 s before, 0.9 s now).

**What the check reports for the test spectrum** (besides the existing warnings). These changes were
silent before:

- counts changed by single precision (the 16777217 channel): SPC, IAEA SPE, CNF, N42-2006/2012, PCF,
  SpecUtils CSV/TXT, TKA, SPC ASCII;
- first channels set to zero: iaea_ascii_dat and npl_ascii (2), laval_ascii (11), jcac_vax (16, plus the 16777217 channel);
- live and real time rounded to whole seconds: davidson_ascii, iaea_ascii_dat, npl_ascii, laval_ascii;
  CHN stores them in 20 ms steps (100.75 -> 100.76 s);
- energy calibration, live time, start time or text not stored by ASCII-1/2, IEEE ASCII, TKA,
  chandata_csv, SpecUtils CSV, NPL, Rump, JCAC; start time truncated to the date by Rump and Laval;
- FWHM calibration not stored by every format but JSON and Excel; changed by CHN;
- PCF and SPC ASCII: energies off by up to 140 keV for the 5-term calibration;
- Exploranium GR-130/135: rebinned to 256/1024 channels; a start time of 2000-01-01 reads back as
  1999-11-30 (a defect of those writers that no review had listed);
- a dropped negative first channel (-10) shifts the energies by up to 6 keV in CHN, SPC, CNF, SPE, N42
  and others.

The writers themselves are not changed. Each change is now reported; fixing the individual writers is
left for later.

**Existing tests changed.** `test_convert_text.py` looked for the word "ASCII" in any warning. The new
warnings carry the format's name ("ASCII-1 ..."), so the test now looks for the text warning itself
("stores only ASCII text"). `test_convert_calibration.py::test_no_warning_when_format_holds_calibration`
expected no warning from IAEA SPE. The read-back now reports that SPE stores the coefficients in single
precision (energies up to 0.004 keV apart over 8192 channels). The test now checks that there is no refit
warning, and that this is the only kind of warning.

**Engine version** stays 1.4.0 (no analysis result changes).

Full test suite: 1264 passed, 68 skipped.

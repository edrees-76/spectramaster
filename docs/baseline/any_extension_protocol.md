# Reading spectrum files with any extension: pre-registered protocol

Written 2026-10-21, before implementation. Results are appended below the line after the run;
nothing above it changes after its SHA-256 is recorded.

## 1. Defect

The user asked that a spectrum file be read whatever its extension. Measured on `origin/main`
(72636ef) by copying every corpus file and every file our writers produce to `probe.xyz` and to
`probe` (no extension), then auto-detecting and reading:

* 242 of 254 files detected under their own name are detected identically and read identically.
* 11 are no longer recognised. Their sniffers require the extension: ASCII-1, ASCII-2 and IEEE
  `.asc` (ascii_formats.py), Channel Data `.csv`, Wallac `.001`, Laval `.de?`, JCAC VAX `.spc`,
  Oxford `.ans` (aptec_import_*.py), and the corpus file `hdtv/.../1k.txt` (ASCII-1).
* 1 changes format: our `specutils_txt` output is ASCII-2 under `.txt` and SpecUtils text
  without it. Both read the same counts; this is unchanged by the work below and reported.
* Excel `.xlsx` is still detected but fails to read: `openpyxl.load_workbook(path)` refuses any
  file whose name does not end in `.xlsx`.
* Folder scans in the batch window (add folder) and folder drops on the main window keep only
  known extensions, with no way to include others. The folder-conversion dialog and the archive
  already have an "all files" option. Opening one file already offers "All files (*)", and the
  input format can already be forced by hand (GUI setting, CLI `-i`).

Why the gates exist (same measurement, each gated sniffer applied to content alone):

* Quantrad Scout `.sct` matched 32 of 204 ordinary text files of this repository (`*.py`,
  `docs/*.md`) and 40 spectra of other formats.
* Oxford `.ans` matched ORTEC `.spc`, SPC float and Canberra AccuSpec files.
* IEEE `.asc` (five numeric lines) matched almost every text spectrum.
* BTI and the weak APTEC ASCII variant matched files of other formats.
* Overlaps among the remaining tests: ASCII-1 / Wallac (and TKA, which has no sniffer at all);
  ASCII-2 / Channel Data CSV; IAEA ASCII `.dat` / EML Sanderson; ASCII-1 / Laval.

## 2. Change

1. `FormatSpec.content_sniffer`: an optional test on the content only, registered for the
   formats whose content test produced no false match in the measurement above:
   ascii1, ascii2, chandata_csv, eml_sanderson, iaea_ascii_dat, npl_ascii, wallac_ascii,
   laval_ascii, jcac_vax. The gated sniffers become "extension and content"; their behaviour
   with their own extension is unchanged. Wallac's content test is made stricter than its gated
   one: the file must have exactly 3 + 1024 non-empty lines (the layout the reader and writer
   use). Not registered: ieee_asc, quantrad_scout, oxford_ans, bti_ascii, the weak APTEC ASCII
   variant (false matches above), ci90_ascii and nucleus_pca (no sample file or writer, so no
   evidence either way), and the six formats without any sniffer (tka, labzy_lzs, caen_gxml,
   specutils_json, tracs_mps, aram).
2. `detect_format` runs exactly as before. Only when it finds nothing does a second stage
   collect every format whose content sniffer matches, then drop a candidate when a more
   specific one also matched (fixed pairs: chandata_csv over ascii2, iaea_ascii_dat over
   eml_sanderson, wallac_ascii over ascii1, laval_ascii over ascii1). One candidate left: it is
   used. Several left: no guess; `read_spectra` raises `FormatError` naming them and asking for
   the input format to be chosen. None: the existing "cannot recognise" error, which now also
   says the input format can be chosen by hand.
3. A spectrum read through the second stage records `extra["format_detection"] = "content"`
   and the format; the GUI and CLI show "format recognised from the content (NAME); choose the
   input format if this is wrong" wherever they already show read warnings.
4. Excel: the workbook is opened from a file object, so the name does not matter.
5. Batch "add folder" and folder drops on the main window add files with a known extension as
   before, plus files with any other extension that are recognised (both stages).

Known limit, stated now: a TKA file (live time, real time, counts, one number per line) with
another extension is read as ASCII-1, the two times becoming the first two channels; the note
of item 3 is shown. TKA cannot be told from ASCII-1 by content.

## 3. Criteria

Harness: `python -m spectramaster.validation.any_extension --src <code root> --out <folder>`. It
uses every corpus file in `test_corpus/catalog.csv`, one file written by every writable format
(1024 channels, counts `i mod 97`, calibration 0.5 + 0.3·ch, live 100 s, real 101 s,
sample id `S1`), and the negative set (every `spectramaster/**/*.py` and `docs/**/*.md`). A read
signature is, per spectrum: channel count, total counts, energy coefficients rounded to 1e-6,
live time; or the exception class. The "before" run uses an export of `origin/main` 72636ef.

| ID | Check | Limit |
|---|---|---|
| AX.C1 | Own name: detected format and read signature of every corpus and written file, before vs after | 0 differences |
| AX.C2 | `probe.xyz` and `probe`: every file whose own-name format is in the content set of §2.1, or is excel_xlsx, is detected as that format and reads with the own-name signature | 0 failures, both names. Excluded and reported: files whose own-name detection is itself a known misdetection (our iaea_ascii_dat output, detected as eml_sanderson before and after this change) |
| AX.C3 | Negative set as `.xyz` | 0 detected |
| AX.C4 | Files detected under their own name with a format outside the content set: detection with `.xyz` / no extension unchanged from before (the second stage only acts when the first finds nothing) | 0 differences |
| AX.C5 | Unit tests: content-detected spectrum carries the note; ambiguity raises `FormatError` naming the candidates; batch add-folder and folder drop include a recognised `.xyz` spectrum and skip an unrecognised `.xyz` file | pass |
| AX.C6 | Standard benchmark | 154 PASS / 13 FAIL / 60 REPORT, no PASS → FAIL |
| AX.C7 | Full test suite | passes; tests whose expected values are this defect are updated and listed |

Reported only: corpus files undetected under their own name and detected by the second stage
(format, whether they read); TKA and the other excluded formats with `.xyz`.

## 4. Outputs

`docs/baseline/after_AX1/`: `any_extension_before.json`, `any_extension_results.md/json`,
`baseline.md/json`. No laboratory data is used or copied.

---
## Results

(appended after the run)

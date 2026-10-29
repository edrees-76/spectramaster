# Round-7 review: tests and harnesses, Codex M2 / L1 and Gemini L3 (pre-registered)

Written 2026-10-29, before any change to the code or the tests. Codex and Gemini round-7 reviews
(`C:\Users\DELL\Downloads\codex_review_round7.md`, `gemini_review_round7.md`, main b3d88d1), findings
Codex M2, Codex L1 and Gemini L3, checked on main c942377. No calculation changes; ENGINE_VERSION is
not changed.

## Findings (checked on the code)

1. **Qt test process ends with a native abort (Codex M2).** `pytest tests/test_round6_quit.py
   tests/test_round6_threads.py tests/test_round5_worker_lifetime.py` prints "9 passed" and then the
   process ends with 0xC0000409 (Git Bash shows 127) in about half of the runs (observed: 4 of 8, then
   6 of 16 runs; PowerShell `$LASTEXITCODE` 0xC0000409 in 2 of 5). Diagnosis so far (scratchpad
   plugins, not committed):
   - at the end of the session 6 top-level widgets created by the tests are still alive
     (`BatchDialog`, `ReportBatchDialog`, `QCWindow`, `QFrame`); no QThread object is alive;
   - closing and deleting every remaining top-level widget, then delivering the deferred deletes,
     before the interpreter's teardown: 0 aborts in 10 runs;
   - doing it for one class only: `BatchDialog` 0 of 8 aborts; `QCWindow` 1 of 8, `ReportBatchDialog`
     3 of 8, `QFrame` 4 of 8, none 4 of 8; delivering the deferred deletes alone: 4 of 8;
   - giving `BatchDialog`'s table model a parent did not change it (6 of 16): not the cause;
   - the application itself (main window plus the batch conversion, batch report and QC windows
     opened, then the main window closed and the application quit, in its own process): 0 of 10
     abnormal ends.
   The object inside a left-open `BatchDialog` whose destruction during the interpreter's teardown
   aborts the process is **not identified**; the finding is a test-process defect, not observed in
   the application.
2. **`round6_inputs` RC.C5 fails on a re-run (Codex L1).** RC.C5 compares the clean spectrum's
   values as a whole, including the width note; R6-G (`round6_fwhm_protocol.md`) added the intended
   channel-binning note, so a re-run gives RC.C5 FAIL with every number identical. A re-run also
   writes over the committed results in `after_R6C`.
3. **Pure text parsers tested through a QApplication (Gemini L3).** `test_parse_counts_refuses` and
   `test_qc_activity` (`tests/test_round6_inputs.py`) request the `app` fixture although
   `parse_counts` and `_parse_activity` need no application (their modules import Qt, so the tests
   still need PySide6).

## Change

1. `tests/conftest.py`: at the end of the test session (`pytest_sessionfinish`, before the CI exit
   already there), every top-level widget still alive is closed and scheduled for deletion and the
   deferred deletes are delivered, so no Qt widget is left to the interpreter's teardown. Nothing is
   skipped; no result changes. Tests that create dialogs are not changed.
2. `validation/round6_inputs.py` RC.C5: the numbers of the clean spectrum (centroid, FWHM, FWTM,
   peak-to-Compton, net area, relative efficiency) are compared with the before values exactly, as
   registered; the width note separately: it must be the before note or the R6-G channel-binning
   note (starts with "FWHM", contains "overestimated by the channel binning" and ends with "not
   corrected"); the result names which. New option `--out DIR` writes a re-run's results elsewhere;
   the default stays `after_R6C`.
3. `tests/test_round6_inputs.py`: the two parser tests use `pytest.importorskip("PySide6")` instead
   of the `app` fixture.

## Criteria

| ID | quantity | limit |
|---|---|---|
| RT.C1 | the three Qt files above, 20 runs, exit code | before the change at least one run ends abnormally; after: 0 of 20 |
| RT.C2 | the application in its own process (script above), 10 runs | 0 of 10 abnormal ends, after the change as before |
| RT.C3 | `python -m spectramaster.validation.round6_inputs --out <tmp>` | 8 PASS / 0 FAIL, RC.C5 naming the R6-G note; the same run with the clean FWHM changed by 1e-9 keV in the measured values gives RC.C5 FAIL (numbers still compared exactly) |
| RT.C4 | the two parser tests in a process of their own | pass with no QApplication created (`QCoreApplication.instance()` is None during the test) |
| RT.C5 | benchmark (`after_R7F`: 154 PASS / 13 FAIL / 60 REPORT) and full test suite | no criterion changes state; suite passes and exits 0; each changed existing test listed |

## Limitations

- The fix removes the left-open widgets at the end of the test session; it does not identify the
  object inside `BatchDialog` whose late destruction aborts. A test that leaves a widget alive is
  still possible; it is no longer left to the interpreter.
- `test_timing_16k_channels` (1.0 s bound on a wall-clock time) can exceed its bound on a busy
  machine (R6-F, R7-F); the bound is not changed here.
- Other harnesses also write their results to their fixed folder when re-run; only `round6_inputs`
  gets `--out` here.

---

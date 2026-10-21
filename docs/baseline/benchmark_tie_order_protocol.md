# Deterministic tie order in the benchmark: pre-registered protocol

Written 2026-10-21, before implementation. This is the separate finding recorded under WP.C11 in
`window_polynomial_protocol.md`. Results are appended below the line after the run; nothing above
it changes after its SHA-256 is recorded.

## 1. Defect

`spectramaster/validation/benchmark.py` lists the 15 most frequent implausible IDB identifications
(`IDB.most_frequent_implausible`).

- It sorts by count only (`key=lambda kv: -kv[1]`).
- Equal counts keep insertion order. Insertion order comes from iterating a Python `set` of nuclide
  names, so it depends on the per-process string hash seed (`PYTHONHASHSEED`).
- Effect seen in after_WP1: the 15th entry was "HPGe Fe-59" (count 15), while after_AX1 had
  "HPGe Sr-85" (count 15). The counts were identical.
- So the same code and data can give a different benchmark report from one run to the next. The
  benchmark comparison "every value identical except runtimes" (used by most protocols) can fail
  for no engine reason.

## 2. Change

1. A helper `_top_counts(counts, n)` returns the n largest entries ordered by count descending, then
   by name ascending. `most_frequent_implausible` uses it.
2. Nothing else changes: no engine code, no identification, no limits, no `ENGINE_VERSION` change
   (the engine is untouched; this is the evaluation harness).

Other tie or set orders in the benchmark report are not changed by this protocol. If C1 finds one,
it is recorded as a FAIL and a further finding, not fixed in this run.

## 3. Criteria (set before the run)

Runs use the full benchmark (`python -m spectramaster.validation.benchmark`, default reference data)
on this branch. "Runtime fields" means `meta/utc`, `meta/wall_time_s`, `*/runtime/median_s`,
`*/runtime/max_s` and `*/identification/median_time_s`.

| id | what | limit |
|---|---|---|
| TO.C1 | two runs, `PYTHONHASHSEED=0` and `PYTHONHASHSEED=12345` | `baseline.json` identical except runtime fields |
| TO.C2 | run with `PYTHONHASHSEED=0` against after_WP1 | every value identical except runtime fields and `IDB/most_frequent_implausible` |
| TO.C3 | `most_frequent_implausible` against after_WP1 | 15 entries; the sequence of counts is identical; the entries with count > 15 are the same set; the order is count descending, then name ascending |
| TO.C4 | criteria totals | 154 PASS / 13 FAIL / 60 REPORT, no PASS -> FAIL |
| TO.C5 | unit tests of `_top_counts` (ties ordered by name, independent of insertion order, n larger than the dictionary) | pass |
| TO.C6 | full test suite | passes; changed existing tests listed with reasons |

**Reported, not a criterion:** which count-15 entry is 15th after the fix (the name-first entry
with count 15; it is not known before the run because entries below the top 15 are not stored).

Outputs go to a new folder `docs/baseline/after_TO1/` (`baseline.*` of the `PYTHONHASHSEED=0` run).

---
## Results

(appended after the run)

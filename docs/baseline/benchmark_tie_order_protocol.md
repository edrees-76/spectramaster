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

Run 2026-10-21, engine 1.9.0 (unchanged). The text above the line is unchanged (SHA-256 of the
pre-registered part still 712888703fbcefac8c479675e22914db7b6f5aa3944043b899061d7427878fcf). Outputs:
`docs/baseline/after_TO1/` (`baseline.*`, `PYTHONHASHSEED=0` run).

The comparison checks values and also the key order of every dictionary. The earlier "identical"
comparisons used Python `==` on dictionaries, which ignores key order.

| id | value | limit | result |
|---|---|---|---|
| TO.C1 seed 0 against seed 12345 | `most_frequent_implausible` identical, in the same order; 11 `identification/by_mixture/*/false_nuclides` dictionaries (NaI, NaI_4096) differ in key order only; the `HPGe.runtime` and `NaI.runtime` entries of `criteria` differ in value | identical except runtime fields | **FAIL as written** |
| TO.C2 seed 0 against after_WP1 | `most_frequent_implausible` (expected); 8 `false_nuclides` dictionaries differ in key order only; the two runtime criteria entries differ in value | identical except runtime fields and `most_frequent_implausible` | **FAIL as written** |
| TO.C3 `most_frequent_implausible` | 15 entries, counts identical, the 14 entries with count > 15 are the same set, order count then name | | PASS |
| TO.C4 criteria totals | 154 PASS / 13 FAIL / 60 REPORT, no PASS -> FAIL | | PASS |
| TO.C5 unit tests | `tests/test_benchmark_tie_order.py`, 3 passed | | PASS |
| TO.C6 full suite | 1366 passed, 69 skipped; no existing test changed | | PASS |

Reported: after the fix the 15th entry is "HPGe Fe-59" (count 15), and the three count-16 entries are
in name order (Bi-211, Eu-154, Pa-234).

**The two FAILs, recorded as they are.**

* **A second set order.** `false_nuclides` and `missed` per mixture are filled by iterating Python
  sets (`reported`, `present`), so their key order depends on the hash seed. The counts in them are
  identical in all three runs. §2 said such an order is recorded, not fixed in this run. It is a
  further finding.
* **Runtime criteria.** §3 lists runtime fields by path but leaves out the `HPGe.runtime` and
  `NaI.runtime` entries of `criteria`, which hold the same runtime medians. Their values differ
  between runs, as runtimes do. This is an omission in the protocol's list, not an engine
  difference. Their status is PASS in all three runs.

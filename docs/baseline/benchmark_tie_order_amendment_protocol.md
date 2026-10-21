# Deterministic tie order in the benchmark, amendment: pre-registered protocol

Written 2026-10-21, after the results of `benchmark_tie_order_protocol.md` and before this
implementation. Results are appended below the line after the run; nothing above it changes after
its SHA-256 is recorded.

## 1. Defect (found by TO.C1)

In `cat_identification` of `spectramaster/validation/benchmark.py`, the per-mixture
`false_nuclides` and `missed` dictionaries are filled by iterating Python sets (`reported`,
`present`). Their key order therefore depends on `PYTHONHASHSEED`. The counts are not affected.

## 2. Change

1. A helper `_by_name(counts)` returns the dictionary with keys in name order.
2. `false_nuclides` and `missed` use it.
3. Nothing else changes: no engine code, no limits, no `ENGINE_VERSION` change.

## 3. Runtime fields

The list in `benchmark_tie_order_protocol.md` §3 left out the `criteria` entries whose value is a
runtime median. Here "runtime fields" means that list plus the `value` of the `criteria` entries
`HPGe.runtime` and `NaI.runtime`. Their `status` is still compared. This is stated before the run.
TO.C1 and TO.C2 stay FAIL as written.

## 4. Criteria (set before the run)

The comparison checks values and the key order of every dictionary. Runs use the full benchmark on
this branch.

| id | what | limit |
|---|---|---|
| TA.C1 | two new runs, `PYTHONHASHSEED=0` and `PYTHONHASHSEED=12345` | `baseline.json` identical, key order included, except runtime fields |
| TA.C2 | run with `PYTHONHASHSEED=0` against after_TO1 | every value identical except runtime fields; the only key-order differences are in `false_nuclides` and `missed`, and every such dictionary is in name order |
| TA.C3 | criteria totals | 154 PASS / 13 FAIL / 60 REPORT, no PASS -> FAIL |
| TA.C4 | unit test of `_by_name` (order independent of insertion order, counts unchanged) | passes |
| TA.C5 | full test suite | passes; changed existing tests listed with reasons |

If TA.C1 finds another order that depends on the hash seed, it is recorded as a FAIL and a further
finding, not fixed in this run.

Outputs go to a new folder `docs/baseline/after_TO2/` (`baseline.*` of the `PYTHONHASHSEED=0` run).

---
## Results

(appended after the run)
